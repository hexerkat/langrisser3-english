"""test_launcher_core.py — the logic behind the build launcher window.

Red state (2026-10-08): tools/launcher_core.py does not exist.

The window (launcher.py) is a thin Tkinter shell; everything it decides
lives here so it can be pinned without a display: which disc folders are
accepted, the exact build.py command it runs, where the finished image is,
and how the last folder is remembered.
"""
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

import launcher_core as lc  # noqa: E402


def _disc(tmp_path, *names):
    d = tmp_path / "Langrisser III (Japan)"
    d.mkdir()
    for n in names:
        (d / n).write_bytes(b"")
    return d


REDUMP = ("Langrisser III (Japan) (3M).cue",
          "Langrisser III (Japan) (3M) (Track 01).bin",
          "Langrisser III (Japan) (3M) (Track 02).bin",
          "Langrisser III (Japan) (3M) (Track 03).bin")


class TestCheckDisc:

    def test_redump_folder_is_accepted(self, tmp_path):
        ok, msg = lc.check_disc_dir(_disc(tmp_path, *REDUMP))
        assert ok, msg

    def test_short_track_names_are_accepted(self, tmp_path):
        ok, _ = lc.check_disc_dir(_disc(tmp_path, "game.cue", "track01.bin",
                                        "track02.bin"))
        assert ok

    def test_missing_folder(self, tmp_path):
        ok, msg = lc.check_disc_dir(tmp_path / "nope")
        assert not ok and "not found" in msg

    def test_missing_cue(self, tmp_path):
        ok, msg = lc.check_disc_dir(_disc(tmp_path, *REDUMP[1:]))
        assert not ok and ".cue" in msg

    def test_missing_data_track(self, tmp_path):
        ok, msg = lc.check_disc_dir(_disc(tmp_path, REDUMP[0], *REDUMP[2:]))
        assert not ok and "Track 01" in msg

    def test_missing_audio_tracks(self, tmp_path):
        ok, msg = lc.check_disc_dir(_disc(tmp_path, *REDUMP[:2]))
        assert not ok and "audio" in msg


class TestBuildArgs:

    def test_plain_build(self, tmp_path):
        assert lc.build_args(tmp_path, encode_movie=False) == ["--jp-iso", str(tmp_path)]

    def test_movie_flag(self, tmp_path):
        assert lc.build_args(tmp_path, encode_movie=True)[-1] == "--encode-movie"

    def test_args_match_build_py_parser(self, tmp_path):
        """Every flag the launcher passes must be one build.py accepts."""
        sys.path.insert(0, str(PROJECT))
        import build
        args = build.build_arg_parser().parse_args(lc.build_args(tmp_path, True))
        assert args.jp_iso == tmp_path and args.encode_movie


class TestOutputRoot:
    """Red state: build.py always writes build/ and cache/ inside its own
    folder, which in the frozen executable is a temporary unpack dir."""

    def test_source_checkout_writes_in_the_repo(self, tmp_path):
        sys.path.insert(0, str(PROJECT))
        import build
        assert build.output_root(False, "/usr/bin/python3", tmp_path) == tmp_path

    def test_executable_writes_next_to_itself(self, tmp_path):
        sys.path.insert(0, str(PROJECT))
        import build
        exe = tmp_path / "dist" / "Langrisser3-Patcher.exe"
        assert build.output_root(True, str(exe), PROJECT) == exe.parent

    def test_main_takes_its_arguments(self):
        sys.path.insert(0, str(PROJECT))
        import build, inspect
        assert "argv" in inspect.signature(build.main).parameters


class TestOutputFolder:

    def test_reads_the_folder_line(self):
        log = ["  BUILD COMPLETE",
               "  Folder:       /x/build/Langrisser III (English v0.7.2)",
               "  Cue:          Langrisser III (English v0.7.2).cue"]
        assert lc.output_folder(log) == Path("/x/build/Langrisser III (English v0.7.2)")

    def test_none_when_the_build_failed(self):
        assert lc.output_folder(["ERROR: No Track 01 .bin found in: /x"]) is None

    def test_matches_what_build_py_prints(self):
        src = (PROJECT / "build.py").read_text(encoding="utf-8")
        assert "print(f'  Folder:       {output_dir}')" in src


class TestSettings:

    def test_roundtrip(self, tmp_path):
        f = tmp_path / "cfg" / "launcher.json"
        lc.save_settings({"disc_dir": "/a b/c", "encode_movie": True}, f)
        assert lc.load_settings(f) == {"disc_dir": "/a b/c", "encode_movie": True}

    def test_missing_or_broken_file_gives_defaults(self, tmp_path):
        assert lc.load_settings(tmp_path / "none.json") == {}
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        assert lc.load_settings(bad) == {}


class TestOpenFolder:
    """The folder goes to the opener as the host's own path text. Red state
    (CI 2026-10-14, windows-latest): the Linux and macOS cases expected the
    literal "/o", which a Windows host writes as "\\o"."""

    def test_linux(self):
        assert lc.open_folder_command(Path("/o"), "linux") == ["xdg-open", str(Path("/o"))]

    def test_macos(self):
        assert lc.open_folder_command(Path("/o"), "darwin") == ["open", str(Path("/o"))]

    def test_windows(self):
        assert lc.open_folder_command(Path("C:/o"), "win32") == ["explorer", str(Path("C:/o"))]


class TestVerifyDisc:
    """Red state (2026-10-12): a disc folder passes on file NAMES alone, so
    any folder with a .cue and Track .bin files enables Build. The disc must
    prove it is Langrisser III (Japan): its gallery archive
    LANG/OMAKE/GRAPHIC.LZH must yield TIALISU.JPG with a good LZH CRC and the
    pinned SHA-256. That same picture is the window background (Tiaris, at
    half size), read from the player's disc and never bundled."""

    TIALISU_SHA256 = "1cb3d55d62eb1532a0fd1c2e8a012ec8af652c757289e26158b177cd5d41c79e"

    @staticmethod
    def _jp():
        import os
        import pytest
        jp = os.environ.get("LANG3_JP_DIR")
        if not jp:
            pytest.skip("LANG3_JP_DIR not set")
        return Path(jp)

    def test_right_file_names_with_wrong_content_fail(self, tmp_path):
        check = lc.verify_disc(_disc(tmp_path, *REDUMP))
        assert not check.ok and check.jpeg is None
        assert "Langrisser III" in check.message

    def test_missing_folder_fails_with_the_name_check_message(self, tmp_path):
        check = lc.verify_disc(tmp_path / "nope")
        assert not check.ok and "not found" in check.message

    def test_real_disc_is_verified_and_gives_tiaris(self):
        import hashlib
        check = lc.verify_disc(self._jp(), choose=lambda names: "TIALISU.JPG")
        assert check.ok, check.message
        assert hashlib.sha256(check.jpeg).hexdigest() == self.TIALISU_SHA256
        w, h, rgb = lc.wallpaper(check.jpeg)
        assert (w, h) == lc.WINDOW_SIZE and len(rgb) == w * h * 3

    def test_background_is_one_of_three_pinned_pictures(self):
        """Ralf (2026-10-14): the background is picked at random among Tiaris,
        Diehärte and Altemüller, then also Luna, Sophia, Liffany and Freya.
        Each is pinned, so only the game's own verified art shows. Red state:
        verify_disc always gave Tiaris; then only the first three."""
        import hashlib
        assert set(lc.WALLPAPERS) == {"TIALISU.JPG", "DHIHALUT.JPG", "ALUTEMU.JPG", "LUNA.JPG",
                                      "SOFIA.JPG", "LIFANIY.JPG", "FUREA.JPG"}
        for name, sha in lc.WALLPAPERS.items():
            check = lc.verify_disc(self._jp(), choose=lambda names, n=name: n)
            assert check.ok and hashlib.sha256(check.jpeg).hexdigest() == sha, name
        w, h, rgb = lc.wallpaper(check.jpeg)
        assert (w, h) == lc.WINDOW_SIZE

    def test_default_choice_is_random_among_the_pictures(self):
        import hashlib
        seen = {hashlib.sha256(lc.verify_disc(self._jp()).jpeg).hexdigest() for _ in range(12)}
        assert seen <= set(lc.WALLPAPERS.values()) and len(seen) > 1

    def test_damaged_picture_on_a_real_track_fails(self, tmp_path):
        import lzh
        from iso_tools import SECTOR_SIZE, _find_jp_track, build_file_index, extract_file_data
        track = bytearray(_find_jp_track(self._jp(), 1).read_bytes())
        e = build_file_index(track)[lc.WALLPAPER_ARCHIVE]
        archive = extract_file_data(track, e.extent, e.size)
        member = next(m for m in lzh.list_members(archive) if m.name == lc.WALLPAPER_MEMBER)
        off = member.data_offset + 1000
        track[(e.extent + off // 2048) * SECTOR_SIZE + 16 + off % 2048] ^= 0xFF
        disc = _disc(tmp_path, REDUMP[0], REDUMP[2])
        (disc / REDUMP[1]).write_bytes(track)
        check = lc.verify_disc(disc)
        assert not check.ok and check.jpeg is None

class TestPicture:

    def test_ppm_header_and_size(self):
        data = lc.ppm(3, 2, bytes(18))
        assert data.startswith(b"P6\n3 2\n255\n")
        assert len(data) == len(b"P6\n3 2\n255\n") + 18

    def test_shade_darkens_only_the_box(self):
        rgb = bytearray([200] * (4 * 2 * 3))          # 4x2, all 200
        out = lc.shade(rgb, 4, 2, (1, 0, 3, 1), 0.5)  # x 1..2, row 0
        px = lambda x, y: out[(y * 4 + x) * 3]
        assert [px(x, 0) for x in range(4)] == [200, 100, 100, 200]
        assert [px(x, 1) for x in range(4)] == [200] * 4

    def test_resize_to_two_thirds(self):
        """The window shows the 1152x870 gallery picture at 768x580 (2/3), so the
        controls get the lower half with room to spare. Red state: no lc.resize."""
        w, h = 6, 3
        rgb = bytearray()
        for y in range(h):
            for x in range(w):
                rgb += bytes([x * 40, y * 100, 7])
        out = lc.resize(rgb, w, h, 4, 2)
        assert len(out) == 4 * 2 * 3
        px = lambda x, y: tuple(out[(y * 4 + x) * 3:(y * 4 + x) * 3 + 3])
        assert px(0, 0)[2] == 7 and px(3, 1)[2] == 7       # flat channel stays flat
        assert px(0, 0)[0] < px(3, 0)[0]                   # left to right gradient kept
        assert px(0, 0)[1] < px(0, 1)[1]                   # top to bottom gradient kept

    def test_wallpaper_size(self):
        assert lc.WINDOW_SIZE == (768, 580)


class TestFontPreview:
    """The patcher shows each font as the game draws it.
    Red state (2026-10-23): no preview existed."""

    def test_pixels_are_the_style_glyphs(self):
        import font_tools as ft
        for key, _label in lc.FONT_CHOICES:
            style = ft.FONT_STYLES[key]
            w, h, rgb = lc.font_preview(key, text="Dä", scale=1, margin=0)
            assert (w, h) == (16, 16)
            for x0, ch, art in ((0, "D", style.LETTERS["D"]),
                                (8, "ä", style.UMLAUTS["ä"])):
                for y in range(16):
                    for x in range(8):
                        lit = rgb[(y * w + x0 + x) * 3] == lc.PREVIEW_FG[0]
                        assert lit == bool(art[y] >> (7 - x) & 1), (key, ch, x, y)

    def test_default_preview_fits_beside_the_label(self):
        for key, _label in lc.FONT_CHOICES:
            w, h, rgb = lc.font_preview(key)
            assert w <= lc.WINDOW_SIZE[0] - 260 and len(rgb) == w * h * 3
