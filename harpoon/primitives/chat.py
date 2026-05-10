"""CHAT.* — text chat, emotes, pings, location markers."""

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field

from harpoon.dispatcher import Dispatcher


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    channel: Literal["room", "team", "whisper"] = "room"
    target: Optional[int] = None  # required for whisper
    text: str = Field(..., min_length=1, max_length=512)


class ChatEmote(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    emote_id: str = Field(..., max_length=32)


class ChatPing(BaseModel):
    """Apex/Valorant-style ping — short signal at a world position."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    pos_x: float
    pos_y: float
    pos_z: float
    ping_type: Literal["danger", "go", "target", "item", "default"] = "default"


class ChatMarkLocation(BaseModel):
    """Persistent marker placed on the map by a player."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    pos_x: float
    pos_y: float
    pos_z: float
    label: str = Field(default="", max_length=32)
    icon: str = Field(default="", max_length=32)


class ChatTypingIndicator(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    channel: Literal["room", "team", "whisper"] = "room"
    target: Optional[int] = None
    typing: bool


def register(d: Dispatcher) -> None:

    @d.register("CHAT.MESSAGE", schema=ChatMessage,
                default_role="player", default_scope="room")
    async def message(server, session, room, target, p: ChatMessage):
        payload = {"source": session.client_id,
                   "source_name": session.name,
                   "channel": p.channel,
                   "text": p.text}

        if p.channel == "whisper":
            if p.target is None:
                await session.send("HARPOON.ERROR",
                                   {"code": "missing_target",
                                    "message": "Whisper requires target"})
                return
            # Whisper: server has all_sessions; target may not be in same room.
            recipient = server.sessions.get(p.target)
            if recipient is None: return
            payload["target"] = p.target
            await recipient.send("CHAT.MESSAGE", payload)
            await session.send("CHAT.MESSAGE", payload)  # echo to sender
            return

        if room is None: return

        if p.channel == "team":
            # Filter by same team as sender (read from custom_state).
            team = room.custom_state.get(f"team_{session.client_id}")
            for s in room.members():
                if s.client_id == session.client_id: continue
                if room.custom_state.get(f"team_{s.client_id}") != team:
                    continue
                await s.send("CHAT.MESSAGE", payload)
            await session.send("CHAT.MESSAGE", payload)  # echo to self
            return

        # Default: room channel
        await server.broadcast_room(room, "CHAT.MESSAGE", payload)

    @d.register("CHAT.EMOTE", schema=ChatEmote,
                default_role="player", default_scope="room")
    async def emote(server, session, room, target, p: ChatEmote):
        if room is None: return
        await server.broadcast_room(room, "CHAT.EMOTE",
                                    {"source": session.client_id,
                                     "emote_id": p.emote_id})

    @d.register("CHAT.PING", schema=ChatPing,
                default_role="player", default_scope="room")
    async def ping(server, session, room, target, p: ChatPing):
        if room is None: return
        await server.broadcast_room(room, "CHAT.PING",
                                    {"source": session.client_id,
                                     "source_name": session.name,
                                     "pos_x": p.pos_x, "pos_y": p.pos_y, "pos_z": p.pos_z,
                                     "ping_type": p.ping_type})

    @d.register("CHAT.MARK_LOCATION", schema=ChatMarkLocation,
                default_role="player", default_scope="room")
    async def mark_location(server, session, room, target, p: ChatMarkLocation):
        if room is None: return
        await server.broadcast_room(room, "CHAT.MARK_LOCATION",
                                    {"source": session.client_id,
                                     "pos_x": p.pos_x, "pos_y": p.pos_y, "pos_z": p.pos_z,
                                     "label": p.label, "icon": p.icon})

    @d.register("CHAT.TYPING_INDICATOR", schema=ChatTypingIndicator,
                default_role="player", default_scope="room")
    async def typing_indicator(server, session, room, target, p: ChatTypingIndicator):
        if room is None: return
        await server.broadcast_room(room, "CHAT.TYPING_INDICATOR",
                                    {"source": session.client_id,
                                     "channel": p.channel,
                                     "typing": p.typing},
                                    exclude_id=session.client_id)
