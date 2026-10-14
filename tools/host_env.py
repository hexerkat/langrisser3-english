"""tools/host_env.py: the environment for programs the patcher starts.

A PyInstaller executable (the released patcher) unpacks itself to a temporary
folder (/tmp/_MEI...) and puts that folder first in LD_LIBRARY_PATH, saving
the user's own value in LD_LIBRARY_PATH_ORIG when there was one. A system
program started from it (ffmpeg, the file manager) inherits the variable,
loads the bundled libraries instead of its own and can die on a version
mismatch: on 2026-10-14 ffmpeg stopped with "libcrypto.so.3: version
`OPENSSL_3.3.0' not found". Every external program gets external_env().
"""
from __future__ import annotations

import os
import sys

_VARS = ('LD_LIBRARY_PATH',)


def external_env(environ=None, frozen=None) -> dict:
    """A copy of the environment as the user had it before the patcher started."""
    env = dict(os.environ if environ is None else environ)
    if frozen is None:
        frozen = getattr(sys, 'frozen', False)
    if frozen:
        for var in _VARS:
            orig = env.pop(var + '_ORIG', None)
            if orig is None:
                env.pop(var, None)
            else:
                env[var] = orig
    return env
