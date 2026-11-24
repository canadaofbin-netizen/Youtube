"""Tests for `.agents/AGENTS.md` <-> `.agents/rules/*.md` 1:1 bidirectional mapping, token budgets, and zero stale contradictions."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS_MD = ROOT / ".agents" / "AGENTS.md"
RULES_DIR = ROOT / ".agents" / "rules"
ARCHIVE_DIR = RULES_DIR / "_archive"
SKILLS_DIR = ROOT / ".agents" / "skills"

STALE_CONTRADICTION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("MarginV=521", r"MarginV\s*=\s*521\b"),
    ("MarginV = EXPRESSIVE_V8_SUBTITLE_MARGIN_V = 521", r"MarginV\s*=\s*EXPRESSIVE_V8_SUBTITLE_MARGIN_V\s*=\s*521\b"),
    ("64pt", r"\b64pt\b"),
    ("xray_brain75_master", r"xray_brain75_master"),
    ("ref_r78m_cut05", r"ref_r78m_cut05"),
    ("Hope", r"\bHope\b"),
    ("Laura", r"\bLaura\b"),
    ("Mini-Cortex", r"Mini-Cortex"),
)


def _parse_agents_section2_rule_paths(agents_txt: str) -> tuple[list[str], list[str]]:
    in_sec2 = False
    active_names: list[str] = []
    archive_rels: list[str] = []
    for line in agents_txt.splitlines():
        if line.startswith("## 2."):
            in_sec2 = True
            continue
        if in_sec2 and line.startswith("## "):
            break
        if not in_sec2 or not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 4:
            continue
        m = re.search(r"`([^`]+\.md)`", cols[2])
        if not m:
            continue
        rel = m.group(1)
        if rel.startswith("_archive/"):
            archive_rels.append(rel)
        else:
            active_names.append(rel)
    return active_names, archive_rels


def test_agents_md_budget_and_bidirectional_rules_mapping() -> None:
    raw = AGENTS_MD.read_bytes()
    txt = raw.decode("utf-8")
    lines = txt.splitlines()
    assert 3_000 <= len(raw) <= 6_500, f"AGENTS.md byte budget out of range: {len(raw)}"
    assert len(lines) <= 60, f"AGENTS.md line budget exceeded: {len(lines)}"

    active_listed, archive_rels = _parse_agents_section2_rule_paths(txt)
    assert len(active_listed) == 25, f"Expected 25 active rules in AGENTS.md Section 2, got {len(active_listed)}"
    assert len(set(active_listed)) == 25, "Duplicate active rule entries in AGENTS.md Section 2"

    disk_active = sorted(p.name for p in RULES_DIR.glob("*.md"))
    assert len(disk_active) == 25, f"Expected 25 active files in .agents/rules/, found {len(disk_active)}: {disk_active}"
    assert set(active_listed) == set(disk_active), (
        f"AGENTS.md <-> .agents/rules mismatch! "
        f"missing_from_disk={set(active_listed) - set(disk_active)}, "
        f"orphans={set(disk_active) - set(active_listed)}"
    )

    for rel in active_listed + archive_rels:
        assert (RULES_DIR / rel).is_file(), f"Broken AGENTS.md rule path: {rel}"

    for arch_name in ("retired_rules_2026-11-18.md", "retired_constants_v4_v7_2026-11-18.md", "archival_reenactment_rules.md"):
        arch_path = ARCHIVE_DIR / arch_name
        assert arch_path.is_file(), f"Missing archive file: {arch_path}"
        assert not arch_path.read_text(encoding="utf-8").startswith("---\n"), f"{arch_name} must not have YAML frontmatter"


def test_rules_frontmatter_tier_and_token_budget() -> None:
    always_on_files: list[str] = []
    model_decision_files: list[str] = []

    for p in sorted(RULES_DIR.glob("*.md")):
        raw = p.read_bytes()
        txt = raw.decode("utf-8")
        if p.name == "production_constants.md":
            assert not txt.startswith("---\n"), "production_constants.md must NOT have YAML frontmatter"
            continue

        assert txt.startswith("---\n"), f"{p.name} missing YAML frontmatter"
        parts = txt.split("---\n", 2)
        assert len(parts) >= 3, f"{p.name} malformed YAML frontmatter"
        fm = parts[1]

        if p.name == "governance_roles.md":
            assert re.search(r"^trigger:\s*always_on\b", fm, flags=re.MULTILINE), "governance_roles.md must be always_on"
            assert 2_000 <= len(raw) <= 4_000, f"governance_roles.md bytes {len(raw)} out of 2000..4000"
            always_on_files.append(p.name)
        else:
            assert re.search(r"^trigger:\s*model_decision\b", fm, flags=re.MULTILINE), f"{p.name} must be model_decision"
            assert re.search(r'^description:\s*\S+', fm, flags=re.MULTILINE), f"{p.name} missing non-empty description"
            assert len(raw) <= 3_800, f"{p.name} exceeds 3,800 B hard ceiling: {len(raw)}"
            model_decision_files.append(p.name)

    assert always_on_files == ["governance_roles.md"]
    assert len(model_decision_files) == 23


def test_zero_stale_contradictions_and_upgrades_present() -> None:
    targets = [p for p in sorted(RULES_DIR.glob("*.md")) if p.name != "production_constants.md"]
    targets.extend(sorted(SKILLS_DIR.glob("*/SKILL.md")))

    hits: list[str] = []
    for path in targets:
        txt = path.read_text(encoding="utf-8")
        for label, pat in STALE_CONTRADICTION_PATTERNS:
            if re.search(pat, txt):
                hits.append(f"{path.relative_to(ROOT)} matched {label}")
    assert hits == [], f"Stale contradictions found: {hits}"

    # youtube-script/SKILL.md stays compact (<= 6,500 B) with retired v7 notes removed
    script_skill = SKILLS_DIR / "youtube-script" / "SKILL.md"
    legacy_v7 = SKILLS_DIR / "youtube-script" / "references" / "legacy_v7.md"
    assert not legacy_v7.exists()
    assert len(script_skill.read_bytes()) <= 6_500, f"youtube-script/SKILL.md exceeds 6,500 B: {len(script_skill.read_bytes())}"

    script_txt = script_skill.read_text(encoding="utf-8")
    assert "4-Stage Emotional Curve" in script_txt
    assert "1 Core Fact per 15s" in script_txt

    # Key P0-1 / P0-2 / P0-3 / P1-4 rule locks
    qa_txt = (RULES_DIR / "qa_gates_rules.md").read_text(encoding="utf-8")
    assert "Wrong / Exact Where / What Instead" in qa_txt
    assert "Mute & Hide Name Test" in qa_txt

    ref_txt = (RULES_DIR / "reference_depiction_rules.md").read_text(encoding="utf-8")
    assert "Semantic ID" in ref_txt
    assert "Ingredients" in ref_txt

    cam_txt = (RULES_DIR / "camera_choreography_rules.md").read_text(encoding="utf-8")
    assert "hero_low_angle" in cam_txt
    assert "35–45%" in cam_txt

    scene_txt = (RULES_DIR / "scene_depiction_rules.md").read_text(encoding="utf-8")
    assert "low-saturation" in scene_txt

    vps_txt = (RULES_DIR / "visual_prompt_spec.md").read_text(encoding="utf-8")
    assert "No voiceover, no narration, no background music, no lip movement." in vps_txt
