"""ADMIN.* — moderation primitives."""

from __future__ import annotations

from harpoon import logging as log
from harpoon.dispatcher import Dispatcher
from harpoon.protocol.schemas import AdminPromote, AdminDemote, AdminSetHost, AdminKick


def register(d: Dispatcher) -> None:

    @d.register("ADMIN.PROMOTE", schema=AdminPromote,
                default_role="host", default_scope="any_in_room")
    async def promote(server, session, room, target, p: AdminPromote):
        if target is None:
            return
        target.role = "admin"
        log.audit(f"{session.name} promoted {target.name} to admin")
        await server.broadcast_room(room, "ADMIN.ROLE_CHANGED",
                                    {"target": target.client_id, "role": "admin"})
        await server.broadcast_room_members(room)

    @d.register("ADMIN.DEMOTE", schema=AdminDemote,
                default_role="host", default_scope="any_in_room")
    async def demote(server, session, room, target, p: AdminDemote):
        if target is None or target.role == "host":
            return
        target.role = "player"
        log.audit(f"{session.name} demoted {target.name} to player")
        await server.broadcast_room(room, "ADMIN.ROLE_CHANGED",
                                    {"target": target.client_id, "role": "player"})
        await server.broadcast_room_members(room)

    @d.register("ADMIN.SET_HOST", schema=AdminSetHost,
                default_role="host", default_scope="any_in_room")
    async def set_host(server, session, room, target, p: AdminSetHost):
        if target is None:
            return
        # Demote current host to admin, promote target to host.
        old_host = room.get(room.host_client_id)
        if old_host is not None:
            old_host.role = "admin"
        target.role = "host"
        room.host_client_id = target.client_id
        log.audit(f"{session.name} transferred host to {target.name}")
        await server.broadcast_room(room, "ADMIN.HOST_CHANGED",
                                    {"new_host": target.client_id})
        await server.broadcast_room_members(room)

    @d.register("ADMIN.KICK", schema=AdminKick,
                default_role="host", default_scope="any_in_room")
    async def kick(server, session, room, target, p: AdminKick):
        if target is None:
            return
        log.audit(f"{session.name} kicked {target.name}: {p.reason}")
        await target.send("HARPOON.KICKED", {"reason": p.reason})
        await server.leave_room(target)
        try:
            await target.ws.close(code=1000, reason="kicked")
        except Exception:
            pass
