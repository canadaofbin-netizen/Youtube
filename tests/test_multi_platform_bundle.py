"""
Multi-Platform (YouTube Shorts + TikTok + Instagram Reels) Compatibility & Bundle Tests.

Verifies:
1. TikTok Creator Rewards `> 60.0s` duration contract (`SHORTS_EXPRESSIVE_V8_DURATION_MIN_SEC == 61.5`,
   `SHORTS_EXPRESSIVE_V8_DURATION_TARGET_RANGE_SEC == (62.0, 118.0)`).
2. 3-Platform Universal UI Safe-Zone Pixel Clamp (`Y >= 12%`, `Y < 68%`, `X <= 910px`) across all
   R70-M chart presets, legacy `bars` Data Stamps, and R71 `render_anatomy_callout_rgba_frame`
   (including extreme top/right/left edge inputs).
3. `export_multi_platform_bundle()` & `main.py multi-bundle --no-copy-video` output structure,
   zero-Hangul English copy, 4-5 TikTok niche hashtags (zero `#fyp`/`#viral`), Reels Line-1 `<= 90` chars
   + save/share CTA, `upload_checklist.json` fields, `fuse.rclone` zero-symlink guarantee, and
   preservation of YouTube `06_publish/metadata.json` R68 `0`-hashtag rule.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import pipeline.config as cfg
from pipeline.anatomy_overlay import render_anatomy_callout_rgba_frame
from pipeline.stamp_overlay import render_data_stamp_rgba_frame
from pipeline.publish import PublishStage, export_multi_platform_bundle
from pipeline.storage import ProjectStorage

HANGUL_RE = re.compile(r"[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]")
SPAM_TAGS = {"#fyp", "#viral", "#foryou", "#foryoupage", "#trending", "#shorts", "#reels", "#tiktok"}


def test_v8_tiktok_creator_rewards_duration_floor() -> None:
    assert cfg.SHORTS_EXPRESSIVE_V8_DURATION_MIN_SEC == 61.5
    assert cfg.SHORTS_EXPRESSIVE_V8_DURATION_TARGET_RANGE_SEC == (62.0, 86.0)
    assert cfg.shorts_duration_range_for_profile("shorts_expressive_v8") == (61.5, 88.0)
    assert cfg.shorts_duration_range_for_profile(
        "shorts_expressive_v8", project_id="v8_ep04_patient_sm_fearless_amygdala"
    ) == (61.5, 120.0)
    assert cfg.DATA_STAMP_Y_FRAC_RANGE == (0.12, 0.62)
    assert cfg.UNIVERSAL_SAFE_X_RIGHT_PX == 910


def test_universal_safe_zone_across_all_chart_presets_and_legacy_bars() -> None:
    width, height = 1080, 1920
    min_y_allowed = int(math.ceil(height * 0.12))
    max_y_exclusive = int(round(height * 0.68))
    max_x_allowed = cfg.UNIVERSAL_SAFE_X_RIGHT_PX

    chart_specs = [
        {
            "title": "Marshmallow Wait Time Comparison Across Conditions",
            "preset": "bar_compare",
            "mode": "study",
            "doi": "10.1016/j.cognition.2012.08.004",
            "source_citation": "Celeste Kidd, Holly Palmeri, Richard N. Aslin, Cognition (2013)",
            "multiplier_badge": "4×",
            "groups": [
                {"label": "Broken Promise", "mean": 3.02, "unit": "min"},
                {"label": "Kept Promise", "mean": 12.09, "unit": "min"},
            ],
        },
        {
            "title": "Group Conformity Rate",
            "preset": "arc_gauge",
            "mode": "study",
            "doi": "10.1037/h0093718",
            "source_citation": "Asch (1956)",
            "percent": 75.0,
        },
        {
            "title": "Waited Full 15 Minutes",
            "preset": "dot_array",
            "mode": "study",
            "doi": "10.1016/j.cognition.2012.08.004",
            "source_citation": "Kidd et al. (2013)",
            "highlighted_k": 9,
            "total_n": 14,
        },
        {
            "title": "Cortisol Spike & Recovery",
            "preset": "line",
            "mode": "study",
            "doi": "10.1016/j.psyneuen.2004.04.005",
            "source_citation": "Dickerson & Kemeny (2004)",
            "x_label": "Post-Stress Recovery Window",
            "y_label": "Cortisol",
            "layers": [
                {
                    "type": "line",
                    "series": [
                        {
                            "start_label": "Baseline",
                            "label": "Peak Cortisol Surge",
                            "values": [12.0, 28.5, 19.0, 26.4],
                            "unit": "nmol/L",
                        }
                    ],
                }
            ],
        },
        {
            "title": "Ebbinghaus Forgetting Curve Conceptual Decay",
            "preset": "curve_marker",
            "mode": "illustrative",
            "fn": "exp_decay",
            "x_label": "Elapsed Days",
            "y_label": "Memory Kept",
            "markers": [{"x": 4.8, "y": 0.18, "label": "Right Edge Inflection"}],
        },
        {
            "title": "Sleep Debt vs Reaction Lag",
            "preset": "scatter_fit",
            "mode": "illustrative",
            "x_label": "Awake Hours",
            "y_label": "Lapses",
            "r": 0.78,
            "n": 36,
        },
        # Legacy bar stamp path (no `preset` / `layers`)
        {
            "title": "Legacy Marshmallow Bar Stamp",
            "source_citation": "Kidd et al. (2013)",
            "multiplier_badge": "4×",
            "bars": [
                {"label": "Broken Promise", "value": 3.0, "unit": "min"},
                {"label": "Kept Promise", "value": 12.1, "unit": "min"},
            ],
        },
    ]

    for spec in chart_specs:
        rgba = render_data_stamp_rgba_frame(spec, t_rel=4.0, total_dur=4.8, width=width, height=height)
        arr = np.asarray(rgba, dtype=np.uint8)
        ys, xs = np.where(arr[:, :, 3] > 0)
        assert len(ys) > 0, f"Chart rendered empty alpha for {spec.get('preset', 'legacy_bars')}"
        assert int(ys.min()) >= min_y_allowed, f"Top safe-zone breach: min_y={ys.min()} < {min_y_allowed}"
        assert int(ys.max()) < max_y_exclusive, f"Subtitle zone breach: max_y={ys.max()} >= {max_y_exclusive}"
        assert int(xs.max()) <= max_x_allowed, f"Right UI rail breach: max_x={xs.max()} > {max_x_allowed}"


def test_universal_safe_zone_anatomy_callout_extreme_edges() -> None:
    width, height = 1080, 1920
    min_y_allowed = int(math.ceil(height * 0.12))
    max_y_exclusive = int(round(height * 0.68))
    min_x_allowed = 48
    max_x_allowed = cfg.UNIVERSAL_SAFE_X_RIGHT_PX

    edge_callouts = [
        # Extreme top-right label + far-right anchor
        {
            "cut_index": 14,
            "display_title": "Dorsolateral Prefrontal Cortex",
            "short_role": "Executive Impulse Brake",
            "anchor_xy": (0.94, 0.34),
            "label_xy": (0.92, 0.06),
            "accent_rgb": (72, 224, 255),
        },
        # Extreme top-left label
        {
            "cut_index": 15,
            "display_title": "Nucleus Accumbens",
            "short_role": "Immediate Reward Surge",
            "anchor_xy": (0.04, 0.08),
            "label_xy": (0.05, 0.07),
            "accent_rgb": (255, 112, 96),
        },
    ]
    for cal in edge_callouts:
        rgba = render_anatomy_callout_rgba_frame(cal, t_rel=1.2, total_dur=2.6, width=width, height=height)
        arr = np.asarray(rgba, dtype=np.uint8)
        ys, xs = np.where(arr[:, :, 3] > 0)
        assert len(ys) > 0
        assert int(ys.min()) >= min_y_allowed, f"Anatomy callout breached top 12%: min_y={ys.min()}"
        assert int(ys.max()) < max_y_exclusive, f"Anatomy callout breached subtitle 68%: max_y={ys.max()}"
        assert int(xs.min()) >= min_x_allowed, f"Anatomy callout breached left margin: min_x={xs.min()}"
        assert int(xs.max()) <= max_x_allowed, f"Anatomy callout breached right 910px rail: max_x={xs.max()}"


def test_export_multi_platform_bundle_and_youtube_zero_hashtag_isolation(tmp_path: Path) -> None:
    storage = ProjectStorage("v8_bundle_unit_test", projects_dir=tmp_path)
    p_dir = storage.project_dir
    for sub in ("02_script", "03_visuals", "05_assembly", "06_publish"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)

    long_hook_title = (
        "Why Broken Promises Crash Your Prefrontal Self-Control System Faster Than Any Late-Night Temptation Ever Could"
    )
    script_doc = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "project_id": "v8_bundle_unit_test",
        "everyday_domain": "habits",
        "title": long_hook_title,
        "doi": "10.1016/j.cognition.2012.08.004",
        "core_reveal_sentence_index": 2,
        "debate_question": "When your habits slip at night, is it weak willpower or broken self-trust?",
        "sentences": [
            "In the Rochester study, children who trusted the adult waited four times longer!",
            "Eating early was never weak willpower — it was smart survival math inside an unreliable room.",
        ],
    }
    storage.save_json("02_script", "script.json", script_doc)
    storage.save_json(
        "03_visuals",
        "visual_plan.json",
        {"schema": 8, "style_profile": "expressive_25d_v8", "format_profile": "shorts_expressive_v8"},
    )
    storage.save_json(
        "05_assembly",
        "probe_report.json",
        {"duration_sec": 68.4, "width": 1080, "height": 1920},
    )
    src_thumb = tmp_path / "cover_src.png"
    Image.new("RGB", (1080, 1920), (24, 38, 72)).save(src_thumb, format="PNG")

    stage = PublishStage(storage)
    run_res = stage.run(
        title="Why Broken Promises Crash Self-Control",
        hashtags=["#Shorts", "#Neuroscience"],
        doi="10.1016/j.cognition.2012.08.004",
        source_summary="Celeste Kidd et al. (2013) tested 28 preschoolers on environmental reliability.",
        thumbnail_source_img=src_thumb,
    )
    assert "multi_platform_bundle" in run_res

    dummy_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    dummy_mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x01" * 4096)

    # Rule R75: YouTube metadata.json carries ONLY clean trailing #shorts (zero topic/BCI hashtags)!
    yt_meta = storage.load_json("06_publish", "metadata.json")
    assert yt_meta is not None
    assert yt_meta["hashtags"] == ["#shorts"]
    assert yt_meta["description"].endswith("\n\n#shorts")
    assert "#" not in yt_meta["description"].removesuffix("#shorts")

    # Overwrite title with long hook in metadata to also verify Reels <=90-char Line-1 clamp
    yt_meta["title"] = long_hook_title
    yt_meta["everyday_domain"] = "habits"
    yt_meta["debate_question"] = script_doc["debate_question"]
    storage.save_json("06_publish", "metadata.json", yt_meta)

    bundle_out = export_multi_platform_bundle(p_dir, copy_video=True)
    bundle_dir = Path(bundle_out["bundle_dir"])
    assert bundle_dir == p_dir / "06_publish" / "multi_platform_bundle"

    expected_files = (
        "video_clean.mp4",
        "cover_9x16.png",
        "tiktok_caption.txt",
        "reels_caption.txt",
        "upload_checklist.json",
    )
    for fname in expected_files:
        fp = bundle_dir / fname
        assert fp.is_file(), f"Missing {fname} in bundle"
        assert not fp.is_symlink(), f"fuse.rclone violation: {fname} must be copied, never symlinked"
        assert fp.stat().st_size > 0

    # Verify TikTok caption rules (R68-D zero-DOI, zero-em-dash, Research: line)
    tiktok_txt = (bundle_dir / "tiktok_caption.txt").read_text(encoding="utf-8").strip()
    assert not HANGUL_RE.search(tiktok_txt), "TikTok caption must contain zero Hangul"
    tt_lines = [ln.strip() for ln in tiktok_txt.splitlines() if ln.strip()]
    assert "10.1016/j.cognition.2012.08.004" not in tiktok_txt
    assert "doi.org" not in tiktok_txt.lower()
    assert "—" not in tiktok_txt
    assert "Research:" in tiktok_txt
    assert script_doc["debate_question"] in tiktok_txt
    tt_tags = tt_lines[-1].split()
    assert 4 <= len(tt_tags) <= 5
    assert all(t.startswith("#") for t in tt_tags)
    assert SPAM_TAGS.isdisjoint(set(t.lower() for t in tt_tags))
    assert "#habits" in tt_tags

    # Verify Reels caption rules (Line 1 <= 90 chars + save/share CTA + 3-5 niche hashtags + zero DOI/em-dash)
    reels_txt = (bundle_dir / "reels_caption.txt").read_text(encoding="utf-8").strip()
    assert not HANGUL_RE.search(reels_txt), "Reels caption must contain zero Hangul"
    rl_lines = [ln.strip() for ln in reels_txt.splitlines() if ln.strip()]
    assert len(rl_lines[0]) <= 90, f"Reels line 1 exceeded 90-char fold: {len(rl_lines[0])}"
    assert "Save this for later & send it to someone curious about how the brain works." in reels_txt
    assert "10.1016/j.cognition.2012.08.004" not in reels_txt
    assert "doi.org" not in reels_txt.lower()
    assert "—" not in reels_txt
    assert "Research:" in reels_txt
    rl_tags = rl_lines[-1].split()
    assert 3 <= len(rl_tags) <= 5
    assert all(t.startswith("#") for t in rl_tags)
    assert SPAM_TAGS.isdisjoint(set(t.lower() for t in rl_tags))

    # Verify upload_checklist.json schema & exact file sizes
    chk = json.loads((bundle_dir / "upload_checklist.json").read_text(encoding="utf-8"))
    assert chk["project_id"] == "v8_bundle_unit_test"
    assert chk["duration_sec"] == 68.4
    assert chk["tiktok_over_60s_eligible"] is True
    assert chk["resolution"] == "1080x1920"
    assert chk["aigc_disclosure_required"] is True
    assert "NEVER use VPN" in chk["vpn_prohibited_warning"]
    for fname in expected_files:
        assert chk["files"][fname]["exists"] is True
        assert chk["files"][fname]["size_bytes"] == (bundle_dir / fname).stat().st_size

    # Verify YouTube metadata.json STILL preserves clean #shorts routing after bundle export
    yt_meta_after = storage.load_json("06_publish", "metadata.json")
    assert yt_meta_after["hashtags"] == ["#shorts"]

    # Verify CLI `main.py multi-bundle --no-copy-video`
    p2_dir = tmp_path / "v8_cli_nocopy_proj"
    for sub in ("02_script", "05_assembly", "06_publish"):
        (p2_dir / sub).mkdir(parents=True, exist_ok=True)
    (p2_dir / "05_assembly" / "probe_report.json").write_text(
        json.dumps({"duration_sec": 59.0, "width": 1080, "height": 1920}),
        encoding="utf-8",
    )
    (p2_dir / "05_assembly" / "final_shorts_1080x1920.mp4").write_bytes(b"\x00" * 512)
    Image.new("RGB", (1080, 1920), (30, 40, 60)).save(p2_dir / "06_publish" / "thumbnail.png", format="PNG")
    (p2_dir / "06_publish" / "metadata.json").write_text(
        json.dumps({"project_id": "v8_cli_nocopy_proj", "title": "Short Test Clip", "hashtags": []}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(cfg.WORKSPACE_ROOT / "main.py"), "multi-bundle", "--project", str(p2_dir), "--no-copy-video"],
        capture_output=True,
        text=True,
        check=True,
    )
    cli_out = json.loads(proc.stdout)
    assert cli_out["checklist"]["tiktok_over_60s_eligible"] is False
    assert cli_out["checklist"]["files"]["video_clean.mp4"]["exists"] is False
    assert (p2_dir / "06_publish" / "multi_platform_bundle" / "cover_9x16.png").is_file()


# --- Merged from test_multi_platform_bundle_v2.py + Phase A fallback checks ---
import pytest  # noqa: E402
from pipeline.instagram_cards import (  # noqa: E402
    CAROUSEL_4X5_HEIGHT,
    CAROUSEL_4X5_SAFE_MARGIN_X,
    CAROUSEL_4X5_WIDTH,
    CardSlide,
    render_carousel_4x5_slides,
    validate_slide_copy_safety,
)
from pipeline.publish import (  # noqa: E402
    build_youtube_community_quiz_payload,
    resolve_bundle_video_path,
    validate_youtube_community_quiz_payload,
)


def _build_synthetic_v8_project(tmp_path: Path) -> Path:
    p_dir = tmp_path / "v8_test_capgras_bundle_v2"
    for sub in ("02_script", "03_visuals", "04_audio", "05_assembly", "06_publish"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)

    script_doc = {
        "schema_version": "8.0",
        "style_profile": "expressive_25d_v8",
        "title": "Why Your Brain Calls Loved Ones Imposters",
        "doi": "10.1098/rspb.1997.0092",
        "citation": "Hirstein & Ramachandran (1997), Proc. R. Soc. Lond. B",
        "primary_brain_region": "fusiform_face_area",
        "paradox_question": "Why did he swear his own parents were identical imposters?",
        "debate_question": "If a familiar face felt zero warmth, would you trust your eyes or your gut?",
        "sentences": [
            {"sentence_index": 1, "act": 1, "text": "A 30-year-old man looked straight at his father and called the police on an imposter!"},
            {"sentence_index": 2, "act": 1, "text": "Yet Why did he swear his own parents were identical imposters?"},
            {"sentence_index": 3, "act": 1, "text": "His visual face detector worked perfectly, while the wire to his emotional center snapped."},
            {"sentence_index": 4, "act": 3, "text": "In 1997, Hirstein and Ramachandran measured skin conductance and found zero emotional spike to his parents' faces."},
            {"sentence_index": 5, "act": 4, "text": "Normally your fusiform face area identifies a face and relays a warm glow straight to the amygdala."},
            {"sentence_index": 6, "act": 6, "text": "Without that gut warmth, your frontal lobe invents a duplicate stranger to explain the coldness."},
        ],
        "data_stamps": [
            {
                "stamp_id": "ds_01",
                "preset": "bar_compare",
                "mode": "study",
                "title": "Skin Conductance Emotional Response",
                "doi": "10.1098/rspb.1997.0092",
                "source_citation": "Hirstein & Ramachandran (1997)",
                "groups": [
                    {"label": "Stranger Face", "mean": 0.12, "unit": "uS"},
                    {"label": "Parent Face (DS)", "mean": 0.13, "unit": "uS"},
                ],
            }
        ],
    }
    (p_dir / "02_script" / "script.json").write_text(json.dumps(script_doc, indent=2), encoding="utf-8")

    cover = Image.new("RGB", (1080, 1920), (14, 22, 34))
    cover_path = p_dir / "06_publish" / "thumbnails" / "thumb_var_A.png"
    cover_path.parent.mkdir(parents=True, exist_ok=True)
    cover.save(cover_path, format="PNG")

    clean_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    clean_mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")

    meta_doc = {
        "title": "Why Your Brain Calls Loved Ones Imposters",
        "description": "Hirstein & Ramachandran (1997) DOI: 10.1098/rspb.1997.0092",
        "tags": [],
    }
    (p_dir / "06_publish" / "metadata.json").write_text(json.dumps(meta_doc, indent=2), encoding="utf-8")
    return p_dir


def test_carousel_4x5_geometry_and_manychat_ban(tmp_path: Path) -> None:
    assert CAROUSEL_4X5_WIDTH == 1080
    assert CAROUSEL_4X5_HEIGHT == 1350
    assert CAROUSEL_4X5_SAFE_MARGIN_X == 90
    assert CAROUSEL_4X5_SAFE_MARGIN_X - 34 >= 50

    with pytest.raises(ValueError, match="Forbidden ManyChat"):
        validate_slide_copy_safety("Comment 'BRAIN' below and I'll DM you the link!")

    bg = tmp_path / "bg.png"
    Image.new("RGB", (1080, 1350), (14, 24, 38)).save(bg, format="PNG")
    slides = [
        CardSlide("HOOK", "HE CALLED POLICE ON HIS OWN DAD", "Capgras syndrome severs warmth from recognition.", bg),
        CardSlide(
            "TAKEAWAY",
            "RECOGNITION NEEDS WARMTH",
            "Without emotional warmth, the brain invents an imposter.",
            bg,
            footer_note="Study: Hirstein & Ramachandran (1997) · DOI: 10.1098/rspb.1997.0092",
        ),
    ]
    rendered = render_carousel_4x5_slides(slides, tmp_path / "cards")
    assert len(rendered) == 2
    for p in rendered:
        with Image.open(p) as im:
            assert im.size == (1080, 1350)


def test_youtube_community_quiz_payload_contract(tmp_path: Path) -> None:
    p_dir = _build_synthetic_v8_project(tmp_path)
    payload = build_youtube_community_quiz_payload(p_dir)
    assert validate_youtube_community_quiz_payload(payload) == []
    assert payload["question"].endswith("?")
    assert len(payload["question"]) <= 240
    assert len(payload["options"]) == 4
    assert sum(1 for o in payload["options"] if o.get("is_correct") is True) == 1
    for opt in payload["options"]:
        assert 1 <= len(opt["text"]) <= 80
    assert "10.1098/rspb.1997.0092" in payload["explanation"]
    assert "@AllAboutBrainOfficial" in payload["explanation"]
    assert len(payload["explanation"]) <= 500
    assert payload["recommended_offset_minutes"] == -210

    bad_multi_correct = dict(payload)
    bad_multi_correct["options"] = [
        {"text": "Option A", "is_correct": True},
        {"text": "Option B", "is_correct": True},
        {"text": "Option C", "is_correct": False},
        {"text": "Option D", "is_correct": False},
    ]
    errs = validate_youtube_community_quiz_payload(bad_multi_correct)
    assert any("exactly 1 option" in e.lower() for e in errs)

    bad_long_opt = dict(payload)
    bad_long_opt["options"] = [
        {"text": "X" * 85, "is_correct": True},
        {"text": "Option B", "is_correct": False},
        {"text": "Option C", "is_correct": False},
        {"text": "Option D", "is_correct": False},
    ]
    errs2 = validate_youtube_community_quiz_payload(bad_long_opt)
    assert any("80-char" in e for e in errs2)


def test_export_multi_platform_bundle_v2_outputs_and_video_fallback(tmp_path: Path) -> None:
    p_dir = _build_synthetic_v8_project(tmp_path)
    # Default copy_video=False avoids 60-95MB duplicate video_clean.mp4 while resolve_bundle_video_path falls back cleanly!
    res = export_multi_platform_bundle(p_dir)

    bundle_dir = p_dir / "06_publish" / "multi_platform_bundle"
    assert not (bundle_dir / "video_clean.mp4").exists()
    resolved_vid = resolve_bundle_video_path(p_dir)
    assert resolved_vid == p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"

    carousel_dir = bundle_dir / "carousel_4x5"
    slides = sorted(carousel_dir.glob("slide_*.png"))
    assert len(slides) == 6
    for sp in slides:
        assert not sp.is_symlink()
        with Image.open(sp) as im:
            assert im.size == (1080, 1350)

    carousel_cap = (bundle_dir / "carousel_caption.txt").read_text(encoding="utf-8")
    assert "10.1098/rspb.1997.0092" in carousel_cap
    assert "Save this" in carousel_cap
    validate_slide_copy_safety(carousel_cap)

    quiz_doc = json.loads((bundle_dir / "youtube_quiz_post.json").read_text(encoding="utf-8"))
    assert validate_youtube_community_quiz_payload(quiz_doc) == []

    checklist = json.loads((bundle_dir / "upload_checklist.json").read_text(encoding="utf-8"))
    assert checklist["bundle_schema_version"] == 2
    assert checklist["source_video_relpath"] == "05_assembly/final_shorts_1080x1920.mp4"
    assert checklist["youtube_upload_srt_cc"] is False
    assert checklist["youtube_auto_dubbing_burned_ass"] is False
    assert checklist["tiktok_trending_sound_prohibited"] is True
    assert checklist["manychat_comment_dm_prohibited"] is True
    assert checklist["cover_safe_zone_check"]["passed"] is True
    assert checklist["carousel_safe_zone_check"]["passed"] is True
    assert checklist["carousel_safe_zone_check"]["horizontal_margin_px"] == 90
    assert "primary_search_keyword" in checklist
    assert len(res["carousel_slides"]) == 6
