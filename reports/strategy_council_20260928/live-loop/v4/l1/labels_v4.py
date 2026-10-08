"""Split-independent label cleaning from retained ordinary/rich receipts.

This is evaluator/trainer code only. CSV row order is NOT a certified runtime
body-ID catalog. A parent-card hint is NOT a body label. Resolve a body only
when exactly one reachable hitpoint-bearing payload has the observed max HP.
Unresolved bodies stay unknown. Visibility/deployment require same-tick rich
evidence and a complete ordinary/rich identity/position/HP join.
"""
from collections import defaultdict
import gzip
import json
from pathlib import Path

from clasher.gamedata_normalization import build_object_registry
from clasher.stat_scaling import scale_stat


def normalized_body(name):
    value=(name or '').lower().replace('_','')
    return {'goblinstab':'goblin','goblinsspear':'speargoblin','goblins':'goblin',
            'skeletons':'skeleton','tower':'princesstower','minions':'minion',
            'archers':'archer','icespirit':'icespirits'}.get(value,value)


def dictionaries(value):
    if isinstance(value,dict):
        yield value
        for v in value.values():yield from dictionaries(v)
    elif isinstance(value,list):
        for v in value:yield from dictionaries(v)


def rich_index(rows):
    """Repeated same-tick snapshots must agree; never choose a later one."""
    grouped=defaultdict(list)
    for row in rows:grouped[row['tick']].append({o['nativeObjectId']:o for o in row['objects']})
    result={}
    def signature(o):
        if o is None:return None
        return tuple(o.get(k) for k in ('owner','cardId','dataGlobalId','x','y','hp','maxHp','visibilityState'))+((o.get('phaseRuntime') or {}).get('deployRemainingMs'),)
    for tick,snapshots in grouped.items():
        result[tick]={}
        for identity in set().union(*(set(s) for s in snapshots)):
            objects=[s.get(identity) for s in snapshots]
            if objects[0] is not None and all(signature(o)==signature(objects[0]) for o in objects):result[tick][identity]=objects[0]
    return result


class BodyLabels:
    def __init__(self,gamedata,catalog):
        data=json.loads(Path(gamedata).read_text());registry=build_object_registry(data)
        names=json.loads(Path(catalog).read_text())['names'].values()
        canonical={normalized_body(n):n for n in names}
        canonical.update(goblin='Goblin',speargoblin='SpearGoblin',skeleton='Skeleton',
                         archer='Archer',minion='Minion',icespirits='IceSpirits')
        self.candidates={}
        for card in data['items']['spells']:
            if 'id' not in card:continue
            found={};seen=set()
            def visit(value):
                for obj in dictionaries(value):
                    name=obj.get('name')
                    if name in registry and name not in seen:
                        seen.add(name);visit(registry[name])
                    if obj.get('source','').split('_')[0] in ('characters','buildings') and obj.get('hitpoints',0)>0:
                        key=canonical.get(normalized_body(name),name)
                        found.setdefault(scale_stat(obj['hitpoints'],11),set()).add(key)
                    # Follow named spawn/morph/death references, including fields
                    # for which the export omits a nested *Data object.
                    for field,v in obj.items():
                        if isinstance(v,str) and v in registry and v not in seen and any(s in field.lower() for s in ('spawn','morph','summon')):
                            seen.add(v);visit(registry[v])
            visit(card)
            self.candidates[card['id']]=found

    def identity(self,o):
        if not o.get('max_hp') or o['max_hp']<=0:return None,'non_hitpoint'
        if o['card_id']==-1:
            anchors={(0,9000,3000):('KingTower',4824),(1,9000,29000):('KingTower',4824)}
            for side,y in [(0,6500),(1,25500)]:
                for x in (3500,14500):anchors[side,x,y]=('PrincessTower',3052)
            expected=anchors.get((o['owner'],o['x'],o['y']))
            if expected and expected[1]==o['max_hp']:return expected[0],'tower_anchor_hp'
            return None,'unresolved_tower'
        candidates=self.candidates.get(o['card_id'],{}).get(o['max_hp'],set())
        if len(candidates)==1:return next(iter(candidates)),'unique_card_payload_hp'
        return None,'ambiguous_payload' if candidates else 'unresolved_payload'

    def clean(self,rows,rich_rows):
        snapshots=rich_index(rich_rows)
        cleaned=[]
        for row in rows:
            objects=[]
            for original in row['objects']:
                o=dict(original);name,reason=self.identity(o)
                o['body_name_original']=o.get('body_name');o['body_name']=name
                o['body_identity_source']=reason
                rich=snapshots.get(row['tick'],{}).get(o['native_id'])
                keys=(('owner','owner'),('card_id','cardId'),('x','x'),('y','y'),('hp','hp'),('max_hp','maxHp'))
                coherent=rich is not None and all(o.get(k)==rich.get(v) for k,v in keys)
                o['visible_hint']=rich.get('visibilityState') if coherent else None
                phase=(rich.get('phaseRuntime') or {}) if coherent else {}
                o['deploying']=(phase['deployRemainingMs']>0) if phase.get('deployRemainingMs') is not None else None
                o['metadata_tick']=row['tick'] if coherent else None
                o['data_global_id']=rich.get('dataGlobalId') if coherent else None
                o['label_join']='same_tick_coherent' if coherent else 'unavailable'
                objects.append(o)
            cleaned.append(dict(row,objects=objects))
        return cleaned


def read_objects(path):
    with gzip.open(path,'rt') as f:return [json.loads(line) for line in f]
