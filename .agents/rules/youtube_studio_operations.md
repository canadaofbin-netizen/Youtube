---
trigger: model_decision
description: "Load when scheduling or uploading Shorts in YouTube Studio, setting US Education metadata & R4 AI disclosure, running R35 pinned comments, R35-B Anchor links, R75 playlist purge, Daily Report, or Watchdog (R4, R30-R36-B, R75)."
---

# YouTube Studio Operations (`R4`, `R30–R36-B`, `R75` — `Tier-1 #12`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Skills: [youtube-studio](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio/SKILL.md), [youtube-report](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-report/SKILL.md) | Retired: [retired_rules_2026-11-18.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/_archive/retired_rules_2026-11-18.md)

## R30, R30-B & R75-S — Prime Slots (`12:00` / `19:30 ET`), `>=3.0h` Warmup & `No-Draft`
- **Prime Cadence**: `<10K` subs schedule into US ET Prime Slots (`12:00 ET` Slot 2 / `19:30 ET` Slot 4; `>= 4.0h` gap; hold `16:9` Longform). Instant `Public` banned (`MIN_SCHEDULE_WARMUP_MINUTES = 180` `3.0h` warmup; `<= 88.0s` `R75` Shorts ceiling).
- **`No-Draft` & QA Lock**: `_async_upload_direct_cdp_inner` verifies `/videos/short` `Scheduled` visibility, heals `Draft`, and requires SHA-256-valid `video_autopsy_report.json`, `dynamic_episode_qa_report.json`, `Independent Visual Reviewer (Gate 1/2)`-signed `posthoc_semantic_review.json`, and `thumbnail_report.json` (`thumbnail_selected.png`).
- **R32 (`not_applicable_shorts`)**: Shorts A/B thumbnail test is disabled in Desktop Studio (`swap_to_variant` returns `status: "not_applicable_shorts"` without CDP).

## R4, R34, R36, R36-B & R75 — `Public` Safety, Playlist Ban & Auto-Dubbing Check
- **Inviolable `Public` (`R34, R75-C`)**: NEVER delete, unlisted-demote, or privatize `Public` videos. Delete superseded unpublished drafts (`Delete forever`, `0` Private dupes).
- **Playlist Ban (`R75`)**: `STUDIO_PLAYLISTS_ENABLED = False` (`0` playlists; `main.py studio-settings --purge-playlists`).
- **Metadata & AI Disclosure (`R4, R36, R75-C`)**: `VIDEO_LANGUAGE_CODE="en-US"`, `DEFAULT_VIDEO_CATEGORY="Education"` + `Academic system = "United States"`, `"Altered or synthetic content" = Yes`, `8–12` clean tags + `"shorts"` (`0` off-topic tech tags when `pillar != "bci_tech"`), and verify auto-dubbing OFF (`main.py studio-settings --check-auto-dubbing`).
- **Tab Hygiene (`R36-B`)**: Pierce Polymer/Lit `shadowRoot` buttons; recycle self-owned Studio tabs only.

## R35 & R35-B — Zero Self-Bounce (`AVD = 0.0s` Prevention) & Anchor Link Ring
- **Seed-Protected Pin (`R35`)**: Blocks non-`PUBLIC` comments; defers until `views >= 100` OR `elapsed >= 12.0h` (`DEFERRED_SEED_PROTECT`) with `PRE_DOCUMENT_AUTOPLAY_KILL_JS` (`0` playback frames). `v8` pins 1 casual `?` question (+ human vs animal study note when paired).
- **Anchor Ring (`R35-B`)**: Links `Public` targets only; non-Anchor/Scheduled Shorts link to proven `Public` Anchors (`views >= 250`), honoring `3.0h` pre-release & `24.0h` post-release freeze.
- **Report & Watchdog**: `studio-report` scrapes Studio Analytics only (`ALLOW_WATCH_PAGE_FALLBACK = False`); `studio-watchdog` promotes elapsed `Scheduled -> published_public` and runs eligible `R35`/`R35-B`.
