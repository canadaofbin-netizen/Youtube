"""
Unit & regression tests for YouTube Studio 'Draft(초안)' Prevention &
Post-Upload Scheduled DOM Verification + Self-Heal (`Task B`).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pipeline.studio.uploader import StudioUploader
from pipeline.studio.browser_session import DirectCDPClient


class _FakeScheduleCDPClient(DirectCDPClient):
    """Hermetic fake DirectCDPClient simulating YouTube Studio Polymer schedule DOM."""

    def __init__(self, *, done_label: str = "Schedule", radio_checks: bool = True, invalid_input: bool = False) -> None:
        # Bypass real WebSocket init
        self.ws_url = "ws://127.0.0.1:9222/devtools/page/FAKE"
        self._ws = None
        self._msg_id = 0
        self.done_label = done_label
        self.radio_checks = radio_checks
        self.invalid_input = invalid_input
        self.eval_calls: list[str] = []

    async def eval(self, expression: str, await_promise: bool = True) -> Any:
        self.eval_calls.append(expression)
        if "__scheduleRadioVerified" in expression:
            return bool(self.radio_checks)
        if "ytcp-date-picker" in expression and "nativeSetter" in expression:
            return not self.invalid_input
        if "#time-of-day-container" in expression and "wanted" in expression:
            return not self.invalid_input
        if "__verifyScheduleCommitReady" in expression:
            if not self.radio_checks or self.invalid_input:
                return {"ok": False, "reason": "invalid_or_unchecked", "doneText": self.done_label}
            low = self.done_label.strip().lower()
            ok = ("schedule" in low) or ("예약" in self.done_label)
            return {"ok": ok, "reason": "ok" if ok else f"done_label={self.done_label}", "doneText": self.done_label}
        return True


def _make_hermetic_stub_project(tmp_path: Path, project_id: str = "stub_sched_proj") -> Path:
    projects_dir = tmp_path / "projects"
    proj = projects_dir / project_id
    for sub in ("02_script", "03_visuals", "05_assembly", "06_publish"):
        (proj / sub).mkdir(parents=True, exist_ok=True)
    (proj / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"dossier": "test_obedience", "pillar": "brain_mysteries"}),
        encoding="utf-8",
    )
    (proj / "02_script" / "script.json").write_text(
        json.dumps({"title": "Why One Breath Terrified Her", "pillar": "brain_mysteries"}),
        encoding="utf-8",
    )
    (proj / "06_publish" / "metadata.json").write_text(
        json.dumps(
            {
                "title": "Why One Breath Terrified Her",
                "description": "Clean two-paragraph viewer description.\n\nResearch: Feinstein et al., Iowa (2013).",
                "pillar": "brain_mysteries",
            }
        ),
        encoding="utf-8",
    )
    mp4 = proj / "05_assembly" / "final_shorts_1080x1920.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x01" * 2048)
    thumb = proj / "06_publish" / "thumbnail.png"
    thumb.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x02" * 1024)
    (proj / "00_project_manifest.json").write_text(
        json.dumps({"project_id": project_id, "stages": {"05_assembly": {"status": "pending", "artifacts": {}}}}),
        encoding="utf-8",
    )
    return projects_dir


def test_prepare_upload_payload_defaults_slot4_1930_et_and_rolls_past_or_booked_dates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_dir = _make_hermetic_stub_project(tmp_path, "ep_sched_a")
    # Book 2026-11-12 as already scheduled by another project in staging_queue.json
    queue_path = tmp_path / "staging_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "queue": [
                    {
                        "project_id": "other_booked_ep",
                        "status": "scheduled",
                        "target_publish_date": "2026-11-12",
                        "slot_id": 4,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    # Freeze current ET to 2026-11-11 19:20 ET (within 20 minutes of 19:30 ET!)
    fixed_now_et = datetime(2026, 11, 11, 19, 20, tzinfo=ZoneInfo("America/New_York"))
    monkeypatch.setattr("pipeline.studio.uploader._now_us_eastern", lambda: fixed_now_et)

    uploader = StudioUploader(projects_dir=projects_dir)
    payload = uploader.prepare_upload_payload(
        "ep_sched_a",
        visibility="scheduled",
        slot_id=None,
        target_date="2026-11-11",
    )
    assert payload["slot_id"] == 4
    assert payload["slot_info"]["time_et"] == "19:30"
    # 2026-11-11 19:30 ET is only +10m away (<= +20m guard) AND 2026-11-12 is booked -> auto-rolls to 2026-11-13!
    assert payload["target_date"] == "2026-11-13"
    assert payload["scheduled_time_et"] == "2026-11-13 19:30 ET"


def test_set_schedule_datetime_utc_rejects_save_draft_button_and_accepts_schedule() -> None:
    dt_et = datetime(2026, 11, 12, 19, 30, tzinfo=ZoneInfo("America/New_York"))

    good_client = _FakeScheduleCDPClient(done_label="Schedule", radio_checks=True, invalid_input=False)
    assert asyncio.run(good_client.set_schedule_datetime_utc("13 Nov 2026", "09:30", dt_et=dt_et)) is True

    ko_client = _FakeScheduleCDPClient(done_label="예약", radio_checks=True, invalid_input=False)
    assert asyncio.run(ko_client.set_schedule_datetime_utc("13 Nov 2026", "09:30", dt_et=dt_et)) is True

    draft_client = _FakeScheduleCDPClient(done_label="Save", radio_checks=True, invalid_input=False)
    assert asyncio.run(draft_client.set_schedule_datetime_utc("13 Nov 2026", "09:30", dt_et=dt_et)) is False

    unchecked_client = _FakeScheduleCDPClient(done_label="Schedule", radio_checks=False, invalid_input=False)
    assert asyncio.run(unchecked_client.set_schedule_datetime_utc("13 Nov 2026", "09:30", dt_et=dt_et)) is False


def test_post_upload_scheduled_verification_and_self_heal(tmp_path: Path) -> None:
    projects_dir = _make_hermetic_stub_project(tmp_path, "ep_heal")
    uploader = StudioUploader(projects_dir=projects_dir)
    dt_et = datetime(2026, 11, 12, 19, 30, tzinfo=ZoneInfo("America/New_York"))

    # Case 1: Initially Draft -> Self-Heal -> Scheduled
    states = [
        {"found": True, "visibility": "Draft", "date": "Nov 11, 2026"},
        {"found": True, "visibility": "Scheduled", "date": "Nov 13, 2026"},
    ]
    heal_called = {"count": 0}

    async def fake_read_row(_client: Any, _vid: str) -> dict[str, Any]:
        return states.pop(0) if states else {"found": True, "visibility": "Scheduled", "date": "Nov 13, 2026"}

    async def fake_self_heal(_client: Any, *, video_id: str, dt_et: datetime, browser_date_label: str, browser_time_24h: str) -> bool:
        heal_called["count"] += 1
        return True

    uploader._read_studio_video_row_status = fake_read_row  # type: ignore[method-assign]
    uploader._self_heal_video_schedule_on_edit_page = fake_self_heal  # type: ignore[method-assign]

    res = asyncio.run(
        uploader.verify_and_self_heal_scheduled_row(
            object(),  # type: ignore[arg-type]
            video_id="AbCdEfGhIjK",
            dt_et=dt_et,
            browser_date_label="13 Nov 2026",
            browser_time_24h="09:30",
        )
    )
    assert heal_called["count"] == 1
    assert res["verified"] is True
    assert res["self_healed"] is True
    assert "Scheduled" in res["visibility_text"]

    # Case 2: Still Draft after Self-Heal -> raises RuntimeError
    async def always_draft(_client: Any, _vid: str) -> dict[str, Any]:
        return {"found": True, "visibility": "초안", "date": ""}

    uploader._read_studio_video_row_status = always_draft  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="Draft|Scheduled"):
        asyncio.run(
            uploader.verify_and_self_heal_scheduled_row(
                object(),  # type: ignore[arg-type]
                video_id="AbCdEfGhIjK",
                dt_et=dt_et,
                browser_date_label="13 Nov 2026",
                browser_time_24h="09:30",
            )
        )
