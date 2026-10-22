# Offline PPO and Session qualification

This is a test-only fixture for the pinned candidate based on
`1ebd0b0a3939761ae2d33eadeed27422eee042f8`. It changes no learner, optimizer,
engine, objective, model architecture, or production launch gate.

`qualify_ppo_session.py` collects 2,048 genuine engine polls for each of four
versions. The unchanged Learner performs three critic warmups and then joint
PPO, with effective batch 2,048 and microbatch 128 or 256. It then collects
256 fresh CPU Session polls under the updated version 4 weights. Total actor
budget is 8,448; only 8,192 polls enter training. This is not the registered
262,144 polls per update or 32-update run.

One CPU actor, one learner, and one local AtomicChunkQueue run synchronously in
one process. The actor model is separate from the learner model. Quota callbacks
stop the real engine clock, perform the update, and acknowledge exact FP64 CPU
weights before the pending poll is observed by Session. The same live engine,
Session history, RNG, and command queue continue across an update inside a game.
After a true terminal, a new seed and Session begin. No engine serialization or
resume is implemented. Actual terminal rewards and the reviewed nominal-deadline
decline handling remain unchanged, including five-tick polls and 27-tick lag.

Every publication retains its queue receipt, source provenance, game seed, engine
tick, policy SHA, version, actor/forced rows, bootstrap, reward, and exact budget
counters. Per-update proofs include strict pre-update likelihood/value parity,
finite FP64 gradients, changed heads, optimizer step counts and moment dtypes,
unchanged anchor, elapsed update and collection time, and memory measurements.
The completed-game play-rate gate remains 15..80 accepted plays per 300 simulated
seconds. Throughput measures only this one R3a readiness opponent and excludes
barrier time. It is not full registered league throughput.

The final 256 original, immutable labels are checked on CPU and the requested
learner device at both batch widths 128 and 256 with absolute error <= 2e-6.
When `--device cpu` is used, GPU parity remains unassessed. A separate masked
wider-padding probe reuses those exact rows without altering any labels or
feeding padded copies to training. It is an invariance probe, not new engine data.

Memory reports apply to observed chunk widths, with maxima for ent/ev/rev recorded
for each update and the final capture. They do not cover the theoretical 256-body
maximum or a full production rollout. CPU RSS is the process high-water mark;
GPU allocated/reserved peaks reset before each learner update. Model/runtime
bootstrap memory and final post-update evaluation also contribute to process RSS.
Memory needs and run time are unknown until measured. No ETA is supplied.

The reviewed bootstrap verifies every pinned manifest file, 9,409 runtime entries
and 17,010 actor entries. It imports torch with CUDA hidden. This entry point
checks that CUDA remains uninitialized and its device-count cache is empty before
restoring the caller's original visibility, before any CUDA availability query.
A failed check stops the fixture. The actor stays on CPU. All imported pretrain
modules must originate from this candidate. The helper has no legacy runtime path.

Run only after the parent reviews and stages the exact source. Parent-provided
own02 staging is verified and idle as of 2026-10-22; this implementation task did
not connect there or launch an engine/model job there. Paths on own02 are:

```sh
RUNTIME=/mpac/sdicks02/repos/clasher-pv1-qual-runtime-0dcab45f7
ACTORS=/mpac/sdicks02/repos/clasher-pv1-qual-actors-0dcab45f7
MANIFEST=/mpac/sdicks02/jobs/clasher/pretrain-v1/fp64-qualification-staging-20261022/joint-manifest.json
```

From the staged candidate's root, set `PYTHON` to the verified full environment.
Set `SIZE`, `ANCHOR`, `ANCHOR_SHA`, `CFG`, and `POLICY_SHA` explicitly for the
new admitted checkpoint. `CFG` is a JSON file containing its exact complete model
configuration, and `POLICY_SHA` is the canonical policy SHA after verified source
FP32 weights are converted to FP64. The source anchor must be named `anchor.pt`
and have its matching admitted `selection.json`. There is no anchor selection,
fallback, capture import, or successful-artifact reuse. M selection is pending.

```sh
SOURCE_SHA=$("$PYTHON" -B bot/pretrain_v1/checks/qualify_ppo_session.py --source-digest)
nice -n 10 "$PYTHON" -B bot/pretrain_v1/checks/qualify_ppo_session.py \
  --test-only --dtype float64 --source-sha256 "$SOURCE_SHA" \
  --size "$SIZE" --anchor "$ANCHOR" --anchor-sha256 "$ANCHOR_SHA" \
  --model-cfg "$CFG" --policy-sha256 "$POLICY_SHA" \
  --runtime "$RUNTIME" --actor-source "$ACTORS" --manifest "$MANIFEST" \
  --device cuda --threads 1 --microbatch 128 --game-seed 2026102208000000 \
  --max-games 64 \
  --out "$PWD/qualification-artifacts/$SOURCE_SHA/$ANCHOR_SHA/ppo-session-cuda-b128-attempt1"
```

Use a new attempt directory for every invocation, including failures. For a
separate microbatch 256 run, choose a new game-seed range and output directory.
CPU-only trials use `--device cpu`. Guards require nice >= 10, MemAvailable >=
29 GiB, and load1 <= 90 before bootstrap, after bootstrap, at games and barriers.
The run is bounded by the fixed poll budget, 64 games maximum, and unchanged
6,001-tick game limit. Any incomplete, stale, rejected, lost, nonfinite, or parity
failure stops the run without replacement data. Failed runs retain their counters
and artifacts. A budget stop may leave one unfinished game without an outcome;
published next-state-complete rows remain valid, and discarded pending rows are
counted exactly. On budget unwind the helper reads the pinned match function's
exception traceback to retain its actual channel diagnostics, executed play log,
command hash, and final tick. It does not patch the match runner or command queue.
The unfinished game must pass the same zero-policy-rejection gate as completed
games, and gets no completed-game play-rate or invented terminal outcome.
No process control, remote transport, leases, or GPU probing is
part of this implementation handoff.

Focused tests use a toy-sized real PolicyV1 and real learner gradients. Mock
engine records exercise barrier accounting only and never count as qualification.

```sh
nice -n 10 env CUDA_VISIBLE_DEVICES='' "$PYTHON" -B -m pytest -q \
  bot/pretrain_v1/tests/test_ppo_session_qualification.py
```

Remaining gates include measurement on both exact next admitted anchors, a full
262,144-row rollout memory bound, full league games/hour, six-hour soak,
recycle/continuation, Mac latency, and precision adoption. A passing offline
fixture resolves none of these automatically. The separate AdamW moment-resume
fix is not part of these changes. These checkpoints are audit artifacts, not a
claim of engine continuation or optimizer-resume qualification.
