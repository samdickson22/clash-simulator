"""Common metrics for canonical (own side at y < 16) 20 Hz observations.

No policy receives this analysis record. Each metric is (sum, denominator),
so pooling and game-cluster bootstrapping preserve opportunity denominators.
Missing opportunities are absent, never imputed as zero.
"""
from dataclasses import dataclass
from collections import defaultdict
import numpy as np

WIN_CONDITIONS = frozenset(('HogRider','RoyalHogs','Xbow','Mortar','Giant','Golem',
    'RoyalGiant','Balloon','LavaHound','GoblinGiant','ElectroGiant','RamRider',
    'BattleRam','GoblinBarrel','Graveyard','Miner','WallBreakers','Wallbreakers',
    'GiantGoblin','LavaHound'))
PHASES = ('single', 'double', 'triple')


def archetype(deck):
    d = set(deck)
    for cards, name in [(('Xbow','Mortar'), 'siege'), (('Golem','LavaHound','Giant','GoblinGiant','ElectroGiant'), 'beatdown'),
                        (('HogRider','RoyalHogs','RamRider','BattleRam'), 'bridge_wincon'),
                        (('GoblinBarrel','Princess'), 'bait'), (('Graveyard','Miner','WallBreakers','Wallbreakers'), 'chip')]:
        if d.intersection(cards): return name
    return 'other'


@dataclass
class Game:
    identity: str
    cluster: str  # match, not perspective
    cohort: str
    role: str
    matchup: str
    deck: list
    loss: float | None
    ticks: np.ndarray
    globals: np.ndarray
    hands: np.ndarray
    offsets: np.ndarray
    entities: np.ndarray  # compact: x,y,own,enemy,troop,building,...,hp at 9
    entity_ids: np.ndarray
    plays: list  # tick, card, x, y (canonical), accepted, elixir_before
    metadata: dict
    queues: np.ndarray | None = None


def extract(game, catalog):
    """Reduce one perspective, retaining all/all-phase/matchup intersections."""
    t, g = game.ticks, game.globals
    if len(t) < 2 or np.any(np.diff(t) <= 0):
        raise ValueError('at least two strictly increasing frame ticks required')
    if game.role not in ('train','dev','exploration'):
        raise ValueError('only train/dev human or exploration simulator roles allowed')
    phase = np.where(g[:,3] > .5, 2, np.where(g[:,2] > .5, 1, 0))
    e = np.clip(g[:,5] * 10., 0., 10.)
    dt = np.r_[np.diff(t)/20., 0.]
    # Refuse to integrate unobserved holes; rows normally arrive at 5 ticks.
    valid_dt = (dt > 0) & (dt <= .5)
    dt = np.where(valid_dt, dt, 0.)
    n = len(t)
    enemy = np.zeros((n,2), dtype=np.int32)
    own_far = np.zeros((n,2), dtype=np.int32)
    f = game.entities
    row = np.repeat(np.arange(n), np.diff(game.offsets))
    if len(f):
        lane = (f[:,0] >= .5).astype(int)
        threat = (f[:,3] > .5) & (f[:,4] > .5) & (f[:,9] > 0) & (f[:,1] <= .5)
        forward = (f[:,2] > .5) & (f[:,4] > .5) & (f[:,9] > 0) & (f[:,1] > .5)
        np.add.at(enemy, (row[threat], lane[threat]), 1)
        np.add.at(own_far, (row[forward], lane[forward]), 1)
    stats = defaultdict(lambda: defaultdict(lambda: [0.,0.]))
    def add(metric, value, denom, i):
        if not np.isfinite(value) or not np.isfinite(denom) or denom <= 0: return
        p = PHASES[int(phase[i])]
        for key in ('all', f'phase={p}', f'matchup={game.matchup}', f'phase={p}|matchup={game.matchup}'):
            pair=stats[key][metric]; pair[0]+=float(value); pair[1]+=float(denom)
    def add_vector(metric, values, denoms):
        for p in range(3):
            ix=np.flatnonzero(phase==p)
            if len(ix): add(metric, np.sum(values[ix]), np.sum(denoms[ix]), ix[0])
    add_vector('time_at_max_fraction', dt*(e >= 9.999), dt)
    add_vector('time_at_max_seconds_per_minute', 60*dt*(e >= 9.999), dt)
    # Conservative lower bound: only intervals already capped, minus an action
    # at their left boundary. Partial approach-to-cap and collector overflow omitted.
    played_rows = set(np.searchsorted(t, int(p['tick']), side='right')-1 for p in game.plays if p['accepted'])
    at_cap=(e >= 9.999) & ~np.isin(np.arange(n),list(played_rows))
    regen = np.choose(phase, [.356, .714, 1.074])
    add_vector('leaked_elixir_lower_bound_per_minute', 60*dt*at_cap*regen, dt)
    plays = []
    for p in game.plays:
        if p['card'] not in catalog['cards']: continue
        i = min(n-1,max(0,int(np.searchsorted(t,p['tick'],side='right')-1)))
        card = catalog['cards'][p['card']]
        if not p['accepted']:
            add('rejected_play_fraction', 1, 1, i); continue
        add('rejected_play_fraction', 0, 1, i)
        plays.append((p,i,card))
        add('play_elixir_below5_fraction', p['elixir_before'] < 5, 1, i)
        add('left_lane_play_fraction', p['x'] < 9, 1, i)
        if p['card'] in WIN_CONDITIONS:
            add('wincon_low_reserve_fraction', p['elixir_before']-card['cost'] < 4, 1, i)
            add('wincon_elapsed_seconds', p['tick']/20., 1, i)
            add('wincon_into_active_threat_fraction', bool(enemy[i].sum()), 1, i)
        # Geometry only, not attributed spell hits. Rolling/delayed spells excluded.
        spell = card.get('spell')
        if spell and spell.get('radial_instant'):
            a,b=game.offsets[i:i+2]; ef=f[a:b]; ids=game.entity_ids[a:b]
            radius=spell['radius']; dx=ef[:,0]*18-p['x'];dy=ef[:,1]*32-p['y']
            hit=(ef[:,3]>.5)&(ef[:,9]>0)&(dx*dx+dy*dy <= radius*radius)&((ef[:,4]>.5)|(ef[:,5]>.5))
            towers=np.array([catalog['bodies'].get(str(int(v)),{}).get('tower',False) for v in ids],bool)
            add('spell_geometry_units', np.sum(hit & ~towers), 1, i)
            add('spell_geometry_towers', np.sum(hit & towers), 1, i)
            value=sum(catalog['bodies'].get(str(int(v)),{}).get('unit_cost',0)*float(hp)
                      for v,hp,h,tw in zip(ids,ef[:,9],hit,towers) if h and not tw)
            add('spell_geometry_exposed_elixir_per_cost',value,card['cost'],i)
    for card in game.deck:
        name=f'card_per_deck_minute:{card}'
        # Include zero-use deck games in the rate denominator.
        add_vector(name, np.zeros(n), dt/60.)
    for p,i,card in plays:
        # Increment numerator in the same scopes without inventing exposure.
        for key in ('all',f'phase={PHASES[phase[i]]}',f'matchup={game.matchup}',f'phase={PHASES[phase[i]]}|matchup={game.matchup}'):
            stats[key][f"card_per_deck_minute:{p['card']}"][0]+=1
    push_elixir=[]; pushes=[]
    for lane in range(2):
        present=enemy[:,lane]>0
        active=np.flatnonzero(present)
        if not len(active): continue
        # A lane incursion begins after >=2 seconds without hostile troops in
        # our half. Includes direct deployments; no stable IDs exist in the store.
        starts=active[np.r_[True,np.diff(t[active])>40]]
        for i in starts:
            if t[i] < 90: continue
            end_tick=t[i]+160
            if t[-1] < end_tick: continue  # fixed window must be fully observed
            if np.any(np.diff(t[i:np.searchsorted(t,end_tick)+1])>10): continue
            push_elixir.append(float(e[i]))
            add('arrival_elixir',e[i],1,i)
            add('arrival_under4_fraction',e[i]<4,1,i)
            for bucket in range(11):
                add(f'arrival_elixir_bin:{bucket}',int(min(10,int(e[i])))==bucket,1,i)
            answers=[(p,j,c) for p,j,c in plays if t[i] <= p['tick'] <= end_tick
                     and int(p['x']>=9)==lane and (p['y']<=16 or c.get('spell'))]
            pre=[p for p,j,c in plays if t[i]-40 <= p['tick'] < t[i]
                 and int(p['x']>=9)==lane and (p['y']<=16 or c.get('spell'))]
            latency=min(((p['tick']-t[i])/20. for p,j,c in answers),default=8.)
            add('response_latency_capped8_seconds',latency,1,i)
            add('no_response_within8_fraction',not answers,1,i)
            add('preemptive_response_proxy_fraction',bool(pre),1,i)
            spend=sum(c['cost'] for p,j,c in answers)
            add('defensive_commitment_ge7_fraction',spend>=7,1,i)
            add('defensive_commitment_elixir',spend,1,i)
            # Cycle availability is a proxy, not a strategic-error oracle.
            affordable_defender=False
            defender_in_hand=False
            defender_tokens=[]
            defender_in_deck=False
            for name in game.deck:
                c=catalog['cards'].get(name,{})
                if not c.get('spell') and name not in WIN_CONDITIONS:
                    defender_in_deck=True
                    defender_tokens.append(c.get('token',-1))
                    defender_in_hand |= c.get('token',-1) in game.hands[i,:4]
                    affordable_defender |= c.get('token',-1) in game.hands[i,:4] and c.get('cost',99)<=e[i]+1e-6
            if defender_in_deck:
                add('no_affordable_defender_in_hand_fraction',not affordable_defender,1,i)
                add('defender_not_in_hand_fraction',not defender_in_hand,1,i)
                if game.queues is not None:
                    distances=[j+1 for j,token in enumerate(game.queues[i]) if token in defender_tokens]
                    if defender_in_hand or distances:
                        add('defender_cycle_distance',0 if defender_in_hand else min(distances),1,i)
            j=min(n-1,int(np.searchsorted(t,end_tick)))
            damage=max(0.,float(g[i,8+lane]-g[j,8+lane]))
            add('tower_hp_fraction_lost_after_push',damage,1,i)
            pushes.append(dict(tick=int(t[i]),lane=lane,elixir=float(e[i]),tower_damage=damage))
            # Find lane clearance for >=2s, then a new friendly incursion within
            # 10s. No unit IDs: this is pressure conversion, not survivor identity.
            clear=None
            for k in range(i+1,min(n,j+1)):
                q=np.searchsorted(t,t[k]+40)
                if q<n and not present[k:q+1].any(): clear=k;break
            if clear is not None and t[-1]>=t[clear]+200:
                stop=np.searchsorted(t,t[clear]+200)
                conversion=bool(np.any(own_far[clear:stop+1,lane]>own_far[clear,lane]))
                add('counterpush_pressure_conversion_fraction',conversion,1,i)
    return dict(identity=game.identity,cluster=game.cluster,cohort=game.cohort,role=game.role,
                matchup=game.matchup,loss=game.loss,metadata=game.metadata,
                stats={k:dict(v) for k,v in stats.items()},pushes=pushes,
                frames=n,duration_seconds=float(dt.sum()))
