"""Read-only Phase A train/validation label diagnostics, no heldout payloads."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
from stage_training import sha
from labels_v4 import BodyLabels,rich_index
from functools import lru_cache


@lru_cache(maxsize=1)
def cleaner():
    root=Path(__file__).resolve().parents[5]
    return BodyLabels(root/'gamedata.json',Path(__file__).parents[1]/'body-catalog.json')


def normal(name):
    value = (name or '').lower().replace('_', '')
    return {'goblinstab':'goblin', 'goblinsspear':'speargoblin', 'goblins':'goblin',
            'skeletons':'skeleton', 'tower':'princesstower', 'minions':'minion',
            'archers':'archer', 'icespirit':'icespirits'}.get(value, value)


def one(args):
    path, catalog = args
    root = Path(path); receipt = json.loads((root/'receipt.json').read_text())
    if receipt['split'] not in ('train','validation'): raise ValueError('Heldout forbidden')
    for name in ('objects.jsonl.gz','rich-objects.jsonl.gz'):
        if sha(root/name) != receipt['files'][name]: raise ValueError('Payload checksum')
    counts = Counter(); pairs = Counter(); examples = []; timelines = defaultdict(list);causes=Counter();resolved=Counter();rich_rows=[]
    with gzip.open(root/'rich-objects.jsonl.gz','rt') as f:
        for line in f:
            row = json.loads(line)
            rich_rows.append(row)
            for o in row['objects']:
                timelines[o['nativeObjectId']].append((row['tick'], o))
    changing = {k for k, v in timelines.items() if len({(o['owner'],o['cardId'],o['dataGlobalId']) for _,o in v})>1}
    snapshots=rich_index(rich_rows)
    counts['rich_native_ids'] = len(timelines); counts['rich_identity_changing_ids'] = len(changing)
    with gzip.open(root/'objects.jsonl.gz','rt') as f:
        for line in f:
            row = json.loads(line)
            for o in row['objects']:
                counts['objects'] += 1
                name,reason=cleaner().identity(o)
                counts['clean_identity_'+reason]+=1
                counts['clean_name_changed']+=name!=o.get('body_name')
                rich=snapshots.get(row['tick'],{}).get(o['native_id'])
                coherent=rich is not None and all(o.get(a)==rich.get(b) for a,b in [('owner','owner'),('card_id','cardId'),('x','x'),('y','y'),('hp','hp'),('max_hp','maxHp')])
                counts['clean_visible_nondeploying']+=bool(name and coherent and rich.get('visibilityState')=='visible' and (rich.get('phaseRuntime') or {}).get('deployRemainingMs')==0)
                contradiction = bool(o.get('body_name') and o.get('body_name_hint') and normal(o['body_name']) != normal(o['body_name_hint']))
                counts['contradictions'] += contradiction
                counts['metadata_from_future'] += o.get('metadata_tick', -1) > row['tick']
                if not contradiction: continue
                if reason=='non_hitpoint':cause='non_body_parent_hint'
                elif name and normal(name)!=normal(o.get('body_name')):cause='catalog_generation_bug'
                elif name:cause='legitimate_parent_child_hint'
                else:cause='unresolved_masked'
                causes[cause]+=1
                resolved[json.dumps([o.get('data_global_id'),o.get('body_name'),o.get('body_name_hint'),o.get('max_hp'),name,reason])]+=1
                counts['contradictory_hitpoint_objects'] += bool(o.get('max_hp',0) and o['max_hp']>0)
                counts['contradictory_changing_ids'] += o['native_id'] in changing
                same = [rich for tick,rich in timelines.get(o['native_id'],[]) if tick==row['tick']]
                for rich in same:
                    counts['contradictory_same_tick_rich'] += 1
                    counts['same_tick_id_differs'] += o.get('data_global_id') != rich['dataGlobalId']
                    counts['same_tick_fields_differ'] += any(o.get(a)!=rich.get(b) for a,b in [('owner','owner'),('card_id','cardId'),('x','x'),('y','y'),('hp','hp'),('max_hp','maxHp')])
                pair = json.dumps([o.get('data_global_id'),o.get('body_name'),o.get('body_name_hint'),o.get('max_hp')])
                pairs[pair] += 1
                if len(examples)<16 and (same or not examples):
                    examples.append(dict(tick=row['tick'], object=o, rich=same[:1]))
    return dict(episode=receipt['episode'],split=receipt['split'],counts=dict(counts),pairs=dict(pairs),examples=examples,causes=dict(causes),resolved=dict(resolved),
                receipt_sha256=sha(root/'receipt.json'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--split',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    members={r['seed']:r for r in json.loads(a.split.read_text())['matches']}
    rows=[]
    for rpath in sorted(a.source.glob('*/receipt.json')):
        r=json.loads(rpath.read_text())
        if r.get('split') not in ('train','validation'):continue
        m=members[r['seed']]
        if (m['split'],m['decks'])!=(r['split'],r['decks']):raise ValueError('Frozen membership mismatch')
        rows.append(str(rpath.parent))
    with ProcessPoolExecutor(a.workers) as pool: results=list(pool.map(one,[(r,{}) for r in rows]))
    counts=Counter();pairs=Counter();causes=Counter();resolved=Counter()
    for r in results:
        counts.update(r['counts']);pairs.update(r['pairs']);causes.update(r['causes']);resolved.update(r['resolved'])
    result=dict(matches=len(results),counts=dict(counts),causes=dict(causes),resolved=dict(resolved.most_common()),pairs=dict(pairs.most_common()),per_match=results,heldout_opened=False)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(result,f)
    print(json.dumps(dict(matches=len(results),counts=dict(counts),causes=dict(causes),top_resolved=resolved.most_common(25))),flush=True)


if __name__=='__main__':main()
