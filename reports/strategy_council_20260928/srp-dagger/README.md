# SRP DAgger kit

This directory owns one canonical 40-game iteration from the seed-2902 1M student. SRP is a
privileged teacher. Student inputs remain public-v4. See DESIGN.md for the fixed
collection, split, loss and evaluation decisions, and PROGRESS.md for live status.

The canonical pilot is complete. Fine-tuned wins fell to 16/192 from the initial
student's 88/192 on the paired public-script evaluation. Held-out CE improved,
but exact action agreement stayed near 42.7%. See [RESULTS.md](RESULTS.md),
[results.json](results.json) and [fit curves](fit-curves.png). The checkpoint is an
experimental artifact; this pilot did not establish a policy improvement.

Run from the repository root with `.venv/bin/python -B` and `nice -n 10`. Long jobs
must go through `reports/strategy_council_20260928/pilot/detach.sh LOGFILE CMD...`.

- `kit.py preflight` validates pilot.toml, engine hashes and actor/eval input parity.
  It requires GAMEDATA_CANONICAL_READY and canonical-data.json first.
- `kit.py collect --start 0 --stop 40` collects complete games and validates each
  NPZ. Use disjoint ranges for at most two workers. Rerunning a range checks and
  skips completed game receipts. Do not run two workers over the same range.
- `verify.py` checks executed-history alignment, public legality, candidate-value
  argmax labels, full terminal context and the requested KL direction.
- `fit.py` aggregates complete games, makes the fixed game split and fits three
  epochs using the existing full-prefix recurrence and public sequence helpers. It refuses to
  overwrite an existing final fit. The frozen anchor has its own full-prefix recurrent state.
- `evaluate.py` imports the shared human-prior-p16 run_eval.py and selects the
  workspace engine. Pass `--parallel 1` or `2`, `--trace-games 0`, `--checkpoint`
  and a distinct `--name`. The fixed initial/final names are in report.py.
- `report.py` validates matching evaluation seeds, seats, decks and levels, then
  reports an exact paired sign-flip test and paired bootstrap interval.
- `rebalance.py` with no PID arguments resumes missing games only when no collector
  is active, using two concurrent single-game commands. Its optional PID pair is
  for a verified handoff from the original owned range workers.
- `run.py` coordinates the rest of this pilot after the explicitly tracked first
  game and initial evaluation. Its PID arguments must identify those owned jobs.
- `canonical.py` runs the replacement pilot with one baseline evaluation worker
  alongside one parity/collection/verification/fit process, then two final-eval
  workers. Launch only after the canonical marker exists. It verifies admitted
  non-meta data equality and canonical Stage 2/3 native fingerprints, writes the
  data/runtime pins, then runs preflight before starting any games.

Artifacts include complete per-game NPZ/JSON records, preflight source hashes,
aggregate.npz, split.json, fit-batches.jsonl, fit-curves.json, student.pt,
fit.json and results.json. completion.json is written only after all stages exit
successfully. The shared evaluation directories retain per-game evidence.

Collection stores every five-tick observation, forced waits as unsupervised
context, every queried teacher label including waits, executed actions and sparse
root candidate values. Candidate values are model-based privileged scores, not
calibrated probabilities. Fit losses use only queried rows. Held-out agreement is
exact action-ID top-1 agreement under full recurrent replay, with play and wait
agreement reported separately.

Collection defaults to the verified native SRP backend; `kit.py` adds `engine-rs`
and `src` to its import path. `native-runtime.json` pins the extension and adapters.
The live engine remains the workspace Python engine. `native_parity.py` performs
a separate complete game on both backends with canonical data and verifies every
public and action array exactly, with sparse root-score differences reported separately. Preserve the original
preflight and native receipts when resuming this pilot. A future iteration needs
its own output directory, config and refreshed runtime/data pins.

`archive/noncanonical-3d99987c/` preserves the invalid first cohort, fit and
evaluations. Its Ice Spirit HP and Goblin damage differed from admitted values.
Nothing in that archive is included in the canonical pilot or its metrics.
