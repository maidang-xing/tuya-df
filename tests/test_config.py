"""Tests for config.py — credentials resolution, session management."""

import json
import os
import pytest
from pathlib import Path

from tuya_df.config import (
    AuthError,
    Credentials,
    SESSION_FILE,
    CONFIG_FILE,
    get_forum_url,
    save_config,
    load_session_cookies,
    get_session_username,
    resolve_credentials,
)
from tuya_df.auth import save_session, clear_session, is_authenticated


class TestCredentials:
    def test_api_key_mode(self):
        creds = Credentials(forum_url="https://f.com", api_key="key123", api_username="user")
        assert creds.is_api_key is True
        assert creds.is_cookie is False
        assert creds.headers() == {"Api-Key": "key123", "Api-Username": "user"}

    def test_cookie_mode(self):
        creds = Credentials(forum_url="https://f.com", cookies={"_t": "abc"})
        assert creds.is_api_key is False
        assert creds.is_cookie is True
        assert creds.headers() == {}

    def test_empty_credentials(self):
        creds = Credentials(forum_url="https://f.com")
        assert creds.is_api_key is False
        assert creds.is_cookie is False
        assert creds.headers() == {}


class TestSessionManagement:
    def test_save_and_load_session(self, tmp_config_dir):
        cookies = [
            {"name": "_t", "value": "abc123", "domain": ".example.com"},
            {"name": "_forum_session", "value": "xyz", "domain": ".example.com"},
            {"name": "other", "value": "foo", "domain": ".example.com"},
        ]
        save_session(cookies, username="testuser")

        loaded = load_session_cookies()
        assert loaded is not None
        assert loaded["_t"] == "abc123"
        assert loaded["_forum_session"] == "xyz"
        assert loaded["other"] == "foo"

        assert get_session_username() == "testuser"
        assert is_authenticated() is True

    def test_clear_session(self, tmp_config_dir):
        save_session([{"name": "_t", "value": "abc", "domain": ".example.com"}], "user")
        assert is_authenticated() is True

        clear_session()
        assert is_authenticated() is False
        assert load_session_cookies() is None

    def test_load_session_missing_file(self, tmp_config_dir):
        assert load_session_cookies() is None
        assert get_session_username() == ""
        assert is_authenticated() is False

    def test_load_session_corrupt_file(self, tmp_config_dir):
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_FILE.write_text("not json")
        assert load_session_cookies() is None


class TestForumUrl:
    def test_default_url(self, tmp_config_dir):
        assert get_forum_url() == "https://forum-tuyaopen.discourse.group"

    def test_custom_url(self, tmp_config_dir):
        save_config(forum_url="https://custom.forum.com")
        assert get_forum_url() == "https://custom.forum.com"

    def test_corrupt_config_falls_back(self, tmp_config_dir):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text("broken")
        assert get_forum_url() == "https://forum-tuyaopen.discourse.group"


class TestResolveCredentials:
    def test_priority_cli_flag_over_env(self, tmp_config_dir, monkeypatch):
        # Set up env vars
        monkeypatch.setenv("TUYA_DF_API_KEY", "env_key")
        monkeypatch.setenv("TUYA_DF_API_USERNAME", "env_user")

        # CLI flag should win
        creds = resolve_credentials(cli_api_key="cli_key", cli_api_username="cli_user")
        assert creds.api_key == "cli_key"
        assert creds.api_username == "cli_user"

    def test_priority_env_over_session(self, tmp_config_dir, monkeypatch):
        # Save a browser session
        save_session(
            [{"name": "_t", "value": "cookie_val", "domain": ".example.com"}],
            "cookie_user",
        )

        # Env var should win over session
        monkeypatch.setenv("TUYA_DF_API_KEY", "env_key")
        monkeypatch.setenv("TUYA_DF_API_USERNAME", "env_user")

        creds = resolve_credentials()
        assert creds.is_api_key is True
        assert creds.api_key == "env_key"

    def test_priority_session_when_no_env(self, tmp_config_dir, monkeypatch):
        monkeypatch.delenv("TUYA_DF_API_KEY", raising=False)
        monkeypatch.delenv("TUYA_DF_API_USERNAME", raising=False)

        save_session(
            [{"name": "_t", "value": "cookie_val", "domain": ".example.com"}],
            "cookie_user",
        )

        creds = resolve_credentials()
        assert creds.is_cookie is True
        assert creds.cookies["_t"] == "cookie_val"

    def test_no_credentials_raises(self, tmp_config_dir, monkeypatch):
        monkeypatch.delenv("TUYA_DF_API_KEY", raising=False)
        monkeypatch.delenv("TUYA_DF_API_USERNAME", raising=False)

        with pytest.raises(AuthError, match="No authentication found"):
            resolve_credentials()

    def test_forum_url_override(self, tmp_config_dir, monkeypatch):
        monkeypatch.delenv("TUYA_DF_API_KEY", raising=False)
        monkeypatch.setenv("TUYA_DF_API_KEY", "key")
        monkeypatch.setenv("TUYA_DF_API_USERNAME", "user")

        creds = resolve_credentials(cli_forum_url="https://override.com")
        assert creds.forum_url == "https://override.com"
