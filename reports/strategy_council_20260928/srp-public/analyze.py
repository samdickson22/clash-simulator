"""OQ matchup bootstrap, prespecified primary bars and descriptive comparisons."""
import json
import tomllib
from collections import defaultdict
from pathlib import Path
from statistics import summarise, boot

HERE = Path(__file__).resolve().parent


def key(record):
    s = record['spec']
    return s['role'],s['opponent'],s['seed'],s['game']


def main():
    config = tomllib.loads((HERE/'config.toml').read_text())
    references = {key(r):r for p in (HERE.parent/'oracle-qualification/games/srp_xm_c256').glob('*.json')
                  if not p.name.endswith('.error.json') for r in [json.loads(p.read_text())]}
    result = {}
    for player in config['players']:
        records = {key(r):r for p in (HERE/'games'/player['name']).glob('*.json') for r in [json.loads(p.read_text())]}
        res = {}
        for group in config['groups']:
            cells = {}
            for cell in group['cells']:
                prefix=[]
                for g in range(cell['games']):
                    k=(group['role'],cell['opponent'],cell['seed'],g)
                    if k not in records:
                        break
                    prefix.append(records[k])
                cells[cell['opponent']] = prefix[:len(prefix)//2*2]
            complete = all(len(cells[c['opponent']]) == c['games'] for c in group['cells'])
            if not complete and len(cells)>1:
                n = min(map(len,cells.values()))
                cells = {k:v[:n] for k,v in cells.items()}
            pooled = sum(cells.values(), [])
            if not pooled:
                res[group['name']] = dict(complete=False,n=0)
                continue
            block = dict(complete=complete,pooled=summarise(pooled),cells={k:summarise(v) for k,v in cells.items()})
            if group['name']=='holdout':
                p,d=block['pooled'],block['cells']['defense']
                block['verdict']='PASS' if complete and all(x['score']>=.55 and x['score_boot95'][0]>.5 for x in (p,d)) else 'FAIL' if complete else 'INCOMPLETE'
            if group['name'] in ('holdout','hog26'):
                diffs=defaultdict(list)
                for rec in pooled:
                    if key(rec) in references:
                        diffs[(rec['spec']['opponent'],rec['matchup_seed'])].append(rec['score']-references[key(rec)]['score'])
                clusters=[v for v in diffs.values() if len(v)==2]
                if clusters:
                    flat=sum(clusters,[])
                    block['paired_vs_privileged']=dict(n=len(flat),difference=sum(flat)/len(flat),ci95=boot(clusters))
            block['timing']=dict(wall_max=max(r['decision_wall_max'] for r in pooled),
                cpu_max=max(r['decision_cpu_max'] for r in pooled),
                wall_over_250ms=sum(r['wall_over_250ms'] for r in pooled),
                cpu_over_250ms=sum(r['cpu_over_250ms'] for r in pooled),
                decisions=sum(r['decisions'] for r in pooled))
            count=sum(r['decisions'] for r in pooled)
            block['derived_public_state']=dict(
                decisions=count,
                hand_determined=sum(r['hand_determined_decisions'] for r in pooled),
                hand_determined_fraction=sum(r['hand_determined_decisions'] for r in pooled)/count,
                cycle_determined=sum(r['cycle_determined_decisions'] for r in pooled),
                cycle_determined_fraction=sum(r['cycle_determined_decisions'] for r in pooled)/count,
                elixir_estimate_fallbacks=sum(r['elixir_estimate_fallbacks'] for r in pooled))
            res[group['name']]=block
        result[player['name']]=res
    (HERE/'results/summary.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
