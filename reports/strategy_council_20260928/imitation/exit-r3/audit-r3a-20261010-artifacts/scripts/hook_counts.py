"""Verify every student fallback/proposer call is accounted for (no skipping/precompute)."""
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);bad=[];tot=dict(stu_fb=0,stu_prop=0,polls=0,search=0,opp_fb=0,opp_polls=0,max_min_offset=0)
for arm in ('K0','R3a'):
    for i in range(600):
        r=json.loads((root/f'fallback-{arm}-{i:04d}.json').read_text());c=r['checks'];s=r['stats'];me=s[r['seat']];op=s[1-r['seat']]
        allpolls=me['polls']+op['polls'];allsearch=len(me['deadlines'])+len(op['deadlines'])
        ok=c['fallback_calls']==allpolls and c['proposer_calls']==allsearch
        if arm=='R3a':
            ok&=c['student_fallback_calls']==me['polls'] and c['student_proposer_calls']==len(me['deadlines'])
            tot['stu_fb']+=c['student_fallback_calls'];tot['stu_prop']+=c['student_proposer_calls'];tot['polls']+=me['polls'];tot['search']+=len(me['deadlines'])
        else: ok&=c['student_fallback_calls']==0
        ok&=len(me['proposer_seconds'])==len(me['deadlines'])
        tot['max_min_offset']=max(tot['max_min_offset'],c['min_timer_offset_seconds'])
        if not ok:bad.append((arm,i))
print(json.dumps(dict(mismatches=bad[:10],n_mismatch=len(bad),**tot),indent=1))
