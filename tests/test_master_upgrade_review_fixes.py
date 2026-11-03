from __future__ import annotations

import argparse
import asyncio
import json
import math
import struct
import wave
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from pipeline import cli, config, flow_ingredients, longform_assembler, news_radar, thumbnail_studio
from pipeline.config import (
    DOSSIERS_DIR,
    FLOW_ZERO_CREDIT_IMAGE_MODEL,
    LONGFORM_VIDEO_FPS,
    LONGFORM_VIDEO_HEIGHT,
    LONGFORM_VIDEO_WIDTH,
    PILLAR_DEFAULT_STYLE_MAP,
    TITLE_MAX_CHARS_DIORAMA,
)
from pipeline.diorama_batch_orchestrator import build_editorial_description_from_dossier
from pipeline.prompt_quality_v5 import validate_production_diorama_v6
from pipeline.reference_image_qa import _dhash_64
from pipeline.studio.community import CommunityManager, _find_matching_dossier_dir
from pipeline.studio.sanitize_scheduled_metadata import (
    build_diversified_description,
    diversify_clone_title,
)
from pipeline.studio.studio_watchdog import cleanup_idle_whale_tabs


class _FakeFlowImageCDPClient:
    """Deterministic fake DirectCDPClient exercising configure_flow_zero_credit_image_mode & generate_flow_image_batch."""

    def __init__(
        self,
        *,
        pane_text: str = "Generating will use 0 credits",
        warn: bool = False,
        initial_family: str = "",
        after_click_family: str = "beluga_display",
        rendered_urls: list[str] | None = None,
    ) -> None:
        self.pane_text = pane_text
        self.warn = warn
        self.family = initial_family
        self.after_click_family = after_click_family
        self.rendered_urls = list(rendered_urls or [])
        self.clicked_dropdown = False
        self.selected_model = False

    async def eval(self, expr: str) -> Any:
        if "localStorage.getItem('flow-prompt-box-settings')" in expr and "txt:" not in expr:
            return {"imageModelFamilyId": self.family, "mode": "IMAGE", "outputCount": 4}
        if "txt:" in expr and "localStorage.getItem('flow-prompt-box-settings')" in expr:
            return {
                "txt": self.pane_text,
                "warn": self.warn,
                "ls": {
                    "mode": "IMAGE",
                    "imageModelFamilyId": self.family,
                    "outputCount": 4,
                },
            }
        if "bCnt" in expr and "bAsp" in expr:
            return {"txt": self.pane_text, "warn": self.warn, "clicked": True}
        if "button.settings-trigger-button')?.innerText" in expr:
            return "Image · 9:16 · x4"
        if "action: 'listener_invoked'" in expr:
            return {"action": "listener_invoked", "x": 400, "y": 800, "disabled": False}
        if "ed.innerText || '').trim().length : 0" in expr:
            return 0
        if "flow-pending-tile" in expr and "urls" in expr:
            return {"urls": list(self.rendered_urls), "pending": 0, "errTiles": 0}
        if "Boolean(document.querySelector('button.prompt-warning-button'))" in expr:
            return self.warn
        if ".filter(im => im.naturalWidth >= 300" in expr:
            return []
        return True

    async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return {}


def test_configure_flow_zero_credit_image_mode_selects_model_when_unset_and_rejects_paid(
    monkeypatch: pytest.MonkeyPatch,
):
    async def _fast_sleep(_sec: float) -> None:
        return None

    monkeypatch.setattr(flow_ingredients.asyncio, "sleep", _fast_sleep)

    client_paid = _FakeFlowImageCDPClient(
        pane_text="Generating will use 4 credits",
        warn=False,
        initial_family="beluga_display",
    )

    async def _fake_find_point_paid(c: Any, sel: str, text: str = "", exact: bool = False) -> tuple[int, int] | None:
        return (200, 300)

    async def _fake_click_paid(c: Any, pt: tuple[int, int]) -> None:
        return None

    monkeypatch.setattr(flow_ingredients, "find_point", _fake_find_point_paid)
    monkeypatch.setattr(flow_ingredients, "trusted_click", _fake_click_paid)

    # Even without button.prompt-warning-button and with family_ok=True, explicit non-zero credit text MUST fail closed
    with pytest.raises(RuntimeError, match="Failed to verify 0-credit Google Flow Image mode"):
        asyncio.run(flow_ingredients.configure_flow_zero_credit_image_mode(client_paid, aspect="9:16", batch_count=4))

    # When imageModelFamilyId starts unset (""), dropdown MUST be opened and Nano Banana 2.1 selected
    client_unset = _FakeFlowImageCDPClient(
        pane_text="Generating will use 0 credits",
        warn=False,
        initial_family="",
    )
    selected_targets: list[str] = []

    async def _fake_find_point_ok(c: Any, sel: str, text: str = "", exact: bool = False) -> tuple[int, int] | None:
        if text == FLOW_ZERO_CREDIT_IMAGE_MODEL:
            selected_targets.append(text)
            c.family = c.after_click_family
        return (220, 340)

    monkeypatch.setattr(flow_ingredients, "find_point", _fake_find_point_ok)
    cfg = asyncio.run(flow_ingredients.configure_flow_zero_credit_image_mode(client_unset, aspect="9:16", batch_count=4))
    assert FLOW_ZERO_CREDIT_IMAGE_MODEL in selected_targets
    assert cfg["zero_credit_verified"] is True
    assert cfg["output_count"] == 4


def test_generate_flow_image_batch_refuses_to_save_or_register_when_candidates_fail_dhash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    async def _fast_sleep(_sec: float) -> None:
        return None

    monkeypatch.setattr(flow_ingredients.asyncio, "sleep", _fast_sleep)

    # Build a 1080x1920 image with rich high-frequency noise so PNG > 8KB, then pass its exact dHash as forbidden source
    rng = np.random.default_rng(42)
    bgr = rng.integers(30, 230, size=(1920, 1080, 3), dtype=np.uint8)
    ok_enc, png_buf = cv2.imencode(".png", bgr)
    assert ok_enc and len(png_buf) > 8_000
    png_bytes = png_buf.tobytes()
    forbidden_dhash = _dhash_64(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))

    fake_urls = [
        "https://flow-content.google/image/cand_1.png",
        "https://flow-content.google/image/cand_2.png",
    ]
    client = _FakeFlowImageCDPClient(
        pane_text="Generating will use 0 credits",
        warn=False,
        initial_family="beluga_display",
        rendered_urls=fake_urls,
    )

    class _FakeResp:
        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return png_bytes

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: _FakeResp())
    registered_calls: list[str] = []
    import pipeline.reference_image_qa as rqa

    async def _noop_clear(_c: Any) -> None:
        return None

    monkeypatch.setattr(flow_ingredients, "clear_prompt_ingredients", _noop_clear)
    monkeypatch.setattr(rqa, "register_reference_image", lambda *a, **kw: registered_calls.append("called"))

    out_png = tmp_path / "ref_s01_start.png"
    res = asyncio.run(
        flow_ingredients.generate_flow_image_batch(
            client,
            prompt="Porcelain figure seated in bright laboratory room",
            out_path=out_png,
            aspect="9:16",
            batch_count=2,
            project_dir=tmp_path,
            source_dhashes=[forbidden_dhash],
        )
    )
    assert res["ok"] is False
    assert res["saved"] is False
    assert not out_png.exists()
    assert registered_calls == []


def test_cmd_longform_assemble_end_to_end_4k_mp4_tpad_and_thumbnails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(config, "PROJECTS_DIR", str(tmp_path))
    monkeypatch.setattr(longform_assembler, "PROJECTS_DIR", str(tmp_path))
    monkeypatch.setattr(thumbnail_studio, "PROJECTS_DIR", str(tmp_path))

    proj_dir = tmp_path / "lf_test_01"
    vis_dir = proj_dir / "03_visuals" / "flow_native_clips"
    aud_dir = proj_dir / "04_audio"
    vis_dir.mkdir(parents=True)
    aud_dir.mkdir(parents=True)

    # Create 3 short 16:9 native clips (12 frames @ 24fps = 0.50s each -> 1.50s total video)
    for idx, color in enumerate([(220, 210, 195), (195, 215, 225), (210, 225, 205)], start=1):
        mp4_path = vis_dir / f"clip_{idx}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(mp4_path), fourcc, 24.0, (640, 360))
        for f_i in range(12):
            frame = np.full((360, 640, 3), color, dtype=np.uint8)
            cv2.circle(frame, (160 + f_i * 18, 180), 48, (80, 110, 160), -1)
            writer.write(frame)
        writer.release()

    (proj_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "clips": [
                    {"index": 1, "act": 1},
                    {"index": 2, "act": 1},
                    {"index": 3, "act": 2, "chapter_break": True},
                ]
            }
        ),
        encoding="utf-8",
    )

    # Create a 2.40s 48kHz stereo WAV narration (> 1.50s video so tpad MUST preserve full audio without -shortest cutoff)
    wav_path = aud_dir / "audio_master.wav"
    sr = 48000
    n_samples = int(sr * 2.40)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for n in range(n_samples):
            val = int(6000.0 * math.sin(2.0 * math.pi * 220.0 * (n / sr)))
            frames.extend(struct.pack("<hh", val, val))
        wf.writeframes(bytes(frames))

    cli.cmd_longform_assemble(argparse.Namespace(project="lf_test_01", hook_text="WHY SILENT BABIES RACE"))

    out_mp4 = proj_dir / "05_assembly" / "final_longform_3840x2160.mp4"
    rep_path = proj_dir / "05_assembly" / "longform_assembly_report.json"
    assert out_mp4.exists() and out_mp4.stat().st_size > 10_000
    assert rep_path.exists()
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    assert rep["passed"] is True
    assert rep["chapter_starts"] == [0, 2]

    cap = cv2.VideoCapture(str(out_mp4))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    fc = float(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    assert (w, h) == (LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT)
    assert abs(fps - LONGFORM_VIDEO_FPS) < 0.5
    # Video stream was padded to cover the full 2.40s narration rather than truncated at 1.50s
    assert (fc / fps) >= 2.35

    for v in ("A", "B", "C"):
        t_png = proj_dir / "06_publish" / f"thumb_longform_{v}.png"
        assert t_png.exists()
        im = cv2.imread(str(t_png))
        assert im is not None
        assert (im.shape[1], im.shape[0]) == (LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT)


def test_porcelain_rebalanced_queue_65_of_65_gate_clean_and_authentic_descriptions():
    from pipeline.flow_prompt_builder import build_flow_prompts
    from pipeline.publish import validate_diorama_paradox_title

    q_path = Path(config.CHANNEL_ROOT) / "porcelain_rebalanced_queue.json"
    assert q_path.exists()
    q = json.loads(q_path.read_text(encoding="utf-8"))
    ready = q["queue"]
    assert len(ready) == 65

    slugs = {it["slug"] for it in ready}
    assert "phineas_gage_iron_rod" not in slugs
    assert not (Path(DOSSIERS_DIR) / "phineas_gage_iron_rod" / "diorama_v7_porcelain").exists()

    for it in ready:
        assert it["pillar"] in PILLAR_DEFAULT_STYLE_MAP
        pdir = Path(it["porcelain_dir"])
        plan, narrations, script_doc = cli._load_gate_inputs(pdir)
        clips = build_flow_prompts(plan, narrations)
        issues = list(validate_production_diorama_v6(plan, narrations, clips, script_doc=script_doc))
        raw_title = str(script_doc.get("title") or plan.get("title") or "").strip()
        if raw_title:
            issues.extend(validate_diorama_paradox_title(raw_title))
        assert issues == [], f"{it['slug']} failed prompt-gate: {issues}"
        sc = json.loads((pdir / "script.json").read_text(encoding="utf-8"))
        md = json.loads((pdir / "metadata.json").read_text(encoding="utf-8"))
        act_sents = [s for a in sc.get("acts", []) for s in a.get("sentences", [])]
        if act_sents:
            assert act_sents == sc["sentences"], f"{it['slug']} acts != sentences"
        desc = md.get("description", "")
        assert not desc.startswith("experiment_chronicle"), f"{it['slug']} leaked template ID"
        assert ". . ." not in desc, f"{it['slug']} leaked empty citation dots"
        assert "-  (" not in desc, f"{it['slug']} leaked empty author citation"


def test_community_line1_question_above_fold_and_reenact_dossier_lookup():
    d_dir = _find_matching_dossier_dir("reenact_01_ainsworth_strange_situation")
    assert d_dir is not None and d_dir.name == "ainsworth_strange_situation"

    cm = CommunityManager()
    pkg = cm.prepare_comment_content("reenact_01_ainsworth_strange_situation")
    comment = pkg["comment_text"]
    lines = [ln.strip() for ln in comment.splitlines() if ln.strip()]
    assert len(lines) >= 2
    assert lines[0].endswith("?"), f"Line 1 must be the viewer question above mobile fold, got: {lines[0]!r}"
    assert "https://doi.org/10.2307/1127388" in comment


def test_editorial_description_and_metadata_sanitizer_parse_real_dossier_citations():
    desc, tags, doi = build_editorial_description_from_dossier(
        project_id="diorama_78_ramachandran_synesthesia_cross_wiring",
        pillar="brain_basics",
        slug="ramachandran_synesthesia_cross_wiring",
        script_doc={"doi": "10.1098/rspb.2000.1576"},
    )
    assert "Ramachandran" in desc
    assert ". . ." not in desc
    assert "-  (" not in desc
    assert "fusiform face area" in desc or "primary visual cortex" in desc
    assert doi == "10.1098/rspb.2000.1576"
    assert "#Shorts" in tags

    # Overlong non-clone title is capped <= TITLE_MAX_CHARS_DIORAMA
    long_title = "Skeptics Called Colored Numbers Fake Poetry, Yet Synesthetes Crushed a One-Second Camouflage Test"
    assert len(long_title) > TITLE_MAX_CHARS_DIORAMA
    capped = diversify_clone_title(long_title, index_seed=2)
    assert len(capped) <= TITLE_MAX_CHARS_DIORAMA

    # build_diversified_description synthesizes from dossier rather than copying script sentences verbatim
    div_desc = build_diversified_description(
        project_id="reenact_01_ainsworth_strange_situation",
        metadata={"title": "1970 Strange Situation: Why Quiet Babies Hid Racing Hearts", "doi": "10.2307/1127388"},
        script={
            "dossier": "ainsworth_strange_situation",
            "sentences": ["UNIQUE_SCRIPT_SENTENCE_ONE_DO_NOT_COPY!", "UNIQUE_SCRIPT_SENTENCE_TWO_DO_NOT_COPY!"],
        },
        index_seed=1,
    )
    assert "UNIQUE_SCRIPT_SENTENCE_ONE_DO_NOT_COPY" not in div_desc
    assert "https://doi.org/10.2307/1127388" in div_desc


def test_watchdog_cleanup_idle_whale_tabs_and_news_radar_canonical_pillars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fake_targets = [
        {"id": "t_flow", "type": "page", "url": "https://labs.google/fx/tools/flow/project/abc"},
        {"id": "t_blank", "type": "page", "url": "about:blank"},
        {"id": "t_studio_1", "type": "page", "url": "https://studio.youtube.com/video/VID1/edit"},
        {"id": "t_studio_2", "type": "page", "url": "https://studio.youtube.com/video/VID2/edit"},
    ]
    closed_urls: list[str] = []

    class _Resp:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *a: Any) -> None:
            return None

        def read(self) -> bytes:
            return self._payload

    import urllib.request

    def _fake_urlopen(url: str, timeout: float = 2.0) -> _Resp:
        if url.endswith("/json/list"):
            return _Resp(json.dumps(fake_targets).encode("utf-8"))
        closed_urls.append(url)
        return _Resp(b"Target is closing")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    res = cleanup_idle_whale_tabs(cdp_port=9222, dry_run=False)
    assert res["cdp_reachable"] is True
    assert set(res["closed"]) == {"t_blank", "t_studio_2"}
    assert not any("t_flow" in u or "t_studio_1" in u for u in closed_urls)

    # Verify news_radar only emits canonical 7 pillars (never 'bci_medicine')
    monkeypatch.setattr(news_radar, "NEURO_NEWS_STAGING_DIR", str(tmp_path / "news_staging"))
    rep = news_radar.scan_breaking_neuro_news(
        offline_items=[
            {"DOI": "10.1038/s41591-026-00001-1", "title": ["Closed-loop deep brain stimulation clinical trial for depression"]},
            {"DOI": "10.1038/s41586-026-00002-2", "title": ["Intracortical brain-computer interface decoding speech"]},
            {"DOI": "10.1126/science.2026.00003", "title": ["Hippocampal sharp-wave ripple consolidation in macaques"]},
        ]
    )
    assert len(rep["candidates"]) == 3
    for cand in rep["candidates"]:
        assert cand["pillar"] in PILLAR_DEFAULT_STYLE_MAP, f"Non-canonical pillar {cand['pillar']!r}"
