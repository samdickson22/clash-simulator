# mypy: disable-error-code="import-untyped"

"""Verify a bounded RL phase changed both value and actor policy tensors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch


def audit_state_dict_changes(
    before_state: dict[str, torch.Tensor],
    after_state: dict[str, torch.Tensor],
    *,
    actor_prefixes: tuple[str, ...],
    value_prefixes: tuple[str, ...],
    allowed_added_prefixes: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Require declared-prefix isolation and both actor/value update groups.

    Schema additions are rejected unless every new parameter matches an explicit
    ``allowed_added_prefixes`` entry. Removals are always rejected.
    """
    if not actor_prefixes or not value_prefixes:
        raise ValueError("actor and value prefix groups must both be non-empty")
    if any(not prefix for prefix in (*actor_prefixes, *value_prefixes)):
        raise ValueError("state-dict prefixes must be non-empty")
    if set(actor_prefixes) & set(value_prefixes):
        raise ValueError("actor and value prefix groups must be disjoint")
    removed = [name for name in before_state if name not in after_state]
    added = [name for name in after_state if name not in before_state]
    if removed:
        raise ValueError("RL phase removed parameters from the model state schema")
    unauthorized_added = [
        name for name in added if not name.startswith(allowed_added_prefixes)
    ]
    if unauthorized_added:
        raise ValueError("RL phase added unauthorized parameters to the model state schema")

    changed = added + [
        name
        for name in before_state
        if not torch.equal(before_state[name], after_state[name])
    ]
    allowed = (*actor_prefixes, *value_prefixes)
    unauthorized = [name for name in changed if not name.startswith(allowed)]
    actor_changes = [name for name in changed if name.startswith(actor_prefixes)]
    value_changes = [name for name in changed if name.startswith(value_prefixes)]
    passes = bool(actor_changes) and bool(value_changes) and not unauthorized
    return {
        "schema_version": 1,
        "changed_parameters": changed,
        "changed_parameter_count": len(changed),
        "actor_changed_parameters": actor_changes,
        "actor_changed_parameter_count": len(actor_changes),
        "value_changed_parameters": value_changes,
        "value_changed_parameter_count": len(value_changes),
        "unauthorized_changes": unauthorized,
        "added_parameters": added,
        "allowed_added_prefixes": list(allowed_added_prefixes),
        "actor_prefixes": list(actor_prefixes),
        "value_prefixes": list(value_prefixes),
        "passes": passes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--actor-prefix", action="append", required=True)
    parser.add_argument("--value-prefix", action="append", required=True)
    parser.add_argument("--allow-added-prefix", action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    before = torch.load(args.before, map_location="cpu", weights_only=False)
    after = torch.load(args.after, map_location="cpu", weights_only=False)
    report = audit_state_dict_changes(
        before["model_state_dict"],
        after["model_state_dict"],
        actor_prefixes=tuple(args.actor_prefix),
        value_prefixes=tuple(args.value_prefix),
        allowed_added_prefixes=tuple(args.allow_added_prefix),
    )
    report.update(
        {
            "before": str(args.before.resolve()),
            "after": str(args.after.resolve()),
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["passes"]:
        raise SystemExit("RL state-dict change audit failed")
    print(json.dumps({"status": "rl_state_dict_change_audit_complete", **report}))


if __name__ == "__main__":
    main()
