# Phineas Gage (`phineas_gage_iron_rod`) — Legacy v4 (`psych_04`) vs Prompt System v5 Comparison

## 1. Executive Summary & Audit Metrics

| Metric | Legacy v4 (`psych_04_phineas_gage_frontal_lobe`) | Prompt System v5 (`shorts_v5`) |
|---|---|---|
| **Schema / Visual Mode** | Schema 4 (undeclared mode; generic clinical study room) | Schema 5 · `NEURO_BIOLOGY` (declared, dossier-backed) |
| **v5 Audit Score** | Fails v5 gate (missing iconic scene, static acting, robotic openers, digits/jargon) | **100.0 / 100.0** (`passed: true`, `issues: []`) |
| **On-Screen Brain Clips** | 6 clips (`crisis`, `pivot`, `step1`, `step2`, `step3`, `breakthrough` pull-out + glowing brain in clips 2 & 10) | **4 clips** (`crisis`, `step1`, `step2`, `step3`) — within `NEURO_BIOLOGY` cap of 4 |
| **Real-Environment Clips** | 4 clips (all stuck inside the same generic medical study room) | **6 clips** across 4 historical settings: 1848 Cavendish railroad rock cut (`S1`), 1848 Cavendish ox-cart & hotel porch (`S2`), 1849 Vermont tavern & contractor room (`S3`), 1850s Chile 6-horse stagecoach & daguerreotype studio (`S4`), Harvard Warren Anatomical Museum (`S5`) |
| **Flesch-Kincaid Grade** | ~10.8 (dense academic phrasing: *"ventromedial prefrontal cortex"*, *"dorsolateral"*, *"uninhibited"*, *"frontal inhibition"*) | **4.69** (plain everyday English: *"judgment center behind your eyes"*, *"emotional alarm"*, *"wiring"*) |
| **Non-Anatomy Jargon** | Multiple (*"lesion"*, *"ventral"*, *"inhibition"*) | **0** (`[]`) |
| **Robotic Step Openers** | 3 (`"Step one:"`, `"Step two:"`, `"Step three:"`) | **0** (`"First,"`, `"Next,"`, `"Finally,"`) |
| **TTS Safety Issues** | Digits (`1848`, `1994`) in spoken narration | **0** (all numbers and years spelled out: *"eighteen forty-eight"*, *"one tenth"*, *"six horses"*) |
| **Historical Accuracy** | Repeats outdated 1994 bilateral myth & omits Gage's recovery in Chile | Incorporates Ratiu 2004 & Van Horn 2012 unilateral left-frontal connectome findings (~11% white-matter loss) and Macmillan & Lena 2010 Chile six-horse stagecoach recovery |

---

## 2. Clip 1–3 Scene & Acting Comparison (Why Viewers Immediately Recognize the Story)

| Clip / Role | Legacy v4 (`psych_04`) Scene | Prompt System v5 (`shorts_v5`) Scene | What the Viewer Now Recognizes |
|---|---|---|---|
| **Clip 1 (`setup`)** | *"A nineteenth-century New England medical study room with a wooden examination chair, an oak writing desk and a glass display case holding an iron rod. A matte-white porcelain mannequin of a railroad foreman with a translucent frosted-glass cranium sits upright in the chair while a physician mannequin stands nearby."* | **Scene `S1` (Iconic, `real_env`)**: *"Wide establishing shot on an 1848 Vermont granite railroad cut in bright sunlight as the camera smoothly tracks forward. A matte-white porcelain railroad foreman mannequin in white shirtsleeves and a dark vest kneels over a drilled granite hole, glances back toward two workman mannequins, and tamps a long tapered iron bar down. The bar strikes an orange spark inside the rock, a white black-powder blast erupts with stone dust, and the bar shoots upward through his left cheek. The foreman mannequin jolts backward onto the ledge while the workmen flinch and drop their pry bars."* | Instead of two static mannequins sitting/standing in a generic study room while the narrator talks about a railroad blast, the viewer immediately sees **the Sept 13, 1848 Cavendish railroad rock cut**, the drilled granite hole, the distraction over his right shoulder, the spark, and the 3-foot-7-inch iron bar blasting upward. |
| **Clip 2 (`symptom`)** | *"Close-up on the railroad foreman mannequin's smooth porcelain face as he slams his hand onto the oak desk. The camera slowly orbits his head, revealing the brain through the translucent frosted-glass cranium: the lateral speech cortex glows electric cyan-blue, while the lower anterior frontal lobe fades to dim crimson-red."* | **Scene `S2` (`real_env`)**: *"Medium tracking shot along a sunlit 1848 Cavendish dirt road beside a wooden hotel porch as the camera glides beside an ox cart. The porcelain foreman mannequin in a singed shirt and head bandage grips the wooden cart rail, steps down onto the road, and walks up the porch stairs toward a physician mannequin in a dark wool coat. The spoked wooden cart wheel creaks to a stop and the physician snaps open the brass clasp of his black leather bag. The foreman mannequin touches his left cheekbone while the physician freezes with raised hands."* | Shows the #1 "no way!" historical fact from Harlow (1848): **minutes after the bar went through his skull, Gage rode upright in an ox cart, stepped out, and walked up the hotel stairs** to greet the doctor. |
| **Clip 3 (`failure`)** | *"In the same medical study room, the physician and co-worker mannequins hold out a railroad schedule ledger across the desk. The foreman mannequin rises from his chair and turns his head away abruptly."* | **Scene `S3` (`real_env`)**: *"Smooth lateral tracking shot across a sunlit 1849 Vermont tavern and contractor room with heavy oak tables. The porcelain foreman mannequin in a wool vest with a closed left eyelid slams his fist onto the oak table and shoves a wooden chair back as a boss mannequin pulls away a work ledger. A pewter mug topples and clatters across the oak tabletop, spilling amber liquid as the leather roster ledger slams shut. Two crewman mannequins recoil a step backward and fold their arms as the foreman snatches his steel rod and strides out."* | Replaces the static *"hold out a ledger / turns his head away"* acting with concrete Action-Physics (R47): a toppling pewter mug, a slamming roster ledger, the drooping left eyelid (from the severed left optic nerve), and the contractors refusing to reinstate him as foreman (*"no longer Gage"*). |

---

## 3. Narrative & Scientific Upgrades (Clips 4–10)

1. **Clip 5 (`pivot`) — The Chile Stagecoach Twist (`S4`)**:
   - **Legacy v4**: Stayed inside the brain void talking about *"a dedicated ventral circuit"*.
   - **v5**: Cuts to a dynamic low-angle tracking shot on the **1850s mountain coach road between Valparaiso and Santiago, Chile**, where Gage climbs onto the driver's box and flicks the leather reins of **six porcelain carriage horses**—debunking the textbook myth that he remained a helpless drifter forever (`Macmillan & Lena 2010`, DOI `10.1080/09602011003760527`).
2. **Clips 4, 6, 7, 8 — Brain ↔ Story Links (`R48`)**:
   - Every brain clip (`crisis`, `step1`, `step2`, `step3`) pairs one canonical `anatomy_map` structure (`ventromedial prefrontal cortex`, `amygdala`, `white-matter tract`, `prefrontal cortex`) with its everyday plain name in the same clip's narration (*"judgment center behind your eyes"*, *"emotional alarm"*, *"wiring"*, *"the front of the brain"*).
3. **Clip 9 (`breakthrough`) & Clip 10 (`conclusion`) — Harvard Warren Museum (`S5`) & 1850 Daguerreotype (`S4`)**:
   - Shows the actual skull and 110-cm tapered iron rod at **Harvard's Warren Anatomical Museum** alongside Van Horn et al.'s (2012, DOI `10.1371/journal.pone.0037454`) connectome finding (~10–11% left frontal white-matter loss), and closes on Gage's dignified 1850 daguerreotype pose (`Wilgus & Wilgus 2009`, DOI `10.1080/09647040903018402`).
