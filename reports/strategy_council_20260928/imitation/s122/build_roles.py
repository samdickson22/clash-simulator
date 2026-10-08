"""Extend C56 roles without changing a single existing assignment.

Preserve existing family membership/leader order. New decks join the first
frequency-ordered existing leader sharing >=7 cards or establish new leaders.
New OOD families contain S122-only decks. Same salt, thresholds, proxy rules.
If a new held-out side conflicts with frozen C56 train, exclude the NEW side;
otherwise exclude new train when the opposing role is non-train. Never mutate v1.
QA selection is outcome-blind, hash-ordered, with >=3 played-card perspectives
for each of 65 new supported cards, then hash-fill to exactly 400.
"""
from __future__ import annotations
import collections,gzip,hashlib,itertools,json,sys
from pathlib import Path
from fetch_source import ROOT,DATA,sha,write
C56DATA=ROOT/'reports/strategy_council_20260928/c56/data'
SALT='c56-roles-v1:'
def h(x):return int(hashlib.sha256((SALT+x).encode()).hexdigest()[:12],16)
def key(r):return r['tag']+'|'+r['side']
def loadrows(p):return [json.loads(l) for l in gzip.open(p)]
def proxy(r):return (tuple(r['own_levels']),r['tower'],r['tower_level'])

def main():
    oldpath=C56DATA/'roles/c56_roles_v1.json'; oldsha=sha(oldpath); old=json.loads(oldpath.read_text())
    before=old['roles'].copy(); oldrows=loadrows(C56DATA/'index/perspectives.jsonl.gz'); rows=loadrows(DATA/'index/perspectives.jsonl.gz')
    assert len(before)==len(oldrows)==82231
    assert not set(before)&{key(r) for r in rows}
    oldcounts=collections.Counter(tuple(r['own_base']) for r in oldrows)
    oldleaders=sorted({tuple(f.split('|')) for f in old['family'].values()},key=lambda d:(-oldcounts[d],d))
    leaders=[]; seven={}; family_of={tuple(r['own_base']):tuple(old['family'][key(r)].split('|')) for r in oldrows}
    def add(leader):
        rank=len(leaders); leaders.append(leader)
        for s in itertools.combinations(leader,7): seven.setdefault(s,rank)
    for d in oldleaders:add(d)
    counts=collections.Counter(tuple(r['own_base']) for r in rows)
    for d,_ in sorted(counts.items(),key=lambda x:(-x[1],x[0])):
        assert d not in family_of
        matches=[seven[s] for s in itertools.combinations(d,7) if s in seven]
        if matches:family_of[d]=leaders[min(matches)]
        else:add(d); family_of[d]=d
    family_size=collections.Counter(family_of[tuple(r['own_base'])] for r in rows)
    oldleader_set=set(oldleaders); oldood={tuple(x) for x in old['ood_families']}
    newood=[]; covered=0
    for leader in sorted(family_size,key=lambda d:h('|'.join(d))):
        if covered>=.04*len(rows):break
        if leader in oldleader_set or not 100<=family_size[leader]<=2500:continue
        newood.append(leader);covered+=family_size[leader]
    ood=oldood|set(newood); proxies=collections.Counter(proxy(r) for r in rows)
    roles=dict(before); family=dict(old['family']); provisional={}
    for r in rows:
        k=key(r); leader=family_of[tuple(r['own_base'])]; family[k]='|'.join(leader)
        if leader in ood:role='eval_ood'
        else:
            p=proxy(r); group='proxy:'+json.dumps(p)
            if proxies[p]>200:group+='|match:'+r['tag']
            bucket=h(group)%1000;role='train' if bucket<900 else 'dev' if bucket<950 else 'eval'
        roles[k]=role;provisional[k]=role
    exclusions=[]
    for r in rows:
        k=key(r); other=r['tag']+'|'+('opponent' if r['side']=='team' else 'team')
        a=provisional[k]; b=before.get(other,provisional.get(other))
        reason=None
        if a=='train' and b is not None and b!='train':reason='new_train_opposes_nontrain'
        elif other in before and b=='train' and a!='train':reason='new_heldout_opposes_frozen_c56_train'
        if reason:roles[k]='excluded_leak';exclusions.append({'key':k,'other':other,'provisional_role':a,'other_role':b,'reason':reason})
    heldout={'dev','eval','eval_ood'};leaks=[]
    for k,r in roles.items():
        tag,side=k.rsplit('|',1);other=tag+'|'+('opponent' if side=='team' else 'team')
        if r=='train' and roles.get(other) in heldout:leaks.append([k,other])
    assert not leaks and all(roles[k]==v for k,v in before.items()) and sha(oldpath)==oldsha
    # v1 stays immutable, including perspectives no longer eligible for v2 actor scope.
    old3m=[key(r) for r in oldrows if 'three-musketeers' in r['own_base']+r['opponent_base']]
    write(DATA/'index/c56-v2-metadata.json',{'v1_roles_sha256':oldsha,'actor_excluded_3m_keys':old3m,'flagged':{key(r):{'battle_healer':'battle-healer' in r['own_base']+r['opponent_base'],'mirror':'mirror' in r['own_base']+r['opponent_base']} for r in oldrows if set(r['own_base']+r['opponent_base'])&{'battle-healer','mirror'}}})
    result={'schema':'clasher.s122-human-roles.v2','rules':__doc__,'parameters':old['parameters'],
            'v1_sha256':oldsha,'index_sha256':sha(DATA/'index/perspectives.jsonl.gz'),
            'counts':dict(collections.Counter(roles.values())),'new_counts':dict(collections.Counter(roles[key(r)] for r in rows)),
            'v1_counts':old['counts'],'v1_assignments_unchanged':True,'families':len(leaders),
            'ood_families':[list(x) for x in old['ood_families']]+[list(x) for x in newood],
            'new_ood_families':[list(x) for x in newood],'new_ood_family_sizes':[family_size[x] for x in newood],
            'roles':dict(sorted(roles.items())),'family':family,
            'v2_actor_ineligible_frozen_c56_keys':old3m,'leak_exclusions':len(exclusions)}
    out=DATA/'roles/s122_roles_v2.json';write(out,result)
    write(DATA/'receipts/T9-leak-check.json',{'v1_assignments_unchanged':True,'v1_sha256':oldsha,'v1_perspectives':len(before),'new_perspectives':len(rows),'cross_version_matches':sum((r['tag']+'|'+('opponent' if r['side']=='team' else 'team')) in before for r in rows),'train_heldout_match_violations':len(leaks),'new_exclusions_by_reason':dict(collections.Counter(x['reason'] for x in exclusions)),'exclusions':exclusions,'frozen_c56_v2_actor_ineligible_3m':len(old3m)})
    payloads=json.loads((DATA/'receipts/T9-payloads.json').read_text());newcards=payloads['new_own_cards']
    ranked=sorted(rows,key=lambda r:(h('s122-qa-v1:'+key(r)),key(r)))
    bycard={c:[r for r in ranked if r['own_plays_by_card'].get(c,0)>0] for c in newcards}
    selected={};coverage=collections.Counter()
    for c in sorted(newcards,key=lambda c:(len(bycard[c]),c)):
        for r in bycard[c]:
            if coverage[c]>=3:break
            if key(r) in selected:continue
            selected[key(r)]=r;coverage.update(card for card in newcards if r['own_plays_by_card'].get(card,0)>0)
    for r in ranked:
        if len(selected)>=400:break
        if key(r) not in selected:selected[key(r)]=r
    assert len(selected)==400
    coverage=collections.Counter(c for r in selected.values() for c in newcards if r['own_plays_by_card'].get(c,0)>0)
    assert all(coverage[c]>=3 for c in newcards)
    sample=sorted(selected.values(),key=lambda r:(r['shard'],r['match_index'],r['seat']))
    deterministic=sorted(sample,key=lambda r:(h('s122-determinism-v1:'+key(r)),key(r)))[:6]
    write(DATA/'qa/s122-sample.json',{'schema':'clasher.s122-qa-sample.v1','selection':'outcome-blind salted hash, rare-card-first >=3 actual-play perspectives, then hash-fill to 400','sample':sample,'determinism_keys':[key(r) for r in deterministic],'played_card_coverage':dict(coverage),'bars':{'overall_placement_acceptance_min':.99,'per_new_card_acceptance_min':.95,'illegal_labels':0,'determinism_perspectives':6,'truth_audit_violations':0,'production_error_fraction_strict_max':.005}})
    write(DATA/'receipts/T9-PASS.json',{'status':'PASS','perspectives':len(rows),'roles_total':len(roles),'role_counts':result['counts'],'new_role_counts':result['new_counts'],'v1_assignments_unchanged':True,'v1_sha256':oldsha,'roles_v2_sha256':sha(out),'new_ood_families':len(newood),'new_ood_perspectives_before_leak_exclusion':covered,'leak_violations':0,'new_leak_exclusions':len(exclusions),'c56_3m_actor_ineligible':len(old3m),'qa_sample_sha256':sha(DATA/'qa/s122-sample.json'),'qa_sample_perspectives':400,'new_cards_covered':len(coverage)})
    print((DATA/'receipts/T9-PASS.json').read_text(),flush=True)
if __name__=='__main__':main()
