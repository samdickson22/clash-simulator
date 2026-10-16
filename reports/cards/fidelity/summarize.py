#!/usr/bin/env python3
"""Compare measured observables, never infer missing coverage as a PASS."""
from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path
import statistics

from scenarios import GROUP1, GROUP2


def compare(r):
    if r['scenario'] == 'stationary_knight':
        return r['verdict'],r['differences']
    a, b = r['ours'], r['rsim']
    diffs = []
    def add(metric, x, y, tolerance=0):
        if isinstance(x, (float,int)) and isinstance(y, (float,int)):
            same = abs(x-y) <= tolerance
        else:
            same = x == y
        if not same:
            diffs.append(dict(metric=metric, ours=x, royalesim=y))
    if 'error' in a or 'error' in b:
        return 'HARNESS-GAP', [dict(metric='exception', ours=a.get('error'), royalesim=b.get('error'))]
    if any(not x[-1] for x in a['deployments']+b['deployments']):
        return 'HARNESS-GAP', [dict(metric='deployment_refused', ours=a['deployments'], royalesim=b['deployments'])]
    au, bu = a['units'], b['units']
    # Names + ordinal match each producer's descendants, even after births drift.
    aa, bb = defaultdict(list), defaultdict(list)
    aliases={'Graveyard_rework_Skeleton':'Skeleton','GoblinCurseGoblin':'Goblin'}
    for u in au: aa[aliases.get(u['name'],u['name'])].append(u)
    for u in bu: bb[aliases.get(u['name'],u['name'])].append(u)
    for name in sorted(set(aa)|set(bb)):
        x, y = aa[name], bb[name]
        add(f'{name}.count', len(x), len(y))
        for i, (u,v) in enumerate(zip(x,y)):
            for f in ('max_hp', 'birth', 'ready'):
                add(f'{name}[{i}].{f}',u[f],v[f],1)
            # Shield collection was fixed after the initial group-1 run.
            if r.get('schema', 1) >= 2:
                add(f'{name}[{i}].shield', u['shield'],v['shield'],1)
                if u.get('configured_damage') is not None and v.get('configured_damage') is not None:
                    add(f'{name}[{i}].configured_damage',u['configured_damage'],v['configured_damage'],1)
                if u.get('configured_speed') and v.get('configured_speed'):
                    add(f'{name}[{i}].configured_speed',u['configured_speed'],v['configured_speed'],abs(v['configured_speed'])*.02)
                if u.get('configured_lifetime_ms') is not None and v.get('configured_lifetime_ms') is not None:
                    add(f'{name}[{i}].configured_lifetime_ms',u['configured_lifetime_ms'],v['configured_lifetime_ms'],1)
            if r['scenario'] == 'alone':
                add(f'{name}[{i}].death',u['death'],v['death'],1)
            if u['speed_tiles_s'] and v['speed_tiles_s']:
                add(f'{name}[{i}].observed_speed',u['speed_tiles_s'],v['speed_tiles_s'],abs(v['speed_tiles_s'])*.02)
    # Damage is checked by corresponding impact, allowing a frame of latency.
    # Enemy losses include friendly tower fire and capped lethal damage; attribution
    # must use the controlled probes or an isolated nonlethal hit.
    for field in ('tower_hits', 'enemy_hits'):
        x,y = a[field],b[field]
        add(field+'.count',len(x),len(y))
        for i,(u,v) in enumerate(zip(x,y)):
            add(f'{field}[{i}].tick',u[0],v[0],1)
            add(f'{field}[{i}].victim',u[1:-1],v[1:-1])
            add(f'{field}[{i}].damage',u[-1],v[-1],1)
    for s in set(a['tower_damage'])|set(b['tower_damage']):
        add(f'tower_damage_{s}s',a['tower_damage'].get(s),b['tower_damage'].get(s),1)
    if r['card'] == 'Elixir Collector' and 'production_ticks' in a:
        x,y=a['production_ticks'],b['production_ticks']
        add('production.count',len(x),len(y))
        for i,(u,v) in enumerate(zip(x,y)):add(f'production[{i}].tick',u,v,1)
    return ('DIFF' if diffs else 'PASS'), diffs


def fmt(x):
    return json.dumps(x, separators=(',', ':'))


def short(r):
    if any('error' in r[k] for k in ('ours','rsim')):
        return '; '.join(k+': '+r[k]['error'].splitlines()[-1] for k in ('ours','rsim') if 'error' in r[k])
    a,b = r['ours'],r['rsim']
    bits=[]
    for label, field in [('HP','max_hp'),('ATK','configured_damage'),('ready','ready')]:
        x=[u[field] for u in a['units'][:6]]; y=[u[field] for u in b['units'][:6]]
        if x or y: bits.append(f'{label} {fmt(x)}/{fmt(y)}')
    bits.append('tower@10/20/30 '+fmt(list(a['tower_damage'].values()))+'/'+fmt(list(b['tower_damage'].values())))
    if a['enemy_hits'] or b['enemy_hits']:
        bits.append('enemy first hits '+fmt(a['enemy_hits'][:2])+'/'+fmt(b['enemy_hits'][:2]))
    return '; '.join(bits)


def main():
    p=argparse.ArgumentParser(); p.add_argument('inputs',nargs='+',type=Path)
    p.add_argument('--out',type=Path,default=Path(__file__).parent)
    p.add_argument('--primary',choices=['adapter','160402'],default='160402')
    a=p.parse_args(); rows={}
    for path in a.inputs:
        for line in path.read_text().splitlines():
            r=json.loads(line); rows[r['card'],r['scenario'],r['table'],r.get('offset_tiles')]=r
    pool=json.loads((a.out/'pool.json').read_text())
    order=GROUP1+GROUP2+[c['name'] for c in pool if c['name'] not in GROUP1+GROUP2]
    bycard=defaultdict(list)
    for r in rows.values():
        r['verdict'],r['differences']=compare(r)
        bycard[r['card']].append(r)
    with (a.out/'results.jsonl').open('w') as f:
        for n in order:
            for r in bycard[n]:
                # Low-HP building decay events are voluminous and unused by
                # comparison. Full raw traces remain in the remote jobs dir.
                for k in ('ours','rsim'):r[k].pop('own_hits',None)
                f.write(json.dumps(r,separators=(',',':'))+'\n')
    notes={}
    if (a.out/'causes.json').exists(): notes=json.loads((a.out/'causes.json').read_text())
    verdicts={}
    lines=['# Card fidelity results','',
           'Measured on 127x08 using level-11 cards, the read-only r1 Python runtime, and the installed RoyaleSim (MIT) binding. All pairs below are **ours / RoyaleSim**. Event ticks are relative to command tick 100; one tick = 50 ms. Both seats share x/y coordinates: blue defends low y, left princess (3.5,25.5) belongs to red. Positions from RoyaleSim are divided by SUBTILE_PER_MILLITILE and 1000.', '',
           'Primary baseline explicitly selects the full client-16.402 table, `cards-160402017-20261006.1`, through the existing RoyaleSim adapter and its shipped 16.402 calibration. A complete secondary run uses the adapter’s default (`cards-15535.1` plus measured CLIENT16402_VALUES corrections). The default has not switched tables upstream; retaining both avoids silently treating the older table as current card data. Build provenance: `ffe0d27de00cd2cc1121e573eba8796bfb8f5f6a`, clean.', '',
           'Each normal troop has a 30-second bridge run and 30-second Knight/Minions fights. Buildings have 75-second idle/lifetime/spawn runs plus 30-second Hog Rider and Giant defenses (Collector has a longer lifetime/production run). Spells have a tower cast, a fixed Knight/Skeleton Army/Minions cluster, and a friendly Giant support cast. No champion abilities, evolutions, or hero forms are pressed. Scripts, fixed tiles, exact events, hashes and deployment interventions are in `scenarios.py` and `results.jsonl`.', '',
           'PASS means the measured scenarios agree: HP/damage within 1, impact/birth/ready/death times within 1 tick, observed early movement speed within 2%. It is not exhaustive validation of unexercised abilities or special mechanics. Lethal damage is capped at remaining HP; enemy damage events can include our tower fire. DIFF attribution below distinguishes a directly measured stat mismatch from a likely mechanic source. Building decay is excluded from enemy-hit comparison. Spell boundary and status-duration probes are detailed below. All source paths in the cause column refer to r1 on 127x08, not an edited implementation.', '',
           '| Card | Verdict | Key measured numbers (ours / RoyaleSim) | Likely cause; responsible r1 source function |',
           '|---|---|---|---|']
    for n in order:
        rr=[r for r in bycard[n] if r['table']==a.primary]
        if not rr: continue
        verdict=('DIFF' if any(r['verdict']=='DIFF' for r in rr) else 'HARNESS-GAP' if any(r['verdict']=='HARNESS-GAP' for r in rr) else 'PASS')
        verdicts[n]=verdict
        primary=next((r for r in rr if r['scenario'] in ('alone','tower','mirror')),rr[0])
        note=notes.get(n,'Measured probes agree.' if verdict=='PASS' else 'Mechanic/trajectory divergence; attribution pending.')
        data=short(primary)
        controlled=[r for r in rr if r['scenario']=='stationary_knight']
        if controlled:
            center=next(r for r in controlled if r['offset_tiles']==0)
            if not any('error' in center[k] for k in ('ours','rsim')):
                data+='; stationary damage '+fmt(center['ours']['damage'])+'/'+fmt(center['rsim']['damage'])
                data+='; effect ticks '+fmt(center['ours']['effect_ticks'])+'/'+fmt(center['rsim']['effect_ticks'])
        if n=='Elixir Collector':
            data+='; death '+fmt([u['death'] for u in primary['ours'].get('units',[])])+'/'+fmt([u['death'] for u in primary['rsim'].get('units',[])])
            data+='; production cycles '+fmt(primary['ours'].get('production_ticks'))+'/'+fmt(primary['rsim'].get('production_ticks'))
        special=next((r for r in rr if r['verdict']=='DIFF' and r is not primary),None)
        if special:
            d=special['differences'][0]
            data+='; '+special['scenario']+' '+d['metric']+' '+fmt(d['ours'])+'/'+fmt(d['royalesim'])
        lines.append('| '+n+' | '+verdict+' | '+data.replace('|','/')+' | '+note+' |')
    counter=Counter(verdicts.values())
    counts={k:counter[k] for k in ('PASS','DIFF','NOT-IN-ROYALESIM','HARNESS-GAP')}
    lines[2:2]=['Completed '+str(len(verdicts))+'/66 cards: '+fmt(counts)+'.','']
    lines+=['','## Coverage and interpretation','',
            'Both engines use their normal deploy paths. The harness seeds RNGs, constructs fixed hands, and starts at absolute tick 100 (past RoyaleSim’s opening lockout). Our elixir top-ups and hand forcing are retained in counters; a refused deployment is HARNESS-GAP rather than a fidelity verdict. No reference fixture corpus or held-out replay data was used. Only measured outputs, code, and the card-name/kind pool are saved; no upstream card data tables are included.','',
            'Spawn counts include all descendants born during the scenario, including death spawns; `alive_at` is a separate survivor count. Early movement speed is the median nonzero displacement before relative tick 120, so close combat/contact can affect it. Initial spawn locations are stored for diagnosis but are not independently gated. First-hit and hit periods can be read from the full ordered impact events; multi-unit/splash events are intentionally not mislabeled as one unit’s hit period.','']
    lines+=['The Collector idle probe runs 175 seconds. `production_ticks` records the source’s completed production clock cycles: ours advances its production counter even when the payout is wasted at 10 elixir; the reference holds the due cycle at the cap. It is not a count of elixir actually credited. The first deployment-time timer initialization is excluded. Both idle lifetimes are observed to death.','',
            'The existing adapters seed Python RNG to 0 and RoyaleSim to the start tick (100); there is no claim that unrelated PRNGs yield identical random placement. Graveyard still differs on deploy-ready ticks independently of its placement pattern. Controlled spell targets use fixed coordinates and no RNG.','',
            'Reproduce with the job instructions in REPRODUCE.md. Full raw event traces remain on 127x08 under `/mpac/sdicks02/jobs/clasher/cards/fidelity/20261015/`; the consolidated JSONL omits unused own-side damage/decay events. Source hashes and supervised job PIDs are in provenance.json.','']
    cc=[r for r in rows.values() if r['scenario']=='stationary_knight' and r['table']==a.primary]
    if cc:
        lines+=['## Controlled spell probes','',
                'One level-11 Knight is made stationary (speed 0) and given 10000 HP in both engines, outside enemy tower range. Offensive spells are normally cast at (9,19.5), Rage at (9,12.5); target x is 9 + offset. The normal spell deploy path is unchanged. RoyaleSim reset spawns and deliberately edited entity snapshots set the target state; the engine computes and verifies the new snapshot checksum. A center-distance boundary includes the Knight’s 0.5-tile hitbox. Effects below measure target-local status occupancy, not an area object’s visual lifetime.','',
                '| Spell | Center damage | Center impact ticks | Effect occupancy ticks | Farthest sampled affected center offset |',
                '|---|---|---|---|---|']
        for n in dict.fromkeys(r['card'] for r in cc):
            rr=[r for r in cc if r['card']==n];center=next(r for r in rr if r['offset_tiles']==0)
            if any('error' in center[k] for k in ('ours','rsim')):continue
            vals=[]
            for field in ('damage','hits','effect_ticks'):
                vals.append(fmt(center['ours'][field])+' / '+fmt(center['rsim'][field]))
            boundary=[]
            for k in ('ours','rsim'):
                ds=[r['offset_tiles'] for r in rr if r[k].get('damage',0) or r[k].get('effect_ticks',0)]
                boundary.append(max(ds) if ds else None)
            vals.append(fmt(boundary[0])+' / '+fmt(boundary[1]))
            lines.append('| '+n+' | '+' | '.join(vals)+' |')
        lines+=['','The radius samples bracket the hit boundary; they are not exact inferred card radii. At the center Snowball’s zero-vector push is also different: ours moves +y, RoyaleSim −x. Positions are retained in the probe rows.','']
    secondary=[r for r in rows.values() if r['table']!=a.primary]
    if secondary:
        lines+=['## Adapter default cross-check','',
                'The same scripts also ran through the unchanged rsim16402 adapter default. Both table arms are retained separately in results.jsonl. Golden Knight and Lumberjack pass with that older table but differ with the full 16.402 table.','',
                '| Card | Full 16.402 table | Adapter default |', '|---|---|---|']
        for n in order:
            rr=[r for r in secondary if r['card']==n]
            if not rr:continue
            v='DIFF' if any(r['verdict']=='DIFF' for r in rr) else 'HARNESS-GAP' if any(r['verdict']=='HARNESS-GAP' for r in rr) else 'PASS'
            lines.append(f'| {n} | {verdicts.get(n,"pending")} | {v} |')
    (a.out/'RESULTS.md').write_text('\n'.join(lines))
    (a.out/'summary.json').write_text(json.dumps(dict(counts=counts,cards=verdicts),indent=2)+'\n')
    print(counts)


if __name__=='__main__': main()
