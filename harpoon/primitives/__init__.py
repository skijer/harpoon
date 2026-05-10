"""Primitive catalog. Each module registers handlers via the dispatcher.

Adding a new domain = create file + import below.
"""

from __future__ import annotations

from harpoon.dispatcher import Dispatcher


def register_all(dispatcher: Dispatcher) -> None:
    """Import every primitive module and register its handlers."""
    from harpoon.primitives import (
        control,        # HARPOON.* + ROOM.*
        admin,          # ADMIN.*
        player,         # PLAYER.*
        appearance,     # APPEARANCE.* (incl. SKIN_SYNC)
        combat,         # COMBAT.*
        world,          # WORLD.*
        inventory,      # INVENTORY.* + SAVE.*
        audio,          # AUDIO.*
        ui,             # UI.*
        map_ops,        # MAP.*
        chat,           # CHAT.*
        voting,         # VOTING.*
        team,           # TEAM.*
    )
    for mod in (control, admin, player, appearance, combat, world,
                inventory, audio, ui, map_ops, chat, voting, team):
        mod.register(dispatcher)
