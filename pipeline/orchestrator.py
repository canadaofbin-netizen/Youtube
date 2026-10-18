"""
Pipeline Orchestrator
Coordinates Ideation -> Scripting (12-gate QA) -> Visual Plan & Flow Prompts -> Publish with full state persistence,
and assembles the final Short from native Google Flow clips via produce_psychology_batch.assemble_final_shorts_video.
"""

from pathlib import Path
from typing import Any

from pipeline.config import (
    MIN_CLIP_SIZE_BYTES,
    MIN_CLIPS_FOR_ASSEMBLY,
)
from pipeline.flow_prompt_builder import (
    build_flow_prompts,
    load_visual_plan,
    write_flow_prompts_json,
)
from pipeline.ideation import IdeationStage
from pipeline.media_integrity import MediaIntegrityValidator
from pipeline.publish import PublishStage
from pipeline.scripting import ScriptingStage
from pipeline.storage import ProjectStorage, numeric_clip_sort_key


class PipelineOrchestrator:
    def __init__(self, project_id: str, title: str = "", pillar: str = ""):
        self.project_id = project_id
        self.storage = ProjectStorage(project_id, title=title, pillar=pillar)
        self.ideation_stage = IdeationStage(self.storage)
        self.scripting_stage = ScriptingStage(self.storage)
        self.publish_stage = PublishStage(self.storage)

    @classmethod
    def assemble_clips_if_available(
        cls,
        storage: ProjectStorage,
        strict: bool = False,
        force_rebuild: bool = False,
        topic_item: dict[str, Any] | None = None,
    ) -> Path | None:
        """
        Assembles 05_assembly/final_shorts_1080x1920.mp4 from the project's native Google Flow clips via
        produce_psychology_batch.assemble_final_shorts_video (native voice, 1.08x A/V sync, subtitles).

        - Counts clip_*.mp4 files >= MIN_CLIP_SIZE_BYTES in 03_visuals/flow_native_clips.
        - Fewer than MIN_CLIPS_FOR_ASSEMBLY clips: strict=True raises RuntimeError
          ("FATAL ERROR [Anti-Placeholder Policy]"); otherwise an existing final video (05_assembly or the
          project-root deliverable) is returned unless force_rebuild is True, else None.
        - With enough clips, an existing final video is reused unless force_rebuild is True. Assembly errors
          (invalid clips, unresolved topic, missing native speech, ffmpeg failures) always propagate.
        """
        from produce_psychology_batch import assemble_final_shorts_video

        assembly_dir = storage.get_stage_dir("05_assembly")
        final_video_path = assembly_dir / "final_shorts_1080x1920.mp4"
        clips_dir = storage.project_dir / "03_visuals" / "flow_native_clips"
        clip_candidates = (
            sorted(
                (f for f in clips_dir.glob("clip_*.mp4") if f.is_file() and f.stat().st_size >= MIN_CLIP_SIZE_BYTES),
                key=numeric_clip_sort_key,
            )
            if clips_dir.exists()
            else []
        )

        if len(clip_candidates) < MIN_CLIPS_FOR_ASSEMBLY:
            if strict:
                raise RuntimeError(
                    f"FATAL ERROR [Anti-Placeholder Policy]: {len(clip_candidates)} valid Google Flow clip(s) "
                    f"(>= {MIN_CLIP_SIZE_BYTES} bytes) found in {clips_dir}; at least {MIN_CLIPS_FOR_ASSEMBLY} "
                    "are required. Placeholder, stretched or frozen video is prohibited."
                )
            if not force_rebuild:
                if final_video_path.exists() and final_video_path.stat().st_size >= MIN_CLIP_SIZE_BYTES:
                    return final_video_path
                for root_cand in sorted(storage.project_dir.glob("final_shorts_*.mp4")):
                    if root_cand.stat().st_size >= MIN_CLIP_SIZE_BYTES:
                        return root_cand
            return None

        if not force_rebuild and final_video_path.exists() and final_video_path.stat().st_size >= MIN_CLIP_SIZE_BYTES:
            return final_video_path

        return assemble_final_shorts_video(storage, force=force_rebuild, topic_item=topic_item)

    @classmethod
    def resume_project(cls, project_id: str) -> dict[str, Any]:
        """
        Resumes or inspects an existing project: validates stages, verifies storage,
        assembles clips if available, and produces a complete status report.
        """
        orchestrator = cls(project_id)
        storage = orchestrator.storage
        manifest = storage.get_manifest()

        # Check or assemble final video
        final_video_path = cls.assemble_clips_if_available(storage)

        # If manifest already had final_video, respect it if path still exists
        if not final_video_path:
            mv = manifest.get("final_video")
            if mv:
                vp = Path(mv["path"] if isinstance(mv, dict) else mv)
                if vp.exists():
                    final_video_path = vp

        # Probe real video metrics if final_video_path exists
        probe_report = storage.load_json("05_assembly", "probe_report.json")
        if final_video_path and final_video_path.exists():
            if not probe_report:
                probe_report = MediaIntegrityValidator.probe_media(final_video_path)
                storage.save_json("05_assembly", "probe_report.json", probe_report)
            manifest["final_video"] = {
                "path": str(final_video_path),
                "size_bytes": final_video_path.stat().st_size,
                "duration": probe_report.get("duration_seconds"),
                "resolution": f"{probe_report.get('width', 1080)}x{probe_report.get('height', 1920)}",
                "source": "multi_clip_assembly",
            }
            storage._write_manifest(manifest)

        # Validate Master QA from existing script data
        script_data = storage.load_json("02_script", "script.json")
        qa_report = storage.load_json("02_script", "qa_report.json")
        if not qa_report and script_data:
            citations = storage.load_json("02_script", "fact_check.json") or []
            qa_report = orchestrator.scripting_stage.validate_qa_gates(script_data, citations)

        master_qa = {
            "all_gates_passed": qa_report.get("all_gates_passed", True) if qa_report else True,
            "gates": qa_report.get("gates", {}) if qa_report else {},
        }
        storage.save_json("05_assembly", "master_qa_report.json", master_qa)

        integrity_report = storage.verify_integrity()

        return {
            "project_id": project_id,
            "manifest": storage.get_manifest(),
            "final_video": str(final_video_path) if final_video_path else None,
            "probe_report": probe_report or {
                "width": 0, "height": 0, "fps": 0.0,
                "duration_seconds": 0.0, "file_size_bytes": 0,
            },
            "master_qa": master_qa,
            "integrity_report": integrity_report,
        }

    def run_from_blueprint(
        self,
        blueprint: dict[str, Any],
        image_source_paths: list[Path] | None = None,
        mode: str = "multi-clip",
    ) -> dict[str, Any]:
        """
        Runs Ideation -> Scripting (12-gate QA) -> Visual Plan & Flow Prompts -> Publish from a structured blueprint
        (pillar production_blueprint or topics_catalog entry). Google Flow clip generation (flow-parallel) and
        assembly (import-clips --auto-assemble) run as separate steps.
        """
        return self.run_full_pipeline(
            topic=blueprint["topic"],
            pillar=blueprint["pillar"],
            source_url=blueprint.get("source_url", "https://pubmed.ncbi.nlm.nih.gov/"),
            source_tier=blueprint.get("source_tier", 1),
            core_facts=blueprint.get("core_facts", ""),
            doi=blueprint.get("doi", "N/A"),
            paradox_statement=blueprint.get("paradox_statement", blueprint["hook_text"]),
            hook_text=blueprint["hook_text"],
            setup_text=blueprint["setup_text"],
            core_text=blueprint["core_text"],
            payoff_text=blueprint["payoff_text"],
            fact_citations=blueprint.get("fact_citations", []),
            clip_narrations=blueprint.get("clip_narrations"),
            visual_plan=blueprint.get("visual_plan"),
            image_source_paths=image_source_paths,
            title=blueprint["title"],
            hashtags=blueprint.get("hashtags", ["#Shorts", "#BCI", "#Neuroscience"]),
            narrative_style=blueprint.get("narrative_style", "chronicle_cutaway"),
            physical_metaphor=blueprint.get("physical_metaphor"),
            story_context=blueprint.get("story_context"),
        )

    def run_from_pillar(
        self,
        pillar_id_or_name: str,
        image_source_paths: list[Path] | None = None,
        mode: str = "multi-clip",
    ) -> dict[str, Any]:
        """Loads the canonical pillar blueprint, then runs Ideation -> Scripting -> Visuals -> Publish."""
        from pipeline.pillars import get_pillar
        pillar_obj = get_pillar(pillar_id_or_name)
        return self.run_from_blueprint(
            blueprint=pillar_obj.production_blueprint,
            image_source_paths=image_source_paths,
            mode=mode,
        )

    def run_full_pipeline(
        self,
        # Stage 1: Ideation
        topic: str,
        pillar: str,
        source_url: str,
        source_tier: int,
        core_facts: str,
        doi: str,
        paradox_statement: str,
        # Stage 2: Scripting
        hook_text: str,
        setup_text: str,
        core_text: str,
        payoff_text: str,
        fact_citations: list[dict[str, str]],
        # Stage 3: Visuals
        image_source_paths: list[Path] | None = None,
        # Stage 6: Publish
        title: str = "",
        hashtags: list[str] | None = None,
        # Per-clip narrations (5-10, Production Contract v4)
        clip_narrations: list[str] | None = None,
        # Visual plan (Production Contract v4)
        visual_plan: dict[str, Any] | None = None,
        # 2-Axis Historical Narrative Router Archetype
        narrative_style: str = "chronicle_cutaway",
        physical_metaphor: str | None = None,
        story_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        print(f"=== Starting Production Pipeline for Project: {self.project_id} (Style: {narrative_style}) ===")

        # Stage 1: Ideation
        print("[Stage 1/3] Running Ideation & Research Ingestion...")
        _ideation_res = self.ideation_stage.run(
            topic=topic,
            pillar=pillar,
            source_url=source_url,
            source_tier=source_tier,
            core_facts=core_facts,
            doi=doi,
            paradox_statement=paradox_statement,
            story_context=story_context,
            physical_metaphor=physical_metaphor,
        )
        print(" -> Stage 1 completed successfully.")

        # Stage 2: Scripting
        print("[Stage 2/3] Running Scripting & 12-Gate QA Loop...")
        scripting_res = self.scripting_stage.run(
            hook_text=hook_text,
            setup_text=setup_text,
            core_text=core_text,
            payoff_text=payoff_text,
            fact_citations=fact_citations,
            narrative_style=narrative_style,
            clip_narrations=clip_narrations,
        )
        print(f" -> Stage 2 completed: {scripting_res['qa_report']['word_count']} words, all gates pass: {scripting_res['qa_report']['all_gates_passed']}.")

        # Stage 2.5 / 03_visuals: Visual Plan & Canonical Google Flow Prompts
        resolved_plan = load_visual_plan(
            self.storage.project_dir,
            {
                "topic": topic,
                "core_facts": core_facts,
                "pillar": pillar,
                "story_context": story_context,
                "visual_plan": visual_plan,
            },
        )
        self.storage.save_json("03_visuals", "visual_plan.json", resolved_plan)
        narrs = scripting_res["script_data"].get("clip_narrations")
        if not narrs:
            from pipeline.generator import split_core_text
            c1, c2 = split_core_text(core_text)
            narrs = [hook_text, setup_text, c1, c2, payoff_text]
        clips = build_flow_prompts(resolved_plan, narrs)
        prompts_path = write_flow_prompts_json(self.storage.project_dir, clips)
        self.storage.record_artifact("03_visuals", "flow_all_in_one_prompts.json", prompts_path)
        print(f" -> Stage 2.5 completed: {len(clips)} Google Flow prompts written to {prompts_path.name}.")

        # Stage 3: Publish
        print("[Stage 3/3] Running Publish Packaging & Metadata Export...")
        publish_res = self.publish_stage.run(
            title=title,
            hashtags=hashtags or ["#Shorts", "#BCI", "#Neuroscience"],
            doi=doi,
            source_summary=core_facts,
            thumbnail_source_img=(
                next(iter(image_source_paths.values()), None)
                if isinstance(image_source_paths, dict)
                else (image_source_paths[0] if image_source_paths else None)
            ),
        )
        print(" -> Stage 3 completed: Metadata, checklist exported.")

        master_qa = {
            "all_gates_passed": scripting_res["qa_report"]["all_gates_passed"],
            "gates": scripting_res["qa_report"]["gates"],
        }
        self.storage.save_json("05_assembly", "master_qa_report.json", master_qa)
        print(f" -> Master QA Status: {'[ALL 12 GATES PASSED]' if master_qa['all_gates_passed'] else '[WARNING: SOME GATES FAILED]'}")

        print("[Storage Verification] Validating multi-stage artifact integrity and SHA-256 hashes...")
        integrity_report = self.storage.verify_integrity()
        print(f" -> Storage Integrity: {integrity_report['verified_artifacts']}/{integrity_report['total_artifacts']} artifacts verified intact.")

        # Check for assembled or existing video and probe report
        final_video_path = self.assemble_clips_if_available(self.storage)
        if not final_video_path:
            mv = self.storage.get_manifest().get("final_video")
            if mv:
                vp = Path(mv["path"] if isinstance(mv, dict) else mv)
                if vp.exists():
                    final_video_path = vp
            else:
                for cand in self.storage.project_dir.glob("final_shorts_*.mp4"):
                    if cand.exists() and cand.stat().st_size > 100_000:
                        final_video_path = cand
                        break

        probe_report = self.storage.load_json("05_assembly", "probe_report.json")
        if not probe_report and final_video_path and Path(final_video_path).exists():
            probe_report = MediaIntegrityValidator.probe_media(Path(final_video_path))
            self.storage.save_json("05_assembly", "probe_report.json", probe_report)

        print("=== Complete Video Production Pipeline Succeeded! ===")
        return {
            "project_id": self.project_id,
            "manifest": self.storage.get_manifest(),
            "metadata": publish_res["metadata"],
            "master_qa": master_qa,
            "integrity_report": integrity_report,
            "final_video": str(final_video_path) if final_video_path else None,
            "probe_report": probe_report or {
                "width": 0, "height": 0, "fps": 0.0,
                "duration_seconds": 0.0, "file_size_bytes": 0,
            },
        }
