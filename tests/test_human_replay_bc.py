"""Human-replay behaviour cloning: weights, streaming recurrence, resumable fit.

Synthetic recordings through the real engine and a tiny model; nothing here is
gameplay evidence.
"""

import json
from dataclasses import replace

import numpy as np
import pytest
import torch

from clasher.rl.council_pilot import build_council_model_config
from clasher.rl.deck_curriculum import pilot_curriculum
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.human_replay_bc import (
    HumanReplayFitConfig,
    _run_streams,
    episode_arrays,
    evaluate_human_replay,
    fit_human_replay,
    selected_tile_rows,
    supervision_weights,
)
from clasher.rl.human_replay_demonstrations import (
    NO_OP_ACTION,
    PROVENANCE,
    RecordedMatch,
    RecordedPlay,
    load_human_replay_shard,
    reconstruct_perspective,
    write_human_replay_shard,
)
from clasher.rl.imitation import _sequence_batch_inputs
from clasher.rl.model import ClasherPolicy
from clasher.rl.structured_obs import StructuredObservationBuilder

HOG = ("HogRider", "Musketeer", "IceGolem", "IceSpirit", "Skeletons", "Cannon", "Fireball", "Log")
PLAYS = [
    (40, 0, "HogRider", 3500, 13500), (100, 0, "Skeletons", 8500, 9500), (232, 0, "Cannon", 8500, 10500),
    (62, 1, "IceGolem", 14500, 20500), (151, 1, "Musketeer", 9500, 26500), (236, 1, "Cannon", 9500, 21500),
]


@pytest.fixture(scope="module")
def setup(tmp_path_factory):
    torch.set_num_threads(1)
    directory = tmp_path_factory.mktemp("human-bc")
    decks = directory / "pilot.json"
    decks.write_text(json.dumps({"decks": [deck for decks in pilot_curriculum().values() for deck in decks]}))
    builder = StructuredObservationBuilder(
        decks_path=decks, max_entities=128, card_semantics_version=4, canonical_perspective=True,
        canonical_lane_globals=True, public_entity_levels=True, public_hand_levels=True,
        public_history_slots=4, public_seen_card_slots=8)
    parts = []
    for part in range(2):
        games = []
        for index in range(3):
            shift = 7 * (3 * part + index)
            plays = tuple(RecordedPlay(tick + shift, player, card, x, y, order)
                          for order, (tick, player, card, x, y) in enumerate(sorted(PLAYS)))
            match = RecordedMatch(
                match_id=f"m{part}{index}", decks=(HOG, HOG), plays=plays, ability_events=(), timeline_ticks=700,
                results=(1, -1), crowns=(0, 0), king_down=(False, False), princess_down=(0, 0), info={})
            game = reconstruct_perspective(match, index % 2, builder, episode_id=10 * part + index)
            game.summary["fit_split"] = int(index == 2)
            games.append(game)
        path = directory / f"shard-{part:03d}-part-00.npz"
        write_human_replay_shard(path, games)
        parts.append(path)
    config = replace(build_council_model_config(builder), d_model=32, num_heads=2, actor_layers=1,
                     critic_layers=1, memory_size=32)
    return builder, parts, config, decks


def test_wait_rows_far_from_plays_are_down_weighted():
    labels = np.full(20, NO_OP_ACTION)
    labels[[9, 15]] = [5, 700]
    valid = np.ones(20, dtype=bool)
    valid[19] = False
    natural = supervision_weights(labels, valid, wait_row_weight=1.0, near_play_rows=4)
    assert natural.tolist() == [1.0] * 19 + [0.0]
    weighted = supervision_weights(labels, valid, wait_row_weight=0.2, near_play_rows=4)
    expected = np.full(20, 0.2, dtype=np.float32)
    expected[5:10] = expected[11:16] = 1.0  # the play and the four steps before it
    expected[19] = 0.0
    assert np.allclose(weighted, expected)


def _batch(shard, summary, device=torch.device("cpu")):
    arrays = episode_arrays(shard, summary)
    rows = len(arrays["expert_actions"])
    inputs = _sequence_batch_inputs(arrays, np.arange(rows)[None, :], device, reset_memory=False)
    return arrays, inputs


def test_skipping_the_tile_decoder_on_wait_rows_keeps_loss_and_gradients(setup):
    builder, parts, config, _ = setup
    torch.manual_seed(3)
    model = ClasherPolicy(config, builder.card_stat_features)
    shard = load_human_replay_shard(parts[0])
    arrays, inputs = _batch(shard, shard.header["perspectives"][0])
    labels = torch.as_tensor(arrays["expert_actions"])
    assert int((labels < NO_OP_ACTION).sum()) == 3
    parameters = list(model.parameters())

    def gradients(select):
        with selected_tile_rows(model) as selector:
            selector.rows = torch.nonzero(labels < NO_OP_ACTION).flatten() if select else None
            output = model(inputs, model.initial_state(1))
            loss = torch.nn.functional.cross_entropy(output.joint_logits[0], labels)
            for parameter in parameters:
                parameter.grad = None
            loss.backward()
        return float(loss.detach()), [None if p.grad is None else p.grad.clone() for p in parameters]

    full_loss, full = gradients(False)
    selected_loss, selected = gradients(True)
    assert selected_loss == pytest.approx(full_loss, abs=1e-6)
    assert sum(g is not None for g in selected) == sum(g is not None for g in full)
    for a, b in zip(full, selected):
        if a is not None:
            assert torch.allclose(a, b, atol=2e-6)
    assert "tile_decoder.attention.in_proj_weight" in model.state_dict()  # the real decoder is restored


def test_streamed_chunks_reproduce_the_full_episode_forward(setup):
    builder, parts, config, _ = setup
    torch.manual_seed(4)
    model = ClasherPolicy(config, builder.card_stat_features).eval()
    shard = load_human_replay_shard(parts[0])
    summary = shard.header["perspectives"][1]
    arrays, inputs = _batch(shard, summary)
    with torch.no_grad():
        reference = model(inputs, model.initial_state(1)).joint_logits[0]
    collected = []

    def step(output, batch, labels, weights):
        collected.append(output.joint_logits[0][weights > 0])

    with torch.no_grad():
        rows = _run_streams(
            model, iter([(summary, arrays)]), streams=2, sequences_per_step=1, sequence_length=32,
            device=torch.device("cpu"), step=step, select_play_rows=False,
            weights_for=lambda summary, arrays: np.ones(len(arrays["expert_actions"]), dtype=np.float32))
    streamed = torch.cat(collected)
    assert rows == len(reference) == len(streamed) and rows % 32 != 0  # includes a padded final chunk
    assert torch.allclose(streamed, reference, atol=1e-4)


def test_fit_is_resumable_and_writes_a_labelled_loadable_checkpoint(setup, tmp_path):
    builder, parts, config, decks = setup
    fit = HumanReplayFitConfig(seed=5, variant="test", sequence_length=32, streams=2, pool_parts=1,
                               wait_row_weight=0.2, near_play_rows=4)
    common = dict(parts=parts, model_config=config, card_stat_features=builder.card_stat_features, config=fit,
                  device=torch.device("cpu"), validation_perspectives=None,
                  checkpoint_metadata={"training_decks_sha256": "0" * 64})
    straight = fit_human_replay(output_checkpoint=tmp_path / "straight.pt", log=lambda record: None, **common)
    assert straight["rows"] == sum(
        summary["rows"] for path in parts for summary in load_human_replay_shard(path).header["perspectives"]
        if summary["fit_split"] == 0)
    assert straight["validation"]["perspectives"] == 2 and straight["validation"]["play_rows"] == 6

    def interrupt(record):
        if record.get("event") == "pool":
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        fit_human_replay(output_checkpoint=tmp_path / "resumed.pt", log=interrupt, **common)
    assert not (tmp_path / "resumed.pt").exists() and (tmp_path / "resumed.pt.state.pt").exists()
    events = []
    fit_human_replay(output_checkpoint=tmp_path / "resumed.pt", log=events.append, **common)
    assert events[0] == {"event": "resumed", "pools_done": 1, "rows": events[0]["rows"]}
    first = torch.load(tmp_path / "straight.pt", weights_only=False)
    second = torch.load(tmp_path / "resumed.pt", weights_only=False)
    for name, tensor in first["model_state_dict"].items():
        assert torch.equal(tensor, second["model_state_dict"][name]), name
    assert first["provenance"] == PROVENANCE and first["args"]["initialization"] == "human_replay_imitation"
    assert first["human_replay_fit"]["critic"].startswith("untrained")
    assert first["human_replay_fit"]["config"]["wait_row_weight"] == 0.2
    # The privileged critic never receives a gradient on this fit path.
    torch.manual_seed(5)
    np.random.seed(5)
    fresh = ClasherPolicy(config, builder.card_stat_features).state_dict()
    changed = [name for name, tensor in first["model_state_dict"].items() if not torch.equal(tensor, fresh[name])]
    assert changed and not any(name.startswith(("critic_encoder.", "value_head.")) for name in changed)
    with pytest.raises(FileExistsError):
        fit_human_replay(output_checkpoint=tmp_path / "straight.pt", log=lambda record: None, **common)
    loaded = load_policy_checkpoint(tmp_path / "straight.pt", device=torch.device("cpu"), decks_path=decks)
    metrics = evaluate_human_replay(loaded.model, parts, keep=lambda summary: summary["fit_split"] == 1,
                                    device=torch.device("cpu"), sequence_length=32, streams=2)
    assert metrics == pytest.approx(straight["validation"], rel=1e-5, abs=1e-6)
    assert 0.0 <= metrics["tile_top1_accuracy"] <= metrics["tile_top5_accuracy"] <= 1.0
