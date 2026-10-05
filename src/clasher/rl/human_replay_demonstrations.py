"""Human-replay demonstrations in the scripted-demonstration row format.

Recorded two-sided timed placements (IL_Replay) are replayed open-loop in the
scalar engine: base card forms, level 11, Princess towers. From one player's
seat the public-contract-v4 observation, the public action mask and the human
action are recorded at every five-tick decision step, exactly as
``scripted_demonstrations.collect_public_script_game`` records a scripted
teacher. A perspective stops at the first contradiction with the recording, at
the first replayed own action the public contract would not allow, or at the
recorded end.

Research artifact (strategy amendment 2026-10-01). The observations include
opponent cards outside the admitted 16-card scope, so nothing produced here is
a Tier A admitted pilot input. Collection never runs on import.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from clasher.arena import Position
from clasher.battle import STANDARD_MATCH_TICKS, BattleState

from .action_space import DiscreteTileActionSpace
from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from .deck_pool import apply_ordered_deck_to_player
from .imitation import CORPUS_SCHEMA_VERSION, CorpusMetadata, validate_corpus_levels
from .public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from .public_observation import (
    REAL_PLAY_ENTITY_FEATURE_INDICES,
    REAL_PLAY_GLOBAL_FEATURE_INDICES,
    ConfidenceAwareActorObservation,
    project_council_public_observation,
)
from .public_policy_contract import PublicPolicySequence
from .reward_model import OBJECTIVE_V1
from .selfplay_env import resolve_match_horizon
from .structured_obs import (
    ACTOR_GLOBAL_SIZE,
    ENTITY_FEATURE_SIZE,
    VISIBLE_CARD_SLOTS,
    EntityCapacityError,
    StructuredObservationBuilder,
)

PROVENANCE = "human-prior research artifact; not a Tier A admitted pilot arm"
LABEL_SOURCE = "human-replay"
DECISION_INTERVAL_TICKS = 5
NO_OP_ACTION = NUM_HAND_SLOTS * NUM_TILES
NUM_ACTIONS = NO_OP_ACTION + 2
FORM_SUFFIXES = ("-ev1", "-ev2", "-hero")
# The recorded timeline runs 91 ticks (4.55 s) past the last playable tick:
# 1,584 of 10,766 matches last exactly 184.55 s (regulation, 3,600 ticks) and
# no play in the corpus is closer than 102 ticks to the recorded end. Durations
# are quantized to 0.5 s, so ten more ticks are dropped.
RECORDED_TAIL_TICKS = 91
RECORDED_END_QUANTIZATION_TICKS = 10
OVERTIME_START_TICK = 3600
LANES = ("left", "right")
SHARD_SCHEMA = "clasher.human-replay-shard.v1"
_ENTITY_COLUMNS = np.asarray(sorted(REAL_PLAY_ENTITY_FEATURE_INDICES), dtype=np.int64)
_GLOBAL_ALLOWED = np.zeros(ACTOR_GLOBAL_SIZE, dtype=np.float32)
_GLOBAL_ALLOWED[sorted(REAL_PLAY_GLOBAL_FEATURE_INDICES)] = 1.0


def split_card_form(slug: str) -> tuple[str, str]:
    """Return ``(base_slug, form)`` with form in base/evo/hero."""
    for suffix in FORM_SUFFIXES:
        if slug.endswith(suffix):
            return slug[: -len(suffix)], "hero" if suffix == "-hero" else "evo"
    return slug, "base"


@dataclass(frozen=True)
class RecordedPlay:
    tick: int
    player: int
    card: str
    x_millitiles: int
    y_millitiles: int
    order: int
    form: str = "base"


@dataclass(frozen=True)
class RecordedMatch:
    """One recording with the team as player 0 (bottom) and the opponent as player 1."""

    match_id: str
    decks: tuple[tuple[str, ...], tuple[str, ...]]
    plays: tuple[RecordedPlay, ...]
    ability_events: tuple[tuple[int, int, int], ...]  # (tick, order, player)
    timeline_ticks: int
    results: tuple[int, int]  # recorded +1 win, -1 loss, 0 draw, per player
    crowns: tuple[int, int]
    king_down: tuple[bool, bool]
    # Destroyed Princess towers per player, or None when the King fell (the
    # source then reports every tower as zero). The source lists surviving
    # towers by position, not by lane, so only the count is known.
    princess_down: tuple[int | None, int | None]
    info: Mapping[str, Any] = field(default_factory=dict)

    @property
    def playable_end_tick(self) -> int:
        return self.timeline_ticks - RECORDED_TAIL_TICKS - RECORDED_END_QUANTIZATION_TICKS

    @property
    def went_to_overtime(self) -> bool:
        """Whether play continued past 180 s, which needs level crowns at 180 s."""
        return self.timeline_ticks - RECORDED_TAIL_TICKS > OVERTIME_START_TICK

    def princess_down_allowed(self, player: int, tick: int) -> int:
        """Most Princess towers the player can have lost by ``tick`` in the recording.

        Overtime is sudden death, so a match that reached it had level crowns
        at 180 s: both players had lost ``min(crowns)`` towers until then.
        """
        if self.went_to_overtime and tick <= OVERTIME_START_TICK:
            return min(2, min(self.crowns))
        return 2 if self.princess_down[player] is None else int(self.princess_down[player])

    def king_down_allowed(self, player: int, tick: int) -> bool:
        return self.king_down[player] and not (self.went_to_overtime and tick <= OVERTIME_START_TICK)


def parse_il_replay_record(record: Mapping[str, Any], slug_to_card: Mapping[str, str]) -> RecordedMatch:
    """Build a ``RecordedMatch`` from one IL_Replay payload record."""
    payload = record["payload"]
    battle = payload["battle"]
    sides = ("team", "opponent")
    decks, slugs, levels, towers, king_down, princess_down = [], [], [], [], [], []
    for side in sides:
        players = battle[side]["players"]
        if len(players) != 1:
            raise ValueError("only one-versus-one recordings are supported")
        player = players[0]
        keys = [card["card_key"] for card in player["deck"]]
        names = tuple(slug_to_card[split_card_form(key)[0]] for key in keys)
        if len(names) != 8 or len(set(names)) != 8:
            raise ValueError("a recorded deck needs eight distinct base cards")
        decks.append(names)
        slugs.append(keys)
        levels.append([int(card["level"]) for card in player["deck"]])
        towers.append((player.get("tower_card") or {}).get("card_key"))
        final = player["final_tower_hitpoints"]
        king = (final.get("king") or 0) <= 0
        king_down.append(king)
        princess_down.append(None if king else sum((final.get(key) or 0) <= 0 for key in ("princess_left", "princess_right")))
    plays, abilities = [], []
    for event in payload.get("events") or []:
        player = sides.index(event["side"])
        tick = int(event["replay_tick_20hz"])
        order = int(event["source_index"])
        if event["kind"] == "activate_ability":
            abilities.append((tick, order, player))
            continue
        if event["kind"] != "play_card":
            raise ValueError(f"unknown recorded event kind {event['kind']!r}")
        base, form = split_card_form(event["card_key"])
        world = (event.get("coordinates") or {}).get("native_world_units")
        if not world:
            raise ValueError("a recorded play has no world coordinate")
        plays.append(RecordedPlay(tick, player, slug_to_card[base], int(world["x"]), int(world["y"]), order, form))
    plays.sort(key=lambda play: (play.tick, play.order))
    abilities.sort()
    result = battle["result"]
    if result not in {"victory", "defeat", "draw"}:
        raise ValueError(f"unknown recorded result {result!r}")
    team = {"victory": 1, "defeat": -1, "draw": 0}[result]
    return RecordedMatch(
        match_id=str(record["tag"]),
        decks=(decks[0], decks[1]),
        plays=tuple(plays),
        ability_events=tuple(abilities),
        timeline_ticks=int(round(float(payload["replay"]["duration"]["timeline_seconds"]) * 20)),
        results=(team, -team),
        crowns=(int(battle["team"]["crowns"]), int(battle["opponent"]["crowns"])),
        king_down=(king_down[0], king_down[1]),
        princess_down=(princess_down[0], princess_down[1]),
        info={
            "source_shard": record.get("shard"),
            "battle_type": record.get("battle_type", battle.get("battle_type")),
            "game_mode": record.get("game_mode", battle.get("game_mode")),
            "deck_slugs": slugs,
            "deck_levels": levels,
            "tower_cards": towers,
        },
    )


def initial_cycle_order(deck: Sequence[str], played: Sequence[str]) -> list[str]:
    """First-appearance order of plays, then unplayed cards.

    After a player's fourth play the hand set is fixed by the play history
    alone; before it, an unplayed card may really have been in hand.
    """
    order: list[str] = []
    for name in played:
        if name not in order:
            order.append(name)
    order += [name for name in deck if name not in order]
    return order[:8]


def world_tile(x_millitiles: int, y_millitiles: int) -> tuple[int, int]:
    """Round to the 500-unit placement lattice, then floor to the tile."""
    tile_x = int(round(x_millitiles / 500.0)) // 2
    tile_y = int(round(y_millitiles / 500.0)) // 2
    return min(max(tile_x, 0), BOARD_WIDTH - 1), min(max(tile_y, 0), BOARD_HEIGHT - 1)


class CachedPublicActionMask:
    """Exact memo of ``PublicActionMaskBuilder.build``.

    The key holds every observation value the builder reads: lifecycle, board
    rotation, hand tokens and confidences, per-slot affordability, the two
    enemy Princess flags and every confident building blocker. Mirror is the
    only card whose legality needs more (own play history); it bypasses the memo.
    """

    def __init__(self, builder: StructuredObservationBuilder, *, maximum_entries: int = 20_000) -> None:
        from clasher.card_aliases import resolve_card_name
        from clasher.spells import SPELL_REGISTRY, MirrorSpell

        self.builder = builder
        self.inner = PublicActionMaskBuilder(builder)
        self.maximum_entries = maximum_entries
        self._cache: dict[tuple, np.ndarray] = {}
        self.hits = 0
        self.misses = 0
        definitions = builder.loader.load_card_definitions()
        self._cost = np.full(len(builder.token_names), np.inf, dtype=np.float64)
        self._mirror = np.zeros(len(builder.token_names), dtype=np.bool_)
        for token in range(1, len(builder.token_names)):
            name = builder.card_name_for_token_id(token)
            stats = builder.loader.get_card(name) if name is not None else None
            if stats is None:
                continue
            self._cost[token] = float(getattr(stats, "mana_cost", 0.0) or 0.0)
            self._mirror[token] = isinstance(SPELL_REGISTRY.get(resolve_card_name(name, definitions)), MirrorSpell)

    def build(self, source: ConfidenceAwareActorObservation) -> np.ndarray:
        observation = source.observation
        request = PublicActionMaskInput.from_confidence_observation(source)
        hand = observation.hand_ids[:NUM_HAND_SLOTS]
        if observation.terminal is not False or self._mirror[hand].any():
            return self.inner.build(request)
        confidence = source.global_feature_confidence
        elixir = float(observation.global_features[5]) * 10.0
        blockers = observation.entity_mask & (observation.entity_features[:, 5] > 0.5) & (source.entity_id_confidence > 0.0)
        key = (
            observation.board_rotated,
            hand.tobytes(),
            (source.hand_id_confidence[:NUM_HAND_SLOTS] > 0.0).tobytes(),
            bool(confidence[5] > 0.0),
            (self._cost[hand] > elixir + 1e-6).tobytes(),
            bool(confidence[11] > 0.0 and observation.global_features[11] <= 1e-4),
            bool(confidence[12] > 0.0 and observation.global_features[12] <= 1e-4),
            observation.entity_ids[blockers].tobytes(),
            observation.entity_features[blockers, :2].tobytes(),
        )
        cached = self._cache.get(key)
        if cached is None:
            self.misses += 1
            cached = self.inner.build(request)
            cached.setflags(write=False)
            if len(self._cache) >= self.maximum_entries:
                self._cache.clear()
            self._cache[key] = cached
        else:
            self.hits += 1
        return cached


@dataclass(frozen=True)
class ReconstructionConfig:
    # Largest elixir shortfall repaired at a replayed own play (the scan saw
    # 0.007 to 0.017 at exact ticks); anything larger ends the perspective.
    elixir_topup_tolerance: float = 0.05
    # The public mask blocks a one-tile margin around Crown Towers and buildings
    # that the game itself allows. "adjacent": a recorded own tile outside the
    # mask is labelled as the nearest legal tile of the same card when one lies
    # within one tile (the placement itself still runs at the recorded point);
    # anything farther ends the perspective. "cut": any masked tile ends it.
    masked_tile_policy: str = "adjacent"
    # "cut": an opponent placement the engine rejects ends the perspective.
    opponent_rejection_policy: str = "cut"
    max_ticks: int = resolve_match_horizon(STANDARD_MATCH_TICKS, 4)

    def __post_init__(self) -> None:
        if self.masked_tile_policy not in {"cut", "adjacent"}:
            raise ValueError("unknown masked tile policy")
        if self.opponent_rejection_policy not in {"cut", "continue"}:
            raise ValueError("unknown opponent rejection policy")
        if not 0.0 <= self.elixir_topup_tolerance <= 0.25:
            raise ValueError("elixir top-up tolerance must stay tiny")


@dataclass(frozen=True)
class HumanReplayDemonstration:
    public: PublicPolicySequence
    controls: dict[str, np.ndarray]
    metadata: CorpusMetadata
    execution: dict[str, np.ndarray]
    summary: dict[str, Any]

    def imitation_arrays(self) -> dict[str, np.ndarray]:
        arrays = dict(self.public.arrays) | self.controls
        validate_corpus_levels(arrays, required=True)
        self.public.validate_action_mask(arrays["action_masks"])
        rows = np.arange(len(arrays["expert_actions"]))
        legal = arrays["action_masks"][rows, arrays["expert_actions"]]
        if np.any(arrays["expert_action_supervision_valid"] & ~legal):
            raise ValueError("a supervised human action is outside its public mask")
        return arrays

    def save(self, path: Path) -> None:
        """Publish one perspective in the scripted game-shard layout."""
        arrays = self.imitation_arrays()
        with path.open("xb") as stream:
            np.savez_compressed(stream, metadata_json=np.asarray(self.metadata.to_json()),
                                summary_json=np.asarray(json.dumps(self.summary, sort_keys=True)),
                                **arrays, **self.execution)


def _force_card_into_hand(player, name: str) -> bool:
    """Opponent-side relaxation from the feasibility scan (counted, never silent)."""
    if name in player.hand:
        return False
    if name in player.cycle_queue:
        player.cycle_queue.remove(name)
    for index, slot in enumerate(player.hand):
        if slot is None:
            player.hand[index] = name
            return True
    evicted = player.hand[0]
    player.hand[0] = name
    if evicted is not None:
        player.cycle_queue.appendleft(evicted)
    return True


def _zone_restricted(battle: BattleState, player_id: int, card: str) -> bool:
    """Whether the card may only be placed in the player's own territory."""
    play = battle.resolve_card_play(player_id, card)
    if play is None:
        return False
    _, stats, spell = play
    if spell is not None:
        return bool(battle.arena._requires_deploy_zone_spell(spell))
    return not bool(getattr(stats, "can_deploy_on_enemy_side", False))


def _is_pocket(player_id: int, y: float) -> bool:
    return y >= 15.0 if player_id == 0 else y < 17.0


def _lane(x: float) -> str:
    return "left" if x < 9.0 else "right"


def _towers(battle: BattleState) -> dict[tuple[int, str], bool]:
    return {(pid, slot): getattr(battle.players[pid], f"{slot}_tower_hp") > 0
            for pid in (0, 1) for slot in ("left", "right", "king")}


def proven_down_lanes(match: RecordedMatch, battle: BattleState) -> tuple[frozenset[str], frozenset[str]]:
    """Lanes whose Princess tower the recording proves destroyed, per owner.

    A territory-restricted card placed beyond the river is only legal once the
    defender's tower on that lane has fallen.
    """
    proven: tuple[set[str], set[str]] = (set(), set())
    restricted: dict[tuple[int, str], bool] = {}
    for play in match.plays:
        y = play.y_millitiles / 1000.0
        if not _is_pocket(play.player, y):
            continue
        key = (play.player, play.card)
        if key not in restricted:
            restricted[key] = _zone_restricted(battle, play.player, play.card)
        if restricted[key]:
            proven[1 - play.player].add(_lane(play.x_millitiles / 1000.0))
    return frozenset(proven[0]), frozenset(proven[1])


def nearest_adjacent_legal_action(mask: np.ndarray, action: int) -> tuple[int, float] | None:
    """Nearest legal tile of the same slot within one tile, with its distance.

    Ties prefer staying on the same row, then the lower tile index.
    """
    slot, tile = divmod(int(action), NUM_TILES)
    tile_y, tile_x = divmod(tile, BOARD_WIDTH)
    best: tuple[float, int, int] | None = None
    for dy in (0, -1, 1):
        for dx in (-1, 0, 1):
            x, y = tile_x + dx, tile_y + dy
            if (dx == 0 and dy == 0) or not (0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT):
                continue
            candidate = slot * NUM_TILES + y * BOARD_WIDTH + x
            if not mask[candidate]:
                continue
            key = (float(np.hypot(dx, dy)), int(dy != 0), candidate)
            if best is None or key < best:
                best = key
    return None if best is None else (best[2], best[0])


def _stable_seed(match_id: str, learner: int) -> int:
    return int.from_bytes(hashlib.sha256(f"{match_id}:{learner}".encode()).digest()[:8], "big")


def reconstruct_perspective(
    match: RecordedMatch,
    learner: int,
    builder: StructuredObservationBuilder,
    *,
    mask_builder: CachedPublicActionMask | None = None,
    config: ReconstructionConfig | None = None,
    episode_id: int = 0,
    row_observer=None,
) -> HumanReplayDemonstration:
    """Replay one recording and record the learner seat's decision rows.

    Both players' placements run at their recorded ticks. A learner play is
    labelled on the decision step at or just before its tick. If the card is
    not yet affordable or in hand on that step but the recorded tick lies
    inside the interval, the play moves to the next decision step and runs on
    that step (at most four ticks late). Own plays inside the public mask run
    through the tile action exactly as the pilot environment applies them.
    """
    if learner not in (0, 1):
        raise ValueError("learner seat must be 0 or 1")
    if not builder.canonical_perspective or not builder.canonical_lane_globals:
        raise ValueError("human demonstrations use the canonical council perspective")
    if not builder.public_hand_levels or not builder.public_entity_levels:
        raise ValueError("human demonstrations require hand and entity levels")
    if builder.public_history_slots != 4 or builder.public_seen_card_slots != 8:
        raise ValueError("human demonstrations require four history and eight seen-card slots")
    config = config or ReconstructionConfig()
    mask_builder = mask_builder or CachedPublicActionMask(builder)
    own_deck = match.decks[learner]
    if any(builder.token_id(name, namespace="card_action") <= 1 for name in own_deck):
        raise ValueError("the learner deck is outside the builder vocabulary")
    battle = BattleState(rng=random.Random(_stable_seed(match.match_id, learner)))
    for pid in (0, 1):
        played = [play.card for play in match.plays if play.player == pid]
        order = initial_cycle_order(match.decks[pid], played)
        # First-appearance order would put the first card played in slot 0.
        # Shuffle the four starting slots so slot position carries no label.
        opening = order[:NUM_HAND_SLOTS]
        random.Random(_stable_seed(match.match_id, pid) ^ 0x5EED).shuffle(opening)
        apply_ordered_deck_to_player(battle.players[pid], opening + order[NUM_HAND_SLOTS:])
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    down_lanes = proven_down_lanes(match, battle)
    own_plays = deque(play for play in match.plays if play.player == learner)
    other_events: deque[tuple[int, int, RecordedPlay | None]] = deque(sorted(
        [(play.tick, play.order, play) for play in match.plays if play.player != learner]
        + [(tick, order, None) for tick, order, player in match.ability_events if player != learner],
        key=lambda item: item[:2]))
    own_ability_events = sum(player == learner for _, _, player in match.ability_events)
    end_tick = min(match.playable_end_tick, config.max_ticks)
    learner_state = battle.players[learner]
    counters = {name: 0 for name in (
        "own_plays_labelled", "own_plays_deferred", "own_plays_projected", "own_elixir_topups", "opponent_plays", "opponent_hand_forced",
        "opponent_elixir_topups", "opponent_nudged", "opponent_rejected", "opponent_abilities",
        "opponent_abilities_accepted", "simultaneous_own_plays")}
    counters["own_elixir_topup_total"] = 0.0
    counters["opponent_elixir_topup_total"] = 0.0
    observations: list[ConfidenceAwareActorObservation] = []
    masks: list[np.ndarray] = []
    actions: list[int] = []
    ticks: list[int] = []
    play_ticks: list[int] = []
    play_positions: list[tuple[float, float]] = []
    scheduled: tuple[int, int, RecordedPlay | None] | None = None  # (execution tick, action, projected play)
    cut_reason: str | None = None
    cut_detail: dict[str, Any] = {}
    last_row_valid = True
    tower_state = _towers(battle)
    projection = [0.0]  # distance of the label from the recorded tile, set by label_own_play
    projections: list[float] = []
    first_projected_row: int | None = None

    def observe() -> tuple[ConfidenceAwareActorObservation, np.ndarray]:
        packet = project_council_public_observation(builder.build_actor(battle, learner))
        return packet, mask_builder.build(packet)

    def label_own_play(play: RecordedPlay, tick: int, packet, mask):
        """Return (action or None, packet, mask, cut reason or None)."""
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
            # The public mask offers no tile for this slot: not affordable yet.
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
            if scheduled is None and own_plays and own_plays[0].tick < tick + DECISION_INTERVAL_TICKS:
                play = own_plays[0]
                projection[0] = 0.0
                action, packet, mask, reason = label_own_play(play, tick, packet, mask)
                if reason is not None:
                    cut_reason = reason
                    cut_detail.setdefault("tick", play.tick)
                    break
                if action is not None:
                    own_plays.popleft()
                    label = action
                    scheduled = (max(play.tick, tick), action, play if projection[0] > 0 else None)
                    counters["own_plays_labelled"] += 1
                    if projection[0] > 0:
                        counters["own_plays_projected"] += 1
                        if first_projected_row is None:
                            first_projected_row = len(actions)
                    counters["own_plays_deferred"] += play.tick < tick
                    play_ticks.append(play.tick)
                    play_positions.append((play.x_millitiles / 1000.0, play.y_millitiles / 1000.0))
                    if own_plays and own_plays[0].tick < tick + DECISION_INTERVAL_TICKS:
                        counters["simultaneous_own_plays"] += 1
            if label == NO_OP_ACTION:
                play_ticks.append(-1)
                play_positions.append((np.nan, np.nan))
                projection[0] = 0.0
            projections.append(projection[0])
            observations.append(packet)
            masks.append(mask)
            actions.append(label)
            ticks.append(tick)
            if row_observer is not None:
                row_observer(battle, learner, label)
        if scheduled is not None and scheduled[0] <= tick:
            if scheduled[2] is None:
                accepted = action_space.apply_action(battle, learner, scheduled[1])
            else:
                # Label projected out of the mask's tower margin: the placement
                # itself still runs where the recording put it.
                accepted = battle.deploy_card(learner, scheduled[2].card, Position(
                    scheduled[2].x_millitiles / 1000.0, scheduled[2].y_millitiles / 1000.0))
            scheduled = None
            if not accepted:
                # The public mask allowed it but the engine did not: the row is
                # context only, like a rejected scripted command.
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
            counters["opponent_hand_forced"] += _force_card_into_hand(player, play.card)
            resolved = battle.resolve_card_play(pid, play.card)
            if resolved is not None and player.elixir + 1e-9 < resolved[1].mana_cost:
                counters["opponent_elixir_topups"] += 1
                counters["opponent_elixir_topup_total"] += float(resolved[1].mana_cost) - float(player.elixir)
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
                if pocket:
                    cut_reason = "pocket_play_but_sim_tower_alive"
                elif config.opponent_rejection_policy == "cut":
                    cut_reason = "opponent_placement_rejected"
                if cut_reason is not None:
                    cut_detail.update(tick=play.tick, card=play.card, world=[x, y], side="opponent")
        if cut_reason is not None:
            break
        before = tower_state
        battle.step()
        after = tower_state = _towers(battle)
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
        # Preserve the terminal observation as recurrent context, never a label.
        packet, mask = observe()
        observations.append(packet)
        masks.append(mask)
        actions.append(NO_OP_ACTION)
        ticks.append(battle.tick)
        play_ticks.append(-1)
        play_positions.append((np.nan, np.nan))
        projections.append(0.0)
        terminal_row = True
    count = len(actions)
    if count == 0:
        raise ValueError(f"perspective produced no decision row ({cut_reason})")
    valid = np.ones(count, dtype=np.bool_)
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
    deck_slugs = match.info.get("deck_slugs") or ([], [])
    forms = [[split_card_form(slug)[1] for slug in slugs] for slugs in deck_slugs]
    supervised_plays = int(np.count_nonzero(valid & (labels < NO_OP_ACTION)))
    summary = {
        "match_id": match.match_id,
        "side": ("team", "opponent")[learner],
        "seat": learner,
        "episode_id": episode_id,
        "recorded_result": match.results[learner],
        "recorded_crowns": [match.crowns[learner], match.crowns[1 - learner]],
        "cut_reason": cut_reason,
        "cut_tick": int(battle.tick),
        "cut_detail": cut_detail,
        "playable_end_tick": int(match.playable_end_tick),
        "rows": count,
        "supervised_rows": int(valid.sum()),
        "supervised_plays": supervised_plays,
        "recorded_own_plays": sum(play.player == learner for play in match.plays),
        "terminal_context_row": terminal_row,
        "first_projected_row": first_projected_row,
        "own_deck": list(own_deck),
        "opponent_deck": list(match.decks[1 - learner]),
        "own_forms": forms[learner],
        "opponent_forms": forms[1 - learner],
        "own_ability_events_ignored": own_ability_events,
        "real_princess_down": [match.princess_down[learner], match.princess_down[1 - learner]],
        "sim_princess_down_at_cut": [sim_princess_down[learner], sim_princess_down[1 - learner]],
        "real_king_down": [match.king_down[learner], match.king_down[1 - learner]],
        "counters": {key: (round(value, 4) if isinstance(value, float) else int(value)) for key, value in counters.items()},
        "info": dict(match.info),
    }
    provenance = json.dumps({
        "role": "training", "provenance": PROVENANCE, "teacher": LABEL_SOURCE, "source": "VanguardX101/IL_Replay",
        "match_id": match.match_id, "side": summary["side"], "seat": learner, "complete_game": False,
        "sampling": "every-five-tick-opportunity", "terminal_context_rows": int(terminal_row),
        "simulation": "open-loop scalar re-simulation; base forms; level 11; Princess towers",
        "cut_reason": cut_reason, "cut_tick": int(battle.tick),
    }, sort_keys=True)
    metadata = CorpusMetadata(
        schema_version=CORPUS_SCHEMA_VERSION, created_at=datetime.now(timezone.utc).isoformat(),
        seed=0, decisions=int(valid.sum()), samples=count, decision_interval=DECISION_INTERVAL_TICKS,
        max_ticks=config.max_ticks, planner_depth=0, planner_simulations=0, planner_action_samples=0,
        max_entities=builder.max_entities, token_names=builder.token_names, reward_profile=OBJECTIVE_V1,
        label_source=LABEL_SOURCE, label_strategy="recorded-human", public_contract_version=4,
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
    }
    result = HumanReplayDemonstration(public, controls, metadata, execution, summary)
    result.imitation_arrays()
    return result


# --------------------------------------------------------------------------
# Compact shard storage. ``load_human_replay_shard`` returns the exact arrays
# ``HumanReplayDemonstration.imitation_arrays`` produced, concatenated.
# --------------------------------------------------------------------------

_ROW_FIELDS = {
    "board_rotated": np.int8, "terminal_status": np.int8, "hand_ids": np.int16, "hand_levels": np.int8,
    "global_features": np.float32, "opponent_history_ids": np.int16, "opponent_history_ages": np.float32,
    "opponent_seen_card_ids": np.int16, "own_last_play_ids": np.int16, "own_last_play_features": np.float32,
    "expert_actions": np.int16, "previous_actions": np.int16, "episode_starts": np.bool_,
    "episode_ids": np.int32, "expert_action_supervision_valid": np.bool_,
}
_EXECUTION_FIELDS = {
    "submitted_ticks": np.int32, "recorded_play_ticks": np.int32, "recorded_world_positions": np.float32,
    "submitted_world_positions": np.float32, "recorded_outcome": np.int8,
    "label_projection_distance": np.float32,
}


def _require_equal(name: str, actual: np.ndarray, expected: np.ndarray) -> None:
    if actual.shape != expected.shape or not np.array_equal(actual, expected):
        raise ValueError(f"{name} is not derivable from the compact shard fields")


def compact_demonstration(demonstration: HumanReplayDemonstration) -> dict[str, np.ndarray]:
    """Drop padding and derivable fields after proving they are derivable."""
    arrays = demonstration.imitation_arrays()
    mask = arrays["entity_mask"]
    counts = mask.sum(axis=1)
    if np.any(mask[:, 1:] & ~mask[:, :-1]):
        raise ValueError("entity rows are not packed")
    known = mask.astype(np.float32)
    allowed = np.zeros(ENTITY_FEATURE_SIZE, dtype=np.float32)
    allowed[_ENTITY_COLUMNS] = 1.0
    _require_equal("entity_id_confidence", arrays["entity_id_confidence"], known)
    _require_equal("entity_feature_confidence", arrays["entity_feature_confidence"], known[..., None] * allowed)
    _require_equal("hand_id_confidence", arrays["hand_id_confidence"], np.ones(arrays["hand_ids"].shape, np.float32))
    _require_equal("global_feature_confidence", arrays["global_feature_confidence"],
                   np.broadcast_to(_GLOBAL_ALLOWED, arrays["global_features"].shape))
    _require_equal("entity_level_confidence", arrays["entity_level_confidence"], (arrays["entity_levels"] > 0).astype(np.float32))
    _require_equal("hand_level_confidence", arrays["hand_level_confidence"], (arrays["hand_levels"] > 0).astype(np.float32))
    _require_equal("previous_rewards", arrays["previous_rewards"], np.zeros(len(counts), np.float32))
    dropped = np.delete(arrays["entity_features"], _ENTITY_COLUMNS, axis=-1)
    if np.any(dropped != 0) or np.any(arrays["entity_features"][~mask] != 0) or np.any(arrays["entity_ids"][~mask] != 0):
        raise ValueError("entity padding or projected-out features are not zero")
    compact = {name: arrays[name].astype(dtype) for name, dtype in _ROW_FIELDS.items()}
    for name, dtype in _ROW_FIELDS.items():
        _require_equal(name, compact[name].astype(arrays[name].dtype), arrays[name])
    compact.update({name: demonstration.execution[name].astype(dtype) for name, dtype in _EXECUTION_FIELDS.items()})
    compact["entity_counts"] = counts.astype(np.int16)
    compact["flat_entity_ids"] = arrays["entity_ids"][mask].astype(np.int16)
    compact["flat_entity_levels"] = arrays["entity_levels"][mask].astype(np.int8)
    compact["flat_entity_features"] = arrays["entity_features"][mask][:, _ENTITY_COLUMNS]
    compact["action_masks"] = arrays["action_masks"]
    return compact


class HumanReplayShardWriter:
    """Accumulate compacted perspectives and write one compressed shard."""

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
        part = compact_demonstration(demonstration)
        # Deduplicate masks per perspective so a shard never holds every row's mask.
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
            "schema": SHARD_SCHEMA, "provenance": PROVENANCE, "token_names": list(template.token_names),
            "max_entities": template.max_entities, "decision_interval": template.decision_interval,
            "max_ticks": template.max_ticks, "public_contract_version": 4, "public_history_slots": 4,
            "public_seen_card_slots": 8, "label_source": LABEL_SOURCE, "rows": self.rows,
            "perspectives": self._summaries, "extra": dict(extra or {}),
        }
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("wb") as stream:
            np.savez_compressed(stream, header_json=np.asarray(json.dumps(header, sort_keys=True)), **merged)
        temporary.replace(path)
        return header


def write_human_replay_shard(path: Path, demonstrations: Sequence[HumanReplayDemonstration], *, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Write perspectives as one compressed shard with a shared mask table."""
    writer = HumanReplayShardWriter()
    for demonstration in demonstrations:
        writer.add(demonstration)
    return writer.write(path, extra=extra)


@dataclass(frozen=True)
class HumanReplayShard:
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
        result.update({name: compact[name][selected] for name in _EXECUTION_FIELDS})
        result.update(
            entity_ids=entity_ids, entity_features=entity_features, entity_mask=entity_mask,
            entity_levels=entity_levels, entity_level_confidence=(entity_levels > 0).astype(np.float32),
            entity_id_confidence=known, entity_feature_confidence=known[..., None] * allowed,
            hand_id_confidence=np.ones(result["hand_ids"].shape, dtype=np.float32),
            hand_level_confidence=(result["hand_levels"] > 0).astype(np.float32),
            global_feature_confidence=np.broadcast_to(_GLOBAL_ALLOWED, result["global_features"].shape).copy(),
            previous_rewards=np.zeros(len(selected), dtype=np.float32),
            action_masks=np.unpackbits(compact["mask_table"][compact["mask_index"][selected]], axis=1,
                                       count=NUM_ACTIONS).astype(np.bool_),
        )
        return result


def load_human_replay_shard(path: Path) -> HumanReplayShard:
    with np.load(path, allow_pickle=False) as archive:
        header = json.loads(str(archive["header_json"].item()))
        if header.get("schema") != SHARD_SCHEMA or header.get("provenance") != PROVENANCE:
            raise ValueError("not a human-replay research shard")
        compact = {name: archive[name] for name in archive.files if name != "header_json"}
    if len(compact["expert_actions"]) != header["rows"]:
        raise ValueError("shard row count does not match its header")
    return HumanReplayShard(header, compact)
