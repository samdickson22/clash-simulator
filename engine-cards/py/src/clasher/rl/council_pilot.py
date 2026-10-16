"""Validated local execution contract for the admitted council pilot."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
from typing import Literal

import tomllib
from pydantic import BaseModel, ConfigDict, Field, model_validator

# Admission scope (reports/strategy_council_20260928/pilot/admission-scope-decision.json).
# The Tier A admission binds the admitted simulator scope: every src/clasher module
# except this explicit training-only list must be byte-identical to the admission
# pins. Training-only modules are pinned by the pilot's own source freeze instead.
# None of them may change what the policy observes, which actions are legal, the
# game dynamics, the reward or opponent behavior; the symbols they export to
# admission-bound modules (and the extra roots below) stay admission-bound at the
# AST level, so only orchestration, learner and throughput code may change.
PILOT_SCOPE_DECISION_ID = "council-pilot-admission-scope-v1"
PILOT_TRAINING_ONLY_MODULES: tuple[str, ...] = (
    "src/clasher/rl/council_budget.py",
    "src/clasher/rl/council_evaluation.py",
    "src/clasher/rl/council_monitor.py",
    "src/clasher/rl/council_pilot.py",
    "src/clasher/rl/council_warmstart.py",
    "src/clasher/rl/imitation.py",
    "src/clasher/rl/parallel_rollout.py",
    "src/clasher/rl/shared_rollout_ipc.py",
    "src/clasher/rl/train_recurrent.py",
)
# Top-level definitions inside training-only modules that must stay AST-identical
# to the admitted source, together with every same-module definition they
# reference. Names that admission-bound modules import from a training-only module
# are added automatically (for example ``_stack_step_inputs``, which the admitted
# opponent adapter and evaluator use to build policy inputs).
PILOT_BOUND_SYMBOLS: dict[str, tuple[str, ...]] = {
    "src/clasher/rl/council_pilot.py": (
        "COUNCIL_INITIALIZATION_BY_ARM",
        "admission_path_for_phase",
        "build_council_model_config",
        "critic_warmup_updates_for_arm",
        "evaluation_commands",
        "publish_initial_pool",
        "require_initialized_weights",
        "retain_league_checkpoint",
        "state_dict_sha256",
        "validate_council_initial_policy",
    ),
    "src/clasher/rl/train_recurrent.py": (
        "RolloutBatch",
        "collect_rollout",
        "collect_rollout_stationary_opponents",
        "compute_gae",
        "ppo_update",
        "planned_rollout_steps",
        "save_checkpoint",
    ),
    "src/clasher/rl/parallel_rollout.py": (
        "ActorWorkerConfig",
        "OpponentSpec",
        "ParallelRolloutCollector",
        "build_policy_observation_builder",
        "concatenate_rollouts",
        "load_checkpoint_opponent",
        "opponent_spec_for_worker",
    ),
}
# Coordinator-authorized training-only extension for stored-state replay.
# Legacy runtimes retain their exact module set and definition bindings.
PILOT_TBPTT_MODULE = "src/clasher/rl/tbptt.py"
PILOT_TBPTT_LEARNER_SYMBOLS = {
    "src/clasher/rl/train_recurrent.py": frozenset((
        "RolloutBatch", "collect_rollout", "collect_rollout_stationary_opponents", "ppo_update",
    )),
    "src/clasher/rl/parallel_rollout.py": frozenset((
        "ActorWorkerConfig", "_actor_worker_main", "concatenate_rollouts",
    )),
}
PILOT_SOURCE_SCOPE = "src/clasher"


class CouncilPilotConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal[1] = 1
    source_root: str
    strategy_path: str
    strategy_sha256: str
    gamedata_path: str
    gamedata_sha256: str
    training_decks_path: str
    training_decks_sha256: str
    development_decks_path: str
    development_decks_sha256: str
    acceptance_decks_path: str
    acceptance_decks_sha256: str
    deployment_decks_path: str
    deployment_decks_sha256: str
    evaluation_protocol_path: str
    source_pins_path: str
    admission_ledger_path: str
    nominal_admission_path: str
    mixed_level_admission_path: str
    output_dir: str
    seeds: tuple[int, int, int] = (2901, 2902, 2903)
    arms: tuple[Literal["scripted", "scratch"], Literal["scripted", "scratch"]] = (
        "scripted",
        "scratch",
    )
    decisions_per_seed: Literal[5_000_000] = 5_000_000
    diagnostic_decisions: Literal[1_000_000] = 1_000_000
    smoke_decisions: int = Field(default=100_000, gt=0, le=100_000)
    warmstart_decisions: int = Field(default=500_000, gt=0, le=500_000)
    # Throughput limits (admission-scope decision v1): the strategy's 64
    # synchronous environments across up to 16 single-thread actor processes.
    num_envs: int = Field(default=4, ge=2, le=64)
    actor_workers: int = Field(default=2, ge=2, le=16)
    actor_threads: Literal[1] = 1
    torch_threads: int = Field(default=2, ge=1, le=8)
    sequence_batch_size: int = Field(default=2, ge=1, le=4)
    recurrent_update_mode: Literal["full-prefix", "stored-state"] = "full-prefix"
    tbptt_chunk: int = Field(default=64, ge=1)
    tbptt_burn_in: int = Field(default=16, ge=0)
    device: Literal["cpu", "mps"] = "cpu"
    # "worker": each actor process runs its own CPU policy copy (admitted path).
    # "learner": actors only step simulators and scripted/frozen opponents; the
    # learner process runs one batched policy forward over every environment per
    # decision, on ``inference_device``. Transitions do not depend on the actor
    # partition. ``inference_device`` may only be the CPU or the learner device,
    # so accelerator accounting (charged whenever ``device`` is mps) stays exact.
    rollout_inference: Literal["worker", "learner"] = "worker"
    inference_device: Literal["cpu", "mps"] = "cpu"
    cpu_core_hour_ceiling: Literal[4608.0] = 4608.0
    accelerator_hour_ceiling: Literal[72.0] = 72.0
    rollout_steps: Literal[128] = 128
    decision_interval: Literal[5] = 5
    max_ticks: Literal[6001] = 6001
    d_model: Literal[128] = 128
    num_heads: Literal[4] = 4
    actor_layers: Literal[4] = 4
    critic_layers: Literal[2] = 2
    memory_size: Literal[256] = 256
    public_contract_version: Literal[4] = 4
    card_semantics_version: Literal[4] = 4
    public_history_slots: Literal[4] = 4
    public_seen_card_slots: Literal[8] = 8
    gamma: Literal[1.0] = 1.0
    # Recipe v7r3 (user-approved 2026-10-01; pilot/v7r3-proposal): 0.99 widens the
    # GAE credit window from ~20 to ~100 decisions on ~1,200-decision matches.
    gae_lambda: Literal[0.95, 0.99] = 0.95
    reward_potential_scale: Literal[0.05] = 0.05
    learning_rate: Literal[0.0001] = 0.0001
    clip_ratio: Literal[0.2] = 0.2
    epochs: Literal[2] = 2
    # Merge-plan item 5 (implementer routine choice, fixed before launch).
    # Scripted warm-start arm only: the first N PPO updates optimize the value
    # loss alone with every non-critic parameter frozen, so a freshly
    # initialized critic cannot push noisy advantages into the cloned actor.
    # 20 updates = 20 x num_envs x 128 learner decisions (10,240 locally, 0.2%
    # of the 5M budget; 163,840 or 3.3% at 64 environments), counted inside the
    # budget and the nominal first million. That spans roughly eight or more
    # complete ~1,200-decision matches, so terminal outcomes reach the value
    # target, and gives 80 value-only AdamW steps at the signed lr locally
    # (2 epochs x 2 minibatches per update). Longer would idle the actor for a
    # measurable share of the smoke/diagnostic budgets. The scratch arm has no
    # actor to protect and always uses 0. Recipe v7r3 uses 60 (v7r2 critics
    # explained as little as 16% of return variance 16 actor updates after the
    # 20-update warm-up). 0 is reserved for continuation configs, whose
    # initializer already carries a trained critic.
    critic_warmup_updates: Literal[0, 20, 60] = 20
    # Recipe v7r3: KL(pi || pi_warm_start) penalty for the scripted arm only,
    # anchored to that seed's scripted initializer (the scratch arm has no
    # trained policy to anchor to and always uses 0). Kept weak because the one
    # v7r2 seed that improved (2903) moved far from its warm start first.
    # Recipe v7r4h (user-approved 2026-10-02): 0.05, reserved for the declared
    # human-prior arm and anchored to the human-imitation checkpoint itself
    # (AlphaStar-style KL to the imitation policy); 0.01 stays the v7r3 value.
    anchor_policy_kl_coef: Literal[0.0, 0.01, 0.05] = 0.0
    # Merge-plan item 6: re-enable the already implemented approximate-KL
    # early stop in both arms. 0.02 is the value Hasty-CR ran with PPO
    # clip 0.2, and it is stricter than the trainer default 0.03 because the
    # warm-started clone is most fragile just after critic warm-up. With two
    # epochs it only ends an update early; it never changes lr or clip.
    target_kl: Literal[0.02] = 0.02
    mixed_level_probability: Literal[0.5] = 0.5
    # Recipe fix v7r2 (user-approved 2026-10-01; pilot/diagnosis-1M). ppo_update
    # applies ``entropy_coef`` to the flattened joint entropy only while both
    # ``action_type_entropy_coef`` and ``location_entropy_coef`` are unset; once
    # either is set, the bonus is type*H(type) + location*H(placement | card)
    # + conditional_slot*H(card | play) and ``entropy_coef`` only fills an unset
    # factor. Two recipes are declared (see ENTROPY_RECIPES):
    # * joint-v1 (v7r1 and earlier): entropy_coef 0.01 on the joint entropy,
    #   whose p(play)-weighted placement term rewards playing over waiting;
    # * factorized-v2: no bonus on wait/play or placement, 0.003 on the card
    #   choice conditional on playing (normalized by p(play), so it has no
    #   play/wait bias). entropy_coef is 0 so no factor can inherit it.
    entropy_coef: float = Field(default=0.01, ge=0)
    action_type_entropy_coef: float | None = Field(default=None, ge=0)
    location_entropy_coef: float | None = Field(default=None, ge=0)
    conditional_slot_entropy_coef: float = Field(default=0.0, ge=0)
    # Frozen initial policies published into each arm's opponent pool. The
    # admission-bound council_opponents samples the pool's ``initial`` entries
    # uniformly inside the 50% initial share (first million) and inside the 50%
    # historical share (league, together with retained checkpoints), so leaving
    # the untrained random control out of the pool removes it from both phases.
    # The scratch arm always keeps it: its own initializer must be a published
    # initial opponent (admission-bound validate_council_initial_policy).
    initial_opponent_policies: tuple[Literal["scripted", "random_control"], ...] = (
        "scripted",
        "random_control",
    )
    evaluation_games_per_style: int = Field(default=86, ge=2)
    evaluation_seed: int = 9413
    evaluation_styles: tuple[str, ...] = ("balanced", "pressure", "defense")
    # Future mixed-level scope still needs admission. No schedule can widen a receipt.
    # ("nominal", "nominal-league") keeps level 11 for the whole budget: after the
    # one-million nominal phase, the league phase runs to decisions_per_seed with
    # retained checkpoints as opponents and no level randomization, so it needs
    # only the nominal (Tier A) receipt.
    phase_order: tuple[str, ...] = ("nominal", "mixed-league")
    # Continuation (user-approved 2026-10-01): one seed's scripted arm starts from
    # a declared earlier pilot checkpoint instead of its warm start. Weights only;
    # optimizer, counters, simulator and RNG start fresh. The checkpoint is bound
    # prospectively by file digest, its own pilot config digest and its decision
    # count (validate_council_continuation).
    continuation_seed: int | None = None
    continuation_checkpoint_path: str | None = None
    continuation_checkpoint_sha256: str | None = None
    continuation_source_config_sha256: str | None = None
    continuation_source_decisions: int | None = Field(default=None, gt=0)
    # Human prior (recipe v7r4h, user-approved 2026-10-02): the scripted-arm slot
    # of every seed starts from one declared human-imitation checkpoint
    # (human-prior-p16, IL_Replay behaviour cloning) instead of that seed's
    # warm start. It is a research artifact under the 2026-10-01 amendment, not
    # a Tier A admitted arm. Weights only (fresh optimizer, counters, simulator
    # and RNG); its critic is untrained, so the 60-update critic warm-up applies;
    # the policy-KL anchor (0.05) points at the same checkpoint; the checkpoint
    # joins the seed's warm start as an initial opponent, with no random control.
    # Bound by path, file digest and reconstruction manifest digest
    # (validate_council_human_prior). Mutually exclusive with continuation.
    human_prior_checkpoint_path: str | None = None
    human_prior_checkpoint_sha256: str | None = None
    human_prior_recon_manifest_sha256: str | None = None

    @model_validator(mode="before")
    @classmethod
    def toml_arrays(cls, values):
        if isinstance(values, dict):
            values = dict(values)
            for name in (
                "seeds",
                "arms",
                "evaluation_styles",
                "phase_order",
                "initial_opponent_policies",
            ):
                if isinstance(values.get(name), list):
                    values[name] = tuple(values[name])
        return values

    @model_validator(mode="after")
    def validate_contract(self):
        if len(set(self.seeds)) != 3 or set(self.arms) != {"scratch", "scripted"}:
            raise ValueError(
                "pilot requires three distinct seeds and both initialization arms"
            )
        if self.actor_workers > self.num_envs or self.num_envs % self.actor_workers:
            raise ValueError(
                "local actors require an equal nonempty environment partition"
            )
        if self.inference_device not in {"cpu", self.device}:
            raise ValueError(
                "inference may run only on the CPU or the accounted learner device"
            )
        if self.rollout_inference == "worker" and self.inference_device != "cpu":
            raise ValueError("per-worker policy copies run on the CPU")
        if any(
            value % self.num_envs
            for value in (
                self.decisions_per_seed,
                self.diagnostic_decisions,
                self.smoke_decisions,
            )
        ):
            raise ValueError(
                "decision milestones must be divisible by learner environment count"
            )
        if self.evaluation_games_per_style * len(self.evaluation_styles) * 2 < 512:
            raise ValueError("final fixed matrix requires at least 512 completed games")
        if self.evaluation_games_per_style % 2:
            raise ValueError("fixed evaluation must contain complete paired seats")
        if self.evaluation_styles != ("balanced", "pressure", "defense"):
            raise ValueError(
                "the fixed evaluation style matrix cannot change within this pilot"
            )
        if self.phase_order not in PHASE_ORDERS:
            raise ValueError(
                "pilot phases must be nominal then mixed-league or nominal-league"
            )
        continuation = (
            self.continuation_seed,
            self.continuation_checkpoint_path,
            self.continuation_checkpoint_sha256,
            self.continuation_source_config_sha256,
            self.continuation_source_decisions,
        )
        if any(value is None for value in continuation) and any(
            value is not None for value in continuation
        ):
            raise ValueError("continuation fields must be declared together")
        human_prior = (
            self.human_prior_checkpoint_path,
            self.human_prior_checkpoint_sha256,
            self.human_prior_recon_manifest_sha256,
        )
        if any(value is None for value in human_prior) and any(
            value is not None for value in human_prior
        ):
            raise ValueError("human-prior fields must be declared together")
        if self.human_prior_checkpoint_path is not None:
            if self.continuation_seed is not None:
                raise ValueError(
                    "human-prior and continuation initializers are mutually exclusive"
                )
            if self.critic_warmup_updates != 60:
                raise ValueError(
                    "the human prior's untrained critic needs the 60-update critic warm-up"
                )
            if self.anchor_policy_kl_coef != 0.05:
                raise ValueError("the human-prior arm declares the 0.05 policy-KL anchor")
            if "random_control" in self.initial_opponent_policies:
                raise ValueError("the human-prior arm's pool has no random control")
        elif self.anchor_policy_kl_coef == 0.05:
            raise ValueError("the 0.05 policy-KL anchor is reserved for the human prior")
        if self.continuation_seed is not None:
            if self.continuation_seed not in self.seeds:
                raise ValueError("continuation seed is not a declared pilot seed")
            if self.anchor_policy_kl_coef:
                raise ValueError("a continuation config declares no warm-start anchor")
        elif self.critic_warmup_updates == 0:
            raise ValueError("a zero critic warm-up is reserved for continuation")
        entropy_recipe(self)
        if (
            "scripted" not in self.initial_opponent_policies
            or len(set(self.initial_opponent_policies))
            != len(self.initial_opponent_policies)
        ):
            raise ValueError(
                "initial opponent policies must be unique and include the scripted warm start"
            )
        for name in self.__class__.model_fields:
            value = getattr(self, name)
            if value is None:
                continue
            if (
                name.endswith("_path") or name in {"source_root", "output_dir"}
            ) and not Path(value).is_absolute():
                raise ValueError(
                    f"{name} must be absolute to avoid cwd-dependent authority"
                )
            if name.endswith("_sha256") and (
                len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
            ):
                raise ValueError(f"{name} must be a SHA-256 digest")
        if (
            len(
                {
                    self.training_decks_path,
                    self.development_decks_path,
                    self.acceptance_decks_path,
                }
            )
            != 3
        ):
            raise ValueError(
                "training, development and acceptance roles must stay separate"
            )
        return self


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# (entropy_coef, action_type_entropy_coef, location_entropy_coef,
#  conditional_slot_entropy_coef) exactly as passed to ppo_update.
ENTROPY_RECIPES: dict[str, tuple[float, float | None, float | None, float]] = {
    "joint-v1": (0.01, None, None, 0.0),
    "factorized-v2": (0.0, 0.0, 0.0, 0.003),
}


PHASE_ORDERS: tuple[tuple[str, ...], ...] = (
    ("nominal", "mixed-league"),
    ("nominal", "nominal-league"),
)


def level_randomization_after(config: CouncilPilotConfig) -> int | None:
    """Mixed-level schedules switch at one million decisions; nominal-league never."""
    return 1_000_000 if config.phase_order[-1] == "mixed-league" else None


def is_continuation(config: CouncilPilotConfig, seed: int, arm: str) -> bool:
    return config.continuation_seed == seed and arm == "scripted"


def anchor_policy_kl_coef_for_arm(config: CouncilPilotConfig, arm: str) -> float:
    if arm not in config.arms:
        raise ValueError("undeclared pilot arm")
    return config.anchor_policy_kl_coef if arm == "scripted" else 0.0


HUMAN_PRIOR_INITIALIZATION = "human_replay_imitation"
HUMAN_PRIOR_ADMISSION_STATUS = (
    "human-prior research artifact (amendment 2026-10-01); not a Tier A admitted pilot arm"
)


def is_human_prior(config: CouncilPilotConfig, seed: int, arm: str) -> bool:
    """The declared human prior occupies the scripted-arm slot of every seed."""
    return (
        config.human_prior_checkpoint_path is not None
        and seed in config.seeds
        and arm == "scripted"
    )


def anchor_checkpoint_path(config: CouncilPilotConfig, seed: int, arm: str) -> Path | None:
    """The scripted arm anchors to its own initializer, if at all: the seed's
    scripted warm start, or the declared human-prior checkpoint."""
    if not anchor_policy_kl_coef_for_arm(config, arm):
        return None
    if is_human_prior(config, seed, arm):
        return Path(config.human_prior_checkpoint_path)
    return Path(config.output_dir) / f"seed-{seed}" / "initialization" / "scripted.pt"


def training_recipe(config: CouncilPilotConfig) -> dict:
    """Recipe fields recorded in every launch record."""
    return {
        "gae_lambda": config.gae_lambda,
        "critic_warmup_updates": config.critic_warmup_updates,
        "anchor_policy_kl_coef": config.anchor_policy_kl_coef,
        "target_kl": config.target_kl,
        "entropy_recipe": entropy_recipe(config),
        "phase_order": list(config.phase_order),
        "level_randomization_after": level_randomization_after(config),
        "human_prior": None
        if config.human_prior_checkpoint_path is None
        else {
            "arm_slot": "scripted",
            "checkpoint": config.human_prior_checkpoint_path,
            "checkpoint_sha256": config.human_prior_checkpoint_sha256,
            "recon_manifest_sha256": config.human_prior_recon_manifest_sha256,
            "initialization": HUMAN_PRIOR_INITIALIZATION,
            "anchor": "human-prior checkpoint",
            "admission_status": HUMAN_PRIOR_ADMISSION_STATUS,
        },
        "continuation": None
        if config.continuation_seed is None
        else {
            "seed": config.continuation_seed,
            "checkpoint": config.continuation_checkpoint_path,
            "checkpoint_sha256": config.continuation_checkpoint_sha256,
            "source_config_sha256": config.continuation_source_config_sha256,
            "source_decisions": config.continuation_source_decisions,
        },
    }


def entropy_recipe(config) -> str:
    """Name of the declared entropy recipe a config (or trainer args) carries."""
    values = (
        config.entropy_coef,
        config.action_type_entropy_coef,
        config.location_entropy_coef,
        config.conditional_slot_entropy_coef,
    )
    for name, expected in ENTROPY_RECIPES.items():
        if values == expected:
            return name
    raise ValueError(f"undeclared entropy recipe {values}; use one of {ENTROPY_RECIPES}")


def opponent_initialization_paths(
    config: CouncilPilotConfig, *, arm: str, scripted: Path, scratch: Path
) -> tuple[Path, ...]:
    """Initial policies to publish in one arm's opponent pool, in publish order.

    The scratch arm keeps its own initializer (the random control) because the
    admission-bound initializer check requires it to be a published opponent.
    """
    if arm not in config.arms:
        raise ValueError("undeclared pilot arm")
    labels = set(config.initial_opponent_policies)
    if arm == "scratch":
        labels.add("random_control")
    return tuple(
        path
        for label, path in (("scripted", scripted), ("random_control", scratch))
        if label in labels
    )


def load_pilot_config(path: Path) -> CouncilPilotConfig:
    config = CouncilPilotConfig.model_validate(tomllib.loads(path.read_text()))
    for prefix in (
        "strategy",
        "gamedata",
        "training_decks",
        "development_decks",
        "acceptance_decks",
        "deployment_decks",
    ):
        if file_sha256(getattr(config, f"{prefix}_path")) != getattr(
            config, f"{prefix}_sha256"
        ):
            raise ValueError(f"{prefix} bytes differ from the pilot configuration")
    from .public_scripted_opponent import SUPPORTED_CARDS

    for role in ("training", "development", "acceptance"):
        payload = json.loads(Path(getattr(config, f"{role}_decks_path")).read_text())
        rows = payload["decks"]
        if payload.get("role") != role or any(row.get("role") != role for row in rows):
            raise ValueError(f"{role} file does not declare that immutable role")
        if not rows or any(
            len(row["cards"]) != 8
            or len(set(row["cards"])) != 8
            or not set(row["cards"]).issubset(SUPPORTED_CARDS)
            for row in rows
        ):
            raise ValueError(f"invalid or out-of-scope {role} decks")
    return config


def load_source_pins(config: CouncilPilotConfig) -> dict[str, str]:
    raw = json.loads(Path(config.source_pins_path).read_text())
    if not isinstance(raw, dict) or not raw:
        raise ValueError("pilot source pins must be a nonempty mapping")
    result = {
        str((Path(config.source_root) / name).resolve()): digest
        for name, digest in raw.items()
    }
    for name, digest in result.items():
        if file_sha256(name) != digest:
            raise ValueError(f"pilot source changed since freeze: {name}")
    return result


def _module_name(relative: str) -> str:
    return relative.removeprefix("src/").removesuffix(".py").replace("/", ".")


def _top_level_bindings(tree: ast.Module) -> dict[str, list[tuple[str, ast.AST]]]:
    """Every module-level name binding, in source order, with a canonical dump."""
    bindings: dict[str, list[tuple[str, ast.AST]]] = {}

    def bind(name: str, canonical: str, node: ast.AST) -> None:
        bindings.setdefault(name, []).append((canonical, node))

    def visit(statements: list[ast.stmt]) -> None:
        for node in statements:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bind(node.name, ast.dump(node), node)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    name = (alias.asname or alias.name).split(".")[0]
                    canonical = repr(
                        (
                            type(node).__name__,
                            getattr(node, "module", None),
                            getattr(node, "level", 0),
                            alias.name,
                            alias.asname,
                        )
                    )
                    bind(name, canonical, node)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    for item in ast.walk(target):
                        if isinstance(item, ast.Name):
                            bind(item.id, ast.dump(node), node)
            elif isinstance(node, (ast.If, ast.Try)):
                visit(node.body)
                visit(node.orelse)
                for handler in getattr(node, "handlers", ()):
                    visit(handler.body)
                visit(getattr(node, "finalbody", []))

    visit(tree.body)
    return bindings


def _referenced_names(node: ast.AST) -> set[str]:
    """Names a definition uses at runtime.

    Function parameter and return annotations are skipped: with postponed
    evaluation they never execute, and the definition's own AST (compared in
    full) still pins the annotation text.
    """
    names: set[str] = set()
    pending: list[ast.AST] = [node]
    while pending:
        item = pending.pop()
        if isinstance(item, ast.Name):
            names.add(item.id)
        for field, value in ast.iter_fields(item):
            if isinstance(item, ast.arg) and field == "annotation":
                continue
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and field == "returns":
                continue
            if isinstance(value, ast.AST):
                pending.append(value)
            elif isinstance(value, list):
                pending.extend(entry for entry in value if isinstance(entry, ast.AST))
    return names


def _bound_symbol_closure(
    bindings: dict[str, list[tuple[str, ast.AST]]], roots: set[str]
) -> set[str]:
    closure: set[str] = set()
    pending = [name for name in roots if name in bindings]
    while pending:
        name = pending.pop()
        if name in closure:
            continue
        closure.add(name)
        for _, node in bindings[name]:
            pending.extend(
                item
                for item in _referenced_names(node)
                if item in bindings and item not in closure
            )
    return closure


def _imports_from_training_only(
    source: str, *, importer: str, training_only: tuple[str, ...]
) -> dict[str, set[str] | None]:
    """Names an admission-bound module imports from training-only modules.

    ``None`` means the whole module object is imported, so every definition in it
    is treated as admission-bound.
    """
    modules = {_module_name(item): item for item in training_only}
    package = _module_name(importer).rsplit(".", 1)[0]
    result: dict[str, set[str] | None] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - node.level + 1])
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            if target in modules:
                names = result.setdefault(modules[target], set())
                if names is not None:
                    if any(alias.name == "*" for alias in node.names):
                        result[modules[target]] = None
                    else:
                        names.update(alias.name for alias in node.names)
            for alias in node.names:
                submodule = f"{target}.{alias.name}"
                if submodule in modules:
                    result[modules[submodule]] = None
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in modules:
                    result[modules[alias.name]] = None
    return result


def verify_pilot_source_scope(
    *,
    pilot_root: Path,
    admitted_root: Path,
    admitted_pins: dict[str, str],
    pilot_pins: dict[str, str],
    training_only: tuple[str, ...] = PILOT_TRAINING_ONLY_MODULES,
    bound_symbols: dict[str, tuple[str, ...]] = PILOT_BOUND_SYMBOLS,
) -> dict:
    """Fail closed unless the pilot runtime honors the admission-scope decision.

    ``admitted_pins`` are the admission receipt's absolute source pins (rooted at
    ``admitted_root``); ``pilot_pins`` are the pilot freeze's absolute pins
    (rooted at ``pilot_root``) whose on-disk digests the caller already verified.

    * Every admitted ``src/clasher`` module outside ``training_only`` must exist in
      the pilot runtime, be pinned by the pilot freeze and hash exactly as
      admitted (ADMISSION_BOUND).
    * Training-only modules must be admitted, present and pinned by the pilot
      freeze, except the explicitly authorized new tbptt.py learner module.
    * No other ``src/clasher`` Python file may exist in the pilot runtime.
    * Inside a changed training-only module, every definition an admission-bound
      module imports, every declared bound root and their same-module
      dependencies must be AST-identical to the admitted source, except the
      named TBPTT learner definitions. Imported definitions remain bound.
    """
    pilot_root = pilot_root.resolve()
    admitted_root = admitted_root.resolve()
    if len(set(training_only)) != len(training_only):
        raise ValueError("duplicate training-only module")
    admitted: dict[str, str] = {}
    for path, digest in admitted_pins.items():
        relative = Path(path).resolve().relative_to(admitted_root).as_posix()
        if relative.startswith(PILOT_SOURCE_SCOPE + "/") and relative.endswith(".py"):
            admitted[relative] = digest
    if not admitted:
        raise ValueError("admission pins no src/clasher module")
    pinned: dict[str, str] = {}
    for path, digest in pilot_pins.items():
        resolved = Path(path).resolve()
        try:
            relative = resolved.relative_to(pilot_root).as_posix()
        except ValueError as error:
            raise ValueError(f"pilot pin outside the pilot source root: {path}") from error
        pinned[relative] = digest
    on_disk = {
        path.resolve().relative_to(pilot_root).as_posix()
        for path in (pilot_root / PILOT_SOURCE_SCOPE).rglob("*.py")
    }
    tbptt_runtime = PILOT_TBPTT_MODULE in on_disk
    if tbptt_runtime and PILOT_TBPTT_MODULE not in training_only:
        training_only = (*training_only, PILOT_TBPTT_MODULE)
    unknown = sorted(on_disk - admitted.keys() - {PILOT_TBPTT_MODULE})
    if unknown:
        raise ValueError(f"unadmitted source module in the pilot runtime: {unknown}")
    for relative in training_only:
        if relative not in admitted and relative != PILOT_TBPTT_MODULE:
            raise ValueError(f"training-only module was never admitted: {relative}")
    admission_bound = sorted(set(admitted) - set(training_only))
    for relative in admission_bound:
        if relative not in on_disk:
            raise ValueError(f"admission-bound module missing: {relative}")
        if pinned.get(relative) != admitted[relative]:
            raise ValueError(
                f"admission-bound module differs from the admission pins: {relative}"
            )
        if file_sha256(pilot_root / relative) != admitted[relative]:
            raise ValueError(f"admission-bound module changed on disk: {relative}")
    changed: list[str] = []
    for relative in training_only:
        if relative not in on_disk or relative not in pinned:
            raise ValueError(f"training-only module is not pinned by the pilot freeze: {relative}")
        if file_sha256(pilot_root / relative) != pinned[relative]:
            raise ValueError(f"training-only module differs from the pilot freeze: {relative}")
        if pinned[relative] != admitted.get(relative):
            changed.append(relative)
    stale = sorted(
        relative
        for relative in pinned
        if relative.startswith(PILOT_SOURCE_SCOPE + "/") and relative not in on_disk
    )
    if stale:
        raise ValueError(f"pilot freeze pins missing source modules: {stale}")
    exported: dict[str, set[str] | None] = {}
    for relative in admission_bound:
        for module, names in _imports_from_training_only(
            (pilot_root / relative).read_text(),
            importer=relative,
            training_only=training_only,
        ).items():
            if names is None or exported.get(module, set()) is None:
                exported[module] = None
            else:
                exported.setdefault(module, set()).update(names)
    bound_report: dict[str, list[str]] = {}
    for relative in changed:
        original_path = admitted_root / relative
        if relative in admitted and file_sha256(original_path) != admitted[relative]:
            raise ValueError(f"admitted source changed on disk: {relative}")
        if exported.get(relative, set()) is None:
            raise ValueError(
                f"an admission-bound module imports all of {relative}; it cannot change"
            )
        original = (
            _top_level_bindings(ast.parse(original_path.read_text()))
            if relative in admitted else {}
        )
        current = _top_level_bindings(ast.parse((pilot_root / relative).read_text()))
        roots = set(bound_symbols.get(relative, ())) | set(exported.get(relative, set()))
        missing = sorted(name for name in roots if name not in original)
        if missing:
            raise ValueError(f"bound roots are not admitted definitions in {relative}: {missing}")
        closure = _bound_symbol_closure(original, roots)
        if tbptt_runtime:
            # Imported definitions stay bound even if also named as learner code.
            imported = _bound_symbol_closure(original, set(exported.get(relative, set())))
            closure -= PILOT_TBPTT_LEARNER_SYMBOLS.get(relative, frozenset()) - imported
        for name in sorted(closure):
            if [item for item, _ in original[name]] != [
                item for item, _ in current.get(name, [])
            ]:
                raise ValueError(
                    f"admission-bound definition {name} changed in training-only {relative}"
                )
        bound_report[relative] = sorted(closure)
    return {
        "decision": PILOT_SCOPE_DECISION_ID,
        "pilot_root": str(pilot_root),
        "admitted_root": str(admitted_root),
        "admission_bound": {relative: admitted[relative] for relative in admission_bound},
        "training_only": {relative: pinned[relative] for relative in training_only},
        "training_only_changed": changed,
        "bound_symbols_checked": bound_report,
    }


_ADMITTED_LEDGER_CHECK = r"""
import json, sys
from pathlib import Path
request = json.loads(sys.stdin.read())
from clasher.rl import readiness_capture_ownership as ledger
root = Path(request["admitted_root"]).resolve()
if Path(ledger.__file__).resolve().parents[3] != root:
    raise SystemExit("ledger check did not import the admitted runtime")
receipt = ledger.require_admission(
    Path(request["ledger_path"]),
    Path(request["receipt_path"]),
    expected_source_pins=request["expected_source_pins"],
    expected_gamedata_sha256=request["gamedata_sha256"],
    expected_gamedata_path=Path(request["gamedata_path"]),
)
sys.stdout.write("\nADMITTED-RECEIPT " + receipt.model_dump_json() + "\n")
"""


def _require_admission_in_admitted_runtime(
    config: CouncilPilotConfig,
    receipt_path: Path,
    *,
    admitted_root: Path,
    admission_bound: dict[str, str],
) -> str:
    """Run the unchanged ledger check with the admitted code from the admitted root.

    ``require_admission`` verifies the fresh declaration against the source tree
    it is imported from, so it can only pass inside the admitted runtime. The
    pilot runtime's admission-bound modules are byte-identical to it (checked by
    ``verify_pilot_source_scope``); they are passed as pins at their admitted
    paths. Numba caches go to a temporary directory so the admitted snapshot is
    never written.
    """
    import subprocess
    import sys
    import tempfile

    admitted_root = admitted_root.resolve()
    interpreter = admitted_root / ".venv/bin/python"
    if not interpreter.exists():
        interpreter = Path(sys.executable)
    request = {
        "admitted_root": str(admitted_root),
        "ledger_path": str(Path(config.admission_ledger_path)),
        "receipt_path": str(receipt_path.resolve()),
        "expected_source_pins": {
            str((admitted_root / relative).resolve()): digest
            for relative, digest in admission_bound.items()
        },
        "gamedata_sha256": config.gamedata_sha256,
        "gamedata_path": str(Path(config.gamedata_path).resolve()),
    }
    with tempfile.TemporaryDirectory(prefix="clasher-admission-check-") as cache:
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "PYTHONHOME", "CLASHER_ROOT"}
        }
        environment.update(
            CLASHER_ROOT=str(admitted_root),
            PYTHONPATH=str(admitted_root / "src"),
            PYTHONDONTWRITEBYTECODE="1",
            NUMBA_CACHE_DIR=cache,
        )
        result = subprocess.run(
            [str(interpreter), "-B", "-c", _ADMITTED_LEDGER_CHECK],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            cwd=str(admitted_root),
            env=environment,
            check=False,
        )
    if result.returncode != 0:
        tail = (result.stderr or result.stdout).strip().splitlines()[-1:] or ["no output"]
        raise ValueError(f"admitted-runtime ledger check refused the admission: {tail[0]}")
    lines = [
        line.removeprefix("ADMITTED-RECEIPT ")
        for line in result.stdout.splitlines()
        if line.startswith("ADMITTED-RECEIPT ")
    ]
    if len(lines) != 1:
        raise ValueError("admitted-runtime ledger check returned no receipt")
    return lines[0]


def require_pilot_admission(
    config: CouncilPilotConfig, receipt_path: Path, *, levels: tuple[int, ...] = (11,)
):
    from .public_scripted_opponent import SUPPORTED_CARDS
    from .readiness_capture_ownership import AdmissionReceipt, require_admission

    source_pins = load_source_pins(config)
    claimed = AdmissionReceipt.model_validate_json(Path(receipt_path).read_text())
    scope = verify_pilot_source_scope(
        pilot_root=Path(config.source_root),
        admitted_root=Path(claimed.source_root),
        admitted_pins=dict(claimed.source_pins),
        pilot_pins=source_pins,
    )
    # The ledger check re-validates the receipt and binds exactly the
    # admission-bound subset, mapped from the pilot root to the admitted root.
    if Path(config.source_root).resolve() == Path(claimed.source_root).resolve():
        receipt = require_admission(
            Path(config.admission_ledger_path),
            receipt_path,
            expected_source_pins={
                str((Path(config.source_root) / relative).resolve()): digest
                for relative, digest in scope["admission_bound"].items()
            },
            expected_source_root=Path(config.source_root),
            expected_gamedata_sha256=config.gamedata_sha256,
            expected_gamedata_path=Path(config.gamedata_path),
        )
    else:
        receipt = AdmissionReceipt.model_validate_json(
            _require_admission_in_admitted_runtime(
                config,
                Path(receipt_path),
                admitted_root=Path(claimed.source_root),
                admission_bound=scope["admission_bound"],
            )
        )
    if receipt != claimed:
        raise ValueError("admission receipt changed during verification")
    if receipt.strategy_sha256 != config.strategy_sha256:
        raise ValueError("admission belongs to a different strategy")
    if receipt.public_contract_version != 4 or set(receipt.supported_cards) != set(
        SUPPORTED_CARDS
    ):
        raise ValueError("admission does not cover this public actor/card scope")
    if not set(levels).issubset(receipt.levels):
        raise ValueError(f"admission does not cover requested levels {levels}")
    if (
        set(levels) != {11}
        and getattr(receipt, "level_sampling_scope", "nominal") != "independent_cards"
    ):
        raise ValueError(
            "mixed pilot needs explicit independent-card training-sampling permission"
        )
    if receipt.training_scope != "scalar_public_policy_only":
        raise ValueError("admission does not authorize this scalar training path")
    return receipt


def build_council_model_config(builder):
    from .model import PolicyConfig

    return PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=128,
        public_contract_version=4,
        public_token_names=builder.token_names,
        public_observation_confidence=True,
        actor_observation_domain="simulator-exact",
        canonical_lane_globals=True,
        card_semantics_version=4,
        public_history_slots=4,
        public_seen_card_slots=8,
        d_model=128,
        num_heads=4,
        actor_layers=4,
        critic_layers=2,
        memory_size=256,
        memory_kind="lstm",
        card_input_mode="hybrid",
        deterministic_hierarchy="slot",
    )


def pilot_environment(config: CouncilPilotConfig) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        CLASHER_ROOT=str(Path(config.gamedata_path).parent),
        PYTHONPATH=str(Path(config.source_root) / "src"),
        PYTHONDONTWRITEBYTECODE="1",
        OMP_NUM_THREADS=str(config.torch_threads),
        MKL_NUM_THREADS=str(config.torch_threads),
        CLASHER_PILOT_BUDGET=str(Path(config.output_dir) / "resource-budget.json"),
    )
    return environment


def state_dict_sha256(state_dict) -> str:
    """Canonical digest of every named tensor's dtype, shape and exact bytes."""
    import torch

    digest = hashlib.sha256()
    for name in sorted(state_dict):
        tensor = state_dict[name]
        if not isinstance(tensor, torch.Tensor):
            raise TypeError(f"state entry {name} is not a tensor")
        value = tensor.detach().cpu().contiguous()
        digest.update(name.encode())
        digest.update(str(value.dtype).encode())
        digest.update(json.dumps(list(value.shape)).encode())
        digest.update(value.reshape(-1).view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


# What each pilot arm must be initialized from, as written by the warm start
# (``fit_imitation_corpus``): the fitted script clone, or its matched untrained
# control at the identical architecture/vocabulary.
COUNCIL_INITIALIZATION_BY_ARM = {
    "scripted": ("public_script_imitation", True),
    "scratch": ("matched_random_control", False),
}


def validate_council_initial_policy(
    pilot: CouncilPilotConfig,
    payload: dict,
    *,
    initialization_path: Path,
    args,
    builder,
) -> dict:
    """Fail closed unless a weights-only initializer matches this exact run.

    The python-backend council path may start from the warm-start checkpoint
    (scripted arm) or its matched fresh control (scratch arm). Both must carry
    the council actor contract, the run's token vocabulary, the admitted
    ruleset/strategy/deck/source/admission digests, a typed BudgetSnapshot from
    this pilot's own ledger, and be the exact file published as an initial
    opponent. Only model weights are consumed; optimizer, counters, simulator
    and RNG state always start fresh.
    """
    from .council_budget import BudgetSnapshot
    from .council_opponents import CouncilOpponentPool, policy_contract_sha256
    from .model import PolicyConfig

    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("initial policy is not a V2 checkpoint")
    if payload.get("model_type") != "entity_spatial_recurrent":
        raise ValueError("initial policy has an unsupported model type")
    config = PolicyConfig.from_dict(payload["model_config"])
    for name, expected in (
        ("public_contract_version", pilot.public_contract_version),
        ("card_semantics_version", pilot.card_semantics_version),
        ("public_history_slots", pilot.public_history_slots),
        ("public_seen_card_slots", pilot.public_seen_card_slots),
    ):
        if getattr(config, name) != expected:
            raise ValueError(f"initial policy {name} differs from the pilot config")
    token_names = tuple(str(name) for name in builder.token_names)
    if tuple(str(name) for name in payload.get("token_names") or ()) != token_names:
        raise ValueError("initial policy token vocabulary differs from the run")
    if tuple(config.public_token_names) != token_names:
        raise ValueError("initial policy public contract vocabulary differs from the run")
    if config != build_council_model_config(builder):
        raise ValueError("initial policy model differs from the council actor contract")
    expected_digests = {
        "gamedata_sha256": pilot.gamedata_sha256,
        "strategy_sha256": pilot.strategy_sha256,
        "training_decks_sha256": pilot.training_decks_sha256,
        "source_pins_sha256": file_sha256(pilot.source_pins_path),
        "admission_sha256": file_sha256(args.council_admission),
    }
    for name, expected in expected_digests.items():
        if payload.get(name) != expected:
            raise ValueError(f"initial policy {name} differs from the run")
    plan = payload.get("warmstart_plan_sha256")
    if not isinstance(plan, str) or len(plan) != 64 or set(plan) - set(
        "0123456789abcdef"
    ):
        raise ValueError("initial policy has no warm-start plan digest")
    if "resource_budget" not in payload:
        raise ValueError("initial policy has no BudgetSnapshot metadata")
    budget = BudgetSnapshot.model_validate(payload["resource_budget"])
    ledger = (Path(pilot.output_dir) / "resource-budget.json").resolve()
    if Path(budget.ledger_path).resolve() != ledger:
        raise ValueError("initial policy budget belongs to a different pilot ledger")
    if budget.active_job is None:
        raise ValueError("initial policy was not written by a budget-owned child")
    arm = getattr(args, "council_arm", None)
    if arm not in COUNCIL_INITIALIZATION_BY_ARM:
        raise ValueError("council initialization requires a declared arm")
    label, trained = COUNCIL_INITIALIZATION_BY_ARM[arm]
    imitation = payload.get("imitation") or {}
    if (payload.get("args") or {}).get("initialization") != label or bool(
        imitation.get("trained")
    ) is not trained:
        raise ValueError(f"initial policy is not the {arm} arm initialization")
    if imitation.get("initial_checkpoint") is not None:
        raise ValueError("council initializers must be fresh warm-start outputs")
    state = payload.get("model_state_dict")
    if not isinstance(state, dict) or not state:
        raise TypeError("initial policy has no model state")
    file_digest = file_sha256(initialization_path)
    pool = CouncilOpponentPool.model_validate_json(
        Path(args.council_opponent_pool).read_text()
    )
    if file_digest not in {entry.sha256 for entry in pool.initial}:
        raise ValueError("initial policy is not a published initial opponent")
    if (
        pool.gamedata_sha256 != pilot.gamedata_sha256
        or pool.policy_contract_sha256 != policy_contract_sha256(config)
    ):
        raise ValueError("opponent pool belongs to a different actor contract")
    return {
        "path": str(Path(initialization_path).resolve()),
        "sha256": file_digest,
        "state_sha256": state_dict_sha256(state),
        "arm": arm,
        "initialization": label,
        "policy_contract_sha256": policy_contract_sha256(config),
        "resource_budget_ledger": str(ledger),
        "checkpoint_optimizer_state_present": "optimizer_state_dict" in payload,
        "weights_only": True,
        "optimizer_reset": True,
        "update_reset": True,
        "simulator_state_reset": True,
    }


def validate_council_continuation(
    pilot: CouncilPilotConfig,
    payload: dict,
    *,
    initialization_path: Path,
    args,
    builder,
) -> dict:
    """Fail closed unless a weights-only continuation matches its declaration.

    The continuation counterpart of validate_council_initial_policy for the one
    declared (seed, scripted) run: the file must be the prospectively declared
    checkpoint (path and digest), written by the declared earlier pilot config
    at the declared decision count, under this run's Tier A admission, ruleset,
    actor contract and vocabulary, from the scripted arm. It must also be a
    published initial opponent of this run's pool. Only model weights are
    consumed; optimizer, counters, simulator and RNG state start fresh.
    """
    from .council_opponents import CouncilOpponentPool, policy_contract_sha256
    from .model import PolicyConfig

    arm = getattr(args, "council_arm", None)
    if not is_continuation(pilot, args.seed, arm):
        raise ValueError("this run is not the declared continuation")
    path = Path(initialization_path).resolve()
    if path != Path(pilot.continuation_checkpoint_path).resolve():
        raise ValueError("continuation checkpoint path differs from the declaration")
    file_digest = file_sha256(path)
    if file_digest != pilot.continuation_checkpoint_sha256:
        raise ValueError("continuation checkpoint bytes differ from the declaration")
    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("continuation checkpoint is not a V2 checkpoint")
    if payload.get("model_type") != "entity_spatial_recurrent":
        raise ValueError("continuation checkpoint has an unsupported model type")
    config = PolicyConfig.from_dict(payload["model_config"])
    token_names = tuple(str(name) for name in builder.token_names)
    if tuple(str(name) for name in payload.get("token_names") or ()) != token_names:
        raise ValueError("continuation token vocabulary differs from the run")
    if config != build_council_model_config(builder):
        raise ValueError("continuation model differs from the council actor contract")
    if payload.get("gamedata_sha256") != pilot.gamedata_sha256:
        raise ValueError("continuation ruleset differs from the admitted runtime")
    if payload.get("council_config_sha256") != pilot.continuation_source_config_sha256:
        raise ValueError("continuation checkpoint came from an undeclared pilot config")
    if int(payload.get("total_transitions", -1)) != pilot.continuation_source_decisions:
        raise ValueError("continuation checkpoint decision count differs from the declaration")
    if (payload.get("council_recipe") or {}).get("arm") != "scripted":
        raise ValueError("continuation checkpoint is not from a scripted arm")
    # A no-update preflight binds a placeholder, never the Tier A receipt.
    if not getattr(args, "preflight_no_update", False) and payload.get(
        "admission_sha256"
    ) != file_sha256(args.council_admission):
        raise ValueError("continuation checkpoint was fitted under a different admission")
    state = payload.get("model_state_dict")
    if not isinstance(state, dict) or not state:
        raise TypeError("continuation checkpoint has no model state")
    pool = CouncilOpponentPool.model_validate_json(
        Path(args.council_opponent_pool).read_text()
    )
    if file_digest not in {entry.sha256 for entry in pool.initial}:
        raise ValueError("continuation checkpoint is not a published initial opponent")
    if (
        pool.gamedata_sha256 != pilot.gamedata_sha256
        or pool.policy_contract_sha256 != policy_contract_sha256(config)
    ):
        raise ValueError("opponent pool belongs to a different actor contract")
    return {
        "path": str(path),
        "sha256": file_digest,
        "state_sha256": state_dict_sha256(state),
        "arm": arm,
        "initialization": "continuation",
        "continuation_source_config_sha256": pilot.continuation_source_config_sha256,
        "continuation_source_decisions": pilot.continuation_source_decisions,
        "continuation_source_initialization": payload.get("council_initialization"),
        "policy_contract_sha256": policy_contract_sha256(config),
        "checkpoint_optimizer_state_present": "optimizer_state_dict" in payload,
        "weights_only": True,
        "optimizer_reset": True,
        "update_reset": True,
        "simulator_state_reset": True,
    }


def validate_council_human_prior(
    pilot: CouncilPilotConfig,
    payload: dict,
    *,
    initialization_path: Path,
    args,
    builder,
) -> dict:
    """Fail closed unless a weights-only human-prior initializer matches its declaration.

    The human-prior counterpart of validate_council_initial_policy for the
    scripted-arm slot of a config that declares ``human_prior_*``. The
    admission-bound initializer check cannot accept this checkpoint (it has no
    public-script warm-start plan, no BudgetSnapshot and no admission digest:
    it was fitted outside the pilot from IL_Replay). Instead the file must be
    the prospectively declared checkpoint (path, file digest, reconstruction
    manifest digest), carry the council actor contract, this run's token
    vocabulary, the admitted ruleset and training-deck digests, the
    ``human_replay_imitation`` initialization label and the research-artifact
    provenance label, and be a published initial opponent of this run's pool.
    Only model weights are consumed; optimizer, counters, simulator and RNG
    state start fresh. The returned record (stored in every checkpoint) states
    that this is a research artifact, not a Tier A admitted arm.
    """
    from .council_opponents import CouncilOpponentPool, policy_contract_sha256
    from .model import PolicyConfig

    arm = getattr(args, "council_arm", None)
    if not is_human_prior(pilot, args.seed, arm):
        raise ValueError("this run is not the declared human-prior arm")
    path = Path(initialization_path).resolve()
    if path != Path(pilot.human_prior_checkpoint_path).resolve():
        raise ValueError("human-prior checkpoint path differs from the declaration")
    file_digest = file_sha256(path)
    if file_digest != pilot.human_prior_checkpoint_sha256:
        raise ValueError("human-prior checkpoint bytes differ from the declaration")
    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("human-prior checkpoint is not a V2 checkpoint")
    if payload.get("model_type") != "entity_spatial_recurrent":
        raise ValueError("human-prior checkpoint has an unsupported model type")
    config = PolicyConfig.from_dict(payload["model_config"])
    token_names = tuple(str(name) for name in builder.token_names)
    if tuple(str(name) for name in payload.get("token_names") or ()) != token_names:
        raise ValueError("human-prior token vocabulary differs from the run")
    if tuple(config.public_token_names) != token_names:
        raise ValueError("human-prior public contract vocabulary differs from the run")
    if config != build_council_model_config(builder):
        raise ValueError("human-prior model differs from the council actor contract")
    if payload.get("gamedata_sha256") != pilot.gamedata_sha256:
        raise ValueError("human-prior ruleset differs from the admitted runtime")
    if payload.get("training_decks_sha256") != pilot.training_decks_sha256:
        raise ValueError("human-prior training-deck digest differs from the run")
    if (
        payload.get("human_replay_recon_manifest_sha256")
        != pilot.human_prior_recon_manifest_sha256
    ):
        raise ValueError("human-prior reconstruction manifest differs from the declaration")
    if (payload.get("args") or {}).get("initialization") != HUMAN_PRIOR_INITIALIZATION:
        raise ValueError("checkpoint is not a human-replay imitation initializer")
    imitation = payload.get("imitation") or {}
    if imitation.get("trained") is not True:
        raise ValueError("human-prior checkpoint is not a trained imitation policy")
    provenance = payload.get("provenance")
    if not isinstance(provenance, str) or "not a Tier A admitted" not in provenance:
        raise ValueError("human-prior checkpoint lacks its research-artifact provenance label")
    state = payload.get("model_state_dict")
    if not isinstance(state, dict) or not state:
        raise TypeError("human-prior checkpoint has no model state")
    pool = CouncilOpponentPool.model_validate_json(
        Path(args.council_opponent_pool).read_text()
    )
    if file_digest not in {entry.sha256 for entry in pool.initial}:
        raise ValueError("human-prior checkpoint is not a published initial opponent")
    if (
        pool.gamedata_sha256 != pilot.gamedata_sha256
        or pool.policy_contract_sha256 != policy_contract_sha256(config)
    ):
        raise ValueError("opponent pool belongs to a different actor contract")
    return {
        "path": str(path),
        "sha256": file_digest,
        "state_sha256": state_dict_sha256(state),
        "arm": arm,
        "arm_slot": "scripted",
        "initialization": "human_prior",
        "checkpoint_initialization": HUMAN_PRIOR_INITIALIZATION,
        "human_replay_recon_manifest_sha256": pilot.human_prior_recon_manifest_sha256,
        "provenance": provenance,
        "admission_status": HUMAN_PRIOR_ADMISSION_STATUS,
        "policy_contract_sha256": policy_contract_sha256(config),
        "checkpoint_optimizer_state_present": "optimizer_state_dict" in payload,
        "checkpoint_update": payload.get("update"),
        "checkpoint_total_transitions": payload.get("total_transitions"),
        "weights_only": True,
        "optimizer_reset": True,
        "update_reset": True,
        "simulator_state_reset": True,
    }


def opponent_initialization_paths_for_seed(
    config: CouncilPilotConfig,
    *,
    seed: int,
    arm: str,
    scripted: Path,
    scratch: Path,
) -> tuple[Path, ...]:
    """Initial pool for one run; a continuation or the human prior also faces its
    own starting point (published next to the seed's warm start)."""
    paths = opponent_initialization_paths(
        config, arm=arm, scripted=scripted, scratch=scratch
    )
    if is_continuation(config, seed, arm):
        paths += (Path(config.continuation_checkpoint_path),)
    if is_human_prior(config, seed, arm):
        paths += (Path(config.human_prior_checkpoint_path),)
    return paths


def require_initialized_weights(model, record: dict, optimizer=None) -> str:
    """After a strict load, the learner must hold exactly the initializer bytes
    and (unless explicitly resumed, which never reaches here) a fresh optimizer."""
    digest = state_dict_sha256(model.state_dict())
    if digest != record["state_sha256"]:
        raise ValueError("initialized weights differ from the checkpoint digest")
    if optimizer is not None and optimizer.state:
        raise RuntimeError("council initialization must start a fresh optimizer")
    return digest


def initializer_path_differs(initializer, declared: str) -> bool:
    """A declared initializer binds weights-only starts; resumes carry none."""
    return initializer is not None and Path(initializer).resolve() != Path(declared).resolve()


def critic_warmup_updates_for_arm(config: CouncilPilotConfig, arm: str) -> int:
    """Only the scripted warm start has a trained actor worth protecting."""
    if arm not in config.arms:
        raise ValueError("undeclared pilot arm")
    return config.critic_warmup_updates if arm == "scripted" else 0


def validate_council_trainer_args(
    pilot: CouncilPilotConfig, args, model_config, builder
) -> None:
    """Reject legacy CLI options that would silently change the signed recipe."""
    if model_config != build_council_model_config(builder):
        raise ValueError("trainer model differs from the council actor contract")
    if args.council_budget_ledger != Path(pilot.output_dir) / "resource-budget.json":
        raise ValueError("council trainer must use its shared compute ledger")
    if args.council_opponent_pool is None:
        raise ValueError("council fitting requires a declared per-match opponent pool")
    arm = getattr(args, "council_arm", None)
    if arm not in pilot.arms:
        raise ValueError("council trainer must declare its initialization arm")
    checks = {
        "num_envs": pilot.num_envs,
        "torch_threads": pilot.torch_threads,
        "opponent_mode": "strategy",
        "opponent_strategy": "balanced",
        "level_randomization_after": level_randomization_after(pilot),
        "mixed_level_probability": 0.5,
        "device": pilot.device,
        "actor_device": pilot.inference_device,
        "rollout_inference": pilot.rollout_inference,
        "actor_workers": pilot.actor_workers,
        "actor_threads": pilot.actor_threads,
        "rollout_steps": pilot.rollout_steps,
        "decision_interval": pilot.decision_interval,
        "max_ticks": pilot.max_ticks,
        "gamma": pilot.gamma,
        "gae_lambda": pilot.gae_lambda,
        "reward_potential_scale": pilot.reward_potential_scale,
        "reward_shaping_gamma": pilot.gamma,
        "elixir_leak_penalty_scale": 0.0,
        "learning_rate": pilot.learning_rate,
        "clip_ratio": pilot.clip_ratio,
        "epochs": pilot.epochs,
        "target_kl": pilot.target_kl,
        "sequence_batch_size": pilot.sequence_batch_size,
        "simulation_backend": "python",
        "defense_scenario_probability": 0.0,
        "lr_anneal": False,
        "online_strategy_teacher": None,
        "matchups_path": None,
        "matchup_probability": 0.0,
        "anchor_l2_coef": 0.0,
        "anchor_policy_kl_coef": anchor_policy_kl_coef_for_arm(pilot, arm),
        "rehearsal_coef": 0.0,
        "causal_rehearsal_coef": 0.0,
        "causal_spatial_rehearsal_coef": 0.0,
        "anchor_rehearsal_coef": 0.0,
        "entropy_coef": pilot.entropy_coef,
        "action_type_entropy_coef": pilot.action_type_entropy_coef,
        "location_entropy_coef": pilot.location_entropy_coef,
        "conditional_slot_entropy_coef": pilot.conditional_slot_entropy_coef,
    }
    for name, default in (("recurrent_update_mode", "full-prefix"),
                          ("tbptt_chunk", 64), ("tbptt_burn_in", 16)):
        expected = getattr(pilot, name)
        if getattr(args, name, default) != expected:
            raise ValueError(f"council trainer option {name} differs from its validated config")
    for name, expected in checks.items():
        if getattr(args, name) != expected:
            raise ValueError(
                f"council trainer option {name} differs from its validated config"
            )
    if args.total_decisions not in {
        pilot.smoke_decisions,
        pilot.diagnostic_decisions,
        pilot.decisions_per_seed,
    }:
        raise ValueError("council trainer target is not a declared decision milestone")
    if args.seed not in pilot.seeds:
        raise ValueError("undeclared pilot seed")
    anchor = anchor_checkpoint_path(pilot, args.seed, arm)
    declared_anchor = getattr(args, "anchor_checkpoint", None)
    if (anchor is None) != (declared_anchor is None) or (
        anchor is not None and Path(declared_anchor).resolve() != anchor.resolve()
    ):
        if is_human_prior(pilot, args.seed, arm):
            raise ValueError(
                "the human-prior anchor must be the declared human-prior checkpoint"
            )
        raise ValueError(
            "the warm-start anchor must be the scripted arm's own initializer"
        )
    if (
        is_human_prior(pilot, args.seed, arm)
        and initializer_path_differs(
            getattr(args, "initialize_policy_from", None),
            pilot.human_prior_checkpoint_path,
        )
    ):
        raise ValueError("the human-prior run must start from its declared checkpoint")
    if (
        arm == "scripted"
        and critic_warmup_updates_for_arm(pilot, arm) == 0
        and not is_continuation(pilot, args.seed, arm)
    ):
        raise ValueError("only the continuation run may skip the critic warm-up")
    initializer = getattr(args, "initialize_policy_from", None)
    if (
        is_continuation(pilot, args.seed, arm)
        and initializer is not None
        and Path(initializer).resolve()
        != Path(pilot.continuation_checkpoint_path).resolve()
    ):
        raise ValueError("the continuation run must start from its declared checkpoint")
    if getattr(args, "critic_warmup_updates", None) != critic_warmup_updates_for_arm(
        pilot, arm
    ):
        raise ValueError(
            "critic warm-up must be the recorded count for the scripted arm "
            "and zero for the scratch arm"
        )
    if Path(args.decks_path).resolve() != Path(pilot.training_decks_path).resolve():
        raise ValueError("council trainer must use the training-role deck source")
    for name in (
        "sampling_decks_path",
        "learner_sampling_decks_path",
        "opponent_sampling_decks_path",
    ):
        value = getattr(args, name)
        if (
            value is not None
            and Path(value).resolve() != Path(pilot.training_decks_path).resolve()
        ):
            raise ValueError(
                "council gameplay fitting cannot sample development or acceptance roles"
            )
    from clasher.paths import gamedata_path

    if gamedata_path() != Path(pilot.gamedata_path).resolve():
        raise ValueError("trainer default ruleset is not bound to the pilot data")


def retain_league_checkpoint(pool_path: Path, checkpoint: Path, decisions: int) -> None:
    """Atomically publish retained history; running matches keep their assignment."""
    from .council_opponents import CouncilOpponentPool, OpponentCheckpoint

    pool = CouncilOpponentPool.model_validate_json(pool_path.read_text())
    entry = OpponentCheckpoint(
        path=str(checkpoint.resolve()), sha256=file_sha256(checkpoint)
    )
    if pool.phase == "league" and any(
        item.sha256 == entry.sha256 for item in pool.historical
    ):
        return
    if decisions < pool.generation:
        raise ValueError("cannot publish an older opponent generation")
    historical = pool.historical + (entry,)
    updated = pool.model_copy(
        update={
            "phase": "league",
            "generation": max(decisions, pool.generation + 1),
            "historical": historical,
        }
    )
    temporary = pool_path.with_suffix(".tmp")
    temporary.write_text(updated.model_dump_json(indent=2) + "\n")
    os.replace(temporary, pool_path)


def admission_path_for_phase(config: CouncilPilotConfig, phase: str) -> Path:
    if phase not in {"smoke", "nominal", "mixed-league"}:
        raise ValueError("undeclared pilot phase")
    return Path(
        config.mixed_level_admission_path
        if phase == "mixed-league"
        else config.nominal_admission_path
    )


def training_command(
    config: CouncilPilotConfig,
    *,
    config_path: Path,
    admission: Path,
    seed: int,
    arm: str,
    phase: str,
    pool_path: Path,
    initialization: Path,
    resume: Path | None = None,
) -> list[str]:
    targets = {
        "smoke": config.smoke_decisions,
        "nominal": config.diagnostic_decisions,
        config.phase_order[-1]: config.decisions_per_seed,
    }
    if phase not in targets or arm not in config.arms or seed not in config.seeds:
        raise ValueError("undeclared pilot arm, phase or seed")
    directory = Path(config.output_dir) / f"seed-{seed}" / arm
    args = [
        str(Path(config.source_root) / ".venv/bin/python"),
        "-B",
        "-m",
        "clasher.rl.train_recurrent",
    ]
    values = {
        "council-config": str(config_path.resolve()),
        "council-admission": str(admission.resolve()),
        "council-budget-ledger": str(Path(config.output_dir) / "resource-budget.json"),
        "council-opponent-pool": str(pool_path.resolve()),
        "decks-path": config.training_decks_path,
        "sampling-decks-path": config.training_decks_path,
        "checkpoint-dir": str(directory),
        "seed": seed,
        "total-decisions": targets[phase],
        "num-envs": config.num_envs,
        "actor-workers": config.actor_workers,
        "actor-threads": config.actor_threads,
        "torch-threads": config.torch_threads,
        "rollout-steps": 128,
        "decision-interval": 5,
        "max-ticks": 6001,
        "public-contract-version": 4,
        "public-history-slots": 4,
        "public-seen-card-slots": 8,
        "card-semantics-version": 4,
        "d-model": 128,
        "num-heads": 4,
        "actor-layers": 4,
        "critic-layers": 2,
        "memory-size": 256,
        "memory-kind": "lstm",
        "card-input-mode": "hybrid",
        "actor-observation-domain": "simulator-exact",
        "device": config.device,
        "actor-device": config.inference_device,
        "rollout-inference": config.rollout_inference,
        "simulation-backend": "python",
        "opponent-mode": "strategy",
        "opponent-strategy": "balanced",
        "gamma": 1,
        "gae-lambda": config.gae_lambda,
        "learning-rate": 0.0001,
        "clip-ratio": 0.2,
        "epochs": 2,
        "sequence-batch-size": config.sequence_batch_size,
        "reward-profile": "objective-v1",
        "reward-shaping-gamma": 1,
        "reward-potential-scale": 0.05,
        "elixir-leak-penalty-scale": 0,
        "mixed-level-probability": 0.5,
        "save-every": 200,
        "target-kl": config.target_kl,
        "council-arm": arm,
        "critic-warmup-updates": critic_warmup_updates_for_arm(config, arm),
        "checkpoint-decisions": 1_000_000,
        "entropy-coef": config.entropy_coef,
        "conditional-slot-entropy-coef": config.conditional_slot_entropy_coef,
    }
    # Omit defaults so existing launch commands remain byte-identical.
    for name, default in (("recurrent_update_mode", "full-prefix"),
                          ("tbptt_chunk", 64), ("tbptt_burn_in", 16)):
        value = getattr(config, name)
        if config.recurrent_update_mode != "full-prefix" or value != default:
            values[name.replace("_", "-")] = value
    # Unset per-factor coefficients keep the trainer default (None), which is
    # what makes ppo_update use the joint-entropy term.
    if config.action_type_entropy_coef is not None:
        values["action-type-entropy-coef"] = config.action_type_entropy_coef
    if config.location_entropy_coef is not None:
        values["location-entropy-coef"] = config.location_entropy_coef
    switch = level_randomization_after(config)
    if switch is not None:
        values["level-randomization-after"] = switch
    anchor = anchor_checkpoint_path(config, seed, arm)
    if anchor is not None:
        values["anchor-checkpoint"] = str(anchor)
        values["anchor-policy-kl-coef"] = anchor_policy_kl_coef_for_arm(config, arm)
    for name, value in values.items():
        args.extend(["--" + name, str(value)])
    if config.phase_order[-1] == "nominal-league":
        # Retained league milestones; each is also an evaluation point.
        for milestone in (2_000_000, 3_000_000, 4_000_000):
            args.extend(["--checkpoint-decisions", str(milestone)])
    args.extend(["--checkpoint-decisions", "5000000", "--no-lr-anneal"])
    args.extend(
        ["--resume-from", str(resume)]
        if resume is not None
        else ["--initialize-policy-from", str(initialization)]
    )
    return args


def publish_initial_pool(
    config: CouncilPilotConfig,
    *,
    pool_path: Path,
    initialization_paths: tuple[Path, ...],
    phase: str = "initial",
    history: tuple[Path, ...] = (),
) -> None:
    import torch

    from .council_opponents import (
        CouncilOpponentPool,
        OpponentCheckpoint,
        policy_contract_sha256,
    )
    from .model import PolicyConfig

    checkpoints = [
        torch.load(path, map_location="cpu", weights_only=False)
        for path in initialization_paths
    ]
    if any(
        item.get("gamedata_sha256") != config.gamedata_sha256 for item in checkpoints
    ):
        raise ValueError("initial policy is not bound to admitted game data")
    contracts = {
        policy_contract_sha256(PolicyConfig.from_dict(item["model_config"]))
        for item in checkpoints
    }
    if len(contracts) != 1:
        raise ValueError("initial policies have different actor contracts")

    def entry(path):
        return OpponentCheckpoint(path=str(path.resolve()), sha256=file_sha256(path))

    pool = CouncilOpponentPool(
        generation=0,
        phase=phase,
        gamedata_sha256=config.gamedata_sha256,
        policy_contract_sha256=next(iter(contracts)),
        initial=tuple(entry(path) for path in initialization_paths),
        historical=tuple(entry(path) for path in history),
    )
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    if pool_path.exists():
        existing = CouncilOpponentPool.model_validate_json(pool_path.read_text())
        if (
            existing.gamedata_sha256 != pool.gamedata_sha256
            or existing.initial != pool.initial
        ):
            raise ValueError(
                "existing opponent pool belongs to a different pilot initialization"
            )
        return
    with pool_path.open("x") as stream:
        stream.write(pool.model_dump_json(indent=2) + "\n")


def evaluation_commands(
    config: CouncilPilotConfig, *, checkpoint: Path, output: Path, final: bool
) -> list[list[str]]:
    commands = []
    roles = [
        (
            "holdout",
            config.acceptance_decks_path if final else config.development_decks_path,
            config.evaluation_games_per_style if final else 32,
        ),
        ("hog26", config.deployment_decks_path, 32),
    ]
    for role_index, (role, deck_path, games) in enumerate(roles):
        for level_index, level_mode in enumerate(
            ("nominal", "mixed") if final else ("nominal",)
        ):
            for style_index, style in enumerate(config.evaluation_styles):
                prefix = output / f"{checkpoint.stem}-{role}-{level_mode}-{style}"
                args = [
                    str(Path(config.source_root) / ".venv/bin/python"),
                    "-B",
                    "-m",
                    "clasher.rl.eval",
                    "--checkpoint",
                    str(checkpoint),
                    "--decks-path",
                    config.training_decks_path,
                    "--candidate-sampling-decks-path",
                    deck_path,
                    "--opponent-sampling-decks-path",
                    config.training_decks_path,
                    "--opponent",
                    "public-script",
                    "--public-script-style",
                    style,
                    "--level-mode",
                    level_mode,
                    "--games",
                    str(games),
                    "--seed",
                    # Final cells use slots 0-11; one-million diagnostics use
                    # slots 12-23 so no diagnostic game reuses a final matchup seed.
                    str(
                        config.evaluation_seed
                        + 1_000_003
                        * (
                            role_index * 6
                            + level_index * 3
                            + style_index
                            + (0 if final else 12)
                        )
                    ),
                    "--decision-interval",
                    "5",
                    "--max-ticks",
                    "6001",
                    "--device",
                    config.device,
                    "--torch-threads",
                    str(config.torch_threads),
                    "--stochastic",
                    "--json-out",
                    str(prefix.with_suffix(".json")),
                    "--games-json-out",
                    str(prefix.with_suffix(".games.json")),
                ]
                commands.append(args)
    return commands


WARMSTART_RESULT_SCHEMA = "clasher.council-script-warmstart-result.v1"
WARMSTART_REBIND_SCHEMA = "clasher.council-script-warmstart-rebind.v1"
# The only checkpoint fields a rebind may change: the pilot freeze digest and the
# budget snapshot that binds an initializer to its pilot ledger.
WARMSTART_REBIND_FIELDS = ("source_pins_sha256", "resource_budget")


def rebind_warmstart_initialization(
    *, config_path: Path, admission_path: Path, seed: int, source_dir: Path
) -> dict:
    """Re-publish an existing warm-start initialization under a new pilot config.

    Runs only as a budget-owned child of the new pilot's ledger. The fitted
    scripted initializer and its matched random control are read from
    ``source_dir`` (an earlier kit's ``seed-N/initialization``) after both are
    verified against that warm start's own result receipt and plan. Only
    ``WARMSTART_REBIND_FIELDS`` change: the new pilot freeze digest and a
    snapshot of this pilot's ledger, written by this child, which is what
    validate_council_initial_policy binds. Weights, the imitation/fit record,
    the plan digest and every data and admission digest are copied unchanged
    and the state-dict digests are checked equal after the write. No
    demonstration is collected and nothing is fitted.
    """
    import torch

    from .council_budget import BudgetSnapshot, budget_snapshot, require_owned_budget

    config_path = Path(config_path).resolve()
    admission_path = Path(admission_path).resolve()
    source_dir = Path(source_dir).resolve()
    config = load_pilot_config(config_path)
    if seed not in config.seeds:
        raise ValueError("undeclared pilot seed")
    ledger = Path(config.output_dir) / "resource-budget.json"
    require_owned_budget(ledger)
    require_pilot_admission(config, admission_path, levels=(11,))
    target_dir = (Path(config.output_dir) / f"seed-{seed}" / "initialization").resolve()
    if target_dir == source_dir or source_dir in target_dir.parents:
        raise ValueError("rebind source must be a different pilot's initialization")
    source_result = source_dir / "scripted-demonstrations" / "result.json"
    receipt = json.loads(source_result.read_text())
    if receipt.get("schema") != WARMSTART_RESULT_SCHEMA:
        raise ValueError("rebind source is not a completed warm-start result")
    plan = receipt["plan"]
    plan_path = source_dir / "scripted-demonstrations" / "plan.json"
    if plan.get("seed") != seed or json.loads(plan_path.read_text()) != plan:
        raise ValueError("rebind source warm start belongs to a different seed or plan")
    plan_sha = file_sha256(plan_path)
    sources = {
        "scripted.pt": (Path(receipt["checkpoint"]), receipt["checkpoint_sha256"], True),
        "scripted-random-control.pt": (
            Path(receipt["control_checkpoint"]),
            receipt["control_checkpoint_sha256"],
            False,
        ),
    }
    result_path = target_dir / "scripted-demonstrations" / "result.json"
    for name, (path, digest, _trained) in sources.items():
        if path.resolve().parent != source_dir or file_sha256(path) != digest:
            raise ValueError(f"rebind source {name} differs from its warm-start receipt")
        if (target_dir / name).exists():
            raise FileExistsError(f"rebind target already exists: {target_dir / name}")
    if result_path.exists():
        raise FileExistsError(f"rebind receipt already exists: {result_path}")
    pins_sha = file_sha256(config.source_pins_path)
    admission_sha = file_sha256(admission_path)
    budget = budget_snapshot(ledger)
    BudgetSnapshot.model_validate(budget)
    expected = {
        "gamedata_sha256": config.gamedata_sha256,
        "strategy_sha256": config.strategy_sha256,
        "training_decks_sha256": config.training_decks_sha256,
        "admission_sha256": admission_sha,
        "warmstart_plan_sha256": plan_sha,
    }
    target_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, dict] = {}
    previous: dict[str, dict] = {}
    for name, (path, digest, trained) in sources.items():
        payload = torch.load(path, map_location="cpu", weights_only=False)
        for field, value in expected.items():
            if payload.get(field) != value:
                raise ValueError(f"rebind source {name} {field} differs from the new pilot")
        if bool((payload.get("imitation") or {}).get("trained")) is not trained:
            raise ValueError(f"rebind source {name} has the wrong arm role")
        state_sha = state_dict_sha256(payload["model_state_dict"])
        previous[name] = {
            "source_pins_sha256": payload.get("source_pins_sha256"),
            "resource_budget_ledger": (payload.get("resource_budget") or {}).get(
                "ledger_path"
            ),
        }
        rebound = dict(payload)
        rebound["source_pins_sha256"] = pins_sha
        rebound["resource_budget"] = budget
        rebound["warmstart_rebind"] = {
            "schema": WARMSTART_REBIND_SCHEMA,
            "source_checkpoint": str(path.resolve()),
            "source_checkpoint_sha256": digest,
            "source_result": str(source_result),
            "source_result_sha256": file_sha256(source_result),
            "state_sha256": state_sha,
            "changed_fields": list(WARMSTART_REBIND_FIELDS),
            "previous": previous[name],
        }
        target = target_dir / name
        with target.open("xb") as stream:
            torch.save(rebound, stream)
        check = torch.load(target, map_location="cpu", weights_only=False)
        if (
            state_dict_sha256(check["model_state_dict"]) != state_sha
            or set(check) != set(payload) | {"warmstart_rebind"}
            or any(
                not _same_payload_value(check[key], payload[key])
                for key in payload
                if key not in WARMSTART_REBIND_FIELDS
            )
        ):
            raise RuntimeError(f"rebind changed more than the binding fields: {name}")
        outputs[name] = {
            "path": str(target),
            "sha256": file_sha256(target),
            "state_sha256": state_sha,
            "source": str(path.resolve()),
            "source_sha256": digest,
        }
    rebind_receipt = {
        "schema": WARMSTART_REBIND_SCHEMA,
        "seed": seed,
        "checkpoint": outputs["scripted.pt"]["path"],
        "checkpoint_sha256": outputs["scripted.pt"]["sha256"],
        "control_checkpoint": outputs["scripted-random-control.pt"]["path"],
        "control_checkpoint_sha256": outputs["scripted-random-control.pt"]["sha256"],
        "initializers": outputs,
        "source_result": str(source_result),
        "source_result_sha256": file_sha256(source_result),
        "changed_fields": list(WARMSTART_REBIND_FIELDS),
        "previous_binding": previous,
        "pilot_config_sha256": file_sha256(config_path),
        "source_pins_sha256": pins_sha,
        "admission_sha256": admission_sha,
        "demonstrations_collected": False,
        "fitted": False,
        "plan": plan,
        "corpus": receipt.get("corpus"),
        "fit": receipt.get("fit"),
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with result_path.open("x") as stream:
        stream.write(json.dumps(rebind_receipt, indent=2, sort_keys=True) + "\n")
    return rebind_receipt


def _same_payload_value(left, right) -> bool:
    """Exact recursive equality for checkpoint payload values (tensors by bytes)."""
    import torch

    if isinstance(left, torch.Tensor) or isinstance(right, torch.Tensor):
        return (
            isinstance(left, torch.Tensor)
            and isinstance(right, torch.Tensor)
            and left.dtype == right.dtype
            and left.shape == right.shape
            and torch.equal(left, right)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _same_payload_value(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return (
            type(left) is type(right)
            and len(left) == len(right)
            and all(_same_payload_value(a, b) for a, b in zip(left, right))
        )
    if isinstance(left, float) and isinstance(right, float) and left != left:
        return right != right  # NaN round-trips as NaN
    return type(left) is type(right) and left == right
