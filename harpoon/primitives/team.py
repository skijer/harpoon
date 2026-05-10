"""TEAM.* — team assignment, ready toggle, team-vs-team relations.

Teams are stored on the room as `room.custom_state[f"team_{client_id}"]`.
This is read by `CHAT.MESSAGE` (channel=team) for team-only chat.
"""

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field

from harpoon import logging as log
from harpoon.dispatcher import Dispatcher


# =============================================================================
# Schemas
# =============================================================================

class TeamAssign(BaseModel):
    """Assign yourself (or another player, if admin) to a team."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None  # None = self
    team: str = Field(..., min_length=1, max_length=32)


class TeamUnassign(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: Optional[int] = None


class TeamSetReady(BaseModel):
    """Toggle the per-player ready flag (lobby use)."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    ready: bool


class TeamSetRelationship(BaseModel):
    """Define how teams treat each other (ally/enemy/neutral)."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    team_a: str = Field(..., max_length=32)
    team_b: str = Field(..., max_length=32)
    relation: Literal["ally", "enemy", "neutral"]


class TeamUpdateScore(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    team: str = Field(..., max_length=32)
    score: int


class TeamSetRole(BaseModel):
    """Assign a gamemode-specific role (seeker/hider/competitor/runner/etc.)
    to a player. Stored on the room as custom_state, broadcast to all."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target: int = Field(..., ge=1)
    role: str = Field(..., max_length=32)


# =============================================================================
# Handlers
# =============================================================================

def register(d: Dispatcher) -> None:

    @d.register("TEAM.ASSIGN", schema=TeamAssign,
                default_role="player", default_scope="any_in_room")
    async def assign(server, session, room, target, p: TeamAssign):
        if room is None: return
        # If no target, assign self.
        if target is None and p.target is None:
            target = session
        if target is None: return
        room.custom_state[f"team_{target.client_id}"] = p.team
        log.room(room.room_id, f"{target.name} -> team {p.team}")
        await server.broadcast_room(room, "TEAM.ASSIGNED",
                                    {"target": target.client_id, "team": p.team,
                                     "source": session.client_id})

    @d.register("TEAM.UNASSIGN", schema=TeamUnassign,
                default_role="player", default_scope="any_in_room")
    async def unassign(server, session, room, target, p: TeamUnassign):
        if room is None: return
        if target is None and p.target is None:
            target = session
        if target is None: return
        room.custom_state.pop(f"team_{target.client_id}", None)
        await server.broadcast_room(room, "TEAM.UNASSIGNED",
                                    {"target": target.client_id,
                                     "source": session.client_id})

    @d.register("TEAM.SET_READY", schema=TeamSetReady,
                default_role="player", default_scope="self")
    async def set_ready(server, session, room, target, p: TeamSetReady):
        if room is None: return
        room.custom_state[f"ready_{session.client_id}"] = p.ready
        await server.broadcast_room(room, "TEAM.READY_CHANGED",
                                    {"source": session.client_id, "ready": p.ready})

    @d.register("TEAM.SET_RELATIONSHIP", schema=TeamSetRelationship,
                default_role="host", default_scope="room")
    async def set_relationship(server, session, room, target, p: TeamSetRelationship):
        if room is None: return
        # Sort to make the key deterministic (alliances are symmetric).
        a, b = sorted([p.team_a, p.team_b])
        room.custom_state[f"rel_{a}_{b}"] = p.relation
        await server.broadcast_room(room, "TEAM.RELATIONSHIP_CHANGED",
                                    {"team_a": p.team_a, "team_b": p.team_b,
                                     "relation": p.relation,
                                     "source": session.client_id})

    @d.register("TEAM.UPDATE_SCORE", schema=TeamUpdateScore,
                default_role="admin", default_scope="room")
    async def update_score(server, session, room, target, p: TeamUpdateScore):
        if room is None: return
        room.custom_state[f"score_{p.team}"] = p.score
        await server.broadcast_room(room, "TEAM.SCORE_UPDATED",
                                    {"team": p.team, "score": p.score,
                                     "source": session.client_id})

    @d.register("TEAM.SET_ROLE", schema=TeamSetRole,
                default_role="admin", default_scope="any_in_room")
    async def set_role(server, session, room, target, p: TeamSetRole):
        if room is None or target is None: return
        room.custom_state[f"role_{target.client_id}"] = p.role
        await server.broadcast_room(room, "TEAM.ROLE_ASSIGNED",
                                    {"target": target.client_id, "role": p.role,
                                     "source": session.client_id})
