"""Opened native refill frames preserve sparse HUD slots without card shifts."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from clasher.data import CardDataLoader
from clasher.rl.native_public_observation import (
    NativePublicObservationAdapter,NativePublicScope,NativePublicProjectionError,PUBLIC_REFERENCE_CARDS,
)
from clasher.rl.public_action_mask import PublicActionMaskBuilder,PublicActionMaskInput
from clasher.rl.public_reference_checks import check_reference_packet
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.structured_obs import StructuredObservationBuilder

FIXTURE=json.loads((Path(__file__).parent/'fixtures/native_hand_refill_15_535_86.json').read_text())
FRAMES=FIXTURE['snapshots']


@pytest.fixture
def source(tmp_path):
    # Decompress the exact pinned capture ruleset, without changing game stats.
    raw=gzip.decompress((Path(__file__).parent/'fixtures/native_gamedata_15_535_86_daa58b28.json.gz').read_bytes())
    assert hashlib.sha256(raw).hexdigest()==FIXTURE['ruleset_source_sha256']
    ruleset=tmp_path/'native-profile.json';ruleset.write_bytes(raw)
    loader=CardDataLoader(ruleset)
    builder=StructuredObservationBuilder(card_vocab=PUBLIC_REFERENCE_CARDS,card_loader=loader,canonical_lane_globals=True,
        public_entity_levels=True,public_hand_levels=True)
    adapter=NativePublicObservationAdapter(builder,NativePublicScope('15.535.86',
        hashlib.sha256(builder.loader.data_file.read_bytes()).hexdigest()),card_names=PUBLIC_REFERENCE_CARDS)
    tokens={builder.loader.get_card(name)._raw_entry['id']:builder.token_id(name,namespace='card_action') for name in PUBLIC_REFERENCE_CARDS}
    return builder,adapter,tokens


def test_actual_refill_gap_and_return_keep_hand_slots_and_visible_next(tmp_path,source):
    builder,adapter,tokens=source
    masks=PublicActionMaskBuilder(builder)
    views=[]
    for snapshot in FRAMES:
        public=adapter.project(snapshot,1)
        views.append(public)
        own=next(player for player in snapshot['players'] if player['owner']==1)
        expected=np.zeros(5,dtype=np.int64)
        for card in own['hand']:
            expected[card['handIndex']]=tokens[card['cardId']]
        expected[4]=tokens[own['nextCard']['cardId']]
        np.testing.assert_array_equal(public.observation.hand_ids,expected)
        np.testing.assert_array_equal(public.hand_id_confidence,expected>0)
        assert check_reference_packet(snapshot,public,1,card_tokens=tokens)==[]
        assert public.observation.hand_levels[0]==0
        assert public.observation.hand_level_confidence[0]==0
        mask=masks.build(PublicActionMaskInput.from_confidence_observation(public))
        if snapshot['tick'] in (100,110):
            assert public.observation.hand_ids[0]==0
            assert not mask[:576].any()
        else:
            assert public.observation.hand_ids[0]>0
            assert public.hand_id_confidence[0]==1
            assert not mask[:576].any()  # Refilled Cannon is still unaffordable.
    assert views[0].observation.hand_ids[4]==views[-1].observation.hand_ids[0]
    assert views[-1].observation.hand_ids[4]!=views[-1].observation.hand_ids[0]
    sequence=PublicPolicySequence.from_observations(builder,views)
    archive=tmp_path/'refill.npz';sequence.save(archive)
    restored=PublicPolicySequence.load(archive,token_names=builder.token_names)
    for name,array in sequence.arrays.items():
        np.testing.assert_array_equal(restored.arrays[name],array)


@pytest.mark.parametrize('case',['missing','duplicate','out-of-range','negative','boolean','string','row','card','next'])
def test_bad_hud_still_rejected_without_silent_padding(case,source):
    _,adapter,tokens=source
    snapshot=FRAMES[0]
    valid=adapter.project(snapshot,1)
    frame=deepcopy(snapshot)
    own=next(player for player in frame['players'] if player['owner']==1)
    if case=='missing': own.pop('hand')
    elif case=='duplicate': own['hand'].append(deepcopy(own['hand'][0]))
    elif case=='out-of-range': own['hand'][0]['handIndex']=4
    elif case=='negative': own['hand'][0]['handIndex']=-1
    elif case=='boolean': own['hand'][0]['handIndex']=True
    elif case=='string': own['hand'][0]['handIndex']='1'
    elif case=='row': own['hand'][0]=None
    elif case=='card': own['hand'][0]['cardId']=[]
    elif case=='next': own.pop('nextCard')
    with pytest.raises(NativePublicProjectionError):
        adapter.project(frame,1)
    assert check_reference_packet(frame,valid,1,card_tokens=tokens)


def test_checker_rejects_shifted_cards_and_false_empty_slot_confidence(source):
    _,adapter,tokens=source
    frame=FRAMES[0]
    public=adapter.project(frame,1)
    shifted=public.observation.hand_ids.copy()
    shifted[:4]=np.roll(shifted[:4],-1)
    assert check_reference_packet(frame,replace(public,observation=replace(public.observation,hand_ids=shifted)),1,card_tokens=tokens)
    confidence=public.hand_id_confidence.copy();confidence[0]=1
    assert check_reference_packet(frame,replace(public,hand_id_confidence=confidence),1,card_tokens=tokens)
