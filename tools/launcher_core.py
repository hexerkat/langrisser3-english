"""launcher_core.py — logic behind the build launcher window (launcher.py).

Kept free of Tkinter so it can be tested without a display: disc-folder
checks, the build.py command line, reading the finished image's folder from
the build log, the remembered settings, and how to open a folder per OS.
"""
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import disc_identity
from iso_tools import _find_jp_track, build_file_index, extract_file_data

FOLDER_PREFIX = "Folder:"

# The disc is identified by the SHA-256 of its whole Track 01
# (tools/disc_identity.py). The window background comes from the gallery the
# game itself ships on disc (CD-ROM extras, LANG/OMAKE), each picture pinned.
# Read from the player's disc, never bundled.
WALLPAPER_ARCHIVE = "LANG/OMAKE/GRAPHIC.LZH"
WALLPAPER_MEMBER = "TIALISU.JPG"
WALLPAPER_SHA256 = "1cb3d55d62eb1532a0fd1c2e8a012ec8af652c757289e26158b177cd5d41c79e"
# The window background, picked at random once the disc is verified (Ralf,
# 2026-10-14): Tiaris, Diehärte, Altemüller, Luna, Sophia, Liffany or Freya
# from the same gallery, each pinned so only the game's own verified art is
# shown. FUREA.JPG is 1024x768, the others 1152x870; all go to WINDOW_SIZE.
WALLPAPERS = {
    "TIALISU.JPG": WALLPAPER_SHA256,
    "DHIHALUT.JPG": "aed22a3f6d61097a6313b8f0bf85e7f0e0332a1afc6da86e73c188ca40a0b78d",
    "ALUTEMU.JPG": "af6d2b51191b4acd93fa2777feb11d8f3b1acea22566aa568e39071bb427d8f7",
    "LUNA.JPG": "d697534c009a999618e13047d6fa7db4b75e94a444440ca4c5f1b442d6fabc5a",
    "SOFIA.JPG": "f518263de2c1014ed7aaff9c34fcdd6120bf306d39044063ea5117ffaca90408",
    "LIFANIY.JPG": "8e5742c535d5614457f7238aa7e8c790bc9867ef7d93821b694824bf253c8827",
    "FUREA.JPG": "e3c8b8cc7218a84fdb722aac2e41ff6df9540d649eed4c3c46199638ff67ccf2",
}
WINDOW_SIZE = (768, 580)     # the 1152x870 gallery picture at 2/3

VERIFYING = "Verifying disc…"
VERIFIED = "Langrisser III (Japan) disc verified."
NOT_VERIFIED = "Not the Langrisser III (Japan) disc, or its data is damaged."


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


# The font selector: build.py --font values and their labels in the window.
# Must match font_tools.FONT_STYLES / DEFAULT_FONT_STYLE (tests/test_font_styles.py);
# kept here so the window opens without importing the font tables.
FONT_CHOICES = (("dosv", "Original style (DOS/V)"),
                ("eagle", "Eagle III"))
FONT_NOTES = {"dosv": "Closest to the Japanese game's own letters",
              "eagle": "Bolder letters, used by earlier versions of the patch"}
DEFAULT_FONT = "dosv"

# The preview beside each font: a line drawn with the style's own 8x16 art
# (tools/font_style_<key>.py), light on a dark window like the game's.
PREVIEW_TEXT = "Diehärte: Leave it to me!"
PREVIEW_FG, PREVIEW_BG = (255, 255, 255), (16, 24, 56)


def font_preview(key: str, text: str = PREVIEW_TEXT, scale: int = 2,
                 margin: int = 4):
    """(width, height, rgb) of text drawn in font style key, each pixel
    scale x scale, with margin background pixels around it."""
    import importlib
    style = importlib.import_module(f"font_style_{key}")
    glyphs = {}
    for table in ("LETTERS", "DIGITS", "PUNCT", "EXTRA_PUNCT",
                  "UMLAUTS", "UMLAUTS_UPPER"):
        glyphs.update(getattr(style, table, None) or {})
    w = len(text) * 8 * scale + 2 * margin
    h = 16 * scale + 2 * margin
    rgb = bytearray(bytes(PREVIEW_BG) * (w * h))
    for i, ch in enumerate(text):
        art = glyphs.get(ch, bytes(16))
        for y in range(16):
            for x in range(8):
                if not art[y] >> (7 - x) & 1:
                    continue
                for dy in range(scale):
                    row = margin + y * scale + dy
                    col = margin + (i * 8 + x) * scale
                    o = (row * w + col) * 3
                    rgb[o:o + 3 * scale] = bytes(PREVIEW_FG) * scale
    return w, h, rgb


def build_args(disc_dir: Path, encode_movie: bool,
               font: str | None = None) -> list[str]:
    """The build.py command-line arguments for this choice."""
    args = ["--jp-iso", str(disc_dir)]
    if font:
        args += ["--font", font]
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


@dataclass
class DiscCheck:
    ok: bool
    message: str
    jpeg: bytes | None = None      # TIALISU.JPG when verified


def verify_disc(disc_dir: Path, choose=None) -> DiscCheck:
    """File names first (fast), then the content: Track 01 must be the exact
    disc the patch is made for (its SHA-256). The gallery picture is the
    background, `choose`n among WALLPAPERS (random by default); a chosen
    picture that does not match its pin falls back to Tiaris."""
    import random
    import lzh
    ok, msg = check_disc_dir(Path(disc_dir))
    if not ok:
        return DiscCheck(False, msg)
    track = _find_jp_track(Path(disc_dir), 1)
    try:
        if not disc_identity.is_supported(track):
            return DiscCheck(False, disc_identity.WRONG_DISC)
        img = bytearray(track.read_bytes())
        entry = build_file_index(img).get(WALLPAPER_ARCHIVE)
        if entry is None:
            return DiscCheck(False, NOT_VERIFIED)
        archive = extract_file_data(img, entry.extent, entry.size)
        jpg = lzh.extract(archive, WALLPAPER_MEMBER)
    except Exception:  # noqa: BLE001 - unreadable data is a failed check, not a crash
        return DiscCheck(False, NOT_VERIFIED)
    if hashlib.sha256(jpg).hexdigest() != WALLPAPER_SHA256:
        return DiscCheck(False, NOT_VERIFIED)
    name = (choose or random.choice)(list(WALLPAPERS))
    if name != WALLPAPER_MEMBER:
        try:
            other = lzh.extract(archive, name)
            if hashlib.sha256(other).hexdigest() == WALLPAPERS[name]:
                jpg = other
        except Exception:  # noqa: BLE001 - keep Tiaris
            pass
    return DiscCheck(True, VERIFIED, jpg)


def wallpaper(jpeg: bytes):
    """(width, height, rgb) of the verified picture at window size."""
    import jpeg_baseline
    w, h, rgb = jpeg_baseline.decode(jpeg)
    return WINDOW_SIZE + (resize(rgb, w, h, *WINDOW_SIZE),)


def resize(rgb, width: int, height: int, new_w: int, new_h: int) -> bytearray:
    """Box-filter resize of packed RGB (each output pixel averages the source
    pixels it covers, whole pixels only)."""
    out = bytearray(new_w * new_h * 3)
    xs = [(x * width // new_w, max(x * width // new_w + 1, (x + 1) * width // new_w))
          for x in range(new_w)]
    for y in range(new_h):
        y0 = y * height // new_h
        y1 = max(y0 + 1, (y + 1) * height // new_h)
        rows = [rgb[r * width * 3:(r + 1) * width * 3] for r in range(y0, y1)]
        o = y * new_w * 3
        for x0, x1 in xs:
            n = (x1 - x0) * len(rows)
            for c in range(3):
                out[o + c] = sum(sum(row[i * 3 + c] for i in range(x0, x1)) for row in rows) // n
            o += 3
    return out


def ppm(width: int, height: int, rgb: bytes) -> bytes:
    """Binary PPM, which Tk's PhotoImage reads without any extension."""
    return b"P6\n%d %d\n255\n" % (width, height) + bytes(rgb)


def shade(rgb, width: int, height: int, box, factor: float) -> bytearray:
    """Copy of rgb with box (x0, y0, x1, y1; end exclusive) scaled by factor."""
    out = bytearray(rgb)
    x0, y0, x1, y1 = box
    x0, x1 = max(0, x0), min(width, x1)
    for y in range(max(0, y0), min(height, y1)):
        row = (y * width + x0) * 3
        end = (y * width + x1) * 3
        out[row:end] = bytes(int(v * factor) for v in out[row:end])
    return out
