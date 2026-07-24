"""Thin wrapper around FindMy.py: load the account + device and fetch reports.

A "device" is either:
  - a DIY/Flipper tag  -> a static ``KeyPair`` (from a base64 private key), or
  - a real AirTag      -> a ``FindMyAccessory`` (from a decrypted .plist).
"""

from __future__ import annotations

import logging

from findmy import (
    AsyncAppleAccount,
    FindMyAccessory,
    KeyPair,
    LocationReport,
    RemoteAnisetteProvider,
)

from . import config

logger = logging.getLogger(__name__)

Device = KeyPair | FindMyAccessory


def load_device() -> Device:
    """Load the trackable device. A DIY static key takes precedence."""
    key_b64 = config.private_key_b64()
    if key_b64 is not None:
        return KeyPair.from_b64(key_b64)
    return FindMyAccessory.from_json(config.ACCESSORY_PATH)


def persist_device(device: Device) -> None:
    """Persist learned state. Only AirTag accessories carry rolling-key alignment."""
    if isinstance(device, FindMyAccessory):
        device.to_json(config.ACCESSORY_PATH)


def new_account() -> AsyncAppleAccount:
    """Fresh account bound to our self-hosted anisette server (for first login)."""
    return AsyncAppleAccount(RemoteAnisetteProvider(config.ANISETTE_URL))


def restore_account() -> AsyncAppleAccount:
    """Restore a previously-saved Apple session (anisette config is embedded)."""
    return AsyncAppleAccount.from_json(config.ACCOUNT_PATH)


def import_plist_to_accessory() -> bool:
    """Convert a decrypted AirTag .plist/.record in PLIST_DIR into accessory.json.

    Only relevant for real AirTags. Returns True if an accessory.json was written.
    """
    if not config.PLIST_DIR.exists():
        return False

    candidates = sorted(
        p
        for p in config.PLIST_DIR.iterdir()
        if p.suffix in (".plist", ".record") and "alignment" not in p.name.lower()
    )
    if not candidates:
        return False

    accessory_plist = candidates[0]
    alignment = next(
        (p for p in config.PLIST_DIR.iterdir() if "alignment" in p.name.lower()), None
    )
    logger.info("Importing accessory from %s (alignment=%s)", accessory_plist.name, alignment)

    accessory = FindMyAccessory.from_plist(accessory_plist, alignment)
    accessory.to_json(config.ACCESSORY_PATH)
    return True


async def fetch_reports(account: AsyncAppleAccount, device: Device) -> list[LocationReport]:
    """Fetch (and decrypt) recent location reports for the device."""
    reports = await account.fetch_location_history(device)
    return list(reports)


def report_to_row(report: LocationReport) -> tuple[int, float, float, int, int]:
    return (
        int(report.timestamp.timestamp()),
        float(report.latitude),
        float(report.longitude),
        int(report.horizontal_accuracy),
        int(report.status),
    )
