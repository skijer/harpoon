"""WORLD.* — scene transitions, teleport, weather, time."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from harpoon.dispatcher import Dispatcher


class _Vec3f(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    x: float
    y: float
    z: float


class _Vec3s(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    x: int
    y: int
    z: int


class _PosRot(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    pos: _Vec3f
    rot: _Vec3s


class WorldTransportScene(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    scene_num: int = Field(..., ge=0, le=255)
    entrance_index: int = Field(default=0, ge=0)
    room_index: int = Field(default=0, ge=0)
    link_age: Optional[int] = None
    pos_rot: Optional[_PosRot] = None


class WorldTeleport(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    x: float
    y: float
    z: float
    rotation: int = 0


class WorldSetTimeOfDay(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None  # None = whole room
    time: int = Field(..., ge=0, le=65535)


class WorldSetWeather(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None
    weather_id: str = Field(..., max_length=32)
    intensity: float = Field(default=1.0, ge=0.0, le=2.0)


class WorldFreezeTime(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None
    duration: Optional[int] = None


class WorldSetTimeScale(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None
    scale: float = Field(..., ge=0.0, le=10.0)


def register(d: Dispatcher) -> None:

    @d.register("WORLD.TRANSPORT_SCENE", schema=WorldTransportScene,
                default_role="admin", default_scope="any_in_room")
    async def transport_scene(server, session, room, target, p: WorldTransportScene):
        if target is None: return
        payload: dict[str, Any] = {
            "source": session.client_id,
            "target": p.target,
            "scene_num": p.scene_num,
            "entrance_index": p.entrance_index,
            "room_index": p.room_index,
        }
        if p.link_age is not None: payload["link_age"] = p.link_age
        if p.pos_rot is not None: payload["pos_rot"] = p.pos_rot.model_dump()
        await target.send("WORLD.TRANSPORT_SCENE", payload)

    @d.register("WORLD.TELEPORT", schema=WorldTeleport,
                default_role="admin", default_scope="any_in_room")
    async def teleport(server, session, room, target, p: WorldTeleport):
        if target is None: return
        await target.send("WORLD.TELEPORT",
                          {"x": p.x, "y": p.y, "z": p.z, "rotation": p.rotation,
                           "source": session.client_id})

    @d.register("WORLD.SET_TIME_OF_DAY", schema=WorldSetTimeOfDay,
                default_role="admin", default_scope="any_in_room")
    async def set_time_of_day(server, session, room, target, p: WorldSetTimeOfDay):
        payload = {"time": p.time, "source": session.client_id}
        if target is not None:
            await target.send("WORLD.SET_TIME_OF_DAY", payload)
        elif room is not None:
            await server.broadcast_room(room, "WORLD.SET_TIME_OF_DAY", payload)

    @d.register("WORLD.SET_WEATHER", schema=WorldSetWeather,
                default_role="admin", default_scope="any_in_room")
    async def set_weather(server, session, room, target, p: WorldSetWeather):
        payload = {"weather_id": p.weather_id, "intensity": p.intensity,
                   "source": session.client_id}
        if target is not None:
            await target.send("WORLD.SET_WEATHER", payload)
        elif room is not None:
            await server.broadcast_room(room, "WORLD.SET_WEATHER", payload)

    @d.register("WORLD.FREEZE_TIME", schema=WorldFreezeTime,
                default_role="admin", default_scope="any_in_room")
    async def freeze_time(server, session, room, target, p: WorldFreezeTime):
        payload: dict[str, Any] = {"source": session.client_id}
        if p.duration is not None: payload["duration"] = p.duration
        if target is not None:
            await target.send("WORLD.FREEZE_TIME", payload)
        elif room is not None:
            await server.broadcast_room(room, "WORLD.FREEZE_TIME", payload)

    @d.register("WORLD.SET_TIME_SCALE", schema=WorldSetTimeScale,
                default_role="admin", default_scope="any_in_room")
    async def set_time_scale(server, session, room, target, p: WorldSetTimeScale):
        payload = {"scale": p.scale, "source": session.client_id}
        if target is not None:
            await target.send("WORLD.SET_TIME_SCALE", payload)
        elif room is not None:
            await server.broadcast_room(room, "WORLD.SET_TIME_SCALE", payload)
