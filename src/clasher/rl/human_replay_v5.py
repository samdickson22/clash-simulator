"""Human-replay demonstrations on public contract v5 (C56 human prior).

The P16 replayer (``human_replay_demonstrations``) re-simulates IL_Replay
recordings open-loop in the scalar engine: base card forms, level 11, Princess
towers, both players' placements at their recorded 20 Hz ticks. This module
keeps that replayer and its row format and changes what contract v5 and
``scope-expansion/PLAN.md`` section 4 require:

* Observation: ``ContractV5ObservationBuilder.build_public`` (pinned 360-token
  vocabulary, semantics v5, enemy stealthed / underground units hidden, own
  Champion button). Mask: ``ContractV5ActionMaskBuilder`` (the game's 3x3
  Princess-tower footprint; ability legal only when the engine allows it).
* Champion ability labels. A recorded own ``activate_ability`` is labelled as
  the ability action only when the own deck holds exactly one Champion and no
  hero form, and the v5 mask allows it. Otherwise it still runs in the sim but
  its row carries no supervision ("label missing").
* Hard contradictions end supervision (the perspective stops): the sim kills a
  tower the recording keeps; a pocket placement while the sim tower stands; a
  recorded placement the engine rejects after nudging; a forced hand (either
  side); an elixir shortfall above the top-up tolerance (either side).
* A real tower kill the sim never reproduces has no timestamp: the perspective
  is kept and flagged (``unreproduced_real_kill``) for down-weighting.
* Storage is the P16 compact shard plus the per-row Champion-button flag, and
  shards are written byte-deterministically (fixed zip timestamps).

Research artifact (strategy amendment 2026-10-01, update 2026-10-03); not a
Tier A admitted input. Collection never runs on import.
"""
from __future__ import annotations

import io
import json
import random
import zipfile
from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from clasher.arena import Position
from clasher.battle import STANDARD_MATCH_TICKS, BattleState

from .action_space import DiscreteTileActionSpace
from .common import NUM_HAND_SLOTS, NUM_TILES
from .contract_v5 import (
    CHAMPION_COOLDOWN_GLOBAL,
    CONTRACT_VERSION,
    V5_DESCRIPTOR_NAMES,
    CachedContractV5ActionMask,
    ContractV5ObservationBuilder,
    global_confidence_v5,
)
from .deck_pool import apply_ordered_deck_to_player
from .human_replay_demonstrations import (
    DECISION_INTERVAL_TICKS,
    LABEL_SOURCE,
    LANES,
    NO_OP_ACTION,
    NUM_ACTIONS,
    PROVENANCE,
    HumanReplayDemonstration,
    RecordedMatch,
    RecordedPlay,
    _ENTITY_COLUMNS,
    _EXECUTION_FIELDS,
    _ROW_FIELDS,
    _force_card_into_hand,
    _is_pocket,
    _lane,
    _require_equal,
    _stable_seed,
    _towers,
    _zone_restricted,
    initial_cycle_order,
    nearest_adjacent_legal_action,
    proven_down_lanes,
    split_card_form,
    world_tile,
)
from .imitation import CORPUS_SCHEMA_VERSION, CorpusMetadata
from .public_policy_contract import PublicPolicySequence
from .reward_model import OBJECTIVE_V1
from .selfplay_env import resolve_match_horizon
from .structured_obs import ENTITY_FEATURE_SIZE, EntityCapacityError

ABILITY_ACTION = NO_OP_ACTION + 1
SHARD_SCHEMA_V5 = "clasher.human-replay-shard.v5"
SIMULATION = "open-loop scalar re-simulation; base forms; level 11; Princess towers; public contract v5"
TOWER_CLAMP_RULE = ("towers proven standing in the recording are held at 1 HP; "
                    "cut when cumulative overshoot exceeds 1.0x tower max HP; "
                    "multiply existing row weights by 0.5 at/after first clamp")
HARD_CUTS = (
    "sim_kill_of_tower_standing_in_real", "pocket_play_but_sim_tower_alive", "opponent_placement_rejected",
    "own_placement_rejected", "own_card_not_in_hand", "opponent_forced_hand", "own_insufficient_elixir",
    "opponent_insufficient_elixir", "own_masked_tile", "entity_capacity",
)


@dataclass(frozen=True)
class ReconstructionConfigV5:
    elixir_topup_tolerance: float = 0.05
    masked_tile_policy: str = "adjacent"
    opponent_forced_hand_policy: str = "cut"
    opponent_elixir_policy: str = "cut"
    max_ticks: int = resolve_match_horizon(STANDARD_MATCH_TICKS, 4)
    tower_clamp: bool = False

    def __post_init__(self) -> None:
        if self.masked_tile_policy not in {"cut", "adjacent"}:
            raise ValueError("unknown masked tile policy")
        if self.opponent_forced_hand_policy not in {"cut", "repair"}:
            raise ValueError("unknown opponent forced-hand policy")
        if self.opponent_elixir_policy not in {"cut", "repair"}:
            raise ValueError("unknown opponent elixir policy")
        if not 0.0 <= self.elixir_topup_tolerance <= 0.25:
            raise ValueError("elixir top-up tolerance must stay tiny")


@dataclass(frozen=True)
class RecordedAbility:
    tick: int
    order: int


class TowerClamp:
    """Replay-local tower damage hooks. No engine classes or globals are patched."""

    threshold = 1.0

    def __init__(self, battle, match, down_lanes):
        self.battle, self.match, self.down_lanes = battle, match, down_lanes
        self.towers = {(e.player_id, e._crown_tower_slot): e for e in battle.entities.values()
                       if getattr(e, "_crown_tower_slot", None) is not None}
        self.overshoot = {key: 0.0 for key in self.towers}
        self.counts = {key: 0 for key in self.towers}
        self.first_tick = None
        self.exceeded = None
        for key, tower in self.towers.items():
            tower.take_damage = self._hook(key, tower, tower.take_damage)

    def contradicts(self, key):
        pid, slot = key
        if slot == "king":
            return not self.match.king_down_allowed(pid, self.battle.tick)
        other = "right" if slot == "left" else "left"
        down = 1 + int(not self.towers[(pid, other)].is_alive)
        return (down > self.match.princess_down_allowed(pid, self.battle.tick)
                or (self.match.princess_down[pid] == 1
                    and self.down_lanes[pid] == frozenset({other})))

    def _hook(self, key, tower, original):
        def take_damage(amount, *, source_kind=None, affects_hidden=False):
            before = float(tower.hitpoints)
            if (tower.is_alive and float(amount) > 0 and before - float(amount) <= 0
                    and tower.can_receive_effect(source_kind, affects_hidden=affects_hidden)
                    and self.contradicts(key)):
                # Crown towers have no incoming-damage modifiers. Preserve their
                # normal damage/King activation path up to the retained last HP.
                if getattr(tower, "mechanics", []):
                    raise ValueError("tower clamp requires unmodified crown-tower damage")
                self.overshoot[key] += float(amount) - (before - 1.0)
                self.counts[key] += 1
                if self.first_tick is None:
                    self.first_tick = self.battle.tick
                if self.overshoot[key] / tower.max_hitpoints > self.threshold and self.exceeded is None:
                    self.exceeded = (self.battle.tick, key)
                amount = before - 1.0
                if amount <= 0:
                    return None
            return original(amount, source_kind=source_kind, affects_hidden=affects_hidden)
        return take_damage

    def row(self):
        active = any(self.counts[key] and tower.is_alive and tower.hitpoints <= 1.0
                     and self.contradicts(key) for key, tower in self.towers.items())
        fraction = max((self.overshoot[key] / tower.max_hitpoints for key, tower in self.towers.items()), default=0.0)
        return bool(active), fraction

    def summary(self):
        return {"first_clamp_tick": self.first_tick, "tower_clamp_threshold": self.threshold,
                "tower_clamp_count": sum(self.counts.values()),
                "tower_clamp_counts": {f"{pid}:{slot}": count for (pid, slot), count in self.counts.items()},
                "max_overshoot_frac": self.row()[1], "tower_clamp_rule": TOWER_CLAMP_RULE}


def tower_clamp_weights(weights, summary, submitted_ticks):
    """Multiply PLAN 4.6 weights, including its other factors, after first clamp."""
    result = np.asarray(weights, dtype=np.float32).copy()
    first = summary.get("first_clamp_tick")
    if first is not None:
        result[np.asarray(submitted_ticks) >= first] *= 0.5
    return result


def champion_cards(deck: Sequence[str], builder: ContractV5ObservationBuilder) -> list[str]:
    column = V5_DESCRIPTOR_NAMES.index("is_champion")
    result = []
    for name in deck:
        token = builder.token_id(name, namespace="card_action")
        if token > 1 and builder.v5_card_descriptors[token, column] > 0:
            result.append(name)
    return result


def reconstruct_perspective_v5(
    match: RecordedMatch,
    learner: int,
    builder: ContractV5ObservationBuilder,
    *,
    mask_builder: CachedContractV5ActionMask | None = None,
    config: ReconstructionConfigV5 | None = None,
    episode_id: int = 0,
    row_observer=None,
) -> HumanReplayDemonstration:
    """Replay one recording and record the learner seat's v5 decision rows."""
    if learner not in (0, 1):
        raise ValueError("learner seat must be 0 or 1")
    if not isinstance(builder, ContractV5ObservationBuilder):
        raise TypeError("contract-v5 reconstruction needs the v5 builder")
    config = config or ReconstructionConfigV5()
    mask_builder = mask_builder or CachedContractV5ActionMask(builder)
    own_deck = match.decks[learner]
    if any(builder.token_id(name, namespace="card_action") <= 1 for name in own_deck):
        raise ValueError("the learner deck is outside the builder vocabulary")
    deck_slugs = match.info.get("deck_slugs") or ([], [])
    forms = [[split_card_form(slug)[1] for slug in slugs] for slugs in deck_slugs]
    own_forms = forms[learner] if forms and len(forms) > learner else []
    own_champions = champion_cards(own_deck, builder)
    ability_attributable = len(own_champions) == 1 and "hero" not in own_forms

    battle = BattleState(rng=random.Random(_stable_seed(match.match_id, learner)))
    for pid in (0, 1):
        played = [play.card for play in match.plays if play.player == pid]
        order = initial_cycle_order(match.decks[pid], played)
        opening = order[:NUM_HAND_SLOTS]
        random.Random(_stable_seed(match.match_id, pid) ^ 0x5EED).shuffle(opening)
        apply_ordered_deck_to_player(battle.players[pid], opening + order[NUM_HAND_SLOTS:])
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    down_lanes = proven_down_lanes(match, battle)
    clamp = TowerClamp(battle, match, down_lanes) if config.tower_clamp else None
    clamp_rows = []
    own_events: deque[RecordedPlay | RecordedAbility] = deque(sorted(
        [play for play in match.plays if play.player == learner]
        + [RecordedAbility(tick, order) for tick, order, player in match.ability_events if player == learner],
        key=lambda event: (event.tick, event.order)))
    other_events: deque[tuple[int, int, RecordedPlay | None]] = deque(sorted(
        [(play.tick, play.order, play) for play in match.plays if play.player != learner]
        + [(tick, order, None) for tick, order, player in match.ability_events if player != learner],
        key=lambda item: item[:2]))
    end_tick = min(match.playable_end_tick, config.max_ticks)
    learner_state = battle.players[learner]
    counters: dict[str, Any] = {name: 0 for name in (
        "own_plays_labelled", "own_plays_deferred", "own_plays_projected", "own_elixir_topups",
        "own_abilities", "own_abilities_labelled", "own_abilities_unattributable", "own_abilities_masked",
        "own_abilities_rejected", "opponent_plays", "opponent_hand_forced", "opponent_elixir_topups",
        "opponent_nudged", "opponent_rejected", "opponent_abilities", "opponent_abilities_accepted",
        "simultaneous_own_plays", "evo_or_hero_plays_labelled")}
    counters["own_elixir_topup_total"] = 0.0
    counters["opponent_elixir_topup_total"] = 0.0
    counters["opponent_max_shortfall"] = 0.0
    own_form_by_card = {name: (own_forms[index] if index < len(own_forms) else "base")
                        for index, name in enumerate(own_deck)}
    observations, masks, actions, ticks, play_ticks, play_positions, millitiles = [], [], [], [], [], [], []
    projections: list[float] = []
    invalid_rows: set[int] = set()
    scheduled: tuple[int, int, RecordedPlay | None, bool] | None = None  # (tick, action, projected play, is ability)
    cut_reason: str | None = None
    cut_detail: dict[str, Any] = {}
    last_row_valid = True
    tower_state = _towers(battle)
    projection = [0.0]
    first_projected_row: int | None = None

    def observe():
        packet = builder.build_public(battle, learner)
        return packet, mask_builder.build(packet)

    def label_own_play(play: RecordedPlay, tick: int, packet, mask):
        exact = play.tick <= tick
        hand = list(learner_state.hand[:NUM_HAND_SLOTS])
        if play.card not in hand:
            return (None, packet, mask, "own_card_not_in_hand") if exact else (None, packet, mask, None)
        slot = hand.index(play.card)
        tile_x, tile_y = world_tile(play.x_millitiles, play.y_millitiles)
        action = action_space.encode_action(slot, tile_x, tile_y, learner)
        resolved = battle.resolve_card_play(learner, play.card)
        cost = float(resolved[1].mana_cost) if resolved is not None else float("inf")
        shortfall = cost - float(learner_state.elixir)
        if shortfall > 1e-6 and not mask[slot * NUM_TILES:(slot + 1) * NUM_TILES].any():
            if not exact:
                return None, packet, mask, None
            if shortfall > config.elixir_topup_tolerance + 1e-9:
                cut_detail.update(shortfall=round(shortfall, 4), card=play.card)
                return None, packet, mask, "own_insufficient_elixir"
            learner_state.elixir = cost
            counters["own_elixir_topups"] += 1
            counters["own_elixir_topup_total"] += shortfall
            packet, mask = observe()
        if not mask[action]:
            world_x, world_y = play.x_millitiles / 1000.0, play.y_millitiles / 1000.0
            cut_detail.update(card=play.card, world=[world_x, world_y])
            if (_is_pocket(learner, world_y) and _zone_restricted(battle, learner, play.card)
                    and getattr(battle.players[1 - learner], f"{_lane(world_x)}_tower_hp") > 0):
                return None, packet, mask, "pocket_play_but_sim_tower_alive"
            adjacent = nearest_adjacent_legal_action(mask, action) if config.masked_tile_policy == "adjacent" else None
            if adjacent is None:
                return None, packet, mask, "own_masked_tile"
            cut_detail.clear()
            projection[0] = adjacent[1]
            return adjacent[0], packet, mask, None
        return action, packet, mask, None

    def no_label_row() -> None:
        play_ticks.append(-1)
        play_positions.append((np.nan, np.nan))
        millitiles.append((-1, -1))

    while True:
        tick = battle.tick
        if battle.game_over:
            cut_reason = "sim_game_over"
            break
        if tick >= end_tick:
            cut_reason = "recorded_end" if tick >= match.playable_end_tick else "horizon"
            break
        if tick % DECISION_INTERVAL_TICKS == 0:
            try:
                packet, mask = observe()
            except EntityCapacityError:
                cut_reason = "entity_capacity"
                break
            label = NO_OP_ACTION
            row_invalid = False
            projection[0] = 0.0
            event = own_events[0] if own_events else None
            if scheduled is None and event is not None and event.tick < tick + DECISION_INTERVAL_TICKS:
                if isinstance(event, RecordedAbility):
                    own_events.popleft()
                    counters["own_abilities"] += 1
                    if not ability_attributable:
                        counters["own_abilities_unattributable"] += 1
                        row_invalid = True
                    elif not mask[ABILITY_ACTION]:
                        counters["own_abilities_masked"] += 1
                        row_invalid = True
                    else:
                        label = ABILITY_ACTION
                        counters["own_abilities_labelled"] += 1
                    scheduled = (max(event.tick, tick), ABILITY_ACTION, None, True)
                    play_ticks.append(event.tick)
                    play_positions.append((np.nan, np.nan))
                    millitiles.append((-1, -1))
                else:
                    play = event
                    action, packet, mask, reason = label_own_play(play, tick, packet, mask)
                    if reason is not None:
                        cut_reason = reason
                        cut_detail.setdefault("tick", play.tick)
                        break
                    if action is None:
                        no_label_row()
                    else:
                        own_events.popleft()
                        label = action
                        scheduled = (max(play.tick, tick), action, play if projection[0] > 0 else None, False)
                        counters["own_plays_labelled"] += 1
                        counters["evo_or_hero_plays_labelled"] += own_form_by_card.get(play.card, "base") != "base"
                        if projection[0] > 0:
                            counters["own_plays_projected"] += 1
                            if first_projected_row is None:
                                first_projected_row = len(actions)
                        counters["own_plays_deferred"] += play.tick < tick
                        play_ticks.append(play.tick)
                        play_positions.append((play.x_millitiles / 1000.0, play.y_millitiles / 1000.0))
                        millitiles.append((play.x_millitiles, play.y_millitiles))
                        if own_events and own_events[0].tick < tick + DECISION_INTERVAL_TICKS:
                            counters["simultaneous_own_plays"] += 1
            else:
                no_label_row()
            if row_invalid:
                invalid_rows.add(len(actions))
            projections.append(projection[0])
            observations.append(packet)
            masks.append(mask)
            actions.append(label)
            ticks.append(tick)
            if clamp is not None:
                clamp_rows.append(clamp.row())
            if row_observer is not None:
                row_observer(battle, learner, label)
        if scheduled is not None and scheduled[0] <= tick:
            if scheduled[3]:
                accepted = bool(battle.activate_champion_ability(learner))
                if not accepted:
                    counters["own_abilities_rejected"] += 1
            elif scheduled[2] is None:
                accepted = action_space.apply_action(battle, learner, scheduled[1])
            else:
                accepted = battle.deploy_card(learner, scheduled[2].card, Position(
                    scheduled[2].x_millitiles / 1000.0, scheduled[2].y_millitiles / 1000.0))
            was_ability = scheduled[3]
            scheduled = None
            if not accepted and not was_ability:
                cut_reason = "own_placement_rejected"
                cut_detail.update(tick=tick, action=int(actions[-1]), hand=list(learner_state.hand[:NUM_HAND_SLOTS]),
                                  elixir=round(float(learner_state.elixir), 4))
                last_row_valid = False
                break
        while other_events and other_events[0][0] <= tick and cut_reason is None:
            _, _, play = other_events.popleft()
            pid = 1 - learner
            player = battle.players[pid]
            if play is None:
                counters["opponent_abilities"] += 1
                counters["opponent_abilities_accepted"] += bool(battle.activate_champion_ability(pid))
                continue
            counters["opponent_plays"] += 1
            if play.card not in player.hand[:NUM_HAND_SLOTS]:
                counters["opponent_hand_forced"] += 1
                if config.opponent_forced_hand_policy == "cut":
                    cut_reason = "opponent_forced_hand"
                    cut_detail.update(tick=play.tick, card=play.card, side="opponent")
                    break
                _force_card_into_hand(player, play.card)
            resolved = battle.resolve_card_play(pid, play.card)
            if resolved is not None and player.elixir + 1e-9 < resolved[1].mana_cost:
                shortfall = float(resolved[1].mana_cost) - float(player.elixir)
                counters["opponent_max_shortfall"] = max(counters["opponent_max_shortfall"], shortfall)
                if config.opponent_elixir_policy == "cut" and shortfall > config.elixir_topup_tolerance + 1e-9:
                    cut_reason = "opponent_insufficient_elixir"
                    cut_detail.update(tick=play.tick, card=play.card, shortfall=round(shortfall, 4), side="opponent")
                    break
                counters["opponent_elixir_topups"] += 1
                counters["opponent_elixir_topup_total"] += shortfall
                player.elixir = float(resolved[1].mana_cost)
            x, y = play.x_millitiles / 1000.0, play.y_millitiles / 1000.0
            accepted = battle.deploy_card(pid, play.card, Position(x, y))
            if not accepted:
                forward = -1 if pid == 0 else 1
                for dx, dy in ((0, forward), (1, 0), (-1, 0), (0, -forward), (1, forward), (-1, forward)):
                    if battle.deploy_card(pid, play.card, Position(x + dx, y + dy)):
                        accepted = True
                        counters["opponent_nudged"] += 1
                        break
            if not accepted:
                counters["opponent_rejected"] += 1
                pocket = (_is_pocket(pid, y) and _zone_restricted(battle, pid, play.card)
                          and getattr(learner_state, f"{_lane(x)}_tower_hp") > 0)
                cut_reason = "pocket_play_but_sim_tower_alive" if pocket else "opponent_placement_rejected"
                cut_detail.update(tick=play.tick, card=play.card, world=[x, y], side="opponent")
        if cut_reason is not None:
            break
        before = tower_state
        battle.step()
        after = tower_state = _towers(battle)
        if clamp is not None and clamp.exceeded is not None:
            clamp_tick, (pid, slot) = clamp.exceeded
            cut_reason = "sim_kill_of_tower_standing_in_real"
            cut_detail.update(tick=clamp_tick, owner=pid, slot=slot,
                              overshoot_frac=clamp.row()[1], threshold=clamp.threshold)
            break
        for (pid, slot), alive in after.items():
            if alive or not before[(pid, slot)]:
                continue
            if slot == "king":
                contradicted = not match.king_down_allowed(pid, battle.tick)
            else:
                other = "right" if slot == "left" else "left"
                sim_down = sum(not after[(pid, lane)] for lane in LANES)
                contradicted = (sim_down > match.princess_down_allowed(pid, battle.tick)
                                or (match.princess_down[pid] == 1 and down_lanes[pid] == frozenset({other})))
            if contradicted:
                cut_reason = "sim_kill_of_tower_standing_in_real"
                cut_detail.update(tick=battle.tick, owner=pid, slot=slot)
        if cut_reason is not None:
            break

    terminal_row = False
    if cut_reason == "sim_game_over" and observations:
        packet, mask = observe()
        observations.append(packet)
        masks.append(mask)
        actions.append(NO_OP_ACTION)
        ticks.append(battle.tick)
        if clamp is not None:
            clamp_rows.append(clamp.row())
        no_label_row()
        projections.append(0.0)
        terminal_row = True
    count = len(actions)
    if count == 0:
        raise ValueError(f"perspective produced no decision row ({cut_reason})")
    valid = np.ones(count, dtype=np.bool_)
    for row in invalid_rows:
        valid[row] = False
    if terminal_row or not last_row_valid:
        valid[-1] = False
    starts = np.zeros(count, dtype=np.bool_)
    starts[0] = True
    labels = np.asarray(actions, dtype=np.int64)
    previous = np.concatenate([[NO_OP_ACTION], labels[:-1]]).astype(np.int64)
    public = PublicPolicySequence.from_observations(builder, observations)
    controls = {
        "action_masks": np.asarray(masks, dtype=np.bool_),
        "expert_actions": labels,
        "previous_actions": previous,
        "previous_rewards": np.zeros(count, dtype=np.float32),
        "episode_starts": starts,
        "episode_ids": np.full(count, episode_id, dtype=np.int64),
        "expert_action_supervision_valid": valid,
    }
    sim_princess_down = tuple(sum(getattr(battle.players[pid], f"{lane}_tower_hp") <= 0 for lane in LANES) for pid in (0, 1))
    sim_king_down = tuple(battle.players[pid].king_tower_hp <= 0 for pid in (0, 1))
    reached_end = cut_reason in {"recorded_end", "horizon", "sim_game_over"}
    unreproduced = []
    if reached_end:
        for pid in (0, 1):
            real = 3 if match.king_down[pid] else int(match.princess_down[pid] or 0)
            sim = 3 if sim_king_down[pid] else int(sim_princess_down[pid])
            if real > sim:
                unreproduced.append(pid)
    supervised_plays = int(np.count_nonzero(valid & (labels < NO_OP_ACTION)))
    summary = {
        "contract_version": CONTRACT_VERSION,
        "match_id": match.match_id,
        "side": ("team", "opponent")[learner],
        "seat": learner,
        "episode_id": episode_id,
        "recorded_result": match.results[learner],
        "recorded_crowns": [match.crowns[learner], match.crowns[1 - learner]],
        "cut_reason": cut_reason,
        "hard_cut": cut_reason in HARD_CUTS,
        "cut_tick": int(battle.tick),
        "cut_detail": cut_detail,
        "playable_end_tick": int(match.playable_end_tick),
        "rows": count,
        "supervised_rows": int(valid.sum()),
        "supervised_plays": supervised_plays,
        "supervised_abilities": int(np.count_nonzero(valid & (labels == ABILITY_ACTION))),
        "recorded_own_plays": sum(play.player == learner for play in match.plays),
        "recorded_own_abilities": sum(player == learner for _, _, player in match.ability_events),
        "terminal_context_row": terminal_row,
        "first_projected_row": first_projected_row,
        "own_deck": list(own_deck),
        "opponent_deck": list(match.decks[1 - learner]),
        "own_forms": own_forms,
        "opponent_forms": forms[1 - learner] if len(forms) > 1 - learner else [],
        "own_champions": own_champions,
        "ability_attributable": ability_attributable,
        "real_princess_down": [match.princess_down[learner], match.princess_down[1 - learner]],
        "real_king_down": [match.king_down[learner], match.king_down[1 - learner]],
        "sim_princess_down_at_cut": [sim_princess_down[learner], sim_princess_down[1 - learner]],
        "sim_king_down_at_cut": [bool(sim_king_down[learner]), bool(sim_king_down[1 - learner])],
        "unreproduced_real_kill": bool(unreproduced),
        "unreproduced_real_kill_owner": ["own" if pid == learner else "opponent" for pid in unreproduced],
        "counters": {key: (round(value, 4) if isinstance(value, float) else int(value)) for key, value in counters.items()},
        "info": dict(match.info),
    }
    if clamp is not None:
        summary.update(clamp.summary())
    simulation = SIMULATION if clamp is None else SIMULATION + "; " + TOWER_CLAMP_RULE
    provenance = json.dumps({
        "role": "training", "provenance": PROVENANCE, "teacher": LABEL_SOURCE, "source": "VanguardX101/IL_Replay",
        "match_id": match.match_id, "side": summary["side"], "seat": learner, "complete_game": False,
        "sampling": "every-five-tick-opportunity", "terminal_context_rows": int(terminal_row),
        "simulation": simulation, "cut_reason": cut_reason, "cut_tick": int(battle.tick),
    }, sort_keys=True)
    metadata = CorpusMetadata(
        schema_version=CORPUS_SCHEMA_VERSION, created_at=datetime.fromtimestamp(0, timezone.utc).isoformat(),
        seed=0, decisions=int(valid.sum()), samples=count, decision_interval=DECISION_INTERVAL_TICKS,
        max_ticks=config.max_ticks, planner_depth=0, planner_simulations=0, planner_action_samples=0,
        max_entities=builder.max_entities, token_names=builder.token_names, reward_profile=OBJECTIVE_V1,
        label_source=LABEL_SOURCE, label_strategy="recorded-human", public_contract_version=CONTRACT_VERSION,
        public_history_slots=4, public_seen_card_slots=8, provenance=provenance,
    )
    decoded = [action_space.decode_action(int(action), learner).position for action in labels]
    execution = {
        "submitted_ticks": np.asarray(ticks, dtype=np.int64),
        "recorded_play_ticks": np.asarray(play_ticks, dtype=np.int64),
        "recorded_world_positions": np.asarray(play_positions, dtype=np.float32).reshape(count, 2),
        "submitted_world_positions": np.asarray(
            [[position.x, position.y] if position is not None else [np.nan, np.nan] for position in decoded],
            dtype=np.float32),
        "recorded_outcome": np.full(count, match.results[learner], dtype=np.int8),
        "label_projection_distance": np.asarray(projections, dtype=np.float32),
        "recorded_millitiles": np.asarray(millitiles, dtype=np.int32).reshape(count, 2),
    }
    if clamp is not None:
        execution["tower_clamped"] = np.asarray([r[0] for r in clamp_rows], dtype=np.bool_)
        execution["overshoot_frac"] = np.asarray([r[1] for r in clamp_rows], dtype=np.float32)
    result = HumanReplayDemonstration(public, controls, metadata, execution, summary)
    result.imitation_arrays()
    return result


# --------------------------------------------------------------------------
# Compact v5 shards (P16 layout + Champion-button flag), byte-deterministic.
# --------------------------------------------------------------------------

_EXECUTION_FIELDS_V5 = dict(_EXECUTION_FIELDS) | {"recorded_millitiles": np.int32}


def compact_demonstration_v5(demonstration: HumanReplayDemonstration) -> dict[str, np.ndarray]:
    """Drop padding and derivable fields after proving they are derivable."""
    arrays = demonstration.imitation_arrays()
    mask = arrays["entity_mask"]
    counts = mask.sum(axis=1)
    if np.any(mask[:, 1:] & ~mask[:, :-1]):
        raise ValueError("entity rows are not packed")
    known = mask.astype(np.float32)
    allowed = np.zeros(ENTITY_FEATURE_SIZE, dtype=np.float32)
    allowed[_ENTITY_COLUMNS] = 1.0
    button = arrays["global_feature_confidence"][:, CHAMPION_COOLDOWN_GLOBAL] > 0.0
    _require_equal("entity_id_confidence", arrays["entity_id_confidence"], known)
    _require_equal("entity_feature_confidence", arrays["entity_feature_confidence"], known[..., None] * allowed)
    _require_equal("hand_id_confidence", arrays["hand_id_confidence"], np.ones(arrays["hand_ids"].shape, np.float32))
    _require_equal("global_feature_confidence", arrays["global_feature_confidence"],
                   global_confidence_v5(len(counts), button))
    _require_equal("entity_level_confidence", arrays["entity_level_confidence"], (arrays["entity_levels"] > 0).astype(np.float32))
    _require_equal("hand_level_confidence", arrays["hand_level_confidence"], (arrays["hand_levels"] > 0).astype(np.float32))
    _require_equal("previous_rewards", arrays["previous_rewards"], np.zeros(len(counts), np.float32))
    dropped = np.delete(arrays["entity_features"], _ENTITY_COLUMNS, axis=-1)
    if np.any(dropped != 0) or np.any(arrays["entity_features"][~mask] != 0) or np.any(arrays["entity_ids"][~mask] != 0):
        raise ValueError("entity padding or projected-out features are not zero")
    compact = {name: arrays[name].astype(dtype) for name, dtype in _ROW_FIELDS.items()}
    for name, dtype in _ROW_FIELDS.items():
        _require_equal(name, compact[name].astype(arrays[name].dtype), arrays[name])
    compact.update({name: demonstration.execution[name].astype(dtype) for name, dtype in _EXECUTION_FIELDS_V5.items()})
    for name in ("tower_clamped", "overshoot_frac"):
        if name in demonstration.execution:
            compact[name] = demonstration.execution[name]
    compact["champion_button"] = button
    compact["entity_counts"] = counts.astype(np.int16)
    compact["flat_entity_ids"] = arrays["entity_ids"][mask].astype(np.int16)
    compact["flat_entity_levels"] = arrays["entity_levels"][mask].astype(np.int8)
    compact["flat_entity_features"] = arrays["entity_features"][mask][:, _ENTITY_COLUMNS]
    compact["action_masks"] = arrays["action_masks"]
    return compact


def save_npz_deterministic(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    """``np.savez_compressed`` layout with fixed zip timestamps and member order."""
    temporary = path.with_name(path.name + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.lib.format.write_array(buffer, np.asanyarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, buffer.getvalue(), compresslevel=6)
    temporary.replace(path)


class HumanReplayShardWriterV5:
    """Accumulate compacted v5 perspectives and write one deterministic shard."""

    def __init__(self) -> None:
        self._parts: list[dict[str, np.ndarray]] = []
        self._summaries: list[dict[str, Any]] = []
        self._template: CorpusMetadata | None = None
        self.rows = 0

    def __len__(self) -> int:
        return len(self._parts)

    def add(self, demonstration: HumanReplayDemonstration) -> None:
        metadata = demonstration.metadata
        if self._template is None:
            self._template = metadata
        if metadata.token_names != self._template.token_names or metadata.max_entities != self._template.max_entities:
            raise ValueError("shard perspectives disagree on the public contract")
        part = compact_demonstration_v5(demonstration)
        table, index = np.unique(np.packbits(part.pop("action_masks"), axis=1), axis=0, return_inverse=True)
        part["mask_table"] = table
        part["mask_index"] = index.reshape(-1).astype(np.int32)
        rows = len(part["expert_actions"])
        self._summaries.append(demonstration.summary | {"row_offset": self.rows, "rows": rows})
        self._parts.append(part)
        self.rows += rows

    def write(self, path: Path, *, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not self._parts or self._template is None:
            raise ValueError("a shard needs at least one perspective")
        skip = {"mask_table", "mask_index"}
        merged = {name: np.concatenate([part[name] for part in self._parts]) for name in self._parts[0] if name not in skip}
        table, inverse = np.unique(np.concatenate([part["mask_table"] for part in self._parts]), axis=0, return_inverse=True)
        inverse = inverse.reshape(-1)
        offsets = np.cumsum([0] + [len(part["mask_table"]) for part in self._parts])
        merged["mask_table"] = table
        merged["mask_index"] = np.concatenate([
            inverse[offset + part["mask_index"]] for offset, part in zip(offsets, self._parts)]).astype(np.int32)
        if len(np.unique(merged["episode_ids"])) != len(self._parts):
            raise ValueError("shard perspectives need distinct episode ids")
        template = self._template
        header = {
            "schema": SHARD_SCHEMA_V5, "provenance": PROVENANCE, "token_names": list(template.token_names),
            "max_entities": template.max_entities, "decision_interval": template.decision_interval,
            "max_ticks": template.max_ticks, "public_contract_version": CONTRACT_VERSION, "public_history_slots": 4,
            "public_seen_card_slots": 8, "label_source": LABEL_SOURCE, "simulation": SIMULATION, "rows": self.rows,
            "perspectives": self._summaries, "extra": dict(extra or {}),
        }
        if "tower_clamped" in merged:
            header["simulation"] += "; " + TOWER_CLAMP_RULE
        merged["header_json"] = np.asarray(json.dumps(header, sort_keys=True))
        save_npz_deterministic(path, merged)
        return header


@dataclass(frozen=True)
class HumanReplayShardV5:
    header: dict[str, Any]
    compact: dict[str, np.ndarray]

    @property
    def rows(self) -> int:
        return int(self.header["rows"])

    @property
    def entity_offsets(self) -> np.ndarray:
        return np.concatenate([[0], np.cumsum(self.compact["entity_counts"].astype(np.int64))])

    def arrays(self, rows: np.ndarray | slice | None = None, *, entity_width: int | None = None) -> dict[str, np.ndarray]:
        """Expand rows to the scripted-demonstration arrays (plus execution fields)."""
        compact = self.compact
        selected = np.arange(self.rows)[slice(None) if rows is None else rows]
        counts = compact["entity_counts"][selected].astype(np.int64)
        width = int(self.header["max_entities"]) if entity_width is None else int(entity_width)
        if counts.size and counts.max() > width:
            raise ValueError("entity width is smaller than a selected row")
        offsets = self.entity_offsets[selected]
        total = int(counts.sum())
        row_index = np.repeat(np.arange(len(selected)), counts)
        column_index = np.arange(total) - np.repeat(np.cumsum(counts) - counts, counts)
        flat_index = np.repeat(offsets, counts) + column_index
        entity_mask = np.zeros((len(selected), width), dtype=np.bool_)
        entity_mask[row_index, column_index] = True
        entity_ids = np.zeros((len(selected), width), dtype=np.int64)
        entity_ids[row_index, column_index] = compact["flat_entity_ids"][flat_index]
        entity_levels = np.zeros((len(selected), width), dtype=np.int64)
        entity_levels[row_index, column_index] = compact["flat_entity_levels"][flat_index]
        entity_features = np.zeros((len(selected), width, ENTITY_FEATURE_SIZE), dtype=np.float32)
        entity_features[row_index[:, None], column_index[:, None], _ENTITY_COLUMNS[None, :]] = compact["flat_entity_features"][flat_index]
        known = entity_mask.astype(np.float32)
        allowed = np.zeros(ENTITY_FEATURE_SIZE, dtype=np.float32)
        allowed[_ENTITY_COLUMNS] = 1.0
        wide = {"board_rotated": np.int8, "terminal_status": np.int8, "episode_starts": np.bool_,
                "expert_action_supervision_valid": np.bool_, "global_features": np.float32,
                "opponent_history_ages": np.float32, "own_last_play_features": np.float32}
        result = {name: compact[name][selected].astype(wide.get(name, np.int64)) for name in _ROW_FIELDS}
        result.update({name: compact[name][selected] for name in _EXECUTION_FIELDS_V5})
        for name in ("tower_clamped", "overshoot_frac"):
            if name in compact:
                result[name] = compact[name][selected]
        result.update(
            entity_ids=entity_ids, entity_features=entity_features, entity_mask=entity_mask,
            entity_levels=entity_levels, entity_level_confidence=(entity_levels > 0).astype(np.float32),
            entity_id_confidence=known, entity_feature_confidence=known[..., None] * allowed,
            hand_id_confidence=np.ones(result["hand_ids"].shape, dtype=np.float32),
            hand_level_confidence=(result["hand_levels"] > 0).astype(np.float32),
            global_feature_confidence=global_confidence_v5(len(selected), compact["champion_button"][selected]),
            previous_rewards=np.zeros(len(selected), dtype=np.float32),
            action_masks=np.unpackbits(compact["mask_table"][compact["mask_index"][selected]], axis=1,
                                       count=NUM_ACTIONS).astype(np.bool_),
        )
        return result


def load_human_replay_shard_v5(path: Path) -> HumanReplayShardV5:
    with np.load(path, allow_pickle=False) as archive:
        header = json.loads(str(archive["header_json"].item()))
        if header.get("schema") != SHARD_SCHEMA_V5 or header.get("provenance") != PROVENANCE:
            raise ValueError("not a contract-v5 human-replay research shard")
        compact = {name: archive[name] for name in archive.files if name != "header_json"}
    if len(compact["expert_actions"]) != header["rows"]:
        raise ValueError("shard row count does not match its header")
    return HumanReplayShardV5(header, compact)
