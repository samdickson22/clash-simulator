from copy import deepcopy
import hashlib
import json

import pytest

from clasher.rl.native_frame_storage import compact_native_frame, validate_native_frame_storage


def frame():
    return {
        'ordinary': {'tick': 5, 'objects': [{'id': 8}]},
        'rich': {'schema': 'native-rich-telemetry.v3', 'ok': True, 'truncated': False,
                 'objects': [{'id': 8, 'phaseRuntime': {'events': ['body field stays']}}],
                 'players': [{'owner': 0}], 'provenance': {'build': 'pinned'},
                 'capabilities': {'visible': True}, 'unknownFutureField': {'events': [99]},
                 'phaseRuntime': {'complete': True, 'nextSequence': 3, 'events': [1, 2]},
                 'combatEvents': {'complete': True, 'events': []}},
        'level_source': {'ordinary': {'tick': 5}, 'levels': {8: 11, 100: 12},
                         'attestation': {'library': 'pinned'}, 'reader_sha256': 'a' * 64},
    }


def test_compactor_preserves_all_non_event_fields_and_owns_storage():
    original = frame(); frozen = deepcopy(original)
    compact = compact_native_frame(original)
    record = validate_native_frame_storage(compact)
    assert original == frozen
    assert compact['ordinary'] == original['ordinary']
    assert compact['level_source'] == original['level_source']
    for key in original['rich']:
        if key in ('phaseRuntime', 'combatEvents'):
            assert compact['rich'][key] == {**original['rich'][key], 'events': None}
        else:
            assert compact['rich'][key] == original['rich'][key]
    assert record.omitted_events['phaseRuntime'].count == 2
    assert record.omitted_events['combatEvents'].count == 0
    encoded = json.dumps(original, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
    assert record.full_frame_json_sha256 == hashlib.sha256(encoded).hexdigest()
    assert record.full_frame_json_bytes == len(encoded)
    original['rich']['objects'][0]['id'] = 9
    assert compact['rich']['objects'][0]['id'] == 8
    assert compact_native_frame(compact) == compact


def test_storage_roundtrip_is_stable_for_level_map_keys_and_json_order():
    compact = compact_native_frame(frame())
    serialized = json.loads(json.dumps(compact, sort_keys=True))
    assert validate_native_frame_storage(serialized).retained_frame_json_sha256 == compact['storage_provenance']['retained_frame_json_sha256']
    before = compact['storage_provenance']['full_frame_json_sha256']
    after = compact_native_frame(json.loads(json.dumps(frame())))['storage_provenance']['full_frame_json_sha256']
    assert before == after


@pytest.mark.parametrize('fault', ['body', 'levels', 'empty-events', 'missing-events', 'unknown-drop', 'sha', 'source-sha', 'schema'])
def test_storage_corruption_rejected(fault):
    compact = compact_native_frame(frame())
    if fault == 'body': compact['rich']['objects'][0]['id'] = 9
    elif fault == 'levels': compact['level_source']['levels'][8] = 10
    elif fault == 'empty-events': compact['rich']['phaseRuntime']['events'] = []
    elif fault == 'missing-events': del compact['rich']['phaseRuntime']['events']
    elif fault == 'unknown-drop': compact['storage_provenance']['omitted_events']['unknownFutureField'] = compact['storage_provenance']['omitted_events']['phaseRuntime']
    elif fault == 'sha': compact['storage_provenance']['retained_frame_json_sha256'] = '0' * 64
    elif fault == 'source-sha': compact['storage_provenance']['producer_source_sha256'] = 'bad'
    else: compact['storage_provenance']['schema_version'] = 'unknown'
    with pytest.raises(ValueError): validate_native_frame_storage(compact)


def test_legacy_full_frame_and_unknown_native_trace_are_not_invented():
    full = frame()
    full['rich']['visibilityRuntime'] = {'events': None, 'capability': 'unknown'}
    assert validate_native_frame_storage(full) is None
    compact = compact_native_frame(full)
    assert compact['rich']['visibilityRuntime'] == full['rich']['visibilityRuntime']
    assert 'visibilityRuntime' not in compact['storage_provenance']['omitted_events']


def test_unknown_native_schema_fails_before_omission():
    full = frame(); full['rich']['schema'] = 'new-schema'
    with pytest.raises(ValueError, match='unsupported'): compact_native_frame(full)


@pytest.mark.parametrize('corrupt_receipt', [False, True])
def test_transport_checks_keep_the_same_result_after_compaction(tmp_path, corrupt_receipt):
    import gzip
    from clasher.data import CardDataLoader
    from clasher.rl.readiness_transport import audit_native_transport_row, compact_transport_snapshot
    from pathlib import Path

    fixtures = Path(__file__).parent / 'fixtures'
    snapshots = json.loads((fixtures / 'native_hand_refill_15_535_86.json').read_text())['snapshots']
    before = next(item for item in snapshots if item['tick'] == 110)
    after = next(item for item in snapshots if item['tick'] == 111)
    data = tmp_path / 'gamedata.json'
    data.write_bytes(gzip.decompress((fixtures / 'native_gamedata_15_535_86_daa58b28.json.gz').read_bytes()))
    loader = CardDataLoader(data)
    transport = {
        'tick': 110, 'before': compact_transport_snapshot(before), 'after': compact_transport_snapshot(after),
        'selected': [{'owner': owner, 'action': 2304, 'name': None, 'cost': None, 'xy': None} for owner in (0, 1)],
        'receipts': [], 'commands': [],
    }
    # Saved real waiting/refill transport inputs, inside a synthetic storage envelope.
    full = frame(); full['ordinary'] = before; full['level_source']['ordinary'] = before
    decision = {'tick': 110, 'actions': [2304, 2304], 'native_frame': full}
    compact_decision = {**decision, 'native_frame': compact_native_frame(full)}
    if corrupt_receipt:
        transport['after']['tick'] = 112
        for candidate in (decision, compact_decision):
            with pytest.raises(ValueError, match='one tick'):
                audit_native_transport_row(transport, candidate, loader)
    else:
        audit_native_transport_row(transport, decision, loader)
        audit_native_transport_row(transport, compact_decision, loader)
