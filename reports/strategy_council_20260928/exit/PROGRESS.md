# ExIt proposal-network confirmation progress

Updated UTC: 2026-10-04T13:16:42.854866+00:00
Status: COMPLETE, FAIL at the preregistered primary gate.

- PREREG-CONFIRM.md and confirm/manifest.json froze before any confirmation game.
- Fresh-seed audit: 72,380 JSON/JSONL files, 905,160 seed fields, zero overlap.
- Five no-game tests passed before launch.
- All 640 games completed; worker exit codes 0, 0, 0.
- Primary: student 123/256 = 0.480469, CI [0.425781, 0.531250], FAIL.
- Holdout scripts: student 104/128, initial 102/128; drop -0.015625,
  CI [-0.078125, 0.046875], secondary PASS.
- Hog26 scripts: student 31/64, initial 30/64; descriptive only.
- Original policy-alone 64 vs 83/192 remains descriptive, not a gate.
- Iterations 2 and 3 were not started. Retain initial s2902 1M proposer.
- Final source/checkpoint, complete-pair, receipt and process audit passed.
- CONFIRM.md, confirm/it1/result.json, completion.json and final-audit.json written.
- Total exit/ storage about 40.5 MB, below 2 GiB.

Running task-owned PIDs: none. Driver 33105 and workers 33109, 33110, 33111 exited.
No foreign process was signalled. No forbidden path was edited.

Exact launch command:
`bash /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/detach.sh /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/exit/confirm/driver.log --cwd /Users/sam/Desktop/code/clasher nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/exit/confirm.py driver`

Next: none under this protocol. Recommendation and all results are in CONFIRM.md.

## Historical iteration-1 run

# Historical ExIt progress

Status: COMPLETE. Iteration 1 rejected; zero accepted iterations. No iteration 2
or 3 was started. No task-owned process remains running.

Done:
- Required source/guidance review and pre-implementation DESIGN.md.
- Canonical/native hash preflight; public-only, recurrence, candidate-gradient
  and identical-policy paired-seat smoke checks passed.
- 150 complete collection games, 50 Hog26, 18,821 searched decisions.
- One full-prefix BC epoch, 475 updates; checkpoint reload passed.
- 384 policy evaluation games. Initial 83/192, student 64/192;
  Hog26 32/96 -> 18/96. Paired drop p = 0.015639333.
- 192 search comparison games. Scripts initial 46/64, student 40/64;
  Hog26 18/32 -> 17/32. Student head-to-head 39/64, Hog26 20/32.
- One simultaneous Cannon placement rejection replayed and explained; the
  affected loss remains included. No engine or planner change.
- Final hash, corpus, checkpoint and paired-matchup audit passed.
- RESULTS.md, result.json, final-audit.json and completion.json written.

Running PIDs: none. Historical drivers 43436 and 20979 both exited.

Next: none. Retain the initial s2902 proposal policy. This run failed the requested
policy-alone gate despite passing search head-to-head. Do not start iteration 2.

Exact final analysis command:
`nice -n 10 .venv/bin/python -B reports/strategy_council_20260928/exit/analyze.py --iteration 1`

Exact replay command:
`bash reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/exit/logs/rejected-play.log --cwd /Users/sam/Desktop/code/clasher nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/exit/diagnose_rejected.py`

Exact original driver command:
`bash reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/exit/logs/driver.log --cwd /Users/sam/Desktop/code/clasher nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/exit/driver.py`

Every collection, fit and evaluation command and child PID is retained in
receipts/. The first report attempt failed an unrequested zero-rejection
assertion. Its error and receipt are preserved; it1-analyze-final.json records the
successful reporting-only amendment. manifest-as-run.json and as-run/analyze.py
preserve the experiment identity. No experiment outcomes were removed or rerun
for acceptance. The diagnostic replay is separate evidence.

Only exit/ was changed. About 40 MB retained, one student checkpoint. The generic
checkpoint metadata caveat is documented in it1/checkpoint-provenance.json.
