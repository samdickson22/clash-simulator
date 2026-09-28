from __future__ import annotations

import argparse
import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import torch
from torch import nn

from clasher.paths import resolve_path
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.model import ClasherPolicy, PolicyConfig, PrototypeRepairAdapter

_STAGE_PREFIXES = ("repair_stages.", "repair_stage_prototype_adapters.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _padded_counts(config: PolicyConfig) -> tuple[int, ...]:
    return config.repair_stage_prototype_counts + (0,) * (
        len(config.repair_stage_sizes)
        - len(config.repair_stage_prototype_counts)
    )


def _padded_thresholds(config: PolicyConfig) -> tuple[float, ...]:
    return config.repair_stage_prototype_thresholds + (
        config.repair_stage_prototype_threshold,
    ) * (
        len(config.repair_stage_sizes)
        - len(config.repair_stage_prototype_thresholds)
    )


def _base_config(config: PolicyConfig) -> dict[str, Any]:
    payload = config.to_dict()
    for key in (
        "repair_stage_sizes",
        "repair_stage_prototype_counts",
        "repair_stage_prototype_threshold",
        "repair_stage_prototype_thresholds",
        "repair_stage_prototype_guard_counts",
        "repair_stage_prototype_guard_thresholds",
        "repair_stage_prototype_hard_guards",
        "repair_stage_yield_to_prior",
    ):
        payload.pop(key)
    return payload


def _verify_shared_base(
    target: ClasherPolicy,
    donor: ClasherPolicy,
) -> None:
    if _base_config(target.config) != _base_config(donor.config):
        raise ValueError("target and donor base policy configurations differ")
    target_state = target.state_dict()
    donor_state = donor.state_dict()
    target_base = {
        name: tensor
        for name, tensor in target_state.items()
        if not name.startswith(_STAGE_PREFIXES)
    }
    donor_base = {
        name: tensor
        for name, tensor in donor_state.items()
        if not name.startswith(_STAGE_PREFIXES)
    }
    if target_base.keys() != donor_base.keys():
        raise ValueError("target and donor base policy state keys differ")
    mismatches = [
        name
        for name in target_base
        if not torch.equal(target_base[name], donor_base[name])
    ]
    if mismatches:
        raise ValueError(f"target and donor base tensors differ: {mismatches[:5]}")


def _greedy_guard_cover(features: torch.Tensor, threshold: float) -> torch.Tensor:
    if not 0.0 <= threshold < 1.0:
        raise ValueError("guard threshold must be in [0, 1)")
    normalized = torch.nn.functional.normalize(features, dim=-1)
    kept_indices: list[int] = []
    for index in range(len(normalized)):
        if not kept_indices:
            kept_indices.append(index)
            continue
        similarities = normalized[index] @ normalized[kept_indices].T
        if bool((similarities <= threshold).all()):
            kept_indices.append(index)
    return features[kept_indices]


def compose_repair_stage(
    *,
    target_path: Path,
    donor_path: Path,
    output_path: Path,
    decks_path: Path,
    guard_features_path: Path | None = None,
    guard_threshold: float = 0.99999,
    donor_stage_index: int | None = None,
) -> None:
    device = torch.device("cpu")
    target = load_policy_checkpoint(
        target_path,
        device=device,
        decks_path=decks_path,
    )
    donor = load_policy_checkpoint(
        donor_path,
        device=device,
        decks_path=decks_path,
    )
    if target.checkpoint["token_names"] != donor.checkpoint["token_names"]:
        raise ValueError("target and donor token vocabularies differ")
    donor_stage_count = len(donor.model.config.repair_stage_sizes)
    if donor_stage_index is None:
        if donor_stage_count != 1:
            raise ValueError(
                "donor checkpoint contains multiple repair stages; "
                "select one with --donor-stage-index"
            )
        donor_stage_index = 0
    if not 0 <= donor_stage_index < donor_stage_count:
        raise ValueError("donor stage index is out of range")
    _verify_shared_base(target.model, donor.model)

    target_config = target.model.config
    donor_config = donor.model.config
    target_stage_index = len(target_config.repair_stage_sizes)
    donor_counts = _padded_counts(donor_config)
    donor_thresholds = _padded_thresholds(donor_config)
    guard_features: torch.Tensor | None = None
    raw_guard_count = guard_count = 0
    if guard_features_path is not None:
        guard_payload = torch.load(
            guard_features_path,
            map_location="cpu",
            weights_only=False,
        )
        guard_features = torch.as_tensor(guard_payload["repair_features"]).float()
        donor_stage = cast(nn.Sequential, donor.model.repair_stages[donor_stage_index])
        first_layer = cast(nn.Linear, donor_stage[0])
        expected_feature_size = first_layer.in_features
        if guard_features.ndim != 2 or guard_features.shape[1] != expected_feature_size:
            raise ValueError(
                "guard repair feature shape mismatch: "
                f"expected (*, {expected_feature_size}), got {tuple(guard_features.shape)}"
            )
        raw_guard_count = int(guard_features.shape[0])
        guard_features = _greedy_guard_cover(guard_features, guard_threshold)
        guard_count = int(guard_features.shape[0])
    expanded_config = replace(
        target_config,
        repair_stage_sizes=(
            *target_config.repair_stage_sizes,
            donor_config.repair_stage_sizes[donor_stage_index],
        ),
        repair_stage_prototype_counts=(
            *_padded_counts(target_config),
            guard_count + donor_counts[donor_stage_index],
        ),
        repair_stage_prototype_thresholds=(
            *_padded_thresholds(target_config),
            donor_thresholds[donor_stage_index],
        ),
        repair_stage_prototype_guard_counts=(
            *target_config.repair_stage_prototype_guard_counts,
            *((0,) * (
                len(target_config.repair_stage_sizes)
                - len(target_config.repair_stage_prototype_guard_counts)
            )),
            guard_count,
        ),
        repair_stage_prototype_guard_thresholds=(
            *target_config.repair_stage_prototype_guard_thresholds,
            *((target_config.repair_stage_prototype_threshold,) * (
                len(target_config.repair_stage_sizes)
                - len(target_config.repair_stage_prototype_guard_thresholds)
            )),
            guard_threshold,
        ),
        repair_stage_prototype_hard_guards=(
            *target_config.repair_stage_prototype_hard_guards,
            *((False,) * (
                len(target_config.repair_stage_sizes)
                - len(target_config.repair_stage_prototype_hard_guards)
            )),
            guard_count > 0,
        ),
        repair_stage_yield_to_prior=(
            *target_config.repair_stage_yield_to_prior,
            *((False,) * (
                len(target_config.repair_stage_sizes)
                - len(target_config.repair_stage_yield_to_prior)
            )),
            True,
        ),
    )
    expanded = ClasherPolicy(
        expanded_config,
        target.builder.card_stat_features,
    )
    incompatible = expanded.load_state_dict(target.model.state_dict(), strict=False)
    allowed_missing = (
        f"repair_stages.{target_stage_index}.",
        f"repair_stage_prototype_adapters.{target_stage_index}.",
    )
    if incompatible.unexpected_keys or any(
        not name.startswith(allowed_missing) for name in incompatible.missing_keys
    ):
        raise RuntimeError(f"unexpected target expansion mismatch: {incompatible}")

    expanded_state = expanded.state_dict()
    donor_state = donor.model.state_dict()
    copied_names: list[str] = []
    donor_stage_prefix = f"repair_stages.{donor_stage_index}."
    for donor_name, donor_tensor in donor_state.items():
        if not donor_name.startswith(donor_stage_prefix):
            continue
        target_name = (
            f"repair_stages.{target_stage_index}."
            + donor_name.removeprefix(donor_stage_prefix)
        )
        if target_name not in expanded_state:
            raise KeyError(f"missing composed state target {target_name}")
        if expanded_state[target_name].shape != donor_tensor.shape:
            raise ValueError(f"shape mismatch for {target_name}")
        expanded_state[target_name].copy_(donor_tensor)
        copied_names.append(target_name)
    donor_adapter = cast(
        PrototypeRepairAdapter,
        donor.model.repair_stage_prototype_adapters[str(donor_stage_index)],
    )
    target_adapter = cast(
        PrototypeRepairAdapter,
        expanded.repair_stage_prototype_adapters[str(target_stage_index)],
    )
    with torch.no_grad():
        if guard_features is not None:
            target_adapter.prototypes[:guard_count].copy_(guard_features)
        target_adapter.prototypes[guard_count:].copy_(donor_adapter.prototypes)
        target_adapter.deltas[guard_count:].copy_(donor_adapter.deltas)
    copied_names.extend(
        [
            f"repair_stage_prototype_adapters.{target_stage_index}.prototypes",
            f"repair_stage_prototype_adapters.{target_stage_index}.deltas",
        ]
    )
    if not copied_names:
        raise ValueError("donor repair stage contained no state tensors")
    expanded.load_state_dict(expanded_state)

    payload = dict(target.checkpoint)
    payload.pop("optimizer_state", None)
    payload.pop("optimizer_state_dict", None)
    payload["model_config"] = expanded_config.to_dict()
    payload["model_state_dict"] = expanded.state_dict()
    payload["hybrid_repair_stage"] = {
        "target_checkpoint": str(target_path),
        "target_sha256": _sha256(target_path),
        "donor_checkpoint": str(donor_path),
        "donor_sha256": _sha256(donor_path),
        "target_stage_index": target_stage_index,
        "donor_stage_index": donor_stage_index,
        "guard_features": (
            str(guard_features_path) if guard_features_path is not None else None
        ),
        "guard_count": guard_count,
        "raw_guard_count": raw_guard_count,
        "guard_threshold": guard_threshold,
        "copied_state_names": copied_names,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    torch.save(payload, temporary_path)
    temporary_path.replace(output_path)
    print(f"saved={output_path}")
    print(f"sha256={_sha256(output_path)}")
    print(f"stages={expanded_config.repair_stage_sizes}")
    print(f"prototype_counts={expanded_config.repair_stage_prototype_counts}")
    print(
        "prototype_thresholds="
        f"{expanded_config.repair_stage_prototype_thresholds}"
    )
    print(f"yield_to_prior={expanded_config.repair_stage_yield_to_prior}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append one verified repair stage to a retained V2 policy."
    )
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--decks", type=Path, default=Path("decks.json"))
    parser.add_argument("--guard-features", type=Path, default=None)
    parser.add_argument("--guard-threshold", type=float, default=0.99999)
    parser.add_argument("--donor-stage-index", type=int, default=None)
    args = parser.parse_args()
    compose_repair_stage(
        target_path=resolve_path(args.target),
        donor_path=resolve_path(args.donor),
        output_path=resolve_path(args.output),
        decks_path=resolve_path(args.decks),
        guard_features_path=(
            resolve_path(args.guard_features, must_exist=True)
            if args.guard_features is not None
            else None
        ),
        guard_threshold=args.guard_threshold,
        donor_stage_index=args.donor_stage_index,
    )


if __name__ == "__main__":
    main()
