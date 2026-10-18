"""
Stage 1: Ideation & Research Ingestion
Evaluates topics via the 5-dimension scoring rubric and formulates Paradox Hooks.
"""

from typing import Any

from pipeline.storage import ProjectStorage


class IdeationStage:
    def __init__(self, storage: ProjectStorage):
        self.storage = storage

    def run(
        self,
        topic: str,
        pillar: str,
        source_url: str,
        source_tier: int,
        core_facts: str,
        doi: str | None = None,
        scores: dict[str, float] | None = None,
        paradox_statement: str | None = None,
        story_context: dict[str, str] | None = None,
        physical_metaphor: str | None = None,
    ) -> dict[str, Any]:
        self.storage.update_stage_status("01_ideation", "running")

        # Default or provided scoring rubric (1.0 to 5.0)
        rubric = scores or {
            "cutaway_feasibility": 5.0,  # 3D cutaway suitability
            "paradox_hook": 5.0,         # Common sense violation
            "recency_impact": 4.5,       # Clinical relevance & breakthrough
            "fact_rigor": 5.0,           # PubMed / clinical trial verification
            "debate_dilemma": 4.5        # Ethical / societal dilemma
        }

        # Weighted calculation (AGENTS.md / bci-news-hunt)
        weighted_score = (
            rubric["cutaway_feasibility"] * 0.30 +
            rubric["paradox_hook"] * 0.25 +
            rubric["recency_impact"] * 0.20 +
            rubric["fact_rigor"] * 0.15 +
            rubric["debate_dilemma"] * 0.10
        )

        research_card = {
            "topic": topic,
            "pillar": pillar,
            "source_url": source_url,
            "source_tier": source_tier,
            "doi": doi or "N/A",
            "scores": rubric,
            "weighted_score": round(weighted_score, 2),
            "core_facts": core_facts,
            "story_context": story_context or {},
            "physical_metaphor": physical_metaphor or "",
            "min_recommended_threshold": 3.5,
            "passed_threshold": weighted_score >= 3.5
        }

        # Paradox Hook definition
        hook_data = {
            "hook_formula": "[A] happens, yet [B] occurs. It sounds completely impossible.",
            "paradox_statement": paradox_statement or "A paralyzed person moves cursors with pure thought. It sounds completely impossible.",
            "dissonance_trigger": "Physical body is paralyzed, but digital agency is restored without moving a muscle."
        }

        # Markdown representation
        markdown_summary = f"""# Stage 1: Ideation & Research Card

## Topic: {topic}
- **Pillar:** {pillar}
- **Source Tier:** Tier {source_tier} ({source_url})
- **PubMed DOI:** {doi or 'N/A'}
- **Weighted Score:** {round(weighted_score, 2)} / 5.00 (Threshold: 3.50)

### 5-Dimension Rubric
- 3D Cutaway Feasibility (30%): {rubric['cutaway_feasibility']}
- Paradox Hook Potential (25%): {rubric['paradox_hook']}
- Recency & Impact (20%): {rubric['recency_impact']}
- Fact Rigor (15%): {rubric['fact_rigor']}
- Debate & Dilemma (10%): {rubric['debate_dilemma']}

### Core Facts
{core_facts}

### Paradox Hook
> {hook_data['paradox_statement']}
"""

        # Lossless persistence
        self.storage.save_json("01_ideation", "research_card.json", research_card)
        self.storage.save_json("01_ideation", "paradox_hook.json", hook_data)
        self.storage.save_text("01_ideation", "source_data.md", markdown_summary)

        self.storage.update_stage_status("01_ideation", "completed")
        return {
            "research_card": research_card,
            "hook_data": hook_data
        }
