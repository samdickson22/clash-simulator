"""X4S-4 O-holdout diagnostic (PLAN r2 C6; descriptive only, never a gate; exploration, NEVER ADOPTABLE).

For each student (checkpoint + calibrated threshold) and each slice (the verified O-holdout packed batches
and the R1 held-out64 slice 0ecce0f0), over every scored root (RootTeacherStore):
  top1_agreement  student deterministic choice == W's best candidate (timed WAIT ids folded to 2304), where
                  the student's choice is its best-ranked legal play if P(play) >= threshold, else WAIT;
  gate_accuracy   (student plays) == (W's best is a play);
  listwise_ce     the frozen exit_r3 teacher_loss at T = 0.003, play weight 1, value weight 0 (row-weighted mean).
GPU float32, TF32 off, inference only. Runs only when no reporting phase is live. Writes diagnostic.json (O_EXCL).
"""
import argparse, hashlib, json, os, subprocess
from pathlib import Path
import numpy as np
import torch

HELDOUT = Path('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1/heldout-corpus')
HELDOUT_SHA = '0ecce0f0f410ff7f1093994cdb62b44c4c141c3a4bddb237cf1427b0a512818f'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


@torch.inference_mode()
def evaluate(policy, threshold, stores):
    from proposals import outputs, rank_actions
    from exit_r3.student import teacher_loss
    agree = gate_ok = n = 0; ce_sum = 0.
    for store in stores:
        for start in range(0, len(store), 64):
            b, y = store.batch(np.arange(start, min(start+64, len(store))))
            bb = {k: v.cuda() for k, v in b.items()}
            pplay, ranks = outputs(policy.model, bb)
            raw = policy.model(bb, torch.empty(0, dtype=torch.long, device='cuda'))
            yy = {k: (v.cuda() if torch.is_tensor(v) else v) for k, v in y.items()}
            m = len(y['action'])
            ce_sum += float(teacher_loss(raw, yy, .003, 1., 0.))*m
            acts, scores, valid = y['root_actions'].numpy(), y['root_scores'].numpy(), y['root_valid'].numpy()
            for i, (row, mask) in enumerate(zip(ranks.cpu().numpy(), b['action_mask'].numpy())):
                sc = np.where(valid[i], scores[i], -np.inf); best = int(acts[i][int(np.argmax(sc))]); best = 2304 if best >= 2304 else best
                order = rank_actions(row, mask)
                choice = int(order[0]) if len(order) and float(pplay[i]) >= threshold else 2304
                agree += choice == best; gate_ok += (choice < 2304) == (best < 2304); n += 1
    return dict(roots=n, top1_agreement=agree/max(1, n), gate_accuracy=gate_ok/max(1, n), listwise_ce=ce_sum/max(1, n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--students', type=Path, required=True, help='JSON {id: {checkpoint, checkpoint_sha256, threshold}}')
    ap.add_argument('--holdout', type=Path, nargs='+', required=True, help='verified O-holdout packed batch directories')
    ap.add_argument('--assets', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    if os.path.lexists(a.out): raise SystemExit('output exists')
    from proposals import load_student
    from exit_r3.student import RootTeacherStore
    torch.set_num_threads(1); torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    if sha(HELDOUT/'manifest.json') != HELDOUT_SHA: raise SystemExit('held-out64 manifest SHA')
    slices = {'O-holdout': [RootTeacherStore(d, a.assets) for d in a.holdout], 'R1-heldout64': [RootTeacherStore(HELDOUT, a.assets)]}
    students = json.loads(a.students.read_text()); out = {}
    for sid, s in students.items():
        if sha(s['checkpoint']) != s['checkpoint_sha256']: raise SystemExit(f'{sid} checkpoint SHA')
        policy = load_student(s['checkpoint']); policy.model.cuda().eval()
        out[sid] = {name: evaluate(policy, float(s['threshold']), st) for name, st in slices.items()}
        del policy; torch.cuda.empty_cache()
    body = dict(utc=subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip(), students=out,
                holdout=[str(d) for d in a.holdout], heldout64_sha256=HELDOUT_SHA, device='CUDA float32, TF32 off',
                label='X4S-4 O-holdout diagnostic; descriptive only; never a gate; exploration, NEVER ADOPTABLE')
    fd = os.open(a.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'w') as f: f.write(json.dumps(body, indent=2)+'\n')
    print(json.dumps(out))


if __name__ == '__main__':
    main()
