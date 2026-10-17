"""Replay live runs through the deployed session (fp_mac_bench.bench_run) and record, per search decision, the
reduce_fast phase split (ship / native / learned, pool timing), candidates, keys and the board unit count (live-diag,
analysis only: same code tree, a wrapper on bot.search.lopp_fast.reduce_fast that returns its result unchanged)."""
import argparse, importlib.util, json, os, sys, time
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument('--bench', required=True); ap.add_argument('--code', required=True)
ap.add_argument('--runs', nargs='+', type=Path, required=True); ap.add_argument('--player', required=True)
ap.add_argument('--out', type=Path, required=True); ap.add_argument('--max-steps', type=int, default=None)
a = ap.parse_args()
spec = importlib.util.spec_from_file_location('fpb', a.bench); fpb = importlib.util.module_from_spec(spec); spec.loader.exec_module(fpb)
os.environ.setdefault('LL_HANDSYNC', '1')
code = fpb.use_code(a.code); drive = fpb.load_drive(code, ['cv2'])
from bot.players.runtime import Runtime
import bot.search.lopp_fast as lf
rt = Runtime()
rec = []
orig = lf.reduce_fast
def board_units(core):
    obs = core.info.packet.observation; names = rt.R.builder.token_names; n = 0
    for i in [int(j) for j in obs.entity_mask.nonzero()[0]]:
        t = int(obs.entity_ids[i])
        if not (0 <= t < len(names) and names[t] in ('Tower', 'KingTower')): n += 1
    return n
def wrapped(core, root, seat, candidates, **kw):
    t0 = time.perf_counter()
    best, info = orig(core, root, seat, candidates, **kw)
    rec.append(dict(best=None if best is None else int(best), board_units_info=info.get('board_units'), top=info.get('top'), tick=int(core.info.tick), units=board_units(core), candidates=len(candidates),
                    plays=sum(1 for c in candidates if c < 2304), wall_ms=(time.perf_counter() - t0) * 1e3,
                    native=info.get('native'), learned=info.get('learned'), phase_ms=info.get('phase_ms'),
                    pool_cpu=info.get('pool_cpu')))
    return best, info
lf.reduce_fast = wrapped
out = {}
for run in a.runs:
    rec.clear()
    steps, searched, errors, cutoffs, trs = fpb.bench_run(drive, rt, a.player, run, a.max_steps)
    out[run.name] = dict(reduce=list(rec), steps=steps, searched=searched, errors=errors[:20], cutoffs=cutoffs)
    print(run.name, len(rec), 'reduce calls', len(errors), 'errors', cutoffs, 'cutoffs', flush=True)
a.out.write_text(json.dumps(out))
