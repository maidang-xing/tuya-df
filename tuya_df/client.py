"""Discourse API client — supports both API key and cookie-session auth.

For cookie-based auth, fetches a CSRF token on first request and includes
it in all subsequent POST/PUT/DELETE requests.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from .config import Credentials, CONFIG_DIR

# Persistent state file for cross-process cooldown tracking
_STATE_FILE = CONFIG_DIR / "state.json"


def _load_state() -> dict:
    """Load persistent state from disk."""
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_state(data: dict) -> None:
    """Save persistent state to disk."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        existing = _load_state()
        existing.update(data)
        _STATE_FILE.write_text(json.dumps(existing))
    except OSError:
        pass  # Non-critical — throttling falls back to no-op


class DiscourseError(Exception):
    """Raised when the Discourse API returns an error."""

    def __init__(self, message: str, status_code: int = 0, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class DiscourseClient:
    """HTTP client for the Discourse REST API.

    Supports two auth modes:
      - API key: sends Api-Key and Api-Username headers
      - Cookie session: sends browser cookies + X-CSRF-Token header
    """

    MAX_RETRIES = 3
    BACKOFF_BASE = 5  # seconds
    MIN_REQUEST_GAP = 5.0  # min seconds between POST/PUT requests (anti-spam)
    POST_COOLDOWN = 60.0  # min seconds between topic/reply creations (Discourse anti-spam window)

    def __init__(self, credentials: Credentials, timeout: int = 30):
        self.base_url = credentials.forum_url.rstrip("/")
        self.credentials = credentials
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "tuya-df/0.1",
            "Accept": "application/json",
        })

        # API key mode
        if credentials.is_api_key:
            self._session.headers.update(credentials.headers())

        # Cookie session mode
        if credentials.is_cookie and credentials.cookies:
            for name, value in credentials.cookies.items():
                self._session.cookies.set(name, value, domain=self._extract_domain())

        self._csrf_token: str | None = None
        self._last_write_time: float = 0.0  # for rate limiting POST/PUT
        self._last_post_time: float = 0.0  # for post creation cooldown

    def _extract_domain(self) -> str:
        """Extract hostname from forum URL for cookie domain."""
        from urllib.parse import urlparse
        return urlparse(self.base_url).hostname or ""

    def _ensure_csrf(self) -> None:
        """Fetch CSRF token if using cookie auth and not yet fetched."""
        if self._csrf_token or not self.credentials.is_cookie:
            return
        try:
            resp = self._session.get(
                f"{self.base_url}/session/csrf.json",
                timeout=self.timeout,
            )
            if resp.ok:
                self._csrf_token = resp.json().get("csrf")
        except Exception:
            pass

    def _throttle_writes(self, method: str) -> None:
        """Enforce minimum delay between write requests to avoid spam detection."""
        if method.upper() not in ("POST", "PUT", "DELETE"):
            return
        now = time.time()
        elapsed = now - self._last_write_time
        if elapsed < self.MIN_REQUEST_GAP:
            wait = self.MIN_REQUEST_GAP - elapsed
            time.sleep(wait)
        self._last_write_time = time.time()

    def _throttle_posts(self) -> None:
        """Enforce minimum delay between topic/reply creations.

        Discourse's "typed too fast" anti-spam checks operate on a ~60s window.
        Time is persisted to disk so cooldown works across separate CLI invocations.
        """
        last_post = _load_state().get("last_post_time", 0.0)
        now = time.time()
        elapsed = now - last_post
        if elapsed < self.POST_COOLDOWN:
            wait = self.POST_COOLDOWN - elapsed
            print(f"⏳ Cooling down {wait:.0f}s before next post (anti-spam)...", flush=True)
            time.sleep(wait)
        _save_state({"last_post_time": time.time()})

    def _check_silenced(self) -> None:
        """Check if the current user is silenced/suspended before posting.

        Raises DiscourseError early to avoid wasting requests and aggravating
        the account's standing.
        """
        try:
            resp = self._session.get(
                f"{self.base_url}/session/current.json",
                timeout=self.timeout,
            )
            if resp.ok:
                user = resp.json().get("current_user", {})
                if user.get("silenced_till") or user.get("silenced"):
                    raise DiscourseError(
                        "Your account is currently silenced. "
                        "Posting is blocked to protect your account. "
                        "Contact the forum administrator to restore access.",
                        status_code=403,
                    )
        except DiscourseError:
            raise
        except Exception:
            pass  # Non-critical — let the actual post attempt proceed

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        data: dict | None = None,
        files: dict | None = None,
        json_body: dict | None = None,
        retry: bool = True,
    ) -> dict:
        """Send a request with retry-on-429. Returns parsed JSON dict."""
        url = path if path.startswith("http") else f"{self.base_url}{path}"

        # Throttle write requests
        self._throttle_writes(method)

        # Ensure CSRF token for cookie auth
        needs_csrf = method.upper() in ("POST", "PUT", "DELETE")
        if needs_csrf and self.credentials.is_cookie:
            self._ensure_csrf()

        headers = {}
        content_type = "application/x-www-form-urlencoded"
        if json_body is not None:
            content_type = "application/json"
        if files is not None:
            content_type = None  # let requests set multipart boundary
        if content_type:
            headers["Content-Type"] = content_type

        # Add CSRF token for cookie auth on write operations
        if needs_csrf and self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token

        for attempt in range(self.MAX_RETRIES):
            try:
                kwargs: dict[str, Any] = {
                    "params": params,
                    "files": files,
                    "headers": headers,
                    "timeout": self.timeout,
                }
                if data:
                    kwargs["data"] = data
                elif json_body:
                    kwargs["json"] = json_body

                resp = self._session.request(method, url, **kwargs)
            except requests.ConnectionError as exc:
                raise DiscourseError(f"Network error: {exc}", status_code=0) from exc
            except requests.Timeout as exc:
                raise DiscourseError(f"Request timed out after {self.timeout}s", status_code=0) from exc

            # Rate limit: retry with exponential backoff
            if resp.status_code == 429 and retry and attempt < self.MAX_RETRIES - 1:
                wait = self.BACKOFF_BASE * (2 ** attempt)
                print(f"⏳ Rate limited, waiting {wait}s... (attempt {attempt + 1}/{self.MAX_RETRIES})", flush=True)
                time.sleep(wait)
                continue

            # CSRF token expired — refresh and retry once
            if resp.status_code == 403 and self.credentials.is_cookie:
                body_text = ""
                try:
                    body_data = resp.json()
                    errs = body_data.get("errors", [""])
                    body_text = errs[0] if isinstance(errs, list) and errs else str(errs)
                except Exception:
                    pass
                if "csrf" in body_text.lower() and not retry:
                    # Already retried, give up
                    pass
                elif "csrf" in body_text.lower():
                    self._csrf_token = None
                    self._ensure_csrf()
                    if self._csrf_token:
                        headers["X-CSRF-Token"] = self._csrf_token
                        continue

            # Parse response
            try:
                body = resp.json()
            except ValueError:
                body = {"raw": resp.text}

            if resp.status_code >= 400:
                if isinstance(body, dict):
                    errors = body.get("errors")
                    if errors:
                        msg = "; ".join(str(e) for e in errors) if isinstance(errors, list) else str(errors)
                    else:
                        msg = body.get("error", f"HTTP {resp.status_code}")
                else:
                    msg = f"HTTP {resp.status_code}"

                # Special handling: session expired
                if resp.status_code == 403 and "not_logged_in" in str(body):
                    raise DiscourseError(
                        "Session expired. Run `tuya-df auth login` again.",
                        status_code=403,
                        response_body=body,
                    )

                # Special handling: silenced/banned user
                error_text = str(body).lower()
                if any(w in error_text for w in ("silenced", "禁言", "suspended", "banned")):
                    raise DiscourseError(
                        "Your account has been silenced or suspended. "
                        "Contact the forum administrator to restore access.",
                        status_code=resp.status_code,
                        response_body=body,
                    )

                raise DiscourseError(msg, status_code=resp.status_code, response_body=body)

            return body

        raise DiscourseError("Max retries exceeded", status_code=429)

    # -- Public API ------------------------------------------------------

    def get(self, path: str, params: dict | None = None) -> dict:
        return self._request("GET", path, params=params)

    def post(self, path: str, data: dict | None = None, json_body: dict | None = None) -> dict:
        return self._request("POST", path, data=data, json_body=json_body)

    def upload_file(self, file_path: str, file_bytes: bytes, mime_type: str, upload_type: str = "composer") -> dict:
        """Upload a file to Discourse. Returns upload response with url/short_url."""
        import os

        # Throttle: uploads are write requests too
        self._throttle_writes("POST")

        # Ensure CSRF for cookie auth
        if self.credentials.is_cookie:
            self._ensure_csrf()

        files = {"files[]": (os.path.basename(file_path), file_bytes, mime_type)}
        data = {"type": upload_type, "synchronous": "true"}
        url = f"{self.base_url}/uploads.json"

        headers = {}
        if self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token

        for attempt in range(self.MAX_RETRIES):
            resp = self._session.post(url, files=files, data=data, headers=headers, timeout=self.timeout)

            if resp.status_code == 429 and attempt < self.MAX_RETRIES - 1:
                wait = self.BACKOFF_BASE * (2 ** attempt)
                print(f"⏳ Rate limited, waiting {wait}s... (attempt {attempt + 1}/{self.MAX_RETRIES})", flush=True)
                time.sleep(wait)
                continue

            try:
                body = resp.json()
            except ValueError:
                body = {"raw": resp.text}

            if resp.status_code >= 400:
                if resp.status_code == 403 and "not_logged_in" in str(body):
                    raise DiscourseError("Session expired. Run `tuya-df auth login` again.", status_code=403)
                if isinstance(body, dict) and body.get("errors"):
                    errs = body["errors"]
                    msg = "; ".join(str(e) for e in errs) if isinstance(errs, list) else str(errs)
                else:
                    msg = f"HTTP {resp.status_code}"
                raise DiscourseError(msg, status_code=resp.status_code, response_body=body)

            return body

        raise DiscourseError("Max retries exceeded on upload", status_code=429)

    def create_topic(
        self,
        title: str,
        raw: str,
        category: int,
        tags: list[str] | None = None,
    ) -> dict:
        """Create a new topic."""
        self._throttle_posts()
        self._check_silenced()
        data: dict[str, Any] = {
            "title": title,
            "raw": raw,
            "category": category,
        }
        if tags:
            data["tags"] = ",".join(tags)
        return self.post("/posts.json", data=data)

    def create_post(self, topic_id: int, raw: str) -> dict:
        """Reply to an existing topic."""
        self._throttle_posts()
        self._check_silenced()
        return self.post("/posts.json", data={"topic_id": topic_id, "raw": raw})

    def get_latest_topics(self, category: str | None = None, limit: int = 5) -> dict:
        """Fetch latest topics, optionally filtered by category."""
        params: dict[str, Any] = {"per": limit}
        if category:
            params["category"] = category
        return self.get("/latest.json", params=params)

    def get_categories(self) -> dict:
        """Fetch all categories."""
        return self.get("/categories.json")

    def search(self, term: str) -> dict:
        """Search forum topics."""
        return self.get("/search.json", params={"term": term})
