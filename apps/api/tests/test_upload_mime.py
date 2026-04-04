"""Tests for MIME magic byte detection in upload router."""
import pytest
from app.uploads.router import _detect_mime

# Minimal valid file headers
JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 20
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
PDF_MAGIC = b"%PDF-1.4" + b"\x00" * 20
WEBP_MAGIC = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 20
FAKE_JPEG = b"PK\x03\x04" + b"\x00" * 20  # zip file pretending to be jpeg


def test_detect_jpeg():
    assert _detect_mime(JPEG_MAGIC) == "image/jpeg"


def test_detect_png():
    assert _detect_mime(PNG_MAGIC) == "image/png"


def test_detect_pdf():
    assert _detect_mime(PDF_MAGIC) == "application/pdf"


def test_detect_webp():
    assert _detect_mime(WEBP_MAGIC) == "image/webp"


def test_reject_fake_extension():
    assert _detect_mime(FAKE_JPEG) is None


def test_reject_empty():
    assert _detect_mime(b"") is None
