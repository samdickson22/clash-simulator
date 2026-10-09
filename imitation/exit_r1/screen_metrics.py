"""Exploration screen statistics, shared by runner and all-WAIT regression tests."""
import numpy as np


def diagnostics(actions, play_probability, wait_probability):
    actions=np.asarray(actions);p=np.asarray(play_probability);w=np.asarray(wait_probability)
    if not len(actions) or len(p)!=len(actions) or len(w)!=len(actions):raise ValueError('empty/mismatched diagnostics')
    if not np.isfinite(p).all() or not np.isfinite(w).all() or ((p<0)|(p>1)|(w<0)|(w>1)).any():
        raise ValueError('invalid policy probabilities')
    positive=actions<2304
    if not positive.any():raise ValueError('teacher slice has no plays')
    return dict(rows=len(actions),teacher_play_rate=float(positive.mean()),teacher_wait_rate=float((actions==2304).mean()),
                play_recall=float(p[positive].mean()),student_play_rate=float(p.mean()),student_wait_rate=float(w.mean()))


def paired_interval(candidate,reference,reps=5000,seed=80991010):
    a=np.asarray(candidate,dtype=np.float64);b=np.asarray(reference,dtype=np.float64)
    if a.shape!=b.shape or a.ndim!=1 or not len(a) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('paired terminal losses required')
    delta=a-b;rng=np.random.default_rng(seed)
    samples=delta[rng.integers(len(delta),size=(reps,len(delta)))].mean(1)
    lo,hi=np.quantile(samples,[.025,.975])
    return dict(loss_change=float(delta.mean()),ci95=[float(lo),float(hi)],pairs=len(delta),reps=reps,seed=seed)


def decide(metrics,paired):
    reasons=[]
    if metrics['play_recall']<.5:reasons.append('teacher play recall below 50%')
    if metrics['student_wait_rate']>1.5*metrics['teacher_wait_rate']:reasons.append('WAIT rate exceeds 1.5 times teacher')
    if paired['ci95'][1]>=0:reasons.append('paired loss-change CI upper bound is nonnegative')
    return dict(survives=not reasons,kill_reasons=reasons,lane='exploration; no multiplicity adjustment')
