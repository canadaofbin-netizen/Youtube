"""
Rule R68-D Unit & Integration Tests — Zero-AI-Smell Plain Story Description & Casual Pinned Comment.

Verifies:
1. Approved verbatim Ep #4 (`v8_ep04_patient_sm_fearless_amygdala`) and Ep #5 (`v8_ep05_ucl_tickle_delay_robot`)
   YouTube descriptions and pinned comments pass `validate_v8_viewer_description` with 0 issues and render 100% verbatim.
2. Hard rejections for em-dashes (`—`, ` -- `), semicolons (`;`), `R68D_BANNED_AI_CLICHES`, DOI URLs/strings,
   bullet/numbered lists, colon subheaders, hashtags (`#`), Hangul, and word-count bounds (`55..135`).
3. `_scrub_experiment_nicknames` replaces omitted academic nicknames with natural `"this experiment"`
   (never `"measured neural protocol"`) while preserving `Research:` / `Primary Peer-Reviewed Sources:` tail.
4. `build_expressive_v8_pinned_comment` and `CommunityManager.prepare_comment_content` output a clean,
   DOI-free, `"My bet:"`-free, em-dash-free, cameo-free 1-sentence `?` question on non-frozen `v8`
   while preserving `PRE_R68H_FROZEN_V8_PROJECTS` compatibility.
5. `PublishStage.run`, `diorama_batch_orchestrator`, and `export_multi_platform_bundle` keep internal
   `metadata["doi"]` & `ai_content_declaration = True` intact while stripping DOIs/AI clichés from viewer text.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from pipeline.config import (
    PRE_R68H_FROZEN_V8_PROJECTS,
    R68D_BANNED_AI_CLICHES,
    R68D_DESCRIPTION_WORD_RANGE,
)
from pipeline.batch_runner import _default_metadata_from_script_and_dossier
from pipeline.publish import (
    PublishStage,
    _scrub_experiment_nicknames,
    build_expressive_v8_pinned_comment,
    export_multi_platform_bundle,
    format_v8_viewer_story_description,
    validate_v8_viewer_description,
)
from pipeline.storage import ProjectStorage
from pipeline.studio.community import CommunityManager

EP04_DESCRIPTION = (
    "Patient S.M. lived for decades with rare damage to both sides of her amygdala, "
    "the part of the brain usually linked to fear. Doctors at the University of Iowa "
    "took her to exotic pet stores, handed her live snakes, showed her horror movies, "
    "and walked her through a haunted house. She stayed curious the whole time and "
    "never once felt scared.\n\n"
    "That changed in a breathing lab. One harmless breath of 35% carbon dioxide gave "
    "her a full panic attack in seconds, the first fear she had felt since childhood. "
    "Outside threats go through the amygdala, while suffocation alarms sit much deeper "
    "in the brainstem, which explains why sudden panic can hit your body even when the "
    "room around you looks completely safe.\n\n"
    "Research: Feinstein et al., University of Iowa (2011, 2013)."
)

EP04_PINNED_COMMENT = (
    "Have you ever had your heart start pounding out of nowhere when nothing scary was going on around you?"
)

EP05_DESCRIPTION = (
    "Try tickling your own palm and nothing happens, even if someone else barely "
    "touches the exact same spot and you lose it.\n\n"
    "A team at UCL tested why by having volunteers move a plastic lever with their "
    "left hand to stroke their right palm with a soft foam brush. When the brush moved "
    "right away, it barely felt like anything because the cerebellum already knew the "
    "touch was coming and turned the sensation down. Once the researchers added a 0.2 "
    "second delay between the two hands, the brain stopped recognizing the touch as "
    "its own, and people started laughing from their own hand.\n\n"
    "Research: Blakemore et al., University College London (1998, 1999)."
)

EP05_PINNED_COMMENT = (
    "Are you super ticklish, or can you keep a straight face no matter what?"
)


def test_r68d_constants_and_approved_ep04_ep05_copy() -> None:
    assert R68D_DESCRIPTION_WORD_RANGE == (55, 135)
    assert "—" in R68D_BANNED_AI_CLICHES
    assert " -- " in R68D_BANNED_AI_CLICHES
    assert "turns out," in R68D_BANNED_AI_CLICHES
    assert "what's wild is" in R68D_BANNED_AI_CLICHES
    assert "measured neural protocol" in R68D_BANNED_AI_CLICHES

    assert validate_v8_viewer_description(EP04_DESCRIPTION, project_id="v8_ep04_patient_sm_fearless_amygdala") == []
    assert validate_v8_viewer_description(EP05_DESCRIPTION, project_id="v8_ep05_ucl_tickle_delay_robot") == []

    rendered_04 = format_v8_viewer_story_description({"viewer_description": EP04_DESCRIPTION})
    rendered_05 = format_v8_viewer_story_description({"viewer_description": EP05_DESCRIPTION})
    assert rendered_04 == EP04_DESCRIPTION
    assert rendered_05 == EP05_DESCRIPTION

    pin_04 = build_expressive_v8_pinned_comment(
        doi="10.1038/nn.3323",
        debate_question=EP04_PINNED_COMMENT,
    )
    pin_05 = build_expressive_v8_pinned_comment(
        doi="10.1038/2870",
        debate_question=EP05_PINNED_COMMENT,
    )
    assert pin_04 == EP04_PINNED_COMMENT
    assert pin_05 == EP05_PINNED_COMMENT
    assert "doi.org" not in pin_04 and "10.1038" not in pin_04
    assert "Mini-Cortex" not in pin_04 and "My bet" not in pin_04


def test_r68d_validator_hard_blocks_ai_smell_and_dois() -> None:
    # 1. Em-dash ('—' and ' -- ')
    bad_em = EP04_DESCRIPTION.replace(", the first fear", " — the first fear")
    errs_em = validate_v8_viewer_description(bad_em, project_id="v8_ep04_patient_sm_fearless_amygdala")
    assert any("banned AI cliché or punctuation" in e for e in errs_em)

    bad_ddash = EP04_DESCRIPTION.replace(", the first fear", " -- the first fear")
    errs_dd = validate_v8_viewer_description(bad_ddash, project_id="v8_ep04_patient_sm_fearless_amygdala")
    assert any("banned AI cliché or punctuation" in e for e in errs_dd)

    # 2. Rhetorical AI clichés & self-referential AI disclosure prose
    for cliche_phrase in ("Turns out, outside threats", "What's wild is that outside threats", "Visuals and voice were created with AI."):
        bad_cliche = EP04_DESCRIPTION.replace("Outside threats", cliche_phrase)
        errs_c = validate_v8_viewer_description(bad_cliche, project_id="v8_ep04_patient_sm_fearless_amygdala")
        assert any("banned AI cliché" in e for e in errs_c), f"Failed to block {cliche_phrase!r}"

    # 3. DOI link or raw DOI identifier
    bad_doi_url = EP04_DESCRIPTION.replace("(2011, 2013).", "(2011) https://doi.org/10.1038/nn.3323.")
    assert any("DOI" in e for e in validate_v8_viewer_description(bad_doi_url))

    bad_doi_raw = EP04_DESCRIPTION.replace("(2011, 2013).", "(10.1038/nn.3323).")
    assert any("DOI" in e for e in validate_v8_viewer_description(bad_doi_raw))

    # 4. Semicolons, bullets, colon subheaders, hashtags, Hangul, and word-range bounds
    assert any("semicolons" in e for e in validate_v8_viewer_description(EP05_DESCRIPTION.replace(", and people", "; and people")))
    bad_bullet = "- " + EP05_DESCRIPTION
    assert any("bullet" in e for e in validate_v8_viewer_description(bad_bullet))
    bad_colon = "The Setup: " + EP05_DESCRIPTION
    assert any("colon subheader" in e for e in validate_v8_viewer_description(bad_colon))
    assert any("hashtags" in e for e in validate_v8_viewer_description(EP05_DESCRIPTION + " #neuroscience"))
    assert any("Hangul" in e for e in validate_v8_viewer_description(EP05_DESCRIPTION.replace("UCL", "UCL 뇌과학")))
    assert any("word count" in e for e in validate_v8_viewer_description("Too short paragraph one.\n\nToo short paragraph two.\n\nResearch: UCL (1998)."))

    # 5. Frozen pilots in PRE_R68H_FROZEN_V8_PROJECTS are exempt
    frozen_id = next(iter(PRE_R68H_FROZEN_V8_PROJECTS))
    assert validate_v8_viewer_description("Documentary case briefing on sleep — https://doi.org/10.1016/j.cub.2016.02.063", project_id=frozen_id) == []


def test_r68d_scrub_experiment_nicknames_uses_natural_phrase() -> None:
    src = "Volunteers completed the Sensory Attenuation Test twice.\n\nResearch: Blakemore et al., Sensory Attenuation Test (1998)."
    scrubbed = _scrub_experiment_nicknames(src, ["Sensory Attenuation Test"])
    prose, _, tail = scrubbed.partition("Research:")
    assert "measured neural protocol" not in scrubbed.lower()
    assert "this experiment" in prose
    assert "Sensory Attenuation Test (1998)." in tail


def test_r68d_pinned_comment_community_and_multi_bundle_end_to_end(tmp_path: Path) -> None:
    # Creator bet + em-dash + hashtag stripped automatically
    cleaned_pin = build_expressive_v8_pinned_comment(
        doi="10.1038/nn.3323",
        debate_question="My bet: brainstem beats logic — have you ever felt sudden panic in a calm room? #Brain",
    )
    assert cleaned_pin == "Have you ever felt sudden panic in a calm room?"
    assert "—" not in cleaned_pin
    assert "My bet" not in cleaned_pin
    assert "doi.org" not in cleaned_pin

    # End-to-end project staging for non-frozen v8
    pid = "v8_r68d_e2e_unit"
    storage = ProjectStorage(pid, projects_dir=tmp_path)
    p_dir = storage.project_dir
    for sub in ("02_script", "03_visuals", "05_assembly", "06_publish"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)

    script_doc = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "project_id": pid,
        "everyday_domain": "anxiety",
        "title": "The Woman Who Felt Zero Fear",
        "doi": "10.1038/nn.3323",
        "viewer_description": EP04_DESCRIPTION,
        "debate_question": EP04_PINNED_COMMENT,
        "cameo_prompt": "Legacy cameo line that must stay omitted unless opted in",
        "sentences": [
            "In twenty eleven at the University of Iowa, doctors handed a fearless patient live snakes.",
            "One breath of carbon dioxide triggered immediate panic through deeper brainstem alarms.",
        ],
    }
    storage.save_json("02_script", "script.json", script_doc)
    storage.save_json(
        "03_visuals",
        "visual_plan.json",
        {"schema": 8, "style_profile": "expressive_25d_v8", "format_profile": "shorts_expressive_v8"},
    )
    storage.save_json("05_assembly", "probe_report.json", {"duration_sec": 74.2, "width": 1080, "height": 1920})
    thumb_src = tmp_path / "thumb_src.png"
    Image.new("RGB", (1080, 1920), (30, 50, 90)).save(thumb_src, format="PNG")

    PublishStage(storage).run(
        title=script_doc["title"],
        hashtags=["#Shorts"],
        doi=script_doc["doi"],
        source_summary="Feinstein et al. (2013) tested CO2 inhalation in bilateral amygdala lesions.",
        thumbnail_source_img=thumb_src,
    )
    (p_dir / "05_assembly" / "final_shorts_1080x1920.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x01" * 1024)
    meta = storage.load_json("06_publish", "metadata.json")
    assert meta["description"] == EP04_DESCRIPTION + "\n\n#shorts"
    assert meta["hashtags"] == ["#shorts"]
    assert "tags" in meta and "shorts" in meta["tags"]
    assert meta["pinned_comment"] == EP04_PINNED_COMMENT
    assert meta["doi"] == "10.1038/nn.3323"
    assert meta["ai_disclosure"] is True
    assert meta["ai_content_declaration"] is True
    assert meta["ai_assisted_content_declaration"]["altered_or_synthetic_content"] is True

    # CommunityManager.prepare_comment_content must NOT re-attach DOI or 'My bet:'
    cm = CommunityManager(projects_dir=tmp_path)
    cm_pkg = cm.prepare_comment_content(pid)
    assert cm_pkg["validation_issues"] == []
    assert cm_pkg["line1_valid"] is True
    assert cm_pkg["comment_text"] == EP04_PINNED_COMMENT
    assert "doi.org" not in cm_pkg["comment_text"]
    assert "My bet" not in cm_pkg["comment_text"]

    # Multi-platform bundle must also stay DOI-free and cliché-free
    bundle = export_multi_platform_bundle(p_dir, copy_video=False)
    b_dir = Path(bundle["bundle_dir"])
    for cap_file in ("tiktok_caption.txt", "reels_caption.txt"):
        cap_txt = (b_dir / cap_file).read_text(encoding="utf-8")
        assert "10.1038" not in cap_txt
        assert "doi.org" not in cap_txt.lower()
        assert "—" not in cap_txt
        assert "Research: Feinstein et al., University of Iowa (2011, 2013)." in cap_txt

    # Fallback synthesis from real dossier when viewer_description is omitted
    synth_meta = _default_metadata_from_script_and_dossier(
        project_id="v8_synth_fallback_check",
        pillar="brain_mysteries",
        slug="feinstein_patient_sm_fearless_amygdala",
        script_doc={
            "schema": 8,
            "style_profile": "expressive_25d_v8",
            "format_profile": "shorts_expressive_v8",
            "title": "The Woman Who Felt Zero Fear",
            "doi": "10.1038/nn.3323",
            "debate_question": EP04_PINNED_COMMENT,
        },
    )
    assert validate_v8_viewer_description(synth_meta["description"], project_id="v8_synth_fallback_check") == []
    assert synth_meta["pinned_comment"] == EP04_PINNED_COMMENT
