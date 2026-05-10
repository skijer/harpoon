"""PLAYER.* — player state, transform, animation, stats, transformations.

Schemas use snake_case canonical names with camelCase aliases for
backwards compatibility with the existing C++ mod. `populate_by_name=True`
means both `target_client_id` and `targetClientId` are accepted.

For the high-frequency per-frame updates (TRANSFORM, SKELETON, etc.) we use
`extra="allow"` so the client can pile in extra fields without the server
choking — the server only relays these to other same-scene clients anyway.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from harpoon.dispatcher import Dispatcher


# =============================================================================
# Common config
# =============================================================================

# Permissive — accepts camelCase aliases AND extra fields (relayed as-is).
_RELAY = ConfigDict(extra="allow", populate_by_name=True)

# Strict — accepts both naming conventions but no extras.
_STRICT = ConfigDict(extra="allow", populate_by_name=True)


# =============================================================================
# Movement / animation schemas (per-frame, high-frequency; permissive)
# =============================================================================

class PlayerUpdateTransform(BaseModel):
    model_config = _RELAY


class PlayerUpdateSkeleton(BaseModel):
    model_config = _RELAY


class PlayerUpdateLimbRotations(BaseModel):
    model_config = _RELAY


class PlayerUpdateAnimationFlags(BaseModel):
    model_config = _RELAY


class PlayerUpdateMotionVars(BaseModel):
    model_config = _RELAY


class PlayerUpdateBowState(BaseModel):
    model_config = _RELAY


class PlayerUpdateHandTypes(BaseModel):
    model_config = _RELAY


class PlayerUpdateVisualState(BaseModel):
    """Sent on scene/entrance/age changes — used for AOI."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    is_save_loaded: bool = Field(default=False, alias="isSaveLoaded")
    scene_num: int = Field(default=255, alias="sceneNum")
    entrance_index: int = Field(default=0, alias="entranceIndex")
    link_age: int = Field(default=0, alias="linkAge")


class PlayerUpdateEquipVisible(BaseModel):
    model_config = _RELAY


class PlayerUpdateFace(BaseModel):
    model_config = _RELAY


class PlayerUpdateScale(BaseModel):
    model_config = _RELAY


# =============================================================================
# Stats schemas (admin-targetable; strict)
# =============================================================================

class PlayerSetHealth(BaseModel):
    model_config = _STRICT
    target: int = Field(..., ge=1)
    value: int = Field(..., ge=0, le=10000)
    max: Optional[int] = None


class PlayerSetMagic(BaseModel):
    model_config = _STRICT
    target: int = Field(..., ge=1)
    value: int = Field(..., ge=0, le=255)
    max: Optional[int] = None


class PlayerSetRupees(BaseModel):
    model_config = _STRICT
    target: int = Field(..., ge=1)
    value: int = Field(..., ge=0, le=999)


class PlayerSetLinkAge(BaseModel):
    model_config = _STRICT
    target: int = Field(..., ge=1)
    age: Literal[0, 1]


class PlayerKill(BaseModel):
    model_config = _RELAY
    killer_client_id: Optional[int] = Field(default=None, alias="killerClientId")
    message: str = Field(default="", max_length=256)


class PlayerRevive(BaseModel):
    model_config = _STRICT
    target: int = Field(..., ge=1)
    hp: Optional[int] = None


class PlayerRespawn(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    scene_num: Optional[int] = Field(default=None, alias="sceneNum")
    entrance_index: Optional[int] = Field(default=None, alias="entranceIndex")


class PlayerSetInvulnerable(BaseModel):
    model_config = _STRICT
    target: int = Field(..., ge=1)
    value: bool
    duration: Optional[int] = None


# =============================================================================
# Transformation schemas
# =============================================================================

class PlayerSetTransformation(BaseModel):
    """form: 0=human, 1=Goron, 2=Zora, 3=Deku, 4=FierceDeity"""
    model_config = _RELAY


class PlayerUpdateGoronState(BaseModel):
    model_config = _RELAY


class PlayerSetInvincibilityTimer(BaseModel):
    model_config = _STRICT
    value: int


class PlayerUpdateCustomItemState(BaseModel):
    """Opaque blob for custom items (Beetle, Fire Rod, Gust Jar, etc.).

    The C++ mod sends one of these per active item every frame with all the
    item-specific positions/scales/states/flags. Server relays as-is.
    """
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    item_id: str = Field(default="", alias="itemId", max_length=64)


class PlayerUpdateFullState(BaseModel):
    """Single-shot full player state update — convenience primitive that
    bundles transform + skeleton + limb rotations + animation flags + motion
    + bow + hand types + equip + face + scale + transformation + custom item
    state into ONE message. Useful for the legacy mod that emits all these
    fields in a single PLAYER_UPDATE per frame.

    The server relays the full payload to other same-scene members; clients
    can pick the fields they care about. Equivalent in effect to firing all
    the granular PLAYER.UPDATE_* primitives at once.
    """
    model_config = _RELAY


# =============================================================================
# Handlers
# =============================================================================

def register(d: Dispatcher) -> None:

    async def _broadcast_same_scene(server, session, room, type_: str,
                                     payload: dict[str, Any]) -> None:
        payload = {**payload, "source": session.client_id,
                   "clientId": session.client_id}  # legacy alias; harmless extra
        await server.broadcast_room(room, type_, payload,
                                    exclude_id=session.client_id,
                                    same_scene_as=session)

    @d.register("PLAYER.UPDATE_TRANSFORM", schema=PlayerUpdateTransform,
                default_role="player", default_scope="self")
    async def update_transform(server, session, room, target, p: PlayerUpdateTransform):
        if room is None: return
        d_ = p.model_dump(by_alias=True, exclude_none=True)
        session.last_transform = d_
        await _broadcast_same_scene(server, session, room, "PLAYER.UPDATE_TRANSFORM", d_)

    @d.register("PLAYER.UPDATE_SKELETON", schema=PlayerUpdateSkeleton,
                default_role="player", default_scope="self")
    async def update_skeleton(server, session, room, target, p: PlayerUpdateSkeleton):
        if room is None: return
        await _broadcast_same_scene(server, session, room, "PLAYER.UPDATE_SKELETON",
                                    p.model_dump(by_alias=True, exclude_none=True))

    @d.register("PLAYER.UPDATE_LIMB_ROTATIONS", schema=PlayerUpdateLimbRotations,
                default_role="player", default_scope="self")
    async def update_limb_rotations(server, session, room, target,
                                     p: PlayerUpdateLimbRotations):
        if room is None: return
        await _broadcast_same_scene(server, session, room, "PLAYER.UPDATE_LIMB_ROTATIONS",
                                    p.model_dump(by_alias=True, exclude_none=True))

    @d.register("PLAYER.UPDATE_ANIMATION_FLAGS", schema=PlayerUpdateAnimationFlags,
                default_role="player", default_scope="self")
    async def update_animation_flags(server, session, room, target,
                                      p: PlayerUpdateAnimationFlags):
        if room is None: return
        await _broadcast_same_scene(server, session, room, "PLAYER.UPDATE_ANIMATION_FLAGS",
                                    p.model_dump(by_alias=True, exclude_none=True))

    @d.register("PLAYER.UPDATE_MOTION_VARS", schema=PlayerUpdateMotionVars,
                default_role="player", default_scope="self")
    async def update_motion_vars(server, session, room, target, p: PlayerUpdateMotionVars):
        if room is None: return
        await _broadcast_same_scene(server, session, room, "PLAYER.UPDATE_MOTION_VARS",
                                    p.model_dump(by_alias=True, exclude_none=True))

    @d.register("PLAYER.UPDATE_BOW_STATE", schema=PlayerUpdateBowState,
                default_role="player", default_scope="self")
    async def update_bow_state(server, session, room, target, p: PlayerUpdateBowState):
        if room is None: return
        await _broadcast_same_scene(server, session, room, "PLAYER.UPDATE_BOW_STATE",
                                    p.model_dump(by_alias=True, exclude_none=True))

    @d.register("PLAYER.UPDATE_HAND_TYPES", schema=PlayerUpdateHandTypes,
                default_role="player", default_scope="self")
    async def update_hand_types(server, session, room, target, p: PlayerUpdateHandTypes):
        if room is None: return
        await _broadcast_same_scene(server, session, room, "PLAYER.UPDATE_HAND_TYPES",
                                    p.model_dump(by_alias=True, exclude_none=True))

    @d.register("PLAYER.UPDATE_VISUAL_STATE", schema=PlayerUpdateVisualState,
                default_role="player", default_scope="self")
    async def update_visual_state(server, session, room, target, p: PlayerUpdateVisualState):
        session.is_save_loaded = p.is_save_loaded
        session.scene_num = p.scene_num
        session.entrance_index = p.entrance_index
        session.link_age = p.link_age
        if room is not None:
            await server.broadcast_room_members(room)

    @d.register("PLAYER.UPDATE_EQUIP_VISIBLE", schema=PlayerUpdateEquipVisible,
                default_role="player", default_scope="self")
    async def update_equip_visible(server, session, room, target, p: PlayerUpdateEquipVisible):
        if room is None: return
        await _broadcast_same_scene(server, session, room, "PLAYER.UPDATE_EQUIP_VISIBLE",
                                    p.model_dump(by_alias=True, exclude_none=True))

    @d.register("PLAYER.UPDATE_FACE", schema=PlayerUpdateFace,
                default_role="player", default_scope="self")
    async def update_face(server, session, room, target, p: PlayerUpdateFace):
        if room is None: return
        await _broadcast_same_scene(server, session, room, "PLAYER.UPDATE_FACE",
                                    p.model_dump(by_alias=True, exclude_none=True))

    @d.register("PLAYER.UPDATE_SCALE", schema=PlayerUpdateScale,
                default_role="player", default_scope="self")
    async def update_scale(server, session, room, target, p: PlayerUpdateScale):
        if room is None: return
        await _broadcast_same_scene(server, session, room, "PLAYER.UPDATE_SCALE",
                                    p.model_dump(by_alias=True, exclude_none=True))

    @d.register("PLAYER.SET_HEALTH", schema=PlayerSetHealth,
                default_role="admin", default_scope="any_in_room")
    async def set_health(server, session, room, target, p: PlayerSetHealth):
        if target is None: return
        await target.send("PLAYER.SET_HEALTH",
                          {"value": p.value, "max": p.max, "source": session.client_id})

    @d.register("PLAYER.SET_MAGIC", schema=PlayerSetMagic,
                default_role="admin", default_scope="any_in_room")
    async def set_magic(server, session, room, target, p: PlayerSetMagic):
        if target is None: return
        await target.send("PLAYER.SET_MAGIC",
                          {"value": p.value, "max": p.max, "source": session.client_id})

    @d.register("PLAYER.SET_RUPEES", schema=PlayerSetRupees,
                default_role="admin", default_scope="any_in_room")
    async def set_rupees(server, session, room, target, p: PlayerSetRupees):
        if target is None: return
        await target.send("PLAYER.SET_RUPEES",
                          {"value": p.value, "source": session.client_id})

    @d.register("PLAYER.SET_LINK_AGE", schema=PlayerSetLinkAge,
                default_role="admin", default_scope="any_in_room")
    async def set_link_age(server, session, room, target, p: PlayerSetLinkAge):
        if target is None: return
        target.link_age = p.age
        await target.send("PLAYER.SET_LINK_AGE",
                          {"age": p.age, "source": session.client_id})

    @d.register("PLAYER.KILL", schema=PlayerKill,
                default_role="player", default_scope="room")
    async def kill(server, session, room, target, p: PlayerKill):
        if room is None: return
        await server.broadcast_room(room, "PLAYER.KILL", {
            "client_id": session.client_id,
            "clientId": session.client_id,
            "killer_client_id": p.killer_client_id,
            "killerClientId": p.killer_client_id,
            "message": p.message,
        })

    @d.register("PLAYER.REVIVE", schema=PlayerRevive,
                default_role="admin", default_scope="any_in_room")
    async def revive(server, session, room, target, p: PlayerRevive):
        if target is None: return
        await target.send("PLAYER.REVIVE",
                          {"hp": p.hp, "source": session.client_id})

    @d.register("PLAYER.RESPAWN", schema=PlayerRespawn,
                default_role="admin", default_scope="any_in_room")
    async def respawn(server, session, room, target, p: PlayerRespawn):
        if target is None: return
        await target.send("PLAYER.RESPAWN",
                          {**p.model_dump(by_alias=True, exclude_none=True),
                           "source": session.client_id})

    @d.register("PLAYER.SET_INVULNERABLE", schema=PlayerSetInvulnerable,
                default_role="admin", default_scope="any_in_room")
    async def set_invulnerable(server, session, room, target, p: PlayerSetInvulnerable):
        if target is None: return
        await target.send("PLAYER.SET_INVULNERABLE",
                          {"value": p.value, "duration": p.duration,
                           "source": session.client_id})

    @d.register("PLAYER.SET_TRANSFORMATION", schema=PlayerSetTransformation,
                default_role="player", default_scope="self")
    async def set_transformation(server, session, room, target, p: PlayerSetTransformation):
        if room is None: return
        await _broadcast_same_scene(server, session, room, "PLAYER.SET_TRANSFORMATION",
                                    p.model_dump(by_alias=True, exclude_none=True))

    @d.register("PLAYER.UPDATE_GORON_STATE", schema=PlayerUpdateGoronState,
                default_role="player", default_scope="self")
    async def update_goron_state(server, session, room, target, p: PlayerUpdateGoronState):
        if room is None: return
        await _broadcast_same_scene(server, session, room, "PLAYER.UPDATE_GORON_STATE",
                                    p.model_dump(by_alias=True, exclude_none=True))

    @d.register("PLAYER.SET_INVINCIBILITY_TIMER", schema=PlayerSetInvincibilityTimer,
                default_role="player", default_scope="self")
    async def set_invincibility_timer(server, session, room, target,
                                       p: PlayerSetInvincibilityTimer):
        if room is None: return
        await _broadcast_same_scene(server, session, room, "PLAYER.SET_INVINCIBILITY_TIMER",
                                    {"value": p.value})

    @d.register("PLAYER.UPDATE_CUSTOM_ITEM_STATE", schema=PlayerUpdateCustomItemState,
                default_role="player", default_scope="self")
    async def update_custom_item_state(server, session, room, target,
                                        p: PlayerUpdateCustomItemState):
        if room is None: return
        await _broadcast_same_scene(server, session, room, "PLAYER.UPDATE_CUSTOM_ITEM_STATE",
                                    p.model_dump(by_alias=True, exclude_none=True))

    @d.register("PLAYER.UPDATE_FULL_STATE", schema=PlayerUpdateFullState,
                default_role="player", default_scope="self")
    async def update_full_state(server, session, room, target, p: PlayerUpdateFullState):
        """One-shot bundle of every per-frame field. Server relays as-is to
        same-scene clients. Schema-permissive: any field is allowed."""
        if room is None: return
        d_ = p.model_dump(by_alias=True, exclude_none=True)
        # Update session AOI fields if present.
        if "scene_num" in d_ or "sceneNum" in d_:
            session.scene_num = int(d_.get("scene_num", d_.get("sceneNum", session.scene_num)))
        if "link_age" in d_ or "linkAge" in d_:
            session.link_age = int(d_.get("link_age", d_.get("linkAge", session.link_age)))
        if "is_save_loaded" in d_ or "isSaveLoaded" in d_:
            session.is_save_loaded = bool(d_.get("is_save_loaded", d_.get("isSaveLoaded", session.is_save_loaded)))
        await _broadcast_same_scene(server, session, room, "PLAYER.UPDATE_FULL_STATE", d_)
