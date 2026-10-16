"""All 122 ladder cards, object births/deaths/lifetimes, Python + native.

Run with single-thread libraries, -B and cpu_job.sh 1 on 04/08. Native snapshots
are inspected EVERY tick. Python's insertion journal also retains one-tick
objects removed within a step. Does not mutate the resources or repair tables.
"""
import argparse
import hashlib
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import traceback

TREE = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(TREE))
sys.path.insert(0, str(TREE / 'reports/cards/tools'))
KINDS = ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity')
TARGETS={'RageBarbarian':'BarbarianRageDamage','Rage':'RageDamage',
         'GoblinDrill':'GoblinDrillDamage','IceWizard':'IceWizardCold','ElectroWizard':'ElectroWizardZap'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--ticks', type=int, default=1500, help='75s exceeds building/effect lifetimes')
    ap.add_argument('--shard', default='0/1', help='disjoint card shard index/count')
    ap.add_argument('--cards', nargs='*', help='development subset; omitted for the class gate')
    a = ap.parse_args()
    from bot.players.runtime import Runtime
    rt = Runtime(verify=True)
    R = rt.R
    import numpy as np
    import clasher_core
    from differential import initial, snapshot, config
    from fair_player import Information
    from pool import ladder_pool
    from clasher.arena import Position
    from bot.cards.fc_cut import SideCut, strings
    from bot.players.royalesim_translate import complete_vocab, Translator
    vocab = json.loads((TREE / 'bot/players/royalesim_vocab.json').read_text())
    original_vocab = vocab
    vocab = complete_vocab(rt, vocab)
    for table in ('units','spells','projectiles','statics'):
        assert all(vocab[table][key]==value for key,value in original_vocab[table].items()),table
    translator=Translator.__new__(Translator)
    translator.statics={key:(value['cols'],value['level'],value['motion']) for key,value in vocab['statics'].items()}
    translator.stats=Counter()
    translator.vocab=vocab
    translator.templates={(t,KINDS.index(k)) for t,k in R.templates}
    translator.builder=R.builder
    translator.units={k:tuple(v) for k,v in vocab['units'].items()}
    translator.lower_units={k.lower():v for k,v in translator.units.items()}
    translator.lower_tokens={n.lower():n for n in R.builder.token_names}
    translator.F={n:i for i,n in enumerate(('team','kind','x','y','status_flags','unit_type','hp','max_hp','facing'))}
    translator.card_of=sorted(R.config['cards'])
    out = dict(root=str(rt.root), ticks=a.ticks, full_pool=not bool(a.cards), failures=[], objects={},
               scenarios=[], checks=Counter(), buffs=Counter(), templates=len(R.templates))
    out['source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        Path(__file__).resolve(), TREE/'bot/players/royalesim_translate.py',
        TREE/'bot/players/royalesim_vocab.py',TREE/'bot/cards/scope.py',
        TREE/'bot/players/runtime.py',rt.root/'engine-rs/differential.py',
        rt.root/'reports/strategy_council_20260928/engine-speed/stage5/fair_player.py')}
    out['native_materialized_carriers']=[]
    out['target_paths']={}
    out['historical_template_kind_aliases']={f'{t}/{k}':v['entity_kind'] for (t,k),v in R.templates.items()
                                            if v['entity_kind']!=KINDS.index(k)}
    seen = set()
    root_seen = set()
    def check(site, fn):
        out['checks'][site.split('/')[0]] += 1
        try:
            return fn()
        except BaseException as e:
            out['failures'].append(dict(site=site, error=f'{type(e).__name__}: {e}', trace=traceback.format_exc()))
    def require(ok, detail):
        assert ok, detail
    def root_row(b, token, row, seat, board_rows=None):
        packet = R.builder.build_public(b, seat)
        obs = packet.observation
        ids, rows, mask = obs.entity_ids.copy(), obs.entity_features.copy(), obs.entity_mask.copy()
        ids[:] = 0; rows[:] = 0; mask[:] = False
        carriers=board_rows if board_rows is not None else [(token,row)]
        assert len(carriers)<=len(ids),('public capacity',len(carriers),len(ids))
        levels = obs.entity_levels.copy();levels[:]=0
        for i,(t,r) in enumerate(carriers):
            ids[i],rows[i],mask[i],levels[i]=t,r,True,11
            rows[i,:2]=np.clip(rows[i,:2],0.,1.)  # same public arena clipping as _entity_row
        from clasher.rl.contract_v5 import project_public_v5
        actor=replace(obs,entity_ids=ids,entity_features=rows,entity_mask=mask,entity_levels=levels,
                      entity_level_confidence=mask.astype(np.float32))
        packet=project_public_v5(actor,champion_button=True)
        own = b.players[seat]
        enemy = b.players[1-seat]
        info = Information(b.tick, seat, packet, dict(elixir=own.elixir, hand=list(own.hand),
                           cycle=list(own.cycle_queue), refill=own.next_card_refill_cooldown_ms), ())
        opp = dict(elixir=enemy.elixir, hand=list(enemy.hand), cycle=list(enemy.cycle_queue),
                   refill=enemy.next_card_refill_cooldown_ms)
        root = R.root(info, opp, np.random.default_rng(19))
        materialized=json.loads(root.snapshot())['entities']
        require(len(materialized)==len(carriers),('native materialization count',len(materialized),len(carriers)))
        for (t,r),e in zip(carriers,materialized):
            kind=KINDS[int(np.argmax(r[4:9]))]
            template=R.templates[t,kind]
            require((e['class'],e['stats']['name'],e.get('spell_name') or '')==
                    (template['class'],template['stats']['name'],template.get('spell_name') or ''),
                    (t,kind,e['class'],e['stats']['name']))
            if R.builder.token_names[t] in TARGETS.values():
                require(e['entity_kind']==3,(t,kind,e['class']))
            key=f'{t}/{kind}'
            if key not in out['native_materialized_carriers']:out['native_materialized_carriers'].append(key)
        root.step(2)
        from bot.live.levels import LevelRoot, Levels
        # Exercise LIVE's duplicate template lookup without modifying its code.
        live=LevelRoot(R,Levels(own=12,opp=12))
        clasher_core.BattleState(live.payload(info,opp,np.random.default_rng(19))).step(2)
    def inspect_object(b, e, card, mode, engine):
        sig = (engine, card, mode, type(e).__name__, getattr(e.card_stats,'name',''), getattr(e, 'spell_name', ''),e.entity_kind)
        if sig in seen:
            return
        seen.add(sig)
        token, row = R.builder._entity_row(e, 0)
        kind = int(np.argmax(row[4:9]))
        key = f'{token}/{KINDS[kind]}'
        rec = out['objects'].setdefault(key, dict(token_name=R.builder.token_names[token], kind=KINDS[kind],
                cards=[], classes=[], names=[], engines=[], modes=[]))
        for col, val in [('cards',card), ('classes',type(e).__name__), ('names',getattr(e,'spell_name','') or getattr(e.card_stats,'name','')),
                         ('engines',engine), ('modes',mode)]:
            if val not in rec[col]: rec[col].append(val)
        label = f'{card}/{mode}/{engine}/{key}'
        check('template/'+label, lambda: require((token,KINDS[kind]) in R.templates, key))
        check('typed-token/'+label, lambda: require(token > 1, key))
        if kind < 2 and getattr(e.card_stats,'name','') not in ('Tower','KingTower'):
            check('meta-body/'+label, lambda: require(any(v['token']==token for v in R.meta['bodies'].values()), key))
            check('meta-body-name/'+label,lambda:require(getattr(e.card_stats,'name','') in R.meta['bodies'],getattr(e.card_stats,'name','')))
            for style, bot in R.bots.items():
                check('script-body/'+label+'/'+style, lambda bot=bot: require(token in bot.bodies, key))
        # Translator static rows are a per-object lookup, even for effects whose
        # external source schema does not currently carry their identity.
        check('translator-static/'+label, lambda: require(f'{token}/{kind}' in vocab['statics'], key))
        check('translator-object/'+label, lambda: require(vocab['objects'].get(f'{token}/{kind}')==[token,kind],key))
        for seat in (0,1):
            check('translator-row/'+label+'/'+str(seat),lambda:Translator._row(translator,seat,token,kind,e.player_id,
                e.position.x*18000,e.position.y*18000,1.,(0.,1.)))
            check('translator-resolved/'+label+'/'+str(seat),lambda seat=seat:resolved(token,kind,e.player_id,e.position.x,e.position.y,seat))
        if (engine,token,kind) not in root_seen:
            root_seen.add((engine,token,kind))
            for seat in (0,1):
                tok, view = R.builder._entity_row(e, seat)
                check('public-root/'+label+'/'+str(seat), lambda: root_row(b,tok,view,seat))
                if card in TARGETS and R.builder.token_names[tok]==TARGETS[card]:
                    def target_board():
                        obs=R.builder.build_public(b,seat).observation
                        carriers=[(int(t),r.copy()) for t,r in zip(obs.entity_ids[obs.entity_mask],obs.entity_features[obs.entity_mask])]
                        # A journal retains the intra-step birth even if the
                        # engine removed it before this tick's ordinary sensor.
                        carriers.append((tok,view))
                        root_row(b,None,None,seat,board_rows=carriers)
                        out['target_paths'].setdefault(key,dict(card=card,exact_translator_seats=[],native_board_seats=[]))['native_board_seats'].append(seat)
                    check('target-native-board/'+label+'/'+str(seat),target_board)
    def root_board(b,seat):
        from fair_player import observe
        info=observe(b,R.builder,seat,())
        p=b.players[1-seat]
        opp=dict(elixir=p.elixir,hand=list(p.hand),cycle=list(p.cycle_queue),refill=p.next_card_refill_cooldown_ms)
        root=R.root(info,opp,np.random.default_rng(19))
        root.step(2)
        R.native.evaluate(root,seat,1.)
    out['template_inventory']={f'{t}/{k}':R.builder.token_names[t] for t,k in R.templates}
    out['translator_statics']=len(vocab['statics'])
    out['translator_tables']={k:len(vocab[k]) for k in ('units','spells','projectiles','statics','objects')}
    def resolved(token,kind,team,x,y,seat):
        before=translator.stats.copy()
        rows=translator._resolved_rows([(token,kind,team,x*18000,y*18000,1.,(0.,1.))],seat)
        require(len(rows)==1 and rows[0][1]==token and int(np.argmax(rows[0][2][4:9]))==kind,(token,kind,rows))
        require(translator.stats==before,dict(translator.stats-before))
    def mapped(state,expected,seat):
        before=translator.stats.copy()
        rows=translator._rows(state,seat)
        require(len(rows)==1 and (rows[0][1],int(np.argmax(rows[0][2][4:9])))==tuple(expected),(expected,rows))
        require(translator.stats==before,dict(translator.stats-before))
    # Exercise real schema selection and its no_template/drop path. A source
    # spell/motion can represent only one carrier; aliases are documented, not
    # claimed to recover child identities absent from the source schema.
    for table in ('units','spells','projectiles','towers'):
        for name,value in vocab[table].items():
            state=dict(entities=[],spells=[],projectiles=[])
            if table=='units':
                translator.types=[name]
                state['entities']=[[0,value[1],81000,243000,0,0,1,1,[0,1]]]
                expected=value
            elif table=='towers':
                state['entities']=[[0,int(name),81000,243000,0,0,1,1,[0,1]]]
                expected=value
            elif table=='spells':
                card,motion=name.rsplit('/',1)
                require(card in translator.card_of,('spell source absent',card))
                state['spells']=[[0,translator.card_of.index(card),int(motion),81000,243000,81000,261000]]
                expected=value
            else:
                if name in ('king','princess'):
                    state['entities']=[[0,2 if name=='king' else 3,81000,243000,0,0,1,1,[0,1]]]
                    # Only the shot is wanted from this source fixture.
                    firer=-1
                else:
                    require(name in translator.card_of,('projectile source absent',name))
                    firer=translator.card_of.index(name)
                state['projectiles']=[[0,81000,243000,81000,261000,0,0,firer]]
                expected=[value,2]
            for seat in (0,1):
                if table=='projectiles' and name in ('king','princess'):
                    def tower_shot(state=state,expected=expected,seat=seat):
                        before=translator.stats.copy();rows=translator._rows(state,seat)
                        require(len(rows)==2 and (rows[-1][1],int(np.argmax(rows[-1][2][4:9])))==tuple(expected),name)
                        require(translator.stats==before,dict(translator.stats-before))
                    check('translator-mapping/'+table+'/'+name+'/'+str(seat),tower_shot)
                else:
                    check('translator-mapping/'+table+'/'+name+'/'+str(seat),lambda state=state,expected=expected,seat=seat:mapped(state,expected,seat))
    for token,kind in R.templates:
        index=KINDS.index(kind)
        check('all-translator-statics/'+str(token)+'/'+kind,
              lambda token=token,index=index:require(f'{token}/{index}' in vocab['statics'],(token,index)))
    out['config_objects']={}
    def config_objects(value,path):
        if isinstance(value,dict):
            if 'class' in value and 'stats' in value:
                kind=KINDS[value['entity_kind']]
                for ns,names in value.get('public_identity',()):
                    token=next((R.builder.token_id(n,namespace=ns) for n in names
                                if R.builder.token_id(n,namespace=ns)>1),1)
                    if token>1:
                        key=f'{token}/{kind}'
                        out['config_objects'].setdefault(key,dict(name=R.builder.token_names[token],paths=[]))['paths'].append(path)
                        check('config-template/'+path,lambda:require((token,kind) in R.templates,(path,key)))
                        break
                else:
                    # Crowns use the dedicated tower namespace, registered by
                    # the frozen initializer; other exported objects must name themselves.
                    check('config-identity/'+path,lambda:require(value['stats']['name'] in ('Tower','KingTower'),path))
            for k,v in value.items():
                if isinstance(v,(dict,list,tuple)):config_objects(v,path+'/'+str(k))
        elif isinstance(value,(list,tuple)):
            for i,v in enumerate(value):config_objects(v,path+'/'+str(i))
    config_objects(R.config,'config')
    class Journal(dict):
        def __init__(self, source):
            super().__init__(source); self.births = list(source.values())
        def __setitem__(self,k,v):
            super().__setitem__(k,v); self.births.append(v)
    names = a.cards or [c['name'] for c in ladder_pool(rt.root/'gamedata.json')]
    index,count = map(int,a.shard.split('/'))
    assert 0 <= index < count
    names=names[index::count]
    out['cards'] = names
    out['shard'] = a.shard
    out['expected_scenarios']=len(names)*3
    out['complete']=False
    for card,name in TARGETS.items():
        if card not in names:continue
        token=R.builder.token_id(name,namespace='area_effect');key=f'{token}/AreaEffect'
        target=out['target_paths'].setdefault(key,dict(card=card,exact_translator_seats=[],native_board_seats=[]))
        for seat in (0,1):
            def target_translator(seat=seat):
                resolved(token,3,0,4.5,13.5,seat)
                target['exact_translator_seats'].append(seat)
            check('target-translator/'+card+'/'+str(seat),target_translator)
        # Record the actual source schema's mapped IDs rather than imply it
        # distinguishes the primary area from nested one-tick damage children.
        target['source_motion_outputs']={}
        for motion in range(7):
            state=dict(entities=[],projectiles=[],spells=[[0,translator.card_of.index(card),motion,81000,243000,81000,261000]])
            rows=translator._rows(state,0)
            target['source_motion_outputs'][str(motion)]=[f'{t}/{KINDS[int(np.argmax(r[4:9]))]}' for _,t,r,_ in rows]
    # Native's public snapshot has no Python objects. Reconstruct only its
    # public identity/static sensor data; no hidden state enters a root.
    python_identities = {}
    def native_objects(state, b, card, mode):
        board=[]
        for e in state['entities']:
            sig = (e['class'],e['stats']['name'],e.get('spell_name',''))
            identity = python_identities.get(sig)
            if identity is None:
                identity = next((v for k,v in python_identities.items() if k[:2]==sig[:2] and not sig[2]), None)
            if identity is None:
                stats = R.builder.loader.get_card(e['stats']['name'])
                if stats is None and e['stats']['name'] in ('Tower','KingTower'):
                    stats = next(x.card_stats for x in b.entities.values() if getattr(x.card_stats,'name','')==e['stats']['name'])
                sensor = SimpleNamespace(card_stats=stats, spell_name=e.get('spell_name',''))
                ns = ('troop_body','building_body','projectile','area_effect','card_action')[e['entity_kind']]
                if e['class']=='ChainLightning': ns='projectile'
                if e['class']=='TimedExplosive': ns='building_body'
                token = R.builder._runtime_entity_token_id(sensor,ns)
                row = np.zeros(32,dtype=np.float32);row[4+e['entity_kind']]=1;row[9]=1
                identity=(token,row)
            token,row=identity
            board.append((token,row,e))
            key=(card,mode,'native',sig,token)
            if key in seen: continue
            seen.add(key)
            kind=e['entity_kind']; label=f'{card}/{mode}/native/{sig}/{token}'
            check('native-template/'+label,lambda:require((token,KINDS[kind]) in R.templates,(token,sig)))
            check('native-typed/'+label,lambda:require(token>1,(token,sig)))
            object_key=f'{token}/{KINDS[kind]}'
            rec=out['objects'].setdefault(object_key,dict(token_name=R.builder.token_names[token],kind=KINDS[kind],cards=[],classes=[],names=[],engines=[],modes=[]))
            for col,val in [('cards',card),('classes',e['class']),('names',e.get('spell_name') or e['stats']['name']),('engines','native'),('modes',mode)]:
                if val not in rec[col]:rec[col].append(val)
            check('native-translator-static/'+label,lambda:require(f'{token}/{kind}' in vocab['statics'],object_key))
            check('native-translator-object/'+label,lambda:require(vocab['objects'].get(f'{token}/{kind}')==[token,kind],object_key))
            if kind<2 and e['stats']['name'] not in ('Tower','KingTower'):
                check('native-meta-body/'+label,lambda:require(any(v['token']==token for v in R.meta['bodies'].values()),object_key))
                check('native-meta-body-name/'+label,lambda:require(e['stats']['name'] in R.meta['bodies'],e['stats']['name']))
                for style,bot in R.bots.items():
                    check('native-script-body/'+label+'/'+style,lambda bot=bot:require(token in bot.bodies,object_key))
            for seat in (0,1):
                check('native-translator-resolved/'+label+'/'+str(seat),lambda seat=seat:resolved(token,kind,e['owner'],e['x'],e['y'],seat))
            if ('native',token,kind) not in root_seen:
                root_seen.add(('native',token,kind))
                for seat in (0,1):
                    view=row.copy();view[0]=e['x']/18;view[1]=e['y']/32
                    view[2:4]=[e['owner']==seat,e['owner']!=seat]
                    if seat: view[:2]=1-view[:2]
                    check('native-public-root/'+label+'/'+str(seat),lambda:root_row(b,token,view,seat))
        return board

    def native_board(b,board,seat):
        carriers=[]
        for token,row,e in board:
            view=row.copy();view[:2]=[e['x']/18,e['y']/32]
            view[2:4]=[e['owner']==seat,e['owner']!=seat]
            view[9]=max(0.,min(1.,e['hp']/max(1.,e['stats']['max_hp'])))
            fx,fy=e.get('facing',[0,0]);m=max(1.,(fx*fx+fy*fy)**.5)
            view[27:29]=[fx/m,fy/m]
            if seat:view[:2]=1-view[:2];view[27:29]*=-1
            carriers.append((token,view))
        # Public entity fields only. Metadata/HUD packet supplies the normal
        # observation shape; no native config, targets, cooldown or RNG enters it.
        root_row(b,None,None,seat,board_rows=carriers)
    for card in names:
        for mode in ('combat','death','lifetime'):
            print('scenario',card,mode,flush=True)
            try:
                deck=tuple(dict.fromkeys((card,'Knight','Archers','Cannon','Minions','Fireball','Skeletons','Zap')))
                b=initial(seed=5000110,cards=deck)
                b.entities=Journal(b.entities)
                commands=[]
                subjects=set()
                # Deploy from BOTH seats. Enemy/ally groups exercise spells,
                # chains, on-hit buffs, healing, conversion and splash objects.
                for seat in (0,1):
                    for name,x,y in [('Knight',4.5,14.5),('Archers',5.5,14.5),('Minions',6.5,14.5),('Cannon',9.5,10.5)]:
                        b.players[seat].hand[0]=name;b.players[seat].elixir=10
                        y=y if seat==0 else 32-y
                        assert b.deploy_card(seat,name,Position(x,y))
                        commands.append((seat,name,x,y))
                    b.players[seat].hand[0]=card;b.players[seat].elixir=10
                    if card=='Mirror':
                        b.players[seat].last_played_card='Knight';b.players[seat].last_played_card_cost=3
                    positions=[(4.5,13.5),(9.5,12.5),(13.5,11.5),(4.5,9.5),(9.5,9.5)]
                    for x,y in positions:
                        y=y if seat==0 else 32-y
                        before=set(b.entities)
                        if b.deploy_card(seat,card,Position(x,y)):
                            subjects.update(set(b.entities)-before)
                            commands.append((seat,card,x,y));break
                    else:raise AssertionError('no legal deployment: '+card)
                cfg=R.config
                if card not in cfg['cards']:
                    # Spirit Empress is action-UNK in v5, but its real engine
                    # objects are still audited; it is not admitted as an action.
                    extra=config((card,),mirror_templates=False)
                    cfg={**cfg,'cards':{**cfg['cards'],**extra['cards']}}
                empty=initial(seed=5000110,cards=deck)
                raw=json.loads(snapshot(empty,cfg));need=[n for n in deck if n in cfg['cards']]
                need += ['level12:Knight'] if card=='Mirror' else []
                cut=SideCut(cfg);kept,gated=cut.keep(need,strings(raw['entities']))
                raw['config']=json.loads('{'+cut.other(kept,gated)+',"cards":'+json.dumps({n:cfg['cards'][n] for n in need})+'}')
                native=clasher_core.BattleState(json.dumps(raw))
                native_plays=[]
                native_subjects=set()
                for seat,name,x,y in commands:
                    state=json.loads(native.snapshot())
                    payload=state['config']['cards'][name]
                    if not any(payload['units']) and not payload.get('spell') and not payload.get('mirror'):
                        # MergeMaiden is an existing paid no-object compatibility
                        # deployment in Python, excluded (action UNK) from v5.
                        # Never feed an empty troop formation to native.
                        assert name=='MergeMaiden'
                        out.setdefault('no_object_cards',{})[name]='Python creates no objects; native action outside v5 scope'
                        continue
                    state['players'][seat]['hand'][0]=name
                    state['players'][seat]['elixir']=10.
                    if name=='Mirror':
                        state['players'][seat].update(last_card='Knight',last_cost=3.)
                    native=clasher_core.BattleState(json.dumps(state))
                    before={e['id'] for e in state['entities']}
                    assert native.apply_action(seat,name,x,y),('native deployment',name,seat,x,y)
                    if name==card:
                        native_subjects.update(e['id'] for e in json.loads(native.snapshot())['entities'] if e['id'] not in before)
                    native_plays.append(name)
                out['checks']['native-deploy']+=len(native_plays)
                limit=a.ticks if mode=='lifetime' else min(a.ticks,450)
                for tick in range(limit+1):
                    births=b.entities.births;b.entities.births=[]
                    for e in [*births,*b.entities.values()]:
                        sig=(type(e).__name__,getattr(e.card_stats,'name',''),getattr(e,'spell_name',''))
                        if sig not in python_identities:
                            python_identities[sig]=R.builder._entity_row(e,0)
                        inspect_object(b,e,card,mode,'python')
                        for status in ('_haste_effects','_slow_effects','_periodic_damage_effects'):
                            if getattr(e,status,None):out['buffs'][status]+=1
                    state=json.loads(native.snapshot())
                    native_board_rows=native_objects(state,b,card,mode)
                    if tick in (0,80,81,160,161,240,241,limit):
                        for seat in (0,1):
                            check(f'public-board/{card}/{mode}/{tick}/{seat}',lambda:root_board(b,seat))
                            check(f'native-public-board/{card}/{mode}/{tick}/{seat}',lambda:native_board(b,native_board_rows,seat))
                    if tick==80 and mode=='lifetime':
                        # Keep the card's own objects and crowns, remove the
                        # target fixtures so buildings can expire naturally.
                        for id,e in list(b.entities.items()):
                            if id not in subjects and getattr(e.card_stats,'name','') not in ('Tower','KingTower'):
                                del b.entities[id]
                            elif type(e).__name__=='Building' and id in subjects:
                                e.damage=0
                        state['entities']=[e for e in state['entities'] if e['id'] in native_subjects or e['stats']['name'] in ('Tower','KingTower')]
                        for e in state['entities']:
                            if e['class']=='Building' and e['id'] in native_subjects:e['stats']['damage']=0.
                        native=clasher_core.BattleState(json.dumps(state))
                    if tick in (80,160,240) and mode=='death':
                        for e in list(b.entities.values()):
                            if getattr(e.card_stats,'name','') not in ('Tower','KingTower') and e.entity_kind<2 and e.is_alive:
                                e.take_damage(e.hitpoints+100000)
                        # Exercise native damage/death callbacks through real
                        # spell dispatch (setting HP to zero bypasses them).
                        state['config']['cards']['Zap']['spell'].update(damage=1.e9,building_damage=1.e9,
                            crown_tower_damage=0.,radius=100.,cast_delay=0.)
                        native=clasher_core.BattleState(json.dumps(state))
                        for owner in (0,1,0,1):
                            state=json.loads(native.snapshot())
                            state['players'][owner]['hand'][0]='Zap'
                            state['players'][owner]['elixir']=10.
                            native=clasher_core.BattleState(json.dumps(state))
                            assert native.apply_action(owner,'Zap',4.5,13.5)

                    if tick==60:
                        for seat in (0,1):
                            if b.can_activate_champion_ability(seat):b.activate_champion_ability(seat)
                            if native.can_activate_champion_ability(seat):native.activate_champion_ability(seat)
                    b.step();native.step()
                out['scenarios'].append(dict(card=card,mode=mode,ticks=limit,engines=['python','native'],seats=[0,1]))
            except BaseException as e:
                out['failures'].append(dict(site=f'scenario/{card}/{mode}',error=f'{type(e).__name__}: {e}',trace=traceback.format_exc()))
        print(card,'objects',len(out['objects']),'failures',len(out['failures']),flush=True)
        out['result']='PASS' if not out['failures'] else 'FAIL'
        a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    out['complete']=len(out['scenarios'])==out['expected_scenarios']
    for key,target in out['target_paths'].items():
        check('target-final/'+key,lambda key=key,target=target:require(
            key in out['native_materialized_carriers'] and set(target['exact_translator_seats'])=={0,1}
            and set(target['native_board_seats'])=={0,1},(key,target)))
    out['result']='PASS' if out['complete'] and not out['failures'] else 'FAIL'
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    return not(out['complete'] and not out['failures'])


if __name__=='__main__':sys.exit(main())
