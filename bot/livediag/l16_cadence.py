"""Isolated L16 Battle Log driver for live-diag; never touches deck-search banks.

Use the caller's pinned checkout on PYTHONPATH. History-noise modes require its
RoyaleSim bind_rsim hook (main6d90040d8 or reviewed descendant). No game is run by
--help. All results retain the truth per-play log for both seats.
"""
import argparse,hashlib,json,os,random,subprocess,traceback
from pathlib import Path
from collections import Counter
from sam_common import OLD,DECKS,utc,sha,dump

def build_runtime():
 import fullpool_eval as fp
 from bot.levels.placement_probe import installed_identity
 meta=json.loads((OLD/'fullpool/manifest.json').read_text())
 assert installed_identity()==meta['simulator']
 assert all(sha(OLD/'fullpool'/p)==v for p,v in meta['models'].items())
 fp.MODEL_ROOT=OLD/'fullpool/models'
 fp.FAST=f'student:{fp.MODEL_ROOT}/fits/f1a2/step-001200.pt'
 fp.OLD_FAST=f'student:{fp.MODEL_ROOT}/students/it5s2-step001200.pt@0.5375'
 rt=fp.runtime(fp.BELIEF);strong=fp.runtime('c56')
 for current in (rt,strong):
  assert current.pins['native_sha256']==meta['native_sha256']
  assert current.pins['gamedata_sha256']==meta['gamedata_sha256']
  fp.install_placement(current);current.STUDENT
 return rt,strong,json.loads((OLD/'fullpool/vocab-combined.json').read_text())

def run_worker(wid,args,bank,rt,strong,vocab):
 import fullpool_eval as fp
 from fullpool_worker import configure
 from fullpool_clean import problems
 from bot.players.royalesim_match import play_match
 from bot.livediag.ours_diag import PacketRecorder
 from bot.search.lopp import FAILURES
 config=json.loads((OLD/'fullpool/player-config.json').read_text())
 arms=[(p,n) for p in args.players.split(',') for n in args.noise.split(',')]
 for index,case in enumerate(bank['cases']):
  sk,sn=(int(x) for x in args.shard.split('/')) if args.shard else (0,1)   # live-diag: --shard K/N
  if index%sn!=sk or (index//sn)%args.workers!=wid:continue
  order=list(range(len(arms)));random.Random(case['seed']^0xA4A4).shuffle(order)
  for arm in order:
   player,noise=arms[arm];seat=case['seat'];output=args.out/'rows'/f'{index:06d}-{arm:02d}.json'
   assert not output.exists(),output
   row=dict(case,player=player,noise_arm=noise,bank_sha256=sha(args.out/'bank.json'),started_utc=utc(),host=os.uname().nodename)
   try:
    kind,_,suffix=player.partition('-')   # live-diag cadence copy: 'base-si5', 'res-si2r' -> LIVE[-res]-si<k>[r]
    wint='wint' in suffix.split('-');suffix='-'.join(t for t in suffix.split('-') if t and t!='wint')   # -wint: bot.livediag.variants.Interruptible facade
    cyc=next((dict(cych='hard',cycs='soft')[t] for t in suffix.split('-') if t in ('cych','cycs')),None)   # cycle-model owner's guard wrapper
    wintp='wintp' in suffix.split('-');suffix='-'.join(t for t in suffix.split('-') if t and t!='wintp')   # live port of wint
    suffix='-'.join(t for t in suffix.split('-') if t not in ('cych','cycs'))
    name=config['players'][int(kind=='res')]
    factory=fp.LIVE+('-res' if kind=='res' else '')+(('-'+suffix) if suffix else '')+('-wint' if wintp else '')
    observed=fp.players(rt,factory,case['opponent'],seat,strong_rt=strong)
    if wintp:
     w=observed[seat].rec.inner;assert type(w).__name__=='Interruptible' and type(w).__module__=='bot.search.interrupt',type(w)
     w.live.fast=w.__dict__.pop('fast')
    configure(observed,seat,name,config)  # clear live/search/Recorder deadlines BEFORE adding wrappers
    if wintp:
     w.live.deadline_seconds=None;assert w.deadline_seconds is None and w.live.search.deadline_seconds is None
    own=observed[seat]
    if wint:
     from bot.livediag.variants import Interruptible
     own.rec.inner=Interruptible(rt,own.rec.inner);assert own.rec.inner.deadline_seconds is None
    if cyc:
     assert not wint,'cyc and wint are not combined'
     from bot.cyclemodel.ab import CycleGuardPlayer
     own.rec.inner=CycleGuardPlayer(rt,own.rec.inner,cyc,f'cyc-{cyc}:{name}')
    if noise!='clean':
     from bot.livediag.history_noise import NoisyPlayer
     assert hasattr(NoisyPlayer,'bind_rsim'),'RoyaleSim noise hook missing; use main6d90040d8 or reviewed descendant'
     noisy=NoisyPlayer(rt,own.rec.inner,noise,f'histnoise:{noise}:{name}')
     noisy.opp_deck=list(case['opponent_deck'])
     own.rec.inner=noisy;own.rec.name=noisy.name
    recorder=PacketRecorder(rt,own)
    assert recorder.deadline_seconds is None and own.deadline_seconds is None
    players=dict(observed);players[seat]=recorder
    own_deck=case['own_deck'];decks=[own_deck,case['opponent_deck']] if seat==0 else [case['opponent_deck'],own_deck]
    levels=[{c:16 for c in deck} for deck in decks]
    before=Counter(FAILURES)
    result=play_match(rt,players,seed=case['seed'],decks=decks,vocab=vocab,client='16.402',levels=levels,tower_levels=[16,16],verbose=True)
    result['public_diagnostics']={str(side):fp.diagnostics(p,result) for side,p in observed.items()}
    failures=dict(Counter(FAILURES)-before)
    errors={str(side):[d for d in getattr(p.rec.inner,'decisions',[]) if 'error' in d or d.get('native_failures')] for side,p in observed.items()}
    unmapped={k:v for k,v in result['translator'].items() if v and ('unmapped' in k or 'missing' in k)}
    issues=[]
    if not result['terminal']:issues.append('nonterminal')
    if failures:issues.append('native failures')
    if any(errors.values()):issues.append('live errors')
    if result['channels'][seat]['rejected']:issues.append('our command rejections')
    if unmapped:issues.append('unmapped public rows')
    row.update(result=result,win=int(result['winner']==seat),draw=int(result['winner'] is None),issues=issues,
       failures=failures,live_errors=errors,unmapped=unmapped,truth_levels=levels,truth_tower_levels=[16,16],
       packet_perc=recorder.perc,packet_dec=recorder.dec,
       noise_counts=dict(getattr(getattr(own.rec.inner,'noise',None),'counts',{}) or {}))
   except BaseException as error:row.update(error=repr(error),traceback=traceback.format_exc())
   dump(output,row)
   assert not problems(row),('unclean row retained',output,problems(row))

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--out',type=Path,required=True);parser.add_argument('--base',type=lambda s:int(s,0),required=True)
 parser.add_argument('--cases',type=int,required=True,help='paired cases PER opponent policy')
 parser.add_argument('--workers',type=int,default=1)
 parser.add_argument('--decks',default='sam',choices=['sam','dd1'],help='dd1: deck-diverse row (bot/fullpool/banks.py DD1)')
 parser.add_argument('--opponents',default='LIVE-K4CW-r16,R3a');parser.add_argument('--shard',default='',help='K/N: only cases with index %% N == K (same bank on several hosts)')
 parser.add_argument('--players',default='base,res');parser.add_argument('--noise',default='clean',help='clean,spells,live,raw; comma separated')
 args=parser.parse_args()
 assert 1<=args.workers<=40 and args.cases>0
 assert set(args.opponents.split(','))<= {'LIVE-K4CW-r16','R3a','v1'}
 assert all(p.partition('-')[0] in ('base','res') and (not p.partition('-')[2] or all(__import__('re').fullmatch(r'si\d+r?|K\d+|T\d+|rh|wint|wintp|cych|cycs',t) for t in p.partition('-')[2].split('-'))) for p in args.players.split(','))
 assert all(n=='clean' or (n.split('+')[0] in ('spells','live','raw','none') or __import__('re').fullmatch(r'own(bad)?\d+(m\d+)?', n.split('+')[0])) for n in args.noise.split(','))   # live-diag: +vt<D> / +ph<P> modifiers
 assert os.environ.get('PYTHONHASHSEED')=='0' and os.environ.get('NUMPY_MADVISE_HUGEPAGE')=='0'
 assert 'BOT_BELIEF_PRIOR' not in os.environ and 'CLASHER_LIVE_FAST' not in os.environ
 assert str(args.out).startswith('/mpac/sdicks02/jobs/clasher/bot-')
 assert not args.out.exists(),'Fresh out directory required; do not silently retry/exclude cases'
 args.out.mkdir(parents=True);(args.out/'rows').mkdir()
 population=[json.loads(line) for line in (OLD/'opponent-decks.jsonl').read_text().splitlines()];assert len(population)==91
 from bot.fullpool.cards import engine_name
 cases=[]
 bl=[sorted(engine_name(c) for c in d['opp_deck']) for d in population];distinct=[]
 for d in bl:
  if d not in distinct:distinct.append(d)
 S62=['Valkyrie','Archers','Bats','Cannon','Fireball','Zap','MiniPekka','Giant'];E16=['Valkyrie','Archers','Minions','Cannon','Fireball','Giant','MiniPekka','Musketeer']
 INF=['Valkyrie','Archers','Goblins','InfernoTower','Fireball','Giant','MiniPekka','Skeletons'];DD1_OWN=[S62,E16,INF]+[list(bl[i]) for i in (1,28,30,64,76)]
 for oi,opponent in enumerate(args.opponents.split(',')):
  for i in range(args.cases):
   if args.decks=='dd1':
    assert len(distinct)==49,len(distinct)
    seed=args.base+i;rng=random.Random(seed);source=(i//8)%49
    own=list(DD1_OWN[i%8]);other=list(distinct[source]);rng.shuffle(own);rng.shuffle(other)
    cases.append(dict(id=f'{oi}-{i:04d}',index=i,seed=seed,seat=(i//8)%2,opponent=opponent,source_index=source,own_index=i%8,own_deck=own,opponent_deck=other))
    continue
   seed=args.base+oi*(args.cases+1)+i;rng=random.Random(seed);source=rng.randrange(91)
   own=list(DECKS['sam']);other=[engine_name(c) for c in population[source]['opp_deck']];rng.shuffle(own);rng.shuffle(other)
   cases.append(dict(id=f'{oi}-{i:04d}',index=i,seed=seed,seat=i%2,opponent=opponent,source_index=source,own_deck=own,opponent_deck=other))
 import bot.players.runtime as runtime_module
 source=Path(runtime_module.__file__).resolve().parents[2]
 bank=dict(created_utc=utc(),base=args.base,decks=args.decks,cases=cases,cases_per_policy=args.cases,players=args.players,noise=args.noise,
  card_levels=16,tower_levels=[16,16],population_sha256=sha(OLD/'opponent-decks.jsonl'),
  source_checkout=str(source),source_commit=(subprocess.run(['git','-C',str(source),'rev-parse','HEAD'],text=True,capture_output=True).stdout.strip() or 'nogit'),
  driver_sha256=sha(__file__),factory_sha256=sha(OLD/'fullpool_eval.py'))
 dump(args.out/'bank.json',bank,True)
 pgid=os.getpgrp();reserved=0
 for p in Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims').glob('lease-*'):
  try:n,g=map(int,p.read_text().split())
  except (OSError,ValueError):continue
  if g==pgid:reserved=max(reserved,n)
 assert reserved>=args.workers+2,(reserved,args.workers)
 rt,strong,vocab=build_runtime();children=[]
 for wid in range(args.workers):
  pid=os.fork()
  if pid==0:
   try:run_worker(wid,args,bank,rt,strong,vocab)
   except BaseException:
    traceback.print_exc();os._exit(1)
   os._exit(0)
  children.append(pid)
 statuses={pid:os.waitpid(pid,0)[1] for pid in children};dump(args.out/'finished.json',dict(utc=utc(),statuses=statuses));assert not any(statuses.values()),statuses
if __name__=='__main__':main()
