"""Tests for post.py — category resolution, topic ID parsing, body assembly."""

import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from tuya_df.commands.post import (
    resolve_category,
    resolve_topic_id,
    process_attachments,
    get_body,
)
from tuya_df.client import DiscourseError
from tuya_df.cli import main


class TestResolveCategory:
    def test_numeric_id(self, mock_client):
        assert resolve_category(mock_client, "9") == 9

    def test_numeric_id_string(self, mock_client):
        assert resolve_category(mock_client, "11") == 11

    def test_exact_slug(self, mock_client, sample_categories):
        mock_client.get_categories.return_value = sample_categories
        assert resolve_category(mock_client, "show-tell") == 9
        assert resolve_category(mock_client, "develop-questions") == 8

    def test_fuzzy_name_single_match(self, mock_client, sample_categories):
        mock_client.get_categories.return_value = sample_categories
        assert resolve_category(mock_client, "show") == 9
        assert resolve_category(mock_client, "learn") == 11

    def test_fuzzy_name_multiple_matches_raises(self, mock_client, sample_categories):
        mock_client.get_categories.return_value = sample_categories
        # "e" matches multiple categories
        import click
        with pytest.raises(click.ClickException, match="Ambiguous"):
            resolve_category(mock_client, "e")

    def test_not_found_raises(self, mock_client, sample_categories):
        mock_client.get_categories.return_value = sample_categories
        import click
        with pytest.raises(click.ClickException, match="not found"):
            resolve_category(mock_client, "nonexistent")


class TestResolveTopicId:
    def test_numeric_id(self, mock_client):
        assert resolve_topic_id("33", mock_client) == 33

    def test_url_format(self, mock_client):
        url = "https://forum.example.com/t/some-topic-title/42"
        assert resolve_topic_id(url, mock_client) == 42

    def test_url_with_slug(self, mock_client):
        url = "https://forum-tuyaopen.discourse.group/t/topic/100"
        assert resolve_topic_id(url, mock_client) == 100

    def test_invalid_input_raises(self, mock_client):
        import click
        with pytest.raises(click.ClickException, match="Cannot parse"):
            resolve_topic_id("not-a-number-or-url", mock_client)


class TestProcessAttachments:
    def test_successful_uploads(self, mock_client, sample_upload_response, tmp_path):
        # Create test files
        img = tmp_path / "photo.png"
        img.write_bytes(b"fake_png_data")
        vid = tmp_path / "demo.mp4"
        vid.write_bytes(b"fake_video_data")

        mock_client.upload_file.return_value = sample_upload_response

        markdown, all_ok = process_attachments(
            mock_client,
            [str(img), str(vid)],
            json_output=False,
        )

        assert all_ok is True
        assert "![photo](upload://abc123.png)" in markdown
        assert "<video" in markdown

    def test_upload_failure_continues(self, mock_client, sample_upload_response, tmp_path):
        img1 = tmp_path / "good.png"
        img1.write_bytes(b"data1")
        img2 = tmp_path / "bad.png"
        img2.write_bytes(b"data2")

        # First upload succeeds, second fails
        mock_client.upload_file.side_effect = [sample_upload_response, DiscourseError("Upload failed")]

        markdown, all_ok = process_attachments(
            mock_client,
            [str(img1), str(img2)],
            json_output=False,
        )

        assert all_ok is False
        assert "![good](upload://abc123.png)" in markdown

    def test_file_too_large_skipped(self, mock_client, tmp_path):
        big_file = tmp_path / "huge.mp4"
        big_file.write_bytes(b"x" * (601 * 1024 * 1024))  # > 500MB limit

        markdown, all_ok = process_attachments(
            mock_client,
            [str(big_file)],
            json_output=False,
        )

        assert all_ok is False
        assert markdown == ""
        mock_client.upload_file.assert_not_called()

    def test_no_attachments_returns_empty(self, mock_client):
        markdown, all_ok = process_attachments(mock_client, [], json_output=False)
        assert markdown == ""
        assert all_ok is True


class TestGetBody:
    def test_body_from_string(self):
        assert get_body("Title", "Hello world", None) == "Hello world"

    def test_body_from_file(self, tmp_path):
        body_file = tmp_path / "post.md"
        body_file.write_text("This is the body from file.")

        assert get_body("Title", None, str(body_file)) == "This is the body from file."

    def test_body_file_strips_whitespace(self, tmp_path):
        body_file = tmp_path / "post.md"
        body_file.write_text("  \n  Content here  \n  ")

        assert get_body("Title", None, str(body_file)) == "Content here"


class TestPostCreateCLI:
    def test_create_post_success(self, mock_client, sample_categories, sample_topic_response):
        runner = CliRunner()
        mock_client.get_categories.return_value = sample_categories
        mock_client.create_topic.return_value = sample_topic_response
        mock_client.get.return_value = {"current_user": {"trust_level": 2}}

        with patch("tuya_df.commands.post.get_client", return_value=mock_client):
            result = runner.invoke(main, [
                "post", "create", "--title", "Test Post", "--body", "Hello world body",
                "--category", "show-tell",
            ])

        assert result.exit_code == 0
        assert "✅ Topic created successfully" in result.output
        mock_client.create_topic.assert_called_once()

    def test_create_post_enqueued(self, mock_client, sample_categories, sample_enqueued_response):
        runner = CliRunner()
        mock_client.get_categories.return_value = sample_categories
        mock_client.create_topic.return_value = sample_enqueued_response
        mock_client.get.return_value = {"current_user": {"trust_level": 2}}

        with patch("tuya_df.commands.post.get_client", return_value=mock_client):
            result = runner.invoke(main, [
                "post", "create", "--title", "Test", "--body", "Body",
                "--category", "show-tell",
            ])

        assert result.exit_code == 0
        assert "awaiting moderator approval" in result.output


class TestPostReplyCLI:
    def test_reply_success(self, mock_client, sample_topic_response):
        runner = CliRunner()
        mock_client.create_post.return_value = {
            "topic_id": 33,
            "post_number": 2,
        }

        with patch("tuya_df.commands.post.get_client", return_value=mock_client):
            result = runner.invoke(main, [
                "post", "reply", "33", "--body", "Thanks for sharing!",
            ])

        assert result.exit_code == 0
        assert "✅ Reply posted" in result.output
        mock_client.create_post.assert_called_once_with(33, "Thanks for sharing!")


class TestPostListCLI:
    def test_list_topics(self, mock_client, sample_topics):
        runner = CliRunner()
        mock_client.get_latest_topics.return_value = sample_topics

        with patch("tuya_df.commands.post.get_client", return_value=mock_client):
            result = runner.invoke(main, ["post", "list"])

        assert result.exit_code == 0
        assert "First Topic" in result.output
        assert "Second Topic" in result.output

    def test_list_empty_topics(self, mock_client):
        runner = CliRunner()
        mock_client.get_latest_topics.return_value = {
            "topic_list": {"topics": []}
        }

        with patch("tuya_df.commands.post.get_client", return_value=mock_client):
            result = runner.invoke(main, ["post", "list"])

        assert result.exit_code == 0
        assert "No topics found" in result.output
