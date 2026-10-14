"""The patcher window shows how far the build is, not just that it is busy.

Red state (2026-10-14, Ralf's test of the CI-built patcher): the bar only
bounced back and forth for 3 to 10 minutes. Nearly all of that time is the
opening movie (ffmpeg) and the sector shifts in `rebuild_iso_batch`, which
printed nothing until each shift ended.

Rules: the build reports (stage, fraction of that stage) to
`build_progress`; `overall` turns that into one 0..1 value for the bar.
Stages: prepare (steps 1-6 start), movie (only when it is encoded), shift,
assemble (step 7).
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))

try:
    import build_progress as bp
except ImportError:  # RED
    bp = None

import iso_tools  # noqa: E402
import movie_tools  # noqa: E402


@pytest.fixture(autouse=True)
def _module():
    if bp is None:
        pytest.fail('RED: tools/build_progress.py missing')
    yield
    bp.set_sink(None)


def _collect():
    seen = []
    bp.set_sink(lambda stage, done: seen.append((stage, done)))
    return seen


# --- the one value the bar shows -------------------------------------------

@pytest.mark.parametrize('movie', [True, False])
def test_overall_runs_from_zero_to_one_in_stage_order(movie):
    stages = ['prepare'] + (['movie'] if movie else []) + ['shift', 'assemble']
    values = [bp.overall(s, d, movie) for s in stages for d in (0, .25, .5, 1)]
    assert values[0] == 0 and values[-1] == 1
    assert values == sorted(values)


def test_shift_owns_most_of_the_bar_without_a_movie():
    lo, hi = bp.overall('shift', 0, False), bp.overall('shift', 1, False)
    assert hi - lo > .9


def test_movie_report_without_a_movie_build_is_ignored():
    assert bp.overall('movie', .5, False) is None


def test_out_of_range_fractions_are_clamped():
    assert bp.overall('shift', 1.7, True) == bp.overall('shift', 1, True)
    assert bp.overall('shift', -1, True) == bp.overall('shift', 0, True)


def test_no_sink_means_report_does_nothing():
    bp.set_sink(None)
    bp.report('shift', .5)   # must not raise


# --- ffmpeg's -progress lines ----------------------------------------------

@pytest.mark.parametrize('line, want', [
    ('out_time_us=42000000', .5),
    ('out_time_us=84000000\n', 1.0),
    ('out_time_us=N/A', None),
    ('progress=end', 1.0),
    ('frame=12', None),
    ('[cinepak @ 0x1] something', None),
])
def test_ffmpeg_progress_line(line, want):
    assert bp.ffmpeg_fraction(line, 84.0) == want


class _FakeProc:
    def __init__(self, lines, code):
        self.stdout = iter(lines)
        self._code = code

    def wait(self):
        return self._code


def test_ffmpeg_reports_the_movie_as_it_encodes(monkeypatch):
    seen = _collect()
    lines = ['frame=1\n', 'out_time_us=21000000\n', 'progress=continue\n',
             'out_time_us=63000000\n', 'progress=end\n']
    cmds = []
    monkeypatch.setattr(movie_tools.subprocess, 'Popen',
                        lambda cmd, **kw: cmds.append(cmd) or _FakeProc(lines, 0))
    movie_tools._run_ffmpeg(['ffmpeg', '-i', 'x', 'out'], cwd='.', quiet=True)
    assert seen == [('movie', .25), ('movie', .75), ('movie', 1.0)]
    assert cmds[0][-1] == 'out' and '-progress' in cmds[0]


def test_ffmpeg_failure_still_carries_its_message(monkeypatch):
    err = "ffmpeg: libcrypto.so.3: version `OPENSSL_3.3.0' not found\n"
    monkeypatch.setattr(movie_tools.subprocess, 'Popen',
                        lambda cmd, **kw: _FakeProc(['out_time_us=0\n', err], 1))
    with pytest.raises(RuntimeError, match='OPENSSL_3.3.0') as info:
        movie_tools._run_ffmpeg(['ffmpeg', 'out'], cwd='.', quiet=True)
    assert 'out_time_us' not in str(info.value)


# --- the sector shifts ------------------------------------------------------

def _image(sectors):
    img = bytearray()
    for i in range(sectors):
        img += iso_tools._make_sector(i, bytes([i % 251]) * iso_tools.USER_SIZE)
    return img


def _entry(path, extent, size, slot):
    return iso_tools.ISOEntry(path, extent, size, False,
                              iso_tools.USER_OFFSET + 64 * slot)


def test_shifts_report_steady_progress_to_the_end():
    image = _image(600)
    index = {'A': _entry('A', 10, 2048, 0), 'B': _entry('B', 200, 2048, 1),
             'C': _entry('C', 400, 2048, 2)}
    seen = _collect()
    out = iso_tools.rebuild_iso_batch(image, index, [
        ('C', b'c' * 3 * 2048), ('A', b'a' * 2 * 2048), ('B', b'b' * 1024)])
    fracs = [d for s, d in seen if s == 'shift']
    assert all(s == 'shift' for s, _ in seen)
    assert fracs == sorted(fracs) and fracs[-1] == 1.0
    assert len(fracs) >= 5             # moves within a shift, not one jump per file
    assert len(out) // iso_tools.SECTOR_SIZE == 600 + 1 + 2
