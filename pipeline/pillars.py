"""
ALL ABOUT BRAIN — 7 Canonical Academic Content Pillars (`P1`, `R20`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContentPillar:
    id: str
    name: str
    icon: str
    target_theme: str
    architectural_metaphor: str
    academic_domain: str
    default_narrative_style: str = "chronicle_cutaway"
    production_blueprint: dict[str, Any] = field(default_factory=dict)


PILLARS_DATA: dict[str, ContentPillar] = {
    "bci_tech": ContentPillar(
        id="bci_tech",
        name="BCI Tech Explained",
        icon="",
        target_theme="Hardware architectures, microelectrode arrays, neural decoders, and wireless telemetry interfaces.",
        architectural_metaphor="1,024 nanoscale electrode threads in the primary motor cortex decoding Layer V action potentials past an injured cervical spinal cord while the eyes track cursor feedback.",
        academic_domain="UCL PALS / Neural Engineering / Computational Neuroscience",
        default_narrative_style="chronicle_cutaway",
    ),
    "brain_news": ContentPillar(
        id="brain_news",
        name="Brain News",
        icon="",
        target_theme="Clinical trial breakthroughs, FDA device approvals, and vascular neuro-interventions.",
        architectural_metaphor="Endovascular stentrode catheter ascending the jugular vein into the superior sagittal sinus beside the primary motor cortex to record neural signals through blood vessel walls.",
        academic_domain="UCL PALS / Clinical Neurology / Neurovascular Medicine",
        default_narrative_style="chronicle_cutaway",
    ),
    "brain_history": ContentPillar(
        id="brain_history",
        name="Brain History",
        icon="",
        target_theme="Historical cranial surgery, trepanation, Phineas Gage, and the evolution of neuroanatomy.",
        architectural_metaphor="White-matter inhibitory pathways connecting the ventromedial prefrontal cortex to the emotional amygdala, passing behind the left orbital eye socket and optic nerve.",
        academic_domain="UCL PALS / History of Neuroscience / Cognitive Neuropsychology",
        default_narrative_style="delusion_museum",
    ),
    "brain_basics": ContentPillar(
        id="brain_basics",
        name="Brain Basics",
        icon="",
        target_theme="Action potentials, myelin insulation, ion channels, and fundamental biophysics of thought.",
        architectural_metaphor="Peripheral tactile mechanoreceptors and spinal dorsal column axons wrapped in glial myelin sheaths conducting saltatory voltage spikes across Nodes of Ranvier into the primary somatosensory cortex.",
        academic_domain="UCL PALS / Cellular Neuroscience / Neurophysiology",
        default_narrative_style="icon_autopsy",
    ),
    "brain_mysteries": ContentPillar(
        id="brain_mysteries",
        name="Brain Mysteries",
        icon="",
        target_theme="Déjà vu, illusions, sleep paralysis, and consciousness binding latency.",
        architectural_metaphor="Retinal optic nerve inputs traveling via dual thalamocortical pathways into the medial temporal lobe and hippocampus with millisecond desynchronization.",
        academic_domain="UCL PALS / Cognitive Neuroscience / Perception & Psychophysics",
        default_narrative_style="case_file",
    ),
    "brain_health": ContentPillar(
        id="brain_health",
        name="Brain Health",
        icon="",
        target_theme="The glymphatic system, sleep cleansing, dopamine receptor down-regulation, and neuroplastic repair.",
        architectural_metaphor="Perivascular glymphatic pathways and astrocytic aquaporin-4 channels expanding 60% during slow-wave sleep to flush toxic amyloid-beta from the cerebral cortex.",
        academic_domain="UCL PALS / Molecular Neurobiology / Sleep Medicine",
        default_narrative_style="caveman_brain",
    ),
    "bci_ethics": ContentPillar(
        id="bci_ethics",
        name="BCI Ethics",
        icon="",
        target_theme="Cognitive privacy, neural cryptography, subconscious ad insertion, and neuro-rights legislation.",
        architectural_metaphor="Intracortical microelectrodes linking auditory cortex inner speech circuits and prefrontal cortex synapses directly to external wireless decoders.",
        academic_domain="UCL PALS / Neuroethics / Jurisprudence & AI Safety",
        default_narrative_style="forbidden_lab",
    ),
}


def get_pillar(pillar_id_or_name: str | ContentPillar) -> ContentPillar:
    """Retrieves pillar by canonical id, fuzzy matching name, or returns ContentPillar directly."""
    if isinstance(pillar_id_or_name, ContentPillar):
        return pillar_id_or_name

    clean = str(pillar_id_or_name).lower().strip()
    if clean in PILLARS_DATA:
        return PILLARS_DATA[clean]

    for p_id, p in PILLARS_DATA.items():
        if p_id in clean or clean in p.name.lower():
            return p
        if p.icon and p.icon in str(pillar_id_or_name):
            return p

    return PILLARS_DATA["bci_tech"]


def list_all_pillars() -> list[ContentPillar]:
    return list(PILLARS_DATA.values())
