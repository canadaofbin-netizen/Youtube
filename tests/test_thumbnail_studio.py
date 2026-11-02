"""
Unit & integration tests for R65 Thumbnail Studio & In-Video Cover Frame (`pipeline/thumbnail_studio.py`).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import warnings

import cv2
import numpy as np
from PIL import Image, ImageDraw
import pytest

from pipeline import config as cfg
from pipeline import thumbnail_studio as ts
from pipeline.flow_prompt_builder import build_diorama_v7_prompts
from pipeline.prompt_quality_v5 import validate_production_diorama_v6, validate_thumbnail_block_v7
from pipeline.storage import ProjectStorage
from pipeline.studio.ab_tester import ThumbnailABTester
from pipeline.studio.uploader import StudioUploader, verify_publish_ready_qa_bundle


ROOT = Path(cfg.WORKSPACE_ROOT)


def _write_synthetic_clip(path: Path, kind: str, seed: int) -> None:
    """Writes a 1.5s 540x960 @ 24fps MP4 clip (`sharp_a`, `sharp_b`, `sharp_c`, `blurred`, `flat`, `split_src`)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = 540, 960
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (w, h))
    rng = np.random.default_rng(seed)

    for f_idx in range(36):
        if kind == "flat":
            frame = np.full((h, w, 3), 185, dtype=np.uint8)
        elif kind == "blurred":
            base = np.full((h, w, 3), (210, 205, 195), dtype=np.uint8)
            cv2.circle(base, (w // 2, h // 2), 140, (150, 145, 140), -1)
            frame = cv2.GaussianBlur(base, (51, 51), 18.0)
        else:
            palettes = {
                "sharp_a": ((226, 214, 198), (44, 62, 94), (214, 96, 68), (245, 240, 230)),
                "sharp_b": ((196, 224, 212), (32, 82, 68), (230, 168, 52), (52, 46, 74)),
                "sharp_c": ((214, 202, 228), (74, 42, 98), (72, 164, 196), (242, 224, 184)),
                "split_src": ((205, 215, 225), (60, 75, 95), (180, 110, 80), (240, 235, 225)),
            }
            bg, c1, c2, c3 = palettes.get(kind, palettes["sharp_a"])
            frame = np.full((h, w, 3), bg, dtype=np.uint8)
            # Crisp central 3:4 low-poly faceted subject (x in 95..445, y in 260..700) keeping border clean
            shift = (f_idx % 6) * 2
            pts_outer = np.array(
                [[140 + shift, 310], [400, 290 + shift], [430, 560], [270, 680], [115, 545]],
                dtype=np.int32,
            )
            cv2.fillPoly(frame, [pts_outer], c1)
            cv2.polylines(frame, [pts_outer], True, (18, 22, 28), 4, lineType=cv2.LINE_AA)
            # Dense internal geometric facets inside centre 3:4 box for crisp focus & high contrast
            for r_i in range(5):
                for c_i in range(4):
                    x0 = 155 + c_i * 58 + ((r_i + c_i) % 2) * 6
                    y0 = 335 + r_i * 58
                    tri = np.array([[x0, y0], [x0 + 46, y0 + 10], [x0 + 22, y0 + 48]], dtype=np.int32)
                    col = c2 if (r_i + c_i) % 2 == 0 else c3
                    cv2.fillPoly(frame, [tri], col)
                    cv2.polylines(frame, [tri], True, (15, 20, 26), 2, lineType=cv2.LINE_AA)
            # Subtle film micro-grain inside centre subject so PNG exceeds 80KB naturally
            noise = rng.integers(-6, 7, size=(420, 320, 3), dtype=np.int16)
            sub = frame[280:700, 110:430].astype(np.int16) + noise
            frame[280:700, 110:430] = np.clip(sub, 0, 255).astype(np.uint8)
        writer.write(frame)
    writer.release()


def _seed_diorama_v7_thumb_project(tmp_path: Path) -> Path:
    projects_dir = tmp_path / "projects"
    storage = ProjectStorage(
        "diorama_99_thumb_studio_unit",
        title="You Sit Completely Still, Yet Watching Someone Grab Food Fires Your Motor Cortex",
        pillar="brain_basics",
        projects_dir=projects_dir,
    )
    p_dir = storage.project_dir
    clips_dir = storage.get_stage_dir("03_visuals") / "flow_native_clips"

    _write_synthetic_clip(clips_dir / "clip_1.mp4", "blurred", seed=1)
    _write_synthetic_clip(clips_dir / "clip_2.mp4", "flat", seed=2)
    _write_synthetic_clip(clips_dir / "clip_3.mp4", "sharp_a", seed=3)      # Cover sentence 3 (hero!)
    _write_synthetic_clip(clips_dir / "clip_4.mp4", "sharp_b", seed=4)      # Distinct sharp #2
    _write_synthetic_clip(clips_dir / "clip_5.mp4", "sharp_c", seed=5)      # Distinct sharp #3
    _write_synthetic_clip(clips_dir / "clip_6.mp4", "split_src", seed=6)    # Used in split_hstack & outro

    script_doc = {
        "schema": 7,
        "schema_version": 7,
        "profile": "neuro_diorama",
        "style_profile": "lowpoly_pastel_v7",
        "title": "You Sit Completely Still, Yet Watching Someone Grab Food Fires Your Motor Cortex",
        "sentences": [
            "You flinch when a stranger stubs a toe, yet you stayed still!",
            "Yet one lab snack proved movement cells fire just by watching!",
            "This is the true story of Giacomo Rizzolatti's Mirror Neuron Discovery.",
            "Here is what went wrong with brain maps.",
            "The motor cortex fired identically.",
            "Which proves watching rehearses action.",
        ],
    }
    visual_plan = {
        "schema": 7,
        "schema_version": 7,
        "profile": "neuro_diorama",
        "style_profile": "lowpoly_pastel_v7",
        "dossier": "new_r65_unit_dossier",
        "thumbnail": {
            "hook_text": "WATCHING = MOVING?",
            "cover_sentence_index": 3,
            "cover_brief": "lab macaque reaching for a raisin centered in pastel lab",
        },
        "chapter_headlines": [
            {"sentence_index": 1, "text": "STILL BODY?"},
            {"sentence_index": 3, "text": "WATCHING = MOVING?"},
        ],
    }
    edl = {
        "schema": 7,
        "profile": "neuro_diorama",
        "style_profile": "lowpoly_pastel_v7",
        "fps": 24,
        "total_duration_sec": 12.0,
        "cuts": [
            {"cut_index": 1, "act": 1, "sentence_index": 1, "end_sentence_index": 1, "mode": "single", "out_start_sec": 0.0, "out_end_sec": 2.0, "frames": 48, "clip_index": 1, "src_start_sec": 0.1, "src_end_sec": 1.3, "grammar": "lowpoly_hands_closeup"},
            {"cut_index": 2, "act": 1, "sentence_index": 2, "end_sentence_index": 2, "mode": "single", "out_start_sec": 2.0, "out_end_sec": 4.0, "frames": 48, "clip_index": 2, "src_start_sec": 0.1, "src_end_sec": 1.3, "grammar": "lowpoly_hands_closeup"},
            {"cut_index": 3, "act": 1, "sentence_index": 3, "end_sentence_index": 3, "mode": "single", "out_start_sec": 4.0, "out_end_sec": 6.0, "frames": 48, "clip_index": 3, "src_start_sec": 0.1, "src_end_sec": 1.3, "grammar": "lowpoly_fullbleed_world"},
            {"cut_index": 4, "act": 3, "sentence_index": 4, "end_sentence_index": 4, "mode": "single", "out_start_sec": 6.0, "out_end_sec": 8.0, "frames": 48, "clip_index": 4, "src_start_sec": 0.1, "src_end_sec": 1.3, "grammar": "lowpoly_matte_brain", "anatomy_label": "MOTOR CORTEX"},
            {"cut_index": 5, "act": 4, "sentence_index": 5, "end_sentence_index": 5, "mode": "single", "out_start_sec": 8.0, "out_end_sec": 9.5, "frames": 36, "clip_index": 5, "src_start_sec": 0.1, "src_end_sec": 1.3, "grammar": "lowpoly_literal_analogy"},
            {"cut_index": 6, "act": 5, "sentence_index": 5, "end_sentence_index": 5, "mode": "split_hstack", "out_start_sec": 9.5, "out_end_sec": 10.8, "frames": 31, "clip_index": 6, "secondary_clip_index": 3, "secondary_src_span": [0.1, 1.2], "src_start_sec": 0.1, "src_end_sec": 1.2, "grammar": "lowpoly_hands_closeup"},
            {"cut_index": 7, "act": 6, "sentence_index": 6, "end_sentence_index": 6, "mode": "single", "outro_sky_card": True, "out_start_sec": 10.8, "out_end_sec": 12.0, "frames": 29, "clip_index": 6, "src_start_sec": 0.1, "src_end_sec": 1.2, "grammar": "lowpoly_fullbleed_world"},
        ],
    }

    storage.save_json("02_script", "script.json", script_doc)
    storage.save_json("03_visuals", "visual_plan.json", visual_plan)
    storage.save_json("05_assembly", "edit_decision_list.json", edl)
    storage.save_json(
        "06_publish",
        "metadata.json",
        {
            "title": script_doc["title"],
            "description": "DOI: 10.1007/BF00230027",
            "profile": "neuro_diorama",
            "video_language": "en-US",
            "title_description_language": "en-US",
            "channel_residence_country": "KR",
            "target_audience_region": "US",
        },
    )
    # Write a valid final MP4 stub for SHA-256 binding
    final_mp4 = storage.get_stage_dir("05_assembly") / "final_shorts_1080x1920.mp4"
    shutil_bytes = (clips_dir / "clip_3.mp4").read_bytes() * 20
    final_mp4.write_bytes(shutil_bytes[: max(len(shutil_bytes), 1_200_000)])
    return p_dir


def test_r65_ssot_constants_and_docs_parity() -> None:
    constants_md = (ROOT / ".agents" / "rules" / "production_constants.md").read_text(encoding="utf-8")
    diorama_md = (ROOT / ".agents" / "rules" / "neuro_diorama_rules.md").read_text(encoding="utf-8")
    studio_md = (ROOT / ".agents" / "rules" / "youtube_studio_operations.md").read_text(encoding="utf-8")
    agents_md = (ROOT / ".agents" / "AGENTS.md").read_text(encoding="utf-8")

    required_names = (
        "THUMBNAIL_REPORT_FILENAME",
        "THUMBNAIL_CONTACT_SHEET_FILENAME",
        "THUMB_CANDIDATE_SAMPLES_PER_CUT",
        "THUMB_EXCLUDE_MODES",
        "THUMB_EXCLUDE_OUTRO",
        "THUMB_SCORE_WEIGHTS",
        "THUMB_INTENT_BONUS",
        "THUMB_MIN_SHARPNESS",
        "THUMB_MIN_LUMA_STD",
        "THUMB_MIN_CENTER_SALIENCE",
        "THUMB_MIN_PAIRWISE_DIFF",
        "THUMB_MIN_TEXT_CONTRAST",
        "THUMB_LEGIBILITY_PREVIEW_W",
        "THUMB_SAFE_Y_RANGE",
        "THUMB_SAFE_MARGIN_X",
        "THUMB_HOOK_MAX_WORDS",
        "THUMB_HOOK_MAX_CHARS",
        "THUMB_HOOK_FONT_SIZE_RANGE",
        "THUMB_HOOK_STROKE_PX",
        "THUMB_MIN_FILE_BYTES",
        "DIORAMA_V7_REQUIRE_THUMBNAIL_BLOCK",
    )
    for name in required_names:
        assert hasattr(cfg, name), f"Missing {name} in pipeline/config.py"
        assert name in constants_md, f"Missing {name} in production_constants.md"
    assert "## R65 — Thumbnail Studio" in diorama_md
    assert "not_applicable_shorts" in studio_md
    assert "| R65 |" in agents_md


def test_thumbnail_studio_candidate_scoring_distinctness_and_qa(tmp_path: Path) -> None:
    p_dir = _seed_diorama_v7_thumb_project(tmp_path)

    cands = ts.collect_candidates(p_dir)
    # Cuts 6 (split_hstack) and 7 (outro_sky_card) must never enter candidate pool
    cand_cut_ids = {c.cut_index for c in cands}
    assert 6 not in cand_cut_ids
    assert 7 not in cand_cut_ids

    rep = ts.run(p_dir, force=True, strict=True)
    assert rep["passed"] is True, f"Expected TQ1-TQ7 pass, got: {rep['failed_gates']}"
    assert rep["hook_text"] == "WATCHING = MOVING?"
    assert rep["hook_source"] == "visual_plan.thumbnail"
    assert 4.0 <= float(rep["cover_frame_sec"]) <= 6.0

    chosen_clips = [rep["variants"][k]["clip_index"] for k in ("A", "B", "C")]
    assert len(set(chosen_clips)) == 3
    # Blurred clip 1 and flat clip 2 must never be selected
    assert 1 not in chosen_clips and 2 not in chosen_clips
    # Cover sentence clip 3 should win Variant A
    assert rep["variants"]["A"]["clip_index"] == 3

    pub_dir = p_dir / "06_publish"
    assert (pub_dir / "thumbnail_contact_sheet.png").exists()
    assert (pub_dir / "thumbnail.png").exists()
    for k in ("A", "B", "C"):
        p_png = pub_dir / f"thumbnail_var_{k}.png"
        assert p_png.exists() and p_png.stat().st_size > cfg.THUMB_MIN_FILE_BYTES
    assert rep["gates"]["TQ5_pairwise_distinct"]["ab_diff"] >= cfg.THUMB_MIN_PAIRWISE_DIFF
    assert rep["gates"]["TQ5_pairwise_distinct"]["bc_diff"] >= cfg.THUMB_MIN_PAIRWISE_DIFF
    assert rep["gates"]["TQ5_pairwise_distinct"]["ac_diff"] >= cfg.THUMB_MIN_PAIRWISE_DIFF


def test_hook_resolution_priority_and_tq1_tq7_failures() -> None:
    script = {"title": "You Sit Completely Still, Yet Watching Someone Grab Food Fires Your Motor Cortex"}
    # 1. Explicit thumbnail block wins
    h1, s1 = ts.resolve_hook(
        {"thumbnail": {"hook_text": "MIRROR CELLS?"}, "chapter_headlines": [{"sentence_index": 1, "text": "STILL BODY?"}]},
        script,
    )
    assert (h1, s1) == ("MIRROR CELLS?", "visual_plan.thumbnail")

    # 2. Chapter headline fallback when thumbnail block absent
    h2, s2 = ts.resolve_hook({"chapter_headlines": [{"sentence_index": 1, "text": "STILL BODY?"}]}, script)
    assert (h2, s2) == ("STILL BODY?", "chapter_headlines")

    # 3. Complementary title fallback when both absent (must pass TQ7 and avoid repeating opening words)
    h3, s3 = ts.resolve_hook({}, script)
    assert s3 == "title_fallback"
    assert ts.validate_hook_lexical(h3, title=script["title"]) == []

    # 4. TQ7 rejects overly long hook, >4 words, lowercase, and title prefix repetition
    assert ts.validate_hook_lexical("THIS HOOK IS WAY TOO LONG FOR MOBILE", title=script["title"])
    assert ts.validate_hook_lexical("You Sit Completely", title=script["title"])
    assert "hook_repeats_title_opening_prefix" in ts.validate_hook_lexical("YOU SIT COMPLETELY", title=script["title"])

    # 5. TQ1 rejects low-contrast unstroked grey-on-grey text at 160px shelf width
    low_c_img = Image.new("RGB", (cfg.VIDEO_WIDTH, cfg.VIDEO_HEIGHT), (150, 150, 150))
    mask = Image.new("L", (cfg.VIDEO_WIDTH, cfg.VIDEO_HEIGHT), 0)
    d_img = ImageDraw.Draw(low_c_img)
    d_msk = ImageDraw.Draw(mask)
    fnt = ImageDraw.Draw(low_c_img).getfont()
    f_path = ts._resolve_v7_font_path()
    from PIL import ImageFont

    big_font = ImageFont.truetype(str(f_path), 120)
    d_img.text((220, 320), "LOW CONTRAST", fill=(168, 168, 168), font=big_font)
    d_msk.text((220, 320), "LOW CONTRAST", fill=255, font=big_font)
    _ = fnt
    wcag_low = ts.measure_shelf_text_contrast(low_c_img, np.array(mask, dtype=np.uint8))
    assert wcag_low < cfg.THUMB_MIN_TEXT_CONTRAST


def test_validate_thumbnail_block_v7_and_hero_prompt_clause() -> None:
    script = {"title": "You Sit Completely Still, Yet Watching Someone Grab Food Fires Your Motor Cortex"}
    # Missing block
    assert any("[thumbnail_v7]" in e for e in validate_thumbnail_block_v7({}, script))

    # Mismatched chapter_headlines at cover_sentence_index
    bad_plan = {
        "thumbnail": {"hook_text": "WATCHING = MOVING?", "cover_sentence_index": 3},
        "chapter_headlines": [{"sentence_index": 3, "text": "PARMA 1992"}],
    }
    errs = validate_thumbnail_block_v7(bad_plan, script)
    assert any("chapter_headlines must include" in e for e in errs)

    # Bad cover_sentence_index outside cold-open 1..3
    bad_idx_plan = {
        "thumbnail": {"hook_text": "WATCHING = MOVING?", "cover_sentence_index": 9},
        "chapter_headlines": [{"sentence_index": 9, "text": "WATCHING = MOVING?"}],
    }
    assert any("cover_sentence_index" in e for e in validate_thumbnail_block_v7(bad_idx_plan, script))

    # Valid block passes and injects R63-compliant hero composition clause on sentence 3 fullbleed clip
    base_clips = [
        {
            "sentence_index": i,
            "act": min(6, (i - 1) // 10 + 1),
            "location_id": "lab_a" if i % 2 else "lab_b",
            "grammar": "lowpoly_fullbleed_world",
            "camera": "locked_tripod",
            "environment": "a sunlit pastel Parma neuroscience laboratory with pale-wood desks",
            "action": "clothed low-poly researchers in white coats observe a seated macaque reaching cleanly for a raisin",
            "lighting": "soft bright diffused pastel daylight",
        }
        for i in range(1, 58)
    ]
    good_plan = {
        "schema": 7,
        "schema_version": 7,
        "profile": "neuro_diorama",
        "style_profile": "lowpoly_pastel_v7",
        "thumbnail": {"hook_text": "WATCHING = MOVING?", "cover_sentence_index": 3, "cover_brief": "raisin reach"},
        "chapter_headlines": [{"sentence_index": 3, "text": "WATCHING = MOVING?"}],
        "clips": base_clips,
    }
    assert validate_thumbnail_block_v7(good_plan, script) == []
    rendered = build_diorama_v7_prompts(good_plan)
    assert "single focal subject centered in crisp silhouette" in rendered[2]["scene"].lower()
    assert "single focal subject centered in crisp silhouette" not in rendered[0]["scene"].lower()


def test_shorts_ab_tester_retire_and_uploader_cover_receipt(tmp_path: Path) -> None:
    p_dir = _seed_diorama_v7_thumb_project(tmp_path)
    projects_dir = p_dir.parent
    pid = p_dir.name

    rep = ts.run(p_dir, force=True, strict=True)
    assert rep["passed"] is True

    # Seed QA bundle reports so StudioUploader.prepare_upload_payload runs full QA lock
    asm_dir = p_dir / "05_assembly"
    final_mp4 = asm_dir / "final_shorts_1080x1920.mp4"
    mp4_sha = hashlib.sha256(final_mp4.read_bytes()).hexdigest()
    edl_sha = hashlib.sha256((asm_dir / "edit_decision_list.json").read_bytes()).hexdigest()
    (asm_dir / "video_autopsy_report.json").write_text(json.dumps({"passed": True, "final_mp4_sha256": mp4_sha}), encoding="utf-8")
    (asm_dir / "dynamic_episode_qa_report.json").write_text(json.dumps({"passed": True, "final_mp4_sha256": mp4_sha}), encoding="utf-8")
    (asm_dir / cfg.POSTHOC_SEMANTIC_QA_REPORT_FILENAME).write_text(
        json.dumps({"passed": True, "final_mp4_sha256": mp4_sha, "edl_sha256": edl_sha, "cut_count": 7, "cuts": [{"cut_index": i} for i in range(1, 8)]}),
        encoding="utf-8",
    )
    distinct_notes = [
        "Over-shoulder wooden desk shows two gloved hands pausing above four color-coded card decks.",
        "Macro tabletop view reveals brass calipers measuring sweat response tracing across warm cream paper.",
        "Wide sunlit laboratory corridor frames faceted researcher walking past pastel mint filing cabinets.",
        "Split comparison screen contrasts erratic red gambling stack against calm blue conservative deck.",
        "Translucent pastel brain model highlights ventromedial prefrontal cortex glowing coral above desk.",
        "Close tactile angle captures index finger hesitating over risky deck before sliding right.",
        "Final wide room pull-back holds steady over balanced card stacks under warm gallery window.",
    ]
    (asm_dir / cfg.POSTHOC_SEMANTIC_REVIEW_FILENAME).write_text(
        json.dumps(
            {
                "project_id": pid,
                "schema": "R64_posthoc_semantic_review_v1",
                "review_origin": "manual_or_vlm_template",
                "final_mp4_sha256": mp4_sha,
                "edl_sha256": edl_sha,
                "cut_count": 7,
                "cuts": [
                    {
                        "cut_index": i,
                        "clip_index": min(6, i),
                        "auto_populated": False,
                        "expresses_intended_meaning": True,
                        "action_needed": "none",
                        "observed_visual_summary": distinct_notes[i - 1],
                    }
                    for i in range(1, 8)
                ],
            }
        ),
        encoding="utf-8",
    )
    ProjectStorage.sync_existing_manifest_from_disk(p_dir, status="ASSEMBLED")

    # 1. ThumbnailABTester returns not_applicable_shorts on neuro_diorama Shorts
    tester = ThumbnailABTester(cdp_port=9222, projects_dir=projects_dir)
    swap_res = tester.swap_to_variant(pid, "B", dry_run=True)
    assert swap_res["status"] == "not_applicable_shorts"
    assert swap_res["swap_success"] is False

    # 2. StudioUploader deprecates & skips --burn-first-frame on neuro_diorama and writes cover_frame_sec receipt
    uploader = StudioUploader(cdp_port=9222, projects_dir=projects_dir)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        payload = uploader.prepare_upload_payload(pid, visibility="unlisted", burn_first_frame=True)
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert "burnin" not in payload["video_path"].name
    assert payload["cover_frame_sec"] == rep["cover_frame_sec"]

    receipt = uploader.upload_project(pid, visibility="unlisted", dry_run=True)
    assert receipt["cover_frame_sec"] == rep["cover_frame_sec"]
    assert receipt["cover_action"] == "select_frame_in_mobile_app"

    # 3. Failing thumbnail_report.json blocks production upload but warns on backfill_soft
    rep_path = p_dir / "06_publish" / cfg.THUMBNAIL_REPORT_FILENAME
    bad_rep = dict(rep, passed=False, failed_gates=["TQ7_hook_lexical"], mode="production")
    rep_path.write_text(json.dumps(bad_rep), encoding="utf-8")
    ProjectStorage.sync_existing_manifest_from_disk(p_dir, status="ASSEMBLED")
    qa_hard = verify_publish_ready_qa_bundle(p_dir)
    assert qa_hard["passed"] is False
    assert any("thumbnail_qa_not_passed" in x for x in qa_hard["issues"])

    soft_rep = dict(bad_rep, mode="backfill_soft")
    rep_path.write_text(json.dumps(soft_rep), encoding="utf-8")
    ProjectStorage.sync_existing_manifest_from_disk(p_dir, status="ASSEMBLED")
    qa_soft = verify_publish_ready_qa_bundle(p_dir)
    assert qa_soft["passed"] is True
    assert qa_soft["warnings"]
