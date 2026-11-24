---
name: youtube-studio
description: Gear 5 YouTube Studio CDP operations via Naver Whale - Unlisted/Scheduled staging (>=3.0h warmup), R75 playlist ban & tag purification, R35-B Related video ring, seed-protected R35 comments, and Go-Live watchdog.
---

# youtube-studio (AI-Only Spec)

SSOT: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | [youtube_studio_operations.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) (R4, R30–R36-B, R75) | Code: `pipeline/studio/`
Channel: `@AllAboutBrainOfficial` (`UC4FeioYYv9X04Di07_MfZ7g`) | Interpreter: `/home/canadaofbin/hermes-venv/bin/python -X utf8`

## 1. CLI Workflow (Run `--dry-run` before mutating new sequences)
1. `main.py studio-settings [--purge-playlists]` (KR residence + `en-US` metadata + `Education` category + `CHANNEL_CLEAN_KEYWORDS` + `0/500` empty Upload Default Tags + permanent playlist purge, R36/R75) | `main.py studio-settings --check-auto-dubbing [--dry-run]` | `main.py studio-settings --audit-v8-readiness`
2. `main.py studio-upload --project <id> --visibility scheduled|unlisted [--slot 4 --date YYYY-MM-DD]` (R4 AI disclosure, `Education` category, `8–12` clean episode tags + `#shorts`, `>= 3.0h` warmup on `scheduled` at Prime Slot 4 `19:30 ET` / Slot 2 `12:00 ET`, instant `public` banned unless `--allow-instant-public`, `<= 88.0s` on `v8`; playlists permanently disabled under R75)
3. `main.py studio-quiz --project <id> [--schedule "YYYY-MM-DD 16:00"]` (`D-Day 16:00 ET` 4-option YouTube Community Quiz `-3.5h` warmup)
4. `main.py studio-link --action apply` (R35-B `Related video` circular Public Anchor ring ONLY — honors `3.0h` pre-release & `24.0h` post-release freeze)
5. `main.py studio-pin --project <id> [--force-immediate-pin]` (R35 comment — blocked on non-`PUBLIC` Shorts and deferred until `>= 100` organic views or `>= 12.0h` post-Public with pre-document `HTMLMediaElement.prototype.play` kill so creator `AVD = 0.0s` never occurs)
6. `main.py studio-watchdog --apply` (promote elapsed Scheduled Shorts, backfill seed-eligible R35 pins & R35-B links; headless daily wrapper: `scripts/run_daily_ops_headless.sh`)

## 2. Critical CDP / Polymer Guardrails
- **Tab Isolation**: Never hijack or close non-Studio tabs (`labs.google` / `flow.google.com`, `instagram.com`, personal user tabs). Use `leased_cdp_tab(..., background=True)` + `enable_background_focus_emulation`.
- **Permanent Playlist Ban (`R75`)**: `STUDIO_PLAYLISTS_ENABLED = False`. Keep `/content/playlists` at `0` rows and remove any empty `Created playlists` shelf on `/editing/profile`.
- **Tag, Category & US Academic System Hygiene (`R75`)**: Non-`bci_tech` episodes use Category `Education` with `Academic system = United States` (`#system-select`), plus `8–12` psychology/neuroscience tags with zero `BANNED_OFF_TOPIC_TECH_TAGS` (`BCI`, `AI`, `neural interface`, `neurotech`, `Neuralink`).
- **Anchor-Outbound Related Video & Public Safety (`R35-B`, `R75`)**: `Scheduled` and `<250`-view Shorts link outbound ONLY to Public Anchors (`views >= 250`) before the `3.0h` pre-release freeze. Never mutate `Public` videos inside freeze/surge windows; `Delete forever` superseded unpublished drafts (`0` Private duplicates).
