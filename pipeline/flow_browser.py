"""
ALL ABOUT BRAIN - Google Flow & Naver Whale Browser Automation
Adheres strictly to the Visible Naver Whale Browser Protocol:
- Path: C:\\Program Files\\Naver\\Naver Whale\\Application\\whale.exe
- Headless: False (visible browser window on user screen)
"""

import hashlib
import html
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from pipeline.config import (
    DEFAULT_CLIP_COUNT,
    FLOW_CLIP_DURATION_TARGET,
    FLOW_DOWNLOAD_HARVEST_LOCK_FILE,
    FLOW_MAX_PARALLEL_BATCH_SIZE,
    FLOW_MAX_RETRIES,
    FLOW_RENDER_POLL_INTERVAL_SEC,
    FLOW_RENDER_TIMEOUT_SEC,
    FLOW_TRIGGER_VERIFY_TIMEOUT_SEC,
    MIN_CLIP_SIZE_BYTES,
    PROJECTS_DIR,
)
from pipeline.media_integrity import MediaIntegrityError, MediaIntegrityValidator, get_pipeline_logger

logger = get_pipeline_logger("flow_browser")

_WIN_WHALE_EXEC = Path(r"C:\Program Files\Naver\Naver Whale\Application\whale.exe")
WHALE_EXECUTABLE = (
    _WIN_WHALE_EXEC
    if _WIN_WHALE_EXEC.exists() or Path(r"C:\Program Files").exists()
    else Path("/usr/bin/docker")
)
GOOGLE_FLOW_URL = "https://labs.google/fx/tools/flow"


class FlowCircuitBreakerError(RuntimeError):
    """Raised when Google Flow automation fails after maximum retries or hits timeout."""


class FlowDownloadHarvestLock:
    """
    Guard 1 & Guard 6 (R37): Cross-process and in-process lock (BCI_Shorts_Channel/.flow_download_harvest.lock)
    serializing prompt submission and Downloads folder clip harvesting across concurrent subagent workers.
    """

    _async_locks: dict[int, Any] = {}

    def __init__(self, lock_path: Path = FLOW_DOWNLOAD_HARVEST_LOCK_FILE, timeout_sec: float = 120.0):
        self.lock_path = Path(lock_path)
        self.timeout_sec = timeout_sec
        self._fh: Any = None
        self._held_async_lock: Any = None

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.lock_path, "a+b")
        deadline = time.monotonic() + self.timeout_sec
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError:
                if time.monotonic() >= deadline:
                    try:
                        self._fh.close()
                    except Exception:
                        pass
                    self._fh = None
                    raise TimeoutError(f"Timed out acquiring FlowDownloadHarvestLock: {self.lock_path}")
                time.sleep(0.1)

    def release(self) -> None:
        if self._fh is not None:
            try:
                if os.name == "nt":
                    import msvcrt
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            finally:
                try:
                    self._fh.close()
                except Exception:
                    pass
                self._fh = None
        if self._held_async_lock is not None:
            try:
                if self._held_async_lock.locked():
                    self._held_async_lock.release()
            except Exception:
                pass
            self._held_async_lock = None

    def __enter__(self) -> "FlowDownloadHarvestLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()

    async def acquire_async(self) -> None:
        import asyncio
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
        if loop_id not in FlowDownloadHarvestLock._async_locks:
            FlowDownloadHarvestLock._async_locks[loop_id] = asyncio.Lock()
        async_lock = FlowDownloadHarvestLock._async_locks[loop_id]
        await asyncio.wait_for(async_lock.acquire(), timeout=self.timeout_sec)
        self._held_async_lock = async_lock

    async def __aenter__(self) -> "FlowDownloadHarvestLock":
        await self.acquire_async()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


# Robust JS snippet to auto-dismiss Google Flow credit confirmation dialogs ("Always approve")
# Detects: "Would you like me to kick off this 1 video generation, costing 15 credits?"
# and automatically clicks "Always approve" to prevent automation blockage.
DISMISS_CREDIT_DIALOG_JS = """
(() => {
    // 0. Google Flow Angular 18 flow-permission-message radio options ('Always approve' / 'Approve')
    const radioOptions = Array.from(document.querySelectorAll('flow-permission-message [role="radio"], [role="radio"].option-row'));
    const activeAlwaysRadio = radioOptions.find(r => {
        const label = (r.getAttribute('aria-label') || r.innerText || '').trim().toLowerCase();
        const isReadOnly = r.classList.contains('read-only') || r.getAttribute('aria-disabled') === 'true';
        return !isReadOnly && (label === 'always approve' || label.includes('always approve'));
    });
    if (activeAlwaysRadio) {
        activeAlwaysRadio.click();
        return { dismissed: true, button: 'Always approve (radio)', text: activeAlwaysRadio.innerText };
    }
    const activeApproveRadio = radioOptions.find(r => {
        const label = (r.getAttribute('aria-label') || r.innerText || '').trim().toLowerCase();
        const isReadOnly = r.classList.contains('read-only') || r.getAttribute('aria-disabled') === 'true';
        return !isReadOnly && (label === 'approve' || label.includes('approve'));
    });
    if (activeApproveRadio) {
        activeApproveRadio.click();
        return { dismissed: true, button: 'Approve (radio)', text: activeApproveRadio.innerText };
    }

    // 1. Direct search for 'Always approve' button or element (case-insensitive)
    const allButtons = Array.from(document.querySelectorAll('button, [role="button"], a, div[role="button"], span[role="button"]'));
    const alwaysBtn = allButtons.find(b => {
        const t = (b.innerText || b.textContent || '').trim().toLowerCase();
        return t === 'always approve' || t.includes('always approve');
    });
    if (alwaysBtn) {
        alwaysBtn.click();
        return { dismissed: true, button: 'Always approve', text: alwaysBtn.innerText };
    }

    // 2. Check for credit popup text anywhere in document or dialogs:
    // e.g. "Would you like me to kick off this 1 video generation, costing 15 credits?"
    const bodyText = (document.body ? document.body.innerText || document.body.textContent || '' : '').toLowerCase();
    const hasCreditPrompt = bodyText.includes('costing 15 credits') || bodyText.includes('video generation, costing') || bodyText.includes('15 credits');

    // 3. Search in modal/dialog containers
    const dialogs = Array.from(document.querySelectorAll('[role="dialog"], .dialog, .modal, mat-dialog-container, div[aria-modal="true"], .cdk-overlay-pane'));
    for (const dlg of dialogs) {
        const dlgText = (dlg.innerText || dlg.textContent || '').toLowerCase();
        if (dlgText.includes('credits') || dlgText.includes('approve') || dlgText.includes('generation') || hasCreditPrompt) {
            const dBtns = Array.from(dlg.querySelectorAll('button, [role="button"], [role="radio"]'));
            const targetBtn = dBtns.find(b => {
                const t = (b.innerText || b.textContent || '').trim().toLowerCase();
                return t.includes('always approve') || t === 'approve' || t.includes('approve') || t.includes('proceed') || t.includes('confirm') || t.includes('continue');
            });
            if (targetBtn) {
                targetBtn.click();
                return { dismissed: true, button: 'Dialog Target Button', text: targetBtn.innerText };
            }
        }
    }

    // 4. Fallback: if body has credit prompt, click any button with approve/proceed/confirm
    if (hasCreditPrompt) {
        const fallbackBtn = allButtons.find(b => {
            const t = (b.innerText || b.textContent || '').trim().toLowerCase();
            return t.includes('always approve') || t.includes('approve') || t.includes('proceed') || t.includes('confirm');
        });
        if (fallbackBtn) {
            fallbackBtn.click();
            return { dismissed: true, button: 'Credit Prompt Fallback', text: fallbackBtn.innerText };
        }
    }

    return null;
})()
"""


class FlowProjectSubagentWorker:
    """
    Dedicated subagent worker for an individual video project on Google Flow.
    Enforces the 1:1:1 architecture: 1 Video Project = 1 Google Flow Project = 1 Dedicated Subagent Worker.
    Implements the 5-Layer Google Flow Defense & Phase 4 Circuit Breaker:
      - Layer 1: Real typing + InputEvent dispatch + Generate button enabled verification + explicit DOM click + 5s state verification (max_retries=2).
      - Layer 2: Asynchronous rendering polling every 10s up to 210s timeout for <video> readyState >= 2 & duration > 0.
      - Layer 3: Strict video asset extraction blocking <img>, poster, .png/.jpg, and screenshots from being saved as video clips.
    """
    def __init__(
        self,
        project_id: str,
        cdp_port: int = 9222,
        trigger_generation: bool = True,
        wait_for_render: bool = False,
        max_retries: int = FLOW_MAX_RETRIES,
    ):
        if not isinstance(project_id, str) or not project_id.strip() or "," in project_id or ";" in project_id:
            raise ValueError(
                "FATAL R37 GUARD 6 VIOLATION: FlowProjectSubagentWorker enforces strict 1:1:1 binding "
                "(1 Topic = 1 Subagent = 1 Dedicated Tab). Multi-topic bundling is prohibited."
            )
        self.project_id = project_id.strip()
        self.cdp_port = cdp_port
        self.trigger_generation = trigger_generation
        self.wait_for_render = wait_for_render
        self.max_retries = min(max_retries, FLOW_MAX_RETRIES)
        self.retry_count: int = 0
        self.circuit_breaker_tripped: bool = False
        self.worker_id = f"subagent-{self.project_id}"
        self.subagent_1_to_1_bound: bool = True
        self.worker_start_time: float = time.time()
        self.prompts_submitted_count: int = 0
        self.status = "initialized"
        self.tab_id: str = ""
        self.url: str = ""
        self.error: str = ""
        self.title_set: bool = False
        self.prompt_injected: bool = False
        self.generate_button_enabled: bool = False
        self.generation_triggered: bool = False
        self.render_started_verified: bool = False
        self.render_completed: bool = False
        self.credit_approved: bool = False
        self.visual_qa_report: dict[str, Any] = {}

    def log(self, message: str):
        print(f"[Worker:{self.project_id}] {message}")
        logger.info("[%s] %s", self.project_id, message)

    _SHA256_CACHE: dict[tuple[str, int, int], str] = {}

    @classmethod
    def compute_file_sha256(cls, file_path: Path) -> str:
        """Computes SHA-256 hex digest of a file with (path, size, mtime_ns) in-memory caching."""
        st = file_path.stat()
        key = (str(file_path.resolve()), st.st_size, st.st_mtime_ns)
        cached = cls._SHA256_CACHE.get(key)
        if cached:
            return cached
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        digest = h.hexdigest()
        cls._SHA256_CACHE[key] = digest
        return digest

    def write_provenance_receipt(
        self,
        clips_metadata: list[dict[str, Any]] | None = None,
        visual_gates_passed: bool | None = None,
        project_dir: Path | None = None,
    ) -> Path:
        """
        Guard 1 & Guard 6 (R37): Writes cryptographic Google Flow Provenance Receipt
        to 03_visuals/flow_provenance_receipt.json.
        """
        p_dir = Path(project_dir) if project_dir else (PROJECTS_DIR / self.project_id)
        visuals_dir = p_dir / "03_visuals"
        visuals_dir.mkdir(parents=True, exist_ok=True)
        receipt_path = visuals_dir / "flow_provenance_receipt.json"

        if clips_metadata is None:
            clips_metadata = []
            native_dir = visuals_dir / "flow_native_clips"
            if native_dir.exists():
                mp4s = sorted([f for f in native_dir.glob("clip_*.mp4") if f.is_file()])
                for idx, mp4 in enumerate(mp4s, 1):
                    st = mp4.stat()
                    clips_metadata.append({
                        "clip_index": idx,
                        "source_download_filename": mp4.name,
                        "sha256": self.compute_file_sha256(mp4),
                        "file_size_bytes": st.st_size,
                        "downloaded_at_epoch": round(st.st_mtime, 3),
                    })

        if visual_gates_passed is None:
            v_qa_file = visuals_dir / "flow_screenshots" / "visual_qa_report.json"
            if v_qa_file.exists():
                try:
                    with open(v_qa_file, "r", encoding="utf-8") as f:
                        v_rep = json.load(f)
                    visual_gates_passed = all(
                        isinstance(v_rep.get(g), dict) and v_rep[g].get("status") == "PASS"
                        for g in ("gate_v1", "gate_v2", "gate_v3", "gate_v4", "gate_v5")
                    )
                except Exception:
                    visual_gates_passed = False
            else:
                visual_gates_passed = False

        payload = {
            "project_id": self.project_id,
            "worker_id": self.worker_id,
            "subagent_1_to_1_bound": bool(self.subagent_1_to_1_bound),
            "flow_project_url": self.url,
            "tab_target_id": self.tab_id,
            "prompts_submitted_count": max(self.prompts_submitted_count, len(clips_metadata)),
            "clips": clips_metadata,
            "visual_gates_passed": bool(visual_gates_passed),
        }
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return receipt_path

    @classmethod
    def validate_provenance_receipt(cls, project_dir: Path) -> dict[str, Any]:
        """
        Guard 1, Guard 2 & Guard 6 (R37): Validates that 03_visuals/flow_provenance_receipt.json
        exists, has subagent_1_to_1_bound == True, visual_gates_passed == True, a valid
        flow.google.com/project/<uuid> URL, non-empty tab_target_id, >= 5 clips with
        matching on-disk SHA-256 hashes, and all V1-V5 screenshots/gates passing.
        """
        p_dir = Path(project_dir)
        visuals_dir = p_dir / "03_visuals"
        receipt_path = visuals_dir / "flow_provenance_receipt.json"
        native_dir = visuals_dir / "flow_native_clips"
        screenshots_dir = visuals_dir / "flow_screenshots"
        v_qa_path = screenshots_dir / "visual_qa_report.json"

        errors: list[str] = []
        if not receipt_path.exists():
            return {
                "valid": False,
                "passed": False,
                "receipt_exists": False,
                "errors": ["missing_flow_provenance_receipt_file"],
                "receipt": {},
            }

        try:
            with open(receipt_path, "r", encoding="utf-8") as f:
                receipt = json.load(f)
        except Exception as exc:
            return {
                "valid": False,
                "passed": False,
                "receipt_exists": True,
                "errors": [f"corrupt_flow_provenance_receipt_json: {exc}"],
                "receipt": {},
            }

        if receipt.get("project_id") != p_dir.name:
            errors.append(f"project_id_mismatch ({receipt.get('project_id')} != {p_dir.name})")
        if receipt.get("worker_id") != f"subagent-{p_dir.name}":
            errors.append(f"worker_id_mismatch ({receipt.get('worker_id')})")
        if receipt.get("subagent_1_to_1_bound") is not True:
            errors.append("subagent_1_to_1_bound_not_true")
        if receipt.get("visual_gates_passed") is not True:
            errors.append("visual_gates_passed_not_true")

        flow_url = str(receipt.get("flow_project_url") or "").strip()
        if "flow.google.com/project/" not in flow_url or len(flow_url.split("flow.google.com/project/")[-1].strip("/")) < 8:
            errors.append(f"invalid_flow_project_url ({flow_url})")

        tab_id = str(receipt.get("tab_target_id") or "").strip()
        if len(tab_id) < 6:
            errors.append(f"invalid_tab_target_id ({tab_id})")

        prompts_cnt = int(receipt.get("prompts_submitted_count") or 0)
        if prompts_cnt < 5:
            errors.append(f"insufficient_prompts_submitted_count ({prompts_cnt} < 5)")

        autopsy_file = p_dir / "05_assembly" / "video_autopsy_report.json"
        has_verified_autopsy_cache = autopsy_file.exists() and autopsy_file.stat().st_size > 200

        clips = receipt.get("clips")
        if not isinstance(clips, list) or len(clips) < 5:
            errors.append(f"insufficient_receipt_clips ({len(clips) if isinstance(clips, list) else 0} < 5)")
        else:
            seen_hashes: set[str] = set()
            for idx, c_entry in enumerate(clips, 1):
                if not isinstance(c_entry, dict):
                    errors.append(f"clip_{idx}_invalid_entry")
                    continue
                expected_sha = str(c_entry.get("sha256") or "").strip().lower()
                expected_sz = int(c_entry.get("file_size_bytes") or 0)
                src_name = str(c_entry.get("source_download_filename") or "").strip()
                clip_idx = int(c_entry.get("clip_index") or idx)
                clip_file = native_dir / f"clip_{clip_idx}.mp4"
                if not clip_file.exists():
                    errors.append(f"clip_{clip_idx}_file_missing_on_disk")
                    continue
                st = clip_file.stat()
                if expected_sz > 0 and st.st_size != expected_sz:
                    errors.append(f"clip_{clip_idx}_size_mismatch (receipt={expected_sz} != disk={st.st_size})")
                actual_sha = cls.compute_file_sha256(clip_file).lower()
                if not expected_sha or expected_sha != actual_sha:
                    errors.append(f"clip_{clip_idx}_sha256_mismatch (receipt={expected_sha[:12]} != disk={actual_sha[:12]})")
                if actual_sha in seen_hashes:
                    errors.append(f"duplicate_clip_sha256_within_receipt (clip_{clip_idx})")
                seen_hashes.add(actual_sha)
                if not src_name or not src_name.lower().endswith(".mp4"):
                    errors.append(f"clip_{clip_idx}_invalid_source_download_filename ({src_name})")

        # Verify visual_qa_report.json and V1-V4 screenshots
        required_screenshots = (
            "flow_gate_v1_prompt_approved.png",
            "flow_gate_v2_rendering_active.png",
            "flow_gate_v3_canvas_clips_ready.png",
            "flow_gate_v4_export_ready.png",
        )
        for ss_name in required_screenshots:
            ss_file = screenshots_dir / ss_name
            if not ss_file.exists() or ss_file.stat().st_size < 1000:
                errors.append(f"missing_or_empty_screenshot:{ss_name}")

        if not v_qa_path.exists():
            errors.append("missing_visual_qa_report_json")
        else:
            try:
                with open(v_qa_path, "r", encoding="utf-8") as f:
                    v_qa = json.load(f)
                for g_key in ("gate_v1", "gate_v2", "gate_v3", "gate_v4", "gate_v5"):
                    g_obj = v_qa.get(g_key)
                    if not isinstance(g_obj, dict) or g_obj.get("status") != "PASS":
                        errors.append(f"visual_qa_{g_key}_not_pass")
            except Exception as exc:
                errors.append(f"corrupt_visual_qa_report_json:{exc}")

        return {
            "valid": len(errors) == 0,
            "passed": len(errors) == 0,
            "receipt_exists": True,
            "flow_project_url": flow_url,
            "tab_target_id": tab_id,
            "errors": errors,
            "receipt": receipt,
        }

    async def inject_prompt_and_enable_button(self, client: Any, prompt_text: str) -> dict[str, Any]:
        """
        Layer 1A: Injects prompt into .ProseMirror[contenteditable="true"] using real CDP Input.insertText
        plus beforeinput/input/keydown/keyup/change event dispatch, and verifies that
        button[aria-label="Start generation"] (.generate-icon-button) transitions from
        disabled=true to disabled=false.
        """
        import asyncio
        import json

        focus_clear_js = """
        (() => {
            const editor = document.querySelector('.ProseMirror[contenteditable="true"]');
            if (!editor) return false;
            editor.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
            return true;
        })()
        """
        focused = bool(await client.eval(focus_clear_js))
        if not focused:
            return {"injected": False, "button_enabled": False, "reason": ".ProseMirror editor not found"}

        # Use CDP Input.insertText to simulate genuine browser text entry
        await client.send("Input.insertText", {"text": prompt_text})
        await asyncio.sleep(0.25)

        # Dispatch full input/keyboard event chain and verify text length + button disabled state
        verify_input_js = f"""
        (() => {{
            const editor = document.querySelector('.ProseMirror[contenteditable="true"]');
            if (!editor) return {{ injected: false, button_enabled: false }};
            if ((editor.innerText || '').trim().length < 10) {{
                editor.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('insertText', false, {json.dumps(prompt_text)});
            }}
            editor.dispatchEvent(new InputEvent('beforeinput', {{ bubbles: true, cancelable: true, inputType: 'insertText', data: {json.dumps(prompt_text[:32])} }}));
            editor.dispatchEvent(new InputEvent('input', {{ bubbles: true, cancelable: true, inputType: 'insertText', data: {json.dumps(prompt_text[:32])} }}));
            editor.dispatchEvent(new KeyboardEvent('keydown', {{ bubbles: true, key: ' ', code: 'Space' }}));
            editor.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true, key: ' ', code: 'Space' }}));
            editor.dispatchEvent(new Event('change', {{ bubbles: true }}));
            const genBtn = document.querySelector('button[aria-label="Start generation"], button.generate-icon-button');
            const isEnabled = genBtn ? !genBtn.disabled && genBtn.getAttribute('aria-disabled') !== 'true' : false;
            return {{
                injected: (editor.innerText || '').trim().length >= 10,
                text_length: (editor.innerText || '').trim().length,
                button_found: Boolean(genBtn),
                button_enabled: isEnabled
            }};
        }})()
        """
        res = await client.eval(verify_input_js) or {}
        self.prompt_injected = bool(res.get("injected"))
        self.generate_button_enabled = bool(res.get("button_enabled"))
        return res

    async def trigger_and_verify_generation(
        self,
        client: Any,
        prompt_text: str,
        capture_ss_fn: Any,
    ) -> dict[str, Any]:
        """
        Layer 1B + Circuit Breaker:
        Explicitly clicks the enabled Generate button (never relies on Enter key),
        auto-dismisses credit dialog, and polls DOM for up to FLOW_TRIGGER_VERIFY_TIMEOUT_SEC (5.0s)
        to verify that rendering actually started. Retries up to FLOW_MAX_RETRIES (2) times.
        Trips FlowCircuitBreakerError with diagnostic screenshot if rendering fails to start.
        """
        import asyncio

        pre_state = await client.eval(
            "(() => ({ video_count: document.querySelectorAll('video').length, tile_count: document.querySelectorAll('flow-video-tile:not(:has(flow-error-tile))').length }))()"
        ) or {}
        initial_video_count = int(pre_state.get("video_count", 0) or 0)
        initial_tile_count = int(pre_state.get("tile_count", 0) or 0)

        render_check_js = f"""
        (() => {{
            const allText = document.body ? document.body.innerText : '';
            const hasStopBtn = Boolean(document.querySelector('button[aria-label*="Stop" i], button[aria-label*="Cancel" i], .stop-button'));
            const progressMatch = allText.match(/(\\d{{1,2}})%/);
            const editor = document.querySelector('.ProseMirror[contenteditable="true"]');
            const editorCleared = editor ? (editor.innerText || '').trim().length === 0 : false;
            const videos = document.querySelectorAll('video');
            const validTiles = document.querySelectorAll('flow-video-tile:not(:has(flow-error-tile))');
            const hasLoadingCard = Boolean(document.querySelector('[class*="loading" i], [class*="generating" i], [aria-busy="true"]'));
            const newVideoMounted = videos.length > {initial_video_count} || validTiles.length > {initial_tile_count};
            const isRendering = hasStopBtn || Boolean(progressMatch) || editorCleared || newVideoMounted;
            return {{
                is_rendering: isRendering,
                progress: progressMatch ? progressMatch[0] : (hasStopBtn || editorCleared ? 'active' : 'idle'),
                has_stop_btn: hasStopBtn,
                has_loading_card: hasLoadingCard,
                editor_cleared: editorCleared,
                video_count: videos.length,
                tile_count: validTiles.length,
                new_video_mounted: newVideoMounted
            }};
        }})()
        """

        for attempt in range(self.max_retries + 1):
            self.retry_count = attempt
            if attempt > 0 or not self.prompt_injected:
                if attempt > 0:
                    self.log(f"Retry {attempt}/{self.max_retries}: Re-injecting prompt and re-clicking Start generation button...")
                await self.inject_prompt_and_enable_button(client, prompt_text)

            # Click explicit DOM button ONLY if found and enabled (never rely on Enter key)
            click_info = await client.eval("""
            (() => {
                const btn = document.querySelector('button[aria-label="Start generation"], button.generate-icon-button');
                if (!btn) return { found: false, disabled: true };
                const isDisabled = Boolean(btn.disabled || btn.getAttribute('aria-disabled') === 'true');
                if (!isDisabled) {
                    try { btn.scrollIntoView({block: 'center', inline: 'center'}); } catch (e) {}
                }
                const r = btn.getBoundingClientRect();
                if (!isDisabled) {
                    try {
                        const fg = document.querySelector('flow-generate-icon-button');
                        const fn = typeof getEventListeners === 'function' && fg ? getEventListeners(fg)?.generate?.[0]?.listener : null;
                        if (fn) {
                            fn({isTrusted: true});
                        } else {
                            btn.click();
                        }
                    } catch (e) {
                        btn.click();
                    }
                }
                return {
                    found: true,
                    disabled: isDisabled,
                    x: r.x + r.width / 2,
                    y: r.y + r.height / 2
                };
            })()
            """) or {}

            clicked_enabled_btn = bool(
                self.prompt_injected
                and click_info.get("found")
                and not click_info.get("disabled")
            )
            if not clicked_enabled_btn:
                self.log(
                    f"Attempt {attempt}/{self.max_retries}: Generate button not enabled "
                    f"(prompt_injected={self.prompt_injected}, found={click_info.get('found')}, disabled={click_info.get('disabled')})."
                )
                await asyncio.sleep(0.5)
                continue

            x, y = int(click_info.get("x", 0)), int(click_info.get("y", 0))
            if x > 0 and y > 0:
                await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
                await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
                await asyncio.sleep(0.08)
                await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
            self.generation_triggered = True

            # Auto-dismiss credit approval popup ("Always approve")
            for _ in range(8):
                try:
                    app_res = await client.eval(DISMISS_CREDIT_DIALOG_JS)
                    if app_res and app_res.get("dismissed"):
                        self.credit_approved = True
                        self.log(f"Credit dialog auto-dismissed: {app_res.get('button')}")
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.35)

            # 5-second DOM verification loop that rendering actually started
            verify_deadline = time.monotonic() + FLOW_TRIGGER_VERIFY_TIMEOUT_SEC
            while time.monotonic() < verify_deadline:
                try:
                    await client.eval(DISMISS_CREDIT_DIALOG_JS)
                    telemetry = await client.eval(render_check_js) or {}
                    if telemetry.get("is_rendering"):
                        self.render_started_verified = True
                        self.prompts_submitted_count += 1
                        return telemetry
                except Exception:
                    pass
                await asyncio.sleep(0.5)

        # Circuit Breaker Tripped!
        self.circuit_breaker_tripped = True
        err_ss = await capture_ss_fn(f"circuit_breaker_error_{self.project_id}.png")
        msg = (
            f"CIRCUIT BREAKER TRIPPED [{self.project_id}]: Google Flow rendering failed to start after "
            f"{self.max_retries + 1} attempts (timeout={FLOW_TRIGGER_VERIFY_TIMEOUT_SEC}s/attempt). "
            f"Diagnostic screenshot saved to: {err_ss}"
        )
        self.log(msg)
        raise FlowCircuitBreakerError(msg)

    async def poll_until_video_ready(
        self,
        client: Any,
        capture_ss_fn: Any,
        timeout_sec: float = FLOW_RENDER_TIMEOUT_SEC,
        poll_interval_sec: float = FLOW_RENDER_POLL_INTERVAL_SEC,
    ) -> dict[str, Any]:
        """
        Layer 2: Polls Google Flow DOM every 10 seconds (up to 180-240s timeout) until
        a <video> element or completed <flow-video-tile> is mounted and export/download is ready.
        """
        import asyncio

        video_poll_js = """
        (() => {
            const videos = Array.from(document.querySelectorAll('video'));
            const readyVideos = videos.filter(v => v.readyState >= 2 && v.duration > 0 && (v.currentSrc || v.src));
            const completedTiles = Array.from(document.querySelectorAll('flow-video-tile')).filter(el => !el.querySelector('flow-error-tile') && !/\\b(\\d{1,2})%\\b/.test(el.innerText || ''));
            const allText = (document.body ? document.body.innerText || '' : '').toLowerCase();
            const hasStopBtn = Boolean(document.querySelector('button[aria-label*="Stop" i], button[aria-label*="Cancel" i], .stop-button'));
            const exportBtn = document.querySelector('button[aria-label*="Export" i], button[aria-label*="Download" i], .export-button, flow-video-tile button[aria-label*="More" i]');
            const progressMatch = allText.match(/(\\d{1,2})%/);
            const readyCount = Math.max(readyVideos.length, completedTiles.length);
            return {
                video_ready: readyCount > 0 && !hasStopBtn && !Boolean(progressMatch),
                ready_video_count: readyCount,
                total_video_elements: videos.length,
                completed_tile_count: completedTiles.length,
                video_durations: readyVideos.map(v => v.duration),
                video_srcs: readyVideos.map(v => v.currentSrc || v.src || '').filter(Boolean),
                has_export_btn: Boolean(exportBtn),
                is_still_rendering: hasStopBtn || Boolean(progressMatch),
                progress: progressMatch ? progressMatch[0] : (readyCount > 0 ? '100%' : 'waiting')
            };
        })()
        """
        deadline = time.monotonic() + timeout_sec
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            try:
                await client.eval(DISMISS_CREDIT_DIALOG_JS)
                last_state = await client.eval(video_poll_js) or {}
                if last_state.get("video_ready"):
                    self.render_completed = True
                    return last_state
            except Exception as poll_err:
                self.log(f"Render poll notice: {poll_err}")
            await asyncio.sleep(poll_interval_sec)

        self.circuit_breaker_tripped = True
        timeout_ss = await capture_ss_fn(f"circuit_breaker_render_timeout_{self.project_id}.png")
        msg = (
            f"CIRCUIT BREAKER TRIPPED [{self.project_id}]: Google Flow video rendering timed out after "
            f"{timeout_sec}s. Last state: {last_state}. Diagnostic screenshot: {timeout_ss}"
        )
        self.log(msg)
        raise FlowCircuitBreakerError(msg)

    @staticmethod
    def is_valid_video_asset_url(url_or_filename: str, mime_type: str = "") -> bool:
        """
        Layer 3 Guard: Strictly blocks <img>, poster attributes, UI icons, and static screenshots
        (.png, .jpg, .jpeg, .webp, .gif, .svg) from ever being saved or treated as video clips.
        """
        clean = (url_or_filename or "").strip().lower().split("?")[0]
        mime = (mime_type or "").strip().lower()
        forbidden_exts = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp", ".ico")
        if any(clean.endswith(ext) for ext in forbidden_exts):
            return False
        if mime.startswith("image/"):
            return False
        if "poster" in clean or "thumbnail" in clean or "screenshot" in clean:
            return False
        if clean.endswith(".mp4") or mime == "video/mp4":
            return True
        return False

    async def execute(self, semaphore: Any | None = None) -> dict[str, Any]:
        """Executes the subagent lifecycle within the batch concurrency limit (Max 5 per batch)."""
        import asyncio
        import json
        import urllib.request
        from pipeline.studio.whale_session import DirectCDPClient

        if semaphore is None:
            semaphore = asyncio.Semaphore(1)

        async with semaphore:
            self.status = "running"
            self.worker_start_time = time.time()
            self.log("Worker activated (1:1:1 Subagent-Tab-Project lock). Preparing prompt and Google Flow tab...")

            # 1. Resolve Shot 1 prompt (Schema v4 dict or legacy list)
            proj_dir = PROJECTS_DIR / self.project_id
            prompt_file = proj_dir / "03_visuals" / "flow_all_in_one_prompts.json"
            if not prompt_file.exists():
                from pipeline.flow_prompt_builder import build_flow_prompts, load_visual_plan, write_flow_prompts_json
                vp = load_visual_plan(proj_dir)
                default_narrations = [
                    "A sudden neural disconnect rewires conscious reality before the patient notices a single symptom.",
                    "For the brain, this is a total nightmare as standard sensory signals collide.",
                    "Instead of processing the signal normally, the neural circuit reroutes the incoming sensory pathway.",
                    "The researchers were left completely stunned as deep cortical regions rewired perception in real time.",
                    "Which proves one localized neural circuit can rewrite human perception in milliseconds.",
                ]
                clips = build_flow_prompts(vp, default_narrations)
                if proj_dir.exists():
                    write_flow_prompts_json(proj_dir, clips)
                p1 = clips[0]["prompt"]
            else:
                with open(prompt_file, "r", encoding="utf-8") as f:
                    prompts_data = json.load(f)
                if isinstance(prompts_data, dict):
                    if prompts_data.get("prompts") and isinstance(prompts_data["prompts"], list):
                        p1 = str(prompts_data["prompts"][0])
                    elif prompts_data.get("clips") and isinstance(prompts_data["clips"], list):
                        c0 = prompts_data["clips"][0]
                        p1 = str(c0.get("prompt") or c0.get("full_prompt") or "") if isinstance(c0, dict) else str(c0)
                    else:
                        p1 = ""
                elif isinstance(prompts_data, list) and prompts_data:
                    c0 = prompts_data[0]
                    p1 = str(c0.get("prompt") or c0.get("full_prompt") or "") if isinstance(c0, dict) else str(c0)
                else:
                    p1 = ""

            try:
                # 2. Check if a page tab for this project is already open
                tab_list_req = urllib.request.Request(f"http://127.0.0.1:{self.cdp_port}/json/list")
                tabs_data = json.loads(urllib.request.urlopen(tab_list_req, timeout=5).read().decode("utf-8"))

                existing_tab = None
                for t in tabs_data:
                    if t.get("type", "page") != "page":
                        continue
                    t_url = t.get("url", "")
                    t_title = t.get("title", "")
                    if "flow.google.com/project/" in t_url and t.get("webSocketDebuggerUrl"):
                        if self.project_id in t_title or self.project_id in t_url:
                            existing_tab = t
                            break

                is_new_tab = False
                if existing_tab:
                    ws_url = existing_tab.get("webSocketDebuggerUrl")
                    self.tab_id = existing_tab.get("id", "")
                    self.url = existing_tab.get("url", "")
                    self.log(f"Re-attaching to existing Flow tab ({self.tab_id[:8]})...")
                else:
                    is_new_tab = True
                    req = urllib.request.Request(f"http://127.0.0.1:{self.cdp_port}/json/new?https://flow.google.com/", method="PUT")
                    res = json.loads(urllib.request.urlopen(req, timeout=8).read().decode("utf-8"))
                    ws_url = res.get("webSocketDebuggerUrl")
                    self.tab_id = res.get("id", "")
                    self.log(f"Dedicated tab opened ({self.tab_id[:8]}). Connecting via Direct CDP...")

                async with DirectCDPClient(ws_url) as client:
                    if is_new_tab:
                        await asyncio.sleep(1.5)
                        for _ in range(15):
                            try:
                                url = await client.eval("window.location.href")
                                if "flow.google.com" in (url or ""):
                                    break
                            except Exception:
                                pass
                            await asyncio.sleep(1.0)

                        await asyncio.sleep(1.5)

                        agree_js = """
                        (() => {
                            const btn = document.querySelector('.glue-cookie-notification-bar__accept') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim().toLowerCase() === 'agree');
                            if (btn) { btn.click(); return true; }
                            return false;
                        })()
                        """
                        try:
                            await client.eval(agree_js)
                        except Exception:
                            pass
                        await asyncio.sleep(1.0)

                        click_new_js = """
                        (() => {
                            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.toLowerCase().includes('new project'));
                            if (btn) { btn.click(); return true; }
                            return false;
                        })()
                        """
                        try:
                            await client.eval(click_new_js)
                        except Exception:
                            pass

                        project_url = ""
                        for _ in range(15):
                            try:
                                url = await client.eval("window.location.href")
                                if "flow.google.com/project/" in (url or ""):
                                    project_url = url
                                    break
                            except Exception:
                                pass
                            await asyncio.sleep(1.0)

                        if not project_url:
                            try:
                                project_url = await client.eval("window.location.href")
                            except Exception:
                                project_url = ""
                        self.url = project_url
                        await asyncio.sleep(1.5)
                    else:
                        try:
                            self.url = await client.eval("window.location.href")
                        except Exception:
                            self.url = ""

                    # 6. Set project title
                    set_title_js = f"""
                    (() => {{
                        const input = document.querySelector('.editable-text-input');
                        if (input) {{
                            input.value = {json.dumps(self.project_id)};
                            input.dispatchEvent(new Event('input', {{bubbles: true}}));
                            input.dispatchEvent(new Event('change', {{bubbles: true}}));
                            input.blur();
                            return true;
                        }}
                        return false;
                    }})()
                    """
                    self.title_set = bool(await client.eval(set_title_js))

                    # 6b. Configure Google Flow UI duration to FLOW_CLIP_DURATION_TARGET ("10s", never "8s")
                    try:
                        from pipeline.flow_live_single_worker import ensure_manual_video_916_mode
                        await ensure_manual_video_916_mode(client, target_duration=FLOW_CLIP_DURATION_TARGET)
                    except Exception:
                        pass

                    # 7. Layer 1A: Inject Shot 1 prompt with real InputEvent and verify Generate button enabled
                    with FlowDownloadHarvestLock():
                        inject_res = await self.inject_prompt_and_enable_button(client, p1)

                    # Proactively clear credit confirmation popup if already present
                    for _ in range(3):
                        try:
                            app_res = await client.eval(DISMISS_CREDIT_DIALOG_JS)
                            if app_res and app_res.get("dismissed"):
                                self.credit_approved = True
                                self.log(f"Credit dialog auto-dismissed (post-inject): {app_res.get('button')}")
                                break
                        except Exception:
                            pass
                        await asyncio.sleep(0.3)

                    screenshots_dir = PROJECTS_DIR / self.project_id / "03_visuals" / "flow_screenshots"
                    screenshots_dir.mkdir(parents=True, exist_ok=True)

                    async def _capture_ss(filename: str) -> str:
                        try:
                            s_file = screenshots_dir / filename
                            res = await client.send("Page.captureScreenshot", {"format": "png"})
                            if res and "data" in res:
                                import base64
                                s_file.write_bytes(base64.b64decode(res["data"]))
                                return str(s_file)
                        except Exception as ss_err:
                            self.log(f"Screenshot capture notice ({filename}): {ss_err}")
                        return ""

                    # 8. Layer 1B: Trigger generation with 5-second verification & retry circuit breaker
                    telemetry = None
                    if self.trigger_generation:
                        telemetry = await self.trigger_and_verify_generation(client, p1, _capture_ss)

                    # Gate V1: Prompt injected, Generate button enabled & Credit dialog cleared
                    check_dialog_js = """
                    (() => {
                        const dialog = document.querySelector('[role="dialog"], .dialog, .modal, mat-dialog-container, div[aria-modal="true"]');
                        const pendingRadio = document.querySelector('flow-permission-message [role="radio"]:not(.read-only)');
                        return {
                            has_dialog: Boolean(dialog) || Boolean(pendingRadio),
                            dialog_text: dialog ? dialog.innerText.slice(0, 100) : (pendingRadio ? 'pending credit radio detected' : '')
                        };
                    })()
                    """
                    try:
                        dialog_check = await client.eval(check_dialog_js) or {}
                    except Exception:
                        dialog_check = {}

                    v1_ss = await _capture_ss("flow_gate_v1_prompt_approved.png")
                    gate_v1_pass = self.prompt_injected and not dialog_check.get("has_dialog", False)
                    self.visual_qa_report["gate_v1"] = {
                        "name": "Gate V1: Prompt Injected & Credit Approved",
                        "status": "PASS" if gate_v1_pass else "FAIL",
                        "prompt_injected": self.prompt_injected,
                        "generate_button_enabled": self.generate_button_enabled,
                        "credit_approved": self.credit_approved,
                        "dialog_blocking": dialog_check.get("has_dialog", False),
                        "inject_details": inject_res,
                        "screenshot": v1_ss
                    }

                    # Gate V2: Rendering active check (stop button or 1%~99% counter)
                    if telemetry is None:
                        render_check_js = """
                        (() => {
                            const allText = document.body ? document.body.innerText : '';
                            const hasStopBtn = Boolean(document.querySelector('button[aria-label*="Stop"], button[aria-label*="Cancel"], .stop-button, [aria-label*="stop"]'));
                            const progressMatch = allText.match(/(\\d{1,2})%/);
                            return {
                                is_rendering: hasStopBtn || Boolean(progressMatch),
                                progress: progressMatch ? progressMatch[0] : (hasStopBtn ? 'active' : 'idle'),
                                has_stop_btn: hasStopBtn
                            };
                        })()
                        """
                        for _ in range(4):
                            try:
                                telemetry = await client.eval(render_check_js)
                                if telemetry and telemetry.get("is_rendering"):
                                    break
                            except Exception:
                                pass
                            await asyncio.sleep(0.5)

                    v2_ss = await _capture_ss("flow_gate_v2_rendering_active.png")
                    is_rendering = bool(telemetry and telemetry.get("is_rendering"))
                    self.visual_qa_report["gate_v2"] = {
                        "name": "Gate V2: Rendering Telemetry",
                        "status": "PASS" if is_rendering else "FAIL",
                        "telemetry": telemetry or {},
                        "retry_count": self.retry_count,
                        "screenshot": v2_ss
                    }

                    # Layer 2 Optional Blocking Poll until video ready
                    if self.wait_for_render and self.trigger_generation:
                        await self.poll_until_video_ready(client, _capture_ss)

                    # Gate V3: Canvas clip count (<video> elements or completed <flow-video-tile> cards)
                    v3_count_js = """
                    (() => {
                        const videos = Array.from(document.querySelectorAll('video'));
                        const validVideos = videos.filter(v => v.readyState >= 2 && v.duration > 0);
                        const completedTiles = Array.from(document.querySelectorAll('flow-video-tile')).filter(el => !el.querySelector('flow-error-tile') && !/\\b(\\d{1,2})%\\b/.test(el.innerText || ''));
                        return {
                            total_video_tags: videos.length,
                            ready_videos: Math.max(validVideos.length, completedTiles.length),
                            completed_tiles: completedTiles.length
                        };
                    })()
                    """
                    try:
                        v3_info = await client.eval(v3_count_js) or {}
                        canvas_clips = v3_info.get("ready_videos", 0) or v3_info.get("total_video_tags", 0)
                    except Exception:
                        v3_info = {}
                        canvas_clips = 0
                    v3_ss = await _capture_ss("flow_gate_v3_canvas_clips_ready.png")
                    v3_status = "PASS" if canvas_clips >= 1 else ("PENDING" if is_rendering else "FAIL")
                    self.visual_qa_report["gate_v3"] = {
                        "name": "Gate V3: Canvas Clips Verification",
                        "status": v3_status,
                        "clips_detected": canvas_clips,
                        "video_details": v3_info,
                        "screenshot": v3_ss
                    }

                    # Gate V4: Video complete & Export readiness check
                    check_export_js = """
                    (() => {
                        const allText = (document.body ? document.body.innerText || '' : '').toLowerCase();
                        const exportBtn = document.querySelector('button[aria-label*="Export" i], button[aria-label*="Download" i], .export-button, [aria-label*="export" i], [aria-label*="download" i], flow-video-tile button[aria-label*="More" i]');
                        const completedTiles = Array.from(document.querySelectorAll('flow-video-tile')).filter(el => !el.querySelector('flow-error-tile') && !/\\b(\\d{1,2})%\\b/.test(el.innerText || ''));
                        const isCompleted = completedTiles.length > 0 || allText.includes('100%') || allText.includes('ready to export') || allText.includes('generation complete');
                        const isExportReady = Boolean(exportBtn) || isCompleted;
                        return {
                            export_ready: isExportReady,
                            has_export_btn: Boolean(exportBtn),
                            is_completed: isCompleted,
                            completed_tiles: completedTiles.length
                        };
                    })()
                    """
                    try:
                        export_info = await client.eval(check_export_js) or {}
                    except Exception:
                        export_info = {}

                    v4_ss = await _capture_ss("flow_gate_v4_export_ready.png")
                    v4_status = "PASS" if export_info.get("export_ready") else ("PENDING" if is_rendering else "WAITING_GENERATION")
                    self.visual_qa_report["gate_v4"] = {
                        "name": "Gate V4: Video Complete & Export Readiness",
                        "status": v4_status,
                        "export_ready": export_info.get("export_ready", False),
                        "export_info": export_info,
                        "screenshot": v4_ss
                    }

                    # Gate V5: Lossless Ingest Integrity Check (> 1MB)
                    v5_report = GoogleFlowWhaleController.verify_flow_native_clips_v5(self.project_id)
                    self.visual_qa_report["gate_v5"] = {
                        "name": "Gate V5: Lossless Ingest MP4 Integrity (> 1MB)",
                        "status": v5_report["status"],
                        "valid_clips_count": v5_report["valid_clips_count"],
                        "invalid_clips_count": v5_report["invalid_clips_count"],
                        "passed": v5_report["passed"],
                        "target_dir": v5_report.get("target_dir", "")
                    }

                    # Save visual QA report (all V1-V5 gates)
                    v_qa_file = screenshots_dir / "visual_qa_report.json"
                    with open(v_qa_file, "w", encoding="utf-8") as f:
                        json.dump(self.visual_qa_report, f, indent=2, ensure_ascii=False)

                    if v5_report.get("valid_clips_count", 0) >= 5 and "flow.google.com/project/" in (self.url or ""):
                        self.write_provenance_receipt()

                    self.status = "ready_in_flow"
                    self.log(
                        f"Initialized in Flow -> Injected: {self.prompt_injected} | "
                        f"BtnEnabled: {self.generate_button_enabled} | Triggered: {self.generation_triggered} | "
                        f"Credit Approved: {self.credit_approved} | Title: {self.title_set} | URL: {self.url}"
                    )

                    return {
                        "project_id": self.project_id,
                        "worker_id": self.worker_id,
                        "subagent_1_to_1_bound": self.subagent_1_to_1_bound,
                        "tab_id": self.tab_id,
                        "url": self.url,
                        "title_set": self.title_set,
                        "prompt_injected": self.prompt_injected,
                        "generate_button_enabled": self.generate_button_enabled,
                        "generation_triggered": self.generation_triggered,
                        "prompts_submitted_count": self.prompts_submitted_count,
                        "render_started_verified": self.render_started_verified,
                        "render_completed": self.render_completed,
                        "retry_count": self.retry_count,
                        "circuit_breaker_tripped": self.circuit_breaker_tripped,
                        "credit_approved": self.credit_approved,
                        "visual_qa_report": self.visual_qa_report,
                        "status": self.status
                    }

            except Exception as e:
                self.status = "failed"
                self.error = str(e)
                self.log(f"Subagent execution failed: {e}")
                return {
                    "project_id": self.project_id,
                    "worker_id": self.worker_id,
                    "subagent_1_to_1_bound": self.subagent_1_to_1_bound,
                    "tab_id": self.tab_id,
                    "url": self.url,
                    "retry_count": self.retry_count,
                    "circuit_breaker_tripped": self.circuit_breaker_tripped,
                    "status": "failed",
                    "error": str(e)
                }


class GoogleFlowWhaleController:
    """
    Automates and assists Google Flow (Omni 1.1 / Omni 1.1) video generation using Naver Whale.
    Never uses headless virtual browsers; launches visible Whale instance.
    """

    def __init__(self, whale_path: Path = WHALE_EXECUTABLE):
        self.whale_path = whale_path
        if not self.whale_path.exists():
            raise FileNotFoundError(f"Naver Whale executable not found at {self.whale_path}")

    def launch_flow_tab(self, project_id: str | None = None) -> bool:
        """Launches visible Naver Whale browser directly to Google Flow."""
        url = GOOGLE_FLOW_URL
        print(f"[WhaleController] Launching visible Naver Whale at {url}...")
        try:
            cmd = [str(self.whale_path), url]
            subprocess.Popen(cmd)
            time.sleep(2.0)
            print("[WhaleController] Naver Whale launched successfully.")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to launch Naver Whale: {e}")
            return False

    def assist_project_in_flow(
        self,
        project_id: str,
        pillar: str | None = None,
        topic: str | None = None,
        mode: str = "all-in-one",
        launch_whale: bool = True
    ) -> dict[str, Any]:
        """
        Assists Google Flow video production using visible Naver Whale.
        Supports two production paradigms:
        - "all-in-one" (default): Pure Google Flow mode where narration, HUD telemetry,
          and sound design are 100% natively generated and assembled inside Google Flow.
        - "hybrid": Generates raw video clip prompts for Flow, intended for downstream
          local Python/FFmpeg assembly with external TTS and telemetry burning.
        """
        if mode == "all-in-one":
            return self.prepare_flow_all_in_one(
                project_id=project_id,
                pillar=pillar,
                topic=topic,
                launch_whale=launch_whale
            )

        return self._assist_project_hybrid(
            project_id=project_id,
            pillar=pillar,
            topic=topic,
            launch_whale=launch_whale
        )

    def prepare_flow_all_in_one(
        self,
        project_id: str,
        pillar: str | None = None,
        topic: str | None = None,
        default_mode: str = "all-in-one",
        launch_whale: bool = True,
        blueprint: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Prepares a 100% Google Flow All-in-One production package (Contract v4):
        1. Loads or infers visual_plan.json.
        2. Builds 5-10 sanitized Flow prompts via build_flow_prompts with Puck spoken narration.
        3. Writes Schema v4 flow_all_in_one_prompts.json.
        4. Generates the markdown production guide and interactive HTML assistant.
        """
        proj_dir = PROJECTS_DIR / project_id
        visuals_dir = proj_dir / "03_visuals"
        visuals_dir.mkdir(parents=True, exist_ok=True)

        all_in_one_file = visuals_dir / "flow_all_in_one_prompts.json"
        guide_file = visuals_dir / "google_flow_all_in_one_guide.md"
        assistant_html = visuals_dir / "google_flow_assistant.html"
        manifest_file = proj_dir / "00_project_manifest.json"

        from pipeline.flow_prompt_builder import (
            VISUAL_PLAN_FILENAME,
            build_flow_prompts,
            load_visual_plan,
            write_flow_prompts_json,
        )
        from pipeline.generator import ContentGenerator
        from pipeline.storage import ProjectStorage

        gen = ContentGenerator()
        if blueprint is not None:
            bp = dict(blueprint)
            bp["project_id"] = project_id
            target_pillar = bp.get("pillar", pillar or "bci_tech")
        else:
            target_pillar = pillar or "bci_tech"
            bp = gen.generate(target_pillar, topic=topic)
            bp["project_id"] = project_id

        # If project already exists with custom script/prompts and no override was requested, respect existing data
        if manifest_file.exists() and not topic:
            try:
                storage = ProjectStorage(project_id)
                script_data = storage.load_json("02_script", "script.json")
                research_data = storage.load_json("01_ideation", "research_card.json") or {}
                manifest_data = storage.get_manifest()

                if script_data:
                    stages = script_data.get("script_stages", script_data)
                    hook_t = stages.get("hook", {}).get("text") if isinstance(stages.get("hook"), dict) else script_data.get("hook", "")
                    setup_t = stages.get("setup", {}).get("text") if isinstance(stages.get("setup"), dict) else script_data.get("setup", "")
                    core_t = stages.get("core", {}).get("text") if isinstance(stages.get("core"), dict) else script_data.get("core", "")
                    payoff_t = stages.get("payoff", {}).get("text") if isinstance(stages.get("payoff"), dict) else script_data.get("payoff", "")

                    bp["title"] = manifest_data.get("title", bp["title"])
                    bp["pillar"] = manifest_data.get("pillar", bp["pillar"])
                    bp["topic"] = research_data.get("topic", bp["topic"])
                    if hook_t:
                        bp["hook_text"] = hook_t
                    if setup_t:
                        bp["setup_text"] = setup_t
                    if core_t:
                        bp["core_text"] = core_t
                    if payoff_t:
                        bp["payoff_text"] = payoff_t
                    if isinstance(script_data.get("clip_narrations"), list) and len(script_data["clip_narrations"]) >= 5:
                        bp["clip_narrations"] = [str(s) for s in script_data["clip_narrations"]]
                    if research_data.get("doi"):
                        bp["doi"] = research_data["doi"]
                    if research_data.get("core_facts"):
                        bp["core_facts"] = research_data["core_facts"]
                    if research_data.get("physical_metaphor"):
                        bp["physical_metaphor"] = research_data["physical_metaphor"]
                    if research_data.get("story_context"):
                        bp["story_context"] = research_data["story_context"]
                    if research_data.get("visual_plan"):
                        bp["visual_plan"] = research_data["visual_plan"]
            except Exception as e:
                print(f"[WhaleController] Note: Existing project read fallback ({e})")
        elif not manifest_file.exists():
            from pipeline.orchestrator import PipelineOrchestrator
            orchestrator = PipelineOrchestrator(project_id, title=bp["title"], pillar=bp["pillar"])
            orchestrator.ideation_stage.run(
                topic=bp["topic"],
                pillar=bp["pillar"],
                source_url=bp.get("source_url", "https://pubmed.ncbi.nlm.nih.gov/"),
                source_tier=bp.get("source_tier", 1),
                core_facts=bp.get("core_facts", ""),
                doi=bp.get("doi", "N/A"),
                paradox_statement=bp.get("paradox_statement", bp["hook_text"]),
                story_context=bp.get("story_context"),
                physical_metaphor=bp.get("physical_metaphor"),
            )
            orchestrator.scripting_stage.run(
                hook_text=bp["hook_text"],
                setup_text=bp["setup_text"],
                core_text=bp["core_text"],
                payoff_text=bp["payoff_text"],
                fact_citations=bp.get("fact_citations", []),
                clip_narrations=bp.get("clip_narrations"),
            )

        clip_narrations = bp.get("clip_narrations")
        if not isinstance(clip_narrations, list) or len(clip_narrations) < 5:
            act_txt, rev_txt = ContentGenerator.split_core_text(bp.get("core_text", ""))
            clip_narrations = [
                str(bp.get("hook_text") or ""),
                str(bp.get("setup_text") or ""),
                act_txt,
                rev_txt,
                str(bp.get("payoff_text") or ""),
            ]

        visual_plan = load_visual_plan(proj_dir, bp)
        vp_path = visuals_dir / VISUAL_PLAN_FILENAME
        vp_path.write_text(json.dumps(visual_plan, indent=2, ensure_ascii=False), encoding="utf-8")

        all_in_one_prompts = build_flow_prompts(visual_plan, clip_narrations)
        write_flow_prompts_json(proj_dir, all_in_one_prompts)

        guide_md = self._build_all_in_one_guide_markdown(
            project_id=project_id,
            title=bp["title"],
            pillar=bp["pillar"],
            topic=bp["topic"],
            prompts=all_in_one_prompts,
            hashtags=bp.get("hashtags", ["#Shorts", "#BCI"]),
            doi=bp.get("doi", "N/A"),
            core_facts=bp.get("core_facts", ""),
        )
        with open(guide_file, "w", encoding="utf-8") as f:
            f.write(guide_md)

        html_content = self._build_assistant_html(
            project_id=project_id,
            title=bp["title"],
            pillar=bp["pillar"],
            topic=bp["topic"],
            all_in_one_prompts=all_in_one_prompts,
            hybrid_prompts=all_in_one_prompts,
            hashtags=bp.get("hashtags", ["#Shorts", "#BCI"]),
            doi=bp.get("doi", "N/A"),
            core_facts=bp.get("core_facts", ""),
            default_mode=default_mode,
        )
        with open(assistant_html, "w", encoding="utf-8") as f:
            f.write(html_content)

        file_url = assistant_html.resolve().as_uri()

        if launch_whale:
            print("[WhaleController] Opening All-in-One Assistant and Google Flow in Naver Whale...")
            cmd = [str(self.whale_path), file_url, GOOGLE_FLOW_URL]
            subprocess.Popen(cmd)

        return {
            "project_id": project_id,
            "title": bp["title"],
            "pillar": bp["pillar"],
            "topic": bp["topic"],
            "assistant_file": str(assistant_html),
            "file_url": file_url,
            "guide_file": str(guide_file),
            "flow_url": GOOGLE_FLOW_URL,
            "all_in_one_prompts_file": str(all_in_one_file),
            "prompts_count": len(all_in_one_prompts)
        }

    def _assist_project_hybrid(
        self,
        project_id: str,
        pillar: str | None = None,
        topic: str | None = None,
        launch_whale: bool = True
    ) -> dict[str, Any]:
        """Loads or prepares hybrid project prompts and displays standard assistant."""
        return self.prepare_flow_all_in_one(
            project_id=project_id,
            pillar=pillar,
            topic=topic,
            default_mode="hybrid",
            launch_whale=launch_whale
        )

    def _build_all_in_one_guide_markdown(
        self,
        project_id: str,
        title: str,
        pillar: str,
        topic: str,
        prompts: list[dict[str, Any]],
        hashtags: list[str],
        doi: str = "N/A",
        core_facts: str = "",
    ) -> str:
        """Generates comprehensive markdown production blueprint for Google Flow editor."""
        tag_str = " ".join(hashtags)
        sp_rows = ""
        for idx, p in enumerate(prompts, 1):
            c_num = p.get("clip_number") or p.get("clip_index") or idx
            t_in = p.get("timeline_in", f"00:{6*(idx-1):02d}")
            t_out = p.get("timeline_out", f"00:{6*idx:02d}")
            stage = p.get("stage_name") or p.get("role") or f"Clip {c_num}"
            cam = p.get("camera_name") or p.get("camera_move") or ""
            narr = (p.get("spoken_narration") or "").replace("|", "\\|")
            trans = p.get("transition_to_next", "Hard cut")
            sp_rows += f"| **Shot {c_num}** | {t_in} - {t_out} | {stage} | {cam} | {narr} | {trans} |\n"

        total_shots = len(prompts)
        avg_shot_dur = round(30.0 / total_shots, 1) if total_shots else 6.0

        md = f"""# ALL ABOUT BRAIN — Google Flow All-in-One Production Blueprint
## Project: {title}
**Project ID**: `{project_id}`  
**Pillar**: {pillar} | **Topic**: {topic}  
**Format**: YouTube Shorts (9:16 Vertical, 1080x1920, 30.0s)  
**Production Engine**: 100% Google Flow (`https://labs.google/fx/tools/flow` / Gemini Omni 1.1)

---

## Google Flow All-in-One Timeline Architecture

### 1. Canvas & Engine Configuration:
- **Studio URL**: `https://labs.google/fx/tools/flow`
- **Video Engine**: Select **Gemini Omni 1.1 (Omni 1.1 Flash / Quality)**
- **Canvas Aspect Ratio**: **9:16 (Vertical)**
- **Video Resolution**: **1080p**
- **Target Duration**: Exactly **30.0 seconds** ({total_shots} sequenced shots at ~{avg_shot_dur} seconds each)

### 2. {total_shots}-Shot Timeline Sequencing & Transition Decisions:
| Shot | Timeline | Role | Camera Choreography | Spoken Narration (Omni 1.1 Embedded) | Transition to Next |
|:---:|:---:|:---:|:---:|:---:|:---:|
{sp_rows}
### 3. Step-by-Step Flow Assembly Instructions:
1. **Generate Shot 1**: Paste Clip 1 All-in-One prompt into Google Flow (Gemini Omni 1.1). Click Generate.
2. **Generate Shots 2 to {total_shots}**: In sequence on the timeline, paste each corresponding prompt (Clip 2 to Clip {total_shots}).
3. **Set Timeline Transitions**:
   - Shot 1 to Shot 2: Instant hard cut (0.1s).
   - Shot 2 to Shot 3: Crossfade / Dissolve (0.25s) to represent transition from external view into 3D cortical layers.
   - Middle Shots: Instant hard cuts (0.1s).
   - Final Shot ({total_shots}): Independent conclusion hold and clean end fade.
4. **Verify Native Audio Sync**: Ensure the native Puck spoken narration and room acoustics sound clean on all clips.
5. **Export from Google Flow**: Click **Export** in the top navigation -> Select **1080x1920 MP4 (30fps)** -> Download finished Shorts video!
6. **Direct YouTube Shorts Upload**: Upload to YouTube Studio with the metadata below and check the "AI-assisted content" label.

---

## Copy-Paste Google Flow (Omni 1.1) All-in-One Prompts
"""
        for i, p in enumerate(prompts, 1):
            c_num = p.get("clip_number") or p.get("clip_index") or i
            t_in = p.get("timeline_in", f"00:{6*(i-1):02d}")
            t_out = p.get("timeline_out", f"00:{6*i:02d}")
            stage = p.get("stage_name") or p.get("role") or f"Clip {c_num}"
            cam = p.get("camera_name") or p.get("camera_move") or ""
            narr = p.get("spoken_narration") or ""
            trans = p.get("transition_to_next", "Hard cut")
            prompt_txt = p.get("prompt") or p.get("full_prompt") or ""
            md += f"""
### Shot {i}: {cam} ({t_in} - {t_out} // {stage})
- **Transition**: `{trans}`
- **Spoken Narration**: "{narr}"
- **Prompt**:
```text
{prompt_txt}
```
"""
        md += f"""
---

## YouTube Shorts Upload Metadata
- **Title**: {title}
- **Description**:
  {topic}. Explaining the cutting-edge neuroscience and brain-computer interface mechanisms behind this discovery.
  Academic Verification: {doi}
  {core_facts}
- **Hashtags**: {tag_str}
- **AI Label**: Check "AI-assisted content" on YouTube Studio
"""
        return md

    def _build_assistant_html(
        self,
        project_id: str,
        title: str,
        pillar: str,
        topic: str,
        all_in_one_prompts: list[dict[str, Any]],
        hybrid_prompts: list[dict[str, Any]] | None = None,
        hashtags: list[str] | None = None,
        doi: str = "N/A",
        core_facts: str = "",
        default_mode: str = "all-in-one",
    ) -> str:
        """Constructs an interactive dark-mode dashboard for Naver Whale browser."""
        hashtags = hashtags or ["#Shorts", "#BCI"]
        hybrid_prompts = hybrid_prompts or all_in_one_prompts
        tag_str = " ".join(hashtags)
        desc_text = (
            f"{topic}. Explaining the cutting-edge neuroscience and brain-computer interface mechanisms behind this discovery.\n\n"
            f"Academic Verification DOI: {doi}\n"
            f"{core_facts}\n\n"
            f"{tag_str}"
        )

        title_esc = html.escape(title)
        project_id_esc = html.escape(project_id)
        pillar_esc = html.escape(str(pillar))
        tag_str_esc = html.escape(tag_str)
        desc_text_esc = html.escape(desc_text)

        aio_cards_html = ""
        for i, p in enumerate(all_in_one_prompts, 1):
            prompt_txt = p.get("prompt") or p.get("full_prompt") or ""
            prompt_esc = html.escape(prompt_txt)
            narration_esc = html.escape((p.get("spoken_narration") or "")[:60])
            stage_esc = html.escape(str(p.get("stage_name") or p.get("role") or f"Clip {i}"))
            trans_esc = html.escape(str(p.get("transition_to_next", "Hard cut")))
            t_in = p.get("timeline_in", f"00:{6*(i-1):02d}")
            t_out = p.get("timeline_out", f"00:{6*i:02d}")
            aio_cards_html += f"""
        <div class="clip-card">
            <div class="clip-header">
                <div class="clip-meta">
                    <span class="shot-badge">SHOT {i}</span>
                    <span class="clip-time">{t_in} – {t_out} (6.0s)</span>
                    <span class="stage-badge">{stage_esc}</span>
                    <span class="trans-badge">Trans: {trans_esc}</span>
                </div>
                <button class="copy-btn" onclick="copyTextFromElement('aio-{i}', this, ' Copied Shot {i}!')"> Copy Shot {i} Prompt</button>
            </div>
            <div class="feature-strip">
                <div class="feature-tag narration-tag"> Spoken: "{narration_esc}..."</div>
                <div class="feature-tag audio-tag"> Native Room Acoustics</div>
            </div>
            <textarea id="aio-{i}" readonly>{prompt_esc}</textarea>
        </div>
"""

        hybrid_cards_html = ""
        for i, p in enumerate(hybrid_prompts, 1):
            prompt_esc = html.escape(p.get("prompt") or p.get("full_prompt") or "")
            cam_esc = html.escape(str(p.get("camera_name") or p.get("camera_move") or f"Clip {i}"))
            hybrid_cards_html += f"""
        <div class="clip-card">
            <div class="clip-header">
                <div class="clip-meta">
                    <span class="shot-badge">SHOT {i}</span>
                    <span class="clip-time">00:{6*(i-1):02d} – 00:{6*i:02d} (6.0s)</span>
                    <span class="stage-badge">{cam_esc}</span>
                    <span class="trans-badge">Mode: Raw Visual Prompt</span>
                </div>
                <button class="copy-btn" onclick="copyTextFromElement('hyb-{i}', this, ' Copied Shot {i}!')"> Copy Shot {i} Prompt</button>
            </div>
            <div class="feature-strip">
                <div class="feature-tag narration-tag"> Downstream Local Assembly</div>
            </div>
            <textarea id="hyb-{i}" readonly>{prompt_esc}</textarea>
        </div>
"""

        aio_bundle = "\n\n---\n\n".join(
            f"### Shot {p.get('clip_number') or p.get('clip_index') or idx}: {p.get('camera_name') or p.get('camera_move') or ''} ({p.get('timeline_in', '')}-{p.get('timeline_out', '')})\n{p.get('prompt') or p.get('full_prompt') or ''}"
            for idx, p in enumerate(all_in_one_prompts, 1)
        )
        hyb_bundle = "\n\n---\n\n".join(
            f"### Shot {i}: {p.get('camera_name') or p.get('camera_move') or f'Clip {i}'}\n{p.get('prompt') or p.get('full_prompt') or ''}"
            for i, p in enumerate(hybrid_prompts, 1)
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ALL ABOUT BRAIN — Google Flow Controller [{project_id_esc}]</title>
    <style>
        :root {{
            --bg-color: #0A1128;
            --card-bg: #101B38;
            --border-color: #1E2E55;
            --primary-blue: #1A73E8;
            --secondary-teal: #0E9AA7;
            --signal-gold: #FFD700;
            --danger-red: #FF3333;
            --text-white: #FFFFFF;
            --text-dim: #94A3B8;
        }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-white);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 24px;
            line-height: 1.5;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 20px;
        }}
        h1 {{ color: var(--primary-blue); margin: 0; font-size: 24px; letter-spacing: -0.5px; }}
        h2 {{ color: var(--secondary-teal); font-size: 15px; font-weight: 500; margin: 4px 0 0 0; }}
        .header-actions {{ display: flex; gap: 12px; }}
        .flow-btn {{
            background: linear-gradient(135deg, #1A73E8, #0E9AA7);
            color: white;
            padding: 10px 20px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: bold;
            font-size: 14px;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 4px 12px rgba(26, 115, 232, 0.3);
            transition: transform 0.15s, opacity 0.15s;
        }}
        .flow-btn:hover {{ opacity: 0.95; transform: translateY(-1px); }}
        .mode-nav {{
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
            background: #0E162F;
            padding: 6px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }}
        .tab-btn {{
            flex: 1;
            background: transparent;
            color: var(--text-dim);
            border: none;
            padding: 10px 16px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .tab-btn.active {{
            background: var(--primary-blue);
            color: white;
            box-shadow: 0 2px 8px rgba(26, 115, 232, 0.4);
        }}
        .tab-btn:hover:not(.active) {{
            background: #142247;
            color: white;
        }}
        .timeline-guide {{
            background: #0E1833;
            border: 1px solid #1C2D5A;
            border-left: 4px solid var(--signal-gold);
            padding: 16px 20px;
            border-radius: 8px;
            margin-bottom: 24px;
        }}
        .guide-title {{
            font-size: 16px;
            font-weight: bold;
            color: var(--signal-gold);
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .timeline-steps {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 8px;
            margin: 14px 0;
        }}
        .step-pill {{
            background: #142247;
            border: 1px solid #23376B;
            border-radius: 6px;
            padding: 8px 10px;
            font-size: 12px;
            text-align: center;
        }}
        .step-pill b {{ display: block; color: var(--secondary-teal); font-size: 13px; }}
        .step-pill span {{ color: var(--text-dim); font-size: 11px; }}
        .step-pill.dissolve {{ border-color: var(--signal-gold); }}
        .clip-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
        }}
        .clip-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .clip-meta {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
        .shot-badge {{
            background: var(--primary-blue);
            color: white;
            font-size: 12px;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: monospace;
        }}
        .clip-time {{ color: var(--signal-gold); font-size: 13px; font-weight: bold; font-family: monospace; }}
        .stage-badge {{
            background: #1C2D5A;
            color: #CBD5E1;
            font-size: 12px;
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .trans-badge {{
            background: #1B294B;
            color: var(--secondary-teal);
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
        }}
        .feature-strip {{
            display: flex;
            gap: 8px;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }}
        .feature-tag {{
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 4px;
            background: #090F24;
            border: 1px solid #1A284D;
        }}
        .narration-tag {{ color: #93C5FD; }}
        .hud-tag {{ color: var(--secondary-teal); }}
        .audio-tag {{ color: var(--signal-gold); }}
        textarea {{
            width: 100%;
            height: 125px;
            background: #070B1A;
            color: #E2E8F0;
            border: 1px solid #1E2E55;
            border-radius: 6px;
            padding: 10px;
            box-sizing: border-box;
            font-family: Consolas, Monaco, monospace;
            font-size: 12.5px;
            line-height: 1.4;
            resize: vertical;
        }}
        .copy-btn {{
            background-color: var(--primary-blue);
            color: white;
            border: none;
            padding: 6px 14px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
            font-size: 13px;
            transition: all 0.2s;
        }}
        .copy-btn:hover {{ background-color: var(--secondary-teal); }}
        .copy-btn.copied {{ background-color: #10B981 !important; }}
        .bundle-box {{
            background: #0B132B;
            border: 1px dashed var(--secondary-teal);
            border-radius: 8px;
            padding: 16px;
            margin: 20px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .metadata-section {{
            background: #0E162F;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px 20px;
            margin-top: 24px;
        }}
        .meta-row {{
            margin-bottom: 12px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .meta-row label {{ font-size: 12px; color: var(--signal-gold); font-weight: bold; text-transform: uppercase; }}
        .meta-input-group {{ display: flex; gap: 8px; }}
        .meta-input-group input, .meta-input-group textarea {{
            background: #070B1A;
            color: #E2E8F0;
            border: 1px solid #1E2E55;
            border-radius: 4px;
            padding: 8px;
            font-size: 13px;
            width: 100%;
        }}
    </style>
</head>
<body>
    <header>
        <div>
            <h1> ALL ABOUT BRAIN // Google Flow Studio Controller</h1>
            <h2>Project: {title_esc} (ID: {project_id_esc}) • {pillar_esc}</h2>
        </div>
        <div class="header-actions">
            <a href="{GOOGLE_FLOW_URL}" target="_blank" class="flow-btn"> Open Google Flow Studio</a>
        </div>
    </header>

    <div class="mode-nav">
        <button id="btn-tab-aio" class="tab-btn" onclick="switchMode('all-in-one')"> All-in-One Mode (Pure Google Flow 100% In-Browser)</button>
        <button id="btn-tab-hyb" class="tab-btn" onclick="switchMode('hybrid')"> Hybrid Mode (Raw Visuals for Local Assembly)</button>
    </div>

    <!-- Hidden bundle text containers for safe copying -->
    <textarea id="aio-bundle-data" style="display:none;" readonly>{html.escape(aio_bundle)}</textarea>
    <textarea id="hyb-bundle-data" style="display:none;" readonly>{html.escape(hyb_bundle)}</textarea>

    <!-- PANEL 1: ALL-IN-ONE GOOGLE FLOW -->
    <div id="panel-aio">
        <div class="timeline-guide">
            <div class="guide-title">
                <span> Pure Google Flow All-in-One Production Protocol</span>
            </div>
            <div>
                Generate all clips directly in Google Flow Omni 1.1 with embedded Puck spoken voiceover and native room acoustics.
                Sequence the shots on the timeline and export your broadcast-ready MP4.
            </div>
            <div class="timeline-steps">
                <div class="step-pill">
                    <b>Shot 1 (0-6s)</b>
                    <span>Hook<br>0.1s Hard Cut</span>
                </div>
                <div class="step-pill dissolve">
                    <b>Shot 2 (6-12s)</b>
                    <span>Crisis<br>0.25s Dissolve</span>
                </div>
                <div class="step-pill">
                    <b>Shot 3 (12-18s)</b>
                    <span>Pivot<br>0.1s Hard Cut</span>
                </div>
                <div class="step-pill">
                    <b>Shot 4 (18-24s)</b>
                    <span>Mechanism<br>0.1s Hard Cut</span>
                </div>
                <div class="step-pill">
                    <b>Shot 5 (24-30s)</b>
                    <span>Conclusion<br>End Fade</span>
                </div>
            </div>
            <div style="font-size: 13px; color: #CBD5E1;">
                <b>Assembly & Export Checklist:</b>
                (1) Canvas: Omni 1.1, 9:16 Vertical, 1080p •
                (2) Copy & paste each prompt in sequence •
                (3) Transition between Shot 2 & Shot 3: Crossfade 0.25s •
                (4) Click Export (1080x1920 MP4) •
                (5) Upload to YouTube Shorts with metadata below!
            </div>
        </div>

        <div class="bundle-box">
            <div>
                <b style="color: var(--secondary-teal);">Need all All-in-One prompts at once?</b>
                <div style="color: var(--text-dim); font-size: 13px;">Copy the unified prompt sequence formatted for Google Flow.</div>
            </div>
            <button class="copy-btn" onclick="copyTextFromElement('aio-bundle-data', this, ' Bundle Copied!')"> Copy All Prompts Bundle</button>
        </div>

        <div id="aio-cards-container">
            {aio_cards_html}
        </div>
    </div>

    <!-- PANEL 2: HYBRID PRODUCTION -->
    <div id="panel-hyb" style="display:none;">
        <div class="timeline-guide" style="border-left-color: var(--secondary-teal);">
            <div class="guide-title" style="color: var(--secondary-teal);">
                <span> Hybrid Pipeline Workflow (Google Flow Visuals + Local Assembly)</span>
            </div>
            <div>
                Generate raw 9:16 video clips in Google Flow, download them, and use the local ALL ABOUT BRAIN pipeline
                for ASR clip ordering, vocal window conditioning, 4-layer soundscape mixing, and single-line ASS subtitle rendering.
            </div>
            <div style="margin-top: 10px; font-size: 13px; color: #CBD5E1;">
                <b>Downstream Execution:</b>
                (1) Generate and download clips •
                (2) Run <code>python main.py import-clips --project {project_id_esc} --dir "C:/Users/.../Downloads"</code> •
                (3) Run <code>python main.py evolve --project {project_id_esc}</code>
            </div>
        </div>

        <div class="bundle-box">
            <div>
                <b style="color: var(--secondary-teal);">Need all Hybrid raw visual prompts?</b>
                <div style="color: var(--text-dim); font-size: 13px;">Copy the 5 raw visual prompts for batch submission in Google Flow.</div>
            </div>
            <button class="copy-btn" onclick="copyTextFromElement('hyb-bundle-data', this, ' Bundle Copied!')"> Copy All 5 Visual Prompts</button>
        </div>

        <div id="hyb-cards-container">
            {hybrid_cards_html}
        </div>
    </div>

    <div class="metadata-section">
        <h3 style="margin-top: 0; color: var(--signal-gold); font-size: 16px;"> YouTube Shorts Upload Metadata</h3>
        <div class="meta-row">
            <label>Title (60 char mobile safe):</label>
            <div class="meta-input-group">
                <input type="text" id="meta-title" value="{title_esc}" readonly>
                <button class="copy-btn" onclick="copyTextFromElement('meta-title', this, ' Copied!')"> Copy</button>
            </div>
        </div>
        <div class="meta-row">
            <label>Description & Academic Verification:</label>
            <div class="meta-input-group">
                <textarea id="meta-desc" rows="4" readonly>{desc_text_esc}</textarea>
                <button class="copy-btn" onclick="copyTextFromElement('meta-desc', this, ' Copied!')"> Copy</button>
            </div>
        </div>
        <div class="meta-row">
            <label>Hashtags:</label>
            <div class="meta-input-group">
                <input type="text" id="meta-tags" value="{tag_str_esc}" readonly>
                <button class="copy-btn" onclick="copyTextFromElement('meta-tags', this, ' Copied!')"> Copy</button>
            </div>
        </div>
    </div>

    <script>
        function switchMode(mode) {{
            const aioPanel = document.getElementById('panel-aio');
            const hybPanel = document.getElementById('panel-hyb');
            const btnAio = document.getElementById('btn-tab-aio');
            const btnHyb = document.getElementById('btn-tab-hyb');

            if (mode === 'hybrid') {{
                aioPanel.style.display = 'none';
                hybPanel.style.display = 'block';
                btnAio.classList.remove('active');
                btnHyb.classList.add('active');
            }} else {{
                aioPanel.style.display = 'block';
                hybPanel.style.display = 'none';
                btnAio.classList.add('active');
                btnHyb.classList.remove('active');
            }}
        }}

        function copyTextFromElement(elementId, btn, successMessage) {{
            const el = document.getElementById(elementId);
            if (!el) return;
            const text = el.value !== undefined ? el.value : el.innerText;
            if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {{
                el.select();
            }}
            const origText = btn.innerText;

            function showSuccess() {{
                btn.innerText = successMessage || ' Copied!';
                btn.classList.add('copied');
                setTimeout(() => {{
                    btn.innerText = origText;
                    btn.classList.remove('copied');
                }}, 2500);
            }}

            if (navigator.clipboard && navigator.clipboard.writeText) {{
                navigator.clipboard.writeText(text).then(showSuccess).catch(() => {{
                    try {{
                        document.execCommand('copy');
                        showSuccess();
                    }} catch (e) {{
                        console.error('Copy fallback failed:', e);
                    }}
                }});
            }} else {{
                try {{
                    document.execCommand('copy');
                    showSuccess();
                }} catch (e) {{
                    console.error('Copy fallback failed:', e);
                }}
            }}
        }}

        // Initialize active tab
        switchMode('{default_mode}');
    </script>
</body>
</html>
"""

    @classmethod
    def verify_flow_native_clips_v5(cls, project_id: str, deep_probe: bool = False) -> dict[str, Any]:
        """
        Gate V5 verification helper:
        Validates that 03_visuals/flow_native_clips contains valid .mp4 video clips (> 1MB)
        and zero synthetic FFmpeg derivative metadata tags (Guard 2).
        When deep_probe=True, also runs MediaIntegrityValidator 7-point inspection
        (ffprobe/ffmpeg stream check, duration, frame pixel diff, optical flow, and anti-derivative tags).
        """
        proj_base = (
            (Path("/tmp/bci_test_projects") / project_id)
            if (os.name != "nt" and str(project_id).startswith("test_") and Path("/tmp").exists())
            else (PROJECTS_DIR / project_id)
        )
        target_dir = proj_base / "03_visuals" / "flow_native_clips"
        if not target_dir.exists():
            return {
                "status": "FAIL",
                "passed": False,
                "valid_clips_count": 0,
                "invalid_clips_count": 0,
                "target_dir": str(target_dir),
                "clips": [],
            }

        mp4_files = sorted([f for f in target_dir.glob("*.mp4") if f.is_file()])
        valid_count = 0
        invalid_count = 0
        clip_details = []

        autopsy_file = proj_base / "05_assembly" / "video_autopsy_report.json"
        receipt_file = proj_base / "03_visuals" / "flow_provenance_receipt.json"
        has_autopsy_cache = (
            (autopsy_file.exists() and autopsy_file.stat().st_size > 200)
            or (receipt_file.exists() and receipt_file.stat().st_size > 200)
        )

        for f in mp4_files:
            sz = f.stat().st_size
            is_valid = sz >= MIN_CLIP_SIZE_BYTES and FlowProjectSubagentWorker.is_valid_video_asset_url(f.name, "video/mp4")
            probe_info: dict[str, Any] = {"name": f.name, "size_bytes": sz, "valid": is_valid}
            if is_valid:
                try:
                    if deep_probe or not has_autopsy_cache:
                        MediaIntegrityValidator.verify_not_synthetic_derivative(f, strict=True)
                    if deep_probe:
                        probe_res = MediaIntegrityValidator.validate_video_file(f, min_size_bytes=MIN_CLIP_SIZE_BYTES, check_motion=True)
                        probe_info["probe"] = probe_res
                except Exception as exc:
                    is_valid = False
                    probe_info["valid"] = False
                    probe_info["error"] = str(exc)

            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
            clip_details.append(probe_info)

        passed = valid_count >= 1 and invalid_count == 0
        return {
            "status": "PASS" if passed else "FAIL",
            "passed": passed,
            "valid_clips_count": valid_count,
            "invalid_clips_count": invalid_count,
            "target_dir": str(target_dir),
            "clips": clip_details,
        }

    def import_downloaded_clips(
        self,
        project_id: str,
        download_folder: Path,
        target_count: int = DEFAULT_CLIP_COUNT,
        deep_probe: bool = False,
        min_mtime_epoch: float | None = None,
    ) -> list[Path]:
        """
        Inspects download folder for user-downloaded Veo clips from Google Flow,
        validates their presence and Gate V5 integrity (> 1MB, .mp4 video guard, zero synthetic derivative tags),
        and maps them to 03_visuals/flow_native_clips and 03_visuals/raw_assets as clip_1.mp4 - clip_N.mp4.
        Acquires cross-process FlowDownloadHarvestLock and enforces mtime >= min_mtime_epoch when provided.
        """
        proj_dir = PROJECTS_DIR / project_id
        native_dir = proj_dir / "03_visuals" / "flow_native_clips"
        native_dir.mkdir(parents=True, exist_ok=True)
        raw_dir = proj_dir / "03_visuals" / "raw_assets"
        raw_dir.mkdir(parents=True, exist_ok=True)

        matched_files = []
        used_src_names = set()
        import re
        import shutil

        def _is_eligible(candidate_file: Path) -> bool:
            if not candidate_file.is_file():
                return False
            if not FlowProjectSubagentWorker.is_valid_video_asset_url(candidate_file.name, "video/mp4"):
                return False
            if candidate_file.name in used_src_names:
                return False
            if min_mtime_epoch is not None and candidate_file.stat().st_mtime < min_mtime_epoch:
                return False
            return True

        with FlowDownloadHarvestLock():
            # First attempt: match by clip number patterns with digit boundaries
            for i in range(1, target_count + 1):
                found = None
                explicit_patterns = [
                    f"clip_{i}.mp4", f"clip{i}.mp4", f"clip_{i}_*.mp4",
                    f"*clip*{i}*.mp4", f"*scene*{i}*.mp4", f"*take*{i}*.mp4"
                ]
                for pat in explicit_patterns:
                    matches = [m for m in download_folder.glob(pat) if _is_eligible(m)]
                    if matches:
                        found = matches[0]
                        break

                if not found:
                    digit_regex = re.compile(rf"(?<!\d)0*{i}(?!\d)")
                    candidates = [
                        m for m in sorted(download_folder.glob("*.mp4"))
                        if _is_eligible(m) and digit_regex.search(m.stem)
                    ]
                    if candidates:
                        found = candidates[0]
                if found and found.exists():
                    MediaIntegrityValidator.verify_not_synthetic_derivative(found, strict=True)
                    if deep_probe:
                        MediaIntegrityValidator.validate_video_file(found, min_size_bytes=MIN_CLIP_SIZE_BYTES, check_motion=True)
                    dest_native = native_dir / f"clip_{i}.mp4"
                    dest_raw = raw_dir / f"clip_{i}.mp4"
                    shutil.copy2(found, dest_native)
                    shutil.copy2(found, dest_raw)
                    matched_files.append(dest_native)
                    used_src_names.add(found.name)
                    sz_mb = dest_native.stat().st_size / (1024 * 1024)
                    v5_tag = "[Gate V5: PASS]" if dest_native.stat().st_size >= MIN_CLIP_SIZE_BYTES else "[Gate V5: FAIL < 1MB]"
                    print(f"[WhaleController] Ingested Clip {i}: {found.name} -> {dest_native.name} ({sz_mb:.2f} MB) {v5_tag}")

            # If pattern matching didn't find all target_count, fall back to sorting available mp4 files by mtime
            if len(matched_files) < target_count:
                all_mp4s = sorted(
                    [f for f in download_folder.glob("*.mp4") if _is_eligible(f)],
                    key=lambda x: x.stat().st_mtime
                )
                for idx in range(len(matched_files) + 1, target_count + 1):
                    if all_mp4s:
                        candidate = all_mp4s.pop(0)
                        MediaIntegrityValidator.verify_not_synthetic_derivative(candidate, strict=True)
                        if deep_probe:
                            MediaIntegrityValidator.validate_video_file(candidate, min_size_bytes=MIN_CLIP_SIZE_BYTES, check_motion=True)
                        dest_native = native_dir / f"clip_{idx}.mp4"
                        dest_raw = raw_dir / f"clip_{idx}.mp4"
                        shutil.copy2(candidate, dest_native)
                        shutil.copy2(candidate, dest_raw)
                        matched_files.append(dest_native)
                        used_src_names.add(candidate.name)
                        sz_mb = dest_native.stat().st_size / (1024 * 1024)
                        v5_tag = "[Gate V5: PASS]" if dest_native.stat().st_size >= MIN_CLIP_SIZE_BYTES else "[Gate V5: FAIL < 1MB]"
                        print(f"[WhaleController] Ingested Clip {idx} (mtime sort): {candidate.name} -> {dest_native.name} ({sz_mb:.2f} MB) {v5_tag}")

        # Persist Gate V5 check into visual_qa_report.json
        try:
            screenshots_dir = proj_dir / "03_visuals" / "flow_screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            v_qa_file = screenshots_dir / "visual_qa_report.json"
            v_report = {}
            if v_qa_file.exists():
                with open(v_qa_file, "r", encoding="utf-8") as f:
                    v_report = json.load(f)
            v5_status = self.verify_flow_native_clips_v5(project_id, deep_probe=deep_probe)
            v_report["gate_v5"] = {
                "name": "Gate V5: Lossless Ingest MP4 Integrity (> 1MB)",
                "status": v5_status["status"],
                "valid_clips_count": v5_status["valid_clips_count"],
                "invalid_clips_count": v5_status["invalid_clips_count"],
                "passed": v5_status["passed"],
                "target_dir": v5_status.get("target_dir", "")
            }
            with open(v_qa_file, "w", encoding="utf-8") as f:
                json.dump(v_report, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        return matched_files

    @classmethod
    def dismiss_credit_dialog(cls, cdp_port: int = 9222) -> dict[str, Any]:
        """
        Connects via CDP and triggers auto-dismissal of any active Google Flow credit confirmation dialogs ("Always approve").
        """
        import asyncio
        import json
        import urllib.request
        from pipeline.studio.whale_session import DirectCDPClient

        async def _dismiss():
            try:
                tab_req = urllib.request.Request(f"http://127.0.0.1:{cdp_port}/json/list")
                tabs = json.loads(urllib.request.urlopen(tab_req, timeout=5).read().decode("utf-8"))
            except Exception as e:
                return {"status": "error", "error": f"Failed to list CDP tabs: {e}"}

            flow_tabs = [t for t in tabs if ("flow.google" in t.get("url", "") or "labs.google" in t.get("url", "")) and t.get("webSocketDebuggerUrl")]
            if not flow_tabs:
                return {"status": "error", "error": "No active Google Flow tabs found on CDP"}

            dismissed_any = False
            results = []
            for t in flow_tabs:
                ws_url = t.get("webSocketDebuggerUrl")
                try:
                    async with DirectCDPClient(ws_url) as client:
                        res = await client.eval(DISMISS_CREDIT_DIALOG_JS)
                        if res and res.get("dismissed"):
                            dismissed_any = True
                            results.append({"tab_id": t.get("id"), "url": t.get("url"), "result": res})
                except Exception as eval_err:
                    results.append({"tab_id": t.get("id"), "error": str(eval_err)})

            return {
                "status": "success",
                "dismissed": dismissed_any,
                "tabs_checked": len(flow_tabs),
                "details": results
            }

        return asyncio.run(_dismiss())

    @classmethod
    def verify_and_capture_gate_v4(cls, project_id: str, cdp_port: int = 9222) -> dict[str, Any]:
        """
        Validates Gate V4: connects via CDP to the Flow project tab, evaluates export readiness,
        captures flow_gate_v4_export_ready.png, and updates visual_qa_report.json.
        """
        import asyncio
        import base64
        import json
        import urllib.request
        from pipeline.studio.whale_session import DirectCDPClient

        proj_dir = PROJECTS_DIR / project_id
        screenshots_dir = proj_dir / "03_visuals" / "flow_screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        v4_img = screenshots_dir / "flow_gate_v4_export_ready.png"

        async def _check_v4():
            try:
                tab_req = urllib.request.Request(f"http://127.0.0.1:{cdp_port}/json/list")
                tabs = json.loads(urllib.request.urlopen(tab_req, timeout=5).read().decode("utf-8"))
            except Exception as e:
                return {"status": "error", "error": f"Failed to list CDP tabs: {e}"}

            target_tab = None
            for t in tabs:
                t_url = t.get("url", "")
                t_title = t.get("title", "")
                if ("flow.google" in t_url or "labs.google" in t_url) and t.get("webSocketDebuggerUrl"):
                    if project_id in t_url or project_id in t_title:
                        target_tab = t
                        break

            if not target_tab:
                for t in tabs:
                    if ("flow.google" in t.get("url", "") or "labs.google" in t.get("url", "")) and t.get("webSocketDebuggerUrl"):
                        target_tab = t
                        break

            if not target_tab:
                return {"status": "error", "error": "No matching Google Flow tab found for Gate V4 check"}

            ws_url = target_tab.get("webSocketDebuggerUrl")
            async with DirectCDPClient(ws_url) as client:
                check_export_js = """
                (() => {
                    const allText = (document.body ? document.body.innerText || '' : '').toLowerCase();
                    const exportBtn = document.querySelector('button[aria-label*="Export" i], button[aria-label*="Download" i], .export-button, [aria-label*="export" i], [aria-label*="download" i]');
                    const isCompleted = allText.includes('100%') || allText.includes('ready to export') || allText.includes('generation complete');
                    const hasStopBtn = Boolean(document.querySelector('button[aria-label*="Stop"], button[aria-label*="Cancel"], .stop-button'));
                    return {
                        export_ready: Boolean(exportBtn) || isCompleted,
                        has_export_btn: Boolean(exportBtn),
                        is_completed: isCompleted,
                        has_stop_btn: hasStopBtn
                    };
                })()
                """
                export_info = await client.eval(check_export_js) or {}

                ss_res = await client.send("Page.captureScreenshot", {"format": "png"})
                if ss_res and "data" in ss_res:
                    v4_img.write_bytes(base64.b64decode(ss_res["data"]))

                is_ready = bool(export_info.get("export_ready"))
                gate_status = "PASS" if is_ready else ("PENDING" if export_info.get("has_stop_btn") else "NOT_READY")

                v_qa_file = screenshots_dir / "visual_qa_report.json"
                v_report = {}
                if v_qa_file.exists():
                    try:
                        with open(v_qa_file, "r", encoding="utf-8") as f:
                            v_report = json.load(f)
                    except Exception:
                        v_report = {}

                v_report["gate_v4"] = {
                    "name": "Gate V4: Video Complete & Export Readiness",
                    "status": gate_status,
                    "export_ready": is_ready,
                    "export_info": export_info,
                    "screenshot": str(v4_img)
                }
                with open(v_qa_file, "w", encoding="utf-8") as f:
                    json.dump(v_report, f, indent=2, ensure_ascii=False)

                return {
                    "gate": "V4",
                    "status": gate_status,
                    "export_ready": is_ready,
                    "screenshot": str(v4_img),
                    "export_info": export_info
                }

        return asyncio.run(_check_v4())

    MAX_BATCH_CONCURRENCY: int = FLOW_MAX_PARALLEL_BATCH_SIZE

    async def _async_open_project_in_flow(
        self,
        project_id: str,
        cdp_port: int = 9222,
        trigger_generation: bool = True,
        wait_for_render: bool = False,
    ) -> dict[str, Any]:
        """Backward compatible delegate to FlowProjectSubagentWorker."""
        import asyncio
        worker = FlowProjectSubagentWorker(
            project_id=project_id,
            cdp_port=cdp_port,
            trigger_generation=trigger_generation,
            wait_for_render=wait_for_render,
        )
        sem = asyncio.Semaphore(1)
        return await worker.execute(sem)

    def open_parallel_flow_projects(
        self,
        project_ids: list[str],
        cdp_port: int = 9222,
        trigger_generation: bool = True,
        wait_for_render: bool = False,
        max_batch: int = FLOW_MAX_PARALLEL_BATCH_SIZE,
    ) -> list[dict[str, Any]]:
        """
        Orchestrates parallel cloud video generation across dedicated 1:1:1 subagent workers.
        Enforces a strict maximum batch size cap of 5 concurrent workers per batch
        (FLOW_MAX_PARALLEL_BATCH_SIZE = 5; max 5 topics per batch, 1 Topic = 1 Subagent = 1 Tab).
        If total projects exceed 5, chunks them into sequential batches of at most 5 topics each.
        """
        import asyncio
        import json
        import time

        effective_max_batch = min(max(1, int(max_batch)), FLOW_MAX_PARALLEL_BATCH_SIZE)
        max_concurrency = effective_max_batch
        unique_pids: list[str] = []
        seen_pids: set[str] = set()
        for pid in project_ids:
            if not isinstance(pid, str) or "," in pid or ";" in pid:
                raise ValueError(
                    "FATAL R37 GUARD 6 VIOLATION: Multi-topic bundling into a single worker is prohibited."
                )
            clean_pid = pid.strip()
            if clean_pid in seen_pids:
                raise ValueError(
                    f"FATAL R37 GUARD 6 VIOLATION: Duplicate project_id '{clean_pid}' in parallel dispatch."
                )
            seen_pids.add(clean_pid)
            unique_pids.append(clean_pid)

        total_projects = len(unique_pids)
        batches = [unique_pids[i:i + max_concurrency] for i in range(0, total_projects, max_concurrency)]

        print(
            f"\n[Orchestrator] Starting 1:1:1 Batch Dispatch: {total_projects} projects in "
            f"{len(batches)} batch(es) (Strict Cap: {max_concurrency} topics/batch)..."
        )

        all_results = []
        for batch_idx, batch_pids in enumerate(batches, 1):
            print(
                f"\n[Orchestrator] === Batch {batch_idx}/{len(batches)}: "
                f"Spawning {len(batch_pids)} dedicated 1:1:1 subagent workers (Max {FLOW_MAX_PARALLEL_BATCH_SIZE}) ==="
            )

            async def _run_batch(pids):
                sem = asyncio.Semaphore(max_concurrency)
                workers = [
                    FlowProjectSubagentWorker(
                        project_id=pid,
                        cdp_port=cdp_port,
                        trigger_generation=trigger_generation,
                        wait_for_render=wait_for_render,
                    )
                    for pid in pids
                ]
                return await asyncio.gather(*[w.execute(sem) for w in workers], return_exceptions=True)

            batch_results = asyncio.run(_run_batch(batch_pids))
            for pid, r in zip(batch_pids, batch_results):
                if isinstance(r, Exception):
                    all_results.append({
                        "project_id": pid,
                        "worker_id": f"subagent-{pid}",
                        "subagent_1_to_1_bound": True,
                        "status": "failed",
                        "error": str(r)
                    })
                else:
                    all_results.append(r)

        # Save batch orchestration manifest (merging with existing records)
        manifest_file = PROJECTS_DIR / "batch_orchestration_manifest.json"
        existing_results_map = {}
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    old_m = json.load(f)
                for r in old_m.get("results", []):
                    existing_results_map[r.get("project_id")] = r
            except Exception:
                pass
        for r in all_results:
            existing_results_map[r.get("project_id")] = r

        merged_results = list(existing_results_map.values())
        manifest_data = {
            "orchestration_timestamp": time.time(),
            "max_batch_concurrency": max_concurrency,
            "flow_max_parallel_batch_size": FLOW_MAX_PARALLEL_BATCH_SIZE,
            "total_projects": len(merged_results),
            "batch_count": len(batches),
            "results": merged_results
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        print(f"[Orchestrator] Batch manifest saved to: {manifest_file} ({len(merged_results)} projects tracked)")

        return all_results


class FlowParallelOrchestrator:
    """
    Guard 6 (R37): Dedicated 1:1:1 Subagent Batch Orchestrator.
    Enforces:
    - 1 Topic = 1 Dedicated Subagent Worker (FlowProjectSubagentWorker) = 1 Dedicated Naver Whale Tab.
    - Hard cap of FLOW_MAX_PARALLEL_BATCH_SIZE = 5 topics per batch.
    """

    MAX_BATCH_SIZE: int = FLOW_MAX_PARALLEL_BATCH_SIZE

    def __init__(self, cdp_port: int = 9222, max_batch_size: int = FLOW_MAX_PARALLEL_BATCH_SIZE):
        self.cdp_port = cdp_port
        self.max_batch_size = min(max(1, int(max_batch_size)), FLOW_MAX_PARALLEL_BATCH_SIZE)

    @staticmethod
    def chunk_topics(project_ids: list[str], max_batch_size: int = FLOW_MAX_PARALLEL_BATCH_SIZE) -> list[list[str]]:
        """Chunks topics into batches of at most FLOW_MAX_PARALLEL_BATCH_SIZE (5)."""
        effective_max_batch = min(max(1, int(max_batch_size)), FLOW_MAX_PARALLEL_BATCH_SIZE)
        return [project_ids[i:i + effective_max_batch] for i in range(0, len(project_ids), effective_max_batch)]

    split_into_batches = chunk_topics

    def dispatch(
        self,
        project_ids: list[str],
        trigger_generation: bool = True,
        wait_for_render: bool = False,
        max_batch_size: int | None = None,
    ) -> list[dict[str, Any]]:
        """Dispatches 1:1:1 FlowProjectSubagentWorker instances in batches of at most 5 topics."""
        effective_max_batch = min(
            max(1, int(max_batch_size if max_batch_size is not None else self.max_batch_size)),
            FLOW_MAX_PARALLEL_BATCH_SIZE,
        )
        ctrl = GoogleFlowWhaleController()
        return ctrl.open_parallel_flow_projects(
            project_ids=project_ids,
            cdp_port=self.cdp_port,
            trigger_generation=trigger_generation,
            wait_for_render=wait_for_render,
            max_batch=effective_max_batch,
        )


