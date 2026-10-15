"""The one Japanese disc the patch is made for, by the SHA-256 of Track 01.

Every engine patch writes at fixed offsets of this disc's programs, so any
other data track would be patched blind. Redump 3M; the 1M dump has the same
Track 01. Rev A (7M) differs in PROG_3..7 and FNT_SYS and is refused.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

TRACK01_SHA256 = "557bfaaa37dc11b6190c46dca8841bc252dfe9f1b3ba8b77ff242843b2bff4c8"

WRONG_DISC = "Wrong disc or damaged data. Needs Langrisser III (Japan), Redump 3M or 1M (not 7M)."


def track01_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def is_supported(path: Path) -> bool:
    return track01_sha256(path) == TRACK01_SHA256
