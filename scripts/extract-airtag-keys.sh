#!/usr/bin/env bash
#
# APPENDIX — real AirTag only. The DIY/Flipper path does NOT need this.
#
# Locates the Find My beacon records on your Mac. On macOS 15+ (Sequoia/Tahoe) the
# records moved to the group container below AND are AES-GCM encrypted, so this
# script can only *find* them — decrypting needs the BeaconStore key, which on
# macOS 15+ requires temporarily disabling SIP and an entitled extractor:
#   https://github.com/pajowu/beaconstorekey-extractor
#
# Requires Full Disk Access on your terminal (System Settings > Privacy & Security
# > Full Disk Access > add your terminal > fully quit and reopen it).
#
set -euo pipefail

# macOS 15+ location, with a fallback to the pre-Sequoia path.
NEW="$HOME/Library/Group Containers/group.com.apple.icloud.searchpartyuseragent/Library/Storage"
OLD="$HOME/Library/com.apple.icloud.searchpartyd"

if [ -d "$NEW/OwnedBeacons" ]; then
  SP="$NEW"
elif [ -d "$OLD/OwnedBeacons" ]; then
  SP="$OLD"
else
  echo "ERROR: could not find OwnedBeacons under either:" >&2
  echo "  $NEW/OwnedBeacons" >&2
  echo "  $OLD/OwnedBeacons" >&2
  echo "Grant Full Disk Access (and fully restart the terminal), open Find My so it" >&2
  echo "syncs your Items, then retry." >&2
  exit 1
fi

echo "Found beacon storage at:"
echo "  $SP"
echo
echo "Owned beacon records:"
ls -1 "$SP/OwnedBeacons/"*.record 2>/dev/null || echo "  (none)"
echo
first="$(ls "$SP/OwnedBeacons/"*.record 2>/dev/null | head -1 || true)"
if [ -n "$first" ]; then
  echo "Format check (first record):"
  if plutil -p "$first" 2>/dev/null | grep -q '"privateKey"'; then
    echo "  -> readable plist (pre-Sequoia). You can convert it with FindMy.py directly."
  else
    echo "  -> ENCRYPTED (macOS 15+). A [nonce, tag, ciphertext] array, not a plist."
    echo "     You must extract the BeaconStore key (SIP disable required) and decrypt"
    echo "     before FindMy.py can use it. See the URL in this script's header."
  fi
fi
