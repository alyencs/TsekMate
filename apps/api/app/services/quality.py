"""Image quality check (stretch): blur and darkness. Runs before grading; a bad photo gets a retake suggestion."""
from __future__ import annotations

import io

from PIL import Image, ImageFilter, ImageStat

BLUR_THRESHOLD = 120.0  # variance of the Laplacian (center crop, 1000 px); below this the photo is likely blurry
DARK_THRESHOLD = 70.0  # mean brightness (0-255)


def check(data: bytes) -> dict:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return {"ok": False, "reason": "File is not a readable image", "sharpness": 0.0, "brightness": 0.0}
    g = img.convert("L")
    g.thumbnail((1000, 1000))
    w, h = g.size
    g = g.crop((int(w * 0.1), int(h * 0.1), int(w * 0.9), int(h * 0.9)))  # ignore borders and table edges
    lap = g.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128))
    sharp = ImageStat.Stat(lap).var[0]
    bright = ImageStat.Stat(g).mean[0]
    reason = None
    if sharp < BLUR_THRESHOLD:
        reason = "Image is blurry"
    elif bright < DARK_THRESHOLD:
        reason = "Image is too dark"
    return {"ok": reason is None, "reason": reason, "sharpness": round(sharp, 1), "brightness": round(bright, 1)}
