# Scripted warm-start execution interface

The executable is `scripts/run_council_warmstart.py`. It uses the learner's strict council pilot TOML and shared readiness admission guard. No real demonstration collection or gameplay fitting ran while implementing this interface.

```sh
.venv/bin/python scripts/run_council_warmstart.py \
  --config /absolute/path/to/pilot.toml \
  --admission /absolute/path/to/passed-tier-a-receipt.json \
  --seed 2901 \
  --output /absolute/path/to/scripted.pt \
  --decisions 50000 --epochs 1 --batch-size 128 --device cpu
```

The seed must be one of the three configured pilot seeds. The decision ceiling must not exceed the TOML ceiling or 500,000 opportunities and must allow two worst-case complete games. The current minimum is 2,402. Collection reserves 1,201 opportunities before starting each match, so it can finish without exceeding the ceiling. The final unused allowance can be up to 1,200 opportunities. Only the learner seat counts toward the budget; the terminal context row is excluded.

The standalone CLI reexecutes with the configured source path and game-data directory before importing project code. Direct Python callers must already run in that fresh environment. Admission is checked before creating an environment or output directory and again before fitting. A changed source/config invalidates fitting while leaving retained game evidence intact.

## Collection

Only the immutable training deck role is sampled. Both decks use level 11; mixed-level teacher data fails closed. Public scripts use balanced, pressure, and defense styles. They receive the clean public-v4 projection and label-independent public mask. The collector uses the effective 6,001-tick full-match horizon, rejects shortened games and defense scenarios, and never publishes an unfinished game as complete.

Every five-tick opportunity is retained, including waits. Rejected commands remain in recurrent context with their original submitted action, but their targets are unsupervised. Submitted ticks, world positions, acceptance flags and accepted-command ticks are recorded independently. Effective deployment timing remains unknown and is recorded as -1, rather than inferred from command acceptance.

Per-game provenance records the seed, seat, styles, initial decks, learner/opponent parent families, and training role. An internal imitation training/validation split is assigned by parent family before games. Both decks in each game come from the same internal split. This diagnostic split uses only training-role families; it does not consume the declared development or acceptance decks.

Each complete game receives an immutable NPZ and JSON receipt. A merge uses temporary disk arrays and removes unused entity padding before compressing the aggregate corpus. It retains all opportunities and terminal context, without play/wait weighting or identity remapping.

## Fitting and checkpoints

The fitted policy starts fresh with the exact council configuration supplied by `build_council_model_config`: width 128, four heads, four actor layers, two critic layers, LSTM width 256, public-v4 levels/confidence, four history slots and eight seen-card slots. The observation domain is `simulator-exact` with the v4 clean projection, matching the council rollout path. It does not enable the older stochastic camera degradation path.

The existing imitation fitter now accepts semantics version 4 and an explicit fresh model configuration. For council sequences it reconstructs the current-weight full episode prefix before each shuffled optimizer chunk, preserves the real episode-start flags, and retains final short chunks by padding only their unsupervised terminal row. Evaluation runs each episode chronologically with uninterrupted recurrent state. Augmentation and play/wait reweighting are disabled on this path.

Outputs are the requested fitted checkpoint, `<stem>-random-control.pt`, and `<stem>-demonstrations/` containing the plan, games, aggregate corpus, collection receipt, and final result. Both checkpoints record game-data, strategy, source-inventory, training-role, admission, and warm-start-plan SHA-256 digests. Their initialization metadata distinguishes public-script imitation from oracle imitation.

`--resume` requires identical admitted plan bytes and unchanged complete-game hashes. It resumes after complete shards without relying on prior RNG state. An incomplete shard publication fails for audit rather than being overwritten. If fitting was interrupted after its control checkpoint was saved, a fresh fitting retry retains that file and writes a new numbered control checkpoint. Completed fitted checkpoints are never overwritten. Fitting retries restart from fresh seeded weights; this is not optimizer-state resumption.

## Checks

Focused tests cover rejection before environment/output creation, bounded synthetic orchestration, complete-shard merging, predefined family splits, level/confidence preservation, v4 model configuration, matched control provenance, prefix/unchunked equivalence, chronological evaluation, and a tiny synthetic optimizer update. The synthetic fixtures mock match completion and do not provide gameplay or teacher-quality evidence.

The focused suite passed 29 tests. `git diff --check` passed for the changed existing sources. Admission and real full-game execution remain prerequisites for actual warm-start production.
