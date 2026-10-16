"""Project extended host replays to compact causal evidence (no config tables)."""
import argparse
import json
from pathlib import Path
import re
from inspect_results import public
from mixed_games import atomic


def pbrief(e, name):
    keep = ('position', 'hitpoints', 'is_alive', 'target_id', 'attack_cooldown',
            'stun_timer', '_freeze_target_pause_remaining', '_ordinary_clock',
            '_movement_target_id', '_native_natural_movement_active',
            '_special_move_active', '_special_move_consumed_tick',
            '_knockback_velocity_work', '_knockback_target',
            'source_entity', 'primary_target', 'current_target_id',
            'remaining_bounces', 'damage', 'visited_ids', 'spell_name',
            '_last_combat_target_id', '_attack_preload_blocked',
            '_attack_windup_active', '_has_attacked_once', 'mechanics')
    return dict(name=name, **{k: e[k] for k in keep if k in e})


def nbrief(e):
    keep = ('id', 'class', 'owner', 'x', 'y', 'hp', 'alive', 'target', 'cooldown',
            'stun', 'freeze_pause', 'clock', 'clock_initialized', 'clock_reseed',
            'move_target', 'moving', 'dash', 'leap', 'hook', 'push', 'push_velocity',
            'shot_target', 'chain_remaining', 'hit_ids', 'spell_name', 'birth',
            'ramp_target', 'ramp_time', 'preload_blocked', 'started', 'windup',
            'last_target', 'scope', 'production')
    return dict(name=e.get('stats', {}).get('name'), **{k:e[k] for k in keep if k in e})


def project(row):
    if 'error' in row:
        return row
    phases = row['phases']
    label = next(k for k in ('start', 'combat', 'movement', 'objects', 'cleanup', 'complete')
                 if any(public(d) for d in phases[k]['field_diff']))
    d = phases[label]
    diffs = [v for v in d['field_diff'] if public(v)]
    ids = {int(m.group(1)) for v in diffs if (m := re.search(r'\.entities\.(\d+)\.', v['field']))}
    for v in diffs:
        if v['field'] == '.entities.ids':
            ids.update(set(v['python']) ^ set(v['rust']))
    native = d['rust']['entities']
    ids.update(e['id'] for e in native if e.get('birth') == row['first']['tick'])
    # Relevant actors include targeted victims, their attackers, and the source
    # bodies of newly created projectiles (source name + owner).
    for _ in range(2):
        selected = [e for e in native if e['id'] in ids]
        new_names = {(e.get('stats',{}).get('name'),e['owner']) for e in selected
                     if e['class'] not in ('Troop','Building')}
        ids.update(e['id'] for e in native if e.get('target') in ids
                   or (e['class'] in ('Troop','Building') and (e.get('stats',{}).get('name'),e['owner']) in new_names))
        ids.update(e.get('target') for e in selected if e.get('target') is not None)
    names = row['first']['detail']['entity_names'].copy()
    names.update({str(e['id']):e.get('stats',{}).get('name') for e in native})

    def state(p,n):
        return dict(python={eid:pbrief(e,names.get(eid)) for eid,e in p['raw_entities'].items() if int(eid) in ids},
                    rust={str(e['id']):nbrief(e) for e in n['entities'] if e['id'] in ids})
    out = dict(game=row['game'],tick=row['first']['tick'],first_phase=label,
               field_diff=diffs, focus_ids=sorted(ids),
               phases={k:dict(field_diff=[v for v in v['field_diff'] if public(v)],
                             **state(v['python'],v['rust'])) for k,v in phases.items()},
               history=[dict(tick=h['tick'],**state(h['python'],h['rust'])) for h in row['history']])
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('destination',type=Path)
    a=p.parse_args()
    for path in sorted(a.source.glob('game-*.json')):
        target=a.destination/path.name
        if target.exists():continue
        atomic(target,project(json.loads(path.read_text())))


if __name__=='__main__':main()
