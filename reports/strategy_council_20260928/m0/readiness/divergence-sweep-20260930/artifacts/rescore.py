import json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,'/Users/sam/Desktop/code/clasher/src')
from clasher.rl.readiness_capture_ownership import BranchClaim, RootSeal
from clasher.rl.training_readiness_v2 import Branch, evaluate
L=Path('/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/readiness-v2.sqlite')
db=sqlite3.connect(L.resolve().as_uri()+'?mode=ro',uri=True); db.execute('PRAGMA query_only=ON')
idx=json.load(open('/tmp/dsweep/index.json'))
out={}
for v in (4,5,6):
    aid=f'm0-tier-a-fresh-v{v}'
    seal=RootSeal.model_validate_json(db.execute('SELECT record FROM root_seals WHERE attempt_id=?',(aid,)).fetchone()[0])
    rows=db.execute('SELECT c.record, r.branch FROM branch_claims c LEFT JOIN branch_results r ON c.nonce=r.nonce WHERE c.attempt_id=?',(aid,)).fetchall()
    sim={(p['famid'],p['role'],p['cond']):p['sj'] for p in idx[str(v)]}
    rec=[];new=[];changed=0
    for rc,rb in rows:
        if rb is None: continue
        b=Branch.model_validate_json(rb); rec.append(b)
        if b.engine=='scalar':
            sj=sim.get((b.family_id,b.candidate_role,b.condition))
            if sj is None: new.append(b); continue
            n='v%d-%05d'%(v,sj)
            f=Path(f'/tmp/dsweep/runs/final/{n}/summary.json')
            if not f.exists(): f=Path(f'/tmp/dsweep/runs/pre/{n}/summary.json')
            s=json.loads(f.read_text())
            nb=b.model_copy(update=dict(score=s['score'],own_remaining_hp=s['own'],enemy_remaining_hp=s['en']))
            changed+=(nb.score,nb.own_remaining_hp,nb.enemy_remaining_hp)!=(b.score,b.own_remaining_hp,b.enemy_remaining_hp)
            new.append(nb)
        else: new.append(b)
    # dedupe (keep last per key) like ledger semantics
    def dd(bs):
        d={}
        for b in bs: d[(b.family_id,b.candidate_role,b.condition,b.engine)]=b
        return tuple(d.values())
    R0=evaluate(seal.protocol,dd(rec)); R1=evaluate(seal.protocol,dd(new))
    def summ(R):
        fams=[dict(f=f.family_id[-2:],mat=f.material_failure,above=list(f.above_floor_classes),rep=list(f.repeatable_classes),pref=list(f.scalar_preferred),comp=f.reference_comparator,sr=round(f.score_regret,4),mr=round(f.margin_regret,4),complete=f.complete) for f in R.families]
        return dict(status=R.status,material=R.material_failures,informative=R.informative_families,events=R.class_events,exposures=R.class_exposures,insufficient=list(R.insufficient_class_coverage),reasons=list(R.reasons),flagged=[x for x in fams if x['mat'] or x['above'] or x['rep'] or not x['complete']])
    out[v]=dict(changed_scalar=changed,recorded=summ(R0),rescored=summ(R1))
    print(v,'changed scalar branches',changed)
    for k in ('recorded','rescored'):
        s=out[v][k]; print(' ',k,s['status'],'mat',s['material'],'inf',s['informative'],'events',s['events'],'insuff',s['insufficient'],s['reasons'])
        for x in s['flagged']: print('    ',x)
json.dump(out,open('/tmp/dsweep/rescore/rescore.json','w'),indent=1,default=str)
