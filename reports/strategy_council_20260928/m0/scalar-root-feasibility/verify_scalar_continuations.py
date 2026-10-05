"""Independent stored-result/grid/trace audit; performs no battle replay."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,hashlib,itertools,json,math

BASE=Path(__file__).resolve().parent
OUT=BASE/'continuations-seed-260928903'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    plan=json.loads((OUT/'study-plan.json').read_text())
    summary=json.loads((OUT/'summary.json').read_text())
    for name,expected in (plan['source_pins']|plan['input_pins']).items():
        assert sha(name)==expected,name
    plan_sha=sha(OUT/'study-plan.json')
    by_class={role:{'branches':0,'score_sum':0.,'margin_sum':0.,'best_family_exposures':0,'informative_nonwait_pair_family_exposures':0} for role in plan['roles']}
    per_card=defaultdict(lambda:{'families':0,'nonwait_informative':0,'score_separated':0,'margin_separated':0})
    families=[];terminal_ticks=[];decision_count=0;branch_count=0
    for row in plan['selected_requests']:
        request,selection=row['request'],row['selection'];family=request['family_id'];matrix={}
        for index,condition in enumerate(plan['conditions']):
            for candidate in selection['candidates']:
                role=candidate['role'];folder=OUT/family/f'condition-{index}-{role}'
                claim=json.loads((folder/'claim.json').read_text());result=json.loads((folder/'result.json').read_text())
                assert result['status']=='complete' and result['terminal'] is True
                assert claim==result['claim']
                assert claim['study_plan_sha256']==plan_sha
                assert claim['candidate']==candidate and claim['condition']==condition
                assert claim['root_public_sha256']==selection['public_packet_sha256']
                assert result['decisions_sha256']==sha(folder/'decisions.jsonl.gz')
                assert result['starting_owner_crown_hp']==10928
                expected_score=.5 if result['winner'] in (None,-1) else float(result['winner']==request['root_owner'])
                assert result['score']==expected_score
                expected_margin=(result['own_remaining_hp']-result['enemy_remaining_hp'])/10928
                assert result['normalized_hp_margin']==expected_margin and math.isfinite(expected_margin)
                for name in ('own_remaining_hp','enemy_remaining_hp'):assert 0<=result[name]<=10928
                with gzip.open(folder/'decisions.jsonl.gz','rt') as stream:
                    ticks=[]
                    for line in stream:
                        entry=json.loads(line);ticks.append(entry['tick'])
                        if len(ticks)==1:
                            assert entry['tick']==selection['root_tick']
                            assert entry['actions'][request['root_owner']]==candidate['action_id']
                            assert entry['public_sha256'][request['root_owner']]==selection['public_packet_sha256']
                        assert len(entry['actions'])==2 and all(type(a)is int and 0<=a<=2304 for a in entry['actions'])
                assert ticks==list(range(selection['root_tick'],ticks[-1]+1,5))
                assert len(ticks)==result['decision_boundaries']
                assert ticks[-1]<result['terminal_tick']<=min(ticks[-1]+5,6001)
                decision_count+=len(ticks);terminal_ticks.append(result['terminal_tick']);branch_count+=1
                matrix[condition,role]=result
                bucket=by_class[role];bucket['branches']+=1;bucket['score_sum']+=result['score'];bucket['margin_sum']+=expected_margin
        means={role:(sum(matrix[c,role]['score'] for c in plan['conditions'])/4,
                     sum(matrix[c,role]['normalized_hp_margin'] for c in plan['conditions'])/4) for role in plan['roles']}
        pairs=[]
        for a,b in itertools.combinations([r for r in plan['roles'] if r!='wait'],2):
            ds=abs(means[a][0]-means[b][0]);dm=abs(means[a][1]-means[b][1])
            pairs.append({'roles':[a,b],'mean_score_difference':ds,'mean_margin_difference':dm,'informative':ds>0 or dm>.01})
        score_separated=any(p['mean_score_difference']>0 for p in pairs)
        margin_separated=any(p['mean_margin_difference']>.01 for p in pairs)
        informative=score_separated or margin_separated
        reported=next(f for f in summary['families'] if f['family_id']==family)
        assert reported['complete'] and reported['scalar_nonwait_informative']==informative
        for role,value in means.items():assert reported['means'][role]=={'score':value[0],'normalized_hp_margin':value[1]}
        best=max(means.values())
        for role in plan['roles']:
            by_class[role]['best_family_exposures']+=int(means[role]==best)
            by_class[role]['informative_nonwait_pair_family_exposures']+=int(any(role in p['roles'] and p['informative'] for p in pairs))
        bucket=per_card[request['focal_card']];bucket['families']+=1;bucket['nonwait_informative']+=int(informative);bucket['score_separated']+=int(score_separated);bucket['margin_separated']+=int(margin_separated)
        families.append({'family_id':family,'focal_card':request['focal_card'],'score_separated':score_separated,'margin_separated':margin_separated,'nonwait_informative':informative,'nonwait_pairs':pairs})
    assert branch_count==512 and len(families)==32 and not summary['failures']
    assert sum(f['nonwait_informative'] for f in families)==summary['scalar_nonwait_informative_families']
    for bucket in by_class.values():
        bucket['mean_score']=bucket.pop('score_sum')/bucket['branches'];bucket['mean_normalized_hp_margin']=bucket.pop('margin_sum')/bucket['branches']
    current={str(p.resolve()):sha(p) for p in Path('src/clasher').rglob('*.py')}
    old=plan['broad_source_snapshot']
    unrelated={'added':sorted(set(current)-set(old)),'removed':sorted(set(old)-set(current)),
               'modified':sorted(name for name in set(current)&set(old) if current[name]!=old[name] and name not in plan['source_pins'])}
    result={'evidence_role':'opened_scalar_development','verification_script_sha256':sha(__file__),
            'plan_sha256':plan_sha,'branches_verified':branch_count,'families_verified':32,'failures':0,
            'decision_boundaries_verified':decision_count,'terminal_tick_range':[min(terminal_ticks),max(terminal_ticks)],
            'scalar_nonwait_informative_families':sum(f['nonwait_informative'] for f in families),
            'score_separated_families':sum(f['score_separated'] for f in families),'margin_separated_families':sum(f['margin_separated'] for f in families),
            'margin_threshold':.01,'per_focal_card':dict(per_card),'per_class':by_class,'families':families,
            'actual_dependency_pins_unchanged':True,'unrelated_source_drift':unrelated,'native_admission':False,'new_branches_executed':0}
    with (OUT/'independent-verification.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='families'},indent=2))


if __name__=='__main__':main()
