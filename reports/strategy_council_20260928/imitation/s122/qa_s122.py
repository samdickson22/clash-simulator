"""Predeclared T10 QA aggregation and deterministic observer noninterference proof."""
import collections,json,sys
from pathlib import Path
import numpy as np
from extract_s122 import DATA,C56,BUILDER,read,write,pins,aggregate,sha,cb

def main():
    pin=pins();plan=read(DATA/'inputs/qa-fast-plan.json');values=[]
    for u in plan['units']:
        v=read(DATA/'qa/s122-qa/units'/f'{u["unit"]}.json')
        assert v['pins']==pin and not v['errors'] and not any(v['violations'])
        assert all(sha(DATA/'qa/s122-qa'/n)==s for n,s in v['files'].items())
        values.append(v)
    assert sum(v['perspectives'] for v in values)==400
    determinism=[]
    for u in plan['units']:
        if u['keys'][0] not in plan['determinism_keys']:continue
        mainpath=DATA/'qa/s122-qa'/f'{u["unit"]}.npz'
        for kind in ('repeat','baseline'):
            check=DATA/f'qa/s122-{kind}'/f'{u["unit"]}.npz'
            assert sha(mainpath)==sha(check),(u['unit'],kind,'archive differs')
            with np.load(mainpath,allow_pickle=False) as a,np.load(check,allow_pickle=False) as b:
                assert set(a.files)==set(b.files)
                for n in a.files:assert a[n].dtype==b[n].dtype and a[n].shape==b[n].shape and a[n].tobytes()==b[n].tobytes(),(u['unit'],kind,n)
        for kind in ('sidecar','audit','events'):
            suffix='.json.gz' if kind=='events' else '.npz'
            assert sha(DATA/'qa/s122-qa'/kind/(u['unit']+suffix))==sha(DATA/'qa/s122-repeat'/kind/(u['unit']+suffix))
        determinism.append({'key':u['keys'][0],'archive_sha256':sha(mainpath),'repeat_and_no_observer_equal':True,'sidecar_and_audit_repeat_equal':True})
    assert len(determinism)==6
    summaries=[s for v in values for s in v['summaries']];stats=aggregate(summaries)
    attempts=collections.Counter();rejected=collections.Counter();per_card_summary=collections.defaultdict(list)
    for v in values:
        for s,meta in zip(v['summaries'],v['stats']):
            attempts.update(meta['per_card']['attempts']);rejected.update(meta['per_card']['rejected'])
            for card in meta['item']['own_base']:per_card_summary[card].append(s)
    slugs=cb.slug_map();payload=read(DATA/'receipts/T9-payloads.json');bycard={}
    for card in payload['roster']:
        name=slugs[card];a=attempts[name];r=rejected[name];members=per_card_summary[card]
        bycard[card]={'own_placement_attempts':a,'own_placement_rejected':r,'own_placement_acceptance':1-r/a if a else None,
                      'perspectives':len(members),'retention':aggregate(members)['retention'] if members else None}
    # Bars are fixed in DESIGN §3. Never change samples or thresholds after outcomes.
    excluded=[c for c in payload['new_own_cards'] if bycard[c]['own_placement_acceptance'] is not None and bycard[c]['own_placement_acceptance']<.95]
    zero_attempts=[c for c in payload['new_own_cards'] if not bycard[c]['own_placement_attempts']]
    illegal=sum(v['illegal_labels'] for v in values)
    passed=stats['placement_acceptance']>=.99 and illegal==0 and not zero_attempts
    result={'passed':passed,'pins':pin,'perspectives':400,'rows':sum(v['rows'] for v in values),'errors':0,'illegal_labels':illegal,
            'stats':stats,'per_card':bycard,'excluded_new_cards':excluded,'new_cards_without_placement_attempts':zero_attempts,
            'violations':[0]*5,'determinism':determinism,'qa_sample_sha256':plan['qa_sample_sha256'],
            'golden_knight_ability_counters':dict(sum((collections.Counter(s['counters']) for s,meta in [(s,m) for v in values for s,m in zip(v['summaries'],v['stats'])] if 'golden-knight' in meta['item']['own_base']),collections.Counter())),
            'per_card_acceptance_definition':'own labels plus own masked/pocket pre-label failures; own placement rejection counts as failure; exact same frozen label path',
            'wall_cpu_by_host':[read(p) for p in sorted((DATA/'qa/s122-qa').glob('complete-*.json'))]}
    write(DATA/'receipts/T10-QA.json',result)
    assert passed,('T10 QA gate failed',stats,illegal,zero_attempts)
    write(DATA/'receipts/T10-QA-PASS.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('per_card','pins','determinism','wall_cpu_by_host')}),flush=True)
if __name__=='__main__':main()
