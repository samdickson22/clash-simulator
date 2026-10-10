"""Operational nice19 adapter around the reviewed excluded capture function."""
import os,socket,time,sys
from pathlib import Path
import run
from common import read,write,sha,job,utc,HERE,plan
from pin import verify
j=job();cfg=plan();d=read(sys.argv[1]);out=Path(sys.argv[2]);cores=list(map(int,sys.argv[3].split(',')))
assert socket.gethostname()=='127x03' and os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getscheduler(0)==os.SCHED_OTHER
assert len(cores)==5 and os.sched_getaffinity(0)==set(cores)
assert d['phase']=='corpus' and d['game_class']=='qualification' and d['tier'] in ('K0c','S','K2','K4')
assert 3<=d['index']<64 and d['seed']==cfg['seed_ranges']['corpus']['base']+d['index']
assert not out.exists();out.mkdir(parents=True);os.chmod(out,0o700)
source=read(j/'capture-source.json');assert source['capture_commit']=='a51ea64cb878ca05bf38a8145174e6d2b9f46d7a'
for name,h in source['capture_code_sha256'].items():assert sha(j/'repo'/name)==h,name
verify(j);write(out/'descriptor.json',d)
run.SLOT_CORES=cores;run.OPTIONS=dict(out=str(out),max_ticks=cfg['max_ticks'],arms=cfg['arms'],return_reserve_seconds=cfg['return_reserve_seconds'],corpus=True)
native=run.initialize();assert sha(native)==cfg['source_reference']['native_sha256']
decks=read(HERE/'guard-decks.json')['primary'];i=d['index'];t=time.monotonic()
result=run.run_game((i,d['seed'],d['tier']+'-200',decks[i%5],decks[(i//5)%5],i%2,'corpus-'+d['tier'],i%50))
assert result['terminal'];verify(j)
write(out/'local-complete.json',dict(utc=utc(),descriptor=d,host=socket.gethostname(),wall_seconds=time.monotonic()-t,slot_cores=cores,capture_sha256=sha(out/'capture.pkl.gz'),games={result['game']+'.json':sha(out/'games'/(result['game']+'.json'))},outcomes_sealed=True,capture_commit=source['capture_commit'],capture_code_sha256=source['capture_code_sha256'],capture_source_sha256=sha(j/'capture-source.json'),operational_worker_sha256=sha(j/'capture-worker.py')))
