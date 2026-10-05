"""Re-audit saved native public channels without claiming camera calibration.

Receipts are deterministic opened-development evidence. They bind raw captures,
projection sources and data; they never change historical execution results.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import Field

from clasher.data import CardDataLoader
from .action_space import DiscreteTileActionSpace
from .native_public_observation import (
    PUBLIC_REFERENCE_CARDS, NativeProjectileCatalog, NativePublicLevelEvidence,
    NativePublicObservationAdapter, NativePublicScope, native_public_level_coverage,
    public_reference_builder,
)
from .own_card_history import AcceptedOwnPlay
from .native_frame_storage import validate_native_frame_storage
from .public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from .public_policy_contract import PublicPolicySequence
from .public_reference_checks import check_reference_entities, check_reference_packet, reference_token_maps
from .readiness_execution import CAPTURE_FILES, canonical_sha, packet_sha
from .training_readiness_v2 import Record, SHA


class NativeCalibrationReceipt(Record):
    schema_version: Literal['native-public-calibration-v1'] = 'native-public-calibration-v1'
    scope: Literal['native-exact-public-v4'] = 'native-exact-public-v4'
    evidence_role: Literal['opened_development'] = 'opened_development'
    structural_validity_established: Literal[True] = True
    measured_native_known_channels_valid: Literal[True] = True
    coordinate_transport_roundtrip_valid: Literal[True] = True
    camera_accuracy_established: Literal[False] = False
    own_card_level_calibration_established: Literal[False] = False
    command_acceptance_independently_audited: Literal[False] = False
    run_directory: str
    source_pins: dict[str, SHA]
    artifact_pins: dict[str, SHA]
    ruleset_sha256: tuple[SHA, ...]
    catalog_sha256: SHA
    frame_count: int = Field(gt=0)
    owner_packet_count: int = Field(gt=0)
    jobs: tuple[dict, ...]
    checked_channels: tuple[str, ...]
    missing_channels: tuple[str, ...]
    limitations: tuple[str, ...]


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024*1024), b''):
            digest.update(data)
    return digest.hexdigest()


def _sources() -> dict[str, str]:
    # Pin projection/serialization plus their card-data and simulator metadata
    # dependencies. Unrelated training/ledger edits do not change calibration.
    package = Path(__file__).resolve().parents[1]
    rl_modules = {
        '__init__.py', 'native_public_calibration.py', 'native_public_observation.py', 'native_frame_storage.py',
        'public_observation.py', 'public_policy_contract.py', 'public_reference_checks.py',
        'public_action_mask.py', 'action_space.py', 'structured_obs.py', 'model.py',
        'joint_action_value.py', 'structured_memory.py', 'card_semantics.py',
        'deck_pool.py', 'common.py', 'own_card_history.py', 'readiness_execution.py',
        'training_readiness_v2.py', 'public_scripted_opponent.py',
    }
    paths = [path for path in package.rglob('*.py')
             if path.relative_to(package).parts[0] not in {'rl', 'torch_sim'}
             or (path.parent == package/'rl' and path.name in rl_modules)]
    return {str(path): sha_file(path) for path in sorted(paths)}


def audit_native_frame(frame, *, builder, adapter, catalog, own_history):
    """Validate raw known channels, missingness and actor serialization for both seats."""
    validate_native_frame_storage(frame)
    ordinary, rich, source = frame['ordinary'], frame['rich'], frame['level_source']
    if source['ordinary'] != ordinary:
        raise ValueError('native level reader and ordinary frame disagree')
    levels = {}
    for key, value in source['levels'].items():
        if type(key) is int:
            identity = key
        elif isinstance(key,str) and key.isdecimal() and str(int(key)) == key:
            identity = int(key)
        else:
            raise ValueError('invalid native level identity')
        if identity in levels:
            raise ValueError('duplicate native level identity')
        levels[identity] = value
    evidence = NativePublicLevelEvidence(
        tick=ordinary['tick'], generation=ordinary['generation'], state_epoch=ordinary['stateEpoch'],
        source_sha256=canonical_sha(source), levels=levels, confidence={identity:1. for identity in levels},
    )
    card_tokens,body_tokens,effect_tokens,tower_tokens = reference_token_maps(builder,PUBLIC_REFERENCE_CARDS,catalog)
    masks = PublicActionMaskBuilder(builder)
    space = DiscreteTileActionSpace()
    packets, action_masks, coverage = [], [], []
    for owner in (0,1):
        view = adapter.project(ordinary,owner,rich_snapshot=rich,level_evidence=evidence,own_last_play=own_history[owner])
        view.validate()
        errors = check_reference_packet(ordinary,view,owner,card_tokens=card_tokens)
        errors += check_reference_entities(ordinary,rich,view,owner,body_tokens=body_tokens,
            effect_tokens=effect_tokens,tower_tokens=tower_tokens,levels=levels,level_confidence=evidence.confidence)
        if errors:
            raise ValueError('native known-channel audit failed: '+'; '.join(errors))
        actor = view.observation
        if actor.hand_levels is None or actor.hand_level_confidence is None:
            raise ValueError('v4 own-card missingness fields are required')
        if actor.hand_levels.any() or actor.hand_level_confidence.any():
            raise ValueError('native source does not establish measured own-card levels')
        mask = masks.build(PublicActionMaskInput.from_confidence_observation(view))
        sequence = PublicPolicySequence.from_observations(builder,[view])
        inputs = sequence.policy_inputs(action_mask=mask[None],previous_actions=np.array([2304]),
            previous_rewards=np.array([123],dtype=np.float32),episode_starts=np.array([True]))
        for name,array in sequence.arrays.items():
            if name in ('terminal_status','board_rotated'):
                continue
            np.testing.assert_array_equal(getattr(inputs,name)[0].numpy(),array)
        if inputs.previous_rewards.any() or any(name.startswith('critic_') for name in sequence.arrays):
            raise ValueError('actor serialization imported privileged supervision')
        # Exhaust every legal placement, not just the selected command. Match
        # tile-center canonical coordinates to the integer native transport.
        for action in np.flatnonzero(mask[:2304]):
            choice = space.decode_action(int(action),owner)
            native_xy = (round(choice.position.x*1000),round(choice.position.y*1000))
            if any(value % 1000 != 500 for value in native_xy):
                raise ValueError('placement is not an exact native tile center')
            if space.encode_action(int(action)//576,int(native_xy[0]//1000),int(native_xy[1]//1000),owner) != action:
                raise ValueError('public/native placement coordinate round trip failed')
        packets.append(view);action_masks.append(mask)
        coverage.append(native_public_level_coverage(builder,view))
    return packets,action_masks,coverage


def audit_saved_run(run_directory: Path) -> NativeCalibrationReceipt:
    sources_before = _sources()
    run_directory = run_directory.resolve()
    plan_path, complete_path = run_directory/'execution-plan.json',run_directory/'complete.json'
    plan,complete = json.loads(plan_path.read_text()),json.loads(complete_path.read_text())
    if plan['purpose'] == 'fresh_acceptance' or complete['status'] != 'completed_development_only':
        raise ValueError('calibration receipt requires completed opened development evidence')
    if any(f['role']!='opened_development' for f in plan['protocol']['families']):
        raise ValueError('calibration data roles must remain opened development')
    artifacts = {str(path):sha_file(path) for path in (plan_path,complete_path)}
    def bind(path,expected=None):
        path = Path(path).resolve(); actual = sha_file(path)
        if expected is not None and actual != expected:
            raise ValueError(f'bound calibration input changed: {path}')
        artifacts[str(path)] = actual
        return actual
    catalog_path = Path(plan['catalog_path'])
    bind(catalog_path,plan['catalog_sha256'])
    catalog = NativeProjectileCatalog.from_csv(catalog_path,expected_sha256=plan['catalog_sha256'])
    folders = sorted(run_directory.glob('job-*'))
    if len(folders)!=complete['jobs']:
        raise ValueError('development completion count disagrees with job inventory')
    summaries=[];rulesets=set();frames=0
    reader_key = next((key for key in plan['source_pins'] if key.endswith('/scripts/read_native_public_levels.py')),None)
    if reader_key is None:
        raise ValueError('native level reader source is unpinned')
    for folder in folders:
        result_path,claim_path = folder/'result.json',folder/'claim.json'
        result,claim=json.loads(result_path.read_text()),json.loads(claim_path.read_text())
        if result['job'] != claim:
            raise ValueError('job claim and completed result disagree')
        if claim['engine'] != 'reference':
            continue
        bind(result_path);bind(claim_path)
        stream_path=folder/'decisions.jsonl.gz';bind(stream_path,result['decisions_sha256'])
        binding=next(c for c in plan['captures'] if c['family_id']==claim['family_id'])
        capture=Path(binding['capture_path'])
        for filename in CAPTURE_FILES:
            bind(capture/filename,binding['input_hashes'][filename])
        rulesets.add(binding['input_hashes']['gamedata.json'])
        loader=CardDataLoader(capture/'gamedata.json')
        builder=public_reference_builder(loader,catalog,public_contract_version=4)
        adapter=NativePublicObservationAdapter(builder,NativePublicScope('15.535.86',binding['input_hashes']['gamedata.json']),
            card_names=PUBLIC_REFERENCE_CARDS,projectile_catalog=catalog)
        history=[None,None]
        for command in json.loads((capture/'result.json').read_text())['commands']:
            if command['submitted_tick'] >= binding['root_tick']:
                continue
            if command['native_acceptance_spend_evidence'] is not True:
                raise ValueError('recorded prefix lacks runtime acceptance evidence')
            history[command['owner']]=AcceptedOwnPlay(command['name'],command['cost'])
        count=0;first_tick=None;last_tick=None;totals={};sparse=0;identities=set()
        with gzip.open(stream_path,'rt') as stream:
            for line in stream:
                row=json.loads(line);frame=row['native_frame']
                if frame is None or type(row['tick']) is not int or frame['ordinary']['tick']!=row['tick']:
                    raise ValueError('decision row lacks its raw native frame')
                if last_tick is not None and row['tick']!=last_tick+5:
                    raise ValueError('recorded native decision sequence has a missing interval')
                if first_tick is None:
                    first_tick=row['tick']
                    if first_tick!=binding['root_tick']:
                        raise ValueError('native audit starts outside declared root')
                level_source=frame['level_source']
                if level_source['reader_sha256']!=plan['source_pins'][reader_key]:
                    raise ValueError('native level reader differs from recorded source')
                if canonical_sha({'ok':True,'attestation':level_source['attestation']})!=plan['native_attestation_sha256']:
                    raise ValueError('native level source runtime attestation mismatch')
                packets,masks,coverage=audit_native_frame(frame,builder=builder,adapter=adapter,catalog=catalog,own_history=history)
                if [packet_sha(view) for view in packets]!=row['public_sha256']:
                    raise ValueError('serialized public packet does not reproduce recorded actor input')
                if coverage!=row['level_coverage_by_owner']:
                    raise ValueError('recorded level coverage differs from raw public data')
                if len(row['actions'])!=2:
                    raise ValueError('both player actions required')
                for owner,(view,mask) in enumerate(zip(packets,masks)):
                    action=row['actions'][owner]
                    if type(action) is not int or not 0<=action<len(mask) or not mask[action]:
                        raise ValueError('recorded action is not public legal')
                    sparse+=int(np.count_nonzero(view.observation.hand_ids[:4])<4)
                    identities.update(int(x) for x in view.observation.entity_ids[view.observation.entity_mask])
                    for channel,counts in coverage[owner].items():
                        bucket=totals.setdefault(channel,{'observed':0,'visible':0})
                        for key,value in counts.items():bucket[key]+=value
                    if action<2304:
                        name=builder.card_name_for_token_id(int(view.observation.hand_ids[action//576]))
                        history[owner]=AcceptedOwnPlay(name,int(loader.get_card(name).mana_cost))
                count+=1;last_tick=row['tick']
        if count==0:raise ValueError('native calibration stream is empty')
        frames+=count
        summaries.append({'job_directory':str(folder),'frame_count':count,'first_tick':first_tick,'last_tick':last_tick,
            'level_coverage':totals,'sparse_hand_owner_packets':sparse,'visible_entity_tokens':sorted(builder.token_names[index] for index in identities),
            'native_attestation_sha256':plan['native_attestation_sha256'],'level_reader_sha256':plan['source_pins'][reader_key]})
    if not summaries:raise ValueError('no native reference jobs to audit')
    for filename, expected in artifacts.items():
        if sha_file(Path(filename)) != expected:
            raise ValueError('calibration input changed during audit: '+filename)
    if _sources()!=sources_before:
        raise ValueError('calibration audit source changed during execution')
    return NativeCalibrationReceipt(run_directory=str(run_directory),source_pins=sources_before,artifact_pins=artifacts,
        ruleset_sha256=tuple(sorted(rulesets)),catalog_sha256=plan['catalog_sha256'],frame_count=frames,owner_packet_count=2*frames,jobs=tuple(summaries),
        checked_channels=('visible_entity_identity_kind_owner','integer_native_xy','body_hp_fraction','own_hand_slot_identity_presence',
            'visible_next_identity','own_elixir','crown_hp_fraction','frame_bound_body_level_labels','public_action_mask','native_tile_center_roundtrip',
            'serialized_public_packet_digest','actor_tensor_shapes_dtypes_missingness'),
        missing_channels=('own_hand_levels','own_next_card_level','visible_clock','motion','unsupported_status_timers','opponent_history'),
        limitations=('Native exact-reference measurements only; no pixel detector or camera accuracy claim.',
            'Own-card level zero/confidence zero is structurally valid but remains uncalibrated.',
            'Historical runtime checked acceptance; per-command receipts and tick+1 snapshots were not saved in these streams, so acceptance is not independently re-audited.',
            'Opened development evidence only; no fresh acceptance or playing-strength claim.',
            'Public masks are recomputed from verified inputs; native command acceptance and placement sensitivity require their own transport evidence.',
            'Known-channel scope is limited to observed identities and situations reported per job; unseen mechanics are not calibrated.'))


def verify_calibration_receipt(path: Path) -> NativeCalibrationReceipt:
    """Recheck bound files and rerun the scoped audit; never trust a boolean alone."""
    receipt=NativeCalibrationReceipt.model_validate_json(path.read_text())
    for filename,expected in receipt.source_pins.items() | receipt.artifact_pins.items():
        if sha_file(Path(filename))!=expected:
            raise ValueError(f'calibration receipt binding changed: {filename}')
    actual=audit_saved_run(Path(receipt.run_directory))
    if actual.model_dump(mode='json')!=receipt.model_dump(mode='json'):
        raise ValueError('calibration receipt does not reproduce its bound evidence')
    return receipt
