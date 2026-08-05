"""categories command — list all forum categories."""

from __future__ import annotations

import click

from ..cli import get_client, handle_api_errors


@click.command()
@click.pass_context
def categories(ctx):
    """List all forum categories.

    \b
    Examples:
      tuya-df categories
      tuya-df categories --json
    """
    json_output = ctx.obj.json_output

    from ..config import AuthError, Credentials, get_forum_url
    from ..client import DiscourseClient

    try:
        client = get_client(ctx)
    except AuthError:
        # categories is a public endpoint — fallback to anonymous
        forum_url = ctx.obj.forum_url or get_forum_url()
        client = DiscourseClient(Credentials(api_key="", api_username="", forum_url=forum_url))

    try:
        data = client.get_categories()
    except Exception as exc:
        handle_api_errors(ctx, exc, json_output)
        return

    cats = data.get("category_list", {}).get("categories", [])

    if json_output:
        import json
        result = [{"id": c["id"], "name": c["name"], "slug": c.get("slug", "")} for c in cats]
        click.echo(json.dumps(result, indent=2))
        return

    if not cats:
        click.echo("No categories found.")
        return

    # Calculate column widths
    id_w = max(len(str(c["id"])) for c in cats)
    name_w = max(len(c["name"]) for c in cats)
    slug_w = max(len(c.get("slug", "")) for c in cats)

    # Header
    header = f"{'ID':<{id_w}}  {'Name':<{name_w}}  {'Slug':<{slug_w}}"
    click.echo(header)
    click.echo("-" * len(header))

    for c in cats:
        click.echo(f"{c['id']:<{id_w}}  {c['name']:<{name_w}}  {c.get('slug', ''):<{slug_w}}")
