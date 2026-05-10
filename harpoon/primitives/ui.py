"""UI.* — HUD, messages, banners, timers, scores, leaderboards."""

from __future__ import annotations

from typing import Any, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field

from harpoon.dispatcher import Dispatcher


class UiShowMessage(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None
    text: str = Field(..., max_length=512)
    duration: float = Field(default=3.0, ge=0.0, le=60.0)
    style: Literal["info", "warning", "error", "success"] = "info"


class UiShowBanner(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None
    text: str = Field(..., max_length=256)
    position: Literal["top", "center", "bottom"] = "top"
    duration: float = Field(default=3.0, ge=0.0, le=60.0)


class UiPlayCutscene(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None
    cutscene_id: int


class UiSetScore(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None
    score_id: str = Field(..., max_length=32)
    value: int


class UiUpdateLeaderboard(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    entries: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


class UiSetHudElement(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None
    element: str = Field(..., max_length=32)
    value: Any


def register(d: Dispatcher) -> None:

    @d.register("UI.SHOW_MESSAGE", schema=UiShowMessage,
                default_role="admin", default_scope="any_in_room")
    async def show_message(server, session, room, target, p: UiShowMessage):
        payload = {"text": p.text, "duration": p.duration, "style": p.style,
                   "source": session.client_id}
        if target is not None:
            await target.send("UI.SHOW_MESSAGE", payload)
        elif room is not None:
            await server.broadcast_room(room, "UI.SHOW_MESSAGE", payload)

    @d.register("UI.SHOW_BANNER", schema=UiShowBanner,
                default_role="admin", default_scope="any_in_room")
    async def show_banner(server, session, room, target, p: UiShowBanner):
        payload = {"text": p.text, "position": p.position, "duration": p.duration,
                   "source": session.client_id}
        if target is not None:
            await target.send("UI.SHOW_BANNER", payload)
        elif room is not None:
            await server.broadcast_room(room, "UI.SHOW_BANNER", payload)

    @d.register("UI.PLAY_CUTSCENE", schema=UiPlayCutscene,
                default_role="admin", default_scope="any_in_room")
    async def play_cutscene(server, session, room, target, p: UiPlayCutscene):
        payload = {"cutscene_id": p.cutscene_id, "source": session.client_id}
        if target is not None:
            await target.send("UI.PLAY_CUTSCENE", payload)
        elif room is not None:
            await server.broadcast_room(room, "UI.PLAY_CUTSCENE", payload)

    @d.register("UI.SET_SCORE", schema=UiSetScore,
                default_role="admin", default_scope="any_in_room")
    async def set_score(server, session, room, target, p: UiSetScore):
        payload = {"score_id": p.score_id, "value": p.value, "source": session.client_id}
        if target is not None:
            await target.send("UI.SET_SCORE", payload)
        elif room is not None:
            await server.broadcast_room(room, "UI.SET_SCORE", payload)

    @d.register("UI.UPDATE_LEADERBOARD", schema=UiUpdateLeaderboard,
                default_role="admin", default_scope="room")
    async def update_leaderboard(server, session, room, target, p: UiUpdateLeaderboard):
        if room is None: return
        await server.broadcast_room(room, "UI.UPDATE_LEADERBOARD",
                                    {"entries": p.entries, "source": session.client_id})

    @d.register("UI.SET_HUD_ELEMENT", schema=UiSetHudElement,
                default_role="admin", default_scope="any_in_room")
    async def set_hud_element(server, session, room, target, p: UiSetHudElement):
        payload = {"element": p.element, "value": p.value, "source": session.client_id}
        if target is not None:
            await target.send("UI.SET_HUD_ELEMENT", payload)
        elif room is not None:
            await server.broadcast_room(room, "UI.SET_HUD_ELEMENT", payload)
