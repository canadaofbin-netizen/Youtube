# ALL ABOUT BRAIN — Master Routing Map (`AGENTS.md`)

- **Channel**: `@AllAboutBrainOfficial` (`UC4FeioYYv9X04Di07_MfZ7g`) | **Root**: `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube` (`fuse.rclone`, 0 symlinks)
- **Py**: `/home/canadaofbin/hermes-venv/bin/python -X utf8` | **Live SSOT**: [`pipeline/config.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py) · [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) (direct-read)
- **Human+AI Bibles**: [ALL_ABOUT_BRAIN_MASTER_PIPELINE.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/docs/ALL_ABOUT_BRAIN_MASTER_PIPELINE.md) · [LOCKED_ASSETS_AND_REFERENCES_BIBLE.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/docs/LOCKED_ASSETS_AND_REFERENCES_BIBLE.md)
- **Fresh-Room Charter**: [governance_roles.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/governance_roles.md) (`always_on`, `R83 v3`: `1` task/ep = `1` fresh `0k` room + ephemeral Vision Reviewer + Zero-Token `scripts/run_daily_ops_headless.sh`)
- **Active Engine Lock**: `expressive_25d_v8` (`1080x1920 @ 30fps`, `61.5–88s`), `elevenlabs_v4` Solo `Siren`, `100%` Google Flow native (`0` API): unified `Omni 1.2 Flash` (`Start+End` `3–10s`) → `Veo 3.1 Lite` (`0` cr), `Nano Banana 2.1` `x1` first-pass / `x2` retry.

## 1. 5-Gear Skills & CLI Map (`main.py <cmd>`)
| Gear | Skill | Key Commands |
|---|---|---|
| 1 Research | [youtube-research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-research/SKILL.md) | `news-radar`, `dossier init\|validate --require-v2\|audit-media` |
| 2 Script+Plan | [youtube-script](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-script/SKILL.md) | `prompt-gate --dir <d>`, `chart-preview --project <id>` |
| 3–4 Produce+QA | [youtube-produce](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-produce/SKILL.md) | `ep status\|run`, `refs`, `ref-qa`, `flow`, `assemble`, `episode-qa`, `posthoc-qa`, `qa-summary`, `thumbnail` |
| 5 Studio | [youtube-studio](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio/SKILL.md) | `multi-bundle`, `studio-upload`, `studio-pin`, `studio-link`, `studio-quiz`, `studio-watchdog` |
| 5 Analytics | [youtube-report](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-report/SKILL.md) | `studio-report` (`07:00 UTC` read-only KPI + Lock 4 alert) |
| 5 Dist QA | [qa-scheduler](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/qa-scheduler/SKILL.md) | `qa-scheduler` (`08:00 UTC` `HOLD/GO`, 5-Asset stagger, IG/TikTok) |

## 2. Atomic Rules Map (`25` Files in `.agents/rules/` — Load Only What Your Task Needs)
| Rule IDs | Owner File (`.agents/rules/`) | Task Scope |
|---|---|---|
| `R83` (`R83-1..8`) | `governance_roles.md` (`always_on`) | `Fresh-Room` (`0k` per ep/task), ephemeral Gate 1/2 VLM, `G1–G5` (`flash`/`inherit`), Zero-Token ops |
| Live Constants | `production_constants.md` (direct-read) | `pipeline/config.py` 1:1 SSOT locks & symbol index |
| `R1, R3, R15, R49-T, R73` | `content_quality_rules.md` | DOI/species accuracy, US English (`FK<=6.5`), TTS safety |
| `P1, R20` | `pillars_domain_rules.md` | 7 academic pillars & 5 everyday domains balance |
| `R44, R44-D, R44-M` | `research_dossier_v2_rules.md` | Schema v2 dossier & 4-Gate archival media audit |
| `R50, R50-B` | `knowledge_hub_asset_manifest_rules.md` | `asset_library/` manifest & `knowledge_base/` packs |
| `R8–R10, R68-D, R88-A, R89` | `metadata_contract_rules.md` | Titles, v8 2-paragraph descriptions, `CC-BY` photo/video credit, hashtags |
| `R11–R12, R19, R28–R29` | `project_storage_rules.md` | `01..06` layout, Flow room lock, FUSE, `tmp_path` tests |
| `R49, R76` | `audio_assembly_rules.md` | Solo `Siren` (`elevenlabs_v4`), `-14 LUFS`, stereo BGM/ASS |
| `R5, R14-B, R38` | `visual_prompt_spec.md` | `Omni 1.2`→`Veo Lite`, `x1/x2`, banned/audio-silence guards |
| `R56, R68, R85, R88` (Cast) | `cast_depiction_rules.md` | `R88` faceless matte-white architectural porcelain + hands POV (`B01–B15` retired) |
| `R14-A, R47` | `scene_depiction_rules.md` | Miniature lighting arc, selective color, 2-Beat prop acting |
| `R66, R68, R72, R82, R85` | `camera_choreography_rules.md` | `push-in ↔ pull-back`, `120ft` drone, `~40%` hero low-angle |
| `R21, R38, R48, R53, R85` | `brain_depiction_rules.md` | `100%` Flow `Ep #31` 6-Scale Brain (`ep31_orig_*`), color lock |
| `R44-M, R66–R67, R72-R, R85, R88-A` | `reference_depiction_rules.md` | `x1/x2` pack, `84` active Canonical (`15` `B01–B15` retired), `R88-A` PD/CC0/CC-BY `0-Face` inserts |
| `R89` | `archival_video_split_sync_rules.md` | `R89` Split-Sync & Viewfinder `0-Face` experiment videos |
| `R56–R61` | `diorama_assembly_subtitles_rules.md` | Audio-First EDL, `82pt/#FFE600/MarginV=510` ASS, 5-archetype titles |
| `R62–R64` | `episode_qa_triage_rules.md` | `DQ` triage, `DQ8` crops, `P7/P9`, 4×3 flicker, post-hoc QA |
| `R65` | `thumbnail_r65_rules.md` | `R65 v4` 50/50 in-skull cutaway thumbnail (`x2`, `TQ4/6/7/8/9`) |
| `R66, R67` (Archived) | `_archive/archival_reenactment_rules.md` | Archived `porcelain_cinematic_v7` baseline & `1:1` quarantine reenactment |
| `R70/R70-M, R71/R71-B` | `data_stamp_charts_rules.md` | `1x1` `study` Data Stamps, `max_y_frac`, anatomy labels |
| `R68, R72/R72-R` | `real_world_drone_refs_rules.md` | `expressive_25d_v8` world, `120ft` drones, Wikimedia refs |
| `R82, R86, R87-H` | `hook_pacing_beatcard_rules.md` | `118pt HookTitle`, `<=12w` hook, dual-speed pacing, Beat Cards |
| `R77–R81, R87-A` | `arrows_callouts_motion_rules.md` | `30fps` optical flow, conditional `#FF2525` arrows vs Cat K, `PatrickHand` |
| `R18-B, R25, R37, R85, R87` | `qa_gates_rules.md` | 12 Tier-1 blockers, Adversarial Gate 1/2 (`Wrong/Where/Instead`), `Mute & Hide Name` |
| `R4, R30–R36-B, R75` | `youtube_studio_operations.md` | Prime Slots, `No-Draft`, `0` playlists, `R35` pin, `R35-B` ring |
| Retired Tier-3 | `_archive/retired_rules_2026-11-18.md` | Verbatim Zero-Deletion archive (legacy frozen branches only) |
