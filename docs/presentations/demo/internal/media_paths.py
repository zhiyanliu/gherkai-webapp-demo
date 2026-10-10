"""Local paths for the archived demo production tools."""
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUILD = Path(os.environ.get("DEMO_BUILD_DIR", HERE / "work")).resolve()
WORK = BUILD / "edit"
RECORDING = BUILD / "capture"
SOURCE = RECORDING / "recording"
PREPARATION = RECORDING / "preparation"
DECK = BUILD / "deck"
RUNTIME_MODULES = Path(os.environ.get(
    "DEMO_NODE_MODULES",
    Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules",
)).resolve()
NODE = os.environ.get("DEMO_NODE", str(RUNTIME_MODULES.parent / "bin/node"))
FFMPEG = os.environ.get("DEMO_FFMPEG", shutil.which("ffmpeg") or "ffmpeg")
FFPROBE = os.environ.get("DEMO_FFPROBE", shutil.which("ffprobe") or "ffprobe")
