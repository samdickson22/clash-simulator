"""Tier B frozen-policy adapters with a tiny untrained checkpoint.

The checkpoint has random weights plus one hand-set output bias that prefers
wait (synthetic weights only; no optimizer step, no gameplay fitting). It is
written to tmp and is never evidence about playing strength.
"""

import json
from dataclasses import replace

import numpy as np
import pytest
import torch
from test_readiness_prefix import DECK, NativeDouble

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.parallel_rollout import build_policy_observation_builder
from clasher.rl.public_observation import (
    exact_public_observation,
    project_council_public_observation,
)
from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS
from clasher.rl.readiness_root_bank import DECKS
from clasher.rl.readiness_tier_b import (
    ScalarPreview,
    TierBRootBank,
    TierBRootRequest,
)
from clasher.rl.readiness_tier_b_policy import (
    DEFAULT_DECK_TABLE,
    IncompleteRootBank,
    PolicyActor,
    collect_tier_b_prefix,
    generate_tier_b_root_bank,
    load_frozen_policy,
    probe_slots,
    remap_packet,
    replay_policy_trace,
    sample_scalar_root,
    verify_policy_root_capture,
)
from clasher.rl.structured_obs import StructuredObservationBuilder

SHA0 = "0" * 64


def tiny_checkpoint(directory, *, wait_bias=3.0, seed=0):
    torch.manual_seed(seed)
    decks = directory / "decks.json"
    decks.write_text(
        json.dumps({"decks": [{"name": f"deck{i}", "cards": list(d)} for i, d in enumerate(DECKS)]})
    )
    vocab = sorted(SUPPORTED_CARDS)
    initial = StructuredObservationBuilder(card_vocab=vocab, max_entities=32, card_semantics_version=4)
    config = PolicyConfig(
        num_tokens=initial.spec.num_tokens, max_entities=32, public_contract_version=4,
        public_token_names=initial.token_names, public_observation_confidence=True,
        card_semantics_version=4, canonical_lane_globals=True, public_history_slots=4,
        public_seen_card_slots=8, d_model=16, num_heads=2, actor_layers=1, critic_layers=1,
        memory_size=16,
    )
    builder = build_policy_observation_builder(
        config, decks_path=decks, token_names=initial.token_names, card_vocab=vocab
    )
    model = ClasherPolicy(config, builder.card_stat_features).eval()
    with torch.no_grad():
        head = [m for m in model.action_type_head if isinstance(m, torch.nn.Linear)][-1]
        head.bias[4] += wait_bias
    path = directory / "untrained-tier-b.pt"
    torch.save(
        {"format_version": 2, "model_config": config.to_dict(), "token_names": builder.token_names,
             "model_state_dict": model.state_dict()},
        path,
    )
    return path, decks


@pytest.fixture(scope="module")
def policy(tmp_path_factory):
    torch.set_num_threads(1)
    directory = tmp_path_factory.mktemp("tier-b-policy")
    path, decks = tiny_checkpoint(directory)
    return load_frozen_policy(path, decks_path=decks)


def request(**kw):
    values = {
        "family_id": "tb-native-0",
        "source_episode_id": "tb-native-0-game",
        "root_owner": 0,
        "episode_seed": 7,
        "decks": (DECK, DECK),
        "deck_id": "synthetic",
        "phase": "early",
        "opponent": "script:pressure",
        "policy_seeds": (11, 12),
        "checkpoint_sha256": SHA0,
        "start_tick": 90,
        "stop_tick": 100,
        "scalar_preview": ScalarPreview(
            scalar_seed=7, scalar_root_tick=95, scalar_packet_sha256=SHA0,
            scalar_candidate_actions=(0, 2304, 576, 2), scalar_original_recommendation=2304,
        ),
    }
    values.update(kw)
    return TierBRootRequest(**values)


def test_checkpoint_loading_rejects_unsupported_vocabulary(tmp_path, policy):
    assert policy.checkpoint_sha256 and policy.policy_contract_sha256
    assert not any(p.requires_grad for p in policy.model.parameters())
    path, _ = tiny_checkpoint(tmp_path)
    with pytest.raises(ValueError, match="admitted card scope"):
        load_frozen_policy(path, decks_path="decks.json")


def test_remap_bridges_reference_vocabulary_without_inventing_channels(policy):
    native = NativeDouble()
    council = policy.builder
    shuffled = ("<pad>", "<unknown>", *sorted(set(council.token_names[2:]) | {"ZZProjectile"}, reverse=True))
    reference = StructuredObservationBuilder(
        card_vocab=sorted(SUPPORTED_CARDS), token_names=shuffled, canonical_lane_globals=True,
        public_entity_levels=True, public_hand_levels=True, card_semantics_version=4,
    )
    source = exact_public_observation(reference.build_actor(native.battle, 0))
    expected = project_council_public_observation(council.build_actor(native.battle, 0))
    bridged, unmapped = remap_packet(source, reference.token_names, council)
    assert unmapped == 0
    for name in ("entity_ids", "entity_features", "entity_mask", "hand_ids", "hand_levels"):
        np.testing.assert_array_equal(getattr(bridged.observation, name), getattr(expected.observation, name))
    # The reference packet has no history slots: they stay missing, not inferred.
    assert bridged.observation.opponent_history_ids.shape == (4,)
    assert not bridged.opponent_history_confidence.any()
    crowded = replace(
        source,
        observation=replace(source.observation, entity_mask=np.ones_like(source.observation.entity_mask)),
    )
    with pytest.raises(ValueError):
        remap_packet(crowded, reference.token_names, council)


def test_actor_is_seeded_masked_and_steps_once_per_packet(policy):
    native = NativeDouble()
    view = exact_public_observation(policy.builder.build_actor(native.battle, 0))
    first, second = PolicyActor(policy, seed=5), PolicyActor(policy, seed=5)
    logp, mask, _ = first.distribution(view)
    assert first.distribution(view)[0] is logp  # cached: recurrent state advanced once
    assert len(first.sequences) == 1
    assert np.all(logp[~mask] < -1e8) and np.isclose(np.exp(logp[mask]).sum(), 1.0, atol=1e-4)
    actions = [first.select_action(view)] + [first.select_action(view) for _ in range(5)]
    assert actions == [second.select_action(view) for _ in range(6)]
    assert all(mask[a] for a in actions)
    other = PolicyActor(policy, seed=5)
    other.distribution(view)
    with pytest.raises(ValueError, match="without an action"):
        other.distribution(exact_public_observation(policy.builder.build_actor(native.battle, 0)))


def test_policy_trace_replays_exactly_and_detects_tampering(policy, tmp_path):
    native = NativeDouble()
    actor = PolicyActor(policy, seed=9)
    for _ in range(4):
        actor.select_action(exact_public_observation(policy.builder.build_actor(native.battle, 0)))
    actor.distribution(exact_public_observation(policy.builder.build_actor(native.battle, 0)))
    actor.save_trace(tmp_path)
    logp, _mask, _step = replay_policy_trace(policy, tmp_path)
    assert np.allclose(logp, actor._cached[1][0], atol=1e-6)
    path = tmp_path / "policy-trace-controls.npz"
    with np.load(path) as data:
        arrays = {k: data[k].copy() for k in data.files}
    arrays["sampled_actions"][1] = (arrays["sampled_actions"][1] + 1) % 2304
    path.unlink()
    np.savez_compressed(path, **arrays)
    with pytest.raises(ValueError, match="not reproducible|previous action"):
        replay_policy_trace(policy, tmp_path)


def test_scalar_game_locates_a_policy_eligible_root_without_outcomes(policy):
    preview = sample_scalar_root(
        policy, decks=(DECKS[0], DECKS[2]), root_owner=1, opponent="script:balanced",
        seed=5, policy_seeds=(1, 2), start_tick=100, stop_tick=400,
    )
    assert isinstance(preview, ScalarPreview)
    assert 100 <= preview.scalar_root_tick <= 400
    assert preview.scalar_candidate_actions[1] == 2304
    again = sample_scalar_root(
        policy, decks=(DECKS[0], DECKS[2]), root_owner=1, opponent="script:balanced",
        seed=5, policy_seeds=(1, 2), start_tick=100, stop_tick=400,
    )
    assert again == preview


def test_scalar_rejection_is_reported_not_replaced(tmp_path):
    path, decks = tiny_checkpoint(tmp_path, wait_bias=-3.0)
    spender = load_frozen_policy(path, decks_path=decks)
    result = sample_scalar_root(
        spender, decks=(DECKS[0], DECKS[1]), root_owner=0, opponent="policy",
        seed=5, policy_seeds=(1, 2), start_tick=100, stop_tick=150,
    )
    assert isinstance(result, str) and "no eligible" in result


def bank_with(policy, *, fail_slots=(), fail_first=(), **kw):
    attempts = {}

    def sampler(p, *, seed, start_tick, slot_index, **_call):
        attempt = attempts.get(slot_index, 0)
        attempts[slot_index] = attempt + 1
        if slot_index in fail_slots or (slot_index in fail_first and attempt == 0):
            return "no eligible scalar policy root in the declared window"
        return ScalarPreview(
            scalar_seed=seed, scalar_root_tick=start_tick, scalar_packet_sha256=SHA0,
            scalar_candidate_actions=(0, 2304, 576, 2), scalar_original_recommendation=2304,
        )

    return generate_tier_b_root_bank(policy, master_seed=31, sampler=sampler, **kw)


def test_root_bank_is_stratified_independent_and_bound_to_the_checkpoint(policy):
    bank = bank_with(policy, fail_first=(4,))
    assert len(bank.requests) == 30 and len(bank.rejected_draws) == 1
    assert bank.rejected_draws[0].slot == 4
    owners = [r.root_owner for r in bank.requests]
    assert owners.count(0) == owners.count(1) == 15
    assert {r.phase for r in bank.requests} == {"early", "middle", "double_elixir"}
    assert len({r.episode_seed for r in bank.requests}) == 30
    assert all(r.checkpoint_sha256 == policy.checkpoint_sha256 for r in bank.requests)
    assert {r.opponent for r in bank.requests} == {"policy", "script:balanced", "script:pressure", "script:defense"}
    for r in bank.requests:
        assert tuple(sorted(r.decks[r.root_owner])) == bank.deck_table[r.deck_id]
    draft = bank.protocol_draft("tier-b-attempt")
    assert draft.family_count == 30 and draft.minimum_nonwait_informative == 15
    same = bank_with(policy, fail_first=(4,))
    assert same == bank  # deterministic from the master seed


def test_incomplete_root_bank_is_never_declarable(policy):
    with pytest.raises(IncompleteRootBank) as error:
        bank_with(policy, fail_slots=(2,), max_draws_per_root=2)
    assert error.value.failures == ("slot 2: no eligible scalar draw",)
    assert len(error.value.rejected) == 2 and len(error.value.requests) == 29


def test_root_bank_rejects_reused_games_and_foreign_checkpoints(policy):
    bank = bank_with(policy)
    rows = list(bank.requests)
    rows[1] = rows[1].model_copy(update={"episode_seed": rows[0].episode_seed})
    with pytest.raises(ValueError, match="duplicate"):
        TierBRootBank.model_validate({**bank.model_dump(), "requests": [r.model_dump() for r in rows]}, strict=False)
    rows = list(bank.requests)
    rows[0] = rows[0].model_copy(update={"checkpoint_sha256": SHA0})
    with pytest.raises(ValueError, match="frozen checkpoint"):
        TierBRootBank.model_validate({**bank.model_dump(), "requests": [r.model_dump() for r in rows]}, strict=False)


def test_probe_bank_declares_each_probe_kind(policy):
    slots = probe_slots(DEFAULT_DECK_TABLE, per_kind=2)
    bank = bank_with(policy, block_kind="targeted_probe", slots=slots)
    assert {r.probe_kind for r in bank.requests} == {
        "lane_choice", "building_pull", "body_block", "charge_blocking", "log_pushback", "shields"
    }
    assert bank.protocol_draft("probe").minimum_nonwait_informative is None


def v4_native():
    """The offline native double with the contract-v4 reference builder flags."""
    native = NativeDouble()
    native.builder = StructuredObservationBuilder(
        card_vocab=sorted(SUPPORTED_CARDS), canonical_lane_globals=True,
        public_entity_levels=True, public_hand_levels=True, card_semantics_version=4,
    )
    return native


def native_prefix(policy, output, req):
    native = v4_native()
    return native, collect_tier_b_prefix(
        req,
        {"rndSeed": req.episode_seed},
        output=output,
        policy=policy,
        reference_builder=native.builder,
        command=native.command,
        read_frame=native.frame,
        project=native.project,
        claim=lambda: None,
        verify_producer=lambda: None,
    )


def test_native_prefix_is_driven_by_the_frozen_policy_and_audited(policy, tmp_path):
    req = request(checkpoint_sha256=policy.checkpoint_sha256)
    output = tmp_path / "capture"
    _native, (result, record) = native_prefix(policy, output, req)
    assert result["status"] == "selected" and record is not None
    selection = result["selection"]
    assert selection["root_tick"] == record.root_tick
    assert selection["original_recommendation"] == record.original_recommendation
    assert [c["action_id"] for c in selection["candidates"]] == list(record.candidate_actions.values())
    saved = json.loads((output / "policy-root.json").read_text())
    assert saved["record"] == record.model_dump(mode="json")
    plan = json.loads((output / "plan.json").read_text())
    assert plan["root_request"] == req.model_dump(mode="json")
    assert verify_policy_root_capture(policy, output) == record
    # Any change to the recorded policy inputs fails the pre-seal audit.
    trace = output / "policy-trace-controls.npz"
    trace.write_bytes(trace.read_bytes() + b"\0")
    with pytest.raises(ValueError, match="policy trace changed"):
        verify_policy_root_capture(policy, output)


def test_native_prefix_rejects_foreign_checkpoint_and_retains_absent_probe(policy, tmp_path):
    with pytest.raises(ValueError, match="different checkpoint"):
        native_prefix(policy, tmp_path / "foreign", request())
    req = request(checkpoint_sha256=policy.checkpoint_sha256, probe_kind="shields")
    _native, (result, record) = native_prefix(policy, tmp_path / "probe", req)
    assert result["status"] == "no_eligible_root" and record is None
    saved = json.loads((tmp_path / "probe" / "policy-root.json").read_text())
    assert saved["record"] is None and saved["status"] == "no_eligible_root"
    with pytest.raises(ValueError, match="no selected policy root"):
        verify_policy_root_capture(policy, tmp_path / "probe")
