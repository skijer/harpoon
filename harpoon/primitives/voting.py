"""VOTING.* — generic voting system (map vote, kick vote, gamemode vote, etc.).

Server-managed vote sessions. Anyone with the right role can start a vote;
players cast a single option per vote. End condition is timeout or admin
END. Result is broadcast as ROOM.EVENT.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from harpoon import logging as log
from harpoon.dispatcher import Dispatcher


# =============================================================================
# Schemas
# =============================================================================

class VotingStartVote(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    vote_id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., max_length=128)
    options: list[str] = Field(..., min_length=1, max_length=32)
    duration_seconds: int = Field(default=30, ge=5, le=600)
    allow_change: bool = True   # can a voter change their answer?


class VotingCastVote(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    vote_id: str = Field(..., max_length=64)
    option_index: int = Field(..., ge=0, le=64)


class VotingEndVote(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    vote_id: str = Field(..., max_length=64)


# =============================================================================
# State
# =============================================================================

class _Vote:
    def __init__(self, vote_id: str, title: str, options: list[str],
                 duration: int, allow_change: bool, started_by: int):
        self.vote_id = vote_id
        self.title = title
        self.options = options
        self.duration = duration
        self.allow_change = allow_change
        self.started_by = started_by
        self.started_at = time.time()
        self.ballots: dict[int, int] = {}  # client_id -> option_index
        self.ended = False
        self.timeout_task: asyncio.Task | None = None

    def tally(self) -> list[int]:
        counts = [0] * len(self.options)
        for idx in self.ballots.values():
            if 0 <= idx < len(counts):
                counts[idx] += 1
        return counts

    def winner(self) -> int:
        counts = self.tally()
        return max(range(len(counts)), key=lambda i: counts[i]) if counts else -1


# Active votes per room
_active: dict[str, dict[str, _Vote]] = {}  # room_id -> vote_id -> _Vote


def register(d: Dispatcher) -> None:

    async def _end_vote(server, room, vote: _Vote, reason: str):
        if vote.ended:
            return
        vote.ended = True
        if vote.timeout_task is not None:
            vote.timeout_task.cancel()

        counts = vote.tally()
        winner = vote.winner()
        log.room(room.room_id, f"vote {vote.vote_id} ended ({reason}) — counts={counts}")
        await server.broadcast_room(room, "VOTING.RESULT", {
            "vote_id": vote.vote_id,
            "title": vote.title,
            "options": vote.options,
            "counts": counts,
            "winner_index": winner,
            "reason": reason,
        })
        _active.get(room.room_id, {}).pop(vote.vote_id, None)

    async def _timeout_vote(server, room, vote: _Vote):
        try:
            await asyncio.sleep(vote.duration)
            await _end_vote(server, room, vote, "timeout")
        except asyncio.CancelledError:
            pass

    @d.register("VOTING.START_VOTE", schema=VotingStartVote,
                default_role="admin", default_scope="room")
    async def start_vote(server, session, room, target, p: VotingStartVote):
        if room is None: return
        votes = _active.setdefault(room.room_id, {})
        if p.vote_id in votes:
            await session.send("HARPOON.ERROR", {
                "code": "vote_already_active",
                "message": f"Vote {p.vote_id} is already running"})
            return
        vote = _Vote(p.vote_id, p.title, p.options, p.duration_seconds,
                     p.allow_change, session.client_id)
        votes[p.vote_id] = vote
        vote.timeout_task = asyncio.create_task(_timeout_vote(server, room, vote))
        log.room(room.room_id, f"vote {p.vote_id} started by {session.name}")
        await server.broadcast_room(room, "VOTING.STARTED", {
            "vote_id": p.vote_id,
            "title": p.title,
            "options": p.options,
            "duration_seconds": p.duration_seconds,
            "started_by": session.client_id,
        })

    @d.register("VOTING.CAST_VOTE", schema=VotingCastVote,
                default_role="player", default_scope="room")
    async def cast_vote(server, session, room, target, p: VotingCastVote):
        if room is None: return
        vote = _active.get(room.room_id, {}).get(p.vote_id)
        if vote is None or vote.ended:
            await session.send("HARPOON.ERROR", {
                "code": "vote_not_found",
                "message": f"Vote {p.vote_id} not active"})
            return
        if p.option_index >= len(vote.options):
            await session.send("HARPOON.ERROR", {
                "code": "bad_option",
                "message": f"Option {p.option_index} out of range"})
            return
        if not vote.allow_change and session.client_id in vote.ballots:
            await session.send("HARPOON.ERROR", {
                "code": "already_voted",
                "message": "Vote does not allow changing"})
            return
        vote.ballots[session.client_id] = p.option_index
        # Broadcast tallies as they change so clients see live counts.
        await server.broadcast_room(room, "VOTING.TALLY", {
            "vote_id": p.vote_id,
            "counts": vote.tally(),
            "voter": session.client_id,
            "option_index": p.option_index,
        })

    @d.register("VOTING.END_VOTE", schema=VotingEndVote,
                default_role="admin", default_scope="room")
    async def end_vote(server, session, room, target, p: VotingEndVote):
        if room is None: return
        vote = _active.get(room.room_id, {}).get(p.vote_id)
        if vote is None: return
        await _end_vote(server, room, vote, "manual")
