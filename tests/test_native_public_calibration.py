"""Synthetic corruption probes for the opened native known-channel auditor."""
from copy import deepcopy
import json

import numpy as np
import pytest
from pydantic import ValidationError

from test_native_public_refill import FRAMES, source as source
from clasher.rl.native_public_calibration import NativeCalibrationReceipt, audit_native_frame, verify_calibration_receipt
from clasher.rl.native_public_observation import NativeProjectileCatalog


def frame():
    ordinary=deepcopy(FRAMES[0])
    # Synthetic level-label test input, not an additional calibration capture.
    rich={key:ordinary[key] for key in ('tick','generation','stateEpoch','count','returned')}
    rich.update(ok=True,schema='native-rich-telemetry.v3',truncated=False,objects=deepcopy(ordinary['objects']))
    return {'ordinary':ordinary,'rich':rich,'level_source':{'ordinary':deepcopy(ordinary),
        'levels':{obj['nativeObjectId']:11 for obj in ordinary['objects']}}}


def test_known_native_channels_and_unknown_own_levels_are_separate(source):
    builder,adapter,_=source
    packets,masks,coverage=audit_native_frame(frame(),builder=builder,adapter=adapter,
        catalog=NativeProjectileCatalog((),'0'*64),own_history=[None,None])
    for owner,packet in enumerate(packets):
        assert coverage[owner]['tower_levels']=={'observed':6,'visible':6}
        assert coverage[owner]['own_next_card_level']=={'observed':0,'visible':1}
        assert not packet.observation.hand_level_confidence.any()
        assert not packet.observation.hand_levels.any()
        assert masks[owner][2304]
    assert packets[1].observation.hand_ids[0]==0
    assert not masks[1][:576].any()


@pytest.mark.parametrize('fault',['frame','level','extra-level','rich-epoch','hp','identity','slot'])
def test_raw_or_projected_corruption_fails(source,fault,monkeypatch):
    builder,adapter,_=source
    raw=frame()
    if fault=='frame':raw['level_source']['ordinary']['tick']+=1
    elif fault=='level':raw['level_source']['levels'][raw['ordinary']['objects'][-1]['nativeObjectId']]=10
    elif fault=='extra-level':raw['level_source']['levels'][999]=11
    elif fault=='rich-epoch':raw['rich']['stateEpoch']+=1
    else:
        original=adapter.project
        def corrupt(*args,**kwargs):
            packet=deepcopy(original(*args,**kwargs))
            if fault=='hp':packet.observation.entity_features[0,9]=.123
            elif fault=='identity':packet.observation.entity_ids[0]=builder.token_id('Knight')
            else:packet.observation.hand_ids[:4]=np.roll(packet.observation.hand_ids[:4],1)
            return packet
        monkeypatch.setattr(adapter,'project',corrupt)
    with pytest.raises((ValueError,AssertionError)):
        audit_native_frame(raw,builder=builder,adapter=adapter,catalog=NativeProjectileCatalog((),'0'*64),own_history=[None,None])


def test_receipt_cannot_claim_camera_own_level_or_execution_acceptance():
    # Start from a structurally valid record so failures prove the scope flags.
    baseline=NativeCalibrationReceipt(run_directory='unused',source_pins={'source':'0'*64},
        artifact_pins={'data':'0'*64},ruleset_sha256=('0'*64,),catalog_sha256='0'*64,
        frame_count=1,owner_packet_count=2,jobs=({},),checked_channels=(),missing_channels=(),limitations=()).model_dump()
    for name in ('camera_accuracy_established','own_card_level_calibration_established',
                 'command_acceptance_independently_audited'):
        with pytest.raises(ValidationError):
            NativeCalibrationReceipt.model_validate(baseline | {name:True})


def test_missing_receipt_bindings_cannot_be_treated_as_calibrated(tmp_path):
    path=tmp_path/'receipt.json'
    path.write_text(json.dumps({'schema_version':'native-public-calibration-v1','structural_validity_established':True}))
    with pytest.raises(ValidationError):verify_calibration_receipt(path)


def test_verifier_rechecks_artifacts_before_replaying_audit(tmp_path,monkeypatch):
    from clasher.rl import native_public_calibration as calibration
    artifact=tmp_path/'raw.json';artifact.write_text('raw measurements')
    source_file=tmp_path/'projection.py';source_file.write_text('original source')
    receipt=NativeCalibrationReceipt(run_directory=str(tmp_path),
        source_pins={str(source_file):calibration.sha_file(source_file)},
        artifact_pins={str(artifact):calibration.sha_file(artifact)},
        ruleset_sha256=('0'*64,),catalog_sha256='0'*64,frame_count=1,owner_packet_count=2,
        jobs=({},),checked_channels=(),missing_channels=(),limitations=())
    path=tmp_path/'receipt.json';path.write_text(receipt.model_dump_json())
    calls=[]
    def replay(directory):
        calls.append(directory)
        return receipt
    monkeypatch.setattr(calibration,'audit_saved_run',replay)
    assert verify_calibration_receipt(path)==receipt
    assert len(calls)==1
    artifact.write_text('changed measurements')
    with pytest.raises(ValueError,match='binding changed'):
        verify_calibration_receipt(path)
    assert len(calls)==1
