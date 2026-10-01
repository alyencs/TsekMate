"""Shared test helpers."""
from __future__ import annotations

TEACHER = {"email": "areyes@university.edu.ph", "password": "tsekmate"}  # development defaults (no .env in tests)


def sign_in(client) -> str:
    """Sign the test client in as the teacher; every later request sends the bearer token."""
    r = client.post("/api/auth/signin", json=TEACHER)
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return token


_n = [0]


def blank(size: tuple[int, int]):
    """A white page that is still a different photo every time (the API refuses the same photo twice per activity)."""
    from PIL import Image

    _n[0] += 1
    img = Image.new("RGB", size, "white")
    for i in range(8):  # an 8-pixel serial number; survives JPEG compression well enough to change the bytes
        img.putpixel((i, 0), (0, 0, 0) if (_n[0] >> i) & 1 else (255, 255, 255))
    img.putpixel((9, 0), ((_n[0] * 37) % 256, (_n[0] * 91) % 256, (_n[0] * 13) % 256))
    return img
