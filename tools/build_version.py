"""tools/build_version.py: the version a build shows, and where it came from.

VERSION holds the release number (tools/stamp_version.py). The CI writes
BUILD_CHANNEL into every patcher it packages (patcher-binaries.yml):
  ""              a published release
  "rc.<commit>"   an rc/v* branch, the release candidate
  "test.<commit>" any other rc/ branch or a manual run, a test build
The label is the number plus "-<channel>", so a test or candidate build can
never pass for the release (Ralf, 2026-10-14). The release candidate shows the
same number the release will.
"""
from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8').strip()
    except OSError:
        return ''


def label(root: Path) -> str | None:
    """VERSION, plus "-<channel>" when BUILD_CHANNEL holds one. None without VERSION."""
    root = Path(root)
    version = _read(root / 'VERSION').lstrip('v')
    if not version:
        return None
    channel = _read(root / 'BUILD_CHANNEL')
    return f'{version}-{channel}' if channel else version


def channel_for(event: str, ref: str, sha: str) -> str:
    """The BUILD_CHANNEL the CI writes for this GitHub event and ref."""
    if event == 'release':
        return ''
    kind = 'rc' if ref.startswith('refs/heads/rc/v') else 'test'
    return f'{kind}.{sha[:7]}'


if __name__ == '__main__':          # used by .github/workflows/patcher-binaries.yml
    import os
    print(channel_for(os.environ.get('GITHUB_EVENT_NAME', ''),
                      os.environ.get('GITHUB_REF', ''), os.environ.get('GITHUB_SHA', '')))
