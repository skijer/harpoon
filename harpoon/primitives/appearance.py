"""APPEARANCE.* — skin sync, cosmetics, model swaps, prop hunt models."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from harpoon.dispatcher import Dispatcher


# =============================================================================
# Schemas
# =============================================================================

class SkinSyncAnnounceCatalog(BaseModel):
    """Tells the room which .o2r skin packs this client has.

    - enabled_mods: packs the user has enabled globally (visible on their Link).
    - sync_catalog: packs available locally for rendering OTHER players.
    """
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    enabled_mods: list[str] = Field(default_factory=list, max_length=512, alias="mods")
    sync_catalog: list[str] = Field(default_factory=list, max_length=512, alias="syncMods")


class SkinSyncUpdateSlots(BaseModel):
    """Which skin pack this client currently has selected per slot
    (`adult`, `child`, `equipment`)."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    slots: dict[str, str] = Field(default_factory=dict)


class AppearanceSetTint(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    color: dict[str, int]


class AppearanceSetScale(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    scale_x: float = 1.0
    scale_y: float = 1.0
    scale_z: float = 1.0


class AppearanceHideFromObserver(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    observer: int = Field(..., ge=1)


class AppearanceShowToObserver(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    observer: int = Field(..., ge=1)


class AppearanceSetPropHuntProp(BaseModel):
    """Prop Hunt: discrete (category, prop_index, prop_state) into the
    client-side prop table (3 cats × 10 props × 4 states)."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    category: int = Field(..., ge=0, le=10)
    prop_index: int = Field(..., ge=-1, le=64)
    prop_state: int = Field(default=0, ge=0, le=16)
    map_idx: int = Field(default=0, ge=0)


class AppearanceSetTrailEffect(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    effect_id: str = Field(..., max_length=64)
    color: Optional[dict[str, int]] = None


class AppearanceSetAuraEffect(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    effect_id: str = Field(..., max_length=64)
    color: Optional[dict[str, int]] = None


class AppearanceSetNametag(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    text: str = Field(..., max_length=32)
    color: Optional[dict[str, int]] = None


class AppearanceSpawnVfxActor(BaseModel):
    """Tell other clients to spawn a visual-only actor at the given pos/rot.

    The server is gamemode-agnostic — it doesn't validate `actor_id` or
    `vfx_kind`. Privacy of custom actors (sw97 medallion magic, etc.) is
    enforced client-side: clients without the relevant pack ignore unknown
    `vfx_kind` values.

    `attached_to_owner` makes the actor follow the sender's dummy player
    (Nayru's Love-style auras). Otherwise the actor is fire-and-forget at
    the given pos/rot (arrows, projectiles)."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    actor_id: int = Field(..., alias="actorId")
    pos_x: float = Field(default=0.0, alias="posX")
    pos_y: float = Field(default=0.0, alias="posY")
    pos_z: float = Field(default=0.0, alias="posZ")
    rot_x: int = Field(default=0, alias="rotX")
    rot_y: int = Field(default=0, alias="rotY")
    rot_z: int = Field(default=0, alias="rotZ")
    params: int = 0
    vfx_kind: str = Field(default="generic", max_length=64, alias="vfxKind")
    attached_to_owner: bool = Field(default=False, alias="attachedToOwner")


# =============================================================================
# Handlers
# =============================================================================

def register(d: Dispatcher) -> None:

    @d.register("APPEARANCE.SKIN_SYNC.ANNOUNCE_CATALOG", schema=SkinSyncAnnounceCatalog,
                default_role="player", default_scope="room")
    async def announce_catalog(server, session, room, target, p: SkinSyncAnnounceCatalog):
        if room is None: return
        await server.broadcast_room(room, "APPEARANCE.SKIN_SYNC.ANNOUNCE_CATALOG",
                                    {"source":   session.client_id,
                                     "clientId": session.client_id,
                                     "mods":     p.enabled_mods,
                                     "syncMods": p.sync_catalog},
                                    exclude_id=session.client_id)

    @d.register("APPEARANCE.SKIN_SYNC.UPDATE_SLOTS", schema=SkinSyncUpdateSlots,
                default_role="player", default_scope="room")
    async def update_slots(server, session, room, target, p: SkinSyncUpdateSlots):
        if room is None: return
        # Flatten slot keys onto the top-level payload — the C++ reader
        # picks up `adultSkin` / `childSkin` directly (no nested object).
        payload = {"source":   session.client_id,
                   "clientId": session.client_id,
                   "slots":    p.slots}
        if isinstance(p.slots, dict):
            payload.update(p.slots)
        await server.broadcast_room(room, "APPEARANCE.SKIN_SYNC.UPDATE_SLOTS",
                                    payload,
                                    exclude_id=session.client_id)

    @d.register("APPEARANCE.SET_TINT", schema=AppearanceSetTint,
                default_role="admin", default_scope="any_in_room")
    async def set_tint(server, session, room, target, p: AppearanceSetTint):
        if target is None: return
        await target.send("APPEARANCE.SET_TINT",
                          {"color": p.color, "source": session.client_id})

    @d.register("APPEARANCE.SET_SCALE", schema=AppearanceSetScale,
                default_role="admin", default_scope="any_in_room")
    async def set_scale(server, session, room, target, p: AppearanceSetScale):
        if target is None: return
        await target.send("APPEARANCE.SET_SCALE",
                          {"scale_x": p.scale_x, "scale_y": p.scale_y, "scale_z": p.scale_z,
                           "source": session.client_id})

    @d.register("APPEARANCE.HIDE_FROM_OBSERVER", schema=AppearanceHideFromObserver,
                default_role="admin", default_scope="any_in_room")
    async def hide_from_observer(server, session, room, target, p: AppearanceHideFromObserver):
        observer = room.get(p.observer) if room else None
        if observer is None: return
        await observer.send("APPEARANCE.HIDE_FROM_OBSERVER",
                            {"target": p.target, "source": session.client_id})

    @d.register("APPEARANCE.SHOW_TO_OBSERVER", schema=AppearanceShowToObserver,
                default_role="admin", default_scope="any_in_room")
    async def show_to_observer(server, session, room, target, p: AppearanceShowToObserver):
        observer = room.get(p.observer) if room else None
        if observer is None: return
        await observer.send("APPEARANCE.SHOW_TO_OBSERVER",
                            {"target": p.target, "source": session.client_id})

    @d.register("APPEARANCE.SET_PROP_HUNT_PROP", schema=AppearanceSetPropHuntProp,
                default_role="admin", default_scope="any_in_room")
    async def set_prop_hunt_prop(server, session, room, target, p: AppearanceSetPropHuntProp):
        if room is None: return
        # Broadcast to whole room — observers need to see the new prop too.
        await server.broadcast_room(room, "APPEARANCE.SET_PROP_HUNT_PROP",
                                    {"target": p.target,
                                     "category": p.category,
                                     "prop_index": p.prop_index,
                                     "prop_state": p.prop_state,
                                     "map_idx": p.map_idx,
                                     "source": session.client_id})

    @d.register("APPEARANCE.SET_TRAIL_EFFECT", schema=AppearanceSetTrailEffect,
                default_role="admin", default_scope="any_in_room")
    async def set_trail_effect(server, session, room, target, p: AppearanceSetTrailEffect):
        if room is None: return
        await server.broadcast_room(room, "APPEARANCE.SET_TRAIL_EFFECT",
                                    {**p.model_dump(exclude_none=True),
                                     "source": session.client_id})

    @d.register("APPEARANCE.SET_AURA_EFFECT", schema=AppearanceSetAuraEffect,
                default_role="admin", default_scope="any_in_room")
    async def set_aura_effect(server, session, room, target, p: AppearanceSetAuraEffect):
        if room is None: return
        await server.broadcast_room(room, "APPEARANCE.SET_AURA_EFFECT",
                                    {**p.model_dump(exclude_none=True),
                                     "source": session.client_id})

    @d.register("APPEARANCE.SET_NAMETAG", schema=AppearanceSetNametag,
                default_role="admin", default_scope="any_in_room")
    async def set_nametag(server, session, room, target, p: AppearanceSetNametag):
        if room is None: return
        await server.broadcast_room(room, "APPEARANCE.SET_NAMETAG",
                                    {**p.model_dump(exclude_none=True),
                                     "source": session.client_id})

    @d.register("APPEARANCE.SPAWN_VFX_ACTOR", schema=AppearanceSpawnVfxActor,
                default_role="player", default_scope="room")
    async def spawn_vfx_actor(server, session, room, target, p: AppearanceSpawnVfxActor):
        # AOI: only relevant to players in the same scene as the sender.
        # Server doesn't know what the actor_id means — clients dispatch
        # by vfx_kind locally. camelCase fields for the C++ client.
        if room is None: return
        await server.broadcast_room(
            room, "APPEARANCE.SPAWN_VFX_ACTOR",
            {"source":            session.client_id,
             "clientId":          session.client_id,
             "actorId":           p.actor_id,
             "posX":              p.pos_x,
             "posY":              p.pos_y,
             "posZ":              p.pos_z,
             "rotX":              p.rot_x,
             "rotY":              p.rot_y,
             "rotZ":              p.rot_z,
             "params":            p.params,
             "vfxKind":           p.vfx_kind,
             "attachedToOwner":   p.attached_to_owner},
            exclude_id=session.client_id,
            same_scene_as=session)
