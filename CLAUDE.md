# air-tag — Claude Code Context

## What this is

Self-hosted AirTag tracker + private Leaflet map. Polls Apple's Find My network,
decrypts location reports locally with the AirTag's private keys, stores points in
SQLite, serves a map via FastAPI. Deployed as a Docker service by `rpi-services`
(profile `airtag`, built from the CalVer tag). Reached only through Caddy on the
tailnet — no host port is published.

## Layout

```
app/
  config.py      env + persistent-file paths under /data
  db.py          aiosqlite store; points deduped on (ts, lat, lon)
  tracker.py     FindMy.py wrapper (load account/accessory, fetch_location_history)
  poller.py      background asyncio loop, POLL_INTERVAL
  login_cli.py   one-time interactive setup (import .plist + Apple login/2FA)
  main.py        FastAPI: /, /api/points, /api/status, /healthz
  templates/map.html, static/{app.js,style.css}
scripts/extract-airtag-keys.sh   run on the Mac to dump AirTag .record files
```

## Key facts

- Primary path is a **DIY tag** (Flipper Zero / ESP32): a static base64 private key
  in `AIRTAG_PRIVATE_KEY` (env) or `/data/private_key`. `tracker.load_device()`
  returns a `KeyPair` for this, or a `FindMyAccessory` (real AirTag) from
  `accessory.json`. `scripts/generate-key.py` makes the key + Flipper `.keys` file.
- Persistent state in `/data` (mounted from `appdata/air-tag/`, gitignored):
  `account.json` (Apple session), `private_key` / `accessory.json` (device),
  `airtag.db`, `plist/` (real-AirTag import only).
- Uses `findmy` (FindMy.py) + a burner Apple ID (independent of the tag keys).
  Anisette runs as its own container.
- Real AirTag extraction needs SIP disabled on macOS 15+ (records are AES-GCM
  encrypted in a data vault) — appendix only, not the default.
- Never commit `.env`, `data/`, `keys/`, `private_key`, `*.record`, `*.plist`,
  `account.json`, `accessory.json`, `*.db`.

## Security posture

Location data is sensitive. Keep it internal-only: no published host port, Caddy
allowlists the Tailscale/LAN ranges and enforces basic auth. Don't add a public
route or a host port mapping.
