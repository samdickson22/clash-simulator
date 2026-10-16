"""Monitoring-only training alarms for the council pilot (merge-plan item 7).

The monitor reads finished rollouts, PPO statistics and the per-match opponent
outcome logs. It writes one metrics row per update to ``training-monitor.jsonl``,
alarm raise/clear transitions to ``training-alarms.jsonl`` and prints
``TRAINING_ALARM`` lines into the training log. It never changes a
hyperparameter, sampling schedule or checkpoint and never stops training;
rollback remains a manual, recorded decision.

Thresholds are fixed monitoring constants, not recipe values:

* card-share collapse: one card takes more than 60% of the learner's plays
  over the window (a 16-card pool played by deck-varied policies should sit far
  below that);
* starved card: a card that was in the learner's hand when it placed a card
  gets under 2% of those placements (uniform choice among four held cards is
  25%), i.e. it is carried but essentially never chosen;
* plays per match outside 10..100 (passive or spamming collapse; elixir alone
  caps a regulation match near 40-60 average-cost plays);
* per-factor entropy (mode, card slot, location) falling below half of its
  first complete window; values are logged every update regardless;
* score against the fixed public scripts in training matches between
  checkpoints dropping more than 0.15 below the best earlier checkpoint interval;
* (v7r2, pilot/diagnosis-1M) training win rate against the fixed scripts over
  the rolling window falling more than 0.05 below its first complete window
  (at least 40 script games in the window);
* (v7r2) wait probability below 0.2 over the last five updates: the policy's
  wait frequency at decisions where a play was legal. Actions are sampled
  on-policy, so this sample mean estimates the mean of pi(wait | s) over those
  states.

Every row also logs, per update and over the window, the wait probability,
play-when-held by elixir-cost tier (plays of the tier's cards divided by the
learner's placements while each was in hand) and training results split by
opponent type (script style, initial warm start / random control, historical,
current).
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .common import NUM_HAND_SLOTS, NUM_TILES

PLACEMENT_ACTIONS = NUM_HAND_SLOTS * NUM_TILES
ENTROPY_FACTORS = {
    "mode": "mode_entropy",
    "card": "conditional_slot_entropy",
    "location": "location_entropy",
    "action_type": "action_type_entropy",
}


@dataclass(frozen=True)
class AlarmThresholds:
    window_updates: int = 20
    max_card_share: float = 0.6
    min_held_card_share: float = 0.02
    min_plays_for_card_alarms: int = 200
    min_held_placements_for_starvation: int = 200
    min_plays_per_match: float = 10.0
    max_plays_per_match: float = 100.0
    min_episodes_for_match_alarms: int = 4
    entropy_drop_fraction: float = 0.5
    entropy_factors: tuple[str, ...] = ("mode", "card", "location")
    script_score_drop: float = 0.15
    min_script_games: int = 20
    min_wait_probability: float = 0.2
    wait_window_updates: int = 5
    min_playable_decisions_for_wait_alarm: int = 200
    script_win_rate_drop: float = 0.05
    min_window_script_games: int = 40


@dataclass
class _UpdateSummary:
    plays: int
    waits: int
    abilities: int
    decisions: int
    episodes: int
    card_plays: dict[str, int]
    held_placements: dict[str, int]
    entropies: dict[str, float]


def rollout_play_summary(
    actions: np.ndarray, hand_ids: np.ndarray, token_names: tuple[str, ...]
) -> dict[str, Any]:
    """Count learner plays, waits and per-card play shares from rollout arrays.

    ``actions`` is ``[sequences, steps]``; ``hand_ids`` is ``[sequences, steps,
    5]`` (four hand slots plus the visible next card, which is never playable).
    """
    actions = np.asarray(actions)
    hand_ids = np.asarray(hand_ids)
    placements = actions < PLACEMENT_ACTIONS
    no_op = PLACEMENT_ACTIONS
    card_plays: dict[str, int] = {}
    held: dict[str, int] = {}
    if np.any(placements):
        slots = actions[placements] // NUM_TILES
        hands = hand_ids[placements][:, :NUM_HAND_SLOTS]
        played = hands[np.arange(len(slots)), slots]
        for token, count in zip(*np.unique(played, return_counts=True)):
            name = token_names[int(token)] if 0 <= int(token) < len(token_names) else "?"
            card_plays[name] = card_plays.get(name, 0) + int(count)
        for row in hands:
            for token in {int(value) for value in row if int(value) > 1}:
                name = token_names[token] if token < len(token_names) else "?"
                held[name] = held.get(name, 0) + 1
    return {
        "plays": int(np.count_nonzero(placements)),
        "waits": int(np.count_nonzero(actions == no_op)),
        "abilities": int(np.count_nonzero(actions == no_op + 1)),
        "decisions": int(actions.size),
        "card_plays": card_plays,
        "held_placements": held,
    }


def read_outcomes(directory: Path, offsets: dict[str, int]) -> list[dict]:
    """Incrementally read ``worker-*-outcomes.jsonl`` records from ``directory``."""
    records: list[dict] = []
    for path in sorted(directory.glob("worker-*-outcomes.jsonl")):
        key = str(path)
        with path.open("rb") as stream:
            stream.seek(offsets.get(key, 0))
            data = stream.read()
        complete = data.rfind(b"\n") + 1
        for line in data[:complete].splitlines():
            if line.strip():
                records.append(json.loads(line))
        offsets[key] = offsets.get(key, 0) + complete
    return records


def initial_opponent_labels(pool_path: Path) -> dict[str, str]:
    """Label the frozen initial policies of an opponent pool by weight digest."""
    pool = json.loads(Path(pool_path).read_text())
    labels: dict[str, str] = {}
    for entry in pool.get("initial", ()):
        name = Path(entry["path"]).name
        labels[entry["sha256"]] = (
            "random_control"
            if "random-control" in name
            else "warm_start"
            if name == "scripted.pt"
            else Path(name).stem
        )
    return labels


def opponent_type(record: dict, labels: dict[str, str] | None = None) -> str:
    kind = str(record.get("kind"))
    if kind == "script":
        return f"script:{record.get('style')}"
    if kind in {"initial", "historical"}:
        label = (labels or {}).get(str(record.get("checkpoint_sha256")))
        return f"{kind}:{label}" if label else kind
    return kind


def results_by_opponent(
    records: list[dict], labels: dict[str, str] | None = None
) -> dict[str, dict]:
    """Learner wins/losses/draws per opponent type, plus ``script`` and ``all``."""
    groups: dict[str, list[dict]] = {"all": list(records)}
    for record in records:
        groups.setdefault(opponent_type(record, labels), []).append(record)
        if record.get("kind") == "script":
            groups.setdefault("script", []).append(record)
    result = {}
    for name, items in sorted(groups.items()):
        wins = sum(item["learner_result"] == "win" for item in items)
        losses = sum(item["learner_result"] == "loss" for item in items)
        result[name] = {
            "games": len(items),
            "wins": wins,
            "losses": losses,
            "draws": len(items) - wins - losses,
            "win_rate": wins / len(items) if items else None,
        }
    return result


def play_when_held_by_cost(
    card_plays: dict[str, int], held: dict[str, int], costs: dict[str, int]
) -> dict[str, dict]:
    """Plays of each cost tier's cards over placements made while they were held."""
    tiers: dict[str, list[int]] = {}
    for name, count in held.items():
        if name not in costs:
            continue
        entry = tiers.setdefault(str(costs[name]), [0, 0])
        entry[0] += card_plays.get(name, 0)
        entry[1] += count
    return {
        tier: {"plays": plays, "held": total, "rate": plays / total if total else None}
        for tier, (plays, total) in sorted(tiers.items(), key=lambda item: int(item[0]))
    }


def wait_counts(actions: np.ndarray, action_masks: np.ndarray) -> tuple[int, int]:
    """(waits, decisions) over decisions where a placement or ability was legal."""
    actions = np.asarray(actions)
    masks = np.asarray(action_masks, dtype=bool)
    playable = np.any(masks[..., :PLACEMENT_ACTIONS], axis=-1)
    if masks.shape[-1] > PLACEMENT_ACTIONS + 1:
        playable |= masks[..., PLACEMENT_ACTIONS + 1]
    waits = int(np.count_nonzero((actions == PLACEMENT_ACTIONS) & playable))
    return waits, int(np.count_nonzero(playable))


def _complete_length(path: Path) -> int:
    data = path.read_bytes()
    return data.rfind(b"\n") + 1


def _score(records: list[dict]) -> float | None:
    if not records:
        return None
    points = {"win": 1.0, "draw": 0.5, "loss": 0.0}
    return sum(points[item["learner_result"]] for item in records) / len(records)


@dataclass
class TrainingAlarmMonitor:
    output_dir: Path
    token_names: tuple[str, ...]
    outcome_dir: Path | None = None
    thresholds: AlarmThresholds = field(default_factory=AlarmThresholds)
    # Elixir cost per token name, for play-when-held by cost tier.
    card_costs: dict[str, int] | None = None
    # Weight digest -> label for initial opponents (see initial_opponent_labels).
    opponent_labels: dict[str, str] | None = None
    # A resumed run: restore first-window baselines from the existing metrics
    # file and skip outcome records written before this process started (they
    # belong to the pre-resume segment, including games after its checkpoint).
    resume: bool = False
    segment_start_update: int = 1

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_path = self.output_dir / "training-monitor.jsonl"
        self.alarms_path = self.output_dir / "training-alarms.jsonl"
        self._window: deque[_UpdateSummary] = deque(
            maxlen=self.thresholds.window_updates
        )
        self._entropy_baseline: dict[str, float] | None = None
        self._active: dict[str, dict] = {}
        self._outcome_offsets: dict[str, int] = {}
        self._pending_outcomes: list[dict] = []
        self._best_script_score: float | None = None
        self._outcome_window: deque[list[dict]] = deque(
            maxlen=self.thresholds.window_updates
        )
        self._wait_window: deque[tuple[int, int]] = deque(
            maxlen=self.thresholds.wait_window_updates
        )
        self._script_baseline: float | None = None
        if self.resume:
            self._restore()

    def _restore(self) -> None:
        if self.metrics_path.exists():
            for line in self.metrics_path.read_text().splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("entropy_baseline") is not None:
                    self._entropy_baseline = dict(row["entropy_baseline"])
                if row.get("script_win_rate_baseline") is not None:
                    self._script_baseline = float(row["script_win_rate_baseline"])
                if (
                    row.get("event") == "checkpoint"
                    and row.get("script_score") is not None
                    and row.get("script_games", 0) >= self.thresholds.min_script_games
                ):
                    self._best_script_score = max(
                        self._best_script_score or 0.0, float(row["script_score"])
                    )
        if self.outcome_dir is not None and Path(self.outcome_dir).exists():
            for path in sorted(Path(self.outcome_dir).glob("worker-*-outcomes.jsonl")):
                self._outcome_offsets[str(path)] = _complete_length(path)

    # -- helpers -----------------------------------------------------------
    def _append(self, path: Path, record: dict) -> None:
        with path.open("a") as stream:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")

    def _transition(
        self, name: str, active: bool, detail: dict, *, update: int, decisions: int
    ) -> dict | None:
        was_active = name in self._active
        if active:
            self._active[name] = detail
        else:
            self._active.pop(name, None)
        if active == was_active:
            return None
        record = {
            "event": "raised" if active else "cleared",
            "alarm": name,
            "update": update,
            "learner_decisions": decisions,
            "detail": detail,
            "action_taken": "none (monitoring only; rollback is manual)",
        }
        self._append(self.alarms_path, record)
        print("TRAINING_ALARM " + json.dumps(record, sort_keys=True), flush=True)
        return record

    @property
    def active_alarms(self) -> tuple[str, ...]:
        return tuple(sorted(self._active))

    # -- per update ----------------------------------------------------------
    def observe_update(
        self,
        *,
        update: int,
        learner_decisions: int,
        actions: np.ndarray,
        hand_ids: np.ndarray,
        episodes_finished: int,
        stats: dict[str, float],
        action_masks: np.ndarray | None = None,
    ) -> list[dict]:
        limits = self.thresholds
        summary = rollout_play_summary(actions, hand_ids, self.token_names)
        new_outcomes = (
            read_outcomes(self.outcome_dir, self._outcome_offsets)
            if self.outcome_dir is not None
            else []
        )
        self._pending_outcomes.extend(new_outcomes)
        self._outcome_window.append(new_outcomes)
        window_outcomes = [item for batch in self._outcome_window for item in batch]
        update_results = results_by_opponent(new_outcomes, self.opponent_labels)
        window_results = results_by_opponent(window_outcomes, self.opponent_labels)
        if action_masks is not None:
            update_waits, update_playable = wait_counts(actions, action_masks)
            self._wait_window.append((update_waits, update_playable))
        else:
            update_waits, update_playable = 0, 0
        window_waits = sum(item[0] for item in self._wait_window)
        window_playable = sum(item[1] for item in self._wait_window)
        wait_probability = update_waits / update_playable if update_playable else None
        window_wait_probability = (
            window_waits / window_playable if window_playable else None
        )
        entropies = {
            factor: float(stats[key])
            for factor, key in ENTROPY_FACTORS.items()
            if key in stats
        }
        self._window.append(
            _UpdateSummary(
                plays=summary["plays"],
                waits=summary["waits"],
                abilities=summary["abilities"],
                decisions=summary["decisions"],
                episodes=int(episodes_finished),
                card_plays=summary["card_plays"],
                held_placements=summary["held_placements"],
                entropies=entropies,
            )
        )
        plays = sum(item.plays for item in self._window)
        waits = sum(item.waits for item in self._window)
        episodes = sum(item.episodes for item in self._window)
        card_plays: dict[str, int] = {}
        held: dict[str, int] = {}
        for item in self._window:
            for name, count in item.card_plays.items():
                card_plays[name] = card_plays.get(name, 0) + count
            for name, count in item.held_placements.items():
                held[name] = held.get(name, 0) + count
        shares = {name: count / plays for name, count in card_plays.items()} if plays else {}
        held_shares = {
            name: card_plays.get(name, 0) / count
            for name, count in held.items()
            if count >= limits.min_held_placements_for_starvation
        }
        window_entropy = {
            factor: float(
                np.mean([item.entropies[factor] for item in self._window if factor in item.entropies])
            )
            for factor in entropies
        }
        full_window = len(self._window) == limits.window_updates
        if full_window and self._entropy_baseline is None:
            self._entropy_baseline = dict(window_entropy)
        plays_per_match = plays / episodes if episodes else None
        waits_per_match = waits / episodes if episodes else None

        events: list[dict] = []

        def emit(name: str, active: bool, detail: dict) -> None:
            record = self._transition(
                name, active, detail, update=update, decisions=learner_decisions
            )
            if record is not None:
                events.append(record)

        card_support = plays >= limits.min_plays_for_card_alarms
        top = max(shares.items(), key=lambda item: item[1]) if shares else (None, 0.0)
        emit(
            "card_share_collapse",
            card_support and top[1] > limits.max_card_share,
            {"card": top[0], "share": top[1], "window_plays": plays,
             "threshold": limits.max_card_share},
        )
        starved = sorted(
            name for name, share in held_shares.items()
            if share < limits.min_held_card_share
        )
        emit(
            "starved_card",
            card_support and bool(starved),
            {"cards": starved,
             "held_play_share": {name: held_shares[name] for name in starved},
             "threshold": limits.min_held_card_share},
        )
        match_support = episodes >= limits.min_episodes_for_match_alarms
        emit(
            "plays_per_match_low",
            match_support and plays_per_match is not None
            and plays_per_match < limits.min_plays_per_match,
            {"plays_per_match": plays_per_match, "episodes": episodes,
             "threshold": limits.min_plays_per_match},
        )
        emit(
            "plays_per_match_high",
            match_support and plays_per_match is not None
            and plays_per_match > limits.max_plays_per_match,
            {"plays_per_match": plays_per_match, "episodes": episodes,
             "threshold": limits.max_plays_per_match},
        )
        emit(
            "wait_probability_low",
            window_playable >= limits.min_playable_decisions_for_wait_alarm
            and window_wait_probability is not None
            and window_wait_probability < limits.min_wait_probability,
            {"window_wait_probability": window_wait_probability,
             "window_playable_decisions": window_playable,
             "window_updates": len(self._wait_window),
             "threshold": limits.min_wait_probability},
        )
        script_window = window_results.get("script", {"games": 0, "win_rate": None})
        script_supported = script_window["games"] >= limits.min_window_script_games
        if full_window and self._script_baseline is None and script_supported:
            self._script_baseline = script_window["win_rate"]
        emit(
            "script_win_rate_falling",
            full_window and script_supported and self._script_baseline is not None
            and script_window["win_rate"]
            < self._script_baseline - limits.script_win_rate_drop,
            {"window_script_win_rate": script_window["win_rate"],
             "window_script_games": script_window["games"],
             "baseline_script_win_rate": self._script_baseline,
             "drop": limits.script_win_rate_drop},
        )
        for factor in limits.entropy_factors:
            baseline = (self._entropy_baseline or {}).get(factor)
            current = window_entropy.get(factor)
            emit(
                f"entropy_collapse_{factor}",
                full_window and baseline is not None and current is not None
                and baseline > 0
                and current < limits.entropy_drop_fraction * baseline,
                {"window_entropy": current, "baseline_entropy": baseline,
                 "fraction": limits.entropy_drop_fraction},
            )

        row = {
            "update": update,
            "learner_decisions": learner_decisions,
            "window_updates": len(self._window),
            "window_plays": plays,
            "window_waits": waits,
            "window_episodes": episodes,
            "plays_per_match": plays_per_match,
            "waits_per_match": waits_per_match,
            "card_share": shares,
            "held_play_share": held_shares,
            "entropy": entropies,
            "window_entropy": window_entropy,
            "entropy_baseline": self._entropy_baseline,
            "critic_warmup": bool(stats.get("critic_warmup", 0.0)),
            "kl_early_stop": bool(stats.get("kl_early_stop", 0.0)),
            "approx_kl": stats.get("approx_kl"),
            "wait_probability": wait_probability,
            "playable_decisions": update_playable,
            "window_wait_probability": window_wait_probability,
            "window_playable_decisions": window_playable,
            "update_play_when_held_by_cost": (
                play_when_held_by_cost(
                    summary["card_plays"], summary["held_placements"], self.card_costs
                )
                if self.card_costs
                else None
            ),
            "play_when_held_by_cost": (
                play_when_held_by_cost(card_plays, held, self.card_costs)
                if self.card_costs
                else None
            ),
            "training_results_by_opponent": update_results,
            "window_training_results_by_opponent": window_results,
            "script_win_rate_baseline": self._script_baseline,
            "segment_start_update": self.segment_start_update,
            "active_alarms": list(self.active_alarms),
        }
        self._append(self.metrics_path, row)
        return events

    # -- per checkpoint --------------------------------------------------------
    def observe_checkpoint(
        self, *, update: int, learner_decisions: int, checkpoint: str
    ) -> list[dict]:
        """Score against fixed scripts in training matches since the last checkpoint."""
        limits = self.thresholds
        if self.outcome_dir is not None:
            self._pending_outcomes.extend(
                read_outcomes(self.outcome_dir, self._outcome_offsets)
            )
        outcomes, self._pending_outcomes = self._pending_outcomes, []
        scripts = [item for item in outcomes if item.get("kind") == "script"]
        by_style: dict[str, list[dict]] = {}
        for item in scripts:
            by_style.setdefault(str(item.get("style")), []).append(item)
        by_kind: dict[str, list[dict]] = {}
        for item in outcomes:
            by_kind.setdefault(str(item.get("kind")), []).append(item)
        score = _score(scripts)
        record = {
            "event": "checkpoint",
            "update": update,
            "learner_decisions": learner_decisions,
            "checkpoint": checkpoint,
            "script_games": len(scripts),
            "script_score": score,
            "script_win_rate": (
                sum(item["learner_result"] == "win" for item in scripts) / len(scripts)
                if scripts else None
            ),
            "script_score_by_style": {
                style: {"games": len(items), "score": _score(items)}
                for style, items in sorted(by_style.items())
            },
            "score_by_opponent_kind": {
                kind: {"games": len(items), "score": _score(items)}
                for kind, items in sorted(by_kind.items())
            },
            "best_previous_script_score": self._best_script_score,
        }
        self._append(self.metrics_path, record)
        events: list[dict] = []
        supported = score is not None and len(scripts) >= limits.min_script_games
        dropped = bool(
            supported
            and self._best_script_score is not None
            and score < self._best_script_score - limits.script_score_drop
        )
        transition = self._transition(
            "script_score_drop",
            dropped,
            {"script_score": score, "script_games": len(scripts),
             "best_previous_script_score": self._best_script_score,
             "threshold": limits.script_score_drop, "checkpoint": checkpoint},
            update=update,
            decisions=learner_decisions,
        )
        if transition is not None:
            events.append(transition)
        if supported:
            self._best_script_score = (
                score if self._best_script_score is None
                else max(self._best_script_score, score)
            )
        return events
