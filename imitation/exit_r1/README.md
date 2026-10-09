# ExIt r1 B2/B3/B5

This is a separate adapter path. `imitation/t11/train.py` and the qualified
`imitation/model/` sources are not edited. No GPU training or live adoption is
launched by this package during B2 generation.

`emitter` runs level11 S6 physical games against W, released-v1, baseline search,
and scripts. W receives only `Information` (public packet, own HUD, public enemy
events), a deck prior, and independently sampled root/RNG. The public sensor and
replay auditor may see the physical game; hidden opponent data never reaches a
player. `D1Tracker`, `model_packet`, and the v5 mask are the gate-c implementations.

Every game is an independent, SHA-sealed packed v6 shard: `train/*.npy`, ragged
entity offsets, a deduplicated big-bit-order mask table, compact v5 columns, D1,
hard chosen labels, final {-1,0,1} outcome and provenance. Additional ragged
`root_offsets`, `root_actions`, `root_scores`, `root_valid` preserve actual native
scores, including screened-out candidates (valid=false) and timedWAIT IDs.
`teacher_search_action` preserves the original timedWAIT while `expert_actions`
expands it into5tick per-pollWAITs. Pending-command rows are flagged separately.
Only terminal games are sealed. `replay.json` records both players' submissions,
execution acceptance and public events; acceptance rebuilds the d27 queues from
labels and reproduces every observed byte and final winner.

`TeacherStore` verifies shard SHAs and exposes the qualified vector batch adapter,
with a teacher-only rounding correction to match the scalar NumPy2 serving path.
The human loader remains unchanged. Teacher loss uses softmax(root score/T),
aggregates WAIT aliases, and computes gate plus conditional card/tile CE, with
rare-play weighting and optional outcome regression. Pending-command WAITs are
excluded because the gate-c packet has no pending-command feature.

Student launch (fill coordinator-owned frozen input paths; do not duplicate jobs):

```sh
python -m imitation.exit_r1.train \
  --init-checkpoint SELECTED_V2_OR_RELEASED_V1.pt \
  --human-store V2_STORE/train --assets V2_ASSETS.npz \
  --teacher-root HOST_GENERATION_DIRECTORY --teacher-ratio .5 \
  --temperature .1 --play-weight 4 --value-weight 0 \
  --steps 4883 --batch-size 8192 --microbatch 7168 \
  --output FRESH_STUDENT_DIRECTORY
```

Use ratio0 for S-human and ratio1 for S-teacher. The checkpoint is a required
parameter, never an implicit dev selection. Mixed indices are deterministic by
seed/step; human epoch eligibility and waitIPW match T11, teacher rows are uniform
across sealed shards. Optional value checkpoints include an extra value head;
strip that head into a base `SetPolicy` before using the standard proposer loader.
Atomic checkpoints retain optimizer/EMA/scheduler/RNG and the step cursor;
resume checks input and recipe hashes. Human ratio0dispatches to the unchanged
qualified optimizer, preserving effective-batch normalization exactly.

Capacity adapter:

```sh
python -m imitation.exit_r1.capacity train --width 192 \
  --store V2_STORE/train --dev V2_STORE/dev --assets V2_ASSETS.npz \
  --qualification T11_STORE_PASS.json --output FRESH_CAPACITY_DIRECTORY \
  --batch-size 8192 --microbatch 7168 --workers 1
python -m imitation.exit_r1.capacity probe --checkpoint RELEASED_V1.pt \
  --widths 192 288 384 768 --iterations 1000 --core 63 --output latency.json
```

Capacity fitting reuses the qualified human trainer only inside that new process;
config/sampling substitutions do not edit or affect frozen T11. Run the matched
row dev check by25% of schedule; `capacity.kill_scan` requires gain>=.005 to
continue. Width192alone passed the measured<=15ms proposer budget. Wider models
are offline-only candidates. Student `screen` kills play recall<50% of teacher
or fallback delta<=0vs v2. These utility decisions need actual coordinator-owned
game/dev measurements; this package does not infer acceptance from NLL.

Generation processes run under setsid/nice>=10/SCHED_IDLE and taskset via
`launch_one.sh`. 08uses nice19and cores0–125. STOP is polled inside games; memory
below24GiB or any worker failure stops the host. `fleet` is a stdlib-only, light
05controller that sums completed roots every30seconds and writes all three owned
STOP files at6M combined roots. Stop/exit JSONs and source/native/input hashes
are retained under `/mpac/sdicks02/jobs/clasher/`; no data belongs in git.


Student screen (B4 plan freeze belongs to the coordinator):

1. Stage sealed host games into distinct subdirectories under /mpac/sdicks02;
   verify rsync checksums against source SHA manifests. Pack with
   `python -m imitation.exit_r1.pack --roots STAGED_03 STAGED_04 STAGED_08 --output PACKED_TEACHER`.
   Do not train from thousands of individual game mmaps. Packing preserves
   ragged entities/root scores, mask mappings, source seals and game boundaries.
2. Fine-tune the three ratios0.5/1/0 from the same pinned checkpoint, using the
   defaults above plus `--warmup 2000`. Select final-step EMA, never report-seed
   outcomes. GPU jobs must use the current host release/lease wrapper and caps;
   keep MemAvailable24GiB. A packed teacher root works with `--teacher-root`.
3. The coordinator freezes `STUDENT-SCREEN-PLAN.md` and the passed seed audit.
   Bind final checkpoints and the qualified E1 native binary with
   `python -m imitation.exit_r1.freeze_screen --plan PLAN --plan-sha256 SHA
   --seed-audit AUDIT --init INIT --S-mix MIX --S-teacher TEACHER --S-human HUMAN
   --native E1_NATIVE.so --output EXECUTION_FREEZE.json`.
4. Run one `screen` process per assigned home core, under the same setsid,
   nice/SCHED_IDLE/taskset limits. Pass `--freeze FILE --freeze-sha256 SHA`,
   `--mode h2h|fallback --arm S-mix|S-teacher|S-human|init`, `--offset I
   --count N --output FRESH_CASE_DIRECTORY`. Mode fallback includes the common
   init-W reference. A 200ms wall clock includes observation, fallback and top8
   proposer; only complete E1 roots count. Reporting ranges are audited;
   `--smoke` uses separate seeds and a separate output.
5. `--mode teacher --arm init` emits the64 held-out B2 teacher games on their
   own seed range. Pack that slice, then run `--mode agreement --arm ARM
   --teacher-store HELDOUT_PACK --assets ASSETS` for each student. The runner
   checks the exact held-out seed set, reports root/poll recall and WAIT rates,
   top8/hard agreement, and whole-game bootstrap intervals.
6. Combine the three agreement JSONs into an arm-keyed diagnostics JSON; run
   `--mode reduce --arm init --games CASES --diagnostics DIAGNOSTICS --output
   REPORT.json`. Missing/nonterminal/identity-mismatched cases fail closed.
   Output includes256-game H2H intervals,600-seed paired intervals and the
   frozen recall/WAIT/CI kill decisions. No multiplicity adjustment.

The new seed inventory wrapper imports the unchanged gate seed auditor and
pins all source inventories/formula contexts. It uses streaming hashes and a
proven equivalent prefix filter for the proposed target intersections. Retired
02/07/18 are explicitly covered through committed formulas and mirrored/archive
provenance; the coordinator-approved exploration exception is documented in the
small receipt. No reporting game runs before the coordinator freezes both SHAs.
