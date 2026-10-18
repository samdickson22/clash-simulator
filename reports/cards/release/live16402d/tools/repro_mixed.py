"""Replay the live16402c failing mixed LIVE game with a candidate graph helper.

Same game as b1/public-graphs/tools/capture_mixed.py (seed 20261016600, deck
B1B2B, LIVE K4L vs random), but the runtime's public_root module is re-executed
from HELPER before the game, in place (same module object, so every consumer
and except-clause sees the candidate). No runtime files are modified.
Arguments: frozen evaluator repo, candidate helper path, fresh output dir.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys

ap = argparse.ArgumentParser()
ap.add_argument('repo', type=Path)
ap.add_argument('helper', type=Path)
ap.add_argument('out', type=Path)
a = ap.parse_args()
a.out.mkdir()  # exclusive; refusal is deliberate
repo = a.repo.resolve(strict=True)
sys.path.insert(0, str(repo))
import bot.players.runtime as runtime
context = {}
calls = 0
failures = 0
public_root = None
original = None

class CaptureRuntime(runtime.Runtime):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        global public_root, original
        if public_root is None:
            import public_root as module
            public_root = module
            code = a.helper.read_bytes()
            module.__dict__['__candidate_sha256__'] = hashlib.sha256(code).hexdigest()
            exec(compile(code, str(a.helper), 'exec'), module.__dict__)
            original = module.repair_public_graph
            module.repair_public_graph = capture
        base = self.R.root
        def root(info, opponent, rng):
            context.update(tick=int(info.tick), seat=int(info.seat))
            try:
                return base(info, opponent, rng)
            finally:
                context.clear()
        self.R.root = root

# noncore_matches.main imports this class and constructs the ACTUAL game R.
# No separate warm-up Runtime or instrumentation of an unused instance.
runtime.Runtime = CaptureRuntime
with (a.out/'boards.jsonl').open('x') as boards:
    def capture(entities):
        global calls, failures
        if set(context) != {'tick', 'seat'} or context['tick'] < 0 or context['seat'] not in (0, 1):
            raise RuntimeError('graph capture outside the actual game root context')
        calls += 1
        # Root IDs are newly reconstructed row IDs; no live IDs or private
        # mount/rank/target/clock enters this capture or the matching policy.
        rows = [{k: copy.deepcopy(e[k]) for k in ('id','owner','class','x','y','facing')} |
                {'stats': {k: copy.deepcopy(v) for k,v in e['stats'].items()
                           if k in ('name','riders','speed','radius')}} for e in entities]
        record = dict(context, rows=rows)
        try:
            result = original(entities)
        except public_root.PublicGraphError as ex:
            failures += 1
            record.update(error=str(ex), report=ex.report)
            raise
        else:
            record['report'] = result
            return result
        finally:
            boards.write(json.dumps(record, sort_keys=True)+'\n')
            boards.flush()
    m = runpy.run_path(str(repo/'reports/cards/runtime/tools/noncore_matches.py'), run_name='graph_capture')
    m['DECKS']['B1B2B']=['GoblinGiant','RoyalRecruits','RageBarbarian','SkeletonBalloon','GoblinCage','Tombstone','Fisherman','ElectroWizard']
    sys.argv=['noncore_matches.py','--player','LIVE-K4L-R-gs-rw-fc-w200-t2-p2',
              '--opponent','random','--deck','B1B2B','--own-deck','B1B2B','--games','1',
              '--seed','20261016600','--max-ticks','2401','--probe-own','--out',str(a.out/'mixed.jsonl')]
    m['main']()
if calls == 0:
    raise SystemExit('capture was not exercised')
(a.out/'capture.json').write_text(json.dumps(dict(calls=calls, failures=failures,
    graph_module=str(Path(public_root.__file__).resolve()),
    graph_sha256=public_root.__candidate_sha256__,
    native=str(Path(sys.modules['clasher_core'].__file__).resolve())), indent=2)+'\n')
