# Agent Install Prompt

Copy and paste the following prompt to any AI agent (Claude Code, Codex, Cursor, etc.) to install tuya-df and its skill in one shot:

---

## Prompt for AI Agents

```
Install the tuya-df Discourse Forum CLI tool and its Claude Code skill by following these steps:

1. Detect the operating system:
   - Windows: run `irm https://raw.githubusercontent.com/maidang-xing/tuya-df/main/install.ps1 | iex` in PowerShell
   - Linux/macOS: run `curl -sSL https://raw.githubusercontent.com/maidang-xing/tuya-df/main/install.sh | bash`

2. After installation, verify by running: `tuya-df --version`

3. If Claude Code is in use (i.e. `~/.claude/skills/` exists), the installer already copied the skill. Verify with: `ls ~/.claude/skills/tuya-df/`

4. Run `tuya-df auth login` — this opens a browser for the user to log in to the forum. Wait for the user to complete login.

5. Verify authentication: `tuya-df auth status --json`

6. List forum categories to confirm everything works: `tuya-df categories --json`

If any step fails, show the error and stop. Do not retry auth login without the user's involvement.
```

---

## What this does

| Step | Action | Result |
|------|--------|--------|
| 1 | Detect OS + run installer | `tuya-df` CLI + Playwright + skill all installed |
| 2 | Version check | Verify CLI is on PATH |
| 3 | Skill check | Verify Claude Code can use it |
| 4 | Browser login | User authenticates with forum (one-time) |
| 5 | Auth status | Confirm session saved |
| 6 | Categories | Confirm API access works |
