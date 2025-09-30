"""
Simple command-line test that requests /quote-image from a running server,
saves the returned image to a file and attempts to open it with the default
image viewer (via Pillow.Image.show()).

Usage:
  python tests/fetch_and_show.py [username] [password]

Notes:
 - Assumes the server is already running on http://127.0.0.1:8101
 - Defaults to username=demo, password=democlient321 if not provided
 - This is intended as a convenience developer test; adapt as needed.
"""
import os
import sys
import tempfile
from pathlib import Path

import requests
from PIL import Image


PORT = 8101
BASE_URL = f"http://127.0.0.1:{PORT}"
TOKEN_URL = f"{BASE_URL}/token"
QUOTE_IMAGE_URL = f"{BASE_URL}/quote-image"


def get_access_token(username: str, password: str) -> str:
    """
    Authenticate with the API and retrieve an access token.

    Args:
        username: The username for authentication
        password: The password for authentication

    Returns:
        The access token string

    Raises:
        SystemExit: If authentication fails
    """
    print(f"Authenticating as '{username}'...")

    try:
        r = requests.post(
            TOKEN_URL,
            data={
                "username": username,
                "password": password
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            timeout=10
        )

        if r.status_code != 200:
            print(f"Authentication failed: {r.status_code} - {r.text}")
            sys.exit(1)

        token_data = r.json()
        access_token = token_data.get("access_token")

        if not access_token:
            print("No access token in response")
            sys.exit(1)

        print("✓ Authentication successful")
        return access_token

    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to authentication endpoint: {e}")
        sys.exit(1)


def fetch_image_and_show(access_token: str):
    """
    Fetch a quote image from the API and display it.

    Args:
        access_token: The JWT access token for authentication

    Returns:
        0 on success, 1 on failure
    """
    print("Requesting quote image...")

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    try:
        r = requests.post(QUOTE_IMAGE_URL, json={}, headers=headers, stream=True, timeout=120)

        if r.status_code == 401:
            print("Authentication required or token expired")
            return 1

        if r.status_code != 200:
            print(f"Server returned error: {r.status_code} - {r.text}")
            return 1

        tmpdir = Path(tempfile.mkdtemp(prefix="quote_img_"))
        out_path = tmpdir / "quote.png"

        with open(out_path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)

        print(f"✓ Saved image to: {out_path}")
        img = Image.open(out_path)
        img.show()
        return 0

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch image: {e}")
        return 1


def main():
    # Get credentials from command line args or use defaults
    username = sys.argv[1] if len(sys.argv) > 1 else os.getenv("API_USERNAME", "demo")
    password = sys.argv[2] if len(sys.argv) > 2 else os.getenv("API_PASSWORD", "password")

    # Authenticate and get token
    access_token = get_access_token(username, password)

    # Fetch and show image
    return fetch_image_and_show(access_token)


if __name__ == "__main__":
    sys.exit(main())
