# `Ep #14` `R89` Supplementary-Video Pilot Candidates (`CC BY 4.0` · `0-Face` Pixel-Audited)

> [!IMPORTANT]
> **Verification Status (`@Topic_Radar` Chief · Zero CDP `9222` / Flow / Project Folder Creation)**
> - **Legal Clearance (`Zero Fair Use Gambling`)**: Every finalist and runner-up carries an independently verified per-article **`CC BY 4.0`** license (`https://creativecommons.org/licenses/by/4.0/`) across Crossref metadata, publisher `Rights and permissions` / copyright statements, and supplementary caption files (**`0`** caption exclusion carve-outs under `R89_CAPTION_EXCLUSION_PATTERNS`).
> - **Pixel & Privacy Gate (`audit_archival_video_eligibility`)**: All 3 finalists + 2 runner-ups were downloaded to `/tmp/r89_ep14_probe/`, trimmed/cropped where specified, stripped of audio (`-an`), and verified via `5.0 fps` YuNet face detection (`eligible=True`, `faces=0, max=0.0000`, `max_frame_diff >= 0.30`).
> - **Zero Overlap**: All 5 DOIs checked against all `81` existing projects + `35`-item [topic_priority_queue.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/topic_priority_queue.json) (`84` unique DOIs) → **`False` (`0` overlap)**.
> - **Next Action**: User selects **1** finalist below before any project folder (`BCI_Shorts_Channel/projects/*`) is created.

---

## 1. Executive Comparison Matrix (`3` Verified Finalists)

| Rank | Domain / Pillar | Paper, Journal & Year | DOI (`HTTP 200`) | License & Carve-Out Audit | Supplementary Movie & Verified Viewport | `audit_archival_video_eligibility` Receipt | Recommended `R89` Mode | `<= 12w` US Shorts Hook (`R87-H`) |
|---|---|---|---|---|---|---|---|---|
| **#1 (Rec.)** | `sleep` / `brain_health` | Carro-Domínguez et al. (ETH Zürich), *Nature Communications* (`2025`) | `10.1038/s41467-025-57289-5` | `CC BY 4.0` · `0` carve-outs (`MOESM2` PDF clean) | `Supplementary Movie 1` (`t = 6.0–10.0s`), `eye_top_crop [90, 0, 620, 200]` | `eligible=True`, `faces=0` (`0.0000`), `max_frame_diff=6.9017`, `issues=[]` | **`Mode 1 (Split-Sync)`** *(or `Mode 2` full `720x480`)* | `"Scientists taped sleepers' eyes open and caught pupils pulsing all night."` (`11w`) |
| **#2** | `memory` / `brain_basics` | Zubair et al. (UCLA / BU), *PLOS Biology* (`2026`) | `10.1371/journal.pbio.3003695` | `CC BY 4.0` · `0` carve-outs (strict PLOS OA) | `S1 Video` (`t = 3.5–7.0s`), `left_mem_below_eyes [60, 175, 790, 710]` | `eligible=True`, `faces=0` (`0.0000`), `max_frame_diff=23.1735`, `issues=[]` | **`Mode 1 (Split-Sync)`** | `"Your eyes dart around right before a lost memory clicks back."` (`11w`) |
| **#3** | `bci_tech` / `habits` | Ding et al. (CMU Bin He Lab), *Nature Communications* (`2025`) | `10.1038/s41467-025-61064-x` | `CC BY 4.0` · `0` carve-outs (`MOESM2` PDF clean) | `Supplementary Movie 1` (`t = 6.0–10.0s`), full `1200x600` or `[0, 0, 600, 600]` | `eligible=True`, `faces=0` (`0.0000`), `max_frame_diff=1.9015` (full) / `2.7783` (left), `issues=[]` | **`Mode 2 (Viewfinder)`** *(or `Mode 1`)* | `"No brain surgery: pure thoughts just moved individual robotic fingers live."` (`11w`) |

---

## 2. Detailed Dossier Cards & Audit Receipts

### Candidate 1 (Recommended #1 — `sleep` · Highest Channel Velocity Domain)
- **Paper Title**: *Pupil size reveals arousal level fluctuations in human sleep*
- **Lead Author & Institution**: Manuel Carro-Domínguez et al., ETH Zürich (Neural Control of Movement Lab)
- **Journal & Publication Date**: *Nature Communications* (`2025-02-28`)
- **DOI & Article URL**: [`10.1038/s41467-025-57289-5`](https://www.nature.com/articles/s41467-025-57289-5)
- **Per-Article License & Carve-Out Audit**:
  - **License**: `CC BY 4.0` ([`https://creativecommons.org/licenses/by/4.0/`](https://creativecommons.org/licenses/by/4.0/)) verified in both Crossref API metadata and the publisher `Rights and permissions` block.
  - **Exclusion Carve-Out Check**: Audited `41467_2025_57289_MOESM2_ESM.pdf` (*Description of Additional Supplementary Files*) against `R89_CAPTION_EXCLUSION_PATTERNS` → **`0` exclusion hits** (`[]`).
- **Supplementary Movie & Direct URL (`HTTP 200`)**:
  - **ID**: `Supplementary Movie 1` (`7,451,336 B`, `720x480 @ 50.0fps`, `20.0s`, `audio=0`)
  - **Direct MP4 URL**: [`41467_2025_57289_MOESM3_ESM.mp4`](https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-025-57289-5/MediaObjects/41467_2025_57289_MOESM3_ESM.mp4)
- **Pixel Audit Receipt (`audit_archival_video_eligibility`, `5.0 fps` YuNet)**:
  - **Recommended Trim Window**: `t = 6.0–10.0s` (`4.0s` peak NREM2 auditory-stimulus pupil dilation, `-an` `audio=0`):
    - **`eye_top_crop [90, 0, 620, 200]`** *(for `Mode 1 Split-Sync`)*: `eligible=True`, `faces=0 (max=0.0000)`, `max_frame_diff=6.9017`, `issues=[]`
    - **`full [0, 0, 720, 480]`** *(for `Mode 2 Viewfinder`)*: `eligible=True`, `faces=0 (max=0.0000)`, `max_frame_diff=4.8412`, `issues=[]`
    - **`pupil_tight [200, 0, 520, 195]`**: `eligible=True`, `faces=0 (max=0.0000)`, `max_frame_diff=10.2503`, `issues=[]`
  - **Forensic Note**: Frames in `t = 0–6s` trigger a YuNet false positive (`max_score=0.6676`) on the uncropped macro iris geometry; trimming strictly to **`t = 6.0–10.0s`** removes all detector false positives while showing the largest pupil expansion (`0` identifiable face — unidentifiable single infrared eye).
  - **Contact Sheet**: [Pupil_Sleep_2025_M1_fast_sheet.jpg](file:///tmp/r89_ep14_probe/Pupil_Sleep_2025_M1_fast_sheet.jpg)
- **Key Study Facts & `R86` Viewer Payoff**:
  - **Findings**: `17` analyzed healthy participants (`18` recruited; `15` full-night pupil recordings) slept overnight with their right eye safely taped open under a clear protective shield. Pupil size fluctuated continuously during unconscious sleep—shrinking inversely with protective sleep spindle clusters (tracking locus coeruleus norepinephrine tone) and predicting evoked cortical delta-wave restoration to nighttime tones.
  - **`R86` One-Sentence Takeaway**: *Even when your eyes are shut and you are fast asleep, your pupils silently pulse open and shut with hidden brain arousal waves that decide whether a sound wakes you up.*
- **Visual Action (`2–4s`) & `R89` Layout Spec**:
  - **On-Screen Motion**: Macro infrared closeup of a sleeping human pupil visibly swelling wide open in `NREM2` sleep as live `FPz`/`Cz` EEG traces ripple underneath.
  - **Best Layout**: **`Mode 1 (Split-Sync)`** — Top viewport (`[90, 0, 620, 200]`) shows the real infrared sleeping pupil ballooning open, synced `1:1` to an `Ep #31` 3D cyan `brainstem` → `thalamus` → `prefrontal cortex` flare in the bottom viewport *(alternatively `Mode 2 Viewfinder` with full `720x480` + `A01` head locator)*.
- **Proposed `<= 12w` US Shorts Hook (`R87-H`) & `0.5s` Mute Test**:
  - **Hook (`11w`)**: *"Scientists taped sleepers' eyes open and caught pupils pulsing all night."*
  - **`0.5s` Mute Test Payoff**: Instant visual shock of a dark sleeping pupil expanding dynamically right above the glowing cyan brainstem without reading a single word.
- **Exact Publish Attribution (`R89` `CC BY 4.0`)**:
  > `Video credit: Adapted from Manuel Carro-Domínguez et al., Nature Communications (2025), Supplementary Movie 1, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) — cropped & muted (https://www.nature.com/articles/s41467-025-57289-5).`

---

### Candidate 2 (Recommended #2 — `memory` · Strict `PLOS Biology` `CC BY 4.0`)
- **Paper Title**: *Eye movements reflect memory-related theta activity in the human brain*
- **Lead Author & Institution**: Humza N. Zubair et al., UCLA (Jane and Terry Semel Institute for Neuroscience and Human Behavior) & Boston University
- **Journal & Publication Date**: *PLOS Biology* `24(3): e3003695` (`2026-03-16`)
- **DOI & Article URL**: [`10.1371/journal.pbio.3003695`](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3003695)
- **Per-Article License & Carve-Out Audit**:
  - **License**: `CC BY 4.0` ([`https://creativecommons.org/licenses/by/4.0/`](https://creativecommons.org/licenses/by/4.0/)) — strict *PLOS Biology* Open Access copyright statement (`"Copyright: © 2026 Zubair et al. This is an open access article distributed under the terms of the Creative Commons Attribution License..."`).
  - **Exclusion Carve-Out Check**: Verified `0` third-party media carve-outs (the substring `"excluded from"` in the article text appears solely inside Methods describing excluded amygdala/non-MTL analysis channels).
- **Supplementary Movie & Direct URL (`HTTP 200`)**:
  - **ID**: `S1 Video` (`video/mp4`, `8,061,774 B`, `1600x720 @ 25.0fps`, `8.0s`, raw `audio=1` → stripped to `0` via Gear 4 `-an`)
  - **Direct MP4 URL**: [`journal.pbio.3003695.s009`](https://journals.plos.org/plosbiology/article/file?type=supplementary&id=10.1371/journal.pbio.3003695.s009)
- **Pixel Audit Receipt (`audit_archival_video_eligibility`, `5.0 fps` YuNet across full `8.0s`, SHA-256 `196fefed021d...`)**:
  - **`left_mem_below_eyes [60, 175, 790, 710]`** *(Recommended for `Mode 1 Split-Sync` — Memory-Cued Navigation first-person room + glowing yellow/red gaze reticle + live hippocampal Theta Power trace, cleanly cropping out the top-left eye inset that hit `0.4436`)*: `eligible=True`, `faces=0 (max=0.0000)`, `max_frame_diff=23.1735`, `issues=[]`
  - **`left_mem_world_right_of_eyes [260, 40, 790, 440]`** *(pure outward first-person gaze scan)*: `eligible=True`, `faces=0 (max=0.0000)`, `max_frame_diff=43.7291`, `issues=[]`
  - **Best `3.5s` Trim Window**: `t = 3.5–7.0s` (gaze sweeping room wall boundaries as the live hippocampal Theta wave spikes upward).
  - **Contact Sheet**: [Zubair_PLOSBio_2026_S1_sheet.jpg](file:///tmp/r89_ep14_probe/Zubair_PLOSBio_2026_S1_sheet.jpg)
  - **Privacy Transparency Flag (`R89` Patient Guard)**: The study recorded `5` adult clinical RNS epilepsy patients (`ages 31–52`); **however**, the cropped viewport `[60, 175, 790, 710]` contains **100% outward-facing empty room walls + yellow gaze cursor + anonymous Theta waveform** (`0` patient face, `0` eyes, `0` body, `0` identifying features). Flagged explicitly for CEO/user sign-off.
- **Key Study Facts & `R86` Viewer Payoff**:
  - **Findings**: Simultaneous mobile intracranial medial temporal lobe (MTL) iEEG and eye tracking in `5` freely walking adults (`ages 31–52`) revealed that hippocampal theta oscillations spike during exploratory saccadic eye movements specifically under memory-guided recall (not visually guided walking), amplify near room boundaries, and lock their phase to saccade onset.
  - **`R86` One-Sentence Takeaway**: *When your eyes dart around a room trying to remember where you left something, every eye flick is physically syncing with hippocampal memory waves.*
- **Visual Action (`2–4s`) & `R89` Layout Spec**:
  - **On-Screen Motion**: First-person room sweep with a bright glowing yellow/red gaze reticle hopping across wall markers while the live hippocampal Theta wave beneath surges sharply upward.
  - **Best Layout**: **`Mode 1 (Split-Sync)`** — Top viewport (`[60, 175, 790, 710]`) shows the real-time Memory-Cued gaze sweep + Theta surge, paired directly below with synced `Ep #31` 3D cyan `hippocampus` + `parietal cortex` recall pulses.
- **Proposed `<= 12w` US Shorts Hook (`R87-H`) & `0.5s` Mute Test**:
  - **Hook (`11w`)**: *"Your eyes dart around right before a lost memory clicks back."*
  - **`0.5s` Mute Test Payoff**: First-person gaze cursor jumping across landmarks in lockstep with a real brainwave trace and 3D hippocampus firing below.
- **Exact Publish Attribution (`R89` `CC BY 4.0`)**:
  > `Video credit: Adapted from Humza N. Zubair et al., PLOS Biology (2026), S1 Video, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) — cropped & muted (https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3003695).`

---

### Candidate 3 (Recommended #3 — `bci_tech` · `0` Clinical Patients · `0` Faces Full-Frame)
- **Paper Title**: *EEG-based brain-computer interface enables real-time robotic hand control at individual finger level*
- **Lead Author & Institution**: Yidan Ding et al. (Bin He Lab), Carnegie Mellon University (Department of Biomedical Engineering)
- **Journal & Publication Date**: *Nature Communications* (`2025-06-30`)
- **DOI & Article URL**: [`10.1038/s41467-025-61064-x`](https://www.nature.com/articles/s41467-025-61064-x)
- **Per-Article License & Carve-Out Audit**:
  - **License**: `CC BY 4.0` ([`https://creativecommons.org/licenses/by/4.0/`](https://creativecommons.org/licenses/by/4.0/)) verified in Crossref metadata and publisher `Rights and permissions`.
  - **Exclusion Carve-Out Check**: Audited `41467_2025_61064_MOESM2_ESM.pdf` (*Description of Additional Supplementary Files*) against `R89_CAPTION_EXCLUSION_PATTERNS` → **`0` exclusion hits** (`[]`).
- **Supplementary Movie & Direct URL (`HTTP 200`)**:
  - **ID**: `Supplementary Movie 1` (`28,855,781 B`, `1200x600 @ 30.0fps`, `50.0s`, raw `audio=1` → stripped to `0` via Gear 4 `-an`)
  - **Direct MP4 URL**: [`41467_2025_61064_MOESM3_ESM.mp4`](https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-025-61064-x/MediaObjects/41467_2025_61064_MOESM3_ESM.mp4)
- **Pixel Audit Receipt (`audit_archival_video_eligibility`, `5.0 fps` YuNet, SHA-256 `1fa6eb9ff4f7...`)**:
  - **Full `1200x600` (entire `50.0s` source movie)**: `eligible=True`, `faces=0 (max=0.0000)`, `max_frame_diff=1.9015`, `issues=[]`
  - **`left_half [0, 0, 600, 600]` (`t = 6.0–10.0s`, `4.0s` hands + robotic hand closeup)**: `eligible=True`, `faces=0 (max=0.0000)`, `max_frame_diff=2.7783`, `issues=[]`
  - **Contact Sheet**: [Ding_EEG_Fingers_2025_M1_fast_sheet.jpg](file:///tmp/r89_ep14_probe/Ding_EEG_Fingers_2025_M1_fast_sheet.jpg)
- **Key Study Facts & `R86` Viewer Payoff**:
  - **Findings**: `21` healthy able-bodied adult BCI users (`0` clinical patients, `0` surgical implants) wore a non-invasive scalp EEG cap and imagined wiggling individual fingers while keeping their real hand stationary on a desk, achieving **`80.56%`** real-time 2-finger (thumb vs pinky) and **`60.61%`** 3-finger (thumb/index/pinky) robotic hand control via deep-learning neural decoding.
  - **`R86` One-Sentence Takeaway**: *Without any brain implant, simply imagining a thumb or pinky wiggle fires distinct motor-cortex signatures strong enough to curl individual robotic fingers live.*
  - **`R75` Tag Note**: Legitimate `bci_tech` pillar episode — completely exempt from off-topic `bci_tech` tag penalties (`pillar == "bci_tech"`).
- **Visual Action (`2–4s`) & `R89` Layout Spec**:
  - **On-Screen Motion**: A real human hand rests completely still on a wooden desk beside a 5-finger black robotic hand whose individual thumb or pinky curls live as a monitor highlights the target finger and a decoding probability curve climbs to `1.0`.
  - **Best Layout**: **`Mode 2 (Dark-Navy Viewfinder + A01 Porcelain Head Locator)`** showcasing the full `1200x600` robotic hand + decoding trace *(or `Mode 1 Split-Sync` using `[0, 0, 600, 600]` hands/robot Top ↔ `Ep #31` 3D cyan `motor cortex` + `premotor cortex` Bottom)*.
- **Proposed `<= 12w` US Shorts Hook (`R87-H`) & `0.5s` Mute Test**:
  - **Hook (`11w`)**: *"No brain surgery: pure thoughts just moved individual robotic fingers live."*
  - **`0.5s` Mute Test Payoff**: Viewer sees a completely still human hand next to a robotic pinky/thumb curling autonomously on command.
- **Exact Publish Attribution (`R89` `CC BY 4.0`)**:
  > `Video credit: Adapted from Yidan Ding et al., Nature Communications (2025), Supplementary Movie 1, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) — cropped & muted (https://www.nature.com/articles/s41467-025-61064-x).`

---

## 3. Verified Runner-Up Appendix (`2` Extra `eligible=True, faces=0` Backups)

1. **Lim et al. (`2025-12-13`, Mayo Clinic, *Nature Communications*) — Awake Breathing-Driven CSF Brain Wash**:
   - **DOI & License**: [`10.1038/s41467-025-66548-4`](https://www.nature.com/articles/s41467-025-66548-4) | `CC BY 4.0` (`0` carve-outs in `MOESM2` PDF) | `N = 45` adults (mean age `58.1` trained vs `49.2` controls).
   - **Movie & Audit**: `Supplementary Movie 3` ([`41467_2025_66548_MOESM5_ESM.mp4`](https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-025-66548-4/MediaObjects/41467_2025_66548_MOESM5_ESM.mp4), `514x456 @ 5.0fps`, `32.6s`, `audio=0`) → `eligible=True`, `faces=0 (max=0.0000)`, `max_frame_diff=5.6923`, `issues=[]`.
   - **Visual**: Live real-time MRI of human lung/diaphragm expansion (`23,512 → 30,373 px²`) driving awake cerebrospinal fluid flow. Strong **`Mode 1 (Split-Sync)`** backup (Diaphragm MRI Top ↔ `Ep #31` 3D Cyan CSF Brain Wash Bottom).
   - **Contact Sheet**: [Lim_CSF_2025_M3_sheet.jpg](file:///tmp/r89_ep14_probe/Lim_CSF_2025_M3_sheet.jpg)
2. **Delahaye et al. (`2023-01-20`, EPFL, *PLOS ONE*) — Avatar Error in Your Favor (Sense of Agency)**:
   - **DOI & License**: [`10.1371/journal.pone.0266212`](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0266212) | `CC BY 4.0` (`3,256` trials; helpful avatar finger swaps noticed only `~24%` of the time).
   - **Movie & Audit**: `S1 Video` ([`journal.pone.0266212.s002`](https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0266212.s002), `t = 28.0–32.0s`, cropped `left_vr_tight [80, 260, 921, 1026]` removing EPFL corner watermark + right face camera panel) → `eligible=True`, `faces=0 (max=0.0000)`, `max_frame_diff=23.0103`, `issues=[]`.
   - **Contact Sheet**: [Delahaye_PLOSOne_2023_S1_fast_sheet.jpg](file:///tmp/r89_ep14_probe/Delahaye_PLOSOne_2023_S1_fast_sheet.jpg)
