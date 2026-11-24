#!/usr/bin/env python3
"""Project-folder artifact & report archiver + Antigravity Stop hook handler (`R83 v3` Fresh-Room).

Copies and synchronizes user-facing Markdown reports/artifacts and embedded media
from `<appDataDir>/brain/<conversation_id>/` into `07_Youtube/artifacts_archive/`:
  - Historical canonical folders (`01_YouTube_CEO/` .. `09_Channel_Art/`) via `HISTORICAL_CONV_FOLDER_MAP`
  - Fresh-Room conversation folders (`conv_<first8>/`) discovered via `conversation_summaries.db` or `Stop` hook

Features:
  - Incremental FUSE-friendly atomic copy (`src_size != dst_size or src_mtime - dst_mtime > 2ms`)
    guarded by a single local `/tmp/aab_artifacts_archive.lock` `flock`.
  - Standalone relative link rewriting inside archived `.md` copies without mutating
    source files in `~/.gemini/.../brain/`.
  - Auto-generated master catalog `artifacts_archive/INDEX.md`.
  - Lifecycle `--hook stop` mode with guaranteed valid JSON stdout and exit code `0`.
"""

from __future__ import annotations

import json
import os
import sys

_PRELOADED_HOOK_STDIN: str | None = None


def _try_fast_cli_hook_exit() -> None:
    """Fast-exit malformed or empty Stop hook invocations before stdlib imports."""
    global _PRELOADED_HOOK_STDIN
    if __name__ != "__main__" or len(sys.argv) != 3 or sys.argv[1] != "--hook":
        return
    mode = sys.argv[2]
    if mode != "stop":
        sys.stdout.write("{}\n")
        sys.stdout.flush()
        raise SystemExit(0)
    default_out = '{"decision": "stop"}\n'
    try:
        raw = sys.stdin.read()
    except Exception:
        sys.stdout.write(default_out)
        sys.stdout.flush()
        raise SystemExit(0)
    _PRELOADED_HOOK_STDIN = raw
    if not raw.strip():
        sys.stdout.write(default_out)
        sys.stdout.flush()
        raise SystemExit(0)
    try:
        payload = json.loads(raw)
    except Exception:
        sys.stdout.write(default_out)
        sys.stdout.flush()
        raise SystemExit(0)
    if not isinstance(payload, dict):
        sys.stdout.write(default_out)
        sys.stdout.flush()
        raise SystemExit(0)


_try_fast_cli_hook_exit()

import contextlib  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402
import posixpath  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import sqlite3  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
from typing import Any, Iterator, Mapping, Sequence  # noqa: E402
import urllib.parse  # noqa: E402

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARCHIVE_DIR = WORKSPACE_ROOT / "artifacts_archive"
DEFAULT_WORKSPACE_HOOKS_PATH = WORKSPACE_ROOT / ".agents" / "hooks.json"
DEFAULT_DB_PATH = Path.home() / ".gemini" / "antigravity-cli" / "conversation_summaries.db"
DEFAULT_PYTHON_BIN = Path("/home/canadaofbin/hermes-venv/bin/python")
YOUTUBE_WORKSPACE_TAG = "07_Youtube"
YOUTUBE_PROJECT_ID = "7efa2720-1afb-42e6-add4-0095ece733b3"
WORKSPACE_HOOK_NAME = "artifact-auto-archive"

DEFAULT_BRAIN_ROOTS: tuple[Path, ...] = (
    Path.home() / ".gemini" / "antigravity-cli" / "brain",
    Path.home() / ".gemini" / "antigravity" / "brain",
    Path.home() / ".gemini" / "antigravity-ide" / "brain",
)

EXCLUDED_DIRS: frozenset[str] = frozenset({".system_generated", "scratch", "__pycache__"})
EXCLUDED_SUFFIXES: tuple[str, ...] = (
    ".metadata.json", ".tmp", ".lock", ".new", "~",
    ".mp4", ".mov", ".mkv", ".webm", ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".f32", ".npz",
)
MAX_ARCHIVED_MEDIA_BYTES: int = 2 * 1024 * 1024  # 2 MiB ceiling for non-Markdown artifacts

HISTORICAL_CONV_FOLDER_MAP: dict[str, str] = {
    "b57c97a8-6324-4c31-a2bb-16b25e28dd55": "01_YouTube_CEO",
    "1f9808d4-ebac-4b58-a570-45c8f1f00a85": "02_Operator",
    "ffbdfca1-9c07-48b3-9b1e-3e3045d67c0c": "03_Research",
    "8c666be9-5bad-43d9-b91a-e7ba2b936c62": "04_Deep_Research",
    "e3210c73-cc41-4432-87b1-c158efe9cadb": "05_Daily_Report",
    "ef8185bb-5afd-4859-b697-2fe07f1ecf1c": "06_QA_Scheduler",
    "0ffee83a-d9de-4520-a177-7d3b57dc01dc": "07_Topic_Radar",
    "8c7f8d97-664d-4d6b-9ef8-b17e721354f9": "08_Headquarters",
    "3c2fa53b-b43c-4f67-9dfd-0e5c86581f67": "09_Channel_Art",
}

# Google Drive / fuse.rclone quantizes mtime to milliseconds (1e-3s).
_MTIME_EPSILON_SEC: float = 0.002

_REL_URI_ESCAPE_MAP = str.maketrans(
    {
        "%": "%25",
        " ": "%20",
        "#": "%23",
        "?": "%3F",
        "(": "%28",
        ")": "%29",
        "[": "%5B",
        "]": "%5D",
        "<": "%3C",
        ">": "%3E",
        '"': "%22",
        "'": "%27",
        "\\": "/",
    }
)

_GEMINI_BRAIN_PATH_RE = re.compile(
    r"^/home/[^/]+/\.gemini/[^/]+/brain/([A-Za-z0-9_\-]{8,})/(.+)$"
)
_MD_INLINE_LINK_RE = re.compile(
    r'(\]\(\s*)(<[^>\n]+>(?:\s+(?:"[^"\n]*"|\'[^\'\n]*\'))?|(?:[^\s()\n]+|\((?:[^\s()\n]+|\([^\s()\n]*\))*\))+(?:\s+(?:"[^"\n]*"|\'[^\'\n]*\'))?)(\s*\))'
)
_HTML_ATTR_LINK_RE = re.compile(r'(\b(?:src|href)=["\'])([^"\'\n]+)(["\'])')
_MD_REF_LINK_RE = re.compile(r"(^\s*\[[^\]]+\]:\s*)(<[^>\n]+>|\S+)", re.MULTILINE)
_URL_TITLE_SPLIT_RE = re.compile(r'^(<[^>\n]+>|\S+)(\s+(?:"[^"]*"|\'[^\']*\'))$')
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_INLINE_CODE_RE = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)")
_ATX_HEADING_RE = re.compile(r"^#{1,6}(?:\s+(.+?))?\s*$")
_CONTAINER_FENCE_INFOS: frozenset[str] = frozenset({"carousel", "tabs"})

_HELD_LOCKS_TLS = threading.local()


@dataclass
class SyncResult:
    conv_id: str
    folder_name: str
    copied: int = 0
    skipped: int = 0
    md_count: int = 0
    media_count: int = 0
    total_files: int = 0


def _fallback_conv_folder(conv_id: str) -> str:
    prefix = re.sub(r"[^A-Za-z0-9_\-]", "", conv_id.strip())[:8] or "unknown"
    return f"conv_{prefix}"


def resolve_archive_folder(
    conv_id: str,
    archive_dir: Path | None = None,
) -> str:
    if conv_id in HISTORICAL_CONV_FOLDER_MAP:
        hist_folder = HISTORICAL_CONV_FOLDER_MAP[conv_id]
        if archive_dir is not None and archive_dir.is_dir():
            suffix = "_" + hist_folder.split("_", 1)[-1]
            existing = sorted(
                d.name for d in archive_dir.iterdir()
                if d.is_dir() and d.name.endswith(suffix) and d.name[:2].isdigit()
            )
            if existing and hist_folder not in existing:
                return existing[0]
        return hist_folder
    return _fallback_conv_folder(conv_id)


def should_exclude_rel_path(rel_path: Path) -> bool:
    parts = rel_path.parts
    if not parts:
        return True
    for part in parts[:-1]:
        if part in EXCLUDED_DIRS or part.startswith("."):
            return True
    name = parts[-1]
    if not name or name.startswith("."):
        return True
    if name.endswith(EXCLUDED_SUFFIXES):
        return True
    if ".resolved" in name:
        return True
    return False


def _collect_source_files(src_dirs: Sequence[Path]) -> dict[Path, tuple[Path, os.stat_result]]:
    """Scan one or more brain `<conv_id>` dirs and return `{rel_path: (src_path, stat)}`."""
    merged: dict[Path, tuple[Path, os.stat_result]] = {}
    for base_dir in src_dirs:
        if not base_dir.is_dir():
            continue
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = sorted(
                d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")
            )
            root_path = Path(root)
            rel_dir = root_path.relative_to(base_dir)
            for fname in sorted(files):
                rel_path = rel_dir / fname if rel_dir.parts else Path(fname)
                if should_exclude_rel_path(rel_path):
                    continue
                fpath = root_path / fname
                try:
                    st = fpath.stat()
                except OSError:
                    continue
                if not os.path.isfile(fpath):
                    continue
                if rel_path.suffix.lower() != ".md" and st.st_size > MAX_ARCHIVED_MEDIA_BYTES:
                    continue
                prev = merged.get(rel_path)
                if prev is None or st.st_mtime > prev[1].st_mtime:
                    merged[rel_path] = (fpath, st)
    return merged


def _scan_dest_stats(dst_dir: Path) -> dict[Path, os.stat_result]:
    """Use `os.scandir` to collect cached FUSE `DirEntry.stat` attributes in minimal RPCs."""
    stats: dict[Path, os.stat_result] = {}
    if not dst_dir.is_dir():
        return stats

    stack: list[tuple[Path, Path]] = [(dst_dir, Path())]
    while stack:
        abs_cur, rel_cur = stack.pop()
        try:
            with os.scandir(abs_cur) as it:
                for entry in it:
                    name = entry.name
                    if name.startswith(".") or name in EXCLUDED_DIRS:
                        continue
                    rel_child = rel_cur / name if rel_cur.parts else Path(name)
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append((abs_cur / name, rel_child))
                        elif entry.is_file(follow_symlinks=False):
                            stats[rel_child] = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
        except OSError:
            continue
    return stats


def _split_query_fragment(url: str) -> tuple[str, str]:
    frag_idx = url.find("#")
    frag = ""
    if frag_idx != -1:
        frag = url[frag_idx:]
        url = url[:frag_idx]
    q_idx = url.find("?")
    query = ""
    if q_idx != -1:
        query = url[q_idx:]
        url = url[:q_idx]
    return url, query + frag


def _encode_rel_url(rel_posix: str) -> str:
    return rel_posix.translate(_REL_URI_ESCAPE_MAP)


def _format_rel_link(target_path: Path, from_dir: Path) -> str:
    rel = os.path.relpath(target_path, start=from_dir).replace(os.sep, "/")
    if not rel.startswith("./") and not rel.startswith("../"):
        rel = f"./{rel}"
    return _encode_rel_url(rel)


def _mask_markdown_code_regions(md_text: str) -> tuple[str, list[tuple[str, str]]]:
    """Mask non-container fenced code blocks and inline backtick code spans while preserving ````carousel```` / ````tabs````."""
    tokens: list[tuple[str, str]] = []
    out_lines: list[str] = []
    masked_buf: list[str] = []
    fence_state: tuple[str, str, int] | None = None

    for line in md_text.splitlines(keepends=True):
        stripped_nl = line.rstrip("\r\n")
        if fence_state is None:
            m_open = _FENCE_OPEN_RE.match(stripped_nl)
            if m_open:
                fence_str, info_raw = m_open.group(1), m_open.group(2).strip()
                fchar = fence_str[0]
                if not (fchar == "`" and "`" in info_raw):
                    first_word = info_raw.split()[0].lower() if info_raw else ""
                    if first_word in _CONTAINER_FENCE_INFOS:
                        fence_state = ("container", fchar, len(fence_str))
                        out_lines.append(line)
                    else:
                        fence_state = ("code", fchar, len(fence_str))
                        masked_buf = [line]
                    continue
            out_lines.append(line)
        else:
            kind, fchar, flen = fence_state
            is_close = bool(re.match(rf"^ {{0,3}}{re.escape(fchar)}{{{flen},}}\s*$", stripped_nl))
            if kind == "container":
                out_lines.append(line)
                if is_close:
                    fence_state = None
            else:
                masked_buf.append(line)
                if is_close:
                    tok = f"\x00MDFENCE_{len(tokens)}\x00"
                    tokens.append((tok, "".join(masked_buf)))
                    out_lines.append(tok)
                    masked_buf = []
                    fence_state = None

    if fence_state is not None and fence_state[0] == "code" and masked_buf:
        tok = f"\x00MDFENCE_{len(tokens)}\x00"
        tokens.append((tok, "".join(masked_buf)))
        out_lines.append(tok)

    stage1 = "".join(out_lines)

    def _mask_inline(m: re.Match[str]) -> str:
        tok = f"\x00MDINLINE_{len(tokens)}\x00"
        tokens.append((tok, m.group(0)))
        return tok

    stage2 = _INLINE_CODE_RE.sub(_mask_inline, stage1)
    return stage2, tokens


def _restore_masked_regions(text: str, tokens: Sequence[tuple[str, str]]) -> str:
    out = text
    for tok, orig in reversed(tokens):
        out = out.replace(tok, orig)
    return out


def rewrite_markdown_links(
    md_text: str,
    *,
    conv_id: str,
    rel_md_path: Path,
    dst_chatroom_dir: Path,
    archive_dir: Path,
    src_brain_dirs: Sequence[Path],
    conv_to_folder: Mapping[str, str],
    brain_roots: Sequence[Path] = DEFAULT_BRAIN_ROOTS,
) -> str:
    """Rewrite absolute brain media/report paths inside archived `.md` copy to clean relative links."""
    md_parent_dir = (dst_chatroom_dir / rel_md_path).parent
    norm_src_dirs = [posixpath.normpath(str(p.resolve())) for p in src_brain_dirs]
    norm_brain_roots = [posixpath.normpath(str(p.resolve())) for p in brain_roots]

    def _can_resolve_other_conv(other_cid: str) -> str | None:
        folder = conv_to_folder.get(other_cid) or resolve_archive_folder(other_cid, archive_dir=archive_dir)
        if (archive_dir / folder).exists():
            return folder
        if other_cid in conv_to_folder or other_cid in HISTORICAL_CONV_FOLDER_MAP:
            for br in brain_roots:
                if (br / other_cid).is_dir():
                    return folder
        return None

    def _rewrite_target(raw_target: str, *, allow_title: bool) -> str:
        stripped = raw_target.strip()
        if not stripped:
            return raw_target

        title_suffix = ""
        if allow_title:
            m_title = _URL_TITLE_SPLIT_RE.match(stripped)
            if m_title:
                url_token, title_suffix = m_title.group(1), m_title.group(2)
            else:
                url_token = stripped
        else:
            url_token = stripped

        if url_token.startswith("<") and url_token.endswith(">"):
            url_token = url_token[1:-1].strip()

        if url_token.startswith(("http://", "https://", "mailto:", "conversation://", "#")):
            return raw_target

        path_part, qf_suffix = _split_query_fragment(url_token)
        if path_part.startswith("file:///"):
            fs_path = urllib.parse.unquote(path_part[len("file://") :])
        elif path_part.startswith("/"):
            fs_path = urllib.parse.unquote(path_part)
        else:
            return raw_target

        norm_fs = posixpath.normpath(fs_path)

        for sdir in norm_src_dirs:
            prefix = sdir + "/"
            if norm_fs.startswith(prefix):
                sub_rel = Path(norm_fs[len(prefix) :])
                if not should_exclude_rel_path(sub_rel):
                    new_rel = _format_rel_link(dst_chatroom_dir / sub_rel, md_parent_dir) + qf_suffix
                    return new_rel + title_suffix

        matched_cid: str | None = None
        matched_sub: Path | None = None
        for broot in norm_brain_roots:
            bprefix = broot + "/"
            if norm_fs.startswith(bprefix):
                rem = norm_fs[len(bprefix) :]
                slash = rem.find("/")
                if slash > 0:
                    matched_cid = rem[:slash]
                    matched_sub = Path(rem[slash + 1 :])
                    break

        if matched_cid is None:
            m_gem = _GEMINI_BRAIN_PATH_RE.match(norm_fs)
            if m_gem:
                matched_cid = m_gem.group(1)
                matched_sub = Path(m_gem.group(2))

        if matched_cid and matched_sub and not should_exclude_rel_path(matched_sub):
            if matched_cid == conv_id:
                new_rel = _format_rel_link(dst_chatroom_dir / matched_sub, md_parent_dir) + qf_suffix
                return new_rel + title_suffix

            other_folder = _can_resolve_other_conv(matched_cid)
            if other_folder is not None:
                target_archived = archive_dir / other_folder / matched_sub
                new_rel = _format_rel_link(target_archived, md_parent_dir) + qf_suffix
                return new_rel + title_suffix

        return raw_target

    masked_md, masked_tokens = _mask_markdown_code_regions(md_text)
    out = _MD_INLINE_LINK_RE.sub(
        lambda m: f"{m.group(1)}{_rewrite_target(m.group(2), allow_title=True)}{m.group(3)}",
        masked_md,
    )
    out = _HTML_ATTR_LINK_RE.sub(
        lambda m: f"{m.group(1)}{_rewrite_target(m.group(2), allow_title=False)}{m.group(3)}",
        out,
    )
    out = _MD_REF_LINK_RE.sub(
        lambda m: f"{m.group(1)}{_rewrite_target(m.group(2), allow_title=False)}",
        out,
    )
    return _restore_masked_regions(out, masked_tokens)


def _is_mtime_newer(src_mtime: float, dst_mtime: float) -> bool:
    return (src_mtime - dst_mtime) > _MTIME_EPSILON_SEC


def _preserve_mtime(dst_path: Path, src_stat: os.stat_result) -> None:
    try:
        os.utime(dst_path, (src_stat.st_atime, src_stat.st_mtime))
    except OSError:
        pass


@contextlib.contextmanager
def _archive_sync_lock(archive_dir: Path) -> Iterator[None]:
    """Serialize archive & `INDEX.md` mutations across concurrent Stop hooks via single `/tmp` flock."""
    if fcntl is None:  # pragma: no cover
        yield
        return

    lock_path = Path(tempfile.gettempdir()) / "aab_artifacts_archive.lock"
    held: set[Path] | None = getattr(_HELD_LOCKS_TLS, "paths", None)
    if held is None:
        held = set()
        _HELD_LOCKS_TLS.paths = held

    if lock_path in held:
        yield
        return

    fh = None
    acquired = False
    try:
        fh = lock_path.open("a+", encoding="utf-8")
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        acquired = True
        held.add(lock_path)
    except OSError:
        if fh is not None:
            with contextlib.suppress(OSError):
                fh.close()
            fh = None

    try:
        yield
    finally:
        if acquired and fh is not None:
            held.discard(lock_path)
            with contextlib.suppress(OSError):
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            with contextlib.suppress(OSError):
                fh.close()


def _atomic_write_bytes(dst_path: Path, data: bytes, src_stat: os.stat_result | None = None) -> None:
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dst_path.parent / f".{dst_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        tmp_path.write_bytes(data)
        if src_stat is not None:
            _preserve_mtime(tmp_path, src_stat)
        os.replace(tmp_path, dst_path)
        if src_stat is not None:
            _preserve_mtime(dst_path, src_stat)
    finally:
        if tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()


def _atomic_copy_file(src_path: Path, dst_path: Path, src_stat: os.stat_result) -> None:
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dst_path.parent / f".{dst_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        shutil.copyfile(src_path, tmp_path)
        _preserve_mtime(tmp_path, src_stat)
        os.replace(tmp_path, dst_path)
        _preserve_mtime(dst_path, src_stat)
    finally:
        if tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()


def sync_conversation(
    conv_id: str,
    *,
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
    brain_roots: Sequence[Path] = DEFAULT_BRAIN_ROOTS,
    explicit_src_dir: Path | None = None,
    ensure_dir: bool = False,
    force_check_src: Path | None = None,
    extra_conv_folders: Mapping[str, str] | None = None,
) -> SyncResult:
    """Incrementally sync one conversation's brain artifacts into `artifacts_archive/<folder>/`."""
    folder_name = (
        extra_conv_folders.get(conv_id)
        if extra_conv_folders and conv_id in extra_conv_folders
        else resolve_archive_folder(conv_id, archive_dir=archive_dir)
    )
    dst_dir = archive_dir / folder_name

    src_dirs: list[Path] = []
    if explicit_src_dir is not None:
        src_dirs.append(explicit_src_dir)
    for br in brain_roots:
        cand = br / conv_id
        if cand not in src_dirs:
            src_dirs.append(cand)

    source_files = _collect_source_files(src_dirs)
    result = SyncResult(conv_id=conv_id, folder_name=folder_name)

    with _archive_sync_lock(archive_dir):
        if not source_files:
            if ensure_dir:
                dst_dir.mkdir(parents=True, exist_ok=True)
            if dst_dir.is_dir():
                existing = _scan_dest_stats(dst_dir)
                for rpath in existing:
                    if rpath.suffix.lower() == ".md":
                        result.md_count += 1
                    else:
                        result.media_count += 1
                result.total_files = len(existing)
            return result

        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_stats = _scan_dest_stats(dst_dir)
        conv_to_folder = {
            cid: resolve_archive_folder(cid, archive_dir=archive_dir)
            for cid in HISTORICAL_CONV_FOLDER_MAP
        }
        if extra_conv_folders:
            for ecid, efolder in extra_conv_folders.items():
                conv_to_folder[ecid] = efolder
        conv_to_folder[conv_id] = folder_name

        force_resolved = force_check_src.resolve() if force_check_src is not None else None

        for rel_path, (src_path, src_stat) in sorted(source_files.items()):
            dst_path = dst_dir / rel_path
            dstat = dst_stats.get(rel_path)
            is_md = rel_path.suffix.lower() == ".md"
            if is_md:
                result.md_count += 1
            else:
                result.media_count += 1

            is_forced = force_resolved is not None and src_path.resolve() == force_resolved

            if not is_md:
                needs_copy = (
                    dstat is None
                    or src_stat.st_size != dstat.st_size
                    or _is_mtime_newer(src_stat.st_mtime, dstat.st_mtime)
                )
                if not needs_copy and is_forced:
                    try:
                        needs_copy = dst_path.read_bytes() != src_path.read_bytes()
                    except OSError:
                        needs_copy = True
                if not needs_copy:
                    result.skipped += 1
                    continue
                _atomic_copy_file(src_path, dst_path, src_stat)
                result.copied += 1
            else:
                if (
                    not is_forced
                    and dstat is not None
                    and src_stat.st_size == dstat.st_size
                    and not _is_mtime_newer(src_stat.st_mtime, dstat.st_mtime)
                ):
                    result.skipped += 1
                    continue

                raw_text = src_path.read_text(encoding="utf-8", errors="surrogateescape")
                rewritten_text = rewrite_markdown_links(
                    raw_text,
                    conv_id=conv_id,
                    rel_md_path=rel_path,
                    dst_chatroom_dir=dst_dir,
                    archive_dir=archive_dir,
                    src_brain_dirs=src_dirs,
                    conv_to_folder=conv_to_folder,
                    brain_roots=brain_roots,
                )
                rewritten_bytes = rewritten_text.encode("utf-8", errors="surrogateescape")

                if (
                    dstat is not None
                    and len(rewritten_bytes) == dstat.st_size
                    and not _is_mtime_newer(src_stat.st_mtime, dstat.st_mtime)
                ):
                    if not is_forced:
                        result.skipped += 1
                        continue
                    try:
                        if dst_path.read_bytes() == rewritten_bytes:
                            result.skipped += 1
                            continue
                    except OSError:
                        pass

                _atomic_write_bytes(dst_path, rewritten_bytes, src_stat)
                result.copied += 1

    result.total_files = result.md_count + result.media_count
    return result


def _extract_md_heading(md_path: Path) -> str:
    try:
        with md_path.open("r", encoding="utf-8", errors="replace") as fh:
            in_frontmatter = False
            fence_state: tuple[str, int] | None = None
            for line_idx in range(60):
                line = fh.readline()
                if not line:
                    break
                stripped_nl = line.rstrip("\r\n")
                stripped = stripped_nl.strip()

                if line_idx == 0 and stripped == "---":
                    in_frontmatter = True
                    continue
                if in_frontmatter:
                    if stripped in ("---", "..."):
                        in_frontmatter = False
                    continue

                if fence_state is None:
                    m_open = _FENCE_OPEN_RE.match(stripped_nl)
                    if m_open:
                        fstr, info_raw = m_open.group(1), m_open.group(2).strip()
                        if not (fstr[0] == "`" and "`" in info_raw):
                            first_word = info_raw.split()[0].lower() if info_raw else ""
                            if first_word not in _CONTAINER_FENCE_INFOS:
                                fence_state = (fstr[0], len(fstr))
                                continue
                else:
                    fchar, flen = fence_state
                    if re.match(rf"^ {{0,3}}{re.escape(fchar)}{{{flen},}}\s*$", stripped_nl):
                        fence_state = None
                    continue

                m_head = _ATX_HEADING_RE.match(stripped)
                if m_head and m_head.group(1):
                    heading = re.sub(r"\s+#+\s*$", "", m_head.group(1)).strip()
                    if heading:
                        clean = heading.replace("|", "\\|")
                        if len(clean) > 90:
                            trunc = clean[:90].rstrip("\\")
                            if trunc.count("`") % 2 == 1:
                                trunc += "`"
                            return trunc + "..."
                        if clean.count("`") % 2 == 1:
                            clean += "`"
                        return clean
    except OSError:
        pass
    return "—"


def _fmt_utc(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def generate_index_md(
    *,
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
    brain_roots: Sequence[Path] = DEFAULT_BRAIN_ROOTS,
) -> Path:
    """Regenerate `artifacts_archive/INDEX.md` cataloging all archived reports and media."""
    with _archive_sync_lock(archive_dir):
        archive_dir.mkdir(parents=True, exist_ok=True)
        hist_folder_to_cid: dict[str, str] = {
            resolve_archive_folder(cid, archive_dir=archive_dir): cid
            for cid in HISTORICAL_CONV_FOLDER_MAP
        }

        subdirs: list[Path] = []
        if archive_dir.is_dir():
            with os.scandir(archive_dir) as it:
                for entry in it:
                    if not entry.name.startswith(".") and entry.is_dir(follow_symlinks=False):
                        subdirs.append(archive_dir / entry.name)
        subdirs.sort(key=lambda p: p.name)

        folder_records: list[
            tuple[str, str | None, list[tuple[Path, os.stat_result]], list[tuple[Path, os.stat_result]]]
        ] = []
        total_md = 0
        total_media = 0

        for sdir in subdirs:
            fstats = _scan_dest_stats(sdir)
            md_items: list[tuple[Path, os.stat_result]] = []
            media_items: list[tuple[Path, os.stat_result]] = []
            for rpath, st in fstats.items():
                if rpath.suffix.lower() == ".md":
                    md_items.append((rpath, st))
                else:
                    media_items.append((rpath, st))
            md_items.sort(key=lambda x: (-x[1].st_mtime, str(x[0])))
            media_items.sort(key=lambda x: str(x[0]))
            total_md += len(md_items)
            total_media += len(media_items)
            folder_records.append((sdir.name, hist_folder_to_cid.get(sdir.name), md_items, media_items))

        lines: list[str] = [
            "# ALL ABOUT BRAIN — Archived Reports & Artifacts (`artifacts_archive/`)",
            "",
            "- **Workspace**: `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube`",
            "- **Auto-Sync Hook**: `.agents/hooks.json` (`Stop`) via `scripts/sync_archive.py`",
            "- **Manual Full Sync**: `/home/canadaofbin/hermes-venv/bin/python -X utf8 scripts/sync_archive.py --sync-all`",
            f"- **Archive Totals**: **{total_md}** Markdown reports/artifacts + **{total_media}** media/chart assets (**{total_md + total_media}** total files)",
            "",
            "## Archived Folders Summary",
            "",
            "| Folder | Conversation ID | `.md` Reports | Media / Assets | Total Files |",
            "|---|---|---:|---:|---:|",
        ]

        for fname, cid, md_items, media_items in folder_records:
            cid_label = f"`{cid}`" if cid else f"`{fname}`"
            folder_url = _encode_rel_url(f"./{fname}/")
            lines.append(
                f"| [`{fname}/`]({folder_url}) | {cid_label} | {len(md_items)} | {len(media_items)} | {len(md_items) + len(media_items)} |"
            )

        lines.append("")

        for fname, cid, md_items, media_items in folder_records:
            header_suffix = f" (`{cid}`)" if cid else ""
            lines.append(f"## `{fname}`{header_suffix}")
            lines.append("")

            if md_items:
                lines.append("| Report / Artifact | Heading | Size | Last Modified |")
                lines.append("|---|---|---:|---|")
                for rpath, st in md_items:
                    rel_posix = rpath.as_posix()
                    rel_label = rel_posix.replace("|", "\\|").replace("`", "\\`")
                    link_url = _encode_rel_url(f"./{fname}/{rel_posix}")
                    heading_src: Path = archive_dir / fname / rpath
                    if cid is not None:
                        for br in brain_roots:
                            local_cand = br / cid / rpath
                            if local_cand.is_file():
                                heading_src = local_cand
                                break
                    heading = _extract_md_heading(heading_src)
                    lines.append(
                        f"| [`{rel_label}`]({link_url}) | {heading} | {_fmt_size(st.st_size)} | {_fmt_utc(st.st_mtime)} |"
                    )
                lines.append("")
            else:
                lines.append("_No Markdown reports archived in this folder yet._")
                lines.append("")

            if media_items:
                grouped: dict[str, list[Path]] = {}
                for rpath, _ in media_items:
                    bucket = rpath.parts[0] if len(rpath.parts) > 1 else "."
                    grouped.setdefault(bucket, []).append(rpath)
                summary_parts: list[str] = []
                for bucket, items in sorted(grouped.items()):
                    if bucket == ".":
                        summary_parts.append(f"`root` ({len(items)} files)")
                    else:
                        bucket_label = bucket.replace("|", "\\|").replace("`", "\\`")
                        bucket_url = _encode_rel_url(f"./{fname}/{bucket}/")
                        summary_parts.append(f"[`{bucket_label}/`]({bucket_url}) ({len(items)} files)")
                lines.append(f"- **Embedded Media & Charts ({len(media_items)} files)**: " + ", ".join(summary_parts))
                lines.append("")

        index_path = archive_dir / "INDEX.md"
        content = "\n".join(lines).rstrip() + "\n"
        content_bytes = content.encode("utf-8")
        if not index_path.exists() or index_path.read_bytes() != content_bytes:
            _atomic_write_bytes(index_path, content_bytes)
        return index_path


def _db_table_columns(cur: sqlite3.Cursor, table_name: str = "conversation_summaries") -> set[str]:
    try:
        cur.execute(f"PRAGMA table_info({table_name})")
        return {str(row[1]) for row in cur.fetchall() if len(row) > 1}
    except sqlite3.Error:
        return set()


def _ws_uris_entries(ws_raw: str) -> list[str]:
    stripped = ws_raw.strip()
    if not stripped or stripped == "[]":
        return []
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if isinstance(x, str) and str(x).strip()]
        if isinstance(parsed, str) and parsed.strip():
            return [parsed.strip()]
    except json.JSONDecodeError:
        pass
    return [stripped]


def _normalize_candidate_path(raw_val: str) -> str:
    val = raw_val.strip()
    if val.startswith("file:///"):
        val = urllib.parse.unquote(val[len("file://") :])
    return os.path.abspath(os.path.expanduser(val))


def _payload_has_youtube_workspace(payload: Mapping[str, Any], workspace_root: Path = WORKSPACE_ROOT) -> bool:
    """Return True iff `payload['workspacePaths']` explicitly contains `07_Youtube` (or a subdirectory inside it)."""
    ws_paths = payload.get("workspacePaths")
    if not isinstance(ws_paths, list) or not ws_paths:
        return False
    ws_norm = posixpath.normpath(str(workspace_root.resolve()))
    for raw_ws in ws_paths:
        if not isinstance(raw_ws, str) or not raw_ws.strip():
            continue
        cand = posixpath.normpath(_normalize_candidate_path(raw_ws))
        if cand == ws_norm or cand.startswith(ws_norm + "/"):
            return True
    return False


def _ws_uris_has_youtube(ws_raw: str, workspace_root: Path = WORKSPACE_ROOT) -> bool:
    entries = _ws_uris_entries(ws_raw)
    if not entries:
        return False
    return _payload_has_youtube_workspace({"workspacePaths": entries}, workspace_root=workspace_root)


def _discover_unlisted_07_youtube_convs(
    db_path: Path,
    known_ids: set[str],
) -> list[str]:
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
    except sqlite3.Error:
        return []
    try:
        cur = conn.cursor()
        cols = _db_table_columns(cur)
        if "conversation_id" not in cols or "workspace_uris" not in cols:
            return []
        has_proj = "project_id" in cols
        has_depth = "nesting_depth" in cols
        select_cols = "conversation_id, workspace_uris" + (", project_id" if has_proj else "")
        where_clause = " WHERE COALESCE(nesting_depth, 0) = 0" if has_depth else ""
        cur.execute(f"SELECT {select_cols} FROM conversation_summaries{where_clause}")
        extra: list[str] = []
        for row in cur.fetchall():
            cid_s = str(row[0] or "").strip()
            if not cid_s or cid_s in known_ids:
                continue
            ws_raw = str(row[1] or "")
            proj_s = str(row[2] or "").strip() if has_proj and len(row) > 2 else ""
            if _ws_uris_has_youtube(ws_raw) or proj_s == YOUTUBE_PROJECT_ID:
                extra.append(cid_s)
        return extra
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _effective_db_path(archive_dir: Path, db_path: Path | None) -> Path | None:
    if db_path is not None:
        return db_path
    if archive_dir.resolve() == DEFAULT_ARCHIVE_DIR.resolve():
        return DEFAULT_DB_PATH
    return None


def sync_all(
    *,
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
    brain_roots: Sequence[Path] = DEFAULT_BRAIN_ROOTS,
    extra_conv_ids: Sequence[str] = (),
    db_path: Path | None = None,
    force_index: bool = False,
) -> list[SyncResult]:
    """Sync historical + DB-discovered `07_Youtube` conversations and rebuild `INDEX.md`."""
    with _archive_sync_lock(archive_dir):
        archive_dir.mkdir(parents=True, exist_ok=True)

        existing_folders: set[str] = set()
        has_index = False
        with os.scandir(archive_dir) as it:
            for entry in it:
                if entry.name == "INDEX.md":
                    has_index = True
                elif not entry.name.startswith(".") and entry.is_dir(follow_symlinks=False):
                    existing_folders.add(entry.name)

        ordered_ids: list[str] = list(HISTORICAL_CONV_FOLDER_MAP.keys())
        seen: set[str] = set(ordered_ids)

        effective_db = _effective_db_path(archive_dir, db_path)
        if effective_db is not None:
            for cid in _discover_unlisted_07_youtube_convs(effective_db, seen):
                ordered_ids.append(cid)
                seen.add(cid)

        for cid in extra_conv_ids:
            cid_clean = cid.strip()
            if cid_clean and cid_clean not in seen:
                ordered_ids.append(cid_clean)
                seen.add(cid_clean)

        known_folders = {cid: resolve_archive_folder(cid, archive_dir=archive_dir) for cid in ordered_ids}

        results: list[SyncResult] = []
        for cid in ordered_ids:
            folder_name = known_folders[cid]
            if folder_name not in existing_folders:
                if not any((br / cid).is_dir() for br in brain_roots):
                    results.append(SyncResult(conv_id=cid, folder_name=folder_name))
                    continue
            res = sync_conversation(
                cid,
                archive_dir=archive_dir,
                brain_roots=brain_roots,
                ensure_dir=False,
                extra_conv_folders=known_folders,
            )
            results.append(res)

        if force_index or not has_index or any(r.copied > 0 for r in results):
            generate_index_md(
                archive_dir=archive_dir,
                brain_roots=brain_roots,
            )
        return results


def _lookup_conv_lineage_in_db(
    cid: str,
    db_path: Path | None,
) -> tuple[int, str, str, list[str]] | None:
    """Return `(nesting_depth, raw_workspace_uris, project_id, ancestor_conv_ids)` for `cid`, or `None`."""
    if not cid or db_path is None or not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1.0)
    except sqlite3.Error:
        return None
    try:
        cur = conn.cursor()
        cols = _db_table_columns(cur)
        if "conversation_id" not in cols:
            return None
        has_depth = "nesting_depth" in cols
        has_ws = "workspace_uris" in cols
        has_proj = "project_id" in cols
        has_parent = "parent_conversation_id" in cols

        select_parts = [
            "nesting_depth" if has_depth else "0",
            "workspace_uris" if has_ws else "''",
            "project_id" if has_proj else "''",
            "parent_conversation_id" if has_parent else "''",
        ]
        query = f"SELECT {', '.join(select_parts)} FROM conversation_summaries WHERE conversation_id = ?"
        cur.execute(query, (cid,))
        row = cur.fetchone()
        if row is None:
            return None

        depth = int(row[0] or 0)
        ws_raw = str(row[1] or "").strip()
        proj_id = str(row[2] or "").strip()
        parent_id = str(row[3] or "").strip()

        ancestors: list[str] = []
        if has_parent and parent_id:
            seen_ids: set[str] = {cid}
            cur_parent = parent_id
            for _ in range(8):
                if not cur_parent or cur_parent in seen_ids:
                    break
                seen_ids.add(cur_parent)
                ancestors.append(cur_parent)
                cur.execute(
                    "SELECT parent_conversation_id FROM conversation_summaries WHERE conversation_id = ?",
                    (cur_parent,),
                )
                prow = cur.fetchone()
                if prow is None:
                    break
                cur_parent = str(prow[0] or "").strip()

        return depth, ws_raw, proj_id, ancestors
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def _is_archivable_hook_conv(
    cid: str,
    payload: Mapping[str, Any],
    archive_dir: Path,
    db_path: Path | None,
) -> bool:
    """Return True iff `cid` is a top-level `07_Youtube` conversation."""
    if cid in HISTORICAL_CONV_FOLDER_MAP:
        return True

    conv_id_raw = str(payload.get("conversationId") or "").strip()
    parent_raw = str(payload.get("parentConversationId") or "").strip()
    root_raw = str(payload.get("rootConversationId") or "").strip()
    if cid == conv_id_raw and ((parent_raw and parent_raw != cid) or (root_raw and root_raw != cid)):
        return False

    effective_db = _effective_db_path(archive_dir, db_path)
    lineage = _lookup_conv_lineage_in_db(cid, effective_db)
    if lineage is not None:
        depth, ws_raw, proj_id, ancestors = lineage
        if depth > 0 or ancestors:
            return False
        if _ws_uris_has_youtube(ws_raw) or proj_id == YOUTUBE_PROJECT_ID:
            return True
        if _ws_uris_entries(ws_raw) and not _payload_has_youtube_workspace(payload):
            return False

    if _payload_has_youtube_workspace(payload):
        return True

    return False


def handle_stop_payload(
    payload: Mapping[str, Any],
    *,
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
    brain_roots: Sequence[Path] = DEFAULT_BRAIN_ROOTS,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Process Antigravity `Stop` hook payload; skip `INDEX.md` rewrite when `0` files changed."""
    artifact_dir_raw = str(payload.get("artifactDirectoryPath") or "").strip()
    conv_id_raw = str(payload.get("conversationId") or "").strip()

    targets: list[tuple[str, Path | None]] = []
    if artifact_dir_raw:
        art_path = Path(_normalize_candidate_path(artifact_dir_raw))
        cid = conv_id_raw or art_path.name
        if cid:
            targets.append((cid, art_path))
    elif conv_id_raw:
        targets.append((conv_id_raw, None))

    for parent_key in ("parentConversationId", "rootConversationId"):
        pcid = str(payload.get(parent_key) or "").strip()
        if pcid and all(pcid != existing_cid for existing_cid, _ in targets):
            targets.append((pcid, None))

    if not targets:
        return {"decision": "stop"}

    effective_db = _effective_db_path(archive_dir, db_path)
    primary_cid = targets[0][0]
    if effective_db is not None and effective_db.exists():
        primary_lineage = _lookup_conv_lineage_in_db(primary_cid, effective_db)
        if primary_lineage is not None:
            _, _, _, p_ancestors = primary_lineage
            for anc_cid in p_ancestors:
                if all(anc_cid != existing_cid for existing_cid, _ in targets):
                    targets.append((anc_cid, None))

    active_targets: list[tuple[str, Path | None]] = []
    for cid, explicit_dir in targets:
        check_dirs: list[Path] = []
        if explicit_dir is not None:
            check_dirs.append(explicit_dir)
        for br in brain_roots:
            cand = br / cid
            if cand not in check_dirs:
                check_dirs.append(cand)
        if _collect_source_files(check_dirs):
            active_targets.append((cid, explicit_dir))

    if not active_targets:
        return {"decision": "stop"}

    filtered_targets = [
        (cid, explicit_dir)
        for cid, explicit_dir in active_targets
        if _is_archivable_hook_conv(cid, payload, archive_dir, db_path)
    ]
    if not filtered_targets:
        return {"decision": "stop"}

    with _archive_sync_lock(archive_dir):
        total_copied = 0
        for cid, explicit_dir in filtered_targets:
            res = sync_conversation(
                cid,
                archive_dir=archive_dir,
                brain_roots=brain_roots,
                explicit_src_dir=explicit_dir,
            )
            total_copied += res.copied

        if total_copied > 0:
            generate_index_md(
                archive_dir=archive_dir,
                brain_roots=brain_roots,
            )

    return {"decision": "stop"}


def _read_hook_stdin() -> str:
    global _PRELOADED_HOOK_STDIN
    if _PRELOADED_HOOK_STDIN is not None:
        raw = _PRELOADED_HOOK_STDIN
        _PRELOADED_HOOK_STDIN = None
        return raw
    return sys.stdin.read()


def _run_hook_mode(hook_type: str, archive_dir: Path, brain_roots: Sequence[Path]) -> int:
    if hook_type == "stop":
        try:
            raw = _read_hook_stdin()
            payload = json.loads(raw) if raw.strip() else {}
            if not isinstance(payload, Mapping):
                payload = {}
            resp = handle_stop_payload(
                payload,
                archive_dir=archive_dir,
                brain_roots=brain_roots,
            )
        except Exception:
            resp = {"decision": "stop"}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
        return 0

    sys.stdout.write("{}\n")
    sys.stdout.flush()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)

    if len(args_list) == 2 and args_list[0] == "--hook":
        return _run_hook_mode(args_list[1], DEFAULT_ARCHIVE_DIR, DEFAULT_BRAIN_ROOTS)

    import argparse

    parser = argparse.ArgumentParser(
        description="Sync Antigravity chatroom artifacts & reports into 07_Youtube/artifacts_archive/"
    )
    parser.add_argument(
        "--sync-all",
        action="store_true",
        help="Sync historical + DB-discovered 07_Youtube conversations and regenerate INDEX.md",
    )
    parser.add_argument(
        "--conv-id",
        action="append",
        default=[],
        help="Specific conversation ID(s) to sync",
    )
    parser.add_argument(
        "--hook",
        choices=("stop",),
        help="Run as Antigravity Stop lifecycle hook reading JSON from stdin",
    )
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR)
    parser.add_argument(
        "--brain-root",
        dest="brain_roots",
        type=Path,
        action="append",
        default=None,
        help="Override `<appDataDir>/brain` root directory (repeatable)",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON summary in CLI sync mode")
    parsed = parser.parse_args(args_list)

    brain_roots: Sequence[Path] = (
        tuple(parsed.brain_roots) if parsed.brain_roots else DEFAULT_BRAIN_ROOTS
    )

    if parsed.hook:
        return _run_hook_mode(parsed.hook, parsed.archive_dir, brain_roots)

    if parsed.sync_all or not parsed.conv_id:
        results = sync_all(
            archive_dir=parsed.archive_dir,
            brain_roots=brain_roots,
            extra_conv_ids=parsed.conv_id,
            force_index=parsed.sync_all,
        )
    else:
        with _archive_sync_lock(parsed.archive_dir):
            results = [
                sync_conversation(
                    cid,
                    archive_dir=parsed.archive_dir,
                    brain_roots=brain_roots,
                    ensure_dir=True,
                )
                for cid in parsed.conv_id
            ]
            generate_index_md(
                archive_dir=parsed.archive_dir,
                brain_roots=brain_roots,
            )

    summary: dict[str, Any] = {
        "archive_dir": str(parsed.archive_dir),
        "index_md": str(parsed.archive_dir / "INDEX.md"),
        "copied_total": sum(r.copied for r in results),
        "skipped_total": sum(r.skipped for r in results),
        "folders": [
            {
                "folder": r.folder_name,
                "conversation_id": r.conv_id,
                "copied": r.copied,
                "skipped": r.skipped,
                "md_count": r.md_count,
                "media_count": r.media_count,
                "total_files": r.total_files,
            }
            for r in results
            if r.total_files > 0 or (parsed.archive_dir / r.folder_name).is_dir()
        ],
    }

    if parsed.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            f"[artifacts_archive] copied={summary['copied_total']} skipped={summary['skipped_total']} -> {summary['archive_dir']}"
        )
        for item in summary["folders"]:
            print(
                f"  - {item['folder']:<24} md={item['md_count']:<3} media={item['media_count']:<3} total={item['total_files']:<3} (copied={item['copied']}, skipped={item['skipped']})"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
