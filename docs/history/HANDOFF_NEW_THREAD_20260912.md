> ARCHITECTURE CHECKPOINT 2026-09-13: Full simulator-centered pipeline design and implementation handoff now live at /Users/sam/.codex/worktrees/clasher-simulator-fidelity-20260913/PIPELINE_DESIGN.md and HANDOFF.md. User authorized simulator improvement, then asked to finish planning before implementation. Persistent goal and old training remain off. Continue simulator work in the isolated worktree.

> USER PAUSE 2026-09-13: Native persistent goal removed and verified null; scheduled monitor paused; queued continuation deleted. No new training, collection, late-continuation probe, search, or policy updates. Comparative research is the current task; a fresh pipeline awaits user decision.

# Clasher Hog 2.6 handoff, September 12, 2026

Read this file first. Then verify the live process and completion artifacts before
running anything. The current training sequence runs as a macOS process outside
the chat turn. A completed assistant response does not mean an agent is still
reasoning, but it also does not stop that process. Trust `ps`, the supervisor
state file, logs, and `complete.json` files.

## Objective

Build and validate a calibrated actor-visible Hog 2.6 outcome model from complete
games. It predicts undiscounted win, draw, or loss and terminal tower margin
across held-out seeds, opponents, seats, and game phases. Privileged state may
appear only in a training teacher.

Do not start search, PPO, self-play learning, policy updates, or promotion until
the public calibration and counterfactual ranking gates pass. The existing
384-game fresh-seed corpus is opened diagnostic evidence. It is excluded from
training and cannot become untouched acceptance evidence. Preserve all reserved
selection, calibration, final-generated, final-original, and draw roles.

The goal is not complete. This work has produced outcome-model evidence, not a
competent Clash Royale playing policy or a measured mid-ladder rating.

## Correct checkout and ownership

- Worktree: `/Users/sam/.codex/worktrees/clasher-event-policy`
- Branch: `codex/hog26-event-policy-redesign`
- HEAD at this handoff: `93fcace5656e6085172871e4011cbb9082afcd21`
- Python: `/Users/sam/Desktop/code/clasher/.venv/bin/python`
- Base checkout: `/Users/sam/Desktop/code/clasher`
- Original September 8 handoff:
  `/Users/sam/Desktop/code/clasher/docs/history/HANDOFF_NEW_THREAD_20260908.md`

Use the worktree above. Do not reset, clean, stash, merge, or delete its data and
reports. The worktree contains many intentional untracked datasets and generated
reports. At this handoff, the only tracked modification reported by
`git status --short --untracked-files=no` was:

```text
 M reports/hog26_protocol_reassessment_20260908.md
```

Read the base checkout's `AGENTS.md`. Preserve unrelated local work and other
running workloads.

## Live state at 2026-09-12 16:37 PDT

One sequential fitting supervisor is running:

- Supervisor PID at the snapshot: `30659`
- Script:
  `/Users/sam/Library/Application Support/ClasherMonitor/run_scaling_fit.py`
- Supervisor log: `reports/hog26_scaling_fit_sequence_20260912.log`
- State file:
  `/Users/sam/Library/Application Support/ClasherMonitor/comparison-status.json`
- Lock:
  `/Users/sam/Library/Application Support/ClasherMonitor/comparison.lock`
- Memory limit: 18 GiB RSS, including descendants

The supervisor runs `globals`, `tree`, then `entity`. It refuses existing output,
requires each preceding `complete.json`, stops on a nonzero exit, and updates the
state file atomically. Do not launch a second copy.

At the snapshot:

- Globals completed all eight fixed fits and wrote `complete.json`.
- Tree was active as PID `35783`, using one CPU core and about 7.2 GiB RSS.
- Tree fold 0 completed in 508.16 seconds. The remaining three folds were queued.
- Entity had not started.

These PIDs and the active stage will become stale. Recheck them:

```sh
cd /Users/sam/.codex/worktrees/clasher-event-policy
cat '/Users/sam/Library/Application Support/ClasherMonitor/comparison-status.json'
ps -axo pid,ppid,etime,%cpu,%mem,rss,command | \
  rg 'run_scaling_fit|run_scaling_comparison|evaluate_scaling'
```

For the current stage, inspect the matching log without restarting it:

```sh
tail -n 40 reports/hog26_scaling_tree_comparison_20260912.log
tail -n 40 reports/hog26_scaling_entity_comparison_20260912.log
```

An observation timeout or a finished chat turn is not a training failure. Treat
the job as failed only if the process is gone and its required completion file is
absent, or the state file records `stage: failed`.

## What has completed

### Corrected 384-game pilot

The birth-corrected pilot contains 384 complete games, 154,811 decision rows,
and 192 paired scenario clusters. Outcomes were 80 wins, zero draws, and 304
losses. It recorded zero rejected card actions. Its complete-manifest SHA-256 is
`74c745c8b42203f8cd83aa7aed19cb1ae8fb9ac9e57cf3b86c5790e745183911`.

The original frozen comparison completed 20 fits. The global classifier was not
stable across seeds. The tree improved pooled margin MAE, but late evidence was
sparse and did not pass. The entity/history model fit training data and became
worse on excluded families. No model passed.

Review:
`reports/hog26_scalar_pilot_completed_comparison_review_20260911.json`

### Opened fresh-seed diagnostic

The diagnostic contains 384 complete games and 155,496 rows. Outcomes were 86
wins, zero draws, and 298 losses. All 20 original frozen fits were evaluated.

The entity model had negative NLL gain in all eight fresh seen-family fits and
all eight fresh excluded-family fits. That showed failure on new scenarios from
trained families as well as family transfer. The tree's overall margin point
estimate stayed positive, but late coverage remained too small for a phase gate.

Review: `reports/hog26_seed_transfer_review_20260912.json`

### Fixed data-scaling experiment

The chosen next test kept the model architectures, folds, seeds, epochs, and tree
iterations fixed. It added 1,152 new training games to the original 384:

- Extension directory:
  `datasets/derived/hog26_scaling_train_seed1279701_20260912`
- Extension: 1,152 games and 463,338 rows
- Combined corpus: 1,536 games, 618,149 rows, 768 paired clusters
- Diagnostic games used in fitting: zero
- Extension complete-manifest SHA-256:
  `5902a7e8b2d9a6b50ba39aa9b237dc0bb97859e38c45bbf766e3300b08ba6e06`
- Frozen plan: `reports/hog26_scaling_frozen_plan_20260912.json`
- Preflight pin: `reports/hog26_scaling_preflight_pin_20260912.json`

The compact loader removes only trailing entity slots that are always masked and
zero. It reconstructs the original 384-game model tensors bit-for-bit. It does
not remove timesteps or visible entities.

### Memory and fitting readiness

The full combined-corpus audit passed before fitting. Both probes used synthetic
targets and saved no outcome model:

- Neural maximal batch, full backpropagation, finite gradients, one optimizer
  step: 3,950,428,160 bytes peak RSS.
- Largest tree fold, 474,642 rows by 2,381 float64 columns, binning and one
  histogram iteration: 9,019,834,368 bytes peak RSS.
- Cutoff for both: 19,327,352,832 bytes.

The tree probe is a full preprocessing and one-iteration memory check. It is not
a measured 100-iteration fit. The live supervisor retains the same 18 GiB guard.

Readiness matched both report hashes, the exact fitting-source inventory, runtime,
collection plan, and combined data audit. Seventeen fitting tests passed and Ruff
was clean before launch.

- `reports/hog26_scaling_full_memory_neural_20260912.json`
- `reports/hog26_scaling_full_memory_tree_20260912.json`
- `reports/hog26_scaling_fitting_readiness_20260912.json`

Do not edit any Python file in `experiments/hog26_scaling_fit` while the sequence
runs. Its source hashes are part of every readiness and fitting manifest. Also do
not edit the plan, preflight pin, memory reports, input data, `src`, `scripts`,
`experiments/hog26_scalar_pilot`, or `experiments/hog26_data_scaling`.

## Preliminary scaled globals result

This is complete output from the globals stage, but it is not the comparison's
final review. Out-of-fold excluded-family results improved sharply with more
data and were consistent across the two fixed seeds:

| Seed | All-state NLL gain | All-state decisive AUC | Representative NLL gain | Representative decisive AUC |
|---:|---:|---:|---:|---:|
| 1279501 | +0.14795 | 0.84403 | +0.18305 | 0.86967 |
| 1279502 | +0.15748 | 0.84411 | +0.18691 | 0.86613 |

Late all-state NLL gains were +0.02812 and +0.05905. Both clustered 95 percent
intervals crossed zero. Late coverage was 80 games and 70 scenario clusters,
with 15 clusters containing a win. Globals uses the current public tower margin
unchanged, so its margin gain is exactly zero by design.

Do not call this acceptance. The fixed comparison plan says no aggregate score
may conceal phase or family regression, and this experiment cannot promote a
candidate. Tree, entity, and the opened fresh-seed diagnostic remain outstanding.

Globals output:
`reports/hog26_scaling_globals_comparison_20260912`

## What to do next

### If fitting is still running

Leave it alone. Check the OS process, state, RSS, log growth, and completion
artifacts. Do not duplicate it or edit pinned resources. The scheduler sends a
continuation request every ten minutes, but that message does not itself prove an
agent or worker is active.

### If fitting failed

Keep all partial outputs and logs. Record the exact failed stage, exit code, peak
RSS, traceback, and last complete artifact. Do not delete the output directory or
rerun around it. Diagnose whether the cause is memory, implementation, data, or
process supervision. Any repair that changes pinned fitting Python requires new
memory reports and a new readiness artifact before another outcome fit.

### If all three models completed

Require these files:

```text
reports/hog26_scaling_globals_comparison_20260912/complete.json
reports/hog26_scaling_tree_comparison_20260912/complete.json
reports/hog26_scaling_entity_comparison_20260912/complete.json
```

Check that each complete file has the expected model and seeds. Check that all
three fitting manifests agree on the 1,536-game audit, collection-plan hash,
comparison-plan hash, vocabulary, input games, and fitting implementation.
Expected artifact counts are 30 regular files for globals, 17 for tree, and 30
for entity.

The prepared fit-authority checker validates completed model files and shared
training authority before diagnostic access:

```sh
cd /Users/sam/.codex/worktrees/clasher-event-policy
env PYTHONPATH='experiments/hog26_scaling_eval:experiments/hog26_seed_transfer:experiments/hog26_scaling_fit:experiments/hog26_data_scaling:experiments/hog26_scalar_pilot:src:.' \
  /Users/sam/Desktop/code/clasher/.venv/bin/python -c \
  'from pathlib import Path; from fit_authority import pin_fits; resources, authority = pin_fits(Path.cwd()); print(len(resources)); print(authority["data_audit"])'
```

Then review fitting and excluded-family results for every seed and fold. Compare
all-state and representative metrics. Inspect overall, every phase, seat, style,
family, and phase by seat by style. Compare fitting errors with excluded errors
to separate capacity from generalization. Do not treat decision rows as
independent games. Require clustered intervals and report slices with missing
outcomes as inconclusive.

Write a machine-readable comparison review before interpreting the diagnostic.
Update `reports/hog26_protocol_reassessment_20260908.md` with exact metrics and
limitations.

## Opened diagnostic evaluation after fitting review

The inference-only evaluator is prepared in `experiments/hog26_scaling_eval`.
It evaluates all 20 scaled fits on the existing 384-game fresh-seed diagnostic.
It performs no fitting, calibration, or selection. It refuses access until all
three model stages are complete and their authority agrees. It pins checkpoints,
manifests, and evaluator source before prediction. It derives class priors only
from the original 384 plus extension 1,152 training manifests.

Run it only after the completed fitting audit described above:

```sh
cd /Users/sam/.codex/worktrees/clasher-event-policy
env OMP_NUM_THREADS=1 \
  PYTHONPATH='experiments/hog26_scaling_eval:experiments/hog26_seed_transfer:experiments/hog26_scaling_fit:experiments/hog26_data_scaling:experiments/hog26_scalar_pilot:src:.' \
  /Users/sam/Desktop/code/clasher/.venv/bin/python \
  experiments/hog26_scaling_eval/evaluate_scaling.py \
  --data datasets/derived/hog26_seed_transfer_seed1279601_20260911 \
  --plan reports/hog26_seed_transfer_frozen_plan_20260911.json \
  --preflight reports/hog26_seed_transfer_preflight_pin_20260911.json \
  --output reports/hog26_scaling_seed_transfer_evaluation_20260912
```

Do not overwrite an existing evaluation directory. If one exists, inspect its
manifest, resources, logs, process, and `complete.json` before acting. Each fit
must report 288 fresh seen-family games and 96 fresh excluded-family games.

After all 20 evaluations complete, audit the outputs and write a review. Compare
the scaled results directly with
`reports/hog26_seed_transfer_review_20260912.json`. The question is whether fixed
architectures improve consistently when training data grows from 384 to 1,536
games, especially on late phases and fresh scenarios. The diagnostic remains
opened evidence and cannot pass the reserved calibration or final gates.

## Current model designs

The comparison is fixed by
`reports/hog26_scalar_pilot_comparison_plan_20260911.json`:

- Globals: 36 inputs, two 32-unit GELU layers, three WDL logits, 30 epochs, two
  seeds, four family folds.
- Tree: 2,381 scalar summary and causal-history features, absolute-error
  histogram gradient boosting, 100 iterations, one seed, four family folds.
- Entity/history: entity token and public-feature encoder, grouped pooling,
  64-unit frame projection, one 64-unit GRU, WDL and terminal-margin heads, full
  game backpropagation, 30 epochs, two seeds, four family folds.

Folds fit 1,152 games and exclude 384 games. Seeds are 1279501 and 1279502 for
neural models and 1279501 for the tree. There are no hyperparameter sweeps,
calibration fitting, epoch selection, or outcome-dependent changes.

## Constraints that matter

- There are no natural draws in either 384-game corpus or the current combined
  training corpus. Do not claim natural-draw calibration.
- Controlled symmetry draws are diagnostics. They cannot supply the natural draw
  rate.
- The opened 384-game seed-transfer set is permanently diagnostic.
- Preserve whole-family folds, paired-seat scenario clusters, complete-game
  undiscounted labels, and actor-visible inputs.
- A pooled gain does not pass if a required phase or subgroup regresses or lacks
  coverage.
- Tests, manifests, and memory probes establish implementation properties. They
  do not establish model quality.
- Do not start reserved collection, search, PPO, self-play, policy updates, or
  promotion from this comparison.

## Files to read in order

1. `docs/history/HANDOFF_NEW_THREAD_20260912.md`
2. `reports/hog26_active_objective_20260911.md`
3. Latest section of `reports/hog26_protocol_reassessment_20260908.md`
4. `/Users/sam/Library/Application Support/ClasherMonitor/comparison-status.json`
5. `reports/hog26_scaling_fitting_readiness_20260912.json`
6. The three scaling comparison manifests, summaries, fold reports, and logs
7. `reports/hog26_seed_transfer_review_20260912.json`
8. `experiments/hog26_scaling_eval/README.md`
9. `experiments/hog26_scaling_eval/fit_authority.py`
10. `experiments/hog26_scaling_eval/evaluate_scaling.py`

The main chronology is the authority for earlier defects and evidence. Read its
latest sections first. Earlier sections contain superseded decisions.

## Scheduled continuation

The local scheduler lives under
`/Users/sam/Library/Application Support/ClasherMonitor`. Its current prompt tells
the next turn to inspect the same supervisor and avoid duplicate fitting. A file
named `paused` in that directory disables new scheduled messages. Do not pause it
while fitting or post-fit review still needs supervision.

No backend goal feature is required to continue this work. The objective and
state in this file, the active-objective report, the supervisor state, and the
completion artifacts are sufficient for another harness or person to resume.
