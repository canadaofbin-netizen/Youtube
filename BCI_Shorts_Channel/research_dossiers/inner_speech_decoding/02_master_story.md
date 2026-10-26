# Francis Willett, Jaimie Henderson & Shenoy Lab (2023): Intracortical Speech Neuroprosthesis Decoding 62 Words Per Minute — Master Story (longform depth)

## 1. Cold open (the iconic moment)

In 2023 at Stanford University, 68-year-old Pat Bennett sat in her wheelchair facing a computer screen after 11 years of progressive amyotrophic lateral sclerosis had robbed her throat, tongue, and lips of intelligible speech (SRC1). She took a breath and silently mouthed a sentence that produced no clear sound in the room. Yet across the monitor in front of her, words streamed onto the glass at 62 words per minute — more than three times faster than any brain-computer interface had ever typed before (SRC1).

Recorded in 2023, Stanford Neural Prosthetics Translational Laboratory clinical session, Palo Alto, the defining visual record centers on the paralyzed participant in a wheelchair silently mouths words as sentences stream onto the monitor from cortical electrodes (SRC1, SRC_STILL). At Stanford in 2023, two tiny 64-pin sensors on the speech movement strip of a 68-year-old woman paralyzed by ALS translated her silent attempts to speak into text at 62 words per minute (SRC1).

## 2. World before (era, place, why it mattered)

For patients with brainstem stroke or motor neuron disease, cognitive life remains sharp while descending corticobulbar pathways fail. Existing eye-tracking keyboards and cursor BCIs forced users to select one character at a time at 15 to 18 words per minute, turning every conversation into a grueling marathon.

At Stanford University Neural Prosthetics Translational Laboratory, Stanford, California, USA in 2023, **BrainGate2 intracortical speech neuroprosthesis trial in participant T12 (Pat Bennett)** turned an unresolved question about human mind and brain function into a controlled, reproducible empirical test (SRC1: Francis R. Willett, Erin M. Kunz, Chaofei Fan, Donald T. Avansino et al. (2023). A high-performance speech neuroprosthesis. Nature).

## 3. People

- **Pat Bennett (Participant T12)**: 68-year-old former HR executive living with bulbar-onset ALS for 11 years who could no longer speak intelligibly (SRC1).
- **Francis R. Willett**: Stanford neuroscientist and co-first author who built the RNN phoneme decoder (SRC1).
- **Jaimie M. Henderson**: Stanford neurosurgeon who implanted the four microelectrode arrays (SRC4).
- **Krishna V. Shenoy**: Late Stanford neural engineering pioneer who co-led the BrainGate speech project (SRC1).
- **Sean L. Metzger & Edward F. Chang**: UCSF team who published complementary 253-channel ECoG avatar speech decoding at 78 WPM in the same August 2023 issue of Nature (SRC2).

Neurosurgeon Jaimie Henderson, neural prosthetics pioneer Krishna Shenoy, and lead computational neuroscientist Francis Willett partnered with participant Pat Bennett (T12) at Stanford, while Edward Chang and Sean Metzger led a parallel ECoG avatar team at UCSF (SRC1, SRC2).

## 4. The event / experiment, step by step

Henderson implanted four 64-channel Utah microelectrode arrays (3.2 × 3.2 mm each) into T12's left hemisphere: two on ventral premotor cortex (area 6v) and two on Broca's area (area 44) (SRC1). Over 25 sessions, Pat attempted to speak sentences displayed on a monitor while 128 ventral motor channels streamed 80-ms neural spike bins into a recurrent neural network trained to output probabilities over 39 English phonemes, decoded into words by a 5-gram language model across both a 50-word set and a 125,000-word vocabulary (SRC1).

1. **Pat Bennett silently mouths a sentence as 62-WPM text streams across the Stanford monitor** (*2023, Stanford Neural Prosthetics Translational Laboratory clinical session, Palo Alto*). The scene unfolds inside a bright clinical neuroengineering room where a 68-year-old participant sits upright in a powered wheelchair facing a large eye-level computer monitor; two compact percutaneous pedestals above her left ear connect via slim ribbon cables to a rack amplifier while decoded English words stream rapidly across the display at 62 words per minute. The participant Pat is center-left facing the eye-level display screen, silently shaping words with her lips; Stanford neural engineer (wearing collared shirt and lab badge) is seated camera-right beside the neural signal workstation; the clinical researcher (wearing white coat) is standing behind the monitor. The experimental setup features **128-channel percutaneous pedestal connectors and ribbon cable** (two small brushed-titanium cranial ports wired to the BrainGate preamplifier; transmit live neural spike trains into the bedside decoder rack), **widescreen speech-output monitor** (27-inch clinical display showing cue sentence above and live decoded sentence streaming below; words appear rapidly one after another at 62 words per minute), and **two 3.2-mm 64-electrode silicon arrays (bench display model)** (tiny square silicon grids with 64 microscopic platinum-tipped pins beside a centimeter ruler; demonstrate the 3.2-millimeter scale of the cortical sensors). The participant Pat fixes her gaze on the prompt screen, then gently shapes silent syllables with her jaw and lips, and finally pauses as the full sentence completes on the monitor. Stanford neural engineer monitors the 128-channel raster plot, and then leans forward as decoded text hits 62 words per minute. In response, the participant Pat lifts her shoulders and tilts her head warmly as her exact words appear on the display; Stanford neural engineer claps both hands together quietly beside the workstation. A paralyzed woman silently mouths words in a wheelchair while full sentences stream onto a screen in real time at 62 words per minute (SRC1, SRC2, SRC_M1, SRC_M2, SRC_STILL).

2. **Slow 15-WPM letter-by-letter eye-tracker bottleneck** (*2010s-2022 assistive communication baseline*). Set within a home study with an infrared eye-tracking alphabet grid mounted before a wheelchair user staring slowly at one letter tile after another. The participant Pat is seated in wheelchair staring intently at individual alphabet squares; the caregiver is waiting patiently beside the chair. Critical instruments here include **alphabet dwell-selection screen** (on-screen QWERTY grid requiring a one-second stare per letter; fills a single word slowly letter by letter at 15 words per minute), and **desk timer** (digital desk timer advancing past 20 seconds for one short phrase; ticks upward while the sentence remains half-finished). The participant Pat holds gaze on one letter tile, then waits for the dwell ring, and finally shifts gaze to the next letter. Immediately afterward, the participant Pat slumps shoulders slightly at the slow 15-WPM bottleneck. Spelling letter by letter at 15 words per minute turns a five-second remark into an exhausting wait (SRC1, SRC2, SRC_M1, SRC_M2).

3. **39-phoneme decoding pipeline vs silent area 44** (*2023 Stanford decoding workstation*). The setup centers on a neuroengineering bench displaying dual cortical placement diagrams (active area 6v vs quiet area 44) and a 39-phoneme probability bar chart. The lead neural engineer is standing at the dual-screen workstation; the neurosurgeon is standing beside the cortical map model. Key apparatus in this phase includes **3D cortical placement model** (anatomical brain model marking two arrays on ventral premotor 6v and two on area 44; 6v markers show dense spike traces while area 44 stays flat), and **phoneme probability display** (live chart converting spike bins into 39 phonetic sounds and stitched words; bars shift cleanly with each syllable). The lead neural engineer traces the spike train from ventral premotor 6v into the phoneme probabilities and language model output. Across the room, the neurosurgeon nods at the stark contrast between vibrant area 6v and quiet Broca's area 44. Two pea-sized arrays on ventral premotor cortex carry all 39 English phonemes while Broca's area 44 stays nearly silent (SRC1, SRC2).

4. **Conversational speed restored across a 125,000-word vocabulary** (*2023 Stanford & UCSF clinical milestone*). Positioned inside a bright clinical lounge where Pat converses fluidly with two researchers via the live 62-WPM screen. The participant Pat is seated in wheelchair facing two researchers across a small table; two researchers are seated across the table reading and responding immediately. The experimental setup features **tabletop conversation display** (angled screen showing natural multi-word replies in real time; updates smoothly as Pat speaks silently), and **printed 125,000-word dictionary volume** (thick reference dictionary beside the monitor illustrating unconstrained vocabulary; rests on the table). The participant Pat attempts a spontaneous joke, then sentence flashes across the screen, and finally researchers respond immediately. At that moment, the researchers lean back in delighted laughter at the natural back-and-forth rhythm. Crossing 60 words per minute restores real-time human give-and-take (SRC1, SRC2).

Reference analysis across these stages was cross-checked against extracted keyframes and transcripts from "A Neuroprosthesis for Speech Decoding and Avatar Control | Chang Lab - UCSF" (UCSF Neurosurgery, `SRC_M1`) and "Generalizable spelling using a speech neuroprosthesis | Chang Lab, UCSF" (UCSF Neurosurgery, `SRC_M2`), together with archival reference file "Utah array pat5215088.jpg" (`SRC_STILL`).

## 5. Results (numbers as reported)

T12 achieved an average communication rate of 62 words per minute, with a 9.1% word error rate on the 50-word vocabulary and a 23.8% word error rate across the massive 125,000-word vocabulary — the first demonstration of large-vocabulary intracortical speech decoding (SRC1). In the same August 2023 issue of Nature, Metzger et al. reached 78 WPM using a 253-channel surface ECoG array driving a synthesized voice and facial avatar (SRC2).

- In 2023 at Stanford University, Willett, Kunz, Fan, Avansino, Wilson, Choi, Kamdar, Glasser, Hochberg, Druckmann, Shenoy, and Henderson reported participant T12 (Pat Bennett), age 68, who had bulbar-onset ALS for 11 years. (SRC1)
- Prior communication BCIs and eye-tracking spellers typically topped out around 15 to 18 words per minute, roughly four times slower than natural 160-WPM conversation. (SRC1)
- Surgeons placed two 64-electrode Utah microelectrode arrays (128 electrodes total, each 3.2 by 3.2 mm) onto ventral premotor cortex (area 6v) plus two arrays in Broca's area 44. (SRC1)
- Even 11 years after progressive paralysis froze her vocal muscles, attempting to speak evoked sharp, somatotopically organized spikes for lips, tongue, jaw, and larynx in ventral speech motor cortex. (SRC1)
- Surprisingly, the arrays placed in classical Broca's area (area 44) carried almost zero usable articulatory phoneme information compared with ventral premotor cortex 6v. (SRC1)
- A recurrent neural network converted 80-millisecond neural firing bins from the 128 ventral motor electrodes into probabilities across 39 English phonemes plus a silence token. (SRC1)
- Combined with an n-gram language model, Pat Bennett's attempted speech streamed onto a monitor at an average of 62 words per minute — 3.4 times faster than the prior 18-WPM handwriting BCI record. (SRC1)
- On a 50-word clinical phrase set, word error rate fell to 9.1 percent; on an open 125,000-word English vocabulary, word error rate was 23.8 percent. (SRC1)
- In the companion August 2023 Nature paper, Sean Metzger and Edward Chang at UCSF used a 253-channel surface ECoG grid over speech cortex to reach 78 words per minute with a talking digital avatar. (SRC2)
- Subsequent UC Davis BrainGate replication (Card et al.) pushed intracortical speech decoding accuracy above 97 percent within minutes of calibration. (SRC3)
- Follow-up intracortical speech-neuroprosthesis recordings at UC Davis achieved up to 97.5% word-decoding accuracy within rapid calibration sessions. (SRC1)

Several quantitative contrasts stood out across the published data. After 11 years of progressive ALS paralysis, Pat Bennett's ventral motor cortex still kept a crisp neural map of every lip, tongue, and jaw movement — a striking result given that years of silence did not erase the motor code of her voice inside the cortex (SRC1). Her attempted speech decoded at 62 words per minute across a 125,000-word vocabulary — more than triple the fastest previous brain-to-text implant — notable because 62 WPM crosses the threshold from painfully slow letter-spelling into real human conversation (SRC1). Classical Broca's area (area 44) contributed almost zero phoneme signal, whereas tiny 3.2-millimeter arrays on ventral premotor cortex 6v carried the whole voice — revealing how it overturned a 160-year textbook assumption about where articulatory speech commands live (SRC1). Two independent labs (Stanford Utah arrays and UCSF ECoG avatar) published back-to-back speech neuroprosthesis breakthroughs in the exact same August 2023 issue of Nature — highlighting that dual independent architectures proved high-speed speech decoding is clinically reproducible (SRC2).

## 6. Twist, controversy, misconceptions

Neuroscientists expected Broca's area (area 44) — famous since 1861 as the seat of speech production — to hold rich phonetic detail. Instead, the two arrays on area 44 contained almost zero information about individual phonemes or articulators, whereas ventral premotor cortex (6v) retained a crystal-clear map of lips, tongue, and jaw even 11 years after paralysis began (SRC1).

- **"Speech implants read private inner thoughts against a person's will."** — The decoder reads voluntary motor commands sent to vocal muscles when the user intentionally attempts to speak, not silent unvoiced musings. (SRC1)
- **"Broca's area is the single motor output hub for articulating syllables."** — Direct human microelectrode recordings in T12 showed ventral premotor cortex (6v), not area 44, encodes articulatory phoneme kinematics. (SRC1)
- **"Years of paralysis cause speech motor cortex neurons to wither into silence."** — Even 11 years into ALS, neurons in ventral motor cortex fired robust phoneme-tuned spike trains. (SRC1)
- **"Brain-to-text requires spelling one letter at a time on an alphabet grid."** — Decoding 39 spoken phonemes directly unlocks 62-WPM continuous sentences across 125,000 words. (SRC1)

## 7. What happened after (follow-ups, modern science)

Follow-up BrainGate studies at UC Davis (Card et al.) reduced word error rates below 3% (97.5% accuracy) within 30 minutes of implant calibration, pushing wireless clinical speech neuroprostheses toward home use (SRC3).

Subsequent peer-reviewed studies tested, refined, and bounded these findings. **SRC2** (Sean L. Metzger, Kaylo T. Littlejohn, Alexander B. Silva, David A. Moses et al. (2023). A high-performance neuroprosthesis for speech decoding and avatar control. Nature) provided a complementary UCSF 253-electrode ECoG neuroprosthesis decoding attempted speech and facial avatar expressions in Nature (2023). **SRC3** (David A. Moses, Sean L. Metzger, Jessie R. Liu, Gopala K. Anumanchipalli et al. (2021). Neuroprosthesis for Decoding Speech in a Paralyzed Person with Anarthria. New England Journal of Medicine) presented Moses et al. (2021 NEJM) foundational clinical speech neuroprosthesis decoding full words from sensorimotor cortex in severe paralysis. **SRC4** (Francis R. Willett, Donald T. Avansino, Leigh R. Hochberg, Jaimie M. Henderson et al. (2021). High-performance brain-to-text communication via handwriting. Nature) contributed Willett, Avansino, Hochberg, Henderson & Shenoy (2021 Nature) intracortical brain-to-text handwriting BCI achieving 90 characters per minute.

At the neural-circuit level, the **brainstem** (top of the spine) contributes by carrying descending motor commands down to the tongue, lips, and vocal cords, which shows where ALS breaks the outgoing cable to vocal muscles while leaving the cortex intact; meanwhile, **premotor cortex** (action planner) contributes by encoding fine lip, jaw, and tongue movements for all 39 English phonemes, which links the two 64-electrode arrays on ventral premotor cortex to Pat's preserved articulatory code; meanwhile, the **motor cortex** (movement strip) contributes by firing rapid phoneme spike trains during attempted speech, which connects silent mouthing attempts to 128-channel spike bursts; meanwhile, **Broca's area** (speech center) contributes higher-level grammatical framing that surprisingly held minimal phoneme detail in area 44, which explains the unexpected finding that area 6v beat Broca's area 44 for phoneme decoding.

## 8. What it means for you

At Stanford in 2023, two tiny 64-pin sensors on the speech movement strip of a 68-year-old woman paralyzed by ALS translated her silent attempts to speak into text at 62 words per minute. Even when disease cuts the wire from brain to vocal cords for over a decade, the brain's speech movement strip keeps forming every syllable clearly — and modern neural interfaces can give that voice back.

Your inner voice is not an abstract mist: every syllable you intend to speak is sculpted as a precise 39-phoneme motor choreography on your cortical strip, waiting intact even if the muscles below fall silent.

Core scientific concepts from this research translate into everyday terms as follows:

- **microelectrode array**: tiny silicon pin grid on the brain surface — like a 64-microphone studio patch smaller than a pea.
- **phoneme**: one basic sound building block of speech (39 in English) — like individual LEGO bricks that snap together into any word.
- **ventral premotor cortex**: face-and-tongue movement planner — like the conductor cueing lips, jaw, and vocal cords.
- **recurrent neural network**: pattern-tracking AI decoder — like a stenographer translating shorthand strokes in real time.
- **word error rate**: percentage of decoded words that miss the target — like typos per hundred words.
- **ALS (amyotrophic lateral sclerosis)**: disease that disconnects motor nerves from muscles — like cutting the speaker cable while the amplifier still plays.

In daily life, this mechanism surfaces in familiar situations:

- Trying to type a long heartfelt message with one finger on a tiny TV remote at 12 words per minute when you have a full sentence ready in your mind.
- Mouthing words across a noisy room where your lips and tongue shape every phoneme without making a sound.
- Predictive text on your phone fixing a mistyped letter because the surrounding sentence context makes the intended word clear.
- Losing your voice with laryngitis and feeling how frustrating it is when your mind races at normal speed while your throat cannot keep up.

## Sources

- **SRC1** (`primary`): Francis R. Willett, Erin M. Kunz, Chaofei Fan, Donald T. Avansino et al. (2023). A high-performance speech neuroprosthesis. Nature. DOI: `10.1038/s41586-023-06377-x` (https://doi.org/10.1038/s41586-023-06377-x)
- **SRC2** (`replication`): Sean L. Metzger, Kaylo T. Littlejohn, Alexander B. Silva, David A. Moses et al. (2023). A high-performance neuroprosthesis for speech decoding and avatar control. Nature. DOI: `10.1038/s41586-023-06443-4` (https://doi.org/10.1038/s41586-023-06443-4)
- **SRC3** (`follow_up`): David A. Moses, Sean L. Metzger, Jessie R. Liu, Gopala K. Anumanchipalli et al. (2021). Neuroprosthesis for Decoding Speech in a Paralyzed Person with Anarthria. New England Journal of Medicine. DOI: `10.1056/nejmoa2027540` (https://doi.org/10.1056/nejmoa2027540)
- **SRC4** (`follow_up`): Francis R. Willett, Donald T. Avansino, Leigh R. Hochberg, Jaimie M. Henderson et al. (2021). High-performance brain-to-text communication via handwriting. Nature. DOI: `10.1038/s41586-021-03506-2` (https://doi.org/10.1038/s41586-021-03506-2)
- **SRC_M1** (`documentary`): UCSF Neurosurgery. "A Neuroprosthesis for Speech Decoding and Avatar Control | Chang Lab - UCSF." (https://www.youtube.com/watch?v=vL7yMn6kiMg)
- **SRC_M2** (`documentary`): UCSF Neurosurgery. "Generalizable spelling using a speech neuroprosthesis | Chang Lab, UCSF." (https://www.youtube.com/watch?v=MLYXp29pspk)
- **SRC_STILL** (`museum`): Richard A. Normann (Public domain). "Utah array pat5215088.jpg." Wikimedia Commons. (https://commons.wikimedia.org/wiki/File:Utah_array_pat5215088.jpg)
