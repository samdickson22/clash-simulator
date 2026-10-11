"""PREREG-K4S END reference cells (r3 §4.5 (a)-(c); K4S-SPEC §8). Delta 8. Never launches games.

Runs after the committed reporting-completion receipt, on every host with counted blocks, in reference
slot 0 while the other slots run the background corpus loop (reporting load profile).

Work units come from TIERS's frozen replay backend through the K4S read-only subclass
(mac/k4s_backend.py); TIERS / e4v3 files are imported by path and never edited:
  (a) no-deadline K4 (TierBackend.work 'K4') and K4S (k4s_work), `--repeats` (3) passes over the corpus;
  (b) K4S deadline mode at 200/180/160/140/120 ms with the 1/c poll charge (sleep (1/c - 1) x the pure SD1
      poll span inside the timer), `--repeats` passes; per state: cutoff, no-complete-play, fallback;
  (c) the pure SD1 and v1 poll spans (`poll_seconds`, call to return) on every corpus state.
No-deadline exactness: the K4S result must equal the K4 result on every state (r3 §2.3: K4S == K4).
Writes one raw per-host JSON; end_pool.py pools hosts into clasher.k4s.mac-fleet-reference.v1.

  end_reference.py --mode reference --bundle B --runtime-root R --native N --corpus K4-states.pkl \
      --corpus-sha256 a97b1fbf... --kernel sdefault.py --scorer anchor_x.py --cores 0,1,2,3,4 --out raw.json
  end_reference.py --mode background ... --cores 5,6,7,8,9 --stop STOPFILE     # load profile on another slot
"""
import argparse, json, os, socket, statistics, sys, threading, time
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
CELLS = ((Fraction(1), 200), (Fraction(9, 10), 180), (Fraction(4, 5), 160), (Fraction(7, 10), 140), (Fraction(3, 5), 120))
K4_CORPUS_SHA256 = 'a97b1fbf6cbc33a7b65aa5fc91eb0acdd07c922aaf0737620a849163aaadbfe8'


def charge_scale(cell):
    """Exact 1/c as a rational string, e.g. 10/9 for c = 0.9."""
    s = 1/cell
    return str(s.numerator) if s.denominator == 1 else f'{s.numerator}/{s.denominator}'


class Timed:
    """Delegating policy wrapper: records the pure poll span and optionally charges (scale-1) x span inside it."""
    def __init__(self, inner, sleep=time.sleep, clock=time.monotonic):
        self.inner, self.sleep, self.clock = inner, sleep, clock
        self.scale = Fraction(1); self.last_poll = None; self.last_sleep = 0.

    def sample(self, *args, **kwargs):
        t = self.clock(); out = self.inner.sample(*args, **kwargs); self.last_poll = self.clock()-t
        extra = float(self.scale-1)*self.last_poll; self.last_sleep = 0.
        if extra > 0:
            t = self.clock(); self.sleep(extra); self.last_sleep = self.clock()-t
        return out

    def __getattr__(self, name):
        return getattr(self.inner, name)


def mhz_logger(cores, stop, rows):
    while not stop.is_set():
        mhz = {}; cpu = None
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('processor'): cpu = int(line.split(':', 1)[1])
            elif line.startswith('cpu MHz') and cpu in cores: mhz[cpu] = float(line.split(':', 1)[1])
        rows.append(dict(t=time.time(), mhz=mhz)); stop.wait(1.)


def backend(a):
    sys.path[:0] = [str(a.e4v3), str(HERE/'mac')]
    from k4s_backend import backend_class
    be = backend_class()(a.bundle, a.runtime_root, a.native, a.corpus, a.corpus_sha256, a.kernel, a.scorer)
    be.search_cpus = a.cores
    be.sd1 = Timed(be.sd1); be.v1 = Timed(be.v1)
    return be


def reference(a):
    be = backend(a); rows = list(be.k4s_rows.values())
    stop = threading.Event(); mhz = []; threading.Thread(target=mhz_logger, args=(set(a.cores), stop, mhz), daemon=True).start()
    out = dict(schema='clasher.k4s.end-reference-raw.v1', host=socket.gethostname(), cores=a.cores, nice=os.getpriority(os.PRIO_PROCESS, 0),
               corpus_sha256=a.corpus_sha256, repeats=a.repeats, states={}, deadline={})
    for r in range(a.repeats):
        for row in rows:
            ident = str(row['id']); s = out['states'].setdefault(ident, dict(k4_wall=[], k4s_wall=[], sd1_poll=[], v1_poll=[]))
            be.sd1.scale = Fraction(1)
            k4_result, k4_t = be.work(row, 'K4'); s['v1_poll'].append(be.v1.last_poll); s['k4_wall'].append(k4_t['wall_seconds'])
            k4s_result, k4s_t = be.k4s_work(row); s['sd1_poll'].append(be.sd1.last_poll); s['k4s_wall'].append(k4s_t['wall_seconds'])
            if k4s_result != k4_result:
                raise ValueError(f'No-deadline K4S != K4 on state {ident}')
            s['result'] = k4s_result
            for cell, budget in CELLS:
                be.sd1.scale = 1/cell
                _, t = be.k4s_work(row, deadline=budget/1000)
                d = out['deadline'].setdefault(str(float(cell)), dict(budget_ms=budget, charge_scale=charge_scale(cell), rows=[]))
                d['rows'].append(dict(id=ident, repeat=r, cutoff=bool(t['cutoff']), no_complete_play=bool(t['no_complete_play']),
                                      fallback=bool(t['fallback']), wall_seconds=t['wall_seconds'], poll_seconds=be.sd1.last_poll,
                                      scale_sleep_seconds=be.sd1.last_sleep))
            be.sd1.scale = Fraction(1)
    stop.set(); out['mhz_1hz'] = mhz
    Path(a.out).write_text(json.dumps(out)+'\n')


def background(a):
    be = backend(a); rows = list(be.k4s_rows.values())
    while not Path(a.stop).exists():
        for row in rows:
            if Path(a.stop).exists(): break
            be.work(row, 'K4')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['reference', 'background'], required=True)
    ap.add_argument('--bundle', type=Path, required=True); ap.add_argument('--runtime-root', type=Path, required=True)
    ap.add_argument('--native', type=Path, required=True); ap.add_argument('--corpus', type=Path, required=True)
    ap.add_argument('--corpus-sha256', default=K4_CORPUS_SHA256); ap.add_argument('--kernel', type=Path, default=HERE/'sdefault.py')
    ap.add_argument('--scorer', type=Path, default=HERE/'anchor_x.py')
    ap.add_argument('--e4v3', type=Path, default=HERE.parents[2]/'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3')
    ap.add_argument('--cores', type=lambda s: [int(x) for x in s.split(',')], required=True)
    ap.add_argument('--repeats', type=int, default=3); ap.add_argument('--out'); ap.add_argument('--stop')
    a = ap.parse_args()
    assert a.corpus_sha256 == K4_CORPUS_SHA256 and len(a.cores) == 5 and a.repeats == 3
    os.sched_setaffinity(0, set(a.cores))
    reference(a) if a.mode == 'reference' else background(a)


if __name__ == '__main__':
    main()
