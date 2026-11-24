"""Comprehensive tests for `scripts/sync_archive.py` and `.agents/hooks.json` (`R83 v3` Fresh-Room)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.parse

from scripts.sync_archive import (
    DEFAULT_ARCHIVE_DIR,
    HISTORICAL_CONV_FOLDER_MAP,
    WORKSPACE_ROOT,
    YOUTUBE_PROJECT_ID,
    _discover_unlisted_07_youtube_convs,
    generate_index_md,
    handle_stop_payload,
    resolve_archive_folder,
    rewrite_markdown_links,
    sync_all,
    sync_conversation,
)

SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "sync_archive.py"
HOOKS_JSON_PATH = WORKSPACE_ROOT / ".agents" / "hooks.json"
GLOBAL_HOOKS_JSON_PATH = Path.home() / ".gemini" / "config" / "hooks.json"
AGENTS_MD_PATH = WORKSPACE_ROOT / ".agents" / "AGENTS.md"


def test_hooks_json_and_workspace_configs_valid() -> None:
    assert HOOKS_JSON_PATH.exists(), ".agents/hooks.json must exist"
    hooks_cfg = json.loads(HOOKS_JSON_PATH.read_text(encoding="utf-8"))
    assert "artifact-auto-archive" in hooks_cfg
    entry = hooks_cfg["artifact-auto-archive"]

    assert "PostToolUse" not in entry, "PostToolUse hook must be removed in Fresh-Room R83 v3"

    stop_list = entry["Stop"]
    assert isinstance(stop_list, list) and len(stop_list) == 1
    assert stop_list[0]["type"] == "command"
    assert stop_list[0]["timeout"] == 20
    assert str(SCRIPT_PATH) in stop_list[0]["command"]
    assert "--hook stop" in stop_list[0]["command"]

    # Global hooks.json must NOT duplicate youtube-artifact-auto-archive
    if GLOBAL_HOOKS_JSON_PATH.exists():
        global_hooks = json.loads(GLOBAL_HOOKS_JSON_PATH.read_text(encoding="utf-8-sig"))
        assert "youtube-artifact-auto-archive" not in global_hooks

    agents_bytes = AGENTS_MD_PATH.read_bytes()
    assert 3_000 <= len(agents_bytes) <= 6_500, "AGENTS.md must stay compact (3-6.5 KB)"
    storage_rules_txt = (WORKSPACE_ROOT / ".agents" / "rules" / "project_storage_rules.md").read_text(encoding="utf-8")
    assert "artifacts_archive/" in storage_rules_txt
    assert "sync_archive.py" in storage_rules_txt

    assert not (WORKSPACE_ROOT / ".rgignore").exists(), "Duplicate .rgignore retired in favor of single .ignore"
    ignore_txt = (WORKSPACE_ROOT / ".ignore").read_text(encoding="utf-8")
    assert "artifacts_archive/" in ignore_txt


def test_sync_all_exclusions_relative_rewriting_and_incremental_skip(tmp_path: Path) -> None:
    brain_root = tmp_path / "brain"
    archive_dir = tmp_path / "artifacts_archive"

    ceo_cid = "b57c97a8-6324-4c31-a2bb-16b25e28dd55"
    res_cid = "ffbdfca1-9c07-48b3-9b1e-3e3045d67c0c"
    unlisted_cid = "deadbeef-1234-5678-9abc-def012345678"

    ceo_src = brain_root / ceo_cid
    (ceo_src / "signature_cast").mkdir(parents=True)
    (ceo_src / ".system_generated" / "steps").mkdir(parents=True)
    (ceo_src / "scratch").mkdir(parents=True)

    # Excluded files that must NEVER be copied
    (ceo_src / ".system_generated" / "steps" / "out.txt").write_text("internal", encoding="utf-8")
    (ceo_src / "scratch" / "draft.md").write_text("scratch", encoding="utf-8")
    (ceo_src / "report.md.metadata.json").write_text("{}", encoding="utf-8")
    (ceo_src / "report.md.resolved.0").write_text("old", encoding="utf-8")
    (ceo_src / ".hidden_note.md").write_text("hidden", encoding="utf-8")

    # Valid media + markdown with absolute, file://, cross-chatroom, HTML img, and workspace code links
    (ceo_src / "signature_cast" / "opt1_sheet.jpg").write_bytes(b"\xff\xd8\xff\xe0FAKEJPG1")
    res_src = brain_root / res_cid
    res_src.mkdir(parents=True)
    (res_src / "ricksclips3000_shorts_report.md").write_text("# RicksClips Benchmark\n", encoding="utf-8")

    original_md = (
        "# Signature Cast Comparison\n\n"
        f"![Option 1]({ceo_src}/signature_cast/opt1_sheet.jpg)\n"
        f"[Self Plan](file://{ceo_src}/report.md#section-2)\n"
        f"[Cross Research](file://{res_src}/ricksclips3000_shorts_report.md)\n"
        f'<img src="{ceo_src}/signature_cast/opt1_sheet.jpg" width="320">\n'
        "[Code Link](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py)\n"
        "[Deleted Old Conv](file:///home/canadaofbin/.gemini/antigravity-cli/brain/e07a753a-0000-0000-0000-000000000000/gone.md)\n"
    )
    (ceo_src / "report.md").write_text(original_md, encoding="utf-8")

    unlisted_src = brain_root / unlisted_cid
    unlisted_src.mkdir(parents=True)
    (unlisted_src / "adhoc.md").write_text("# Adhoc Report\n", encoding="utf-8")

    results_1 = sync_all(
        archive_dir=archive_dir,
        brain_roots=[brain_root],
        extra_conv_ids=[unlisted_cid],
    )
    assert sum(r.copied for r in results_1) == 4

    assert (archive_dir / "01_YouTube_CEO" / "report.md").exists()
    assert (archive_dir / "01_YouTube_CEO" / "signature_cast" / "opt1_sheet.jpg").exists()
    assert (archive_dir / "03_Research" / "ricksclips3000_shorts_report.md").exists()
    assert (archive_dir / "conv_deadbeef" / "adhoc.md").exists()

    assert not (archive_dir / "01_YouTube_CEO" / ".system_generated").exists()
    assert not (archive_dir / "01_YouTube_CEO" / "scratch").exists()
    assert not (archive_dir / "01_YouTube_CEO" / "report.md.metadata.json").exists()
    assert not (archive_dir / "01_YouTube_CEO" / "report.md.resolved.0").exists()
    assert not (archive_dir / "01_YouTube_CEO" / ".hidden_note.md").exists()

    assert (ceo_src / "report.md").read_text(encoding="utf-8") == original_md
    archived_md = (archive_dir / "01_YouTube_CEO" / "report.md").read_text(encoding="utf-8")
    assert "![Option 1](./signature_cast/opt1_sheet.jpg)" in archived_md
    assert "[Self Plan](./report.md#section-2)" in archived_md
    assert "[Cross Research](../03_Research/ricksclips3000_shorts_report.md)" in archived_md
    assert '<img src="./signature_cast/opt1_sheet.jpg" width="320">' in archived_md
    assert "file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py" in archived_md
    assert "e07a753a-0000-0000-0000-000000000000/gone.md" in archived_md

    index_txt = (archive_dir / "INDEX.md").read_text(encoding="utf-8")
    assert "./01_YouTube_CEO/report.md" in index_txt
    assert "./03_Research/ricksclips3000_shorts_report.md" in index_txt
    assert "./conv_deadbeef/adhoc.md" in index_txt

    results_2 = sync_all(
        archive_dir=archive_dir,
        brain_roots=[brain_root],
        extra_conv_ids=[unlisted_cid],
    )
    assert sum(r.copied for r in results_2) == 0
    assert sum(r.skipped for r in results_2) == 4

    updated_md = original_md + "\nUpdated conclusion.\n"
    (ceo_src / "report.md").write_text(updated_md, encoding="utf-8")
    st = (ceo_src / "report.md").stat()
    os.utime(ceo_src / "report.md", (st.st_atime, st.st_mtime + 5))

    results_3 = sync_all(
        archive_dir=archive_dir,
        brain_roots=[brain_root],
        extra_conv_ids=[unlisted_cid],
    )
    assert sum(r.copied for r in results_3) == 1
    assert "Updated conclusion." in (archive_dir / "01_YouTube_CEO" / "report.md").read_text(encoding="utf-8")


def test_stop_hook_subprocess_and_edge_cases(tmp_path: Path) -> None:
    brain_root = tmp_path / "brain"
    archive_dir = tmp_path / "artifacts_archive"
    daily_cid = "e3210c73-cc41-4432-87b1-c158efe9cadb"
    daily_brain = brain_root / daily_cid
    daily_brain.mkdir(parents=True)

    base_cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(SCRIPT_PATH),
        "--archive-dir",
        str(archive_dir),
        "--brain-root",
        str(brain_root),
    ]
    hook_cwd = WORKSPACE_ROOT / ".agents"

    report_src = daily_brain / "youtube_daily_report_2026_11_05.md"
    chart_src = daily_brain / "2026-11-05_studio_charts.png"
    chart_src.write_bytes(b"\x89PNG\r\n\x1a\nFAKEPNG")
    report_src.write_text(f"# Daily Report\n![Chart]({chart_src})\n", encoding="utf-8")

    # Large (>2MB) & video/audio (.mp4/.wav) files must be excluded from archive
    (daily_brain / "huge_preview.mp4").write_bytes(b"0" * 1024)
    (daily_brain / "voice_test.wav").write_bytes(b"0" * 1024)
    (daily_brain / "oversized_dump.png").write_bytes(b"0" * (2 * 1024 * 1024 + 64))

    handle_stop_payload(
        {"conversationId": daily_cid, "artifactDirectoryPath": str(daily_brain)},
        archive_dir=archive_dir,
        brain_roots=[brain_root],
    )
    assert not (archive_dir / "05_Daily_Report" / "huge_preview.mp4").exists()
    assert not (archive_dir / "05_Daily_Report" / "voice_test.wav").exists()
    assert not (archive_dir / "05_Daily_Report" / "oversized_dump.png").exists()
    archived_report = archive_dir / "05_Daily_Report" / "youtube_daily_report_2026_11_05.md"
    assert archived_report.exists()
    assert "![Chart](./2026-11-05_studio_charts.png)" in archived_report.read_text(encoding="utf-8")
    assert (archive_dir / "05_Daily_Report" / "2026-11-05_studio_charts.png").exists()
    assert (archive_dir / "INDEX.md").exists()

    # No-op Stop hook when 0 files changed -> returns {"decision": "stop"} without rewriting INDEX.md
    index_path = archive_dir / "INDEX.md"
    os.utime(index_path, (1_700_000_000, 1_700_000_000))
    mtime_before = int(index_path.stat().st_mtime)

    stop_payload = {
        "conversationId": daily_cid,
        "artifactDirectoryPath": str(daily_brain),
        "terminationReason": "NO_TOOL_CALL",
        "fullyIdle": True,
    }
    proc_stop_noop = subprocess.run(
        [*base_cmd, "--hook", "stop"],
        input=json.dumps(stop_payload),
        text=True,
        capture_output=True,
        cwd=hook_cwd,
        check=True,
    )
    assert json.loads(proc_stop_noop.stdout) == {"decision": "stop"}
    assert int(index_path.stat().st_mtime) == mtime_before

    # Malformed JSON stdin never crashes Stop hook and emits valid JSON stdout + exit 0
    proc_bad = subprocess.run(
        [*base_cmd, "--hook", "stop"],
        input="{corrupted json!!!",
        text=True,
        capture_output=True,
        cwd=hook_cwd,
        check=False,
    )
    assert proc_bad.returncode == 0
    assert json.loads(proc_bad.stdout) == {"decision": "stop"}


def test_live_project_archive_populated() -> None:
    assert not (WORKSPACE_ROOT / ".agents" / "chatrooms.json").exists(), ".agents/chatrooms.json retired under Fresh-Room R83 v3"
    assert (DEFAULT_ARCHIVE_DIR / "INDEX.md").exists()

    ceo_dir = DEFAULT_ARCHIVE_DIR / "01_YouTube_CEO"
    for fname in (
        "benchmark_success_formula_report.md",
        "signature_character_comparison_report.md",
        "implementation_plan.md",
        "walkthrough.md",
        "signature_cast/opt1_sheet.jpg",
        "signature_cast/opt1_scene_conflict.jpg",
        "signature_cast/opt1_scene_brain75.jpg",
    ):
        assert (ceo_dir / fname).exists(), f"Missing archived CEO asset: {fname}"

    sig_md = (ceo_dir / "signature_character_comparison_report.md").read_text(encoding="utf-8")
    assert "./signature_cast/opt1_sheet.jpg" in sig_md
    assert "./signature_cast/opt1_scene_conflict.jpg" in sig_md
    assert "./signature_cast/opt1_scene_brain75.jpg" in sig_md
    assert "./scratch/" not in sig_md

    res_dir = DEFAULT_ARCHIVE_DIR / "03_Research"
    for fname in (
        "ricksclips3000_shorts_report.md",
        "heyhistorically_shorts_report.md",
        "psychtoonshq_videos_report.md",
    ):
        assert (res_dir / fname).exists(), f"Missing archived Research report: {fname}"


def test_rewrite_markdown_links_code_fences_carousel_and_special_filenames(tmp_path: Path) -> None:
    ceo_cid = "b57c97a8-6324-4c31-a2bb-16b25e28dd55"
    src_dir = tmp_path / "brain" / ceo_cid
    archive_dir = tmp_path / "artifacts_archive"
    dst_dir = archive_dir / "01_YouTube_CEO"

    tricky_rel_paths = [
        "my folder/chart 1.png",
        "chart_#1.png",
        "chart_?1.png",
        "100%_pass.png",
        "step_1)_chart.png",
        "시그니처 (1).png",
    ]
    for rp in tricky_rel_paths:
        src_f = src_dir / rp
        src_f.parent.mkdir(parents=True, exist_ok=True)
        src_f.write_bytes(b"PNGDATA")
        dst_f = dst_dir / rp
        dst_f.parent.mkdir(parents=True, exist_ok=True)
        dst_f.write_bytes(b"PNGDATA")

    md_input = (
        "# Deep Link Test\n\n"
        "````carousel\n"
        f"![Carousel Real](<{src_dir}/my folder/chart 1.png> \"Slide 1\")\n"
        "````\n\n"
        f"[`CodeLabel`](file://{src_dir}/100%25_pass.png)\n"
        f"![Hash](file://{src_dir}/chart_%231.png)\n"
        f"![Query](file://{src_dir}/chart_%3F1.png)\n"
        f"![UnbalancedParen](file://{src_dir}/step_1%29_chart.png)\n"
        f"![KoreanEncoded](file://{src_dir}/%EC%8B%9C%EA%B7%B8%EB%8B%88%EC%B2%98%20(1).png)\n"
        f"[ref_space]: <{src_dir}/my folder/chart 1.png>\n\n"
        "```markdown\n"
        f"Literal code block must NOT change: ![CodeExample]({src_dir}/chart_#1.png)\n"
        "```\n\n"
        f"Literal inline code must NOT change: `![InlineExample]({src_dir}/chart_#1.png)`\n"
    )

    rewritten = rewrite_markdown_links(
        md_input,
        conv_id=ceo_cid,
        rel_md_path=Path("sub/nested/report.md"),
        dst_chatroom_dir=dst_dir,
        archive_dir=archive_dir,
        src_brain_dirs=[src_dir],
        conv_to_folder={ceo_cid: "01_YouTube_CEO"},
        brain_roots=[tmp_path / "brain"],
    )

    assert '![Carousel Real](../../my%20folder/chart%201.png "Slide 1")' in rewritten
    assert "[`CodeLabel`](../../100%25_pass.png)" in rewritten
    assert "![Hash](../../chart_%231.png)" in rewritten
    assert "![Query](../../chart_%3F1.png)" in rewritten
    assert "![UnbalancedParen](../../step_1%29_chart.png)" in rewritten
    assert "![KoreanEncoded](../../시그니처%20%281%29.png)" in rewritten
    assert "[ref_space]: ../../my%20folder/chart%201.png" in rewritten
    assert f"Literal code block must NOT change: ![CodeExample]({src_dir}/chart_#1.png)" in rewritten
    assert f"Literal inline code must NOT change: `![InlineExample]({src_dir}/chart_#1.png)`" in rewritten

    nested_md_dir = dst_dir / "sub" / "nested"
    nested_md_dir.mkdir(parents=True, exist_ok=True)
    for encoded_rel in (
        "../../my%20folder/chart%201.png",
        "../../100%25_pass.png",
        "../../chart_%231.png",
        "../../chart_%3F1.png",
        "../../step_1%29_chart.png",
        "../../시그니처%20%281%29.png",
    ):
        decoded = urllib.parse.unquote(encoded_rel)
        assert (nested_md_dir / decoded).is_file(), f"Decoded link did not resolve: {encoded_rel}"


def test_subsecond_same_size_edit_and_heading_table_safety(tmp_path: Path) -> None:
    brain_root = tmp_path / "brain"
    archive_dir = tmp_path / "artifacts_archive"
    ceo_cid = "b57c97a8-6324-4c31-a2bb-16b25e28dd55"
    ceo_src = brain_root / ceo_cid
    ceo_src.mkdir(parents=True)

    long_heading = "A" * 84 + " `porcelain_cinematic_v7` Gate"
    md_file = ceo_src / "status_report.md"
    md_file.write_text(
        "---\n# yaml frontmatter comment\ntitle: test\n---\n"
        "```bash\n# shell comment\n```\n"
        f"# {long_heading}\n\nResult: PASS (71.3%)\n",
        encoding="utf-8",
    )
    os.utime(md_file, (1_700_000_000.100, 1_700_000_000.100))

    r1 = sync_conversation(ceo_cid, archive_dir=archive_dir, brain_roots=[brain_root])
    assert r1.copied == 1

    md_file.write_text(
        "---\n# yaml frontmatter comment\ntitle: test\n---\n"
        "```bash\n# shell comment\n```\n"
        f"# {long_heading}\n\nResult: FAIL (12.9%)\n",
        encoding="utf-8",
    )
    os.utime(md_file, (1_700_000_000.500, 1_700_000_000.500))

    r2 = sync_conversation(ceo_cid, archive_dir=archive_dir, brain_roots=[brain_root])
    assert r2.copied == 1
    assert "Result: FAIL (12.9%)" in (archive_dir / "01_YouTube_CEO" / "status_report.md").read_text(encoding="utf-8")

    os.utime(archive_dir / "01_YouTube_CEO" / "status_report.md", (1_700_000_000.500, 1_700_000_000.500))
    os.utime(md_file, (1_700_000_000.5004, 1_700_000_000.5004))
    r3 = sync_conversation(ceo_cid, archive_dir=archive_dir, brain_roots=[brain_root])
    assert r3.copied == 0 and r3.skipped == 1

    idx_path = generate_index_md(archive_dir=archive_dir, brain_roots=[brain_root])
    idx_txt = idx_path.read_text(encoding="utf-8")
    assert "yaml frontmatter comment" not in idx_txt
    assert "shell comment" not in idx_txt
    row_lines = [ln for ln in idx_txt.splitlines() if "status_report.md" in ln]
    assert len(row_lines) == 1
    assert row_lines[0].count("`") % 2 == 0


def test_subagent_db_lineage_concurrent_stop_hooks_and_non_youtube_fast_noop(tmp_path: Path) -> None:
    brain_root = tmp_path / "brain"
    archive_dir = tmp_path / "artifacts_archive"
    parent_ws = str(WORKSPACE_ROOT.parent)

    db_path = tmp_path / "conversation_summaries.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE conversation_summaries (
            conversation_id TEXT PRIMARY KEY,
            title TEXT,
            nesting_depth INTEGER,
            workspace_uris TEXT,
            project_id TEXT,
            parent_conversation_id TEXT
        )
        """
    )

    hq_cid = "8c7f8d97-664d-4d6b-9ef8-b17e721354f9"
    unlisted_ws_cid = "unlisted01-1111-2222-3333-444444444444"
    unlisted_proj_cid = "unlisted02-1111-2222-3333-444444444444"
    sub_lvl1_cid = "sublevel01-1111-2222-3333-444444444444"
    sub_lvl2_cid = "sublevel02-1111-2222-3333-444444444444"
    ucl_cid = "uclconv01-0000-0000-0000-000000000001"
    intern_cid = "intern001-0000-0000-0000-000000000002"
    outside_cid = "outside01-0000-0000-0000-000000000003"
    prefix_collision_cid = "prefix001-0000-0000-0000-000000000005"

    conn.executemany(
        "INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?)",
        [
            (hq_cid, "Headquarters", 0, f'["file://{WORKSPACE_ROOT}"]', YOUTUBE_PROJECT_ID, ""),
            (unlisted_ws_cid, "Adhoc YT WS", 0, f'["file://{WORKSPACE_ROOT}/03_visuals"]', "", ""),
            (unlisted_proj_cid, "Adhoc YT Proj", 0, "[]", YOUTUBE_PROJECT_ID, ""),
            (sub_lvl1_cid, "HQ Sub 1", 1, f'["file://{parent_ws}"]', "", hq_cid),
            (sub_lvl2_cid, "HQ Sub 2", 2, f'["file://{parent_ws}"]', "", sub_lvl1_cid),
            (ucl_cid, "UCL", 0, f'["file://{parent_ws}/02_UCL"]', "ucl-proj", ""),
            (intern_cid, "Intern", 0, f'["file://{parent_ws}/04_Internship"]', "intern-proj", ""),
            (outside_cid, "Outside", 0, "", "", ""),
            (prefix_collision_cid, "Backup", 0, f'["file://{WORKSPACE_ROOT}_Backup"]', "backup-proj", ""),
        ],
    )
    conn.commit()
    conn.close()

    discovered = set(_discover_unlisted_07_youtube_convs(db_path, {hq_cid}))
    assert discovered == {unlisted_ws_cid, unlisted_proj_cid}

    # Foreign workspaces must never touch artifacts_archive/ and must run in <15ms
    for cid, ws_paths in (
        (ucl_cid, [f"{parent_ws}/02_UCL"]),
        (intern_cid, [f"{parent_ws}/04_Internship"]),
        (outside_cid, None),
        (prefix_collision_cid, [f"{WORKSPACE_ROOT}_Backup"]),
    ):
        bdir = brain_root / cid
        bdir.mkdir(parents=True, exist_ok=True)
        (bdir / "implementation_plan.md").write_text("# Non-YouTube Plan\n", encoding="utf-8")
        stop_payload: dict[str, object] = {
            "conversationId": cid,
            "artifactDirectoryPath": str(bdir),
            "terminationReason": "NO_TOOL_CALL",
        }
        if ws_paths is not None:
            stop_payload["workspacePaths"] = ws_paths
        assert handle_stop_payload(
            stop_payload, archive_dir=archive_dir, brain_roots=[brain_root], db_path=db_path
        ) == {"decision": "stop"}
    assert not archive_dir.exists()

    intern_stop = {
        "conversationId": intern_cid,
        "workspacePaths": [f"{parent_ws}/04_Internship"],
        "artifactDirectoryPath": str(brain_root / intern_cid),
        "terminationReason": "NO_TOOL_CALL",
    }
    handle_stop_payload(intern_stop, archive_dir=archive_dir, brain_roots=[brain_root], db_path=db_path)
    stop_times_ms: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        handle_stop_payload(intern_stop, archive_dir=archive_dir, brain_roots=[brain_root], db_path=db_path)
        stop_times_ms.append((time.perf_counter() - t0) * 1000.0)
    stop_times_ms.sort()
    assert stop_times_ms[2] < 15.0

    # Depth-2 subagent Stop hook walks DB lineage up to HQ without archiving ephemeral subagent dir
    sub2_dir = brain_root / sub_lvl2_cid
    sub2_dir.mkdir(parents=True, exist_ok=True)
    (sub2_dir / "subagent_scratch.md").write_text("# Ephemeral\n", encoding="utf-8")
    hq_dir = brain_root / hq_cid
    hq_dir.mkdir(parents=True, exist_ok=True)
    (hq_dir / "script_generated_chart.png").write_bytes(b"\x89PNG\r\n\x1a\nHQCHART")

    stop_resp = handle_stop_payload(
        {
            "conversationId": sub_lvl2_cid,
            "workspacePaths": [parent_ws],
            "artifactDirectoryPath": str(sub2_dir),
            "terminationReason": "NO_TOOL_CALL",
        },
        archive_dir=archive_dir,
        brain_roots=[brain_root],
        db_path=db_path,
    )
    assert stop_resp == {"decision": "stop"}
    assert not (archive_dir / f"conv_{sub_lvl2_cid[:8]}").exists()
    assert not (archive_dir / f"conv_{sub_lvl1_cid[:8]}").exists()
    assert (archive_dir / "08_Headquarters" / "script_generated_chart.png").exists()


def test_live_all_youtube_chatrooms_retroactively_archived() -> None:
    assert (DEFAULT_ARCHIVE_DIR / "INDEX.md").is_file()
    for cid, canonical_folder in HISTORICAL_CONV_FOLDER_MAP.items():
        resolved_folder = resolve_archive_folder(cid, archive_dir=DEFAULT_ARCHIVE_DIR)
        assert resolved_folder.endswith("_" + canonical_folder.split("_", 1)[-1])


def test_sync_conversation_and_sync_all_dedup_canonical_folders_without_registry(tmp_path: Path) -> None:
    archive_dir = tmp_path / "artifacts_archive"
    (archive_dir / "04_Daily_Report").mkdir(parents=True)
    (archive_dir / "05_QA_Scheduler").mkdir(parents=True)
    (archive_dir / "06_Topic_Radar").mkdir(parents=True)

    brain_root = tmp_path / "brain"
    daily_cid = "e3210c73-cc41-4432-87b1-c158efe9cadb"
    sched_cid = "ef8185bb-5afd-4859-b697-2fe07f1ecf1c"
    radar_cid = "0ffee83a-d9de-4520-a177-7d3b57dc01dc"
    for cid, fname in ((daily_cid, "daily.md"), (sched_cid, "sched.md"), (radar_cid, "radar.md")):
        (brain_root / cid).mkdir(parents=True)
        (brain_root / cid / fname).write_text(f"# {fname}\n", encoding="utf-8")

    res_daily = sync_conversation(daily_cid, archive_dir=archive_dir, brain_roots=[brain_root])
    assert res_daily.folder_name == "04_Daily_Report"
    assert not (archive_dir / "05_Daily_Report").exists()
    assert (archive_dir / "04_Daily_Report" / "daily.md").is_file()

    all_res = sync_all(
        archive_dir=archive_dir,
        brain_roots=[brain_root],
        extra_conv_ids=[daily_cid, sched_cid, radar_cid],
    )
    by_cid = {r.conv_id: r.folder_name for r in all_res}
    assert by_cid[daily_cid] == "04_Daily_Report"
    assert by_cid[sched_cid] == "05_QA_Scheduler"
    assert by_cid[radar_cid] == "06_Topic_Radar"
    assert not (archive_dir / "05_Daily_Report").exists()
    assert not (archive_dir / "06_QA_Scheduler").exists()
    assert not (archive_dir / "07_Topic_Radar").exists()
