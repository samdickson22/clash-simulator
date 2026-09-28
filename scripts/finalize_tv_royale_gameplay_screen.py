"""Fail-closed finalization for the TV Royale 2,000-game gameplay screen."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return payload


def _same_checkpoint(left: str, right: str) -> bool:
    return Path(left).expanduser().resolve() == Path(right).expanduser().resolve()


def _game_count(payload: dict[str, Any]) -> int:
    if "games" in payload:
        return int(payload["games"])
    return sum(int(payload.get(key, 0)) for key in ("wins", "losses", "draws"))


def finalize_gameplay_screen(
    *,
    screen_root: Path,
    development_selected_path: Path,
    promotion_candidate_path: Path,
) -> dict[str, Any]:
    """Publish a candidate only when every staged gate passed for one checkpoint."""
    promotion_candidate_path.parent.mkdir(parents=True, exist_ok=True)
    promotion_candidate_path.write_text("", encoding="utf-8")
    selected = development_selected_path.read_text(encoding="utf-8").strip()
    if not selected:
        return {
            "schema_version": 1,
            "status": "no_development_candidate",
            "promotion_eligible": False,
            "checkpoint": None,
        }
    if not Path(selected).expanduser().resolve().is_file():
        raise FileNotFoundError(f"selected checkpoint does not exist: {selected}")

    summaries = {
        "development": _load_object(screen_root / "development_screen_summary.json"),
        "expanded": _load_object(screen_root / "expanded" / "expanded_summary.json"),
        "priority": _load_object(screen_root / "priority" / "priority_summary.json"),
        "full168": _load_object(screen_root / "full168" / "full168_summary.json"),
        "human_meta": _load_object(screen_root / "human_meta" / "summary.json"),
    }
    development_rows = summaries["development"].get("candidates")
    if not isinstance(development_rows, list):
        raise TypeError("development summary needs a candidate list")
    matching_development = [
        row
        for row in development_rows
        if isinstance(row, dict)
        and isinstance(row.get("checkpoint"), str)
        and _same_checkpoint(row["checkpoint"], selected)
    ]
    if len(matching_development) != 1:
        raise ValueError("development selection does not identify exactly one candidate")
    development = matching_development[0]

    checkpoint_mismatches = [
        name
        for name in ("expanded", "priority", "full168", "human_meta")
        if not isinstance(summaries[name].get("checkpoint"), str)
        or not _same_checkpoint(summaries[name]["checkpoint"], selected)
    ]
    evidence_counts = {
        "development": _game_count(development),
        "expanded": _game_count(summaries["expanded"]),
        "priority": _game_count(summaries["priority"]),
        "full168": _game_count(summaries["full168"]),
        "human_meta": _game_count(summaries["human_meta"]),
    }
    required_evidence_counts = {
        "development": 24,
        "expanded": 96,
        "priority": 60,
        "full168": 168,
        "human_meta": 128,
    }
    gates = {
        "development": int(development["wins"]) > int(development["losses"]),
        "expanded": int(summaries["expanded"]["wins"])
        > int(summaries["expanded"]["losses"]),
        "priority": summaries["priority"].get("passes_strict_no_regression") is True,
        "full168": summaries["full168"].get("passes_strict_no_regression") is True,
        "human_meta": summaries["human_meta"].get("passes_human_meta_gate") is True,
        "checkpoint_consistency": not checkpoint_mismatches,
        "complete_evidence_counts": evidence_counts == required_evidence_counts,
        "human_meta_evaluation_only": (
            summaries["human_meta"].get("evaluation_only") is True
            and summaries["human_meta"].get("training_action_labels_used") is False
        ),
    }
    eligible = all(gates.values())
    payload = {
        "schema_version": 1,
        "status": "promotion_candidate_ready" if eligible else "promotion_rejected",
        "promotion_eligible": eligible,
        "checkpoint": selected,
        "gates": gates,
        "checkpoint_mismatches": checkpoint_mismatches,
        "evidence_counts": evidence_counts,
        "required_evidence_counts": required_evidence_counts,
    }
    if eligible:
        promotion_candidate_path.write_text(selected + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screen-root", required=True, type=Path)
    parser.add_argument("--development-selected", required=True, type=Path)
    parser.add_argument("--promotion-candidate", required=True, type=Path)
    parser.add_argument("--summary-out", required=True, type=Path)
    args = parser.parse_args()
    payload = finalize_gameplay_screen(
        screen_root=args.screen_root,
        development_selected_path=args.development_selected,
        promotion_candidate_path=args.promotion_candidate,
    )
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
