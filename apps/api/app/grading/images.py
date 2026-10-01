"""Shrink paper photos before they are sent to the AI.

Claude Haiku 4.5 reads images at most 1568 px on the long edge and downsizes anything larger itself, so sending the
full phone photo costs no extra tokens but makes every request (and every Batch API upload) several MB larger.
Shrinking to that size first keeps what the model sees the same and keeps a class set well under the 256 MB batch limit.

The photo's EXIF rotation is applied, so the model sees the paper the way the browser shows it and its bounding boxes
line up with the stored photo. The stored photo itself is never changed. PDFs are sent as they are.
"""
from __future__ import annotations

import io
import logging

from PIL import Image, ImageOps

log = logging.getLogger("tsekmate.images")

MAX_EDGE = 1568
JPEG_QUALITY = 85
_EXIF_ORIENTATION = 0x0112


def prepare(data: bytes, media_type: str) -> tuple[bytes, str]:
    """Return (bytes, media_type) to send. Unchanged when the photo is already small and upright, or not an image."""
    if media_type == "application/pdf":
        return data, media_type
    try:
        img = Image.open(io.BytesIO(data))
        rotated = img.getexif().get(_EXIF_ORIENTATION, 1) not in (1, None)
        if max(img.size) <= MAX_EDGE and not rotated:
            return data, media_type
        img = ImageOps.exif_transpose(img)
        img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return out.getvalue(), "image/jpeg"
    except Exception as e:  # an unreadable photo is sent as it is; the AI call reports the problem to the teacher
        log.warning("could not shrink photo (%s); sending the original", e)
        return data, media_type
