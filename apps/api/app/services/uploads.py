"""Upload validation. The file's own bytes decide its type; the browser's declared content type is not trusted.

Accepted: JPEG, PNG, WEBP (decoded with Pillow, with a pixel limit checked before any decoding) and PDF (by its
header; PDFs are stored and sent to the AI as documents, never opened by Pillow).
"""
from __future__ import annotations

import io

from PIL import Image

MAX_UPLOAD = 10 * 1024 * 1024  # bytes per file
MAX_FILES = 100  # files per request (a large class set)
MAX_PIXELS = 40_000_000  # about 7300 x 5500; far above any phone photo
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}
PIL_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
# Process-wide guard for every later decode (quality check, photo shrinking): Pillow refuses images above twice this.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class UploadRejected(ValueError):
    """str() is the teacher-facing reason; `status` is the HTTP status."""

    def __init__(self, message: str, status: int = 415) -> None:
        super().__init__(message)
        self.status = status


def sniff(data: bytes) -> str | None:
    """The content type from the file signature, or None when it is not an accepted type."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:5] == b"%PDF-":
        return "application/pdf"
    return None


def validate(name: str, data: bytes) -> str:
    """Return the real content type of an upload, or raise UploadRejected with a readable reason."""
    if not data:
        raise UploadRejected(f"{name}: file is empty.", 400)
    if len(data) > MAX_UPLOAD:
        raise UploadRejected(f"{name}: file is larger than 10 MB.", 413)
    ctype = sniff(data)
    if ctype is None:
        raise UploadRejected(f"{name}: only JPG, PNG, WEBP, or PDF files are supported.")
    if ctype == "application/pdf":
        if b"%%EOF" not in data[-2048:]:
            raise UploadRejected(f"{name}: this PDF looks incomplete or damaged. Export it again and re-upload.")
        return ctype
    try:
        with Image.open(io.BytesIO(data)) as img:  # reads the header only
            fmt = PIL_FORMATS.get(img.format or "")
            w, h = img.size
            if fmt != ctype:
                raise UploadRejected(f"{name}: the file contents do not match an accepted image type.")
            if w * h > MAX_PIXELS:
                raise UploadRejected(f"{name}: the image is too large ({w} x {h} pixels). Take the photo at a normal size.", 413)
            img.verify()  # structural check without decoding the pixels
    except UploadRejected:
        raise
    except Exception:
        raise UploadRejected(f"{name}: the image is damaged or not a real {EXTENSIONS[ctype].upper()} file.") from None
    return ctype
