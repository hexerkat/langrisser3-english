"""Only the exact disc the patch is made for is accepted: Track 01 must have
the pinned SHA-256 (Redump 3M; the 1M dump is the same data).

Red state (2026-10-15, Ralf's test with the Redump 7M disc, Rev A): the
patcher checked only the gallery picture, which Rev A shares, so it accepted
the disc. Rev A has a different PROG_3 (169,518 bytes differ), PROG_4..7 and
FNT_SYS. The build wrote every engine patch at the 3M offsets without
complaint, and the game froze on a button press while music and the
background kept running. The command line build had no disc check at all.

Ralf (2026-10-15): "a verificacao nao deveria ser só a imagem da galeria. e
sim o hash do disco".
"""
import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / 'tools'))

import launcher_core as lc  # noqa: E402
from iso_tools import SECTOR_SIZE, _find_jp_track, build_file_index  # noqa: E402


def _jp_dir() -> Path:
    jp = os.environ.get('LANG3_JP_DIR')
    if not jp:
        pytest.skip('LANG3_JP_DIR not set')
    return Path(jp)


@pytest.fixture(scope='module')
def other_revision(tmp_path_factory):
    """The real disc with one byte of PROG_3 changed: same gallery, same
    file names, different program, like Rev A."""
    jp = _jp_dir()
    d = tmp_path_factory.mktemp('disc') / 'Langrisser III (Japan) (Rev A) (7M)'
    d.mkdir()
    track = bytearray(_find_jp_track(jp, 1).read_bytes())
    e = build_file_index(track)['LANG/PROG_3.BIN']
    track[e.extent * SECTOR_SIZE + 16 + 0x1000] ^= 0x01
    for f in jp.iterdir():
        if f.suffix.lower() == '.cue':
            (d / f.name).write_text(f.read_text())
        elif f == _find_jp_track(jp, 1):
            (d / f.name).write_bytes(track)
        else:
            (d / f.name).symlink_to(f)
    return d


def test_the_supported_disc_is_verified():
    check = lc.verify_disc(_jp_dir())
    assert check.ok, check.message


def test_another_revision_is_refused_by_the_patcher(other_revision):
    check = lc.verify_disc(other_revision)
    assert not check.ok and check.jpeg is None
    assert '3M' in check.message


def test_another_revision_is_refused_by_the_build(other_revision, tmp_path):
    import build
    out = io.StringIO()
    with redirect_stdout(out):
        code = build.main(['--jp-iso', str(other_revision)])
    assert code == 1
    assert '3M' in out.getvalue()
    assert '[2/7]' not in out.getvalue()        # stops before any work
