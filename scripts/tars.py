#!/usr/bin/env python3
"""Deterministic state, URL hashing, decay scoring, and index helper for TARS."""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_DECAY_LAMBDA = 0.003
DEFAULT_STALE_DAYS = 7
ACTIVE_THRESHOLD = 0.45
PROBATION_THRESHOLD = 0.25

_SCP_RE = re.compile(r"^(?:(?P<user>[^@:/\\]+)@)?(?P<host>[^:/\\]+):(?P<path>.+)$")
_WIN_DRIVE_RE = re.compile(r"^[A-Za-z]:[/\\]")
_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
_LEARNING_ID_RE = re.compile(r"^([A-Z])(\d+)(?:_.*)?\.md$")


def _parse_date(value: str | _dt.date | None) -> _dt.date:
    if isinstance(value, _dt.date) and not isinstance(value, _dt.datetime):
        return value
    if not value:
        return _dt.date.today()
    return _dt.date.fromisoformat(str(value).strip())


def _canonical_fs_path(path: str | Path) -> str:
    resolved = os.path.realpath(os.fspath(path)).replace("\\", "/")
    if len(resolved) > 1:
        resolved = resolved.rstrip("/")
    return resolved


def _lowercase_authority_host(authority: str, strip_ssh_port: bool = False) -> str:
    if "@" in authority:
        authority = authority.rsplit("@", 1)[1]
    if authority.startswith("["):
        end_bracket = authority.find("]")
        if end_bracket != -1:
            host = authority[: end_bracket + 1].lower()
            rest = authority[end_bracket + 1 :]
            if strip_ssh_port and rest == ":22":
                rest = ""
            return host + rest
    if ":" in authority:
        host, port = authority.rsplit(":", 1)
        if strip_ssh_port and port == "22":
            return host.lower()
        return f"{host.lower()}:{port}"
    return authority.lower()


def normalize_remote_url(url: str) -> str:
    """Normalize a Git remote URL so HTTPS, SSH, .git, and trailing-/ forms match."""
    raw = (url or "").strip()
    if not raw:
        return ""

    if "://" in raw:
        scheme, rest = raw.split("://", 1)
        scheme_lower = scheme.lower()
        authority, _, path = rest.partition("/")
        host = _lowercase_authority_host(
            authority, strip_ssh_port=(scheme_lower == "ssh")
        )
        normalized = f"{host}/{path}" if path else host
    elif not _WIN_DRIVE_RE.match(raw):
        scp_match = _SCP_RE.match(raw)
        if scp_match:
            host = scp_match.group("host").lower()
            path = scp_match.group("path").lstrip("/")
            normalized = f"{host}/{path}" if path else host
        else:
            normalized = raw.replace("\\", "/")
    else:
        normalized = raw.replace("\\", "/")

    normalized = normalized.rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    normalized = normalized.rstrip("/")
    return normalized


def _run_git(repo_path: str | Path, args: list[str]) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", os.fspath(repo_path), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except OSError:
        pass
    return ""


def _strip_yaml_comment(raw: str) -> str:
    in_quote: str | None = None
    for idx, ch in enumerate(raw):
        if ch in ("'", '"') and (idx == 0 or raw[idx - 1] != "\\"):
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
        elif ch == "#" and in_quote is None and (idx == 0 or raw[idx - 1].isspace()):
            return raw[:idx].rstrip()
    return raw.strip()


def _parse_yaml_scalar(raw: str) -> Any:
    cleaned = _strip_yaml_comment(raw)
    if cleaned == "":
        return ""
    if cleaned.startswith("[") and cleaned.endswith("]"):
        inner = cleaned[1:-1].strip()
        if not inner:
            return []
        return [_unquote(part.strip()) for part in inner.split(",") if part.strip()]
    low = cleaned.lower()
    if low in ("null", "~"):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?\d+", cleaned):
        return int(cleaned)
    if re.fullmatch(r"-?\d+\.\d+", cleaned):
        return float(cleaned)
    return _unquote(cleaned)


def _unquote(val: str) -> str:
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        return val[1:-1]
    return val


def parse_yaml_mapping(text: str) -> dict[str, Any]:
    """Parse simple flat and single-level nested YAML mappings using stdlib only."""
    data: dict[str, Any] = {}
    current_block: dict[str, Any] | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        key = key.strip()
        if indent > 0 and current_block is not None:
            current_block[key] = _parse_yaml_scalar(val)
            continue
        parsed_val = _parse_yaml_scalar(val)
        if parsed_val == "" and _strip_yaml_comment(val) == "":
            nested: dict[str, Any] = {}
            data[key] = nested
            current_block = nested
        else:
            data[key] = parsed_val
            current_block = None
    return data


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body) from Markdown text."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    fm_text = match.group(1)
    body = text[match.end() :]
    return parse_yaml_mapping(fm_text), body


def _format_yaml_value(val: Any) -> str:
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, float):
        return f"{val:.2f}"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, list):
        return "[" + ", ".join(str(item) for item in val) + "]"
    s = str(val)
    if s == "" or any(ch in s for ch in (":", "#", "[", "]")):
        escaped = s.replace('"', '\\"')
        return f'"{escaped}"'
    return s


def update_frontmatter_fields(text: str, updates: dict[str, Any]) -> str:
    """Update top-level scalar/list keys in YAML frontmatter without disturbing body."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        lines = ["---"]
        for key, val in updates.items():
            lines.append(f"{key}: {_format_yaml_value(val)}")
        lines.append("---")
        return "\n".join(lines) + "\n" + text

    fm_lines = match.group(1).splitlines()
    body = text[match.end() :]
    remaining = dict(updates)
    out_lines: list[str] = []

    for line in fm_lines:
        if line.strip() and not line.startswith((" ", "\t", "#")) and ":" in line:
            key, _, rest = line.partition(":")
            key_clean = key.strip()
            if key_clean in remaining:
                val_str = _format_yaml_value(remaining.pop(key_clean))
                comment = ""
                if "#" in rest:
                    stripped_val = _strip_yaml_comment(rest)
                    idx = rest.find("#", len(stripped_val))
                    if idx != -1:
                        comment = "  " + rest[idx:].strip()
                out_lines.append(f"{key_clean}: {val_str}{comment}")
                continue
        out_lines.append(line)

    for key, val in remaining.items():
        out_lines.append(f"{key}: {_format_yaml_value(val)}")

    newline = "\r\n" if "\r\n" in text[: match.end()] else "\n"
    return f"---{newline}" + newline.join(out_lines) + f"{newline}---{newline}" + body


def compute_project_id(
    repo_root: str | Path, remote_url: str | None = None
) -> dict[str, str]:
    """Compute <folder-name>_<6-char-sha256> from normalized origin URL or path."""
    canonical_root = _canonical_fs_path(repo_root)
    folder_name = Path(canonical_root).name or "root"

    raw_remote = (
        _run_git(canonical_root, ["config", "--get", "remote.origin.url"])
        if remote_url is None
        else remote_url.strip()
    )
    normalized_remote = normalize_remote_url(raw_remote)
    hash_input = normalized_remote if normalized_remote else canonical_root
    short_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:6]

    return {
        "repo_path": canonical_root,
        "folder_name": folder_name,
        "remote_url": raw_remote,
        "normalized_remote": normalized_remote,
        "hash_input": hash_input,
        "hash": short_hash,
        "project_id": f"{folder_name}_{short_hash}",
    }


def resolve_project(
    repo_path: str | Path = ".",
    remote_url: str | None = None,
    tars_root: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve repo root, normalized project ID, storage paths, and mismatch warning."""
    top = _run_git(repo_path, ["rev-parse", "--show-toplevel"])
    resolved_root = _canonical_fs_path(top if top else repo_path)
    info = compute_project_id(resolved_root, remote_url=remote_url)

    root_dir = Path(tars_root) if tars_root else Path.home() / ".tars"
    project_dir = root_dir / "projects" / info["project_id"]
    meta_path = project_dir / "meta.yaml"

    warning = ""
    if meta_path.is_file():
        meta = parse_yaml_mapping(meta_path.read_text(encoding="utf-8"))
        stored_repo = meta.get("repo_path")
        if stored_repo:
            stored_canon = _canonical_fs_path(str(stored_repo))
            if stored_canon != resolved_root:
                warning = (
                    f"Stored meta.yaml repo_path ({stored_canon}) differs from "
                    f"current repo_root ({resolved_root})."
                )

    return {
        **info,
        "tars_root": _canonical_fs_path(root_dir),
        "project_dir": _canonical_fs_path(project_dir),
        "meta_exists": meta_path.is_file(),
        "warning": warning,
    }


def compute_score(
    applied_count: int,
    accepted_count: int,
    last_used: str | _dt.date,
    today: str | _dt.date | None = None,
    decay_lambda: float = DEFAULT_DECAY_LAMBDA,
    superseded: bool = False,
) -> dict[str, Any]:
    """Compute Bayesian-smoothed exponential decay score and lifecycle status."""
    last_dt = _parse_date(last_used)
    today_dt = _parse_date(today)
    delta_t = max(0, (today_dt - last_dt).days)

    raw = ((accepted_count + 1) / (applied_count + 2)) * math.exp(
        -decay_lambda * delta_t
    )
    score = round(raw, 2)

    if superseded:
        status = "deprecated"
    elif score >= ACTIVE_THRESHOLD:
        status = "active"
    elif score >= PROBATION_THRESHOLD:
        status = "probation"
    else:
        status = "deprecated"

    return {
        "applied_count": applied_count,
        "accepted_count": accepted_count,
        "last_used": last_dt.isoformat(),
        "today": today_dt.isoformat(),
        "delta_t": delta_t,
        "score": score,
        "status": status,
        "superseded": superseded,
    }


def next_learning_id(learning_dir: str | Path, prefix: str) -> str:
    """Allocate the next 3-digit ID (scanning all files including deprecated)."""
    clean_prefix = prefix.strip().upper()
    if len(clean_prefix) != 1 or not clean_prefix.isalpha():
        raise ValueError(f"Invalid prefix {prefix!r}; expected single letter (L or P).")

    dir_path = Path(learning_dir)
    max_num = 0
    if dir_path.is_dir():
        for entry in dir_path.iterdir():
            if not entry.is_file():
                continue
            m = _LEARNING_ID_RE.match(entry.name)
            if m and m.group(1) == clean_prefix:
                max_num = max(max_num, int(m.group(2)))
    return f"{clean_prefix}{max_num + 1:03d}"


def _extract_summary(body: str, fallback_id: str) -> str:
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            if heading:
                return heading
        return line
    return fallback_id


def rebuild_index(
    learning_dir: str | Path,
    title: str | None = None,
    today: str | _dt.date | None = None,
    write: bool = False,
    decay_lambda: float = DEFAULT_DECAY_LAMBDA,
) -> dict[str, Any]:
    """Recalculate decay across all rules in learning_dir and rebuild _index.md."""
    dir_path = Path(learning_dir)
    today_dt = _parse_date(today)

    if title is None:
        is_global = dir_path.parent.name == "global"
        title = "Global Learnings Index" if is_global else "Project Learnings Index"

    entries: list[dict[str, Any]] = []
    updated_files: list[str] = []

    if dir_path.is_dir():
        learning_files = sorted(
            p
            for p in dir_path.iterdir()
            if p.is_file() and p.suffix == ".md" and p.name != "_index.md"
        )
        for file_path in learning_files:
            raw_text = file_path.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(raw_text)
            if not fm:
                continue

            rule_id = str(fm.get("id") or file_path.stem.split("_", 1)[0])
            applied = int(fm.get("applied_count", 0))
            accepted = int(fm.get("accepted_count", 0))
            last_used = str(fm.get("last_used") or fm.get("created") or today_dt.isoformat())

            raw_check = compute_score(
                applied, accepted, last_used, today=today_dt, decay_lambda=decay_lambda
            )
            explicitly_superseded = bool(fm.get("superseded_by")) or (
                str(fm.get("status", "")).lower() == "deprecated"
                and raw_check["score"] >= PROBATION_THRESHOLD
            )
            result = compute_score(
                applied,
                accepted,
                last_used,
                today=today_dt,
                decay_lambda=decay_lambda,
                superseded=explicitly_superseded,
            )

            old_score = fm.get("score")
            old_status = str(fm.get("status", ""))
            if write and (
                old_score is None
                or round(float(old_score), 2) != result["score"]
                or old_status != result["status"]
            ):
                new_text = update_frontmatter_fields(
                    raw_text, {"score": result["score"], "status": result["status"]}
                )
                file_path.write_text(new_text, encoding="utf-8")
                updated_files.append(file_path.name)

            if result["status"] in ("active", "probation"):
                tags_raw = fm.get("tags", [])
                tags = tags_raw if isinstance(tags_raw, list) else [str(tags_raw)]
                entries.append(
                    {
                        "id": rule_id,
                        "score": result["score"],
                        "status": result["status"],
                        "tags": [str(t) for t in tags],
                        "summary": _extract_summary(body, rule_id),
                        "file": file_path.name,
                    }
                )

    entries.sort(key=lambda item: (-item["score"], item["id"]))
    index_lines = [
        f"# {title}",
        "<!-- Format: ID | score | tags | one-line summary -->",
    ]
    for item in entries:
        tags_str = "[" + ", ".join(item["tags"]) + "]"
        index_lines.append(
            f"{item['id']} | {item['score']:.2f} | {tags_str} | {item['summary']}"
        )
    index_content = "\n".join(index_lines) + "\n"

    index_path = dir_path / "_index.md"
    if write:
        dir_path.mkdir(parents=True, exist_ok=True)
        index_path.write_text(index_content, encoding="utf-8")

    return {
        "learning_dir": _canonical_fs_path(dir_path),
        "index_path": _canonical_fs_path(index_path),
        "today": today_dt.isoformat(),
        "entry_count": len(entries),
        "entries": entries,
        "updated_files": updated_files,
        "written": write,
    }


def inspect_scratchpad(
    project_dir: str | Path,
    stale_days: int = DEFAULT_STALE_DAYS,
    pause_stale: bool = False,
    today: str | _dt.date | None = None,
) -> dict[str, Any]:
    """Inspect scratchpad tasks, auto-pause stale active/awaiting-go tasks, flag stale paused tasks."""
    proj_path = Path(project_dir)
    scratchpad_dir = proj_path / "scratchpad"
    meta_path = proj_path / "meta.yaml"
    today_dt = _parse_date(today)

    meta = parse_yaml_mapping(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    active_task_id = meta.get("active_task_id")

    tasks: list[dict[str, Any]] = []
    auto_paused: list[str] = []
    stale_paused: list[str] = []
    active_task: str | None = None
    awaiting_go_task: str | None = None
    paused_tasks: list[dict[str, Any]] = []
    clear_active_pointer = False

    if scratchpad_dir.is_dir():
        for task_dir in sorted(p for p in scratchpad_dir.iterdir() if p.is_dir()):
            task_md = task_dir / "task.md"
            if not task_md.is_file():
                continue
            raw_text = task_md.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(raw_text)
            task_id = str(fm.get("id") or task_dir.name)
            status = str(fm.get("status") or "paused")
            updated_raw = str(fm.get("updated") or fm.get("created") or today_dt.isoformat())
            age_days = max(0, (today_dt - _parse_date(updated_raw)).days)
            is_stale = age_days >= stale_days

            if pause_stale and status in ("active", "awaiting-go") and is_stale:
                task_md.write_text(
                    update_frontmatter_fields(raw_text, {"status": "paused"}),
                    encoding="utf-8",
                )
                status = "paused"
                auto_paused.append(task_dir.name)
                if active_task_id == task_dir.name:
                    clear_active_pointer = True

            record = {
                "id": task_id,
                "dir": task_dir.name,
                "status": status,
                "updated": updated_raw,
                "age_days": age_days,
                "stale": is_stale,
                "rework_count": int(fm.get("rework_count", 0)),
                "touched_files": fm.get("touched_files", []),
                "summary": _extract_summary(body, task_dir.name),
            }
            tasks.append(record)

            if status == "active":
                active_task = task_dir.name
            elif status == "awaiting-go":
                awaiting_go_task = task_dir.name
            elif status == "paused":
                paused_tasks.append(record)
                if is_stale:
                    stale_paused.append(task_dir.name)

    if pause_stale and clear_active_pointer and meta_path.is_file():
        meta_raw = meta_path.read_text(encoding="utf-8")
        updated_meta = re.sub(
            r"(?m)^active_task_id:.*$", "active_task_id: null", meta_raw
        )
        meta_path.write_text(updated_meta, encoding="utf-8")
        active_task_id = None

    return {
        "project_dir": _canonical_fs_path(proj_path),
        "today": today_dt.isoformat(),
        "stale_days": stale_days,
        "active_task_id": active_task_id,
        "active_task": active_task,
        "awaiting_go_task": awaiting_go_task,
        "paused_tasks": paused_tasks,
        "auto_paused": auto_paused,
        "stale_paused": stale_paused,
        "tasks": tasks,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tars.py",
        description="Deterministic state, project hashing, decay math, and index helper for TARS.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_proj = sub.add_parser("project-id", help="Resolve normalized project ID and paths.")
    p_proj.add_argument("--repo", default=".", help="Path inside target repository/folder.")
    p_proj.add_argument("--remote", default=None, help="Override git origin remote URL.")
    p_proj.add_argument("--tars-root", default=None, help="Override ~/.tars root path.")
    p_proj.add_argument("--json", action="store_true", help="Emit JSON output.")

    p_score = sub.add_parser("score", help="Calculate decay score and learning status.")
    p_score.add_argument("--applied", type=int, required=True, help="applied_count")
    p_score.add_argument("--accepted", type=int, required=True, help="accepted_count")
    p_score.add_argument("--last-used", required=True, help="last_used date (YYYY-MM-DD)")
    p_score.add_argument("--today", default=None, help="Reference date (YYYY-MM-DD)")
    p_score.add_argument("--superseded", action="store_true", help="Force deprecated status.")
    p_score.add_argument("--lambda", dest="decay_lambda", type=float, default=DEFAULT_DECAY_LAMBDA)
    p_score.add_argument("--json", action="store_true", help="Emit JSON output.")

    p_next = sub.add_parser("next-id", help="Return next 3-digit learning ID (L### or P###).")
    p_next.add_argument("--dir", required=True, help="Learning directory path.")
    p_next.add_argument("--prefix", required=True, choices=["L", "P", "l", "p"], help="ID prefix.")

    p_idx = sub.add_parser("rebuild-index", help="Recalculate decay and rebuild _index.md.")
    p_idx.add_argument("--dir", required=True, help="Learning directory path.")
    p_idx.add_argument("--title", default=None, help="Custom markdown title for _index.md.")
    p_idx.add_argument("--today", default=None, help="Reference date (YYYY-MM-DD).")
    p_idx.add_argument("--write", action="store_true", help="Write updates back to disk.")
    p_idx.add_argument("--lambda", dest="decay_lambda", type=float, default=DEFAULT_DECAY_LAMBDA)
    p_idx.add_argument("--json", action="store_true", help="Emit JSON output.")

    p_stat = sub.add_parser("status", help="Inspect scratchpad tasks and auto-pause stale ones.")
    p_stat.add_argument("--project-dir", required=True, help="Path to ~/.tars/projects/<id>.")
    p_stat.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS)
    p_stat.add_argument("--pause-stale", action="store_true", help="Pause stale active/awaiting-go tasks.")
    p_stat.add_argument("--today", default=None, help="Reference date (YYYY-MM-DD).")
    p_stat.add_argument("--json", action="store_true", help="Emit JSON output.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "project-id":
        res = resolve_project(
            repo_path=args.repo, remote_url=args.remote, tars_root=args.tars_root
        )
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res["warning"]:
                print(f"WARNING: {res['warning']}", file=sys.stderr)
            print(res["project_id"])
        return 0

    if args.command == "score":
        res = compute_score(
            applied_count=args.applied,
            accepted_count=args.accepted,
            last_used=args.last_used,
            today=args.today,
            decay_lambda=args.decay_lambda,
            superseded=args.superseded,
        )
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"{res['score']:.2f} {res['status']}")
        return 0

    if args.command == "next-id":
        print(next_learning_id(args.dir, args.prefix))
        return 0

    if args.command == "rebuild-index":
        res = rebuild_index(
            learning_dir=args.dir,
            title=args.title,
            today=args.today,
            write=args.write,
            decay_lambda=args.decay_lambda,
        )
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"{res['entry_count']} active/probation entries -> {res['index_path']}")
        return 0

    if args.command == "status":
        res = inspect_scratchpad(
            project_dir=args.project_dir,
            stale_days=args.stale_days,
            pause_stale=args.pause_stale,
            today=args.today,
        )
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(
                f"active={res['active_task']} awaiting_go={res['awaiting_go_task']} "
                f"paused={len(res['paused_tasks'])} auto_paused={len(res['auto_paused'])}"
            )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
