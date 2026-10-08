# T6/T8 progress

Updated 2026-10-08 UTC. Implementation is present; **full smoke/timing qualification is incomplete**.
127x05 `/mpac/sdicks02/repos/clasher` is the source and requested mirror checkout.
No engine/gamedata edits, git commits, outcome claims, protected-host access, or process killing.

## Implemented files

All new runtime code lives in `imitation/evaluation/`:
- `d1.py`, `events.py`: public accepted-event sensor and token-valued serving D1.
- `search.py`, `candidates.py`: Arm B on Stage 5b's existing Rust fair deadline scorer,
  200 ms/two workers; sensor/D1/inference inside the caller's absolute deadline.
- `standalone.py`: T=1 gate/card/tile sampling every five ticks; explicit T=1
  also overrides checkpoint calibration temperatures, without hazard rescaling.
- `p16_adapter.py`, `run_p16.py`: existing P16 command generator/evaluator adapters,
  native s2902/v4 comparator behavior; separate imitation v5 observation/mask;
  fixed physical worlds for H2H controller swaps. Receipts record asymmetry.
- `register.py`, `seed_audit.py`, `run_gate.py`: prospective schedules, hashed
  fleet-audit/freeze prerequisites and resumable gate game launchers.
- `synthetic_checkpoint.py`, `smoke.py`, `skew_replay.py`, `verify_skew_tensors.py`,
  `summarize_smoke.py`, `test_adapters.py`, `test_policy_edge.py`: verification tools.
- `LAUNCH.md`: exact smoke, registration, audit and gate launch commands.

PREREG drafts: `imitation/gate-b/PREREG.md`, `imitation/gate-c/PREREG.md`.
Checkpoint SHA256 remains TBD. No gate is frozen and no confirmatory games ran.
Prospective schedules were generated on 127x03 and mirrored here:
- gate b: 320 H2H world pairs +128 script pairs used by each arm =1,152 games.
- gate c: 192 C56 script pairs, 64 per style; P16 generator supplies the other
  1,408 games (384 ×3 policies +256 H2H), for 1,792 total.
Seed namespaces are proposed only; full fleet seed audit remains for freeze.

## Verification completed

- Four light CPU tests passed on 127x05, including real-engine two-seat v5
  sample legality/event updates and P16 v4-infrastructure/v5-actor dispatch with
  fixed-world controller pairing. `receipts-t6t8/unit-tests.txt`.
- Eight full C56 scripted worlds on 127x03, seeds 880200–880207 (Stage 5 oracle
  seed/deck construction), alternating verified perspective. Actual deadline
  player computes D1 on its non-search cadence; scripts drive the games.
- **7,304/7,304 decision rows: all D1 keys, dtype, shape and bytes equal the
  independent SidecarObserver.** A second pass over each saved public event
  stream reproduces every serving-row hash.
- Saved both paths' D1 and actual public packets. The shared model feature
  adapter and collator then produced **byte-identical model input tensors on
  all 7,304 rows / eight games**. Receipt:
  `receipts-t6t8/skew-tensors-verification.json`.
- The original row-only run and the packet/tensor capture run both exited 0;
  receipts/logs retained. These are deterministic replay/adapter evidence, not
  model gameplay or strength evidence. Replays use the existing fleet runtime;
  no claim of identical outcomes to historical Stage 5 engine snapshots.
- Fleet launches: no console user, about 80 pre-existing Python processes;
  one additional nice-10 worker per run, sequential runs, both finished. A host
  snapshot is retained. No owned worker remains after the completed replays.

## Pending/blocker

127x03 has Torch, the Python/Rust engines and comparator checkpoints, but no
`imitation/model/` module. The user explicitly restricted fleet copies to this
task's own files. An asynchronous question requests permission to stage a
checksum-pinned dependency snapshot in a new owned directory, or an existing
fleet model snapshot path. **No answer has arrived; no dependency was copied.**
Only owned adapters/docs, generated synthetic checkpoint and receipts were synced
with `rsync -c`. No shared dependency file was overwritten.

The full-size random checkpoint exists on 05 and 03 at
`/mpac/sdicks02/tmp/t6t8-synthetic.pt`, but the CPU API dependency is still needed.
Consequently:
- search smoke: **0/20 model-driven games; not run**;
- timing p50/p99, decisions >250 ms: **not measured**, no timing pass claimed;
- P16-script adapter smoke: **0/4 full games**;
- s2902 H2H adapter smoke: **0/4 full games**;
- C56-script adapter smoke: **0/4 full games**.
Do not call T6/T8 done or launch a real gate on the basis of current evidence.

## Explicit implementation details for review

Stage 5b samples 16 BEFORE deduplicating scripts, so its actual unique count can
be smaller. Arm B matches that exact post-dedup count, replacing up to eight
slots and filling with the same random draw. This preserves A unchanged and
makes candidate count equality assertable. The PREREG documents the convention.

P16 command/deck/seed protocol is reused, but the adapters currently run against
the checkout's Python engine, not an asserted byte-identical pilot-runtime-v4
engine. Runtime/gamedata are pinned at registration. If literal frozen-v4 engine
identity is required, that compatibility qualification remains necessary.

The final freeze makes a checkpoint-filled immutable PREREG copy; source drafts
remain TBD. The seed audit requires all five allowed historical inventories plus
explicit review of generated seed ranges, and fails closed on missing evidence.
