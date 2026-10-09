# Operational amendment 04: validation inference sharing

Coordinator decision labeled **2026-10-08 19:58Z**, received in this thread;
implementation record begun 2026-10-08 19:53:51 UTC (the first live clock reading
preceded the coordinator's supplied label). Recorded before any selection or
heldout opening. Frozen PREREG, split, training weights and selection rule remain
unchanged. This amendment authorizes an equality-gated candidate, not adoption.

The coordinator authorized one shared inference pass per epoch over all64
validation matches, compact persistent decoder inputs with file SHA manifests,
and parallel CPU body/event grid post-processing. Adoption requires bit-exact
counts/metrics and every non-path-dependent manifest field against the completed
epoch1/event0.5/body0.1 and0.2 cells, plus body0.3 when complete. A failure must be
reported and retain the original path; no silent approximation or retuning.

## Exact factorization under investigation

Pinned PixelPerception first runs the encoder, then body-threshold-specific
tracking, then supplies those track births to the learned temporal head. Thus a
single final event tensor from one body branch is not a sufficient cache for the
others. The candidate shares the encoder and the temporal operations BEFORE the
birth projection/concatenation, while retaining the original classifier/output
tail for every body threshold. Each branch keeps its own unchanged PixelPerception
ring, tracker, causal own-HUD spell corroboration and EventFusion/NMS state.

`shared_temporal_v4.py` duplicates the pinned operation order without changing the
original source. `shared_model_v4.py` reuses outputs only after exact equality
checks on the shared pixel/temporal inputs. No batching or fp16 conversion is used.
Future persisted decoder records must preserve exact values, ordering, ties,
birth/track state and per-card thresholds; lossy raw caching has no admission.

04 probe with the authenticated epoch1 backup and three synthetic feature/age/
mask cases:27 branch comparisons ×4 tensors =108 bit-exact comparisons PASS.
Changing births changed real checkpoint outputs; fp16 round trips changed raw
values. This is structural/numerical evidence only, NOT full-cell equality.
Real validation-match comparison is a separate bounded09 probe. It explicitly
excludes availability fields and cannot certify newly measured timing/counts.

Full64-match parity for all three completed cells, authentic availability and
all metrics/manifest comparisons remain REQUIRED and unmeasured. Reusing an old
completion journal to pretend new CPU work completed earlier is forbidden.
The original measured-completion replay remains the admitted fallback.

## Resource and continuation amendment

Before04:30Z, GPU work may use04 and live leased09/13/14/15; CPU work may use
home01/03 (at most80 of our processes on01, respecting T5) and eligible leases.
Leased work starts stopping04:30 and exits by05:00Z, with offhost04 backups at
least hourly. Leased caps, console rules, reclaim wrappers and roader exclusions
are unchanged. Check actual lease/usage before every launch.

**05:00Z is a leased-host exit deadline, not a global task deadline.** Thereafter
continue home01/03 CPU work.01/04 GPUs belong to T11 after05:00;08 remains T5.
The20-minute continuation persists until genuine final results/noise evidence.
The cleanup companion only verifies exits/receipts and self-deletes; it does not
cancel unfinished home work. Both app-owned schedule prompts were updated.

The existing1TB aggregate/300GB-host cache caps and200GB free floor remain.
996GB of reservations plus legacy/headroom are already assigned. Candidate cache
expansion must have a measured/reassigned budget before writes; the approved18
duplicate-retirement queue may not be bypassed. Initial probes retain only
compact receipts and use existing weights/caches, with no raw-output expansion.

Status: **candidate only; full equality PENDING; no accelerated selection
evidence, no actual selection seal, and no heldout opening.**

Coordinator storage follow-up labeled2026-10-08 20:06Z: aggregate1.1TB approved,
up to1.3TB if needed. Per-host300GB and200GB free floor unchanged; leased shards
retire within one day of lease end. Proceed without waiting for duplicate18
retirement. Initial raw-output reservations:20GB additional each on04/09/13/14/15
(total100GB); allocations become01=290,18=292,16=214,03=126,04=20,09=74,13=20,
14=20,15=40GB,total1096GB plus legacy/headroom within1.1TB. Record any further
allocation before writes;1.3TB is a ceiling, not an untracked allocation.
