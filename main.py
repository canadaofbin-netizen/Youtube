"""
ALL ABOUT BRAIN - YouTube Shorts Automated Production Pipeline Entry Point
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))


def _ensure_media_interpreter() -> None:
    """F-6: re-exec under an interpreter that has OpenCV when the current one lacks it (e.g. bare /usr/bin/python3)."""
    try:
        import cv2  # noqa: F401
        return
    except ImportError:
        pass
    if os.environ.get("AAB_REEXEC_DONE"):
        return
    candidates = [os.environ.get("AAB_PYTHON"), str(Path.home() / "hermes-venv" / "bin" / "python3"), str(WORKSPACE_ROOT / ".venv" / "bin" / "python")]
    for cand in candidates:
        if cand and Path(cand).exists() and Path(cand).resolve() != Path(sys.executable).resolve():
            os.environ["AAB_REEXEC_DONE"] = "1"
            os.execv(cand, [cand, *sys.argv])


_ensure_media_interpreter()

from pipeline.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
