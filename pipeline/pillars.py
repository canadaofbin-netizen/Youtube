"""
ALL ABOUT BRAIN - 7 Content Pillars Specification & Production Blueprints
Adheres to UCL PALS academic standards and Production Contract v4.
"""

from dataclasses import dataclass
from typing import Any

from pipeline.flow_prompt_builder import BANNED_PROMPT_TOKENS, infer_visual_plan

BANNED_STYLE_TOKENS = [
    "pixel art", "8-bit", "16-bit retro", "low poly", "voxel", "claymation",
    "cartoon", "anime", "2D illustration", "comic book style", "sketch", "pencil drawing",
    "watercolor", "oil painting", "impressionist", "abstract art", "minimalist flat design",
    "cel-shaded", "neon punk", "cyberpunk", "dreamy pastel", "soft watercolor glow", "glitch art",
    *BANNED_PROMPT_TOKENS,
]


@dataclass(frozen=True)
class ContentPillar:
    id: str
    name: str
    icon: str
    target_theme: str
    architectural_metaphor: str
    academic_domain: str
    production_blueprint: dict[str, Any]
    default_narrative_style: str = "chronicle_cutaway"


PILLARS_DATA: dict[str, ContentPillar] = {
    # -------------------------------------------------------------------------
    # Pillar 1: BCI Tech Explained
    # -------------------------------------------------------------------------
    "bci_tech": ContentPillar(
        id="bci_tech",
        name="BCI Tech Explained",
        icon="",
        target_theme="Hardware architectures, microelectrode arrays, neural decoders, and wireless telemetry interfaces.",
        architectural_metaphor="1,024 nanoscale electrode threads in the primary motor cortex decoding Layer V action potentials past an injured cervical spinal cord while the eyes track cursor feedback.",
        academic_domain="UCL PALS / Neural Engineering / Computational Neuroscience",
        default_narrative_style="chronicle_cutaway",
        production_blueprint={
            "project_id": "pillar1_bci_tech_neuralink_n1",
            "title": "This Man Plays Chess with His Mind",
            "pillar": " BCI Tech Explained",
            "topic": "Neuralink N1 Motor Cortex BCI Human Clinical Trial",
            "source_url": "https://neuralink.com/blog/first-human-clinical-trial/",
            "source_tier": 1,
            "doi": "10.1038/s41586-024-07387-4",
            "core_facts": "Noland Arbaugh received the N1 wireless BCI with 1,024 electrodes across 64 threads on the primary motor cortex, controlling digital chess cursors wirelessly with millimeter precision.",
            "paradox_statement": "A paralyzed man plays live chess using only silent thought. It sounds like a cheat code.",
            "hook_text": "In twenty twenty-four, paralyzed patient Noland Arbaugh sat before a laptop screen. He played live chess using silent thought alone, without moving a single muscle.",
            "setup_text": "A diving accident had severed his cervical spinal cord and trapped every motor signal inside his skull. For his brain, this was a total nightmare.",
            "core_text": "Instead of repairing the broken spinal cord, neural engineers targeted the source. Sixty-four flexible electrode threads entered the hand region of his primary motor cortex. Step one: as his eyes track the chessboard, motor cortex electrodes decode action potentials into wireless cursor moves. The researchers were left completely stunned.",
            "payoff_text": "Which proves that a direct cortical interface can bypass a severed spinal cord and turn pure human intention into real-time action in seconds.",
            "clip_narrations": [
                "In twenty twenty-four, paralyzed patient Noland Arbaugh sat before a laptop screen. He played live chess using silent thought alone, without moving a single muscle.",
                "A diving accident had severed his cervical spinal cord and trapped every motor signal inside his skull. For his brain, this was a total nightmare.",
                "Instead of repairing the broken spinal cord, neural engineers targeted the source. Sixty-four flexible electrode threads entered the hand region of his primary motor cortex.",
                "Step one: as his eyes track the chessboard, motor cortex electrodes decode action potentials into wireless cursor moves. The researchers were left completely stunned.",
                "Which proves that a direct cortical interface can bypass a severed spinal cord and turn pure human intention into real-time action in seconds.",
            ],
            "visual_plan": infer_visual_plan(
                topic="Neuralink N1 Motor Cortex BCI Human Clinical Trial",
                core_facts="Noland Arbaugh received the N1 wireless BCI with 1,024 electrodes across 64 threads on the primary motor cortex.",
                pillar_id="bci_tech",
            ),
            "fact_citations": [
                {"claim": "1,024 electrodes on motor cortex", "source": "Neuralink PRIME Study (2024)"},
                {"claim": "Millimeter cursor control without muscle movement", "source": "Nature / NEJM Brain-Computer Interface Publications"},
            ],
            "hashtags": ["#Shorts", "#BCI", "#Neuralink", "#BrainScience", "#MindControl"],
        },
    ),

    # -------------------------------------------------------------------------
    # Pillar 2: Brain News
    # -------------------------------------------------------------------------
    "brain_news": ContentPillar(
        id="brain_news",
        name="Brain News",
        icon="",
        target_theme="Clinical trial breakthroughs, FDA device approvals, and vascular neuro-interventions.",
        architectural_metaphor="Endovascular stentrode catheter ascending the jugular vein into the superior sagittal sinus beside the primary motor cortex to record neural signals through blood vessel walls.",
        academic_domain="UCL PALS / Clinical Neurology / Neurovascular Medicine",
        default_narrative_style="chronicle_cutaway",
        production_blueprint={
            "project_id": "pillar2_brain_news_synchron_stentrode",
            "title": "BCI Implanted with Zero Skull Drilling",
            "pillar": " Brain News",
            "topic": "Synchron Stentrode Endovascular Brain-Computer Interface",
            "source_url": "https://synchron.com/news/first-human-clinical-results",
            "source_tier": 1,
            "doi": "10.1001/jamaneurol.2022.4847",
            "core_facts": "Synchron implanted the Stentrode BCI via the jugular vein into blood vessels over the primary motor cortex without open skull surgery, enabling paralyzed patients to communicate online.",
            "paradox_statement": "Surgeons just linked a computer directly to a living brain without opening the skull.",
            "hook_text": "In a landmark clinical trial, surgeons linked a paralyzed patient's brain directly to a personal computer without drilling a single millimeter into the human skull.",
            "setup_text": "Traditional brain implants require open craniotomy surgery that risks cortical bleeding and severe tissue damage. For paralyzed patients, this was a total nightmare.",
            "core_text": "Instead of cutting through cranial bone, doctors inserted a self-expanding nitinol stentrode catheter into the neck jugular vein and guided it up into the brain. Resting inside the superior sagittal vessel beside the motor cortex, sixteen sensors record neural firing through intact vessel walls. The researchers were left completely stunned.",
            "payoff_text": "Which proves that the cerebral bloodstream itself serves as a natural surgical highway to connect the human motor cortex directly with external digital machines.",
            "clip_narrations": [
                "In a landmark clinical trial, surgeons linked a paralyzed patient's brain directly to a personal computer without drilling a single millimeter into the human skull.",
                "Traditional brain implants require open craniotomy surgery that risks cortical bleeding and severe tissue damage. For paralyzed patients, this was a total nightmare.",
                "Instead of cutting through cranial bone, doctors inserted a self-expanding nitinol stentrode catheter into the neck jugular vein and guided it up into the brain.",
                "Resting inside the superior sagittal vessel beside the motor cortex, sixteen sensors record neural firing through intact vessel walls. The researchers were left completely stunned.",
                "Which proves that the cerebral bloodstream itself serves as a natural surgical highway to connect the human motor cortex directly with external digital machines.",
            ],
            "visual_plan": infer_visual_plan(
                topic="Synchron Stentrode Endovascular Brain-Computer Interface",
                core_facts="Synchron implanted the Stentrode BCI via the jugular vein into blood vessels over the primary motor cortex without open skull surgery.",
                pillar_id="brain_news",
            ),
            "fact_citations": [
                {"claim": "Endovascular catheter delivery of cortical electrodes", "source": "JAMA Neurology (2023) Synchron COMMAND Study"},
                {"claim": "Zero open skull surgery required for permanent BCI", "source": "Nature Biotechnology / FDA Breakthrough Device"},
            ],
            "hashtags": ["#Shorts", "#Neurotech", "#BrainNews", "#Synchron", "#Biomedical"],
        },
    ),

    # -------------------------------------------------------------------------
    # Pillar 3: Brain History
    # -------------------------------------------------------------------------
    "brain_history": ContentPillar(
        id="brain_history",
        name="Brain History",
        icon="",
        target_theme="Historical cranial surgery, trepanation, Phineas Gage, and the evolution of neuroanatomy.",
        architectural_metaphor="White-matter inhibitory pathways connecting the ventromedial prefrontal cortex to the emotional amygdala, passing behind the left orbital eye socket and optic nerve.",
        academic_domain="UCL PALS / History of Neuroscience / Cognitive Neuropsychology",
        default_narrative_style="delusion_museum",
        production_blueprint={
            "project_id": "pillar3_brain_history_phineas_gage",
            "title": "An Iron Rod Shot Through His Brain",
            "pillar": " Brain History",
            "topic": "The Phineas Gage Accident and Prefrontal Cortex Localization",
            "source_url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1114479/",
            "source_tier": 1,
            "doi": "10.1136/bmj.317.7174.1673",
            "core_facts": "In 1848, an iron tamping rod passed behind Phineas Gage's left eye and pierced his left ventromedial prefrontal cortex. He survived conscious, but his social inhibition permanently changed.",
            "paradox_statement": "An iron rod blasted clean through this man's skull, yet he walked away speaking.",
            "hook_text": "In eighteen forty-eight, a blast drove a heavy iron rod straight through Phineas Gage's skull, yet he walked away speaking clearly within minutes.",
            "setup_text": "The rod entered beneath his left cheekbone and tore through his frontal lobe behind the optic nerve. For nineteenth-century doctors, this was a total nightmare.",
            "core_text": "Instead of destroying his memory or speech, the injury selectively severed the white-matter tracts connecting his ventromedial prefrontal cortex to his subcortical emotional amygdala. Without prefrontal inhibitory signals calming the amygdala, his social judgment vanished while his rational intellect stayed intact. The researchers were left completely stunned.",
            "payoff_text": "Which proves that human moral personality and emotional self-control depend on intact physical white-matter pathways inside the frontal lobes of the human brain.",
            "clip_narrations": [
                "In eighteen forty-eight, a blast drove a heavy iron rod straight through Phineas Gage's skull, yet he walked away speaking clearly within minutes.",
                "The rod entered beneath his left cheekbone and tore through his frontal lobe behind the optic nerve. For nineteenth-century doctors, this was a total nightmare.",
                "Instead of destroying his memory or speech, the injury selectively severed the white-matter tracts connecting his ventromedial prefrontal cortex to his subcortical emotional amygdala.",
                "Without prefrontal inhibitory signals calming the amygdala, his social judgment vanished while his rational intellect stayed intact. The researchers were left completely stunned.",
                "Which proves that human moral personality and emotional self-control depend on intact physical white-matter pathways inside the frontal lobes of the human brain.",
            ],
            "visual_plan": infer_visual_plan(
                topic="The Phineas Gage Accident and Prefrontal Cortex Localization",
                core_facts="In 1848, an iron tamping rod passed behind Phineas Gage's left eye and pierced his left ventromedial prefrontal cortex.",
                pillar_id="brain_history",
            ),
            "fact_citations": [
                {"claim": "Tamping iron traversed left prefrontal cortex without causing death", "source": "British Medical Journal (1998) / Macmillan (2000)"},
                {"claim": "First documented evidence of frontal lobe executive function localization", "source": "Science (1994) Gage 3D Digital Reconstruction"},
            ],
            "hashtags": ["#Shorts", "#Neuroscience", "#BrainHistory", "#PhineasGage", "#MedicalHistory"],
        },
    ),

    # -------------------------------------------------------------------------
    # Pillar 4: Brain Basics
    # -------------------------------------------------------------------------
    "brain_basics": ContentPillar(
        id="brain_basics",
        name="Brain Basics",
        icon="",
        target_theme="Action potentials, myelin insulation, ion channels, and fundamental biophysics of thought.",
        architectural_metaphor="Peripheral tactile mechanoreceptors and spinal dorsal column axons wrapped in glial myelin sheaths conducting saltatory voltage spikes across Nodes of Ranvier into the primary somatosensory cortex.",
        academic_domain="UCL PALS / Cellular Neuroscience / Neurophysiology",
        default_narrative_style="icon_autopsy",
        production_blueprint={
            "project_id": "pillar4_brain_basics_action_potential",
            "title": "Thoughts Travel Faster Than a Racecar",
            "pillar": " Brain Basics",
            "topic": "Action Potential Propagation and Saltatory Conduction",
            "source_url": "https://www.ncbi.nlm.nih.gov/books/NBK538143/",
            "source_tier": 1,
            "doi": "10.1016/B978-0-12-809324-5.00004-9",
            "core_facts": "Action potentials travel along myelinated axons at up to 120 meters per second (over 268 mph) via saltatory conduction jumping between Nodes of Ranvier.",
            "paradox_statement": "Your thoughts travel faster than a Formula One racecar along microscopic biological wires.",
            "hook_text": "Every time skin touches a hot stove, electrical signals race along microscopic nerves into the human cortex faster than a Formula One racecar.",
            "setup_text": "Uninsulated nerve fibers leak electrical current into surrounding brain fluid and stall within millimeters. For a full-sized human nervous system, this is a total nightmare.",
            "core_text": "Instead of boosting raw cellular voltage, glial cells wrap long axons from the spinal cord to the cortex in tightly layered lipid myelin insulation. Electrical action potentials leap from one Node of Ranvier gap to the next at over one hundred meters per second. The researchers were left completely stunned.",
            "payoff_text": "Which proves that microscopic myelin insulation and ion channel gaps enable seventy-millivolt neural sparks to power human perception and movement in split seconds.",
            "clip_narrations": [
                "Every time skin touches a hot stove, electrical signals race along microscopic nerves into the human cortex faster than a Formula One racecar.",
                "Uninsulated nerve fibers leak electrical current into surrounding brain fluid and stall within millimeters. For a full-sized human nervous system, this is a total nightmare.",
                "Instead of boosting raw cellular voltage, glial cells wrap long axons from the spinal cord to the cortex in tightly layered lipid myelin insulation.",
                "Electrical action potentials leap from one Node of Ranvier gap to the next at over one hundred meters per second. The researchers were left completely stunned.",
                "Which proves that microscopic myelin insulation and ion channel gaps enable seventy-millivolt neural sparks to power human perception and movement in split seconds.",
            ],
            "visual_plan": infer_visual_plan(
                topic="Action Potential Propagation and Saltatory Conduction",
                core_facts="Action potentials travel along myelinated axons at up to 120 meters per second via saltatory conduction jumping between Nodes of Ranvier.",
                pillar_id="brain_basics",
            ),
            "fact_citations": [
                {"claim": "Saltatory conduction achieves up to 120 m/s velocity", "source": "Principles of Neural Science (Kandel et al., 6th Ed.)"},
                {"claim": "Myelin sheathing prevents electrical attenuation across axonal distances", "source": "Nature Reviews Neuroscience / UCL Lecture Series"},
            ],
            "hashtags": ["#Shorts", "#Neuroscience", "#BrainBasics", "#Biology", "#Physics"],
        },
    ),

    # -------------------------------------------------------------------------
    # Pillar 5: Brain Mysteries
    # -------------------------------------------------------------------------
    "brain_mysteries": ContentPillar(
        id="brain_mysteries",
        name="Brain Mysteries",
        icon="",
        target_theme="Déjà vu, illusions, sleep paralysis, and consciousness binding latency.",
        architectural_metaphor="Retinal optic nerve inputs traveling via dual thalamocortical pathways into the medial temporal lobe and hippocampus with millisecond desynchronization.",
        academic_domain="UCL PALS / Cognitive Neuroscience / Perception & Psychophysics",
        default_narrative_style="case_file",
        production_blueprint={
            "project_id": "pillar5_brain_mysteries_deja_vu",
            "title": "The Glitch Behind Déjà Vu Revealed",
            "pillar": " Brain Mysteries",
            "topic": "Dual Processing Theory of Déjà Vu in Thalamocortical Pathways",
            "source_url": "https://www.nature.com/articles/nrn1346",
            "source_tier": 1,
            "doi": "10.1038/nrn1346",
            "core_facts": "Déjà vu occurs when a micro-delay in one perceptual pathway causes the brain to process identical sensory data twice in milliseconds, mistakenly stamping the second arrival as an old memory.",
            "paradox_statement": "That eerie feeling of reliving this exact second is a timing glitch inside your neurons.",
            "hook_text": "Walking into a brand-new room can trigger an eerie certainty that this exact moment has already happened before, even when the place is completely unfamiliar.",
            "setup_text": "When present reality suddenly feels like a recorded memory replay, conscious perception clashes with logic. For the human brain, this is a total nightmare.",
            "core_text": "Instead of predicting the future, the retina sends visual signals along dual optic nerve pathways through the thalamic relay toward the temporal lobe memory circuit. When one pathway lags by twenty milliseconds, the hippocampus stamps the delayed second arrival as an old memory. The researchers were left completely stunned.",
            "payoff_text": "Which proves that déjà vu is not a paranormal premonition, but a millisecond synchronization glitch between thalamic sensory relays and hippocampal familiarity circuits.",
            "clip_narrations": [
                "Walking into a brand-new room can trigger an eerie certainty that this exact moment has already happened before, even when the place is completely unfamiliar.",
                "When present reality suddenly feels like a recorded memory replay, conscious perception clashes with logic. For the human brain, this is a total nightmare.",
                "Instead of predicting the future, the retina sends visual signals along dual optic nerve pathways through the thalamic relay toward the temporal lobe memory circuit.",
                "When one pathway lags by twenty milliseconds, the hippocampus stamps the delayed second arrival as an old memory. The researchers were left completely stunned.",
                "Which proves that déjà vu is not a paranormal premonition, but a millisecond synchronization glitch between thalamic sensory relays and hippocampal familiarity circuits.",
            ],
            "visual_plan": infer_visual_plan(
                topic="Dual Processing Theory of Déjà Vu in Thalamocortical Pathways",
                core_facts="Déjà vu occurs when a micro-delay in one perceptual pathway causes the brain to process identical sensory data twice in milliseconds.",
                pillar_id="brain_mysteries",
            ),
            "fact_citations": [
                {"claim": "Dual processing desynchronization produces subjective familiarity", "source": "Trends in Cognitive Sciences / Brown (2004)"},
                {"claim": "Thalamocortical millisecond delay triggers false memory attribution", "source": "Nature Reviews Neuroscience"},
            ],
            "hashtags": ["#Shorts", "#BrainMysteries", "#DejaVu", "#Psychology", "#Consciousness"],
        },
    ),

    # -------------------------------------------------------------------------
    # Pillar 6: Brain Health
    # -------------------------------------------------------------------------
    "brain_health": ContentPillar(
        id="brain_health",
        name="Brain Health",
        icon="",
        target_theme="The glymphatic system, sleep cleansing, dopamine receptor down-regulation, and neuroplastic repair.",
        architectural_metaphor="Perivascular glymphatic pathways and astrocytic aquaporin-4 channels expanding 60% during slow-wave sleep to flush toxic amyloid-beta from the cerebral cortex.",
        academic_domain="UCL PALS / Molecular Neurobiology / Sleep Medicine",
        default_narrative_style="caveman_brain",
        production_blueprint={
            "project_id": "pillar6_brain_health_glymphatic_wash",
            "title": "Your Brain Washes Itself Every Night",
            "pillar": " Brain Health",
            "topic": "The Glymphatic System and Nocturnal Toxic Metabolite Clearance",
            "source_url": "https://www.science.org/doi/10.1126/science.1241224",
            "source_tier": 1,
            "doi": "10.1126/science.1241224",
            "core_facts": "During deep sleep, brain interstitial space increases by 60%, allowing convective influx of cerebrospinal fluid via astrocytic aquaporin-4 channels to clear toxic amyloid-beta and tau proteins.",
            "paradox_statement": "If you skip sleep tonight, your brain literally drowns in its own toxic waste.",
            "hook_text": "Skipping a single night of deep sleep leaves the living human cortex bathing in the exact same metabolic waste proteins linked to Alzheimer's disease.",
            "setup_text": "Awake cortical neurons fire non-stop all day and shed sticky amyloid-beta plaques between tight cellular gaps. For the waking brain, this is a total nightmare.",
            "core_text": "Instead of relying on lymphatic vessels, the sleeping brain activates its own high-pressure plumbing network across the cerebral cortex during slow-wave delta sleep. Glial cells shrink by sixty percent, letting cerebrospinal fluid surge through aquaporin-4 channels to flush toxic plaques out. The researchers were left completely stunned.",
            "payoff_text": "Which proves that deep slow-wave sleep is an active mechanical wash cycle that scrubs neurotoxic waste from the cerebral cortex every single night.",
            "clip_narrations": [
                "Skipping a single night of deep sleep leaves the living human cortex bathing in the exact same metabolic waste proteins linked to Alzheimer's disease.",
                "Awake cortical neurons fire non-stop all day and shed sticky amyloid-beta plaques between tight cellular gaps. For the waking brain, this is a total nightmare.",
                "Instead of relying on lymphatic vessels, the sleeping brain activates its own high-pressure plumbing network across the cerebral cortex during slow-wave delta sleep.",
                "Glial cells shrink by sixty percent, letting cerebrospinal fluid surge through aquaporin-4 channels to flush toxic plaques out. The researchers were left completely stunned.",
                "Which proves that deep slow-wave sleep is an active mechanical wash cycle that scrubs neurotoxic waste from the cerebral cortex every single night.",
            ],
            "visual_plan": infer_visual_plan(
                topic="The Glymphatic System and Nocturnal Toxic Metabolite Clearance",
                core_facts="During deep sleep, brain interstitial space increases by 60%, allowing convective influx of cerebrospinal fluid via astrocytic aquaporin-4 channels.",
                pillar_id="brain_health",
            ),
            "fact_citations": [
                {"claim": "Deep sleep expands interstitial space by 60% for CSF bulk flow", "source": "Science (Xie et al., 2013)"},
                {"claim": "Glymphatic clearance eliminates neurotoxic beta-amyloid proteins", "source": "Nature Neuroscience / Nedergaard Lab"},
            ],
            "hashtags": ["#Shorts", "#BrainHealth", "#SleepScience", "#Biohacking", "#Alzheimers"],
        },
    ),

    # -------------------------------------------------------------------------
    # Pillar 7: BCI Ethics
    # -------------------------------------------------------------------------
    "bci_ethics": ContentPillar(
        id="bci_ethics",
        name="BCI Ethics",
        icon="",
        target_theme="Cognitive privacy, neural cryptography, subconscious ad insertion, and neuro-rights legislation.",
        architectural_metaphor="Intracortical microelectrodes linking auditory cortex inner speech circuits and prefrontal cortex synapses directly to external wireless decoders.",
        academic_domain="UCL PALS / Neuroethics / Jurisprudence & AI Safety",
        default_narrative_style="forbidden_lab",
        production_blueprint={
            "project_id": "pillar7_bci_ethics_neural_privacy",
            "title": "Can Hackers Steal Your Private Thoughts?",
            "pillar": " BCI Ethics",
            "topic": "Cognitive Privacy, Neural Cryptography, and Neuro-Rights",
            "source_url": "https://www.nature.com/articles/551159a",
            "source_tier": 1,
            "doi": "10.1038/551159a",
            "core_facts": "Advances in decoding intracortical signals enable reconstruction of internal monologue and visual memories, prompting global legal frameworks for neurorights to protect cognitive liberty.",
            "paradox_statement": "Your innermost thoughts are never private once a wireless chip enters your skull.",
            "hook_text": "Modern brain-computer interfaces can decode unspoken words directly from human cortex activity before the lips or vocal cords ever move to make a sound.",
            "setup_text": "An unencrypted wireless neural implant exposes private inner speech and emotional states to external interception. For human cognitive liberty, this is a total nightmare.",
            "core_text": "Instead of reading surface muscle twitches, intracortical electrode arrays tap directly into auditory cortex and prefrontal cortex synapses that generate silent internal monologue. Artificial intelligence decoders translate raw cortical spike patterns into continuous text streams at conversational speeds in real time. The researchers were left completely stunned.",
            "payoff_text": "Which proves that protecting the biological human brain requires hardware-level neural cryptography and constitutional neuro-rights before wireless cortical implants become everyday consumer technology.",
            "clip_narrations": [
                "Modern brain-computer interfaces can decode unspoken words directly from human cortex activity before the lips or vocal cords ever move to make a sound.",
                "An unencrypted wireless neural implant exposes private inner speech and emotional states to external interception. For human cognitive liberty, this is a total nightmare.",
                "Instead of reading surface muscle twitches, intracortical electrode arrays tap directly into auditory cortex and prefrontal cortex synapses that generate silent internal monologue.",
                "Artificial intelligence decoders translate raw cortical spike patterns into continuous text streams at conversational speeds in real time. The researchers were left completely stunned.",
                "Which proves that protecting the biological human brain requires hardware-level neural cryptography and constitutional neuro-rights before wireless cortical implants become everyday consumer technology.",
            ],
            "visual_plan": infer_visual_plan(
                topic="Cognitive Privacy, Neural Cryptography, and Neuro-Rights",
                core_facts="Advances in decoding intracortical signals enable reconstruction of internal monologue and visual memories.",
                pillar_id="bci_ethics",
            ),
            "fact_citations": [
                {"claim": "Four ethical priorities for neurotechnologies and artificial intelligence", "source": "Nature (Yuste et al., 2017)"},
                {"claim": "Cognitive liberty and neurorights statutory frameworks", "source": "UNESCO International Bioethics Committee"},
            ],
            "hashtags": ["#Shorts", "#BCIEthics", "#NeuroRights", "#CyberSecurity", "#FutureTech"],
        },
    ),
}


def get_pillar(pillar_id_or_name: str | ContentPillar) -> ContentPillar:
    """Retrieves pillar by canonical id, fuzzy matching name, or returns ContentPillar directly."""
    if isinstance(pillar_id_or_name, ContentPillar):
        return pillar_id_or_name

    clean = str(pillar_id_or_name).lower().strip()
    # Check canonical ids
    if clean in PILLARS_DATA:
        return PILLARS_DATA[clean]

    # Fuzzy check
    for p_id, p in PILLARS_DATA.items():
        if p_id in clean or clean in p.name.lower():
            return p
        if p.icon and p.icon in str(pillar_id_or_name):
            return p

    # Default to bci_tech
    return PILLARS_DATA["bci_tech"]


def list_all_pillars() -> list[ContentPillar]:
    return list(PILLARS_DATA.values())
