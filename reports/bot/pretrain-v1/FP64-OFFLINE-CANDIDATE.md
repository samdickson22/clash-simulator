# FP64 offline qualification candidate

This is an engineering candidate based on `ac3410d8b`. It does not admit FP64 to
production, choose model size or weights, change the objective, or authorize RL.
The strict absolute `2e-6` actor likelihood/value gate remains unchanged.
[NUMERICAL-QUALIFICATION.md](NUMERICAL-QUALIFICATION.md) records why FP32 controls
and explicit math attention failed, and the limitations of the forward-only FP64
probe. That probe recomputed distributions; the harness here captures actual
production Session samples.

`LearnerConfig(precision='float64', test_only=True)` verifies the selected FP32 BC
anchor before converting its network. The frozen human anchor and AdamW are then
constructed from that converted network. The source anchor file SHA remains the
identity of the selected BC file. Policy SHA covers configuration, tensor dtype,
shape and bytes, so the converted policy has a different identity. AdamW moments
follow parameter dtype; its float32 scalar step counter retains PyTorch's normal
contract. The likelihood helpers still cast logits to float32.

The default remains FP32. Its recorded config, parameter identities, and forward
outputs are preserved. The only model change replaces the 22 explicit float input
casts with casts to the class-token dtype. Session sampling semantics and all
actor/queue array schemas are unchanged. PolicyUpdate and learner checkpoint
loads reject wrong stored dtypes before PyTorch can silently cast. Candidate
checkpoints require matching test-only precision, source anchor, config and
runtime provenance on resume. Production `policy.load` refuses non-FP32 weights
and FP64 qualification checkpoints.

## Local checks

`bot/pretrain_v1/tests/test_fp64_qualification.py` covers real retained FP32
features against the exact landed model, actual Session samples at 128/256 and
short/mixed-width batches, four toy updates including PPO with finite policy
gradients, immutable source arrays and frozen anchor, checkpoint roundtrip and
wrong dtype/provenance rejection, and PolicyUpdate/NPY queue precision.
The toy budgets are fixtures, never registered RL training.

Run the focused suites with an existing local pytest installation. The pinned
2.7.1 environment has no pytest; this worktree uses symlinks to existing pure
Python pytest dependencies under `qualification-artifacts/pytest-local-deps`,
without modifying either environment. Before CPU work, check for duplicate
qualification jobs, `MemAvailable >= 29 GiB`, load1 <= 90, and use nice >= 10.

```bash
nice -n 10 env CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH="$PWD/qualification-artifacts/pytest-local-deps:$PWD/src:$PWD" \
  /mpac/sdicks02/repos/clasher-pv1-rl-env271-20261022/bin/python -m pytest \
  bot/pretrain_v1/tests/test_fp64_qualification.py bot/pretrain_v1/tests/test_rl_learner.py \
  bot/pretrain_v1/tests/test_stream_actor.py bot/pretrain_v1/tests/test_rl_coordinator.py \
  bot/pretrain_v1/tests/test_rl_math.py -q
```

## Actual engine capture and learner checks

Run from the candidate worktree. These commands make fresh directories only under
its ignored `qualification-artifacts/` directory. The harness verifies its source
digest before and after each run, verifies the exact supplied anchor SHA, and
records imported module origins. It loads the candidate's local bootstrap, whose
package override points to this candidate. The old immutable bootstrap would
instead override the candidate with old code. Runtime and other actor modules
come from the supplied source pins and their verified joint manifest.

The capture plays one game at the real account levels against R3a, with the
production Session, true terminal rewards and existing boundary-declined
semantics. Its fixture actor limit is 4000 polls and chunks are 128 rows; it does
not call a learner update. It records its own trajectory hash rather than assert
FP32's old command hash, row count or outcome. The selected anchors below are the
old v3 evidence inputs, not a choice of the final RL starts.

```bash
PY=/mpac/sdicks02/repos/clasher-pv1-rl-env271-20261022/bin/python
SCRIPT=bot/pretrain_v1/checks/qualify_fp64.py
SOURCE_SHA=$($PY "$SCRIPT" source-digest)
ANCHOR=/mpac/sdicks02/scratch/pretrain-v1-dev/sweep/anchors/S100/anchor.pt
ANCHOR_SHA=e9366c55503f3d826fa6add0beb9880883be9274158e728f03f932dcd19acbc7
SIZE=S100
OUT="$PWD/qualification-artifacts/$SOURCE_SHA"

nice -n 10 env CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  "$PY" "$SCRIPT" capture --source-sha256 "$SOURCE_SHA" --size "$SIZE" \
  --anchor "$ANCHOR" --anchor-sha256 "$ANCHOR_SHA" --threads 1 --game-seed 2026102204000100 \
  --runtime /mpac/sdicks02/repos/pretrain-v1-rl-runtime-0dcab45f7-joint \
  --actor-source /mpac/sdicks02/repos/pretrain-v1-rl-actors-0dcab45f7-joint \
  --manifest /mpac/sdicks02/scratch/pretrain-v1-dev/rl-readiness/joint-manifest.json \
  --out "$OUT/capture-$SIZE-cpu1"

nice -n 10 env CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  "$PY" "$SCRIPT" check --source-sha256 "$SOURCE_SHA" --size "$SIZE" \
  --anchor "$ANCHOR" --anchor-sha256 "$ANCHOR_SHA" --threads 1 --device cpu \
  --capture "$OUT/capture-$SIZE-cpu1" --out "$OUT/check-$SIZE-cpu1" --update-fixture
```

For M, explicitly set `SIZE=M`, anchor
`/mpac/sdicks02/scratch/pretrain-v1-dev/sweep/anchors/M/anchor.pt` and SHA
`caa5f58ff250fdd689734ad80eb426e654ab4828ff4b08e655df7265e8486f7e`.
Repeat only `check` with `--threads 4` and a fresh output suffix for CPU4 against
the same actual CPU1 samples. No recapture is needed.

The optional `--update-fixture` uses the first two complete authentic chunks as
an explicit 256-row, effective-batch-256, microbatch-128, one-update warmup
fixture. It preserves their chronology, terminal flags, rewards and bootstraps;
runs the real learner update and checkpoint roundtrip; and verifies the unchanged
frozen anchor. It does not qualify production update cost, full PPO memory or the
registered 262144 x 32 budget.

## Parent qualification gates

The harness `check` supports `--device cuda` and records peak reserved bytes.
The parent can run the same captured inputs with the same PyTorch version,
`--threads 1`, the exact SHA arguments, a fresh output suffix and the selected
GPU's visibility. This implementation task did not access a GPU or remote host.
The pinned bootstrap hides GPUs only during CPU engine capture; the check mode
never invokes that bootstrap. Attention settings are explicit inside a context
and restored on exit; no import changes global kernel policy.

GPU and full effective-batch-2048 PPO updates, generated Session samples after a
real-size update, optimizer/activation/peak memory at registered shapes,
throughput, game rate, Mac CPU latency, and the exact next selected BC starts
remain unqualified. `check --update-fixture` is a small warmup fixture. The
four-update CPU contract test establishes the PPO code path only on a toy model.
New selected checkpoints require their exact explicit paths and SHA values; the
harness has no automatic anchor selection and does not wait for the pending M.
A passing offline candidate review grants no launch or adoption approval.

## Independent review and remaining resume limitation

Fresh independent GPT-6.1 Sol with high reasoning effort reviewed code commit
`bf96bd145f381367c667f639cc262326f58c87e1` against exact base
`ac3410d8bf5dadf3936db12c98e20fcfd9b4eb89`. It returned **GO for offline candidate
handoff only**, with no blocking findings, after inspecting the changed semantics
and the underlying numerical evidence. Review task ID:
`node:delegated-task:command%3Amcp%3A9947a035-0633-43c6-a05d-5790286884d5%3Adelegate-task%3Afp64-offline-sol-high-review-round1-20261022`.

The reviewer identified one inherited nonblocking P2: resume accepts an incomplete
subset of AdamW parameter states. Deleting initialized moments can silently restart
that parameter's history. This candidate checks present moments for dtype, shape
and finiteness, but does not establish their completeness or stage-specific step
counts. Fresh captures and fresh fixture updates do not exercise that corruption.
Before production resume qualification, require the expected initialized parameter
set and counters for the warmup/update stage, with deletion-corruption coverage.
The reviewer made no source edits and launched no checks or games.

## Completed CPU qualification measurements

The reviewed source remained unchanged at package SHA256
`2d9842c8d8ab9631767b8f9fc732b66bff9bcba282cba6228d04e69e2958e9f6`.
All 162 focused tests passed on PyTorch 2.7.1+cu118 in 62.34 seconds. The retained
real-feature baseline checks found byte-identical default FP32 trunk, gate, tile
and value outputs and identical canonical policy digests against the landed
`ac3410d8b` model for both sizes.

Exactly one fresh actual engine Session game ran per old v3 size, CPU1, GPUs
hidden, nice 15, preflight load below 4 and over 110 GiB available. S100 published 1183 polls;
M published 703. Both reached a true terminal with zero discards, zero rejected
commands and one boundary-declined row. Trajectory hashes happened to match their
old FP32 controls; no fixed trajectory hash, row count or result was asserted.
All imported pretrain modules were verified to originate in this worktree.

Both sizes passed the unchanged absolute `2e-6` gate on all actual Session rows,
for learner CPU1 and CPU4, each at microbatch 128 and 256. Maximum logp errors were
`7.75249269224787e-7` for S100 and `4.857857112128272e-7` for M. Maximum value errors
across those measurements were below `2.1e-14`. CPU4 reused the same immutable
CPU1 captures, with no additional games.

Each size also passed one real learner warmup update on its first 256 authentic
rows, two optimizer steps, and a checkpoint roundtrip with unchanged frozen
anchor and float64 AdamW moments. This is the explicit effective-batch-256 fixture
specified above. The constructor config reported by the forward checks retains
the registered budget; the distinct fixture config is saved in its checkpoint
and copied into [FP64-OFFLINE-RESULTS.json](FP64-OFFLINE-RESULTS.json). That receipt
records exact file hashes, configurations, per-batch errors and artifact paths.
It does not treat the fixture as a registered training-budget measurement.

Raw receipts, immutable NPY chunks, result JSON and fixture checkpoints remain
under this worktree's ignored directory
`qualification-artifacts/2d9842c8d8ab9631767b8f9fc732b66bff9bcba282cba6228d04e69e2958e9f6/`.
The code was independently reviewed before these measurements. No source changes
followed review; this section and the compact JSON receipt record later results.
The outstanding parent gates and inherited resume limitation above still apply.
