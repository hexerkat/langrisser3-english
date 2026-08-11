"""fsutil.py — output-path handling shared by every report writer.

`reports/` in this project is conventionally a **symlink** to a sibling
history repo (see `tests/test_layout_qa_snapshot.py`). A plain
`path.mkdir(parents=True, exist_ok=True)` cannot cope with that: when
the link dangles (the sibling repo was moved or deleted), `os.mkdir`
refuses to follow it and `exist_ok` does not forgive it, so every
writer died with a bare `FileExistsError` raised from inside pathlib.

`ensure_output_dir()` is the one place that knows the rule: a symlink
states the intent "write over there", so materialise the target.
"""

import os
from pathlib import Path

__all__ = ['ensure_output_dir']


def ensure_output_dir(path) -> Path:
    """Make `path` usable as an output directory; return it.

    Creates missing parents, follows (and materialises) dangling
    symlinks — including a dangling link used as a parent — and fails
    loudly when the path is occupied by a regular file.
    """
    path = Path(path)

    if path.is_symlink() and not path.exists():
        target = Path(os.readlink(path))
        if not target.is_absolute():
            target = path.parent / target
        ensure_output_dir(target)          # chains resolve recursively
        return path

    if path.exists() and not path.is_dir():
        raise NotADirectoryError(
            f'output path is not a directory: {path}\n'
            f'  Move or remove it, or point --output somewhere else.'
        )

    parent = path.parent
    if parent != path and not parent.exists():
        ensure_output_dir(parent)

    path.mkdir(parents=True, exist_ok=True)
    return path
