"""Tests for the stdlib baseline-JPEG decoder behind the launcher wallpaper.

Red state (2026-10-12): tools/jpeg_baseline.py does not exist.

Truth is ffmpeg's decode of the same file. The decoder proper is pinned on
the raw Y/Cb/Cr planes (ffmpeg -pix_fmt = the file's own), where two correct
decoders differ only by IDCT rounding: max 1 at full size. Half size is
compared with ffmpeg's planes averaged over 2x2 boxes.

RGB is only compared on the real Tiaris picture, the thing the player sees,
with a mean bound: chroma upsampling legitimately differs (ffmpeg
interpolates, we replicate). A first draft compared RGB on synthetic 4:2:0
color bars and failed at mean 8 while the planes matched to 1: on hard color
edges that metric measures upsampling, not decoding.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

import jpeg_baseline as jb  # noqa: E402

FFMPEG = shutil.which("ffmpeg")
JP_DIR = os.environ.get("LANG3_JP_DIR")
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")


def ffmpeg_rgb(path):
    out = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return out.stdout


def box2(rgb, w, h):
    """Average 2x2 boxes (odd edges: the last full box wins, like the decoder)."""
    ow, oh = (w + 1) // 2, (h + 1) // 2
    out = bytearray(ow * oh * 3)
    for y in range(oh):
        for x in range(ow):
            for c in range(3):
                vals = [rgb[(min(2 * y + dy, h - 1) * w + min(2 * x + dx, w - 1)) * 3 + c]
                        for dy in (0, 1) for dx in (0, 1)]
                out[(y * ow + x) * 3 + c] = (sum(vals) + 2) // 4
    return out, ow, oh


def mean_abs(a, b):
    assert len(a) == len(b)
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def make_jpeg(tmp_path, size, pix_fmt):
    p = tmp_path / f"t_{size}_{pix_fmt}.jpg"
    subprocess.run([FFMPEG, "-v", "error", "-f", "lavfi", "-i", f"testsrc=size={size}",
                    "-frames:v", "1", "-q:v", "3", "-pix_fmt", pix_fmt, str(p)], check=True)
    return p


def ffmpeg_planes(path, pix_fmt, sizes):
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-f", "rawvideo",
                          "-pix_fmt", pix_fmt, "-"], capture_output=True, check=True).stdout
    out, o = [], 0
    for w, h in sizes:
        out.append(raw[o:o + w * h])
        o += w * h
    return out


def box2_plane(p, w, h):
    ow, oh = w // 2, h // 2
    return bytes((p[2 * y * w + 2 * x] + p[2 * y * w + 2 * x + 1] + p[(2 * y + 1) * w + 2 * x]
                  + p[(2 * y + 1) * w + 2 * x + 1] + 2) // 4 for y in range(oh) for x in range(ow))


@needs_ffmpeg
@pytest.mark.parametrize("size,pix_fmt,chroma", [
    ("37x23", "yuvj420p", (19, 12)), ("64x48", "yuvj444p", (64, 48)),
    ("50x30", "yuvj422p", (25, 30))])
def test_full_scale_planes_match_ffmpeg(tmp_path, size, pix_fmt, chroma):
    p = make_jpeg(tmp_path, size, pix_fmt)
    w, h = (int(v) for v in size.split("x"))
    sizes = [(w, h), chroma, chroma]
    dw, dh, planes = jb.decode_planes(p.read_bytes(), scale=1)
    assert (dw, dh) == (w, h)
    assert [(pw, ph) for pw, ph, _ in planes] == sizes
    for (_, _, mine), ref in zip(planes, ffmpeg_planes(p, pix_fmt, sizes)):
        assert max(abs(a - b) for a, b in zip(mine, ref)) <= 1


@needs_ffmpeg
def test_half_scale_planes_match_ffmpeg_box_average(tmp_path):
    p = make_jpeg(tmp_path, "64x48", "yuvj420p")
    _, _, planes = jb.decode_planes(p.read_bytes(), scale=2)
    sizes = [(64, 48), (32, 24), (32, 24)]
    for (pw, ph, mine), ref, (w, h) in zip(planes, ffmpeg_planes(p, "yuvj420p", sizes), sizes):
        assert (pw, ph) == (w // 2, h // 2)
        assert mean_abs(mine, box2_plane(ref, w, h)) < 1.0


@needs_ffmpeg
@pytest.mark.skipif(not JP_DIR, reason="LANG3_JP_DIR not set")
def test_tiaris_half_scale_matches_ffmpeg(tmp_path):
    from iso_tools import _find_jp_track, build_file_index, extract_file_data
    import lzh
    img = bytearray(_find_jp_track(Path(JP_DIR), 1).read_bytes())
    e = build_file_index(img)["LANG/OMAKE/GRAPHIC.LZH"]
    jpg = lzh.extract(extract_file_data(img, e.extent, e.size), "TIALISU.JPG")
    p = tmp_path / "TIALISU.JPG"
    p.write_bytes(jpg)
    w, h, rgb = jb.decode(jpg, scale=2)
    assert (w, h) == (576, 435)
    ref, _, _ = box2(ffmpeg_rgb(p), 1152, 870)
    assert mean_abs(rgb, ref) < 3.0


def test_rejects_non_jpeg():
    with pytest.raises(ValueError):
        jb.decode(b"not a jpeg at all", scale=2)


@needs_ffmpeg
def test_rejects_progressive(tmp_path):
    p = tmp_path / "prog.jpg"
    subprocess.run([FFMPEG, "-v", "error", "-f", "lavfi", "-i", "testsrc=size=32x32",
                    "-frames:v", "1", "-c:v", "mjpeg", "-pix_fmt", "yuvj420p",
                    "-q:v", "3", str(p)], check=True)
    data = bytearray(p.read_bytes())
    sof = data.index(b"\xff\xc0")
    data[sof + 1] = 0xC2          # mark the frame progressive
    with pytest.raises(ValueError):
        jb.decode(bytes(data), scale=2)
