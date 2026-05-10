"""Permission tables — what each role can call, and how often.

`player` rules apply to everyone after handshake. `admin` and `host`
inherit player + add moderation primitives. The server doesn't know about
gamemodes; pack-specific gating happens client-side via the room browser
filter (clients only see rooms whose gamemode_id they have installed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


Scope = Literal["self", "any_in_room", "room", "global"]
Role = Literal["player", "admin", "host"]


@dataclass(frozen=True)
class Rule:
    primitive: str
    scope: Scope
    rate_limit: tuple[int, float]   # (count, window_seconds)
    conditions: dict = field(default_factory=dict)


def _rl(count: int, window: float = 1.0) -> tuple[int, float]:
    """Rate-limit literal: `_rl(60)` = 60/sec, `_rl(1, 10.0)` = 1 per 10s."""
    return (count, window)


_PLAYER_DEFAULTS: dict[str, Rule] = {
    # Connection / room control.
    "ROOM.LIST":                            Rule("ROOM.LIST",                       "self",        _rl(5)),
    "ROOM.CREATE":                          Rule("ROOM.CREATE",                     "self",        _rl(2)),
    "ROOM.JOIN":                            Rule("ROOM.JOIN",                       "self",        _rl(2)),
    "ROOM.LEAVE":                           Rule("ROOM.LEAVE",                      "self",        _rl(2)),
    "ROOM.BROADCAST_EVENT":                 Rule("ROOM.BROADCAST_EVENT",            "room",        _rl(20)),

    # Player state — high-frequency per-frame.
    "PLAYER.UPDATE_FULL_STATE":             Rule("PLAYER.UPDATE_FULL_STATE",        "self",        _rl(60)),
    "PLAYER.UPDATE_TRANSFORM":              Rule("PLAYER.UPDATE_TRANSFORM",         "self",        _rl(60)),
    "PLAYER.UPDATE_SKELETON":               Rule("PLAYER.UPDATE_SKELETON",          "self",        _rl(60)),
    "PLAYER.UPDATE_LIMB_ROTATIONS":         Rule("PLAYER.UPDATE_LIMB_ROTATIONS",    "self",        _rl(60)),
    "PLAYER.UPDATE_ANIMATION_FLAGS":        Rule("PLAYER.UPDATE_ANIMATION_FLAGS",   "self",        _rl(60)),
    "PLAYER.UPDATE_MOTION_VARS":            Rule("PLAYER.UPDATE_MOTION_VARS",       "self",        _rl(60)),
    "PLAYER.UPDATE_BOW_STATE":              Rule("PLAYER.UPDATE_BOW_STATE",         "self",        _rl(60)),
    "PLAYER.UPDATE_HAND_TYPES":             Rule("PLAYER.UPDATE_HAND_TYPES",        "self",        _rl(60)),
    "PLAYER.UPDATE_VISUAL_STATE":           Rule("PLAYER.UPDATE_VISUAL_STATE",      "self",        _rl(10)),
    "PLAYER.UPDATE_EQUIP_VISIBLE":          Rule("PLAYER.UPDATE_EQUIP_VISIBLE",     "self",        _rl(20)),
    "PLAYER.UPDATE_FACE":                   Rule("PLAYER.UPDATE_FACE",              "self",        _rl(20)),
    "PLAYER.UPDATE_SCALE":                  Rule("PLAYER.UPDATE_SCALE",             "self",        _rl(10)),
    "PLAYER.UPDATE_CUSTOM_ITEM_STATE":      Rule("PLAYER.UPDATE_CUSTOM_ITEM_STATE", "self",        _rl(60)),
    "PLAYER.SET_TRANSFORMATION":            Rule("PLAYER.SET_TRANSFORMATION",       "self",        _rl(10)),
    "PLAYER.UPDATE_GORON_STATE":            Rule("PLAYER.UPDATE_GORON_STATE",       "self",        _rl(60)),
    "PLAYER.SET_INVINCIBILITY_TIMER":       Rule("PLAYER.SET_INVINCIBILITY_TIMER",  "self",        _rl(10)),
    "PLAYER.KILL":                          Rule("PLAYER.KILL",                     "room",        _rl(2)),

    # Combat — broadcast to a target.
    "COMBAT.DEAL_DAMAGE":                   Rule("COMBAT.DEAL_DAMAGE",              "any_in_room", _rl(20)),
    "COMBAT.APPLY_STATUS":                  Rule("COMBAT.APPLY_STATUS",             "any_in_room", _rl(10)),
    "COMBAT.KNOCKBACK":                     Rule("COMBAT.KNOCKBACK",                "any_in_room", _rl(10)),
    "COMBAT.DECOY_HIT":                     Rule("COMBAT.DECOY_HIT",                "any_in_room", _rl(10)),
    "COMBAT.SPAWN_DECOY":                   Rule("COMBAT.SPAWN_DECOY",              "self",        _rl(2)),
    "COMBAT.DESTROY_DECOY":                 Rule("COMBAT.DESTROY_DECOY",            "self",        _rl(2)),
    "COMBAT.CUSTOM_EFFECT":                 Rule("COMBAT.CUSTOM_EFFECT",            "any_in_room", _rl(10)),

    # Save / inventory / map sync — bursty during scene init, hence high cap.
    "SAVE.SET_FLAG":                        Rule("SAVE.SET_FLAG",                   "room",        _rl(200)),
    "SAVE.UNSET_FLAG":                      Rule("SAVE.UNSET_FLAG",                 "room",        _rl(200)),
    "SAVE.SET_QUEST_STATE":                 Rule("SAVE.SET_QUEST_STATE",            "room",        _rl(200)),
    "SAVE.UPDATE_TEAM_STATE":               Rule("SAVE.UPDATE_TEAM_STATE",          "room",        _rl(1, 10.0)),
    "SAVE.REQUEST_TEAM_STATE":              Rule("SAVE.REQUEST_TEAM_STATE",         "room",        _rl(2)),
    "SAVE.CUTSCENE_TRIGGER":                Rule("SAVE.CUTSCENE_TRIGGER",           "room",        _rl(10)),
    "SAVE.GAME_COMPLETE":                   Rule("SAVE.GAME_COMPLETE",              "room",        _rl(2)),
    "INVENTORY.GIVE_ITEM":                  Rule("INVENTORY.GIVE_ITEM",             "room",        _rl(200)),
    "INVENTORY.SET_DUNGEON_ITEMS":          Rule("INVENTORY.SET_DUNGEON_ITEMS",     "room",        _rl(20)),
    "INVENTORY.SET_AMMO":                   Rule("INVENTORY.SET_AMMO",              "room",        _rl(20)),
    "MAP.ENTRANCE_DISCOVERED":              Rule("MAP.ENTRANCE_DISCOVERED",         "room",        _rl(200)),

    # Appearance / skin sync — visible to other players in the room.
    "APPEARANCE.SKIN_SYNC.ANNOUNCE_CATALOG":Rule("APPEARANCE.SKIN_SYNC.ANNOUNCE_CATALOG","room",   _rl(2)),
    "APPEARANCE.SKIN_SYNC.UPDATE_SLOTS":    Rule("APPEARANCE.SKIN_SYNC.UPDATE_SLOTS","room",       _rl(10)),
    "APPEARANCE.SET_TINT":                  Rule("APPEARANCE.SET_TINT",             "any_in_room", _rl(10)),
    "APPEARANCE.SET_SCALE":                 Rule("APPEARANCE.SET_SCALE",            "any_in_room", _rl(10)),
    "APPEARANCE.HIDE_FROM_OBSERVER":        Rule("APPEARANCE.HIDE_FROM_OBSERVER",   "any_in_room", _rl(20)),
    "APPEARANCE.SHOW_TO_OBSERVER":          Rule("APPEARANCE.SHOW_TO_OBSERVER",     "any_in_room", _rl(20)),
    "APPEARANCE.SPAWN_VFX_ACTOR":           Rule("APPEARANCE.SPAWN_VFX_ACTOR",      "room",        _rl(30)),

    # Audio.
    "AUDIO.PLAY_SFX":                       Rule("AUDIO.PLAY_SFX",                  "self",        _rl(60)),
    "AUDIO.OCARINA_SFX":                    Rule("AUDIO.OCARINA_SFX",               "room",        _rl(60)),

    # World / teleport.
    "WORLD.TRANSPORT_SCENE":                Rule("WORLD.TRANSPORT_SCENE",           "any_in_room", _rl(2)),
    "WORLD.TELEPORT":                       Rule("WORLD.TELEPORT",                  "any_in_room", _rl(2)),

    # Chat / voting / team.
    "CHAT.MESSAGE":                         Rule("CHAT.MESSAGE",                    "room",        _rl(10)),
    "CHAT.EMOTE":                           Rule("CHAT.EMOTE",                      "room",        _rl(5)),
    "CHAT.PING":                            Rule("CHAT.PING",                       "room",        _rl(10)),
    "CHAT.MARK_LOCATION":                   Rule("CHAT.MARK_LOCATION",              "room",        _rl(2)),
    "VOTING.CAST_VOTE":                     Rule("VOTING.CAST_VOTE",                "room",        _rl(10)),
    "TEAM.SET_READY":                       Rule("TEAM.SET_READY",                  "self",        _rl(5)),
}

_ADMIN_EXTRAS: dict[str, Rule] = {
    "ROOM.SET_PHASE":                       Rule("ROOM.SET_PHASE",                  "room",        _rl(5)),
    "ROOM.SET_TIMER":                       Rule("ROOM.SET_TIMER",                  "room",        _rl(5)),
    "ROOM.SET_GAMEMODE_CONFIG":             Rule("ROOM.SET_GAMEMODE_CONFIG",        "room",        _rl(2)),
    "PLAYER.SET_HEALTH":                    Rule("PLAYER.SET_HEALTH",               "any_in_room", _rl(10)),
    "PLAYER.REVIVE":                        Rule("PLAYER.REVIVE",                   "any_in_room", _rl(5)),
    "PLAYER.RESPAWN":                       Rule("PLAYER.RESPAWN",                  "any_in_room", _rl(5)),
    "PLAYER.SET_INVULNERABLE":              Rule("PLAYER.SET_INVULNERABLE",         "any_in_room", _rl(10)),
    "TEAM.SET_ROLE":                        Rule("TEAM.SET_ROLE",                   "any_in_room", _rl(10)),
    "VOTING.START_VOTE":                    Rule("VOTING.START_VOTE",               "room",        _rl(1, 10.0)),
    "VOTING.END_VOTE":                      Rule("VOTING.END_VOTE",                 "room",        _rl(5)),
    "UI.SHOW_MESSAGE":                      Rule("UI.SHOW_MESSAGE",                 "any_in_room", _rl(5)),
    "UI.SHOW_BANNER":                       Rule("UI.SHOW_BANNER",                  "any_in_room", _rl(2)),
    "UI.UPDATE_LEADERBOARD":                Rule("UI.UPDATE_LEADERBOARD",           "room",        _rl(5)),
    "ADMIN.PROMOTE":                        Rule("ADMIN.PROMOTE",                   "any_in_room", _rl(2)),
    "ADMIN.DEMOTE":                         Rule("ADMIN.DEMOTE",                    "any_in_room", _rl(2)),
}

_HOST_EXTRAS: dict[str, Rule] = {
    "ROOM.START_GAME":                      Rule("ROOM.START_GAME",                 "room",        _rl(2)),
    "ROOM.SELECT_MAP":                      Rule("ROOM.SELECT_MAP",                 "room",        _rl(2)),
    "ROOM.SET_GAMEMODE_ID":                 Rule("ROOM.SET_GAMEMODE_ID",            "room",        _rl(2)),
    "ADMIN.SET_HOST":                       Rule("ADMIN.SET_HOST",                  "any_in_room", _rl(2)),
    "ADMIN.KICK":                           Rule("ADMIN.KICK",                      "any_in_room", _rl(2)),
}


# Resolved per-role rule tables (player ⊂ admin ⊂ host).
_RULES_BY_ROLE: dict[str, dict[str, Rule]] = {
    "player": dict(_PLAYER_DEFAULTS),
    "admin":  {**_PLAYER_DEFAULTS, **_ADMIN_EXTRAS},
    "host":   {**_PLAYER_DEFAULTS, **_ADMIN_EXTRAS, **_HOST_EXTRAS},
}


class PermissionRegistry:
    """Stateless permission lookup. Returns the same built-in rules
    regardless of gamemode_id — the server doesn't load packs."""

    def lookup_rule(self, gamemode_id: str, role: str, primitive: str) -> Optional[Rule]:
        return _RULES_BY_ROLE.get(role, {}).get(primitive)
