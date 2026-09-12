"""Audit a complete pilot before exposing whitelisted public arrays to fitting."""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from compact_public import compact_public, compact_public_batch
from scalar_models import PublicSequence
from scaling_protocol import validate_pilot_plan as validate_scaling_plan

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
from scripts.hog26_scalar_pilot_protocol import (
    validate_pilot_plan as validate_original_plan,
)
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


def load_complete_pilot(directory, *, plan_path, preflight_path, original=False):
    expected_games = 384 if original else 1152
    expected_clusters = 192 if original else 576
    validate_pilot_plan = validate_original_plan if original else validate_scaling_plan
    directory = Path(directory)
    complete_path = directory / 'complete.json'
    if not complete_path.is_file():
        raise ValueError('pilot is incomplete; no partial corpus access for fitting')
    complete = json.loads(complete_path.read_text())
    plan = json.loads(Path(plan_path).read_text())
    preflight = json.loads(Path(preflight_path).read_text())
    validate_pilot_plan(plan, plan['source_authority'], expected_preflight=preflight)
    if (complete.get('status') != 'complete-audited' or complete.get('mode') != 'collect'
            or complete.get('game_count') != expected_games or len(complete.get('games', [])) != expected_games
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
    if len(records) != expected_games or set(records) != {p.name for p in directory.glob('game-*.npz')}:
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
            public = compact_public({key:data[key] for key in PUBLIC_FIELDS})
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
    if rows != complete['rows'] or len({g.cluster for g in games}) != expected_clusters:
        raise ValueError('row or paired-scenario total differs')
    counts = {f:sum(g.family==f for g in games) for f in sorted({g.family for g in games})}
    if counts != {f'family-{i:03d}':expected_games//8 for i in range(8)}:
        raise ValueError('family coverage differs')
    return games,vocabulary,{'games':expected_games,'rows':rows,'clusters':expected_clusters,
                            'plan_sha256':digest(plan),'complete_manifest_sha256':hashlib.sha256(complete_path.read_bytes()).hexdigest()}


public_batch = compact_public_batch


def validate_combined_games(original, extension, diagnostic_clusters):
    if len(original) != 384 or len(extension) != 1152:
        raise ValueError('combined training requires exactly384 original and1152 new games')
    old_clusters = {g.cluster for g in original}
    new_clusters = {g.cluster for g in extension}
    if len(old_clusters) != 192 or len(new_clusters) != 576:
        raise ValueError('combined cluster counts differ')
    if old_clusters & new_clusters or (old_clusters | new_clusters) & set(diagnostic_clusters):
        raise ValueError('training clusters overlap existing training or diagnostic data')
    games = original + extension
    for family in range(8):
        name = f'family-{family:03d}'
        if sum(g.family == name for g in original) != 48 or sum(g.family == name for g in extension) != 144:
            raise ValueError('combined family quota differs')
    for fold in range(4):
        excluded = sum(int(g.family[-3:])//2 == fold for g in games)
        if excluded != 384 or len(games)-excluded != 1152:
            raise ValueError('combined fold counts differ')
    if any(sum(g.cluster == cluster for g in games) != 2 for cluster in old_clusters | new_clusters):
        raise ValueError('combined cluster is not a paired scenario')
    return games


def load_combined_training(extension_directory, *, extension_plan, extension_preflight):
    plan = json.loads(Path(extension_plan).read_text())
    resources = plan['source_authority']['resources']
    root = Path(resources['manifest']['path']).parent.parent
    original_plan = root/'reports/hog26_scalar_birthfixed_frozen_plan_20260911.json'
    original_preflight = root/'reports/hog26_scalar_birthfixed_preflight_pin_20260911.json'
    original_directory = root/'datasets/derived/hog26_scalar_birthfixed_pilot_seed1279261_20260911'
    # Reject incomplete extension before opening any original training arrays.
    if not (Path(extension_directory)/'complete.json').is_file():
        raise ValueError('extension incomplete; no combined fitting access')
    original, old_vocab, old_audit = load_complete_pilot(original_directory,
        plan_path=original_plan, preflight_path=original_preflight, original=True)
    new, new_vocab, new_audit = load_complete_pilot(extension_directory,
        plan_path=extension_plan, preflight_path=extension_preflight)
    if old_vocab != new_vocab:
        raise ValueError('combined public vocabularies differ')
    if old_audit['complete_manifest_sha256'] != resources['original_training_complete']['sha256']:
        raise ValueError('original training manifest differs from extension pin')
    diagnostic_path = Path(resources['diagnostic_complete']['path'])
    if hashlib.sha256(diagnostic_path.read_bytes()).hexdigest() != resources['diagnostic_complete']['sha256']:
        raise ValueError('diagnostic inventory changed')
    diagnostic = json.loads(diagnostic_path.read_text())
    games = validate_combined_games(original, new, {g['cluster_id'] for g in diagnostic['games']})
    return games, old_vocab, {'games':1536, 'clusters':768,
        'rows':old_audit['rows']+new_audit['rows'], 'original':old_audit, 'extension':new_audit,
        'diagnostic_fitting_games':0, 'storage':'audited zero trailing padding removed; exact batch reconstruction'}
