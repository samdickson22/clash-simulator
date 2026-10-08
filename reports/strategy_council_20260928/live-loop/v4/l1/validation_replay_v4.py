"""Guarded full-validation fleet replay; no selection seal or heldout entry.

Output payloads and completion journal are separate: the journal timestamp is
measured AFTER payload JSON serialization, write and flush. Scoring must use the
journal's availability, never the runtime's inner compute-only timestamp.
"""
import argparse
import json
import math
from pathlib import Path
import time

from validation_admission_v4 import read, sha, validate_run


def threshold_options(global_threshold, mapping=None):
    """Registered event configuration; fitting/proposal provenance is separate."""
    grid=[i/10 for i in range(1,10)]
    if type(global_threshold) not in (int,float) or global_threshold not in grid:
        raise ValueError('Registered global threshold required')
    values={'default':global_threshold} if mapping is None else mapping
    if (not isinstance(values,dict) or values.get('default')!=global_threshold
            or any(not isinstance(k,str) or not k or k.strip()!=k for k in values)
            or any(type(v) not in (int,float) or v not in grid for v in values.values())):
        raise ValueError('Registered per-card thresholds with matching default required')
    return dict(values)


def frame_times(frames):
    if not frames:
        raise ValueError('Empty validation episode')
    times = []
    for i, frame in enumerate(frames):
        value = frame['produced_at']
        if (type(frame['seq']) is not int or frame['seq'] != i
                or isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value)):
            raise ValueError('Invalid frame identity/production timestamp')
        times.append(value)
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Nonchronological validation frames')
    return [(value-times[0])*1000 for value in times]


def replay_episode(runtime, cache, episode, frames, emit, journal, *, clock=time.perf_counter):
    """FIFO diagnostic at original production times; every frame, no dropping.

    Cache blocks are decoded once, and their loading cost is charged to their
    first frame. Only the current image/public time reaches pixel inference.
    emit must serialize/write/flush before returning. journal records completion
    separately; journal bookkeeping is charged to the following service interval.
    """
    times = frame_times(frames)
    block_size = cache.index[episode]['block_size']
    ready = times[0]
    started = clock()
    block = None
    for i, stamp in enumerate(times):
        if i % block_size == 0:
            block = cache.get(episode, list(range(i, min(i+block_size, len(times)))), raw=True)
        result = runtime.step(block[i % block_size], episode, stamp)
        emit(dict(source_seq=i, payload=result))
        finished = clock()
        service = (finished-started)*1000
        if not math.isfinite(service) or service < 0:
            raise ValueError('Invalid measured service duration')
        ready = max(ready, stamp)+service
        started = finished
        journal(dict(episode_id=episode, source_seq=i, timestamp_ms=stamp,
                     service_ms=service, available_timestamp_ms=ready))
    return dict(frames=len(times), final_available_timestamp_ms=ready)


def completed_predictions(outputs, completions, *, episode, expected_frames, calibration):
    """Join a complete episode to the scorer ABI using journal availability.

    Pure adapter: the file-backed caller must authenticate replay hashes and
    validation membership first. Empty calibration is required here because
    existence_q is a raw sigmoid only in that case; isotonic fitting must not
    accidentally consume already calibrated probabilities as raw scores.
    """
    if calibration != {}:
        raise ValueError('Raw-score adapter requires uncalibrated replay')
    if not isinstance(episode, str) or not episode or type(expected_frames) is not int or expected_frames < 1:
        raise ValueError('Complete episode identity/count required')
    outputs, completions = list(outputs), list(completions)
    if len(outputs) != expected_frames or len(completions) != expected_frames:
        raise ValueError('Incomplete replay payload/completion population')
    def number(row, key):
        value = row[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Invalid numeric replay field: '+key)
        return value
    predictions = []
    ready, previous_stamp = 0., None
    for i, (output, completion) in enumerate(zip(outputs, completions)):
        if any(type(row.get('source_seq')) is not int or row['source_seq'] != i for row in (output, completion)):
            raise ValueError('Missing, duplicate or reordered replay frame')
        payload = output['payload']
        if payload.get('episode_id') != episode or completion.get('episode_id') != episode:
            raise ValueError('Episode mismatch in replay join')
        stamp = number(completion, 'timestamp_ms')
        if (number(payload, 'timestamp_ms') != stamp or (i == 0 and stamp != 0)
                or (previous_stamp is not None and stamp <= previous_stamp)):
            raise ValueError('Replay production clock mismatch')
        service = number(completion, 'service_ms')
        available = number(completion, 'available_timestamp_ms')
        if service < 0 or not math.isclose(available, max(ready, stamp)+service, rel_tol=0, abs_tol=1e-6):
            raise ValueError('Completion journal violates measured FIFO recurrence')
        ready, previous_stamp = available, stamp
        for candidate in payload['event_candidates']:
            if not isinstance(candidate.get('card'), str) or not candidate['card']:
                raise ValueError('Missing candidate card')
            if type(candidate.get('side')) is not int or candidate['side'] not in (0, 1):
                raise ValueError('Invalid native side')
            execution = number(candidate, 'execution_timestamp_ms')
            score = number(candidate, 'existence_q')
            if not stamp-1500-1e-6 <= execution <= stamp+1e-6 or not 0 <= score <= 1:
                raise ValueError('Invalid execution age or raw score')
            predictions.append(dict(episode_id=episode, source_seq=i, kind='card_play',
                card=candidate['card'], side=candidate['side'], score=score,
                x_tiles=number(candidate, 'x_tiles'), y_tiles=number(candidate, 'y_tiles'),
                execution_timestamp_ms=execution, available_timestamp_ms=available))
    return predictions


def run(args):
    # Authenticate producer completion/full formal fit before any pixel access.
    readiness = validate_run(args.run, args.source, args.split, args.phase_state, args.phase_exit)
    if not 1 <= args.epoch <= 24 or args.threshold not in [i/10 for i in range(1, 10)]:
        raise ValueError('Registered epoch and threshold grid required')
    body_threshold=getattr(args,'body_threshold',.5)
    if type(body_threshold) not in (int,float) or body_threshold not in [i/10 for i in range(1,10)]:
        raise ValueError('Registered body threshold grid required')
    map_path=getattr(args,'threshold_map',None)
    map_sha=sha(map_path) if map_path is not None else None
    mapping=read(map_path) if map_path is not None else None
    if map_path is not None and not isinstance(mapping,dict):raise ValueError('Threshold map must be a JSON object')
    thresholds=threshold_options(args.threshold,mapping)
    replay_mode='combined' if map_path is not None else 'grid'
    if args.output.exists():
        raise ValueError('Fresh replay output required; retain interrupted attempts')
    model_root = args.run/'model'
    fit = read(model_root/'manifest.json')
    cache_root = Path(fit['pixel_cache'])
    receipts, frames = [], {}
    for episode, digest in sorted(readiness['validation_receipt_sha256'].items()):
        folder = args.source/episode
        if sha(folder/'receipt.json') != digest:
            raise ValueError('Validation receipt changed')
        receipt = read(folder/'receipt.json')
        if receipt['episode'] != episode or receipt['split'] != 'validation':
            raise ValueError('Validation isolation failure')
        if sha(folder/'frames.jsonl') != receipt['files']['frames.jsonl']:
            raise ValueError('Validation frame metadata changed')
        rows = [json.loads(line) for line in (folder/'frames.jsonl').read_text().splitlines()]
        frame_times(rows)
        if len(rows) != receipt['frames']:
            raise ValueError('Incomplete validation frame population')
        frames[episode] = rows
        receipts.append(dict(receipt, receipt_sha256=digest))
    from pixel_cache import PixelCache
    if fit.get('formal_cache_union') is True:
        from formal_union_v4 import open_formal_union
        connection=getattr(args,'cache_union',None)
        if connection is None:raise ValueError('Formal union replay requires live pinned cache connections')
        cache=open_formal_union(args.source,args.split,args.phase_state,args.phase_exit,
                                args.run/'admission.json',connection)
        if cache.provenance!=fit['cache_union_provenance']:
            cache.close();raise ValueError('Replay cache differs from measured formal union')
    else:
        cache = PixelCache(cache_root, receipts)  # Full payload SHA/equality verification.
    import cv2
    import torch
    from clasher.data import CardDataLoader
    from clasher.vision.l1_v4 import PerceptionV4, PixelPerception
    torch.set_num_threads(1)
    cv2.setNumThreads(1)
    free, _ = torch.cuda.mem_get_info()
    if free < 16*1024**3:
        raise RuntimeError('Need 16GiB free before replay')
    torch.cuda.set_per_process_memory_fraction(.65)
    checkpoint = model_root/f'epoch-{args.epoch}.pt'
    if sha(checkpoint) != readiness['checkpoint_sha256'][str(args.epoch)]:
        raise ValueError('Checkpoint changed after admission')
    state = torch.load(checkpoint, map_location='cpu', weights_only=True)
    if not set(thresholds)<=set(state['cards'])|{'default'}:
        raise ValueError('Threshold map contains card outside fitted vocabulary')
    if map_path is not None and sha(map_path)!=map_sha:
        raise ValueError('Threshold map changed during admission')
    model = PerceptionV4(len(state['cards']), len(state['bodies']))
    model.load_state_dict(state['model'])
    loader = CardDataLoader()
    spells = [n for n in state['cards'] if loader.get_card(n)._raw_entry['id']//1000000 == 28]
    runtime = PixelPerception(model, state['cards'], state['bodies'], spells,
                              thresholds, {}, device='cuda',body_threshold=body_threshold)
    args.output.mkdir()
    def write_json(path, value):
        with path.open('x') as f:
            json.dump(value, f, indent=2, allow_nan=False)
            f.write('\n')
    manifest = dict(schema='clasher.v4.validation-replay.v1', epoch=args.epoch,
        threshold=args.threshold, body_threshold=body_threshold, readiness=readiness, precision='fp32', device='cuda',
        replay_mode=replay_mode, event_thresholds=thresholds, threshold_map_sha256=map_sha,
        cache_index_sha256={r['episode']:sha(cache_root/r['episode']/'index.json') for r in receipts},
        driver_sha256=sha(Path(__file__)), spells=spells, calibration={},
        timing='completion journal after payload write/flush; FIFO; cache loading included',
        scope='fleet validation diagnostic; native 20 FPS; no frame dropping',
        limitations='Truth mapping, threshold/epoch selection, body calibration and Mac replay pending',
        heldout_payloads_opened=False, selection_seal=False)
    write_json(args.output/'manifest.json', manifest)
    summaries = {}
    for episode in sorted(frames):
        with (args.output/f'{episode}-outputs.jsonl').open('x') as outputs, \
             (args.output/f'{episode}-completion.jsonl').open('x') as completions:
            def emit(row):
                outputs.write(json.dumps(row, allow_nan=False)+'\n')
                outputs.flush()
            def journal(row):
                completions.write(json.dumps(row, allow_nan=False)+'\n')
                completions.flush()
            summaries[episode] = replay_episode(runtime, cache, episode, frames[episode], emit, journal)
        print(json.dumps(dict(validation_episode_complete=episode,
            matches_completed=len(summaries),matches_total=len(frames),
            frames_completed=sum(r['frames'] for r in summaries.values()),time=time.time())),flush=True)
    write_json(args.output/'complete.json', dict(manifest_sha256=sha(args.output/'manifest.json'),
        episodes=summaries, files_sha256={p.name:sha(p) for p in sorted(args.output.glob('*.jsonl'))},
        heldout_payloads_opened=False, selection_seal=False))
    if fit.get('formal_cache_union') is True:cache.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('run', 'source', 'split', 'phase-state', 'phase-exit', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--epoch', type=int, required=True)
    parser.add_argument('--threshold', type=float, required=True)
    parser.add_argument('--body-threshold', type=float, default=.5)
    parser.add_argument('--cache-union',type=Path,help='Live connections to the exact cache union used by formal fit')
    parser.add_argument('--threshold-map',type=Path,help='Combined replay: JSON per-card map including default; no selection authority')
    run(parser.parse_args())
