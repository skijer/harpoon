"""MAP.* — minimap markers, fog of war, entrance discovery."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from harpoon.dispatcher import Dispatcher


class MapEntranceDiscovered(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    entrance_index: int = Field(..., ge=0, alias="entranceIndex")


class MapSetMarker(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    marker_id: str = Field(..., max_length=64)
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    label: str = Field(default="", max_length=32)
    icon: str = Field(default="", max_length=32)
    color: Optional[dict[str, int]] = None


class MapRemoveMarker(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    marker_id: str = Field(..., max_length=64)


class MapRevealArea(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None
    area_id: str = Field(..., max_length=64)
    percent: float = Field(default=100.0, ge=0.0, le=100.0)


def register(d: Dispatcher) -> None:

    @d.register("MAP.ENTRANCE_DISCOVERED", schema=MapEntranceDiscovered,
                default_role="player", default_scope="room")
    async def entrance_discovered(server, session, room, target, p: MapEntranceDiscovered):
        if room is None: return
        await server.broadcast_room(room, "MAP.ENTRANCE_DISCOVERED",
                                    {"source":        session.client_id,
                                     "clientId":      session.client_id,
                                     "entranceIndex": p.entrance_index},
                                    exclude_id=session.client_id)

    @d.register("MAP.SET_MARKER", schema=MapSetMarker,
                default_role="admin", default_scope="room")
    async def set_marker(server, session, room, target, p: MapSetMarker):
        if room is None: return
        await server.broadcast_room(room, "MAP.SET_MARKER",
                                    {**p.model_dump(exclude_none=True),
                                     "source": session.client_id})

    @d.register("MAP.REMOVE_MARKER", schema=MapRemoveMarker,
                default_role="admin", default_scope="room")
    async def remove_marker(server, session, room, target, p: MapRemoveMarker):
        if room is None: return
        await server.broadcast_room(room, "MAP.REMOVE_MARKER",
                                    {"marker_id": p.marker_id,
                                     "source": session.client_id})

    @d.register("MAP.REVEAL_AREA", schema=MapRevealArea,
                default_role="admin", default_scope="any_in_room")
    async def reveal_area(server, session, room, target, p: MapRevealArea):
        payload = {"area_id": p.area_id, "percent": p.percent,
                   "source": session.client_id}
        if target is not None:
            await target.send("MAP.REVEAL_AREA", payload)
        elif room is not None:
            await server.broadcast_room(room, "MAP.REVEAL_AREA", payload)
