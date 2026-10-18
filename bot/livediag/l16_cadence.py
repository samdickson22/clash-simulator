"""Isolated L16 Battle Log driver for live-diag; never touches deck-search banks.

Use the caller's pinned checkout on PYTHONPATH. History-noise modes require its
RoyaleSim bind_rsim hook (main6d90040d8 or reviewed descendant). No game is run by
--help. All results retain the truth per-play log for both seats.
"""
import argparse,hashlib,json,os,random,subprocess,traceback
from pathlib import Path
from collections import Counter
from sam_common import OLD,DECKS,utc,sha,dump
OLD=Path(os.environ.get('LIVEDIAG_OLD',str(OLD)))   # live-diag: a read-only mirror of bot-deckopt2 on hosts without it (bot-livediag/mirror/)

def build_runtime(vocab_path=None):
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
 return rt,strong,json.loads(Path(vocab_path or OLD/'fullpool/vocab-combined.json').read_text())   # live-diag: --vocab (pool v3 full-scope vocab)

def run_worker(wid,args,bank,rt,strong,vocab):
 import fullpool_eval as fp
 from fullpool_worker import configure
 from fullpool_clean import problems
 from bot.players.royalesim_match import play_match
 from bot.livediag.ours_diag import PacketRecorder
 from bot.search.lopp import FAILURES
 config=json.loads((OLD/'fullpool/player-config.json').read_text())
 plan_table=json.loads(Path(args.plan_table).read_text()) if args.plan_table else None
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
    fv2='fv2' in suffix.split('-');suffix='-'.join(t for t in suffix.split('-') if t and t!='fv2')
    sdiag='sdiag' in suffix.split('-');suffix='-'.join(t for t in suffix.split('-') if t and t!='sdiag')   # play-quality owner: v2 shadow recorder (bot/pq/shadow.py), analysis only   # play-quality owner: the HP1 v2 human policy @tau* as the fast tier (cutoff default)
    suffix='-'.join(t for t in suffix.split('-') if t not in ('cych','cycs'))
    pl=next((t[2] for t in suffix.split('-') if t in ('PLx','PLd','PLr')),None);suffix='-'.join(t for t in suffix.split('-') if t not in ('PLx','PLd','PLr'))   # LV2 planner levels (bot/search/levelplan.py): x = true levels, d = ours true + opponent from --plan-table
    bn=next((t[2:] for t in suffix.split('-') if t[:2]=='bn' and t[2:] in ('off','v11','v14c','v11x3')),None)   # cycle-model owner's board-noise wrapper
    suffix='-'.join(t for t in suffix.split('-') if not (t[:2]=='bn' and t[2:] in ('off','v11','v14c','v11x3')))
    name=config['players'][int(kind=='res')]
    factory=fp.LIVE+('-res' if kind=='res' else '')+(('-'+suffix) if suffix else '')+('-wint' if wintp else '')
    if case['opponent']=='LIVE-K4CW-r16-fp':   # live-diag: K4CW-r16 on the full-pool belief + f1a2 fast tier (bot/livediag/k4cw_fp.py)
     from bot.livediag.k4cw_fp import make_k4cw_fp
     observed=fp.players(rt,factory,'R3a',seat,strong_rt=strong)
     observed[1-seat]=fp.Observed(make_k4cw_fp(rt,fp.FAST),'strong opponent full-pool','FullPoolBelief',fp.FAST.split(':',1)[1])
    elif case['opponent']=='HPv2':   # play-quality owner: the HP1 v2 human policy @tau* alone (human-like opponent row)
     from bot.eval.headline import make_player
     from bot.search.lopp_fast import V2_TAU,human_policy_path
     observed=fp.players(rt,factory,'R3a',seat,strong_rt=strong)
     observed[1-seat]=fp.Observed(make_player(rt,f'student:{human_policy_path()}@{V2_TAU}'),'v2 human policy')
    else:observed=fp.players(rt,factory,case['opponent'],seat,strong_rt=strong)
    if kind=='pv2':   # play-quality owner: the HP1 v2 human policy @tau* ALONE in our seat (LivePlayer fast tier)
     from bot.live.player import LivePlayer
     from bot.search.lopp_fast import V2_TAU,human_policy_path
     assert not (suffix or wint or wintp or fv2 or sdiag or cyc or pl or bn is not None),'pv2 takes no tokens'
     pol=LivePlayer(rt,tier='fast',fast_spec=f'student:{human_policy_path()}@{V2_TAU}',name='pv2');assert pol.deadline_seconds is None
     observed[seat]=fp.Observed(pol,'v2 policy alone',None,str(human_policy_path()))
    if wintp:
     w=observed[seat].rec.inner;assert type(w).__name__=='Interruptible' and type(w).__module__=='bot.search.interrupt',type(w)
     w.live.fast=w.__dict__.pop('fast')
    if kind!='pv2':configure(observed,seat,name,config)  # clear live/search/Recorder deadlines BEFORE adding wrappers
    if wintp:
     w.live.deadline_seconds=None;assert w.deadline_seconds is None and w.live.search.deadline_seconds is None
    if fv2:
     from bot.live.player import load_fast
     from bot.search.lopp_fast import V2_TAU,human_policy_path
     live=w.live if wintp else observed[seat].rec.inner;assert type(live).__name__=='LivePlayer',type(live)
     live.fast=load_fast(rt,f'student:{human_policy_path()}@{V2_TAU}');row['fast_tier']=str(live.fast.path);observed[seat].expected_fast=str(human_policy_path())
    own=observed[seat]
    if wint:
     from bot.livediag.variants import Interruptible
     own.rec.inner=Interruptible(rt,own.rec.inner);assert own.rec.inner.deadline_seconds is None
    if cyc:
     assert not wint,'cyc and wint are not combined'
     from bot.cyclemodel.ab import CycleGuardPlayer
     own.rec.inner=CycleGuardPlayer(rt,own.rec.inner,cyc,f'cyc-{cyc}:{name}')
    if bn is not None:   # bot/livediag/board_noise.py: own troops relabelled as enemy in our view (after wint/cyc, before history noise)
     from bot.livediag.board_noise import BoardNoisePlayer
     own.rec.inner=BoardNoisePlayer(rt,own.rec.inner,bn,case['seed'],seat)
    if noise!='clean':
     from bot.livediag.history_noise import NoisyPlayer
     assert hasattr(NoisyPlayer,'bind_rsim'),'RoyaleSim noise hook missing; use main6d90040d8 or reviewed descendant'
     noisy=NoisyPlayer(rt,own.rec.inner,noise,f'histnoise:{noise}:{name}')
     noisy.opp_deck=list(case['opponent_deck'])
     own.rec.inner=noisy;own.rec.name=noisy.name
    if sdiag:
     from bot.pq.shadow import ShadowRecorder
     from bot.search.levelplan import find_search
     from bot.search.lopp_fast import V2_TAU,human_policy_path
     recorder=ShadowRecorder(rt,own,find_search(own),human_policy_path(),V2_TAU)
    else:recorder=PacketRecorder(rt,own)
    assert recorder.deadline_seconds is None and own.deadline_seconds is None
    players=dict(observed);players[seat]=recorder
    own_deck=case['own_deck'];decks=[own_deck,case['opponent_deck']] if seat==0 else [case['opponent_deck'],own_deck]
    if args.levels=='account':   # live-diag PEKKA-1 secondary row: our account levels vs the Battle Log row's logged levels
     ours={c:int(v) for c,v in (x.split('=') for x in args.our_levels.split(','))};king=ours.pop('King')
     lv_own={c:ours[c] for c in own_deck};lv_opp={c:int(case['opponent_levels'][c]) for c in case['opponent_deck']}
     levels=[lv_own,lv_opp] if seat==0 else [lv_opp,lv_own];towers=[king,int(case['opponent_king'])] if seat==0 else [int(case['opponent_king']),king]
    else:levels=[{c:16 for c in deck} for deck in decks];towers=[16,16]
    assert not (pl and 'RF' in suffix.split('-')),'RF and PL<x> both install root_fn; not combined yet'
    if pl:   # LV2: our planner plans at levels (default: L11 rollouts); the opponents' planners are unchanged
     from bot.search.levelplan import install as install_levels,dist_level
     seat_lv=levels[seat];opp_lv=levels[1-seat] if pl=='x' else (lambda c,_own=dict(seat_lv):dist_level(plan_table,c,_own))   # PLd: table level for every card (no deck knowledge)
     if pl=='r':   # play-quality owner PLr (revealed levels): table level until a card is played, then its true level (public level badge); true King level (public)
      from bot.search.revealed_levels import RevealedLevels
      opp_lv=RevealedLevels(levels[1-seat],lambda c,_own=dict(seat_lv):dist_level(plan_table,c,_own))
     plan_towers=list(towers)
     if pl=='d':plan_towers[1-seat]=int(plan_table['king'])
     row['planner_levels']=dict(arm=pl,status=install_levels(rt,observed[seat],seat,decks,seat_lv,opp_lv,plan_towers),own=seat_lv,opp=opp_lv.truth if pl=='r' else opp_lv if pl=='x' else {c:opp_lv(c) for c in case['opponent_deck']},towers=plan_towers)
     assert row['planner_levels']['status'].startswith('exact'),row['planner_levels']['status']
     if pl=='r':
      from bot.search.levelplan import find_search
      opp_lv.bind(find_search(observed[seat]),seat);row['planner_levels']['revealed']=opp_lv.log
    before=Counter(FAILURES)
    result=play_match(rt,players,seed=case['seed'],decks=decks,vocab=vocab,client='16.402',levels=levels,tower_levels=towers,verbose=True)
    result['public_diagnostics']={str(side):fp.diagnostics(p,result) for side,p in observed.items()}
    if 'LP' in ''.join(t[:2] for t in suffix.split('-')):   # play-quality owner: lag-projection counters (bot/search/lagproj.py)
     from bot.search.levelplan import find_search
     row['lagproj_stats']=dict(getattr(find_search(observed[seat]),'lagproj_stats',None) or {})
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
       failures=failures,live_errors=errors,unmapped=unmapped,truth_levels=levels,truth_tower_levels=towers,
       packet_perc=recorder.perc,packet_dec=recorder.dec,shadow=getattr(recorder,'shadow',None),
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
 parser.add_argument('--only',default='',help='comma-separated case indices: re-run exactly these (same seeds) of the bank')
 parser.add_argument('--pool',type=Path,default=None,help='opponent Battle Log pool jsonl (default v1 = OLD/opponent-decks.jsonl, 91 rows); v2: bot.livediag.build_bl_pool')
 parser.add_argument('--opponents',default='LIVE-K4CW-r16,R3a');parser.add_argument('--shard',default='',help='K/N: only cases with index %% N == K (same bank on several hosts)')
 parser.add_argument('--pair-opponents',action='store_true',help='live-diag: the same seed / deck / seat for case i against every opponent (paired opponent calibration)')
 parser.add_argument('--strata',default='',help="live-diag: 'name=i,j,..;name2=..' pool row indices per stratum; --cases cases per stratum")
 parser.add_argument('--levels',default='l16',choices=['l16','account'],help='account: --our-levels vs each row\'s logged opp_levels + opp_king_level')
 parser.add_argument('--own-deck',default='',help='our 8 cards (engine names, as the cycle owner LVG2 copy); default DECKS[sam] (the old Giant deck)')
 parser.add_argument('--our-levels',default='',help='account row: Card=level,...,King=k (our live account)')
 parser.add_argument('--plan-table',default='',help='LV2: opponent level table for PLd arms (bot/fullpool/lv2_table.py)')
 parser.add_argument('--vocab',type=Path,default=None,help='RoyaleSim translator vocab (default OLD/fullpool/vocab-combined.json; pool v3: the full-scope vocab)')
 parser.add_argument('--players',default='base,res');parser.add_argument('--noise',default='clean',help='clean,spells,live,raw; comma separated')
 args=parser.parse_args()
 assert 1<=args.workers<=40 and args.cases>0
 assert not args.own_deck or (len(set(args.own_deck.split(',')))==8 and args.decks=='sam'),'--own-deck: 8 distinct cards, replaces DECKS[sam]'
 assert (args.levels=='account')==bool(args.our_levels),'--our-levels exactly with --levels account'
 assert set(args.opponents.split(','))<= {'LIVE-K4CW-r16','LIVE-K4CW-r16-fp','R3a','v1','HPv2'}
 assert all(p=='pv2' or p.partition('-')[0] in ('base','res') and (not p.partition('-')[2] or all(__import__('re').fullmatch(r'si\d+r?|K\d+|T\d+|H\d+|PL[xdr]|rh|wint|wintp|cych|cycs|lb|bT\d+u\d+|bS\d+u\d+|bn(off|v11|v14c|v11x3)|sh\d+|RF0?|hk\d+|fv2|LP\d+|mkv2|pt\d+|sdiag',t) for t in p.partition('-')[2].split('-'))) for p in args.players.split(','))
 assert all(n=='clean' or (n.split('+')[0] in ('spells','live','raw','none','v2') or __import__('re').fullmatch(r'own(bad)?\d+(m\d+)?', n.split('+')[0])) for n in args.noise.split(','))   # live-diag: +vt<D> / +ph<P> modifiers
 assert os.environ.get('PYTHONHASHSEED')=='0' and os.environ.get('NUMPY_MADVISE_HUGEPAGE')=='0'
 assert 'BOT_BELIEF_PRIOR' not in os.environ and 'CLASHER_LIVE_FAST' not in os.environ
 assert str(args.out).startswith('/mpac/sdicks02/jobs/clasher/bot-')
 assert not args.out.exists(),'Fresh out directory required; do not silently retry/exclude cases'
 args.out.mkdir(parents=True);(args.out/'rows').mkdir()
 pool=args.pool or OLD/'opponent-decks.jsonl'
 population=[json.loads(line) for line in Path(pool).read_text().splitlines() if line.strip()]
 assert len(population)==91 if args.pool is None else len(population)>=91
 assert args.decks!='dd1' or args.pool is None,'DD1 is defined on the v1 pool'
 from bot.fullpool.cards import engine_name
 cases=[]
 bl=[sorted(engine_name(c) for c in d['opp_deck']) for d in population];distinct=[]
 for d in bl:
  if d not in distinct:distinct.append(d)
 S62=['Valkyrie','Archers','Bats','Cannon','Fireball','Zap','MiniPekka','Giant'];E16=['Valkyrie','Archers','Minions','Cannon','Fireball','Giant','MiniPekka','Musketeer']
 INF=['Valkyrie','Archers','Goblins','InfernoTower','Fireball','Giant','MiniPekka','Skeletons'];DD1_OWN=[S62,E16,INF]+[list(bl[i]) for i in (1,28,30,64,76)]
 strata=[(n,[int(x) for x in v.split(',') if x]) for n,_,v in (t.partition('=') for t in args.strata.split(';') if t)]
 for oi,opponent in enumerate(args.opponents.split(',') if strata else []):   # live-diag: --strata (pool v3 PEKKA-1)
  for si,(sname,idxs) in enumerate(strata):
   for i in range(args.cases):
    seed=args.base+(0 if args.pair_opponents else oi*len(strata)*(args.cases+1))+si*(args.cases+1)+i;rng=random.Random(seed);source=idxs[rng.randrange(len(idxs))]
    row=population[source];deck=[engine_name(c) for c in row['opp_deck']];own=list(args.own_deck.split(',') if args.own_deck else DECKS['sam']);other=list(deck);rng.shuffle(own);rng.shuffle(other)
    lv=dict(zip(deck,row.get('opp_levels') or [None]*8))
    assert args.levels!='account' or (all(lv.get(c) for c in deck) and row.get('opp_king_level')),('account row needs logged levels',row.get('run'))
    cases.append(dict(id=f'{oi}-{sname}-{i:04d}',index=si*args.cases+i,seed=seed,seat=i%2,opponent=opponent,stratum=sname,source_index=source,
     source_run=row.get('run'),own_deck=own,opponent_deck=other,opponent_levels=lv,opponent_king=row.get('opp_king_level')))
 for oi,opponent in enumerate([] if strata else args.opponents.split(',')):
  for i in range(args.cases):
   if args.decks=='dd1':
    assert len(distinct)==49,len(distinct)
    seed=args.base+i;rng=random.Random(seed);source=(i//8)%49
    own=list(DD1_OWN[i%8]);other=list(distinct[source]);rng.shuffle(own);rng.shuffle(other)
    cases.append(dict(id=f'{oi}-{i:04d}',index=i,seed=seed,seat=(i//8)%2,opponent=opponent,source_index=source,own_index=i%8,own_deck=own,opponent_deck=other))
    continue
   seed=args.base+(0 if args.pair_opponents else oi*(args.cases+1))+i;rng=random.Random(seed);source=rng.randrange(len(population))
   own=list(args.own_deck.split(',') if args.own_deck else DECKS['sam']);other=[engine_name(c) for c in population[source]['opp_deck']];rng.shuffle(own);rng.shuffle(other)
   cases.append(dict(id=f'{oi}-{i:04d}',index=i,seed=seed,seat=i%2,opponent=opponent,source_index=source,own_deck=own,opponent_deck=other))
 if args.only:
  keep={int(x) for x in args.only.split(',') if x}
  cases=[c for c in cases if c['index'] in keep]
 import bot.players.runtime as runtime_module
 source=Path(runtime_module.__file__).resolve().parents[2]
 assert ('PLd' in args.players or 'PLr' in args.players)==bool(args.plan_table),'--plan-table exactly with PLd/PLr arms'
 bank=dict(created_utc=utc(),own_deck=args.own_deck or None,plan_table=args.plan_table or None,plan_table_sha256=sha(args.plan_table) if args.plan_table else None,base=args.base,pair_opponents=args.pair_opponents,decks=args.decks,cases=cases,cases_per_policy=args.cases,players=args.players,noise=args.noise,
  card_levels=16 if args.levels=='l16' else 'account',tower_levels=[16,16] if args.levels=='l16' else 'account',levels=args.levels,our_levels=args.our_levels,strata=args.strata,vocab_path=str(args.vocab or OLD/'fullpool/vocab-combined.json'),vocab_sha256=sha(args.vocab or OLD/'fullpool/vocab-combined.json'),population_sha256=sha(pool),population_path=str(pool),population_rows=len(population),
  source_checkout=str(source),source_commit=(subprocess.run(['git','-C',str(source),'rev-parse','HEAD'],text=True,capture_output=True).stdout.strip() or 'nogit'),
  driver_sha256=sha(__file__),factory_sha256=sha(OLD/'fullpool_eval.py'))
 dump(args.out/'bank.json',bank,True)
 pgid=os.getpgrp();reserved=0
 for p in Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims').glob('lease-*'):
  try:n,g=map(int,p.read_text().split())
  except (OSError,ValueError):continue
  if g==pgid:reserved=max(reserved,n)
 assert reserved>=args.workers+2,(reserved,args.workers)
 rt,strong,vocab=build_runtime(args.vocab);children=[]
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
