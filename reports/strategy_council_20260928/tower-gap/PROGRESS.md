# tower-gap: PROGRESS (resumable)

Task: why the sim kills towers that survive in real human matches (C56 first contradiction
"sim_kill_of_tower_standing_in_real"), and the cheapest fix. Read-only on src/, c56/, pilot/, m0/.
PY=/Users/sam/Desktop/code/clasher/.venv/bin/python ; T=reports/strategy_council_20260928/tower-gap
Stats venv (outside repo, pandas+statsmodels): /Users/sam/.cache/tower-gap-statsvenv/bin/python

## Done
- step 0: read CLAUDE/AGENTS, c56 QA_SUMMARY + data/PROGRESS, human_replay_v5.py, extract.py.
- step 1: scripts/dump_summaries.py --payloads -> data/perspectives.jsonl.gz (41,699 completed perspectives as of
  Oct 3 14:10 PDT; extraction still running) + data/payload_facts.jsonl.gz (74,236 matches). scripts/common.py loads both.
- step 2: runtime/ = rsync copy of c56/data/runtime-engine-v2; only change: tower_scaling.py level range 1..16
  (formula reproduces real L13-16 tower HP exactly). scripts/resim.py = instrumented replay: unmodified
  reconstruct_perspective_v5 + in-process monkeypatches (sim-kill recorded not cut, tower-damage attribution,
  level variants, clamp variant). Base reproduces extraction cut tick and supervised rows exactly.
  Sample data/sample300.jsonl = 300 random s117 perspectives, one per match (seed 7).
- step 3: scripts/q2_assoc.py -> data/q1_q2_stats.json (owner/slot/time, rates, clustered logits).
- Scratch cleaned 15:15 (simkill.pkl, smoke files, /tmp/tg*).

## Running PIDs
- none. resim300 workers 21019/21025 finished (1,800/1,800 runs, 0 errors). Rerun command (resumable, skips done keys):
  cd /Users/sam/Desktop/code/clasher && T=$PWD/reports/strategy_council_20260928/tower-gap; for w in 0 1; do $PWD/reports/strategy_council_20260928/pilot/detach.sh $T/logs/resim300-w$w.log --cwd $PWD env CLASHER_ROOT=$T/runtime PYTHONPATH=$T/runtime/src OMP_NUM_THREADS=1 nice -n 10 $PWD/.venv/bin/python $T/scripts/resim.py --sample $T/data/sample300.jsonl --variants base clamp tower_real rel evo2 spell_ctd --workers 2 --worker $w --out $T/data/resim300-w$w.jsonl; done

## Done (cont.)
- step 4: scripts/analyze_resim.py -> data/resim300_analysis.json (final, n=300).
- step 5: README.md final (causes, numbers, mechanism tests, recommendation: clamp-at-1-HP replayer rule,
  1.0x overshoot cut, ~74.5% -> ~84% projected).

## Next (optional)
- native checks: Hunter defending, Cannon Cart attacking, Elite Barbarians.
- implement clamp rule in a replayer v5.1 (owner: c56-data), re-extract.
- stats venv deleted to save disk; recreate: uv venv /Users/sam/.cache/tower-gap-statsvenv --python 3.12 && uv pip install --python /Users/sam/.cache/tower-gap-statsvenv/bin/python pandas statsmodels scipy
