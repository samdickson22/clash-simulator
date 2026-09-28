"""Public level readings join the reviewed native Knight/Mirror scene."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.native_public_observation import (
    NativePublicLevelEvidence,
    NativePublicObservationAdapter,
    NativePublicProjectionError,
    NativePublicScope,
)
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.structured_obs import StructuredObservationBuilder

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/native_public_mirror_levels_15_535_86.json').read_text())
CARDS = ('Giant', 'Prince', 'Knight', 'Archers', 'Tesla', 'Fireball', 'Zap', 'Mirror')


def setup(levels=True):
    builder = StructuredObservationBuilder(card_vocab=CARDS, canonical_lane_globals=True, public_entity_levels=levels, max_entities=16)
    adapter = NativePublicObservationAdapter(builder, NativePublicScope('15.535.86', hashlib.sha256(builder.loader.data_file.read_bytes()).hexdigest()), card_names=CARDS)
    raw = FIXTURE['level_evidence']
    evidence = NativePublicLevelEvidence(**(raw | {'levels': {int(k): v for k,v in raw['levels'].items()}, 'confidence': {int(k): v for k,v in raw['confidence'].items()}}))
    return builder, adapter, evidence


@pytest.mark.parametrize('perspective', [0, 1])
def test_native_public_labels_reach_archive_and_model(perspective, tmp_path):
    builder, adapter, evidence = setup()
    view = adapter.project(FIXTURE['ordinary'], perspective, level_evidence=evidence)
    actor = view.observation
    selected = actor.entity_mask & (actor.entity_ids == builder.token_id('Knight'))
    assert sorted(actor.entity_levels[selected].tolist()) == [11, 11, 12, 12]
    assert (actor.entity_features[selected, 9] == 1).all()
    assert (actor.entity_level_confidence[selected] == 1).all()
    # The evidence did not claim a level reading for Crown Towers.
    assert not actor.entity_levels[actor.entity_mask & ~selected].any()
    sequence = PublicPolicySequence.from_observations(builder, [view])
    path = tmp_path / 'native.npz'
    sequence.save(path)
    restored = PublicPolicySequence.load(path, token_names=builder.token_names)
    inputs = restored.policy_inputs(action_mask=np.ones((1,2306),dtype=bool), previous_actions=np.zeros(1,dtype=np.int64),previous_rewards=np.zeros(1,dtype=np.float32),episode_starts=np.ones(1,dtype=bool))
    model = ClasherPolicy(PolicyConfig(num_tokens=builder.spec.num_tokens, max_entities=16, d_model=16,num_heads=4,actor_layers=1,critic_layers=1,memory_size=24,public_contract_version=3,public_token_names=builder.token_names,public_observation_confidence=True),builder.card_stat_features).eval()
    with torch.no_grad():
        assert torch.isfinite(model(inputs).next_state[0]).all()


def test_native_hp_cannot_substitute_for_public_level_reading():
    _, adapter, evidence = setup()
    with pytest.raises(NativePublicProjectionError, match='HP mismatch'):
        adapter.project(FIXTURE['ordinary'], 0)
    wrong = replace(evidence, levels={k:11 for k in evidence.levels})
    with pytest.raises(NativePublicProjectionError, match='HP mismatch'):
        adapter.project(FIXTURE['ordinary'], 0, level_evidence=wrong)
    _, legacy, _ = setup(False)
    with pytest.raises(NativePublicProjectionError, match='level-aware'):
        legacy.project(FIXTURE['ordinary'], 0, level_evidence=evidence)


@pytest.mark.parametrize('change', ['tick', 'generation', 'source', 'body', 'confidence', 'scope'])
def test_stale_or_invalid_level_readings_fail(change):
    _, adapter, evidence = setup()
    if change == 'tick': evidence = replace(evidence, tick=evidence.tick+1)
    elif change == 'generation': evidence = replace(evidence, generation=evidence.generation+1)
    elif change == 'source': evidence = replace(evidence, source_sha256='')
    elif change == 'body': evidence = replace(evidence, levels={999:12}, confidence={999:1.0})
    elif change == 'confidence': evidence = replace(evidence, confidence={k:0.0 for k in evidence.levels})
    elif change == 'scope': evidence = replace(evidence, levels={k:13 for k in evidence.levels})
    with pytest.raises(NativePublicProjectionError):
        adapter.project(FIXTURE['ordinary'], 0, level_evidence=evidence)
