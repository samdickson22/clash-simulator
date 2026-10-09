"""Reduce coexistence timing and step-throughput evidence on a home CPU."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root
run=root/'coexistence-v2';receipt=json.loads((run/'coexistence.json').read_text());control=np.array(receipt['baseline'][1:]);treated=np.array(receipt['treatment'][1:]);assert len(control)>=10 and len(treated)>=10
harmonic=lambda x:len(x)/np.sum(1/x)
rng=np.random.default_rng(8091009)
def block_sample(xs):
    starts=rng.integers(len(xs),size=(len(xs)+2)//3)
    return xs[(starts[:,None]+np.arange(3))%len(xs)].ravel()[:len(xs)]
ratios=np.array([harmonic(block_sample(treated))/harmonic(block_sample(control)) for _ in range(5000)])
ratio=float(harmonic(treated)/harmonic(control));ci=np.quantile(ratios,[.025,.975]).tolist();guards=[];lat=[];raw=[];cpu=[];games=[];pauses=0.;schedulers=set()
for batch in sorted(run.glob('batch*')):
    clock=json.loads((batch/'pause-clock.json').read_text());pauses+=clock['paused_total_seconds']
    for line in (batch/'gpu-guard.jsonl').read_text().splitlines():
        e=json.loads(line);guards.append(e)
        assert not set(e['affinity'])&set(e['excluded_cpus'])
    for path in (batch/'games').glob('*.json'):
        row=json.loads(path.read_text());ab=row['search_ab'];assert ab['latency_clock']=='active_wall' and ab['full_decision_latency']
        games.append(row);lat.extend(ab['latency_seconds']);raw.extend(ab['raw_wall_latency_seconds']);cpu.extend(ab['cpu_latency_seconds'])
    if (batch/'receipt.json').exists():schedulers.add(json.loads((batch/'receipt.json').read_text()).get('scheduler','unknown'))
assert schedulers == {5}, 'completed shards must use SCHED_IDLE'
assert guards and games
parity=json.loads((root/'receipts/pause-parity.json').read_text());assert parity['matched']
report=f"On 127x08, 15 minutes without exploration sims followed by 15 minutes with 16 SCHED_IDLE sims, pinned away from observed active GPU-job cores and SMT siblings. Fresh GRU step throughput: {harmonic(control):.2f}→{harmonic(treated):.2f} rows/s, change {(ratio-1)*100:+.2f}%, 95% moving-block bootstrap ratio CI [{ci[0]:.4f}, {ci[1]:.4f}] ({len(control)}/{len(treated)} complete steps, boundary-crossing first steps excluded). "+('The measured reduction stays within 5% and the pointwise interval excludes a 5% drop.' if ratio>=.95 and ci[0]>.95 else 'This sample does not rule out a 5% throughput drop; no throughput guarantee is established.')+f" Guard-paused samples: {sum(g['paused'] for g in guards)}/{len(guards)}; completed qualification games: {len(games)}. Fixed-work action SHA256 and winners match in all 4 arms with three forced pauses and permuted LPT dispatch. Legacy primary wall timings remain raw; new full-decision telemetry excludes external pauses, while guarded optional decision deadlines use process CPU time. CPU deadlines do not guarantee a 200 ms wall bound. Short background rsync collections continued in both phases; no delay-fixes simulations or reductions ran on 08."
result=dict(first_ten_minutes=json.loads((root/'receipts/coexistence-throughput-10min.json').read_text()),qualification_source_sha256=json.loads((root/'receipts/qualification-source.json').read_text()),runtime=json.loads((root/'receipts/qualification-runtime.json').read_text()),background_io='Five delay-fixes leased lanes periodically rsync reduced completed game JSON to08 during both phases; no delay-fixes simulations or reductions on08.',exploration=True,report_text=report,host=receipt['host'],start_utc=receipt['start_utc'],end_utc=receipt['end_utc'],period_seconds=receipt['period_seconds'],workers=16,metric=receipt['metric'],boundary_steps_excluded=True,baseline_rate=float(harmonic(control)),treatment_rate=float(harmonic(treated)),ratio=ratio,ratio_ci95=ci,bootstrap=dict(reps=5000,block_steps=3,seed=8091009,unit='independently resampled sequential phase steps; not paired treatment games'),baseline_steps=len(control),treatment_steps=len(treated),baseline_rates=control.tolist(),treatment_rates=treated.tolist(),guard_samples=len(guards),paused_samples=sum(g['paused'] for g in guards),completed_pause_seconds=pauses,completed_games=len(games),scheduler='SCHED_IDLE',own_gpu_affinity_overlap_samples=0,action_parity=parity,latency=dict(decisions=len(lat),active_wall_p95=float(np.quantile(lat,.95)),raw_wall_p95=float(np.quantile(raw,.95)),cpu_p95=float(np.quantile(cpu,.95)),active_wall_over200=sum(v>.2 for v in lat),raw_wall_over200=sum(v>.2 for v in raw),raw_minus_active_seconds=float(sum(raw)-sum(lat))),source_sha256={str(path.relative_to(root.parents[2])):hashlib.sha256(path.read_bytes()).hexdigest() for path in [root/'gpu_guard.py',root/'worker_runtime.py',root/'home_worker.py',root/'lease_worker.py',root.parents[2]/'src/clasher/analysis/loss_review/throughput_guard.py']})
(root/'receipts/coexistence-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(report)
