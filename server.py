#!/usr/bin/env python3
"""Harpoon WebSocket multiplayer server — entry point.

The server is intentionally gamemode-agnostic: no YAML packs, no manifest
loading. Permissions are built-in defaults; clients announce in the handshake
which gamemodes they have installed locally and the server filters the room
browser per-client. Custom / private gamemodes (Prop Hunt etc.) live only on
the clients that own the pack.

Usage:
    python server.py [--host 0.0.0.0] [--port 8765]
                     [--tls-cert PATH --tls-key PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import ssl
import sys

from harpoon import logging as log
from harpoon.primitives import register_all
from harpoon.security.permissions import PermissionRegistry
from harpoon.transport import HarpoonServer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Harpoon multiplayer server")
    p.add_argument("--host", default="0.0.0.0", help="Bind host (default 0.0.0.0)")
    p.add_argument("--port", type=int, default=8765, help="Bind port (default 8765)")
    p.add_argument("--tls-cert", help="Path to TLS certificate (enables WSS)")
    p.add_argument("--tls-key", help="Path to TLS private key (enables WSS)")
    return p.parse_args()


def build_ssl_context(cert_path: str | None, key_path: str | None) -> ssl.SSLContext | None:
    if not cert_path or not key_path:
        return None
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
    return ctx


async def amain() -> int:
    args = parse_args()

    # Built-in defaults — no YAML, no per-gamemode rules. The dispatcher uses
    # this to look up rate limits + scope for each registered primitive.
    permissions = PermissionRegistry()

    # SSL (optional).
    ssl_ctx = build_ssl_context(args.tls_cert, args.tls_key)

    # Server.
    server = HarpoonServer(args.host, args.port, permissions, ssl_ctx)

    # Register all primitives.
    register_all(server.dispatcher)

    log.info(f"Registered {len(server.dispatcher.list_primitives())} primitives:")
    for name in server.dispatcher.list_primitives():
        log.info(f"  - {name}")

    await server.serve_forever()
    return 0


def main() -> int:
    try:
        return asyncio.run(amain())
    except KeyboardInterrupt:
        log.info("Shutting down (Ctrl+C)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
