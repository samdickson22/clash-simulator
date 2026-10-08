"""Explicit train/dev-only packed-store reader. No root plan or eval metadata read."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib,json,multiprocessing,os,resource,socket,time
from pathlib import Path
import numpy as np
from .metrics import Game,archetype,extract

COLUMNS=('submitted_ticks','global_features','hand_ids','own_deck','entity_offsets',
         'flat_entity_features','flat_entity_ids','expert_actions','expert_action_supervision_valid',
         'submitted_world_positions','recorded_play_ticks','tower_clamped','own_queue')
STORE=None;CATALOG=None


def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,separators=(',',':'),allow_nan=False)+'\n');tmp.replace(path)


def make_catalog(builder):
    from clasher.spells import SPELL_REGISTRY
    cards={};bodies={}
    for name in builder.card_vocab:
        try: c=builder.loader.get_card(name)
        except (KeyError,ValueError): continue
        spell=SPELL_REGISTRY.get(name)
        if isinstance(spell,type): spell=spell()
        sp=None
        if str(c.card_type).lower()=='spell' or spell is not None:
            sp=dict(radius=float(getattr(spell,'radius',0) or 0),
                    radial_instant=name in ('Fireball','Zap','GiantSnowball','Snowball','Rocket'))
        cards[name]=dict(token=int(builder.token_id(name,namespace='card_action')),
                         cost=float(c.mana_cost),spell=sp)
    for token,name in enumerate(builder.token_names):
        # Static metadata only. Swarm cost apportioned by nominal summon count.
        try:
            c=builder.loader.get_card(name)
            cost=float(c.mana_cost)/max(1,int(c.summon_count or 1))
        except (KeyError,ValueError,AttributeError): cost=0.
        bodies[str(token)]=dict(name=name,tower=('tower' in name.lower()),unit_cost=cost)
    return dict(cards=cards,bodies=bodies,token_names=list(builder.token_names))


class TrainDevStore:
    def __init__(self,root,role):
        if role not in ('train','dev'): raise ValueError('human role must be train or dev')
        self.path=Path(root)/role
        if self.path.is_symlink(): raise ValueError('role directory must not be a symlink')
        self.manifest=json.loads((self.path/'manifest.json').read_text())
        if self.manifest['role']!=role: raise ValueError('role manifest mismatch')
        self.role=role
        self.arrays={n:np.load(self.path/f'{n}.npy',mmap_mode='r',allow_pickle=False) for n in COLUMNS}
        if any(p['role']!=role for p in self.manifest['perspectives']): raise ValueError('mixed-role manifest')

    def game(self,item,catalog):
        z=self.arrays;s=item['target_start'];end=s+item['rows'];summary=item['summary']
        # Exclude every frame at/after first tower clamp or projected label.
        # Those continuations distort pressure and tower-damage diagnostics.
        cut=summary.get('cut_tick',2**31)
        if summary.get('first_clamp_tick') is not None:cut=min(cut,summary['first_clamp_tick'])
        ts=np.asarray(z['submitted_ticks'][s:end]);end=s+int(np.searchsorted(ts,cut,side='left'))
        if end-s<2:return None
        a=int(z['entity_offsets'][s]);b=int(z['entity_offsets'][end])
        deck=summary['own_deck'];tokens=sorted(catalog['cards'][n]['token'] for n in deck)
        if sorted(map(int,z['own_deck'][s]))!=tokens: raise ValueError('vocabulary/deck mismatch')
        g=np.asarray(z['global_features'][s:end]);hands=np.asarray(z['hand_ids'][s:end]);ticks=np.asarray(z['submitted_ticks'][s:end])
        plays=[]
        for j in np.flatnonzero((z['expert_actions'][s:end]<2304)&z['expert_action_supervision_valid'][s:end]):
            action=int(z['expert_actions'][s+j]);token=int(hands[j,action//576]);names=[n for n in deck if catalog['cards'][n]['token']==token]
            if len(names)!=1: raise ValueError('unresolved played card')
            # Labels can be scheduled later in their 5-tick observation window.
            pt=max(int(ticks[j]),int(z['recorded_play_ticks'][s+j]))
            xy=np.asarray(z['submitted_world_positions'][s+j],float)
            if summary['seat']==1:xy=np.array([18.,32.])-xy
            if not np.isfinite(xy).all():continue
            # Pre-play balance advances naturally to its execution tick.
            phase=2 if g[j,3]>.5 else 1 if g[j,2]>.5 else 0
            elixir=min(10.,float(g[j,5])*10+(pt-int(ticks[j]))*[.0178,.0357,.0537][phase])
            plays.append(dict(tick=pt,card=names[0],x=float(xy[0]),y=float(xy[1]),accepted=True,elixir_before=elixir))
        from clasher.rl.c56_scripted import C56_ADDED_CARDS
        from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS
        base=all(f=='base' for f in summary.get('own_forms',[])+summary.get('opponent_forms',[]))
        c56=set(deck+summary['opponent_deck']) <= (SUPPORTED_CARDS | C56_ADDED_CARDS)
        return Game(item['identity'],summary['match_id'],'human',self.role,
            archetype(deck)+' vs '+archetype(summary['opponent_deck']),deck,
            float(summary['recorded_result']<0),ticks,g,hands,
            np.asarray(z['entity_offsets'][s:end+1])-a,np.asarray(z['flat_entity_features'][a:b]),
            np.asarray(z['flat_entity_ids'][a:b]),plays,
            dict(cut_reason=summary['cut_reason'],retained_rows=end-s,original_rows=item['rows'],
                 c56=bool(c56),c56_base=bool(base and c56),own_deck=deck,opponent_deck=summary['opponent_deck'],
                 own_elixir_topups=summary['counters'].get('own_elixir_topups',0),
                 source='C56/S122 command reconstruction',strength='not pro-qualified',
                 mode=summary['info'].get('battle_type'),forms=summary.get('own_forms'),
                 max_overshoot_frac=summary.get('max_overshoot_frac'),
                 projected_plays=summary['counters'].get('own_plays_projected',0)),
            np.asarray(z['own_queue'][s:end]))


def process(item):
    start=time.process_time()
    game=STORE.game(item,CATALOG)
    if game is None:return None
    result=extract(game,CATALOG);result['cpu_seconds']=time.process_time()-start
    return result


def main():
    global STORE,CATALOG
    ap=argparse.ArgumentParser();ap.add_argument('--store',type=Path,required=True);ap.add_argument('--role',choices=('train','dev'),required=True)
    ap.add_argument('--workers',type=int,required=True);ap.add_argument('--limit',type=int);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--partition',type=int,default=0);ap.add_argument('--partitions',type=int,default=1)
    args=ap.parse_args();start=time.monotonic()
    if args.out.resolve().is_relative_to(args.store.resolve()):raise ValueError('output must be outside the source store')
    if (args.out/'games.jsonl').exists():raise ValueError('use a fresh output directory')
    from clasher.rl.contract_v5 import ContractV5ObservationBuilder
    CATALOG=make_catalog(ContractV5ObservationBuilder());STORE=TrainDevStore(args.store,args.role)
    all_items=STORE.manifest['perspectives'];items=[p for p in all_items if int(hashlib.sha256(p['identity'].encode()).hexdigest(),16)%args.partitions==args.partition]
    # Exclude projected trajectories entirely, not only the projected row.
    items=[p for p in items if p['summary']['counters'].get('own_plays_projected',0)==0]
    if args.limit:items=items[:args.limit]
    args.out.mkdir(parents=True,exist_ok=True);write(args.out/'catalog.json',CATALOG)
    count=frames=0;cpu=0
    with (args.out/'games.jsonl').open('w') as stream,ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('fork')) as pool:
        for result in pool.map(process,items,chunksize=8):
            if result is None:continue
            stream.write(json.dumps(result,separators=(',',':'))+'\n');count+=1;frames+=result['frames'];cpu+=result['cpu_seconds']
            if count%1000==0:print(json.dumps(dict(games=count,frames=frames,wall=time.monotonic()-start)),flush=True)
    write(args.out/'receipt.json',dict(role=args.role,available=len(all_items),eligible=len(items),games=count,frames=frames,
          wall_seconds=time.monotonic()-start,worker_cpu_seconds=cpu,workers=args.workers,host=socket.gethostname(),
          nice=os.getpriority(os.PRIO_PROCESS,0),affinity=sorted(os.sched_getaffinity(0)),
          role_manifest_sha256=hashlib.sha256((STORE.path/'manifest.json').read_bytes()).hexdigest(),
          input_columns=COLUMNS,partition=args.partition,partitions=args.partitions))

if __name__=='__main__':main()
