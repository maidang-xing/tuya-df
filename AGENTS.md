# tuya-df — Agent Instructions

This project includes `tuya-df`, a CLI tool for posting to the TuyaOpen Discourse forum.

## Quick Reference for AI Agents

### Check auth status
```bash
tuya-df auth status --json
```

### List categories (no auth needed)
```bash
tuya-df categories --json
```

### List recent topics (no auth needed)
```bash
tuya-df post list --json
tuya-df post list --category show-tell --json
```

### Create a post
```bash
tuya-df post create \
  --title "Post Title" \
  --body "Markdown body text" \
  --category "show-tell" \
  --json
```

### Create a post with attachments
```bash
tuya-df post create \
  --title "Demo" \
  --body "See the screenshot below" \
  --category "show-tell" \
  --attach ./screenshot.png \
  --attach ./demo.mp4 \
  --json
```

### Reply to a topic
```bash
tuya-df post reply 33 --body "Reply text" --json
```

### Upload a file
```bash
tuya-df upload ./photo.png --json
```

## Important Notes

- Always use `--json` for machine-readable output
- Categories: `show-tell` (id=9), `develop-questions` (id=8), `learn-tutorials` (id=11), `announcement` (id=6), `events-contests` (id=7)
- Exit code 0 = success, 2 = auth error, 4 = API error
- Response `pending_moderation: true` means the post is queued for approval (TL0 users)

## Anti-spam safety (built-in, automatic)

The tool enforces multiple anti-spam layers automatically — you do NOT need to add delays yourself:

1. **Post cooldown (60s)** — persisted to disk, works across separate CLI calls. If you try to post twice quickly, the tool waits automatically.
2. **Write throttle (5s)** — minimum gap between all write requests including uploads.
3. **Pre-post silence check** — aborts before posting if the account is already silenced.
4. **Rate limit retry** — HTTP 429 triggers exponential backoff (5s → 10s → 20s).

**Agent rules:**
- NEVER issue multiple `post create`/`post reply` commands in parallel or rapid succession
- Wait for each post command to fully complete before issuing the next
- If you see "Cooling down" in stderr, the tool is handling it — just wait
- If you see "silenced" in any error output, STOP immediately and inform the user
