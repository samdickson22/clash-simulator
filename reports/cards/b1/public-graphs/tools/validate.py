"""Frozen evaluator driver with an explicit, process-local Python helper overlay."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys

if os.environ.get('BOT_FULLPOOL_POLICIES'):
    raise SystemExit('fixed-checkpoint gate rejects BOT_FULLPOOL_POLICIES override')

ap=argparse.ArgumentParser()
ap.add_argument('phase', choices=('real-r1','real-live','mixed','headline-baseline','headline-candidate'))
ap.add_argument('job',type=Path)
a=ap.parse_args(); J=a.job.resolve(strict=True)
repo=Path('/mpac/sdicks02/jobs/clasher/cards/r1-cards3-phase1/repo-eval')
sys.path.insert(0,str(repo))
helper=J/'public_root.py'
spec=importlib.util.spec_from_file_location('public_root',helper)
module=importlib.util.module_from_spec(spec);sys.modules['public_root']=module;spec.loader.exec_module(module)
import bot.players.runtime as runtime

class CheckedRuntime(runtime.Runtime):
    def __init__(self,*args,**kw):
        super().__init__(*args,**kw)
        import clasher_core
        if Path(sys.modules['public_root'].__file__).resolve()!=helper:
            raise RuntimeError('wrong graph helper import')
        actual=Path(clasher_core.__file__).resolve()
        digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
        if digest(actual)!=self.pins['native_sha256']:
            raise RuntimeError('actual imported native does not match pin')
        record=dict(phase=a.phase, pid=os.getpid(), helper=str(helper),helper_sha256=digest(helper),
            native=str(actual),native_sha256=digest(actual),runtime=str(self.root),
            gamedata_sha256=digest(self.root/'gamedata.json'),vocabulary_count=len(self.R.builder.token_names),
            v1_sha256=digest(self.v1_path),r3a_sha256=digest(self.student_path),
            fair_player=str(Path(sys.modules['fair_player'].__file__).resolve()),
            consumers={n:str(Path(sys.modules[n].__file__).resolve()) for n in
                ('bot.levels.root','bot.live.levels') if n in sys.modules})
        if a.phase == 'mixed':
            context = {}
            base_root, base_graph = self.R.root, self.R.repair_public_graph
            def root(info, opponent, rng):
                context.update(tick=int(info.tick),seat=int(info.seat))
                try:
                    return base_root(info,opponent,rng)
                finally:
                    context.clear()
            def graph(entities):
                value = base_graph(entities)
                report = self.R.public_graph_report
                if report.get('structural_fallback'):
                    if set(context) != {'tick','seat'}:
                        raise RuntimeError('missing mixed graph context')
                    with (J/'mixed-structural.jsonl').open('a') as f:
                        f.write(json.dumps(dict(context,report=report))+'\n')
                return value
            self.R.root = root
            self.R.repair_public_graph = graph
        # A worker can legitimately construct multiple Runtime instances.
        with (J/(a.phase+'-imports-'+str(os.getpid())+'.jsonl')).open('a') as f:
            f.write(json.dumps(record,sort_keys=True)+'\n')

runtime.Runtime=CheckedRuntime
if a.phase.startswith('headline-'):
    sys.argv=['bot.eval.headline','--out',str(J/a.phase),'--candidate','K4L-R-gs-rw-fc-p2',
              '--opponents','R3a,v1','--games','6','--workers','1']
    runpy.run_module('bot.eval.headline',run_name='__main__')
elif a.phase.startswith('real-'):
    spec=importlib.util.spec_from_file_location('real_games',J/'real_games.py')
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    probe.run(runtime.Runtime(),J/(a.phase+'.json'))
else:
    m=runpy.run_path(str(repo/'reports/cards/runtime/tools/noncore_matches.py'),run_name='graph_candidate_mixed')
    m['DECKS']['B1B2B']=['GoblinGiant','RoyalRecruits','RageBarbarian','SkeletonBalloon','GoblinCage','Tombstone','Fisherman','ElectroWizard']
    sys.argv=['noncore_matches.py','--player','LIVE-K4L-R-gs-rw-fc-w200-t2-p2','--opponent','random',
              '--deck','B1B2B','--own-deck','B1B2B','--games','2','--seed','20261016600',
              '--max-ticks','2401','--probe-own','--out',str(J/'mixed.jsonl')]
    m['main']()
    results=[json.loads(s) for s in (J/'mixed.jsonl').read_text().splitlines()]
    if len(results)!=2 or any(r.get('crash') or r['root_errors'] or r['panics'] or r['errors'] or
                             r['search_failures'] or r['native_failures'] for r in results):
        raise RuntimeError('mixed game failed clean root/search contract')
