# Reproduce or resume the card probes

All final measurements use 127x08 and `/mpac/sdicks02/repos/clasher-bot-runtime/r1/src`. The frozen pool is `pool.json`: exactly `ladder_pool()` minus the literal `C56` set. Card order is group 1, then group 2, then remaining pool order. The Cage row includes its Brawler.

Copy `scenarios.py`, `controlled.py`, and `pool.json` into a fresh directory under `/mpac/sdicks02/jobs/clasher/cards/fidelity/` on 08. The adapters are read from `/mpac/sdicks02/repos/clasher-bot/bot/fidelity/engines.py`; no runtime or other worktree files need modification. The installed RoyaleSim binding is in the bot venv on 08. Its build and all r1 Python/data hashes are recorded in `provenance.json`.

From that jobs directory on 08, launch the full-table run:

```bash
setsid nohup /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 7 \
  nice -n 15 env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/mpac/sdicks02/repos/clasher-bot-runtime/r1/src \
  CLASHER_ROOT=/mpac/sdicks02/repos/clasher-bot-runtime/r1 \
  NUMBA_CACHE_DIR="$PWD/numba-cache" \
  /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B scenarios.py \
  --pool pool.json --out full.jsonl --workers 6 --table 160402 \
  >full.log 2>&1 </dev/null &
printf '%s\n' "$!" >full.pid
```

The lease above allows six workers plus their coordinator. Keep the recorded PID; inspect/wait on that PID, never discover jobs with `pgrep`. For the single-worker option, use `cpu_job.sh 2` and `--workers 1`. The original measured jobs used up to six workers, always through the lease and `nice -n 15`.

Run the same command with `--table adapter` and a separate output filename for the unchanged harness baseline. `--cards GoblinCage ...` restricts a resume to named cards. `scenarios.py` skips successful card/scenario/table keys already present in its output and retries exceptions. Use a fresh output if the source, feed, harness schema, or calibration changes.

Use `controlled.py --out controlled-full.jsonl --workers 6 --table 160402` in the same leased, detached environment for the six-spell, 19-offset geometry/duration matrix. It runs each spell through normal deployment against one stationary 10000-HP Knight. Repeat with `--table adapter` for the secondary arm. These target-state interventions are explicit in every controlled row. Edited RoyaleSim snapshots receive the engine's own rebuilt checksum and are verified on load.

Copy the completed small JSONL files back into this report directory, then consolidate:

```bash
python3 -B summarize.py full.jsonl adapter.jsonl controlled-full.jsonl controlled-adapter.jsonl
python3 -B verify_results.py
```

The checked-in consolidated `results.jsonl` can also be passed directly to `summarize.py` to rebuild the Markdown and summary. Validation expects 620 unique pairs: 196 natural scenarios and 114 controlled scenarios for each table arm. To check source citations and the measured battle-module hash on 08, also run `verify_results.py --source-root /mpac/sdicks02/repos/clasher-bot-runtime/r1` alongside the consolidated outputs, pool, causes and summary.

The original raw runs, logs, and PID records remain in `/mpac/sdicks02/jobs/clasher/cards/fidelity/20261015/` on 08. The final Collector rows come from `collector-175-{adapter,160402}.jsonl`, overriding earlier shorter runs. Early pilot/harness failures are retained remotely for audit and excluded from the consolidated results. No commits or pushes were made.
