"""Pydantic schemas for control-plane primitives (HARPOON.* and ROOM.*).

Gameplay primitive schemas (PLAYER.*, COMBAT.*, etc.) live alongside their
handlers in `harpoon/primitives/<domain>.py` and are added in Phase 1+.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# HARPOON.* — connection lifecycle
# =============================================================================

class Color(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    r: int = Field(..., ge=0, le=255)
    g: int = Field(..., ge=0, le=255)
    b: int = Field(..., ge=0, le=255)


class HarpoonHandshake(BaseModel):
    """Client → Server. First message after connect.

    Also accepts the legacy mod's `clientState` envelope: if present, fields
    are pulled from inside it. Tolerates `clientVersion` camelCase alias.

    `protocol` must be the literal string "harpoon" — soft barrier that
    rejects generic WebSocket clients trying to speak random JSON to the
    server. Doesn't add cryptographic security (the literal is in the source)
    but keeps the server from being trivially repurposed as an open relay.

    `installed_gamemodes` is the list of gamemode pack ids the client has
    locally (folder names under its harpoon/gamemodes/). The server uses this
    list to filter the room browser per-client — clients never see rooms for
    gamemodes they don't have installed (privacy for custom packs).
    """
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=32)
    color: Color
    client_version: str = Field(default="", max_length=64, alias="clientVersion")
    installed_gamemodes: list[str] = Field(default_factory=list,
                                            alias="installedGamemodes")
    protocol: str = Field(default="", max_length=32)


class HarpoonResume(BaseModel):
    """Client → Server. Reconnect with a previously issued sessionToken."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    session_token: str = Field(..., min_length=64, max_length=64, alias="sessionToken")


# =============================================================================
# ROOM.* — room lifecycle
# =============================================================================

class RoomCreate(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=64)
    gamemode_id: str = Field(default="default", max_length=64, alias="gameMode")
    password: str = Field(default="", max_length=64)
    max_players: int = Field(default=16, ge=2, le=64, alias="maxPlayers")


class RoomJoin(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    room_id: str = Field(..., min_length=1, max_length=64, alias="roomId")
    password: str = Field(default="", max_length=64)


class RoomLeave(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class RoomList(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class RoomSetGamemodeId(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    gamemode_id: str = Field(..., min_length=1, max_length=64)


class RoomSetGamemodeConfig(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    config: dict[str, Any] = Field(default_factory=dict)


class RoomSetPhase(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    phase: str = Field(..., min_length=1, max_length=32)


class RoomSetTimer(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    seconds: int = Field(..., ge=0, le=86400)
    label: str = Field(default="", max_length=32)


class RoomBroadcastEvent(BaseModel):
    """Escape hatch — opaque event the server only relays."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    event_name: str = Field(..., min_length=1, max_length=64)
    data: dict[str, Any] = Field(default_factory=dict)


class RoomStartGame(BaseModel):
    """Host-only. Triggers the standard start sequence:
       - validates min_players from the manifest,
       - if the gamemode declares `maps`, transitions to phase `map_select`
         and emits ROOM.MAP_SELECT_BEGIN with the map list + map_select_mode,
       - else transitions directly to `countdown` with ROOM.SET_TIMER.
    """
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class RoomSelectMap(BaseModel):
    """Host-only. Confirms a selected map (from the manifest's `maps`
    array) and transitions phase to `countdown`. Server stores the chosen
    map index in `room.config.confirmed_map_index` and broadcasts
    ROOM.MAP_CONFIRMED + ROOM.PHASE_CHANGED + ROOM.TIMER.
    """
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    map_index: int = Field(..., ge=0, le=64, alias="mapIndex")


# =============================================================================
# ADMIN.* — moderation
# =============================================================================

class AdminPromote(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)


class AdminDemote(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)


class AdminSetHost(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)


class AdminKick(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    reason: str = Field(default="", max_length=256)
