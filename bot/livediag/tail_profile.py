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
decs = []
_mk = drive.make_session
def make_session(*a, **k):      # per-step decision record (source / action / hit / preparation cutoff), result unchanged
    sess = _mk(*a, **k); _step = sess.step
    def step(rec):
        d = _step(rec)
        if d is not None:
            st = getattr(d, 'stats', None) or {}
            decs.append(dict(ts=rec.get('timestamp_ms', rec.get('ts_ms')), action=int(getattr(d, 'action', -1)), source=st.get('source'), hit=st.get('hit'),
                             prep=st.get('preparation_cutoff'), rebuilds=st.get('belief_rebuilds'), stale=st.get('belief_stale'),
                             wall_ms=st.get('wall_ms')))
        return d
    sess.step = step
    return sess
drive.make_session = make_session
out = {}
for run in a.runs:
    rec.clear(); decs.clear()
    steps, searched, errors, cutoffs, trs = fpb.bench_run(drive, rt, a.player, run, a.max_steps)
    out[run.name] = dict(decisions=list(decs), reduce=list(rec), steps=steps, searched=searched, errors=errors[:20], cutoffs=cutoffs)
    print(run.name, len(rec), 'reduce calls', len(errors), 'errors', cutoffs, 'cutoffs', flush=True)
a.out.write_text(json.dumps(out))
