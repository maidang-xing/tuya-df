"""Utility functions — file classification, MIME inference, Markdown embedding."""

from __future__ import annotations

import os
from pathlib import Path

# -- MIME type mapping (not relying on system mimetypes) --------------------

_MIME_MAP: dict[str, str] = {
    # Images
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    # Videos
    ".mp4": "video/mp4",
    ".m4v": "video/x-m4v",
    ".webm": "video/webm",
    ".ogg": "video/ogg",
    ".ogv": "video/ogg",
    ".mov": "video/quicktime",
    # Audio
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    # Documents
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    # Archives
    ".zip": "application/zip",
    ".gz": "application/gzip",
    ".tar": "application/x-tar",
    ".7z": "application/x-7z-compressed",
    ".rar": "application/x-rar-compressed",
    # Code
    ".c": "text/x-c",
    ".cpp": "text/x-c++",
    ".h": "text/x-c",
    ".hpp": "text/x-c++",
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".java": "text/x-java",
    ".go": "text/x-go",
    ".rs": "text/x-rust",
    ".sh": "text/x-shellscript",
    # Binary
    ".bin": "application/octet-stream",
    ".hex": "text/plain",
    ".elf": "application/x-elf",
    ".log": "text/plain",
}

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"}
_VIDEO_EXTS = {".mp4", ".m4v", ".webm", ".ogg", ".ogv", ".mov"}

# -- Size limits (bytes) — Discourse defaults, admin may differ -------------

MAX_SIZES: dict[str, int] = {
    "image": 10 * 1024 * 1024,      # 10 MB
    "video": 500 * 1024 * 1024,     # 500 MB
    "attachment": 30 * 1024 * 1024, # 30 MB
}


def classify_file(file_path: str) -> str:
    """Classify a file as 'image', 'video', or 'attachment' based on extension."""
    ext = Path(file_path).suffix.lower()
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _VIDEO_EXTS:
        return "video"
    return "attachment"


def get_mime_type(file_path: str) -> str:
    """Get MIME type for a file based on extension. Falls back to octet-stream."""
    ext = Path(file_path).suffix.lower()
    return _MIME_MAP.get(ext, "application/octet-stream")


def read_file_bytes(file_path: str) -> bytes:
    """Read file contents as bytes."""
    with open(file_path, "rb") as f:
        return f.read()


def generate_embed_markdown(
    file_path: str,
    file_type: str,
    upload_result: dict,
) -> str:
    """Generate the Markdown embed for an uploaded file.

    Args:
        file_path: Original local file path (for display name)
        file_type: 'image', 'video', or 'attachment'
        upload_result: Response from /uploads.json

    Returns:
        Markdown string to embed in the post body.
    """
    filename = os.path.basename(file_path)
    stem = Path(file_path).stem

    short_url = upload_result.get("short_url", "")
    full_url = upload_result.get("url", "")

    if file_type == "image":
        return f"![{stem}]({short_url})"

    elif file_type == "video":
        # Discourse renders <video> tags in posts
        return f'<video src="{full_url}" controls></video>'

    else:
        # Attachment link
        return f"[{filename}|attachment]({short_url})"
