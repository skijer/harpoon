# Harpoon

> **Multiplayer server for Ship of Harkinian.** Play *Ocarina of Time*
> together — coop randomizer, story coop, and any custom gamemode the
> client adds — over a single WebSocket relay.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

The server is a thin relay: it routes messages between rooms of clients,
applies rate limits, and filters who sees which rooms. **It knows nothing
about specific gamemodes** — gameplay logic lives entirely in the client.
Clients announce in their handshake which gamemode packs they have
installed locally and only see rooms for those packs.

To play you need the matching client:
[`skijer/Shipwright` — branch `Not-Enough-Items`](https://github.com/skijer/Shipwright/tree/Not-Enough-Items).
Vanilla Shipwright builds do not speak this protocol.

---

## Quick start

```bash
git clone https://github.com/skijer/harpoon.git
cd harpoon
python -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python server.py
```

The server listens on `ws://0.0.0.0:8765` by default.

To override host or port:
```bash
python server.py --host 0.0.0.0 --port 8765
```

### Requirements
- Python 3.11+
- A reachable port (default 8765). Open it in your firewall / cloud
  security group if you want remote players.

### Connecting a client
In SoH's network menu, point Host at your server's address and Port at
8765. Use `ws://` for plain (LAN, dev) and `wss://` for production —
see the TLS section below.

---

## TLS / public deployment

The server speaks plain `ws://`. For anything beyond LAN, terminate TLS
at a reverse proxy. The simplest setup is [Caddy](https://caddyserver.com)
— auto-provisions Let's Encrypt:

```caddyfile
harpoon.example.com {
    reverse_proxy 127.0.0.1:8765
}
```

Bind the Python server to `127.0.0.1` so only Caddy can reach it.
Players connect to `wss://harpoon.example.com`.

The same pattern works behind an AWS ALB (HTTPS listener with an ACM
cert, target group → EC2 port 8765). Bump the ALB idle timeout to
3600s — the default 60s kills WebSocket connections.

---

## What the server does

- **Lobby & rooms.** Players create / list / join rooms; the server
  tracks membership and broadcasts roster updates.
- **Per-scene area-of-interest.** Per-frame state (position, skeleton,
  custom items) only goes to teammates in the same scene as the
  sender. Cuts bandwidth and prevents leaking activity outside the
  scene.
- **Token-based session resume.** Clients can reconnect with a
  256-bit token issued at handshake without re-announcing identity.
- **Schema validation.** Every primitive has a [pydantic](https://docs.pydantic.dev)
  schema with size and type bounds. Malformed payloads are rejected
  before they reach any handler.
- **Rate limits + role gating.** Built-in defaults per primitive
  (e.g. `PLAYER.UPDATE_FULL_STATE` 60/sec, `INVENTORY.GIVE_ITEM`
  200/sec). Admin / host primitives require the matching role.

---

## Privacy / hardening

- **Per-process IP hashing.** Raw client IPs are never written to logs
  or sent to other clients. Each connection gets a salted-and-truncated
  SHA256 hash that's stable for a server run, useless across restarts.
- **No personal data persisted.** No database, no IP logs, no message
  archive. Everything lives in memory and is gone on restart.
- **Connection caps.** 256 concurrent sessions, 4 per peer hash, 64
  total rooms. Tunable in `transport.py`.
- **Handshake watchdog.** Connections that don't send a valid
  `HARPOON.HANDSHAKE` within 10s are dropped. Pre-handshake messages
  other than HANDSHAKE / RESUME are rejected.
- **Protocol marker.** Handshake must include `protocol="harpoon"`.
  Soft barrier against the server being repurposed as a generic relay.

The server is **honest-operator trust**: anyone running it can read
every message in plaintext. For end-to-end privacy run your own
instance — the same model as gb-yoshi-web, syncplay, and similar
hobby relays.

---

## Project layout

```
harpoon/
  protocol/         JSON envelope + pydantic schemas
  primitives/       Per-domain handlers (player, combat, save, …)
  security/         Permission table + rate limiter + token gen
  transport.py      WebSocket lifecycle + AOI broadcasting
  dispatcher.py     Routes messages to primitives by name
  session.py        Per-connection state
  room.py           Room membership + config
  logging.py        Coloured console logging
server.py           Entry point — argparse, SSL setup, serves forever
```

Adding a new primitive:
1. Define a pydantic schema in `harpoon/primitives/<domain>.py`
2. Register it with `@d.register("DOMAIN.NAME", schema=…)`
3. Add a rule to `_PLAYER_DEFAULTS` (or `_ADMIN_EXTRAS` / `_HOST_EXTRAS`)
   in `harpoon/security/permissions.py`

That's it — the dispatcher picks it up at startup.

---

## Acknowledgements

- **[HarbourMasters](https://github.com/HarbourMasters)** — Ship of
  Harkinian and libultraship.
- **[@garrettjoecox](https://github.com/garrettjoecox)** — [Anchor](https://github.com/garrettjoecox/OOT),
  whose save-sync model the randomizer mode is based on.
- **[zeldaret/oot](https://github.com/zeldaret/oot)** — the OoT
  decompilation everything stands on.

— Maintained by [@skijer](https://github.com/skijer).
