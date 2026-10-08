"""Synthetic pinned-base union planning; no media or real source reads."""
from copy import deepcopy
import json
from cache_extension_v4 import extension,disjoint_extension,SPLIT_SHA


def main():
    checks=0
    def check(v):
        nonlocal checks
        assert v;checks+=1
    def inventory(ids):
        return dict(matches=len(ids),episodes=ids,receipt_sha256={ep:'a'*64 for ep in ids},heldout_payloads_opened=False)
    old=inventory(['v4-phase-a-1','v4-phase-a-2']);now=inventory(old['episodes']+['v4-phase-a-3'])
    base=dict(complete_for_snapshot=True,formal_population_seal=False,heldout_payloads_opened=False,
        split_sha256=SPLIT_SHA,source_snapshot_sha256='b'*64,matches=2,index_sha256={ep:'c'*64 for ep in old['episodes']},
        files_verified=4,equality_mismatches=0,equality_checked=2)
    result=extension(now,base,old,'b'*64)
    check(result['episodes']==['v4-phase-a-3'] and result['current_matches']==3)
    check(result['complete_population'] is False and result['heldout_payloads_opened'] is False)
    check(extension(old,base,old,'b'*64)['matches']==0)
    def reject(n,b,o=old,digest='b'*64):
        nonlocal checks
        try:extension(n,b,o,digest)
        except ValueError:checks+=1
        else:raise AssertionError('Invalid plan accepted')
    for key,value in [('complete_for_snapshot',False),('formal_population_seal',True),
        ('heldout_payloads_opened',True),('split_sha256','x'),('source_snapshot_sha256','x'),
        ('matches',1),('files_verified',2),('equality_mismatches',1),('equality_checked',0),('index_sha256',{})]:
        bad=deepcopy(base);bad[key]=value;reject(now,bad)
    bad=deepcopy(now);bad['receipt_sha256']['v4-phase-a-1']='d'*64;reject(bad,base)
    reject(inventory(['v4-phase-a-1']),base)
    bad=deepcopy(now);bad['episodes'].append(bad['episodes'][0]);reject(bad,base)
    bad=deepcopy(now);bad['heldout_payloads_opened']=True;reject(bad,base)
    third=inventory(['v4-phase-a-3']);third_base=deepcopy(base)
    third_base.update(matches=1,index_sha256={'v4-phase-a-3':'c'*64},files_verified=2,equality_checked=1)
    bases=[(base,old,'b'*64),(third_base,third,'b'*64)]
    check(disjoint_extension(now,bases)['matches']==0)
    newer=inventory(now['episodes']+['v4-phase-a-4'])
    check(disjoint_extension(newer,bases)['episodes']==['v4-phase-a-4'])
    for bad_bases in ([],bases+bases[:1],[(third_base,third,'x')]):
        try:disjoint_extension(newer,bad_bases)
        except ValueError:checks+=1
        else:raise AssertionError('Invalid disjoint bases accepted')
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)),flush=True)


if __name__=='__main__':main()
