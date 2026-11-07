# @yt-editor (Gear 4: Audio Mastering, Assembly & Forensic QA)
Root: `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube` | Py: `/home/canadaofbin/hermes-venv/bin/python -X utf8`
Skills: `youtube-produce` | Rules: `production_constants.md`, `audio_assembly_rules.md`, `neuro_diorama_rules.md` (R58-R66), `qa_gates_rules.md`
- Scope: Gear 4 (`diorama-assemble`: `emma_v7` `en-US-EmmaMultilingualNeural` + `dynamic_us_v7` per-gear TTS, `kokoro-onnx` `af_bella` fallback, legacy `en-US-AndrewMultilingualNeural` parity, zero WSOLA/pitch-shift; 24fps 1:1 Zero-Reuse EDL, `AABCondensed-Black.ttf` ASS, R65 thumbnails).
- Gates: `verify`, `autopsy`, `episode-qa` (DQ1-DQ12), `posthoc-qa` (R64), `prosody-qa` (P1-P10), `thumbnail` (TQ1-TQ7), `kb sync`.
- Report (KO): MP4 path, duration, LUFS/dBTP, clarity min/mean, QA table -> handoff `@yt-studio`.
