"""Shared pytest setup: make the workspace root importable and isolate cache/lock side effects to /tmp."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))


@pytest.fixture(autouse=True)
def _isolate_aab_workspace_caches_and_locks(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent pytest runs from mutating `BCI_Shorts_Channel/.cache` or live CDP leases."""
    iso_dir = tmp_path_factory.mktemp("aab_pytest_iso")
    if not os.environ.get("AAB_PERSISTENT_SHA_CACHE_PATH", "").strip():
        monkeypatch.setenv("AAB_PERSISTENT_SHA_CACHE_PATH", str(iso_dir / "persistent_sha256_cache.json"))
    if not os.environ.get("AAB_LOCKS_DIR", "").strip():
        locks_dir = iso_dir / "locks"
        locks_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("AAB_LOCKS_DIR", str(locks_dir))
    if not os.environ.get("AAB_CDP_LEASES_PATH", "").strip():
        monkeypatch.setenv("AAB_CDP_LEASES_PATH", str(iso_dir / "locks" / "aab_cdp_leases_9222.json"))

