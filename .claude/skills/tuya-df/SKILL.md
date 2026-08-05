---
name: tuya-df
description: Post to the TuyaOpen Discourse forum via CLI — create topics, reply, upload files, list categories
---

# tuya-df — Discourse Forum CLI

Use `tuya-df` to interact with the TuyaOpen Discourse forum from the terminal.

## When to use

- User asks to post/share something to the forum
- User asks to reply to a forum topic
- User asks to upload a file to the forum
- User asks to see forum categories or recent topics

## Prerequisites

The user must have run `tuya-df auth login` at least once (browser session), or set `TUYA_DF_API_KEY` and `TUYA_DF_API_USERNAME` environment variables.

Check auth status first:
```bash
tuya-df auth status --json
```

## Commands

### Create a post
```bash
tuya-df post create \
  --title "Title" \
  --body "Markdown body" \
  --category "show-tell" \
  --json
```

Category accepts: ID (`9`), slug (`show-tell`), or fuzzy name (`show`).

### Create a post with attachments
```bash
tuya-df post create \
  --title "Title" \
  --body "Body text" \
  --category "show-tell" \
  --attach ./screenshot.png \
  --attach ./demo.mp4 \
  --json
```
Files are auto-classified: images (`.png` `.jpg` `.gif`), videos (`.mp4` `.webm`), or attachments (anything else). The embed Markdown is auto-generated and appended to the body.

### Body from file
```bash
tuya-df post create --title "Title" --body-file ./post.md --category "show-tell" --json
```

### Reply to a topic
```bash
tuya-df post reply <topic_id> --body "Reply text" --json
```

### List recent topics
```bash
tuya-df post list --json
tuya-df post list --category show-tell --json
```

### List categories
```bash
tuya-df categories --json
```

### Upload a single file
```bash
tuya-df upload ./photo.png --json
```

## Categories reference

| ID | Name | Slug |
|---|---|---|
| 6 | Announcement | announcement |
| 7 | Events & Contests | events-contests |
| 8 | Develop & Questions | develop-questions |
| 9 | Show & Tell | show-tell |
| 11 | Learn & Tutorials | learn-tutorials |

## JSON output

Always pass `--json` for structured output. Example success response:
```json
{
  "success": true,
  "topic_id": 42,
  "post_number": 1,
  "pending_moderation": false
}
```

If `pending_moderation` is `true`, inform the user their post is awaiting moderator approval.

## Important

- Do NOT post more than once per 30 seconds — Discourse auto-silences fast posting
- If you get exit code 2, the session expired — tell the user to run `tuya-df auth login`
- If you get exit code 4, show the error message from the JSON `error` field
