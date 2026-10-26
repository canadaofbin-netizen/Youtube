# Rule: Optional Reference Frame & Source-to-Prompt Protocol

Parent Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Composer Spec: [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) · Code: [`pipeline/reference_image_qa.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/reference_image_qa.py), [`pipeline/scene_blueprint.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/scene_blueprint.py)

Single source of truth for **optional** reference still frames (`R51`) and reference-conditioned packets (`R52`).

## Default Mode vs Optional Reference Mode (`R51` / `R52`)
1. **Default Mode — Text-Only Schema v4 (`31_O2CmlKOk` Standard)**:
   - By default, `flow_all_in_one_prompts.json` (`Schema v4`) is pasted directly into **Google Flow (`Omni 1.1` · `9:16` · `8s/10s`)** as **text-only prompts** without requiring pre-generated reference PNGs.
   - Text-only Schema v4 allows Flow Omni 1.1's native physics and camera engine to execute full 3D camera dives (`Clip 4`), smooth orbital moves (`Clip 2, 5, 7`), and dynamic **2-Beat character acting** (`Clip 1, 2, 3, 9, 10`) without static start-frame stiffness.
2. **Optional Helper Mode — Reference Still Conditioning (`main.py ref-qa` / `main.py packets`)**:
   - When a producer explicitly chooses to attach reference PNGs (`Ingredients to Video` or `Frames to Video`) for specific clips:
     - Clear any stale video chips from the Flow prompt bar first (video chips lock duration to `8s`).
     - Upload the static `.png` reference image(s), then explicitly re-select **`Omni 1.1`**, **`9:16`**, and **`10s`**.
     - `pipeline/reference_image_qa.py` (`Q1–Q11`) and `pipeline/scene_blueprint.py` remain available as optional CLI tools (`main.py ref-qa`, `main.py packets`) whenever still-image conditioning is desired.
