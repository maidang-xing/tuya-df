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
- Do not post more than once per 30 seconds — Discourse may silence accounts that post too fast
