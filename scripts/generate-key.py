#!/usr/bin/env python3
"""Generate an OpenHaystack / Find My key pair for a DIY tag (e.g. Flipper Zero).

Writes a `.keys` file (to load onto the Flipper) and prints the base64 private key
you set as AIRTAG_PRIVATE_KEY on the server. Compatible with FindMyFlipper and
FindMy.py (SECP224R1, 28-byte keys).

Requires: pip install cryptography

Usage:
    python3 scripts/generate-key.py [output_dir]     (default: ./keys)
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec


def advertisement_template() -> bytearray:
    adv = "1eff4c001219" + "00" + "00" * 22 + "00" + "00"
    return bytearray.fromhex(adv)


def mac_and_payload(pub_x: bytes) -> tuple[str, str]:
    addr = bytearray(pub_x[:6])
    addr[0] |= 0b11000000
    adv = advertisement_template()
    adv[7:29] = pub_x[6:28]
    adv[29] = pub_x[0] >> 6
    return addr.hex(), adv.hex()


def main(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Retry until the hashed adv key has no '/' in its first 7 chars (Flipper quirk).
    while True:
        priv = ec.generate_private_key(ec.SECP224R1(), default_backend())
        priv_bytes = priv.private_numbers().private_value.to_bytes(28, "big")
        pub_x = priv.public_key().public_numbers().x.to_bytes(28, "big")

        priv_b64 = base64.b64encode(priv_bytes).decode()
        pub_b64 = base64.b64encode(pub_x).decode()
        digest = hashes.Hash(hashes.SHA256())
        digest.update(pub_x)
        hashed_b64 = base64.b64encode(digest.finalize()).decode()
        if "/" not in hashed_b64[:7]:
            break

    mac, payload = mac_and_payload(pub_x)
    keyfile = out_dir / f"{mac}.keys"
    keyfile.write_text(
        f"Private key: {priv_b64}\n"
        f"Advertisement key: {pub_b64}\n"
        f"Hashed adv key: {hashed_b64}\n"
        f"MAC: {mac}\n"
        f"Payload: {payload}\n"
    )

    print("=" * 70)
    print("Flipper key file written to:", keyfile)
    print("  -> copy it to the Flipper SD card under: apps_data/FindMyFlipper/")
    print("=" * 70)
    print()
    print("SERVER: set this as AIRTAG_PRIVATE_KEY in rpi-services/.env")
    print()
    print("  AIRTAG_PRIVATE_KEY=" + priv_b64)
    print()
    print("Keep the private key secret — it decrypts this tag's location.")
    return 0


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("keys")
    raise SystemExit(main(out))
