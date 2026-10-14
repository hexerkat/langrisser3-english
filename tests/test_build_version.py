"""The version a build shows says where the build came from, and a packaged
build leaves no cache behind.

Red state (2026-10-14, Ralf's test of the CI-built patcher):
  - a test build from rc/patcher-test showed "v0.7.2", like the release, so
    nobody could tell a test or candidate build from the real one;
  - the patcher left a 23 MB `cache/` folder (copies of disc files) next to
    the executable after every build.

Rules: VERSION holds the release number; the CI writes BUILD_CHANNEL into the
patcher it packages: empty for a published release, "rc.<commit>" for an
rc/v* branch (release candidate), "test.<commit>" for any other rc/ branch.
The label is VERSION, plus "-<channel>" when there is one. It names the
window, the output folder and the title-screen credit.
"""
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

try:
    import build_version as bv
except ImportError:  # RED
    bv = None


@pytest.fixture(autouse=True)
def _module():
    if bv is None:
        pytest.fail('RED: tools/build_version.py missing')


def _root(tmp_path, version='0.8.0', channel=None):
    (tmp_path / 'VERSION').write_text(version + '\n')
    if channel is not None:
        (tmp_path / 'BUILD_CHANNEL').write_text(channel)
    return tmp_path


def test_release_label_is_the_number(tmp_path):
    assert bv.label(_root(tmp_path)) == '0.8.0'
    assert bv.label(_root(tmp_path, channel='\n')) == '0.8.0'


def test_candidate_and_test_labels(tmp_path):
    assert bv.label(_root(tmp_path, channel='rc.4cde827\n')) == '0.8.0-rc.4cde827'
    assert bv.label(_root(tmp_path, channel='test.4cde827')) == '0.8.0-test.4cde827'


def test_no_version_file(tmp_path):
    assert bv.label(tmp_path) is None


@pytest.mark.parametrize('event, ref, want', [
    ('release', 'refs/tags/v0.8.0', ''),
    ('push', 'refs/heads/rc/v0.8.0', 'rc.4cde827'),
    ('push', 'refs/heads/rc/patcher-test', 'test.4cde827'),
    ('workflow_dispatch', 'refs/heads/main', 'test.4cde827'),
])
def test_channel_from_the_ci_event(event, ref, want):
    assert bv.channel_for(event, ref, '4cde827d0e1f2a3b') == want


def test_credit_line_names_the_label(tmp_path):
    import build
    root = _root(tmp_path, channel='rc.4cde827')
    assert build.title_credit_text(root) == \
        'English patch 0.8.0-rc.4cde827 / Hexerkat & RalfGuth • 2026'


def test_packaged_build_uses_a_cache_that_goes_away(tmp_path):
    import build
    with build.build_cache(frozen=True) as cache:
        (cache / 'LANG_JP.CPK').write_bytes(b'x')
        assert cache.exists() and cache != build.OUTPUT_ROOT / 'cache'
    assert not cache.exists()


def test_source_build_keeps_its_cache():
    import build
    with build.build_cache(frozen=False) as cache:
        assert cache == build.OUTPUT_ROOT / 'cache'
