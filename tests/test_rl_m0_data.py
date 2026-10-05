from dataclasses import replace
import json

import numpy as np
import pytest
import torch

from clasher.rl.deck_curriculum import CurriculumDeck, curriculum_families, pilot_curriculum, split_curriculum
from clasher.rl.imitation import _batch_inputs, _sequence_batch_inputs, load_corpus, permute_hand_imitation_batch, validate_corpus_levels
from clasher.rl.scripted_demonstrations import collect_public_script_game
from clasher.rl.selfplay_env import SelfPlayBattleEnv, StepInfo
from clasher.rl.structured_obs import StructuredObservationBuilder


def test_parent_descendants_duplicate_rosters_and_missing_parent_do_not_leak():
    cards = ("HogRider", "Musketeer", "Cannon", "Fireball", "Log", "Skeletons", "IceGolem", "IceSpirit")
    root = CurriculumDeck("root", cards, "hog", "test")
    child = replace(root, name="child", parent="root", cards=(*cards[:-1], "Zap"))
    grandchild = replace(child, name="grandchild", parent="child", cards=(*cards[:-2], "Archers", "Zap"))
    duplicate = replace(root, name="other-parent")
    external = replace(child, name="external", parent="missing-root", cards=(*cards[:-1], "Tesla"))
    sibling = replace(child, name="sibling", parent="missing-root", cards=(*cards[:-1], "Goblins"))
    decks = [root, child, grandchild, duplicate, external, sibling]
    splits = split_curriculum(decks, validation_fraction=.5, seed=3, held_out_archetypes=frozenset())
    assert splits == split_curriculum(list(reversed(decks)), validation_fraction=.5, seed=3, held_out_archetypes=frozenset())
    roles = {deck.name: role for role, split in enumerate(splits) for deck in split}
    assert len({roles[name] for name in ("root", "child", "grandchild", "other-parent")}) == 1
    assert roles["external"] == roles["sibling"]
    held = split_curriculum([root, replace(child, archetype="x-bow")], validation_fraction=.5, seed=3)
    assert len(held[2]) == 2


def test_pilot_roles_have_disjoint_families_rosters_and_sampling_masses():
    from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS
    pool = pilot_curriculum()
    assert pool == pilot_curriculum()
    all_rosters = []
    all_cards = set()
    family_roles = {}
    for role, decks in pool.items():
        weights = {}
        for deck in decks:
            all_cards.update(deck["cards"])
            all_rosters.append(tuple(sorted(deck["cards"])))
            family = deck["parent"] or deck["name"]
            assert family_roles.setdefault(family, role) == role
            weights[deck["source"]] = weights.get(deck["source"], 0) + deck["sampling_weight"]
            assert len(set(deck["cards"])) == 8
        assert weights == pytest.approx({"engineering-structured": .6, "semantic-procedural": .3, "legal-stress": .1})
    assert all_cards == SUPPORTED_CARDS
    assert len(set(all_rosters)) == len(all_rosters)


def test_synthetic_complete_game_adapter_roundtrips_inputs(tmp_path, monkeypatch):
    from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
    from clasher.rl.public_policy_contract import PublicPolicySequence
    pool = pilot_curriculum()
    decks_path = tmp_path / "pilot.json"
    decks_path.write_text(json.dumps({"decks": sum(pool.values(), [])}))
    builder = StructuredObservationBuilder(decks_path=decks_path, max_entities=16, card_semantics_version=4, canonical_perspective=True, canonical_lane_globals=True, public_entity_levels=True, public_hand_levels=True, public_history_slots=4, public_seen_card_slots=8)
    env = SelfPlayBattleEnv(decks_path=decks_path, decision_interval_ticks=5, seed=3, canonical_lane_globals=True, public_contract_version=4)
    env.reset(seed=3)
    # This is a two-step contract fixture, not a played game or teacher evidence.
    monkeypatch.setattr(PublicScriptedOpponent, "select_action", lambda self, packet: 2304)
    def synthetic_step(actions, *, pre_action_masks):
        env.battle.tick += 5
        env.battle.game_over = env.battle.tick == 10
        return {0: 0., 1: 0.}, env.battle.game_over, StepInfo({0: True, 1: True}, 5)
    monkeypatch.setattr(env, "step", synthetic_step)
    result = collect_public_script_game(env, builder, seed=3, episode_id=7, role="training", family_id="synthetic")
    assert result.metadata.decisions == 2
    assert result.metadata.samples == 3
    archive = tmp_path / "game.npz"
    result.save(archive)
    metadata, arrays = load_corpus(archive)
    assert metadata.public_contract_version == 4
    assert arrays["expert_action_supervision_valid"].tolist() == [True, True, False]
    assert arrays["previous_rewards"].tolist() == [0., 0., 0.]
    assert arrays["hand_levels"].shape == (3, 5)
    from clasher.rl.model import ClasherPolicy, PolicyConfig
    model = ClasherPolicy(PolicyConfig(num_tokens=builder.spec.num_tokens, max_entities=16,
        card_semantics_version=4, public_contract_version=4, public_token_names=builder.token_names,
        public_observation_confidence=True, canonical_lane_globals=True, public_history_slots=4,
        public_seen_card_slots=8, d_model=32, num_heads=4, actor_layers=1, critic_layers=1,
        memory_size=32), builder.card_stat_features).eval()
    supervised = _sequence_batch_inputs(arrays, np.asarray([[0,1,2]]), torch.device("cpu"))
    inference = result.public.policy_inputs(action_mask=arrays["action_masks"], previous_actions=arrays["previous_actions"],
        previous_rewards=arrays["previous_rewards"], episode_starts=arrays["episode_starts"])
    with torch.no_grad():
        expected, actual = model(inference), model(supervised)
    torch.testing.assert_close(expected.joint_logits, actual.joint_logits)
    for expected_state, actual_state in zip(expected.next_state, actual.next_state):
        torch.testing.assert_close(expected_state, actual_state)
    from clasher.rl.imitation import _council_imitation_state, _imitation_evaluation_batches, fit_imitation_corpus
    from clasher.rl.council_warmstart import _merge_complete_games
    with torch.no_grad():
        state = _council_imitation_state(model, arrays, np.asarray([[1,2]]), device=torch.device("cpu"), episode_offsets={7:0})
        suffix = _sequence_batch_inputs(arrays, np.asarray([[1,2]]), torch.device("cpu"), reset_memory=False)
        suffix_output = model(suffix, state)
        torch.testing.assert_close(suffix_output.joint_logits, expected.joint_logits[:,1:])
        evaluated = list(_imitation_evaluation_batches(model, arrays, np.asarray([1,2]), batch_size=1, device=torch.device("cpu"), trim_entity_padding=True))
        for selected, _, output in evaluated:
            torch.testing.assert_close(output.joint_logits[:,0], expected.joint_logits[0,selected])
    shard_paths = []
    for split in (0,1):
        game = replace(result, controls=result.controls | {
            "episode_ids": np.full(3, split, dtype=np.int64),
            "fit_split": np.full(3, split, dtype=np.int8),
        })
        path = tmp_path / f"fit-{split}.npz"
        game.save(path)
        shard_paths.append(path)
    merged = tmp_path / "merged.npz"
    merged_info = _merge_complete_games(shard_paths, merged, provenance={"role":"training", "complete_games":True})
    assert merged_info["decisions"] == 4
    assert merged_info["samples"] == 6
    # Synthetic optimizer API check only. No real gameplay or teacher labels.
    resource_snapshot = {"cpu_core_hours_used":0.5,"accelerator_hours_used":0.0,
        "cpu_core_hours_remaining":4607.5,"accelerator_hours_remaining":72.0,
        "active_job":None,"ledger_path":str(tmp_path/"synthetic-budget.json"),
        "accounting":"allocated task cores times elapsed wall time; no unrelated host jobs"}
    fit = fit_imitation_corpus(corpus_path=merged, output_checkpoint=tmp_path/"fit.pt",
        control_checkpoint=tmp_path/"control.pt", decks_path=decks_path, seed=3,
        epochs=1, batch_size=4, learning_rate=1e-4, validation_fraction=.5,
        device=torch.device("cpu"), d_model=32, num_heads=4, actor_layers=1,
        critic_layers=1, memory_size=32, model_config_override=model.config,
        checkpoint_metadata={"gamedata_sha256":"a"*64,"resource_budget":resource_snapshot},
        card_semantics_version=4, sequence_length=4, train_on_forced_actions=True,
        trim_entity_padding=True)
    assert fit["recurrence"] == "current-weight-full-episode-prefix"
    assert torch.load(tmp_path/"fit.pt", weights_only=False)["resource_budget"] == resource_snapshot
    assert fit["predefined_fit_split"] is True
    assert torch.load(tmp_path/"fit.pt", weights_only=False)["args"]["initialization"] == "public_script_imitation"
    arrays["hand_levels"][:, :4] = [10, 11, 12, 0]
    arrays["hand_level_confidence"][:, :4] = [1., .9, .7, 0.]
    validate_corpus_levels(arrays, required=True)
    inputs = _sequence_batch_inputs(arrays, np.asarray([[0, 1, 2]]), torch.device("cpu"), trim_entity_padding=True)
    flat = _batch_inputs(arrays, np.asarray([0]), torch.device("cpu"), trim_entity_padding=True)
    assert torch.equal(inputs.hand_levels[:, :1], flat.hand_levels)
    assert inputs.entity_levels.shape == inputs.entity_ids.shape
    assert inputs.opponent_history_ids.shape == (1, 3, 4)
    permuted, _ = permute_hand_imitation_batch(inputs, torch.tensor([[2304,2304,2304]]), torch.tensor([[3,2,1,0]]))
    assert permuted.hand_levels[0,0,:4].tolist() == [0,12,11,10]
    assert torch.equal(permuted.hand_level_confidence[0,0,:4], inputs.hand_level_confidence[0,0,:4].flip(0))
    public_path = tmp_path / "public.npz"
    result.public.save(public_path)
    public = PublicPolicySequence.load(public_path, token_names=builder.token_names)
    assert np.array_equal(public.arrays["hand_levels"], result.public.arrays["hand_levels"])
    legacy = {key: value for key,value in arrays.items() if key not in {"entity_levels", "entity_level_confidence", "hand_levels", "hand_level_confidence"}}
    validate_corpus_levels(legacy)
    assert _batch_inputs(legacy, np.asarray([0]), torch.device("cpu")).hand_levels is None
    with pytest.raises(ValueError, match="missing"):
        validate_corpus_levels(legacy, required=True)


def test_warmstart_rejects_admission_before_outputs_or_environment(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from clasher.rl import council_pilot, council_warmstart
    monkeypatch.setattr(council_pilot, "load_pilot_config", lambda _: SimpleNamespace())
    def denied(*args, **kwargs):
        raise ValueError("unadmitted")
    monkeypatch.setattr(council_pilot, "require_pilot_admission", denied)
    monkeypatch.setattr(council_warmstart, "SelfPlayBattleEnv", lambda **_: pytest.fail("environment created before admission"))
    with pytest.raises(ValueError, match="unadmitted"):
        council_warmstart.run_script_warmstart(config_path=tmp_path/"config.toml", admission_path=tmp_path/"receipt.json", seed=1, output_checkpoint=tmp_path/"output"/"policy.pt")
    assert list(tmp_path.iterdir()) == []


def test_warmstart_training_families_and_tail_contract():
    from pathlib import Path
    from clasher.rl.council_warmstart import _training_deck_plan
    from clasher.rl.imitation import sequence_chunks
    path = Path("reports/strategy_council_20260928/m0/data/roles_v2/training.json")
    decks, splits = _training_deck_plan(path, seed=2901)
    assert set(splits.values()) == {0, 1}
    assert len({deck["family_id"] for deck in decks}) == 7
    for deck in decks:
        assert splits[deck["family_id"]] in (0, 1)
    chunks = sequence_chunks(np.array([0,0,0,1,1,1,1,1]), np.arange(8), sequence_length=4, preserve_tails=True)
    assert chunks.tolist() == [[0,1,2,2],[7,7,7,7],[3,4,5,6]]


def test_bounded_warmstart_orchestration_uses_admission_and_complete_shards(tmp_path, monkeypatch):
    """Synthetic orchestration fixture; teacher collection and fitting are mocked."""
    from datetime import datetime, timezone
    from pathlib import Path
    from types import SimpleNamespace
    from clasher.rl import council_budget, council_pilot, council_warmstart
    from clasher.rl.imitation import CorpusMetadata
    from clasher.rl.public_observation import project_council_public_observation
    from clasher.rl.public_policy_contract import PublicPolicySequence
    from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
    from clasher.rl.scripted_demonstrations import ScriptedGameDemonstration
    root = Path.cwd()
    config_path, admission_path = tmp_path/"pilot.toml", tmp_path/"admission.json"
    config_path.write_text("synthetic test configuration")
    admission_path.write_text("synthetic test guard fixture")
    pins = tmp_path/"pins.json"
    pins.write_text("{}")
    decks_path = root/"reports/strategy_council_20260928/m0/data/roles_v2/training.json"
    config = SimpleNamespace(output_dir=str(tmp_path), warmstart_decisions=4, seeds=(2901,2902,2903), torch_threads=1,
        device="cpu", training_decks_path=str(decks_path), gamedata_path=str(root/"gamedata.json"),
        source_root=str(root), gamedata_sha256="1"*64, strategy_sha256="2"*64,
        source_pins_path=str(pins), training_decks_sha256=council_warmstart._sha(decks_path))
    monkeypatch.setenv("CLASHER_ROOT", str(root))
    monkeypatch.setenv("CLASHER_PILOT_BUDGET", str(tmp_path / "resource-budget.json"))
    monkeypatch.setattr(council_budget, "require_owned_budget", lambda _: {"synthetic": True})
    monkeypatch.setattr(council_budget, "budget_snapshot", lambda _: {"synthetic": True})
    monkeypatch.setattr(council_pilot, "load_pilot_config", lambda _:config)
    guard_calls = []
    monkeypatch.setattr(council_pilot, "require_pilot_admission", lambda *a,**kw:guard_calls.append(kw))
    monkeypatch.setattr(council_warmstart, "FULL_GAME_DECISION_LIMIT", 2)
    def synthetic_game(env,builder,**kwargs):
        assert guard_calls and kwargs["max_decisions"] == 2
        observation = project_council_public_observation(builder.build_actor(env.battle, kwargs["learner_player_id"]))
        terminal = replace(observation, observation=replace(observation.observation, terminal=True))
        public = PublicPolicySequence.from_observations(builder,[observation,observation,terminal])
        masks = np.stack([PublicActionMaskBuilder(builder).build(PublicActionMaskInput.from_confidence_observation(view)) for view in (observation,observation,terminal)])
        controls = {"action_masks":masks, "previous_actions":np.full(3,2304,dtype=np.int64),
            "previous_rewards":np.zeros(3,dtype=np.float32), "episode_starts":np.array([True,False,False]),
            "expert_actions":np.full(3,2304,dtype=np.int64), "episode_ids":np.full(3,kwargs["episode_id"],dtype=np.int64),
            "expert_action_supervision_valid":np.array([True,True,False])}
        metadata = CorpusMetadata(schema_version=1,created_at=datetime.now(timezone.utc).isoformat(),seed=kwargs["seed"],
            decisions=2,samples=3,decision_interval=5,max_ticks=6001,planner_depth=0,planner_simulations=0,
            planner_action_samples=0,max_entities=128,token_names=builder.token_names,label_source="public-script",
            public_contract_version=4,public_history_slots=4,public_seen_card_slots=8,
            provenance=json.dumps({"role":"training","complete_game":True,"synthetic":True}))
        return ScriptedGameDemonstration(public,controls,metadata,{"accepted_commands":np.ones(2,dtype=bool)})
    monkeypatch.setattr(council_warmstart,"collect_public_script_game",synthetic_game)
    fitted=[]
    def synthetic_fit(**kwargs):
        assert len(guard_calls)==2
        assert kwargs["model_config_override"].d_model==128
        assert kwargs["model_config_override"].actor_observation_domain=="simulator-exact"
        assert kwargs["checkpoint_metadata"]["gamedata_sha256"]=="1"*64
        _,arrays=load_corpus(kwargs["corpus_path"])
        assert arrays["fit_split"].tolist()==[0,0,0,1,1,1]
        assert arrays["previous_rewards"].tolist()==[0.]*6
        kwargs["output_checkpoint"].write_text("mock fitted checkpoint")
        kwargs["control_checkpoint"].write_text("mock matched random checkpoint")
        fitted.append(kwargs)
        return {"synthetic":True}
    monkeypatch.setattr(council_warmstart,"fit_imitation_corpus",synthetic_fit)
    receipt = council_warmstart.run_script_warmstart(config_path=config_path,admission_path=admission_path,
        seed=2901,output_checkpoint=tmp_path/"model.pt")
    assert receipt["corpus"]["decisions"]==4
    assert receipt["corpus"]["games"]==2
    assert len(fitted)==1
