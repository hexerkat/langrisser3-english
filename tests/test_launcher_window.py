"""While a build runs, the patcher window locks what would change it.

Red state (2026-10-17, Windows patcher from CI, user report): after Build,
Browse, the disc folder field and the opening movie option still answered.
A new folder or a movie toggle mid build changes nothing in the running build
and leaves the window showing choices the result does not follow.
"""
import importlib
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

tk = pytest.importorskip('tkinter')


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['launcher.py'])   # no argument: the window
    launcher = importlib.import_module('launcher')
    monkeypatch.setattr(launcher.shutil, 'which', lambda name: '/usr/bin/' + name)
    monkeypatch.setattr(launcher.lc, 'load_settings', lambda: {})
    monkeypatch.setattr(launcher.lc, 'save_settings', lambda s: None)
    monkeypatch.setattr(launcher.Launcher, '_check_disc', lambda self: True)
    monkeypatch.setattr(launcher.threading, 'Thread',
                        lambda **kw: type('T', (), {'start': lambda self: None})())
    monkeypatch.setattr(launcher.messagebox, 'showinfo', lambda *a, **k: None)
    monkeypatch.setattr(launcher.messagebox, 'showerror', lambda *a, **k: None)
    try:
        w = launcher.Launcher()
    except tk.TclError as exc:
        pytest.skip(f'no display: {exc}')
    w.withdraw()
    w.disc_var.set('/some/disc')
    yield w
    w.destroy()


def _locked(w):
    return {
        'browse': w.browse_btn.instate(['disabled']),
        'folder': w.disc_entry.instate(['disabled']),
    }


def test_build_locks_browse_folder_and_movie(app):
    app.movie_var.set(False)
    app._build()
    assert _locked(app) == {'browse': True, 'folder': True}
    app._toggle_movie()
    assert app.movie_var.get() is False


def test_finish_unlocks_them(app):
    app._build()
    app.code = 1
    app._finish()
    assert _locked(app) == {'browse': False, 'folder': False}
    app._toggle_movie()
    assert app.movie_var.get() is True


def test_window_opens_on_the_dosv_font(monkeypatch, app):
    """User request 2026-10-23: DOS/V is preselected every time the window
    opens, even when the last build used another font.
    Red state: the window restored the font saved in the settings."""
    import launcher
    monkeypatch.setattr(launcher.lc, 'load_settings', lambda: {'font': 'eagle'})
    w = launcher.Launcher()
    try:
        assert w.font_var.get() == 'dosv'
    finally:
        w.destroy()


def test_preview_opens_a_balloon_popup(app):
    """The fonts are compared in a popup, one game balloon per font; the main
    window carries no preview picture.
    Red state (2026-11-01, user playtest): each font row had a fixed preview
    of a made up line beside it, and there was no popup."""
    import launcher
    assert not any(app.canvas.type(i) == 'image'
                   for i in app.canvas.find_withtag('font'))
    app.preview_btn.invoke()
    win = app.preview_win
    assert win is not None and win.winfo_exists()
    assert set(win.balloons) == {k for k, _label in launcher.lc.FONT_CHOICES}
    for key, photo in win.balloons.items():
        w, h, _rgb = launcher.lc.balloon_preview(key)
        assert (photo.width(), photo.height()) == (w, h)
    app.preview_btn.invoke()                 # a second click reuses the popup
    assert app.preview_win is win


def test_preview_locked_while_building(app):
    app._lock(True)
    assert app.preview_btn.instate(['disabled'])
    app._lock(False)
    assert not app.preview_btn.instate(['disabled'])
