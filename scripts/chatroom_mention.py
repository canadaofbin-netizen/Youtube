#!/usr/bin/env python3
"""Cross-chatroom @mention registry & resolver for 07_Youtube (YouTube_CEO dispatch).

Resolves `@Research`, `@Daily_Report`, `@Headquarters`, `@Channel_Art` (and Korean aliases
or newly created top-level 07_Youtube conversations in Antigravity's SQLite DB) into exact
`conversation_id` recipients for `send_message(Recipient=..., Message=...)`.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_PATH = WORKSPACE_ROOT / ".agents" / "chatrooms.json"
DEFAULT_DB_PATH = Path("/home/canadaofbin/.gemini/antigravity-cli/conversation_summaries.db")
DEFAULT_BRAIN_DIR = Path("/home/canadaofbin/.gemini/antigravity-cli/brain")
WORKSPACE_TAG = "07_Youtube"

# Matches @mention tokens preceded by start-of-string or whitespace/punctuation (ignores emails foo@bar)
MENTION_RE = re.compile(r"(?<![\w.@])@([A-Za-z0-9_\-\uac00-\ud7a3]+)")

# Longest-first Korean postpositions, honorifics, and room suffixes commonly attached without whitespace
_KO_PARTICLE_SUFFIXES: tuple[str, ...] = tuple(
    sorted(
        {
            "채팅방한테", "채팅방에게", "채팅방에서", "채팅방으로", "채팅방에", "채팅방은", "채팅방이", "채팅방을", "채팅방도", "채팅방",
            "방한테", "방에게", "방에서", "방으로", "방에", "방은", "방이", "방을", "방도", "방랑",
            "팀한테", "팀에게", "팀에서", "팀으로", "팀에", "팀은", "팀이", "팀을", "팀도", "팀랑",
            "님한테", "님에게", "님께서", "님께", "님은", "님이", "님을", "님도", "님과", "님와", "님랑",
            "한테서", "에게서", "한테", "에게", "께서", "에서", "으로", "이랑", "하고",
            "께", "에", "로", "랑", "와", "과", "은", "는", "이", "가", "을", "를", "도", "만", "님", "방", "팀",
        },
        key=len,
        reverse=True,
    )
)


def _norm(token: str) -> str:
    clean = token.strip().lstrip("@").strip("-_").lower()
    return re.sub(r"[\s\-]+", "_", clean)


def _candidate_stems(raw_tok: str) -> list[str]:
    base = raw_tok.strip().lstrip("@").rstrip("-_")
    if not base:
        return []
    out = [base]
    for sfx in _KO_PARTICLE_SUFFIXES:
        if base.endswith(sfx) and len(base) > len(sfx):
            stem = base[: -len(sfx)].rstrip("-_")
            if stem and stem not in out:
                out.append(stem)
    return out


def _slug_handle(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9\uac00-\ud7a3]+", "_", title.strip()).strip("_")
    return f"@{slug or 'Chatroom'}"


def query_live_db_chatrooms(
    db_path: Path = DEFAULT_DB_PATH,
    workspace_filter: str = WORKSPACE_TAG,
) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=3.0)
    except sqlite3.Error:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT conversation_id, title, workspace_uris, step_count, last_modified_time, status
            FROM conversation_summaries
            WHERE nesting_depth = 0
            ORDER BY last_modified_time DESC
            """
        )
        out: list[dict[str, Any]] = []
        for cid, title, ws_uris, steps, mtime, status in cur.fetchall():
            ws_str = ws_uris or ""
            if workspace_filter and workspace_filter not in ws_str:
                continue
            cid_s = str(cid)
            clean_title = str(title or "").strip()
            # Skip conversations deleted in UI (missing brain/<cid> transcript) when querying live Antigravity DB
            if (
                db_path == DEFAULT_DB_PATH
                and DEFAULT_BRAIN_DIR.is_dir()
                and not (DEFAULT_BRAIN_DIR / cid_s / ".system_generated" / "logs" / "transcript.jsonl").is_file()
            ):
                continue
            if not clean_title:
                continue
            out.append(
                {
                    "conversation_id": cid_s,
                    "title": clean_title,
                    "step_count": int(steps or 0),
                    "last_modified_time": str(mtime or ""),
                    "status": str(status or ""),
                }
            )
        return out
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def load_registry(registry_path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    if not registry_path.exists():
        return {
            "schema_version": 1,
            "workspace": str(WORKSPACE_ROOT),
            "hub_conversation_id": "",
            "ignored_handles": [],
            "chatrooms": [],
        }
    return json.loads(registry_path.read_text(encoding="utf-8"))


def sync_registry(
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    db_path: Path = DEFAULT_DB_PATH,
    write: bool = True,
) -> dict[str, Any]:
    reg = load_registry(registry_path)
    live_rows = query_live_db_chatrooms(db_path=db_path)
    enforce_live_transcript = (
        registry_path == DEFAULT_REGISTRY_PATH
        and db_path == DEFAULT_DB_PATH
        and DEFAULT_BRAIN_DIR.is_dir()
    )
    kept_rooms = [
        c
        for c in reg.get("chatrooms", [])
        if c.get("conversation_id")
        and (
            not enforce_live_transcript
            or (DEFAULT_BRAIN_DIR / str(c["conversation_id"]) / ".system_generated" / "logs" / "transcript.jsonl").is_file()
        )
    ]
    pruned = len(reg.get("chatrooms", [])) - len(kept_rooms)
    reg["chatrooms"] = kept_rooms
    by_id = {c["conversation_id"]: c for c in kept_rooms}

    added = 0
    for row in live_rows:
        cid = row["conversation_id"]
        if cid in by_id:
            by_id[cid]["title"] = row["title"] or by_id[cid].get("title", "")
            by_id[cid]["last_modified_time"] = row["last_modified_time"]
            by_id[cid]["status"] = row["status"]
        elif row["title"] != "YouTube Daily Report Redesign":
            handle = _slug_handle(row["title"])
            entry = {
                "handle": handle,
                "conversation_id": cid,
                "title": row["title"],
                "role": "Auto-discovered 07_Youtube top-level chatroom",
                "aliases": [_norm(handle), _norm(row["title"])],
                "active": True,
                "last_modified_time": row["last_modified_time"],
                "status": row["status"],
            }
            reg.setdefault("chatrooms", []).append(entry)
            by_id[cid] = entry
            added += 1

    if write:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"registry": reg, "added": added, "pruned": pruned, "live_count": len(live_rows)}


def _substring_match_room(key: str, rooms: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(key) < 2:
        return None
    active_rooms = [r for r in rooms if r.get("active", True)]
    for pool in (active_rooms, [r for r in rooms if not r.get("active", True)]):
        cands = [
            r
            for r in pool
            if key in _norm(r.get("handle", ""))
            or key in _norm(r.get("title", ""))
            or any(key in _norm(a) for a in r.get("aliases", []))
        ]
        if len(cands) == 1:
            return cands[0]
        if cands:
            return None
    return None


def resolve_mentions(
    text: str,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    if not text or not text.strip():
        return {"input": text, "resolved": [], "unresolved": [], "task_message": ""}

    synced = sync_registry(registry_path=registry_path, db_path=db_path, write=False)["registry"]
    ignored = {_norm(h) for h in synced.get("ignored_handles", [])}
    all_rooms: list[dict[str, Any]] = list(synced.get("chatrooms", []))
    # Index active chatrooms first so archived rooms never shadow active aliases
    ordered_rooms = [r for r in all_rooms if r.get("active", True)] + [
        r for r in all_rooms if not r.get("active", True)
    ]

    lookup: dict[str, dict[str, Any]] = {}
    for room in ordered_rooms:
        keys = {_norm(room.get("handle", "")), _norm(room.get("title", ""))}
        for alias in room.get("aliases", []):
            keys.add(_norm(alias))
        if room.get("conversation_id"):
            keys.add(room["conversation_id"].lower())
        for k in keys:
            if k and k not in lookup:
                lookup[k] = room

    raw_mentions = MENTION_RE.findall(text)
    resolved: list[dict[str, Any]] = []
    unresolved: list[str] = []
    seen_ids: set[str] = set()
    matched_tokens: list[str] = []

    for tok in raw_mentions:
        stems = _candidate_stems(tok)
        if not stems:
            continue
        if any(_norm(s) in ignored for s in stems):
            continue

        room: dict[str, Any] | None = None
        for s in stems:
            k = _norm(s)
            if k and k in lookup:
                room = lookup[k]
                break
        if room is None:
            for s in stems:
                k = _norm(s)
                room = _substring_match_room(k, ordered_rooms)
                if room is not None:
                    break

        if room is not None:
            matched_tokens.append(f"@{tok}")
            cid = room["conversation_id"]
            if cid not in seen_ids:
                seen_ids.add(cid)
                resolved.append(
                    {
                        "mention": f"@{tok}",
                        "handle": room["handle"],
                        "title": room.get("title", ""),
                        "recipient": cid,
                        "conversation_id": cid,
                        "role": room.get("role", ""),
                    }
                )
        else:
            unresolved.append(f"@{tok}")

    cleaned = text
    for mt in matched_tokens:
        cleaned = re.sub(
            rf"(?<![\w.@]){re.escape(mt)}(?![A-Za-z0-9_\-\uac00-\ud7a3])\s*[:,;-]?\s*",
            "",
            cleaned,
            count=1,
        )
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    task_msg = cleaned or text.strip()

    for item in resolved:
        item["task_message"] = task_msg

    return {
        "input": text,
        "resolved": resolved,
        "unresolved": unresolved,
        "task_message": task_msg,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="07_Youtube cross-chatroom @mention resolver")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List registered & live 07_Youtube chatrooms")
    p_list.add_argument("--all", action="store_true", help="Include archived chatrooms")
    p_list.add_argument("--json", action="store_true")

    sub.add_parser("sync", help="Sync newly opened 07_Youtube chatrooms from SQLite DB into chatrooms.json")

    p_res = sub.add_parser("resolve", help="Resolve @mentions in text to send_message Recipient IDs")
    p_res.add_argument("text", help="Prompt text containing @Chatroom mentions")
    p_res.add_argument("--strict", action="store_true", help="Exit 1 if no mention resolved or any unresolved")

    p_wake = sub.add_parser("wake", help="Wake a sleeping/unloaded chatroom via official agy --conversation CLI")
    p_wake.add_argument("handle", help="Target @Chatroom handle or conversation_id (e.g. @Operator)")
    p_wake.add_argument("prompt", help="Task prompt to deliver & execute immediately")
    p_wake.add_argument("--timeout", default="0", help="agy --print-timeout value (default: 0 = wait until turn finishes)")

    sub.add_parser("wake-daemons", help="Wake all active chatrooms & restore @Daily_Report/@QA_Scheduler/@Topic_Radar daemon crons after server restart")

    args = parser.parse_args(argv)

    if args.cmd == "wake":
        tok = args.handle if str(args.handle).startswith("@") else f"@{args.handle}"
        out = resolve_mentions(f"{tok} {args.prompt}", registry_path=args.registry, db_path=args.db)
        if not out["resolved"]:
            print(json.dumps({"ok": False, "error": f"Unresolved handle: {args.handle}"}, ensure_ascii=False))
            return 1
        target = out["resolved"][0]
        cid = target["conversation_id"]
        proc = subprocess.run(
            [
                "agy",
                "--conversation",
                cid,
                "--dangerously-skip-permissions",
                "-p",
                args.prompt,
                "--print-timeout",
                str(args.timeout),
            ],
            capture_output=True,
            text=True,
        )
        print(
            json.dumps(
                {
                    "ok": proc.returncode == 0,
                    "handle": target["handle"],
                    "conversation_id": cid,
                    "returncode": proc.returncode,
                    "stdout_tail": (proc.stdout or "")[-600:],
                    "stderr_tail": (proc.stderr or "")[-300:],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if proc.returncode == 0 else proc.returncode

    if args.cmd == "wake-daemons":
        daemon_specs = [
            ("@Daily_Report", "e3210c73-cc41-4432-87b1-c158efe9cadb", "[Auto-Wake] Verify `manage_task(Action='list')` and re-register daily 07:00 UTC YouTube Studio report cron (`IsDaemon=True`) if cleared."),
            ("@QA_Scheduler", "ef8185bb-5afd-4859-b697-2fe07f1ecf1c", "[Auto-Wake] Verify `manage_task(Action='list')` and re-register daily 08:00 UTC QA Scheduler cron (`IsDaemon=True`) if cleared."),
            ("@Topic_Radar", "0ffee83a-d9de-4520-a177-7d3b57dc01dc", "[Auto-Wake] Verify `manage_task(Action='list')` and re-register Monday 09:30 UTC weekly topic research cron (`IsDaemon=True`) if cleared."),
            ("@Research", "ffbdfca1-9c07-48b3-9b1e-3e3045d67c0c", "[Auto-Wake] Verify `manage_task(Action='list')` and re-register standing 6h inbox watchdog cron (`0 */6 * * *`, `IsDaemon=True`) if cleared."),
            ("@Operator", "1f9808d4-ebac-4b58-a570-45c8f1f00a85", "[Auto-Wake] Server restart wakeup check; process any pending inbox tasks or confirm standby."),
        ]

        def _w(spec: tuple[str, str, str]) -> dict[str, Any]:
            h, cid, pr = spec
            r = subprocess.run(
                ["agy", "--conversation", cid, "--dangerously-skip-permissions", "-p", pr, "--print-timeout", "90s"],
                capture_output=True,
                text=True,
            )
            return {"handle": h, "conversation_id": cid, "returncode": r.returncode}

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(daemon_specs)) as pool:
            results = list(pool.map(_w, daemon_specs))
        print(json.dumps({"woken": results}, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "sync":
        res = sync_registry(registry_path=args.registry, db_path=args.db, write=True)
        print(json.dumps({"added": res["added"], "live_count": res["live_count"], "total": len(res["registry"]["chatrooms"])}, ensure_ascii=False))
        return 0

    if args.cmd == "list":
        reg = sync_registry(registry_path=args.registry, db_path=args.db, write=False)["registry"]
        rooms = [r for r in reg.get("chatrooms", []) if args.all or r.get("active", True)]
        if args.json:
            print(json.dumps(rooms, ensure_ascii=False, indent=2))
        else:
            for r in rooms:
                aliases = ", ".join(f"@{a}" for a in r.get("aliases", [])[:4])
                print(f"{r['handle']:<16} -> {r['conversation_id']}  ({r.get('title', '')})  [{aliases}]")
        return 0

    if args.cmd == "resolve":
        out = resolve_mentions(args.text, registry_path=args.registry, db_path=args.db)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if args.strict and (not out["resolved"] or out["unresolved"]):
            return 1
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
