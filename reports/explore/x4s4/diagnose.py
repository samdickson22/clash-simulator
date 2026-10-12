"""X4S-4 O-holdout diagnostic (PLAN r3 C6; descriptive only, never a gate; exploration, NEVER ADOPTABLE).
r2 after Sol script review r1 (F9, F10, F15).

For each student (checkpoint + calibrated threshold) and each slice (the verified O-holdout packed batches
and the R1 held-out64 slice 0ecce0f0), over every scored root (RootTeacherStore):
  top1_agreement   student deterministic choice == W's best candidate (timed WAIT ids folded to 2304), where
                   the student's choice is its best-ranked legal play if P(play) >= threshold, else WAIT;
  gate_accuracy    (student plays) == (W's best is a play);
  listwise_ce      (PLAN §6, the diagnostic) per-root listwise cross-entropy of the factored student policy against
                   W's T = 0.003 targets, gate_ce + card_ce + tile_ce of the frozen exit_r3 teacher_loss terms,
                   averaged over roots with weight w = weight * supervised (play weight 1);
  frozen_objective the frozen training objective over ALL roots of the slice (Sol F15): sum(gate_ce*w)/sum(w) +
                   sum((card_ce+tile_ce)*w)/sum(w*play_mass), accumulated as global numerators/denominators, so
                   it is invariant to batch size and order. Each batch's per-row terms are cross-checked against the
                   frozen teacher_loss on that batch (relative 1e-4).
GPU float32, TF32 off, inference only. Exclusion (Sol F9): it first creates <job>/driver/DIAGNOSTIC.lock (O_EXCL,
with its pid; the driver dispatches no fit or reporting phase while the lock's pid lives), then refuses to run if any
reporting supervisor or fit process group from <job>/receipts is alive; the lock is removed at exit. Output is
confined below <job>/analysis/ or <job>/receipts/ and written once (O_EXCL, 0444).
"""
import argparse, hashlib, json, os, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import confine                                   # noqa: E402

HELDOUT = Path('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1/heldout-corpus')
HELDOUT_SHA = '0ecce0f0f410ff7f1093994cdb62b44c4c141c3a4bddb237cf1427b0a512818f'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


class CEAccumulator:
    """Global numerators/denominators of the frozen teacher objective and the per-root listwise CE (pure numpy)."""
    def __init__(self):
        self.gate_num = self.play_num = self.gate_den = self.play_den = self.joint_num = 0.0
        self.roots = 0

    def add(self, gate_ce, card_ce, tile_ce, w, play_mass):
        gate_ce, card_ce, tile_ce, w, play_mass = (np.asarray(x, np.float64) for x in (gate_ce, card_ce, tile_ce, w, play_mass))
        self.gate_num += float((gate_ce*w).sum()); self.play_num += float(((card_ce+tile_ce)*w).sum())
        self.gate_den += float(w.sum()); self.play_den += float((w*play_mass).sum())
        self.joint_num += float(((gate_ce+card_ce+tile_ce)*w).sum()); self.roots += len(w)

    def result(self):
        frozen = self.gate_num/max(self.gate_den, 1e-12) + self.play_num/max(self.play_den, 1e-12)
        return dict(listwise_ce=self.joint_num/max(self.gate_den, 1e-12), frozen_objective=frozen,
                    gate_den=self.gate_den, play_den=self.play_den)


def row_terms(raw, yy, temperature=.003):
    """Per-row gate/card/tile CE, w and play mass exactly as the frozen teacher_loss computes them (play_weight 1)."""
    import torch
    from exit_r3.student import teacher_targets, masked_log_softmax
    a = yy['root_actions'].long(); a = torch.where(a >= 2400, 2304, a)
    q = teacher_targets(yy, temperature)
    rows = torch.arange(len(a), device=a.device)[:, None]
    slot = (a//576).clamp(0, 3); tile = a % 576
    gate = torch.where(a == 2304, 0, torch.where(a == 2305, 2, 1))
    gp = masked_log_softmax(raw['gate'], raw['gate_mask']); cp = masked_log_softmax(raw['card'], raw['card_mask'])
    tp = masked_log_softmax(raw['tile'], raw['tile_mask'])
    w = yy['weight'].float()*yy['supervised'].float()
    play = (a < 2304).float()
    return (-(q*gp[rows, gate]).sum(-1), -(q*play*cp[rows, slot]).sum(-1), -(q*play*tp[rows, slot, tile]).sum(-1), w, (q*play).sum(-1))


def evaluate(policy, threshold, stores, batch=64):
    import torch
    from proposals import outputs, rank_actions
    from exit_r3.student import teacher_loss
    acc = CEAccumulator(); agree = gate_ok = n = 0; worst = 0.0
    with torch.inference_mode():
        for store in stores:
            for start in range(0, len(store), batch):
                b, y = store.batch(np.arange(start, min(start+batch, len(store))))
                bb = {k: v.cuda() for k, v in b.items()}
                pplay, ranks = outputs(policy.model, bb)
                raw = policy.model(bb, torch.empty(0, dtype=torch.long, device='cuda'))
                yy = {k: (v.cuda() if torch.is_tensor(v) else v) for k, v in y.items()}
                g, c, t, w, pm = row_terms(raw, yy)
                frozen = float(teacher_loss(raw, yy, .003, 1., 0.))
                mine = float((g*w).sum()/(w.sum().clamp_min(1e-12)) + ((c+t)*w).sum()/((w*pm).sum().clamp_min(1e-12)))
                worst = max(worst, abs(mine-frozen)/max(1e-6, abs(frozen)))
                if worst > 1e-4: raise SystemExit(f'per-row terms differ from the frozen teacher_loss ({mine} vs {frozen})')
                acc.add(*(x.double().cpu().numpy() for x in (g, c, t, w, pm)))
                acts, scores, valid = y['root_actions'].numpy(), y['root_scores'].numpy(), y['root_valid'].numpy()
                for i, (row, mask) in enumerate(zip(ranks.cpu().numpy(), b['action_mask'].numpy())):
                    sc = np.where(valid[i], scores[i], -np.inf); best = int(acts[i][int(np.argmax(sc))]); best = 2304 if best >= 2304 else best
                    order = rank_actions(row, mask)
                    choice = int(order[0]) if len(order) and float(pplay[i]) >= threshold else 2304
                    agree += choice == best; gate_ok += (choice < 2304) == (best < 2304); n += 1
    return dict(roots=n, top1_agreement=agree/max(1, n), gate_accuracy=gate_ok/max(1, n), frozen_crosscheck_max_rel=worst, **acc.result())


def group_alive(pgid):
    try: os.killpg(int(pgid), 0); return True
    except ProcessLookupError: return False
    except PermissionError: return True


def live_study_work(job):
    """Reporting supervisors and fits launched by the driver (receipts) that are still alive."""
    live = []
    for rec in [*sorted((job/'receipts').glob('phase-*-launch.json')), *sorted((job/'receipts').glob('fit-*-launch*.json'))]:
        try: r = json.loads(rec.read_text())
        except (OSError, ValueError): live.append(f'{rec.name} unreadable'); continue
        if group_alive(r['pgid']): live.append(rec.name)
    return live


def acquire_lock(job):
    lock = confine.writable(str(job/'driver'/'DIAGNOSTIC.lock'), roles=('driver',), must_not_exist=True)
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, 'w') as f: f.write(json.dumps(dict(pid=os.getpid(), utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())))+'\n')
    live = live_study_work(job)          # checked AFTER the lock exists: the driver cannot dispatch in between
    if live:
        os.unlink(lock); raise SystemExit(f'diagnostic refused: live reporting/fit work {live}')
    return lock


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--students', type=Path, required=True, help='JSON {id: {checkpoint, checkpoint_sha256, threshold}}')
    ap.add_argument('--holdout', type=Path, nargs='+', required=True, help='verified O-holdout packed batch directories')
    ap.add_argument('--assets', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    out = confine.writable(str(a.out), roles=('analysis', 'receipts'), must_not_exist=True)
    lock = acquire_lock(confine.JOB)
    try:
        import torch
        from proposals import load_student
        from exit_r3.student import RootTeacherStore
        torch.set_num_threads(1); torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
        if sha(HELDOUT/'manifest.json') != HELDOUT_SHA: raise SystemExit('held-out64 manifest SHA')
        slices = {'O-holdout': [RootTeacherStore(d, a.assets) for d in a.holdout], 'R1-heldout64': [RootTeacherStore(HELDOUT, a.assets)]}
        students = json.loads(a.students.read_text()); res = {}
        for sid, s in students.items():
            if sha(s['checkpoint']) != s['checkpoint_sha256']: raise SystemExit(f'{sid} checkpoint SHA')
            policy = load_student(s['checkpoint']); policy.model.cuda().eval()
            res[sid] = {name: evaluate(policy, float(s['threshold']), st) for name, st in slices.items()}
            del policy; torch.cuda.empty_cache()
        body = dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), students=res,
                    holdout=[str(d) for d in a.holdout], heldout64_sha256=HELDOUT_SHA, device='CUDA float32, TF32 off',
                    ce_definition='listwise_ce: per-root gate+card+tile CE vs W T=0.003 targets; frozen_objective: global frozen teacher_loss',
                    label='X4S-4 O-holdout diagnostic; descriptive only; never a gate; exploration, NEVER ADOPTABLE')
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        with os.fdopen(fd, 'w') as f: f.write(json.dumps(body, indent=2)+'\n')
        print(json.dumps(res))
    finally:
        os.unlink(lock)


if __name__ == '__main__':
    main()
