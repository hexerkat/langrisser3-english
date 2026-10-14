"""How far a build is, for the patcher window's progress bar.

The build calls `report(stage, done)` with the fraction of the current stage;
the patcher installs a sink with `set_sink` and turns each report into one
0..1 value with `overall`. With no sink (command-line builds) reports cost
nothing.

Stages, in order: prepare (steps 1-6 start, seconds), movie (the ffmpeg
encode, only with --encode-movie), shift (the sector shifts of
`iso_tools.rebuild_iso_batch`, minutes), assemble (step 7). The spans are
measured shares of a build's time, rounded.
"""
from __future__ import annotations

SPANS = {
    True: {'prepare': (0.0, 0.02), 'movie': (0.02, 0.60),
           'shift': (0.60, 0.98), 'assemble': (0.98, 1.0)},
    False: {'prepare': (0.0, 0.02), 'shift': (0.02, 0.98),
            'assemble': (0.98, 1.0)},
}

_sink = None


def set_sink(fn) -> None:
    """fn(stage, done) receives every report; None turns reporting off."""
    global _sink
    _sink = fn


def report(stage: str, done: float) -> None:
    if _sink is not None:
        _sink(stage, done)


def overall(stage: str, done: float, movie: bool) -> float | None:
    """The bar value for `done` (0..1) of `stage`; None for a stage this
    build does not have."""
    span = SPANS[bool(movie)].get(stage)
    if span is None:
        return None
    lo, hi = span
    return lo + (hi - lo) * min(1.0, max(0.0, done))


def ffmpeg_fraction(line: str, duration: float) -> float | None:
    """The movie fraction in one line of `ffmpeg -progress`, or None."""
    key, _, value = line.strip().partition('=')
    if key == 'progress' and value == 'end':
        return 1.0
    if key == 'out_time_us' and value.isdigit():
        return min(1.0, int(value) / (duration * 1e6))
    return None
