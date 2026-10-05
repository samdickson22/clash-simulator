"""Human-replay reconstruction keeps rows, hands, masks and labels aligned.

Synthetic recordings drive the real scalar engine (no corpus access, nothing
fitted). The row checks mirror ``test_scripted_demo_wait_rows``.
"""

import json

import numpy as np
import pytest

from clasher.battle import BattleState
from clasher.rl.deck_curriculum import pilot_curriculum
from clasher.rl.deck_pool import apply_ordered_deck_to_player
from clasher.rl.human_replay_demonstrations import (
    NO_OP_ACTION,
    PROVENANCE,
    CachedPublicActionMask,
    RecordedMatch,
    RecordedPlay,
    ReconstructionConfig,
    load_human_replay_shard,
    nearest_adjacent_legal_action,
    parse_il_replay_record,
    reconstruct_perspective,
    world_tile,
    write_human_replay_shard,
)
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.structured_obs import StructuredObservationBuilder

HOG = ("HogRider", "Musketeer", "IceGolem", "IceSpirit", "Skeletons", "Cannon", "Fireball", "Log")
TILES = 576


@pytest.fixture(scope="module")
def builder(tmp_path_factory):
    decks = tmp_path_factory.mktemp("decks") / "pilot.json"
    decks.write_text(json.dumps({"decks": [deck for decks in pilot_curriculum().values() for deck in decks]}))
    return StructuredObservationBuilder(
        decks_path=decks, max_entities=128, card_semantics_version=4,
        canonical_perspective=True, canonical_lane_globals=True,
        public_entity_levels=True, public_hand_levels=True,
        public_history_slots=4, public_seen_card_slots=8,
    )


def recording(plays, *, timeline_ticks=900, crowns=(0, 0), princess_down=(0, 0), king_down=(False, False)):
    ordered = tuple(RecordedPlay(tick, player, card, x, y, order)
                    for order, (tick, player, card, x, y) in enumerate(sorted(plays)))
    return RecordedMatch(
        match_id="synthetic", decks=(HOG, HOG), plays=ordered, ability_events=(),
        timeline_ticks=timeline_ticks, results=(1, -1), crowns=crowns, king_down=king_down,
        princess_down=princess_down, info={"deck_slugs": [["hog-rider"] * 8, ["hog-rider-ev1"] * 8]},
    )


# Team (player 0) plays in the bottom half, the opponent (player 1) in the top half.
BASE_PLAYS = [
    (40, 0, "HogRider", 3501, 13499),
    (100, 0, "Skeletons", 8500, 9500),
    (103, 0, "IceSpirit", 9500, 9500),   # same decision interval as the Skeletons
    (232, 0, "Cannon", 8500, 10500),
    (400, 0, "Musketeer", 3500, 8500),   # inside the public mask's tower margin
    (62, 1, "IceGolem", 14500, 20500),
    (151, 1, "Musketeer", 9500, 26500),
    (236, 1, "Cannon", 9500, 21500),
    (402, 1, "HogRider", 14500, 18500),
]


def observed(match, seat, builder, **kwargs):
    hands = []

    def observer(battle, learner, label):
        hand = list(battle.players[learner].hand[:4])
        hands.append([0 if name is None else builder.token_id(name) for name in hand])

    game = reconstruct_perspective(match, seat, builder, row_observer=observer, **kwargs)
    return game, np.asarray(hands)


@pytest.mark.parametrize("seat", [0, 1])
def test_rows_carry_pre_decision_hand_and_labels_hit_recorded_card(builder, seat):
    match = recording(BASE_PLAYS)
    game, hands = observed(match, seat, builder)
    arrays = game.imitation_arrays()
    summary = game.summary
    assert summary["cut_reason"] == "recorded_end" and not summary["terminal_context_row"]
    rows = len(arrays["expert_actions"])
    assert rows == len(hands) == (match.playable_end_tick + 4) // 5
    assert np.array_equal(game.execution["submitted_ticks"], np.arange(rows) * 5)
    labels, valid = arrays["expert_actions"], arrays["expert_action_supervision_valid"]
    assert valid.all() and arrays["episode_starts"].tolist() == [True] + [False] * (rows - 1)
    # Every row stores the hand the decision was made from.
    assert np.array_equal(arrays["hand_ids"][:, :4], hands)
    own = [play for play in match.plays if play.player == seat]
    play_rows = np.flatnonzero(labels < NO_OP_ACTION)
    assert len(play_rows) == len(own) == summary["supervised_plays"]
    for row, play in zip(play_rows, own):
        token = builder.token_id(play.card)
        slot, tile = divmod(int(labels[row]), TILES)
        # The label sits on the decision step at or just before the recorded tick
        # (one step later only for the second play of a shared interval).
        assert row * 5 <= play.tick < row * 5 + 5 or (play.tick < row * 5 and row - 1 in play_rows)
        assert hands[row][slot] == token
        assert token not in hands[row + 1]  # the card left the hand before the next row
        assert arrays["action_masks"][row, labels[row]]
        tile_x, tile_y = world_tile(play.x_millitiles, play.y_millitiles)
        if seat == 1:  # the learner always sees itself at the bottom
            tile_x, tile_y = 17 - tile_x, 31 - tile_y
        projected = game.execution["label_projection_distance"][row]
        if projected == 0:
            assert tile == tile_y * 18 + tile_x
        else:
            assert projected == 1.0 and abs(tile % 18 - tile_x) + abs(tile // 18 - tile_y) == 1
    # A supervised wait never coincides with a card leaving the hand.
    for row in np.flatnonzero(labels[:-1] == NO_OP_ACTION):
        left = [token for token in hands[row] if token and token not in hands[row + 1]]
        assert left == []
    assert np.array_equal(arrays["previous_actions"][1:], labels[:-1])
    assert arrays["previous_actions"][0] == NO_OP_ACTION and not arrays["previous_rewards"].any()
    assert set(np.unique(arrays["board_rotated"])) == {seat}
    assert (game.execution["recorded_outcome"] == (1, -1)[seat]).all()
    assert json.loads(game.metadata.provenance)["provenance"] == PROVENANCE
    assert game.metadata.label_source == "human-replay" and game.metadata.public_contract_version == 4


def test_team_rows_show_margin_projection_and_shared_interval(builder):
    game, _ = observed(recording(BASE_PLAYS), 0, builder)
    counters = game.summary["counters"]
    assert counters["simultaneous_own_plays"] == 1 and counters["own_plays_projected"] == 1
    labels = game.imitation_arrays()["expert_actions"]
    play_rows = np.flatnonzero(labels < NO_OP_ACTION).tolist()
    assert play_rows == [8, 20, 21, 46, 80]
    assert game.summary["first_projected_row"] == 80
    # The strict policy stops at the first recorded tile outside the public mask.
    strict, _ = observed(recording(BASE_PLAYS), 0, builder, config=ReconstructionConfig(masked_tile_policy="cut"))
    assert strict.summary["cut_reason"] == "own_masked_tile" and strict.summary["rows"] == 80
    assert np.array_equal(strict.imitation_arrays()["expert_actions"], labels[:80])


def test_cached_mask_equals_public_mask_builder(builder):
    cached = CachedPublicActionMask(builder)
    direct = PublicActionMaskBuilder(builder)
    game = reconstruct_perspective(recording(BASE_PLAYS), 1, builder, mask_builder=cached)
    arrays = game.imitation_arrays()
    assert cached.hits > cached.misses > 0
    # Rebuild every stored mask from the stored public row alone.
    for row in range(0, len(arrays["expert_actions"]), 3):
        request = PublicActionMaskInput(
            entity_ids=arrays["entity_ids"][row], entity_features=arrays["entity_features"][row],
            entity_mask=arrays["entity_mask"][row], hand_ids=arrays["hand_ids"][row],
            global_features=arrays["global_features"][row],
            entity_id_confidence=arrays["entity_id_confidence"][row],
            hand_id_confidence=arrays["hand_id_confidence"][row],
            global_feature_confidence=arrays["global_feature_confidence"][row],
            terminal=bool(arrays["terminal_status"][row]), board_rotated=bool(arrays["board_rotated"][row]),
        )
        assert np.array_equal(direct.build(request), arrays["action_masks"][row])


def _first_affordable_tick(first_tick, cost):
    battle = BattleState()
    for player in battle.players:
        apply_ordered_deck_to_player(player, list(HOG))
    while battle.tick < first_tick:
        battle.step()
    from clasher.arena import Position

    assert battle.deploy_card(0, "HogRider", Position(3.5, 13.5))
    while battle.players[0].elixir + 1e-9 < cost:
        battle.step()
    return battle.tick


def test_play_made_as_elixir_arrives_moves_to_the_next_decision_step(builder):
    first = next(tick for tick in range(200, 260) if _first_affordable_tick(tick, 4) % 5 in (2, 3))
    arrival = _first_affordable_tick(first, 4)
    match = recording([(first, 0, "HogRider", 3500, 13500), (arrival, 0, "Musketeer", 9500, 9500)])
    game, hands = observed(match, 0, builder)
    labels = game.imitation_arrays()["expert_actions"]
    play_rows = np.flatnonzero(labels < NO_OP_ACTION)
    # Not affordable on the step before the recorded tick, so the label and the
    # placement move to the next step; the row before stays a wait with the card in hand.
    assert play_rows[-1] * 5 == arrival - arrival % 5 + 5
    assert game.summary["counters"]["own_plays_deferred"] == 1
    assert game.summary["counters"]["own_elixir_topups"] == 0
    assert builder.token_id("Musketeer") in hands[play_rows[-1]]


@pytest.mark.parametrize(
    ("plays", "reason", "rows"),
    [
        ([(40, 0, "HogRider", 3500, 13500), (50, 0, "Musketeer", 9500, 9500)], "own_insufficient_elixir", 10),
        ([(40, 0, "HogRider", 3500, 13500), (300, 0, "HogRider", 3500, 13500)], "own_card_not_in_hand", 60),
        ([(40, 0, "HogRider", 3500, 20500)], "pocket_play_but_sim_tower_alive", 8),
        ([(40, 0, "Cannon", 3500, 8500)], "own_masked_tile", 8),
    ],
)
def test_first_illegal_own_action_ends_the_perspective(builder, plays, reason, rows):
    game = reconstruct_perspective(recording(plays), 0, builder)
    assert game.summary["cut_reason"] == reason
    arrays = game.imitation_arrays()
    # The offending step is not recorded; every kept row is a legal supervised label.
    assert len(arrays["expert_actions"]) == rows == game.summary["rows"]
    assert arrays["expert_action_supervision_valid"].all()


def test_opponent_pocket_placement_with_standing_tower_is_a_contradiction(builder):
    game = reconstruct_perspective(recording([(40, 0, "HogRider", 3500, 13500), (80, 1, "Musketeer", 3500, 12500)]), 0, builder)
    assert game.summary["cut_reason"] == "pocket_play_but_sim_tower_alive"
    assert game.summary["rows"] == 17 and game.summary["cut_detail"]["side"] == "opponent"


def test_recorded_tower_bounds_respect_overtime_and_king_reports():
    regulation = recording([], timeline_ticks=3691, crowns=(1, 0), princess_down=(0, 1))
    assert not regulation.went_to_overtime and regulation.playable_end_tick == 3590
    assert regulation.princess_down_allowed(1, 1000) == 1 and regulation.princess_down_allowed(0, 1000) == 0
    overtime = recording([], timeline_ticks=4691, crowns=(1, 0), princess_down=(0, 1))
    # Sudden death: crowns were level at 180 s, so no tower fell before it.
    assert overtime.went_to_overtime
    assert overtime.princess_down_allowed(1, 3600) == 0 and overtime.princess_down_allowed(1, 3601) == 1
    three = recording([], timeline_ticks=4691, crowns=(3, 1), princess_down=(1, None), king_down=(False, True))
    assert three.princess_down_allowed(1, 3000) == 1 and three.princess_down_allowed(1, 4000) == 2
    assert not three.king_down_allowed(1, 3600) and three.king_down_allowed(1, 3601)


def test_lattice_tile_and_adjacent_projection():
    assert world_tile(9501, 25499) == (9, 25) and world_tile(7000, 21000) == (7, 21)
    assert world_tile(8999, 1) == (9, 0) and world_tile(18000, 32000) == (17, 31)
    mask = np.zeros(4 * TILES + 2, dtype=bool)
    action = 2 * TILES + 5 * 18 + 5
    assert nearest_adjacent_legal_action(mask, action) is None
    mask[2 * TILES + 4 * 18 + 5] = mask[2 * TILES + 5 * 18 + 6] = mask[1 * TILES + 5 * 18 + 4] = True
    assert nearest_adjacent_legal_action(mask, action) == (2 * TILES + 5 * 18 + 6, 1.0)  # same row first
    mask[2 * TILES + 5 * 18 + 6] = False
    assert nearest_adjacent_legal_action(mask, action) == (2 * TILES + 4 * 18 + 5, 1.0)


def test_parse_il_replay_record_uses_counts_not_lanes():
    deck = [{"card_key": key, "level": 16} for key in
            ("hog-rider", "musketeer-hero", "ice-golem", "ice-spirit", "skeletons", "cannon-ev1", "fireball", "the-log")]
    slug = {"hog-rider": "HogRider", "musketeer": "Musketeer", "ice-golem": "IceGolem", "ice-spirit": "IceSpirit",
            "skeletons": "Skeletons", "cannon": "Cannon", "fireball": "Fireball", "the-log": "Log"}

    def side(crowns, king, left, right):
        return {"crowns": crowns, "players": [{"deck": deck, "tower_card": {"card_key": "tower-princess"},
                "final_tower_hitpoints": {"king": king, "princess_left": left, "princess_right": right}}]}

    def event(kind, who, tick, index, card="cannon-ev1"):
        return {"kind": kind, "side": who, "replay_tick_20hz": tick, "source_index": index, "card_key": card,
                "coordinates": {"native_world_units": {"x": 9501, "y": 9499}}}

    record = {"tag": "abc", "shard": 3, "payload": {
        "battle": {"result": "defeat", "team": side(0, 4000, 1500, 0), "opponent": side(3, 0, 0, 0)},
        "replay": {"duration": {"timeline_seconds": 184.55}},
        "events": [event("play_card", "opponent", 30, 1), event("activate_ability", "team", 20, 0),
                   event("play_card", "team", 30, 2, "the-log")]}}
    match = parse_il_replay_record(record, slug)
    assert match.timeline_ticks == 3691 and match.results == (-1, 1) and match.crowns == (0, 3)
    # One surviving tower is reported first, whatever its lane; a fallen King hides both.
    assert match.princess_down == (1, None) and match.king_down == (False, True)
    assert [(play.tick, play.player, play.card, play.form) for play in match.plays] == [
        (30, 1, "Cannon", "evo"), (30, 0, "Log", "base")]
    assert match.ability_events == ((20, 0, 0),) and match.decks[0] == HOG


def test_compact_shard_round_trip_is_exact(builder, tmp_path):
    games = [reconstruct_perspective(recording(BASE_PLAYS), seat, builder, episode_id=seat) for seat in (0, 1)]
    path = tmp_path / "shard.npz"
    header = write_human_replay_shard(path, games, extra={"source_shard": 0})
    shard = load_human_replay_shard(path)
    assert header["provenance"] == PROVENANCE and shard.rows == sum(game.summary["rows"] for game in games)
    expanded = shard.arrays()
    for name in games[0].imitation_arrays():
        expected = np.concatenate([game.imitation_arrays()[name] for game in games])
        assert expanded[name].dtype == expected.dtype, name
        assert np.array_equal(expanded[name], expected), name
    for name in games[0].execution:
        expected = np.concatenate([game.execution[name] for game in games])
        assert np.array_equal(expanded[name], expected, equal_nan=True), name
    # A row subset trimmed to its own entity width matches the padded rows.
    rows = np.arange(40, 90)
    width = int(expanded["entity_mask"][rows].sum(axis=1).max())
    subset = shard.arrays(rows, entity_width=width)
    assert np.array_equal(subset["entity_features"], expanded["entity_features"][rows, :width])
    assert np.array_equal(subset["action_masks"], expanded["action_masks"][rows])
    assert [item["row_offset"] for item in shard.header["perspectives"]] == [0, games[0].summary["rows"]]
