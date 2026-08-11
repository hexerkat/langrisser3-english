"""test_layout_qa_output_paths.py — TDD for output-directory creation.

RED STATE (2026-08-11): every writer called
`path.parent.mkdir(parents=True, exist_ok=True)` directly. That call
raises a bare `FileExistsError` when the parent is a **dangling
symlink** — `exist_ok` only forgives a parent that is an existing
*directory*, and `os.mkdir` never follows a broken link.

That is exactly what happened to this project: `reports/` is a symlink
to a sibling repo (`~/romhack/lang3_layout_qa_history`) that vanished
from disk, so `analyze --all`, `report`, `worklist` and `snapshot` all
died with a traceback pointing at pathlib instead of at the real cause.

GREEN: `ensure_output_dir()` is the single writer-side helper. It
materialises the link target (the link states the intent: "write
there"), and raises a clear, actionable error when the path exists as
something that can never hold reports (a regular file).
"""

import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.fsutil import ensure_output_dir  # noqa: E402


def test_creates_a_plain_missing_directory(tmp_path):
    target = tmp_path / 'reports' / 'history'
    assert ensure_output_dir(target) == target
    assert target.is_dir()


def test_is_idempotent_on_an_existing_directory(tmp_path):
    target = tmp_path / 'reports'
    target.mkdir()
    ensure_output_dir(target)
    assert target.is_dir()


def test_materialises_a_dangling_symlink_target(tmp_path):
    """The regression: `reports` -> a sibling repo that no longer exists."""
    missing_repo = tmp_path / 'gone' / 'lang3_layout_qa_history'
    link = tmp_path / 'reports'
    link.symlink_to(missing_repo)
    assert not link.exists()          # dangling — the Red state

    ensure_output_dir(link)

    assert missing_repo.is_dir()
    assert link.is_symlink() and link.is_dir()   # link still intact


def test_materialises_through_a_dangling_symlink_parent(tmp_path):
    """`reports/history/` under a dangling `reports` link."""
    link = tmp_path / 'reports'
    link.symlink_to(tmp_path / 'gone' / 'history_repo')

    ensure_output_dir(link / 'history')

    assert (link / 'history').is_dir()


def test_rejects_a_regular_file_with_an_actionable_error(tmp_path):
    clash = tmp_path / 'reports'
    clash.write_text('not a directory')

    with pytest.raises(NotADirectoryError) as exc:
        ensure_output_dir(clash)

    assert str(clash) in str(exc.value)


def test_every_writer_routes_through_the_helper():
    """No writer may go back to a bare `mkdir` — that is the defect."""
    writers = [
        PROJ / 'tools' / 'layout_qa' / 'cli.py',
        PROJ / 'tools' / 'layout_qa' / 'readiness.py',
        PROJ / 'tools' / 'layout_qa' / 'snapshot.py',
        PROJ / 'tools' / 'layout_qa' / 'worklist.py',
        PROJ / 'tools' / 'polish_order.py',
        PROJ / 'tools' / 'gen_layout_prd.py',
    ]
    offenders = []
    for path in writers:
        for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if '.mkdir(' in line and 'fsutil' not in line:
                offenders.append(f'{path.name}:{n}: {line.strip()}')
    assert not offenders, 'bare mkdir() left in writers:\n' + '\n'.join(offenders)
