# Tempo exploration operations

Exploration only: synthetic paired games, no pre-registration and no registered evaluation/heldout data. Nothing here authorizes deployment or a git commit.

`src/clasher/analysis/loss_review/tempo.py` holds the opt-in leaf option curve, timing candidates and WAIT score prior. `simulate.py --tempo` activates them; omitting `--tempo` preserves the existing S6/A/B path. E/H/W/EW arm definitions are recorded in each game and schedule. Resume validates those definitions before reusing results. An initial HW tuning definition mistakenly enabled E; the corrected definition has no E term, is tested explicitly, and is rerun on the separate combination seeds. The superseded instances are retained outside the analysis games tree and counted separately in the compute audit. EW remains selected because its zero losses and first tie precedence are invariant to the corrected HW result.

A direct diagnostic command, run only on an authorized CPU host with the shared guard/shard wrapper for production work:

```bash
nice -n 10 chrt --idle 0 python -B -m clasher.analysis.loss_review.simulate \
  --tempo --delays 27 --arms 0 E H12 H16 W EW \
  --tempo-elixir-weight 0.005 --tempo-wait-prior 0.01 \
  --tempo-combo-horizon 320 --full-decision-latency \
  --pairs 1000 --workers 40 --seed-base 281474976780666 \
  --exclusions reports/explore/tempo/exclusions.json --out FRESH_EXPLORATION_PATH
```

The reusable fleet path is `pipeline.py` → `scheduler.py` → `worker_runtime.py`, using the original A/B `gpu_guard.py`, native binary, five-deck selection, matchup/seat/style schedule and metric extractor. Reporting uses 50-pair shards; tuning uses 150 pairs; combination selection uses 25-pair shards. `select.py` reads only separate tuning/combination games, and the scheduler takes the resulting fixed selection. It does not choose parameters from reporting results. Each phase has an atomic scheduler receipt; `--resume-state` preserves active job identities instead of duplicating launches. Source and native comparisons are in `receipts/runtime-pin.json` and `receipts/baseline-match.json`.

All leased simulations go through immutable wrapper `run_v2.sh` r3, with declared whole-job process and PSS budgets. `stage.sh` runs from home 04 and checksum-copies only the required Clasher runtime. Shard payloads, subprocess launches, remote helpers and rsync servers explicitly start with `nice -n 10 chrt --idle 0`; forked workers inherit both settings. This launch fix was applied at ~02:25Z after the coordinator caught a transient nice-0 helper. Existing compliant shards continued without restart. The inherited policy regression and first-instruction/fork/exec receipts are retained. Simulation workers use affinity exclusions. Every measured GPU-rate baseline is a throughput measurement from the co-located job, never utilization. Captures use completed-frame journal counts; only rate telemetry is read, with no prediction/label/outcome decoding. The original baseline and unloaded refresh controls are retained. Baseline refreshes are permitted only after continuous stopped-simulator control; failed control assertions leave a refresh unauthorized. Already-paused stalled shards may drain via exact, verified own PIDs; unfinished cases resume elsewhere. No broad process kills are used.

New leased shard admission stops at 04:15Z. Each leased runner initiates termination by 04:29Z and the wrapper owns descendant cleanup; this task verifies its own leased workers and monitors exited before 04:30Z. Hosts 01/02/08 and owner-repository paths are excluded. Home 03 checks the reservation marker before every launch. The 16 worker count was reduced from a refused 40-worker declaration to 28 under combined PSS limits.

Reduction uses shared seed bootstrap draws for wins/losses, pooled loss-review metrics, expensive-card affordability and mean latency. It reports active wall, raw wall and CPU timing separately; the actual 200 ms requirement uses raw wall time. Zero empirical rates are sample estimates, not population upper bounds.

No full per-game files are copied to 05. They stay on 04 and original shard hosts. Compact JSON, the report, source, tests and execution/admission receipts are the local deliverables. `TASK_STATE.json` identifies the current controller and phase for a continuation.
