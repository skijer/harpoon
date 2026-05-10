"""HARPOON.* and ROOM.* — connection lifecycle and room management."""

from __future__ import annotations

from harpoon import logging as log
from harpoon.dispatcher import Dispatcher
from harpoon.protocol.schemas import (
    HarpoonHandshake, HarpoonResume,
    RoomCreate, RoomJoin, RoomLeave, RoomList,
    RoomSetGamemodeId, RoomSetGamemodeConfig, RoomSetPhase, RoomSetTimer,
    RoomBroadcastEvent, RoomStartGame, RoomSelectMap,
)


def register(d: Dispatcher) -> None:

    # =========================================================================
    # HARPOON.HANDSHAKE — set name/color/version
    # =========================================================================
    @d.register("HARPOON.HANDSHAKE", schema=HarpoonHandshake,
                default_role="player", default_scope="self")
    async def handshake(server, session, room, target, p: HarpoonHandshake):
        # Reject non-Harpoon clients so the server can't be repurposed as a
        # generic WS relay. Soft barrier — the literal is public.
        if p.protocol and p.protocol != "harpoon":
            await session.send("HARPOON.ERROR", {
                "code": "wrong_protocol",
                "message": f"Expected protocol='harpoon', got {p.protocol!r}",
            })
            try:
                await session.ws.close(code=1008, reason="wrong_protocol")
            except Exception:
                pass
            return

        session.name = p.name
        session.color = p.color.model_dump()
        session.client_version = p.client_version
        session.installed_gamemodes = list(p.installed_gamemodes)
        session.handshake_complete = True
        log.player(f"{session.name} handshake (id={session.client_id} v={p.client_version} "
                   f"gamemodes={session.installed_gamemodes})")
        await session.send("HARPOON.HANDSHAKE_ACK", {
            "client_id": session.client_id,
            "session_token": session.token,
        })
        await session.send("ROOM.LIST_RESPONSE",
                           {"rooms": server.list_rooms_for(session)})

    # =========================================================================
    # HARPOON.RESUME — reconnect using a session_token issued by a prior connect.
    # =========================================================================
    @d.register("HARPOON.RESUME", schema=HarpoonResume,
                default_role="player", default_scope="self")
    async def resume(server, session, room, target, p: HarpoonResume):
        prior = server.tokens.get(p.session_token)
        if prior is None or prior.client_id == session.client_id:
            await session.send("HARPOON.ERROR", {
                "code": "resume_unknown",
                "message": "Token not recognized",
            })
            return
        session.client_id = prior.client_id
        session.name = prior.name
        session.color = prior.color
        session.role = prior.role
        session.installed_gamemodes = list(prior.installed_gamemodes)
        session.handshake_complete = True
        if prior.room_id and prior.room_id in server.rooms:
            r = server.rooms[prior.room_id]
            r.sessions[session.client_id] = session
            session.room_id = prior.room_id
        server.sessions.pop(prior.client_id, None)
        log.info(f"{session.name} resumed session id={session.client_id}")
        await session.send("HARPOON.RESUMED", {
            "client_id": session.client_id,
            "room_id": session.room_id,
        })

    # =========================================================================
    # ROOM.CREATE
    # =========================================================================
    @d.register("ROOM.CREATE", schema=RoomCreate,
                default_role="player", default_scope="self")
    async def room_create(server, session, room, target, p: RoomCreate):
        # A client can only create rooms for gamemodes it has installed.
        # Empty list = client didn't announce; allow through.
        installed = session.installed_gamemodes or []
        if installed and p.gamemode_id not in installed:
            await session.send("HARPOON.ERROR", {
                "code": "gamemode_not_installed",
                "message": f"You don't have the '{p.gamemode_id}' pack installed locally",
            })
            return
        if session.room_id:
            await server.leave_room(session)
        new_room = await server.create_room(session, p.name, p.gamemode_id,
                                             p.password, p.max_players)
        if new_room is None:
            # Hit the server-wide room cap; create_room already sent the error.
            return
        await session.send("ROOM.JOINED", {
            "room_id": new_room.room_id,
            "room_name": new_room.name,
            "gamemode_id": new_room.gamemode_id,
        })
        await server.broadcast_room_members(new_room)
        await server.broadcast_room_list()

    # =========================================================================
    # ROOM.JOIN
    # =========================================================================
    @d.register("ROOM.JOIN", schema=RoomJoin,
                default_role="player", default_scope="self")
    async def room_join(server, session, room, target, p: RoomJoin):
        target_room = server.get_room(p.room_id)
        if target_room is None:
            await session.send("HARPOON.ERROR", {
                "code": "room_not_found", "message": f"Room {p.room_id} not found"})
            return
        # Block joining a gamemode the client didn't announce as installed.
        # Empty list = client didn't announce; allow through.
        installed = session.installed_gamemodes or []
        if installed and target_room.gamemode_id not in installed:
            await session.send("HARPOON.ERROR", {
                "code": "gamemode_not_installed",
                "message": f"You don't have the '{target_room.gamemode_id}' pack installed locally",
            })
            return
        if target_room.password and target_room.password != p.password:
            await session.send("HARPOON.ERROR", {
                "code": "wrong_password", "message": "Wrong password"})
            return
        if target_room.is_full():
            await session.send("HARPOON.ERROR", {
                "code": "room_full", "message": "Room is full"})
            return
        await server.join_room(session, target_room)
        await session.send("ROOM.JOINED", {
            "room_id": target_room.room_id,
            "room_name": target_room.name,
            "gamemode_id": target_room.gamemode_id,
        })
        await server.broadcast_room_members(target_room)
        await server.broadcast_room_list()

    # =========================================================================
    # ROOM.LEAVE
    # =========================================================================
    @d.register("ROOM.LEAVE", schema=RoomLeave,
                default_role="player", default_scope="self")
    async def room_leave(server, session, room, target, p: RoomLeave):
        await server.leave_room(session)
        await session.send("ROOM.LEFT", {})
        await session.send("ROOM.LIST_RESPONSE",
                           {"rooms": server.list_rooms_for(session)})
        await server.broadcast_room_list()

    # =========================================================================
    # ROOM.LIST
    # =========================================================================
    @d.register("ROOM.LIST", schema=RoomList,
                default_role="player", default_scope="self")
    async def room_list(server, session, room, target, p: RoomList):
        await session.send("ROOM.LIST_RESPONSE",
                           {"rooms": server.list_rooms_for(session)})

    # =========================================================================
    # ROOM.SET_GAMEMODE_ID — only host
    # =========================================================================
    @d.register("ROOM.SET_GAMEMODE_ID", schema=RoomSetGamemodeId,
                default_role="host", default_scope="room")
    async def set_gamemode_id(server, session, room, target, p: RoomSetGamemodeId):
        if room is None: return
        room.gamemode_id = p.gamemode_id
        log.room(room.room_id, f"gamemode_id -> {p.gamemode_id}")
        await server.broadcast_room(room, "ROOM.GAMEMODE_CHANGED",
                                    {"gamemode_id": p.gamemode_id})
        await server.broadcast_room_members(room)

    # =========================================================================
    # ROOM.SET_GAMEMODE_CONFIG — opaque config blob
    # =========================================================================
    @d.register("ROOM.SET_GAMEMODE_CONFIG", schema=RoomSetGamemodeConfig,
                default_role="admin", default_scope="room")
    async def set_gamemode_config(server, session, room, target, p: RoomSetGamemodeConfig):
        if room is None: return
        room.config = p.config
        await server.broadcast_room(room, "ROOM.GAMEMODE_CONFIG", {"config": p.config})

    # =========================================================================
    # ROOM.SET_PHASE
    # =========================================================================
    @d.register("ROOM.SET_PHASE", schema=RoomSetPhase,
                default_role="admin", default_scope="room")
    async def set_phase(server, session, room, target, p: RoomSetPhase):
        if room is None: return
        room.phase = p.phase
        log.room(room.room_id, f"phase -> {p.phase}")
        await server.broadcast_room(room, "ROOM.PHASE_CHANGED", {"phase": p.phase})

    # =========================================================================
    # ROOM.SET_TIMER
    # =========================================================================
    @d.register("ROOM.SET_TIMER", schema=RoomSetTimer,
                default_role="admin", default_scope="room")
    async def set_timer(server, session, room, target, p: RoomSetTimer):
        if room is None: return
        import time
        room.timer_seconds = p.seconds
        room.timer_label = p.label
        room.timer_started_at = time.time()
        await server.broadcast_room(room, "ROOM.TIMER",
                                    {"seconds": p.seconds, "label": p.label})

    # =========================================================================
    # ROOM.BROADCAST_EVENT — escape hatch for client-driven gamemode events
    # =========================================================================
    @d.register("ROOM.BROADCAST_EVENT", schema=RoomBroadcastEvent,
                default_role="player", default_scope="room")
    async def broadcast_event(server, session, room, target, p: RoomBroadcastEvent):
        if room is None: return
        await server.broadcast_room(room, "ROOM.EVENT",
                                    {"event_name": p.event_name,
                                     "data": p.data,
                                     "source": session.client_id},
                                    exclude_id=session.client_id)

    # =========================================================================
    # ROOM.START_GAME — host-only relay
    # =========================================================================
    # The server is gamemode-agnostic: maps / min_players / phases all live
    # in the host client's local YAML. The server just relays the event so
    # every member's client triggers its own start sequence.
    @d.register("ROOM.START_GAME", schema=RoomStartGame,
                default_role="host", default_scope="room")
    async def start_game(server, session, room, target, p: RoomStartGame):
        if room is None: return
        log.room(room.room_id, f"start_game (gm={room.gamemode_id} players={len(room.sessions)})")
        await server.broadcast_room(room, "ROOM.START_GAME",
                                    {"started_by": session.client_id})

    # =========================================================================
    # ROOM.SELECT_MAP — host (or vote winner) confirms a chosen map
    # =========================================================================
    # Map list lives in client YAMLs. Server just relays the index.
    @d.register("ROOM.SELECT_MAP", schema=RoomSelectMap,
                default_role="host", default_scope="room")
    async def select_map(server, session, room, target, p: RoomSelectMap):
        if room is None: return
        room.config["confirmed_map_index"] = p.map_index
        log.room(room.room_id, f"map confirmed: [{p.map_index}]")
        await server.broadcast_room(room, "ROOM.MAP_CONFIRMED",
                                    {"map_index": p.map_index,
                                     "selected_by": session.client_id})
