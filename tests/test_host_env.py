"""Programs the packaged patcher starts get the user's own environment.

Red state (2026-10-14, Linux patcher built by CI, Ralf's playtest): the
PyInstaller executable puts its unpack folder (/tmp/_MEI...) in
LD_LIBRARY_PATH. The system ffmpeg inherited it, loaded the bundled older
libcrypto and stopped before encoding the opening:

    /usr/bin/ffmpeg: /tmp/_MEI.../libcrypto.so.3: version `OPENSSL_3.3.0' not found

and the window log showed only "returned non-zero exit status 1", without
ffmpeg's own message.
"""
import subprocess
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


def test_ffmpeg_runs_with_the_clean_environment(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, '', '')

    monkeypatch.setattr(movie_tools.subprocess, 'run', fake_run)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setenv('LD_LIBRARY_PATH', '/tmp/_MEI12345')
    monkeypatch.delenv('LD_LIBRARY_PATH_ORIG', raising=False)
    movie_tools._run_ffmpeg(['ffmpeg', '-version'], cwd='.', quiet=True)
    assert 'LD_LIBRARY_PATH' not in seen['env']


def test_ffmpeg_failure_carries_its_message(monkeypatch):
    err = "/usr/bin/ffmpeg: libcrypto.so.3: version `OPENSSL_3.3.0' not found\n"

    def fake_run(cmd, **kw):
        raise subprocess.CalledProcessError(1, cmd, output='', stderr=err)

    monkeypatch.setattr(movie_tools.subprocess, 'run', fake_run)
    with pytest.raises(RuntimeError, match='OPENSSL_3.3.0'):
        movie_tools._run_ffmpeg(['ffmpeg'], cwd='.', quiet=True)
