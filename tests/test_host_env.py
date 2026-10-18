"""Programs the packaged patcher starts get the user's own environment.

Red state (2026-10-14, Linux patcher built by CI, Ralf's playtest): the
PyInstaller executable puts its unpack folder (/tmp/_MEI...) in
LD_LIBRARY_PATH. The system ffmpeg inherited it, loaded the bundled older
libcrypto and stopped before encoding the opening:

    /usr/bin/ffmpeg: /tmp/_MEI.../libcrypto.so.3: version `OPENSSL_3.3.0' not found

and the window log showed only "returned non-zero exit status 1", without
ffmpeg's own message.

Red state (2026-10-17, Windows patcher built by CI, user report): with the
opening movie on, Build opened a black prompt window for ffmpeg. Closing it
killed ffmpeg and the build failed. A console program started from the
windowed patcher needs CREATE_NO_WINDOW.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))

try:
    import host_env
except ImportError:  # RED
    host_env = None

import movie_tools  # noqa: E402

MEI = {'LD_LIBRARY_PATH': '/tmp/_MEI12345', 'PATH': '/usr/bin', 'HOME': '/home/x'}


@pytest.fixture(autouse=True)
def _module():
    if host_env is None:
        pytest.fail('RED: tools/host_env.py missing')


def test_frozen_drops_the_unpack_folder():
    env = host_env.external_env(MEI, frozen=True)
    assert 'LD_LIBRARY_PATH' not in env
    assert env['PATH'] == '/usr/bin' and env['HOME'] == '/home/x'


def test_frozen_restores_the_users_own_value():
    env = host_env.external_env(dict(MEI, LD_LIBRARY_PATH_ORIG='/opt/lib'), frozen=True)
    assert env['LD_LIBRARY_PATH'] == '/opt/lib'
    assert 'LD_LIBRARY_PATH_ORIG' not in env


def test_not_frozen_is_untouched():
    assert host_env.external_env(MEI, frozen=False) == MEI


class _FakeProc:
    def __init__(self, lines, code):
        self.stdout = iter(lines)
        self._code = code

    def wait(self):
        return self._code


def test_ffmpeg_runs_with_the_clean_environment(monkeypatch):
    seen = {}

    def fake_popen(cmd, **kw):
        seen.update(kw)
        return _FakeProc([], 0)

    monkeypatch.setattr(movie_tools.subprocess, 'Popen', fake_popen)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setenv('LD_LIBRARY_PATH', '/tmp/_MEI12345')
    monkeypatch.delenv('LD_LIBRARY_PATH_ORIG', raising=False)
    movie_tools._run_ffmpeg(['ffmpeg', '-version'], cwd='.', quiet=True)
    assert 'LD_LIBRARY_PATH' not in seen['env']


def test_ffmpeg_failure_carries_its_message(monkeypatch):
    err = "/usr/bin/ffmpeg: libcrypto.so.3: version `OPENSSL_3.3.0' not found\n"
    monkeypatch.setattr(movie_tools.subprocess, 'Popen',
                        lambda cmd, **kw: _FakeProc([err], 1))
    with pytest.raises(RuntimeError, match='OPENSSL_3.3.0'):
        movie_tools._run_ffmpeg(['ffmpeg'], cwd='.', quiet=True)


CREATE_NO_WINDOW = 0x08000000


@pytest.mark.parametrize('quiet', [True, False])
def test_ffmpeg_opens_no_prompt_window_on_windows(monkeypatch, quiet):
    seen = {}

    def fake_popen(cmd, **kw):
        seen.update(kw)
        return _FakeProc([], 0)

    def fake_run(cmd, **kw):
        seen.update(kw)
    monkeypatch.setattr(movie_tools.subprocess, 'Popen', fake_popen)
    monkeypatch.setattr(movie_tools.subprocess, 'run', fake_run)
    monkeypatch.setattr(sys, 'platform', 'win32')
    movie_tools._run_ffmpeg(['ffmpeg', '-version'], cwd='.', quiet=quiet)
    assert seen.get('creationflags', 0) & CREATE_NO_WINDOW


def test_no_window_flag_only_on_windows():
    assert host_env.no_window('win32') == {'creationflags': CREATE_NO_WINDOW}
    assert host_env.no_window('linux') == {}
