"""Frozen pixel-only replay on the eight training-split dev matches.

Native truth is used only by scoring after channel.step, never as model input.
Cache payloads and sources remain read-only. Run detached/nice 10 on 127x03.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time
import cv2
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'src'))
from clasher.live.tower_channel import TowerChannel, SLOT_NAMES
from extract import decode, rows, sha, SPLIT_SHA


def run(a):
    cv2.setNumThreads(1)
    freeze = json.loads(a.freeze.read_text())
    for path,digest in freeze['files_sha256'].items():
        if sha(Path(path)) != digest:
            raise ValueError('Frozen model/source changed')
    manifest = json.loads((a.crops/'manifest.json').read_text())
    if manifest['split_sha256'] != SPLIT_SHA or set(manifest['fit']) & set(manifest['dev']):
        raise ValueError('Study split mismatch')
    if sha(a.split) != SPLIT_SHA:
        raise ValueError('Formal split changed')
    members = {r['seed']:r for r in json.loads(a.split.read_text())['matches']}
    counts = {s:Counter() for s in SLOT_NAMES}
    confusion = {s:{t:Counter() for t in ['alive','destroyed','unknown']} for s in SLOT_NAMES}
    latencies, pins = [], {}
    channel = TowerChannel()
    a.output.mkdir(parents=True,exist_ok=True)
    with (a.output/'predictions.jsonl').open('x') as output:
        for ep in manifest['dev']:
            if members[int(ep.rsplit('-',1)[-1])]['split'] != 'train':
                raise ValueError('Forbidden dev membership')
            folder = a.source/ep
            receipt = json.loads((folder/'receipt.json').read_text())
            idx = json.loads((a.cache/ep/'index.json').read_text())
            if receipt['split'] != 'train' or idx['split'] != 'train' or idx['receipt_sha256'] != sha(folder/'receipt.json'):
                raise ValueError('Dev provenance changed')
            # Verify read-only raw cache bytes, rather than trusting index names.
            if sha(a.cache/ep/'raw.zst') != idx['sha256']['raw.zst']:
                raise ValueError('Raw cache checksum differs')
            frames = rows(folder/'frames.jsonl')
            truth = json.loads((a.crops/(ep+'.json')).read_text())
            known = {(r['ordinal'],r['slot']):r['hp'] for r in truth['rows'] if r['hp'] is not None}
            pins[ep] = {k:v for k,v in truth.items() if k != 'rows'}
            manual_ordinals = {truth['rows'][0]['ordinal'],truth['rows'][-1]['ordinal']}
            with (a.cache/ep/'raw.zst').open('rb') as raw:
                for block in idx['blocks']:
                    offset,size = block['raw.zst']
                    raw.seek(offset)
                    images = decode(raw.read(size),block['count'])
                    for j,image in enumerate(images):
                        i = block['start']+j
                        stamp = (frames[i]['produced_at']-frames[0]['produced_at'])*1000
                        start = time.perf_counter_ns()
                        measured = channel.step(image,ep,stamp)
                        elapsed = (time.perf_counter_ns()-start)/1e6
                        if i >= 16:
                            latencies.append(elapsed)
                        for s,obs in enumerate(measured):
                            c = counts[obs.slot]
                            c['all_frames'] += 1
                            c['all_'+obs.state] += 1
                            hp = known.get((i,s))
                            if hp is not None:
                                t = 'alive' if hp > 0 else 'destroyed'
                                confusion[obs.slot][t][obs.state] += 1
                                c['eligible_truth'] += 1
                                if obs.hp_known:
                                    c['number_read'] += 1
                                    c['number_exact'] += obs.hp == hp
                                    c['number_abs_error_sum'] += abs(obs.hp-hp)
                                if obs.hp_fraction is not None:
                                    err = abs(obs.hp_fraction-hp/(4824 if s%3 == 0 else 3052))
                                    c['bar_read'] += 1
                                    c['bar_abs_error_sum'] += err
                                    c['bar_within_5pct'] += err <= .05
                            if hp is not None or i in manual_ordinals or obs.state == 'destroyed':
                                from dataclasses import asdict
                                output.write(json.dumps(dict(episode=ep,ordinal=i,observation=asdict(obs),truth_hp=hp))+'\n')
            print(ep,len(frames),'frames complete',flush=True)
    t = np.array(latencies)
    result = dict(schema='clasher.public-tower-dev.v1', scope='8 disjoint training-split dev matches; never formal validation',
        manifest_sha256=sha(a.crops/'manifest.json'), freeze_sha256=sha(a.freeze), provenance=pins,
        native_confusion={s:{t:dict(c) for t,c in v.items()} for s,v in confusion.items()},
        metrics={s:dict(v) for s,v in counts.items()},
        latency_ms=dict(samples=len(t),mean=float(t.mean()),p50=float(np.median(t)),p95=float(np.quantile(t,.95)),
                        p99=float(np.quantile(t,.99)),max=float(t.max()),includes='all six crops, classifier, OCR/bar, confirmations and typed observations; excludes cache I/O; first 16 frames/match warmup excluded'),
        validation_payloads_opened=False,heldout_payloads_opened=False,dev_used_for_fitting=False)
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for n in ['source','cache','split','crops','freeze','output']:
        p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
