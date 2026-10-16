#!/usr/bin/env python3
"""Resumable card probes; no game data is copied into the report.

Uses the existing bot.fidelity.engines adapters and RoyaleSim's Python binding
(RoyaleSim, MIT). No upstream code ported.
Run from a jobs directory with CLASHER_ROOT pinned to the read-only r1 runtime.
All event ticks below are relative to the first command (absolute tick 100).
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import hashlib
import json
import math
import os
import re
from pathlib import Path
import statistics
import sys
import time
import traceback
from types import SimpleNamespace

START = 100
GROUP1 = 'GoblinCage SpearGoblins Bomber Tombstone Barbarians BattleRam MegaMinion BarbarianHut Mortar DartBarrell Witch Pekka SkeletonWarriors SkeletonDragons'.split()
GROUP2 = 'RoyalGiant ThreeMusketeers RoyalRecruits GiantSkeleton BattleHealer Freeze Snowball Vines SkeletonBalloon GoblinGiant GiantBuffer Hunter MiniSparkys'.split()
FILL = ['Knight', 'Archer', 'Giant', 'Minions', 'Musketeer', 'BabyDragon', 'Balloon', 'Wizard', 'Zap', 'Skeletons']


def load_edited_snapshot(b, state):
    """Re-sign deliberately edited test state with the engine's own checksum."""
    try:
        b.load(json.dumps(state).encode())
    except ValueError as exc:
        m = re.search(r'snapshot self-check failed: saved hash 0x[0-9a-f]+, rebuilt (0x[0-9a-f]+)',str(exc))
        if not m:
            raise
        state['state_hash'] = int(m.group(1), 16)
        b.load(json.dumps(state).encode())


def adapters():
    # The adapter is read from the existing harness; imports never select its src.
    sys.path.append(os.environ.get('FIDELITY_ADAPTER_ROOT', '/mpac/sdicks02/repos/clasher-bot'))
    from bot.fidelity.engines import OursEngine, RsimEngine
    from bot.fidelity.fixture import Play
    return OursEngine, RsimEngine, Play


def fixture(names, names2):
    decks = []
    for wanted in (names, names2):
        d = list(dict.fromkeys(wanted + FILL))[:8]
        decks.append(d)
    ids = {n: i for i, n in enumerate(dict.fromkeys(decks[0] + decks[1]))}
    fix = SimpleNamespace(initial_order=[[ids[n] for n in d] for d in decks], start_tick=START,
                          initial_elixir=[10., 10.])
    return ids, fix


def make_engine(kind, names, names2, table):
    Ours, Rsim, _ = adapters()
    ids, fix = fixture(names, names2)
    e = Ours(ids) if kind == 'ours' else Rsim(ids, client='16.402')
    if kind != 'ours' and table == '160402':
        e.b = e.rs.Battle(card_names=None, slot_of_k=[[0, 1, 2], [0, 1, 2]],
                         calibration_overrides={'cards.CARD_TABLE': '"client160402017_20261006"'})
        e.cat_idx = {r[0]: i for i, r in enumerate(json.loads(e.b.catalogue_json()))}
    e.reset(fix)
    if kind == 'ours' and 'MergeMaiden' in ids:
        e.id_of.update({n: ids['MergeMaiden'] for n in ('MergeMaiden_Normal', 'MergeMaiden_Mounted')})
    if kind == 'rsim':
        if 'MergeMaiden' in ids:
            for name in ('MergeMaiden_Normal', 'MergeMaiden_Mounted'):
                if name in e.cat_idx:
                    e.idx_to_native[e.cat_idx[name]] = ids['MergeMaiden']
        # The collector cannot be in a real opening hand. Force the same test
        # hand in both engines, recording the intervention (normal deploy next).
        if 'Elixir Collector' in ids:
            st = json.loads(e.b.save())
            want = e.cat_idx['Elixir Collector']
            # Snapshot hand ids index the internal CardDb, not the catalogue;
            # recover the matching value from the existing queue by deck order.
            pl = st['players'][0]
            public = e._st()['players'][0]
            if want not in public['hand']:
                if public['next_card'] != want:
                    raise RuntimeError('collector must be next in the test deck')
                j = 0
                pl['hand'][0],pl['queue'][j] = pl['queue'][j],pl['hand'][0]
                load_edited_snapshot(e.b, st)
                e._state = None
                e.counters['hand_forced'] += 1
                if want not in e._st()['players'][0]['hand']:
                    raise RuntimeError('collector hand forcing did not select collector')
    return e, ids


def body_name(e):
    s = e.card_stats
    raw = getattr(s, 'summon_character_data', None) or {}
    return raw.get('name') or s.name


def snapshot(e, kind, types):
    if kind == 'ours':
        from clasher.entities import Building, Troop
        out = []
        for u in e.b.entities.values():
            if not isinstance(u, (Troop, Building)) or not u.is_alive or u.hitpoints <= 0:
                continue
            tower = u.card_stats.name in ('Tower', 'PrincessTower', 'KingTower')
            slot = (0 if u.card_stats.name == 'KingTower' else 1 if u.position.x < 9 else 2) if tower else None
            out.append(dict(id=u.id, side=u.player_id, root=e.roots.get(u.id, -2), tower=slot,
                            name=body_name(u), hp=round(u.hitpoints), max_hp=round(u.max_hitpoints),
                            x=u.position.x, y=u.position.y, deploy=round((u.deploy_delay_remaining + u.spawn_stagger_remaining)*20),
                            shield=round(sum(getattr(m, 'current_shield', 0) for m in u.mechanics)), damage=round(u.damage),
                            speed=getattr(u, 'speed', 0), lifetime_ms=getattr(u.card_stats,'lifetime_ms',None),
                            target=getattr(u, 'target_id', None)))
        return out
    F = e.F
    out = []
    for r in e._st()['entities']:
        if r[F['hp']] <= 0:
            continue
        cid = r[F['card_id']]
        slot = r[F['tower_slot']]
        x, y = r[F['x']]/e.sub/1000, r[F['y']]/e.sub/1000
        tower = (0 if slot == 0 else 1 if x < 9 else 2) if cid == -1 and slot is not None and slot >= 0 else None
        out.append(dict(id=r[F['uid']], side=r[F['team']], root=e.idx_to_native.get(cid, -2), tower=tower,
                        name=types[r[F['unit_type']]], hp=r[F['hp']], max_hp=r[F['max_hp']],
                        x=x, y=y, deploy=r[F['deploy_ticks']], shield=r[F['shield']],
                        target=r[F['target_uid']]))
    return out


def script(card, scenario):
    n, kind = card['name'], card['kind']
    if scenario == 'alone':
        tile = (7.5, 10.5) if kind == 'building' else (3.5, 14.5)
        return [(0, n, tile, 0)], (3500 if n == 'Elixir Collector' else 1500) if kind == 'building' else 600
    if scenario in ('knight', 'minions', 'hog', 'giant'):
        other = dict(knight='Knight', minions='Minions', hog='HogRider', giant='Giant')[scenario]
        tile = (7.5, 12.5) if kind == 'building' else (3.5, 14.5)
        return [(0, n, tile, 0), (1, other, (3.5, 17.5), 0)], 600
    if scenario == 'tower':
        return [(0, n, (3.5, 25.5), 0)], 600
    if scenario == 'cluster':
        # Targets deploy in their own half. Spell follows after the action delay;
        # positions are intentionally fixed, never retargeted to either engine.
        return [(1, 'Knight', (3.5, 18.5), 0), (1, 'SkeletonArmy', (5.5, 18.5), 1),
                (1, 'Minions', (3.5, 20.5), 2), (0, n, (3.5, 18.5), 30)], 300
    if scenario == 'support':
        # Exercises Rage, Clone, and troop buffs with an actual friendly push.
        return [(0, 'Giant', (3.5, 14.5), 0),
                (1, 'Knight', (3.5, 17.5), 0), (0, n, (3.5, 14.5), 35)], 600
    if scenario == 'mirror':
        return [(0, 'Knight', (3.5, 14.5), 0), (0, n, (5.5, 14.5), 40)], 600
    raise ValueError(scenario)


def run_one(card, scenario, kind, table):
    seq, end = script(card, scenario)
    names = [x[1] for x in seq if x[0] == 0]
    names2 = [x[1] for x in seq if x[0] == 1]
    e, ids = make_engine(kind, names, names2, table)
    _, _, Play = adapters()
    types = json.loads(e.b.unit_types_json()) if kind == 'rsim' else None
    root = ids[card['name']]
    bytick = defaultdict(list)
    for side, n, tile, t in seq:
        bytick[t].append((side, n, tile))
    prev = {u['id']: u for u in snapshot(e, kind, types)}
    towers0 = {(u['side'], u['tower']): u['hp'] for u in prev.values() if u['tower'] is not None}
    towers = dict(towers0)
    units = {}
    tower_hits, enemy_hits, own_hits = [], [], []
    tower_damage, alive_at, elixir = {}, {}, {}
    deployments = []
    production_ticks = []
    last_production = 0
    last_mana_ms = None
    source_hash = None
    if kind == 'ours':
        import clasher.battle
        source = Path(clasher.battle.__file__)
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if '/clasher-bot-runtime/r1/src/' not in str(source):
            raise RuntimeError(f'final probe must import r1, got {source}')
    for t in range(end):
        for side, n, tile in bytick[t]:
            p = Play(side=side, card=n, card_id=ids[n], kind='card', tile=tile,
                     exec_tick=START+t, command_tick=START+t, slot=-1)
            ok = e.deploy(p)
            deployments.append([t, side, n, bool(ok)])
        e.step()
        now = {u['id']: u for u in snapshot(e, kind, types)}
        if card['name'] == 'Elixir Collector':
            if kind == 'ours':
                produced = max((getattr(m, '_produced', 0) for u in e.b.entities.values()
                                for m in getattr(u, 'mechanics', [])), default=0)
                if produced > last_production:
                    production_ticks.append(t+1)
                last_production = max(last_production, produced)
            else:
                es = json.loads(e.b.save())['ents']
                timer = next((ms for i,ms in enumerate(es['mana_ms'])
                              if es['alive'][i] and es['kind'][i]=='Building' and es['team'][i]=='Blue'), None)
                if timer is not None and last_mana_ms is not None and timer > last_mana_ms and t+1 > 20:
                    production_ticks.append(t+1)
                last_mana_ms = timer
        if kind == 'rsim' and card['name'] in ('Mirror', 'Clone'):
            F = e.F
            for row in e._st()['entities']:
                if row[F['team']] == 0 and ((card['name']=='Mirror' and row[F['level']]==12)
                                          or (card['name']=='Clone' and row[F['status_flags']] & 32)):
                    uid = row[F['uid']]
                    if uid in now:
                        now[uid]['root'] = root
        if kind == 'rsim' and any(u['side'] == 0 and u['root'] == root and u['tower'] is None and uid not in units for uid,u in now.items()):
            # Read the instantiated entity stats, not any upstream card table.
            saved = json.loads(e.b.save())
            es = saved['ents']
            stats = {seq*2+(1 if team=='Red' else 0): (dmg, speed/18, saved['lifetime_ms'][i])
                     for i,(seq,team,dmg,speed) in enumerate(zip(es['team_seq'],es['team'],es['damage'],es['speed']))}
            for uid,u in now.items():
                if uid in stats:
                    u['damage'],u['speed'],u['lifetime_ms'] = stats[uid]
        rel = t + 1
        for uid, u in now.items():
            old = prev.get(uid)
            if u['tower'] is not None:
                key = (u['side'], u['tower'])
                if old and u['hp'] < old['hp']:
                    tower_hits.append([rel, *key, old['hp']-u['hp']])
                towers[key] = u['hp']
            else:
                if old and u['hp'] < old['hp']:
                    ev = [rel, u['name'], old['hp']-u['hp']]
                    (own_hits if u['side'] == 0 else enemy_hits).append(ev)
                if u['root'] == root and u['side'] == 0:
                    if uid not in units:
                        units[uid] = dict(name=u['name'], birth=rel, max_hp=u['max_hp'],
                                          shield=u['shield'], position=[round(u['x'], 4), round(u['y'], 4)],
                                          ready=None, last=rel, death=None, travel=[],
                                          configured_damage=u.get('damage'), configured_speed=u.get('speed'))
                        units[uid]['configured_lifetime_ms'] = u.get('lifetime_ms')
                    rec = units[uid]
                    rec['last'] = rel
                    if u['deploy'] <= 0 and rec['ready'] is None:
                        rec['ready'] = rel
                    if old and u['deploy'] <= 0 and rel < 120:
                        dist = math.hypot(u['x']-old['x'], u['y']-old['y'])
                        if 0.0001 < dist < 0.2:
                            rec['travel'].append(round(dist*20, 5))
        for uid, old in prev.items():
            if uid not in now:
                if old['tower'] is not None:
                    key = (old['side'], old['tower'])
                    tower_hits.append([rel, *key, old['hp']])
                    towers[key] = 0
                else:
                    if uid in units:
                        units[uid]['death'] = rel
                    # Lethal damage is capped at the remaining health.
                    ev = [rel, old['name'], old['hp']]
                    (own_hits if old['side'] == 0 else enemy_hits).append(ev)
        if rel in (200, 400, 600):
            tower_damage[str(rel//20)] = sum(hp - towers.get(k, 0) for k, hp in towers0.items() if k[0] == 1)
            alive_at[str(rel//20)] = dict(Counter(u['name'] for u in now.values() if u['root'] == root and u['side'] == 0 and u['tower'] is None))
            elixir[str(rel//20)] = (round(e.b.players[0].elixir, 4) if kind == 'ours' else e._st()['players'][0]['elixir_milli']/1000)
        prev = now
    for r in units.values():
        samples = r.pop('travel')
        r['speed_tiles_s'] = round(statistics.median(samples), 4) if samples else None
    return dict(deployments=deployments, units=list(units.values()), tower_damage=tower_damage,
                tower_hits=tower_hits, enemy_hits=enemy_hits, own_hits=own_hits, alive_at=alive_at,
                elixir=elixir, production_ticks=production_ticks, counters=dict(e.counters), r1_battle_sha256=source_hash,
                source=str(source) if kind == 'ours' else None,
                rsim_table=e.b.card_table() if kind == 'rsim' else None,
                rsim_provenance=e.b.provenance() if kind == 'rsim' else None)


def paired(task):
    card, scenario, table = task
    result = dict(card=card['name'], scenario=scenario, table=table, elapsed_s=0, schema=2)
    start = time.time()
    for kind in ('ours', 'rsim'):
        try:
            result[kind] = run_one(card, scenario, kind, table)
        except Exception:
            result[kind] = dict(error=traceback.format_exc())
    result['elapsed_s'] = round(time.time()-start, 3)
    return result


def scenarios(card):
    if card['name'] == 'Mirror':
        return ['mirror']
    if card['kind'] == 'building':
        return ['alone', 'hog', 'giant']
    if card['kind'] == 'spell' and card['name'] not in ('Heal', 'MergeMaiden'):
        return ['tower', 'cluster', 'support']
    return ['alone', 'knight', 'minions']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--pool', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cards', nargs='*')
    p.add_argument('--scenarios', nargs='*')
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--table', choices=['adapter', '160402'], default='adapter')
    a = p.parse_args()
    pool = json.loads(a.pool.read_text())
    order = GROUP1+GROUP2+[c['name'] for c in pool if c['name'] not in GROUP1+GROUP2]
    pool = sorted(pool, key=lambda c: order.index(c['name']))
    done = set()
    if a.out.exists():
        for l in a.out.read_text().splitlines():
            r = json.loads(l)
            if not any('error' in r.get(k, {}) for k in ('ours', 'rsim')):
                done.add((r['card'], r['scenario'], r['table']))
    tasks = [(c, s, a.table) for c in pool if not a.cards or c['name'] in a.cards
             for s in (a.scenarios or scenarios(c)) if (c['name'], s, a.table) not in done]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=a.workers) as ex, a.out.open('a') as f:
        for r in ex.map(paired, tasks, chunksize=1):
            f.write(json.dumps(r, separators=(',', ':'))+'\n'); f.flush()
            print(r['card'], r['scenario'], r['elapsed_s'],
                  [k for k in ('ours', 'rsim') if 'error' in r[k]], flush=True)


if __name__ == '__main__':
    main()
