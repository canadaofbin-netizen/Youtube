"""
ALL ABOUT BRAIN — Workspace Hygiene & Recurrence Guard (`scripts/workspace_hygiene.py`).

Enforces repository cleanliness and FUSE safety:
  1. Root directory contains only approved entries (no stray caches, `.tmp_*`, `.lock`, or legacy clutter).
  2. `pipeline/` contains zero `test_*.py` files and zero resurrected legacy Oct scripts.
  3. Zero `.tmp_*` atomic-write leftovers under `pipeline/`, `scripts/`, `tests/`, `.agents/`, `docs/`, or `research_dossiers/`.
  4. Zero POSIX symlinks in checked code/config/dossier trees (`fuse.rclone` rule).
  5. Zero hardcoded machine-specific legacy paths (`C:\\Users\\yunky`, `g:\\My Drive`, `/home/seluser`, `/tmp/bci_v5_ssd_workspace`).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

APPROVED_ROOT_ENTRIES: frozenset[str] = frozenset(
    {
        ".agents",
        ".git",
        ".gitignore",
        ".ignore",
        ".rgignore",
        "BCI_Shorts_Channel",
        "Completed_Psychology_100_Shorts",
        "Hermes youtube worklplace",
        "README.md",
        "artifacts_archive",
        "docs",
        "main.py",
        "pipeline",
        "produce_psychology_batch.py",
        "pytest.ini",
        "reports",
        "scripts",
        "tests",
    }
)

APPROVED_ROOT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^final_shorts_v8_pilot_\d+[A-Za-z0-9_]*\.mp4$"),
    re.compile(r"^final_shorts_v8_ep\d+[A-Za-z0-9_]*\.mp4$"),
    re.compile(r"^final_brain_only_[A-Za-z0-9_]+\.mp4$"),
)

BANNED_PIPELINE_FILES: frozenset[str] = frozenset(
    {
        "assemble_100_shorts.py",
        "assembly.py",
        "audio.py",
        "batch_psychology_production.py",
        "colab_runner.py",
        "fix_psychology_topic1.py",
        "generate_100_shorts_assets.py",
        "psychology_100_topics.py",
        "smoke_psychology_topic1.py",
        "smoke_topic1.py",
        "smoketest.py",
        "video_qa_inspector.py",
        "visuals.py",
    }
)

_LEGACY_PATH_TOKENS = (
    "C:\\" + "Users\\" + "yunky",
    "C:/" + "Users/" + "yunky",
    "g:\\" + "My Drive",
    "g:/" + "My Drive",
    "/home/" + "seluser",
    "/tmp/" + "bci_v5_ssd_workspace",
)


def _is_approved_root_entry(name: str) -> bool:
    if name in APPROVED_ROOT_ENTRIES:
        return True
    return any(pat.match(name) for pat in APPROVED_ROOT_PATTERNS)


def audit_workspace_hygiene(workspace_root: Path | None = None) -> dict[str, Any]:
    root = Path(workspace_root) if workspace_root is not None else WORKSPACE_ROOT
    issues: list[str] = []

    # 1. Root clutter check
    if root.exists():
        for entry in sorted(root.iterdir(), key=lambda p: p.name):
            if entry.is_symlink():
                issues.append(f"[symlink] forbidden POSIX symlink at root: {entry.name}")
            if not _is_approved_root_entry(entry.name):
                issues.append(f"[root_clutter] unapproved root entry: {entry.name}")

    # 2. pipeline/ test_*.py and banned legacy modules check
    pipe_dir = root / "pipeline"
    if pipe_dir.is_dir():
        for fp in sorted(pipe_dir.iterdir(), key=lambda p: p.name):
            if fp.is_symlink():
                issues.append(f"[symlink] forbidden POSIX symlink: pipeline/{fp.name}")
            if fp.is_file():
                if fp.name.startswith("test_") and fp.name.endswith(".py"):
                    issues.append(f"[pipeline_test_file] test file inside pipeline/: pipeline/{fp.name}")
                if fp.name in BANNED_PIPELINE_FILES:
                    issues.append(f"[legacy_pipeline_file] resurrected legacy Oct module: pipeline/{fp.name}")

    # 2b. BCI_Shorts_Channel top-level lock / temp / legacy duplicate clutter check
    chan_dir = root / "BCI_Shorts_Channel"
    if chan_dir.is_dir():
        for c_entry in sorted(chan_dir.iterdir(), key=lambda p: p.name):
            if c_entry.is_symlink():
                issues.append(f"[symlink] forbidden POSIX symlink: BCI_Shorts_Channel/{c_entry.name}")
            if c_entry.name.endswith(".lock") or c_entry.name == ".flow_download_harvest.lock":
                issues.append(f"[channel_lock_file] lock file on FUSE channel dir: BCI_Shorts_Channel/{c_entry.name}")
            if c_entry.name.startswith(".tmp_"):
                issues.append(f"[tmp_artifact] stranded temp entry in channel dir: BCI_Shorts_Channel/{c_entry.name}")
            if c_entry.is_dir() and c_entry.name in ("news", "scripts"):
                issues.append(
                    f"[duplicate_channel_dir] resurrected legacy duplicate directory: BCI_Shorts_Channel/{c_entry.name}"
                )

    # 3. Leftover .tmp_* & symlink scan across code/config/dossiers
    scan_trees = [
        root / "pipeline",
        root / "scripts",
        root / "tests",
        root / ".agents",
        root / "docs",
        root / "BCI_Shorts_Channel" / "research_dossiers",
    ]
    for tree in scan_trees:
        if not tree.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(tree, followlinks=False):
            # Prune heavy media subtrees inside dossiers so hygiene check stays < 1s on fuse.rclone
            dirnames[:] = [
                d
                for d in dirnames
                if d not in ("__pycache__", ".git", "media", "reference_images", "_scratch")
            ]
            dp = Path(dirpath)
            for dn in dirnames:
                cand_d = dp / dn
                if cand_d.is_symlink():
                    issues.append(f"[symlink] forbidden POSIX symlink: {cand_d.relative_to(root)}")
                if dn.startswith(".tmp_"):
                    issues.append(f"[tmp_leftover] stranded temp dir: {cand_d.relative_to(root)}")
            for fn in filenames:
                cand_f = dp / fn
                if cand_f.is_symlink():
                    issues.append(f"[symlink] forbidden POSIX symlink: {cand_f.relative_to(root)}")
                if fn.startswith(".tmp_"):
                    issues.append(f"[tmp_leftover] stranded temp file: {cand_f.relative_to(root)}")

    # 4. Hardcoded machine-specific path check across repo Python code & tests
    self_resolved = Path(__file__).resolve()
    code_targets: list[Path] = []
    for top_py in ("main.py", "produce_psychology_batch.py"):
        if (root / top_py).is_file():
            code_targets.append(root / top_py)
    for sub in ("pipeline", "scripts", "tests"):
        sdir = root / sub
        if sdir.is_dir():
            for dirpath, dirnames, filenames in os.walk(sdir):
                dirnames[:] = sorted(d for d in dirnames if d != "__pycache__" and not d.startswith("."))
                dp = Path(dirpath)
                for fn in sorted(filenames):
                    if fn.endswith(".py"):
                        code_targets.append(dp / fn)

    for py_file in code_targets:
        try:
            if py_file.resolve() == self_resolved:
                continue
        except OSError:
            pass
        txt = py_file.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(txt.splitlines(), start=1):
            for tok in _LEGACY_PATH_TOKENS:
                if tok.lower() in line.lower():
                    issues.append(
                        f"[hardcoded_path] {py_file.relative_to(root)}:{line_no} contains legacy hardcoded path {tok!r}"
                    )

    return {
        "passed": len(issues) == 0,
        "workspace_root": str(root),
        "issue_count": len(issues),
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit ALL ABOUT BRAIN workspace hygiene.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if any workspace hygiene violation exists.")
    parser.add_argument("--root", type=Path, default=None, help="Optional workspace root override.")
    args = parser.parse_args(argv)

    report = audit_workspace_hygiene(args.root)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.check and not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
