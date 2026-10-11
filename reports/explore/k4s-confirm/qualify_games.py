"""PREREG-K4S game-level qualification driver (excluded qualification seeds; outcomes never read).

Runs whole games through run.run_game under either runtime, on one five-core slot:
  --runtime k4s : this K4S runner (PYTHONPATH from k4s-confirm/runtime.sh)
  --runtime t1  : the frozen T1 runner, ef4c073a bytes staged at repo/reports/explore/t1 (T1 runtime.sh)
Modes (r3 §4.1):
  nodeadline : listed arms with deadline_seconds=None; command hashes compared by check_games.py
               (K4-200 under K4S == T1 K4-200; K4S-200 == K4-200).
  charged    : listed arms exactly as frozen in plan.json (deadline + 1/c poll charge).
  zero       : K4S with a 0 ms deadline and no charge: every decision must return the SD1 default.
Writes games/<ident>.json and a receipt. Never prints or reads loss/winner.
"""
import argparse, json, os, socket, sys, time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runtime', choices=['k4s', 't1'], required=True)
    ap.add_argument('--mode', choices=['nodeadline', 'charged', 'zero'], required=True)
    ap.add_argument('--index', type=int, required=True)       # qualification seed index
    ap.add_argument('--population', choices=['primary', 'guard'], required=True)
    ap.add_argument('--arms', nargs='+', required=True)
    ap.add_argument('--cores', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    import run
    from common import plan, read, sha, utc
    cfg = plan()
    cores = list(map(int, a.cores.split(','))); assert len(cores) == 5
    os.sched_setaffinity(0, set(cores)); run.SLOT_CORES = cores
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19 and socket.gethostname() == '127x03'
    base = 4503605837370496
    seed = base + a.index
    cells = 50 if a.population == 'primary' else 18
    cell = a.index % cells
    decks = read(Path(run.__file__).parent/'guard-decks.json')
    if a.population == 'primary':
        own, other = decks['primary'][cell % 5], decks['primary'][(cell//5) % 5]
    else:
        own, other = decks['l2'][(cell//2) % 3], decks['guard'][cell//6]['cards']
    arms = {}
    for name in a.arms:
        spec = dict(cfg['arms'][name])
        if a.mode == 'nodeadline':
            spec['deadline_seconds'] = None
        elif a.mode == 'zero':
            assert spec['kernel'] == 'K4-anytime-sdefault'
            spec.update(deadline_seconds=0.0, inference_scale=1.0, budget_ms=200, qualification_only=True)
        arms[name] = spec
    a.out.mkdir(parents=True, exist_ok=True)
    run.OPTIONS = dict(out=str(a.out), max_ticks=cfg['max_ticks'], arms=arms, return_reserve_seconds=cfg['return_reserve_seconds'])
    native = run.initialize()
    assert sha(native) == '44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2'
    games = []
    for name in a.arms:
        t = time.monotonic()
        if a.runtime == 't1':
            r = run.run_game((a.index, seed, name, own, other, cell % 2, 'qualification', cell))
        else:
            placement = dict(rotation=None, block_id=f'qualification-{a.index:04d}', replacement_k=None)
            r = run.run_game((a.index, seed, name, own, other, cell % 2, 'qualification', cell, placement))
        assert r['terminal']
        games.append(dict(game=r['game'], wall_seconds=time.monotonic()-t, sha256=sha(a.out/'games'/(r['game']+'.json'))))
    receipt = dict(utc=utc(), runtime=a.runtime, mode=a.mode, index=a.index, seed=seed, population=a.population, cell=cell,
                   arms=a.arms, cores=cores, games=games, run_py_sha256=sha(run.__file__), plan_sha256=sha(Path(run.__file__).parent/'plan.json'))
    (a.out/f'receipt-{a.runtime}-{a.mode}-{a.population}{a.index}.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(dict(done=len(games))), flush=True)


if __name__ == '__main__':
    main()
