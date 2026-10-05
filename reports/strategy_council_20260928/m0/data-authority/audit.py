"""Read-only comparison of two already opened ruleset inputs."""
import hashlib
import json
from pathlib import Path

import numpy as np

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.dynamic_spells import load_dynamic_spells
from clasher.player import PlayerState
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS
from clasher.rl.card_semantics import SEMANTIC_EXTRA_FEATURE_NAMES

ROOT = Path.cwd()
OUT = ROOT / 'reports/strategy_council_20260928/m0/data-authority'
PATHS = {'workspace': ROOT/'gamedata.json', 'capture': ROOT/'reports/calibration_development_20260915/expanded-deck-development/forward-0/gamedata.json'}
NAMES = tuple(sorted(SUPPORTED_CARDS))
LEGACY_FEATURES = ('elixir_cost','is_troop','is_building','is_spell','is_champion','hitpoints','damage','attack_range','sight_range','movement_speed','hit_speed','deploy_time','collision_radius','summon_count','targets_ground','targets_air')
FEATURE_NAMES = LEGACY_FEATURES + tuple(SEMANTIC_EXTRA_FEATURE_NAMES)
FIELDS = ('level','mana_cost','hitpoints','scaled_hitpoints','damage','scaled_damage','range','sight_range','speed','hit_speed','load_time','deploy_time','collision_radius','lifetime_ms','summon_count','summon_deploy_delay','projectile_damage','projectile_speed','damage_special','shield_hitpoints','target_type','area_damage_radius','first_hit_time','retarget_time')
SPELL_FIELDS = ('level','damage','radius','crown_tower_damage','duration','stun_duration','speed','mana_cost','building_damage_percent','crown_tower_damage_percent')

def scalar(value):
    return value if isinstance(value, (str,int,float,bool,type(None))) else repr(value)

def summary(obj, fields):
    return {name: scalar(getattr(obj,name,None)) for name in fields}

def payloaddiff(a,b,prefix=''):
    result=[]
    if isinstance(a,dict) and isinstance(b,dict):
        for key in sorted(a.keys()|b.keys()):
            result += payloaddiff(a.get(key),b.get(key),f'{prefix}.{key}' if prefix else key)
    elif isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
        for i,(x,y) in enumerate(zip(a,b)): result += payloaddiff(x,y,f'{prefix}[{i}]')
    elif a!=b: result.append({'path':prefix,'workspace':a,'capture':b})
    return result

loaders={key:CardDataLoader(path) for key,path in PATHS.items()}
builders={key:StructuredObservationBuilder(card_loader=loader,card_vocab=NAMES,card_semantics_version=4) for key,loader in loaders.items()}
registries={key:load_dynamic_spells(path) for key,path in PATHS.items()}
rows=[]
for name in NAMES:
    row={'name':name}
    stats={key:loader.get_card(name) for key,loader in loaders.items()}
    row['loaded']={key:summary(value,FIELDS) for key,value in stats.items()}
    row['loaded_differences']=payloaddiff(row['loaded']['workspace'],row['loaded']['capture'])
    row['normalized_payload_differences']=payloaddiff(stats['workspace']._raw_entry,stats['capture']._raw_entry)
    vectors={key:builder.card_stat_features[builder.token_id(name)] for key,builder in builders.items()}
    row['semantic_v4_differences']=[{'index':int(i),'feature':FEATURE_NAMES[i], 'workspace':float(vectors['workspace'][i]),'capture':float(vectors['capture'][i])} for i in np.flatnonzero(vectors['workspace']!=vectors['capture'])]
    row['runtime']={}
    for key,loader in loaders.items():
        battle=BattleState(players=[PlayerState(0,hand=[name]+[other for other in NAMES if other!=name][:3],elixir=10), PlayerState(1)],card_loader=loader)
        resolved=battle.resolve_card_play(0,name)
        before=set(battle.entities)
        accepted=battle.deploy_card(0,name,Position(7,7))
        bodies=[entity for entity in battle.entities.values() if entity.id not in before]
        row['runtime'][key]={'accepted':accepted,'resolved_spell':None if resolved[2] is None else summary(resolved[2],SPELL_FIELDS),'new_entities':[summary(entity,('name','hitpoints','max_hitpoints','damage','shield_hitpoints')) for entity in bodies]}
        if resolved[2] is not None:
            own=registries[key].get(resolved[0])
            row['runtime'][key]['file_bound_spell']=None if own is None else summary(own,SPELL_FIELDS)
    rows.append(row)
result={'files':{key:{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size} for key,path in PATHS.items()},'cards':rows}
(OUT/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
for row in rows:
    print(row['name'],len(row['loaded_differences']),'loaded differences;',len(row['semantic_v4_differences']),'semantic differences;',len(row['normalized_payload_differences']),'payload differences')
    for item in row['loaded_differences']:print(' ',item)

# Exercise the actual readiness constructor, not only an equivalent battle.
import sys
sys.path.insert(0, str(ROOT/'scripts'))
from compare_reacting_public_branches import scalar_initial
from clasher.rl.selfplay_env import SelfPlayBattleEnv
capture = PATHS['capture'].parent
initial = json.loads((capture/'initial.json').read_text())
config = json.loads((capture/'plan.json').read_text())['config']
names = {loaders['capture'].get_card(name)._raw_entry['id']:name for name in NAMES}
reference = scalar_initial(initial, names, config, loaders['capture'])
default_env = SelfPlayBattleEnv(public_contract_version=4, seed=734)
default_env.reset()
result['constructed_authorities'] = {
    'scalar_initial_card_loader': str(reference.card_loader.data_file),
    'default_env_card_loader': str(default_env.battle.card_loader.data_file),
    'default_env_structured_builder_loader': str(default_env.structured_obs_builder.loader.data_file),
    'scalar_initial_IceSpirit_resolved':summary(reference.resolve_card_play(0,'IceSpirit')[1],FIELDS),
    'default_env_IceSpirit_resolved':summary(default_env.battle.resolve_card_play(0,'IceSpirit')[1],FIELDS),
    'capture_level_cap':config['battle']['lvlcap'],
    'capture_card_minimum_level':config['battle']['cardlvlmin'],
}
(OUT/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
