"""Decorator-based primitive registry.

Each primitive declares: name, schema, required_role, scope, rate_limit.
The dispatcher validates everything before calling the handler. Handlers
typically only contain the relay logic (send to target / broadcast room).

Scope semantics:
  - "self":        target must be the sender (or no target field at all)
  - "any_in_room": target must be another session in the same room
  - "room":        no specific target; affects whole room (broadcast)
  - "global":      no scope check (dangerous; reserved for ADMIN)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, Optional, Type

from pydantic import BaseModel, ValidationError

from harpoon import logging as log
from harpoon.protocol.envelope import Envelope, wrap
from harpoon.room import Room
from harpoon.security.permissions import PermissionRegistry
from harpoon.security.ratelimit import RateLimiter
from harpoon.session import Session


Scope = Literal["self", "any_in_room", "room", "global", "none"]
HandlerFn = Callable[..., Awaitable[None]]


@dataclass
class Primitive:
    name: str
    schema: Optional[Type[BaseModel]]
    handler: HandlerFn
    default_role: str  # Minimum role hint; gamemode YAML can override.
    default_scope: Scope


class Dispatcher:
    def __init__(self, permissions: PermissionRegistry, rate_limiter: RateLimiter) -> None:
        self._registry: dict[str, Primitive] = {}
        self.permissions = permissions
        self.rate_limiter = rate_limiter
        # Set externally by the transport — gives handlers access to the
        # global state (rooms, all sessions). Avoids a circular import.
        self.server: Any = None

    def register(self, name: str, *, schema: Type[BaseModel] | None = None,
                 default_role: str = "player",
                 default_scope: Scope = "self") -> Callable[[HandlerFn], HandlerFn]:
        """Decorator to register a primitive handler.

        Usage:
            @dispatcher.register("WORLD.TRANSPORT_SCENE", schema=WorldTransport,
                                 default_role="admin", default_scope="any_in_room")
            async def transport(server, session, room, target, payload): ...
        """
        def deco(fn: HandlerFn) -> HandlerFn:
            self._registry[name] = Primitive(
                name=name, schema=schema, handler=fn,
                default_role=default_role, default_scope=default_scope)
            return fn
        return deco

    def list_primitives(self) -> list[str]:
        return sorted(self._registry.keys())

    # =========================================================================
    # Dispatch
    # =========================================================================

    async def handle(self, session: Session, envelope: dict[str, Any]) -> None:
        """Entry point. Accepts envelope shape only: `{type, seq, payload}`."""
        try:
            env = Envelope.model_validate(envelope)
        except ValidationError as e:
            log.warn(f"[{session.name}] bad envelope: {e.errors()[:2]}")
            await self._send_error(session, "bad_envelope",
                                   "Message must be {type, seq, payload}")
            return

        type_ = env.type
        prim = self._registry.get(type_)
        if prim is None:
            log.warn(f"[{session.name}] unknown primitive: {type_}")
            await self._send_error(session, "unknown_primitive", type_)
            return

        payload = dict(env.payload)
        resolved = type_

        # Schema validation.
        validated: BaseModel | dict[str, Any] = payload
        if prim.schema is not None:
            try:
                validated = prim.schema.model_validate(payload)
            except ValidationError as e:
                log.warn(f"[{session.name}] schema fail on {resolved}: {e.errors()[:3]}")
                await self._send_error(session, "schema_invalid",
                                       f"{resolved}: {e.errors()[0]['msg']}")
                return

        # Permission + rate limit (gamemode-driven).
        room = self.server.get_room(session.room_id) if session.room_id else None
        gamemode_id = room.gamemode_id if room else "default"
        rule = self.permissions.lookup_rule(gamemode_id, session.role, resolved)

        # If no rule and primitive needs auth, deny. Lobby/connection primitives
        # are always allowed regardless of gamemode YAML — these are the means
        # by which clients reach a gamemode in the first place.
        always_allowed = resolved.startswith("HARPOON.") or resolved in (
            "ROOM.LIST", "ROOM.CREATE", "ROOM.JOIN", "ROOM.LEAVE")

        if rule is None and not always_allowed:
            log.warn(f"[{session.name}] denied: {resolved} (role={session.role}, gm={gamemode_id})")
            await self._send_error(session, "forbidden",
                                   f"{resolved} not allowed for role={session.role}")
            return

        if rule is not None:
            count, window = rule.rate_limit
            if not self.rate_limiter.check(session.client_id, resolved, count, window):
                log.warn(f"[{session.name}] rate limit on {resolved}")
                await self._send_error(session, "rate_limited", f"{resolved}: too many calls")
                return

        # Resolve target if scope requires one.
        target: Optional[Session] = None
        scope = rule.scope if rule else prim.default_scope
        target_id = None
        if isinstance(validated, BaseModel):
            target_id = getattr(validated, "target", None)
        else:
            target_id = validated.get("target") or validated.get("targetClientId")

        if scope == "self":
            if target_id is not None and target_id != session.client_id:
                await self._send_error(session, "scope_self", f"{resolved}: target must be self")
                return
            target = session
        elif scope == "any_in_room":
            if not room:
                await self._send_error(session, "no_room", f"{resolved}: must be in a room")
                return
            if target_id is None:
                # Treat missing target as broadcast to room (sane default).
                target = None
            else:
                target = room.get(int(target_id))
                if target is None:
                    return  # silent drop — target left
        elif scope == "room":
            if not room:
                await self._send_error(session, "no_room", f"{resolved}: must be in a room")
                return

        # Dispatch.
        try:
            log.audit(f"{session.name}({session.client_id})/{session.role} -> {resolved} "
                      f"target={target_id} room={session.room_id}")
            await prim.handler(self.server, session, room, target, validated)
        except Exception as e:
            log.error(f"handler crash on {resolved}: {e!r}")

    async def _send_error(self, session: Session, code: str, message: str) -> None:
        await session.send("HARPOON.ERROR", {"code": code, "message": message})
