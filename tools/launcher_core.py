"""launcher_core.py — logic behind the build launcher window (launcher.py).

Kept free of Tkinter so it can be tested without a display: disc-folder
checks, the build.py command line, reading the finished image's folder from
the build log, the remembered settings, and how to open a folder per OS.
"""
import json
import os
import sys
from pathlib import Path

from iso_tools import _find_jp_track

FOLDER_PREFIX = "Folder:"


def check_disc_dir(disc_dir: Path) -> tuple[bool, str]:
    """Is this a usable Japanese disc folder? Mirrors what build.py needs:
    a .cue, the Track 01 data .bin and the audio track .bins."""
    disc_dir = Path(disc_dir)
    if not disc_dir.is_dir():
        return False, f"Folder not found: {disc_dir}"
    if not any(disc_dir.glob("*.cue")):
        return False, "No .cue file in this folder."
    if _find_jp_track(disc_dir, 1) is None:
        return False, 'No Track 01 .bin (e.g. "Langrisser III (Japan) (Track 01).bin").'
    if _find_jp_track(disc_dir, 2) is None:
        return False, "No audio tracks (Track 02 and up) next to Track 01."
    return True, "Japanese disc found."


def build_args(disc_dir: Path, encode_movie: bool) -> list[str]:
    """The build.py command-line arguments for this choice."""
    args = ["--jp-iso", str(disc_dir)]
    if encode_movie:
        args.append("--encode-movie")
    return args


def output_folder(log_lines) -> Path | None:
    """The image folder build.py prints at the end, or None if it never did."""
    for line in log_lines:
        text = line.strip()
        if text.startswith(FOLDER_PREFIX):
            return Path(text[len(FOLDER_PREFIX):].strip())
    return None


def settings_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "langrisser3-english" / "launcher.json"


def load_settings(path: Path | None = None) -> dict:
    path = path or settings_path()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict, path: Path | None = None) -> None:
    path = Path(path or settings_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def open_folder_command(folder: Path, platform: str = sys.platform) -> list[str]:
    if platform == "win32":
        return ["explorer", str(folder)]
    if platform == "darwin":
        return ["open", str(folder)]
    return ["xdg-open", str(folder)]
