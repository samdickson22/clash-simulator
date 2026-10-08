"""Completion-only operational accounting; never changes frozen analysis or result.json."""
import collections,hashlib,json,re,statistics,time
from pathlib import Path
from collect_r2e import HERE,OPS,MANIFEST,verified,validate,write,mirror

verified()
monitor=json.loads((OPS/'migration-monitor-r2e.json').read_text())
assert monitor['complete_only_ready'] and monitor['analysis_complete']
assert monitor['valid_terminal_receipts']==4992 and monitor['successful_collected_partitions']==248
result=json.loads((HERE/'result.json').read_text())
assert result['complete'] and result['games']==4992 and result['manifest']==MANIFEST
rows=[validate(p) for p in sorted((HERE/'confirmation').glob('*.json'))]
assert len(rows)==4992
result_sha=hashlib.sha256((HERE/'result.json').read_bytes()).hexdigest()
pat=r'^(?:User time \(seconds\)|System time \(seconds\)):\s*([0-9.]+)'
def log_cpu(paths):
    return sum(sum(float(v) for v in re.findall(pat,p.read_text(),re.M)) for p in paths)/3600
original_failed=list((OPS/'original-04-r2').glob('s1-confirm-*-r2.log'))
original_failed=[p for p in original_failed if re.fullmatch(r's1-confirm-\d+-r2.log',p.name)]
assert len(original_failed)==48
success=list((HERE/'collected-status').glob('worker-*.log'));assert len(success)==248
failed_cpu=log_cpu(original_failed);success_cpu=log_cpu(success)
node_logs=list((OPS/'attempt-supervisor-logs-r2e').glob('s1-confirm-node-*.log'))
assert len(node_logs)==5
node_cpu=sum(sum(float(v) for v in re.findall(r'^\s*(?:User time \(seconds\)|System time \(seconds\)):\s*([0-9.]+)',p.read_text(),re.M)) for p in node_logs)/3600
warmup_cpu=node_cpu-failed_cpu-success_cpu
assert warmup_cpu>=-0.001
qual=json.loads((OPS/'receipt-qualification-127x04-r2e.json').read_text())
quarantine=json.loads((OPS/'quarantine-r2e.json').read_text())
assert quarantine['mismatches']==0
timings={}
for mode in ('scripts','head-to-head'):
    timings[mode]={}
    for cell in sorted({r['variant'] for r in rows if r['mode']==mode}):
        selected=[r['timing'] for r in rows if r['mode']==mode and r['variant']==cell]
        timings[mode][cell]=dict(games=len(selected),decisions=sum(t['decisions'] for t in selected),
            over_250ms=sum(t['overruns'] for t in selected),maximum_decision_seconds=max(t['max'] for t in selected),
            median_game_p50_seconds=statistics.median(t['p50'] for t in selected),
            median_game_p99_seconds=statistics.median(t['p99'] for t in selected),
            qualification='Medians of per-game quantiles, not pooled decision quantiles; host-load-sensitive wall time')
audit=dict(utc=time.time(),manifest=MANIFEST,result_json_sha256=result_sha,eligible_games=4992,successful_partitions=248,
    restoration_hashes={h:json.loads((OPS/f'restoration-audit-{h}-r2e.json').read_text())['sealed_files_verified'] for h in ('127x01','127x04','127x08')},
    original_04_admitted=541,original_04_excluded=94,original_08_admitted=2000,original_08_excluded=0,
    receipt_rule=qual['rule'],physical_host_counts=result['compute']['hosts'],
    eligible_game_cpu_hours=result['compute']['game_cpu_hours'],
    excluded_original_04_game_cpu_hours=qual['excluded_recorded_cpu_hours'],
    original_04_failed_attempt_worker_cpu_hours=failed_cpu,successful_attempt_worker_cpu_hours=success_cpu,
    total_observed_attempt_worker_cpu_hours=failed_cpu+success_cpu,
    total_observed_supervisor_and_worker_cpu_hours=node_cpu,
    supervisor_initialization_and_control_cpu_hours=warmup_cpu,
    preflight_cpu_hours=result['compute']['preconfirmation_linux_cpu_hours'],quarantine=quarantine,
    accounting='Failed+successful worker totals include eligible and excluded games, interrupted work, and per-worker overhead; do not add eligible/excluded game CPU again. Supervisor totals include those workers plus initialization/control. Unknown 07 work and unmetered Mac work are additional. Quarantined 07 metered games, if any, are separate.',
    decision_timing=timings)
write(OPS/'completion-audit-r2e.json',audit)
summary=f'''\n## Recovery and complete-only audit\n
All 468 sealed hashes and manifest matched on 01, 04 and 08 (1,404 file checks). Original 04 receipts: 541 admitted before 01:39:00Z, 94 preserved and replayed at or after the cutoff. Original 08 receipts: all identity-valid copies admitted, zero excluded. Each of the 4,992 scheduled games contributes one eligible receipt. All 248 partitions completed successfully. Attempts: 04 originals r2e; migrations on 04/08 r2f; collector r2e. Original 04 r2 failures remain preserved.

Eligible game CPU: {audit['eligible_game_cpu_hours']:.8f} core-hours. Excluded original 04 game CPU: {audit['excluded_original_04_game_cpu_hours']:.8f} core-hours (additional to eligible game CPU). Total observed worker CPU across failed and successful attempts: {failed_cpu+success_cpu:.8f} core-hours, including {failed_cpu:.8f} in the preserved failed 04 attempt. This total already includes eligible and excluded game work; these quantities must not be added together. The five original/recovery/migration supervisors and their workers together recorded {node_cpu:.8f} core-hours; the difference, {warmup_cpu:.8f} core-hours, is supervisor initialization/control overhead. R2 preflight CPU: {audit['preflight_cpu_hours']:.8f} core-hours. Unknown 07 work and unmetered Mac work remain additional. Completion/quarantine and per-cell decision-timing summaries: operations/completion-audit-r2e.json.
'''
with (HERE/'RESULTS.md').open('a') as f:f.write(summary)
with (HERE/'PROGRESS.md').open('a') as f:f.write(summary)
with (HERE/'RESUME.md').open('a') as f:f.write('\nCOMPLETE: result.json and RESULTS.md published after all completion gates. No remaining study launch.\n'+summary)
assert hashlib.sha256((HERE/'result.json').read_bytes()).hexdigest()==result_sha
mirror()
print(json.dumps({k:v for k,v in audit.items() if k!='decision_timing'}))
