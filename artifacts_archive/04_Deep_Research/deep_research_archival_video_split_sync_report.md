# Archival & Supplementary Experiment Video Policy (`R89` Split-Sync Architecture)

> **Role**: `@Deep_Research` Policy, Copyright, Privacy & Technical Geometry Audit  
> **Scope**: Extending `R88-A` (`0-Face` still photographs in [`pipeline/archival_insert_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/archival_insert_builder.py)) safely to **`2–4s` muted real-experiment video clips** via **Mode 1 (`Split-Sync`)** and **Mode 2 (`Dark-Navy Rounded Viewfinder + Porcelain Region Locator`)**  
> **Non-Negotiable Stance**: **Zero Fair Use Gambling (`0%` unverified copyrighted TV/university footage)** · **Zero-Face / Zero-Minor Default** · **`100%` Gear 4 Local Compositing (`0` Google Flow uploads)**

---

## Executive Verdict

1. **Split-Screen Does NOT Legalize Copyrighted Footage**: Cropping a `2–4s` clip into a split-screen bezel disrupts *automated* linear frame matching, **but does not stop Content ID Manual Claiming or DMCA takedown strikes** (`3` strikes = channel termination). Relying on U.S. Fair Use (`17 U.S.C. § 107`) on a monetizing-track channel is an unnecessary legal gamble—especially because **YouTube explicitly prohibits registering Public Domain (`PD`) or Creative Commons (`CC`) works as exclusive Content ID references**.
2. **Most Famous 1950s–1990s Psychology Clips Are Copyright & Privacy Traps**: Iconic footage of **Milgram (*Obedience*)**, **Gazzaniga Split-Brain (*"Joe"* / Alan Alda PBS)**, **Stanford Marshmallow Test**, **Ainsworth *Strange Situation***, **Skinner Box / Harvard Film Archive**, **Patient H.M.**, and **Harlow's monkeys** are actively owned/distributed by estates, universities, or broadcasters (`Alexander Street / ProQuest`, `Chedd-Angier / PBS`, `Harvard Film Archive`, `MIT`). Route **all** of these to [`R67` (`source_reenactment.py`)](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/archival_reenactment_rules.md#L13-L14) faceless porcelain reenactment.
3. **The True Legal Goldmine Is Peer-Reviewed `CC-BY 4.0` Supplementary Movies + `17 U.S.C. § 105` US Federal Media**: Modern neuroscience (`Nature Communications`, `eLife`, `PLOS Biology/ONE`, verified `PMC Open Access` articles, and federal `NIH/NIMH/DARPA/NASA` recordings) contains thousands of crisp **`0-Face` supplementary experiment videos** (`BCI cursor typing`, `robotic arm control`, `2-photon calcium imaging`, `eye-tracking`, `fMRI BOLD overlays`) that are **`100%` copyright-immune** once per-article license tags, third-party carve-out captions, and multi-frame `YuNet` face scans pass.
4. **UI Geometry Requires Putting Both `Split-Sync` Halves Strictly Inside `Y=288..1218, X=80..908`**: Putting our reactive 3D brain in the lower `50%` (`Y=960..1920`) would bury it behind YouTube Shorts/TikTok/Reels bottom UI (`660–672px` = `Y=1248..1920`) and our locked [`MarginV=510` `82pt` yellow ASS subtitles](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py#L1317-L1325) (`Y ≈ 1235..1410`). Tightly stacking Top Video + Bottom Brain inside **`X=80..908, Y=288..1218`** eliminates `100%` of UI & subtitle collisions and preserves full `0.5s Mute Test` distinctiveness.

---

## 1. YouTube Content ID, Fair Use (`17 U.S.C. § 107`) & `Inauthentic / Reused Content` (`answer/1311392`)

### 1.1 Automated Content ID vs. Manual Claiming Reality
- **Both Audio & Video Are Fingerprinted**: YouTube Content ID maintains reference fingerprints for exclusively owned audio, visual, and audiovisual assets. Splitting or framing a video (`PiP`, border bezel, `2–4s` trim) often breaks automated pixel-grid matching, **but does not grant immunity**:
  - **Audio Risk**: Even `1–2 seconds` of documentary narration, background score, or recognizable laboratory ambient recordings can trigger automated Content ID audio matching or human claims. **Mandatory Lock**: `ffmpeg -an` (`100%` source audio removal before assembly).
  - **Manual Claiming Tool & DMCA Strikes**: Studio Content Manager grants eligible partners a **Manual Claiming Tool** that searches public videos and issues claims by **exact start/end timestamps** even when automated matching misses a split-screen segment. While YouTube's manual claiming policy forbids monetizing trivial incidental background clips, rights holders can also file formal **Copyright Takedown Requests (Strikes)** directly if automated claims do not apply.
- **Why `PD / CC0 / CC-BY 4.0` Is Structural Immunity**: Under YouTube's Content ID reference eligibility rules, partners **must hold exclusive rights** in the claimed territory; **public domain works and Creative Commons-licensed works are explicitly ineligible** to be submitted as exclusive Content ID references. Any mistaken claim against verified `PD`/`CC-BY` media has straightforward documentary grounds for immediate dispute/release.

### 1.2 Why Fair Use (`17 U.S.C. § 107`) Fails as an Automated Pipeline Strategy
Under YouTube's Fair Use guidelines and `17 U.S.C. § 107`:
1. **Only a Court Decides Fair Use**: YouTube explicitly warns that neither crediting the source, nor educational intent, nor `"Section 107 disclaimer"` creates Fair Use protection, and Content ID cannot evaluate legal fair use.
2. **Factor 3 ("Heart of the Work") Trap on `2–4s` Clips**: Borrowing a `3s` clip that constitutes the iconic payoff of a documentary (e.g., Milgram's participant pleading to stop, or Gazzaniga's patient *Joe* drawing two different shapes simultaneously) can weigh against Fair Use even at short length.
3. **Copyright Check ≠ YPP Monetization Approval**: A channel applying for or operating in the YouTube Partner Program (`YPP`) still undergoes **Reused Content** policy review regardless of whether a clip avoids copyright strikes. For a growing channel (`62` subs → YPP milestone), **Zero-Fair-Use-Gambling (`PD / CC0 / CC-BY 4.0` only)** eliminates existential strike risk cleanly.

### 1.3 July 15, 2025 `Inauthentic Content` (`answer/1311392`) & Semantic ID Originality
- On **July 15, 2025**, YouTube renamed `"Repetitious content"` to **`"Inauthentic content"`** ([YouTube Help `answer/1311392`](https://support.google.com/youtube/answer/1311392)) to target mass-produced, templated, low-human-value uploads while keeping **`"Reused content"`** enforcement unchanged (requiring significant original commentary, narrative structure, and visual transformation).
- **How `Split-Sync` Improves Both Compliance and Anti-AI-Fatigue**:
  - When a `2.0–4.0s` muted real-experiment clip (`<= 2` archival cuts combined `R88-A + R89`, `<= 10%` of total episode runtime) plays in the upper window **simultaneously coupled** to our bespoke `Ep #31` 3D brain mechanism in the lower stage, driven by original `Solo Siren` research narration:
    - **`>= 90%` of the timeline** remains 100% original 3D/2.5D diorama production (`Inauthentic Content` safe + `Reused Content` safe).
    - The split viewport itself creates a **distinct `0.5s` Mute Test signature** and unique early visual tokens (`Semantic ID`), breaking the "all-AI synthetic reel" look while keeping AI generation costs `0` for those frames (`Gear 4` local render).

---

## 2. Primary Audit: Famous Experiment Footage, Journal Supplementary Video Licenses & False-PD Traps

### 2.1 Famous Neuroscience & Psychology Footage — Copyright & Privacy Clearance Table

| Experiment / Subject | Actual Rights Holder / Custodian | Legal / Privacy Status | Required Pipeline Action |
|---|---|---|---|
| **Stanley Milgram *Obedience* (1962)** | Copyright held by Stanley Milgram, renewed by **Alexandra Milgram**; academic streaming/distribution via **Alexander Street (ProQuest)** & **Penn State Media Sales** | 🔴 **COPYRIGHTED + Identifiable Adult Faces** | **Permanent Direct-Video Ban.** Route to `R67` porcelain reenactment (`0-Face` shock generator console). |
| **Gazzaniga Split-Brain (*"Joe"* / Alan Alda / *W.J.*)** | *Scientific American Frontiers* (*"Joe"*) produced by **Chedd-Angier Production Co. / PBS**; 1960s Caltech *W.J.* reels restricted institutional/unpublished (`17 U.S.C. § 303`) | 🔴 **COPYRIGHTED + Clinical Patient** | **Permanent Direct-Video Ban.** Route to `R67` or modern `CC-BY 4.0` `0-Face` corpus callosotomy DTI/cursor data. |
| **Stanford Marshmallow Test (Mischel)** | Mischel estate / Stanford / commercial broadcasters (`CBS`, Zimbardo compilations) | 🔴 **COPYRIGHTED + Minors (`< 18`)** | **Permanent Direct-Video Ban.** Triple hazard (copyright + `answer/2801999` child safety + lack of parent CC release). Route to `R67`. |
| **Ainsworth *Strange Situation*** | Johns Hopkins / UVA academic distribution (e.g., NYU Film Library / APA-style educational licensing) | 🔴 **COPYRIGHTED + Infants/Toddlers** | **Permanent Direct-Video Ban.** Route to `R67` faceless porcelain child/caregiver silhouettes. |
| **B.F. Skinner *Pigeons / Skinner Box*** | **B.F. Skinner Foundation** / **Harvard Film Archive** (*B.F. Skinner Collection*) — frequently mislabeled `"Public Domain"` on Internet Archive | 🔴 **COPYRIGHTED TRAP** | **Ban unless** strictly proven `17 U.S.C. § 105` WWII U.S. military (*Project Pigeon*) official National Archives federal film record. |
| **Patient H.M. (Henry Molaison)** | MIT / Corkin clinical archives (post-1953 testing tapes) | 🔴 **COPYRIGHTED + Clinical Privacy / HIPAA** | **Permanent Direct-Video Ban.** Use `0-Face` `CC-BY` MRI hippocampus schematic or `R67` porcelain. |
| **Harry Harlow Rhesus Monkey Studies** | UW-Madison archives & commercial psychology compilations | 🔴 **COPYRIGHTED + Animal Distress Ad Risk** | **Permanent Direct-Video Ban.** Avoid copyright + advertiser-friendly animal distress flags; use `R67`. |
| **Ivan Pavlov Conditioned Reflex** | Classroom staples (e.g., Coronet Films 1976 *Pavlov's Experiment*) are copyrighted | 🟡/🔴 **HIGH-TRAP** | Ban all post-1930 sound/classroom films (`1931+`). Allow *only* verified pre-1931 (`<= 1930-12-31`) silent published film with provenance receipt. |
| **Modern BCI Trials (*BrainGate*, Stanford, UCSF)** | Broadcaster/PR clips (`60 Minutes`, Stanford News YouTube) = `All Rights Reserved` | 🟡 **SPLIT STATUS** | 🔴 Ban TV/PR reposts; 🟢 **GOLDMINE** for **peer-reviewed `CC-BY 4.0` Supplementary Movies** stripped strictly to **`0-Face`** cursor typing / robotic arm / spike rasters! |

---

### 2.2 Journal Supplementary Video License Audit (`Addendum #1`)

Publishing a supplementary movie in an open-access journal does **not** automatically make every file safe for commercial Shorts cropping. Mandatory license checks differ sharply by publisher:

| Journal / Repository | Default Article License | Supplementary Video Carve-Out & Reuse Trap | Pipeline Verification Rule |
|---|---|---|---|
| **`PLOS Biology` / `PLOS ONE`** | 🟢 **Strict `CC BY 4.0`** | **Safest Tier**: PLOS explicitly bans third-party stock/non-open footage inside supporting information unless written `CC BY 4.0` permission was obtained. | Allow after confirming zero identifiable faces (`YuNet`) and no third-party exclusion note in legend. |
| **`eLife`** | 🟢 **`CC BY 4.0`** (or `CC0` for US Gov authors) | Very clean open science mandate; verify legend does not cite third-party restricted video. | Allow after article JSON/HTML `license == CC-BY-4.0` + caption audit + `0-Face` scan. |
| **`Nature Communications` (`Springer Nature`)** | 🟡 **`CC BY 4.0` (WITH Exclusion Clause)** | **Per-Video Carve-Out Trap**: Springer Nature explicitly permits third-party media or identifiable clinical patient videos to be **excluded from the `CC BY` license** inside the caption or `Rights and permissions` note. | **Mandatory automated text check**: Reject if `Rights and permissions`, `supplementary movie` legend, or XML `<license>` contains `"excluded from"`, `"third party"`, `"permission"`, or `"All rights reserved"`. |
| **`Science Advances` (`AAAS`)** | 🔴/🟡 **`CC BY` vs `CC BY-NC` Choice** | Authors frequently select **`CC BY-NC`** (Non-Commercial) to avoid higher APCs or satisfy institution prefs. | **Block by default unless** exact article metadata confirms **`CC BY 4.0`** (reject all `CC BY-NC`). |
| **`PNAS`** | 🔴/🟡 **`CC BY-NC-ND` Default Trap!** | **Double Violation**: Delayed OA (6 months) and many Immediate OA papers default to **`CC BY-NC-ND`** (forbids *both* YouTube ad monetization `NC` *and* cropping/Split-Sync compositing `ND`!). | **Permanent Reject for `CC BY-NC-ND`.** Only allow when article explicitly declares `CC BY 4.0`. |
| **`PMC Open Access Subset`** | 🟡 **Mixed (`CC BY`, `CC BY-NC`, `NO-DERIV`, `Author Manuscript`)** | `"Free in PMC"` ≠ Open Access Subset! Accepted Author Manuscripts in PMC are often `All Rights Reserved`. | Query PMC OA Web Service / JATS XML `<license license-type="open-access">` -> allow **only** `cc by` (`>= 3.0`) or `cc0`. |
| **`NIH / NIMH / DARPA / NASA` (`17 U.S.C. § 105`)** | 🟢 **U.S. Public Domain** | **Grant-Funded Trap**: `17 U.S.C. § 105` covers works by **U.S. federal employees** on official duty—**NOT university labs funded by NIH/DARPA grants**! | Verify creator agency affiliation (`NIH intramural`, `NIMH`, `DARPA`, `NARA`) rather than grant acknowledgment text alone. |

#### Exact `CC BY 4.0 Section 3(a)` Attribution + Modification Rule ("DOI Only" Fails Legal Compliance)
Under [**CC BY 4.0 Section 3(a)(1)–(2)**](https://creativecommons.org/licenses/by/4.0/legalcode):
- Simply writing `DOI: 10.xxxx/...` omits required creator identification, license title + URI, and modification notice.
- Because Split-Sync **crops, scales, mutes (`-an`), and frames** the supplementary movie alongside our 3D brain, **`§ 3(a)(1)(B)`** explicitly requires indicating that changes were made:
  - **On-Screen Pill (`Gear 4`)**: `Source: <Lead Author> et al. (<Year>) · CC BY 4.0 (cropped, muted)`
  - **Description Line (`pipeline/publish.py`)**: `Video credit: Adapted from <Lead Author> et al., <Journal> (<Year>), <Supp. Movie ID>, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) — cropped & muted (<Article URL>).`

---

### 2.3 Classic Archive "False Public Domain" Traps (`Addendum #2`)
1. **"No TV Logo" ≠ Public Domain**: Under **`17 U.S.C. § 102` and `§ 302–303`**, raw unbroadcast 16mm university lab films (Caltech, Yale, Harvard, Stanford, UW-Madison) filmed between 1931 and 2026 are automatically protected by copyright even if they lack watermarks, TV network bugs, or `©` notices (works unpublished before 1978 remain protected up to 120 years from creation).
2. **Internet Archive Self-Tagging Trap**: Any user uploading a VHS rip of Milgram, Skinner, or a 1970s documentary to `archive.org` can manually pick `Public Domain Mark 1.0` in the upload dropdown. That tag has **zero legal weight** without verified `Prelinger Archives` / `National Archives (NARA)` / pre-1931 (`<= 1930-12-31`) / `17 U.S.C. § 105` federal-agency provenance.
3. **Rule**: Never rely on `"no logo"` or user-assigned `archive.org` / YouTube `"Creative Commons"` tags (re-upload laundering is rampant on YouTube). Always trace to **primary institutional origin + written license record**.

---

## 3. Human Subjects, Clinical Patients, Minors & HIPAA (`45 CFR § 164.514`) in Video

- **CC BY Licenses Do NOT Grant Publicity or Privacy Rights**: [**CC BY 4.0 Section 2(b)(1)**](https://creativecommons.org/licenses/by/4.0/legalcode) explicitly states that **publicity rights, privacy rights, and moral/personality rights are NOT licensed** under CC BY (unless held by the licensor and waived solely to exercise copyright).
- **Clinical Trial Videos & HIPAA Safe Harbor (`45 CFR § 164.514`)**: Under `45 CFR § 164.514(b)(2)(i)(Q)`, **"full-face photographs and any comparable images"** (including identifiable video/voice of clinical patients) are Protected Health Information (`PHI`) that **cannot pass HIPAA Safe Harbor de-identification**. Journals like *Springer Nature* and *PLOS* require explicit signed Patient Consent for open-access global digital publication—yet **many journals still carve out identifiable patient clips from CC-BY (`excluded from CC-BY`), and patients retain YouTube Privacy Complaint rights ([`answer/2801895`](https://support.google.com/youtube/answer/2801895))** if distressed by commercial Short virality.
- **Minors (`< 18`) Strict Lock ([`answer/2801999`](https://support.google.com/youtube/answer/2801999))**: Minors cannot grant independent commercial publicity consent, and YouTube Child Safety enforces harsher takedowns on footage featuring children without documented verifiable guardian clearance.

### Therefore — Clear 3-Way Privacy Boundary for Video (`R89`):
1. **🟢 `0-Face` Real Experiment Video (Recommended Default)**: Hands mirror-drawing, robotic arm grasping, BCI cursor typing on a screen, mouse/rodent apparatus (`non-distress`), `2-photon` microscopy, eye-tracking gaze overlay, `fMRI`/`EEG` monitor recordings. Automated multi-frame **`YuNet` face detector (`score_threshold=0.42`) across sampled frames (`5 fps`) MUST return `0` faces**.
2. **🔴 Identifiable Living Clinical Patients, Faces & All Minors (`< 18`)**: **Permanently Banned from Direct Video Insert**—even inside `CC-BY 4.0` clinical papers! If a `CC-BY 4.0` paper (*BrainGate*, aphasia trial) has a video showing both a patient's face and their BCI screen/hands, **either crop strictly to the `0-Face` monitor/hand region** (with `CC BY 4.0` modification notice + multi-frame `YuNet = 0`) OR route to `R67` faceless porcelain.
3. **🟡 Pre-1931 (`<= 1930-12-31`) Non-Graphic `PD` Historical Film Exception**: Allowed *only* with verified publication date `< 1931`, non-minor, non-graphic archival subject (mirrors our `R88-A` rule in [`archival_insert_builder.py:8-9`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/archival_insert_builder.py#L8-L9)).

---

## 4. `1080×1920` UI Geometry & Pipeline Integration (Mode 1 `Split-Sync` vs Mode 2 `Viewfinder`)

Measured directly against [`pipeline/config.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py#L973-L1325), [`pipeline/dynamic_episode_qa.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/dynamic_episode_qa.py#L1036-L1072), and cross-platform vertical video UI overlays:
- **Platform Dead Zones (`1080×1920`)**:
  - **Top Dead Zone**: YouTube Shorts `288px` (`Y=0..288`), TikTok `240–280px`, IG Reels `269px`.
  - **Right Icon Stack**: YouTube Shorts `192px` (`X=888..1080`), TikTok `120–180px`, matching **`config.UNIVERSAL_SAFE_X_RIGHT_PX = 910`** ([`L974`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py#L974)).
  - **Bottom UI + ASS Subtitles**: YouTube Shorts & Reels bottom chrome covers bottom `672px` (`Y=1248..1920`; TikTok `660px`), and our locked `v8` ASS subtitles (`82pt` `AABCondensed-Black`, `MarginV=510`, `MarginL=80`, `MarginR=165`, [`L1317-1325`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py#L1317-L1325)) occupy **`Y ≈ 1235..1410, X = 80..915`**.
  - **Cut 1 Hook Exclusion**: Cut 1 (`0.00–2.20s`) carries `118pt HookTitle` at `MarginV=238` (`Y ≈ 238..415`, [`L1154-1163`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py#L1154-L1163)). **Therefore `R89` video inserts are forbidden on Cut 1 (`Cut >= 2`, `start_sec >= 2.20s`)**.

![R89 Archival Video Dual-Mode Blueprint (1080x1920 Safe-Zone Architecture)](../01_YouTube_CEO/r89_video_split_sync_modes_blueprint.jpg)

### Exact Pixel Specifications & `Gear 4` / `QA` Fit

| Spec Field | **Mode 1: `Split-Sync Dual-Stage`** *(User Signature Format)* | **Mode 2: `Rounded Viewfinder + Porcelain Locator`** |
|---|---|---|
| **Primary Use Case** | Simultaneous **behavior ↔ mechanism** (Top: BCI cursor / mirror-draw; Bottom: synced `Ep #31` 3D brain reacting in real time) | Micro/telemetry footage lacking obvious human reference (`2-photon` microscopy, eye-tracking heatmap, spike raster) |
| **Outer Safe Box (`1080×1920`)** | Strictly inside **`X = 80..908` (`W=828`), `Y = 288..1218` (`H=930`)** — flush with `MarginL=80`, `UNIVERSAL_SAFE_X_RIGHT_PX=910`, `MarginV=510` | Strictly inside **`X = 80..908` (`W=828`), `Y = 288..1218` (`H=930`)** |
| **Real Video Viewport** | Top Rounded Window: **`X=80..908`, `Y=288..728` (`828×440`, fits `16:9` at `780×438` cleanly, `-an`)** | Large Rounded Viewfinder: **`X=80..908`, `Y=288..1058` (`828×770`, dark-navy `#1C263B/#314262` bezel, `-an`)** |
| **3D Brain / Locator Sync** | Bottom Stage **`X=80..908`, `Y=774..1218` (`828×444`)**: synced bespoke Flow `Ep #31` clip (`A02`/`A01` cropped & centered) | Bottom-Left Corner Badge **`X=94..294`, `Y=948..1148` (`200×200`)**: `A01` matte-white porcelain head + glowing `#E62B1E`/`#27D8FF` target dot |
| **Attribution Pill Placement** | Sync Bridge **`Y=735..767`**, left-aligned `X=80`: `Source: <Author> (<Year>) · CC BY 4.0 (cropped, muted)` | Beside Badge **`X=312..896`, `Y=1084..1138`**: `Source: <Author> (<Year>) · CC BY 4.0 (cropped)` |
| **Zero-Overlap Clearance** | `828×444` brain sits cleanly above **`Y=1235`** ASS subtitles & **`Y=1248`** bottom UI (`0%` UI occlusion) | Corner badge bottom `Y=1148` leaves **`87px`** margin above `MarginV=510` ASS subtitles (`Y=1235`) |
| **`Gear 4` & `DQ` Pipeline Hooks** | Composite in `archival_insert_builder.py` (or sibling `archival_video_builder.py`) via PyAV (`libx264`, `yuv420p`, `30fps`, `0` Flow uploads) + extend [`_resolve_diorama_clip_files`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py#L1234-L1258), [`DQ6`/`DQ7`/`DQ8`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/dynamic_episode_qa.py#L2614-L2632), and [`publish.py` (`Video credit:`)](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/publish.py#L634-L690). Note `DQ8` must bypass horizontal split-seam alarms on verified `R89` cuts while adding **5fps multi-frame `YuNet` scan**. |

---

## 5. `R89` Zero-Risk Operating Spec & Routing Matrix

### 5.1 3-Tier Video Traffic Light (`R89` Governance)

| Tier | Eligible Sources | Mandatory Verification & Provenance Receipts |
|---|---|---|
| **🟢 Tier 1: Direct Allow (`direct_insert_pd_cc0`)** | 1. **`17 U.S.C. § 105` US Federal Agency Works** (intramural `NIH`, `NIMH`, `DARPA`, `NASA`, `NARA` employee productions — **never** NIH grant-funded university clips).<br>2. Verified **`CC0 1.0`** lab datasets/videos.<br>3. Pre-1931 (`<= 1930-12-31`) silent historical film with verified publication provenance.<br>*All must pass `0-Face` multi-frame `YuNet < 0.42` + `-an` mute.* | Store `video_sha256`, `rendered_clip_sha256`, `source_url`, `creator_agency`, `publication_year`, `yunet_max_face_score = 0.0`, `audio_stream_count = 0`, `flow_upload_count = 0` in `03_visuals/archival_videos_manifest.json`. Zero description credit needed. |
| **🟡 Tier 2: Conditional Allow w/ Receipt (`direct_insert_cc_by`)** | **Peer-reviewed `CC BY 4.0` / `CC BY 3.0` Supplementary Movies** from `PLOS Biology/ONE`, `eLife`, `Nature Communications`, verified `PMC OA Subset` (`<license>` XML = `CC BY`), or `Science Advances` / `PNAS` **only when per-article license explicitly = `CC BY 4.0`**.<br>*Must pass caption exclusion audit + `0-Face` crop & multi-frame `YuNet` scan.* | Require ALL Tier 1 fields PLUS: exact `doi`, `license_uri`, `author`, `supplementary_movie_id`, automated **`caption_exclusion_audit_passed = True`** (regex rejects `"excluded"`, `"third party"`, `"permission"`), **`on-screen credit pill` (`§ 3(a)` cropped/muted note)**, and **`Video credit:` line in `publish.py`**. |
| **🔴 Tier 3: Permanent Direct-Video Ban** | 1. **All `CC BY-NC`, `CC BY-ND`, `CC BY-NC-ND`, `CC BY-SA`, `All Rights Reserved`, Stock/TV/PBS/BBC/YouTube re-uploads** (`Milgram`, `Gazzaniga "Joe"`, `Skinner/Harvard`, `H.M./MIT`, `Harlow`, `Marshmallow`, `Strange Situation`).<br>2. **Any living clinical patient face, identifiable human face (`YuNet >= 0.42`), or minor (`< 18`)**.<br>3. Any user-tagged `archive.org` `"Public Domain"` upload lacking primary agency/pre-1931 provenance.<br>4. Any `"fair use"` defense claim (`classification = banned`). | Hard block in `validate_archival_videos_manifest()` & `DQ8`. Automatically route historical human scenes (`Milgram`, `Split-Brain`, `Marshmallow`, `Harlow`) to **`R67` Porcelain Reenactment**! |

### 5.2 Numeric Production Guardrails (`R88-A + R89` Combined)
- **Audio Strip**: `100%` muted (`-an`, `audio_streams = 0`, zero raw lab/documentary audio).
- **Duration & Count Ceiling**: Each `R89` clip **`2.0–4.0s`** (`R88A_CLIP_DURATION_RANGE`); combined **`R88-A (photo) + R89 (video)`** archival cuts **`<= 2` per Short**, total archival share **`<= 10%` of episode duration** (`<= 7.5s` on a `75s` Short — preserving `>= 90%` original `Ep #31` 3D/2.5D footage and `Inauthentic/Reused Content` safety).
- **Placement Guard**: **`Cut >= 2` only** (`start_sec >= 2.20s`, never overlapping `118pt HookTitle`); Mode 1 bottom brain stage **must** contribute active real-time animation synchronized cleanly inside `Y=774..1218`.
- **Natural Motion QA (`DQ7`)**: Verify actual frame delta inside the archival video viewport (`min_frame_diff >= 0.30` / non-frozen source video; reject frozen slides posing as `R89` videos).

### 5.3 When to Choose Which Format (`R89` vs `R88-A` vs `R67`)

| Narrative Need in Script | Optimal Format | Why |
|---|---|---|
| **Behavior ↔ Mechanism Causal Proof** *(BCI patient cursor typing ↔ M1 cortex firing; mirror-drawing hands ↔ cerebellum adaptation)* | **🟢 `R89 Mode 1 (Split-Sync)`** | Viewer visually connects **real-world motor/screen outcome (Top)** to our **`Ep #31` neural circuit (Bottom)** simultaneously (`0.5s Mute Test` signature!). |
| **Pure Cellular / Neural Telemetry** *(`2-photon` calcium sparks, gaze-tracking heatmap, cortical traveling wave movie)* | **🟢 `R89 Mode 2 (Viewfinder + Corner Locator)`** | Maximizes telemetry resolution inside `828×770` viewport while corner `A01` porcelain badge preserves brand continuity and spatial orientation. |
| **Famous 1931–2025 Historical / Human / Child Experiment** *(Milgram, Marshmallow, Ainsworth, Gazzaniga "Joe", Harlow, H.M.)* | **🔵 `R67` Faceless Porcelain Reenactment** (`0` direct video) | **Zero** copyright strike, **zero** `answer/2801999` minor risk, **zero** `answer/2801895` / HIPAA patient risk, `100%` Flow-native `Semantic ID` cohesion. |
| **Iconic Apparatus, Vintage Blueprint, or Pre-1931 Historical Plate** *(static `0-Face` fMRI room photo, Cajal Golgi plate, lab notebook)* | **🟡 `R88-A` Still Photo w/ `1.08x` Ken Burns** | Already shipped and SHA-256 gated in [`archival_insert_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/archival_insert_builder.py) with `<= 8%` duration share. |
