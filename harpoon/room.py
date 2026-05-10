"""Room — a multiplayer lobby. Holds sessions, gamemode_id, phase, config."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Optional

from harpoon.session import Session


class Room:
    def __init__(self, room_id: str, name: str, gamemode_id: str = "default",
                 password: str = "", max_players: int = 16) -> None:
        self.room_id = room_id
        self.name = name
        self.gamemode_id = gamemode_id
        self.password = password
        self.max_players = max_players

        self.host_client_id: int = 0
        self.phase: str = "lobby"
        self.timer_seconds: int = 0
        self.timer_label: str = ""
        self.timer_started_at: float = 0.0

        # Opaque config blob the host sets via ROOM.SET_GAMEMODE_CONFIG.
        # The server never interprets it; clients render based on it.
        self.config: dict[str, Any] = {}

        # Custom KV state set via ROOM.CUSTOM_STATE — visible to all members.
        self.custom_state: dict[str, Any] = {}

        # Members.
        self.sessions: dict[int, Session] = {}
        self.lock = asyncio.Lock()

        self.created_at = time.time()

    @classmethod
    def generate_id(cls) -> str:
        return str(uuid.uuid4())[:8]

    def add_session(self, session: Session) -> None:
        if not self.sessions:
            self.host_client_id = session.client_id
            session.role = "host"
        self.sessions[session.client_id] = session
        session.room_id = self.room_id

    def remove_session(self, client_id: int) -> Optional[Session]:
        session = self.sessions.pop(client_id, None)
        if session is not None:
            session.room_id = None
            # Host transfer to next remaining member.
            if self.host_client_id == client_id and self.sessions:
                next_id = next(iter(self.sessions))
                self.host_client_id = next_id
                self.sessions[next_id].role = "host"
        return session

    def is_empty(self) -> bool:
        return not self.sessions

    def is_full(self) -> bool:
        return len(self.sessions) >= self.max_players

    def get(self, client_id: int) -> Optional[Session]:
        return self.sessions.get(client_id)

    def members(self) -> list[Session]:
        return list(self.sessions.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "roomId": self.room_id,
            "name": self.name,
            "gameMode": self.gamemode_id,
            "hasPassword": bool(self.password),
            "playerCount": len(self.sessions),
            "maxPlayers": self.max_players,
            "phase": self.phase,
        }
