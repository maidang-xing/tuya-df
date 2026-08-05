"""auth login / auth status / auth logout commands."""

from __future__ import annotations

import click

from ..auth import run_browser_auth, clear_session, is_authenticated
from ..config import get_forum_url, get_session_username, load_session_cookies


@click.group()
def auth():
    """Authentication management."""
    pass


@auth.command()
@click.pass_context
def login(ctx):
    """Log in to the Discourse forum via browser.

    Opens a browser window for you to log in to the forum.
    After login, your session is saved automatically.
    You only need to do this once (until the session expires).

    \b
    Example:
      tuya-df auth login
    """
    forum_url = ctx.obj.forum_url or get_forum_url()
    json_output = ctx.obj.json_output

    try:
        username = run_browser_auth(forum_url)
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(f"Browser authentication failed: {exc}")

    if not username:
        raise click.ClickException("Login failed or timed out. Please try again.")

    if json_output:
        import json
        click.echo(json.dumps({"success": True, "username": username}, indent=2))
    else:
        click.echo(f"\n✅ Login successful!")
        click.echo(f"   Username: {username}")
        click.echo(f"   Session saved to ~/.config/tuya-df/session.json")
        click.echo(f"\nYou can now use tuya-df to post to the forum!")


@auth.command()
@click.pass_context
def status(ctx):
    """Show current authentication status."""
    json_output = ctx.obj.json_output

    # Check API key env vars first
    import os
    if os.environ.get("TUYA_DF_API_KEY"):
        info = {
            "authenticated": True,
            "method": "api_key",
            "username": os.environ.get("TUYA_DF_API_USERNAME", "(not set)"),
            "forum_url": get_forum_url(),
        }
    elif is_authenticated():
        username = get_session_username()
        info = {
            "authenticated": True,
            "method": "browser_session",
            "username": username or "(unknown)",
            "forum_url": get_forum_url(),
        }
    else:
        info = {
            "authenticated": False,
            "message": "Run 'tuya-df auth login' to authenticate.",
        }

    if json_output:
        import json
        click.echo(json.dumps(info, indent=2))
    else:
        if info["authenticated"]:
            method_label = "API Key" if info["method"] == "api_key" else "Browser Session"
            click.echo(f"✅ Authenticated as: {info['username']}")
            click.echo(f"   Method: {method_label}")
            click.echo(f"   Forum:  {info['forum_url']}")
        else:
            click.echo("❌ Not authenticated.")
            click.echo("   Run 'tuya-df auth login' to log in via browser,")
            click.echo("   or set TUYA_DF_API_KEY and TUYA_DF_API_USERNAME environment variables.")
            ctx.exit(2)


@auth.command()
@click.pass_context
def logout(ctx):
    """Clear saved authentication session."""
    json_output = ctx.obj.json_output
    clear_session()
    if json_output:
        import json
        click.echo(json.dumps({"success": True, "message": "Session cleared."}, indent=2))
    else:
        click.echo("✅ Session cleared. Run 'tuya-df auth login' to log in again.")
