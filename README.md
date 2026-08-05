<div align="center">

# tuya-df

**Discourse Forum CLI for TuyaOpen**

Post, reply, and upload files to the TuyaOpen Discourse forum — straight from your terminal.

[English](#english) | [中文](#中文)

</div>

---

<a id="english"></a>

## 🇬🇧 English

### What is this?

`tuya-df` is a command-line tool (like `gh` for GitHub) that lets you interact with the [TuyaOpen Discourse forum](https://forum-tuyaopen.discourse.group) without opening a browser. Create topics, reply to posts, and upload images/videos/files — all from the terminal. Designed for both humans and AI agents.

### Quick Start (3 steps)

```bash
# 1. Install
git clone https://github.com/<your-username>/tuya-df.git
cd tuya-df
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[browser]"
python -m playwright install chromium

# 2. Login (opens browser, one-time only)
tuya-df auth login

# 3. Post!
tuya-df post create --title "Hello TuyaOpen!" --body "My first CLI post." --category "show-tell"
```

That's it. You're posting to the forum from the terminal.

### Commands

```bash
# Authentication
tuya-df auth login           # Browser login (one-time)
tuya-df auth status          # Check auth status
tuya-df auth logout          # Clear session

# Browse (no login required)
tuya-df categories           # List forum categories
tuya-df post list            # Recent topics
tuya-df post list -c show-tell -n 5   # Filter by category

# Create topics
tuya-df post create \
  --title "My Project" \
  --body "Check this out!" \
  --category "show-tell" \
  --attach ./screenshot.png \
  --attach ./demo.mp4 \
  --tags "t5,project"

# Reply to topics
tuya-df post reply 33 --body "Great work!"

# Upload files
tuya-df upload ./photo.png

# Machine-readable output (for AI agents / scripts)
tuya-df --json post list
tuya-df --json categories
```

### Authentication Methods

| Method | Best for | How |
|---|---|---|
| **Browser login** | Humans | `tuya-df auth login` → log in via browser → cookies saved |
| **API Key (env var)** | AI agents / CI | `export TUYA_DF_API_KEY=xxx` + `export TUYA_DF_API_USERNAME=xxx` |
| **API Key (flag)** | One-off use | `tuya-df --api-key xxx --api-username name post create ...` |

Browser login requires [Playwright](https://playwright.dev/) + Chromium. After the initial login, no browser is needed.

### `--attach` Smart Media Handling

Just pass files with `--attach` and `tuya-df` handles the rest:

| File type | Extensions | Embed format |
|---|---|---|
| 🖼️ Image | `.png` `.jpg` `.gif` `.webp` `.svg` | `![filename](upload://xxx.png)` |
| 🎬 Video | `.mp4` `.m4v` `.webm` `.mov` | `<video src="..." controls></video>` |
| 📎 Attachment | `.pdf` `.zip` `.bin` `.log` ... | `[filename\|attachment](upload://xxx)` |

Uploads are automatic — the generated Markdown is appended to your post body.

### JSON Output for AI Agents

All commands support `--json` for structured output:

```bash
tuya-df --json post create --title "Test" --body "Hello" --category 9
```
```json
{
  "success": true,
  "topic_id": 42,
  "post_number": 1,
  "pending_moderation": false
}
```

### Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | General error |
| 2 | Auth failure |
| 3 | Network error |
| 4 | API error |
| 5 | Partial success (some attachments failed) |

### Requirements

- Python 3.9+
- `click`, `requests` (installed automatically)
- `playwright` + Chromium (only for `auth login`)

### For New Forum Users (Trust Level 0)

New users' posts enter a moderation queue. `tuya-df` will detect this and show a clear message. Don't post too frequently — Discourse may auto-silence accounts that post too fast.

---

<a id="中文"></a>

## 🇨🇳 中文

### 这是什么？

`tuya-df` 是一个命令行工具（类似 GitHub 的 `gh`），让你无需打开浏览器就能与 [TuyaOpen 论坛](https://forum-tuyaopen.discourse.group) 交互。发帖、回复、上传图片/视频/文件——全部在终端完成。同时为人类用户和 AI Agent 设计。

### 一键使用（3 步）

```bash
# 1. 安装
git clone https://github.com/<your-username>/tuya-df.git
cd tuya-df
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[browser]"
python -m playwright install chromium

# 2. 登录（会打开浏览器，只需一次）
tuya-df auth login

# 3. 发帖！
tuya-df post create --title "大家好！" --body "这是我的第一个 CLI 帖子。" --category "show-tell"
```

完成。你已经在终端里发帖了。

### 命令一览

```bash
# 认证
tuya-df auth login           # 浏览器登录（只需一次）
tuya-df auth status          # 查看登录状态
tuya-df auth logout          # 清除登录

# 浏览（无需登录）
tuya-df categories           # 查看论坛分类
tuya-df post list            # 最新帖子
tuya-df post list -c show-tell -n 5   # 按分类筛选

# 发新帖
tuya-df post create \
  --title "我的项目" \
  --body "给大家分享一个项目！" \
  --category "show-tell" \
  --attach ./截图.png \
  --attach ./演示.mp4 \
  --tags "t5,项目分享"

# 回复帖子
tuya-df post reply 33 --body "感谢分享！"

# 上传文件
tuya-df upload ./照片.png

# JSON 输出（AI Agent / 脚本友好）
tuya-df --json post list
tuya-df --json categories
```

### 认证方式

| 方式 | 适合 | 用法 |
|---|---|---|
| **浏览器登录** | 人类用户 | `tuya-df auth login` → 浏览器登录 → cookie 自动保存 |
| **API Key（环境变量）** | AI Agent / CI | `export TUYA_DF_API_KEY=xxx` + `export TUYA_DF_API_USERNAME=xxx` |
| **API Key（参数）** | 临时使用 | `tuya-df --api-key xxx --api-username name post create ...` |

浏览器登录需要安装 [Playwright](https://playwright.dev/) 和 Chromium。首次登录后不再需要浏览器。

### `--attach` 智能附件处理

只需用 `--attach` 传入文件，`tuya-df` 自动处理上传和嵌入：

| 类型 | 扩展名 | 嵌入格式 |
|---|---|---|
| 🖼️ 图片 | `.png` `.jpg` `.gif` `.webp` `.svg` | `![文件名](upload://xxx.png)` |
| 🎬 视频 | `.mp4` `.m4v` `.webm` `.mov` | `<video src="..." controls></video>` |
| 📎 附件 | `.pdf` `.zip` `.bin` `.log` ... | `[文件名\|attachment](upload://xxx)` |

上传全自动——生成的 Markdown 会追加到帖子正文末尾。

### AI Agent 友好的 JSON 输出

所有命令支持 `--json` 结构化输出：

```bash
tuya-df --json post create --title "测试" --body "你好" --category 9
```
```json
{
  "success": true,
  "topic_id": 42,
  "post_number": 1,
  "pending_moderation": false
}
```

### 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 一般错误 |
| 2 | 认证失败 |
| 3 | 网络错误 |
| 4 | API 错误 |
| 5 | 部分成功（部分附件上传失败） |

### 环境要求

- Python 3.9+
- `click`、`requests`（自动安装）
- `playwright` + Chromium（仅 `auth login` 需要）

### 论坛新用户须知（Trust Level 0）

新用户的帖子会进入审核队列。`tuya-df` 会自动检测并提示。请不要频繁发帖——Discourse 会自动禁言发帖过快的账号。

### 项目结构

```
tuya-df/
├── pyproject.toml              # 打包配置 + 依赖
├── README.md                   # 本文件
├── LICENSE
├── tuya_df/
│   ├── cli.py                  # CLI 入口，全局选项
│   ├── config.py               # 配置 / 会话管理
│   ├── auth.py                 # Playwright 浏览器登录
│   ├── client.py               # Discourse API 客户端（CSRF + 限速 + 重试）
│   ├── utils.py                # 文件分类 / MIME / Markdown 嵌入
│   └── commands/
│       ├── auth_cmd.py         # auth login / status / logout
│       ├── post.py             # post create / reply / list
│       ├── upload.py           # upload
│       └── categories.py       # categories
└── tests/
```

## License

Apache-2.0
