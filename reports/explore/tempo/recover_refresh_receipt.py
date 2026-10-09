"""Reconcile a validated refresh whose PID-selection assertion prevented cleanup."""
import json,math
from pathlib import Path
root=Path('/mpac/sdicks02/repos/clasher-lease/tempo-runtime/reports/explore/tempo');base=json.loads((root/'receipts/perception-rate.baseline.json').read_text());t=base['recalibration_utc']
records=[json.loads(s) for s in (root/'receipts/perception-rate.jsonl').read_text().splitlines()];window=[r for r in records if t-120<=r['utc']<=t];rate=sum(r['frames_per_second_step'] for r in window)/len(window)
assert math.isclose(rate,base['baseline'],rel_tol=1e-12)
controls=[json.loads(s) for s in (root/'early-reporting/gpu-guard.jsonl').read_text().splitlines()];controls=[r for r in controls if t-120<=r['utc']<=t];assert len(controls)>=40 and all(r['paused'] for r in controls) and t-controls[0]['utc']>=110
prior=json.loads((root/'receipts/baseline-recalibration-127x13.json').read_text());receipt=dict(prior,new_baseline=rate,control_samples=len(controls),control_seconds=t-controls[0]['utc'],rate_samples=window,utc=t,actual_refresh_recovered=True,note='Initial refresh passed unloaded validation and was written, then runtime-PID assertion refused cleanup. Old runtime retained original comparator; next shard read this validated baseline. No GPU process changed.')
(root/'receipts/baseline-recalibration-127x13.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(baseline=rate,control_seconds=receipt['control_seconds'],recovered=True)))
