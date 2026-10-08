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


class TestBuildCommand:

    def test_plain_build(self, tmp_path):
        disc = tmp_path / "disc"
        cmd = lc.build_command(disc, encode_movie=False, python="py")
        assert cmd == ["py", "-u", str(PROJECT / "build.py"),
                       "--jp-iso", str(disc)]

    def test_movie_flag(self, tmp_path):
        cmd = lc.build_command(tmp_path, encode_movie=True, python="py")
        assert cmd[-1] == "--encode-movie"

    def test_command_matches_build_py_parser(self, tmp_path):
        """Every flag the launcher passes must be one build.py accepts."""
        sys.path.insert(0, str(PROJECT))
        import build
        cmd = lc.build_command(tmp_path, encode_movie=True, python="py")
        args = build.build_arg_parser().parse_args(cmd[3:])
        assert args.jp_iso == tmp_path and args.encode_movie


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

    def test_linux(self):
        assert lc.open_folder_command(Path("/o"), "linux") == ["xdg-open", "/o"]

    def test_macos(self):
        assert lc.open_folder_command(Path("/o"), "darwin") == ["open", "/o"]

    def test_windows(self):
        assert lc.open_folder_command(Path("C:/o"), "win32") == ["explorer", str(Path("C:/o"))]
