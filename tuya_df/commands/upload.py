"""upload command — upload a single file, return URL."""

from __future__ import annotations

import os
import sys

import click

from ..cli import get_client, handle_api_errors
from ..utils import classify_file, get_mime_type, read_file_bytes, MAX_SIZES


@click.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.pass_context
def upload(ctx, file_path):
    """Upload a single file to the forum. Returns the upload URL.

    \b
    Examples:
      tuya-df upload ./screenshot.png
      tuya-df upload ./demo.mp4 --json
    """
    json_output = ctx.obj.json_output

    try:
        client = get_client(ctx)
    except Exception as exc:
        handle_api_errors(ctx, exc, json_output)
        return

    file_type = classify_file(file_path)
    mime = get_mime_type(file_path)
    file_bytes = read_file_bytes(file_path)

    # Size check
    size = len(file_bytes)
    limit = MAX_SIZES.get(file_type, MAX_SIZES["attachment"])
    if size > limit:
        size_mb = size / (1024 * 1024)
        limit_mb = limit / (1024 * 1024)
        msg = f"File too large: {size_mb:.1f}MB > {limit_mb:.0f}MB limit ({file_type})"
        if json_output:
            import json
            click.echo(json.dumps({"success": False, "error": msg}))
        else:
            click.echo(f"❌ {msg}", err=True)
        ctx.exit(1)

    try:
        result = client.upload_file(file_path, file_bytes, mime)
    except Exception as exc:
        handle_api_errors(ctx, exc, json_output)
        return

    short_url = result.get("short_url", result.get("url", ""))
    full_url = result.get("url", "")

    if json_output:
        import json
        click.echo(json.dumps({
            "success": True,
            "short_url": short_url,
            "url": full_url,
            "filename": os.path.basename(file_path),
            "type": file_type,
        }, indent=2))
    else:
        click.echo(f"✅ Uploaded: {os.path.basename(file_path)}")
        click.echo(f"   URL: {short_url}")
        click.echo(f"   Type: {file_type}")
