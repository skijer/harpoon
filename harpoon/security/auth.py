"""Session token generation and validation.

Tokens are 256-bit random hex (64 chars). They identify a session across
reconnects without ever exposing the client's IP. The mapping
`token -> Session` lives in memory only — restarting the server invalidates
all tokens, same as the legacy server.
"""

from __future__ import annotations

import secrets


TOKEN_BYTES = 32  # 256 bits → 64 hex chars
TOKEN_HEX_LEN = TOKEN_BYTES * 2


def generate_token() -> str:
    """Cryptographically secure 256-bit hex token."""
    return secrets.token_hex(TOKEN_BYTES)


def is_valid_token_format(token: str) -> bool:
    """Cheap shape check before doing dictionary lookup."""
    if len(token) != TOKEN_HEX_LEN:
        return False
    try:
        int(token, 16)
    except ValueError:
        return False
    return True
