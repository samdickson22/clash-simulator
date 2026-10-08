"""Complete-only paired inference; outcome access begins after receipt barrier."""
from pathlib import Path
import hashlib,json,time
import numpy as np
from cells import CELLS
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 manifest=sha(HERE/'evaluation-manifest.json');schedule=json.loads((HERE/'schedule.json').read_text())
 expected=[(ep,c,s) for ep in schedule['pairs'] for c in CELLS for s in (0,1)]
 paths=sorted((HERE/'confirmation').glob('*.json'));assert len(paths)==len(expected)==1792
 status=HERE/'collected-status'
 for host in ('127x04','127x08'):assert (status/f'supervisor-{host}.exit').read_text().strip()=='0'
 for i in range(152):
  assert (status/f'worker-{i}.exit').read_text().strip()=='0'
  d=json.loads((status/f'worker-{i}-done.json').read_text());assert d['complete'] and d['manifest']==manifest
 rows=[];aggregate=hashlib.sha256()
 for index,(p,(ep,c,s)) in enumerate(zip(paths,expected)):
  row=json.loads(p.read_text());assert row['job']==index and row['manifest']==manifest and row['terminal']
  for k,v in [('pair',ep['pair']),('seed',ep['seed']),('noise_seed',ep['noise_seed']),('variant',c),('seat',s)]:assert row[k]==v
  aggregate.update(p.name.encode()+bytes.fromhex(sha(p)));rows.append(row)
 # All identity and process receipts exist and pass before any score is accessed.
 rng=np.random.default_rng(9731100003);indices=rng.integers(0,128,size=(10000,128))
 values={c:np.array([np.mean([r['score'] for r in rows if r['variant']==c and r['pair']==i]) for i in range(128)]) for c in CELLS}
 def ci(x):return dict(point=float(np.mean(x)),ci95=np.quantile(x[indices].mean(1),[.025,.975]).tolist())
 scores={c:ci(v) for c,v in values.items()}
 contrasts={name:ci(values[a]-values[b]) for name,a,b in [('primary','T2-N90','Full-N90'),('secondary','T2-N97','Full-N97'),('ceiling_gap','R-derived','T2-N97')]}
 for k in ('primary','secondary'):contrasts[k]['pass']=contrasts[k]['ci95'][0]>0
 diagnostics={}
 for c in CELLS:
  games=[r for r in rows if r['variant']==c];traces=[(s,r) for r in games for s in r['elt_trace']]
  post=[]
  for s,r in traces:
   if any(0<=s['tick']-(e['truth_tick'] if e['kind']=='missed' else e['arrival_tick'])<=1200 for e in r['event_audit'] if e['kind'] in ('missed','spurious','confused')):post.append(s)
  n=len(traces);assert n
  hand90=[s for s,_ in traces if s.get('hand90') is not None]
  diagnostics[c]=dict(samples=n,coverage=float(np.mean([s['covered'] for s,_ in traces])),
   width=float(np.mean([s['interval'][1]-s['interval'][0] for s,_ in traces])),
   mae=float(np.mean([abs(s['elixir_mean']-s['truth_elixir']) for s,_ in traces])),
   post_error_samples=len(post),post_error_coverage=float(np.mean([s['covered'] for s in post])) if post else None,
   hand90_fraction=len(hand90)/n,hand90_accuracy=float(np.mean([s['hand90_correct'] for s in hand90])) if hand90 else None,
   unanimity_fraction=float(np.mean([s['hand_concentrated'] for s,_ in traces])),
   hypothesis90_fraction=float(np.mean([s['hypothesis_concentrated'] for s,_ in traces])),
   cpu_hours=sum(r['cpu_seconds'] for r in games)/3600,mean_decision_p50=float(np.mean([r['timing']['p50'] for r in games])),
   rejected=sum(r['rejected'][0] for r in games),perception={k:sum(r['perception'].get(k,0) for r in games) for k in set().union(*(r['perception'] for r in games))})
 for c,anchor in [('T2-N97','Full-N97'),('T2-N90','Full-N90')]:
  d=diagnostics[c];d['calibration_pass']=d['coverage']>=.88 and d['post_error_coverage']>=.8;d['sharpness_pass']=d['width']<diagnostics[anchor]['width']
 result=dict(manifest=manifest,receipt_aggregate=aggregate.hexdigest(),games=len(rows),bootstrap_seed=9731100003,bootstrap_samples=10000,scores=scores,contrasts=contrasts,diagnostics=diagnostics,game_cpu_hours=sum(r['cpu_seconds'] for r in rows)/3600)
 (HERE/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 lines=['# S3 results','',f'Complete: {len(rows)} games. Paired-matchup bootstrap (10,000 draws; both seats retained).','', '| Cell | Score | 95% CI |','| --- | ---: | --- |']
 for c,d in scores.items():lines.append(f"| {c} | {100*d['point']:.1f}% | [{100*d['ci95'][0]:.1f}, {100*d['ci95'][1]:.1f}] |")
 lines+=['','## Registered contrasts','']
 for k,d in contrasts.items():lines.append(f"- {k}: {100*d['point']:+.1f} pp [{100*d['ci95'][0]:+.1f}, {100*d['ci95'][1]:+.1f}]"+(f"; {'PASS' if d['pass'] else 'FAIL'}" if 'pass' in d else ''))
 lines+=['','## Tracker diagnostics','','| Cell | Coverage | Post-error coverage | Width | MAE | Hand mass ≥90% | Unanimity |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
 for c,d in diagnostics.items():
  pe=f"{d['post_error_coverage']:.3f}" if d['post_error_coverage'] is not None else 'n/a'
  lines.append(f"| {c} | {d['coverage']:.3f} | {pe} | {d['width']:.3f} | {d['mae']:.3f} | {d['hand90_fraction']:.4f} | {d['unanimity_fraction']:.4f} |")
 lines+=['',f"Game CPU: {result['game_cpu_hours']:.2f} core-hours. Supervisor/worker, development and preflight accounting are reported separately in compute-audit.json.",'',f'Manifest: `{manifest}`. Receipt aggregate: `{aggregate.hexdigest()}`.','', 'Truth is scoring-only. T2 intervals use the calibration-split radius frozen before confirmation. Full/ELT anchors retain their original intervals. No outcome-based exclusions. T2-N64 is descriptive. Raw receipts stay on the fleet.']
 (HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(dict(complete=True,games=len(rows),manifest=manifest)),flush=True)
if __name__=='__main__':main()
