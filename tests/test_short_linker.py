"""
Unit & Integration Tests for Short-to-Short Related Video Automation (R35-B)
and Gear 5 Pipeline Safeguards (R34, R18-V5, R4/R9, R35, R36-B).
Follows Rule R28 (100% self-cleaning temporary directories; zero production mutation).
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import cv2

from pipeline.publish import PublishStage
from pipeline.research_dossier import init_dossier, validate_dossier
from pipeline.storage import ProjectStorage
from pipeline.studio.community import CommunityManager
from pipeline.studio.queue_manager import is_live_youtube_receipt, passes_v5_publish_gate
from pipeline.studio.short_linker import (
    ShortLinkGraph,
    StudioShortLinker,
    write_studio_publish_receipt,
)


def _make_node(
    pid: str,
    vid: str,
    *,
    title: str | None = None,
    pillar: str = "brain_health",
    visual_mode: str = "HYBRID",
    visibility: str = "public",
    views: int = 100,
    impressions: int = 200,
    apv_pct: float = 65.0,
    viewed_pct: float = 70.0,
    regions: list[str] | None = None,
    lexical_tokens: list[str] | None = None,
    published_at_dt: datetime | None = None,
    scheduled_at_dt: datetime | None = None,
    longform_video_id: str | None = None,
) -> dict[str, Any]:
    return {
        "project_id": pid,
        "video_id": vid,
        "title": title or f"Case {pid}",
        "pillar": pillar,
        "visual_mode": visual_mode,
        "visibility": visibility,
        "views": views,
        "impressions": impressions,
        "apv_pct": apv_pct,
        "viewed_pct": viewed_pct,
        "regions": regions if regions is not None else [],
        "lexical_tokens": lexical_tokens or [],
        "published_at_utc": published_at_dt.isoformat() if published_at_dt else None,
        "scheduled_at_utc": scheduled_at_dt.isoformat() if scheduled_at_dt else None,
        "published_longform_video_id": longform_video_id,
    }


def test_affinity_4_axis_and_behavioral_psych_redistribution(tmp_path: Path):
    now = datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc)
    n_neuro_1 = _make_node(
        "p_neuro_1",
        "VidNeuro001",
        pillar="brain_mysteries",
        visual_mode="HYBRID",
        regions=["fusiform_gyrus", "amygdala"],
        lexical_tokens=["face", "impostor", "familiarity", "delusion"],
        apv_pct=90.0,
        viewed_pct=78.0,
    )
    n_neuro_2 = _make_node(
        "p_neuro_2",
        "VidNeuro002",
        pillar="brain_mysteries",
        visual_mode="NEURO_BIOLOGY",
        regions=["amygdala", "hippocampus"],
        lexical_tokens=["fear", "amygdala", "familiarity", "memory"],
        apv_pct=82.0,
        viewed_pct=75.0,
    )
    n_behav_1 = _make_node(
        "p_behav_1",
        "VidBehav001",
        pillar="bci_ethics",
        visual_mode="BEHAVIORAL_PSYCH",
        regions=[],
        lexical_tokens=["obedience", "authority", "shock", "experiment", "compliance"],
        apv_pct=88.0,
        viewed_pct=81.0,
    )
    n_behav_2 = _make_node(
        "p_behav_2",
        "VidBehav002",
        pillar="bci_ethics",
        visual_mode="BEHAVIORAL_PSYCH",
        regions=[],
        lexical_tokens=["obedience", "authority", "prison", "role", "compliance"],
        apv_pct=84.0,
        viewed_pct=79.0,
    )

    graph = ShortLinkGraph(
        projects_dir=tmp_path,
        graph_file=tmp_path / "graph.json",
        nodes=[n_neuro_1, n_neuro_2, n_behav_1, n_behav_2],
        now_utc=now,
    )

    aff_neuro = graph.compute_affinity(n_neuro_1, n_neuro_2)
    assert aff_neuro["behavioral_reweighted"] is False
    assert aff_neuro["anatomy"] > 0.3
    assert aff_neuro["pillar_mode"] >= 0.85
    assert aff_neuro["total"] > 0.55

    # BEHAVIORAL_PSYCH nodes have empty regions by R45 design; weights must redistribute cleanly
    aff_behav = graph.compute_affinity(n_behav_1, n_behav_2)
    assert aff_behav["behavioral_reweighted"] is True
    assert aff_behav["anatomy"] == 0.0
    assert aff_behav["pillar_mode"] == 1.0
    assert aff_behav["lexical"] > 0.4
    assert aff_behav["total"] > 0.60


def test_seed_boost_5_node_ring_zero_two_cycles(tmp_path: Path):
    now = datetime(2026, 10, 25, 20, 0, tzinfo=timezone.utc)
    old_pub = now - timedelta(hours=96)

    nodes = [
        _make_node(
            "psych_01_habit",
            "p4ou90cHt50",
            pillar="brain_health",
            views=1436,
            impressions=1693,
            apv_pct=63.2,
            viewed_pct=84.8,
            regions=["basal_ganglia", "striatum", "dorsolateral_pfc"],
            lexical_tokens=["habit", "loop", "autopilot", "striatum"],
            published_at_dt=old_pub,
        ),
        _make_node(
            "psych_02_speech",
            "p0etX4iMJ7Q",
            pillar="bci_tech",
            views=1,
            impressions=1,
            apv_pct=51.8,
            viewed_pct=100.0,
            regions=["motor_cortex", "brocas_area"],
            lexical_tokens=["speech", "implant", "words", "decoder"],
            published_at_dt=old_pub,
        ),
        _make_node(
            "psych_03_split",
            "nGNIl26te0w",
            pillar="brain_mysteries",
            views=199,
            impressions=830,
            apv_pct=60.8,
            viewed_pct=23.9,
            regions=["corpus_callosum"],
            lexical_tokens=["split", "hemisphere", "conscious", "skull"],
            published_at_dt=old_pub,
        ),
        _make_node(
            "psych_05_capgras",
            "lZv3_UAWScI",
            pillar="brain_mysteries",
            views=7,
            impressions=11,
            apv_pct=94.7,
            viewed_pct=63.6,
            regions=["fusiform_gyrus", "amygdala"],
            lexical_tokens=["impostor", "family", "delusion", "conscious"],
            published_at_dt=old_pub,
        ),
        _make_node(
            "psych_06_sleep",
            "31_O2CmlKOk",
            pillar="brain_health",
            views=1966,
            impressions=2480,
            apv_pct=90.3,
            viewed_pct=79.3,
            regions=["hypothalamus", "hippocampus"],
            lexical_tokens=["sleep", "glymphatic", "toxins", "night"],
            published_at_dt=old_pub,
        ),
    ]

    graph = ShortLinkGraph(
        projects_dir=tmp_path,
        graph_file=tmp_path / "short_link_graph.json",
        nodes=nodes,
        now_utc=now,
    )
    plan = graph.plan_links(mode="seed_boost")
    assert plan["edge_count"] == 5
    assert plan["two_cycle_count"] == 0, f"Unexpected 2-cycles: {plan['two_cycles']}"

    edge_by_src = {e["source_project_id"]: e["target_project_id"] for e in plan["edges"]}
    assert edge_by_src["psych_06_sleep"] == "psych_05_capgras"
    assert edge_by_src["psych_05_capgras"] == "psych_01_habit"
    assert edge_by_src["psych_01_habit"] == "psych_02_speech"
    assert edge_by_src["psych_02_speech"] == "psych_06_sleep"
    assert edge_by_src["psych_03_split"] == "psych_05_capgras"

    # Also verify semantic_chain produces zero 2-cycles for N=5
    plan_sem = graph.plan_links(mode="semantic_chain")
    assert plan_sem["two_cycle_count"] == 0


def test_directional_visibility_guard_and_24h_seed_lock(tmp_path: Path):
    now = datetime(2026, 10, 25, 20, 0, tzinfo=timezone.utc)
    pub_mature = _make_node(
        "p_pub_mature",
        "VidPubMat01",
        visibility="public",
        published_at_dt=now - timedelta(hours=36),
    )
    pub_fresh = _make_node(
        "p_pub_fresh",
        "VidPubFrs02",
        visibility="public",
        published_at_dt=now - timedelta(hours=6),
    )
    unlisted_vid = _make_node("p_unlisted", "VidUnlist03", visibility="unlisted")
    sched_early = _make_node(
        "p_sched_early",
        "VidSchedE04",
        visibility="scheduled",
        scheduled_at_dt=now + timedelta(hours=12),
    )
    sched_late = _make_node(
        "p_sched_late",
        "VidSchedL05",
        visibility="scheduled",
        scheduled_at_dt=now + timedelta(hours=36),
    )
    sched_missing_ts = _make_node(
        "p_sched_missing",
        "VidSchedM06",
        visibility="scheduled",
        scheduled_at_dt=None,
    )

    # Public source can ONLY target Public (never Unlisted or Scheduled)
    assert ShortLinkGraph.is_valid_link_direction(pub_mature, pub_fresh) is True
    assert ShortLinkGraph.is_valid_link_direction(pub_mature, unlisted_vid) is False
    assert ShortLinkGraph.is_valid_link_direction(pub_mature, sched_early) is False
    assert ShortLinkGraph.is_valid_link_direction(pub_mature, pub_mature) is False

    # Unlisted/Scheduled source can target Public or earlier-or-equal Scheduled, never later/unknown Scheduled
    assert ShortLinkGraph.is_valid_link_direction(unlisted_vid, pub_mature) is True
    assert ShortLinkGraph.is_valid_link_direction(sched_late, sched_early) is True
    assert ShortLinkGraph.is_valid_link_direction(sched_early, sched_late) is False
    assert ShortLinkGraph.is_valid_link_direction(sched_early, sched_missing_ts) is False

    # 24h seed lock check
    graph = ShortLinkGraph(
        projects_dir=tmp_path,
        graph_file=tmp_path / "graph.json",
        nodes=[pub_mature, pub_fresh],
        now_utc=now,
    )
    plan_locked = graph.plan_links(mode="seed_boost", force=False)
    edges_by_pid = {e["source_project_id"]: e for e in plan_locked["edges"]}
    assert edges_by_pid["p_pub_mature"]["action"] == "apply_link"
    assert edges_by_pid["p_pub_fresh"]["action"] == "deferred_seed_lock"

    plan_forced = graph.plan_links(mode="seed_boost", force=True)
    edges_forced = {e["source_project_id"]: e for e in plan_forced["edges"]}
    assert edges_forced["p_pub_fresh"]["action"] == "apply_link"


def test_longform_parent_bridge_and_dossier_validation(tmp_path: Path, monkeypatch):
    import pipeline.research_dossier as rd

    dossiers_root = tmp_path / "dossiers"
    monkeypatch.setattr(rd, "DOSSIERS_ROOT", dossiers_root)
    d_dir = init_dossier("test_longform_case", "Test Case", pillar="brain_mysteries", visual_mode="HYBRID", root=dossiers_root)
    lf_outline = json.loads((d_dir / "07_longform_outline.json").read_text(encoding="utf-8"))
    assert "published_longform_video_id" in lf_outline
    assert "published_longform_title" in lf_outline

    # Invalid longform ID format should be flagged by validate_dossier
    lf_outline["published_longform_video_id"] = "bad_id"
    (d_dir / "07_longform_outline.json").write_text(json.dumps(lf_outline, indent=2), encoding="utf-8")
    val_bad = validate_dossier("test_longform_case", root=dossiers_root)
    assert any("published_longform_video_id" in issue for issue in val_bad["issues"])

    # Valid 11-char YouTube ID should not trigger longform ID format error
    lf_outline["published_longform_video_id"] = "LfDocVideo1"
    (d_dir / "07_longform_outline.json").write_text(json.dumps(lf_outline, indent=2), encoding="utf-8")
    val_ok = validate_dossier("test_longform_case", root=dossiers_root)
    assert not any("published_longform_video_id" in issue for issue in val_ok["issues"])

    now = datetime(2026, 10, 25, 20, 0, tzinfo=timezone.utc)
    n1 = _make_node(
        "p_short_with_lf",
        "ShortVid001",
        published_at_dt=now - timedelta(hours=48),
        longform_video_id="LfDocVideo1",
    )
    n2 = _make_node(
        "p_other_short",
        "ShortVid002",
        published_at_dt=now - timedelta(hours=48),
    )
    graph = ShortLinkGraph(
        projects_dir=tmp_path,
        graph_file=tmp_path / "graph.json",
        nodes=[n1, n2],
        now_utc=now,
    )
    plan = graph.plan_links(mode="semantic_chain")
    e1 = next(e for e in plan["edges"] if e["source_project_id"] == "p_short_with_lf")
    assert e1["target_type"] == "longform"
    assert e1["target_video_id"] == "LfDocVideo1"
    assert e1["link_reason"] == "published_longform_bridge"


class _FakeStudioCDPClient:
    """Deterministic stub DirectCDPClient simulating YouTube Studio /video/<id>/edit DOM."""

    def __init__(self, edit_url: str, state_log: list[dict[str, Any]], shared_state: dict[str, Any]):
        self.edit_url = edit_url
        self.state_log = state_log
        self.shared_state = shared_state
        self.playlist_assigned = False
        self.selected_vid = ""
        self.selected_title = ""
        self.saved_clicked = False

    async def __aenter__(self):
        self.state_log.append({"event": "open", "url": self.edit_url})
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.state_log.append({"event": "close", "url": self.edit_url})

    async def find_element(self, selectors: list[str] | str) -> str | None:
        return "found"

    async def wait_for_element(self, selectors: list[str] | str, timeout_sec: float = 15.0) -> bool:
        return True

    async def click(self, selectors: list[str] | str) -> bool:
        self.state_log.append({"event": "click", "selector": selectors})
        sel_str = str(selectors)
        if "#save" in sel_str:
            self.saved_clicked = True
        return True

    async def type_into(self, selectors: list[str] | str, text: str) -> bool:
        self.state_log.append({"event": "type", "selector": selectors, "text": text})
        return True

    async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return {}

    async def eval(self, expression: str) -> Any:
        import re as _re

        if "UC4FeioYYv9X04Di07_MfZ7g" in expression:
            return True
        if "ytcp-video-metadata-playlists" in expression:
            return "1 playlist" if self.playlist_assigned else ""
        if "ytcp-playlist-dialog" in expression and "ytcp-checkbox-group" in expression:
            self.playlist_assigned = True
            if not self.shared_state.get("playlist_created"):
                self.shared_state["playlist_created"] = True
                return {"found": False}
            return {"found": True, "wasChecked": False, "matchedText": "Neuroscience Shorts"}
        if "return { exists: true, text: txt, disabled }" in expression:
            return {"exists": True, "text": "None", "disabled": False}
        if "ytcp-video-pick-dialog" in expression and "ytcp-entity-card" in expression:
            m_vid = _re.search(r"const targetVid = \"([^\"]+)\"", expression)
            m_title = _re.search(r"const targetTitle = \"([^\"]*)\"", expression)
            self.selected_vid = m_vid.group(1) if m_vid else "lZv3_UAWScI"
            self.selected_title = (m_title.group(1) if m_title else "Linked Companion Short") or "Linked Companion Short"
            return {
                "matched": True,
                "matchMode": "video_id",
                "videoId": self.selected_vid,
                "cardTitle": self.selected_title,
            }
        if "return { text: (el.innerText || '').replace" in expression:
            return {"text": self.selected_title, "linkedId": self.selected_vid}
        if "return { exists: true, disabled }" in expression:
            return {"exists": True, "disabled": False}
        if "ytcp-video-metadata-editor ytcp-button#save" in expression:
            return True
        return True


def test_studio_short_linker_stub_cdp_and_consolidated_receipt(tmp_path: Path, monkeypatch):
    import pipeline.studio.short_linker as sl_mod

    async def _fast_sleep(_sec: float):
        return None

    monkeypatch.setattr(sl_mod.asyncio, "sleep", _fast_sleep)

    projects_dir = tmp_path / "projects"
    now = datetime(2026, 10, 25, 20, 0, tzinfo=timezone.utc)
    old_iso = (now - timedelta(hours=72)).isoformat()

    specs = [
        ("psych_06_sleep", "31_O2CmlKOk", "What One Sleepless Night Does to Your Brain", "brain_health", 1966, 2480),
        ("psych_05_capgras", "lZv3_UAWScI", "When You Believe Your Family Are Imposters", "brain_mysteries", 7, 11),
        ("psych_01_habit", "p4ou90cHt50", "Why Deep Brain Loops Lock Habits on Autopilot", "brain_health", 1436, 1693),
        ("psych_02_speech", "p0etX4iMJ7Q", "How a Brain Implant Decodes 62 Words Per Minute", "bci_tech", 1, 1),
    ]
    explicit_nodes = []
    for pid, vid, title, pillar, views, imp in specs:
        pub_dir = projects_dir / pid / "06_publish"
        pub_dir.mkdir(parents=True, exist_ok=True)
        (projects_dir / pid / "00_project_manifest.json").write_text(
            json.dumps({"project_id": pid, "title": title, "pillar": pillar}),
            encoding="utf-8",
        )
        (pub_dir / "upload_receipt.json").write_text(
            json.dumps({
                "project_id": pid,
                "video_id": vid,
                "title": title,
                "visibility": "public",
                "status": "published_public",
                "published_at": old_iso,
                "ai_altered_content_declared": True,
            }),
            encoding="utf-8",
        )
        (pub_dir / "community_receipt.json").write_text(
            json.dumps({"project_id": pid, "video_id": vid, "pinned": True}),
            encoding="utf-8",
        )
        (pub_dir / "ab_test_manifest.json").write_text(
            json.dumps({"current_active_variant": "A", "rotation_interval_hours": 24}),
            encoding="utf-8",
        )
        explicit_nodes.append(
            _make_node(
                pid,
                vid,
                title=title,
                pillar=pillar,
                views=views,
                impressions=imp,
                published_at_dt=now - timedelta(hours=72),
            )
        )

    state_log: list[dict[str, Any]] = []
    shared_state: dict[str, Any] = {}
    recycled_calls: list[int] = []

    linker = StudioShortLinker(
        cdp_port=9222,
        projects_dir=projects_dir,
        graph_file=tmp_path / "short_link_graph.json",
        cdp_client_factory=lambda url: _FakeStudioCDPClient(url, state_log, shared_state),
        recycle_tab_fn=lambda **kwargs: recycled_calls.append(1) or "new_tab_id",
    )

    res = linker.run(
        mode="seed_boost",
        assign_playlists=True,
        dry_run=False,
        force=True,
        nodes=explicit_nodes,
    )
    assert res["verified_count"] == 4
    assert res["two_cycle_count"] == 0
    # 4 edits with STUDIO_TAB_RECYCLE_INTERVAL == 3 triggers exactly 1 Studio tab recycle
    assert len(recycled_calls) == 1
    assert (tmp_path / "short_link_graph.json").exists()

    for pid, _, _, _, _, _ in specs:
        rel_rec = json.loads((projects_dir / pid / "06_publish" / "related_video_receipt.json").read_text(encoding="utf-8"))
        assert rel_rec["verified"] is True
        assert rel_rec["match_mode"] == "video_id"
        assert rel_rec["playlist_verified"] is True

        cons_path = write_studio_publish_receipt(pid, projects_dir=projects_dir)
        cons_rec = json.loads(cons_path.read_text(encoding="utf-8"))
        assert cons_rec["stage_5_complete"] is True
        assert cons_rec["related_video"]["linked"] is True
        assert cons_rec["playlist"]["assigned"] is True
        assert cons_rec["community_pin"]["pinned"] is True


def test_r34_receipt_guard_v5_gate_doi_and_dossier_comment_synthesis(tmp_path: Path):
    # 1. R34 receipt recognition
    assert is_live_youtube_receipt({"status": "published_public", "video_id": "p4ou90cHt50"}) is True
    assert is_live_youtube_receipt({"status": "uploaded", "video_id": "31_O2CmlKOk"}) is True
    assert is_live_youtube_receipt({"status": "deleted_from_studio", "video_id": "oldDeleted1"}) is False
    assert is_live_youtube_receipt({"status": "dry_run_success", "video_id": "sim_psych_01"}) is False

    # 2. v5 gate blocks missing/legacy v4 projects unless allow_legacy_v4=True
    legacy_dir = tmp_path / "legacy_v4_proj"
    legacy_dir.mkdir(parents=True)
    ok_default, issues = passes_v5_publish_gate(legacy_dir, allow_legacy_v4=False)
    assert ok_default is False and issues
    ok_override, _ = passes_v5_publish_gate(legacy_dir, allow_legacy_v4=True)
    assert ok_override is True

    # 3. PublishStage DOI URL normalization + R4 disclosure + related_short Companion Case
    pub_projects = tmp_path / "pub_projects"
    st = ProjectStorage("test_pub_norm", title="Test Brain Case", pillar="bci_tech", projects_dir=pub_projects)
    asm_dir = st.get_stage_dir("05_assembly")
    dummy_mp4 = asm_dir / "final_shorts_1080x1920.mp4"
    writer = cv2.VideoWriter(str(dummy_mp4), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (1080, 1920))
    for i in range(15):
        frame = np.full((1920, 1080, 3), 40 + i * 8, dtype=np.uint8)
        writer.write(frame)
    writer.release()

    pub_res = PublishStage(st).run(
        title="How a Brain Implant Decodes 62 Words Per Minute",
        hashtags=["#Neuroscience", "#BCI", "#BrainScience"],
        doi="10.1038/s41586-023-06377-x",
        source_summary="62 words per minute decoded from speech motor cortex",
        related_short={"title": "Split Brain Dual Mind", "video_id": "nGNIl26te0w"},
    )
    desc = pub_res["metadata"]["description"]
    assert "https://doi.org/10.1038/s41586-023-06377-x" in desc
    assert "AI Disclosure:" in desc
    assert pub_res["metadata"]["ai_assisted_content_declaration"]["altered_or_synthetic_content"] is True
    assert "https://www.youtube.com/shorts/nGNIl26te0w" in desc

    # 4. CommunityManager dossier-driven 5-paragraph plain-prose synthesis (zero emojis, zero bullets, hermetic R28)
    dossiers_root = tmp_path / "dossiers"
    gage_dossier = dossiers_root / "phineas_gage_frontal_lobe"
    gage_dossier.mkdir(parents=True, exist_ok=True)
    (gage_dossier / "dossier.json").write_text(
        json.dumps(
            {
                "slug": "phineas_gage_frontal_lobe",
                "topic_title": "How an Iron Rod Rewired Phineas Gage",
                "pillar": "neuro_history",
                "visual_mode": "NEURO_BIOLOGY",
                "case": {
                    "subject": "Phineas Gage",
                    "year": 1848,
                    "location": "Cavendish, Vermont",
                    "summary": "In 1848, railroad foreman Phineas Gage survived a 13-pound tamping iron driven through his left frontal lobe.",
                },
                "primary_paper": {
                    "authors": "Damasio et al.",
                    "year": 1994,
                    "journal": "Science",
                    "doi": "10.1126/science.8178168",
                    "finding": "3D skull reconstruction localized damage to ventromedial prefrontal white-matter tracts.",
                },
                "follow_ups": [
                    {
                        "authors": "Van Horn et al.",
                        "year": 2012,
                        "finding": "Diffusion tractography showed 11 percent of left frontal white matter connections were severed.",
                    }
                ],
                "brain_links": [
                    {
                        "region": "ventromedial prefrontal cortex",
                        "observable_behavior": "impulsive social outbursts despite intact speech and memory",
                        "mechanism": "loss of top-down inhibitory tracts between prefrontal cortex and limbic circuits",
                    }
                ],
                "misconceptions": [
                    {
                        "myth": "Phineas Gage remained permanently feral until death",
                        "truth": "He later worked for years driving six-horse stagecoaches in Chile under structured routines",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    gage_proj = pub_projects / "psych_04_phineas_gage_frontal_lobe"
    (gage_proj / "06_publish").mkdir(parents=True, exist_ok=True)
    (gage_proj / "00_project_manifest.json").write_text(
        json.dumps({"project_id": "psych_04_phineas_gage_frontal_lobe", "dossier_slug": "phineas_gage_frontal_lobe"}),
        encoding="utf-8",
    )
    (gage_proj / "06_publish" / "metadata.json").write_text(
        json.dumps({"title": "How an Iron Rod Rewired Phineas Gage", "doi": "10.1126/science.8178168"}),
        encoding="utf-8",
    )

    cm = CommunityManager(projects_dir=pub_projects, dossiers_root=dossiers_root)
    payload = cm.prepare_comment_content(
        "psych_04_phineas_gage_frontal_lobe",
        companion_short={"title": "Split Brain Dual Mind", "video_id": "nGNIl26te0w"},
    )
    body = payload["comment_text"]
    assert "•" not in body
    assert "https://doi.org/10.1126/science.8178168" in body
    assert "Split Brain Dual Mind" in body
    blocks = [p.strip() for p in body.split("\n\n") if p.strip()]
    # [Headline] + 5 editorial paragraphs + Source/Companion/Question footer = 7 blocks
    assert len(blocks) == 7


def test_lexical_affinity_strips_boilerplate_and_discovers_misconceptions_and_narrations(tmp_path: Path):
    """Unrelated videos sharing full channel footer/disclosure/meme boilerplate must NOT saturate lexical affinity."""
    projects_dir = tmp_path / "projects"
    dossiers_root = tmp_path / "dossiers"
    shared_footer = (
        "\n\nSource & Verification:\n"
        "- Primary Paper: Verified peer-reviewed neuroscience journal\n"
        "- Key Finding: Measured in controlled human clinical trials.\n\n"
        "AI Disclosure: Visuals and voice synthesis in this documentary Short were generated "
        "with AI tools to illustrate peer-reviewed neuroscience findings.\n\n"
        "ALL ABOUT BRAIN translates peer-reviewed neuroscience and Brain-Computer Interface "
        "research into visual stories.\n\n"
        "#Shorts #Neuroscience #BrainScience #Psychology #BCI"
    )

    def _seed_case(
        pid: str,
        vid: str,
        title: str,
        desc_lead: str,
        narrations: list[str],
        myth: str,
        truth: str,
    ) -> None:
        pdir = projects_dir / pid
        (pdir / "02_script").mkdir(parents=True, exist_ok=True)
        (pdir / "06_publish").mkdir(parents=True, exist_ok=True)
        slug = f"slug_{pid}"
        ddir = dossiers_root / slug
        ddir.mkdir(parents=True, exist_ok=True)
        (pdir / "00_project_manifest.json").write_text(
            json.dumps({"project_id": pid, "title": title, "pillar": "bci_tech", "dossier_slug": slug}),
            encoding="utf-8",
        )
        (pdir / "02_script" / "script.json").write_text(
            json.dumps(
                {
                    "clip_narrations": narrations
                    + ["Your brain was built by survival, not truth. And your brain never asked your permission."]
                }
            ),
            encoding="utf-8",
        )
        (pdir / "06_publish" / "metadata.json").write_text(
            json.dumps({"title": title, "description": desc_lead + shared_footer}),
            encoding="utf-8",
        )
        (pdir / "06_publish" / "upload_receipt.json").write_text(
            json.dumps({"project_id": pid, "video_id": vid, "status": "published_public", "visibility": "public"}),
            encoding="utf-8",
        )
        (ddir / "dossier.json").write_text(
            json.dumps({"slug": slug, "visual_mode": "BEHAVIORAL_PSYCH", "misconceptions": [{"myth": myth, "truth": truth}]}),
            encoding="utf-8",
        )

    _seed_case(
        "p_speech_1",
        "vidSpeech01",
        "Intracortical Electrode Array Restores Rapid Phoneme Speech",
        "Microelectrode arrays decode attempted articulatory vocal tract movements.",
        ["Ventral premotor electrodes translate silent articulatory phoneme kinematics into fluent text."],
        "Brain implants read private unspoken inner monologues",
        "Decoders only detect deliberate vocal motor commands sent toward speech muscles",
    )
    _seed_case(
        "p_sleep_1",
        "vidSleep001",
        "Slow-Wave Sleep Flushes Metabolic Amyloid Through Interstitial Channels",
        "Astrocytic aquaporin channels expand interstitial fluid clearance overnight.",
        ["Cerebrospinal waves wash beta amyloid plaques across perivascular glymphatic pathways during deep slumber."],
        "Napping briefly at noon replaces nocturnal slow-wave clearance",
        "Sustained delta oscillations are required to dilate interstitial fluid channels",
    )
    _seed_case(
        "p_speech_2",
        "vidSpeech02",
        "Subdural Electrocorticography Synthesizes Spoken Avatar Sentences",
        "Cortical speech decoders map attempted vocal tract phoneme kinematics.",
        ["Articulatory phoneme decoders convert silent motor commands into real-time spoken sentences."],
        "Speech neuroprostheses read private inner thoughts",
        "Implants decode deliberate vocal motor commands directed at speech muscles",
    )

    graph = ShortLinkGraph(
        projects_dir=projects_dir,
        dossiers_dir=dossiers_root,
        reports_dir=tmp_path / "reports",
        graph_file=tmp_path / "graph.json",
    )
    nodes = {n["project_id"]: n for n in graph.discover_nodes()}
    assert "phoneme" in nodes["p_speech_1"]["lexical_tokens"]
    assert "monologues" in nodes["p_speech_1"]["lexical_tokens"]  # from dossier misconceptions

    aff_unrelated = graph.compute_affinity(nodes["p_speech_1"], nodes["p_sleep_1"])
    aff_related = graph.compute_affinity(nodes["p_speech_1"], nodes["p_speech_2"])
    assert aff_unrelated["lexical"] < 0.15
    assert aff_related["lexical"] > 0.35


def test_studio_short_linker_search_input_fallback(tmp_path: Path, monkeypatch):
    """When Pass 1 card scan misses in a large catalog, Pass 2 types into search_input and links cleanly."""
    import pipeline.studio.short_linker as sl_mod

    async def _fast_sleep(_sec: float):
        return None

    monkeypatch.setattr(sl_mod.asyncio, "sleep", _fast_sleep)

    class _Pass2SearchCDP(_FakeStudioCDPClient):
        def __init__(self, edit_url: str, state_log: list[dict[str, Any]], shared_state: dict[str, Any]):
            super().__init__(edit_url, state_log, shared_state)
            self.card_scan_attempts = 0

        async def eval(self, expression: str) -> Any:
            if "ytcp-video-pick-dialog" in expression and "ytcp-entity-card" in expression:
                self.card_scan_attempts += 1
                if self.card_scan_attempts == 1:
                    return {"matched": False, "cardCount": 30}
            return await super().eval(expression)

    projects_dir = tmp_path / "projects"
    now = datetime(2026, 10, 25, 20, 0, tzinfo=timezone.utc)
    nodes = []
    for pid, vid, title in [
        ("p_src", "vidSrc00001", "Source Case Title"),
        ("p_dst", "vidDst00002", "Target Companion Title"),
    ]:
        pub_dir = projects_dir / pid / "06_publish"
        pub_dir.mkdir(parents=True, exist_ok=True)
        (projects_dir / pid / "00_project_manifest.json").write_text(
            json.dumps({"project_id": pid, "title": title, "pillar": "bci_tech"}),
            encoding="utf-8",
        )
        (pub_dir / "upload_receipt.json").write_text(
            json.dumps({"project_id": pid, "video_id": vid, "status": "published_public", "visibility": "public"}),
            encoding="utf-8",
        )
        nodes.append(_make_node(pid, vid, title=title, published_at_dt=now - timedelta(hours=80)))

    state_log: list[dict[str, Any]] = []
    shared_state: dict[str, Any] = {}
    linker = StudioShortLinker(
        cdp_port=9222,
        projects_dir=projects_dir,
        graph_file=tmp_path / "graph.json",
        cdp_client_factory=lambda url: _Pass2SearchCDP(url, state_log, shared_state),
        recycle_tab_fn=lambda **kwargs: "tab_id",
    )
    res = linker.run(mode="semantic_chain", assign_playlists=False, dry_run=False, force=True, nodes=nodes)
    assert res["verified_count"] == 2
    typed_queries = [e["text"] for e in state_log if e.get("event") == "type"]
    assert "Target Companion Title" in typed_queries
    assert "Source Case Title" in typed_queries


def test_direct_cdp_set_file_input_shadow_dom_and_temp_tab_url_encoding(tmp_path: Path, monkeypatch):
    """DirectCDPClient.set_file_input pierces Shadow DOM with json imported, and open_temp_direct_client URL-encodes ?v=."""
    import asyncio
    import shutil
    import pipeline.studio.whale_session as ws_mod
    from pipeline.studio.whale_session import DirectCDPClient, WhaleSessionController

    dummy_png = tmp_path / "thumb.png"
    dummy_png.write_bytes(b"\x89PNG\r\n\x1a\n")

    # Avoid writing staged copies into /home/canadaofbin/chrome-profile/flow_bridge during hermetic unit tests (R28)
    monkeypatch.setattr(shutil, "copy2", lambda src, dst, *a, **kw: dst)

    client = DirectCDPClient("ws://127.0.0.1:9222/devtools/page/fake")
    sent_calls: list[tuple[str, dict[str, Any] | None]] = []

    async def _fake_send(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        sent_calls.append((method, params))
        if method == "Runtime.evaluate":
            return {"result": {"objectId": "shadow-file-input-obj-1"}}
        if method == "DOM.setFileInputFiles":
            return {}
        return {}

    monkeypatch.setattr(client, "send", _fake_send)
    ok = asyncio.run(client.set_file_input(dummy_png, selector=["input#file-loader", "input[type='file']"]))
    assert ok is True
    assert any(
        m == "DOM.setFileInputFiles" and p and p.get("objectId") == "shadow-file-input-obj-1"
        for m, p in sent_calls
    )

    # Verify open_temp_direct_client URL-encodes query strings (?v=...) and close_tab_by_id only closes that target
    requested_urls: list[tuple[str, str]] = []

    class _FakeResp:
        def __init__(self, body: bytes):
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _fake_urlopen(req, timeout=5):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        method = req.get_method() if hasattr(req, "get_method") else "GET"
        requested_urls.append((method, url))
        if "/json/new?" in url:
            return _FakeResp(
                json.dumps(
                    {
                        "id": "TEMP_WATCH_TAB_99",
                        "type": "page",
                        "url": "https://www.youtube.com/watch?v=31_O2CmlKOk",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/TEMP_WATCH_TAB_99",
                    }
                ).encode("utf-8")
            )
        if "/json/list" in url:
            return _FakeResp(
                json.dumps(
                    [
                        {"id": "USER_WATCH_TAB_1", "type": "page", "url": "https://www.youtube.com/watch?v=userVideo"},
                        {"id": "TEMP_WATCH_TAB_99", "type": "page", "url": "https://www.youtube.com/watch?v=31_O2CmlKOk"},
                    ]
                ).encode("utf-8")
            )
        return _FakeResp(b"Target is closing")

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    ctrl = WhaleSessionController(cdp_port=9222)
    temp_client, temp_id = ctrl.open_temp_direct_client("https://www.youtube.com/watch?v=31_O2CmlKOk")
    assert temp_id == "TEMP_WATCH_TAB_99"
    assert isinstance(temp_client, DirectCDPClient)
    assert any(
        m == "PUT" and "%3Fv%3D31_O2CmlKOk" in u
        for m, u in requested_urls
    )
    assert ctrl.close_tab_by_id(temp_id) is True
    assert any(u.endswith("/json/close/TEMP_WATCH_TAB_99") for _, u in requested_urls)
    assert not any("USER_WATCH_TAB_1" in u for _, u in requested_urls)


