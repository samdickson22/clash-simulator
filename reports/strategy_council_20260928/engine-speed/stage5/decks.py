"""Frozen human-role deck catalogs. Never use evaluation rows in the prior."""
import gzip
import hashlib
import json
from pathlib import Path
from collections import Counter
import sys
from clasher.card_aliases import resolve_card_name
from c56_controller import CARDS

COUNCIL=Path(__file__).resolve().parents[2]
CATALOG=COUNCIL/'c56/engine/root-v3/human_deck_catalog.json'
ROLES=COUNCIL/'c56/data/roles/c56_roles_v1.json'
INDEX=COUNCIL/'c56/data/index/perspectives.jsonl.gz'


def catalogs():
    sys.path.insert(0,str(COUNCIL/'m0/human-prior-scan'))
    from card_map import SLUG_TO_GAMEDATA
    roles=json.loads(ROLES.read_text())
    catalog=json.loads(CATALOG.read_text())
    assert catalog['roles_sha256']==hashlib.sha256(ROLES.read_bytes()).hexdigest()
    assert roles['index_sha256']==hashlib.sha256(INDEX.read_bytes()).hexdigest()==catalog['index_sha256']
    counts={role:Counter() for role in ('train','dev','eval','eval_ood')}
    declared={resolve_card_name(n):n for n in CARDS}
    with gzip.open(INDEX,'rt') as stream:
        for line in stream:
            row=json.loads(line);role=roles['roles'].get(f"{row['tag']}|{row['side']}")
            if role not in counts:
                continue
            cards=tuple(sorted(declared.get(resolve_card_name(SLUG_TO_GAMEDATA[n]),SLUG_TO_GAMEDATA[n]) for n in row['own_base']))
            if len(set(cards))==8 and set(cards)<=set(CARDS):
                counts[role][cards]+=1
    assert counts['train']==Counter({tuple(d['cards']):d['frequency'] for d in catalog['decks']})
    return {role:dict(decks=[dict(cards=list(d),frequency=n) for d,n in sorted(rows.items())]) for role,rows in counts.items()}


def family(cards):
    c=set(cards)
    if 'Goblinstein' in c:return 'Goblinstein'
    if 'ArcherQueen' in c:return 'AQ'
    if c==set(('HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log')):return 'Hog 2.6'
    if 'HogRider' in c and c & {'Earthquake','Firecracker','MightyMiner'}:return 'Hog EQ/Firecracker/MM'
    if 'Xbow' in c:return 'X-Bow'
    if 'RoyalHogs' in c or 'FirespiritHut' in c:return 'Royal Hogs/Furnace'
    if 'GoblinBarrel' in c or 'Princess' in c:return 'bait'
    return 'other'
