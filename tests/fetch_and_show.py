"""
Simple command-line test that requests /quote-image from a running server,
saves the returned image to a file and attempts to open it with the default
image viewer (via Pillow.Image.show()).

Usage:
  python tests/fetch_and_show.py

Notes:
 - Assumes the server is already running on http://127.0.0.1:8101
 - Reads credentials from tests/config.cfg file
 - This is intended as a convenience developer test; adapt as needed.
"""
import os
import sys
import tempfile
import configparser
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


def load_credentials_from_config():
    """
    Load username and password from tests/config.cfg file.

    Returns:
        tuple: (username, password)

    Raises:
        SystemExit: If config file not found or credentials not present
    """
    config_path = Path("config.cfg")

    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)

    try:
        config = configparser.ConfigParser()
        config.read(config_path)

        if "CREDENTIALS" not in config:
            print("Error: [CREDENTIALS] section not found in config.cfg")
            sys.exit(1)

        username = config["CREDENTIALS"].get("username")
        password = config["CREDENTIALS"].get("password")

        if not username or not password:
            print("Error: username and password must be set in [CREDENTIALS] section of config.cfg")
            sys.exit(1)

        return username, password
    except Exception as e:
        print(f"Error: Failed to read config file: {e}")
        sys.exit(1)


def main():
    # Get credentials from config file
    username, password = load_credentials_from_config()

    # Authenticate and get token
    access_token = get_access_token(username, password)

    # Fetch and show image
    return fetch_image_and_show(access_token)


if __name__ == "__main__":
    sys.exit(main())
