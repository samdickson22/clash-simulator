"""Complete-match demonstrations from public engineering teachers.

Collection is explicit and never runs on import. The coordinator must admit the
scope before producing labels; M0 uses only synthetic adapter contract tests.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from clasher.battle import STANDARD_MATCH_TICKS

from .imitation import CORPUS_SCHEMA_VERSION, CorpusMetadata, validate_corpus_levels
from .public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from .public_observation import project_council_public_observation
from .public_policy_contract import PublicPolicySequence
from .public_scripted_opponent import PublicScriptedOpponent
from .selfplay_env import SelfPlayBattleEnv, resolve_match_horizon
from .structured_obs import StructuredObservationBuilder


@dataclass(frozen=True)
class ScriptedGameDemonstration:
    public: PublicPolicySequence
    controls: dict[str, np.ndarray]
    metadata: CorpusMetadata
    execution: dict[str, np.ndarray]

    def imitation_arrays(self) -> dict[str, np.ndarray]:
        arrays = dict(self.public.arrays) | self.controls
        validate_corpus_levels(arrays, required=True)
        self.public.validate_action_mask(arrays["action_masks"])
        return arrays

    def save(self, path: Path) -> None:
        """Publish a complete game without overwriting an existing role record."""
        arrays = self.imitation_arrays()
        with path.open("xb") as stream:
            np.savez_compressed(stream, metadata_json=np.asarray(self.metadata.to_json()), **arrays, **self.execution)


def collect_public_script_game(
    env: SelfPlayBattleEnv,
    builder: StructuredObservationBuilder,
    *,
    seed: int,
    episode_id: int,
    role: str,
    family_id: str,
    learner_player_id: int = 0,
    styles: tuple[str, str] = ("balanced", "pressure"),
    max_decisions: int = 10000,
) -> ScriptedGameDemonstration:
    """Collect one initialized full match, keeping natural wait opportunities.

    The caller resets the environment with the declared decks before calling.
    Aborted or shortened games raise without publishing a partial trajectory.
    Only the learner seat supplies labels; both players see public observations.
    """
    if role not in {"training", "development", "acceptance"} or not family_id:
        raise ValueError("declare an immutable data role and deck family")
    if learner_player_id not in (0, 1) or max_decisions <= 0:
        raise ValueError("invalid learner seat or decision budget")
    if env.battle is None or env.battle.tick != 0 or env.battle.game_over:
        raise ValueError("complete-game collection requires a fresh reset")
    full_horizon = resolve_match_horizon(STANDARD_MATCH_TICKS, 4)
    if env.public_contract_version != 4 or env.max_ticks != full_horizon or env.defense_scenario is not None:
        raise ValueError("public-v4 full-match horizon is required; shortened and defense-scenario games are excluded")
    if env.decision_interval_ticks != 5:
        raise ValueError("council demonstration timing requires five ticks")
    if not builder.public_hand_levels or not builder.public_entity_levels:
        raise ValueError("council demonstrations require hand and entity levels")
    if builder.public_history_slots != 4 or builder.public_seen_card_slots != 8:
        raise ValueError("council demonstrations require four history and eight seen-card slots")
    # Script metadata still assumes level 11 for own cards and Crown towers.
    for player in env.battle.players:
        if getattr(player, "tower_level", 11) != 11 or any(level != 11 for level in getattr(player, "card_levels", {}).values()):
            raise ValueError("mixed-level teachers require separate qualification")
    initial_decks = [list(player.deck) for player in env.battle.players]
    controllers = [PublicScriptedOpponent(builder, style=style) for style in styles]
    mask_builder = PublicActionMaskBuilder(builder)
    observations = []
    masks = []
    actions = []
    accepted = []
    ticks = []
    previous = []
    prior_action = env.action_space.no_op_action
    for _ in range(max_decisions):
        packets = [project_council_public_observation(builder.build_actor(env.battle, seat)) for seat in (0, 1)]
        public_masks = {seat: mask_builder.build(PublicActionMaskInput.from_confidence_observation(packets[seat])) for seat in (0, 1)}
        decisions = {seat: controllers[seat].select_action(packets[seat]) for seat in (0, 1)}
        if any(not public_masks[seat][decisions[seat]] for seat in (0, 1)):
            raise ValueError("public teacher submitted an illegal action")
        observations.append(packets[learner_player_id])
        masks.append(public_masks[learner_player_id])
        actions.append(decisions[learner_player_id])
        previous.append(prior_action)
        ticks.append(env.battle.tick)
        _, done, info = env.step(decisions, pre_action_masks=public_masks)
        accepted.append(info.action_success[learner_player_id])
        prior_action = decisions[learner_player_id]
        if done:
            if not env.battle.game_over:
                raise ValueError("collector reached a truncation instead of match termination")
            break
    else:
        raise ValueError("decision budget exhausted before complete match")
    # Preserve the terminal observation as recurrent context, never a label.
    terminal = project_council_public_observation(builder.build_actor(env.battle, learner_player_id))
    observations.append(terminal)
    masks.append(mask_builder.build(PublicActionMaskInput.from_confidence_observation(terminal)))
    actions.append(env.action_space.no_op_action)
    previous.append(prior_action)
    count = len(actions)
    starts = np.zeros(count, dtype=np.bool_)
    starts[0] = True
    valid = np.zeros(count, dtype=np.bool_)
    # Rejected commands remain causal context and execution evidence, never a
    # supervised instruction to repeat an action the environment did not accept.
    valid[:-1] = np.asarray(accepted, dtype=np.bool_)
    public = PublicPolicySequence.from_observations(builder, observations)
    controls = {
        "action_masks": np.asarray(masks, dtype=np.bool_),
        "expert_actions": np.asarray(actions, dtype=np.int64),
        "previous_actions": np.asarray(previous, dtype=np.int64),
        "previous_rewards": np.zeros(count, dtype=np.float32),
        "episode_starts": starts,
        "episode_ids": np.full(count, episode_id, dtype=np.int64),
        "expert_action_supervision_valid": valid,
    }
    provenance = json.dumps({"role": role, "family_id": family_id, "seed": seed, "seat": learner_player_id, "styles": styles, "initial_decks": initial_decks, "teacher": "public-script", "complete_game": True, "sampling": "every-five-tick-opportunity", "terminal_context_rows": 1, "effective_deployment": "unknown; acceptance is not deployment"}, sort_keys=True)
    metadata = CorpusMetadata(
        schema_version=CORPUS_SCHEMA_VERSION, created_at=datetime.now(timezone.utc).isoformat(),
        seed=seed, decisions=count - 1, samples=count, decision_interval=5,
        max_ticks=full_horizon, planner_depth=0, planner_simulations=0,
        planner_action_samples=0, max_entities=builder.max_entities,
        token_names=builder.token_names, reward_profile=env.reward_profile,
        label_source="public-script", label_strategy=styles[learner_player_id],
        public_contract_version=4, public_history_slots=4, public_seen_card_slots=8,
        provenance=provenance,
    )
    execution = {
        "submitted_actions": np.asarray(actions[:-1], dtype=np.int64),
        "submitted_ticks": np.asarray(ticks, dtype=np.int64),
        "accepted_commands": np.asarray(accepted, dtype=np.bool_),
        "accepted_command_ticks": np.where(np.asarray(accepted, dtype=np.bool_) & (np.asarray(actions[:-1]) < env.action_space.no_op_action), np.asarray(ticks, dtype=np.int64), -1),
        "submitted_world_positions": np.asarray([
            [selection.position.x, selection.position.y] if selection.position is not None else [np.nan, np.nan]
            for action in actions[:-1]
            for selection in [env.action_space.decode_action(action, learner_player_id)]
        ], dtype=np.float32),
        "effective_deployment_ticks": np.full(count - 1, -1, dtype=np.int64),
    }
    result = ScriptedGameDemonstration(public, controls, metadata, execution)
    result.imitation_arrays()
    return result
