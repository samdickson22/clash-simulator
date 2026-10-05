"""Prospective 64-game base-form human-deck schedule covering all 66 cards.

Read-only over the corpus. No simulation outcomes participate in selection.
"""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import random

from clasher.card_aliases import resolve_card_name
from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS
from clasher.rl.c56_scripted import C56_ADDED_CARDS

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[3]
SCAN=ROOT/'reports/strategy_council_20260928/m0/human-prior-scan'


def base(slug):
    for suffix in ('-ev1','-ev2','-hero'):
        if slug.endswith(suffix):return slug[:-len(suffix)]
    return slug


def main():
    output=FOLDER/'human64-plan.json'
    assert not output.exists(),'preserve the existing prospective plan'
    original=SUPPORTED_CARDS|C56_ADDED_CARDS
    aliases={resolve_card_name(n):n for n in original}
    rows=json.loads((SCAN/'supported_cards.json').read_text())['cards']
    scope={r['slug']:aliases.get(resolve_card_name(r['gamedata']),resolve_card_name(r['gamedata']))
           for r in rows if r['scalar_s120'] or r['slug'] in {'vines','void','goblin-curse','elixir-collector','goblin-drill'}}
    assert len(set(scope.values()))==122
    remaining={r['canonical'] for r in json.loads((FOLDER/'scope.json').read_text())['remaining']}
    frequencies=Counter();examples={};matched=0
    with gzip.open(SCAN/'corpus_index.jsonl.gz','rt') as handle:
        for line in handle:
            row=json.loads(line)
            for seat in ('team','opponent'):
                side=row['sides'][seat]
                slugs=[base(c) for c in side['deck']]
                if not side['plays'] or side['tower']!='tower-princess' or not set(slugs)<=scope.keys():continue
                deck=tuple(sorted(scope[c] for c in slugs))
                if len(deck)!=8 or len(set(deck))!=8:continue
                frequencies[deck]+=1;matched+=1
                examples.setdefault(deck,dict(shard=row['shard'],tag=row['tag'],side=seat))
    ranked=sorted(frequencies,key=lambda d:(-frequencies[d],d))
    assert remaining <= set().union(*(set(d) for d in ranked))
    selected=[];uncovered=set(remaining)
    while uncovered:
        deck=max(ranked,key=lambda d:(len(set(d)&uncovered),frequencies[d]))
        assert set(deck)&uncovered
        selected.append(deck);uncovered-=set(deck)
    assert len(selected)<=32,('more than32 decks needed',len(selected))
    selected += [d for d in ranked if d not in selected][:32-len(selected)]
    episodes=[]
    for pair,deck in enumerate(selected):
        opponent=ranked[(pair*17+3)%len(ranked)]
        rng=random.Random(666000+pair)
        decks=[list(deck),list(opponent)]
        for d in decks:rng.shuffle(d)
        for reverse in (False,True):
            ordered=list(reversed(decks)) if reverse else decks
            originals=(opponent,deck) if reverse else (deck,opponent)
            episodes.append(dict(id=len(episodes),pair=pair,seed=667000+pair,decks=ordered,
                                 frequencies=[frequencies[d] for d in originals],
                                 examples=[examples[d] for d in originals]))
    sources=[SCAN/'supported_cards.json',SCAN/'corpus_index.jsonl.gz',FOLDER/'scope.json',Path(__file__)]
    plan=dict(status='prospective; simulation/admission pending',
              selection='greedy remaining-card coverage then deck frequency; fill32 unique focal decks by frequency; fixed17-stride human opponents; paired seats; no outcome selection',
              forms='evolution/hero suffixes substituted by their Python base card; no evolved or hero mechanics',
              towers='Princess',level=11,source_perspectives=matched,unique_decks=len(ranked),
              sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
              required_cards=sorted(remaining),episodes=episodes)
    output.write_text(json.dumps(plan,indent=2)+'\n')
    print('planned',len(episodes),'games covering',len(remaining),'cards from',len(ranked),'human decks')


if __name__=='__main__':main()
