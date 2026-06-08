"""WebSocket transport. Connection lifecycle and message I/O.

Single wire shape: every message — incoming and outgoing — is an envelope
`{type, seq, payload}`. Messages that don't match are rejected.
"""

from __future__ import annotations

import asyncio
import json
import ssl
from typing import Any, Optional

import websockets
from websockets.asyncio.server import ServerConnection, serve

from harpoon import logging as log
from harpoon.dispatcher import Dispatcher
from harpoon.primitives import voting
from harpoon.protocol.envelope import wrap
from harpoon.room import Room
from harpoon.security.permissions import PermissionRegistry
from harpoon.security.ratelimit import RateLimiter
from harpoon.session import Session


async def _close_quietly(ws: ServerConnection, code: int, reason: str) -> None:
    """Close a ws and swallow any exception — used for early-rejection paths
    where we don't care if the peer already hung up."""
    try:
        await ws.close(code=code, reason=reason)
    except Exception:
        pass


class HarpoonServer:
    def __init__(self, host: str, port: int,
                 permissions: PermissionRegistry,
                 ssl_context: Optional[ssl.SSLContext] = None) -> None:
        self.host = host
        self.port = port
        self.ssl_context = ssl_context

        self.sessions: dict[int, Session] = {}    # client_id -> Session
        self.tokens: dict[str, Session] = {}      # token -> Session (for resume)
        self.rooms: dict[str, Room] = {}          # room_id -> Room

        self.rate_limiter = RateLimiter()
        self.dispatcher = Dispatcher(permissions, self.rate_limiter)
        self.dispatcher.server = self
        self.permissions = permissions

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def serve_forever(self) -> None:
        scheme = "wss" if self.ssl_context else "ws"
        log.info(f"Harpoon server listening on {scheme}://{self.host}:{self.port}")
        log.info(f"Loaded primitives: {len(self.dispatcher.list_primitives())}")
        async with serve(self._handle_connection, self.host, self.port,
                         ssl=self.ssl_context, max_size=2**20, ping_interval=20):
            await asyncio.Future()  # block forever

    # Resource caps. Idle ws drops after the timeout; the rest cap memory
    # against a hostile peer hammering connect / room_create.
    HANDSHAKE_TIMEOUT_SECONDS = 10.0
    MAX_CONCURRENT_SESSIONS = 256
    MAX_TOTAL_ROOMS = 64
    MAX_SESSIONS_PER_PEER = 4

    async def _handle_connection(self, ws: ServerConnection) -> None:
        if len(self.sessions) >= self.MAX_CONCURRENT_SESSIONS:
            log.warn(f"server full ({len(self.sessions)}) — refusing connection")
            await _close_quietly(ws, 1013, "server_full")
            return

        session = Session(ws)

        peer_count = sum(1 for s in self.sessions.values() if s.peer_hash == session.peer_hash)
        if peer_count >= self.MAX_SESSIONS_PER_PEER:
            log.warn(f"peer {session.peer_hash} at session cap — refusing")
            await _close_quietly(ws, 1013, "too_many_per_peer")
            return

        self.sessions[session.client_id] = session
        self.tokens[session.token] = session
        log.connect(f"id={session.client_id} peer={session.peer_hash}")

        await session.send("HARPOON.SERVER_INFO", {
            "client_id": session.client_id,
            "session_token": session.token,
        })

        # Drop the connection if no valid HARPOON.HANDSHAKE arrives in time.
        async def kick_if_no_handshake() -> None:
            try:
                await asyncio.sleep(self.HANDSHAKE_TIMEOUT_SECONDS)
                if not session.handshake_complete and session.connected:
                    log.warn(f"[id={session.client_id}] no handshake — closing")
                    session.connected = False
                    await _close_quietly(ws, 1008, "handshake_required")
            except asyncio.CancelledError:
                pass

        watchdog = asyncio.create_task(kick_if_no_handshake())

        try:
            async for raw in ws:
                if not isinstance(raw, str):
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError as e:
                    log.warn(f"[{session.name}] bad JSON: {e}")
                    continue
                if not isinstance(msg, dict):
                    continue
                # Pre-handshake: only HARPOON.HANDSHAKE / .RESUME allowed,
                # so the server can't be repurposed as a generic relay.
                if not session.handshake_complete:
                    msg_type = msg.get("type", "")
                    if msg_type not in ("HARPOON.HANDSHAKE", "HARPOON.RESUME"):
                        log.warn(f"[id={session.client_id}] pre-handshake msg rejected: {msg_type!r}")
                        continue
                await self.dispatcher.handle(session, msg)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            log.error(f"[{session.name}] connection crash: {e!r}")
        finally:
            watchdog.cancel()
            await self._cleanup_session(session)

    async def _cleanup_session(self, session: Session) -> None:
        log.disconnect(f"id={session.client_id} {session.name}")
        session.connected = False
        self.rate_limiter.forget(session.client_id)
        if session.room_id:
            await self.leave_room(session)
        self.sessions.pop(session.client_id, None)
        self.tokens.pop(session.token, None)

    # =========================================================================
    # Room management
    # =========================================================================

    def get_room(self, room_id: Optional[str]) -> Optional[Room]:
        if room_id is None:
            return None
        return self.rooms.get(room_id)

    def list_rooms(self) -> list[dict[str, Any]]:
        """Unfiltered room list — used internally / for diagnostics. Most
        callers should prefer `list_rooms_for(session)` so that clients only
        see rooms they have the gamemode pack installed for."""
        return [r.to_dict() for r in self.rooms.values()]

    def list_rooms_for(self, session: Session) -> list[dict[str, Any]]:
        """Per-session filtered room list. Hides any room whose gamemode_id
        the client doesn't have installed locally — that's the privacy
        mechanism for custom packs (Prop Hunt etc. stay invisible to anyone
        without the YAML).

        Legacy clients that don't announce a list (empty) get the full,
        unfiltered list — they'll happily ignore unknown gamemode_ids on
        their side anyway, and forcing them to send 0 rooms breaks the
        room browser without warning."""
        installed = session.installed_gamemodes or []
        if not installed:
            return self.list_rooms()
        installed_set = set(installed)
        return [r.to_dict() for r in self.rooms.values()
                if r.gamemode_id in installed_set]

    async def create_room(self, session: Session, name: str, gamemode_id: str,
                          password: str, max_players: int) -> Optional[Room]:
        # Hard cap on total rooms — a single bad actor can otherwise spam
        # ROOM.CREATE within their per-second rate limit and exhaust memory.
        if len(self.rooms) >= self.MAX_TOTAL_ROOMS:
            log.warn(f"room cap reached ({len(self.rooms)}/{self.MAX_TOTAL_ROOMS}) — refusing create from {session.name}")
            await session.send("HARPOON.ERROR", {
                "code": "server_full",
                "message": f"Server at room cap ({self.MAX_TOTAL_ROOMS}); try again later",
            })
            return None
        room = Room(Room.generate_id(), name, gamemode_id, password, max_players)
        self.rooms[room.room_id] = room
        room.add_session(session)
        log.room(room.room_id, f"created by {session.name} (gm={gamemode_id})")
        return room

    async def join_room(self, session: Session, room: Room) -> None:
        if session.room_id:
            await self.leave_room(session)
        room.add_session(session)
        log.room(room.room_id, f"{session.name} joined")

    async def leave_room(self, session: Session) -> None:
        room = self.get_room(session.room_id)
        if room is None:
            return
        room.remove_session(session.client_id)
        log.room(room.room_id, f"{session.name} left")
        if room.is_empty():
            self.rooms.pop(room.room_id, None)
            # Leak fix: cancel every pending vote-timeout task for this
            # room and drop the room's slot in voting._active. Without
            # this, abandoned vote timeouts sleep until their duration
            # elapses while pinning the deleted Room — the dominant
            # memory leak on a long-running server with room churn.
            voting.cleanup_room(room.room_id)
            log.room(room.room_id, "destroyed (empty)")
        else:
            await self.broadcast_room_members(room)

    # =========================================================================
    # Broadcast helpers — used by primitive handlers
    # =========================================================================

    async def broadcast_room(self, room: Room, type_: str, payload: dict[str, Any],
                             exclude_id: int = 0,
                             same_scene_as: Optional[Session] = None) -> None:
        """Send envelope to all members of `room`.

        - exclude_id: skip this client (typically the sender).
        - same_scene_as: Area-of-Interest filter — skip clients not in the same
          scene as `same_scene_as.scene_num` (or with no save loaded).
        """
        for s in room.members():
            if s.client_id == exclude_id:
                continue
            if same_scene_as is not None and (
                s.scene_num != same_scene_as.scene_num or not s.is_save_loaded):
                continue
            await s.send(type_, payload)

    async def send_to_client(self, client_id: int, type_: str,
                             payload: dict[str, Any]) -> None:
        """Send envelope to a single client by id (room-scoped delivery)."""
        s = self.sessions.get(client_id)
        if s is None:
            return
        await s.send(type_, payload)

    async def broadcast_room_members(self, room: Room) -> None:
        """Send the updated roster + room metadata to every member."""
        roster = [s.to_dict() for s in room.members()]
        for s in room.members():
            await s.send("ROOM.MEMBERS_UPDATED", {
                "ownClientId":  s.client_id,
                "hostClientId": room.host_client_id,
                "roomId":       room.room_id,
                "roomName":     room.name,
                "gameMode":     room.gamemode_id,
                "phase":        room.phase,
                "config":       room.config,
                "clients":      roster,
            })

    async def broadcast_room_list(self) -> None:
        """Send updated room list (`ROOM.LIST_RESPONSE`) to clients NOT in a
        room. Each client gets their own filtered view — only rooms whose
        gamemode_id is in their announced installed_gamemodes."""
        for s in self.sessions.values():
            if s.room_id is None:
                await s.send("ROOM.LIST_RESPONSE",
                             {"rooms": self.list_rooms_for(s)})
