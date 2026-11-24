"""
ALL ABOUT BRAIN — Unified Configuration Facade (`pipeline/config.py`).

Re-exports all live SSOT constants and profile helpers from the 4 domain modules:
  - `pipeline.config_paths` (workspace, storage, `/dev/shm` scratch, browser paths)
  - `pipeline.config_flow`  (Omni 1.2 Flash, Veo 3.1 Lite, Nano Banana 2.1, credit budgets)
  - `pipeline.config_qa`    (DQ/TQ/Prosody/LUFS/dHash/Post-Hoc QA thresholds)
  - `pipeline.config_v8`    (`expressive_25d_v8`, R68-R89 rules, cast/brain/camera locks)
"""

from pipeline.config_paths import *  # noqa: F401,F403
from pipeline.config_paths import _resolve_whale_executable  # noqa: F401
from pipeline.config_flow import *  # noqa: F401,F403
from pipeline.config_qa import *  # noqa: F401,F403
from pipeline.config_v8 import *  # noqa: F401,F403
