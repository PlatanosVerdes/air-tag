"""Runtime configuration, read from environment."""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))

# Persistent state files.
ACCOUNT_PATH = DATA_DIR / "account.json"      # Apple login session
KEY_PATH = DATA_DIR / "private_key"           # DIY/Flipper static key (base64), file fallback
ACCESSORY_PATH = DATA_DIR / "accessory.json"  # real AirTag key source (from a decrypted .plist)
PLIST_DIR = DATA_DIR / "plist"                # drop a decrypted AirTag .plist here to import
DB_PATH = DATA_DIR / "airtag.db"

APPLE_ID = os.environ.get("APPLE_ID", "")
APPLE_PASSWORD = os.environ.get("APPLE_PASSWORD", "")
ANISETTE_URL = os.environ.get("ANISETTE_URL", "http://anisette:6969")

# DIY / Flipper tag: base64 private key (from generate-key.py / FindMyFlipper).
# Takes precedence over an AirTag accessory.json when set.
PRIVATE_KEY = os.environ.get("AIRTAG_PRIVATE_KEY", "").strip()

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "900"))
TZ = os.environ.get("TZ", "Europe/Madrid")


def private_key_b64() -> str | None:
    """The static DIY key from env, or the key file, if present."""
    if PRIVATE_KEY:
        return PRIVATE_KEY
    if KEY_PATH.exists():
        return KEY_PATH.read_text().strip() or None
    return None


def has_device() -> bool:
    """True if a trackable device is configured (a DIY key or an AirTag accessory)."""
    return private_key_b64() is not None or ACCESSORY_PATH.exists()


def is_configured() -> bool:
    """True once the Apple session and a trackable device are both present."""
    return ACCOUNT_PATH.exists() and has_device()
