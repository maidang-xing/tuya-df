"""tuya-df CLI entry point — command registration and global options."""

from __future__ import annotations

import sys

import click

from . import __version__
from .config import AuthError, get_forum_url, resolve_credentials


# -- Exit codes -----------------------------------------------------------
EXIT_OK = 0
EXIT_GENERAL_ERROR = 1
EXIT_AUTH_ERROR = 2
EXIT_NETWORK_ERROR = 3
EXIT_API_ERROR = 4
EXIT_PARTIAL = 5


class GlobalOptions:
    """Holds resolved global options passed via the CLI context."""

    def __init__(self, api_key, api_username, forum_url, json_output):
        self.api_key = api_key
        self.api_username = api_username
        self.forum_url = forum_url
        self.json_output = json_output


@click.group()
@click.option("--api-key", envvar="TUYA_DF_API_KEY", default=None, help="Discourse API key (overrides config).")
@click.option("--api-username", envvar="TUYA_DF_API_USERNAME", default=None, help="Discourse API username (overrides config).")
@click.option("--forum-url", envvar="TUYA_DF_FORUM_URL", default=None, help="Discourse forum URL (overrides config).")
@click.option("--json", "json_output", is_flag=True, default=False, help="Output machine-readable JSON.")
@click.version_option(__version__, prog_name="tuya-df")
@click.pass_context
def main(ctx, api_key, api_username, forum_url, json_output):
    """tuya-df — Discourse Forum CLI for TuyaOpen.

    Post, reply, and upload files to the TuyaOpen Discourse forum.

    Quick start:
      tuya-df auth login        # authenticate (one-time)
      tuya-df categories        # see forum categories
      tuya-df post create --title "Hello" --category "show-tell"
    """
    ctx.obj = GlobalOptions(api_key, api_username, forum_url, json_output)


def get_client(ctx):
    """Build a DiscourseClient from resolved credentials. Raises AuthError if no creds."""
    from .client import DiscourseClient

    opts: GlobalOptions = ctx.obj
    creds = resolve_credentials(
        cli_api_key=opts.api_key,
        cli_api_username=opts.api_username,
        cli_forum_url=opts.forum_url,
    )
    return DiscourseClient(creds)


def handle_api_errors(ctx, exc, json_output):
    """Translate DiscourseError / AuthError to proper exit codes."""
    from .client import DiscourseError

    if isinstance(exc, AuthError):
        if json_output:
            import json as jsonmod
            click.echo(jsonmod.dumps({"success": False, "error": str(exc), "exit_code": EXIT_AUTH_ERROR}, indent=2))
        else:
            click.echo(f"❌ {exc}", err=True)
        ctx.exit(EXIT_AUTH_ERROR)
    elif isinstance(exc, DiscourseError):
        code = EXIT_NETWORK_ERROR if exc.status_code == 0 else EXIT_API_ERROR
        if json_output:
            import json as jsonmod
            click.echo(jsonmod.dumps({"success": False, "error": str(exc), "exit_code": code}, indent=2))
        else:
            click.echo(f"❌ {exc}", err=True)
        ctx.exit(code)
    else:
        raise exc


# -- Register subcommands --------------------------------------------------

from .commands.auth_cmd import auth
from .commands.categories import categories
from .commands.post import post
from .commands.upload import upload

main.add_command(auth)
main.add_command(post)
main.add_command(upload)
main.add_command(categories)


if __name__ == "__main__":
    main()
