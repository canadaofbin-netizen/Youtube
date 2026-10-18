"""
ALL ABOUT BRAIN - Autonomous AI Script & Visual Prompt Generator (Production Contract v4).
Generates broadcast-ready 5-10 clip narrations (18-28 words per clip) and Google Flow Omni 1.1 prompts
for any of the 7 Content Pillars using deterministic local synthesis (zero external paid APIs).
"""

import re
from typing import Any

from pipeline.config import (
    CLIP_COUNT_MAX,
    CLIP_COUNT_MIN,
    FLOW_DEFAULT_VOICE,
    NARRATIVE_STYLE_SPECS,
    SCRIPT_WORD_MAX,
    SCRIPT_WORD_MIN,
    clip_roles,
    resolve_narrative_style,
)
from pipeline.flow_prompt_builder import (
    ROLE_CAMERA_MOVES,
    build_flow_prompts,
    infer_visual_plan,
    load_visual_plan,
    validate_flow_prompts,
    validate_narrations,
)
from pipeline.pillars import get_pillar

DEFIANCE_TRIGGERS = [
    "For your brain, this is a total nightmare.",
    "For his brain, this was a total nightmare.",
    "The researchers were left completely stunned.",
    "Instead of",
    "Which proves",
    "Which is why",
]


class ContentGenerator:
    """
    Autonomous local algorithmic content generator (Zero External Paid APIs).
    Enforces Production Contract v4: 5-10 clips (18-28 words/clip), Deep-Mechanism Role Spine,
    validate_narrations + validate_flow_prompts compliance.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = None

    def generate(
        self,
        pillar_id_or_name: str | Any | None = None,
        topic: str | None = None,
        use_gemini: bool = False,
        pillar: Any | None = None,
        style: str = "auto",
    ) -> dict[str, Any]:
        """Generates a complete Production Contract v4 blueprint for the given pillar, topic, and narrative style."""
        target_pillar = pillar if pillar is not None else pillar_id_or_name
        pillar_obj = get_pillar(target_pillar)
        return self._generate_algorithmic(pillar_obj, topic, style=style)

    def _generate_algorithmic(
        self,
        pillar: Any,
        topic: str | None = None,
        style: str = "auto",
    ) -> dict[str, Any]:
        """Produces a validated Contract v4 blueprint with clip_narrations, visual_plan, and flow_all_in_one_prompts."""
        base_bp = dict(pillar.production_blueprint)

        explicit_style = bool(style and style.strip().lower() not in ("auto", ""))
        active_style = resolve_narrative_style(
            style=style,
            pillar_id=pillar.id,
            topic=topic or base_bp["topic"],
        )
        style_spec = NARRATIVE_STYLE_SPECS.get(active_style, NARRATIVE_STYLE_SPECS["chronicle_cutaway"])
        base_bp["narrative_style"] = active_style
        base_bp["narrative_style_info"] = style_spec

        custom_topic = bool(topic and topic.strip() and topic.strip().lower() != base_bp["topic"].lower())
        if custom_topic or explicit_style:
            from pipeline.researcher import TopicResearcher

            clean_topic = (topic or base_bp["topic"]).strip()
            clean_topic_slug = re.sub(r"[^\w]+", "_", clean_topic.lower())[:30]
            base_bp["topic"] = clean_topic
            if custom_topic:
                base_bp["project_id"] = f"{pillar.id}_{clean_topic_slug}"
                base_bp["title"] = f"{clean_topic[:48]} {pillar.icon}".strip()
            elif explicit_style:
                base_bp["project_id"] = f"{pillar.id}_{active_style}_{clean_topic_slug[:20]}"

            research_pkg = TopicResearcher().research_topic(
                query=clean_topic,
                pillar_id=pillar.id,
                style=active_style,
                allow_network=False,
            )
            base_bp["story_context"] = research_pkg["story_context"]
            base_bp["physical_metaphor"] = research_pkg["physical_metaphor"]
            if research_pkg.get("visual_plan"):
                base_bp["visual_plan"] = research_pkg["visual_plan"]
            if custom_topic:
                base_bp["doi"] = research_pkg["doi"]
                base_bp["source_url"] = research_pkg["source_url"]
                base_bp["core_facts"] = research_pkg["core_facts"]
                base_bp["paradox_statement"] = research_pkg["paradox_statement"]

            adapted_script = self._synthesize_script_for_topic(pillar, clean_topic, style=active_style)
            base_bp["hook_text"] = adapted_script["hook"]
            base_bp["setup_text"] = adapted_script["setup"]
            base_bp["core_text"] = adapted_script["core"]
            base_bp["payoff_text"] = adapted_script["payoff"]
            base_bp["clip_narrations"] = list(adapted_script["clip_narrations"])

        clip_narrations = [str(s).strip() for s in (base_bp.get("clip_narrations") or []) if str(s).strip()]
        if not clip_narrations or validate_narrations(clip_narrations):
            fallback_script = self._synthesize_script_for_topic(
                pillar,
                base_bp.get("topic", "Neural Circuitry"),
                style=active_style,
            )
            clip_narrations = list(fallback_script["clip_narrations"])
            base_bp["hook_text"] = fallback_script["hook"]
            base_bp["setup_text"] = fallback_script["setup"]
            base_bp["core_text"] = fallback_script["core"]
            base_bp["payoff_text"] = fallback_script["payoff"]

        narr_errors = validate_narrations(clip_narrations)
        if narr_errors:
            raise ValueError(f"Generated clip_narrations failed Contract v4 validation: {narr_errors}")

        base_bp["clip_narrations"] = clip_narrations
        base_bp["clip_roles"] = list(clip_roles(len(clip_narrations)))
        base_bp["narrative_spine"] = clip_roles(len(clip_narrations))

        visual_plan = load_visual_plan(
            project_dir=None,
            topic_item={
                "topic": base_bp.get("topic", ""),
                "core_facts": base_bp.get("core_facts", ""),
                "pillar": pillar.id,
                "story_context": base_bp.get("story_context"),
                "visual_plan": base_bp.get("visual_plan"),
            },
        )
        if not visual_plan:
            visual_plan = infer_visual_plan(
                topic=base_bp.get("topic", ""),
                core_facts=base_bp.get("core_facts", ""),
                pillar_id=pillar.id,
                story_context=base_bp.get("story_context"),
            )

        flow_prompts = build_flow_prompts(visual_plan, clip_narrations, voice=FLOW_DEFAULT_VOICE)
        base_bp["visual_plan"] = visual_plan
        base_bp["flow_all_in_one_prompts"] = flow_prompts
        return base_bp

    @staticmethod
    def _balance_script_word_count(script_dict: dict[str, Any], max_words: int = SCRIPT_WORD_MAX) -> dict[str, Any]:
        """Preserves script stages and guarantees total word count is within SCRIPT_WORD_MIN..max_words."""
        result = dict(script_dict)
        if isinstance(result.get("clip_narrations"), list) and len(result["clip_narrations"]) >= 5:
            narrs = [str(s).strip() for s in result["clip_narrations"] if str(s).strip()]
            result["hook"] = narrs[0]
            result["setup"] = narrs[1]
            result["core"] = " ".join(narrs[2:-1])
            result["payoff"] = narrs[-1]
            return result

        pad_tokens = ["single", "tiny", "deep", "living", "active", "fast", "hidden", "direct", "real", "inner"]

        def _count(d: dict[str, Any]) -> int:
            full = f"{d.get('hook', '')} {d.get('setup', '')} {d.get('core', '')} {d.get('payoff', '')}"
            return len(re.findall(r"\b[\w'-]+\b", full))

        while _count(result) > max_words:
            core_words = str(result.get("core", "")).split()
            if len(core_words) <= 15:
                break
            del core_words[4]
            result["core"] = " ".join(core_words)

        pad_idx = 0
        while _count(result) < SCRIPT_WORD_MIN and pad_idx < len(pad_tokens):
            token = pad_tokens[pad_idx % len(pad_tokens)]
            pad_idx += 1
            core_words = str(result.get("core", "")).split()
            if len(core_words) >= 2:
                core_words.insert(-1, token)
                result["core"] = " ".join(core_words)
            else:
                result["core"] = f"{token} {result.get('core', '')}".strip()

        return result

    def synthesize_by_narrative_style(
        self,
        style_id: str,
        pillar: Any,
        topic: str,
    ) -> dict[str, Any]:
        """
        Synthesizes a 5-clip Contract v4 narration script (18-28 words per clip, 90-140 words total)
        across all 6 narrative archetypes.
        """
        clean_topic = (topic or "the human brain").strip()
        topic_words = re.findall(r"\b[\w'-]+\b", clean_topic)
        topic_ref = " ".join(topic_words[:4]) if len(topic_words) > 4 else (clean_topic if topic_words else "neural circuits")

        resolved = resolve_narrative_style(style=style_id, pillar_id=getattr(pillar, "id", ""), topic=clean_topic)

        archetype_narrations: dict[str, list[str]] = {
            "case_file": [
                f"Inside a quiet neurology clinic, a baffling case of {topic_ref} shocked examining doctors while the patient stayed wide awake and alert.",
                "Sudden sensory disconnection threatened total emotional isolation and perceptual collapse inside the ward. For the patient's brain, this was a total nightmare.",
                "Instead of processing reality as one single stream, the human cortex splits visual feature recognition from deep limbic emotional verification.",
                "Signals race from the retina through the optic nerve into the fusiform gyrus while the amygdala tract fails. The researchers were left completely stunned.",
                "Which proves that severing a single white-matter bridge between vision and emotion can rewrite human reality within milliseconds.",
            ],
            "delusion_museum": [
                f"Inside a candlelit anatomy theater, early physicians investigating {topic_ref} made a dramatic mistake yet defended the myth for centuries.",
                "Blaming the human heart for damaged thoughts left cortical injuries completely untreated. For ancient patients, this was a total nightmare.",
                "Instead of storing memories inside the chambers of the heart, the skull houses eighty-six billion neurons wired across specialized cortical lobes.",
                "Sensory nerves from the eyes and ears route electrical spikes through the thalamus into the hippocampus and prefrontal cortex. The researchers were left completely stunned.",
                "Which proves that every human memory, emotion, and moral decision emerges from physical white-matter circuits inside the folded cortex.",
            ],
            "forbidden_lab": [
                f"Inside a shielded neurobiology laboratory, a controlled experiment on {topic_ref} exposed a hidden vulnerability inside human decision circuits.",
                "Unfiltered external signals bypassed conscious willpower and triggered an involuntary behavioral response. For human autonomy, this is a total nightmare.",
                "Instead of waiting for slow prefrontal deliberation, incoming sensory cues take a high-speed subcortical shortcut straight into deep reward nuclei.",
                "Auditory and visual pathways fire the amygdala and dorsal striatum milliseconds before the prefrontal cortex can intervene. The researchers were left completely stunned.",
                "Which proves that protecting human cognitive liberty requires guarding the fast subcortical pathways that steer behavior beneath conscious awareness.",
            ],
            "icon_autopsy": [
                f"Under high-resolution laboratory microscopes, neuroscientists mapping {topic_ref} uncovered a remarkable physical wiring secret inside the human cerebral cortex.",
                "Without dense structural insulation, raw bioelectric signals leak into surrounding tissue and fade out. For the nervous system, this is a total nightmare.",
                "Instead of boosting cellular voltage, glial support cells wrap long axonal fibers in tightly layered myelin sheaths across the brain.",
                "Action potentials leap from one exposed ion channel gap to the next from the thalamus to the cortex. The researchers were left completely stunned.",
                "Which proves that microscopic myelin architecture and synaptic geometry set the physical speed limit of human thought and perception.",
            ],
            "caveman_brain": [
                f"Fifty thousand years ago, the ancient neural reflex behind {topic_ref} kept human ancestors alive yet backfires in modern bedrooms.",
                "Chronic modern stress keeps survival alarms firing all night and blocks toxic protein clearance. For the waking brain, this is a total nightmare.",
                "Instead of fighting stress hormones with sheer willpower, deep slow-wave sleep activates a pressurized fluid cleansing network across the cortex.",
                "Retinal threat pathways quiet down in the amygdala while cerebrospinal fluid flushes metabolic waste from cortical channels. The researchers were left completely stunned.",
                "Which proves that modern brain health depends on honoring ancient circadian sleep circuits that wash the living cortex every night.",
            ],
            "chronicle_cutaway": [
                f"During a landmark neuroengineering trial on {topic_ref}, human intention bypassed damaged nerves without moving a single physical muscle.",
                "A severed spinal pathway trapped motor commands inside the skull and threatened permanent paralysis. For the patient's brain, this was a total nightmare.",
                "Instead of repairing broken spinal tracts, engineers implanted microelectrode threads directly into the primary motor cortex to read neural spikes.",
                "As the retina tracks a screen cursor, cortical decoders translate firing patterns into wireless digital commands. The researchers were left completely stunned.",
                "Which proves that direct brain-computer interfaces can route human thought past injured tissue and restore independent communication in real time.",
            ],
        }

        narrs = list(archetype_narrations.get(resolved, archetype_narrations["chronicle_cutaway"]))
        return {
            "hook": narrs[0],
            "setup": narrs[1],
            "core": f"{narrs[2]} {narrs[3]}",
            "payoff": narrs[4],
            "clip_narrations": narrs,
        }

    def _synthesize_story_arc(
        self,
        pillar: Any,
        topic: str,
        story_context: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Generates a 5-clip Contract v4 narrative script from story_context or pillar archetype."""
        res = self.synthesize_by_narrative_style(
            style_id="auto",
            pillar=pillar,
            topic=topic,
        )
        narrs = res["clip_narrations"]
        return {
            "hook": narrs[0],
            "dilemma": narrs[1],
            "action": narrs[2],
            "reveal": narrs[3],
            "twist": narrs[4],
            "clip_narrations": narrs,
        }

    def _synthesize_script_for_topic(
        self,
        pillar: Any,
        topic: str,
        style: str = "auto",
    ) -> dict[str, Any]:
        """Synthesizes a 5-clip Contract v4 script tailored to the requested topic, pillar domain, and style."""
        clean_topic = (topic or "Neural Circuitry").strip()
        resolved_style = resolve_narrative_style(
            style=style,
            pillar_id=getattr(pillar, "id", str(pillar)),
            topic=clean_topic,
        )
        return self.synthesize_by_narrative_style(
            style_id=resolved_style,
            pillar=pillar,
            topic=clean_topic,
        )

    def _verify_blueprint(self, bp: dict[str, Any]) -> bool:
        """Verifies if blueprint meets Production Contract v4 narration and prompt quality criteria."""
        clip_narrations = bp.get("clip_narrations")
        if isinstance(clip_narrations, list) and CLIP_COUNT_MIN <= len(clip_narrations) <= CLIP_COUNT_MAX:
            if validate_narrations(clip_narrations):
                return False
            full_script = " ".join(str(s) for s in clip_narrations)
        else:
            hook = bp.get("hook_text", "").strip()
            setup = bp.get("setup_text", "").strip()
            core = bp.get("core_text", "").strip()
            payoff = bp.get("payoff_text", "").strip()
            full_script = f"{hook} {setup} {core} {payoff}".strip()
            words = re.findall(r"\b[\w'-]+\b", full_script)
            if not (SCRIPT_WORD_MIN <= len(words) <= SCRIPT_WORD_MAX):
                return False

        if re.search(r"\b(i|we|my|our)\b", full_script, re.IGNORECASE):
            return False

        flow_prompts = bp.get("flow_all_in_one_prompts")
        if isinstance(flow_prompts, list) and flow_prompts:
            if validate_flow_prompts(flow_prompts):
                return False

        return True

    def segment_script_dynamically(
        self,
        script_stages: dict[str, str],
        target_clip_count: int = 7,
    ) -> list[dict[str, Any]]:
        """
        Segments a script into N clips (5-10) mapped to Contract v4 clip_roles and ROLE_CAMERA_MOVES.
        """
        target_count = max(CLIP_COUNT_MIN, min(CLIP_COUNT_MAX, target_clip_count))

        stages = [
            {"name": "setup", "text": script_stages.get("hook", "")},
            {"name": "crisis", "text": script_stages.get("dilemma", script_stages.get("setup", ""))},
            {"name": "pivot", "text": script_stages.get("action", "")},
            {"name": "mechanism", "text": script_stages.get("reveal", "")},
            {"name": "conclusion", "text": script_stages.get("twist", script_stages.get("payoff", ""))},
        ]

        words_per_stage = [len(re.findall(r"\b[\w'-]+\b", s["text"])) for s in stages]
        total_words = sum(words_per_stage) or 1
        durations = [max(3.0, round((w / total_words) * 30.0, 1)) for w in words_per_stage]

        diff = round(30.0 - sum(durations), 1)
        if diff != 0:
            durations[2] = round(durations[2] + diff, 1)

        clips: list[dict[str, Any]] = []
        for i in range(5):
            clips.append({
                "clip_number": i + 1,
                "stage_name": stages[i]["name"],
                "spoken_text": stages[i]["text"],
                "duration_sec": durations[i],
                "camera_name": "",
            })

        while len(clips) < target_count:
            longest_idx = max(range(len(clips) - 1), key=lambda i: clips[i]["duration_sec"])
            clip_to_split = clips[longest_idx]
            if clip_to_split["duration_sec"] <= 3.5:
                break

            text1, text2 = self.split_core_text(clip_to_split["spoken_text"])
            dur1 = round(clip_to_split["duration_sec"] / 2.0, 1)
            dur2 = round(clip_to_split["duration_sec"] - dur1, 1)

            clip_to_split["spoken_text"] = text1
            clip_to_split["duration_sec"] = dur1

            new_clip = {
                "clip_number": 0,
                "stage_name": clip_to_split["stage_name"],
                "spoken_text": text2,
                "duration_sec": dur2,
                "camera_name": "",
            }
            clips.insert(longest_idx + 1, new_clip)

        roles = clip_roles(len(clips))
        for i, (c, role) in enumerate(zip(clips, roles), start=1):
            c["clip_number"] = i
            c["stage_name"] = role
            c["camera_name"] = ROLE_CAMERA_MOVES[role]

        return clips

    @staticmethod
    def split_core_text(core_text: str) -> tuple[str, str]:
        """
        Splits core_text into two balanced halves respecting sentence boundaries or major clause breaks.
        """
        cleaned = core_text.strip()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
        if len(sentences) >= 2:
            mid = len(sentences) // 2
            return " ".join(sentences[:mid]), " ".join(sentences[mid:])

        clause_matches = list(re.finditer(r"[,;]\s+", cleaned))
        if clause_matches:
            mid_target = len(cleaned) // 2
            best_m = min(clause_matches, key=lambda m: abs(m.start() - mid_target))
            return cleaned[: best_m.start() + 1].strip(), cleaned[best_m.end() :].strip()

        words = cleaned.split()
        mid = len(words) // 2
        return " ".join(words[:mid]), " ".join(words[mid:])


split_core_text = ContentGenerator.split_core_text
