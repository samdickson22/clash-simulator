"""Synthetic support-boundary/count-integrity and tie-break regressions."""
from copy import deepcopy
import json
from card_thresholds_v4 import select_card_thresholds


def main():
    checks = 0
    def check(v):
        nonlocal checks
        assert v
        checks += 1
    def rejected(rows):
        nonlocal checks
        try: select_card_thresholds(rows, global_threshold=.6)
        except ValueError: checks += 1
        else: raise AssertionError('Invalid sweep accepted')
    def total(rows):
        return {k:sum(r[k] for r in rows) for k in ('truth','predictions','matched')}
    sweep = []
    for i in range(1,10):
        entries = [dict(card='Knight',side=s,truth=5,predictions=5,matched=2) for s in (0,1)]
        entries.append(dict(card='Archers',side=0,truth=9,predictions=9,matched=3))
        if i == 4:
            for r in entries[:2]:r.update(predictions=10,matched=3)  # F1 equal, precision lower.
        if i == 1:entries.append(dict(card='Ghost',side=1,truth=0,predictions=1,matched=0))
        sweep.append(dict(schema='clasher.v4.validation-score.v1',epoch=3,threshold=i/10,body_threshold=.5,
            replay_mode='grid',event_thresholds={'default':i/10},
            heldout_payloads_opened=False,selection_seal=False,readiness={'fixture':True},
            validation_receipts={'ep':'fixture'},truth_payloads={'ep':'fixture'},sources={'scorer':'fixture'},
            point=dict(timing='point',per_card_side=entries,all_sides=total(entries),
                       opponent=total([r for r in entries if r['side']==0]))))
    r=select_card_thresholds(sweep,global_threshold=.6)
    check(r['body_threshold']==.5)
    check(r['thresholds']=={'default':.6,'Knight':.9})
    check(r['support']['Knight']['validation_events']==10)
    check(r['support']['Archers']['validation_events']==9 and r['support']['Archers']['fit']=='global')
    check(r['support']['Ghost']['validation_events']==0 and r['support']['Ghost']['threshold']==.6)
    check(r['selection_seal'] is False and r['heldout_opening_authorized'] is False)
    check(select_card_thresholds(list(reversed(sweep)),global_threshold=.6)==r)
    rejected(sweep[:8])
    for path,value in [(['epoch'],4),(['threshold'],.55),(['heldout_payloads_opened'],True),
                       (['replay_mode'],'combined'),(['event_thresholds'],{'default':.1,'Knight':.8}),
                       (['body_threshold'],.7),(['body_threshold'],None),(['body_threshold'],True),
                       (['readiness'],{'fixture':'other'}),(['point','timing'],'conservative'),
                       (['point','all_sides','matched'],0)]:
        bad=deepcopy(sweep);row=bad[0]
        for key in path[:-1]:row=row[key]
        row[path[-1]]=value;rejected(bad)
    bad=deepcopy(sweep);bad[0]['point']['per_card_side'].append(deepcopy(bad[0]['point']['per_card_side'][0]));rejected(bad)
    bad=deepcopy(sweep)
    for row in bad:row['body_threshold']=.55
    rejected(bad)
    bad=deepcopy(sweep);bad[0]['point']['per_card_side'][0]['matched']=True;rejected(bad)
    bad=deepcopy(sweep);bad[0]['point']['per_card_side'][0]['card']='default';rejected(bad)
    bad=deepcopy(sweep);bad[0]['point']['per_card_side'][0]['truth']+=1
    bad[0]['point']['all_sides']['truth']+=1;bad[0]['point']['opponent']['truth']+=1;rejected(bad)
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)),flush=True)


if __name__ == '__main__':main()
