#!/usr/bin/env python3
"""
Simple command-line test that starts the FastAPI app, requests /quote-image,
saves the returned image to a file and attempts to open it with the default
image viewer (via Pillow.Image.show()).

Usage:
  python tests/fetch_and_show.py

Notes:
 - The script will forward your OPENAI_API_KEY environment variable to the
   server process. If you don't have a key set, the server will fail to
   generate via OpenAI; in that case the script will print the server output
   so you can diagnose the issue.
 - This is intended as a convenience developer test; adapt as needed.
"""
import os
import sys
import time
import subprocess
import signal
import tempfile
from pathlib import Path

import requests
from PIL import Image


PORT = 8101
URL = f"http://127.0.0.1:{PORT}/quote-image"


def start_server():
    env = os.environ.copy()
    # Run uvicorn in a subprocess
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    return proc


def wait_for_server(timeout=30.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.options(f"http://127.0.0.1:{PORT}/")
            # If any response, consider server up
            return True
        except Exception:
            time.sleep(0.5)
    return False


def fetch_image_and_show():
    r = requests.post(URL, json={}, stream=True, timeout=60)
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
    proc = start_server()
    try:
        if not wait_for_server(timeout=20.0):
            print("Server did not start in time. Dumping server output:")
            out, _ = proc.communicate(timeout=1)
            print(out.decode(errors="replace") if out else "<no output>")
            return 2

        return fetch_image_and_show()
    finally:
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
