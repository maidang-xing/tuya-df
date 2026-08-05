"""Tests for client.py — API client, CSRF, rate limiting, error handling."""

import json
import time
import pytest
import responses
from unittest.mock import patch, MagicMock

from tuya_df.config import Credentials
from tuya_df.client import DiscourseClient, DiscourseError


BASE_URL = "https://forum.example.com"


@pytest.fixture
def cookie_client(tmp_config_dir):
    """Client with cookie-based auth."""
    return DiscourseClient(Credentials(
        forum_url=BASE_URL,
        cookies={"_t": "test_cookie", "_forum_session": "session_cookie"},
    ))


@pytest.fixture
def api_key_client():
    """Client with API key auth."""
    return DiscourseClient(Credentials(
        forum_url=BASE_URL,
        api_key="test_key",
        api_username="testuser",
    ))


class TestClientInit:
    def test_api_key_headers_set(self, api_key_client):
        assert "Api-Key" in api_key_client._session.headers
        assert "Api-Username" in api_key_client._session.headers

    def test_cookie_mode_no_api_headers(self, cookie_client):
        assert "Api-Key" not in cookie_client._session.headers

    def test_base_url_strips_trailing_slash(self):
        client = DiscourseClient(Credentials(forum_url="https://f.com/", api_key="k"))
        assert client.base_url == "https://f.com"

    def test_cookie_domain_extracted(self, cookie_client):
        domain = cookie_client._extract_domain()
        assert domain == "forum.example.com"


class TestCsrfHandling:
    @responses.activate
    def test_csrf_fetched_on_first_write(self, cookie_client):
        responses.add(
            responses.GET,
            f"{BASE_URL}/session/csrf.json",
            json={"csrf": "csrf_token_123"},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/posts.json",
            json={"topic_id": 1, "post_number": 1},
            status=200,
        )

        cookie_client.create_topic("Title", "Body", 9)

        # CSRF should have been fetched
        assert cookie_client._csrf_token == "csrf_token_123"
        # CSRF token should be in the POST request headers
        post_request = responses.calls[-1].request
        assert post_request.headers.get("X-CSRF-Token") == "csrf_token_123"

    @responses.activate
    def test_csrf_not_fetched_for_api_key_mode(self, api_key_client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/posts.json",
            json={"topic_id": 1, "post_number": 1},
            status=200,
        )

        api_key_client.create_topic("Title", "Body", 9)
        assert api_key_client._csrf_token is None


class TestRateLimiting:
    @responses.activate
    def test_429_retries_with_backoff(self, cookie_client, monkeypatch):
        # Mock time.sleep to avoid real delays
        sleep_calls = []
        monkeypatch.setattr("tuya_df.client.time.sleep", lambda x: sleep_calls.append(x))

        responses.add(
            responses.GET,
            f"{BASE_URL}/session/csrf.json",
            json={"csrf": "token"},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/posts.json",
            json={"errors": ["rate limited"]},
            status=429,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/posts.json",
            json={"errors": ["rate limited"]},
            status=429,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/posts.json",
            json={"topic_id": 1, "post_number": 1},
            status=200,
        )

        result = cookie_client.create_topic("Title", "Body", 9)
        assert result["topic_id"] == 1
        # Should have retried twice (5s, 10s backoff)
        assert len(sleep_calls) >= 2
        assert sleep_calls[0] == 5  # BACKOFF_BASE * 2^0

    @responses.activate
    def test_429_max_retries_exhausted(self, cookie_client, monkeypatch):
        monkeypatch.setattr("tuya_df.client.time.sleep", lambda x: None)
        monkeypatch.setattr("tuya_df.client.DiscourseClient.MIN_REQUEST_GAP", 0.0)

        responses.add(
            responses.GET,
            f"{BASE_URL}/session/csrf.json",
            json={"csrf": "token"},
            status=200,
        )
        for _ in range(3):
            responses.add(
                responses.POST,
                f"{BASE_URL}/posts.json",
                json={"errors": ["rate limited"]},
                status=429,
            )

        # After exhausting retries, the last 429 response is processed as an error
        with pytest.raises(DiscourseError, match="rate limited"):
            cookie_client.create_topic("Title", "Body", 9)


class TestThrottleWrites:
    def test_write_requests_throttled(self, api_key_client, monkeypatch):
        monkeypatch.setattr("tuya_df.client.DiscourseClient.MIN_REQUEST_GAP", 0.1)

        sleep_calls = []
        monkeypatch.setattr("tuya_df.client.time.sleep", lambda x: sleep_calls.append(x))

        # First write — no delay (last_write_time is 0)
        api_key_client._throttle_writes("POST")
        assert len(sleep_calls) == 0

        # Second write immediately — should sleep
        api_key_client._throttle_writes("POST")
        assert len(sleep_calls) == 1
        assert sleep_calls[0] > 0

    def test_get_not_throttled(self, api_key_client, monkeypatch):
        sleep_calls = []
        monkeypatch.setattr("tuya_df.client.time.sleep", lambda x: sleep_calls.append(x))

        api_key_client._throttle_writes("GET")
        api_key_client._throttle_writes("GET")

        assert len(sleep_calls) == 0


class TestErrorHandling:
    @responses.activate
    def test_session_expired_error(self, cookie_client, monkeypatch):
        monkeypatch.setattr("tuya_df.client.DiscourseClient.MIN_REQUEST_GAP", 0.0)

        responses.add(
            responses.GET,
            f"{BASE_URL}/session/csrf.json",
            json={"csrf": "token"},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/posts.json",
            json={"errors": ["You need to be logged in to do that."], "error_type": "not_logged_in"},
            status=403,
        )

        with pytest.raises(DiscourseError, match="Session expired"):
            cookie_client.create_topic("Title", "Body", 9)

    @responses.activate
    def test_silenced_user_error(self, api_key_client, monkeypatch):
        monkeypatch.setattr("tuya_df.client.DiscourseClient.MIN_REQUEST_GAP", 0.0)

        responses.add(
            responses.POST,
            f"{BASE_URL}/posts.json",
            json={"errors": ["This user has been silenced."]},
            status=403,
        )

        with pytest.raises(DiscourseError, match="silenced or suspended"):
            api_key_client.create_topic("Title", "Body", 9)

    @responses.activate
    def test_generic_api_error(self, api_key_client, monkeypatch):
        monkeypatch.setattr("tuya_df.client.DiscourseClient.MIN_REQUEST_GAP", 0.0)

        responses.add(
            responses.POST,
            f"{BASE_URL}/posts.json",
            json={"errors": ["Title is too short"]},
            status=422,
        )

        with pytest.raises(DiscourseError, match="Title is too short"):
            api_key_client.create_topic("T", "Body", 9)

    @responses.activate
    def test_network_error(self, api_key_client):
        import requests as req

        with patch.object(api_key_client._session, "request", side_effect=req.ConnectionError("DNS failed")):
            with pytest.raises(DiscourseError, match="Network error"):
                api_key_client.get("/latest.json")


class TestPublicAPI:
    @responses.activate
    def test_create_topic(self, api_key_client, monkeypatch):
        monkeypatch.setattr("tuya_df.client.DiscourseClient.MIN_REQUEST_GAP", 0.0)

        responses.add(
            responses.POST,
            f"{BASE_URL}/posts.json",
            json={"topic_id": 42, "post_number": 1},
            status=200,
        )

        result = api_key_client.create_topic("Hello", "Body text here", 9, ["tag1", "tag2"])

        assert result["topic_id"] == 42
        body = responses.calls[0].request.body
        if isinstance(body, bytes):
            body = body.decode()
        assert "title=Hello" in body
        assert "category=9" in body
        assert "tags=tag1%2Ctag2" in body or "tags=tag1,tag2" in body

    @responses.activate
    def test_create_post_reply(self, api_key_client, monkeypatch):
        monkeypatch.setattr("tuya_df.client.DiscourseClient.MIN_REQUEST_GAP", 0.0)

        responses.add(
            responses.POST,
            f"{BASE_URL}/posts.json",
            json={"topic_id": 33, "post_number": 2},
            status=200,
        )

        result = api_key_client.create_post(33, "Reply text")
        assert result["post_number"] == 2

    @responses.activate
    def test_get_latest_topics(self, api_key_client):
        responses.add(
            responses.GET,
            f"{BASE_URL}/latest.json",
            json={"topic_list": {"topics": [{"id": 1, "title": "Test"}]}},
            status=200,
        )

        result = api_key_client.get_latest_topics(limit=5)
        assert len(result["topic_list"]["topics"]) == 1

    @responses.activate
    def test_get_categories(self, api_key_client, sample_categories):
        responses.add(
            responses.GET,
            f"{BASE_URL}/categories.json",
            json=sample_categories,
            status=200,
        )

        result = api_key_client.get_categories()
        assert len(result["category_list"]["categories"]) == 5

    @responses.activate
    def test_upload_file(self, api_key_client, sample_upload_response, monkeypatch):
        monkeypatch.setattr("tuya_df.client.DiscourseClient.MIN_REQUEST_GAP", 0.0)

        responses.add(
            responses.POST,
            f"{BASE_URL}/uploads.json",
            json=sample_upload_response,
            status=200,
        )

        result = api_key_client.upload_file("test.png", b"fake_image_data", "image/png")
        assert result["short_url"] == "upload://abc123.png"

    @responses.activate
    def test_search(self, api_key_client):
        responses.add(
            responses.GET,
            f"{BASE_URL}/search.json",
            json={"topics": [{"id": 1, "title": "Match"}]},
            status=200,
        )

        result = api_key_client.search("hello")
        assert "topics" in result
