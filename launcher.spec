# PyInstaller recipe for the standalone patcher (Windows .exe / Linux binary).
#   pip install pyinstaller && pyinstaller launcher.spec
# Bundles Python, Tkinter, build.py, tools/ and the git-tracked patch data, so
# the user needs nothing installed. Output: dist/Langrisser3-Patcher[.exe].
import subprocess
from pathlib import Path

# tools/ and build.py ship as SOURCE files at their repo paths: the modules
# find the project root as Path(__file__).parent.parent, which only holds if
# the folder layout survives (PyInstaller would otherwise flatten them).
DATA_DIRS = ["scripts", "data", "assets", "metadata", "config", "tools"]

tracked = subprocess.run(["git", "ls-files", "-z", *DATA_DIRS, "VERSION", "build.py"],
                         capture_output=True, check=True).stdout.decode().split("\0")
datas = [(f, str(Path(f).parent)) for f in tracked
         if f and not f.startswith("tools/research/")]
# The CI writes BUILD_CHANNEL (tools/build_version.py) before packaging: the
# channel of this build, shown after the version number. Absent = a release.
if Path("BUILD_CHANNEL").exists():
    datas.append(("BUILD_CHANNEL", "."))
SOURCE_SHIPPED = {Path(f).resolve() for f in tracked if f.endswith(".py")}

a = Analysis(
    ["launcher.py"],
    pathex=[".", "tools"],
    datas=datas,
    hiddenimports=["build"],
    excludes=["pytest"],
)
# The analysis still walks tools/ to collect the stdlib modules they need;
# the tools modules themselves are dropped here and load from the sources.
a.pure = [m for m in a.pure if Path(m[1]).resolve() not in SOURCE_SHIPPED]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="Langrisser3-Patcher",
    console=False,
    upx=False,
)
