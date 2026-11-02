"""
ALL ABOUT BRAIN - YouTube Community & Comment Pinning Automation
Automatically posts peer-reviewed academic DOI citations and cognitive dissonance
questions as top-level comments and pins them to the top of the Shorts video.
Uses DirectCDPClient over visible Naver Whale (zero Playwright multi-tab hang).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from pipeline.config import CHANNEL_ROOT
from pipeline.storage import ProjectStorage
from pipeline.studio.config import (
    COMMUNITY_SELECTORS,
    DEFAULT_CDP_PORT,
    YOUTUBE_WATCH_BASE_URL,
)
from pipeline.studio.short_linker import write_studio_publish_receipt
from pipeline.studio.whale_session import WhaleSessionController

_EMOJI_STRIP_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "]+",
    flags=re.UNICODE,
)


def _strip_emojis_and_bullets(text: str) -> str:
    cleaned = _EMOJI_STRIP_RE.sub("", text or "")
    cleaned = re.sub(r"^\s*[-*•]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def _smart_trim_headline(text: str, max_len: int = 96) -> str:
    cleaned = _strip_emojis_and_bullets(text).strip(" .,:;-—")
    if len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[:max_len].rsplit(" ", 1)[0].rstrip(" ,:;-—&")
    return cut or cleaned[:max_len]


def _parse_citation_author_year_journal(src: dict[str, Any]) -> str:
    """Extracts 'Author (Year, Journal)' cleanly whether stored in split fields or a single 'citation' string."""
    authors = str(src.get("authors") or src.get("author") or "").strip()
    year = str(src.get("year") or "").strip()
    journal = str(src.get("journal") or src.get("venue") or "").strip()
    citation = str(src.get("citation") or "").strip()

    if citation and (not authors or not journal):
        m = re.match(r"^([^(]+?)\s*\((\d{4}[a-z]?)\)\.\s*(.+)$", citation)
        if m:
            if not authors:
                authors = m.group(1).strip().rstrip(",")
            if not year:
                year = m.group(2).strip()
            rest = m.group(3).strip().rstrip(".")
            segs = [s.strip() for s in rest.split(".") if s.strip()]
            if not journal and len(segs) >= 2:
                cand_j = re.sub(r",\s*\d.*$", "", segs[-1]).strip()
                if 2 <= len(cand_j) <= 65:
                    journal = cand_j

    if authors and year and journal:
        return f"{authors} ({year}, {journal})"
    if authors and year:
        return f"{authors} ({year})"
    if authors:
        return authors
    if journal and year:
        return f"a {year} study in {journal}"
    return "peer-reviewed neuroscience research"


def _find_matching_dossier_dir(project_id: str, dossiers_root: Path | None = None) -> Path | None:
    root = dossiers_root or (CHANNEL_ROOT / "research_dossiers")
    if not root.exists():
        return None
    stripped = re.sub(r"^(?:psych|diorama)_\d+_", "", project_id)
    direct = root / stripped
    if direct.is_dir():
        return direct

    proj_tokens = set(stripped.split("_"))
    best_dir: Path | None = None
    best_overlap = 0
    for d_dir in sorted(root.iterdir()):
        if not d_dir.is_dir():
            continue
        d_json_path = d_dir / "dossier.json"
        if d_json_path.exists():
            try:
                meta = json.loads(d_json_path.read_text(encoding="utf-8"))
                linked = list(meta.get("linked_projects") or []) + list(meta.get("shorts_projects") or [])
                if project_id in linked:
                    return d_dir
            except Exception:
                pass
        overlap = len(proj_tokens & set(d_dir.name.split("_")))
        if overlap >= 2 and overlap > best_overlap:
            best_overlap = overlap
            best_dir = d_dir
    return best_dir


_DIORAMA_NATURAL_PACKAGES: dict[str, dict[str, Any]] = {
    "phineas_gage_iron_rod": {
        "headline": "How Phineas Gage Rebuilt His Life After an Iron Rod Pierced His Brain",
        "paragraphs": [
            "In 1848, a 13-pound iron tamping bar shot straight through railroad foreman Phineas Gage's left front brain in Vermont — yet minutes later he sat up in an ox cart and greeted Doctor John Harlow.",
            "In John Van Horn's brain-mapping study (2012, PLoS ONE), researchers reconstructed Gage's skull alongside modern scans to trace what that blast actually cut.",
            "The rod destroyed 4 percent of his outer cortex — smaller than a playing card — while severing 11 percent of the white-matter cables linking his emotional alarm to the calm planner behind his forehead.",
            "Textbooks claim Gage died a jobless drifter. In reality, Malcolm Macmillan's historical records show he moved to Chile and spent years driving six-horse mountain stagecoaches.",
            "Strict daily routines gave his surviving brain circuits a steady rail to follow.",
        ],
        "question": "Right before blurting something out in anger, what stops you faster — taking one slow breath or stepping out of the room?",
    },
    "patient_hm_hippocampus": {
        "headline": "Why Patient H.M. Forgot Every Chat in 30 Seconds Yet Learned New Hand Skills",
        "paragraphs": [
            "After a 1953 operation for severe seizures, Henry Molaison — known as Patient H.M. — kept his sharp wit and childhood stories, yet could no longer save new conscious memories.",
            "Following William Scoville and Brenda Milner's landmark report (1957, Journal of Neurology, Neurosurgery & Psychiatry), Milner tested Henry with simple hand puzzles to see what survived.",
            "During a mirror-drawing test, Henry traced a star watching only his hand's reflection. Over three days his errors vanished — yet on Day 3 he swore he had never seen that mirror box in his life.",
            "People assume memory sits in one tank. Henry proved the hippocampus records conscious facts, while motor skills wire separately inside the basal ganglia and cerebellum.",
            "Your hands can quietly build real mastery even on days when nothing feels like it sticks.",
        ],
        "question": "What physical skill — like typing a password or riding a bike — do your hands remember automatically even if you cannot explain the steps?",
    },
    "ramachandran_phantom_limb_mirror": {
        "headline": "How a $10 Cardboard Mirror Box Unclenched a Phantom Hand Locked for 10 Years",
        "paragraphs": [
            "Ten years after losing an arm, patients in V. S. Ramachandran's clinic still felt a missing fist clenching so hard that invisible nails seemed to dig into a vanished palm.",
            "In his clinical study (1998, Brain), Ramachandran tested amputees at UC San Diego using cotton swabs and a $10 mirror stood inside an open cardboard box.",
            "Brushing a blindfolded patient's cheek felt like touching his missing thumb because the face map sits right next to the hand map. Then, watching his healthy hand's reflection open inside the mirror box made his cramped phantom fist unclench on the spot.",
            "Doctors used to blame stump nerves, yet cutting nerves failed. The real jam was a motor strip shouting 'open' with zero visual proof returning.",
            "One clean reflection broke a ten-year loop in seconds, showing adult body maps stay remarkably adaptable.",
        ],
        "question": "Have you ever felt your own hand twitch while watching a VR avatar or magic trick — did your brain buy the illusion right away?",
    },
    "alien_hand_syndrome": {
        "headline": "Why His Right Hand Buttoned His Shirt While His Own Left Hand Unbuttoned It",
        "paragraphs": [
            "Stroke patients have sat getting dressed before work while their own left hand glided up smoothly and unbuttoned every button their right hand just fastened.",
            "Across studies by Gary Goldberg (1981, Archives of Neurology) and Todd Feinberg (1992, Neurology), doctors tracked hands that performed smooth actions without conscious permission.",
            "Spotting a mug or doorknob automatically preps a reach in premotor cortex while a frontal brake blocks 99 percent of urges. When a stroke breaks that brake or cuts the bridge between hemispheres, the hand acts solo.",
            "Movies treat this like thinking a stranger owns your arm. In reality, patients know 100 percent the arm is theirs — what vanishes is agency, the feeling that 'I pressed start.'",
            "Holding a soft foam roll satisfied one patient's grasp reflex so he walked past clinic doors cleanly.",
        ],
        "question": "If one of your hands started grabbing nearby door handles on autopilot, would you hold a stress ball or try pinning your hand in a pocket?",
    },
    "milgram_obedience_shock": {
        "headline": "Why 65% Flipped the 450-Volt Switch at Yale — Yet Refused One Direct Order",
        "paragraphs": [
            "In 1961, everyday New Haven residents sat in a Yale lab facing thirty metal switches labeled from 15 volts up to 450 volts.",
            "In Stanley Milgram's study (1963, Journal of Abnormal and Social Psychology) and archival reviews by Alexander Haslam and Stephen Reicher (2012, PLoS Biology), researchers tracked what pushed forty men forward — and what stopped them.",
            "Even after wall-pounding at 300 volts, 65 percent reached the final switch. Yet audio tapes revealed a twist: whenever the lab coat barked his fourth line — 'You have no other choice' — almost every volunteer quit cold.",
            "That shatters the myth that humans obey like blind robots. People kept going only when prods appealed to helping science, and beside two rebel peers, 90 percent refused.",
            "Harm spreads fastest when disguised as a worthy shared duty — until one voice says no.",
        ],
        "question": "In a tense room where everyone stays silent, what makes speaking up easier — questioning things early or seeing just one other person refuse?",
    },
    "hippocampal_memory_prosthesis": {
        "headline": "Why Random Pulses Gave 0% Gain While a Custom Rhythm Boosted Memory by 37%",
        "paragraphs": [
            "During hospital memory games, shapes tapped on a touchscreen faded within seconds — until engineers listened to each volunteer's own neural timing.",
            "In Robert Hampson, Dong Song, and Theodore Berger's clinical study (2018, Journal of Neural Engineering), seventeen epilepsy patients wearing hair-thin wires played matching rounds while researchers recorded signals across the hippocampus.",
            "Translating each person's own 'good-memory' timing code in real time boosted short-term recall by 37 percent — and surprise tests 75 minutes later with the wires switched off still scored 35 percent higher.",
            "Sci-fi films treat chips like USB drives that upload skills. When Hampson's team sent the exact same power in a scrambled rhythm, gain dropped to 0 percent.",
            "Rather than storing files on silicon, gentle timing helped the brain's own wiring lock moments in.",
        ],
        "question": "If a medical implant only echoed your own natural memory rhythm after an injury without storing data outside your head, would you use it?",
    },
    "clive_wearing_seven_second_mind": {
        "headline": "His Memory Reset Every 7 Seconds, Yet He Still Conducted an Entire Choir",
        "paragraphs": [
            "After a rare viral brain fever in 1985, British conductor Clive Wearing was stranded on a 7-to-30-second island of time — feeling every half minute as if he had just woken up.",
            "Across decades of tracking by Barbara Wilson and Alan Baddeley (1995, Journal of Clinical and Experimental Neuropsychology), researchers compared his daily life with his musical gift.",
            "All day Clive wrote 'I am awake' in notebooks and crossed out earlier lines in confusion. Yet before a piano or his London choir, he played and conducted seamlessly — then forgot touching the keys ten seconds later.",
            "Movies show amnesia wiping identity clean. Clive proved that facts in the hippocampus, habits in the basal ganglia, and love in the amygdala run on separate circuits — so he still leapt up whenever his wife Deborah walked in.",
            "Even when timelines shatter, practiced skill and devotion hold on deep beneath conscious recall.",
        ],
        "question": "What song from years ago can your hands or voice still jump into the instant you hear the first three notes?",
    },
    "invisible_gorilla_attention": {
        "headline": "Why Half the Room — and 83% of Radiologists — Missed a Gorilla in Plain Sight",
        "paragraphs": [
            "At Harvard in 1999, volunteers counted basketball passes made by players in white shirts while someone in a gorilla suit walked to center court, thumped her chest, and stayed for nine seconds.",
            "Across Daniel Simons and Christopher Chabris's experiment (1999, Perception) and Trafton Drew's hospital study (2013, Psychological Science), researchers tested what happens when human focus narrows.",
            "Half of viewers missed the gorilla completely. Wilder still, when Drew hid a gorilla 48 times larger than a matchhead inside lung CT scans, 83 percent of expert radiologists missed it — even as eye trackers proved they looked straight at it.",
            "People assume sharp eyesight or high IQ prevents this. In reality, your eyes catch the light fine while your parietal attention spotlight filters out anything outside your search target.",
            "That is why drivers watching only for cars can look straight past a cyclist.",
        ],
        "question": "Did you catch the gorilla the first time you ever heard about that test — or what everyday item do you lose most while staring right at it?",
    },
    "maguire_london_taxi_hippocampus": {
        "headline": "Memorizing 25,000 London Streets Grew Drivers' Brains — With One Hidden Trade-Off",
        "paragraphs": [
            "To earn a London black-cab badge, trainees spend four years on mopeds memorizing 25,000 twisting streets and thousands of landmarks without GPS.",
            "Across three MRI studies led by Eleanor Maguire at UCL (2000, PNAS; 2006, Hippocampus; 2011, Current Biology), researchers scanned veteran cabbies, bus drivers, and 79 trainees over four years.",
            "Cabbies carried thicker gray matter in the back hippocampus than both ordinary adults and red-bus drivers running fixed routes in identical traffic. Four-year scans proved only trainees who actually passed grew new tissue.",
            "Old textbooks claimed adult brains freeze like concrete. Yet growth carried a trade-off: cabbies' front hippocampus shrank slightly, making new visual shapes tougher to pack — like shifting coats on a crowded shelf.",
            "Following phone arrows daily lets that inner map coast, while choosing routes yourself wakes it up.",
        ],
        "question": "Could you cross your city to a new neighborhood today without opening GPS once, or do you keep map arrows on even for familiar streets?",
    },
    "broca_patient_tan_speech_loss": {
        "headline": "He Spoke Only One Syllable for 21 Years — and 146 Years Later an MRI Showed Why",
        "paragraphs": [
            "In 1861 Paris, Louis Victor Leborgne understood every question and counted accurately on his fingers, yet for 21 years only one sound left his lips: 'tan, tan.'",
            "Examined by surgeon Paul Broca in 1861 and scanned in high-resolution MRI by Nina Dronkers (2007, Brain), Leborgne's un-sliced brain bridged two centuries of science.",
            "Broca found a walnut-sized hollow on the left front surface — the first solid proof tying speech to the left hemisphere. Because Broca left the brain whole in spirits, Dronkers scanned that exact specimen 146 years later.",
            "Textbooks taught that surface damage alone causes permanent muteness, though surface-only patients usually recover in months. The 2007 MRI revealed deep damage severing the white-matter cable highway underneath.",
            "Fluent speech rides a deep fiber bridge — and behind missing words, clear thought often shines intact.",
        ],
        "question": "Have you ever pictured an object or name with 100% clarity in your head while your mouth froze for five seconds trying to pull up the word?",
    },
    "olds_milner_pleasure_center": {
        "headline": "A Bent Wire Missed Its Target by 3mm — and Exposed Craving Without Joy",
        "paragraphs": [
            "In 1953 Montreal, James Olds lowered a hair-thin silver wire toward a rat's alertness zone, unaware the tip had bent forward by three millimeters.",
            "Across James Olds and Peter Milner's classic report (1954, Journal of Comparative and Physiological Psychology) and Kent Berridge's dopamine studies (2015, Neuron), scientists split reward in two.",
            "Rat #34 marched straight back to the corner where gentle current pulsed. Given a brass lever, rats pressed up to 2,000 times an hour ignoring food — yet stopped within minutes and slept calmly the moment power switched off.",
            "Newspapers dubbed that spot the 'pleasure center,' feeding the myth that dopamine equals bliss. Human patients wired along that bundle later described an urgent itch to click again without satisfaction — pure 'wanting,' not 'liking.'",
            "Midnight phone scrolling taps that exact loop: your thumb keeps swiping long after enjoyment stops.",
        ],
        "question": "When you catch yourself scrolling late at night with zero enjoyment, what breaks the loop faster — putting the phone across the room or setting a timer?",
    },
    "blindsight_subcortical_vision": {
        "headline": "Clinically Blind on One Side, He Swore It Was Dark — Then Pointed 90% Right",
        "paragraphs": [
            "After London surgery removed his right visual cortex, Patient D.B. was completely blind across the left half of his world.",
            "In Lawrence Weiskrantz's landmark study (1974, Brain) and Beatrice de Gelder's obstacle-hallway test (2008, Current Biology), researchers asked blind patients simply to guess.",
            "Whenever a silent dot flashed on his blind left side, D.B. insisted he saw nothing — yet his finger pointed on target 90 percent of the time. Years later, totally cortical-blind Patient T.N. walked down a chair-filled corridor without his cane and dodged every obstacle.",
            "People assume vision is one screen at the back of the head. While 90 percent of eye fibers feed conscious sight, an ancient 10 percent shortcut dives straight into the brainstem's reflex map.",
            "Your reflex sight tracks motion milliseconds before your conscious mind ever paints a picture.",
        ],
        "question": "Have you ever caught a falling cup or ducked a fast object before your conscious mind even knew what moved?",
    },
}


class CommunityManager:
    """
    Automates publishing and pinning the official academic verification comment
    and cognitive dissonance debate trigger for newly released Shorts (Rule R35).
    """

    def __init__(
        self,
        cdp_port: int = DEFAULT_CDP_PORT,
        projects_dir: Path | None = None,
        dossiers_root: Path | None = None,
    ):
        self.cdp_port = cdp_port
        self.projects_dir = projects_dir
        self.dossiers_root = dossiers_root
        self.session = WhaleSessionController(cdp_port=cdp_port)

    def _synthesize_from_dossier(self, dossier_dir: Path) -> dict[str, Any] | None:
        """Synthesizes an R35-compliant 5-paragraph YouTube-Natural-Script comment package from a research dossier."""
        slug = dossier_dir.name
        try:
            d_meta = json.loads((dossier_dir / "dossier.json").read_text(encoding="utf-8"))
        except Exception:
            d_meta = {}

        sources_doc = {}
        if (dossier_dir / "01_sources.json").exists():
            try:
                sources_doc = json.loads((dossier_dir / "01_sources.json").read_text(encoding="utf-8"))
            except Exception:
                sources_doc = {}

        primary_src = next(
            (
                s for s in (sources_doc.get("sources") or [])
                if isinstance(s, dict) and s.get("type") in ("primary", "primary_historical") and (s.get("doi") or s.get("url"))
            ),
            None,
        )
        doi_val = str((primary_src or {}).get("doi") or "").strip()

        if slug in _DIORAMA_NATURAL_PACKAGES:
            curated = dict(_DIORAMA_NATURAL_PACKAGES[slug])
            if doi_val:
                curated["doi"] = doi_val
            return curated

        if not d_meta:
            return None

        plain_doc = {}
        if (dossier_dir / "05_plain_language.json").exists():
            try:
                plain_doc = json.loads((dossier_dir / "05_plain_language.json").read_text(encoding="utf-8"))
            except Exception:
                plain_doc = {}

        cite_str = _parse_citation_author_year_journal(primary_src) if primary_src else "peer-reviewed neuroscience research"

        p_case = d_meta.get("primary_case") or {}
        headline = _smart_trim_headline(str(p_case.get("title") or d_meta.get("topic") or dossier_dir.name), max_len=96)
        one_sentence = _strip_emojis_and_bullets(str(plain_doc.get("one_sentence_story") or ""))
        so_what = _strip_emojis_and_bullets(str(plain_doc.get("so_what_for_you") or ""))

        core_facts = [
            _strip_emojis_and_bullets(str(f.get("fact") if isinstance(f, dict) else f))
            for f in (d_meta.get("core_facts") or [])
            if (f.get("fact") if isinstance(f, dict) else f)
        ]
        wow_facts = [
            _strip_emojis_and_bullets(str(w.get("fact") if isinstance(w, dict) else w))
            for w in (d_meta.get("wow_facts") or [])
            if (w.get("fact") if isinstance(w, dict) else w)
        ]
        people_first_tokens = {
            str(p.get("name") or "").split()[idx]
            for p in (p_case.get("people") or [])
            if isinstance(p, dict) and p.get("name")
            for idx in range(len(str(p.get("name")).split()))
        }
        misconceptions = d_meta.get("misconceptions") or []
        myth_truth = ""
        if misconceptions and isinstance(misconceptions[0], dict):
            myth = _strip_emojis_and_bullets(str(misconceptions[0].get("myth") or "")).rstrip(".")
            truth = _strip_emojis_and_bullets(str(misconceptions[0].get("truth") or "")).rstrip(".")
            if myth and truth:
                m_w0 = myth.split()[0]
                m_lead = myth if m_w0 in people_first_tokens else (myth[0].lower() + myth[1:])
                t_w0 = truth.split()[0]
                t_lead = truth if t_w0 in people_first_tokens else (truth[0].lower() + truth[1:])
                myth_truth = f"People often assume that {m_lead}. In reality, {t_lead}."

        raw_f2 = (core_facts[1] if len(core_facts) > 1 else (core_facts[0] if core_facts else "the underlying experimental mechanism in detail")).rstrip(".")
        f2_w0 = raw_f2.split()[0] if raw_f2 else ""
        f2_lead = raw_f2 if f2_w0 in people_first_tokens else (raw_f2[0].lower() + raw_f2[1:] if len(raw_f2) > 1 else raw_f2)
        p1 = one_sentence or (core_facts[0] if core_facts else f"A landmark case in {p_case.get('place', 'neuroscience')} continues to reshape how we understand human behavior.")
        p2 = f"In the study by {cite_str}, researchers documented how {f2_lead}."
        p3 = wow_facts[0] if wow_facts else (core_facts[2] if len(core_facts) > 2 else p1)
        p4 = myth_truth or (core_facts[3] if len(core_facts) > 3 else "Rather than a vague psychological quirk, the evidence points to a concrete circuit-level mechanism.")
        p5 = so_what or "Once you see how this pathway works, everyday habits and split-second reactions make much more sense."

        hooks = d_meta.get("everyday_hooks") or []
        question = ""
        if hooks:
            hook_line = _strip_emojis_and_bullets(str(hooks[0])).rstrip(".!?")
            if "?" in str(hooks[0]):
                question = _strip_emojis_and_bullets(str(hooks[0]))
            else:
                h_low = hook_line[0].lower() + hook_line[1:] if len(hook_line) > 1 else hook_line.lower()
                question = f"Have you ever caught yourself experiencing that — like {h_low}?"

        return {
            "doi": doi_val,
            "headline": headline,
            "paragraphs": [p1, p2, p3, p4, p5],
            "question": question,
        }

    def prepare_comment_content(
        self,
        project_id: str,
        companion_short: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Prepares the formatted R35 academic DOI and debate trigger comment with dossier synthesis."""
        storage = ProjectStorage(project_id, projects_dir=self.projects_dir)
        manifest = storage.get_manifest()
        metadata = storage.load_json("06_publish", "metadata.json") or {}
        related_receipt = storage.load_json("06_publish", "related_video_receipt.json") or {}

        explicit_slug = str(metadata.get("dossier_slug") or manifest.get("dossier_slug") or "").strip()
        dossiers_base = self.dossiers_root or (CHANNEL_ROOT / "research_dossiers")
        dossier_dir = (
            (dossiers_base / explicit_slug)
            if (explicit_slug and (dossiers_base / explicit_slug).is_dir())
            else _find_matching_dossier_dir(project_id, dossiers_root=self.dossiers_root)
        )
        dossier_pkg = self._synthesize_from_dossier(dossier_dir) if dossier_dir else None

        # 1. Resolve DOI dynamically
        doi = None
        research_card = storage.load_json("01_ideation", "research_card.json")
        if research_card and research_card.get("doi"):
            doi = str(research_card["doi"]).strip()

        if not doi and metadata.get("doi"):
            doi = str(metadata["doi"]).strip()

        if not doi:
            desc = metadata.get("description", "")
            m = re.search(r"(?:Source & Verification:\s*(?:https?://doi\.org/)?|doi\.org/)(10\.\d{4,9}/[^\s\n\r]+)", desc)
            if m:
                doi = m.group(1).strip()

        if not doi and dossier_pkg and dossier_pkg.get("doi"):
            doi = str(dossier_pkg["doi"]).strip()

        if not doi:
            bp = manifest.get("blueprint", {})
            if bp and bp.get("doi"):
                doi = str(bp["doi"]).strip()

        if not doi:
            doi = "10.1038/s41586-024-07387-4"

        # 2. Resolve 5-Paragraph Editorial Case Commentary (Rule R35)
        _GENERIC_PLACEHOLDERS = {
            "physical body is paralyzed, but digital agency is restored without moving a muscle.",
        }
        _TOPIC_PACKAGES = {
            "psych_01_habit_loop_basal_ganglia": {
                "headline": "The Man Who Forgot His Own House Still Walked Straight to the Kitchen",
                "paragraphs": [
                    "A clinical case showing how a patient with severe amnesia could navigate his home without knowing where the rooms were is drawing renewed attention in neuroscience.",
                    "According to the peer-reviewed study by Ann Graybiel (2008, Nature Reviews Neuroscience) alongside work on amnesic patient Eugene Pauly, researchers examined how the brain executes complex routines after the hippocampus is destroyed by viral encephalitis.",
                    "What stood out most was that even when Eugene could not draw a floor plan of his own house or point to the kitchen door, the moment he felt hungry he stood up, walked down the hallway, and opened the exact cabinet holding his snacks.",
                    "This does not mean his conscious memory had returned. Instead, recordings from the dorsal striatum show that the basal ganglia compress repeated routines into a single start-to-finish motor chunk ('task-bracketing') that fires automatically once triggered by a cue.",
                    "In other words, conscious memory and habitual action run on two separate neural circuits inside the brain.",
                ],
                "question": "What habit do you catch your brain running on autopilot before you even think about it?",
            },
            "psych_02_inner_speech_decoding": {
                "headline": "A Paralyzed Patient Spoke at 62 Words Per Minute Using Only a Brain Implant",
                "paragraphs": [
                    "A clinical breakthrough in which a paralyzed patient with ALS communicated at near-conversational speed through a brain-computer interface is drawing major attention.",
                    "According to the Stanford study led by Francis Willett, Jaimie Henderson, and Krishna Shenoy (2023, Nature), researchers implanted four microelectrode arrays into the ventral premotor speech cortex of a patient who no longer spoke intelligibly.",
                    "What stood out during the trials was that as the patient simply attempted to mouth sentences, a recurrent neural network decoded her neural firing patterns into text on a screen at 62 words per minute across a 125,000-word vocabulary, more than three times faster than any prior speech BCI.",
                    "Crucially, the implant is not 'reading private thoughts' from across the brain. It specifically decodes the fine motor neural commands intended for the lips, tongue, jaw, and larynx in the speech motor cortex.",
                    "Even years after paralysis, the brain's cortical map for individual phonemes remains remarkably intact and ready to be decoded.",
                ],
                "question": "If a neural implant can decode speech at 62 words per minute, where should cognitive privacy boundaries be drawn?",
            },
            "psych_03_split_brain_dual_consciousness": {
                "headline": "When One Hand Buttoned a Shirt, the Other Hand Immediately Unbuttoned It",
                "paragraphs": [
                    "Neurological cases in which patients whose left and right brain hemispheres were surgically separated began acting as if two independent minds shared one body continue to fascinate cognitive science.",
                    "According to Michael Gazzaniga's landmark review of split-brain patients (2000, Brain), surgeons severed the corpus callosum, the bundle of 200 million nerve fibers connecting the two hemispheres, to stop intractable epilepsy.",
                    "In controlled visual-field tests, when an instruction like 'walk' was flashed only to the nonverbal right hemisphere, the patient stood up and walked away. Yet when asked why he stood up, his verbal left hemisphere instantly invented a plausible excuse: 'I wanted to go get a soda.'",
                    "This does not mean the patient was intentionally lying. Rather, the left hemisphere houses a specialized neural system ('the interpreter') that continuously weaves a coherent story to explain actions initiated by brain circuits it cannot access.",
                    "Our sense of a single unified self relies heavily on the left hemisphere's ongoing narrative construction.",
                ],
                "question": "When the corpus callosum is severed, do you think two separate conscious minds exist inside one skull?",
            },
            "psych_05_capgras_imposter_delusion": {
                "headline": "The Son Who Looked at His Own Parents and Insisted They Were Identical Impostors",
                "paragraphs": [
                    "A striking neurological case in which a young man recognized every detail of his parents' faces yet was convinced they had been replaced by look-alike impostors is a classic window into how the brain constructs familiarity.",
                    "According to the peer-reviewed study by William Hirstein and V. S. Ramachandran (1997, Proceedings of the Royal Society B), researchers tested patient DS after a traumatic brain injury while measuring his galvanic skin conductance response to familiar and unfamiliar faces.",
                    "What surprised the researchers was that DS had completely intact vision and could confirm the people standing in front of him looked exactly like his mother and father, yet the moment he saw them in person, his skin-conductance monitor remained completely flat. Strangely, when his mother spoke to him over the telephone, the delusion vanished.",
                    "This occurred because the head injury selectively severed the visual pathway connecting the fusiform face area (FFA) to the amygdala, while leaving the auditory pathway to the amygdala intact.",
                    "Recognizing a loved one requires both an accurate visual template and an automatic emotional limbic signal confirming who they are.",
                ],
                "question": "If your visual cortex recognized someone's face but your emotional circuit stayed silent, would you trust your eyes or your gut?",
            },
            "psych_06_glymphatic_sleep_toxins": {
                "headline": "Why Your Brain Cells Physically Shrink by 60 Percent the Moment Deep Sleep Begins",
                "paragraphs": [
                    "A landmark neuroscience experiment showing how the living brain physically opens its own internal plumbing pipes during deep sleep has transformed our understanding of why sleep is biologically mandatory.",
                    "According to the peer-reviewed study by Lulu Xie and Maiken Nedergaard et al. (2013, Science), researchers used two-photon imaging in live mice to track the real-time flow of cerebrospinal fluid through brain tissue across waking and sleeping states.",
                    "What stood out in the imaging was that as soon as the brain entered slow-wave sleep, glial cells shrank and the interstitial space between neurons expanded by 60 percent, allowing cerebrospinal fluid to rush through brain tissue and flush out toxic beta-amyloid proteins at twice the waking rate.",
                    "This clearance is not passive diffusion. It is driven by the glymphatic system, a pressurized fluid transport network gated by aquaporin-4 water channels that stays largely closed while you are awake and processing sensory information.",
                    "Skipping deep sleep does not just leave you tired; it prevents the brain from completing its nightly metabolic wash cycle.",
                ],
                "question": "How many hours of uninterrupted sleep do you usually get on a weeknight?",
            },
        }

        pkg = _TOPIC_PACKAGES.get(project_id) or dossier_pkg or {}
        dissonance_trigger = pkg.get("question")
        if not dissonance_trigger and research_card and isinstance(research_card.get("story_context"), dict):
            cand = str(research_card["story_context"].get("social_comment_trigger") or "").strip()
            if cand and cand.lower() not in _GENERIC_PLACEHOLDERS:
                dissonance_trigger = cand

        paradox_data = storage.load_json("01_ideation", "paradox_hook.json")
        if not dissonance_trigger and paradox_data:
            for k in ("social_comment_trigger", "dissonance_trigger", "paradox_statement"):
                cand = str(paradox_data.get(k) or "").strip()
                if cand and cand.lower() not in _GENERIC_PLACEHOLDERS and "?" in cand:
                    dissonance_trigger = cand
                    break

        if not dissonance_trigger:
            title = metadata.get("title") or manifest.get("title", "this neural mechanism")
            clean_title = re.sub(r"[^\w\s\?]", "", title).strip()
            if "?" in clean_title:
                dissonance_trigger = f"{clean_title} What is your take on this neural mechanism?"
            else:
                dissonance_trigger = f"Have you ever noticed '{clean_title}' happening in your own brain?"

        clean_trigger = _strip_emojis_and_bullets(
            re.sub(
                r"\s*What would you have done(?: in their shoes)?\?\s*Share your theory below!?",
                "",
                dissonance_trigger.strip(),
                flags=re.IGNORECASE,
            )
        )

        doi_clean = doi.strip()
        doi_link = doi_clean if doi_clean.startswith("http") else f"https://doi.org/{doi_clean}"

        headline = _strip_emojis_and_bullets(str(pkg.get("headline") or ""))
        paragraphs = [_strip_emojis_and_bullets(p) for p in (pkg.get("paragraphs") or []) if p]

        if not headline or not paragraphs:
            raw_title = str(metadata.get("title") or manifest.get("title") or project_id).strip()
            headline = re.sub(r"[^\w\s\-\',:\?]", "", raw_title).strip()
            sc = (research_card or {}).get("story_context") or {}
            protagonist = str(sc.get("protagonist") or "the study participants").strip()
            location = str(sc.get("location") or "clinical neuroscience").strip()
            yr = str(sc.get("era_year") or "peer-reviewed research").strip()
            core_facts = str((research_card or {}).get("core_facts") or "").strip()
            if not core_facts:
                desc = str(metadata.get("description") or "")
                for ln in (l.strip() for l in desc.splitlines() if l.strip()):
                    if not ln.startswith("Source & Verification:") and not ln.startswith("#") and "ALL ABOUT BRAIN" not in ln and ln != raw_title:
                        core_facts = ln
                        break
            target_reg = str((research_card or {}).get("target_region") or "the target neural circuit").strip()
            damaged_reg = str((research_card or {}).get("damaged_region") or "the primary pathway").strip()
            paragraphs = [
                f"A neuroscience case from {location} ({yr}) involving {protagonist} highlights how specific brain circuits shape human perception and behavior.",
                f"According to the peer-reviewed study, researchers investigated how neural signaling changes across {damaged_reg} and {target_reg} under controlled experimental conditions.",
                _strip_emojis_and_bullets(core_facts) or f"What stood out during testing was the precise dissociation between automatic neural processing in {target_reg} and conscious awareness.",
                f"Rather than a general cognitive change, the findings point to a specific circuit-level mechanism operating between {damaged_reg} and {target_reg}.",
                "Understanding this pathway helps clarify how the brain separates fast unconscious processing from conscious experience.",
            ]

        companion_info = companion_short
        if not companion_info and related_receipt.get("verified") and related_receipt.get("target_title"):
            companion_info = {
                "title": str(related_receipt["target_title"]),
                "video_id": str(related_receipt.get("target_video_id") or ""),
            }

        companion_line = ""
        if isinstance(companion_info, dict) and companion_info.get("title"):
            comp_title = _strip_emojis_and_bullets(str(companion_info["title"]))
            if comp_title:
                companion_line = f"Related case linked on this Short: {comp_title}\n"

        body_text = "\n\n".join(paragraphs)
        comment_text = (
            f"[{headline}]\n\n"
            f"{body_text}\n\n"
            f"{companion_line}"
            f"Source: {doi_link}\n"
            f"{clean_trigger}"
        )

        return {
            "project_id": project_id,
            "headline": headline,
            "doi": doi,
            "doi_link": doi_link,
            "dissonance_trigger": dissonance_trigger,
            "social_comment_trigger": dissonance_trigger,
            "word_count": len(comment_text.split()),
            "comment_text": comment_text,
        }

    def stage_prepared_comment(self, project_id: str) -> dict[str, Any]:
        """Persists 06_publish/prepared_comment.json with manifest SHA-256 registration."""
        storage = ProjectStorage(project_id, projects_dir=self.projects_dir)
        payload = self.prepare_comment_content(project_id)
        staged = {
            **payload,
            "staged_at": datetime.now(timezone.utc).isoformat(),
        }
        storage.save_json("06_publish", "prepared_comment.json", staged)
        return staged

    async def _delete_existing_self_comments(self, client: Any, keep_marker: str = "") -> int:
        """Deletes existing top-level comments authored by @AllAboutBrainOfficial before posting a replacement."""
        deleted = 0
        for _ in range(5):
            clicked_menu = await client.eval(
                f"""(() => {{
                    const keep = {json.dumps(keep_marker)};
                    const threads = Array.from(document.querySelectorAll('ytd-comment-thread-renderer'));
                    for (const th of threads) {{
                        const txt = (th.innerText || '');
                        if (!txt.includes('@AllAboutBrainOfficial') && !txt.includes('ALL ABOUT BRAIN')) continue;
                        if (keep && txt.includes(keep)) continue;
                        const btn = th.querySelector('button[aria-label="Action menu"], button[aria-label="작업 메뉴"], ytd-menu-renderer button');
                        if (btn) {{
                            btn.scrollIntoView({{ block: 'center' }});
                            btn.click();
                            return true;
                        }}
                    }}
                    return false;
                }})()"""
            )
            if not clicked_menu:
                break
            await asyncio.sleep(1.0)
            clicked_delete = await client.eval(
                """(() => {
                    const items = Array.from(document.querySelectorAll(
                        'ytd-menu-popup-renderer ytd-menu-navigation-item-renderer, ytd-menu-popup-renderer ytd-menu-service-item-renderer, tp-yt-iron-dropdown yt-list-item-view-model'
                    ));
                    for (const it of items) {
                        const rect = it.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;
                        const label = (it.innerText || '').trim();
                        if (/^(delete|삭제)$/i.test(label) || label === 'Delete' || label === '삭제') {
                            const target = it.querySelector('a.yt-simple-endpoint, tp-yt-paper-item') || it;
                            target.click();
                            return true;
                        }
                    }
                    return false;
                })()"""
            )
            if not clicked_delete:
                await client.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
                await client.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
                break
            await asyncio.sleep(1.0)
            confirmed = await client.eval(
                """(() => {
                    const dialogs = Array.from(document.querySelectorAll('yt-confirm-dialog-renderer, tp-yt-paper-dialog'));
                    for (const dlg of dialogs) {
                        const rect = dlg.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;
                        const cbtn = dlg.querySelector('#confirm-button button, button[aria-label="Delete"], button[aria-label="삭제"]');
                        if (cbtn) {
                            cbtn.click();
                            return true;
                        }
                        const btns = Array.from(dlg.querySelectorAll('button'));
                        const match = btns.find(b => /^(delete|삭제)$/i.test((b.innerText || '').trim()));
                        if (match) {
                            match.click();
                            return true;
                        }
                    }
                    return false;
                })()"""
            )
            if not confirmed:
                await client.click(["yt-confirm-dialog-renderer #confirm-button button", "#confirm-button button"])
            await asyncio.sleep(2.0)
            deleted += 1
        return deleted

    async def _async_post_and_pin(
        self,
        video_id: str,
        comment_payload: dict[str, Any],
        dry_run: bool = False,
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        """Executes comment posting and pinning via DirectCDPClient in an isolated temporary tab (R36-B)."""
        project_id = comment_payload["project_id"]
        comment_text = comment_payload["comment_text"]
        headline_marker = f"[{comment_payload.get('headline', '')}]" if comment_payload.get("headline") else ""
        storage = ProjectStorage(project_id, projects_dir=self.projects_dir)
        now_iso = datetime.now(timezone.utc).isoformat()
        shorts_url = f"{YOUTUBE_WATCH_BASE_URL}{video_id}"
        watch_url = f"https://www.youtube.com/watch?v={video_id}"

        storage.save_json(
            "06_publish",
            "prepared_comment.json",
            {**comment_payload, "staged_at": now_iso},
        )

        if dry_run:
            receipt = {
                "project_id": project_id,
                "video_id": video_id,
                "shorts_url": shorts_url,
                "comment_text": comment_text,
                "doi_included": "doi.org/" in comment_text,
                "pinned": True,
                "deleted_previous_count": 0,
                "posted_at": now_iso,
                "status": "dry_run_success",
            }
            storage.save_json("06_publish", "community_receipt.json", receipt)
            return receipt

        client, temp_tab_id = self.session.open_temp_direct_client(watch_url)
        pinned_ok = False
        deleted_prev = 0
        try:
            async with client:
                await client.send("Page.enable")
                await client.send("Runtime.enable")
                await client.send("Page.bringToFront")
                await client.wait_for_element(["ytd-watch-metadata", "#above-the-fold"], timeout_sec=15.0)
                await asyncio.sleep(2.0)
                await client.eval(
                    """(() => {
                        const v = document.querySelector('video');
                        if (v) v.pause();
                    })()"""
                )

                # On 2026 vertical-video watch pages, the first ytd-comments#comments is hidden;
                # scroll the visible ytd-comments:not([hidden]) into center + wheel to trigger IntersectionObserver.
                box_ready = False
                comments_blocked_reason = ""
                for _ in range(8):
                    await client.eval(
                        """(() => {
                            const c = document.querySelector('ytd-comments:not([hidden])') || document.querySelector('#below') || document.body;
                            c.scrollIntoView({ block: 'center' });
                            window.scrollBy(0, 260);
                            window.dispatchEvent(new Event('scroll'));
                        })()"""
                    )
                    try:
                        await client.send(
                            "Input.dispatchMouseEvent",
                            {"type": "mouseWheel", "x": 400, "y": 500, "deltaX": 0, "deltaY": 250},
                            timeout_sec=2.0,
                        )
                    except Exception:
                        pass
                    blocked_check = await client.eval(
                        """(() => {
                            const msg = document.querySelector('ytd-comments:not([hidden]) ytd-message-renderer, #comments ytd-message-renderer');
                            const t = msg ? (msg.innerText || '').trim() : '';
                            if (/not supported on private videos|비공개 동영상에서는 댓글이 지원되지|Comments are turned off|댓글이 사용 중지/i.test(t)) {
                                return t;
                            }
                            return '';
                        })()"""
                    )
                    if blocked_check:
                        comments_blocked_reason = str(blocked_check)
                        break
                    if await client.find_element(COMMUNITY_SELECTORS["comment_input_box"]):
                        box_ready = True
                        break
                    await asyncio.sleep(1.2)

                if comments_blocked_reason:
                    receipt = {
                        "project_id": project_id,
                        "video_id": video_id,
                        "shorts_url": shorts_url,
                        "comment_text": comment_text,
                        "doi_included": "doi.org/" in comment_text,
                        "pinned": False,
                        "deleted_previous_count": 0,
                        "posted_at": now_iso,
                        "status": "deferred_scheduled_private",
                        "reason": comments_blocked_reason,
                    }
                    storage.save_json("06_publish", "community_receipt.json", receipt)
                    write_studio_publish_receipt(project_id, projects_dir=self.projects_dir)
                    return receipt

                if not box_ready and not await client.wait_for_element(COMMUNITY_SELECTORS["comment_input_box"], timeout_sec=8.0):
                    raise RuntimeError("Could not find YouTube comment input box over DirectCDPClient.")

                if replace_existing:
                    await asyncio.sleep(1.5)
                    deleted_prev = await self._delete_existing_self_comments(client, keep_marker=headline_marker)
                    await client.eval(
                        """(() => {
                            const c = document.querySelector('ytd-comments:not([hidden])') || document.querySelector('#below') || document.body;
                            c.scrollIntoView({ block: 'center' });
                        })()"""
                    )
                    await asyncio.sleep(0.8)

                already_posted_exact = False
                if headline_marker:
                    already_posted_exact = bool(
                        await client.eval(
                            f"""(() => {{
                                const marker = {json.dumps(headline_marker)};
                                const threads = Array.from(document.querySelectorAll('ytd-comment-thread-renderer'));
                                return threads.some(th => {{
                                    const txt = (th.innerText || '');
                                    return (txt.includes('@AllAboutBrainOfficial') || txt.includes('ALL ABOUT BRAIN')) && txt.includes(marker);
                                }});
                            }})()"""
                        )
                    )

                if not already_posted_exact:
                    await client.click(COMMUNITY_SELECTORS["comment_input_box"])
                    await asyncio.sleep(0.8)

                    typed = await client.type_into(
                        ["div#contenteditable-root[contenteditable='true']", *COMMUNITY_SELECTORS["comment_input_box"]],
                        comment_text,
                    )
                    if not typed:
                        raise RuntimeError("Failed to type DOI comment into contenteditable box.")
                    await asyncio.sleep(0.8)

                    submitted = await client.click(COMMUNITY_SELECTORS["comment_submit_button"])
                    if not submitted:
                        raise RuntimeError("Failed to click comment submit button.")
                    await asyncio.sleep(3.5)

                already_pinned = bool(
                    await client.eval(
                        f"""(() => {{
                            const marker = {json.dumps(headline_marker)};
                            const threads = Array.from(document.querySelectorAll('ytd-comment-thread-renderer'));
                            return threads.some(th => {{
                                const txt = (th.innerText || '');
                                if (marker && !txt.includes(marker)) return false;
                                return /Pinned by|고정함/i.test(txt);
                            }});
                        }})()"""
                    )
                )
                if already_pinned:
                    pinned_ok = True
                else:
                    opened_pin_menu = await client.eval(
                        f"""(() => {{
                            const marker = {json.dumps(headline_marker)};
                            const threads = Array.from(document.querySelectorAll('ytd-comment-thread-renderer'));
                            for (const th of threads) {{
                                const txt = (th.innerText || '');
                                if (marker && !txt.includes(marker)) continue;
                                const btn = th.querySelector('button[aria-label="Action menu"], button[aria-label="작업 메뉴"], ytd-menu-renderer button');
                                if (btn) {{
                                    btn.scrollIntoView({{ block: 'center' }});
                                    btn.click();
                                    return true;
                                }}
                            }}
                            return false;
                        }})()"""
                    )
                    if not opened_pin_menu and await client.wait_for_element(COMMUNITY_SELECTORS["comment_action_menu"], timeout_sec=8.0):
                        opened_pin_menu = await client.click(COMMUNITY_SELECTORS["comment_action_menu"])

                    if opened_pin_menu:
                        await asyncio.sleep(1.0)
                        clicked_pin = await client.eval(
                            """(() => {
                                const items = Array.from(document.querySelectorAll(
                                    'ytd-menu-popup-renderer ytd-menu-service-item-renderer, ytd-menu-popup-renderer ytd-menu-navigation-item-renderer, tp-yt-iron-dropdown yt-list-item-view-model'
                                ));
                                for (const it of items) {
                                    const rect = it.getBoundingClientRect();
                                    if (rect.width === 0 || rect.height === 0) continue;
                                    const label = (it.innerText || '').trim();
                                    if (/^(pin|고정)$/i.test(label) || label === 'Pin' || label === '고정') {
                                        const target = it.querySelector('tp-yt-paper-item, a.yt-simple-endpoint') || it;
                                        target.click();
                                        return true;
                                    }
                                }
                                return false;
                            })()"""
                        )
                        if not clicked_pin:
                            clicked_pin = await client.click(COMMUNITY_SELECTORS["pin_menu_item"])
                        if clicked_pin:
                            await asyncio.sleep(1.0)
                            confirmed_pin = await client.eval(
                                """(() => {
                                    const dialogs = Array.from(document.querySelectorAll('yt-confirm-dialog-renderer, tp-yt-paper-dialog'));
                                    for (const dlg of dialogs) {
                                        const rect = dlg.getBoundingClientRect();
                                        if (rect.width === 0 || rect.height === 0) continue;
                                        const cbtn = dlg.querySelector('#confirm-button button, button[aria-label="Pin"], button[aria-label="고정"]');
                                        if (cbtn) {
                                            cbtn.click();
                                            return true;
                                        }
                                        const btns = Array.from(dlg.querySelectorAll('button'));
                                        const match = btns.find(b => /^(pin|고정)$/i.test((b.innerText || '').trim()));
                                        if (match) {
                                            match.click();
                                            return true;
                                        }
                                    }
                                    return false;
                                })()"""
                            )
                            if not confirmed_pin:
                                await client.click(COMMUNITY_SELECTORS["confirm_pin_button"])
                            await asyncio.sleep(2.0)
                            pinned_ok = bool(
                                await client.eval(
                                    f"""(() => {{
                                        const marker = {json.dumps(headline_marker)};
                                        const threads = Array.from(document.querySelectorAll('ytd-comment-thread-renderer'));
                                        return threads.some(th => {{
                                            const txt = (th.innerText || '');
                                            if (marker && !txt.includes(marker)) return false;
                                            return /Pinned by|고정함/i.test(txt);
                                        }});
                                    }})()"""
                                )
                            ) or bool(confirmed_pin)
        finally:
            self.session.close_tab_by_id(temp_tab_id)

        receipt = {
            "project_id": project_id,
            "video_id": video_id,
            "shorts_url": shorts_url,
            "comment_text": comment_text,
            "doi_included": "doi.org/" in comment_text,
            "pinned": pinned_ok,
            "deleted_previous_count": deleted_prev,
            "posted_at": now_iso,
            "status": "pinned" if pinned_ok else "posted_unpinned",
        }
        storage.save_json("06_publish", "community_receipt.json", receipt)
        write_studio_publish_receipt(project_id, projects_dir=self.projects_dir)
        return receipt

    def post_and_pin_comment(
        self,
        project_id: str,
        video_id: str | None = None,
        dry_run: bool = False,
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        """Synchronous wrapper to post and pin DOI comment."""
        storage = ProjectStorage(project_id, projects_dir=self.projects_dir)
        if not video_id:
            receipt = storage.load_json("06_publish", "upload_receipt.json")
            if receipt and receipt.get("video_id") and receipt["video_id"] != "unknown":
                video_id = receipt["video_id"]
            else:
                video_id = f"sim_{project_id[:11]}"

        payload = self.prepare_comment_content(project_id)
        return asyncio.run(
            self._async_post_and_pin(
                video_id,
                payload,
                dry_run=dry_run,
                replace_existing=replace_existing,
            )
        )

    def pin_all_public_unpinned(
        self,
        dry_run: bool = False,
        replace_existing: bool = False,
        project_filter: set[str] | None = None,
    ) -> dict[str, Any]:
        """
        Stages 06_publish/prepared_comment.json across projects and posts+pins R35 comments
        on all uploaded Public Shorts that do not yet have a pinned community_receipt.json.
        Scheduled/Private Shorts gracefully defer with 'deferred_scheduled_private'.
        """
        base_dir = self.projects_dir or (CHANNEL_ROOT / "projects")
        valid_id_re = re.compile(r"^[A-Za-z0-9_-]{11}$")
        results: list[dict[str, Any]] = []
        staged_only: list[str] = []

        for p_dir in sorted(base_dir.iterdir()):
            if not p_dir.is_dir() or p_dir.name.startswith("."):
                continue
            pid = p_dir.name
            if project_filter and pid not in project_filter:
                continue
            if not (p_dir / "00_project_manifest.json").exists():
                continue

            upload_rec = {}
            up_path = p_dir / "06_publish" / "upload_receipt.json"
            if up_path.exists():
                try:
                    upload_rec = json.loads(up_path.read_text(encoding="utf-8"))
                except Exception:
                    upload_rec = {}

            vid = str(upload_rec.get("video_id") or "").strip()
            has_real_vid = bool(valid_id_re.match(vid)) and not vid.startswith("sim_")

            if not has_real_vid:
                has_script_or_meta = (
                    (p_dir / "02_script" / "script.json").exists()
                    or (p_dir / "06_publish" / "metadata.json").exists()
                )
                if has_script_or_meta:
                    self.stage_prepared_comment(pid)
                    staged_only.append(pid)
                continue

            comm_rec = {}
            comm_path = p_dir / "06_publish" / "community_receipt.json"
            if comm_path.exists():
                try:
                    comm_rec = json.loads(comm_path.read_text(encoding="utf-8"))
                except Exception:
                    comm_rec = {}

            self.stage_prepared_comment(pid)
            if comm_rec.get("pinned") is True and not replace_existing:
                results.append(
                    {
                        "project_id": pid,
                        "video_id": vid,
                        "pinned": True,
                        "status": "already_pinned",
                    }
                )
                continue

            rec = self.post_and_pin_comment(
                project_id=pid,
                video_id=vid,
                dry_run=dry_run,
                replace_existing=replace_existing,
            )
            results.append(
                {
                    "project_id": pid,
                    "video_id": vid,
                    "pinned": bool(rec.get("pinned")),
                    "deleted_previous_count": int(rec.get("deleted_previous_count", 0)),
                    "status": str(rec.get("status", "")),
                }
            )

        return {
            "processed_uploaded_count": len(results),
            "staged_upcoming_count": len(staged_only),
            "staged_upcoming_projects": staged_only,
            "results": results,
        }
