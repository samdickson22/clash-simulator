"""T9 S121 (legacy S122 naming) payloads/index, using pinned data only.

C56 is independently re-filtered and checked before this entrypoint is allowed.
No original payload, index, role, runtime or engine file is ever changed.
"""
from __future__ import annotations
import collections, gzip, hashlib, json, os, sys, time
from pathlib import Path
import pyarrow.parquet as pq
from fetch_source import ROOT, DATA, OUT as RAW, sha, write
COUNCIL=ROOT/'reports/strategy_council_20260928'
sys.path.insert(0,str(COUNCIL/'m0/human-prior-scan'))
from card_map import base_slug,SLUG_TO_GAMEDATA,UNSUPPORTED_BASE
C56=set(json.loads((COUNCIL/'scope-expansion/scope_coverage.json').read_text())['c56_list'])
S122=set(SLUG_TO_GAMEDATA); S121=S122-{'three-musketeers'}; S117=S122-set(UNSUPPORTED_BASE)
SIDES=('team','opponent')
P16={'archers','cannon','dark-prince','fireball','giant','goblins','hog-rider','ice-golem','ice-spirit','knight','the-log','musketeer','prince','skeletons','tesla','zap'}

def line(x):return (json.dumps(x,sort_keys=True,separators=(',',':'))+'\n').encode()

def main():
    gate=json.loads((DATA/'receipts/T9-C56-equality.json').read_text())
    assert gate['payload_byte_equal'] and gate['archive_byte_equal'] and gate['shards']==52
    assert len(S121)==121 and len(S121-C56)==65
    entries=[x for x in json.loads((RAW/'hf_manifest.json').read_text())['files'] if x['path'].startswith('replays/')]
    for folder in ('payloads','index/shards','receipts/payload-shards'): (DATA/folder).mkdir(parents=True,exist_ok=True)
    for shard,e in enumerate(entries):
        target=DATA/f'payloads/shard-{shard:03d}.jsonl.gz'
        idx=DATA/f'index/shards/shard-{shard:03d}.jsonl.gz'
        receipt=DATA/f'receipts/payload-shards/shard-{shard:03d}.json'
        if receipt.exists():
            saved=json.loads(receipt.read_text()); assert sha(target)==saved['payload_sha256'] and sha(idx)==saved['index_sha256']; continue
        assert sha(RAW/e['path'])==e['sha256']
        counts=collections.Counter(); cards=collections.Counter(); played=collections.Counter(); flags=collections.Counter(); match_index=0
        with gzip.GzipFile(filename=str(target)+'.tmp',mode='wb',mtime=0) as pf, gzip.GzipFile(filename=str(idx)+'.tmp',mode='wb',mtime=0) as ix:
            parquet=pq.ParquetFile(RAW/e['path'])
            for batch in parquet.iter_batches(batch_size=64,columns=['replay_tag','battle_type','game_mode','payload_json']):
                for source_row in batch.to_pylist():
                    counts['raw_matches']+=1
                    payload=json.loads(source_row['payload_json']); battle=payload['battle']
                    players={s:battle[s]['players'] for s in SIDES}
                    if any(len(p)!=1 for p in players.values()): counts['not_1v1']+=1; continue
                    players={s:p[0] for s,p in players.items()}
                    decks={s:[base_slug(c['card_key'])[0] for c in p['deck']] for s,p in players.items()}
                    if any(len(d)!=8 or len(set(d))!=8 or not set(d)<=S122 for d in decks.values()): counts['invalid_deck']+=1; continue
                    if any((p.get('tower_card') or {}).get('card_key')!='tower-princess' for p in players.values()): counts['tower_troop_matches']+=1; continue
                    events=payload.get('events') or []
                    plays={s:[ev for ev in events if ev.get('side')==s and ev.get('kind')=='play_card'] for s in SIDES}
                    if any(not p for p in plays.values()): counts['no_plays_matches']+=1; continue
                    new=[s for s in SIDES if not set(decks[s])<=C56]
                    counts['pre_3m_new_perspectives']+=len(new)
                    # Exclude even an unplayed 3M deck slot, and any out-of-deck 3M event.
                    if any('three-musketeers' in d for d in decks.values()) or any(base_slug(ev.get('card_key') or '')[0]=='three-musketeers' for ps in plays.values() for ev in ps):
                        counts['three_musketeers_matches']+=1; counts['three_musketeers_new_perspectives']+=len(new); continue
                    if not new: continue
                    meta={'battle_healer':any('battle-healer' in d for d in decks.values()),'mirror':any('mirror' in d for d in decks.values())}
                    record={'tag':source_row['replay_tag'],'shard':shard,'battle_type':source_row['battle_type'],'game_mode':source_row['game_mode'],'s122_sides':new,'flags':meta,'payload':payload}
                    pf.write(line(record)); counts['matches']+=1
                    for side in new:
                        p=players[side]; other=SIDES[1-SIDES.index(side)]; bases=sorted(decks[side]); slugs=sorted(c['card_key'] for c in p['deck'])
                        playcounts=collections.Counter(base_slug(ev.get('card_key') or '')[0] for ev in plays[side])
                        row={'shard':shard,'match_index':match_index,'tag':record['tag'],'side':side,'seat':SIDES.index(side),
                             'episode_id':1_000_000_000+shard*100_000+match_index*2+SIDES.index(side),
                             's117':set(decks[other])<=S117,'own_base':bases,'own_slugs':slugs,
                             'own_levels':sorted(f"{c['card_key']}:{c['level']}" for c in p['deck']),
                             'tower':p['tower_card']['card_key'],'tower_level':p['tower_card'].get('level'),
                             'opponent_base':sorted(decks[other]),'game_mode':record['game_mode'],'battle_type':record['battle_type'],
                             'result':battle['result'] if side=='team' else {'victory':'defeat','defeat':'victory'}.get(battle['result'],battle['result']),
                             'timeline_seconds':payload['replay']['duration']['timeline_seconds'],'own_plays':len(plays[side]),
                             'own_plays_by_card':dict(sorted(playcounts.items())),
                             'own_abilities':sum(ev.get('side')==side and ev.get('kind')=='activate_ability' for ev in events),
                             'p16':set(bases)<=P16,'flags':meta,'source':'s122-new'}
                        ix.write(line(row)); counts['perspectives']+=1; cards.update(bases); played.update(playcounts); flags.update(k for k,v in meta.items() if v)
                    match_index+=1
        os.replace(str(target)+'.tmp',target); os.replace(str(idx)+'.tmp',idx)
        result={'shard':shard,'counts':dict(counts),'perspectives_by_own_card':dict(cards),'recorded_plays_by_card':dict(played),'flagged_perspectives':dict(flags),'payload_sha256':sha(target),'index_sha256':sha(idx)}
        write(receipt,result); print(json.dumps({'shard':shard,**counts}),flush=True)
    final=DATA/'index/perspectives.jsonl.gz'
    if not final.exists():
        with gzip.GzipFile(filename=str(final)+'.tmp',mode='wb',mtime=0) as f:
            for shard in range(52):
                with gzip.open(DATA/f'index/shards/shard-{shard:03d}.jsonl.gz','rb') as src:
                    while b:=src.read(1048576):f.write(b)
        os.replace(str(final)+'.tmp',final)
    receipts=[json.loads((DATA/f'receipts/payload-shards/shard-{s:03d}.json').read_text()) for s in range(52)]
    aggregate={k:dict(sum((collections.Counter(r[k]) for r in receipts),collections.Counter())) for k in ('counts','perspectives_by_own_card','recorded_plays_by_card','flagged_perspectives')}
    assert aggregate['counts']['pre_3m_new_perspectives']==355585,aggregate['counts']
    result=aggregate|{'roster':sorted(S121),'new_own_cards':sorted(S121-C56),'source_revision':json.loads((RAW/'hf_manifest.json').read_text())['revision'],'index_sha256':sha(final),'payload_files':[{'file':f'shard-{r["shard"]:03d}.jsonl.gz','sha256':r['payload_sha256']} for r in receipts]}
    write(DATA/'receipts/T9-payloads.json',result)
if __name__=='__main__':main()
