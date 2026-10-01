"""Render synthetic handwritten papers (seed data and smoke tests only; never used in the reported evaluation)."""
from __future__ import annotations

import io
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import API_DIR

FONT_PATH = API_DIR / "assets" / "fonts" / "Caveat.ttf"
W, H = 1000, 1400
INK = [(28, 38, 92), (20, 20, 30), (40, 60, 120)]


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), size)


def render_paper(
    header: str,
    blocks: list[tuple[str, list[tuple[str, str, bool]]]],
    seed: int = 0,
    blur: bool = False,
    title_font: int = 46,
    line_font: int = 54,
) -> tuple[bytes, dict[str, list[float]]]:
    """blocks: [(label, [(unit_key, text, smudge), ...])]. Returns JPEG bytes and normalized bboxes per unit key."""
    rnd = random.Random(seed)
    img = Image.new("RGB", (W, H), (252, 251, 247))
    d = ImageDraw.Draw(img)
    # ruled paper
    for y in range(132, H, 56):
        d.line([(0, y), (W, y)], fill=(200, 215, 235), width=2)
    d.line([(90, 0), (90, H)], fill=(240, 170, 170), width=2)
    ink = rnd.choice(INK)
    d.text((120, 18), header, font=_font(title_font), fill=ink)
    boxes: dict[str, list[float]] = {}
    y = 84
    lf = _font(line_font)
    for label, lines in blocks:
        d.text((105, y), label, font=lf, fill=ink)
        for key, text, smudge in lines:
            x = 175 + rnd.randint(-6, 10)
            dy = rnd.randint(-4, 4)
            l, t, r, b = d.textbbox((x, y + dy), text, font=lf)
            d.text((x, y + dy), text, font=lf, fill=ink)
            pad = 8
            box = (max(0, l - pad), max(0, t - pad), min(W, r + pad), min(H, b + pad))
            if smudge:
                region = img.crop(box).filter(ImageFilter.GaussianBlur(1.8))
                smear = Image.new("RGB", region.size, (150, 150, 165))
                img.paste(Image.blend(region, smear, 0.18), box[:2])
                d = ImageDraw.Draw(img)
            boxes[key] = [round(box[0] / W, 4), round(box[1] / H, 4), round((box[2] - box[0]) / W, 4), round((box[3] - box[1]) / H, 4)]
            y += 56
        y += 18
        if y > H - 80:
            break
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(6))
    img = img.rotate(rnd.uniform(-1.2, 1.2), fillcolor=(235, 233, 228), resample=Image.BILINEAR)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=82)
    return out.getvalue(), boxes


def thumbnail_ok(data: bytes) -> bool:
    try:
        Image.open(io.BytesIO(data)).verify()
        return True
    except Exception:
        return False


CACHE_DIR = API_DIR / ".data" / "render-cache"


def render_paper_cached(header: str, blocks: list, seed: int = 0, blur: bool = False, **kw) -> tuple[bytes, dict[str, list[float]]]:
    """Same as render_paper, cached on disk by a hash of the inputs (seed images are deterministic)."""
    import hashlib
    import json

    key = hashlib.sha1(json.dumps([header, blocks, seed, blur, kw], sort_keys=True).encode()).hexdigest()
    img_p, box_p = CACHE_DIR / f"{key}.jpg", CACHE_DIR / f"{key}.json"
    if img_p.exists() and box_p.exists():
        return img_p.read_bytes(), json.loads(box_p.read_text())
    data, boxes = render_paper(header, blocks, seed=seed, blur=blur, **kw)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        img_p.write_bytes(data)
        box_p.write_text(json.dumps(boxes))
    except OSError:
        pass
    return data, boxes
