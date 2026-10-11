"""One excluded own-tier200ms game; capture only public decisions, never outcomes."""
import argparse,os,socket,time
from pathlib import Path
import run
from common import plan,read,write,sha,job,utc,HERE

def main():
 p=argparse.ArgumentParser();p.add_argument('--block',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--cores',required=True);a=p.parse_args();cfg=plan();d=read(a.block);host=socket.gethostname();j=job()
 assert host in cfg['compute']['hosts'] and d['phase']=='corpus' and d['tier'] in ('K0c','S','K2','K4')
 assert d['game_class']=='qualification'
 assert 0<=d['index']<64 and d['seed']==cfg['seed_ranges']['corpus']['base']+d['index']
 cores=list(map(int,a.cores.split(',')));assert len(cores)==5 and os.sched_getaffinity(0)==set(cores)
 assert os.getpriority(os.PRIO_PROCESS,0)==10 and os.sched_getscheduler(0)==os.SCHED_OTHER
 assert not a.out.exists();a.out.mkdir(parents=True);os.chmod(a.out,0o700)
 run.SLOT_CORES=cores;run.OPTIONS=dict(out=str(a.out),max_ticks=cfg['max_ticks'],arms=cfg['arms'],return_reserve_seconds=cfg['return_reserve_seconds'],corpus=True)
 native=run.initialize();assert sha(native)==cfg['source_reference']['native_sha256']
 decks=read(HERE/'guard-decks.json')['primary'];i=d['index'];seat=i%2;t=time.monotonic()
 write(a.out/'descriptor.json',d)
 result=run.run_game((i,d['seed'],d['tier']+'-200',decks[i%5],decks[(i//5)%5],seat,'corpus-'+d['tier'],i%50))
 assert result['terminal']
 write(a.out/'local-complete.json',dict(utc=utc(),descriptor=d,host=host,wall_seconds=time.monotonic()-t,slot_cores=cores,capture_sha256=sha(a.out/'capture.pkl.gz'),games={result['game']+'.json':sha(a.out/'games'/(result['game']+'.json'))},outcomes_sealed=True))
if __name__=='__main__':main()
