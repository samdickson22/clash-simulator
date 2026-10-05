"""Offline full-versus-compact equivalence audit over existing native decisions."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time
import zipfile

import numpy as np

from clasher.data import CardDataLoader
from clasher.rl.native_frame_storage import compact_native_frame, validate_native_frame_storage
from clasher.rl.native_public_calibration import _sources, audit_native_frame, sha_file
from clasher.rl.native_public_observation import (
    PUBLIC_REFERENCE_CARDS, NativeProjectileCatalog, NativePublicObservationAdapter,
    NativePublicScope, public_reference_builder,
)
from clasher.rl.own_card_history import AcceptedOwnPlay
from clasher.rl.readiness_execution import packet_sha
from clasher.rl.readiness_transport import compact_transport_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path.cwd().resolve()
    sources_before = _sources()
    sources_before[str(Path(__file__).resolve())] = sha_file(Path(__file__))
    with zipfile.ZipFile(args.output / 'audit-source.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, expected in sorted(sources_before.items()):
            path = Path(filename); data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('audit source changed while archiving')
            archive.writestr(str(path.relative_to(root)), data)
    plan_path = args.run_directory / 'execution-plan.json'
    plan = json.loads(plan_path.read_text())
    catalog_path = Path(plan['catalog_path'])
    catalog = NativeProjectileCatalog.from_csv(catalog_path, expected_sha256=plan['catalog_sha256'])
    artifacts = {str(plan_path.resolve()): sha_file(plan_path), str(catalog_path): sha_file(catalog_path)}
    jobs = []; started = time.perf_counter(); total_frames = 0
    for directory in sorted(args.run_directory.glob('job-*')):
        result_path = directory / 'result.json'; result = json.loads(result_path.read_text())
        if result['job']['engine'] != 'reference':
            continue
        stream_path = directory / 'decisions.jsonl.gz'
        source_sha = sha_file(stream_path)
        if source_sha != result['decisions_sha256']:
            raise ValueError('original decision stream hash mismatch')
        artifacts[str(result_path.resolve())] = sha_file(result_path)
        artifacts[str(stream_path.resolve())] = source_sha
        binding = next(c for c in plan['captures'] if c['family_id'] == result['job']['family_id'])
        capture = Path(binding['capture_path']); data_path = capture / 'gamedata.json'
        if sha_file(data_path) != binding['input_hashes']['gamedata.json']:
            raise ValueError('original capture data hash mismatch')
        artifacts[str(data_path)] = sha_file(data_path)
        prefix_path = capture / 'result.json'; artifacts[str(prefix_path)] = sha_file(prefix_path)
        loader = CardDataLoader(data_path)
        builder = public_reference_builder(loader, catalog, public_contract_version=4)
        adapter = NativePublicObservationAdapter(
            builder, NativePublicScope('15.535.86', artifacts[str(data_path)]),
            card_names=PUBLIC_REFERENCE_CARDS, projectile_catalog=catalog,
        )
        history = [None, None]
        for command in json.loads(prefix_path.read_text())['commands']:
            if command['submitted_tick'] < binding['root_tick']:
                if command['native_acceptance_spend_evidence'] is not True:
                    raise ValueError('prefix lacks original acceptance evidence')
                history[command['owner']] = AcceptedOwnPlay(command['name'], command['cost'])
        outdir = args.output / directory.name; outdir.mkdir()
        compact_path = outdir / 'decisions.compact.jsonl.gz'
        count = raw_json_bytes = compact_json_bytes = 0
        first_tick = last_tick = None; frame_hashes = hashlib.sha256()
        with gzip.open(stream_path, 'rt') as source, gzip.open(compact_path, 'xt', compresslevel=9) as sink:
            for line in source:
                row = json.loads(line); full = row['native_frame']
                tick = row['tick']
                if tick != (binding['root_tick'] if count == 0 else last_tick + 5):
                    raise ValueError('original stream skips a decision interval')
                compact = compact_native_frame(full)
                record = validate_native_frame_storage(compact)
                if compact['ordinary'] != full['ordinary'] or compact['level_source'] != full['level_source']:
                    raise ValueError('compaction changed an ordinary or level source channel')
                if compact_transport_snapshot(compact['ordinary']) != compact_transport_snapshot(full['ordinary']):
                    raise ValueError('compaction changed command transport inputs')
                baseline = audit_native_frame(full, builder=builder, adapter=adapter, catalog=catalog, own_history=history)
                candidate = audit_native_frame(compact, builder=builder, adapter=adapter, catalog=catalog, own_history=history)
                expected = row['public_sha256']
                if [packet_sha(view) for view in baseline[0]] != expected or [packet_sha(view) for view in candidate[0]] != expected:
                    raise ValueError('public packets differ from each other or the archived packet hashes')
                for a, b in zip(baseline[1], candidate[1], strict=True):
                    np.testing.assert_array_equal(a, b)
                if baseline[2] != candidate[2] or baseline[2] != row['level_coverage_by_owner']:
                    raise ValueError('calibration coverage changed')
                for owner, (view, mask) in enumerate(zip(baseline[0], baseline[1], strict=True)):
                    action = row['actions'][owner]
                    if type(action) is not int or not 0 <= action < len(mask) or not mask[action]:
                        raise ValueError('archived action is not public legal')
                    if action < 2304:
                        name = builder.card_name_for_token_id(int(view.observation.hand_ids[action // 576]))
                        history[owner] = AcceptedOwnPlay(name, int(loader.get_card(name).mana_cost))
                encoded = json.dumps({**row, 'native_frame': compact}, separators=(',', ':'), allow_nan=False) + '\n'
                sink.write(encoded)
                raw_json_bytes += len(line.encode()); compact_json_bytes += len(encoded.encode())
                frame_hashes.update((record.full_frame_json_sha256 + '\n').encode())
                count += 1; total_frames += 1; first_tick = tick if first_tick is None else first_tick; last_tick = tick
                if count % 100 == 0:
                    print(json.dumps({'job': directory.name, 'frames': count, 'total_frames': total_frames,
                                      'seconds': time.perf_counter() - started}), flush=True)
                last_full = full
        if count == 0:
            raise ValueError('empty native stream')
        # One full last-decision frame is a separate diagnostic copy. It is not
        # labelled terminal: the archived last decision precedes finalization.
        last_path = outdir / 'full-last-decision-frame.json.gz'
        with gzip.open(last_path, 'xt', compresslevel=9) as sink:
            sink.write(json.dumps(last_full, separators=(',', ':'), allow_nan=False) + '\n')
        jobs.append({
            'job': directory.name, 'frames': count, 'first_tick': first_tick, 'last_tick': last_tick,
            'source_path': str(stream_path.resolve()), 'source_sha256': source_sha,
            'source_gzip_bytes': stream_path.stat().st_size, 'source_json_bytes': raw_json_bytes,
            'compact_path': str(compact_path.resolve()), 'compact_sha256': sha_file(compact_path),
            'compact_gzip_bytes': compact_path.stat().st_size, 'compact_json_bytes': compact_json_bytes,
            'full_frame_digest_sequence_sha256': frame_hashes.hexdigest(),
            'full_last_decision_path': str(last_path.resolve()), 'full_last_decision_sha256': sha_file(last_path),
            'full_last_decision_gzip_bytes': last_path.stat().st_size,
            'public_packet_hashes_match_archive': True, 'action_masks_equal': True,
            'calibration_checks_and_coverage_equal': True, 'transport_inputs_equal': True,
        })
    if total_frames != 1406:
        raise ValueError(f'expected all 1406 v6 native frames, observed {total_frames}')
    sources_after = _sources(); sources_after[str(Path(__file__).resolve())] = sha_file(Path(__file__))
    changed_sources = sorted(name for name in sources_before.keys() | sources_after.keys()
                             if sources_before.get(name) != sources_after.get(name))
    changed_artifacts = [name for name, expected in artifacts.items() if sha_file(Path(name)) != expected]
    compact_total = sum(job['compact_gzip_bytes'] for job in jobs)
    original_total = sum(job['source_gzip_bytes'] for job in jobs)
    receipt = {
        'schema': 'native-frame-storage-equivalence.v1', 'status': 'passed' if not changed_sources and not changed_artifacts else 'source_or_input_drift',
        'frames': total_frames, 'owner_packets_per_format': total_frames * 2,
        'native_calls': 0, 'gameplay_fitting': False, 'new_calibration_receipt': False,
        'source_pins': sources_before, 'source_changes': changed_sources, 'input_pins': artifacts,
        'input_changes': changed_artifacts, 'audit_source_archive_sha256': sha_file(args.output / 'audit-source.zip'),
        'jobs': jobs, 'elapsed_seconds': time.perf_counter() - started,
        'source_gzip_bytes': original_total, 'compact_gzip_bytes': compact_total,
        'compressed_fraction_retained': compact_total / original_total,
        'tier_a_512_native_branches_estimated_bytes': max(job['compact_gzip_bytes'] + job['full_last_decision_gzip_bytes'] for job in jobs) * 512,
        'estimate_scope': '512 repetitions of the larger measured branch plus one full last-decision snapshot each; excludes prefix/transport/source archives and checkpoints; not a worst-case bound for other games.',
        'limitations': [
            'Full parsed-frame/event digests commit omitted traces; they do not recover them or hash original socket bytes.',
            'No native API, engine, observation acquisition, clock or decision interval changed.',
            'V6 lacks independent command-acceptance journals; transport input equality is proved, not fresh execution acceptance.',
            'No bandwidth, native generation speed, camera calibration, fresh admission or playing-strength claim.',
        ],
    }
    with (args.output / 'receipt.json').open('x') as sink:
        json.dump(receipt, sink, indent=2, allow_nan=False); sink.write('\n')
    print(json.dumps({key: receipt[key] for key in ('status', 'frames', 'elapsed_seconds', 'source_gzip_bytes', 'compact_gzip_bytes', 'tier_a_512_native_branches_estimated_bytes')}), flush=True)
    if receipt['status'] != 'passed':
        raise ValueError('source/input drift invalidates a stable equivalence claim; evidence retained')


if __name__ == '__main__':
    main()
