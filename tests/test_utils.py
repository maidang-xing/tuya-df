"""Tests for utils.py — file classification, MIME inference, Markdown embedding."""

import pytest
from pathlib import Path

from tuya_df.utils import (
    classify_file,
    get_mime_type,
    read_file_bytes,
    generate_embed_markdown,
    MAX_SIZES,
)


class TestClassifyFile:
    @pytest.mark.parametrize("filename", [
        "photo.png", "photo.PNG", "image.jpg", "image.JPEG",
        "anim.gif", "pic.webp", "logo.svg", "bitmap.bmp", "icon.ico",
    ])
    def test_image_classification(self, filename):
        assert classify_file(filename) == "image"

    @pytest.mark.parametrize("filename", [
        "clip.mp4", "video.MP4", "demo.m4v", "trailer.webm",
        "audio.ogg", "recording.mov",
    ])
    def test_video_classification(self, filename):
        assert classify_file(filename) == "video"

    @pytest.mark.parametrize("filename", [
        "doc.pdf", "archive.zip", "data.bin", "code.py",
        "log.txt", "config.yaml", "firmware.hex", "unknown.xyz",
    ])
    def test_attachment_classification(self, filename):
        assert classify_file(filename) == "attachment"


class TestGetMimeType:
    @pytest.mark.parametrize("ext,mime", [
        (".png", "image/png"),
        (".jpg", "image/jpeg"),
        (".jpeg", "image/jpeg"),
        (".gif", "image/gif"),
        (".webp", "image/webp"),
        (".svg", "image/svg+xml"),
        (".mp4", "video/mp4"),
        (".webm", "video/webm"),
        (".mov", "video/quicktime"),
        (".pdf", "application/pdf"),
        (".zip", "application/zip"),
        (".py", "text/x-python"),
        (".c", "text/x-c"),
        (".bin", "application/octet-stream"),
        (".log", "text/plain"),
    ])
    def test_known_mimes(self, ext, mime):
        assert get_mime_type(f"file{ext}") == mime

    def test_unknown_mime_fallback(self):
        assert get_mime_type("file.unknownext") == "application/octet-stream"

    def test_case_insensitive(self):
        assert get_mime_type("PHOTO.PNG") == "image/png"
        assert get_mime_type("clip.MP4") == "video/mp4"


class TestMaxSizes:
    def test_image_limit(self):
        assert MAX_SIZES["image"] == 10 * 1024 * 1024

    def test_video_limit(self):
        assert MAX_SIZES["video"] == 500 * 1024 * 1024

    def test_attachment_limit(self):
        assert MAX_SIZES["attachment"] == 30 * 1024 * 1024


class TestReadFileBytes:
    def test_read_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")

        assert read_file_bytes(str(test_file)) == b"hello world"

    def test_read_binary_file(self, tmp_path):
        test_file = tmp_path / "data.bin"
        test_file.write_bytes(b"\x00\x01\x02\xff")

        assert read_file_bytes(str(test_file)) == b"\x00\x01\x02\xff"


class TestGenerateEmbedMarkdown:
    def test_image_embed(self, sample_upload_response):
        md = generate_embed_markdown("/path/to/screenshot.png", "image", sample_upload_response)
        assert md == "![screenshot](upload://abc123.png)"

    def test_image_embed_uses_stem_not_filename(self, sample_upload_response):
        md = generate_embed_markdown("/path/to/my.photo.jpg", "image", sample_upload_response)
        assert md == "![my.photo](upload://abc123.png)"

    def test_video_embed(self, sample_upload_response):
        md = generate_embed_markdown("/path/to/demo.mp4", "video", sample_upload_response)
        assert '<video src="/uploads/default/original/3X/a/b/abc123.png" controls></video>' in md

    def test_attachment_embed(self, sample_upload_response):
        md = generate_embed_markdown("/path/to/datasheet.pdf", "attachment", sample_upload_response)
        assert md == "[datasheet.pdf|attachment](upload://abc123.png)"

    def test_embed_with_missing_short_url(self):
        upload_result = {"url": "/uploads/default/original/3X/abc.png"}
        md = generate_embed_markdown("photo.png", "image", upload_result)
        # Should fall back to full url when short_url is missing
        assert md == "![photo](/uploads/default/original/3X/abc.png)"

    def test_embed_with_empty_response(self):
        md = generate_embed_markdown("doc.pdf", "attachment", {})
        assert md == "[doc.pdf|attachment]()"

    def test_video_embed_uses_full_url_not_short_url(self, sample_upload_response):
        md = generate_embed_markdown("demo.mp4", "video", sample_upload_response)
        # Video should use full URL path, not upload:// short_url
        assert "upload://" not in md
        assert "/uploads/default/original/3X/a/b/abc123.png" in md
