"""Session — a connected client.

Identified by a 256-bit token (NEVER by IP). The numeric `client_id` is kept
because clients use it to address each other (target=N), but the source of
truth for identity across reconnects is the token.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
from typing import Any, Optional

from websockets.asyncio.server import ServerConnection

from harpoon.protocol.envelope import wrap
from harpoon.security.auth import generate_token


# Random salt regenerated on every server boot. Keeps `peer_hash` stable
# within a run (operator can correlate connect/disconnect for one peer)
# but unrecoverable across restarts and across hosts.
_PEER_HASH_SALT = os.urandom(16).hex()


class Session:
    _next_id = 1
    _id_lock = threading.Lock()

    def __init__(self, ws: ServerConnection) -> None:
        self.ws = ws
        with Session._id_lock:
            self.client_id = Session._next_id
            Session._next_id += 1

        self.token: str = generate_token()
        self.role: str = "player"           # "player" | "admin" | "host"
        self.name: str = f"Player{self.client_id}"
        self.color: dict[str, int] = {"r": 100, "g": 255, "b": 100}
        self.client_version: str = ""
        # Gamemode pack ids the client has locally. Used to filter the
        # room browser per-client (they only see rooms for packs they own).
        self.installed_gamemodes: list[str] = []

        # Visual / world state — updated by PLAYER.UPDATE_VISUAL_STATE
        self.is_save_loaded: bool = False
        self.scene_num: int = 255
        self.entrance_index: int = 0
        self.link_age: int = 0

        # Last-known transform cache (for late joiners / interest management)
        self.last_transform: dict[str, Any] = {}

        # Room membership
        self.room_id: Optional[str] = None

        # Salted hash of the peer IP — the only diagnostic identifier
        # we keep. Raw IP is never stored or broadcast.
        self.peer_hash = self._extract_peer_hash(ws)
        self.handshake_complete: bool = False
        self._send_lock = asyncio.Lock()
        self.connected: bool = True

    @staticmethod
    def _extract_peer_hash(ws: ServerConnection) -> str:
        try:
            sock = ws.transport.get_extra_info("peername")  # type: ignore[attr-defined]
            ip = sock[0] if sock else "?"
        except Exception:
            ip = "?"
        return hashlib.sha256((_PEER_HASH_SALT + ip).encode("utf-8")).hexdigest()[:8]

    async def send(self, type_: str, payload: dict[str, Any] | None = None, seq: int = 0) -> None:
        """Send an envelope `{type, seq, payload}`. Silent on broken pipe."""
        if not self.connected:
            return
        msg = wrap(type_, payload, seq)
        try:
            async with self._send_lock:
                await self.ws.send(json.dumps(msg, separators=(",", ":")))
        except Exception:
            self.connected = False

    def to_dict(self) -> dict[str, Any]:
        """Public profile broadcast to the room. NEVER includes IP/token."""
        return {
            "clientId": self.client_id,
            "name": self.name,
            "color": self.color,
            "online": self.connected,
            "role": self.role,
            "isSaveLoaded": self.is_save_loaded,
            "sceneNum": self.scene_num,
            "linkAge": self.link_age,
        }

    def __repr__(self) -> str:
        return f"<Session id={self.client_id} name={self.name!r} room={self.room_id}>"
