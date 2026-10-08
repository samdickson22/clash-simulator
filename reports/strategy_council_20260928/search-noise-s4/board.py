"""Public-token boundary; templates supply static card/body associations only."""
from collections import defaultdict

def body_card_map(resources):
    mapping=defaultdict(set)
    def primary(value):
        if isinstance(value,dict) and 'class' in value:
            yield value
        elif isinstance(value,list):
            for item in value: yield from primary(item)
    for card,spec in resources.config['cards'].items():
        for template in primary(spec.get('units',[])):
            if template['class'] not in ('Troop','Building'): continue
            body=template['stats']['name']
            meta=resources.meta['bodies'].get(body)
            if meta: mapping[int(meta['token'])].add(card)
    # Ambiguous multi-card bodies remain mixtures; no true deck is consulted.
    return {token:tuple((card,1/len(names)) for card in sorted(names)) for token,names in mapping.items()}

def public_bodies(info):
    obs=info.packet.observation
    return [(int(token),float(row[0])*18,float(row[1])*32)
            for token,row in zip(obs.entity_ids[obs.entity_mask],obs.entity_features[obs.entity_mask])
            if row[3]>.5 and (row[4]>.5 or row[5]>.5)]
