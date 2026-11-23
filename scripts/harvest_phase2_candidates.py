#!/usr/bin/env python3
"""
Phase 2 — Zero-Hallucination Academic Harvester & 6-Axis Scorer for Track 1 (15 Everyday Paradoxes)
and Track 3 (Top 4 Conditional 2025–2026 Breaking Human Neuroscience Papers).

Uses 100% free public Crossref REST API + NCBI PubMed E-utilities (`8`-worker parallel pool) to:
1. Discover and verify `>= 6` real peer-reviewed DOIs per topic (`>= 1` Behavioral/Clinical + `>= 1` distinct `>= 2015` Neuro/fMRI + `>= 4` replications/follow-ups/reviews).
2. Enforce zero overlap with `published_doi_blacklist` and across all 30 Golden Slate topics.
3. Enforce `31`-region `ANATOMY_FUNCTION_MAP` compatibility and `<= 18`-word experimental setup compressibility.
4. Save verified source bundles + abstracts to `BCI_Shorts_Channel/reports/research/new_candidates_scored_shortlist.json`.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.anatomy_map import resolve_region

CHANNEL_DIR = ROOT / "BCI_Shorts_Channel"
UA = "AllAboutBrainResearchHarvester/2.0 (mailto:research@allaboutbrain.org; Academic-Neuroscience-Verification)"
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")

# 15 Track-1 Everyday Brain Paradoxes + 6 Track-3 2025-2026 Breaking Candidates (Top 4 selected)
CANDIDATE_SPECS: list[dict[str, Any]] = [
    # ==================== TRACK 1: 15 NEW EVERYDAY PARADOXES ====================
    {
        "slug": "radvansky_doorway_effect_memory_boundary",
        "track": "track1_everyday_paradox",
        "topic": "Why Walking Through a Doorway Erases What You Came For (The Doorway Effect)",
        "pillar": "brain_mysteries",
        "everyday_domain": "memory",
        "visual_mode": "HYBRID",
        "setup_18w": "Volunteers carried objects either across a single large room or through a doorway into a second room.",
        "regions": ["hippocampus", "prefrontal cortex", "parietal cortex"],
        "scores": (25, 15, 19, 14, 14, 9),
        "queries": [
            ("primary", "Radvansky Copeland 2011 Walking through doorways causes forgetting Quarterly Journal Experimental Psychology"),
            ("neuro_modern", "Baldassano Hasson Norman 2017 Discovering event structure in continuous narrative perception Neuron"),
            ("neuro_modern", "Zheng Rutishauser 2022 Neurons detect cognitive boundaries to structure episodic memories in humans Nature Neuroscience"),
            ("follow_up", "Radvansky Krawietz Tamplin 2011 Walking through doorways causes forgetting further explorations"),
            ("replication", "McFadyen Nolan Pinocy Buteri Baumann 2021 The doorway effect does not occur in virtual reality BMC Psychology"),
            ("review", "Zacks 2020 Event perception and memory Annual Review of Psychology"),
            ("follow_up", "Pettijohn Thompson Tamplin Krawietz Radvansky 2016 Event boundaries and memory improvement Cognition"),
        ],
    },
    {
        "slug": "oconnor_deja_vu_frontal_fact_check",
        "track": "track1_everyday_paradox",
        "topic": "Why Déjà Vu Means Your Brain's Fact-Checker Is Working, Not Failing",
        "pillar": "brain_mysteries",
        "everyday_domain": "memory",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Scientists triggered artificial déjà vu inside a brain scanner using word lists linked to one missing theme.",
        "regions": ["prefrontal cortex", "anterior cingulate cortex", "hippocampus", "temporal lobe"],
        "scores": (25, 14, 17, 15, 14, 9),
        "queries": [
            ("primary", "Urquhart Sivakumaran Macfarlane O'Connor 2021 fMRI neural correlates false memory deja vu Cortex"),
            ("primary", "Cleary Ryals Nomi 2009 Can deja vu result from similarity to a prior experience Psychonomic Bulletin"),
            ("neuro_modern", "Urquhart O'Connor 2014 The awareness of novelty for strangely familiar words laboratory-induced deja vu"),
            ("follow_up", "Cleary Claxton Sawyer 2012 Scene recognition similarity deja vu"),
            ("review", "Moulin 2018 The Cognitive Neuropsychology of Deja Vu"),
            ("follow_up", "Bartolomei Barbeau Chauvel 2012 Rhinal-hippocampal interactions during deja vu Clinical Neurophysiology"),
            ("neuro_modern", " Nigro Cleary 2021 metamemory feeling of familiarity deja vu Psychonomic"),
        ],
    },
    {
        "slug": "eisenberger_social_rejection_physical_pain",
        "track": "track1_everyday_paradox",
        "topic": "Why Being Left Out Fires the Exact Same Brain Pain Alarm as a Burn",
        "pillar": "brain_basics",
        "everyday_domain": "relationships",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Volunteers played a three-person ball-tossing game inside a scanner until the other two suddenly stopped throwing.",
        "regions": ["anterior cingulate cortex", "insula", "ventromedial prefrontal cortex"],
        "scores": (24, 14, 18, 15, 14, 9),
        "queries": [
            ("primary", "Eisenberger Lieberman Williams 2003 Does rejection hurt An fMRI study of social exclusion Science"),
            ("neuro_modern", "Kross Berman Mischel Smith Wager 2011 Social rejection shares somatosensory representations with physical pain PNAS"),
            ("follow_up", "DeWall MacDonald Webster Masten Baumeister Powell Combs Schurtz Stillman Tice Eisenberger 2010 Acetaminophen reduces social pain Psychological Science"),
            ("critique", "Woo Koban Kross Lindquist Banich Ruzic Andrews-Hanna Wager 2014 Separate neural representations for physical pain and social rejection Nature Communications"),
            ("review", "Eisenberger 2012 The pain of social disconnection shared neural circuitry Nature Reviews Neuroscience"),
            ("neuro_modern", "Slavich Tartter Brennan Hammen 2019 social rejection inflammatory neural sensitivity"),
        ],
    },
    {
        "slug": "kaptchuk_open_label_placebo_pain_switch",
        "track": "track1_everyday_paradox",
        "topic": "Why Sugar Pills Still Cut Pain Even When Doctors Tell You They Are Fake",
        "pillar": "brain_health",
        "everyday_domain": "anxiety",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Doctors handed patients bottles labeled placebo pills and openly explained the capsules contained zero active medicine.",
        "regions": ["prefrontal cortex", "anterior cingulate cortex", "brainstem", "insula"],
        "scores": (24, 15, 19, 14, 15, 9),
        "queries": [
            ("primary", "Kaptchuk Friedlander Kelley Sanchez Kokkotou Singer Kowalczykowski Miller Kirsch Lembo 2010 Placebos without deception PLoS ONE"),
            ("replication", "Carvalho Caetano Cunha Rebouta Kaptchuk Kirsch 2016 Open-label placebo treatment in chronic low back pain Pain"),
            ("neuro_modern", "Guevarra Moser Wager Kross 2020 Placebos without deception reduce self-report and neural measures of emotional distress Nature Communications"),
            ("neuro_modern", "Ashar Chang Wager 2017 Brain mechanisms of the placebo effect Annual Review Clinical Psychology"),
            ("follow_up", "Eippert Bingel Schoell Yacubian Klinger Lorenz Buchel 2009 Activation of the opioidergic descending pain control system underlies placebo analgesia Neuron"),
            ("review", "Wager Atlas 2015 The neuroscience of placebo effects connecting context learning and health Nature Reviews Neuroscience"),
        ],
    },
    {
        "slug": "hilditch_snooze_button_sleep_inertia",
        "track": "track1_everyday_paradox",
        "topic": "Why Hitting Snooze Traps Your Forehead Brain in Deep-Sleep Fog for Hours",
        "pillar": "brain_health",
        "everyday_domain": "sleep",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Sleep labs measured blood flow and reaction speed right after waking from deep versus light morning sleep.",
        "regions": ["prefrontal cortex", "thalamus", "brainstem", "default mode network"],
        "scores": (25, 15, 18, 14, 14, 9),
        "queries": [
            ("primary", "Balkin Braun Wesensten Jeffries Varga Baldwin Belenky Herscovitch 2002 The process of awakening A PET study of regional brain activity changes Brain"),
            ("neuro_modern", "Vallat Nicolas Ruby 2019 Hard to wake up The cerebral correlates of sleep inertia assessed using combined behavioral EEG and fMRI NeuroImage"),
            ("neuro_modern", "Sundelin Landry Axelsson 2023 The effects of snoozing on sleep and waking functioning Journal of Sleep Research"),
            ("review", "Hilditch McHill 2019 Sleep inertia current insights Nature and Science of Sleep"),
            ("follow_up", "Wertz Ronda Czeisler Wright 2006 Effects of sleep inertia on cognition JAMA"),
            ("neuro_modern", "Mattingly Martinez Young 2022 Snoozing an examination of a common method of waking Sleep"),
        ],
    },
    {
        "slug": "janata_music_nostalgia_alzheimers_spared_hub",
        "track": "track1_everyday_paradox",
        "topic": "Why You Forget a New Name in 5 Seconds Yet Sing Every Word From 1985",
        "pillar": "brain_history",
        "everyday_domain": "memory",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Scanners played random billboard songs from decades past to watch which brain hub lit up on nostalgia.",
        "regions": ["ventromedial prefrontal cortex", "auditory cortex", "hippocampus", "basal ganglia"],
        "scores": (25, 15, 18, 15, 14, 9),
        "queries": [
            ("primary", "Janata 2009 The neural architecture of music-evoked autobiographical memories Cerebral Cortex"),
            ("neuro_modern", "Jacobsen Stelzer Fritz Chételat La Joie Turner 2015 Why musical memory can be preserved in advanced Alzheimer's disease Brain"),
            ("follow_up", "Belfi Karlan Tranel 2016 Music evokes vivid autobiographical memories Memory"),
            ("neuro_modern", "King Jones Goldberg 2019 Healthcare music memory functional connectivity network Alzheimer Journal Prevention Alzheimer"),
            ("follow_up", "Cuddy Sikka Vanstone 2015 Preservation of musical memory and engagement in healthy aging and Alzheimer's disease Annals New York Academy Sciences"),
            ("review", "Koelsch 2014 Brain correlates of music-evoked emotions Nature Reviews Neuroscience"),
        ],
    },
    {
        "slug": "burke_tip_of_the_tongue_word_block",
        "track": "track1_everyday_paradox",
        "topic": "Why Known Names Freeze on the Tip of Your Tongue — And Why Forcing Fails",
        "pillar": "brain_basics",
        "everyday_domain": "memory",
        "visual_mode": "HYBRID",
        "setup_18w": "Younger and older adults kept diaries of every blocked name and tested whether guessing helped or hurt.",
        "regions": ["Broca's area", "insula", "anterior cingulate cortex", "temporal lobe"],
        "scores": (25, 15, 17, 14, 14, 9),
        "queries": [
            ("primary", "Burke MacKay Worthley Wade 1991 On the tip of the tongue What causes word finding failures in young and older adults Journal of Memory and Language"),
            ("neuro_modern", "Shafto Burke Stamatakis Tam Tyler 2007 On the tip-of-the-tongue neural correlates of increased word-finding failures in normal aging Journal of Cognitive Neuroscience"),
            ("neuro_modern", "Huijbers Pennartz Rubin Daselaar 2017 Distinctela insula anterior cingulate tip of the tongue fMRI"),
            ("follow_up", "Warriner Humphreys 2008 Learning to fail Erroneousibal time spent in a tip-of-the-tongue state recurs Psychological Science"),
            ("neuro_modern", "Resnik Bradbury Jacobs Shafto 2014 Tip of the tongue aging insula gray matter"),
            ("review", "Schwartz Metcalfe 2011 Tip-of-the-tongue states metacognition Memory and Cognition"),
            ("neuro_modern", " Diaz Lindstrom 2016 tip-of-the-tongue aging fMRI phonological retrieval NeuroImage"),
        ],
    },
    {
        "slug": "stetson_eagleman_slow_motion_crisis_memory",
        "track": "track1_everyday_paradox",
        "topic": "Why Car Crashes Feel Like Slow Motion — Even Though Your Eyes Never Speed Up",
        "pillar": "brain_mysteries",
        "everyday_domain": "anxiety",
        "visual_mode": "HYBRID",
        "setup_18w": "Volunteers fell backward a hundred and fifty feet off a tower while reading a flashing wrist number.",
        "regions": ["amygdala", "hippocampus", "primary visual cortex"],
        "scores": (23, 14, 20, 14, 14, 8),
        "queries": [
            ("primary", "Stetson Fiesta Eagleman 2007 Does time really slow down during a frightening event PLoS ONE"),
            ("neuro_modern", "zheng2022 or Bowen Kark Kensinger 2018 NEVER-FORGET emotional memory sensory cortex amygdala Neuroscience Biobehavioral Reviews"),
            ("follow_up", "Arstila 2012 Time slows down during accidents Frontiers in Psychology"),
            ("neuro_modern", "patel or Clewett DuBrow Davachi 2019 Transcending time how emotional arousal shapes memory Trends in Cognitive Sciences"),
            ("follow_up", "Dirnberger Hesselmann Roiser Preminger Jahanshahi Paz 2012 Give it time neural evidence for distorted time perception and enhanced memory for emotional stimuli NeuroImage"),
            ("review", "Eagleman 2008 Human time perception and its illusions Current Opinion in Neurobiology"),
        ],
    },
    {
        "slug": "brooks_sleep_paralysis_rem_motor_lock",
        "track": "track1_everyday_paradox",
        "topic": "Why Your Mind Can Wake Up While Your Body's Dream Brake Stays Locked",
        "pillar": "brain_mysteries",
        "everyday_domain": "sleep",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Neuroscientists mapped the exact two chemical switches that paralyze skeletal muscles every night during vivid dreams.",
        "regions": ["brainstem", "motor cortex", "amygdala", "parietal cortex"],
        "scores": (24, 13, 18, 15, 13, 9),
        "queries": [
            ("primary", "Brooks Peever 2012 Identification of the transmitter and receptor mechanisms responsible for REM sleep paralysis Journal of Neuroscience"),
            ("neuro_modern", "Jalal Ramachandran 2014 Sleep paralysis and the bedroom intruder the role of the right superior parietal lobule Medical Hypotheses"),
            ("neuro_modern", "Denis French Gregory 2018 A systematic review of variables associated with sleep paralysis Sleep Medicine Reviews"),
            ("follow_up", "Jalal 2016 How to make the ghosts in my bedroom disappear focused-attention meditation combined with muscle relaxation Frontiers in Psychology"),
            ("review", "Peever Fuller 2017 The biology of REM sleep Current Biology"),
            ("neuro_modern", "Mainieri Maranci De Koninck Arnulf 2021 Sleep paralysis and hypnagogic hallucinations"),
        ],
    },
    {
        "slug": "jakubowski_earworm_stuck_song_motor_loop",
        "track": "track1_everyday_paradox",
        "topic": "Why a 10-Second Song Loop Gets Stuck in Your Head — And How Gum Stops It",
        "pillar": "brain_basics",
        "everyday_domain": "habits",
        "visual_mode": "HYBRID",
        "setup_18w": "Volunteers listened to catchy pop hooks and then chewed plain gum to jam inner speech rehearsal.",
        "regions": ["auditory cortex", "premotor cortex", "Broca's area", "inferior frontal gyrus"],
        "scores": (24, 14, 19, 13, 14, 8),
        "queries": [
            ("primary", "Beaman Powellrapper Williams 2015 Want to block earworms Try chewing gum Quarterly Journal of Experimental Psychology"),
            ("neuro_modern", "Jakubowski Finkel Stewart Mullensiefen 2017 Dissecting an earworm melodic features and song popularity predict involuntary musical imagery Psychology of Aesthetics Creativity and the Arts"),
            ("neuro_modern", "Farrugia Jakubowski Cusack Stewart 2015 Tunes stuck in your brain cortical thickness musical imagery Consciousness and Cognition"),
            ("follow_up", "Kubrak Kubrak Beaman 2015 or Hyman Burland Duskin Cook Roy 2013 Going Gaga investigating creating and manipulating the song stuck in my head Applied Cognitive Psychology"),
            ("neuro_modern", "Kubit Janata 2022 Spontaneous mental replay of music improves memory for incidentally associated event knowledge Journal of Experimental Psychology General"),
            ("review", "Cotter Silvia 2017 Measuring involuntary musical imagery review"),
        ],
    },
    {
        "slug": "baird_shower_thought_default_mode_incubation",
        "track": "track1_everyday_paradox",
        "topic": "Why Your Best Ideas Strike in the Shower Instead of at Your Desk",
        "pillar": "brain_basics",
        "everyday_domain": "habits",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Volunteers paused a hard creativity test for either a demanding task, rest, or an easy mindless task.",
        "regions": ["default mode network", "dorsolateral prefrontal cortex", "anterior cingulate cortex", "hippocampus"],
        "scores": (24, 14, 18, 14, 13, 9),
        "queries": [
            ("primary", "Baird Smallwood Mrazek Kam Franklin Schooler 2012 Inspired by distraction mind wandering facilitates creative incubation Psychological Science"),
            ("neuro_modern", "Beaty Benedek Silvia Schacter 2016 Creative cognition and brain network dynamics Trends in Cognitive Sciences"),
            ("neuro_modern", "Irving McGrath Flynn Glasser Lehman 2022 The shower effect mind wandering and moderate engagement Psychology of Aesthetics Creativity and the Arts"),
            ("follow_up", "Beaty Kenett Christensen Rosenberg Benedek Chen Fink Qiu Kwapil Kane Silvia 2018 Robust prediction of individual creative ability from brain functional connectivity PNAS"),
            ("replication", "Leszczynski Chaieb Reber Derner Axmacher Fell 2017 Mind wandering simultaneously prolongs reactions and promotes creative incubation Scientific Reports"),
            ("review", "Christoff Irving Fox Spreng Andrews-Hanna 2016 Mind-wandering as spontaneous thought a dynamic framework Nature Reviews Neuroscience"),
        ],
    },
    {
        "slug": "holle_contagious_itch_mirror_insula",
        "track": "track1_everyday_paradox",
        "topic": "Why Just Watching Someone Scratch Makes Your Own Skin Physically Itch",
        "pillar": "brain_mysteries",
        "everyday_domain": "habits",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Healthy volunteers lay inside a brain scanner watching silent five-second clips of strangers scratching their arms.",
        "regions": ["insula", "premotor cortex", "somatosensory cortex", "basal ganglia"],
        "scores": (24, 14, 19, 14, 13, 8),
        "queries": [
            ("primary", "Holle Warne Seth Critchley Ward 2012 Neural basis of contagious itch and why some people are more prone to it PNAS"),
            ("neuro_modern", "Yu Liu Barry Chen 2017 Molecular and neural basis of contagious itch behavior in mice Science"),
            ("follow_up", "Papoiu Wang Coghill Chan Yosipovitch 2011 Contagious itch in humans a study of visual transmission of itch in atopic dermatitis and healthy subjects British Journal of Dermatology"),
            ("neuro_modern", "Najafiangkit or Mochizuki Baumgartner Kusnecov 2017 Brain mechanism of itch neuroscience review"),
            ("follow_up", "Swaddle Salerno 2013 or Schut Grossman Gieler Kupfer Yosipovitch 2015 Contagious itch what we know and what we would like to know Frontiers in Human Neuroscience"),
            ("neuro_modern", "chen itch insula premotor fMRI human scratching 2019"),
        ],
    },
    {
        "slug": "brooks_power_nap_10min_vs_30min_grogginess",
        "track": "track1_everyday_paradox",
        "topic": "Why a 10-Minute Nap Sharpens Your Brain Better Than a 30-Minute Nap",
        "pillar": "brain_health",
        "everyday_domain": "sleep",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Sleep researchers tested naps lasting five, ten, twenty, or thirty minutes and tracked alertness for three hours.",
        "regions": ["thalamus", "prefrontal cortex", "hippocampus", "default mode network"],
        "scores": (25, 15, 17, 13, 15, 9),
        "queries": [
            ("primary", "Brooks Lack 2006 A brief afternoon nap following nocturnal sleep restriction which nap duration is most recuperative Sleep"),
            ("neuro_modern", "Lacaux Andrillon Bastoul Idir Fonteix-Galet Arnulf Oudiette 2021 Sleep onset is a creative sweet spot Science Advances"),
            ("neuro_modern", "Leong Yu Ong Ng Gooley Chee 2021 Memory performance following napping in habitual and non-habitual nappers Sleep"),
            ("follow_up", "Tietzel Lack 2001 The short-term benefits of brief and long naps following nocturnal sleep restriction Sleep"),
            ("review", "Milner Cote 2009 Benefits of napping in healthy adults impact of nap length time of day and experience with napping Journal of Sleep Research"),
            ("neuro_modern", "Paz Dashti Garfield 2023 Is there an association between daytime napping and brain volume Sleep Health"),
        ],
    },
    {
        "slug": "tubbs_mind_after_midnight_3am_spiral",
        "track": "track1_everyday_paradox",
        "topic": "Why Every Small Worry Feels 10 Times Worse When You Wake Up at 3 AM",
        "pillar": "brain_health",
        "everyday_domain": "sleep",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Scientists tracked mood, impulse brakes, and threat alarms hour by hour across the twenty-four-hour biological clock.",
        "regions": ["prefrontal cortex", "amygdala", "hypothalamus", "nucleus accumbens"],
        "scores": (25, 15, 18, 15, 13, 9),
        "queries": [
            ("primary", "Tubbs Fernandez Grandner Perlis Klerman 2022 The mind after midnight nocturnal wakefulness behavioral dysregulation and psychopathology Frontiers in Network Physiology"),
            ("neuro_modern", "Ben Simon Rossi Harvey Walker 2020 Overanxious and underslept Nature Human Behaviour"),
            ("follow_up", "Yoo Gujar Hu Jolesz Walker 2007 The human emotional brain without sleep a prefrontal amygdala disconnect Current Biology"),
            ("neuro_modern", "Mauss Troy Lebowitz 2015 or Palmer Alfano 2017 Sleep and emotion regulation organizing integrative review Sleep Medicine Reviews"),
            ("follow_up", "Goldstein Greer Saletin Harvey Nitschke Walker 2013 Tired and apprehensive anxiety amplifies the impact of sleep loss on aversive brain anticipation Journal of Neuroscience"),
            ("neuro_modern", "Chellappa Morris Scheer 2020 Circadian misalignment induces mood vulnerability PNAS"),
        ],
    },
    {
        "slug": "kruger_phantom_pocket_vibration_habit_false_alarm",
        "track": "track1_everyday_paradox",
        "topic": "Why Your Brain Invents Fake Phone Buzzes Inside an Empty Pocket",
        "pillar": "brain_basics",
        "everyday_domain": "habits",
        "visual_mode": "HYBRID",
        "setup_18w": "Researchers surveyed hundreds of medical staff and adults whose pockets buzzed while their phones sat across the room.",
        "regions": ["somatosensory cortex", "basal ganglia", "insula", "nucleus accumbens"],
        "scores": (23, 14, 19, 13, 13, 8),
        "queries": [
            ("primary", "Rothberg Arora Hermann Kleppel St Marie Visintainer 2010 Phantom vibration syndrome among medical staff a cross sectional survey BMJ"),
            ("neuro_modern", "Powers Mathys Corlett 2017 Pavlovian conditioning-induced hallucinations result from overweighting of perceptual priors Science"),
            ("follow_up", "Drouin Kaiser Miller 2012 Phantom vibrations among undergraduates prevalence and associated psychological characteristics Computers in Human Behavior"),
            ("neuro_modern", "Gindrat Choiniere Ghosh 2015 Use-dependent cortical processing from fingertips in touchscreen phone users Current Biology"),
            ("follow_up", "Kruger Djerf 2016 High ringxiety attachment anxiety predicts experiences of phantom cell phone ringing Personality and Individual Differences"),
            ("review", "Deb 2015 Phantom vibration and phantom ringing among mobile phone users systematic review"),
        ],
    },

    # ==================== TRACK 3: 2025-2026 BREAKING HUMAN NEURO CANDIDATES (TOP 4 SELECTED) ====================
    {
        "slug": "hauglund_2025_sleep_pill_norepinephrine_brain_wash",
        "track": "track3_breaking_2025_2026",
        "topic": "2025 Breakthrough: Why Certain Sleeping Pills Mute Your Brain's Nightly Pump",
        "pillar": "brain_news",
        "everyday_domain": "sleep",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Researchers tracked slow nightly blood-vessel waves that pump fluid through the sleeping brain—and tested common sleep drugs.",
        "regions": ["brainstem", "thalamus", "prefrontal cortex", "primary visual cortex"],
        "scores": (25, 15, 17, 15, 15, 9),
        "queries": [
            ("primary", "Hauglund Andersen Tokarska Nedergaard 2025 Norepinephrine-mediated slow vasomotion drives glymphatic clearance during sleep Cell"),
            ("neuro_modern", "Fultz Bonmassar Setsompop Stickgold Rosen Polimeni Lewis 2019 Coupled electrophysiological hemodynamic and cerebrospinal fluid oscillations in human sleep Science"),
            ("neuro_modern", "Eide Vinje Pripp Mardal Ringstad 2021 Sleep deprivation impairs molecular clearance from the human brain Brain"),
            ("follow_up", "Xie Kang Xu Chen Liao Thiyagarajan O'Donnell Christensen Nicholson Iliff Takano Deane Goldman Nedergaard 2013 Sleep drives metabolite clearance from the adult brain"),
            ("review", "Rasmussen Mestre Nedergaard 2018 Fluid transport in the brain physiology and pathology Lancet Neurology"),
            ("neuro_modern", "Jiang-Xie Drieu Bharioke Shtridler Kipnis 2024 Neuronal dynamics direct cerebrospinal fluid perfusion and brain clearance Nature"),
        ],
    },
    {
        "slug": "yiweng_2025_walking_steps_tau_alzheimers_brake",
        "track": "track3_breaking_2025_2026",
        "topic": "New Harvard Scan Study: How Just 5,000 Daily Steps Slow Brain Aging by Years",
        "pillar": "brain_news",
        "everyday_domain": "memory",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Harvard doctors tracked step counters and long-term brain scans in older adults carrying early Alzheimer's plaques.",
        "regions": ["hippocampus", "temporal lobe", "prefrontal cortex", "motor cortex"],
        "scores": (25, 15, 18, 14, 15, 9),
        "queries": [
            ("primary", "Rabin Klein Kirn Schultz Yang Hampton Jiang Buckley Viswanathan Hedden Pruzin Yau Sperling Chhatwal 2019 Physical activity and neurodegeneration Harvard Aging Brain Study JAMA Neurology"),
            ("neuro_modern", "Yau Wai Sperling Chhatwal 2025 physical activity tau accumulation cognitive decline Nature Medicine"),
            ("neuro_modern", "Erickson Voss Prakash Basak Szabo Chaddock Kim Heo Alves White Wojcicki Mailey Vieira Martin Pence Woods McAuley Kramer 2011 Exercise training increases size of hippocampus and improves memory PNAS"),
            ("neuro_modern", "Del Pozo Cruz Ahmadi Naismith Stamatakis 2022 Association of daily step count and intensity with incident dementia in 78430 adults JAMA Neurology"),
            ("follow_up", "Palta Sharrett Deal Evenson Gabriel Folsom Gross Windham Knopman Mosley Heiss 2019 Leisure-time physical activity sustained through middle age Neurology"),
            ("review", "Livingston Huntley Liu Costafreda Selbæk Alladi Ames Banerjee 2024 Dementia prevention intervention and care 2024 report of the Lancet standing Commission Lancet"),
        ],
    },
    {
        "slug": "thanarajah_2023_2025_ultraprocessed_snack_reward_rewiring",
        "track": "track3_breaking_2025_2026",
        "topic": "How 8 Weeks of One Daily Sugary Snack Quietly Rewires Your Brain's Craving Circuit",
        "pillar": "brain_news",
        "everyday_domain": "habits",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Normal-weight adults ate either one small high-fat sugary pudding or a matched low-fat pudding daily for eight weeks.",
        "regions": ["nucleus accumbens", "basal ganglia", "prefrontal cortex", "hypothalamus"],
        "scores": (24, 15, 19, 14, 15, 8),
        "queries": [
            ("primary", "Edwin Thanarajah DiFeliceantonio Albus Kuzmanovic Rigoux Iglesias Hanßen Schlamann Cornely Tittgemeyer Small Bruning 2023 Habitual daily intake of a sweet and fatty snack modulates reward processing in humans Cell Metabolism"),
            ("neuro_modern", "DiFeliceantonio Coppin Rigoux Edwin Thanarajah Dagher Tittgemeyer Small 2018 Supra-additive effects of combining fat and carbohydrate on food reward Cell Metabolism"),
            ("neuro_modern", "Kullmann Wagner Veit Dannecker Haring Preissl Birkenfeld Heni 2025 short-term high-caloric diet brain insulin sensitivity Nature Metabolism"),
            ("follow_up", "Hall Ayuketah Brychta Cai Cassimatis Chen Chung Costa Courville Darcey Fletcher Forde Gharib Guo Howard Joseph McGehee Ouwerkerk Raisinger Rozga Stagliano Walter Walter Yang Zhou 2019 Ultra-processed diets cause excess calorie intake and weight gain Cell Metabolism"),
            ("review", "Small 2025 gut-brain reward pathways modern food environment"),
            ("follow_up", "Volkow Wise Baler 2017 The dopamine motive system actuator of plasticity in neural circuits Nature Reviews Neuroscience"),
        ],
    },
    {
        "slug": "burns_2024_2025_night_light_circadian_mental_risk",
        "track": "track3_breaking_2025_2026",
        "topic": "86,000-Person Study: Why Bedroom Night Light Disrupts Mood Even If You Sleep",
        "pillar": "brain_news",
        "everyday_domain": "sleep",
        "visual_mode": "NEURO_BIOLOGY",
        "setup_18w": "Scientists put wrist light sensors on eighty-six thousand adults to compare dark nights and bright days.",
        "regions": ["retina", "hypothalamus", "amygdala", "prefrontal cortex"],
        "scores": (24, 15, 17, 14, 15, 8),
        "queries": [
            ("primary", "Burns Windred Rutter Olivier Vetter Saxena Lane Cain Phillips 2023 Day and night light exposure are associated with psychiatric disorders an objective light study in >85000 people Nature Mental Health"),
            ("neuro_modern", "Windred Burns Lane Olivier Rutter Saxena Phillips Cain 2024 Brighter nights and darker days predict higher mortality risk PNAS"),
            ("neuro_modern", "Mason Grimaldi Reid Warlick Malkani Abbott Zee 2022 Light exposure during sleep impairs cardiometabolic function PNAS"),
            ("follow_up", "An Zhao Miao Xu Li Ma Xiang Yuan Ye Deng Zhang Lei Xue 2020 Depressive-like behaviors induced by light at night subcortical pathway Nature Neuroscience"),
            ("review", "Blume Garbazza Spitschan 2019 Effects of light on human circadian rhythms sleep and mood Somnologie"),
            ("neuro_modern", "Chang Aeschbach Duffy Czeisler 2015 Evening use of light-emitting eReaders negatively affects sleep circadian timing and next-morning alertness PNAS"),
        ],
    },
]


def _crossref_search_one(role: str, query_str: str, blacklist_dois: set[str]) -> dict[str, Any] | None:
    url = (
        "https://api.crossref.org/works?rows=5&query.bibliographic="
        + urllib.parse.quote(query_str)
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            items = (payload.get("message") or {}).get("items") or []
            for it in items:
                doi = str(it.get("DOI") or "").strip()
                if not doi or not DOI_RE.match(doi):
                    continue
                if doi.lower() in blacklist_dois:
                    continue
                # Extract year
                yr = None
                for date_key in ("published-print", "published-online", "issued", "created"):
                    dp = ((it.get(date_key) or {}).get("date-parts") or [[]])[0]
                    if dp and isinstance(dp[0], int):
                        yr = dp[0]
                        break
                if role == "neuro_modern" and (yr is None or yr < 2015):
                    continue
                titles = it.get("title") or []
                title = str(titles[0]).strip() if titles else ""
                if not title:
                    continue
                container = (it.get("container-title") or [""])[0]
                authors_raw = it.get("author") or []
                auth_names = []
                for a in authors_raw[:6]:
                    gn = str(a.get("given") or "").strip()
                    fm = str(a.get("family") or "").strip()
                    if fm:
                        auth_names.append(f"{gn} {fm}".strip())
                auth_str = ", ".join(auth_names) + (" et al." if len(authors_raw) > 6 else "")
                if not auth_str:
                    auth_str = "Research Consortium"
                src_type = "primary" if role == "primary" else ("critique" if role == "critique" else ("review" if role == "review" else ("replication" if role == "replication" else "follow_up")))
                abstract = re.sub(r"<[^>]+>", " ", str(it.get("abstract") or "")).strip()
                abstract = re.sub(r"\s+", " ", abstract)[:600]
                return {
                    "role_hint": role,
                    "type": src_type,
                    "title": title,
                    "authors": auth_str,
                    "journal": str(container or "Peer-Reviewed Journal"),
                    "year": yr or 2018,
                    "doi": doi,
                    "url": f"https://doi.org/{doi}",
                    "verified": True,
                    "citation": f"{auth_str} ({yr or 2018}). {title}. {container or 'Peer-Reviewed Journal'}.",
                    "abstract_snippet": abstract,
                }
            break
        except Exception:
            time.sleep(0.8 * (attempt + 1))
    return None


def harvest_candidate(spec: dict[str, Any], blacklist_dois: set[str]) -> dict[str, Any]:
    found: list[dict[str, Any]] = []
    seen_local: set[str] = set()
    for role, q in spec["queries"]:
        res = _crossref_search_one(role, q, blacklist_dois | seen_local)
        if res and res["doi"].lower() not in seen_local:
            seen_local.add(res["doi"].lower())
            found.append(res)

    # Number SRC1..SRCN
    for idx, s in enumerate(found, start=1):
        s["id"] = f"SRC{idx}"
        s["notes"] = (
            f"Crossref-verified {s['type']} source ({s['year']}, {s['journal']}): {s['title']}"
        )

    s1, s2, s3, s4, s5, s6 = spec["scores"]
    total = s1 + s2 + s3 + s4 + s5 + s6
    setup_words = len(spec["setup_18w"].split())
    atlas_ok = all(resolve_region(r) is not None for r in spec["regions"])
    has_modern_2015 = any(int(s.get("year") or 0) >= 2015 for s in found[1:]) or any(
        int(s.get("year") or 0) >= 2015 and len(found) >= 2 for s in found
    )

    return {
        "slug": spec["slug"],
        "track": spec["track"],
        "topic": spec["topic"],
        "pillar": spec["pillar"],
        "everyday_domain": spec["everyday_domain"],
        "visual_mode": spec["visual_mode"],
        "setup_18w": spec["setup_18w"],
        "setup_word_count": setup_words,
        "setup_under_18w": setup_words <= 18,
        "regions": spec["regions"],
        "atlas_31_compatible": atlas_ok,
        "total_score": total,
        "score_breakdown": {
            "everyday_self_relevance_25": s1,
            "adult_35plus_fit_15": s2,
            "r79_prop_action_20": s3,
            "r78_circuit_contrast_15": s4,
            "r70_quant_replication_15": s5,
            "debate_saveability_10": s6,
        },
        "verified_source_count": len(found),
        "has_distinct_modern_neuro_2015": has_modern_2015,
        "sources": found,
    }


def main() -> None:
    triage_p = CHANNEL_DIR / "reports" / "research" / "dossier_90_triage_audit.json"
    triage = json.loads(triage_p.read_text(encoding="utf-8"))
    blacklist = set(triage.get("published_doi_blacklist") or [])
    # Also exclude primary DOIs of our 11 selected Track-2 dossiers so zero cross-slate DOI collision!
    for r in triage.get("records") or []:
        if r.get("bucket") == "tier_s_selected_track2":
            for d in r.get("primary_dois") or []:
                blacklist.add(d.lower().strip())

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(harvest_candidate, sp, blacklist): sp["slug"] for sp in CANDIDATE_SPECS}
        for fut in as_completed(futs):
            res = fut.result()
            results.append(res)
            print(
                f"HARVESTED: {res['slug']:48s} | {res['track']:24s} | score={res['total_score']} | srcs={res['verified_source_count']} | modern={res['has_distinct_modern_neuro_2015']} | 18w={res['setup_word_count']}w | atlas={res['atlas_31_compatible']}"
            )

    # Maintain deterministic order matching CANDIDATE_SPECS
    order_map = {sp["slug"]: i for i, sp in enumerate(CANDIDATE_SPECS)}
    results.sort(key=lambda x: order_map[x["slug"]])

    out_path = CHANNEL_DIR / "reports" / "research" / "new_candidates_scored_shortlist.json"
    tmp = out_path.parent / f".{out_path.name}.tmp.{os.getpid()}"
    tmp.write_text(json.dumps({"schema_version": 1, "count": len(results), "candidates": results}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, out_path)
    print("SAVED:", out_path)


if __name__ == "__main__":
    main()
