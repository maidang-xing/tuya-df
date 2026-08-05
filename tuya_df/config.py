"""Configuration and session management for tuya-df.

Reads/writes two files under ~/.config/tuya-df/:
  - session.json    (sensitive: browser cookies from forum login, chmod 600)
  - config.json     (non-sensitive: forum URL, preferences)

Auth lookup priority:
  1. --api-key / --api-username CLI flags (for admin-provided API keys)
  2. TUYA_DF_API_KEY / TUYA_DF_API_USERNAME env vars (for CI/agent)
  3. ~/.config/tuya-df/session.json (browser cookie session from `auth login`)
  4. None → caller should raise AuthError
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_FORUM_URL = "https://forum-tuyaopen.discourse.group"
CONFIG_DIR = Path(os.environ.get("TUYA_DF_CONFIG_DIR", Path.home() / ".config" / "tuya-df"))
SESSION_FILE = CONFIG_DIR / "session.json"
CONFIG_FILE = CONFIG_DIR / "config.json"


class AuthError(Exception):
    """Raised when no valid credentials are found."""


@dataclass
class Credentials:
    """Resolved credentials for a single Discourse forum.

    Either api_key-based (admin-provided) or cookie-based (browser login).
    """

    forum_url: str
    api_key: str = ""
    api_username: str = ""
    cookies: dict[str, str] | None = None

    @property
    def is_api_key(self) -> bool:
        """True if using API key authentication."""
        return bool(self.api_key)

    @property
    def is_cookie(self) -> bool:
        """True if using cookie-based session authentication."""
        return bool(self.cookies)

    def headers(self) -> dict[str, str]:
        """HTTP headers for authenticated Discourse API requests."""
        if self.is_api_key:
            return {"Api-Key": self.api_key, "Api-Username": self.api_username}
        return {}


def save_config(forum_url: str | None = None) -> None:
    """Save non-sensitive preferences."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if CONFIG_FILE.exists():
        try:
            existing = json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    if forum_url:
        existing["forum_url"] = forum_url
    CONFIG_FILE.write_text(json.dumps(existing, indent=2) + "\n")


def get_forum_url() -> str:
    """Return the configured forum URL (config file or default)."""
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
            return cfg.get("forum_url", DEFAULT_FORUM_URL)
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_FORUM_URL


def load_session_cookies() -> dict[str, str] | None:
    """Load saved browser session cookies from disk, or None if not present."""
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text())
        cookies = data.get("cookies", [])
        # Convert to simple name→value dict
        return {c["name"]: c["value"] for c in cookies}
    except (json.JSONDecodeError, OSError):
        return None


def get_session_username() -> str:
    """Return the username from saved session, or empty string."""
    if not SESSION_FILE.exists():
        return ""
    try:
        data = json.loads(SESSION_FILE.read_text())
        return data.get("username", "")
    except (json.JSONDecodeError, OSError):
        return ""


def resolve_credentials(
    cli_api_key: str | None = None,
    cli_api_username: str | None = None,
    cli_forum_url: str | None = None,
) -> Credentials:
    """Resolve credentials following the priority chain.

    Priority:
      1. CLI flags (--api-key / --api-username)
      2. Environment variables (TUYA_DF_API_KEY / TUYA_DF_API_USERNAME)
      3. Saved browser session (cookies from `auth login`)
      4. None → raise AuthError
    """
    forum_url = cli_forum_url or get_forum_url()

    # 1. CLI flags — API key mode
    if cli_api_key:
        return Credentials(
            forum_url=forum_url,
            api_key=cli_api_key,
            api_username=cli_api_username or os.environ.get("TUYA_DF_API_USERNAME", ""),
        )

    # 2. Environment variables — API key mode
    env_key = os.environ.get("TUYA_DF_API_KEY")
    if env_key:
        return Credentials(
            forum_url=forum_url,
            api_key=env_key,
            api_username=os.environ.get("TUYA_DF_API_USERNAME", ""),
        )

    # 3. Saved browser session — cookie mode
    cookies = load_session_cookies()
    if cookies and any(k in cookies for k in ("_t", "_forum_session")):
        return Credentials(
            forum_url=forum_url,
            cookies=cookies,
        )

    # 4. Nothing found
    raise AuthError(
        "No authentication found. Run `tuya-df auth login` to log in via browser, "
        "or set TUYA_DF_API_KEY and TUYA_DF_API_USERNAME environment variables."
    )
