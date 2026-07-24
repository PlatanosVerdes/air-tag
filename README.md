# air-tag

Self-hosted location tracker with a private map. Polls Apple's Find My network for
your tag's encrypted location reports, decrypts them locally, stores the points in
SQLite, and serves a Leaflet map of where the tag has been.

Runs on the Raspberry Pi home server as a Docker service (built by
[`rpi-services`](https://github.com/PlatanosVerdes/rpi-services)). No cloud, no
third party ever sees your location: decryption happens on your own hardware.

Primary hardware is a **DIY tag** (Flipper Zero via
[FindMyFlipper](https://github.com/MatthewKuKanich/FindMyFlipper), or an ESP32/nRF5x
running OpenHaystack firmware) whose keys you generate yourself. A genuine AirTag is
also supported but needs a one-time key extraction from a Mac (see the appendix) —
which on macOS 15+ requires temporarily disabling SIP, so DIY is recommended.

## How it works

```
┌──────────┐   auth headers   ┌───────────┐   encrypted reports   ┌─────────────┐
│ anisette │◀────────────────▶│  air-tag  │◀─────────────────────▶│ Apple Find  │
│ (Docker) │                  │  (Docker) │                       │ My network  │
└──────────┘                  └─────┬─────┘                       └─────────────┘
                                    │ decrypt with your private key
                                    ▼
                            SQLite  +  FastAPI/Leaflet map
```

Your tag broadcasts a BLE advertisement carrying its **public** key. Any nearby
iPhone grabs its GPS fix, encrypts it with that public key and uploads it to Apple.
The server downloads those encrypted reports and decrypts them with the matching
**private** key — which only you hold.

Why a burner Apple ID works: Apple lets *any* account download *any* encrypted
report as long as you know the public key. Only the private key can decrypt it. So
the login account and the tag keys are completely independent.

## Security model

This service exposes exactly where you move, so it is locked down deliberately:

- **No public exposure.** The container publishes **no host port**. The only way in
  is through Caddy, which only answers on the Pi's Tailscale IP (nothing is
  port-forwarded to the internet).
- **Tailnet/LAN allowlist.** The Caddy route returns `403` to any client outside the
  Tailscale CGNAT range and private LAN ranges.
- **Basic auth** on top, so a compromised or shared tailnet device still needs a
  password.
- **Secrets never leave the Pi.** The Apple session, the private key and the SQLite
  DB live in `appdata/air-tag/` (gitignored). Nothing sensitive is committed.
- Only the map *tiles* are fetched from a public tile server (CARTO/OSM) by the
  browser viewing the map. The location data itself never leaves your network.

## Setup (DIY tag — Flipper Zero)

### 1. Create a burner Apple ID

Make a throwaway Apple ID (appleid.apple.com) with SMS 2FA. Put it in
`rpi-services/.env` as `AIRTAG_APPLE_ID` / `AIRTAG_APPLE_PASSWORD`.

### 2. Generate a key pair

```bash
pip install cryptography
python3 scripts/generate-key.py
```

It writes a `<mac>.keys` file and prints your base64 private key. Two things come
out of it:
- The `.keys` file → goes on the **Flipper**.
- `AIRTAG_PRIVATE_KEY=...` → goes on the **server**.

### 3. Load the tag onto the Flipper

1. Install the **FindMyFlipper** app on the Flipper (Flipper mobile app catalog, or
   sideload the `.fap`). Updating the Flipper firmware first is recommended.
2. Copy the `.keys` file to the SD card under `apps_data/FindMyFlipper/`.
3. Open FindMyFlipper → config → **Import Tag From File** → pick your `.keys`.
   (Or "Register Tag Manually" using the MAC + Payload the script printed.)
4. Start broadcasting. Leave it near iPhones for a while so reports accumulate.

### 4. Configure and deploy the server

In `rpi-services/.env`:

```bash
AIRTAG_APPLE_ID=burner@example.com
AIRTAG_APPLE_PASSWORD=...
AIRTAG_PRIVATE_KEY=<base64 private key from step 2>
```

First login (creates the Apple session; asks for the SMS 2FA code):

```bash
cd ~/rpi-services
docker compose run --rm air-tag python -m app.login_cli
```

Set the Caddy password in `config/caddy/services.caddy` (replace
`REPLACE_WITH_BCRYPT_HASH`):

```bash
docker exec caddy caddy hash-password --plaintext 'your-strong-password'
docker compose -f ~/rpi-homeserver/compose-core.yml restart caddy
```

Bring it up (also part of the `all` profile):

```bash
docker compose up -d anisette air-tag
```

Open **https://airtag.platanosverdes.com** from any device on your tailnet.

## Configuration

| Env var | Default | Meaning |
| :--- | :--- | :--- |
| `AIRTAG_APPLE_ID` | – | Burner Apple ID email |
| `AIRTAG_APPLE_PASSWORD` | – | Burner Apple ID password |
| `AIRTAG_PRIVATE_KEY` | – | Base64 private key of your DIY tag |
| `AIRTAG_POLL_INTERVAL` | `900` | Seconds between polls to Apple |
| `ANISETTE_URL` | `http://anisette:6969` | Self-hosted anisette server |

## Data & endpoints

- `GET /` — the map.
- `GET /api/points?days=7` — stored points as JSON (also `since` / `until` unix seconds).
- `GET /api/status` — point count, last error, config state.
- `GET /healthz` — liveness.

## Limitations

- Coverage depends on how many Apple devices pass near the tag. Busy areas give a
  dense trail; empty areas give sparse points or none.
- Location history from Apple is best-effort (~7 days). The trail fills in and
  lengthens as the poller keeps running and accumulating points in SQLite.
- If Apple flags the burner account you may need to re-run `login_cli`.

## Appendix: using a real AirTag

Supported, but on macOS 15+ (Sequoia/Tahoe) the AirTag's keys sit in a
SIP-protected data vault and an encrypted keychain item, so extraction requires
**temporarily disabling SIP** (recovery mode + `amfi_get_out_of_my_way=1`) and
running an entitled extractor such as
[beaconstorekey-extractor](https://github.com/pajowu/beaconstorekey-extractor).
Once you have a decrypted `.plist`, drop it in `appdata/air-tag/plist/`, leave
`AIRTAG_PRIVATE_KEY` empty, and run `login_cli` — it imports the accessory instead
of using a static key. This path is not recommended unless you specifically need
that physical AirTag.
