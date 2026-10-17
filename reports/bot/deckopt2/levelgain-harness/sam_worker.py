"""Existing full-pool players; only truth deck/level/tower inputs are varied."""
import argparse,json,os,random,shlex,signal,subprocess,time,traceback
from collections import Counter
from sam_common import ROOT,OLD,REPO,PY,DECKS,utc,sha,dump
import fullpool_worker as original
import fullpool_eval as fp
from fullpool_clean import problems

def remote(argv):return subprocess.check_output(['ssh','127x05',shlex.join(list(map(str,argv)))],text=True)
def prepare():
 from bot.levels.placement_probe import installed_identity
 meta=json.loads((OLD/'fullpool/manifest.json').read_text())
 assert installed_identity()==meta['simulator']
 original.verify(meta)
 rt=fp.runtime(fp.BELIEF);strong=fp.runtime('c56')
 for current in (rt,strong):
  assert current.pins['native_sha256']==meta['native_sha256']
  assert current.pins['gamedata_sha256']==meta['gamedata_sha256']
  fp.install_placement(current);current.STUDENT
 return rt,strong,json.loads((OLD/'fullpool/vocab-combined.json').read_text())

def game(rt,strong,vocab,meta,bank,case,candidate,player,output,block):
 from bot.players.royalesim_match import play_match
 from bot.search.lopp import FAILURES
 started=time.monotonic();ps={};stage=block['stage']
 row=dict(case,candidate=candidate,player=player,stage='validation',scenario=meta['scenario'],host=os.uname().nodename,
          started_utc=utc(),bank_sha256=sha(ROOT/stage/'validation/bank.json'),block=block)
 try:
  seat=case['seat'];own=[meta['candidates'][candidate][i] for i in case['own_permutation']]
  own_levels=meta['candidate_plans'][candidate]['levels']
  decks=[own,case['opponent_deck']] if seat==0 else [case['opponent_deck'],own]
  levels=[own_levels,case['opponent_levels']] if seat==0 else [case['opponent_levels'],own_levels]
  ps=fp.players(rt,fp.LIVE+('-res' if player.endswith('-res') else ''),case['opponent'],seat,strong_rt=strong)
  original.configure(ps,seat,player,meta['player_config']);before=Counter(FAILURES)
  towers=[case['opponent_tower_level']]*2; towers[seat]=meta['tower_level']
  result=play_match(rt,ps,seed=case['seed'],decks=decks,vocab=vocab,client='16.402',levels=levels,tower_levels=towers,verbose=True)
  result['public_diagnostics']={str(side):fp.diagnostics(p,result) for side,p in ps.items()}
  logs=result.pop('play_log');result.pop('command_events',None)
  failures=dict(Counter(FAILURES)-before)
  errors={str(side):[d for d in getattr(p.rec.inner,'decisions',[]) if 'error' in d or d.get('native_failures')] for side,p in ps.items()}
  unmapped={k:v for k,v in result['translator'].items() if v and ('unmapped' in k or 'missing' in k)}
  issues=[]
  if not result['terminal']:issues.append('nonterminal')
  if failures:issues.append('native failures')
  if any(errors.values()):issues.append('live errors')
  if result['channels'][seat]['rejected']:issues.append('our command rejections')
  if unmapped:issues.append('unmapped public rows')
  if result['public_diagnostics'][str(seat)]['cutoff_hits']:issues.append('unexpected no-wall cutoff')
  row.update(result=result,win=int(result['winner']==seat),draw=int(result['winner'] is None),
   score=.5 if result['winner'] is None else float(result['winner']==seat),
   card_plays=dict(Counter(c for _,c,_,ok in logs[seat] if ok)),failures=failures,live_errors=errors,
   unmapped=unmapped,issues=issues,truth_levels=levels,truth_tower_levels=towers)
 except BaseException as error:row.update(error=repr(error),traceback=traceback.format_exc())
 finally:
  from bot.search import lopp_fast
  for pool in lopp_fast._POOLS.values():pool.close()
 row['wall_seconds']=time.monotonic()-started;dump(output,row)
 return row

def preflight(rt,strong,vocab):
 stage='shifted';meta=json.loads((ROOT/stage/'manifest.json').read_text());bank=json.loads((ROOT/stage/'validation/bank.json').read_text());case=bank['cases'][0];player=bank['players'][0]
 rows=[]
 for i in range(2):
  row=game(rt,strong,vocab,meta,bank,case,'baseline',player,ROOT/f'preflight/repeat-{i}.json',dict(stage=stage,repeat=i))
  assert not problems(row),problems(row)
  assert row['truth_tower_levels'][case['seat']]==7 and row['truth_tower_levels'][1-case['seat']]==8
  rows.append(row)
 assert rows[0]['result']['command_sha256']==rows[1]['result']['command_sha256']
 assert rows[0]['result']['state_hash']==rows[1]['result']['state_hash']
 dump(ROOT/'preflight/receipt.json',dict(utc=utc(),passed=True,command_sha256=rows[0]['result']['command_sha256'],state_hash=rows[0]['result']['state_hash'],our_king=7,opponent_king=8))
 subprocess.run(['rsync','-a',str(ROOT/'preflight/receipt.json'),f'127x05:{ROOT}/preflight/'],check=True)
 print('LEVELGAIN_REPEAT_PASSED',flush=True)

def work(label,wid,rt,strong,vocab):
 stopping=False
 def stop(*args):
  nonlocal stopping
  stopping=True
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGUSR1,stop)
 worker=f'{os.uname().nodename}-{label}-{wid}';completed=0
 while not stopping and not (ROOT/f'PAUSE-{label}').exists():
  claim=json.loads(remote([PY,ROOT/'sam_queue.py','--worker',worker]))
  if claim is None:break
  stage,index=claim['stage'],claim['index'];d=ROOT/stage
  # Inputs may land while controllers are running. Copy the immutable bank and
  # manifest before the first case in a new stage, without touching old stages.
  for relative in ('manifest.json','validation/bank.json'):
   if not (d/relative).exists():
    (d/relative).parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['rsync','-a',f'127x05:{d/relative}',str(d/relative)],check=True)
  meta=json.loads((d/'manifest.json').read_text());bank=json.loads((d/'validation/bank.json').read_text())
  assert sha(d/'manifest.json')==bank['manifest_sha256']
  assert all(sha(ROOT/p)==v for p,v in meta['helper_sha256'].items())
  case=bank['cases'][index];arms=[(n,p) for n in bank['candidates'] for p in bank['players']]
  order=list(range(len(arms)));random.Random(case['seed']^0xA4A4).shuffle(order)
  block=dict(stage=stage,worker=worker,controller_label=label,worker_pid=os.getpid(),case_index=index,arm_order=[arms[a] for a in order],cpu_slots=1,affinity=sorted(os.sched_getaffinity(0)))
  dump(ROOT/f'active-{label}-{wid}.json',dict(utc=utc(),**block))
  for position,arm in enumerate(order):
   candidate,player=arms[arm];output=d/'validation/rows'/f'{index*len(arms)+arm:06d}.json'
   assert not output.exists(),output
   row=game(rt,strong,vocab,meta,bank,case,candidate,player,output,dict(block,arm_position=position,game_pid=os.getpid()))
   subprocess.run(['rsync','-a',str(output),f'127x05:{d}/validation/rows/'],check=True)
   if problems(row):
    remote(['touch',ROOT/'STOP']);raise RuntimeError(('unclean game retained',str(output),problems(row)))
   completed+=1
  dump(ROOT/f'block-complete-{stage}-{index:04d}.json',dict(utc=utc(),**block))
 dump(ROOT/f'worker-complete-{label}-{wid}.json',dict(utc=utc(),games=completed,stopping=stopping))

def main():
 p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--workers',type=int,default=1);p.add_argument('--preflight',action='store_true');a=p.parse_args()
 assert 1<=a.workers<=40
 pgid=os.getpgrp();slots=0
 for path in __import__('pathlib').Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims').glob('lease-*'):
  try:n,g=map(int,path.read_text().split())
  except (OSError,ValueError):continue
  if g==pgid:slots=max(slots,n)
 assert slots>=a.workers+2,(slots,a.workers)
 rt,strong,vocab=prepare()
 if a.preflight:preflight(rt,strong,vocab);return
 def pause(*args):(ROOT/f'PAUSE-{a.label}').touch()
 signal.signal(signal.SIGTERM,pause);signal.signal(signal.SIGUSR1,pause)
 children=[]
 for wid in range(a.workers):
  pid=os.fork()
  if pid==0:
   try:work(a.label,wid,rt,strong,vocab)
   except BaseException as error:
    dump(ROOT/f'worker-error-{a.label}-{wid}.json',dict(utc=utc(),error=repr(error),traceback=traceback.format_exc()));os._exit(1)
   os._exit(0)
  children.append(pid)
 dump(ROOT/f'controller-{a.label}.json',dict(utc=utc(),pid=os.getpid(),pgid=pgid,worker_pids=children,cpu_lease=slots))
 statuses={pid:os.waitpid(pid,0)[1] for pid in children};dump(ROOT/f'controller-finished-{a.label}.json',dict(utc=utc(),statuses=statuses));assert not any(statuses.values()),statuses
if __name__=='__main__':main()
