"""AUDIO.* — BGM, SFX, voice."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from harpoon.dispatcher import Dispatcher


class AudioPlaySfx(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    sfx_id: int = Field(..., alias="sfxId")
    scene_num: Optional[int] = Field(default=None, alias="sceneNum")
    pos_x: Optional[float] = Field(default=None, alias="posX")
    pos_y: Optional[float] = Field(default=None, alias="posY")
    pos_z: Optional[float] = Field(default=None, alias="posZ")
    volume: float = Field(default=1.0, ge=0.0, le=2.0)


class AudioPlayBgm(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    music_id: int = Field(..., alias="musicId")
    target: Optional[int] = None
    volume: float = Field(default=1.0, ge=0.0, le=2.0)
    loop: bool = True


class AudioStopBgm(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None
    fade_out_seconds: float = Field(default=0.0, ge=0.0, alias="fadeOutSeconds")


class AudioFadeBgm(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None
    target_volume: float = Field(..., ge=0.0, le=2.0, alias="targetVolume")
    duration: float = Field(..., ge=0.0)


def register(d: Dispatcher) -> None:

    @d.register("AUDIO.PLAY_SFX", schema=AudioPlaySfx,
                default_role="player", default_scope="self")
    async def play_sfx(server, session, room, target, p: AudioPlaySfx):
        if room is None: return
        payload = {
            "source": session.client_id,
            "sfx_id": p.sfx_id,
            "scene_num": p.scene_num if p.scene_num is not None else session.scene_num,
            "volume": p.volume,
        }
        if p.pos_x is not None: payload["pos_x"] = p.pos_x
        if p.pos_y is not None: payload["pos_y"] = p.pos_y
        if p.pos_z is not None: payload["pos_z"] = p.pos_z
        await server.broadcast_room(room, "AUDIO.PLAY_SFX", payload,
                                    exclude_id=session.client_id,
                                    same_scene_as=session)

    @d.register("AUDIO.PLAY_BGM", schema=AudioPlayBgm,
                default_role="admin", default_scope="any_in_room")
    async def play_bgm(server, session, room, target, p: AudioPlayBgm):
        payload = {"music_id": p.music_id, "volume": p.volume, "loop": p.loop,
                   "source": session.client_id}
        if target is not None:
            await target.send("AUDIO.PLAY_BGM", payload)
        elif room is not None:
            await server.broadcast_room(room, "AUDIO.PLAY_BGM", payload)

    @d.register("AUDIO.STOP_BGM", schema=AudioStopBgm,
                default_role="admin", default_scope="any_in_room")
    async def stop_bgm(server, session, room, target, p: AudioStopBgm):
        payload = {"fade_out_seconds": p.fade_out_seconds, "source": session.client_id}
        if target is not None:
            await target.send("AUDIO.STOP_BGM", payload)
        elif room is not None:
            await server.broadcast_room(room, "AUDIO.STOP_BGM", payload)

    @d.register("AUDIO.FADE_BGM", schema=AudioFadeBgm,
                default_role="admin", default_scope="any_in_room")
    async def fade_bgm(server, session, room, target, p: AudioFadeBgm):
        payload = {"target_volume": p.target_volume, "duration": p.duration,
                   "source": session.client_id}
        if target is not None:
            await target.send("AUDIO.FADE_BGM", payload)
        elif room is not None:
            await server.broadcast_room(room, "AUDIO.FADE_BGM", payload)
