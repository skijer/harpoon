"""COMBAT.* — damage, status, knockback, decoy, custom effects."""

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field

from harpoon.dispatcher import Dispatcher


# =============================================================================
# Schemas
# =============================================================================

DamageType = Literal["physical", "fire", "ice", "electric", "poison",
                     "holy", "dark", "true",
                     "fire_rod", "ice_rod", "light_rod", "heavy", "bomb",
                     "aoe_stun", "launch", "normal", "boomerang",
                     "goron_roll", "goron_punch", "zora_fins", "fd_beam"]


class DamageFlags(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    type: DamageType = "physical"
    critical: bool = False
    piercing: bool = False
    knockback: float = 0.0
    status_effect: Optional[str] = None


class CombatDealDamage(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1, alias="targetClientId")
    damage: float = Field(..., ge=0.0, le=999.0)
    damage_flags: DamageFlags = Field(default_factory=DamageFlags)


class CombatHeal(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    amount: float = Field(..., ge=0.0, le=999.0)
    type: Literal["potion", "spell", "regen", "vampire", "fairy"] = "potion"


class CombatApplyStatus(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1, alias="targetClientId")
    status_id: str = Field(..., max_length=32, alias="statusId")
    duration: int = Field(default=0, ge=0)
    intensity: float = Field(default=1.0)


class CombatRemoveStatus(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    status_id: str = Field(..., max_length=32)


class CombatKnockback(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    force_x: float = 0.0
    force_y: float = 0.0
    force_z: float = 0.0


class CombatDecoyHit(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1, alias="targetClientId")
    decoy_slot: int = Field(..., ge=0, le=10, alias="decoySlot")


class CombatSpawnDecoy(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    slot: int = Field(..., ge=0, le=10)


class CombatDestroyDecoy(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    slot: int = Field(..., ge=0, le=10)


class CombatCustomEffect(BaseModel):
    """Whip pull, switch hook swap, dominion rod puppet, etc."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1, alias="targetClientId")
    effect_type: int = Field(..., ge=0, le=64, alias="customEffectType")


# =============================================================================
# Handlers
# =============================================================================

def register(d: Dispatcher) -> None:

    @d.register("COMBAT.DEAL_DAMAGE", schema=CombatDealDamage,
                default_role="player", default_scope="any_in_room")
    async def deal_damage(server, session, room, target, p: CombatDealDamage):
        if target is None: return
        await target.send("COMBAT.DEAL_DAMAGE", {
            "source": session.client_id,
            "target": p.target,
            "damage": p.damage,
            "damage_flags": p.damage_flags.model_dump(),
        })

    @d.register("COMBAT.HEAL", schema=CombatHeal,
                default_role="admin", default_scope="any_in_room")
    async def heal(server, session, room, target, p: CombatHeal):
        if target is None: return
        await target.send("COMBAT.HEAL",
                          {"amount": p.amount, "type": p.type, "source": session.client_id})

    @d.register("COMBAT.APPLY_STATUS", schema=CombatApplyStatus,
                default_role="player", default_scope="any_in_room")
    async def apply_status(server, session, room, target, p: CombatApplyStatus):
        if target is None: return
        await target.send("COMBAT.APPLY_STATUS",
                          {"status_id": p.status_id,
                           "duration": p.duration,
                           "intensity": p.intensity,
                           "source": session.client_id})

    @d.register("COMBAT.REMOVE_STATUS", schema=CombatRemoveStatus,
                default_role="admin", default_scope="any_in_room")
    async def remove_status(server, session, room, target, p: CombatRemoveStatus):
        if target is None: return
        await target.send("COMBAT.REMOVE_STATUS",
                          {"status_id": p.status_id, "source": session.client_id})

    @d.register("COMBAT.KNOCKBACK", schema=CombatKnockback,
                default_role="player", default_scope="any_in_room")
    async def knockback(server, session, room, target, p: CombatKnockback):
        if target is None: return
        await target.send("COMBAT.KNOCKBACK",
                          {"force_x": p.force_x, "force_y": p.force_y, "force_z": p.force_z,
                           "source": session.client_id})

    @d.register("COMBAT.DECOY_HIT", schema=CombatDecoyHit,
                default_role="player", default_scope="any_in_room")
    async def decoy_hit(server, session, room, target, p: CombatDecoyHit):
        if target is None: return
        await target.send("COMBAT.DECOY_HIT", {
            "source": session.client_id,
            "target": p.target,
            "decoy_slot": p.decoy_slot,
        })

    @d.register("COMBAT.SPAWN_DECOY", schema=CombatSpawnDecoy,
                default_role="player", default_scope="self")
    async def spawn_decoy(server, session, room, target, p: CombatSpawnDecoy):
        if room is None: return
        await server.broadcast_room(room, "COMBAT.SPAWN_DECOY",
                                    {"source": session.client_id, **p.model_dump()},
                                    exclude_id=session.client_id,
                                    same_scene_as=session)

    @d.register("COMBAT.DESTROY_DECOY", schema=CombatDestroyDecoy,
                default_role="player", default_scope="self")
    async def destroy_decoy(server, session, room, target, p: CombatDestroyDecoy):
        if room is None: return
        await server.broadcast_room(room, "COMBAT.DESTROY_DECOY",
                                    {"source": session.client_id, "slot": p.slot},
                                    exclude_id=session.client_id,
                                    same_scene_as=session)

    @d.register("COMBAT.CUSTOM_EFFECT", schema=CombatCustomEffect,
                default_role="player", default_scope="any_in_room")
    async def custom_effect(server, session, room, target, p: CombatCustomEffect):
        if target is None: return
        await target.send("COMBAT.CUSTOM_EFFECT", {
            "source": session.client_id,
            "target": p.target,
            "effect_type": p.effect_type,
            "attacker_pos_x": p.attacker_pos_x,
            "attacker_pos_y": p.attacker_pos_y,
            "attacker_pos_z": p.attacker_pos_z,
            "attacker_yaw": p.attacker_yaw,
        })
