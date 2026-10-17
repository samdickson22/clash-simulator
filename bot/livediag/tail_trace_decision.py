"""Trace one live decision in replay (live-diag, read-only analysis): at searches with tick in [--t0, --t1], dump the
decision packet's entities (token, team flag, features), our hand, the candidates with their final scores (core.last),
and the chosen action; plus each step's translator board for the frames in [--n0, --n1]. Wraps lopp_fast.reduce_fast
(result unchanged) and runs fp_mac_bench.bench_run through the code tree's drive.py make_session."""
import argparse, importlib.util, json, os
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument('--bench', required=True); ap.add_argument('--code', required=True); ap.add_argument('--run', type=Path, required=True)
ap.add_argument('--player', required=True); ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--t0', type=float, required=True); ap.add_argument('--t1', type=float, required=True)
a = ap.parse_args()
spec = importlib.util.spec_from_file_location('fpb', a.bench); fpb = importlib.util.module_from_spec(spec); spec.loader.exec_module(fpb)
os.environ.setdefault('LL_HANDSYNC', '1')
code = fpb.use_code(a.code); drive = fpb.load_drive(code, ['cv2'])
from bot.players.runtime import Runtime
import bot.search.lopp_fast as lf
rt = Runtime(); names = rt.R.builder.token_names
out = []
self_ref = []
orig = lf.reduce_fast
def tile(act):
    s, t = divmod(int(act), 576); return dict(slot=s, x=t % 18, y=t // 18) if act < 2304 else dict(wait=int(act))
def wrapped(core, root, seat, candidates, **kw):
    best, info = orig(core, root, seat, candidates, **kw)
    t = float(core.info.tick)
    if a.t0 <= t <= a.t1:
        obs = core.info.packet.observation
        ents = []
        for i in [int(j) for j in obs.entity_mask.nonzero()[0]]:
            tok = int(obs.entity_ids[i]); f = [round(float(x), 4) for x in obs.entity_features[i][:12]]
            ents.append(dict(token=tok, name=names[tok] if 0 <= tok < len(names) else tok, f=f))
        hand = [names[int(x)] if int(x) > 0 else None for x in list(obs.hand_ids)[:4]]
        last = getattr(core, 'last', None) or {}
        cands = [dict(action=int(c), **tile(c), card=(hand[int(c)//576] if int(c) < 2304 else None), score=s)
                 for c, s in zip(last.get('candidates', []), last.get('scores', []))]
        cands.sort(key=lambda d: -(d['score'] if d['score'] is not None else -9))
        waits = [c for c in cands if 'wait' in c]
        ev = [dict(kind=getattr(e,'kind',None), name=getattr(e,'name',None), tick=getattr(e,'tick',None), seat=getattr(e,'seat',None)) for e in (core.info.events or [])][-12:]
        b = getattr(getattr(self_ref[0], 'p', None), 'belief', None) if self_ref else None
        out.append(dict(events_tail=ev, tick=t, seat=seat, best=None if best is None else int(best), best_tile=None if best is None else tile(best),
                        hand=hand, elixir=float(obs.global_features[5]) * 10, entities=ents, candidates=cands[:8] + [c for c in cands[8:] if 'wait' in c], n_scored=len(cands), info={k: v for k, v in info.items() if k != 'phase_ms'},
                        n_candidates_in=len(candidates)))
    return best, info
lf.reduce_fast = wrapped
steps, searched, errors, cutoffs, trs = fpb.bench_run(drive, rt, a.player, a.run, None)
a.out.write_text(json.dumps(dict(traces=out, errors=errors[:10], cutoffs=cutoffs, translator=trs), indent=1, default=str))
print(len(out), 'traced decisions;', len(errors), 'errors;', cutoffs, 'cutoffs')
