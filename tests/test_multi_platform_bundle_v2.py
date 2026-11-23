"""
Unit tests for Workstream 1 (`multi-bundle` v2):
- `4:5` (`1080x1350`) 6-slide episode Carousel builder (`CAROUSEL_4X5_SAFE_MARGIN_X == 90`, `x=90..990` inside `3:4` profile grid crop `x=34..1046`)
- Permanent ban on ManyChat / comment-keyword DM automation CTAs (`validate_slide_copy_safety`)
- Slide 04 R70-M Data Stamp composite & Slide 06 `Study: ... · DOI: ...` + `SAVE & SHARE`
- YouTube Community `Quiz` payload builder & validator (`<=80` char options, exactly 1 `is_correct: True`, `<=500` char explanation, `-210` min offset)
- `export_multi_platform_bundle()` v2 artifacts (`carousel_4x5/slide_01..06.png`, `carousel_caption.txt`, `youtube_quiz_post.json`, `upload_checklist.json` safety locks & safe-zone report)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from pipeline.instagram_card_builder import (
    CAROUSEL_4X5_HEIGHT,
    CAROUSEL_4X5_SAFE_MARGIN_X,
    CAROUSEL_4X5_WIDTH,
    CardSlide,
    extract_episode_carousel_slides,
    render_carousel_4x5_slides,
    validate_slide_copy_safety,
)
from pipeline.publish import (
    build_instagram_carousel_caption,
    build_youtube_community_quiz_payload,
    export_multi_platform_bundle,
    validate_youtube_community_quiz_payload,
)
from pipeline.storage import ProjectStorage


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

    # Minimal valid PNG cover & MP4 placeholder
    cover = Image.new("RGB", (1080, 1920), (14, 22, 34))
    cover_path = p_dir / "06_publish" / "thumbnails" / "thumb_var_A.png"
    cover_path.parent.mkdir(parents=True, exist_ok=True)
    cover.save(cover_path, format="PNG")

    clean_mp4 = p_dir / "05_assembly" / "final_short_clean.mp4"
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
    # 3:4 profile grid crops 1080x1350 horizontally to 1012.5px -> ~34px per side; 90px margin leaves 56px buffer!
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


def test_export_multi_platform_bundle_v2_outputs_and_safety_locks(tmp_path: Path) -> None:
    p_dir = _build_synthetic_v8_project(tmp_path)
    res = export_multi_platform_bundle(p_dir, copy_video=False)

    bundle_dir = p_dir / "06_publish" / "multi_platform_bundle"
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
    assert checklist["youtube_upload_srt_cc"] is False
    assert checklist["youtube_auto_dubbing_burned_ass"] is False
    assert checklist["tiktok_trending_sound_prohibited"] is True
    assert checklist["manychat_comment_dm_prohibited"] is True
    assert checklist["cover_safe_zone_check"]["passed"] is True
    assert checklist["carousel_safe_zone_check"]["passed"] is True
    assert checklist["carousel_safe_zone_check"]["horizontal_margin_px"] == 90
    assert "primary_search_keyword" in checklist
    assert len(res["carousel_slides"]) == 6
