# 2.5D Character Motion & Expression Standard Lexicon (`expressive_25d_v8`)

- **SSOT JSON**: [ricks_clips_character_motion_lexicon.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/research/ricks_clips_character_motion_lexicon.json)
- **Rule Integration Target**: [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md) (`R68`, `R78-M/H/V`), [cast_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/cast_depiction_rules.md), [scene_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/scene_depiction_rules.md), [camera_choreography_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/camera_choreography_rules.md)
- **Viral Benchmark**: `https://www.youtube.com/shorts/QlDPMzGmYac` (*This Shape Saved Roller Coasters*, `@RicksClips3000` — `11,125,390` views, `195,357` likes, `63.16s`, `1080x1920 @ 30fps`)
- **Author**: `@Research` (`2026-11-15`)

---

## 0. Forensic Optical-Flow Contrast & The 3-Phase Beat Physics Law

### 0.1 Quantitative Telemetry (`QlDPMzGmYac` vs Broken `Ep #8` Baseline)
> **Unit Calibration Note (`DISOpticalFlow`)**: `forensic_motion_audit.py` measures `Subj P90` on a **`270x480` downsampled grid every 2nd frame**, subtracting the median outer `18–22%` border camera flow. Multiply `270x480` pixel velocities by **`4.0x`** for native `1080x1920` pixel coordinates.

| Metric | Viral Benchmark (`QlDPMzGmYac`, `11.12M`) | Broken `Ep #8` Human Cuts (`v2`) | Production Gate Target (`Ep #9+`) |
|---|---|---|---|
| **Hero `Subj P90` (`270x480` grid)** | **`4.99 – 7.66 px/f`** (mean `5.95`) | `0.62 – 1.83 px/f` (mean `0.95`) | **`>= 3.50 px/f`** (target `4.8 – 7.8`) |
| **Hero `Subj P90` (`1080x1920` native)** | **`19.96 – 30.64 px/f`** | `2.48 – 7.32 px/f` | **`>= 14.0 px/f`** (target `19.2 – 31.2`) |
| **Peak-to-Median `Burst Ratio`** | **`4.65x – 10.73x`** (mean `6.42x`) | `1.20x – 2.55x` (uniform drift) | **`>= 3.20x`** (snappy impulse + hold) |
| **Hero Character Height (`%` of `1920px`)** | **`45.3% – 79.2%`** | `14% – 92%` (erratic scale collapse) | **`45.0% – 80.0%`** (`T2` default `48–64%`) |
| **Eye-Level Horizon (`EyeY %` from top)** | **`35.1% – 56.8%`** | `18% – 78%` (90° top-down dives) | **`35.0% – 57.0%`** (`-6° .. +8°` pitch) |
| **Action Beat Cadence (`sec / beat`)** | **`0.51s – 1.60s`** (hero mean `1.48s`) | `5.07s – 5.27s` (static mannequin stall) | **`1.15s – 1.95s / beat`** (`<= 2.20s` pose max) |

### 0.2 The 3-Phase Beat Physics Law (`State-A -> Snappy Action -> Clean Hold`)
Every `expressive_25d_v8` human character cut MUST execute a crisp **ballistic impulse curve** rather than uniform floating drift:
1. **`Phase 1 — State-A Anticipation (0.25–0.45s)` & Start-Keyframe Mandate**:
   - `kf_XX_start.png` MUST depict **pre-action physical equilibrium (`State-A`)**: all four chair legs planted flat on the floor, framed photo held in both hands *before* placing onto the empty easel, closed leather folder at chest, or hand poised two inches from a closed doorknob/handset.
   - **NEVER** bake `State-B` climax or mid-air postures into `kf_XX_start.png` (eliminates the *Start-Frame Climax Trap* that produced `Ep #8 C01` floating tilted chairs and `C09` pre-placed portraits).
2. **`Phase 2 — Snappy Ballistic Action (0.40–0.80s)`**:
   - Drive velocity through **shoulder/elbow/torso + rigid prop displacement** (`Subj P90 >= 3.5 px/f @ 270x480`, `Burst >= 3.2x`).
   - One unambiguous physical verb chain per beat (`lifts -> sets crisply`, `pushes off -> slides back`, `grips -> snaps in half`).
3. **`Phase 3 — Clean Hold & Step-Snap Reaction (0.50–1.10s)`**:
   - Decelerate cleanly into surface/prop contact (`Clean Hold`) while executing a **1–3 frame (`0.03–0.10s`) 2D ink expression step-snap** synced to a single fast blink or `8°–14°` head tilt/nod.
   - For cuts lasting `3.4–4.6s`, chain **2 linked beats** (`Beat 1: Actor Prop Impulse` -> `Beat 2: Partner Step-Back / Secondary Prop Tap`) so no single static pose ever exceeds **`2.20s`**.

### 0.3 Truncation-Proof Prompt Assembly Order (`First-28-Words Rule`)
To prevent `hi_w` word-budget trimmers from slicing off action verbs:
- **Mandatory Slot Order**: `[1. Shot Scale + Eye-Level Pitch (4–6w)] + [2. Explicit Cast Subject + Wardrobe + 12–22w Snappy Action Clause] + [3. 2D Charcoal Ink Expression Clause] + [4. Grounded Room Props & Lighting]`.
- The **explicit subject noun + primary active verb MUST appear inside the first 28 words** of every Google Flow prompt.
- **Banned Static/Floaty Tokens**: `sits upright`, `stands calmly`, `stands still`, `waits quietly`, `freezes in place`, `drifts slowly`, `floats gently`, `lingers in silence`, `warping background depth`, `dolly zoom vertigo`.

---

## 1. `State-A -> Snappy Action -> Clean Hold` 20 Physical Action Patterns (`A01..A20`)

All `20` Google Flow English action clauses are pre-validated at **`17–19` words** (`12–22w` window), begin with an explicit character subject noun, and contain **zero** banned hardware, slow-motion, or liquid-ink tokens.

### 1.1 Clinical & Neuroscience Lab Actions (`A01–A05`)
| ID | Pattern (KR) | `State-A` (Start Keyframe PNG) | `Snappy Action` (`0.4–0.8s`) | `Clean Hold` (`State-B`) | Google Flow Self-Contained Clause (`17–19w`) |
|---|---|---|---|---|---|
| `A01` | 소품 들어 올려 탁 내려놓기 (액자·장비 세팅) | Doctor stands upright holding framed photo at chest height beside an empty tabletop easel. | Lifts frame briskly with both hands and sets it squarely onto the wooden easel ledge. | Steps half-pace back holding an open palm beside the resting portrait. | `the doctor lifts the framed photo with both hands, sets it crisply onto the easel, and steps back` (`18w`) |
| `A02` | 손가락 센서 클립 '착' 물리기 (`SCR`/생체신호) | Patient rests bare hand palm-up on exam pad while clinician holds sensor clip two inches above. | Clinician pinches clip open and snaps it snugly onto the patient's index fingertip. | Clinician pulls hands cleanly back as patient holds fingers flat on the pad. | `the clinician snaps the small sensor clip onto the patient's resting index fingertip and pulls both hands back` (`18w`) |
| `A03` | 실험 콘솔 레버 단호하게 내리기 | Researcher stands at control desk with right hand poised above an upright brass control lever. | Grips lever knob and pulls it briskly downward into the locked bottom slot. | Keeps hand resting firmly on the lowered handle as desk indicator glows. | `the researcher grips the upright control lever, pulls it briskly down into place, and holds the handle steady` (`18w`) |
| `A04` | 차트 넘겨 핵심 그래프 손가락으로 짚기 | Researcher holds wooden clipboard angled against left forearm with right thumb under top sheet. | Flips top page briskly over clip and taps flat chart line firmly with index finger. | Holds index finger planted on the chart line while tilting head toward patient. | `the researcher flips the clipboard page briskly upward, taps the flat chart line firmly, and holds finger there` (`18w`) |
| `A05` | 덮개 상자 두 손으로 들어 내부 공개하기 | Experimenter grips both side handles of a matte wooden cover resting flat on the table. | Lifts wooden cover straight up six inches in one brisk motion and sets it aside. | Both figures lean slightly forward holding gaze locked on the revealed table object. | `the experimenter lifts the wooden cover straight off the table with both hands and sets it cleanly aside` (`18w`) |

### 1.2 Everyday Domestic & Everyday Anomaly Actions (`A06–A10`)
| ID | Pattern (KR) | `State-A` (Start Keyframe PNG) | `Snappy Action` (`0.4–0.8s`) | `Clean Hold` (`State-B`) | Google Flow Self-Contained Clause (`17–19w`) |
|---|---|---|---|---|---|
| `A06` | 식탁 짚고 의자 뒤로 확 밀며 물러나기 (`C01` 교정 표준) | Young man sits level on all four chair legs with palms flat on the kitchen table edge. | Pushes firmly off table edge, sliding wooden chair briskly backward across the floor. | Freezes upright in slid-back chair gripping both knees with stiffened shoulders. | `the young man pushes off the table edge, slides his chair briskly backward, and grips both knees tightly` (`18w`) |
| `A07` | 지갑·사진첩 양손으로 확 펼쳐 보이기 (`QlDPMzGmYac` `5.5s`) | Character stands at chest-up bust framing holding a closed leather folder with both hands. | Flips leather folder wide open toward front with a crisp two-hand wrist snap. | Holds open folder steady at chest height while tilting head slightly downward. | `the young man flips the leather folder wide open with both hands at chest height and holds it steady` (`19w`) |
| `A08` | 울리는 수화기 낚아채 귀에 바싹 대기 | Character stands beside desk telephone with right hand poised two inches from resting handset. | Snatches corded handset briskly off cradle and presses it straight to ear. | Holds handset snugly at ear as shoulders drop with a warm single nod. | `the young man snatches the telephone handset off its cradle, presses it to his ear, and nods warmly` (`18w`) |
| `A09` | 방문 당겨 열고 문턱 한 걸음 들어와 멈추기 | Mother stands at closed wooden door with right hand gripping the brass doorknob. | Pulls wooden door briskly open and takes one clear step across the threshold. | Pauses squarely inside open doorway keeping one hand on the door edge. | `the mother pulls the wooden door briskly open, steps across the threshold, and pauses inside the doorway` (`17w`) |
| `A10` | 마시려던 머그컵 멈추고 테이블에 딱 내려놓기 | Man holds a ceramic mug halfway between wooden tabletop and mouth. | Lowers ceramic mug briskly straight down onto the tabletop with a firm tap. | Releases handle and leans torso slightly back facing across the table. | `the man lowers his ceramic mug briskly onto the tabletop, releases the handle, and leans slightly back` (`17w`) |

### 1.3 Interpersonal Dialogue & Conflict Actions (`A11–A15`)
| ID | Pattern (KR) | `State-A` (Start Keyframe PNG) | `Snappy Action` (`0.4–0.8s`) | `Clean Hold` (`State-B`) | Google Flow Self-Contained Clause (`17–19w`) |
|---|---|---|---|---|---|
| `A11` | 반보 물러서며 단호하게 팔짱 끼기 | Young man stands facing partner with forearms raised slightly in an open posture. | Takes a crisp half-step backward and folds both arms tightly across his chest. | Holds folded-arm silhouette firmly with chin tucked slightly inward. | `the young man takes a crisp half-step back, folds both arms tightly across his chest, and holds still` (`18w`) |
| `A12` | 정면 팔 뻗어 지목 + 상대방 반보 후퇴 (2인 연쇄) | Son and mother stand three feet apart at eye level with arms resting down. | Son raises one arm briskly pointing straight ahead while mother steps half-pace back. | Son holds extended arm level as mother presses one hand to her chest. | `the son raises one arm pointing straight ahead while his mother steps back pressing a hand to her chest` (`19w`) |
| `A13` | 양손 머리 옆에 얹으며 고개 `12°` 갸웃하기 | Patient sits facing forward with both hands resting loosely on thighs. | Raises both hands briskly to press palms lightly against sides of white head. | Tilts head twelve degrees sideways and holds that puzzled silhouette cleanly. | `the patient raises both hands to the sides of his head, tilts twelve degrees, and holds the pose` (`18w`) |
| `A14` | 상체 숙여 정밀 관찰 후 번쩍 허리 펴기 (`QlDPMzGmYac` `21.2s`) | Man stands upright beside table prop with hands resting near waist. | Leans torso briskly forward to inspect photo closely, then straightens cleanly upright. | Stands tall with squared shoulders and chin held level. | `the man leans briskly forward to inspect the photo closely, then straightens upright and holds his chin level` (`18w`) |
| `A15` | 포옹하려 다가오다 양손 제지에 멈춰 서기 | Mother steps forward with arms opening while son faces her across room. | Son raises both open palms at chest height, halting her two feet away. | Both hold the tense two-foot gap as mother lowers arms slowly. | `the mother steps forward with open arms until her son raises both palms up, halting her in place` (`18w`) |

### 1.4 Visual Metaphor & Physical Rule Demos (`A16–A20`)
| ID | Pattern (KR) | `State-A` (Start Keyframe PNG) | `Snappy Action` (`0.4–0.8s`) | `Clean Hold` (`State-B`) | Google Flow Self-Contained Clause (`17–19w`) |
|---|---|---|---|---|---|
| `A16` | 양손 나뭇가지·연필 '똑' 부러뜨리기 (`QlDPMzGmYac` `27.4s`) | Figure stands at medium shot gripping a straight dry wooden twig horizontally in both fists. | Twists both wrists sharply inward, snapping the twig cleanly into two halves. | Holds both broken halves apart at chest height in a crisp silhouette. | `the figure grips a dry wooden twig in both fists, snaps it cleanly in half, and holds both pieces` (`19w`) |
| `A17` | 해머 치켜들었다 작업대에 단번에 내리찍기 (`QlDPMzGmYac` `0.1s`) | Figure grips a wooden mallet with both hands raised poised above right shoulder. | Swings wooden mallet briskly down onto workbench block in one decisive strike. | Holds mallet head planted squarely on the block after impact. | `the figure swings the raised wooden mallet briskly down onto the block and holds it planted on impact` (`18w`) |
| `A18` | 보드 다이어그램 곡선 따라 긋고 정점 찍기 (`QlDPMzGmYac` `8.4s`) | Speaker stands beside upright board holding a wooden pointer near lower corner. | Sweeps pointer briskly up diagram arch and taps peak mark firmly. | Turns torso toward front while keeping pointer tip planted on peak. | `the speaker sweeps a wooden pointer up the board diagram, taps the peak firmly, and turns toward front` (`18w`) |
| `A19` | 양손 두 카드 중 한쪽 내리고 선택 카드 높이 들기 | Participant holds two distinct matte cards level at shoulder height in both hands. | Lowers left card briskly to waist while raising right card high beside head. | Holds raised right card steady with a crisp single nod. | `the participant lowers the left card briskly while raising the right card high beside his head and nods` (`18w`) |
| `A20` | 시험 좌석에 훌쩍 올라타 안전바 두 손으로 잡기 (`QlDPMzGmYac` `34.1s`) | Subject stands beside test seat gripping side armrest with both hands. | Steps briskly into seat, settles squarely down, and grips front bar with both hands. | Sits upright gripping bar firmly while facing straight ahead. | `the subject steps briskly into the seat, settles squarely down, and grips the front bar with both hands` (`18w`) |

---

## 2. Smudge-Free `2D Ink Step-Snap Expression` Lexicon (`12` Archetypes `E01..E12`)

### 2.1 Frame-by-Frame Discovery (`f184..f195`, `6.13s–6.50s` Proof)
Forensic `30fps` single-frame extraction on `QlDPMzGmYac` proves **why** `@RicksClips3000` never suffers black-ink smearing on white heads:
- `f184–f185` (`6.13–6.17s`): High arched brows + solid black vertical ovals + wide toothy D-grin (`E01`).
- `f186–f187` (`6.20–6.23s`): Brows snap horizontally flat in `1` frame while mouth holds steady.
- `f188–f189` (`6.27–6.30s`): Eyes close into clean horizontal ink bars `— —` (`2` frames = `0.067s` blink gate).
- `f190–f191` (`6.33–6.37s`): Eyes reopen half-lidded `┬ ┬` (`f190`) and mouth snaps in **1 single frame (`0.033s`)** to a short flat dash `-` (`E02`).
- **Core Rule**: **2D charcoal ink eyes NEVER translate, slide, or morph across stationary white vinyl skin.** Direction of attention changes ONLY via **whole-head rotation/tilt (`8°–14°`)**, and emotional polarity swaps across a **fast `1–2` frame blink or head nod** using **solid pupil-free geometric shapes** (`solid oval`, `half-lidded flat-top`, `chevron > <`, `happy arc ^ ^`, `circular ring`).

### 2.2 Strictly Banned Liquid 2D Ink Verbs (`Zero-Smear Blacklist`)
Never emit any of the following in `expressive_25d_v8` prompts:
- `"eyes shift"`, `"eyes slowly widen"`, `"pupils dart"`, `"pupils dilate"`, `"eyebrows morph"`, `"mouth slowly curves"`, `"blinks repeatedly"`, `"gaze drifts"`, `"ink slides"`, `"features morph"`.

### 2.3 The 12 Standardized `2D Ink Step-Snap` Archetypes (`E01..E12`)
| ID | Archetype (KR) | Ref `t` | Brow Ink Geometry | Eye Ink Geometry (Zero Liquid Pupil) | Mouth Ink Geometry | Head Tilt | Google Flow Self-Contained Expression Phrase (`13–18w`) |
|---|---|---|---|---|---|---|---|
| `E01` | 순수·기대 활짝 미소 | `5.65s` | High rounded arches | Solid vertical black ovals | Wide upward D-grin + white tooth band | `0°` | `bold 2D charcoal ink arched brows over solid oval eyes and a wide cheerful grin` |
| `E02` | 반눈 일자입 허탈·무감정 스냅 | `6.50s` | Flat low horizontal bars | Half-lidded flat-topped black eyes | Short straight horizontal dash `-` | `-4°` | `2D charcoal ink flat brows over half-lidded eyes and a straight deadpan line mouth` |
| `E03` | 원형 링 경악·충격 | `12.20s` | High steeply lifted arches | Crisp circular ink rings + pin-dot center | Small rounded hollow oval `o` | `+10°` | `high lifted 2D ink brows over wide circular ring eyes and a small shocked oval mouth` |
| `E04` | V자 눈썹 불신·경계 (`Imposter`) | `15.30s` | Steep inward V-slanted bars | Narrow flat-topped solid black eyes | Tight downward-tilted short line | `-8°` | `inward-angled 2D charcoal ink brows over narrow flat-topped eyes and a tight pressed mouth` |
| `E05` | 꺽쇠(`> <`) 전력 타격·집중 | `0.40s` | Compact pressed effort brows | Bold inward-pointing chevrons `> <` | Wide clenched rectangular grin | `-6°` | `tight chevron-squint 2D charcoal ink eyes with pressed brows and a braced clenched grin` |
| `E06` | 비대칭 외눈썹 + `14°` 갸웃 | `19.35s` | One high arch + one flat bar | Clean solid vertical black ovals | Small crooked off-center line | `+14°` tilt | `one raised 2D ink brow and one flat brow over solid oval eyes with a puzzled head tilt` |
| `E07` | 자신만만 한쪽 입꼬리 스머크 | `8.60s` | Sharp V-angled brows | Half-lidded solid black eyes | Asymmetric one-corner upward smirk | `+8°` turn | `sharp angled 2D ink brows over half-lidded eyes and a crisp one-sided smirk` |
| `E08` | 초승달(`^ ^`) 고개 젖힌 폭소 | `21.80s` | High buoyant arches | Bold upward-curved arcs `^ ^` | Wide open D-shaped laugh mouth | `+14°` back | `upward-curved happy arc 2D ink eyes and an open laughing mouth as head tilts back` |
| `E09` | 안도·따뜻한 음성 재회 미소 | `57.05s` | Soft relaxed gentle curves | Solid ovals + gentle upward lower lid | Clean upward U-shaped smile | `+5°` nod | `relaxed 2D charcoal ink brows over warm oval eyes and a clean gentle upward smile` |
| `E10` | 팔자(`/ \`) 걱정·긴장 정지 | `35.00s` | Inner-corners-raised `/ \` | Tall crisp vertical black ovals | Small tight horizontal pressed line | `0°` | `upward-slanted worried 2D ink brows over tall oval eyes and a tight nervous mouth` |
| `E11` | 외눈 찡그림(`< o`) 정밀 관찰 | `21.23s` | Lowered brow + arched brow | One chevron `<` + one solid oval `o` | Small concentrated corner tuck | `-10°` lean | `one chevron-squinted 2D ink eye and one open oval eye under focused angled brows` |
| `E12` | 눈 번쩍 + 턱 `10°` 유레카 깨달음 | `15.80s` | High symmetrical arches | Large crisp round-oval solid eyes | Clean open half-smile curve | `+10°` lift | `high arched 2D charcoal ink brows over bright round-oval eyes with a crisp upward chin lift` |

### 2.4 High-Retention Step-Snap Transition Pairs
- **Emotional Drop / Capgras Flatline**: `E01_hopeful_open_grin -> [1-frame blink + 4° chin drop] -> E02_deadpan_flatline_drop`
- **Uncanny Shock / Paradox Hook**: `E04_suspicious_narrow_glare -> [10° head jolt back] -> E03_hollow_ring_shock`
- **Scientific Inspection -> Breakthrough**: `E11_focused_squint_inspect -> [10° chin lift + chart tap] -> E12_eureka_spark_realization`
- **Puzzled Question -> Discovery**: `E06_puzzled_asymmetric_tilt -> [straighten head + nod] -> E12_eureka_spark_realization`
- **Visual Alienation -> Auditory Relief (Phone Twist)**: `E02_deadpan_flatline_drop -> [handset to ear + 5° warm nod] -> E09_relieved_warm_smile`

---

## 3. Quantified Camera & Character Screen-Ratio Golden Rules

### 3.1 Three Standardized Human Shot Tiers (`1080x1920` Vertical Canvas)
| Shot Tier | Episode Share | Character Height (`%` of `1920px`) | Head Sphere Diameter (`%` of `1920px`) | Eye-Level `EyeY` (`%` from Top) | Recommended Cut Duration | Primary Use Case |
|---|---|---|---|---|---|---|
| **`T1` Bust Reaction Close-Up** | `15–25%` | **`65% – 80%`** | `24% – 33%` | `34% – 42%` | `1.6s – 2.8s` | High-impact `2D Step-Snap` face switches + chest-level hand props (`A07` wallet/folder flip, `A08` phone to ear) |
| **`T2` Medium Prop Workhorse (`DEFAULT`)** | **`55–65%`** | **`48% – 64%`** | `13% – 20%` | `38% – 54%` | `2.6s – 4.2s` | Core clinical/domestic 2-beat prop actions (`A01` easel setdown, `A02` sensor clip, `A04` clipboard tap, `A06` chair slide, `A16` twig snap) |
| **`T3` Grounded Full-Body Blocking** | `15–25%` | **`38% – 48%`** | `11% – 14%` | `40% – 57%` | `2.5s – 3.8s` | Doorway entries (`A09`), 2-person confrontation (`A12`, `A15`), simulator seat entry (`A20`) with visible floor contact shadow |

### 3.2 Hard Geometry, Horizon & Pacing Locks
1. **Hero Character Height Golden Band**: **`45.0% – 80.0%`** of `1920px` (`864px – 1536px`) for `T1+T2` hero cuts; never below `38.0%` (`730px`) on any acting human shot.
2. **Eye-Level Horizon & Pitch Lock**: Keep `EyeY` inside **`35.0% – 57.0%`** from top of frame and camera pitch strictly within **`-6° .. +8°` eye-level** (`0°` default). **Ban `90°` vertical top-down dives onto indoor characters** and **ban `dolly_zoom_vertigo` / `"warping background depth"`**.
3. **Two-Character Relative Scale Lock**: When two adult characters share a medium or full shot (`A12`, `A15`), their head-sphere diameters in the start keyframe MUST match within **`0.85x – 1.15x`** (eliminates `Ep #8 C10` giant-vs-toddler perspective distortion).
4. **Beat Cadence & Single-Pose Ceiling**: Target **`1.15s – 1.95s / beat`** (`QlDPMzGmYac` hero mean `1.48s/beat`; tight prop cuts `0.51s–1.60s/beat`). Enforce a hard ceiling of **`<= 2.20s` per static pose**.

### 3.3 `QlDPMzGmYac` Hero Character Shot-by-Shot Telemetry Table
| Shot Window | Time (`s`) | Dur (`s`) | Beats | `sec/beat` | Char Height (`%`) | Head Sphere (`%`) | `EyeY` (`%`) | Camera Pitch | `Subj P90` (`270x480`) | `Burst Ratio` |
|---|---|---|---|---|---|---|---|---|---|---|
| `C01_Hammer_Lift_Strike` | `0.05–1.05` | `1.00` | `1` | `1.00s` | **`47.1%`** | `13.4%` | `40.4%` | `+5°` eye-low | `4.99 px/f` | `6.80x` |
| `C03_Wallet_Open_SmileToDeadpan` | `5.15–6.85` | `1.70` | `2` | `0.85s` | **`79.2%`** | `33.3%` | `35.1%` | `0°` bust | `5.28 px/f` | `6.82x` |
| `C04_Rival_Blueprint_Smirk` | `7.00–10.20` | `3.20` | `2` | `1.60s` | **`47.4%`** | `11.4%` | `56.8%` | `0°` med-full | `5.52 px/f` | `4.77x` |
| `C06_Stump_Grab_Hammer` | `14.60–16.20` | `1.60` | `2` | `0.80s` | **`55.7%`** | `15.3%` | `54.6%` | `0°` knee-up | `5.52 px/f` | `4.77x` |
| `C08_Rival_Telescope_Laugh` | `21.05–22.25` | `1.20` | `2` | `0.60s` | **`70.1%`** | `16.8%` | `39.9%` | `+3°` knee-up | `2.29 px/f` | `4.65x` |
| `C10_Rival_Snap_Twig` | `26.80–28.60` | `1.80` | `2` | `0.90s` | **`57.8%`** | `13.8%` | `51.0%` | `0°` medium | `2.29 px/f` | `4.65x` |
| `C12_Rival_Climb_ShowOff_Wave` | `31.70–34.05` | `2.35` | `2` | `1.18s` | **`45.3%`** | `12.0%` | `47.1%` | `0°` platform | `2.57 px/f` | `6.35x` |
| `C13_Owner_Hop_Into_Cart` | `34.10–35.12` | `1.02` | `2` | `0.51s` | **`45.8%`** | `11.5%` | `39.7%` | `0°` platform | `7.66 px/f` | `3.23x` |
