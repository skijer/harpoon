"""INVENTORY.* and SAVE.* — items, flags, quest state, save sync."""

from __future__ import annotations

from typing import Any, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field

from harpoon.dispatcher import Dispatcher


# =============================================================================
# Schemas
# =============================================================================

class InventoryGiveItem(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None
    mod_id: int = Field(default=0, ge=0, alias="modId")
    get_item_id: int = Field(..., alias="getItemId")
    count: int = Field(default=1, ge=1, le=999)


class InventoryRemoveItem(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    item_id: int = Field(..., alias="itemId")
    count: int = Field(default=1, ge=1)


class InventorySetDungeonItems(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    map_index: int = Field(..., ge=0, le=128, alias="mapIndex")
    dungeon_items: int = Field(..., ge=0, le=255, alias="dungeonItems")
    dungeon_keys: int = Field(..., ge=-1, le=127, alias="dungeonKeys")


class InventorySetAmmo(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    item_id: int = Field(default=0, alias="itemId")
    amount: int = Field(..., ge=0, le=999)
    amount_bought: int = Field(default=0, ge=0, le=999, alias="amountBought")


class SaveSetFlag(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    namespace: Literal["scene", "event", "infinite", "randomizer", "permanent"] = "scene"
    scene_num: int = Field(default=-1, alias="sceneNum")
    flag_type: int = Field(..., alias="flagType")
    flag: int


class SaveUnsetFlag(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    namespace: Literal["scene", "event", "infinite", "randomizer", "permanent"] = "scene"
    scene_num: int = Field(default=-1, alias="sceneNum")
    flag_type: int = Field(..., alias="flagType")
    flag: int


class SaveSetQuestState(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    rc: int  # RandomizerCheck
    status: int
    skipped: bool = False


class SaveUpdateTeamState(BaseModel):
    """Full save dump from one client — opaque to the server, broadcast as-is."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    state: dict[str, Any] = Field(default_factory=dict)


class SaveCutsceneTrigger(BaseModel):
    """Story-coop cutscene replay request. Best-effort, scene-scoped."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    cutscene_index: int = Field(..., alias="cutsceneIndex")
    scene_num: int = Field(..., alias="sceneNum")


class SaveRequestTeamState(BaseModel):
    """Late-joiner asks teammates to push their current save state."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class SaveGameComplete(BaseModel):
    """Local player killed final Ganon — broadcast to room."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class AudioOcarinaSfx(BaseModel):
    """Streamed ocarina note from one player to teammates in the same scene."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    note: int = Field(..., ge=0, le=255)
    modulator: float = 1.0
    bend: int = Field(default=0, ge=-128, le=127)
    quiet: bool = True
    target_client_id: Optional[int] = Field(default=None, alias="targetClientId")


# =============================================================================
# Handlers
# =============================================================================

# Outbound payloads use camelCase keys (modId, sceneNum, …) because the
# C++ readers index them directly. Schemas still accept snake_case inbound
# via populate_by_name=True.

def register(d: Dispatcher) -> None:

    @d.register("INVENTORY.GIVE_ITEM", schema=InventoryGiveItem,
                default_role="player", default_scope="room")
    async def give_item(server, session, room, target, p: InventoryGiveItem):
        if room is None: return
        payload = {
            "source":    session.client_id,
            "clientId":  session.client_id,
            "modId":     p.mod_id,
            "getItemId": p.get_item_id,
            "count":     p.count,
        }
        if target is not None:
            await target.send("INVENTORY.GIVE_ITEM", payload)
        else:
            await server.broadcast_room(room, "INVENTORY.GIVE_ITEM", payload,
                                        exclude_id=session.client_id)

    @d.register("INVENTORY.REMOVE_ITEM", schema=InventoryRemoveItem,
                default_role="admin", default_scope="any_in_room")
    async def remove_item(server, session, room, target, p: InventoryRemoveItem):
        if target is None: return
        await target.send("INVENTORY.REMOVE_ITEM",
                          {"itemId": p.item_id, "count": p.count,
                           "source": session.client_id, "clientId": session.client_id})

    @d.register("INVENTORY.SET_DUNGEON_ITEMS", schema=InventorySetDungeonItems,
                default_role="player", default_scope="room")
    async def set_dungeon_items(server, session, room, target, p: InventorySetDungeonItems):
        if room is None: return
        await server.broadcast_room(room, "INVENTORY.SET_DUNGEON_ITEMS",
                                    {"source":       session.client_id,
                                     "clientId":     session.client_id,
                                     "mapIndex":     p.map_index,
                                     "dungeonItems": p.dungeon_items,
                                     "dungeonKeys":  p.dungeon_keys},
                                    exclude_id=session.client_id)

    @d.register("INVENTORY.SET_AMMO", schema=InventorySetAmmo,
                default_role="player", default_scope="room")
    async def set_ammo(server, session, room, target, p: InventorySetAmmo):
        if room is None: return
        await server.broadcast_room(room, "INVENTORY.SET_AMMO",
                                    {"source":       session.client_id,
                                     "clientId":     session.client_id,
                                     "itemId":       p.item_id,
                                     "amount":       p.amount,
                                     "amountBought": p.amount_bought},
                                    exclude_id=session.client_id)

    @d.register("SAVE.SET_FLAG", schema=SaveSetFlag,
                default_role="player", default_scope="room")
    async def set_flag(server, session, room, target, p: SaveSetFlag):
        if room is None: return
        await server.broadcast_room(room, "SAVE.SET_FLAG",
                                    {"source":    session.client_id,
                                     "clientId":  session.client_id,
                                     "namespace": p.namespace,
                                     "sceneNum":  p.scene_num,
                                     "flagType":  p.flag_type,
                                     "flag":      p.flag},
                                    exclude_id=session.client_id)

    @d.register("SAVE.UNSET_FLAG", schema=SaveUnsetFlag,
                default_role="player", default_scope="room")
    async def unset_flag(server, session, room, target, p: SaveUnsetFlag):
        if room is None: return
        await server.broadcast_room(room, "SAVE.UNSET_FLAG",
                                    {"source":    session.client_id,
                                     "clientId":  session.client_id,
                                     "namespace": p.namespace,
                                     "sceneNum":  p.scene_num,
                                     "flagType":  p.flag_type,
                                     "flag":      p.flag},
                                    exclude_id=session.client_id)

    @d.register("SAVE.SET_QUEST_STATE", schema=SaveSetQuestState,
                default_role="player", default_scope="room")
    async def set_quest_state(server, session, room, target, p: SaveSetQuestState):
        if room is None: return
        await server.broadcast_room(room, "SAVE.SET_QUEST_STATE",
                                    {"source":   session.client_id,
                                     "clientId": session.client_id,
                                     "rc":       p.rc,
                                     "status":   p.status,
                                     "skipped":  p.skipped},
                                    exclude_id=session.client_id)

    @d.register("SAVE.UPDATE_TEAM_STATE", schema=SaveUpdateTeamState,
                default_role="player", default_scope="room")
    async def update_team_state(server, session, room, target, p: SaveUpdateTeamState):
        if room is None: return
        await server.broadcast_room(room, "SAVE.UPDATE_TEAM_STATE",
                                    {"source":   session.client_id,
                                     "clientId": session.client_id,
                                     "state":    p.state},
                                    exclude_id=session.client_id)

    @d.register("SAVE.CUTSCENE_TRIGGER", schema=SaveCutsceneTrigger,
                default_role="player", default_scope="room")
    async def cutscene_trigger(server, session, room, target, p: SaveCutsceneTrigger):
        if room is None: return
        await server.broadcast_room(room, "SAVE.CUTSCENE_TRIGGER",
                                    {"source": session.client_id,
                                     "cutsceneIndex": p.cutscene_index,
                                     "sceneNum": p.scene_num},
                                    exclude_id=session.client_id)

    @d.register("SAVE.REQUEST_TEAM_STATE", schema=SaveRequestTeamState,
                default_role="player", default_scope="room")
    async def request_team_state(server, session, room, target, p: SaveRequestTeamState):
        # Late-joiner pull. Forward to room so any teammate can respond by
        # pushing SAVE.UPDATE_TEAM_STATE (their existing save broadcast handler
        # will reach the requester through the same room).
        if room is None: return
        await server.broadcast_room(room, "SAVE.REQUEST_TEAM_STATE",
                                    {"source":   session.client_id,
                                     "clientId": session.client_id},
                                    exclude_id=session.client_id)

    @d.register("SAVE.GAME_COMPLETE", schema=SaveGameComplete,
                default_role="player", default_scope="room")
    async def game_complete(server, session, room, target, p: SaveGameComplete):
        if room is None: return
        await server.broadcast_room(room, "SAVE.GAME_COMPLETE",
                                    {"source":   session.client_id,
                                     "clientId": session.client_id},
                                    exclude_id=session.client_id)

    @d.register("AUDIO.OCARINA_SFX", schema=AudioOcarinaSfx,
                default_role="player", default_scope="room")
    async def ocarina_sfx(server, session, room, target, p: AudioOcarinaSfx):
        if room is None: return
        # Single-target delivery if `targetClientId` is set, else
        # broadcast to everyone in the same scene.
        payload = {"source":    session.client_id,
                   "clientId":  session.client_id,
                   "note":      p.note,
                   "modulator": p.modulator,
                   "bend":      p.bend,
                   "quiet":     p.quiet}
        if p.target_client_id is not None:
            # Scope check: target must be in the same room as the sender.
            if any(m.client_id == p.target_client_id for m in room.members()):
                await server.send_to_client(p.target_client_id, "AUDIO.OCARINA_SFX", payload)
        else:
            await server.broadcast_room(room, "AUDIO.OCARINA_SFX", payload,
                                        exclude_id=session.client_id,
                                        same_scene_as=session)
