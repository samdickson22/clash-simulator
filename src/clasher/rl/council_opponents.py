"""Public opponents sampled and frozen at match boundaries for council PPO."""

from __future__ import annotations

import hashlib
import json
import random
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
import torch
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .model import ClasherPolicy, PolicyConfig
from .public_observation import project_council_public_observation
from .public_scripted_opponent import PublicScriptedOpponent
from .structured_obs import StructuredObservationBuilder

if TYPE_CHECKING:
    from .selfplay_env import SelfPlayBattleEnv


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy_contract_sha256(config: PolicyConfig) -> str:
    return hashlib.sha256(
        json.dumps(
            config.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


class OpponentCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CouncilOpponentPool(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["council-opponents-v1"] = "council-opponents-v1"
    generation: int = Field(ge=0)
    phase: Literal["initial", "league"]
    gamedata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scripts: tuple[Literal["balanced", "pressure", "defense"], ...] = (
        "balanced",
        "pressure",
        "defense",
    )
    initial: tuple[OpponentCheckpoint, ...] = ()
    historical: tuple[OpponentCheckpoint, ...] = ()

    @model_validator(mode="after")
    def validate_pool(self) -> CouncilOpponentPool:
        if not self.scripts or len(set(self.scripts)) != len(self.scripts):
            raise ValueError("declare a nonempty unique scripted pool")
        if self.phase == "initial" and not self.initial:
            raise ValueError("initial phase requires a frozen initial policy")
        for entries in (self.initial, self.historical):
            if len({item.sha256 for item in entries}) != len(entries):
                raise ValueError("duplicate opponent weights distort sampling")
        return self


def league_history_pool(pool: CouncilOpponentPool) -> tuple[OpponentCheckpoint, ...]:
    """Historical opponents for the league phase: initial policies plus retained
    checkpoints, deduplicated by weight hash so no file is double-weighted."""
    seen: set[str] = set()
    entries = []
    for entry in (*pool.initial, *pool.historical):
        if entry.sha256 not in seen:
            seen.add(entry.sha256)
            entries.append(entry)
    return tuple(entries)


@dataclass
class _Episode:
    battle: object
    player_id: int
    assignment: dict
    model: ClasherPolicy | None
    script: PublicScriptedOpponent | None
    state: tuple[torch.Tensor, torch.Tensor] | None
    previous_action: int
    rng_state: torch.Tensor
    decisions: int = 0
    last_tick: int = -1
    last_action: int = -1
    outcome_recorded: bool = False


def outcome_log_for(assignment_log: Path) -> Path:
    """Monitoring-only per-match outcomes live next to the assignment log."""
    name = assignment_log.name
    if "assignments" in name:
        return assignment_log.with_name(name.replace("assignments", "outcomes"))
    return assignment_log.with_name(f"{assignment_log.stem}-outcomes.jsonl")


class CouncilLeagueOpponent:
    """Adapter for collect_rollout_stationary_opponents(opponent_bot=...).

    The manifest is read only when a new match starts. Initial phase uses an
    equal script/initial-policy mixture. League phase uses 25/50/25 percent
    scripts/history/current. The frozen initial policies (warm-start and
    scratch initializations) remain eligible inside the 50% historical share
    alongside retained checkpoints, uniformly per unique weight file, so the
    league keeps them visible after the first million decisions. Scripts fill
    the historical share only when neither pool exists. Current weights are
    copied at the boundary and never synchronized mid-match.
    This CPU actor adapter isolates opponent sampling from learner Torch RNG.
    """

    def __init__(
        self,
        *,
        builder: StructuredObservationBuilder,
        learner_model: ClasherPolicy,
        pool_path: str | Path,
        seed: int,
        worker_id: int = 0,
        assignment_log: str | Path | None = None,
        on_assignment: Callable[[dict], None] | None = None,
        checkpoint_cache_size: int = 4,
    ) -> None:
        if learner_model.config.public_contract_version != 4:
            raise ValueError("council opponents require public contract 4")
        if learner_model.config.dropout != 0:
            raise ValueError("council opponents require deterministic recurrent replay")
        if next(learner_model.parameters()).device.type != "cpu":
            raise ValueError("this local opponent adapter requires CPU actors")
        if checkpoint_cache_size < 1:
            raise ValueError("checkpoint cache must be positive")
        self.builder, self.learner_model = builder, learner_model
        # The existing builder factory carries contract version as metadata.
        self.builder.public_contract_version = 4  # type: ignore[attr-defined]
        self.pool_path = Path(pool_path).resolve()
        self.worker_id, self.policy_version = worker_id, 0
        self.learner_decisions = 0
        self.rng = random.Random(seed)
        self.assignment_log = None if assignment_log is None else Path(assignment_log)
        self.outcome_log = (
            None if self.assignment_log is None else outcome_log_for(self.assignment_log)
        )
        self.on_assignment = on_assignment
        self.checkpoint_cache_size = checkpoint_cache_size
        self._models: OrderedDict[str, ClasherPolicy] = OrderedDict()
        self._scripts: dict[str, PublicScriptedOpponent] = {}
        self._episodes: dict[object, _Episode] = {}
        self._serial = 0
        self._last_pool: CouncilOpponentPool | None = None
        self._last_pool_sha: str | None = None

    def set_context(self, *, policy_version: int, learner_decisions: int) -> None:
        if (
            policy_version < self.policy_version
            or learner_decisions < self.learner_decisions
        ):
            raise ValueError("opponent collection context moved backwards")
        self.policy_version, self.learner_decisions = policy_version, learner_decisions

    def assignment_for(self, env: SelfPlayBattleEnv) -> dict:
        return dict(self._episodes[env].assignment)

    def record_outcome(self, env: SelfPlayBattleEnv, learner_player: int) -> dict | None:
        """Log a finished match against its frozen assignment (monitoring only).

        Called by the collector before ``env.reset()``. It never changes
        sampling, weights or learner experience.
        """
        episode = self._episodes.get(env)
        if (
            env.battle is None
            or episode is None
            or episode.battle is not env.battle
            or episode.outcome_recorded
        ):
            return None
        winner = env.battle.winner
        result = (
            "draw" if winner is None else "win" if winner == learner_player else "loss"
        )
        record = {
            "assignment_id": episode.assignment["assignment_id"],
            "kind": episode.assignment["kind"],
            "style": episode.assignment["style"],
            "checkpoint_sha256": episode.assignment["checkpoint_sha256"],
            "phase": episode.assignment["phase"],
            "pool_generation": episode.assignment["pool_generation"],
            "learner_decisions_at_assignment": episode.assignment[
                "learner_decisions_at_assignment"
            ],
            "learner_player_id": learner_player,
            "learner_result": result,
            "end_tick": int(env.battle.tick),
        }
        episode.outcome_recorded = True
        if self.outcome_log is not None:
            self.outcome_log.parent.mkdir(parents=True, exist_ok=True)
            with self.outcome_log.open("a") as stream:
                stream.write(json.dumps(record, sort_keys=True) + "\n")
        return record

    def _new_model(self, state: dict) -> ClasherPolicy:
        # Constructing a throwaway initialization must not consume learner RNG.
        with torch.random.fork_rng(devices=[]):
            model = ClasherPolicy(
                self.learner_model.config, self.builder.card_stat_features
            )
        expected = model.state_dict()
        for name, value in expected.items():
            if name.endswith(("card_stat_features", "semantic_card_features")) and (
                name not in state or not torch.equal(value, state[name].cpu())
            ):
                raise ValueError("opponent semantic buffers differ from declared data")
        model.load_state_dict(state)
        return model.eval().requires_grad_(False)

    def _checkpoint(
        self, entry: OpponentCheckpoint, pool: CouncilOpponentPool
    ) -> ClasherPolicy:
        path = Path(entry.path)
        if not path.is_absolute():
            path = self.pool_path.parent / path
        if file_sha256(path) != entry.sha256:
            raise ValueError("opponent checkpoint changed")
        if entry.sha256 in self._models:
            self._models.move_to_end(entry.sha256)
            return self._models[entry.sha256]
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        if checkpoint.get("format_version") != 2:
            raise ValueError("opponent checkpoint must use recurrent format 2")
        config = PolicyConfig.from_dict(checkpoint["model_config"])
        if policy_contract_sha256(config) != pool.policy_contract_sha256:
            raise ValueError("opponent policy contract differs")
        if checkpoint.get("gamedata_sha256") != pool.gamedata_sha256:
            raise ValueError("opponent checkpoint has no matching data authority")
        model = self._new_model(checkpoint["model_state_dict"])
        self._models[entry.sha256] = model
        while len(self._models) > self.checkpoint_cache_size:
            self._models.popitem(last=False)
        return model

    def _start(self, env: SelfPlayBattleEnv, player_id: int) -> _Episode:
        assert env.battle is not None
        if env.battle.tick != 0:
            raise ValueError("opponent assignment must start at the match boundary")
        raw = self.pool_path.read_bytes()
        pool = CouncilOpponentPool.model_validate_json(raw)
        pool_sha = hashlib.sha256(raw).hexdigest()
        if self._last_pool is not None:
            if pool.generation < self._last_pool.generation:
                raise ValueError("opponent pool generation moved backwards")
            if (
                pool.generation == self._last_pool.generation
                and pool_sha != self._last_pool_sha
            ):
                raise ValueError("opponent pool changed without a new generation")
            if self._last_pool.phase == "league" and pool.phase != "league":
                raise ValueError("opponent pool phase moved backwards")
            if self._last_pool.phase == pool.phase == "initial" and (
                pool.model_dump(exclude={"generation"})
                != self._last_pool.model_dump(exclude={"generation"})
            ):
                raise ValueError("initial opponent mixture must remain frozen")
        if (
            policy_contract_sha256(self.learner_model.config)
            != pool.policy_contract_sha256
        ):
            raise ValueError("pool and learner policy contracts differ")
        if (
            tuple(self.builder.token_names)
            != self.learner_model.config.public_token_names
        ):
            raise ValueError("opponent builder vocabulary differs")
        if file_sha256(env.battle.card_loader.data_file) != pool.gamedata_sha256:
            raise ValueError("pool data differs from running environment")
        if file_sha256(self.builder.loader.data_file) != pool.gamedata_sha256:
            raise ValueError("opponent builder data differs")
        draw = self.rng.random()
        if pool.phase == "initial":
            kind = "script" if draw < 0.5 else "initial"
        else:
            kind = (
                "script" if draw < 0.25 else "historical" if draw < 0.75 else "current"
            )
        history_pool = league_history_pool(pool)
        fallback = kind == "historical" and not history_pool
        if fallback:
            kind = "script"
        model, script, checkpoint_sha, style = None, None, None, None
        if kind == "script":
            style = self.rng.choice(pool.scripts)
            if style not in self._scripts:
                self._scripts[style] = PublicScriptedOpponent(self.builder, style=style)
            script = self._scripts[style]
        elif kind in ("initial", "historical"):
            entry = self.rng.choice(pool.initial if kind == "initial" else history_pool)
            checkpoint_sha = entry.sha256
            model = self._checkpoint(entry, pool)
        else:
            state = {
                key: value.detach().cpu().clone()
                for key, value in self.learner_model.state_dict().items()
            }
            model = self._new_model(state)
            digest = hashlib.sha256()
            for name, tensor in sorted(state.items()):
                digest.update(name.encode())
                digest.update(str((tuple(tensor.shape), tensor.dtype)).encode())
                digest.update(tensor.contiguous().numpy().tobytes())
            checkpoint_sha = digest.hexdigest()
        self._serial += 1
        assignment = {
            "assignment_id": f"worker-{self.worker_id}-episode-{self._serial}",
            "player_id": player_id,
            "pool_generation": pool.generation,
            "pool_sha256": pool_sha,
            "phase": pool.phase,
            "kind": kind,
            "style": style,
            "checkpoint_sha256": checkpoint_sha,
            "history_fallback_to_script": fallback,
            "learner_policy_version": self.policy_version,
            "learner_decisions_at_assignment": self.learner_decisions,
            "game_start_tick": env.battle.tick,
            "gamedata_sha256": pool.gamedata_sha256,
        }
        if self.assignment_log is not None:
            self.assignment_log.parent.mkdir(parents=True, exist_ok=True)
            with self.assignment_log.open("a") as stream:
                stream.write(json.dumps(assignment, sort_keys=True) + "\n")
        if self.on_assignment is not None:
            self.on_assignment(dict(assignment))
        self._last_pool, self._last_pool_sha = pool, pool_sha
        generator = torch.Generator().manual_seed(self.rng.getrandbits(63))
        return _Episode(
            env.battle,
            player_id,
            assignment,
            model,
            script,
            None if model is None else model.initial_state(1),
            env.action_space.no_op_action,
            generator.get_state(),
        )

    @torch.no_grad()
    def select_action(
        self, env: SelfPlayBattleEnv, player_id: int, *, action_mask: np.ndarray
    ) -> int:
        if env.battle is None:
            raise ValueError("opponent requires a running match")
        episode = self._episodes.get(env)
        if (
            episode is None
            or episode.battle is not env.battle
            or episode.player_id != player_id
        ):
            episode = self._start(env, player_id)
            self._episodes[env] = episode
        if episode.last_tick == env.battle.tick:
            if not action_mask[episode.last_action]:
                raise ValueError("duplicate opponent frame changed legal support")
            return episode.last_action
        observation = env.get_structured_observation(
            player_id, actor_observation_domain="simulator-exact"
        )
        public_mask = env.get_action_mask(player_id, structured_observation=observation)
        if not np.array_equal(public_mask, action_mask):
            raise ValueError("opponent transport mask differs from public mask")
        if episode.script is not None:
            action = episode.script.select_action(
                project_council_public_observation(
                    self.builder.build_actor(env.battle, player_id)
                )
            )
        else:
            from .train_recurrent import _stack_step_inputs

            assert episode.model is not None and episode.state is not None

            inputs = _stack_step_inputs(
                [observation],
                public_mask[None],
                np.asarray([episode.previous_action]),
                np.zeros(1, dtype=np.float32),
                np.asarray([episode.decisions == 0]),
                torch.device("cpu"),
                public_observation_confidence=True,
                builder=self.builder,
            )
            with torch.random.fork_rng(devices=[]):
                torch.set_rng_state(episode.rng_state)
                actions, _, _, state, _ = episode.model.act(
                    inputs, episode.state, deterministic=False
                )
                episode.rng_state = torch.get_rng_state()
            action = int(actions[0, 0])
            episode.state = (state[0].detach(), state[1].detach())
        if not public_mask[action]:
            raise ValueError("opponent produced an illegal action")
        episode.previous_action = action
        episode.decisions += 1
        episode.last_tick, episode.last_action = env.battle.tick, action
        return action
