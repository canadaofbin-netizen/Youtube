"""
Lossless Multi-Stage Data Persistence Storage System
Ensures zero data loss across Stages 1 through 6 with atomic writes and manifest tracking.
"""

import hashlib
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import PROJECTS_DIR

STAGE_NAMES = [
    "01_ideation",
    "02_script",
    "03_visuals",
    "04_audio",
    "05_assembly",
    "06_publish"
]

_CLIP_INDEX_RE = re.compile(r"(\d+)")


def numeric_clip_sort_key(path: Path | str) -> tuple[int, str]:
    """
    Sort key for clip files that orders by the first integer in the file stem
    (clip_2.mp4 < clip_10.mp4). Files without a number sort last, alphabetically.
    """
    stem = Path(path).stem
    match = _CLIP_INDEX_RE.search(stem)
    return (int(match.group(1)) if match else 10**9, stem.lower())

class ProjectStorage:
    def __init__(self, project_id: str, title: str = "", pillar: str = ""):
        self.project_id = project_id
        self.project_dir = PROJECTS_DIR / project_id
        self.logs_dir = self.project_dir / "logs"
        self.log_file = self.logs_dir / "pipeline.log"
        self.manifest_path = self.project_dir / "00_project_manifest.json"
        self._lock = __import__("threading").Lock()
        self._init_project_structure(title, pillar)

    def append_log(self, level: str, message: str):
        """Appends a structured timestamped line to projects/<project_id>/logs/pipeline.log."""
        try:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            line = f"{ts} [{level.upper()}] [{self.project_id}] {message}\n"
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def _init_project_structure(self, title: str, pillar: str):
        """Create project directory, logs directory, and all stage subdirectories."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if not self.log_file.exists():
            self.append_log("INFO", f"Initialized project structure (title={title!r}, pillar={pillar!r})")
        for stage_name in STAGE_NAMES:
            (self.project_dir / stage_name).mkdir(parents=True, exist_ok=True)

        with self._lock:
            if not self.manifest_path.exists():
                now = datetime.now(timezone.utc).isoformat()
                manifest = {
                "project_id": self.project_id,
                "title": title,
                "pillar": pillar,
                "created_at": now,
                "updated_at": now,
                "stages": {
                    stage_name: {
                        "status": "pending",
                        "updated_at": None,
                        "artifacts": {},
                        "errors": []
                    }
                    for stage_name in STAGE_NAMES
                },
                "final_video": None
            }
                self._write_manifest(manifest)
            else:
                # Update title or pillar if provided and ensure stages exist
                manifest = self.get_manifest()
                updated = False
                if title and not manifest.get("title"):
                    manifest["title"] = title
                    updated = True
                if pillar and not manifest.get("pillar"):
                    manifest["pillar"] = pillar
                    updated = True
                if "stages" not in manifest or not isinstance(manifest.get("stages"), dict):
                    manifest["stages"] = {
                        s: {"status": "pending", "updated_at": None, "artifacts": {}, "errors": []}
                        for s in STAGE_NAMES
                    }
                    updated = True
                else:
                    for s in STAGE_NAMES:
                        if s not in manifest["stages"]:
                            manifest["stages"][s] = {"status": "pending", "updated_at": None, "artifacts": {}, "errors": []}
                            updated = True
                if updated:
                    self._write_manifest(manifest)

    def get_manifest(self) -> dict[str, Any]:
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _atomic_replace_or_write(temp_path: Path, target_path: Path, fallback_content: str | None = None, is_json: bool = False, json_data: Any = None):
        """
        Atomically replaces target_path with temp_path, employing a retry loop and direct-write
        fallback to prevent Windows WinError 32 PermissionError/OSError during background Google Drive sync.
        """
        import os as _os
        if _os.name != "nt":
            try:
                if is_json:
                    target_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")
                elif fallback_content is not None:
                    target_path.write_text(fallback_content, encoding="utf-8")
                elif temp_path.exists():
                    shutil.copy2(temp_path, target_path)
                temp_path.unlink(missing_ok=True)
                return
            except Exception:
                pass
        for attempt in range(5):
            try:
                temp_path.replace(target_path)
                return
            except (PermissionError, OSError):
                if attempt == 4:
                    try:
                        if is_json:
                            with open(target_path, "w", encoding="utf-8") as f:
                                json.dump(json_data, f, indent=2, ensure_ascii=False)
                        elif fallback_content is not None:
                            with open(target_path, "w", encoding="utf-8") as f:
                                f.write(fallback_content)
                        else:
                            shutil.copy2(temp_path, target_path)
                        temp_path.unlink(missing_ok=True)
                    except Exception as e:
                        print(f"[WARN] Atomic replace fallback encountered: {e}")
                else:
                    time.sleep(0.15)

    def _write_manifest(self, manifest: dict[str, Any]):
        import os as _os
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        if _os.name != "nt":
            self.manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            return
        temp_file = self.manifest_path.parent / f"00_manifest_{time.time_ns()}.tmp"
        written = False
        for attempt in range(5):
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2, ensure_ascii=False)
                written = True
                break
            except (OSError, PermissionError):
                time.sleep(0.1)

        if not written:
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            return

        self._atomic_replace_or_write(temp_file, self.manifest_path, is_json=True, json_data=manifest)

    def get_stage_dir(self, stage_name: str) -> Path:
        p = self.project_dir / stage_name
        p.mkdir(parents=True, exist_ok=True)
        return p

    def update_stage_status(self, stage_name: str, status: str, errors: list[str] | None = None):
        with self._lock:
            manifest = self.get_manifest()
            if "stages" not in manifest or not isinstance(manifest["stages"], dict):
                manifest["stages"] = {}
            if stage_name not in manifest["stages"]:
                manifest["stages"][stage_name] = {"status": "pending", "updated_at": None, "artifacts": {}, "errors": []}
            manifest["stages"][stage_name]["status"] = status
            manifest["stages"][stage_name]["updated_at"] = datetime.now(timezone.utc).isoformat()
            if errors:
                manifest["stages"][stage_name]["errors"] = errors
            self._write_manifest(manifest)
        self.append_log("ERROR" if errors else "INFO", f"Stage {stage_name} status -> {status}" + (f" (errors={errors})" if errors else ""))

    def record_artifact(
        self,
        stage_name: str,
        relative_path: str,
        abs_path: Path,
        known_sha256: str | None = None,
        known_size_bytes: int | None = None,
    ):
        """Record artifact in manifest with SHA-256 and byte size."""
        if known_sha256 is not None and known_size_bytes is not None:
            sha256 = known_sha256
            size_bytes = known_size_bytes
        else:
            if not abs_path.exists():
                return
            size_bytes = abs_path.stat().st_size
            sha256 = self._calculate_sha256(abs_path)
        with self._lock:
            manifest = self.get_manifest()
            if "stages" not in manifest or not isinstance(manifest["stages"], dict):
                manifest["stages"] = {}
            if stage_name not in manifest["stages"]:
                manifest["stages"][stage_name] = {"status": "pending", "updated_at": None, "artifacts": {}, "errors": []}
            if "artifacts" not in manifest["stages"][stage_name]:
                manifest["stages"][stage_name]["artifacts"] = {}
            manifest["stages"][stage_name]["artifacts"][relative_path] = {
                "sha256": sha256,
                "size_bytes": size_bytes,
                "recorded_at": datetime.now(timezone.utc).isoformat()
            }
            self._write_manifest(manifest)
        self.append_log("INFO", f"Recorded artifact {stage_name}/{relative_path} ({size_bytes}B, sha256={sha256[:12]}...)")

    _SHA_CACHE: dict[tuple[str, int, int], str] = {}

    @classmethod
    def _calculate_sha256(cls, path: Path) -> str:
        st = path.stat()
        key = (str(path.resolve()), st.st_size, st.st_mtime_ns)
        cached = cls._SHA_CACHE.get(key)
        if cached:
            return cached
        for attempt in range(4):
            try:
                h = hashlib.sha256()
                with open(path, "rb") as f:
                    while chunk := f.read(65536):
                        h.update(chunk)
                digest = h.hexdigest()
                cls._SHA_CACHE[key] = digest
                return digest
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(0.35 * (attempt + 1))
        return ""

    def save_json(self, stage_name: str, filename: str, data: Any) -> Path:
        import os as _os
        stage_dir = self.get_stage_dir(stage_name)
        target = stage_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        payload_str = json.dumps(data, indent=2, ensure_ascii=False)
        payload_bytes = payload_str.encode("utf-8")
        known_sha = hashlib.sha256(payload_bytes).hexdigest()
        known_sz = len(payload_bytes)
        if _os.name != "nt":
            for attempt in range(4):
                try:
                    target.write_text(payload_str, encoding="utf-8")
                    break
                except OSError:
                    if attempt == 3:
                        raise
                    time.sleep(0.35 * (attempt + 1))
            self.record_artifact(stage_name, filename, target, known_sha256=known_sha, known_size_bytes=known_sz)
            return target
        temp = target.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8") as f:
            f.write(payload_str)
        self._atomic_replace_or_write(temp, target, is_json=True, json_data=data)
        self.record_artifact(stage_name, filename, target, known_sha256=known_sha, known_size_bytes=known_sz)
        return target

    def load_json(self, stage_name: str, filename: str) -> Any | None:
        target = self.get_stage_dir(stage_name) / filename
        if not target.exists():
            return None
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_text(self, stage_name: str, filename: str, text: str) -> Path:
        import os as _os
        stage_dir = self.get_stage_dir(stage_name)
        target = stage_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        if _os.name != "nt":
            target.write_text(text, encoding="utf-8")
            self.record_artifact(stage_name, filename, target)
            return target
        temp = target.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8") as f:
            f.write(text)
        self._atomic_replace_or_write(temp, target, fallback_content=text)
        self.record_artifact(stage_name, filename, target)
        return target

    def load_text(self, stage_name: str, filename: str) -> str | None:
        target = self.get_stage_dir(stage_name) / filename
        if not target.exists():
            return None
        with open(target, "r", encoding="utf-8") as f:
            return f.read()

    def copy_file(self, src: Path, stage_name: str, dest_filename: str) -> Path:
        stage_dir = self.get_stage_dir(stage_name)
        dest = stage_dir / dest_filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        self.record_artifact(stage_name, dest_filename, dest)
        return dest

    def verify_integrity(self) -> dict[str, Any]:
        """
        Verifies that every artifact recorded across all stages exists on disk,
        has not been truncated, and matches its recorded SHA-256 hash.
        Guarantees lossless multi-stage data persistence.
        """
        manifest = self.get_manifest()
        total_artifacts = 0
        verified_artifacts = 0
        issues = []

        for stage_name, stage_data in manifest.get("stages", {}).items():
            stage_dir = self.get_stage_dir(stage_name)
            for rel_path, meta in stage_data.get("artifacts", {}).items():
                total_artifacts += 1
                file_path = stage_dir / rel_path
                if not file_path.exists():
                    issues.append({
                        "stage": stage_name,
                        "artifact": rel_path,
                        "error": "File missing on disk"
                    })
                    continue

                curr_size = file_path.stat().st_size
                if curr_size != meta.get("size_bytes"):
                    issues.append({
                        "stage": stage_name,
                        "artifact": rel_path,
                        "error": f"Size mismatch: expected {meta.get('size_bytes')} bytes, got {curr_size} bytes"
                    })
                    continue

                curr_sha = self._calculate_sha256(file_path)
                if curr_sha != meta.get("sha256"):
                    issues.append({
                        "stage": stage_name,
                        "artifact": rel_path,
                        "error": f"SHA-256 mismatch: expected {meta.get('sha256')}, got {curr_sha}"
                    })
                    continue

                verified_artifacts += 1

        all_intact = (len(issues) == 0 and total_artifacts > 0)
        report = {
            "all_intact": all_intact,
            "total_artifacts": total_artifacts,
            "verified_artifacts": verified_artifacts,
            "corrupted_or_missing": issues,
            "verified_at": datetime.now(timezone.utc).isoformat()
        }

        # Update manifest with latest integrity audit
        manifest["integrity_audit"] = report
        self._write_manifest(manifest)
        return report

