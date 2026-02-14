from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


PathLike = str | Path

_PROJECT_MARKERS = ("pyproject.toml", "gamedata.json")


def _find_root_from(start: Path) -> Optional[Path]:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if all((candidate / marker).exists() for marker in _PROJECT_MARKERS):
            return candidate
    return None


def project_root() -> Path:
    env_root = os.environ.get("CLASHER_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    cwd_root = _find_root_from(Path.cwd())
    if cwd_root is not None:
        return cwd_root

    module_root = _find_root_from(Path(__file__))
    if module_root is not None:
        return module_root

    # Fallback for editable installs and local source tree.
    return Path(__file__).resolve().parents[2]


def _to_abs(path: Path) -> Path:
    return path.expanduser().resolve()


def resolve_path(path: PathLike, *, must_exist: bool = False) -> Path:
    raw = Path(path).expanduser()
    candidates = [_to_abs(raw)] if raw.is_absolute() else [_to_abs(Path.cwd() / raw), _to_abs(project_root() / raw)]

    seen: set[Path] = set()
    deduped: list[Path] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)

    for candidate in deduped:
        if candidate.exists():
            return candidate

    chosen = deduped[-1] if deduped else _to_abs(raw)
    if must_exist:
        raise FileNotFoundError(f"path not found: {path} (resolved candidate: {chosen})")
    return chosen


def gamedata_path(path: PathLike | None = None, *, must_exist: bool = True) -> Path:
    target = path if path is not None else project_root() / "gamedata.json"
    return resolve_path(target, must_exist=must_exist)


def decks_path(path: PathLike | None = None, *, must_exist: bool = True) -> Path:
    target = path if path is not None else project_root() / "decks.json"
    return resolve_path(target, must_exist=must_exist)


def hitboxes_path(path: PathLike | None = None, *, must_exist: bool = True) -> Path:
    target = path if path is not None else project_root() / "hitboxes.json"
    return resolve_path(target, must_exist=must_exist)


def checkpoints_dir(path: PathLike | None = None, *, create: bool = False) -> Path:
    target = path if path is not None else project_root() / "checkpoints"
    resolved = resolve_path(target, must_exist=False)
    if create:
        resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def latest_checkpoint(checkpoint_dir: PathLike, pattern: str = "policy_update_*.pt") -> Path | None:
    try:
        resolved_dir = resolve_path(checkpoint_dir, must_exist=True)
    except FileNotFoundError:
        return None
    if not resolved_dir.is_dir():
        raise NotADirectoryError(f"checkpoint_dir is not a directory: {resolved_dir}")
    candidates = sorted(resolved_dir.glob(pattern))
    return candidates[-1] if candidates else None
