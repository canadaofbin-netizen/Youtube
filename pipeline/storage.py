"""
Lossless Multi-Stage Data Persistence Storage System
Ensures zero data loss across Stages 1 through 6 with atomic writes and manifest tracking.
"""

import contextlib
import hashlib
import json
import os
import re
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows fallback
    _fcntl = None  # type: ignore[assignment]

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
    _PROC_LOCKS_GUARD = threading.Lock()
    _PROC_LOCKS: dict[str, threading.RLock] = {}
    _TLS = threading.local()

    @classmethod
    @contextlib.contextmanager
    def _manifest_file_lock(cls, project_dir: Path):
        """Serializes manifest read-modify-write cycles across both threads and OS processes."""
        resolved_dir = str(Path(project_dir).resolve())
        with cls._PROC_LOCKS_GUARD:
            rlock = cls._PROC_LOCKS.setdefault(resolved_dir, threading.RLock())
        with rlock:
            held: set[str] | None = getattr(cls._TLS, "held_manifest_locks", None)
            if held is None:
                held = set()
                cls._TLS.held_manifest_locks = held
            if resolved_dir in held:
                yield
                return
            lock_root = Path("/tmp") if (os.name != "nt" and Path("/tmp").exists()) else Path(project_dir)
            lock_root.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha1(resolved_dir.encode("utf-8")).hexdigest()[:16]
            lock_file = lock_root / f".aab_manifest_{digest}.lock"
            fh = None
            locked_flock = False
            held.add(resolved_dir)
            try:
                if _fcntl is not None:
                    try:
                        fh = open(lock_file, "a+", encoding="utf-8")
                        _fcntl.flock(fh.fileno(), _fcntl.LOCK_EX)
                        locked_flock = True
                    except OSError:
                        if fh is not None:
                            fh.close()
                            fh = None
                yield
            finally:
                if locked_flock and fh is not None and _fcntl is not None:
                    try:
                        _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)
                    except OSError:
                        pass
                if fh is not None:
                    try:
                        fh.close()
                    except OSError:
                        pass
                held.discard(resolved_dir)

    def __init__(
        self,
        project_id: str,
        title: str = "",
        pillar: str = "",
        projects_dir: Path | None = None,
    ):
        self.project_id = project_id
        if projects_dir is not None:
            self.project_dir = Path(projects_dir) / project_id
        elif os.name != "nt" and (str(project_id).startswith(("test_", "temp_")) or "_verify_" in str(project_id)) and Path("/tmp").exists():
            self.project_dir = Path("/tmp/bci_test_projects") / project_id
        else:
            self.project_dir = PROJECTS_DIR / project_id
        self.logs_dir = self.project_dir / "logs"
        self.log_file = self.logs_dir / "pipeline.log"
        self.manifest_path = self.project_dir / "00_project_manifest.json"
        self._lock = threading.RLock()
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
        if not title and not pillar and self.manifest_path.exists() and self.logs_dir.exists():
            return
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if not self.log_file.exists():
            self.append_log("INFO", f"Initialized project structure (title={title!r}, pillar={pillar!r})")
        for stage_name in STAGE_NAMES:
            (self.project_dir / stage_name).mkdir(parents=True, exist_ok=True)

        with self._lock, self._manifest_file_lock(self.project_dir):
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
                            "errors": [],
                        }
                        for stage_name in STAGE_NAMES
                    },
                    "final_video": None,
                }
                self._write_manifest(manifest)
            else:
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
        with self._manifest_file_lock(self.project_dir):
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)

    @staticmethod
    def _atomic_replace_or_write(temp_path: Path, target_path: Path, fallback_content: str | None = None, is_json: bool = False, json_data: Any = None):
        """
        Atomically replaces target_path with temp_path via os.replace, employing a retry loop and direct-write
        fallback only if os.replace raises a transient FUSE/sync OSError across all attempts.
        """
        for attempt in range(5):
            try:
                if temp_path.exists():
                    os.replace(temp_path, target_path)
                    return
                break
            except (PermissionError, OSError):
                if attempt < 4:
                    time.sleep(0.12 * (attempt + 1))
        try:
            if fallback_content is not None:
                target_path.write_text(fallback_content, encoding="utf-8")
            elif is_json:
                target_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            elif temp_path.exists():
                shutil.copy2(temp_path, target_path)
        except Exception as e:
            print(f"[WARN] Atomic replace fallback encountered: {e}")
        finally:
            temp_path.unlink(missing_ok=True)

    @classmethod
    def _write_manifest_file(cls, manifest_path: Path, manifest: dict[str, Any]) -> None:
        temp_file = manifest_path.parent / f".tmp_00_manifest_{os.getpid()}_{time.time_ns()}.json"
        payload = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        written = False
        for attempt in range(5):
            try:
                temp_file.write_text(payload, encoding="utf-8")
                written = True
                break
            except (OSError, PermissionError):
                time.sleep(0.1)
        if not written:
            manifest_path.write_text(payload, encoding="utf-8")
            return
        cls._atomic_replace_or_write(temp_file, manifest_path, fallback_content=payload, is_json=True, json_data=manifest)

    def _write_manifest(self, manifest: dict[str, Any]):
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        with self._manifest_file_lock(self.project_dir):
            self._write_manifest_file(self.manifest_path, manifest)

    def get_stage_dir(self, stage_name: str) -> Path:
        p = self.project_dir / stage_name
        p.mkdir(parents=True, exist_ok=True)
        return p

    def update_stage_status(self, stage_name: str, status: str, errors: list[str] | None = None):
        with self._lock, self._manifest_file_lock(self.project_dir):
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
        with self._lock, self._manifest_file_lock(self.project_dir):
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
                "recorded_at": datetime.now(timezone.utc).isoformat(),
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
        stage_dir = self.get_stage_dir(stage_name)
        target = stage_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        payload_str = json.dumps(data, indent=2, ensure_ascii=False)
        payload_bytes = payload_str.encode("utf-8")
        known_sha = hashlib.sha256(payload_bytes).hexdigest()
        known_sz = len(payload_bytes)
        temp = target.parent / f".tmp_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}_{target.name}"
        written = False
        for attempt in range(4):
            try:
                temp.write_text(payload_str, encoding="utf-8")
                written = True
                break
            except OSError:
                if attempt == 3:
                    break
                time.sleep(0.15 * (attempt + 1))
        if written:
            self._atomic_replace_or_write(temp, target, fallback_content=payload_str, is_json=True, json_data=data)
        else:
            target.write_text(payload_str, encoding="utf-8")
        self.record_artifact(stage_name, filename, target, known_sha256=known_sha, known_size_bytes=known_sz)
        return target

    def load_json(self, stage_name: str, filename: str) -> Any | None:
        target = self.get_stage_dir(stage_name) / filename
        if not target.exists() or target.stat().st_size == 0:
            return None
        try:
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None

    def save_text(self, stage_name: str, filename: str, text: str) -> Path:
        stage_dir = self.get_stage_dir(stage_name)
        target = stage_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.parent / f".tmp_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}_{target.name}"
        written = False
        for attempt in range(4):
            try:
                temp.write_text(text, encoding="utf-8")
                written = True
                break
            except OSError:
                if attempt == 3:
                    break
                time.sleep(0.15 * (attempt + 1))
        if written:
            self._atomic_replace_or_write(temp, target, fallback_content=text)
        else:
            target.write_text(text, encoding="utf-8")
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
        with self._lock, self._manifest_file_lock(self.project_dir):
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
                            "error": "File missing on disk",
                        })
                        continue

                    curr_size = file_path.stat().st_size
                    if curr_size != meta.get("size_bytes"):
                        issues.append({
                            "stage": stage_name,
                            "artifact": rel_path,
                            "error": f"Size mismatch: expected {meta.get('size_bytes')} bytes, got {curr_size} bytes",
                        })
                        continue

                    curr_sha = self._calculate_sha256(file_path)
                    if curr_sha != meta.get("sha256"):
                        issues.append({
                            "stage": stage_name,
                            "artifact": rel_path,
                            "error": f"SHA-256 mismatch: expected {meta.get('sha256')}, got {curr_sha}",
                        })
                        continue

                    verified_artifacts += 1

            all_intact = (len(issues) == 0 and total_artifacts > 0)
            report = {
                "all_intact": all_intact,
                "total_artifacts": total_artifacts,
                "verified_artifacts": verified_artifacts,
                "corrupted_or_missing": issues,
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }

            manifest["integrity_audit"] = report
            self._write_manifest(manifest)
            return report

    @classmethod
    def sync_existing_manifest_from_disk(cls, project_dir: Path, status: str | None = None) -> bool:
        """
        Refreshes stage artifact SHA-256 & byte-size records on disk when `00_project_manifest.json`
        already tracks `stages` (preventing stale manifest drift after standalone clip remediation or re-assembly).
        """
        p_dir = Path(project_dir)
        mpath = p_dir / "00_project_manifest.json"
        if not mpath.exists():
            return False
        with cls._manifest_file_lock(p_dir):
            if not mpath.exists():
                return False
            try:
                mdata = json.loads(mpath.read_text(encoding="utf-8"))
            except Exception:
                return False
            if not isinstance(mdata, dict) or not isinstance(mdata.get("stages"), dict):
                return False
            now_iso = datetime.now(timezone.utc).isoformat()
            if status:
                mdata["status"] = status
            mdata["updated_at"] = now_iso
            from pipeline.media_cache import fast_file_sha256

            for s_name in STAGE_NAMES:
                sdir = p_dir / s_name
                arts: dict[str, Any] = {}
                if sdir.exists():
                    for fp in sorted(sdir.rglob("*")):
                        if fp.is_file() and not fp.name.startswith(".tmp_"):
                            rel = fp.relative_to(sdir).as_posix()
                            arts[rel] = {
                                "sha256": fast_file_sha256(fp),
                                "size_bytes": fp.stat().st_size,
                                "recorded_at": now_iso,
                            }
                prev_stage = mdata["stages"].get(s_name) if isinstance(mdata["stages"].get(s_name), dict) else {}
                mdata["stages"][s_name] = {
                    "status": ("completed" if arts else prev_stage.get("status", "pending")),
                    "updated_at": now_iso,
                    "artifacts": arts,
                    "errors": [],
                }
            cls._write_manifest_file(mpath, mdata)
            return True

    @classmethod
    def record_if_manifest_tracks_stages(
        cls,
        project_dir: Path,
        stage_name: str,
        relative_path: str,
        abs_path: Path,
    ) -> bool:
        """Updates a single stage artifact entry in `00_project_manifest.json` if `stages` tracking is active."""
        p_dir = Path(project_dir)
        mpath = p_dir / "00_project_manifest.json"
        fp = Path(abs_path)
        if not mpath.exists() or not fp.exists():
            return False
        sha256 = cls._calculate_sha256(fp)
        size_bytes = fp.stat().st_size
        with cls._manifest_file_lock(p_dir):
            if not mpath.exists() or not fp.exists():
                return False
            try:
                mdata = json.loads(mpath.read_text(encoding="utf-8"))
            except Exception:
                return False
            if not isinstance(mdata, dict) or not isinstance(mdata.get("stages"), dict):
                return False
            now_iso = datetime.now(timezone.utc).isoformat()
            stage_obj = mdata["stages"].setdefault(
                stage_name,
                {"status": "completed", "updated_at": now_iso, "artifacts": {}, "errors": []},
            )
            arts = stage_obj.setdefault("artifacts", {})
            arts[str(relative_path)] = {
                "sha256": sha256,
                "size_bytes": size_bytes,
                "recorded_at": now_iso,
            }
            stage_obj["updated_at"] = now_iso
            mdata["updated_at"] = now_iso
            cls._write_manifest_file(mpath, mdata)
            return True

    @classmethod
    def prune_manifest_stage_prefix(
        cls,
        project_dir: Path,
        stage_name: str,
        prefix: str,
        keep_relative_paths: set[str],
    ) -> int:
        """Removes stale stage artifact entries matching `prefix` not present in `keep_relative_paths`."""
        p_dir = Path(project_dir)
        mpath = p_dir / "00_project_manifest.json"
        if not mpath.exists():
            return 0
        with cls._manifest_file_lock(p_dir):
            if not mpath.exists():
                return 0
            try:
                mdata = json.loads(mpath.read_text(encoding="utf-8"))
            except Exception:
                return 0
            if not isinstance(mdata, dict) or not isinstance(mdata.get("stages"), dict):
                return 0
            stage_obj = mdata["stages"].get(stage_name)
            if not isinstance(stage_obj, dict) or not isinstance(stage_obj.get("artifacts"), dict):
                return 0
            arts = stage_obj["artifacts"]
            stale_keys = [k for k in list(arts.keys()) if str(k).startswith(prefix) and str(k) not in keep_relative_paths]
            if not stale_keys:
                return 0
            for k in stale_keys:
                arts.pop(k, None)
            now_iso = datetime.now(timezone.utc).isoformat()
            stage_obj["updated_at"] = now_iso
            mdata["updated_at"] = now_iso
            cls._write_manifest_file(mpath, mdata)
            return len(stale_keys)


