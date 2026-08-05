"""Shared pytest fixtures for tuya-df tests."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from tuya_df.config import Credentials


@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """Redirect config directory to a temp path for isolation."""
    config_dir = tmp_path / "tuya-df-config"
    monkeypatch.setattr("tuya_df.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("tuya_df.config.SESSION_FILE", config_dir / "session.json")
    monkeypatch.setattr("tuya_df.config.CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr("tuya_df.auth.SESSION_FILE", config_dir / "session.json")
    monkeypatch.setattr("tuya_df.auth.CONFIG_DIR", config_dir)
    return config_dir


@pytest.fixture
def cookie_credentials():
    """Credentials using cookie-based session auth."""
    return Credentials(
        forum_url="https://forum.example.com",
        cookies={"_t": "cookie_t_value", "_forum_session": "session_value"},
    )


@pytest.fixture
def api_key_credentials():
    """Credentials using API key auth."""
    return Credentials(
        forum_url="https://forum.example.com",
        api_key="test_api_key_12345",
        api_username="testuser",
    )


@pytest.fixture
def mock_client():
    """A fully mocked DiscourseClient that never makes real HTTP calls."""
    client = MagicMock()
    client.base_url = "https://forum.example.com"
    client.credentials.is_cookie = False
    client.credentials.is_api_key = True
    return client


@pytest.fixture
def sample_categories():
    """Sample Discourse categories response."""
    return {
        "category_list": {
            "categories": [
                {"id": 6, "name": "Announcement", "slug": "announcement"},
                {"id": 7, "name": "Events & Contests", "slug": "events-contests"},
                {"id": 8, "name": "Develop & Questions", "slug": "develop-questions"},
                {"id": 9, "name": "Show & Tell", "slug": "show-tell"},
                {"id": 11, "name": "Learn & Tutorials", "slug": "learn-tutorials"},
            ]
        }
    }


@pytest.fixture
def sample_topics():
    """Sample Discourse latest topics response."""
    return {
        "topic_list": {
            "topics": [
                {"id": 33, "title": "First Topic", "posts_count": 2, "views": 15, "like_count": 3, "created_at": "2026-08-01T10:00:00Z"},
                {"id": 28, "title": "Second Topic", "posts_count": 1, "views": 5, "like_count": 0, "created_at": "2026-08-02T12:00:00Z"},
            ]
        }
    }


@pytest.fixture
def sample_upload_response():
    """Sample Discourse upload response."""
    return {
        "id": 42,
        "url": "/uploads/default/original/3X/a/b/abc123.png",
        "short_url": "upload://abc123.png",
        "thumbnail_url": "/uploads/default/optimized/3X/a/b/abc123_optimized.png",
    }


@pytest.fixture
def sample_topic_response():
    """Sample Discourse topic creation response."""
    return {
        "id": 100,
        "topic_id": 50,
        "post_number": 1,
        "topic_slug": "hello-world",
    }


@pytest.fixture
def sample_enqueued_response():
    """Sample Discourse response when post is enqueued for moderation."""
    return {
        "action": "enqueued",
        "pending_post": {
            "id": 1,
            "title": "Test",
        },
    }
