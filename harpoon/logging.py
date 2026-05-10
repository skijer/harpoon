"""Colored logging matching the legacy server format."""

from __future__ import annotations

import sys
from datetime import datetime

try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
except ImportError:
    class _Stub:
        def __getattr__(self, _):
            return ""
    Fore = _Stub()  # type: ignore
    Style = _Stub()  # type: ignore


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _emit(level: str, color: str, msg: str) -> None:
    print(f"{Style.BRIGHT}[{_ts()}]{Style.RESET_ALL} {color}{level:<8}{Style.RESET_ALL} {msg}",
          file=sys.stdout, flush=True)


def info(msg: str) -> None:
    _emit("INFO", Fore.CYAN, msg)


def warn(msg: str) -> None:
    _emit("WARN", Fore.YELLOW, msg)


def error(msg: str) -> None:
    _emit("ERROR", Fore.RED, msg)


def connect(msg: str) -> None:
    _emit("CONNECT", Fore.GREEN, msg)


def disconnect(msg: str) -> None:
    _emit("DISCONN", Fore.MAGENTA, msg)


def packet(msg: str) -> None:
    _emit("PACKET", Fore.WHITE, msg)


def room(room_id: str, msg: str) -> None:
    _emit("ROOM", Fore.YELLOW, f"[{room_id}] {msg}")


def player(msg: str) -> None:
    _emit("PLAYER", Fore.GREEN, msg)


def audit(msg: str) -> None:
    """Auditable log line — every primitive invocation goes here for forensics."""
    _emit("AUDIT", Fore.MAGENTA, msg)
