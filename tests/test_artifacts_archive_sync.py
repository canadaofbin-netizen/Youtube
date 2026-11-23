"""Comprehensive tests for `scripts/sync_artifacts_archive.py` and `.agents/hooks.json`."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.parse

import pytest

from scripts.sync_artifacts_archive import (
    DEFAULT_ARCHIVE_DIR,
    DEFAULT_BRAIN_ROOTS,
    DEFAULT_DB_PATH,
    DEFAULT_GLOBAL_HOOKS_PATH,
    DEFAULT_REGISTRY_PATH,
    GLOBAL_HOOK_NAME,
    WORKSPACE_ROOT,
    YOUTUBE_PROJECT_ID,
    _collect_source_files,
    _discover_unlisted_07_youtube_convs,
    ensure_global_hooks_json,
    generate_index_md,
    handle_post_tool_use_payload,
    handle_stop_payload,
    load_chatroom_map,
    resolve_archive_folder,
    rewrite_markdown_links,
    sync_all,
    sync_conversation,
)

SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "sync_artifacts_archive.py"
HOOKS_JSON_PATH = WORKSPACE_ROOT / ".agents" / "hooks.json"
AGENTS_MD_PATH = WORKSPACE_ROOT / ".agents" / "AGENTS.md"


def _make_sample_registry(path: Path) -> Path:
    data = {
        "schema_version": 1,
        "workspace": str(WORKSPACE_ROOT),
        "chatrooms": [
            {
                "handle": "@YouTube_CEO",
                "conversation_id": "b57c97a8-6324-4c31-a2bb-16b25e28dd55",
                "title": "YouTube_CEO",
                "role": "Executive orchestrator",
                "active": True,
            },
            {
                "handle": "@Research",
                "conversation_id": "ffbdfca1-9c07-48b3-9b1e-3e3045d67c0c",
                "title": "Research",
                "role": "Competitor teardown",
                "active": True,
            },
            {
                "handle": "@Daily_Report",
                "conversation_id": "e3210c73-cc41-4432-87b1-c158efe9cadb",
                "title": "Daily Report",
                "role": "Daily Studio KPI report",
                "active": True,
            },
            {
                "handle": "@Headquarters",
                "conversation_id": "8c7f8d97-664d-4d6b-9ef8-b17e721354f9",
                "title": "Headquarters",
                "role": "Pipeline engineering",
                "active": True,
            },
            {
                "handle": "@Channel_Art",
                "conversation_id": "3c2fa53b-b43c-4f67-9dfd-0e5c86581f67",
                "title": "Channel Art",
                "role": "Branding",
                "active": True,
            },
            {
                "handle": "@Empty_Archived",
                "conversation_id": "00000000-1111-2222-3333-444444444444",
                "title": "Empty Archived",
                "role": "Archive",
                "active": False,
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def test_hooks_json_and_workspace_configs_valid() -> None:
    assert HOOKS_JSON_PATH.exists(), ".agents/hooks.json must exist"
    hooks_cfg = json.loads(HOOKS_JSON_PATH.read_text(encoding="utf-8"))
    assert "artifact-auto-archive" in hooks_cfg
    entry = hooks_cfg["artifact-auto-archive"]

    post_groups = entry["PostToolUse"]
    assert isinstance(post_groups, list) and len(post_groups) == 1
    matcher = post_groups[0]["matcher"]
    for required_tool in ("write_file", "edit_file", "write_to_file", "replace_file_content", "generate_image"):
        assert required_tool in matcher
    post_cmd = post_groups[0]["hooks"][0]
    assert post_cmd["type"] == "command"
    assert post_cmd["timeout"] == 20
    assert str(SCRIPT_PATH) in post_cmd["command"]
    assert "--hook post-tool-use" in post_cmd["command"]

    stop_list = entry["Stop"]
    assert isinstance(stop_list, list) and len(stop_list) == 1
    assert stop_list[0]["type"] == "command"
    assert stop_list[0]["timeout"] == 20
    assert str(SCRIPT_PATH) in stop_list[0]["command"]
    assert "--hook stop" in stop_list[0]["command"]

    agents_bytes = AGENTS_MD_PATH.read_bytes()
    assert 3_000 <= len(agents_bytes) <= 6_500, "AGENTS.md must stay compact (3-6.5 KB)"
    storage_rules_txt = (WORKSPACE_ROOT / ".agents" / "rules" / "project_storage_rules.md").read_text(encoding="utf-8")
    assert "artifacts_archive/" in storage_rules_txt
    assert "sync_artifacts_archive.py" in storage_rules_txt

    for ignore_name in (".rgignore", ".ignore"):
        ignore_txt = (WORKSPACE_ROOT / ignore_name).read_text(encoding="utf-8")
        assert "artifacts_archive/" in ignore_txt


def test_sync_all_exclusions_relative_rewriting_and_incremental_skip(tmp_path: Path) -> None:
    reg_path = _make_sample_registry(tmp_path / ".agents" / "chatrooms.json")
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

    # 1st run: copies everything
    results_1 = sync_all(
        archive_dir=archive_dir,
        registry_path=reg_path,
        brain_roots=[brain_root],
        extra_conv_ids=[unlisted_cid],
    )
    assert sum(r.copied for r in results_1) == 4  # report.md + opt1_sheet.jpg + ricksclips + adhoc.md

    # Verify active rooms exist (even 05_Channel_Art with 0 files), while empty inactive room does NOT exist
    assert (archive_dir / "01_YouTube_CEO" / "report.md").exists()
    assert (archive_dir / "01_YouTube_CEO" / "signature_cast" / "opt1_sheet.jpg").exists()
    assert (archive_dir / "02_Research" / "ricksclips3000_shorts_report.md").exists()
    assert (archive_dir / "05_Channel_Art").is_dir()
    assert not (archive_dir / "06_Empty_Archived").exists()
    assert (archive_dir / "conv_deadbeef" / "adhoc.md").exists()

    # Verify excluded items were NOT copied
    assert not (archive_dir / "01_YouTube_CEO" / ".system_generated").exists()
    assert not (archive_dir / "01_YouTube_CEO" / "scratch").exists()
    assert not (archive_dir / "01_YouTube_CEO" / "report.md.metadata.json").exists()
    assert not (archive_dir / "01_YouTube_CEO" / "report.md.resolved.0").exists()
    assert not (archive_dir / "01_YouTube_CEO" / ".hidden_note.md").exists()

    # Verify link rewriting in archived copy AND zero mutation of source file
    assert (ceo_src / "report.md").read_text(encoding="utf-8") == original_md
    archived_md = (archive_dir / "01_YouTube_CEO" / "report.md").read_text(encoding="utf-8")
    assert "![Option 1](./signature_cast/opt1_sheet.jpg)" in archived_md
    assert "[Self Plan](./report.md#section-2)" in archived_md
    assert "[Cross Research](../02_Research/ricksclips3000_shorts_report.md)" in archived_md
    assert '<img src="./signature_cast/opt1_sheet.jpg" width="320">' in archived_md
    assert "file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py" in archived_md
    assert "e07a753a-0000-0000-0000-000000000000/gone.md" in archived_md

    # Verify INDEX.md lists reports with relative links
    index_txt = (archive_dir / "INDEX.md").read_text(encoding="utf-8")
    assert "./01_YouTube_CEO/report.md" in index_txt
    assert "./02_Research/ricksclips3000_shorts_report.md" in index_txt
    assert "./conv_deadbeef/adhoc.md" in index_txt

    # 2nd run: incremental skip must copy 0 files even though archived_md byte length != original_md byte length!
    results_2 = sync_all(
        archive_dir=archive_dir,
        registry_path=reg_path,
        brain_roots=[brain_root],
        extra_conv_ids=[unlisted_cid],
    )
    assert sum(r.copied for r in results_2) == 0
    assert sum(r.skipped for r in results_2) == 4

    # Modify 1 source file with newer mtime -> only that 1 file re-copies
    updated_md = original_md + "\nUpdated conclusion.\n"
    (ceo_src / "report.md").write_text(updated_md, encoding="utf-8")
    st = (ceo_src / "report.md").stat()
    os.utime(ceo_src / "report.md", (st.st_atime, st.st_mtime + 5))

    results_3 = sync_all(
        archive_dir=archive_dir,
        registry_path=reg_path,
        brain_roots=[brain_root],
        extra_conv_ids=[unlisted_cid],
    )
    assert sum(r.copied for r in results_3) == 1
    assert "Updated conclusion." in (archive_dir / "01_YouTube_CEO" / "report.md").read_text(encoding="utf-8")


def test_post_tool_use_and_stop_hooks_subprocess_and_edge_cases(tmp_path: Path) -> None:
    reg_path = _make_sample_registry(tmp_path / ".agents" / "chatrooms.json")
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
        "--registry",
        str(reg_path),
        "--brain-root",
        str(brain_root),
    ]
    hook_cwd = WORKSPACE_ROOT / ".agents"  # Exact working directory Antigravity uses for hooks.json

    # 1. Fast exit on non-artifact workspace file write
    non_art_payload = {
        "conversationId": daily_cid,
        "artifactDirectoryPath": str(daily_brain),
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": str(tmp_path / "workspace" / "foo.py")},
        },
    }
    proc = subprocess.run(
        [*base_cmd, "--hook", "post-tool-use"],
        input=json.dumps(non_art_payload),
        text=True,
        capture_output=True,
        cwd=hook_cwd,
        check=True,
    )
    assert json.loads(proc.stdout) == {}
    assert not archive_dir.exists()

    # 2. Fast exit on `.system_generated/` and tool `"error"`
    (daily_brain / ".system_generated").mkdir(parents=True)
    (daily_brain / ".system_generated" / "step.txt").write_text("x", encoding="utf-8")
    for bad_payload in (
        {
            "conversationId": daily_cid,
            "artifactDirectoryPath": str(daily_brain),
            "toolCall": {"name": "write_file", "args": {"Path": str(daily_brain / ".system_generated" / "step.txt")}},
        },
        {
            "conversationId": daily_cid,
            "artifactDirectoryPath": str(daily_brain),
            "error": "exit status 1",
            "toolCall": {"name": "write_file", "args": {"Path": str(daily_brain / "report.md")}},
        },
    ):
        resp = handle_post_tool_use_payload(
            bad_payload, archive_dir=archive_dir, registry_path=reg_path, brain_roots=[brain_root]
        )
        assert resp == {}
        assert not archive_dir.exists()

    # 3. Real artifact write via PostToolUse (`TargetFile` from `write_to_file`)
    report_src = daily_brain / "youtube_daily_report_2026_11_05.md"
    chart_src = daily_brain / "2026-11-05_studio_charts.png"
    chart_src.write_bytes(b"\x89PNG\r\n\x1a\nFAKEPNG")
    report_src.write_text(
        f"# Daily Report\n![Chart]({chart_src})\n",
        encoding="utf-8",
    )
    art_payload = {
        "conversationId": daily_cid,
        "artifactDirectoryPath": str(daily_brain),
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": str(report_src)},
        },
    }
    proc_sync = subprocess.run(
        [*base_cmd, "--hook", "post-tool-use"],
        input=json.dumps(art_payload),
        text=True,
        capture_output=True,
        cwd=hook_cwd,
        check=True,
    )
    assert json.loads(proc_sync.stdout) == {}
    archived_report = archive_dir / "03_Daily_Report" / "youtube_daily_report_2026_11_05.md"
    assert archived_report.exists()
    assert "![Chart](./2026-11-05_studio_charts.png)" in archived_report.read_text(encoding="utf-8")
    assert (archive_dir / "03_Daily_Report" / "2026-11-05_studio_charts.png").exists()
    assert (archive_dir / "INDEX.md").exists()

    # 4. Stop hook when 0 files changed -> returns {"decision": "stop"} and does NOT rewrite INDEX.md
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
    assert int(index_path.stat().st_mtime) == mtime_before, "No-op Stop hook must not rewrite INDEX.md"

    # 5. Stop hook catches new chart generated by script during turn -> syncs and updates INDEX.md
    extra_chart = daily_brain / "2026-11-05_sec1_channel_growth.png"
    extra_chart.write_bytes(b"\x89PNG\r\n\x1a\nSEC1")
    resp_stop_new = handle_stop_payload(
        stop_payload, archive_dir=archive_dir, registry_path=reg_path, brain_roots=[brain_root]
    )
    assert resp_stop_new == {"decision": "stop"}
    assert (archive_dir / "03_Daily_Report" / "2026-11-05_sec1_channel_growth.png").exists()
    assert int(index_path.stat().st_mtime) > mtime_before

    # 6. Malformed JSON stdin never crashes hooks and still emits valid JSON stdout + exit 0
    for mode, expected in (("post-tool-use", {}), ("stop", {"decision": "stop"})):
        proc_bad = subprocess.run(
            [*base_cmd, "--hook", mode],
            input="{corrupted json!!!",
            text=True,
            capture_output=True,
            cwd=hook_cwd,
            check=False,
        )
        assert proc_bad.returncode == 0
        assert json.loads(proc_bad.stdout) == expected


def test_live_project_archive_populated() -> None:
    assert DEFAULT_REGISTRY_PATH.exists()
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
    assert "/signature_cast/" in sig_md and "brain/b57c97a8-6324-4c31-a2bb-16b25e28dd55/signature_cast/" not in sig_md
    assert "./scratch/" not in sig_md, "Excluded scratch/ links must not be rewritten into broken relative links"

    bench_md = (ceo_dir / "benchmark_success_formula_report.md").read_text(encoding="utf-8")
    assert "./benchmark_media/012_jar_31M.jpg" in bench_md
    assert "../03_Research/ricksclips3000_shorts_report.md" in bench_md or "../02_Research/ricksclips3000_shorts_report.md" in bench_md
    assert "/.gemini/" not in bench_md

    res_dir = DEFAULT_ARCHIVE_DIR / "03_Research"
    for fname in (
        "ricksclips3000_shorts_report.md",
        "heyhistorically_shorts_report.md",
        "psychtoonshq_videos_report.md",
    ):
        assert (res_dir / fname).exists(), f"Missing archived Research report: {fname}"
        txt = (res_dir / fname).read_text(encoding="utf-8")
        assert "./" in txt and "/.gemini/" not in txt

    for folder in ("02_Operator", "03_Research", "04_Daily_Report", "05_QA_Scheduler", "06_Topic_Radar"):
        assert (DEFAULT_ARCHIVE_DIR / folder).is_dir()


def test_rewrite_markdown_links_code_fences_carousel_and_special_filenames(tmp_path: Path) -> None:
    ceo_cid = "b57c97a8-6324-4c31-a2bb-16b25e28dd55"
    src_dir = tmp_path / "brain" / ceo_cid
    archive_dir = tmp_path / "artifacts_archive"
    dst_dir = archive_dir / "01_YouTube_CEO"

    # Create tricky files inside nested directories and verify every rewritten relative URL resolves on disk
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

    # Carousel & code-labeled links MUST rewrite cleanly
    assert '![Carousel Real](../../my%20folder/chart%201.png "Slide 1")' in rewritten
    assert "[`CodeLabel`](../../100%25_pass.png)" in rewritten
    assert "![Hash](../../chart_%231.png)" in rewritten
    assert "![Query](../../chart_%3F1.png)" in rewritten
    assert "![UnbalancedParen](../../step_1%29_chart.png)" in rewritten
    assert "![KoreanEncoded](../../시그니처%20%281%29.png)" in rewritten
    assert "[ref_space]: ../../my%20folder/chart%201.png" in rewritten

    # Fenced code block & inline code span MUST remain untouched
    assert f"Literal code block must NOT change: ![CodeExample]({src_dir}/chart_#1.png)" in rewritten
    assert f"Literal inline code must NOT change: `![InlineExample]({src_dir}/chart_#1.png)`" in rewritten

    # Verify every rewritten relative target resolves back to the actual archived file on disk
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
    reg_path = _make_sample_registry(tmp_path / ".agents" / "chatrooms.json")
    brain_root = tmp_path / "brain"
    archive_dir = tmp_path / "artifacts_archive"
    ceo_cid = "b57c97a8-6324-4c31-a2bb-16b25e28dd55"
    ceo_src = brain_root / ceo_cid
    ceo_src.mkdir(parents=True)

    # Frontmatter `# comment` + code block `# comment` + >90 char heading slicing inside `backtick`
    long_heading = "A" * 84 + " `porcelain_cinematic_v7` Gate"
    md_file = ceo_src / "status_report.md"
    md_file.write_text(
        "---\n# yaml frontmatter comment\ntitle: test\n---\n"
        "```bash\n# shell comment\n```\n"
        f"# {long_heading}\n\nResult: PASS (71.3%)\n",
        encoding="utf-8",
    )
    os.utime(md_file, (1_700_000_000.100, 1_700_000_000.100))

    r1 = sync_conversation(ceo_cid, archive_dir=archive_dir, registry_path=reg_path, brain_roots=[brain_root])
    assert r1.copied == 1

    # Same-second (+400 ms) edit with identical byte length must NOT be skipped!
    md_file.write_text(
        "---\n# yaml frontmatter comment\ntitle: test\n---\n"
        "```bash\n# shell comment\n```\n"
        f"# {long_heading}\n\nResult: FAIL (12.9%)\n",
        encoding="utf-8",
    )
    os.utime(md_file, (1_700_000_000.500, 1_700_000_000.500))

    r2 = sync_conversation(ceo_cid, archive_dir=archive_dir, registry_path=reg_path, brain_roots=[brain_root])
    assert r2.copied == 1
    assert "Result: FAIL (12.9%)" in (archive_dir / "01_YouTube_CEO" / "status_report.md").read_text(encoding="utf-8")

    # Sub-millisecond quantization difference (<2ms, as on fuse.rclone) must skip cleanly
    os.utime(archive_dir / "01_YouTube_CEO" / "status_report.md", (1_700_000_000.500, 1_700_000_000.500))
    os.utime(md_file, (1_700_000_000.5004, 1_700_000_000.5004))
    r3 = sync_conversation(ceo_cid, archive_dir=archive_dir, registry_path=reg_path, brain_roots=[brain_root])
    assert r3.copied == 0 and r3.skipped == 1

    # INDEX.md must ignore YAML/bash comments and balance truncated backticks so table pipes stay intact
    idx_path = generate_index_md(archive_dir=archive_dir, registry_path=reg_path, brain_roots=[brain_root])
    idx_txt = idx_path.read_text(encoding="utf-8")
    assert "yaml frontmatter comment" not in idx_txt
    assert "shell comment" not in idx_txt
    row_lines = [ln for ln in idx_txt.splitlines() if "status_report.md" in ln]
    assert len(row_lines) == 1
    assert row_lines[0].count("`") % 2 == 0, f"Unclosed backtick in INDEX.md row: {row_lines[0]}"


def test_nested_code_action_workspace_isolation_subagent_filter_and_concurrent_hooks(tmp_path: Path) -> None:
    reg_path = _make_sample_registry(tmp_path / ".agents" / "chatrooms.json")
    brain_root = tmp_path / "brain"
    archive_dir = tmp_path / "artifacts_archive"

    # Build sample SQLite DB marking subagent nesting_depth=1 and foreign workspace depth=0
    db_path = tmp_path / "conversation_summaries.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE conversation_summaries (conversation_id TEXT PRIMARY KEY, nesting_depth INTEGER, workspace_uris TEXT)"
    )
    subagent_cid = "subagent12-0000-0000-0000-000000000001"
    foreign_cid = "foreign12-0000-0000-0000-000000000002"
    conn.execute(
        "INSERT INTO conversation_summaries VALUES (?, ?, ?)",
        (subagent_cid, 1, f'["file://{WORKSPACE_ROOT}"]'),
    )
    conn.execute(
        "INSERT INTO conversation_summaries VALUES (?, ?, ?)",
        (foreign_cid, 0, '["file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/04_Internship"]'),
    )
    conn.commit()
    conn.close()

    # 1. Subagent writing temporary note in its OWN brain dir must NOT pollute `conv_subagent/`
    sub_brain = brain_root / subagent_cid
    sub_brain.mkdir(parents=True)
    (sub_brain / "task.md").write_text("# Ephemeral Subagent Note\n", encoding="utf-8")

    ceo_cid = "b57c97a8-6324-4c31-a2bb-16b25e28dd55"
    ceo_brain = brain_root / ceo_cid
    ceo_brain.mkdir(parents=True)
    (ceo_brain / "parent_report.md").write_text("# Parent CEO Report\n", encoding="utf-8")

    handle_post_tool_use_payload(
        {
            "conversationId": subagent_cid,
            "parentConversationId": ceo_cid,
            "artifactDirectoryPath": str(sub_brain),
            "toolCall": {"name": "write_to_file", "args": {"TargetFile": str(sub_brain / "task.md")}},
        },
        archive_dir=archive_dir,
        registry_path=reg_path,
        brain_roots=[brain_root],
        db_path=db_path,
    )
    assert not (archive_dir / "conv_subagent").exists()

    # Stop hook on subagent skips subagent self-dir (`conv_subagent`) while syncing parent chatroom (`01_YouTube_CEO`)!
    handle_stop_payload(
        {
            "conversationId": subagent_cid,
            "parentConversationId": ceo_cid,
            "artifactDirectoryPath": str(sub_brain),
            "terminationReason": "NO_TOOL_CALL",
        },
        archive_dir=archive_dir,
        registry_path=reg_path,
        brain_roots=[brain_root],
        db_path=db_path,
    )
    assert not (archive_dir / "conv_subagent").exists()
    assert (archive_dir / "01_YouTube_CEO" / "parent_report.md").exists()

    # 2. Foreign workspace unlisted conversation must NOT leak into 07_Youtube/artifacts_archive
    foreign_brain = brain_root / foreign_cid
    foreign_brain.mkdir(parents=True)
    (foreign_brain / "resume.md").write_text("# Internship Note\n", encoding="utf-8")
    handle_post_tool_use_payload(
        {
            "conversationId": foreign_cid,
            "workspacePaths": ["/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/04_Internship"],
            "artifactDirectoryPath": str(foreign_brain),
            "toolCall": {"name": "write_to_file", "args": {"TargetFile": str(foreign_brain / "resume.md")}},
        },
        archive_dir=archive_dir,
        registry_path=reg_path,
        brain_roots=[brain_root],
        db_path=db_path,
    )
    assert not (archive_dir / "conv_foreign1").exists()

    # 3. Nested `code_action` protobuf JSON (`actionSpec.createFile.path.absoluteUri`) syncs cleanly
    res_cid = "ffbdfca1-9c07-48b3-9b1e-3e3045d67c0c"
    res_brain = brain_root / res_cid
    res_brain.mkdir(parents=True)
    nested_md = res_brain / "nested_proto_report.md"
    nested_md.write_text("# Proto CodeAction Report\n", encoding="utf-8")
    handle_post_tool_use_payload(
        {
            "conversationId": res_cid,
            "artifactDirectoryPath": str(res_brain),
            "toolCall": {
                "name": "code_action",
                "args": {
                    "actionSpec": {
                        "createFile": {"path": {"absoluteUri": f"file://{nested_md}"}},
                    }
                },
            },
        },
        archive_dir=archive_dir,
        registry_path=reg_path,
        brain_roots=[brain_root],
        db_path=db_path,
    )
    assert (archive_dir / "02_Research" / "nested_proto_report.md").exists()

    # Idempotent PostToolUse (`copied == 0`) must NOT rewrite INDEX.md
    idx_path = archive_dir / "INDEX.md"
    os.utime(idx_path, (1_700_000_000, 1_700_000_000))
    handle_post_tool_use_payload(
        {
            "conversationId": res_cid,
            "artifactDirectoryPath": str(res_brain),
            "toolCall": {"name": "write_to_file", "args": {"TargetFile": str(nested_md)}},
        },
        archive_dir=archive_dir,
        registry_path=reg_path,
        brain_roots=[brain_root],
        db_path=db_path,
    )
    assert int(idx_path.stat().st_mtime) == 1_700_000_000

    # 4. Concurrent multi-process PostToolUse hooks firing simultaneously across 4 chatrooms
    parallel_rooms = [
        ("b57c97a8-6324-4c31-a2bb-16b25e28dd55", "01_YouTube_CEO", "parallel_ceo.md"),
        ("ffbdfca1-9c07-48b3-9b1e-3e3045d67c0c", "02_Research", "parallel_res.md"),
        ("e3210c73-cc41-4432-87b1-c158efe9cadb", "03_Daily_Report", "parallel_daily.md"),
        ("8c7f8d97-664d-4d6b-9ef8-b17e721354f9", "04_Headquarters", "parallel_hq.md"),
    ]
    procs: list[tuple[subprocess.Popen[str], str]] = []
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(SCRIPT_PATH),
        "--archive-dir",
        str(archive_dir),
        "--registry",
        str(reg_path),
        "--brain-root",
        str(brain_root),
        "--hook",
        "post-tool-use",
    ]
    for cid, _, fname in parallel_rooms:
        cdir = brain_root / cid
        cdir.mkdir(parents=True, exist_ok=True)
        fpath = cdir / fname
        fpath.write_text(f"# Concurrent {fname}\n", encoding="utf-8")
        payload_json = json.dumps(
            {
                "conversationId": cid,
                "artifactDirectoryPath": str(cdir),
                "toolCall": {"name": "write_to_file", "args": {"TargetFile": str(fpath)}},
            }
        )
        p = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=WORKSPACE_ROOT / ".agents",
        )
        procs.append((p, payload_json))

    for p, payload_json in procs:
        out, err = p.communicate(input=payload_json, timeout=15)
        assert p.returncode == 0, f"Hook failed: {err}"
        assert json.loads(out) == {}

    final_index = (archive_dir / "INDEX.md").read_text(encoding="utf-8")
    for _, folder, fname in parallel_rooms:
        assert (archive_dir / folder / fname).exists()
        assert f"./{folder}/{fname}" in final_index


def test_global_hooks_json_installation_preservation_and_live_config(tmp_path: Path) -> None:
    # 1. Verify live ~/.gemini/config/hooks.json is installed and mirrors .agents/hooks.json spec
    assert DEFAULT_GLOBAL_HOOKS_PATH.exists(), "~/.gemini/config/hooks.json must exist"
    live_global = json.loads(DEFAULT_GLOBAL_HOOKS_PATH.read_text(encoding="utf-8-sig"))
    assert GLOBAL_HOOK_NAME in live_global
    live_entry = live_global[GLOBAL_HOOK_NAME]
    ws_entry = json.loads(HOOKS_JSON_PATH.read_text(encoding="utf-8"))["artifact-auto-archive"]
    assert live_entry == ws_entry

    # 2. Fresh install + idempotency
    fresh_hooks = tmp_path / "fresh" / "hooks.json"
    assert ensure_global_hooks_json(fresh_hooks) is True
    assert ensure_global_hooks_json(fresh_hooks) is False
    assert json.loads(fresh_hooks.read_text(encoding="utf-8"))[GLOBAL_HOOK_NAME] == ws_entry

    # 3. Preserves pre-existing hooks (even with UTF-8 BOM) without mutating unrelated entries
    existing_hooks = tmp_path / "existing" / "hooks.json"
    existing_hooks.parent.mkdir(parents=True)
    custom_spec = {
        "ucl-custom-hook": {
            "Stop": [{"type": "command", "command": "echo ucl-done", "timeout": 5}],
        }
    }
    existing_hooks.write_bytes(b"\xef\xbb\xbf" + json.dumps(custom_spec, indent=2).encode("utf-8"))
    assert ensure_global_hooks_json(existing_hooks) is True
    merged = json.loads(existing_hooks.read_text(encoding="utf-8"))
    assert merged["ucl-custom-hook"] == custom_spec["ucl-custom-hook"]
    assert merged[GLOBAL_HOOK_NAME] == ws_entry

    # 4. Refuses to clobber non-object JSON
    bad_hooks = tmp_path / "bad_hooks.json"
    bad_hooks.write_text('["unexpected-array"]', encoding="utf-8")
    with pytest.raises(ValueError, match="Expected JSON object"):
        ensure_global_hooks_json(bad_hooks)

    # 5. CLI `--install-global-hook --global-hooks-path` mode
    cli_hooks = tmp_path / "cli" / "hooks.json"
    proc1 = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(SCRIPT_PATH),
            "--install-global-hook",
            "--global-hooks-path",
            str(cli_hooks),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(proc1.stdout)["updated"] is True
    proc2 = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(SCRIPT_PATH),
            "--install-global-hook",
            "--global-hooks-path",
            str(cli_hooks),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(proc2.stdout)["updated"] is False


def test_all_five_active_rooms_parent_workspace_subagent_db_lineage_and_dual_hook_dedup(
    tmp_path: Path,
) -> None:
    reg_path = _make_sample_registry(tmp_path / ".agents" / "chatrooms.json")
    brain_root = tmp_path / "brain"
    archive_dir = tmp_path / "artifacts_archive"
    parent_ws = str(WORKSPACE_ROOT.parent)  # /home/canadaofbin/gdrive/Kyubin_Yun_Workspace (no 07_Youtube!)

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

    ceo_cid = "b57c97a8-6324-4c31-a2bb-16b25e28dd55"
    res_cid = "ffbdfca1-9c07-48b3-9b1e-3e3045d67c0c"
    daily_cid = "e3210c73-cc41-4432-87b1-c158efe9cadb"
    hq_cid = "8c7f8d97-664d-4d6b-9ef8-b17e721354f9"
    art_cid = "3c2fa53b-b43c-4f67-9dfd-0e5c86581f67"
    archived_cid = "00000000-1111-2222-3333-444444444444"
    unlisted_ws_cid = "unlisted01-1111-2222-3333-444444444444"
    unlisted_proj_cid = "unlisted02-1111-2222-3333-444444444444"
    sub_lvl1_cid = "sublevel01-1111-2222-3333-444444444444"
    sub_lvl2_cid = "sublevel02-1111-2222-3333-444444444444"

    # Simulate Research having a PARENT workspace URI in DB, Channel_Art having empty workspace_uris,
    # plus unlisted 07_Youtube rooms (one by workspace_uris, one by project_id) and a depth-2 subagent chain under HQ
    rows = [
        (ceo_cid, "YouTube_CEO", 0, f'["file://{WORKSPACE_ROOT}"]', YOUTUBE_PROJECT_ID, ""),
        (res_cid, "Research", 0, f'["file://{parent_ws}"]', "parent-proj-id", ""),
        (daily_cid, "Daily_Report", 0, f'["file://{WORKSPACE_ROOT}"]', YOUTUBE_PROJECT_ID, ""),
        (hq_cid, "Headquarters", 0, f'["file://{WORKSPACE_ROOT}"]', YOUTUBE_PROJECT_ID, ""),
        (art_cid, "Channel_Art", 0, "[]", "", ""),
        (archived_cid, "Empty_Archived", 0, f'["file://{parent_ws}"]', "", ""),
        (unlisted_ws_cid, "Adhoc YT WS", 0, f'["file://{WORKSPACE_ROOT}/03_visuals"]', "", ""),
        (unlisted_proj_cid, "Adhoc YT Proj", 0, "[]", YOUTUBE_PROJECT_ID, ""),
        (sub_lvl1_cid, "HQ Sub 1", 1, f'["file://{parent_ws}"]', "", hq_cid),
        (sub_lvl2_cid, "HQ Sub 2", 2, f'["file://{parent_ws}"]', "", sub_lvl1_cid),
    ]
    conn.executemany("INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()

    # 1. `sync_all(..., db_path=...)` discovers unlisted DB rooms (both workspace_uris and project_id) + archived room
    for cid, rel_name in (
        (archived_cid, "legacy_audit.md"),
        (unlisted_ws_cid, "visuals_note.md"),
        (unlisted_proj_cid, "proj_note.md"),
    ):
        d = brain_root / cid
        d.mkdir(parents=True, exist_ok=True)
        (d / rel_name).write_text(f"# {rel_name}\n", encoding="utf-8")

    sync_results = sync_all(
        archive_dir=archive_dir,
        registry_path=reg_path,
        brain_roots=[brain_root],
        db_path=db_path,
    )
    assert sum(r.copied for r in sync_results) == 3
    assert (archive_dir / "06_Empty_Archived" / "legacy_audit.md").exists()
    assert (archive_dir / "conv_unlisted" / "visuals_note.md").exists() or (
        archive_dir / f"conv_{unlisted_ws_cid[:8]}" / "visuals_note.md"
    ).exists()

    # 2. Prospective hook coverage across ALL 5 active chatrooms under parent/omitted workspacePaths + dual-hook dedup
    five_active = [
        (ceo_cid, "01_YouTube_CEO", [str(WORKSPACE_ROOT)], "write_to_file", "ceo_brief.md"),
        (res_cid, "02_Research", [parent_ws], "write_to_file", "competitor_teardown.md"),
        (daily_cid, "03_Daily_Report", None, "write_to_file", "daily_kpi.md"),
        (hq_cid, "04_Headquarters", [parent_ws], "replace_file_content", "qa_gate_report.md"),
        (art_cid, "05_Channel_Art", [], "generate_image", "channel_banner_v1.png"),
    ]

    for cid, folder, ws_paths, tool_name, fname in five_active:
        cdir = brain_root / cid
        cdir.mkdir(parents=True, exist_ok=True)
        fpath = cdir / fname
        if fname.endswith(".png"):
            fpath.write_bytes(b"\x89PNG\r\n\x1a\nBANNER")
            tool_args: dict[str, object] = {"ImageName": "channel_banner_v1", "Prompt": "Porcelain brain"}
        else:
            fpath.write_text(f"# {folder} v1\n", encoding="utf-8")
            tool_args = {"TargetFile": str(fpath)}

        payload: dict[str, object] = {
            "conversationId": cid,
            "artifactDirectoryPath": str(cdir),
            "toolCall": {"name": tool_name, "args": tool_args},
        }
        if ws_paths is not None:
            payload["workspacePaths"] = ws_paths

        # Hook #1 (global hook `~/.gemini/config/hooks.json`): copies & updates INDEX.md
        assert (
            handle_post_tool_use_payload(
                payload,
                archive_dir=archive_dir,
                registry_path=reg_path,
                brain_roots=[brain_root],
                db_path=db_path,
            )
            == {}
        )
        assert (archive_dir / folder / fname).exists()

        # Hook #2 (workspace hook `07_Youtube/.agents/hooks.json` firing milliseconds later): zero-copy dedup!
        idx_path = archive_dir / "INDEX.md"
        os.utime(idx_path, (1_700_000_000, 1_700_000_000))
        assert (
            handle_post_tool_use_payload(
                payload,
                archive_dir=archive_dir,
                registry_path=reg_path,
                brain_roots=[brain_root],
                db_path=db_path,
            )
            == {}
        )
        assert int(idx_path.stat().st_mtime) == 1_700_000_000, f"Duplicate hook rewrote INDEX.md for {folder}"

    # 3. Sub-millisecond same-byte-length edit via `replace_file_content` MUST still be caught on Hook #1
    hq_file = brain_root / hq_cid / "qa_gate_report.md"
    orig_stat = hq_file.stat()
    hq_file.write_text("# 04_Headquarters v2\n", encoding="utf-8")  # exact same byte length as v1!
    os.utime(hq_file, (orig_stat.st_atime, orig_stat.st_mtime))
    handle_post_tool_use_payload(
        {
            "conversationId": hq_cid,
            "workspacePaths": [parent_ws],
            "artifactDirectoryPath": str(brain_root / hq_cid),
            "toolCall": {"name": "replace_file_content", "args": {"TargetFile": str(hq_file)}},
        },
        archive_dir=archive_dir,
        registry_path=reg_path,
        brain_roots=[brain_root],
        db_path=db_path,
    )
    assert "# 04_Headquarters v2" in (archive_dir / "04_Headquarters" / "qa_gate_report.md").read_text(
        encoding="utf-8"
    )

    # 4. Depth-2 subagent Stop hook WITHOUT `parentConversationId` in stdin JSON walks DB lineage up to HQ!
    sub2_dir = brain_root / sub_lvl2_cid
    sub2_dir.mkdir(parents=True, exist_ok=True)
    (sub2_dir / "subagent_scratch.md").write_text("# Ephemeral\n", encoding="utf-8")
    (brain_root / hq_cid / "script_generated_chart.png").write_bytes(b"\x89PNG\r\n\x1a\nHQCHART")

    stop_resp = handle_stop_payload(
        {
            "conversationId": sub_lvl2_cid,
            "workspacePaths": [parent_ws],
            "artifactDirectoryPath": str(sub2_dir),
            "terminationReason": "NO_TOOL_CALL",
        },
        archive_dir=archive_dir,
        registry_path=reg_path,
        brain_roots=[brain_root],
        db_path=db_path,
    )
    assert stop_resp == {"decision": "stop"}
    assert not (archive_dir / f"conv_{sub_lvl2_cid[:8]}").exists()
    assert not (archive_dir / f"conv_{sub_lvl1_cid[:8]}").exists()
    assert (archive_dir / "04_Headquarters" / "script_generated_chart.png").exists()


def test_strict_non_youtube_isolation_outside_of_project_and_fast_noop_latency(tmp_path: Path) -> None:
    reg_path = _make_sample_registry(tmp_path / ".agents" / "chatrooms.json")
    brain_root = tmp_path / "brain"
    archive_dir = tmp_path / "artifacts_archive"
    parent_ws = str(WORKSPACE_ROOT.parent)

    db_path = tmp_path / "conversation_summaries.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE conversation_summaries (
            conversation_id TEXT PRIMARY KEY,
            nesting_depth INTEGER,
            workspace_uris TEXT,
            project_id TEXT,
            parent_conversation_id TEXT
        )
        """
    )
    ucl_cid = "uclconv01-0000-0000-0000-000000000001"
    intern_cid = "intern001-0000-0000-0000-000000000002"
    outside_cid = "outside01-0000-0000-0000-000000000003"
    parent_unlisted_cid = "parent001-0000-0000-0000-000000000004"
    prefix_collision_cid = "prefix001-0000-0000-0000-000000000005"

    conn.executemany(
        "INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?)",
        [
            (ucl_cid, 0, f'["file://{parent_ws}/02_UCL"]', "ucl-proj", ""),
            (intern_cid, 0, f'["file://{parent_ws}/04_Internship"]', "intern-proj", ""),
            (outside_cid, 0, "", "", ""),
            (parent_unlisted_cid, 0, f'["file://{parent_ws}"]', "parent-proj", ""),
            (prefix_collision_cid, 0, f'["file://{WORKSPACE_ROOT}_Backup"]', "backup-proj", ""),
        ],
    )
    conn.commit()
    conn.close()

    assert _discover_unlisted_07_youtube_convs(db_path, set()) == []

    foreign_cases: list[tuple[str, list[str] | None]] = [
        (ucl_cid, [f"{parent_ws}/02_UCL"]),
        (intern_cid, [f"{parent_ws}/04_Internship"]),
        (outside_cid, None),  # proto3 omitempty when Outside of Project!
        (parent_unlisted_cid, [parent_ws]),
        (prefix_collision_cid, [f"{WORKSPACE_ROOT}_Backup"]),
    ]

    for cid, ws_paths in foreign_cases:
        bdir = brain_root / cid
        bdir.mkdir(parents=True, exist_ok=True)
        plan_md = bdir / "implementation_plan.md"
        plan_md.write_text("# Non-YouTube Plan\n", encoding="utf-8")

        post_payload: dict[str, object] = {
            "conversationId": cid,
            "artifactDirectoryPath": str(bdir),
            "toolCall": {"name": "write_to_file", "args": {"TargetFile": str(plan_md)}},
        }
        img_payload: dict[str, object] = {
            "conversationId": cid,
            "artifactDirectoryPath": str(bdir),
            "toolCall": {"name": "generate_image", "args": {"ImageName": "diagram"}},
        }
        stop_payload: dict[str, object] = {
            "conversationId": cid,
            "artifactDirectoryPath": str(bdir),
            "terminationReason": "NO_TOOL_CALL",
        }
        if ws_paths is not None:
            post_payload["workspacePaths"] = ws_paths
            img_payload["workspacePaths"] = ws_paths
            stop_payload["workspacePaths"] = ws_paths

        assert (
            handle_post_tool_use_payload(
                post_payload, archive_dir=archive_dir, registry_path=reg_path, brain_roots=[brain_root], db_path=db_path
            )
            == {}
        )
        assert (
            handle_post_tool_use_payload(
                img_payload, archive_dir=archive_dir, registry_path=reg_path, brain_roots=[brain_root], db_path=db_path
            )
            == {}
        )
        assert handle_stop_payload(
            stop_payload, archive_dir=archive_dir, registry_path=reg_path, brain_roots=[brain_root], db_path=db_path
        ) == {"decision": "stop"}

    assert not archive_dir.exists(), "Foreign / Outside-of-Project conversations must NEVER touch artifacts_archive/"

    # Verify <15ms fast no-op for non-YouTube workspaces (UCL & Internship)
    ucl_ws_write = {
        "conversationId": ucl_cid,
        "workspacePaths": [f"{parent_ws}/02_UCL"],
        "artifactDirectoryPath": str(brain_root / ucl_cid),
        "toolCall": {"name": "write_to_file", "args": {"TargetFile": f"{parent_ws}/02_UCL/lecture_notes.md"}},
    }
    intern_stop = {
        "conversationId": intern_cid,
        "workspacePaths": [f"{parent_ws}/04_Internship"],
        "artifactDirectoryPath": str(brain_root / intern_cid),
        "terminationReason": "NO_TOOL_CALL",
    }
    # Warm 1 iteration then measure median over 5 runs
    handle_post_tool_use_payload(
        ucl_ws_write, archive_dir=archive_dir, registry_path=reg_path, brain_roots=[brain_root], db_path=db_path
    )
    handle_stop_payload(
        intern_stop, archive_dir=archive_dir, registry_path=reg_path, brain_roots=[brain_root], db_path=db_path
    )

    post_times_ms: list[float] = []
    stop_times_ms: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        handle_post_tool_use_payload(
            ucl_ws_write, archive_dir=archive_dir, registry_path=reg_path, brain_roots=[brain_root], db_path=db_path
        )
        post_times_ms.append((time.perf_counter() - t0) * 1000.0)

        t1 = time.perf_counter()
        handle_stop_payload(
            intern_stop, archive_dir=archive_dir, registry_path=reg_path, brain_roots=[brain_root], db_path=db_path
        )
        stop_times_ms.append((time.perf_counter() - t1) * 1000.0)

    post_times_ms.sort()
    stop_times_ms.sort()
    assert post_times_ms[2] < 15.0, f"UCL PostToolUse median {post_times_ms[2]:.2f}ms >= 15ms"
    assert stop_times_ms[2] < 15.0, f"Internship Stop median {stop_times_ms[2]:.2f}ms >= 15ms"


def test_live_all_youtube_chatrooms_retroactively_archived() -> None:
    cmap = load_chatroom_map(DEFAULT_REGISTRY_PATH)
    assert len([c for c in cmap.values() if c.active]) == 7

    all_yt_cids: list[str] = list(cmap.keys())
    seen = set(all_yt_cids)
    if DEFAULT_DB_PATH.exists():
        for extra_cid in _discover_unlisted_07_youtube_convs(DEFAULT_DB_PATH, seen):
            all_yt_cids.append(extra_cid)
            seen.add(extra_cid)

    index_txt = (DEFAULT_ARCHIVE_DIR / "INDEX.md").read_text(encoding="utf-8")

    # Every active room folder must exist and be listed in INDEX.md
    for info in cmap.values():
        if info.active:
            assert (DEFAULT_ARCHIVE_DIR / info.folder_name).is_dir()
            assert f"./{info.folder_name}/" in index_txt

    # Every non-excluded artifact across ALL YouTube rooms (active + archived + DB) must exist in artifacts_archive/
    for cid in all_yt_cids:
        src_dirs = [br / cid for br in DEFAULT_BRAIN_ROOTS]
        src_files = _collect_source_files(src_dirs)
        if not src_files:
            continue
        folder = resolve_archive_folder(cid, cmap)
        for rel_path in src_files:
            archived_file = DEFAULT_ARCHIVE_DIR / folder / rel_path
            assert archived_file.is_file(), f"Missing archived file for {cid} ({folder}): {rel_path}"
            if rel_path.suffix.lower() == ".md":
                assert f"./{folder}/{rel_path.as_posix()}" in index_txt


