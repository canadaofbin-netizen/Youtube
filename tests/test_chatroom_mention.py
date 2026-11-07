"""Tests for cross-chatroom @mention registry and resolver (`scripts/chatroom_mention.py`)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.chatroom_mention import (
    DEFAULT_REGISTRY_PATH,
    main,
    resolve_mentions,
    sync_registry,
)


def _make_temp_db(db_path: Path) -> Path:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE conversation_summaries (
            conversation_id TEXT PRIMARY KEY,
            title TEXT,
            workspace_uris TEXT,
            step_count INTEGER,
            last_modified_time TEXT,
            status TEXT,
            nesting_depth INTEGER
        )
        """
    )
    conn.executemany(
        "INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "ffbdfca1-9c07-48b3-9b1e-3e3045d67c0c",
                "Research",
                '["file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube"]',
                90,
                "2026-11-05T02:37:03Z",
                "CASCADE_RUN_STATUS_IDLE",
                0,
            ),
            (
                "11111111-2222-3333-4444-555555555555",
                "Shorts Hook Lab",
                '["file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube"]',
                12,
                "2026-11-05T03:00:00Z",
                "CASCADE_RUN_STATUS_IDLE",
                0,
            ),
            (
                "99999999-8888-7777-6666-555555555555",
                "Subagent Worker",
                '["file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube"]',
                5,
                "2026-11-05T03:01:00Z",
                "CASCADE_RUN_STATUS_IDLE",
                1,
            ),
            (
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "Other Workspace Chat",
                '["file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/02_UCL"]',
                10,
                "2026-11-05T03:02:00Z",
                "CASCADE_RUN_STATUS_IDLE",
                0,
            ),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


def test_workspace_chatrooms_registry_valid() -> None:
    assert DEFAULT_REGISTRY_PATH.exists()
    data = json.loads(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
    by_handle = {c["handle"]: c["conversation_id"] for c in data["chatrooms"]}
    assert by_handle["@YouTube_CEO"] == "b57c97a8-6324-4c31-a2bb-16b25e28dd55"
    assert by_handle["@Research"] == "ffbdfca1-9c07-48b3-9b1e-3e3045d67c0c"
    assert by_handle["@Daily_Report"] == "e3210c73-cc41-4432-87b1-c158efe9cadb"
    assert by_handle["@Headquarters"] == "8c7f8d97-664d-4d6b-9ef8-b17e721354f9"
    assert by_handle["@Channel_Art"] == "3c2fa53b-b43c-4f67-9dfd-0e5c86581f67"


def test_resolve_english_korean_and_dynamic_db_mentions(tmp_path: Path) -> None:
    reg_copy = tmp_path / "chatrooms.json"
    reg_copy.write_text(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    db_path = _make_temp_db(tmp_path / "summaries.db")

    # 1. Case-insensitive English + Korean alias + email/channel-handle ignore
    out = resolve_mentions(
        "@research @일일리포트 Check user@example.com and @AllAboutBrainOfficial metrics",
        registry_path=reg_copy,
        db_path=db_path,
    )
    assert out["unresolved"] == []
    ids = [r["recipient"] for r in out["resolved"]]
    assert ids == [
        "ffbdfca1-9c07-48b3-9b1e-3e3045d67c0c",
        "e3210c73-cc41-4432-87b1-c158efe9cadb",
    ]
    assert out["task_message"] == "Check user@example.com and @AllAboutBrainOfficial metrics"

    # 2. Newly created top-level 07_Youtube chatroom in SQLite DB auto-resolves without manual edit
    dyn = resolve_mentions("@Shorts_Hook_Lab test 3 cold opens", registry_path=reg_copy, db_path=db_path)
    assert len(dyn["resolved"]) == 1
    assert dyn["resolved"][0]["recipient"] == "11111111-2222-3333-4444-555555555555"
    assert dyn["task_message"] == "test 3 cold opens"

    # 3. Subagents (nesting_depth=1) and non-07_Youtube workspaces are excluded from sync
    synced = sync_registry(registry_path=reg_copy, db_path=db_path, write=True)
    assert synced["added"] == 1
    cids = {c["conversation_id"] for c in synced["registry"]["chatrooms"]}
    assert "99999999-8888-7777-6666-555555555555" not in cids
    assert "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" not in cids


def test_edge_cases_empty_and_unknown_strict(tmp_path: Path) -> None:
    reg_copy = tmp_path / "chatrooms.json"
    reg_copy.write_text(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    missing_db = tmp_path / "missing.db"

    empty = resolve_mentions("   ", registry_path=reg_copy, db_path=missing_db)
    assert empty["resolved"] == [] and empty["unresolved"] == [] and empty["task_message"] == ""

    rc_unknown = main(["--registry", str(reg_copy), "--db", str(missing_db), "resolve", "--strict", "@NonExistentRoom hi"])
    assert rc_unknown == 1

    rc_ok = main(["--registry", str(reg_copy), "--db", str(missing_db), "resolve", "--strict", "@Research summarize hooks"])
    assert rc_ok == 0


def test_korean_particles_active_precedence_and_trailing_hyphen(tmp_path: Path) -> None:
    reg_copy = tmp_path / "chatrooms.json"
    reg_copy.write_text(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    missing_db = tmp_path / "missing.db"

    # 1. Korean postpositions / honorifics / room-suffixes attached directly without whitespace
    ko = resolve_mentions(
        "@리서치한테 @본부에게 @채널아트랑 @총괄님께 @Research한테 경쟁 채널 쇼츠 후킹 공식 분석해줘",
        registry_path=reg_copy,
        db_path=missing_db,
    )
    assert ko["unresolved"] == []
    assert [r["recipient"] for r in ko["resolved"]] == [
        "ffbdfca1-9c07-48b3-9b1e-3e3045d67c0c",
        "8c7f8d97-664d-4d6b-9ef8-b17e721354f9",
        "3c2fa53b-b43c-4f67-9dfd-0e5c86581f67",
        "b57c97a8-6324-4c31-a2bb-16b25e28dd55",
    ]
    assert ko["task_message"] == "경쟁 채널 쇼츠 후킹 공식 분석해줘"

    # 2. Active room wins over archived rooms containing "Daily" ("YouTube Daily Report Redesign" / "Plan")
    daily = resolve_mentions("@Daily 오늘 리포트 확인", registry_path=reg_copy, db_path=missing_db)
    assert daily["unresolved"] == []
    assert len(daily["resolved"]) == 1
    assert daily["resolved"][0]["handle"] == "@Daily_Report"
    assert daily["task_message"] == "오늘 리포트 확인"

    # 3. Trailing hyphen token cleanup does not fail word-boundary stripping
    hyph = resolve_mentions("@daily-report- check funnel metrics", registry_path=reg_copy, db_path=missing_db)
    assert hyph["unresolved"] == []
    assert hyph["resolved"][0]["handle"] == "@Daily_Report"
    assert hyph["task_message"] == "check funnel metrics"

