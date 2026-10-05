"""Merge-plan item 7: monitoring-only training alarms."""

import json

import numpy as np

from clasher.rl.common import NUM_TILES
from clasher.rl.council_monitor import (
    AlarmThresholds,
    TrainingAlarmMonitor,
    rollout_play_summary,
)

NO_OP = 4 * NUM_TILES
TOKENS = ("<pad>", "<unknown>", "Archers", "Cannon", "HogRider", "Log", "Zap")
HAND = [2, 3, 4, 5, 6]  # four playable slots plus visible next card


def _rollout(slot_plays, waits, sequences=4):
    """Actions ``[sequences, steps]`` with the given slot plays then waits."""
    row = [slot * NUM_TILES + 100 for slot in slot_plays] + [NO_OP] * waits
    actions = np.asarray([row] * sequences, dtype=np.int64)
    hand_ids = np.broadcast_to(np.asarray(HAND), (*actions.shape, 5)).copy()
    return actions, hand_ids


STATS = {
    "mode_entropy": 0.2,
    "conditional_slot_entropy": 1.0,
    "location_entropy": 3.0,
    "action_type_entropy": 0.5,
    "approx_kl": 0.001,
    "kl_early_stop": 0.0,
    "critic_warmup": 0.0,
}


def _monitor(tmp_path, **limits):
    thresholds = AlarmThresholds(
        window_updates=3,
        min_plays_for_card_alarms=20,
        min_held_placements_for_starvation=20,
        min_episodes_for_match_alarms=2,
        min_script_games=4,
        **limits,
    )
    return TrainingAlarmMonitor(
        output_dir=tmp_path / "run",
        token_names=TOKENS,
        outcome_dir=tmp_path / "opponents",
        thresholds=thresholds,
    )


def _alarms(monitor):
    if not monitor.alarms_path.exists():
        return []
    return [json.loads(line) for line in monitor.alarms_path.read_text().splitlines()]


def test_play_summary_maps_slots_to_held_cards():
    actions, hands = _rollout([0, 0, 1, 3], waits=4, sequences=1)
    summary = rollout_play_summary(actions, hands, TOKENS)
    assert summary["plays"] == 4 and summary["waits"] == 4
    assert summary["card_plays"] == {"Archers": 2, "Cannon": 1, "Log": 1}
    # Every placement had all four cards in hand; next card (Zap) is never held.
    assert summary["held_placements"] == {"Archers": 4, "Cannon": 4, "HogRider": 4, "Log": 4}


def test_card_collapse_and_starved_card_raise_once_and_clear(tmp_path, capsys):
    monitor = _monitor(tmp_path)
    before = dict(STATS)
    actions, hands = _rollout([0] * 9 + [1, 2, 3], waits=20)
    for update in (1, 2, 3):
        monitor.observe_update(update=update, learner_decisions=update * 128,
                               actions=actions, hand_ids=hands,
                               episodes_finished=1, stats=STATS)
    assert STATS == before  # monitoring never edits trainer statistics
    alarms = _alarms(monitor)
    raised = [item["alarm"] for item in alarms if item["event"] == "raised"]
    assert raised.count("card_share_collapse") == 1  # edge-triggered, not spammed
    collapse = next(item for item in alarms if item["alarm"] == "card_share_collapse")
    assert collapse["detail"]["card"] == "Archers" and collapse["detail"]["share"] == 0.75
    assert "monitoring only" in collapse["action_taken"]
    assert "TRAINING_ALARM" in capsys.readouterr().out
    assert "card_share_collapse" in monitor.active_alarms
    # A starved card: HogRider (slot 2) never chosen while held.
    starve = _monitor(tmp_path / "starve")
    actions, hands = _rollout([0, 1, 3] * 4, waits=20)
    for update in (1, 2, 3):
        starve.observe_update(update=update, learner_decisions=update, actions=actions,
                              hand_ids=hands, episodes_finished=1, stats=STATS)
    starved = next(item for item in _alarms(starve) if item["alarm"] == "starved_card")
    assert starved["detail"]["cards"] == ["HogRider"]
    # Balanced play clears the collapse alarm after the window rolls over.
    balanced, hands = _rollout([0, 1, 2, 3] * 3, waits=20)
    for update in (4, 5, 6):
        monitor.observe_update(update=update, learner_decisions=update * 128,
                               actions=balanced, hand_ids=hands,
                               episodes_finished=1, stats=STATS)
    cleared = [item for item in _alarms(monitor) if item["event"] == "cleared"]
    assert any(item["alarm"] == "card_share_collapse" for item in cleared)
    assert "card_share_collapse" not in monitor.active_alarms
    rows = [json.loads(line) for line in monitor.metrics_path.read_text().splitlines()]
    assert len(rows) == 6
    assert rows[-1]["plays_per_match"] == 48.0 and rows[-1]["waits_per_match"] == 80.0
    assert set(rows[-1]["entropy"]) == {"mode", "card", "location", "action_type"}


def test_plays_per_match_band(tmp_path):
    monitor = _monitor(tmp_path)
    actions, hands = _rollout([0], waits=60)
    for update in (1, 2):
        monitor.observe_update(update=update, learner_decisions=update, actions=actions,
                               hand_ids=hands, episodes_finished=1, stats=STATS)
    low = next(item for item in _alarms(monitor) if item["alarm"] == "plays_per_match_low")
    assert low["detail"]["plays_per_match"] == 4.0
    spam = _monitor(tmp_path / "spam")
    actions, hands = _rollout([0, 1, 2, 3] * 30, waits=0)
    for update in (1, 2):
        spam.observe_update(update=update, learner_decisions=update, actions=actions,
                            hand_ids=hands, episodes_finished=1, stats=STATS)
    assert any(item["alarm"] == "plays_per_match_high" for item in _alarms(spam))


def test_per_factor_entropy_collapse_is_relative_to_first_window(tmp_path):
    monitor = _monitor(tmp_path)
    actions, hands = _rollout([0, 1, 2, 3] * 3, waits=20)
    for update in (1, 2, 3):
        monitor.observe_update(update=update, learner_decisions=update, actions=actions,
                               hand_ids=hands, episodes_finished=1, stats=STATS)
    assert not any(item["alarm"].startswith("entropy") for item in _alarms(monitor))
    collapsed = STATS | {"location_entropy": 0.1}
    for update in (4, 5, 6):
        monitor.observe_update(update=update, learner_decisions=update, actions=actions,
                               hand_ids=hands, episodes_finished=1, stats=collapsed)
    names = {item["alarm"] for item in _alarms(monitor)}
    assert "entropy_collapse_location" in names
    assert "entropy_collapse_mode" not in names and "entropy_collapse_card" not in names


def test_script_score_at_checkpoints_uses_only_fixed_script_matches(tmp_path):
    monitor = _monitor(tmp_path)
    outcomes = tmp_path / "opponents" / "worker-0-outcomes.jsonl"
    outcomes.parent.mkdir(parents=True)

    def write(results, kind="script", style="balanced"):
        with outcomes.open("a") as stream:
            for result in results:
                stream.write(json.dumps({"kind": kind, "style": style,
                                         "learner_result": result}) + "\n")

    write(["win"] * 6 + ["loss"] * 2)
    write(["loss"] * 5, kind="historical", style=None)  # never counted as script
    monitor.observe_checkpoint(update=200, learner_decisions=102400, checkpoint="a.pt")
    write(["win"] * 2 + ["loss"] * 6, style="pressure")
    events = monitor.observe_checkpoint(update=400, learner_decisions=204800,
                                        checkpoint="b.pt")
    assert [item["alarm"] for item in events] == ["script_score_drop"]
    assert events[0]["detail"]["best_previous_script_score"] == 0.75
    rows = [json.loads(line) for line in monitor.metrics_path.read_text().splitlines()]
    first, second = rows
    assert first["script_games"] == 8 and first["script_score"] == 0.75
    assert first["score_by_opponent_kind"]["historical"] == {"games": 5, "score": 0.0}
    assert second["script_score_by_style"] == {"pressure": {"games": 8, "score": 0.25}}


# --- v7r2 instrumentation (pilot/diagnosis-1M) --------------------------------

COSTS = {"Archers": 3, "Cannon": 3, "HogRider": 4, "Log": 2, "Zap": 2}


def _masks(actions, playable_rows=None):
    """Masks where every decision has a legal play unless rows are restricted."""
    masks = np.zeros((*actions.shape, NO_OP + 2), dtype=bool)
    masks[..., NO_OP] = True
    rows = range(actions.shape[0]) if playable_rows is None else playable_rows
    for row in rows:
        masks[row, :, :NO_OP] = True
    return masks


def _write_outcomes(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        for record in records:
            stream.write(json.dumps(record) + "\n")


def test_wait_probability_cost_tiers_and_opponent_split_are_logged(tmp_path):
    from clasher.rl.council_monitor import initial_opponent_labels

    pool = tmp_path / "pool.json"
    pool.write_text(json.dumps({"initial": [
        {"path": "/x/initialization/scripted.pt", "sha256": "a" * 64},
        {"path": "/x/initialization/scripted-random-control.pt", "sha256": "b" * 64},
    ]}))
    labels = initial_opponent_labels(pool)
    assert labels == {"a" * 64: "warm_start", "b" * 64: "random_control"}
    monitor = TrainingAlarmMonitor(
        output_dir=tmp_path / "run", token_names=TOKENS,
        outcome_dir=tmp_path / "opponents", card_costs=COSTS, opponent_labels=labels,
        thresholds=AlarmThresholds(window_updates=3, wait_window_updates=2,
                                   min_playable_decisions_for_wait_alarm=10),
    )
    _write_outcomes(tmp_path / "opponents" / "worker-0-outcomes.jsonl", [
        {"kind": "script", "style": "balanced", "learner_result": "win"},
        {"kind": "script", "style": "pressure", "learner_result": "loss"},
        {"kind": "initial", "checkpoint_sha256": "b" * 64, "learner_result": "win"},
        {"kind": "initial", "checkpoint_sha256": "a" * 64, "learner_result": "draw"},
    ])
    # Slots 0,0,1,3 = Archers x2, Cannon, Log; 4 waits. Row 1 has no legal play.
    actions, hands = _rollout([0, 0, 1, 3], waits=4, sequences=2)
    monitor.observe_update(update=1, learner_decisions=16, actions=actions,
                           hand_ids=hands, episodes_finished=1, stats=STATS,
                           action_masks=_masks(actions, playable_rows=[0]))
    row = json.loads(monitor.metrics_path.read_text().splitlines()[-1])
    assert row["playable_decisions"] == 8 and row["wait_probability"] == 0.5
    tiers = row["update_play_when_held_by_cost"]
    # Each of the 8 placements held Archers, Cannon, HogRider and Log.
    assert tiers["2"] == {"plays": 2, "held": 8, "rate": 0.25}  # Log
    assert tiers["3"] == {"plays": 6, "held": 16, "rate": 0.375}  # Archers + Cannon
    assert tiers["4"] == {"plays": 0, "held": 8, "rate": 0.0}  # HogRider
    split = row["training_results_by_opponent"]
    assert split["script"] == {"games": 2, "wins": 1, "losses": 1, "draws": 0, "win_rate": 0.5}
    assert split["script:balanced"]["wins"] == 1
    assert split["initial:random_control"]["win_rate"] == 1.0
    assert split["initial:warm_start"]["draws"] == 1
    assert split["all"]["games"] == 4
    # The same records still reach the checkpoint score exactly once.
    monitor.observe_checkpoint(update=1, learner_decisions=16, checkpoint="a.pt")
    checkpoint_row = json.loads(monitor.metrics_path.read_text().splitlines()[-1])
    assert checkpoint_row["script_games"] == 2


def test_wait_probability_alarm_is_monitoring_only(tmp_path):
    monitor = TrainingAlarmMonitor(
        output_dir=tmp_path / "run", token_names=TOKENS,
        thresholds=AlarmThresholds(wait_window_updates=2,
                                   min_playable_decisions_for_wait_alarm=10),
    )
    patient, hands = _rollout([0], waits=9)  # 9 of 10 playable decisions wait
    spam, _ = _rollout([0, 1, 2, 3, 0, 1, 2, 3, 0], waits=1)  # 1 of 10
    for update, actions in enumerate((patient, spam, spam), start=1):
        monitor.observe_update(update=update, learner_decisions=update, actions=actions,
                               hand_ids=hands, episodes_finished=1, stats=STATS,
                               action_masks=_masks(actions))
    raised = [item for item in _alarms(monitor) if item["alarm"] == "wait_probability_low"]
    assert len(raised) == 1 and raised[0]["update"] == 3  # window (spam, spam) = 0.1
    assert raised[0]["detail"]["window_wait_probability"] == 0.1
    assert "monitoring only" in raised[0]["action_taken"]
    rows = [json.loads(line) for line in monitor.metrics_path.read_text().splitlines()]
    assert [row["window_wait_probability"] for row in rows] == [0.9, 0.5, 0.1]


def test_script_win_rate_falling_alarm_against_first_window(tmp_path):
    monitor = TrainingAlarmMonitor(
        output_dir=tmp_path / "run", token_names=TOKENS, outcome_dir=tmp_path / "opponents",
        thresholds=AlarmThresholds(window_updates=2, min_window_script_games=8),
    )
    outcomes = tmp_path / "opponents" / "worker-env000-outcomes.jsonl"
    actions, hands = _rollout([0, 1, 2, 3], waits=4)

    def update(number, wins, losses):
        _write_outcomes(outcomes, [{"kind": "script", "style": "defense", "learner_result": r}
                                   for r in ["win"] * wins + ["loss"] * losses])
        _write_outcomes(outcomes, [{"kind": "initial", "learner_result": "win"}] * 3)
        monitor.observe_update(update=number, learner_decisions=number, actions=actions,
                               hand_ids=hands, episodes_finished=1, stats=STATS)

    update(1, 2, 2)
    update(2, 2, 2)  # first full window: 4/8 = 0.5 -> baseline
    update(3, 2, 2)
    assert not any(item["alarm"] == "script_win_rate_falling" for item in _alarms(monitor))
    update(4, 0, 4)  # window (3, 4): 2/8 = 0.25 < 0.5 - 0.05
    update(5, 0, 4)
    events = [item for item in _alarms(monitor) if item["alarm"] == "script_win_rate_falling"]
    assert [item["event"] for item in events] == ["raised"] and events[0]["update"] == 4
    assert events[0]["detail"]["baseline_script_win_rate"] == 0.5
    row = json.loads(monitor.metrics_path.read_text().splitlines()[-1])
    assert row["script_win_rate_baseline"] == 0.5
    assert row["window_training_results_by_opponent"]["script"]["win_rate"] == 0.0


def test_resumed_monitor_keeps_baselines_and_skips_pre_resume_outcomes(tmp_path):
    outcomes = tmp_path / "opponents" / "worker-0-outcomes.jsonl"
    first = TrainingAlarmMonitor(
        output_dir=tmp_path / "run", token_names=TOKENS, outcome_dir=tmp_path / "opponents",
        thresholds=AlarmThresholds(window_updates=1, min_window_script_games=2),
    )
    actions, hands = _rollout([0, 1, 2, 3], waits=4)
    _write_outcomes(outcomes, [{"kind": "script", "style": "balanced", "learner_result": "win"}] * 2)
    first.observe_update(update=1, learner_decisions=1, actions=actions, hand_ids=hands,
                         episodes_finished=1, stats=STATS)
    # Games played after the last checkpoint by the interrupted process.
    _write_outcomes(outcomes, [{"kind": "script", "style": "balanced", "learner_result": "loss"}] * 5)
    resumed = TrainingAlarmMonitor(
        output_dir=tmp_path / "run", token_names=TOKENS, outcome_dir=tmp_path / "opponents",
        thresholds=AlarmThresholds(window_updates=1, min_window_script_games=2),
        resume=True, segment_start_update=2,
    )
    _write_outcomes(outcomes, [{"kind": "script", "style": "balanced", "learner_result": "win"}] * 2)
    resumed.observe_update(update=2, learner_decisions=2, actions=actions, hand_ids=hands,
                           episodes_finished=1, stats=STATS)
    row = json.loads(resumed.metrics_path.read_text().splitlines()[-1])
    assert row["training_results_by_opponent"]["script"]["games"] == 2
    assert row["script_win_rate_baseline"] == 1.0
    assert row["entropy_baseline"] == json.loads(
        first.metrics_path.read_text().splitlines()[0])["entropy_baseline"]
    assert row["segment_start_update"] == 2
