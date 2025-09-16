#!/usr/bin/env python3
"""
Simple command-line test that requests /quote-image from a running server,
saves the returned image to a file and attempts to open it with the default
image viewer (via Pillow.Image.show()).

Usage:
  python tests/fetch_and_show.py

Notes:
 - Assumes the server is already running on http://127.0.0.1:8101
 - This is intended as a convenience developer test; adapt as needed.
"""
import tempfile
from pathlib import Path

import requests
from PIL import Image


PORT = 8101
URL = f"http://127.0.0.1:{PORT}/quote-image"


def fetch_image_and_show():
    r = requests.post(URL, json={}, stream=True, timeout=120)
    if r.status_code != 200:
        print("Server returned error:", r.status_code, r.text)
        return 1

    tmpdir = Path(tempfile.mkdtemp(prefix="quote_img_"))
    out_path = tmpdir / "quote.png"
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)

    print(f"Saved image to: {out_path}")
    img = Image.open(out_path)
    img.show()
    return 0


def main():
    return fetch_image_and_show()


if __name__ == "__main__":
    import sys
    sys.exit(main())
