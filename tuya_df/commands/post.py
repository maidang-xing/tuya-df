"""post create / post reply / post list commands."""

from __future__ import annotations

import os
import re
import sys

import click

from ..cli import EXIT_PARTIAL, get_client, handle_api_errors
from ..utils import (
    classify_file,
    generate_embed_markdown,
    get_mime_type,
    read_file_bytes,
    MAX_SIZES,
)


@click.group()
def post():
    """Post management — create, reply, list."""
    pass


def resolve_category(client, category_input: str) -> int | None:
    """Resolve category input (ID, slug, or fuzzy name) to a numeric ID."""
    # Try as integer first
    try:
        return int(category_input)
    except ValueError:
        pass

    # Fetch categories and match
    data = client.get_categories()
    cats = data.get("category_list", {}).get("categories", [])

    # Exact slug match
    for c in cats:
        if c.get("slug") == category_input:
            return c["id"]

    # Fuzzy name match (case-insensitive, partial)
    matches = [c for c in cats if category_input.lower() in c["name"].lower()]
    if len(matches) == 1:
        return matches[0]["id"]
    elif len(matches) > 1:
        names = ", ".join(f"{c['id']}={c['name']}" for c in matches)
        raise click.ClickException(f"Ambiguous category '{category_input}', matches: {names}")

    raise click.ClickException(
        f"Category '{category_input}' not found. Run 'tuya-df categories' to see options."
    )


def resolve_topic_id(topic: str, client) -> int:
    """Resolve topic ID from a number or a full Discourse topic URL."""
    try:
        return int(topic)
    except ValueError:
        pass

    # Try to extract from URL: .../t/<slug>/<id>
    match = re.search(r"/t/[^/]+/(\d+)", topic)
    if match:
        return int(match.group(1))

    raise click.ClickException(
        f"Cannot parse topic ID from '{topic}'. Use a numeric ID or a topic URL."
    )


def process_attachments(client, file_paths: list[str], json_output: bool) -> tuple[str, bool]:
    """Upload all attachment files and return (markdown_block, all_succeeded)."""
    embeds = []
    all_ok = True

    for path in file_paths:
        file_type = classify_file(path)
        mime = get_mime_type(path)
        file_bytes = read_file_bytes(path)

        # Size check
        size = len(file_bytes)
        limit = MAX_SIZES.get(file_type, MAX_SIZES["attachment"])
        if size > limit:
            size_mb = size / (1024 * 1024)
            limit_mb = limit / (1024 * 1024)
            click.echo(f"⚠️  Skipping {os.path.basename(path)}: {size_mb:.1f}MB > {limit_mb:.0f}MB limit", err=True)
            all_ok = False
            continue

        try:
            result = client.upload_file(path, file_bytes, mime)
        except Exception as exc:
            click.echo(f"❌ Upload failed: {os.path.basename(path)} — {exc}", err=True)
            all_ok = False
            continue

        embed = generate_embed_markdown(path, file_type, result)
        embeds.append(embed)

        if not json_output:
            short_url = result.get("short_url", result.get("url", ""))
            click.echo(f"📎 Uploaded: {os.path.basename(path)} → {short_url}", err=True)

    markdown_block = "\n\n".join(embeds)
    return markdown_block, all_ok


def get_body(title: str, body: str | None, body_file: str | None) -> str:
    """Resolve post body from --body, --body-file, or interactive $EDITOR."""
    if body is not None:
        return body

    if body_file:
        with open(body_file, "r", encoding="utf-8") as f:
            return f.read().strip()

    # Interactive: open $EDITOR
    editor = os.environ.get("EDITOR", "nano")
    import subprocess
    import tempfile

    click.echo(f"\n📝 Opening {editor} for post body...")
    click.echo(f"   Title: {title}")

    with tempfile.NamedTemporaryFile(suffix=".md", mode="w+", delete=False) as tmp:
        tmp.write(f"# {title}\n\n")
        tmp.flush()
        tmp_path = tmp.name

    try:
        subprocess.call([editor, tmp_path])
        with open(tmp_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        # Remove the title line we added
        lines = content.splitlines()
        if lines and lines[0].startswith("# "):
            lines = lines[1:]
        return "\n".join(lines).strip()
    finally:
        os.unlink(tmp_path)


@post.command()
@click.option("--title", required=True, help="Topic title.")
@click.option("--body", default=None, help="Post body text (Markdown).")
@click.option("--body-file", "-f", default=None, type=click.Path(exists=True), help="Read body from file.")
@click.option("--category", "-c", required=True, help="Category ID, slug, or name.")
@click.option("--tags", "-t", default=None, help="Comma-separated tags.")
@click.option("--attach", "-a", "attachments", multiple=True, type=click.Path(exists=True), help="Attach file(s). Can be repeated.")
@click.pass_context
def create(ctx, title, body, body_file, category, tags, attachments):
    """Create a new topic on the forum.

    \b
    Examples:
      tuya-df post create --title "Hello" --body "World" --category "show-tell"
      tuya-df post create --title "Guide" --body-file ./guide.md -c develop-questions
      tuya-df post create --title "Demo" --body "See this" -c 9 -a photo.png -a video.mp4
    """
    json_output = ctx.obj.json_output

    try:
        client = get_client(ctx)
    except Exception as exc:
        handle_api_errors(ctx, exc, json_output)
        return

    # Warn new users about posting restrictions
    try:
        user_resp = client.get("/session/current.json")
        user_info = user_resp.get("current_user", {})
        if user_info.get("trust_level", 99) == 0:
            if not json_output:
                click.echo("ℹ️  You are a new user (Trust Level 0).", err=True)
                click.echo("   Your post will be queued for moderator approval.", err=True)
                click.echo("   Avoid posting too frequently to prevent auto-silencing.\n", err=True)
    except Exception:
        pass  # Non-critical, continue

    # Resolve category
    try:
        cat_id = resolve_category(client, category)
    except click.ClickException:
        raise
    except Exception as exc:
        handle_api_errors(ctx, exc, json_output)
        return

    # Get body content
    raw_body = get_body(title, body, body_file)

    # Process attachments
    attach_markdown = ""
    attach_ok = True
    if attachments:
        attach_markdown, attach_ok = process_attachments(client, list(attachments), json_output)

    # Assemble final body
    if attach_markdown:
        final_body = raw_body + "\n\n" + attach_markdown if raw_body else attach_markdown
    else:
        final_body = raw_body

    if not final_body.strip():
        raise click.ClickException("Post body is empty. Provide --body, --body-file, or write in the editor.")

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    # Create topic
    try:
        result = client.create_topic(title, final_body, cat_id, tag_list)
    except Exception as exc:
        handle_api_errors(ctx, exc, json_output)
        return

    topic_id = result.get("topic_id")
    post_number = result.get("post_number")
    forum_url = client.base_url
    action = result.get("action", "")
    is_pending = action == "enqueued" or (not topic_id and action)

    if json_output:
        import json
        output = {
            "success": True,
            "topic_id": topic_id,
            "post_number": post_number,
            "pending_moderation": is_pending,
        }
        if topic_id:
            output["url"] = f"{forum_url}/t/topic/{topic_id}"
        click.echo(json.dumps(output, indent=2))
    else:
        if is_pending:
            click.echo(f"\n⏳ Post submitted — awaiting moderator approval.")
            click.echo(f"   Title: {title}")
            click.echo(f"   Your post is in the moderation queue (new user).")
            click.echo(f"   It will appear publicly once a moderator approves it.")
        else:
            click.echo(f"\n✅ Topic created successfully!")
            click.echo(f"   Title: {title}")
            if topic_id:
                click.echo(f"   Link:  {forum_url}/t/topic/{topic_id}")
        if not attach_ok:
            click.echo(f"   ⚠️  Some attachments failed to upload (see above)")

    if not attach_ok:
        ctx.exit(EXIT_PARTIAL)


@post.command()
@click.argument("topic")
@click.option("--body", "-b", default=None, help="Reply body text (Markdown).")
@click.option("--body-file", "-f", default=None, type=click.Path(exists=True), help="Read body from file.")
@click.option("--attach", "-a", "attachments", multiple=True, type=click.Path(exists=True), help="Attach file(s).")
@click.pass_context
def reply(ctx, topic, body, body_file, attachments):
    """Reply to an existing topic.

    \b
    Examples:
      tuya-df post reply 33 --body "Thanks!"
      tuya-df post reply https://forum-tuyaopen.discourse.group/t/topic/33 -f reply.md
    """
    json_output = ctx.obj.json_output

    try:
        client = get_client(ctx)
    except Exception as exc:
        handle_api_errors(ctx, exc, json_output)
        return

    topic_id = resolve_topic_id(topic, client)

    # Get body
    if body is not None:
        raw_body = body
    elif body_file:
        with open(body_file, "r", encoding="utf-8") as f:
            raw_body = f.read().strip()
    else:
        raise click.ClickException("Reply body is required. Use --body or --body-file.")

    # Process attachments
    attach_markdown = ""
    attach_ok = True
    if attachments:
        attach_markdown, attach_ok = process_attachments(client, list(attachments), json_output)

    # Assemble final body
    if attach_markdown:
        final_body = raw_body + "\n\n" + attach_markdown if raw_body else attach_markdown
    else:
        final_body = raw_body

    try:
        result = client.create_post(topic_id, final_body)
    except Exception as exc:
        handle_api_errors(ctx, exc, json_output)
        return

    post_number = result.get("post_number")
    topic_id_result = result.get("topic_id", topic_id)
    action = result.get("action", "")
    is_pending = action == "enqueued" or (not post_number and action)

    if json_output:
        import json
        output = {
            "success": True,
            "topic_id": topic_id_result,
            "post_number": post_number,
            "pending_moderation": is_pending,
        }
        click.echo(json.dumps(output, indent=2))
    else:
        if is_pending:
            click.echo(f"\n⏳ Reply submitted — awaiting moderator approval.")
        else:
            click.echo(f"\n✅ Reply posted!")
            click.echo(f"   Topic: {client.base_url}/t/topic/{topic_id_result}")
            click.echo(f"   Post #: {post_number}")
        if not attach_ok:
            click.echo(f"   ⚠️  Some attachments failed to upload (see above)")

    if not attach_ok:
        ctx.exit(EXIT_PARTIAL)


@post.command(name="list")
@click.option("--category", "-c", default=None, help="Filter by category slug or ID.")
@click.option("--limit", "-n", default=10, help="Number of topics to show (default: 10).")
@click.pass_context
def list_topics(ctx, category, limit):
    """List recent topics.

    \b
    Examples:
      tuya-df post list
      tuya-df post list --category show-tell --limit 5
      tuya-df post list --json
    """
    json_output = ctx.obj.json_output

    # post list can work without auth for public reads
    from ..config import resolve_credentials, AuthError, Credentials
    from ..client import DiscourseClient, DiscourseError

    try:
        client = get_client(ctx)
    except AuthError:
        # Fallback: public read without credentials
        from ..config import get_forum_url
        forum_url = ctx.obj.forum_url or get_forum_url()
        client = DiscourseClient(Credentials(api_key="", api_username="", forum_url=forum_url))
    except Exception as exc:
        handle_api_errors(ctx, exc, json_output)
        return

    try:
        data = client.get_latest_topics(category=category, limit=limit)
    except Exception as exc:
        handle_api_errors(ctx, exc, json_output)
        return

    topics = data.get("topic_list", {}).get("topics", [])

    if json_output:
        import json
        result = [{
            "id": t["id"],
            "title": t["title"],
            "posts_count": t.get("posts_count", 1),
            "views": t.get("views", 0),
            "like_count": t.get("like_count", 0),
            "created_at": t.get("created_at"),
        } for t in topics]
        click.echo(json.dumps(result, indent=2))
        return

    if not topics:
        click.echo("No topics found.")
        return

    click.echo(f"{'ID':<6} {'Replies':<9} {'Views':<7} Title")
    click.echo("-" * 70)
    for t in topics:
        replies = t.get("posts_count", 1) - 1
        views = t.get("views", 0)
        click.echo(f"{t['id']:<6} {replies:<9} {views:<7} {t['title']}")
