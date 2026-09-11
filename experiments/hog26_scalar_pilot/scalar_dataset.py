"""Audit a complete pilot before exposing whitelisted public arrays to fitting."""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from scalar_models import PublicSequence

from clasher.rl.simple_pytorch_backend import (
    _compile_public_mask_v2_tables,
    _typed_lookups,
    load_current_client_typed_vocabulary,
)
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Provider
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.collect_hog26_scalar_pilot import EXTRA_TOKENS
from scripts.hog26_scalar_corpus import validate_scalar_corpus
from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata
from scripts.hog26_scalar_openings import digest
from scripts.hog26_scalar_pilot_protocol import validate_pilot_plan
from scripts.hog26_scalar_public_payload_mask import (
    ScalarPublicPayloadMaskProvider,
    ScalarPublicPayloadMaskRules,
)

PUBLIC_FIELDS = tuple(PublicSequence.__dataclass_fields__)

@dataclass(frozen=True)
class Game:
    public: dict
    target_class: int
    target_margin: float
    family: str
    style: str
    seat: int
    cluster: str
    path: str
    sha256: str


def _validate_game_record(data, audit, record, expected_metadata, expected_initial_hand, seat):
    if audit['metadata'] != expected_metadata:
        raise ValueError('game metadata differs from exact external authority')
    if int(data['learner_seat']) != seat:
        raise ValueError('stored learner seat differs from schedule')
    if not np.array_equal(data['hand_ids'][0], expected_initial_hand):
        raise ValueError('stored initial public hand differs from audited opening')
    policy=expected_metadata['policy_token_names']
    hand=np.asarray(data['hand_ids'])
    if ((hand<0)|(hand>=len(policy))).any():
        raise ValueError('hand identity outside policy vocabulary')
    if any(i!=0 and (i==1 or not policy[i].startswith('card_action:')) for i in np.unique(hand)):
        raise ValueError('hand identity is not a known card-action token')
    for key,value in audit.items():
        if key!='metadata' and record.get(key)!=value:
            raise ValueError('recomputed game audit differs from completion record: '+key)
    for key in ('family_id','style','learner_seat','scenario_id','cluster_id'):
        if record.get(key)!=expected_metadata[key]:
            raise ValueError('completion record differs from scheduled identity: '+key)


def load_complete_pilot(directory, *, plan_path, preflight_path):
    directory = Path(directory)
    complete_path = directory / 'complete.json'
    if not complete_path.is_file():
        raise ValueError('pilot is incomplete; no partial corpus access for fitting')
    complete = json.loads(complete_path.read_text())
    plan = json.loads(Path(plan_path).read_text())
    preflight = json.loads(Path(preflight_path).read_text())
    validate_pilot_plan(plan, plan['source_authority'], expected_preflight=preflight)
    if (complete.get('status') != 'complete-audited' or complete.get('mode') != 'collect'
            or complete.get('game_count') != 384 or len(complete.get('games', [])) != 384
            or complete['plan_sha256'] != digest(plan)
            or complete['source_authority_sha256'] != plan['source_authority_sha256']):
        raise ValueError('complete manifest differs from frozen pilot authority')
    if json.loads((directory/'run_plan.json').read_text()) != plan:
        raise ValueError('collector used a different plan')
    authority=plan['source_authority']
    root=Path(authority['resources']['manifest']['path']).parent.parent
    for relative,expected_hash in authority['sources'].items():
        if hashlib.sha256((root/relative).read_bytes()).hexdigest()!=expected_hash:
            raise ValueError('pinned collection source changed: '+relative)
    for resource in authority['resources'].values():
        if hashlib.sha256(Path(resource['path']).read_bytes()).hexdigest()!=resource['sha256']:
            raise ValueError('pinned collection resource changed')
    pinned_vocabulary=load_current_client_typed_vocabulary()
    if pinned_vocabulary.sha256!=authority['vocabulary_sha256']:
        raise ValueError('base vocabulary differs from collection pin')
    builder=StructuredObservationBuilder(decks_path=root/'decks.json',token_names=pinned_vocabulary.token_names,
                                        max_entities=128,card_semantics_version=3,canonical_lane_globals=True)
    setup=compile_standard_simple_setup(builder.loader,authority['contract']['canonical_names'],device='cpu',canonical_lane_globals=True)
    lookup,_=_typed_lookups(setup,builder.loader,pinned_vocabulary)
    base_provider=SimplePublicMaskV2Provider(_compile_public_mask_v2_tables(builder,setup,lookup))
    outcome_tokens=(*pinned_vocabulary.token_names,*EXTRA_TOKENS)
    mask_provider=ScalarPublicPayloadMaskProvider(base_provider,ScalarPublicPayloadMaskRules.compile(
        builder.loader,policy_token_names=pinned_vocabulary.token_names,outcome_token_names=outcome_tokens))
    # The collection source pin remains historical after collection. Fitting
    # code has its own authority; it is not an opportunity to reinterpret labels.
    records = {r['path']:r for r in complete['games']}
    if len(records) != 384 or set(records) != {p.name for p in directory.glob('game-*.npz')}:
        raise ValueError('missing, duplicate or extra game files')
    expected = []
    for index, schedule in enumerate(plan['schedules']):
        verified = audit_scalar_opening_metadata(schedule['metadata'], expected_authority=schedule['external_authority'])
        for scenario in verified:
            for seat in schedule['learner_seats']:
                expected.append((f'game-{index:03d}-{scenario.ordinal:03d}-{seat}.npz', schedule, scenario, seat))
    if {x[0] for x in expected} != set(records):
        raise ValueError('game inventory differs from audited scenarios')
    games = []
    vocabulary = None
    rows = 0
    for name, schedule, scenario, seat in expected:
        path = directory/name
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha != records[name]['sha256']:
            raise ValueError('game digest differs from completed manifest')
        if json.loads(path.with_suffix('.audit.json').read_text()) != records[name]:
            raise ValueError('per-game audit differs from completed manifest')
        audit = validate_scalar_corpus(path)
        metadata = audit['metadata']
        expected_meta = {
            'schema':'clasher.scalar-pilot-game-metadata.v1','mode':'collect',
            'source_authority_sha256':plan['source_authority_sha256'],'plan_sha256':digest(plan),
            'opening_metadata':schedule['metadata'],'opening_authority':schedule['external_authority'],
            'scenario_id':scenario.scenario_id,'cluster_id':scenario.cluster_id,
            'ordinal':scenario.ordinal,'learner_seat':seat,'family_id':schedule['family_id'],
            'style':schedule['external_authority']['opponent_style'],
            'outcome_token_names':list(outcome_tokens),'policy_token_names':list(pinned_vocabulary.token_names),
            'mask_semantics_digest':mask_provider.semantics_digest,
            'retention':'all predecision learner rows through first actual terminal; no filtering by success/outcome',
        }
        if metadata != expected_meta:
            raise ValueError('game metadata differs from externally pinned scenario')
        tokens = tuple(metadata['outcome_token_names'])
        if vocabulary is not None and tokens != vocabulary:
            raise ValueError('inconsistent outcome vocabulary')
        vocabulary = tokens
        for deck in scenario.relative_decks:
            if any(pinned_vocabulary.resolve(card,'card_action')<=1 for card in deck):
                raise ValueError('configured full deck contains an unresolved action identity')
        expected_hand=[pinned_vocabulary.resolve(card,'card_action') for card in scenario.relative_decks[0][:5]]
        with np.load(path,allow_pickle=False) as data:
            _validate_game_record(data,audit,records[name],expected_meta,expected_hand,seat)
            if data['entity_ids'].shape[1]!=128:
                raise ValueError('pilot entity capacity differs from frozen128 contract')
            public = {key:data[key].copy() for key in PUBLIC_FIELDS}
            # Loss/draw/win is the comparison plan's explicit class order.
            raw_wdl = data['outcome_wdl']
            target = int(np.argmax(raw_wdl[::-1]))
            margin = float(data['terminal_tower_margin'])
        public['hand_ids'] = public['hand_ids'][:,:4]
        public['hand_id_confidence'] = public['hand_id_confidence'][:,:4]
        if audit['rows'] != records[name]['rows']:
            raise ValueError('row count differs from audited manifest')
        rows += audit['rows']
        games.append(Game(public,target,margin,schedule['family_id'],metadata['style'],seat,scenario.cluster_id,str(path),sha))
    if rows != complete['rows'] or len({g.cluster for g in games}) != 192:
        raise ValueError('row or paired-scenario total differs')
    counts = {f:sum(g.family==f for g in games) for f in sorted({g.family for g in games})}
    if counts != {f'family-{i:03d}':48 for i in range(8)}:
        raise ValueError('family coverage differs')
    return games,vocabulary,{'games':384,'rows':rows,'clusters':192,
                            'plan_sha256':digest(plan),'complete_manifest_sha256':hashlib.sha256(complete_path.read_bytes()).hexdigest()}


def public_batch(games):
    """Model tensors contain exactly public arrays; grouping/targets stay separate."""
    if not games:
        raise ValueError('empty batch')
    lengths = torch.tensor([len(g.public['entity_ids']) for g in games],dtype=torch.long)
    max_time = int(lengths.max())
    # Crop only universally masked trailing storage; no visible entity or feature is removed.
    max_entities = max(1, max((int(np.flatnonzero(g.public["entity_mask"].any(axis=0))[-1]) + 1
                              if g.public["entity_mask"].any() else 1) for g in games))
    tensors = {}
    for key in PUBLIC_FIELDS:
        source = games[0].public[key]
        if key.startswith("entity_"):
            source = source[:, :max_entities]
        values = np.zeros((len(games),max_time,*source.shape[1:]),dtype=source.dtype)
        for i,g in enumerate(games):
            incoming = g.public[key]
            if key.startswith("entity_"):
                incoming = incoming[:, :max_entities]
            values[i,:len(incoming)] = incoming
        tensors[key] = torch.from_numpy(values)
    return PublicSequence(**tensors),lengths
