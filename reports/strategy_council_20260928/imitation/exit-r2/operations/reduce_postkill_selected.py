"""Only complete interleaved blocks contribute to S-default paired contrasts."""
import argparse
import json
from pathlib import Path
from imitation.exit_r1.rows import sha,write_json as original_write_json
from postkill_selected import labelled
def write_json(path,value):original_write_json(path,labelled(value))
from imitation.exit_r1.screen_metrics import paired_interval
from postkill_admission import BASE,SMOKE_BASE,arm_order
from postkill_selected import frozen,selection

def collect(j,arms,smoke=False):
    h=frozen(j);stage=j/('postkill-sdefault-smoke' if smoke else 'postkill-sdefault');values={a:[] for a in arms}
    indices=(4,5) if smoke else range(600)
    for i in indices:
        b=json.loads((stage/'blocks'/f'{i:04d}.json').read_text())
        assert b['never_adoptable'] and not b['adoption_eligible']
        assert b['selection_amendment_sha256']==sha(j/'postkill-selection-amendment.json')
        assert b['complete'] and b['smoke']==smoke and b['arms']==arms
        assert b['arm_order']==arm_order(arms,i) and b['harness_sha256']==sha(j/'postkill-sdefault-addendum.json')
        assert b['context']['host']=='127x01' and len(b['context']['affinity'])==1
        assert b['context']['scheduler']=='SCHED_OTHER' and b['context']['nice']==10
        assert len(b['cases'])==len(arms) and [r['arm'] for r in b['cases']]==b['arm_order']
        keys=[]
        for case in b['cases']:
            arm=case['arm'];path=stage/'cases'/f'sdefault-{arm}-{i:04d}.json'
            assert sha(path)==case['sha256'];r=json.loads(path.read_text())
            assert r['never_adoptable'] and not r['adoption_eligible'] and r['lane']=='exploration; never adoptable'
            assert r['selection_amendment_sha256']==sha(j/'postkill-selection-amendment.json')
            assert (r['mode'],r['arm'],r['index'],r['seed'],r['seat'],r['terminal'],r['smoke'])==(
                'sdefault',arm,i,(SMOKE_BASE if smoke else BASE)+i,i%2,True,smoke)
            assert r['freeze_sha256']==sha(j/'freeze.json') and r['harness_sha256']==sha(j/'postkill-sdefault-addendum.json')
            assert r['adapter_sha256']==sha(j/'ops/k_postkill_sdefault.py') and r['native_sha256']==h['native_sha256']
            assert r['threads']==1 and r['coarse_horizon']==160 and r['opponent']=='v1-policy'
            source='v1_polled' if arm=='C-v1' else ('K0_frozen' if arm=='K0' else 'student_argmax')
            assert r['default_source']==source and r['own_v1_poll']=='released v1'
            assert r['scheduler']==b['context']['scheduler'] and r['nice']==b['context']['nice']
            if not smoke and arm not in ('C-v1','K0'):
                off=json.loads((j/'offline'/f'{arm}.json').read_text())
                assert r['student_checkpoint_sha256']==off['checkpoint_sha256']
            assert r['search_ab']['worker_affinity']==b['context']['affinity'] and r['search_ab']['host'].split('.')[0]==b['context']['host']
            raw=stage/'k-raw'/arm/'games'/f'sim-{i:04d}-d27-{arm}.json'
            assert sha(raw)==r['raw_game_sha256'];raw_record=json.loads(raw.read_text())
            assert raw_record['never_adoptable'] and not raw_record['adoption_eligible']
            assert raw_record['metadata']['never_adoptable'] and not raw_record['metadata']['adoption_eligible']
            assert raw_record['selection_amendment_sha256']==sha(j/'postkill-selection-amendment.json')
            assert raw_record['metadata']['selection_amendment_sha256']==sha(j/'postkill-selection-amendment.json')
            for field in ('threads','coarse_horizon','default_source'):
                assert raw_record[field]==r[field] and raw_record['metadata'][field]==r[field]
            assert raw_record['metadata']['deadline_seconds']==.2 and raw_record['metadata']['return_reserve_seconds']==.008
            keys.append((r['seed'],r['seat'],r['own_deck'],r['opponent_deck']))
            if not smoke:
                assert r['loss'] in (0,1);values[arm].append(r['loss'])
            else:
                checks=json.loads((stage/f'checks-{arm}-{i:04d}.json').read_text())
                assert checks['timer_calls']>0 and checks['min_inference_offset_seconds']>=0
                if arm=='S-standin':assert checks['student_calls']>0
        assert all(key==keys[0] for key in keys),'Unpaired decks/seat/seed'
    return values

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--smoke',action='store_true')
    a=p.parse_args();assert not a.smoke, "Original frozen reducer owns smoke qualification";j=Path(a.job)
    chosen=['S-standin'] if a.smoke else selection(j);assert chosen
    arms=['C-v1']+chosen+['K0'];losses=collect(j,arms,a.smoke)
    if a.smoke:
        # Mechanics only. Do not read, report or reuse smoke losses.
        write_json(j/'postkill-wrapper-qualification.json',dict(passed=True,states=125,smoke_games=6,
            smoke_indices=[4,5],all_terminal=True,interleaved=True,
            inference_inside_K_wall0=True,v1_polling_both_actors=True,legal_default_and_proposals=True,
            harness_sha256=sha(j/'postkill-sdefault-addendum.json'),
            adapter_sha256=sha(j/'ops/k_postkill_sdefault.py'),
            synthetic_qualification_sha256=sha(j/'sdefault-qualification.json'),
            indices_excluded_from_reporting=True))
        return
    stage=j/'postkill-sdefault'
    for arm in chosen:
        contrast=paired_interval(losses[arm],losses['C-v1'],reps=5000,seed=80991010)
        anchor=paired_interval(losses[arm],losses['K0'],reps=5000,seed=80991010)
        write_json(stage/f'{arm}.json',dict(arm=arm,study='post-kill descriptive S-default',games=600,paired=contrast,
            descriptive_K0=anchor,absolute_losses={key:paired_interval(value,[0]*len(value),reps=5000,seed=80991010) for key,value in losses.items()},
            comparison='Full student package (hooks plus default) vs C-v1; does not separate hook/default effects.',
            interleaving='All arms of each seed, same host/core/class, back-to-back deterministic rotated block',
            lane='exploration; never adoptable; no multiplicity adjustment',harness_sha256=sha(j/'postkill-sdefault-addendum.json')))

if __name__=='__main__':main()
