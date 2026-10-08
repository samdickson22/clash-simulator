# T5 execution and analysis

T4's throughput-qualified files are immutable dependencies. `train.py` calls
the unchanged T4 `train.main`; its explicit dependency injection supplies a
policy factory, provenance-checked stores, row-index annotations, GRU store
binding and an interruptible dev loader. Sampling, iid shuffle, optimizer,
loss denominators, EMA, scheduling and resumable checkpoint state remain T4's.
This adapter is additional T5 code, not a claim that T4 qualified the GRU's speed.

`noD1` masks token types3–13 and15–17 and zeros global numeric columns15–19.
Original public hand/next, seen cards, entity features, globals, champion button
and legal action masks remain. Deck information is still used to map auxiliary
targets; it does not enter noD1 features. Types have no positional embeddings.

`gru` adds a one-layer192-wide GRU. Every endpoint uses its current CLS plus
the preceding31 stored observation rows, in order, bounded by perspective
start. Missing pre-start history is absent, not repeated through the GRU.
The final valid GRU output replaces CLS for all heads. All current/past CLS
states use current weights and receive gradients. Trunks are activation
checkpointed with RNG preservation. Historical rows are deduplicated within
each endpoint microbatch; their encoding uses local8192 entity-count ordering
and a1024 history-only chunk (resource-r2 technical OOM correction). Endpoint sampling remains iid;
unsampled waits remain available as public context. Nothing is carried across
optimizer steps or perspectives. Dev and held-out evaluation use the same
sliding window with current EMA weights. Main's measured throughput is not a
prediction for this additional computation. GRU stays on home08.

`guards.py` verifies T4's canonical manifest, T5's full freeze, assets/store/
role pins. `preflight.py` checks who, host leases, occupancy and GPU headroom.
Leased runs get `--stop-at 2026-10-09T04:20:00Z`, leaving40 minutes to the
mandatory05:00Z exit. SIGTERM during training saves the qualified full state;
SIGTERM at/during dev exits via the saved pre-dev checkpoint. Resume exactly
the same run, with a fresh launcher label and verified checkpoint, after the
prior process has exited. Never resume a still-running PID or a selected
best-dev checkpoint for continuation; use the latest resumable step/epoch.

Selection sequence:

1. `select run`: completed run's lowest uncalibrated EMA dev joint NLL, earliest
   step on ties. Emit checkpoint SHA256 and log/complete receipt hashes.
2. `select combine`: exactly five registered run receipts. Choose the main seed
   by dev NLL, then earliest step, then lower seed.
3. `score calibrate`: dev-only cap100000/PCG64 seed1, three qualified temperature
   fits. `select release` binds all five checkpoints and temperature files.
4. `score score`: requires release, fixed role/content pins and exclusive role
   claim beside checkpoint. Each1024-row forward commits raw/calibrated metrics,
   T3-aligned frequency metrics and row/perspective identities atomically.
   A failed technical attempt can resume only with a recorded reason; all
   committed batches are reused. Completed roles cannot be scored again.
5. `analyze`: reads hashed committed statistics, never loads a model. Exact
   10000 whole-perspective resamples, PCG64 seed2026100805, shared draws for
   paired metrics and all cards. Undefined conditional resamples are counted.
   `report` assembles gate tables, all seeds/ablations and supplied compute/curve
   summaries into the requested Markdown artifact.

The T5 frequency scorer matches T3 float64 probability normalization and final
1e-300 NLL clipping, including zero training counts. T4's logit helper instead
clips counts at1e-30; using that helper would change the baseline. This difference
was caught and corrected before fitting/scoring. Full dev alignment reproduces
all four T3 baseline NLLs within1e-10. No baseline is refitted.

Validation runs on04 only: synthetic causal/boundary/noD1/gradient/hash/metric/
whole-cluster tests; bit-identical checkpoint resume for all variants; eager
bf16 forward/backward; SIGTERM at dev entry. Synthetic artifacts are retained.
There are no additional fitted real-data trials and no changes to T4 files.

## Resource-r2 technical continuation

Initial13/14 jobs exceeded shared-process RSS and were safely checkpointed;
initial GRU08 OOMed during step3 before a checkpoint. All evidence is retained.
One loader worker plus MADV_DONTNEED on copied read-only mmap inputs bounds
RSS without data/tensor changes. Current endpoint microbatch remains7168,
effective8192; only added GRU historical encoding chunks drop to1024. GRU
checkpoints every10steps in addition to epoch checkpoints. No objective, seed,
sample membership, history length, architecture, selection, calibration or bar
changes. Qualified T4 files are unchanged. Technical synthetic replay across
old4worker -> new1worker is bit-exact for all variants; an8192-row real-train
GRU forward/backward with a no-update optimizer passed (no parameter fitting),
peak allocated27555.244MiB/reserved37484MiB. Checkpoint provenance migration
compares every non-hash payload field, retaining originals.
