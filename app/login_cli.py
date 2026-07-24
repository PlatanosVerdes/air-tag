"""One-time interactive setup: log the Apple account in (and import AirTag keys if any).

Run once (with a TTY):

    docker compose run --rm air-tag python -m app.login_cli

DIY / Flipper tag: set AIRTAG_PRIVATE_KEY (or drop the base64 key in /data/private_key)
and this just logs the burner Apple account in.

Real AirTag: copy a decrypted .plist into /data/plist first; it is imported here.
"""

from __future__ import annotations

import asyncio
import logging

from findmy import LoginState, SmsSecondFactorMethod, TrustedDeviceSecondFactorMethod

from . import config, tracker

logging.basicConfig(level=logging.INFO)


async def _do_2fa(account) -> None:
    methods = await account.get_2fa_methods()
    for i, method in enumerate(methods):
        if isinstance(method, TrustedDeviceSecondFactorMethod):
            print(f"  {i} - Trusted device")
        elif isinstance(method, SmsSecondFactorMethod):
            print(f"  {i} - SMS ({method.phone_number})")
        else:
            print(f"  {i} - {method}")
    idx = int(input("2FA method? > "))
    method = methods[idx]
    await method.request()
    code = input("Code? > ")
    await method.submit(code)


async def main() -> int:
    # Step 1: make sure a trackable device is configured.
    if config.private_key_b64() is not None:
        print("Using DIY/Flipper static key.")
    elif config.ACCESSORY_PATH.exists():
        print(f"Using AirTag accessory at {config.ACCESSORY_PATH}")
    elif tracker.import_plist_to_accessory():
        print(f"Imported AirTag accessory -> {config.ACCESSORY_PATH}")
    else:
        print(
            "ERROR: no device configured.\n"
            "  DIY/Flipper: set AIRTAG_PRIVATE_KEY (base64) or write it to "
            f"{config.KEY_PATH}\n"
            "  Real AirTag: drop a decrypted .plist in "
            f"{config.PLIST_DIR}"
        )
        return 1

    # Step 2: Apple login (burner account).
    if config.ACCOUNT_PATH.exists():
        print(f"account.json already present at {config.ACCOUNT_PATH} — skipping login.")
        return 0

    email = config.APPLE_ID or input("Apple ID email? > ")
    password = config.APPLE_PASSWORD or input("Apple ID password? > ")

    account = tracker.new_account()
    try:
        state = await account.login(email, password)
        if state == LoginState.REQUIRE_2FA:
            await _do_2fa(account)
        print(f"Logged in as: {account.account_name}")
        account.to_json(config.ACCOUNT_PATH)
        print(f"Saved session -> {config.ACCOUNT_PATH}")
    finally:
        await account.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
