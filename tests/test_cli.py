"""Tests for CLI integration — categories, upload, auth commands."""

import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from tuya_df.cli import main
from tuya_df.client import DiscourseError
from tuya_df.config import AuthError


class TestCategoriesCommand:
    def test_categories_human_output(self, mock_client, sample_categories):
        runner = CliRunner()
        mock_client.get_categories.return_value = sample_categories

        with patch("tuya_df.commands.categories.get_client", return_value=mock_client):
            result = runner.invoke(main, ["categories"])

        assert result.exit_code == 0
        assert "Announcement" in result.output
        assert "Show & Tell" in result.output
        assert "ID" in result.output

    def test_categories_json_output(self, mock_client, sample_categories):
        runner = CliRunner()
        mock_client.get_categories.return_value = sample_categories

        with patch("tuya_df.commands.categories.get_client", return_value=mock_client):
            result = runner.invoke(main, ["--json", "categories"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 5
        assert data[0]["id"] in (6, 7, 8, 9, 11)

    def test_categories_no_auth_falls_back(self, sample_categories):
        """Categories should work without auth (public endpoint)."""
        runner = CliRunner()

        mock_anon_client = MagicMock()
        mock_anon_client.get_categories.return_value = sample_categories

        with patch("tuya_df.commands.categories.get_client", side_effect=AuthError("no auth")):
            with patch("tuya_df.client.DiscourseClient", return_value=mock_anon_client):
                result = runner.invoke(main, ["categories"])

        assert result.exit_code == 0
        assert "Announcement" in result.output


class TestUploadCommand:
    def test_upload_image_success(self, mock_client, sample_upload_response, tmp_path):
        runner = CliRunner()
        img = tmp_path / "photo.png"
        img.write_bytes(b"fake_png")

        mock_client.upload_file.return_value = sample_upload_response

        with patch("tuya_df.commands.upload.get_client", return_value=mock_client):
            result = runner.invoke(main, ["upload", str(img)])

        assert result.exit_code == 0
        assert "upload://abc123.png" in result.output
        assert "image" in result.output

    def test_upload_json_output(self, mock_client, sample_upload_response, tmp_path):
        runner = CliRunner()
        img = tmp_path / "photo.png"
        img.write_bytes(b"data")

        mock_client.upload_file.return_value = sample_upload_response

        with patch("tuya_df.commands.upload.get_client", return_value=mock_client):
            result = runner.invoke(main, ["--json", "upload", str(img)])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["short_url"] == "upload://abc123.png"
        assert data["type"] == "image"

    def test_upload_file_too_large(self, mock_client, tmp_path):
        runner = CliRunner()
        big_file = tmp_path / "huge.mp4"
        big_file.write_bytes(b"x" * (601 * 1024 * 1024))

        with patch("tuya_df.commands.upload.get_client", return_value=mock_client):
            result = runner.invoke(main, ["upload", str(big_file)])

        assert result.exit_code == 1
        assert "too large" in result.output.lower()
        mock_client.upload_file.assert_not_called()

    def test_upload_api_error(self, mock_client, tmp_path):
        runner = CliRunner()
        img = tmp_path / "photo.png"
        img.write_bytes(b"data")

        mock_client.upload_file.side_effect = DiscourseError("Not allowed", status_code=422)

        with patch("tuya_df.commands.upload.get_client", return_value=mock_client):
            result = runner.invoke(main, ["upload", str(img)])

        assert result.exit_code == 4
        assert "Not allowed" in result.output

    def test_upload_nonexistent_file(self):
        runner = CliRunner()
        result = runner.invoke(main, ["upload", "/nonexistent/file.png"])
        assert result.exit_code != 0


class TestAuthCommands:
    def test_auth_status_not_authenticated(self, tmp_config_dir, monkeypatch):
        runner = CliRunner()
        monkeypatch.delenv("TUYA_DF_API_KEY", raising=False)
        monkeypatch.delenv("TUYA_DF_API_USERNAME", raising=False)

        result = runner.invoke(main, ["auth", "status"])

        assert result.exit_code == 2
        assert "Not authenticated" in result.output

    def test_auth_status_with_env_key(self, tmp_config_dir, monkeypatch):
        runner = CliRunner()
        monkeypatch.setenv("TUYA_DF_API_KEY", "test_key")
        monkeypatch.setenv("TUYA_DF_API_USERNAME", "testuser")

        result = runner.invoke(main, ["auth", "status"])

        assert result.exit_code == 0
        assert "testuser" in result.output
        assert "API Key" in result.output

    def test_auth_status_with_session(self, tmp_config_dir, monkeypatch):
        from tuya_df.auth import save_session
        runner = CliRunner()

        monkeypatch.delenv("TUYA_DF_API_KEY", raising=False)
        monkeypatch.delenv("TUYA_DF_API_USERNAME", raising=False)

        save_session(
            [{"name": "_t", "value": "cookie", "domain": ".example.com"}],
            "browseruser",
        )

        result = runner.invoke(main, ["auth", "status"])

        assert result.exit_code == 0
        assert "browseruser" in result.output
        assert "Browser Session" in result.output

    def test_auth_status_json_not_authenticated(self, tmp_config_dir, monkeypatch):
        runner = CliRunner()
        monkeypatch.delenv("TUYA_DF_API_KEY", raising=False)

        result = runner.invoke(main, ["--json", "auth", "status"])

        # JSON mode outputs the status without exiting with error code
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["authenticated"] is False

    def test_auth_logout_clears_session(self, tmp_config_dir, monkeypatch):
        from tuya_df.auth import save_session, is_authenticated
        runner = CliRunner()

        monkeypatch.delenv("TUYA_DF_API_KEY", raising=False)
        save_session(
            [{"name": "_t", "value": "cookie", "domain": ".example.com"}],
            "user",
        )
        assert is_authenticated() is True

        result = runner.invoke(main, ["auth", "logout"])

        assert result.exit_code == 0
        assert "Session cleared" in result.output
        assert is_authenticated() is False


class TestGlobalOptions:
    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "tuya-df" in result.output
        assert "auth" in result.output
        assert "post" in result.output
        assert "upload" in result.output
        assert "categories" in result.output

    def test_unknown_command(self):
        runner = CliRunner()
        result = runner.invoke(main, ["nonexistent"])
        assert result.exit_code != 0
