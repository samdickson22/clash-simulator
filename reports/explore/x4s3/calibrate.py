"""X4S-3 (exploration, NEVER ADOPTABLE): label-free R3 gate calibration of a final-EMA student.

Exactly the calibration half of exit-r3/operations/offline.py: all 8,088 eligible roots of the
ExIt R1 held-out64 slice (manifest 0ecce0f0), GPU float32 with TF32 off, batches of 64,
proposals.calibrate (nearest 34.6% deterministic root play; midpoints; smaller threshold on
ties). No teacher label, recall, regret or outcome is computed or used.
"""
import argparse, hashlib, json, subprocess, time
from pathlib import Path
import numpy as np
import torch
from exit_r3.student import RootTeacherStore
from proposals import load_student, outputs, rank_actions, calibrate

HELDOUT = Path('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1/heldout-corpus')
HELDOUT_SHA = '0ecce0f0f410ff7f1093994cdb62b44c4c141c3a4bddb237cf1427b0a512818f'


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True); ap.add_argument('--checkpoint', type=Path, required=True)
    ap.add_argument('--assets', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--expect-threshold', type=float)
    a = ap.parse_args()
    assert not a.out.exists()
    start = time.monotonic()
    torch.set_num_threads(1); torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    assert sha(HELDOUT/'manifest.json') == HELDOUT_SHA
    store = RootTeacherStore(HELDOUT, a.assets); assert len(store) == 8088
    games = np.asarray(store.arrays['perspective_ids'][store.root_indices])
    assert set(map(int, np.unique(games))) == {4503601207370496+i for i in range(64)}
    ck = torch.load(a.checkpoint, map_location='cpu', weights_only=True)
    meta = dict(step=int(ck['state']['step']), width=ck['config']['width'], seed=ck['args']['seed'], steps=ck['args']['steps'],
                advantage_weight=ck['args']['advantage_weight'], teacher_manifests=ck['hashes']['teacher_manifests'],
                init_checkpoint=ck['hashes']['init_checkpoint'], assets=ck['hashes']['assets'])
    assert meta['step'] == meta['steps'] and meta['width'] == 192 and meta['advantage_weight'] == 0
    del ck
    policy = load_student(a.checkpoint); policy.model.cuda().eval()
    probabilities = []; legal = []
    for s in range(0, len(store), 64):
        b, _ = store.batch(np.arange(s, min(s+64, len(store))))
        pplay, ranks = outputs(policy.model, {k: v.cuda() for k, v in b.items()})
        probabilities.extend(pplay.cpu().numpy().tolist())
        for row, mask in zip(ranks.cpu().numpy(), b['action_mask'].numpy()):
            legal.append(bool(len(rank_actions(row, mask))))
    probabilities = np.asarray(probabilities); legal = np.asarray(legal)
    threshold = calibrate(probabilities, legal)
    played = legal & (probabilities >= threshold)
    result = dict(id=a.id, threshold=threshold, target_play_rate=.346, actual_play_rate=float(played.mean()), rows=len(probabilities),
                  legal_rows=int(legal.sum()), checkpoint=str(a.checkpoint), checkpoint_sha256=sha(a.checkpoint),
                  heldout_manifest_sha256=HELDOUT_SHA, checkpoint_meta=meta, labels_not_used_for_threshold=True,
                  exploratory_calibration_reuse=True, device='CUDA float32, TF32 off', torch=torch.__version__,
                  gpu_wall_seconds=time.monotonic()-start, label='X4S-3 exploration, NEVER ADOPTABLE',
                  utc=subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip())
    if a.expect_threshold is not None:
        result['expected_threshold'] = a.expect_threshold; result['threshold_reproduced'] = threshold == a.expect_threshold
    a.out.write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result), flush=True)
    if a.expect_threshold is not None and threshold != a.expect_threshold: raise SystemExit(1)


if __name__ == '__main__': main()
