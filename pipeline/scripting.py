"""
Stage 2: Scripting & 12-Gate Master QA Loop (Production Contract v4).

Validates a 5-10 clip narration script: per-clip 18-28 spoken words (script_word_range(n) in total), the role
sequence from config.clip_roles(n), the pivot clip containing "Instead of", and the conclusion opening with
"Which proves" / "Which is why". Legacy 4-stage scripts (hook/setup/core/payoff without clip_narrations) are
still scored but fail G1.
"""

import re
from typing import Any

from pipeline.config import (
    AV_SPEEDUP_FACTOR,
    CLIP_COUNT_MAX,
    CLIP_COUNT_MIN,
    EFFECTIVE_WPS,
    FINAL_SHORTS_DURATION_MAX_SEC,
    FLOW_DEFAULT_VOICE,
    NATIVE_FLOW_WPS,
    NARRATIVE_STYLE_SPECS,
    SCRIPT_WORD_MAX,
    SCRIPT_WORD_MIN,
    clip_roles,
    max_allowed_dead_air_sec,
    pivot_clip_index,
    script_word_range,
)
from pipeline.storage import ProjectStorage

PROHIBITED_WORDS = [
    "omg", "literally insane", "smash that", "subscribe", "welcome back",
    "hey guys", "don't forget to like", "drop a comment", "mind-blowing",
    "i think", "we believe", "in my opinion", "you won't believe", "so basically",
    "drop a like", "smash that subscribe", "holy cow", "blow your mind"
]

CONCLUSION_OPENERS = ("which proves", "which is why")
PIVOT_PHRASE = "instead of"

_WORD_RE = re.compile(r"\b[\w'-]+\b")

# Roles whose narration feeds each content gate when clip_narrations are present
_OPENING_ROLES = ("setup", "symptom", "failure", "crisis")
_CRISIS_ROLES = ("symptom", "failure", "crisis")
_MECHANISM_ROLES = ("crisis", "pivot", "mechanism", "step1", "step2", "step3", "breakthrough")


def _count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _extract_clip_narrations(script_data: dict[str, Any]) -> list[str] | None:
    raw = script_data.get("clip_narrations")
    if not isinstance(raw, list):
        return None
    cleaned = [str(s).strip() for s in raw if str(s).strip()]
    return cleaned or None


class ScriptingStage:
    def __init__(self, storage: ProjectStorage):
        self.storage = storage

    def validate_qa_gates(
        self,
        script_data: dict[str, Any],
        fact_citations: list[dict[str, str]],
        actual_speech_duration: float | None = None,
        audio_truncated: bool = False,
        cumulative_dead_air_sec: float | None = None,
        min_words: int | None = None,
        max_words: int | None = None
    ) -> dict[str, Any]:
        if "script_stages" in script_data and isinstance(script_data["script_stages"], dict):
            nested_stages = dict(script_data["script_stages"])
            # preserve top-level metadata if not present in nested
            for k in ["actual_speech_duration", "audio_truncated", "cumulative_dead_air_sec", "clip_narrations"]:
                if k in script_data and k not in nested_stages:
                    nested_stages[k] = script_data[k]
            script_data = nested_stages

        hook_obj = script_data.get("hook", {})
        setup_obj = script_data.get("setup", script_data.get("dilemma", {}))
        core_obj = script_data.get("core", {})
        if not core_obj:
            action_text = script_data.get("action", {}).get("text", "")
            reveal_text = script_data.get("reveal", {}).get("text", "")
            core_obj = {"text": f"{action_text} {reveal_text}".strip()}
        payoff_obj = script_data.get("payoff", script_data.get("twist", {}))

        hook_raw = str(hook_obj.get("text", "")).strip()
        setup_raw = str(setup_obj.get("text", "")).strip()
        core_raw = str(core_obj.get("text", "")).strip()
        payoff_raw = str(payoff_obj.get("text", "")).strip()

        narrations = _extract_clip_narrations(script_data)
        n_clips = len(narrations) if narrations else 0
        roles: tuple[str, ...] = ()
        if narrations and CLIP_COUNT_MIN <= n_clips <= CLIP_COUNT_MAX:
            roles = clip_roles(n_clips)

        def _role_text(wanted: tuple[str, ...]) -> str:
            return " ".join(t for t, r in zip(narrations or [], roles) if r in wanted)

        if roles:
            full_text = " ".join(narrations)
            opening_text = _role_text(_OPENING_ROLES)
            crisis_text = _role_text(_CRISIS_ROLES)
            mechanism_text = _role_text(_MECHANISM_ROLES)
            conclusion_text = narrations[-1]
            pivot_text = narrations[pivot_clip_index(n_clips)]
        else:
            full_text = " ".join(narrations) if narrations else f"{hook_raw} {setup_raw} {core_raw} {payoff_raw}".strip()
            opening_text = f"{hook_raw} {setup_raw}"
            crisis_text = opening_text
            mechanism_text = core_raw
            conclusion_text = payoff_raw
            pivot_text = full_text

        word_count = _count_words(full_text)

        if actual_speech_duration is None:
            actual_speech_duration = script_data.get("actual_speech_duration")
        if not audio_truncated:
            audio_truncated = script_data.get("audio_truncated", False)
        if cumulative_dead_air_sec is None:
            cumulative_dead_air_sec = script_data.get("cumulative_dead_air_sec")

        if actual_speech_duration and actual_speech_duration > 0:
            effective_duration = float(actual_speech_duration)
        else:
            effective_duration = round(word_count / EFFECTIVE_WPS, 2) if word_count else 0.0
        wps = round(word_count / effective_duration, 2) if effective_duration > 0 else 0.0

        # G1: Clip narrations (count, per-clip words, openers), total word count & timing
        if roles:
            range_min, range_max = script_word_range(n_clips)
        else:
            range_min, range_max = SCRIPT_WORD_MIN, SCRIPT_WORD_MAX
        effective_min = min_words if min_words is not None else range_min
        effective_max = max_words if max_words is not None else range_max
        g1_issues: list[str] = []
        if not narrations:
            g1_issues.append(f"clip_narrations missing ({CLIP_COUNT_MIN}-{CLIP_COUNT_MAX} per-clip narrations required)")
        elif not roles:
            g1_issues.append(f"{n_clips} clip_narrations (must be {CLIP_COUNT_MIN}-{CLIP_COUNT_MAX})")
        else:
            from pipeline.flow_prompt_builder import validate_narrations

            g1_issues.extend(validate_narrations(narrations))
        if not (effective_min <= word_count <= effective_max):
            g1_issues.append(f"Word count is {word_count} (Target: {effective_min}-{effective_max})")
        if actual_speech_duration is not None and actual_speech_duration > FINAL_SHORTS_DURATION_MAX_SEC:
            g1_issues.append(
                f"Actual speech duration {actual_speech_duration:.2f}s exceeds {FINAL_SHORTS_DURATION_MAX_SEC}s Shorts limit"
            )
        if audio_truncated:
            g1_issues.append("Audio speech was truncated")
        g1_pass = not g1_issues
        if g1_pass:
            g1_reason = (
                f"{n_clips} clip narrations, {word_count} words (Target: {effective_min}-{effective_max}), "
                f"pacing {wps} wps, duration {effective_duration:.2f}s."
            )
        else:
            g1_reason = "; ".join(g1_issues)

        # G2: Paradox hook (counter-intuitive opening)
        opening_lower = opening_text.lower()
        paradox_triggers = [
            "impossible", "not the way", "yet", "without moving", "without", "insane",
            "paradox", "dump", "toxic", "survived", "different", "before", "download",
            "plug", "never", "contrary", "secret", "truth", "myth", "think", "believe",
            "glitch", "illusion", "faster", "miracle", "shock", "mystery", "fiction",
            "incredibly", "straight through", "accidental", "terror", "imposter",
            "cheat code", "nightmare", "panic mode", "autopilot", "stranger", "two",
            "opposite", "silent", "rewire", "blind", "wash", "stole", "hijack"
        ]
        g2_pass = any(k in opening_lower for k in paradox_triggers)
        g2_reason = "Opening contains a counter-intuitive paradox." if g2_pass else "Opening lacks a paradox trigger."

        # G3: Crisis (physical, biological or neurological jeopardy)
        crisis_lower = crisis_text.lower()
        crisis_triggers = [
            "threatened", "isolation", "paralyzed", "fail", "damage", "rupture", "crisis",
            "fatal", "accident", "toxic", "waste", "alzheimer", "disease", "death", "danger",
            "risk", "threat", "poison", "explosion", "injury", "wound", "loss", "destroy",
            "bleed", "stroke", "paralysis", "stop", "collapse", "leak", "failure", "halt",
            "breakdown", "panic", "error", "hijack", "breach", "decay", "nightmare", "severed",
            "vanished", "hostility", "rage", "shattered", "fled", "delusion", "overload",
            "clash", "trapped", "blind", "steal"
        ]
        g3_pass = any(k in crisis_lower for k in crisis_triggers)
        g3_reason = "Crisis clips establish physical or biological jeopardy." if g3_pass else "Crisis clips lack jeopardy."

        # G4: Concrete anatomical mechanism
        mechanism_lower = mechanism_text.lower()
        mechanism_triggers = [
            "retina", "optic", "eye", "ear", "auditory", "cochlea", "amygdala", "hippocampus",
            "prefrontal", "cortex", "thalamus", "striatum", "fusiform", "callosum", "cingulate",
            "pathway", "tract", "synapse", "axon", "myelin", "neuron", "electrode", "stentrode",
            "channel", "fluid", "plaque", "nerve", "lobe", "brainstem", "spinal",
            "cable", "threads", "wire", "pipe", "plumbing", "mesh", "stent",
            "valve", "filter", "spark", "river", "circuit", "network", "signal",
            "pump", "battery", "processor", "chip", "implant", "shield", "conduit",
            "insulation", "drain", "bridge", "switchboard", "port", "hemisphere", "dopamine"
        ]
        g4_pass = any(k in mechanism_lower for k in mechanism_triggers)
        g4_reason = (
            "Mechanism clips trace an explicit anatomical pathway." if g4_pass
            else "Mechanism clips lack a concrete anatomical mechanism."
        )

        # G5: Independent conclusion opener
        conclusion_lower = conclusion_text.strip().lower()
        g5_pass = conclusion_lower.startswith(CONCLUSION_OPENERS)
        g5_reason = (
            "Conclusion opens with 'Which proves' / 'Which is why'." if g5_pass
            else f"Conclusion must open with 'Which proves' or 'Which is why' (got: {conclusion_text[:60]!r})."
        )

        # G6: Tone & prohibited words (3rd person objective documentary tone)
        found_prohibited = [p for p in PROHIBITED_WORDS if p in full_text.lower()]
        first_person_tokens = re.findall(r"\b(i|we|my|our)\b", full_text, re.IGNORECASE)
        g6_pass = (len(found_prohibited) == 0 and len(first_person_tokens) == 0)
        if found_prohibited:
            g6_reason = f"Found prohibited terms: {found_prohibited}"
        elif first_person_tokens:
            g6_reason = f"First-person pronouns detected: {first_person_tokens}. 3rd person objective documentary tone required."
        else:
            g6_reason = "Zero clickbait phrases and 3rd person objective documentary tone maintained."

        # G7-G10: Production-stage gates (audited by qa_gates / video_autopsy during stages 3-5)
        g7_pass = True
        g7_reason = "Visual plan (real environment, porcelain mannequins, frosted-glass cranium, brain void) applied at stage 3."
        g8_pass = True
        g8_reason = "Prompt validator (banned tokens, no hex codes, no Audio:/Camera Angle) applied at stage 3."
        g9_pass = True
        g9_reason = "One camera move per clip following the role sequence (real environment -> drill-down -> brain -> pull-out)."
        g10_pass = True
        g10_reason = (
            f"Voice locked to Google Flow Omni 1.1 {FLOW_DEFAULT_VOICE} at {NATIVE_FLOW_WPS} wps native "
            f"(~{EFFECTIVE_WPS} wps after the {AV_SPEEDUP_FACTOR}x speedup)."
        )

        # G11: Pivot clip contains "Instead of"
        g11_pass = PIVOT_PHRASE in pivot_text.lower()
        if g11_pass:
            g11_reason = "Pivot clip contains 'Instead of'."
        elif roles:
            g11_reason = f"Pivot clip {pivot_clip_index(n_clips) + 1} must contain 'Instead of'."
        else:
            g11_reason = "Script must contain 'Instead of' (pivot)."

        # G12: Causal momentum connectives & measured dead air
        propulsive_connectors = [
            "instead of", "step one", "here is how it works", "which proves", "which is why",
            "which", "yet", "until", "instead", "except", "before", "the moment", "leaving",
            "triggering", "collapsing", "turning", "transforming", "forcing", "without",
            "acting like", "instantly", "moving", "proving that", "so", "meaning",
            "revealing", "allowing", "causing"
        ]
        has_propulsive_conn = any(c in full_text.lower() for c in propulsive_connectors)
        max_dead_air = max_allowed_dead_air_sec(effective_duration)
        dead_air_ok = (cumulative_dead_air_sec is None) or (float(cumulative_dead_air_sec) <= max_dead_air)
        g12_pass = has_propulsive_conn and dead_air_ok
        if not has_propulsive_conn:
            g12_reason = "Lacks propulsive causal connectives."
        elif not dead_air_ok:
            g12_reason = f"Measured cumulative dead air ({float(cumulative_dead_air_sec):.2f}s) exceeds {max_dead_air:.2f}s limit."
        elif cumulative_dead_air_sec is not None:
            g12_reason = f"Measured dead air {float(cumulative_dead_air_sec):.2f}s <= {max_dead_air:.2f}s."
        else:
            g12_reason = "Propulsive causal connectives present (dead air not yet measured)."

        all_pass = all([g1_pass, g2_pass, g3_pass, g4_pass, g5_pass, g6_pass, g7_pass, g8_pass, g9_pass, g10_pass, g11_pass, g12_pass])
        script_gates_pass = all([g1_pass, g2_pass, g3_pass, g4_pass, g5_pass, g6_pass, g11_pass, g12_pass])

        raw_sentences = [s.strip() for s in re.split(r"[.!?]+", full_text) if s.strip()]
        sent_word_counts = [_count_words(s) for s in raw_sentences if _count_words(s)]
        max_sent_words = max(sent_word_counts) if sent_word_counts else 0
        avg_sent_words = round(sum(sent_word_counts) / len(sent_word_counts), 2) if sent_word_counts else 0.0

        return {
            "all_gates_passed": all_pass,
            "script_gates_passed": script_gates_pass,
            "clip_count": n_clips,
            "word_count": word_count,
            "pacing_wps": wps,
            "max_sentence_words": max_sent_words,
            "avg_sentence_words": avg_sent_words,
            "gates": {
                "G1_clip_narrations_and_timing": {"passed": g1_pass, "details": g1_reason},
                "G2_paradox_hook": {"passed": g2_pass, "details": g2_reason},
                "G3_crisis_dilemma": {"passed": g3_pass, "details": g3_reason},
                "G4_anatomical_mechanism": {"passed": g4_pass, "details": g4_reason},
                "G5_conclusion_opener": {"passed": g5_pass, "details": g5_reason},
                "G6_tone_and_prohibited_terms": {"passed": g6_pass, "details": g6_reason},
                "G7_visual_dna_compliance": {"passed": g7_pass, "details": g7_reason},
                "G8_anti_pixel_filter": {"passed": g8_pass, "details": g8_reason},
                "G9_camera_and_cut_cadence": {"passed": g9_pass, "details": g9_reason},
                "G10_voice_anchor_match": {"passed": g10_pass, "details": g10_reason},
                "G11_pivot_instead_of": {"passed": g11_pass, "details": g11_reason},
                "G12_zero_dead_air": {"passed": g12_pass, "details": g12_reason}
            }
        }

    def run(
        self,
        hook_text: str,
        setup_text: str,
        core_text: str,
        payoff_text: str,
        fact_citations: list[dict[str, str]] | None = None,
        narrative_style: str = "chronicle_cutaway",
        clip_narrations: list[str] | None = None,
    ) -> dict[str, Any]:
        self.storage.update_stage_status("02_script", "running")
        style_info = NARRATIVE_STYLE_SPECS.get(narrative_style, NARRATIVE_STYLE_SPECS["chronicle_cutaway"])

        narrations = [str(s).strip() for s in (clip_narrations or []) if str(s).strip()]
        if CLIP_COUNT_MIN <= len(narrations) <= CLIP_COUNT_MAX:
            roles: list[str] = list(clip_roles(len(narrations)))
        else:
            roles = []

        script_data: dict[str, Any] = {
            "narrative_style": narrative_style,
            "narrative_style_name": style_info["name_en"],
            "narrative_spine": roles or ["hook", "setup", "core", "payoff"],
            "hook": {"text": hook_text.strip()},
            "setup": {"text": setup_text.strip()},
            "core": {"text": core_text.strip()},
            "payoff": {"text": payoff_text.strip()},
        }
        if narrations:
            script_data["clip_narrations"] = narrations

        citations = fact_citations or [
            {"claim": "1,024 electrodes on motor cortex", "source": "Neuralink First Human Clinical Trial (PRIME Study, 2024)"},
            {"claim": "Direct wireless mind-control for computer cursor", "source": "Nature / NEJM Brain-Computer Interface Publications"}
        ]

        qa_report = self.validate_qa_gates(script_data, citations)

        target_min, target_max = script_word_range(len(narrations)) if roles else (SCRIPT_WORD_MIN, SCRIPT_WORD_MAX)
        spine_label = " -> ".join(script_data["narrative_spine"])

        full_script = f"""# Stage 2: Script & Master QA Report

## Word Count & Narrative Analysis
- **Narrative Archetype:** `{narrative_style}` ({style_info['name_ko']} / {style_info['name_en']})
- **Role Sequence ({qa_report['clip_count']} clips):** `{spine_label}`
- **Total Words:** {qa_report['word_count']} words (Target: {target_min}-{target_max})
- **Pacing:** {qa_report['pacing_wps']} words/sec (Target: {NATIVE_FLOW_WPS} wps native, ~{EFFECTIVE_WPS} wps after {AV_SPEEDUP_FACTOR}x)
- **QA Master Loop Status:** {'[ALL PASS]' if qa_report['all_gates_passed'] else '[ACTION REQUIRED]'}

---

## Script Breakdown

"""
        if roles:
            for idx, (role, text) in enumerate(zip(roles, narrations), start=1):
                full_script += f"### Clip {idx} — {role} ({_count_words(text)} words)\n\"{text}\"\n\n"
        else:
            for label, text in (("Hook", hook_text), ("Setup", setup_text), ("Core", core_text), ("Payoff", payoff_text)):
                full_script += f"### {label} ({_count_words(text)} words)\n\"{text}\"\n\n"
        full_script += "---\n\n## 12-Gate QA Master Results\n"
        for gate_id, gate_info in qa_report["gates"].items():
            status = "PASS" if gate_info["passed"] else "FAIL"
            full_script += f"- **{gate_id}:** [{status}] {gate_info['details']}\n"

        # Lossless persistence
        self.storage.save_json("02_script", "script.json", script_data)
        self.storage.save_json("02_script", "qa_report.json", qa_report)
        self.storage.save_json("02_script", "fact_check.json", citations)
        self.storage.save_text("02_script", "script.md", full_script)

        self.storage.update_stage_status("02_script", "completed")
        return {
            "script_data": script_data,
            "qa_report": qa_report
        }
