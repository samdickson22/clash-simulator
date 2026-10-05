"""Native v4 packets serialize unmeasured owned-card levels as missing."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.native_public_observation import (
    NativeProjectileCatalog, NativePublicLevelEvidence, NativePublicObservationAdapter,
    NativePublicScope, native_public_level_coverage, public_reference_builder,
)
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.structured_obs import StructuredObservationBuilder

FIXTURE = json.loads((Path(__file__).parent/'fixtures/native_public_mirror_levels_15_535_86.json').read_text())
CARDS = ('Giant','Prince','Knight','Archers','Tesla','Fireball','Zap','Mirror')


def source():
    builder = StructuredObservationBuilder(card_vocab=CARDS,canonical_lane_globals=True,
        public_entity_levels=True,public_hand_levels=True,max_entities=16,card_semantics_version=4)
    scope = NativePublicScope('15.535.86',hashlib.sha256(builder.loader.data_file.read_bytes()).hexdigest())
    adapter = NativePublicObservationAdapter(builder,scope,card_names=CARDS)
    raw = FIXTURE['level_evidence']
    evidence = NativePublicLevelEvidence(**(raw | {'levels':{int(k):v for k,v in raw['levels'].items()},
        'confidence':{int(k):v for k,v in raw['confidence'].items()}}))
    return builder,adapter,evidence


@pytest.mark.parametrize('owner',[0,1])
def test_native_v4_unknown_own_levels_are_valid_roundtrip_and_actor_inputs(owner,tmp_path):
    builder,adapter,evidence = source()
    public = adapter.project(FIXTURE['ordinary'],owner,level_evidence=evidence)
    public.validate()
    actor=public.observation
    assert actor.hand_levels.dtype == np.int64 and actor.hand_levels.shape == (5,)
    assert actor.hand_level_confidence.dtype == np.float32
    assert not actor.hand_levels.any() and not actor.hand_level_confidence.any()
    coverage = native_public_level_coverage(builder,public)
    assert coverage['own_hand_levels'] == {'observed':0,'visible':4}
    assert coverage['own_next_card_level'] == {'observed':0,'visible':1}
    assert coverage['body_levels'] == {'observed':4,'visible':4}
    assert coverage['tower_levels'] == {'observed':0,'visible':6}
    masks=PublicActionMaskBuilder(builder)
    mask=masks.build(PublicActionMaskInput.from_confidence_observation(public))
    assert mask[:2304].any()  # Missing levels do not forbid otherwise known legality.
    seq=PublicPolicySequence.from_observations(builder,[public])
    path=tmp_path/'native-v4.npz'
    seq.save(path)
    restored=PublicPolicySequence.load(path,token_names=builder.token_names)
    for name,array in seq.arrays.items():
        np.testing.assert_array_equal(restored.arrays[name],array)
    inputs=restored.policy_inputs(action_mask=mask[None],previous_actions=np.array([2304]),
        previous_rewards=np.array([91],dtype=np.float32),episode_starts=np.array([True]))
    assert not inputs.previous_rewards.any()
    model=ClasherPolicy(PolicyConfig(num_tokens=builder.spec.num_tokens,max_entities=16,
        card_semantics_version=4,public_contract_version=4,public_token_names=builder.token_names,
        public_observation_confidence=True,d_model=16,num_heads=4,actor_layers=1,critic_layers=1,memory_size=24),builder.card_stat_features).eval()
    with torch.no_grad():
        output=model(inputs)
    assert torch.isfinite(output.next_state[0]).all()
    assert output.distribution().probs[~inputs.action_mask].sum() == 0


def test_native_nominal_scope_hp_and_undeclared_hud_keys_do_not_establish_levels():
    builder,adapter,evidence=source()
    frame=deepcopy(FIXTURE['ordinary'])
    own=next(player for player in frame['players'] if player['owner']==0)
    for card in [*own['hand'],own['nextCard']]:
        card.update(level=11,level_confidence=1,publicLevel=11)
    view=adapter.project(frame,0,level_evidence=evidence)
    assert adapter.scope.level == 11
    assert not view.observation.hand_levels.any()
    assert not view.observation.hand_level_confidence.any()
    # A partially confident reviewed body label is observed, not missing.
    uncertain=replace(evidence,confidence={key:.5 for key in evidence.confidence})
    partial=adapter.project(frame,0,level_evidence=uncertain)
    assert native_public_level_coverage(builder,partial)['body_levels']['observed']==4
    assert (partial.observation.entity_level_confidence[partial.observation.entity_levels>0]==.5).all()


def test_reference_builder_v4_is_explicit_and_legacy_default_unchanged():
    builder,_,_=source()
    catalog=NativeProjectileCatalog((),'0'*64)
    legacy=public_reference_builder(builder.loader,catalog)
    current=public_reference_builder(builder.loader,catalog,public_contract_version=4)
    assert legacy.public_entity_levels and not legacy.public_hand_levels
    assert current.public_entity_levels and current.public_hand_levels
    assert legacy.token_names==current.token_names
    with pytest.raises(ValueError,match='contract v3 or v4'):
        public_reference_builder(builder.loader,catalog,public_contract_version=99)
