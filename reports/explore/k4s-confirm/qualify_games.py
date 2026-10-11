"""PREREG-K4S game-level qualification driver (excluded qualification seeds; outcomes never read).

Runs whole games through run.run_game under either runtime, on one five-core slot:
  --runtime k4s : this K4S runner (PYTHONPATH from k4s-confirm/runtime.sh)
  --runtime t1  : the frozen T1 runner, ef4c073a bytes staged at repo/reports/explore/t1 (T1 runtime.sh)
Modes (r3 §4.1):
  nodeadline : listed arms with deadline_seconds=None; command hashes compared by check_games.py
               (K4-200 under K4S == T1 K4-200; K4S-200 == K4-200).
  charged    : listed arms exactly as frozen in plan.json (deadline + 1/c poll charge).
  zero       : K4S with a 0 ms deadline and no charge: every decision must return the SD1 default.
  injected   : deadline-enabled K4-200 through the COMPLETE run_game under a deterministic virtual clock, for the
               T1 vs K4S comparison of r3 §4.1 (injected-clock decisions on the qualification seeds). time.monotonic
               is replaced BEFORE `run` is imported (belief/anchor/planner bind it as a default argument); simulated
               time advances only on work events - each policy poll and each native rollout, by fixed cyclic costs -
               never on clock reads, so extra instrumentation reads in the K4S runner cannot shift any cutoff. The
               collector runs single-threaded (threads=1) so rollout order, and therefore every cutoff, is
               deterministic; the 4-thread collector is equated to T1 on the 125 fixed states.
Writes games/<ident>.json and a receipt. Never prints or reads loss/winner.
"""
import argparse, json, os, socket, sys, time
from pathlib import Path


VT = [1000.0]
# Cycle lengths are coprime with the 4 polls per 10 ticks, so the search seat meets every cost: prep cutoff (0.194,
# 0.230 > the 192 ms cutoff; 0.230 also overruns by one tick), late scoring (0.185) and ordinary decisions.
POLL_COSTS = (0.002, 0.120, 0.194, 0.002, 0.230, 0.150, 0.185)
ROLLOUT_COSTS = (0.0004, 0.0011, 0.0037)
COUNTS = dict(polls=0, rollouts=0)


def install_virtual_clock():
    import time
    time.monotonic = lambda: VT[0]


class _Native:
    def __init__(self, inner): self._inner = inner
    def rollout_e1(self, *args):
        # The native budget argument (last) is enforced in virtual time, never against the real clock.
        *head, budget = args
        cost = ROLLOUT_COSTS[COUNTS['rollouts'] % len(ROLLOUT_COSTS)]; COUNTS['rollouts'] += 1
        if budget < cost:
            VT[0] += max(budget, 0.); raise TimeoutError('virtual native budget')
        value = self._inner.rollout_e1(*head, 1e6)
        VT[0] += cost
        return value
    def __getattr__(self, name): return getattr(self._inner, name)


def instrument_work(run):
    from policy import V1Policy
    original = V1Policy.poll
    def poll(self, *args, **kwargs):
        try:
            return original(self, *args, **kwargs)
        finally:
            VT[0] += POLL_COSTS[COUNTS['polls'] % len(POLL_COSTS)]; COUNTS['polls'] += 1
    V1Policy.poll = poll
    run.R.native = _Native(run.R.native)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runtime', choices=['k4s', 't1'], required=True)
    ap.add_argument('--mode', choices=['nodeadline', 'charged', 'zero', 'injected'], required=True)
    ap.add_argument('--index', type=int, required=True)       # qualification seed index
    ap.add_argument('--population', choices=['primary', 'guard'], required=True)
    ap.add_argument('--arms', nargs='+', required=True)
    ap.add_argument('--cores', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    if a.mode == 'injected':
        install_virtual_clock()
    import run
    from common import plan, read, sha, utc
    cfg = plan()
    cores = list(map(int, a.cores.split(',')))
    # Planned work cores are physical CPUs 0-54 on every fleet host (K4S plan.json compute.hosts; T1's plan has no 04 row).
    assert len(cores) == 5 and cores == list(range(cores[0], cores[0]+5)) and cores[0] % 5 == 0 and set(cores) <= set(range(55)), 'planned five-core slot'
    os.sched_setaffinity(0, set(cores)); run.SLOT_CORES = cores
    assert os.sched_getaffinity(0) == set(cores) and os.sched_getscheduler(0) == os.SCHED_OTHER
    assert os.getpriority(os.PRIO_PROCESS, 0) in (10, 19) and socket.gethostname() in ('127x01', '127x03', '127x04', '127x08')
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
        elif a.mode == 'injected':
            assert name == 'K4-200' and spec['deadline_seconds'] == 0.2
            spec['threads'] = 1
        elif a.mode == 'zero':
            assert spec['kernel'] == 'K4-anytime-sdefault'
            spec.update(deadline_seconds=0.0, inference_scale=1.0, budget_ms=200, qualification_only=True)
        arms[name] = spec
    a.out.mkdir(parents=True, exist_ok=True)
    run.OPTIONS = dict(out=str(a.out), max_ticks=cfg['max_ticks'], arms=arms, return_reserve_seconds=cfg['return_reserve_seconds'])
    native = run.initialize()
    assert sha(native) == '44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2'
    if a.mode == 'injected':
        instrument_work(run)
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
