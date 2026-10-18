"""
ALL ABOUT BRAIN - YouTube Shorts Automated Production Pipeline Entry Point
"""

import sys
from pathlib import Path

# Add project root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from pipeline.cli import main

if __name__ == "__main__":
    main()
