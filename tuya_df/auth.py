"""Browser-based authentication for Discourse forums.

Flow:
  1. Launch Playwright browser (visible to user)
  2. Navigate to forum login page
  3. User logs in manually (handles 2FA, captcha, OAuth, etc.)
  4. CLI detects successful login (page redirect or cookie presence)
  5. Extract session cookies
  6. Save to ~/.config/tuya-df/session.json (chmod 600)

After login, all subsequent API calls use the saved cookies — no browser needed.
"""

from __future__ import annotations

import json
import time

from .config import CONFIG_DIR, DEFAULT_FORUM_URL


SESSION_FILE = CONFIG_DIR / "session.json"

# Cookie names Discourse uses for authentication
AUTH_COOKIES = ("_t", "_forum_session")


def save_session(cookies: list[dict], username: str | None = None) -> None:
    """Save session cookies to disk (chmod 600)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "cookies": cookies,
        "username": username or "",
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SESSION_FILE.write_text(json.dumps(data, indent=2) + "\n")
    SESSION_FILE.chmod(0o600)


def load_session() -> dict | None:
    """Load saved session from disk, or None if not present."""
    if not SESSION_FILE.exists():
        return None
    try:
        return json.loads(SESSION_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def clear_session() -> None:
    """Delete saved session file."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def get_auth_cookies() -> dict[str, str]:
    """Return auth cookies as a simple dict, or empty dict if not logged in."""
    session = load_session()
    if not session:
        return {}
    return {c["name"]: c["value"] for c in session.get("cookies", []) if c["name"] in AUTH_COOKIES}


def is_authenticated() -> bool:
    """Check if we have saved session cookies."""
    return bool(get_auth_cookies())


def run_browser_auth(forum_url: str = DEFAULT_FORUM_URL) -> str | None:
    """Run Playwright browser to let user log in interactively.

    Returns username on success, None on failure.
    """
    import click

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise click.ClickException(
            "Playwright is required for browser login.\n"
            "Install it with: pip install playwright && playwright install chromium"
        )

    click.echo("\n🌐 Opening browser for Discourse login...")
    click.echo(f"   Forum: {forum_url}")
    click.echo("\n   Please log in to the forum in the browser window.")
    click.echo("   After you're logged in, return here.\n")

    username = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Navigate to the forum
        page.goto(forum_url)

        # Wait for user to log in — detect by checking for the current user
        # Discourse sets a `__discourse_user__` or we can check the /session/current endpoint
        click.echo("⏳ Waiting for you to log in... (timeout: 5 minutes)")

        try:
            # Poll for login by checking the current user API endpoint
            max_wait = 300  # 5 minutes
            poll_interval = 2  # seconds
            elapsed = 0

            while elapsed < max_wait:
                # Check if we can access the current user endpoint
                try:
                    resp = page.evaluate("""
                        async () => {
                            try {
                                const resp = await fetch('/session/current.json');
                                if (resp.ok) {
                                    const data = await resp.json();
                                    return data;
                                }
                            } catch(e) {}
                            return null;
                        }
                    """)

                    if resp and resp.get("current_user"):
                        username = resp["current_user"].get("username")
                        click.echo(f"\n✅ Detected login: {username}")
                        break
                except Exception:
                    pass

                time.sleep(poll_interval)
                elapsed += poll_interval

            if not username:
                click.echo("\n⚠️  Timeout or login not detected. Saving cookies anyway.")
        except Exception as exc:
            click.echo(f"\n⚠️  Error while waiting for login: {exc}")

        # Extract all cookies from the browser context
        cookies = context.cookies()

        browser.close()

    # Filter to only keep cookies for the forum domain
    from urllib.parse import urlparse

    forum_domain = urlparse(forum_url).hostname or ""
    forum_cookies = [
        c for c in cookies
        if forum_domain in c.get("domain", "")
    ]

    # Check if we got auth cookies
    auth_cookie_names = {c["name"] for c in forum_cookies}
    has_auth = any(name in auth_cookie_names for name in AUTH_COOKIES)

    if not has_auth and not username:
        click.echo("\n❌ No authentication cookies found. Login may have failed.")
        return None

    # Save session
    save_session(forum_cookies, username)

    return username
