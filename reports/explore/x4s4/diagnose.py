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
GPU float32, TF32 off, inference only. r3 (Sol r2 R2-F3, R2-F9): every read and write goes through x4s4io; inputs
are not caller choices - the verified O-holdout batches listed in <job>/data/HOLDOUT-VERIFIED.json (bank C
3500-3999; its SHA is recorded), exactly the five students R3a (staged plan), R3a-rep, R5, R5-rep, R5W (runtime
READY receipts) with checkpoint SHAs re-verified, and assets pinned by RUNTIME-INVENTORY. The diagnostic registers
its process group, takes driver/DIAGNOSTIC.lock (pid + starttime) inside the driver's exclusive DISPATCH flock after
checking that no reporting/fit group lives, and runs the live guards (STOP, hard stop, MemAvailable, PSS <= 50 GiB,
tree, disk) before each student and every 100 batches; a breach aborts without output. The lock is removed at exit.
Output: <job>/analysis/diagnostic.json, written once (0444).
"""
import argparse, fcntl, hashlib, json, os, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import x4s4io as io, studytree                   # noqa: E402

STUDENTS = ('R3a', 'R3a-rep', 'R5', 'R5-rep', 'R5W')

HELDOUT = Path('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1/heldout-corpus')
HELDOUT_SHA = '0ecce0f0f410ff7f1093994cdb62b44c4c141c3a4bddb237cf1427b0a512818f'


def sha(p): return io.sha256_file(str(p))


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


def evaluate(policy, threshold, stores, batch=64, guard=None):
    import torch
    from proposals import outputs, rank_actions
    from exit_r3.student import teacher_loss
    acc = CEAccumulator(); agree = gate_ok = n = 0; worst = 0.0
    with torch.inference_mode():
        for store in stores:
            for k, start in enumerate(range(0, len(store), batch)):
                if guard and k % 100 == 0: guard()                     # STOP / hard stop / memory / PSS / tree (R2-F3)
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


class Abort(Exception):
    pass


def live_study_work(job):
    """Reporting supervisors and fits launched by the driver (receipts) that are still alive (verified owned PIDs)."""
    live = []
    for n in io.listdir(job+'/receipts'):
        if (n.startswith('phase-') and n.endswith('-launch.json')) or n.startswith('fit-') and '-launch' in n:
            try: r = io.read_json(f'{job}/receipts/{n}', 1 << 20)
            except io.Refusal: live.append(f'{n} unreadable'); continue
            if io.group_alive(r.get('pgid'), r.get('starttime')): live.append(n)
    return live


def acquire_lock(job):
    """Under the driver's exclusive DISPATCH flock: refuse while reporting/fit work lives, else create the
    diagnostic lock (pid + starttime). The driver checks that lock inside the same flock before every launch."""
    lock = job+'/driver/DIAGNOSTIC.lock'
    fd = io.open_append(job+'/driver/DISPATCH.lock', roles=('driver',))
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        live = live_study_work(job)
        if live: raise SystemExit(f'diagnostic refused: live reporting/fit work {live}')
        me = io.own_identity()
        io.write_json_once(lock, dict(pid=me['pid'], starttime=me['starttime'], utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())),
                           roles=('driver',), mode=0o644)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)
    return lock


def students_of(job):
    """Exactly the five declared students, from the staged plan (R3a) and the runtime READY receipts (R2-F9)."""
    plan = io.read_json(job+'/base/repo/reports/explore/x4s3/plan.json', 16 << 20)
    out = {'R3a': dict(checkpoint=plan['student']['checkpoint'], checkpoint_sha256=plan['student']['checkpoint_sha256'],
                       threshold=plan['student']['threshold'])}
    for sid in STUDENTS[1:]:
        st = io.read_json(f'{job}/rt-{sid}/READY.json', 4 << 20)['student']
        out[sid] = dict(checkpoint=st['checkpoint'], checkpoint_sha256=st['checkpoint_sha256'], threshold=st['threshold'])
    return out


def holdout_of(job):
    """R3-F3: the verified O-holdout NOW - studytree.authenticate_gate re-verifies the HOLDOUT-VERIFIED receipt chain,
    the exact batch inventory and every batch's complete seal against the gate's manifest pins (bank C 3500-3999 was
    checked by the verifier over exactly those bytes), so a substituted corpus is refused before the frozen loader."""
    batches, gate_sha, _ = studytree.authenticate_gate(job, 'holdout')
    return batches, gate_sha


def guard_factory(job):
    me = io.own_identity(); lead = io.proc_stat(me['pgid'])
    own = (me['pgid'], lead['starttime'] if lead else me['starttime'])
    def guard():
        why = studytree.monitor(job, own=own, check_psi=False)
        if why: raise Abort(why)
    return guard


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=io.JOB+'/analysis/diagnostic.json')
    a = ap.parse_args()
    job = io.JOB
    io.check_writable(a.out, roles=('analysis',), must_not_exist=True)
    guard = guard_factory(job)
    guard()                                                         # STOP / hard stop / memory / tree before anything
    holdout, holdout_sha = holdout_of(job)
    students = students_of(job)
    inv = io.read_json(job+'/RUNTIME-INVENTORY.json', 4 << 20)
    assets = job+'/inputs/assets.npz'
    if io.sha256_file(assets) != inv.get('inputs/assets.npz'): raise SystemExit('assets differ from RUNTIME-INVENTORY')
    if io.sha256_file(str(HELDOUT/'manifest.json')) != HELDOUT_SHA: raise SystemExit('held-out64 manifest SHA')
    studytree.register(job, 'diagnose')
    lock = acquire_lock(job)
    try:
        import torch
        from proposals import load_student
        from exit_r3.student import RootTeacherStore
        torch.set_num_threads(1); torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
        slices = {'O-holdout': [RootTeacherStore(d, assets) for d in holdout], 'R1-heldout64': [RootTeacherStore(str(HELDOUT), assets)]}
        res = {}
        for sid, s in students.items():
            guard()
            if io.sha256_file(s['checkpoint']) != s['checkpoint_sha256']: raise SystemExit(f'{sid} checkpoint SHA')
            policy = load_student(s['checkpoint']); policy.model.cuda().eval()
            res[sid] = {name: evaluate(policy, float(s['threshold']), st, guard=guard) for name, st in slices.items()}
            del policy; torch.cuda.empty_cache()
        body = dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), students=res, student_checkpoints=students,
                    holdout=holdout, holdout_gate_sha256=holdout_sha, heldout64_sha256=HELDOUT_SHA, device='CUDA float32, TF32 off',
                    ce_definition='listwise_ce: per-root gate+card+tile CE vs W T=0.003 targets; frozen_objective: global frozen teacher_loss',
                    label='X4S-4 O-holdout diagnostic; descriptive only; never a gate; exploration, NEVER ADOPTABLE')
        io.write_json_once(a.out, body, roles=('analysis',), mode=0o444)
        print(json.dumps(res))
    except Abort as e:
        raise SystemExit(f'diagnostic stopped by a live guard: {e}')
    finally:
        io.remove_tree(lock, roles=('driver',))


if __name__ == '__main__':
    main()
