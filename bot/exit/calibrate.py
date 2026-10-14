"""On-policy play-threshold calibration (fixed point on the student's OWN states).

    python -m bot.exit.calibrate --ckpt CKPT --out DIR --base TRAIN1 --start S --games 64 --rounds 3 --workers 60

Round k: the student with threshold tau_k plays `games` labelled games (bot.exit.generate, K4S-b64 teacher,
pool as given) on bank indices [S + k*games, S + (k+1)*games). On its own labelled root states we read its
P(play) (behavior_p_play), whether a play is legal, and the teacher's label. tau_{k+1} = proposals.calibrate(
P(play), legal, teacher play rate on those states). Stop when |student play rate - teacher play rate| at tau_k
is below --tol. An off-policy threshold (calibrated on another policy's states) is not trusted: v1-tau lost
45 pp that way (reports/bot/STRENGTH.md).

Writes DIR/calibration.json, and CKPT.calibration.json (the previous one is kept as CKPT.offpolicy.json).
The round games are ordinary ExIt shards on the new student's states, i.e. reusable as next-iteration data.

--mode rate (default after 2026-10-14 05:35Z): match the TEACHER's plays per game instead. Each round the student
plays `games` plain games vs --opponents on fresh training-bank indices (bot.eval.headline with --base TRAIN1);
on the SAME `games` cases every round (common random numbers), tau is moved by secant/bisection on mean candidate plays/game until within --tol-plays of --target-plays (the
K4S-b64 teacher's plays/game vs the same opponent on the training bank). Rationale: the per-state target chases
itself (more plays -> fewer high-elixir labelled states -> lower teacher rate); R3a recalibrated that way lost
11.6 pp vs v1 at 44.8 plays/game.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np


def read_round(games_dir: Path):
    p, legal, tplay = [], [], []
    for d in sorted(games_dir.glob('game-*')):
        t = d / 'train'
        if not (d / 'manifest.json').exists():
            continue
        p.append(np.load(t / 'behavior_p_play.npy')); legal.append(np.load(t / 'behavior_legal_play.npy'))
        tplay.append(np.load(t / 'expert_actions.npy') < 2304)
    return np.concatenate(p), np.concatenate(legal), np.concatenate(tplay)


def run_rate_round(a, rd, spec, start):
    import subprocess, sys
    cmd = [sys.executable, '-B', '-m', 'bot.eval.headline', '--out', str(rd), '--candidate', spec,
           '--opponents', a.opponents, '--games', str(a.games), '--start', str(start), '--workers', str(a.workers),
           '--base', str(a.base)]
    subprocess.run(cmd, check=True)
    rows = [json.loads(l) for p in rd.glob('games-*.jsonl') for l in p.read_text().splitlines()]
    rows = [r for r in rows if 'error' not in r]
    plays = [r['plays'][str(r['seat'])] for r in rows]
    return float(np.mean(plays)), float(np.std(plays) / np.sqrt(len(plays))), float(np.mean([r['score'] for r in rows])), len(rows)


def rate_mode(a, tau):
    log, pts = [], []
    for k in range(a.rounds):
        rd = a.out / f'rate-{k}'
        start = a.start   # common random numbers: the SAME cases every round (round-to-round case noise ~2 plays)
        plays, se, score, n = run_rate_round(a, rd, f'{a.prefix}:{a.ckpt}@{tau!r}', start)
        pts.append((tau, plays))
        entry = dict(round=k, start=start, games=n, threshold=tau, plays_per_game=plays, se=se, score=score,
                     target=a.target_plays)
        log.append(entry); print(json.dumps(entry), flush=True)
        (a.out / 'calibration-rate.json').write_text(json.dumps(log, indent=2))
        if abs(plays - a.target_plays) <= a.tol_plays:
            break
        above = [t for t, p in pts if p > a.target_plays]   # too many plays -> raise tau
        below = [t for t, p in pts if p < a.target_plays]
        if above and below:
            lo, hi = max(above), min(below)
            pl, ph = dict(pts)[lo], dict(pts)[hi]
            tau = lo + (hi - lo) * (pl - a.target_plays) / max(1e-9, pl - ph)   # secant inside the bracket
        else:
            tau = tau + (a.step if plays > a.target_plays else -a.step)
    best = min(log, key=lambda e: abs(e['plays_per_game'] - a.target_plays))
    return dict(threshold=best['threshold'], method='on-policy plays/game controller (bot.exit.calibrate --mode rate)',
                target_plays_per_game=a.target_plays, actual_plays_per_game=best['plays_per_game'],
                opponents=a.opponents, rounds=log)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--ckpt', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--base', required=True, type=int)
    ap.add_argument('--start', required=True, type=int)
    ap.add_argument('--games', type=int, default=64)
    ap.add_argument('--rounds', type=int, default=3)
    ap.add_argument('--workers', type=int, default=60)
    ap.add_argument('--pool', default='v1,v1,self')
    ap.add_argument('--budget', type=int, default=64)
    ap.add_argument('--tol', type=float, default=0.01)
    ap.add_argument('--threshold', type=float, help='tau_0 (default: CKPT.calibration.json)')
    ap.add_argument('--prefix', default='student', choices=['student', 'student10'])
    ap.add_argument('--mode', default='rate', choices=['rate', 'state'])
    ap.add_argument('--target-plays', type=float)
    ap.add_argument('--tol-plays', type=float, default=1.0)
    ap.add_argument('--step', type=float, default=0.03)
    ap.add_argument('--opponents', default='v1')
    a = ap.parse_args(argv)
    from bot.exit import generate
    from bot.exit.train import bootstrap
    bootstrap()
    from proposals import calibrate
    cal_path = Path(str(a.ckpt) + '.calibration.json')
    tau = a.threshold if a.threshold is not None else float(json.loads(cal_path.read_text())['threshold'])
    a.out.mkdir(parents=True, exist_ok=True)
    if a.mode == 'rate':
        if a.target_plays is None:
            ap.error('--mode rate needs --target-plays')
        final = rate_mode(a, tau)
        return finish(a, cal_path, final)
    log = []
    for k in range(a.rounds):
        rd = a.out / f'round-{k}'
        start = a.start + k * a.games
        generate.main(['--out', str(rd), '--student', f'{a.prefix}:{a.ckpt}@{tau!r}', '--pool', a.pool,
                       '--games', str(a.games), '--start', str(start), '--workers', str(a.workers),
                       '--budget', str(a.budget), '--base', str(a.base)])
        p, legal, tplay = read_round(rd / 'games')
        rate_s, rate_t = float((legal & (p >= tau)).mean()), float(tplay.mean())
        new = calibrate(p, legal, rate_t)
        entry = dict(round=k, start=start, games=a.games, threshold=tau, rows=int(len(p)),
                     student_play_rate=rate_s, teacher_play_rate=rate_t, next_threshold=float(new))
        log.append(entry); print(json.dumps(entry), flush=True)
        (a.out / 'calibration.json').write_text(json.dumps(log, indent=2))
        if abs(rate_s - rate_t) < a.tol:
            break
        tau = float(new)
    final = dict(threshold=tau, method='on-policy fixed point (bot.exit.calibrate)', rounds=log,
                 target_play_rate=log[-1]['teacher_play_rate'], actual_play_rate=log[-1]['student_play_rate'])
    return finish(a, cal_path, final)


def finish(a, cal_path, final):
    if a.prefix == 'student':  # student10 calibrations are recorded in DIR only
        if cal_path.exists() and not Path(str(a.ckpt) + '.offpolicy.json').exists():
            shutil.copy(cal_path, str(a.ckpt) + '.offpolicy.json')
        cal_path.write_text(json.dumps(final, indent=2))
    (a.out / 'final.json').write_text(json.dumps(final, indent=2))
    print(json.dumps(final), flush=True)


if __name__ == '__main__':
    main()
