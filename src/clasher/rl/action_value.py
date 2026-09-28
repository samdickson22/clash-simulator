from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn

from .counterfactual_corpus import CandidateContext


@dataclass(frozen=True)
class ActionValueConfig:
    state_size: int
    card_feature_size: int
    tile_feature_size: int
    state_hidden_size: int = 128
    action_hidden_size: int = 128
    hidden_size: int = 128
    base_relative_interactions: bool = False


class PublicActionValueHead(nn.Module):
    """Small action-conditioned ranker over frozen public policy features."""

    def __init__(self, config: ActionValueConfig) -> None:
        super().__init__()
        self.config = config
        self.state_encoder = nn.Sequential(
            nn.LayerNorm(config.state_size),
            nn.Linear(config.state_size, config.state_hidden_size),
            nn.GELU(),
            nn.Linear(config.state_hidden_size, config.hidden_size),
            nn.GELU(),
        )
        action_size = (
            config.card_feature_size
            + config.tile_feature_size
            + 3
            + 2
        )
        self.action_encoder = nn.Sequential(
            nn.LayerNorm(action_size),
            nn.Linear(action_size, config.action_hidden_size),
            nn.GELU(),
            nn.Linear(config.action_hidden_size, config.hidden_size),
            nn.GELU(),
        )
        scorer_inputs = 7 if config.base_relative_interactions else 3
        self.scorer = nn.Sequential(
            nn.Linear(scorer_inputs * config.hidden_size, config.hidden_size),
            nn.GELU(),
            nn.Linear(config.hidden_size, 1),
        )

    def forward(
        self,
        state_features: Tensor,
        card_features: Tensor,
        tile_features: Tensor,
        action_kinds: Tensor,
        policy_log_probabilities: Tensor,
        policy_type_log_probabilities: Tensor,
    ) -> Tensor:
        if state_features.shape[:-1] != card_features.shape[:-2]:
            raise ValueError("state and candidate batch dimensions do not match")
        if card_features.shape[:-1] != tile_features.shape[:-1]:
            raise ValueError("candidate card and tile dimensions do not match")
        kinds = torch.nn.functional.one_hot(
            action_kinds.clamp(0, 2).long(),
            num_classes=3,
        ).to(card_features.dtype)
        policy = torch.stack(
            (
                policy_log_probabilities.clamp(-20.0, 0.0) / 20.0,
                policy_type_log_probabilities.clamp(-20.0, 0.0) / 20.0,
            ),
            dim=-1,
        )
        action_input = torch.cat(
            (card_features, tile_features, kinds, policy),
            dim=-1,
        )
        state = self.state_encoder(state_features)
        action = self.action_encoder(action_input)
        state = state.unsqueeze(-2).expand_as(action)
        if self.config.base_relative_interactions:
            base = action[..., :1, :].expand_as(action)
            score_inputs = torch.cat(
                (
                    state,
                    action,
                    base,
                    action - base,
                    action * base,
                    state * action,
                    state * (action - base),
                ),
                dim=-1,
            )
        else:
            score_inputs = torch.cat((state, action, state * action), dim=-1)
        score: Tensor = self.scorer(score_inputs).squeeze(-1)
        if self.config.base_relative_interactions:
            score = score - score[..., :1]
        return score


@dataclass(frozen=True)
class LoadedPublicActionValueHead:
    head: PublicActionValueHead
    source_policy: str
    source_policy_sha256: str | None
    corpus_sha256: str
    minimum_score_gain: float

    @torch.no_grad()
    def score_candidates(
        self,
        state_features: Tensor,
        context: CandidateContext,
    ) -> np.ndarray:
        device = next(self.head.parameters()).device
        state = state_features.detach().to(device=device, dtype=torch.float32)
        if state.ndim != 1:
            raise ValueError("action-value state features must be rank one")
        scores = self.head(
            state.unsqueeze(0),
            torch.as_tensor(context.card_features, device=device).unsqueeze(0),
            torch.as_tensor(context.tile_features, device=device).unsqueeze(0),
            torch.as_tensor(context.kinds, device=device).unsqueeze(0),
            torch.as_tensor(
                context.policy_log_probabilities,
                device=device,
            ).unsqueeze(0),
            torch.as_tensor(
                context.policy_type_log_probabilities,
                device=device,
            ).unsqueeze(0),
        )[0]
        valid = torch.as_tensor(context.valid, device=device)
        result = np.asarray(
            scores.masked_fill(~valid, -torch.inf).cpu().numpy(),
            dtype=np.float32,
        )
        return result

    @torch.no_grad()
    def select_candidate(
        self,
        state_features: Tensor,
        context: CandidateContext,
    ) -> tuple[int, np.ndarray]:
        scores = self.score_candidates(state_features, context)
        best = int(np.argmax(scores))
        if scores[best] <= scores[0] + self.minimum_score_gain:
            return 0, scores
        return best, scores


@dataclass(frozen=True)
class LoadedPublicActionValueEnsemble:
    """Conservative candidate selector over independently fitted rankers.

    Member disagreement is treated as model uncertainty.  The selector ranks
    each intervention by a lower dispersion bound on its paired score gain
    over the frozen actor's base action; it never compares unpaired absolute
    head scales.
    """

    members: tuple[LoadedPublicActionValueHead, ...]
    dispersion_scale: float
    minimum_lower_bound_gain: float
    member_gain_scales: tuple[float, ...]
    aggregation: str = "mean-lower-bound"

    def __post_init__(self) -> None:
        if len(self.members) < 3:
            raise ValueError("action-value ensemble requires at least three members")
        if self.dispersion_scale < 0.0:
            raise ValueError("ensemble dispersion scale must be nonnegative")
        if self.minimum_lower_bound_gain < 0.0:
            raise ValueError("ensemble minimum gain must be nonnegative")
        if len(self.member_gain_scales) != len(self.members) or any(
            not math.isfinite(value) or value <= 0.0
            for value in self.member_gain_scales
        ):
            raise ValueError("ensemble member gain scales are invalid")
        if self.aggregation not in {"mean-lower-bound", "median"}:
            raise ValueError("ensemble aggregation is invalid")
        source_policies = {member.source_policy for member in self.members}
        source_policy_hashes = {
            member.source_policy_sha256 for member in self.members
        }
        corpus_hashes = {member.corpus_sha256 for member in self.members}
        if len(source_policies) != 1:
            raise ValueError("ensemble members target different source policies")
        if len(source_policy_hashes) != 1:
            raise ValueError("ensemble members target different policy hashes")
        if len(corpus_hashes) != 1:
            raise ValueError("ensemble members use different training corpora")

    @property
    def source_policy(self) -> str:
        return self.members[0].source_policy

    @property
    def corpus_sha256(self) -> str:
        return self.members[0].corpus_sha256

    @property
    def source_policy_sha256(self) -> str | None:
        return self.members[0].source_policy_sha256

    @torch.no_grad()
    def score_candidates(
        self,
        state_features: Tensor,
        context: CandidateContext,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        member_scores = np.stack(
            [member.score_candidates(state_features, context) for member in self.members]
        ).astype(np.float32, copy=False)
        paired_gains = np.where(
            context.valid[None, :],
            member_scores - member_scores[:, :1],
            0.0,
        )
        paired_gains = paired_gains / np.asarray(
            self.member_gain_scales, dtype=np.float32
        )[:, None]
        gain_mean = paired_gains.mean(axis=0)
        gain_dispersion = paired_gains.std(axis=0, ddof=1)
        aggregate = (
            np.median(paired_gains, axis=0)
            if self.aggregation == "median"
            else gain_mean
        )
        lower_gain = (
            aggregate
            if self.aggregation == "median"
            else aggregate - self.dispersion_scale * gain_dispersion
        )
        lower_gain[~context.valid] = -np.inf
        lower_gain[0] = 0.0
        return aggregate, gain_dispersion, lower_gain

    @torch.no_grad()
    def select_candidate(
        self,
        state_features: Tensor,
        context: CandidateContext,
    ) -> tuple[int, np.ndarray, np.ndarray, np.ndarray]:
        mean_scores, gain_dispersion, lower_gain = self.score_candidates(
            state_features,
            context,
        )
        best = int(np.argmax(lower_gain))
        if lower_gain[best] <= self.minimum_lower_bound_gain:
            best = 0
        return best, mean_scores, gain_dispersion, lower_gain


def load_public_action_value_head(
    checkpoint_path: Path,
    *,
    device: torch.device,
) -> LoadedPublicActionValueHead:
    payload: dict[str, Any] = torch.load(
        checkpoint_path,
        map_location=device,
        weights_only=False,
    )
    if int(payload.get("schema_version", 0)) != 1:
        raise ValueError("unsupported public action-value checkpoint schema")
    config = ActionValueConfig(**dict(payload["config"]))
    head = PublicActionValueHead(config).to(device)
    head.load_state_dict(payload["state_dict"])
    head.eval()
    return LoadedPublicActionValueHead(
        head=head,
        source_policy=str(payload["source_policy"]),
        source_policy_sha256=(
            str(payload["source_policy_sha256"])
            if payload.get("source_policy_sha256") is not None
            else None
        ),
        corpus_sha256=str(payload["corpus_sha256"]),
        minimum_score_gain=float(payload.get("minimum_score_gain", 0.0)),
    )


def load_public_action_value_ensemble(
    manifest_path: Path,
    *,
    device: torch.device,
) -> LoadedPublicActionValueEnsemble:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "clasher.public_action_value_ensemble.v1":
        raise ValueError("unsupported public action-value ensemble schema")
    calibration_value = payload.get("calibration_report")
    calibration_sha256 = payload.get("calibration_report_sha256")
    if not isinstance(calibration_value, str) or not isinstance(
        calibration_sha256, str
    ):
        raise TypeError("ensemble manifest lacks calibration authority")
    calibration_path = (
        Path(calibration_value)
        if Path(calibration_value).is_absolute()
        else manifest_path.parent / Path(calibration_value)
    ).resolve()
    if hashlib.sha256(calibration_path.read_bytes()).hexdigest() != calibration_sha256:
        raise ValueError("ensemble calibration report hash mismatch")
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    if calibration.get("schema") != (
        "clasher.public_action_value_ensemble_calibration.v1"
    ) or calibration.get("passed") is not True:
        raise ValueError("ensemble calibration did not pass")
    selected = calibration.get("selected")
    if not isinstance(selected, dict):
        raise TypeError("ensemble calibration lacks a selected configuration")
    selected_controller = calibration.get("selected_controller")
    if not isinstance(selected_controller, dict) or selected_controller.get(
        "kind"
    ) != "ensemble":
        raise ValueError("ensemble was not the calibrated controller")
    raw_members = payload.get("members")
    if not isinstance(raw_members, list) or len(raw_members) < 3:
        raise ValueError("ensemble manifest needs at least three member paths")
    member_paths = tuple(
        (
            Path(value)
            if Path(value).is_absolute()
            else manifest_path.parent / Path(value)
        ).resolve()
        for value in raw_members
        if isinstance(value, str)
    )
    members = tuple(
        load_public_action_value_head(
            member_path,
            device=device,
        )
        for member_path in member_paths
    )
    if len(members) != len(raw_members):
        raise TypeError("ensemble member paths must be strings")
    report_member_hashes = calibration.get("member_sha256")
    member_hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in member_paths]
    if report_member_hashes != member_hashes:
        raise ValueError("ensemble members differ from calibration authority")
    dispersion_scale = float(payload.get("dispersion_scale", 1.0))
    minimum_gain = float(payload.get("minimum_lower_bound_gain", 0.0))
    raw_gain_scales = payload.get("member_gain_scales")
    if not isinstance(raw_gain_scales, list):
        raise TypeError("ensemble manifest lacks member gain scales")
    member_gain_scales = tuple(float(value) for value in raw_gain_scales)
    aggregation = str(payload.get("aggregation", "mean-lower-bound"))
    if dispersion_scale != float(selected.get("dispersion_scale", math.nan)):
        raise ValueError("ensemble dispersion differs from calibration")
    if minimum_gain != float(
        selected.get("minimum_lower_bound_gain", math.nan)
    ):
        raise ValueError("ensemble threshold differs from calibration")
    if list(member_gain_scales) != calibration.get("member_gain_scales"):
        raise ValueError("ensemble member scales differ from calibration")
    if aggregation != str(selected.get("aggregation", "mean-lower-bound")):
        raise ValueError("ensemble aggregation differs from calibration")
    ensemble = LoadedPublicActionValueEnsemble(
        members=members,
        dispersion_scale=dispersion_scale,
        minimum_lower_bound_gain=minimum_gain,
        member_gain_scales=member_gain_scales,
        aggregation=aggregation,
    )
    if ensemble.source_policy_sha256 is None:
        raise ValueError("ensemble members lack portable source-policy hashes")
    if calibration.get("source_policy_sha256") != ensemble.source_policy_sha256:
        raise ValueError("ensemble source policy differs from calibration")
    return ensemble


def load_public_action_value_controller(
    selection_path: Path,
    *,
    device: torch.device,
) -> LoadedPublicActionValueHead | LoadedPublicActionValueEnsemble:
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "clasher.public_action_value_controller.v1":
        raise ValueError("unsupported public action-value controller schema")
    kind = payload.get("kind")
    if kind not in {"single", "ensemble"}:
        raise ValueError("unknown public action-value controller kind")

    def resolve(value: Any, label: str) -> Path:
        if not isinstance(value, str):
            raise TypeError(f"controller {label} path must be a string")
        path = Path(value)
        return (path if path.is_absolute() else selection_path.parent / path).resolve()

    artifact_path = resolve(payload.get("artifact"), "artifact")
    artifact_sha256 = payload.get("artifact_sha256")
    if not isinstance(artifact_sha256, str) or hashlib.sha256(
        artifact_path.read_bytes()
    ).hexdigest() != artifact_sha256:
        raise ValueError("controller artifact hash mismatch")
    calibration_path = resolve(
        payload.get("calibration_report"), "calibration report"
    )
    calibration_sha256 = payload.get("calibration_report_sha256")
    if not isinstance(calibration_sha256, str) or hashlib.sha256(
        calibration_path.read_bytes()
    ).hexdigest() != calibration_sha256:
        raise ValueError("controller calibration hash mismatch")
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    selected = calibration.get("selected_controller")
    if (
        calibration.get("schema")
        != "clasher.public_action_value_ensemble_calibration.v1"
        or calibration.get("passed") is not True
        or not isinstance(selected, dict)
        or selected.get("kind") != kind
    ):
        raise ValueError("controller differs from passing calibration")
    if kind == "ensemble":
        controller: LoadedPublicActionValueHead | LoadedPublicActionValueEnsemble = (
            load_public_action_value_ensemble(artifact_path, device=device)
        )
    else:
        member_index = selected.get("member_index")
        members = calibration.get("single_members")
        if not isinstance(member_index, int) or not isinstance(members, list):
            raise ValueError("single controller lacks calibrated member identity")
        try:
            member_report = members[member_index]
        except IndexError as error:
            raise ValueError("single controller member index is out of range") from error
        if not isinstance(member_report, dict) or member_report.get(
            "checkpoint_sha256"
        ) != artifact_sha256:
            raise ValueError("single controller differs from calibrated member")
        controller = load_public_action_value_head(artifact_path, device=device)
    source_sha256 = payload.get("source_policy_sha256")
    if not isinstance(source_sha256, str) or source_sha256 != (
        controller.source_policy_sha256
    ):
        raise ValueError("controller source policy hash mismatch")
    if calibration.get("source_policy_sha256") != source_sha256:
        raise ValueError("controller calibration policy hash mismatch")
    return controller


def public_action_value_checkpoint(
    *,
    head: PublicActionValueHead,
    source_policy: str,
    source_policy_sha256: str | None = None,
    corpus_sha256: str,
    minimum_score_gain: float = 0.0,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "config": asdict(head.config),
        "source_policy": source_policy,
        "source_policy_sha256": source_policy_sha256,
        "corpus_sha256": corpus_sha256,
        "minimum_score_gain": minimum_score_gain,
        "state_dict": head.state_dict(),
    }
