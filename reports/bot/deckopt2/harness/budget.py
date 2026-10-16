"""Rarity-aware upgrade planning from pinned official game-data arrays.

Plans only cards in the deck. Held copies and rarity-specific wild cards are
consumable resources; gold is shared. No gems or wild-card purchase is assumed.
A positive per-level strength surrogate makes copies-only maxima exact when
all fit, and supports bounded budget allocation when the wild inventory lands.
"""
from pathlib import Path
from itertools import product
import json
from bot.fullpool.cards import C56,engine_name
ROOT=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2')
RARITIES=('Common','Rare','Epic','Legendary','Champion')
WEIGHT=dict(Giant=1.8,MiniPekka=1.6,Valkyrie=1.5,InfernoTower=1.6,Cannon=1.4,
            Musketeer=1.45,Wizard=1.45,Archers=1.3,Minions=1.25,Fireball=1.5,
            Skeletons=1.05,Goblins=1.05,Arrows=1.2,FireSpirits=1.,GoblinHut=1.1,Knight=1.3)
PRIORITY=('Giant','MiniPekka','Valkyrie','InfernoTower','Cannon','Musketeer','Wizard','Fireball',
          'Archers','Minions','Skeletons','Goblins','Arrows','FireSpirits','GoblinHut','Knight')


def load(collection_path=None):
    raw=json.loads((ROOT/'upgrade-source-gamedata.json').read_text())
    rarity_rows={r['name']:r for r in raw['items']['rarities']}
    spells={engine_name(s['name'],strict=False):s for s in raw['items']['spells'] if engine_name(s['name'],strict=False)}
    collection={engine_name(c):v for c,v in json.loads(Path(collection_path or ROOT/'collection-final.json').read_text()).items() if not c.startswith('_')}
    return collection,spells,rarity_rows


def options(card,collection,spells,table,budget,wild):
    own=collection[card];rarity=spells[card]['rarity'];rr=table[rarity]
    lv=int(own['level']);gold=total=0;steps=[]
    out=[dict(level=lv,gold=0,wild=0,steps=[],value=0.)]
    # Array index0 is the transition from the rarity's absolute starting level.
    while lv<16:
        index=lv-int(rr['relativeLevel'])-1
        copies=int(rr['upgradeMaterialCount'][index]);price=int(rr['upgradeCost'][index])
        if not copies or price<=0:break
        total+=copies;gold+=price
        shortage=max(0,total-int(own['copies']))
        if gold>budget or shortage>int(wild.get(rarity,0)):break
        held_used=max(0,min(copies,int(own['copies'])-(total-copies)))
        steps=steps+[dict(card=card,from_level=lv,to_level=lv+1,gold=price,copies=copies,
                         held_copies=held_used,wild_cards=copies-held_used,rarity=rarity)]
        lv+=1
        value=WEIGHT.get(card,1.)*(1.1**(lv-11)-1.1**(int(own['level'])-11))
        out.append(dict(level=lv,gold=gold,wild=shortage,steps=steps,value=value))
    return rarity,out


def plan(deck,wild=None,budget=10321,collection_path=None):
    collection,spells,table=load(collection_path);wild=wild or {}
    assert len(set(deck))==len(deck)==8 and set(deck)<=set(collection)&set(C56)
    states={(0,0,0,0,0,0):(0.,[])}
    for card in deck:
        rarity,opts=options(card,collection,spells,table,budget,wild)
        ridx=1+RARITIES.index(rarity);new={}
        for state,(value,path) in states.items():
            for opt in opts:
                resources=list(state);resources[0]+=opt['gold'];resources[ridx]+=opt['wild']
                if resources[0]>budget or resources[ridx]>int(wild.get(rarity,0)):continue
                key=tuple(resources);proposal=(value+opt['value'],path+[opt])
                old=new.get(key)
                if old is None or proposal[0]>old[0]+1e-12:new[key]=proposal
        states=new
        assert states
    resources,(value,path)=max(states.items(),key=lambda item:(item[1][0],-item[0][0],tuple(-v for v in item[0][1:])))
    order={c:i for i,c in enumerate(PRIORITY)}
    steps=[step for opt in path for step in opt['steps']]
    steps.sort(key=lambda s:(order.get(s['card'],999),s['from_level']))
    result=dict(levels={card:opt['level'] for card,opt in zip(deck,path)},gold=resources[0],
                remaining_gold=budget-resources[0],wild_cards_used=dict(zip(RARITIES,resources[1:])),
                upgrade_order=steps,heuristic_value=value,
                heuristic='maximize weighted absolute strength curve1.1**(level-11), weights prioritize Giant and core defence; exact resource-constrained enumeration, not measured upgrade EV')
    # Independent sequential resource replay catches offset/copy/wild/accounting mistakes.
    gold=budget;copies={c:int(collection[c]['copies']) for c in deck};levels={c:int(collection[c]['level']) for c in deck};wc={r:int(wild.get(r,0)) for r in RARITIES}
    for step in steps:
        c=step['card'];assert levels[c]==step['from_level']
        assert copies[c]>=step['held_copies'] and wc[step['rarity']]>=step['wild_cards']
        copies[c]-=step['held_copies'];wc[step['rarity']]-=step['wild_cards'];gold-=step['gold'];levels[c]+=1
        assert gold>=0
    assert levels==result['levels'] and budget-gold==result['gold']
    return result


def candidates():
    old=json.loads((ROOT/'manifest.json').read_text())
    out=dict(old['candidates']);base=out['baseline']
    changes=[('inferno',{'Cannon':'InfernoTower'}),('wizard',{'Musketeer':'Wizard'}),
             ('wizard-minions',{'Minions':'Wizard'}),('wizard-valk',{'Valkyrie':'Wizard'}),
             ('fire-spirits',{'Cannon':'FireSpirits'}),('fire-spirits-minions',{'Minions':'FireSpirits'}),
             ('inferno-wizard',{'Cannon':'InfernoTower','Musketeer':'Wizard'}),
             ('inferno-arrows',{'Cannon':'InfernoTower','Minions':'Arrows'}),
             ('inferno-skeletons',{'Cannon':'InfernoTower','Minions':'Skeletons'}),
             ('inferno-skeletons-musket',{'Cannon':'InfernoTower','Musketeer':'Skeletons'}),
             ('inferno-goblins',{'Cannon':'InfernoTower','Minions':'Goblins'}),
             ('inferno-wizard-arrows',{'Cannon':'InfernoTower','Musketeer':'Wizard','Minions':'Arrows'}),
             ('inferno-wizard-skeletons',{'Cannon':'InfernoTower','Musketeer':'Wizard','Minions':'Skeletons'}),
             ('inferno-wizard-fire',{'Cannon':'InfernoTower','Musketeer':'Wizard','Minions':'FireSpirits'}),
             ('wizard-skeletons',{'Musketeer':'Wizard','Cannon':'Skeletons'}),
             ('wizard-arrows',{'Musketeer':'Wizard','Cannon':'Arrows'}),
             ('wizard-goblins',{'Musketeer':'Wizard','Cannon':'Goblins'}),
             ('skeletons-arrows',{'Cannon':'Skeletons','Minions':'Arrows'}),
             ('skeletons-goblins',{'Cannon':'Skeletons','Minions':'Goblins'}),
             ('skeletons-fire',{'Cannon':'Skeletons','Minions':'FireSpirits'}),
             ('inferno-goblins-skeletons',{'Cannon':'InfernoTower','Minions':'Goblins','Musketeer':'Skeletons'}),
             ('wizard-skeletons-arrows',{'Musketeer':'Wizard','Cannon':'Skeletons','Minions':'Arrows'})]
    for name,replacements in changes:out['budget-'+name]=[replacements.get(c,c) for c in base]
    decks=[tuple(sorted(d)) for d in out.values()]
    assert len(out)==32 and len(decks)==len(set(decks))
    return out

if __name__=='__main__':
    from bot.deckopt2.run import utc,sha,dump
    decks=candidates();plans={n:plan(d) for n,d in decks.items()}
    dump(ROOT/'variant-A-copies-only.json',dict(created_utc=utc(),collection_sha256=sha(ROOT/'collection-final.json'),
         table_sha256=sha(ROOT/'upgrade-source-gamedata.json'),cards='owned C56 only',budget=10321,wild_cards={},candidates=decks,plans=plans),exclusive=True)
    print('Locked copies-only variantA:',len(plans),'decks; maxgold',max(p['gold'] for p in plans.values()),'baselinegold',plans['baseline']['gold'])
