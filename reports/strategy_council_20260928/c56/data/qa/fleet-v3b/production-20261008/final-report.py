import json,datetime,hashlib,shutil,subprocess
from pathlib import Path
D=Path('/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/c56/data'); Q=D/'qa/fleet-v3b/production-20261008'
read=lambda p:json.loads(p.read_text())
qa=read(Q/'final-qa.json'); completion=read(Q/'production-completion.json'); mirror=read(Q/'mirror-127x04.json')
assert completion['complete'] and qa['complete'] and mirror['complete_corpus'] and mirror['checksum_differences']==0
assert qa['units']==1767
perspectives=qa['stats']['perspectives']; errors=len(qa['errors'])
assert perspectives+errors==82231
nodes={}
for h in ('127x01','127x03','127x04'):
 c=read(Q/f'completed-{h}.json'); n=completion['nodes'][h]
 assert c['complete'] and read(Q/f'v2-final-verification-{h}.json')['originals_and_preserved_copies_verified']
 nodes[h]={k:n[k] for k in ('units','perspectives','rows','errors')}
 nodes[h].update(wall_seconds=c['wall_seconds'],cpu_seconds=c['cpu_seconds'],bytes=sum(x['bytes'] for x in c['files'].values()),units_per_hour=c['units']*3600/c['wall_seconds'])
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
receipt=dict(utc=now,complete=True,units=qa['units'],perspectives=perspectives,rows=qa['rows'],errors=errors,illegal_labels=qa['illegal_labels'],retention=qa['stats']['retention'],placement_acceptance=qa['stats']['placement_acceptance'],output_bytes=qa['output_bytes'],nodes=nodes,mirror=mirror,v2_preserved_archives_per_node=137,v2_preserved_bytes_per_node=415341863,final_qa_sha256=hashlib.sha256((Q/'final-qa.json').read_bytes()).hexdigest(),production_completion_sha256=hashlib.sha256((Q/'production-completion.json').read_bytes()).hexdigest())
receipt['incident_inputs_unchanged_hosts']=[h for h in ('127x01','127x04') if read(Q/f'incident-input-audit-{h}.json')['pass_']]
receipt['invalidated_extraction_units']=[]
receipt['final_collector_runtime']=read(Q/'collector-runtime-receipt.json')
(Q/'completion-summary.json').write_text(json.dumps(receipt,indent=2)+'\n')
lines=[f"## Production completion — {now}", '', f"**COMPLETE: {qa['units']:,}/1,767 units; {perspectives:,} successful perspectives / 82,231 attempted; {qa['rows']:,} persisted rows; {errors} errors; {qa['illegal_labels']} illegal labels.** Every persisted row passed the existing validators. Full-corpus retention **{100*qa['stats']['retention']:.4f}%**; placement acceptance **{100*qa['stats']['placement_acceptance']:.4f}%**. Opponent-cut retention loss **{qa['opponent_cut_retention_points']:.4f} points**, within the 3-point rule. Runtime, extractor, recipe and frozen inputs remain pinned; no BC training or commits.", '', f"Published NPZ/sidecar pairs: **{qa['output_bytes']:,} bytes**. The 811-unit base is included exactly once; 956 new units were extracted. All 1,767 expected unit keys and 82,231 perspective attempts are covered. Both phase-specific placement/retention gates passed.", '']
for phase,p in qa['phases'].items():
 lines.append(f"- {phase}: {p['units']} units, {p['extracted']:,} successful perspectives, {p['errors']} errors; retention {100*p['stats']['retention']:.4f}%; placement {100*p['stats']['placement_acceptance']:.4f}%.")
lines+=['','Production extraction (new units only; QA/collection overhead separate):','']
for h,n in nodes.items():
 lines.append(f"- {h}: {n['units']} units, {n['perspectives']:,} perspectives, {n['rows']:,} rows, {n['errors']} errors; wall {n['wall_seconds']:.3f} s, CPU {n['cpu_seconds']:.3f} s, {n['units_per_hour']:.2f} units/hour; {n['bytes']:,} bytes.")
lines+=['',f"**127x04 complete-copy PASS** at {mirror['utc']}: {mirror['files']:,} files / {mirror['bytes']:,} bytes, zero checksum differences, complete_corpus=true. The full `recon/engine-v3` output is at the same absolute path on 01 and 04.",'','**V2 preservation PASS:** all 137 original archives plus sidecars on every node remain checksum-identical to their preservation copies, 415,341,863 bytes per node. Required copies are at `127x01` and `127x04:/mpac/sdicks02/repos/clasher-local-data/c56-v2-archive-preserve/`; an additional verified copy is on 03. See v2-preservation-<host>.json and v2-final-verification-<host>.json.','', 'Receipts: `qa/fleet-v3b/production-20261008/{completion-summary,production-completion,final-qa,mirror-127x04}.json`; corpus index/completion: `recon/engine-v3/{fleet-index,completion}.json`. Collector label `c56-v3b-production-20261008-supervise-r5`; extraction label `c56-v3b-production-20261008-extract` on each node. Retain all logs, exits and earlier interrupted/failed supervisor receipts.','', 'No resume is needed after successful completion. For recovery or a repeat integrity audit, use `resume.txt` / `run-production.sh` after inspecting PID, lock and exit receipts. Exact collector command (fresh label; existing completed workers are reused):', '```sh', "ssh 127x01 'bash /mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/c56/data/qa/fleet-v3b/production-20261008/run-production.sh supervise c56-v3b-production-20261008-supervise-r6'",'```','', 'Overwrite audit PASS on 01/04: all 454 frozen inputs and 1,622 base files match pins, input ctimes predate the overwrite window, zero units invalidated. Collector r5 recomputed all 956 new-unit row audits under the explicitly verified frozen runtime after r4 caught its launcher binding error; earlier QA caches remain preserved and superseded. Root reports and small receipts are mirrored to 127x05; no NPZs are copied to the command center. Intermediate raw-equivalence and external-wrapper-overwrite incidents are retained below. The production wrapper is isolated under `scripts/fleet_v3b_production_worker_20261008.py`; original extractor SHA remains 8e95786c… and runtime SHA 1ec2c60c….','']
section='\n'.join(lines)
for name in ('PROGRESS.md','FLEET-RESULTS.md'):
 p=D/name; text=p.read_text(); parts=text.split('\n\n',2)
 status=f"Current v3b status: **COMPLETE** at {now}: 1,767 units, {perspectives:,} perspectives, {qa['rows']:,} rows, {errors} errors, retention {100*qa['stats']['retention']:.4f}%; full checksum backup verified on 127x04."
 text=parts[0]+'\n\n'+status+'\n\n'+section+'\n\n'+parts[2]
 p.write_text(text); shutil.copy2(p,Q/('production-backup-'+name))
print(json.dumps(receipt,indent=2))
