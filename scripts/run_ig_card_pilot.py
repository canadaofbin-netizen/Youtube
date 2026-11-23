"""
Run 1 test episode of English Instagram Card News (4:5 Carousel PNGs + 9:16 Reels PNGs & MP4)
using Google Flow 0-credit Nano Banana 2 backgrounds + Pillow editorial compositing.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipeline.config import CHANNEL_DIR, FLOW_DEFAULT_PROJECT_URL, FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT
from pipeline.flow_ingredients import (
    close_flow_project_client,
    generate_flow_image_batch,
    open_flow_project_client,
    wait_for_flow_ready,
)
from pipeline.instagram_card_builder import CardSlide, build_instagram_card_package
from pipeline.studio.instagram_uploader import build_instagram_reels_caption

RUN_DIR = CHANNEL_DIR / "runs" / "ig_cards_20261114_feature_interference"
BG_DIR = RUN_DIR / "backgrounds"
CANDIDATES_DIR = RUN_DIR / "flow_candidates"

SLIDE_SPECS = [
    {
        "tag": "NEW NEUROSCIENCE · NOV 2026",
        "headline": "YOUR BRAIN DOESN'T RUN OUT OF POWER WHEN MULTITASKING.",
        "body": "A new Nature Neuroscience study shows your neural channels literally bleed into each other.",
        "footer_note": "@ALLABOUTBRAIN · UCHICAGO STUDY",
        "prompt": (
            "Translucent glass human brain filled with glowing electric cyan neural threads, "
            "two luminous signal streams crossing and tangling inside the center, "
            "deep obsidian navy background, spacious dark empty negative space at top and lower third, "
            "cinematic scientific editorial 3D render, ultra clean, absolutely no text, no letters, no numbers, no watermark"
        ),
    },
    {
        "tag": "THE MYTH",
        "headline": "WE BLAME MISTAKES ON WEAK FOCUS.",
        "body": "Juggling chats, emails, and tabs feels like low willpower. Yet researchers found your errors are not random lapses.",
        "footer_note": "@ALLABOUTBRAIN · PEER-REVIEWED",
        "prompt": (
            "Minimalist dark profile silhouette of a human head surrounded by floating abstract translucent glass panes "
            "and subtle cyan and warm amber light orbs swirling in darkness, moody obsidian navy background, "
            "generous dark empty negative space in upper and lower third, editorial 3D illustration, "
            "absolutely no text, no letters, no numbers, no UI icons"
        ),
    },
    {
        "tag": "THE EXPERIMENT",
        "headline": "200+ HUMANS. SHIFTING RULES. HIDDEN CUES.",
        "body": "UChicago scientists tested over 200 people and recorded monkey V1 and parietal neurons as task rules shifted without warning.",
        "footer_note": "@ALLABOUTBRAIN · NATURE NEUROSCIENCE",
        "prompt": (
            "Abstract dark scientific visualization of optical monochrome circular wave discs hovering above luminous "
            "cyan cortical neuron columns in a dark chamber, subtle volumetric light, deep obsidian background, "
            "clean dark negative space at top and bottom third, editorial science art, "
            "absolutely no text, no letters, no numbers"
        ),
    },
    {
        "tag": "FEATURE INTERFERENCE",
        "headline": "UNCERTAINTY CAUSES NEURAL CROSSTALK.",
        "body": "When rules are clear, neuron groups stay separated. When unsure, irrelevant visual details leak in and corrupt your decision.",
        "footer_note": "@ALLABOUTBRAIN · THE MECHANISM",
        "prompt": (
            "Macro 3D scientific render of two distinct glowing neural pathways in the cortex, one crisp cyan and one warm coral, "
            "colliding and tangling into a luminous knot in the middle of the frame, deep dark obsidian void, "
            "wide dark negative space at top and lower third, ultra detailed bioluminescent axons, "
            "absolutely no text, no letters, no numbers"
        ),
    },
    {
        "tag": "PRACTICAL SHIFT",
        "headline": "LOCK ONE RULE BEFORE YOU SWITCH.",
        "body": "Remove rule ambiguity before changing tasks. A 10-second clear boundary stops irrelevant cues from bleeding over.",
        "footer_note": "@ALLABOUTBRAIN · BRAIN PROTOCOL",
        "prompt": (
            "Minimalist architectural 3D render of a single razor-sharp electric cyan light beam passing cleanly through "
            "a dark crystalline geometric prism while faint chaotic sparks remain outside, deep navy obsidian backdrop, "
            "wide dark negative space at top and lower third, sleek editorial lighting, "
            "absolutely no text, no letters, no numbers"
        ),
    },
    {
        "tag": "KEY TAKEAWAY",
        "headline": "MISTAKES HAVE STRUCTURE. PROTECT YOUR SIGNAL.",
        "body": "Save this for your next deep-work sprint and share it with someone who blames their willpower.",
        "footer_note": "Xue et al., Nat Neurosci (2026) · 10.1038/s41593-026-02430-w",
        "prompt": (
            "Luminous crystalline human brain suspended in deep obsidian space with calm, cleanly separated parallel rings "
            "of electric cyan light orbiting smoothly around it, authoritative scientific editorial finale render, "
            "spacious dark empty lower third and top margin, absolutely no text, no letters, no numbers"
        ),
    },
]


async def generate_backgrounds() -> list[Path]:
    BG_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    owner_id = "ig_card_pilot_20261114"

    # Skip Flow calls only for slides that already have a verified PNG on disk
    missing_indices = [i for i in range(len(SLIDE_SPECS)) if not (BG_DIR / f"bg_{i + 1:02d}.png").exists()]
    if not missing_indices:
        return [BG_DIR / f"bg_{i + 1:02d}.png" for i in range(len(SLIDE_SPECS))]

    client, tid = await open_flow_project_client(
        project_url=FLOW_DEFAULT_PROJECT_URL,
        owner_id=owner_id,
        allow_tab_reuse=False,
    )
    try:
        ready = await wait_for_flow_ready(client, timeout_sec=35.0)
        if not ready:
            raise RuntimeError("Google Flow editor did not become ready in time")
        seen_srcs: set[str] = set()
        for idx in missing_indices:
            spec = SLIDE_SPECS[idx]
            out_path = BG_DIR / f"bg_{idx + 1:02d}.png"
            cand_subdir = CANDIDATES_DIR / f"slide_{idx + 1:02d}"
            res = await generate_flow_image_batch(
                client=client,
                prompt=spec["prompt"],
                out_path=out_path,
                aspect="9:16",
                batch_count=FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
                seen_img_srcs=seen_srcs,
                project_dir=RUN_DIR,
                save_all_candidates_dir=cand_subdir,
            )
            print(f"[Flow slide {idx + 1}/6] ok={res.get('ok')} reason={res.get('reason', '')} out={out_path.name}", flush=True)
            if not res.get("ok") or not out_path.exists():
                raise RuntimeError(f"Flow generation failed for slide {idx + 1}: {res}")
    finally:
        await close_flow_project_client(client, tid, owner_id=owner_id)

    return [BG_DIR / f"bg_{i + 1:02d}.png" for i in range(len(SLIDE_SPECS))]


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    bg_paths = asyncio.run(generate_backgrounds())

    slides = [
        CardSlide(
            tag=spec["tag"],
            headline=spec["headline"],
            body=spec["body"],
            bg_image=bg_paths[i],
            footer_note=spec["footer_note"],
        )
        for i, spec in enumerate(SLIDE_SPECS)
    ]

    pkg = build_instagram_card_package(slides, RUN_DIR)
    caption = build_instagram_reels_caption(
        hook_question="Why does multitasking actually make you mess up — even on easy tasks?",
        mechanism_summary=(
            "New University of Chicago research in Nature Neuroscience (>200 humans + neural recordings in V1 and "
            "parietal cortex) found that multitasking mistakes aren't random attention lapses. When you're uncertain "
            "which rule applies, your brain fails to keep signals separated — irrelevant visual details bleed into "
            "relevant neural channels ('feature interference'), creating predictable errors."
        ),
        debate_question="Do you notice more silly slips when your priorities aren't clear?",
        citation_line="Xue, Markman, Chen, Cohen et al. · Nature Neuroscience 29, 2822–2834 (Nov 2026)",
        doi="10.1038/s41593-026-02430-w",
        hashtags=["#neuroscience", "#brainscience", "#multitasking", "#focus", "#cognitivepsychology"],
    )
    (RUN_DIR / "caption.txt").write_text(caption, encoding="utf-8")
    manifest = {
        "topic": "Feature interference & multitasking under task uncertainty",
        "doi": "10.1038/s41593-026-02430-w",
        "journal": "Nature Neuroscience Vol. 29 (Nov 2026)",
        "outputs": pkg,
        "caption_path": str(RUN_DIR / "caption.txt"),
    }
    (RUN_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("DONE:", json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
