"""PE-1 control check (COORDINATOR f6afe586), run on 127x05 only. It is read-only and raises no STOP.

It applies the reviewed C7b metric, qualify4.parity_once at d09bdef9, to a COPY of Q7's two capture-free evaluation
phases (smoke/eval-K4S-120 and smoke/eval-S-200). io.JOB points at the copy, so nothing is written into J.
parity_once only computes; pause() is never called. Games are projected to timing metadata only, never outcomes.
"""
import json, sys
code, job = sys.argv[1], sys.argv[2]
sys.path.insert(0, code)
import x4s4io as io
io.JOB = job; io.REPORT_ROOT = code
import qualify4 as Q
phases = [f'{job}/smoke/eval-K4S-120', f'{job}/smoke/eval-S-200']
res = Q.parity_once(phases, 8, bank='smoke')
res.pop('inventory')
print(json.dumps(dict(res, check='pe1-control', phases=phases, code_commit='d09bdef9aecc416cb83b002fcff002ff57579fde',
                      label='X4S-4 PE-1 control check, exploration, NEVER ADOPTABLE'), indent=1, sort_keys=True))
