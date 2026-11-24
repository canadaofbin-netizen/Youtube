# YouTube Channel Banner Global Benchmark & Redesign Architecture (`ALL ABOUT BRAIN`)

> **Deliverable**: Global 14-Channel Live Banner Benchmark + `ALL ABOUT BRAIN v2` Forensic Audit + 3 Avatar-Synced Redesign Formulas  
> **Viewport Lock**: Master `2560×1440` · Desktop Strip `2560×423` (`y=508..931`) · Mobile Safe Zone `1546×423` (`x=507..2053, y=508..931`)  
> **Target Avatar Palette Lock**: **`TED Red (#E62B1E)` / `RicksClips (#E03931)` Circle** + **`Ep #31` Alabaster Gypsum (`#DCDFE3`) & Sulcal Cyan (`#27D8FF`)** on **`Void (#040711)`**  

---

## Executive Summary (Key Findings from `n=14` Live Banners)

1. **Every Visual-First Benchmark Puts Its Subject Inside the `1546×423` Mobile Safe Zone (`x=507..2053`)**: Among channels without an established celebrity/publisher household name, `100%` place their primary visual hero, anatomical render, or graphic frame directly inside `x=507..2053` (`Veritasium`, `Institute of Human Anatomy`, `Kurzgesagt`, `TED-Ed`, `SciShow`, `AsapSCIENCE`, `Zack D. Films`, `Johnny Harris`, `RealLifeLore`). Only legacy celebrity/news names (`Huberman Lab` `Safe Edge=2.38%`, `Vox` `0.55%`) run text-only center safe zones.
2. **Our Current `ALL ABOUT BRAIN v2` Strands `100%` of Brains Outside Mobile (`x < 507`, `x > 2053`)**: [`scripts/build_brand_identity_pack.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/build_brand_identity_pack.py#L783-L805) places identical mirrored `flank_w=476` brains at `x=18..494` and `x=2066..2542`. Mobile viewers see **only bare centered text on a nearly flat `#070710` void**.
3. **Flank Brightness Attenuation Crushes Authority (`Wings Lum = 19.8`)**: Multiplying wing brain RGB by `0.48` ([`L746`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/build_brand_identity_pack.py#L746)), radial falloff (`1.35`), and alpha `0.78` ([`L760`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/build_brand_identity_pack.py#L760)) reduces wing luminance to `19.8` (`aab_v2_red`) vs `130.6` on `Institute of Human Anatomy`. Even on Desktop, the two mirrored wings look dimmed and muddy rather than bright sculpted porcelain.
4. **Zero Upload Schedules (`0/14` Channels)**: Across all `14` downloaded banners and `probe.json` `desc` strings, **`0/14` include upload cadence promises** (e.g., `"New Shorts Daily"`). Top channels lock a timeless 3-to-5-word value proposition or pure brand mark instead of brittle schedules.
5. **Complementary Avatar-to-Banner Tension Beats Monochromatic Mud**: High-performing Shorts/media pairs intentionally create crisp chromatic contrast between avatar and banner (`Zack D. Films`: `#55AEFE` avatar vs `#D31111` banner; `Vox`: `#FEF200` avatar vs `#000000` banner; `Veritasium`: `#2575E8` avatar vs deep-space grid). Syncing our banner to the finalized **`#E62B1E` Red Circle + `#DCDFE3`/`#27D8FF` Gypsum/Cyan Avatar** demands **`#040711` obsidian stage + bright `#DCDFE3`/`#27D8FF` hero inside `1546×423` + razor-sharp `#E62B1E` editorial signal accents**—replacing the maroon-dimmed `#200A10` v2 banner.

---

## 1. Visual Benchmark Sheets (Live `2560×424` Public Strips with `1546×423` Mobile Overlay)

### Group A — Global Science, Medical & Documentary Leaders (`n=9`)
![Group A: 9 Global Science, Medical & Documentary Channel Banners](../01_YouTube_CEO/bench_sheet_1_science.jpg)

### Group B — Viral 3D / Shorts Explainers (`n=5`) vs `ALL ABOUT BRAIN v2` (`Red` & `Cyan`)
![Group B: 5 Viral Shorts & Explainer Banners vs ALL ABOUT BRAIN v2](../01_YouTube_CEO/bench_sheet_2_shorts_and_aab.jpg)

---

## 2. Quantitative & Visual Teardown Across All 14 Benchmark Channels

All external strips were downloaded live (`2560×424`) into [`probe.json`](file:///tmp/banner_bench/probe.json) and measured via [`telemetry.json`](file:///tmp/banner_bench/telemetry.json). Our two `2560×1440` v2 masters were cropped to the exact YouTube desktop strip (`y=508..932`) for apples-to-apples comparison.

| # | Channel (Subs) | Avatar BG Hex | Inside `1546×423` Mobile Safe Zone (`x=507..2053`) | Desktop Wings (`0..507`, `2053..2560`) | Safe / Wings Lum | Safe / Wings Edge % | Pattern Lesson for Us |
|---:|---|---|---|---|---:|---:|---|
| 1 | **Veritasium** (`21.5M`) | `#2575E8` | `[Ve 42.0]ritasium` + `"an element of truth"` (`4w`) over lit curved horizon | Dark starfield + subtle curved grid (`no` extra icons) | `71.7 / 26.7` | `20.68% / 14.14%` | `2.7×` center-to-wing brightness gradient; timeless 4-word motto |
| 2 | **Andrew Huberman** (`8.03M`) | `#FFFFFF` | Wide-tracked cyan `"HUBERMAN LAB"` on `#000000` (`0` tagline) | Pure `#000000` void (`0.00%` edge) | `9.9 / 0.0` | `2.38% / 0.00%` | Text-only works *only* when host photo/name is famous |
| 3 | **Institute of Human Anatomy** (`8.96M`) | `#000000` | **`0` words** — bright anatomical models + right-edge 3D lateral brain (`#9E5F84`) | Left spine/ribs + right brain extension | `141.9 / 130.6` | `18.87% / 14.20%` | **Closest anatomical peer**: bright (`Lum=141.9`) 3D specimens live *inside* mobile box |
| 4 | **Kurzgesagt** (`25.8M`) | `#081D4C` | Centered glowing Earth + tiny duck + `"Quality > Quantity"` (`3` tokens) | Deep `#0A1438` cosmos (`0.00%` edge) | `32.3 / 20.5` | `2.05% / 0.00%` | Single unmistakable luminous hero centered beats cluttered twin clones |
| 5 | **Cleo Abram** (`9.02M`) | — | Giant neon-lime `"HUGE*"` + `"*if true"` on `#0867FF` blue | Floating matching lime asterisks | `123.4 / 105.7` | `6.00% / 3.70%` | Confident 2-color poster scale reads clearly at phone-screen width |
| 6 | **Vox** (`12.7M`) | `#FEF200` | Small centered white serif `"Vox"` on `#000000` | Pure `#000000` void | `3.2 / 0.0` | `0.55% / 0.00%` | Loud vibrant badge avatar (`#FEF200`) lets banner stay ultra-clean obsidian |
| 7 | **TED-Ed** (`23M`) | `#393836` | `#E62B1E`–style `"TED"` + grey `"Ed"` + `"Lessons Worth Sharing"` (`3w`) | Diverse character cast peeking inward across `507` / `2053` | `196.0 / 137.0` | `7.84% / 24.54%` | Flanking characters intentionally **peek into** mobile edges cleanly |
| 8 | **SciShow** (`8.42M`) | — | Dark microscope silhouette + green `"SciShow"` + subtle `"PRODUCED BY COMPLEXLY"` | Faint chalkboard DNA equations | `42.3 / 35.6` | `2.33% / 0.00%` | Signature science prop (`microscope`) anchored squarely inside safe zone |
| 9 | **AsapSCIENCE** (`10.8M`) | — | Asymmetric **Left Text** (`AsapSCIENCE` + `"making science make sense"`) + **Right Duo** | Clean sky-blue gradient continuation | `161.1 / 202.5` | `11.25% / 0.16%` | Classic asymmetric split keeps `100%` of subject & type safe on phones |
| 10 | **Zack D. Films** (`29.8M`) | `#55AEFE` | Tilted black `"ZACK D FILMS"` inside distressed 35mm film strip (`0` tagline) | Solid punchy `#D31111` red strip (`0.00%` edge) | `45.3 / 58.2` | `11.79% / 0.00%` | `#1` Shorts bench: cyan avatar vs `#D31111` banner creates instant scroll-stop |
| 11 | **Ricks Clips** (`204K`) | `#E03931` | Giant 3D-extruded white `"RICKS CLIPS"` filling ~65% safe zone | Seamless `#E03931` coral-red strip | `103.7 / 91.9` | `7.96% / 0.00%` | Bold white type + matching `#E03931` avatar locks instant channel unity |
| 12 | **Yellow Dude** (`247K`) | — | Brush yellow `"YELLOWDUDE"` + `"VLOG"` inside center box | Dark navy `#132033` starry night sky | `49.3 / 30.1` | `7.57% / 2.53%` | Atmospheric outer starfield gives depth without stealing center contrast |
| 13 | **Johnny Harris** (`8.02M`) | — | Movie-poster lockup `"THE HUMAN ELEMENT"` over camera/face | Moody teal mountains & faint handwritten notes | `105.7 / 87.3` | `9.89% / 2.23%` | Atmospheric documentary object (`lens/notes`) establishes cinematic pedigree |
| 14 | **RealLifeLore** (`7.93M`) | — | Shaded topographic map + high-contrast centered dark badge `"REAL LIFE LORE"` | Continuous terrain atlas across full `2560px` | `131.8 / 78.8` | `41.62% / 24.51%` | Rich domain texture (`topography`) spans wings while badge protects legibility |
| — | **`ALL ABOUT BRAIN v2` (Red)** | **`#E62B1E` target** | Bare white `"ALL ABOUT BRAIN"` + dim `2px` hairline + `"REAL NEUROSCIENCE · VERIFIED STUDIES"` | Identical darkened mirrored `#FF2525` brains (`* 0.48`) | **`43.9 / 19.8`** | **`2.90% / 2.31%`** | **Fails mobile hero test (`0%` brain inside `507..2053`) & dims wings to mud** |
| — | **`ALL ABOUT BRAIN v2` (Cyan)** | `#27D8FF` (legacy) | Same bare centered typography (`Safe Ink [652,618,1902,820]`) | Identical darkened mirrored `#27D8FF` brains (`* 0.48`) | `48.4 / 20.8` | `2.94% / 2.33%` | Better palette coherence than Red v2, still empty/cloned on wings & bare on phone |

### Five Cross-Channel Design Laws Distilled (`n=14`)
1. **Mobile Safe-Zone Self-Sufficiency (`9/14` non-celebrity rule)**: A viewer tapping `@AllAboutBrainOfficial` on YouTube Shorts mobile sees **only `1546×423`**. Your `Ep #31` 3D brain—our single strongest brand moat—*must* appear inside `x=507..2053`.
2. **Luminance Hierarchy (`Center >= Wings`, never muddy silhouettes)**: Successful dark banners keep outer wings ultra-quiet (`Vox 0.0`, `Huberman 0.0`, `Kurzgesagt 20.5`, `Veritasium 26.7`) *while keeping the mobile focal centerpiece luminous and crisp*. Conversely, brightening outer wings with a darkened specimen (`v2`: `Wings Lum=19.8`) creates grey mud.
3. **Asymmetry or Mode-Variation Beats Horizontal Mirror Cloning**: None of the `14` benchmark channels mirror-clone the exact same cut-out object symmetrically on left and right. Where flanking art exists (`TED-Ed`, `Institute of Human Anatomy`, `AsapSCIENCE`), left and right subjects are *distinct* silhouettes or anatomical modes.
4. **Maximal Readability & `0` Cadence Bloat**: `0/14` banners carry weekly schedules. Taglines, when present, stay `<= 4` crisp words (`"an element of truth"`, `"Lessons Worth Sharing"`, `"Quality > Quantity"`, `"making science make sense"`), or `0` words when the badge speaks (`Zack D.`, `Ricks Clips`, `Anatomy Lab`).
5. **Coordinated `#E62B1E` Avatar Pairing**: Because our finalized avatar uses a **`TED Red (#E62B1E)` circle behind white gypsum + `#27D8FF` cyan vessels**, filling the banner with desaturated `#FF2525` maroon glow (`#200A10`) muddies our visual identity. Instead, preserve **icy white `#DCDFE3` gypsum + `#27D8FF` electric cyan vessels** as the brain rendering lock and deploy **`#E62B1E` exclusively as sharp high-contrast editorial ink accents** (vertical bar, solid capsule pill, or `A03` right-hemisphere split).

---

## 3. Forensic Audit of `ALL ABOUT BRAIN v2` ([`build_brand_identity_pack.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/build_brand_identity_pack.py#L727-L866))

Inspected directly in [`banner_youtube_2560x1440_red.png`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/brand_assets/v2_ep31_rebrand/banner_youtube_2560x1440_red.png), [`banner_youtube_2560x1440.png`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/brand_assets/v2_ep31_rebrand/banner_youtube_2560x1440.png), and [`manifest.json`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/brand_assets/v2_ep31_rebrand/manifest.json#L66-L161):

- **Failure 1 — Strict Exclusion from Mobile (`L783–L804`)**: Both brains sit at `x=18..494` and `x=2066..2542`. Inside `SAFE_ZONE_BOX=(507, 508, 2053, 931)`, `0` pixels of 3D brain survive. Mobile Shorts visitors perceive a text-only dark box.
- **Failure 2 — Over-Attenuated Porcelain (`L746, L760`)**: Applying `arr[:, :, :3] *= 0.48` plus `alpha * radial * inward * 0.78` destroys the signature `#DCDFE3` alabaster-gypsum contrast that makes [`logo_A_ep31_gypsum_cyan.png`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/brand_assets/v2_ep31_rebrand/logo_A_ep31_gypsum_cyan.png) pop at `32px`.
- **Failure 3 — Unused Canonical Diversity (`SOURCE_ASSETS L46–L54`)**: We already possess crisp `1080×1920` renders of [`A01_mode1_translucent_head_lateral`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/brand_assets/v2_ep31_rebrand/logo_B_mode1_xray_skull.png), [`A02_mode2_whole_brain_lateral`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/brand_assets/v2_ep31_rebrand/logo_A_ep31_gypsum_cyan.png), and [`A03_mode2_whole_brain_dorsal_topdown`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/brand_assets/v2_ep31_rebrand/logo_C_split_cyan_crimson.png), yet v2 clones `A02` twice instead of creating anatomical progression.
- **Failure 4 — Generic Centered Typography Hierarchy (`L811–L852`)**: `AABCondensed-Black` (`164pt`) + `2px` hairline (`alpha=130`) + `"REAL NEUROSCIENCE · VERIFIED STUDIES"` lacks a visual container/pill or directional asymmetry—reading like a neutral starter placeholder when viewed beside `Veritasium`, `Zack D.`, and `Johnny Harris`.
- **Failure 5 — Palette Drift Against New `#E62B1E` Red + Cyan Avatar**: `banner_youtube_2560x1440_red.png` turns both wing brains crimson (`#FF2525`) over a `#200A10` reddish glow, conflicting with our finalized **vivid `#E62B1E` circle + `#27D8FF` Cyan Ep #31 Brain** avatar identity.

---

## 4. Three Concrete Banner Redesign Formulas (Synced to `#E62B1E` + `#27D8FF` Avatar)

All three proof-of-concept comps below were built read-only from our existing `1080×1920` `canonical_assets/v1/A_brain/` masters (`A01`, `A02`, `A03`) and fonts (`AABCondensed-Black.ttf`, `Inter-Variable.ttf`), verifying zero safe-zone clipping inside `1546×423`:

![ALL ABOUT BRAIN — 3 Banner Redesign Formulas Proof-of-Concept Comps](../01_YouTube_CEO/aab_redesign_3_concepts_mockup.jpg)

### Blueprint Comparison & Exact `2560×1440` Production Coordinates

| Dimension | **Concept 1 — Asymmetric Neuro-Lab Split** *(PRIMARY RECOMMENDED)* | **Concept 2 — Mode-1 Skull → Mode-2 Cortex Panorama** | **Concept 3 — Red-Bracket Dorsal Split Editorial** *(SHORTS A/B CHALLENGER)* |
|---|---|---|---|
| **Benchmark Lineage** | `AsapSCIENCE` + `Kurzgesagt` + `Veritasium` | `Institute of Human Anatomy` + `TED-Ed` | `Zack D. Films` + `Ricks Clips` + `Vox` |
| **Core Visual Hook Inside Mobile (`507..2053`)** | Left-placed bright `A02` lateral brain (`100%` visible on phone, facing right) + crisp left-aligned wordmark block | Illuminating dual-border crop: `A01` glass head peeking left edge (`x=507`) + `A02` cyan cortex peeking right edge (`x=2053`) | Bold `2-line` editorial stack (`ALL ABOUT` / `BRAIN`) on left + **`A03` dorsal split brain** (`#27D8FF` Left vs `#E62B1E` Right) on right |
| **Canvas Backdrop (`2560×1440`)** | `#040711` base + radial `#0E223E` focal glow (`cx=0.44`) + ultra-faint `#27D8FF` (`alpha=7..10`) neuro-grid wings | `#040711` base + `#0C1A30` center glow + smooth elliptical center scrim (`exp(-1.8r²)`, `#040711 @ alpha 195`) | Pure clean `#040711` obsidian void across all outer wings (`0%` distraction, max center pop) |
| **Exact Specimen Box (`2560×1440` master)** | `A02` flipped R: max `365×335` at `x=545..910`, `y=552..887` (`bright_gain=1.06`, `alpha=1.0`) | Left `A01` flipped: `560×424` @ `x=275..835` (`feather >= 0.25` alpha) · Right `A02`: `445×360` @ `x=1815..2260` | `A03` dorsal (`Cyan L` / `#E62B1E R`): `430×375` centered at `x=1715` (`x=1525..1905`, `y=532..907`) |
| **Exact Wordmark & Accent Placement** | `x=965..1980`: `#E62B1E` vertical pill (`10×36px`) + `"ONE REAL PAPER PER SHORT"` (`32pt` `#CBD5E1`) · `"ALL ABOUT BRAIN"` (`124pt` `#F8FAFC`) · `210×6px` `#27D8FF` rule + `"PEER-REVIEWED NEUROSCIENCE IN 3D"` (`30pt` `#A5D8EE`) | Centered `x=1280`: `"ALL ABOUT BRAIN"` (`122pt` `#F8FAFC`, `y≈604`) + solid `#E62B1E` capsule pill (`w=sub_w+68, h=54px`, `y=752`) with `"REAL NEUROSCIENCE · VERIFIED STUDIES"` (`29pt` white) | `x=542`: `22×312px` `#E62B1E` bar · `x=596`: `"ALL ABOUT"` (`84pt` `#CBD5E1`) + `"BRAIN"` (`182pt` `#F8FAFC`) · `y=828`: `#E62B1E` pill `"60s STUDIES"` (`24pt` white) + `"PEER-REVIEWED NEUROSCIENCE"` (`29pt` `#E2E8F0`) |
| **TV Bleed (`y < 508`, `y > 931`) Behavior** | Smooth radial `#040711` + subtle `#27D8FF` coordinate grid extends seamlessly to `0..1440` | Full `1080×1920` vertical cranium neck (`A01`) and brainstem (`A02`) can bleed softly beyond `y=508..931` on Smart TVs! | Crisp minimal `#040711` cinema letterbox on Smart TV (`Vox`/`Huberman` clean frame) |
| **Harmony Score w/ `#E62B1E` Circle Avatar** | **Best Scientific Authority**: Avatar repeats the exact `A02` cyan-gypsum brain inside `#E62B1E`, echoed by banner's `#E62B1E` bar + bright `A02` hero | **Best Showroom Storytelling**: Links Channel Banner directly to our `Mode 1` & `Mode 2` in-episode transitions (`R66/R85`) | **Best Mobile Thumb-Stop**: Literally puts both `#27D8FF` cyan and `#E62B1E` red inside one split brain right next to massive `"BRAIN"` type |

---

## 5. Actionable Next Step for `@YouTube_CEO` & `@Operator`

1. **Primary Recommendation (`Concept 1` for Default Launch, `Concept 3` as Close Shorts-Native Alternative)**:
   - Choose **Concept 1 (Asymmetric Neuro-Lab Split)** if positioning priority is **editorial trust & long-term medical/neuroscience authority** (`Veritasium × Kurzgesagt × AsapSCIENCE` tier), ensuring `100%` of the bright `Ep #31` brain and `0%`-truncated wordmark sit cleanly inside the `1546×423` mobile box.
   - Choose **Concept 3 (Red-Bracket Dorsal Split Editorial)** if optimizing strictly for **1-second mobile Shorts tap-to-subscribe punch** (`Zack D. × RicksClips × Vox`), where oversized `"BRAIN"` + `#E62B1E` signal bar + `A03` split hemispheres match the `#E62B1E` avatar seamlessly.
2. **Code Integration Spec for [`scripts/build_brand_identity_pack.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/build_brand_identity_pack.py#L764-L866)** (owned by `@Operator`):
   - Deprecate `_make_vignetted_flank_brain(..., * 0.48)` cloned wing placement outside `x=507..2053`.
   - Add `TED_RED_HEX = "#E62B1E"` / `TED_RED_RGB = (230, 43, 30)` constant alongside `EP31_CYAN` and `VOID_RGB`.
   - Retain the strict pixel-ink safe-zone assertion (`L854–L865`) covering **both `text_layer` and the primary safe-zone `brain_hero_layer`** so `manifest.json` programmatically certifies hero visibility inside `[507, 508, 2053, 931]`.
   - Keep `0` upload schedule strings and update the avatar generator (`build_logo_a` variant) to output the approved `#E62B1E` circular fill + clean `#DCDFE3`/`#27D8FF` `Ep #31` brain preview alongside the chosen banner.
