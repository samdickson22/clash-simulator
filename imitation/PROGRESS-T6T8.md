# T6/T8 implementation and plumbing qualification

Updated 2026-10-08 UTC. **Requested synthetic-checkpoint qualification complete.**
No model-strength or gate outcome claims. Confirmatory gates are not frozen or
played; their checkpoint fields remain TBD pending T5.

## Final immutable snapshot

Tree SHA256: `e3c60ef30743427aa8b654d3327fe0a567791a78221c90468181c2ab70a6cc90`.
- 127x05 and 127x03: `/mpac/sdicks02/repos/clasher-eval-snapshots/e3c60ef30743427a/`
- leased 127x11: `/mpac/sdicks02/repos/clasher-lease/eval-snapshots/e3c60ef30743427a/`
- Per-file/source-commit manifest: `receipts-t6t8/final/snapshot-manifest.json`.
- Model source matches reference commit `43d895e069e5b6ce25229c2fefa140880869dce2`;
  manifest identifies every byte-identical committed file and pins other working
  files explicitly. No model source changes occurred during this qualification.
- Random full-size checkpoint SHA256:
  `8c5be4ab918e3829789952cbc8b0337182fa133f52626d26f2fb5268498f2bad`.

The snapshot is a real Python package, preventing namespace merging with mutable
shared model code. `CLASHER_EVAL_RUNTIME_ROOT` selects the existing engine/data
checkout separately. After the coordinator's authorization, no shared host
`imitation/` path was written. Only isolated snapshots, owned run outputs, and
an exact C56 prior/synthetic-checkpoint input copy on leased 11 were staged.
All transfers used `rsync -c`. The source, docs and collected evidence are in
the requested 127x05 checkout. No git commits or engine/gamedata edits.

## Final search smoke: PASS

20/20 full terminal games on leased 127x11, all using the final snapshot.
15,194 candidate decisions (including non-search cadence and forced waits):
- p50 **5.026539 ms**; p99 **200.362424 ms**; max **242.040966 ms**.
- **0 decisions >250 ms**.
- **0 mask-illegal actions for either side; 0 rejected candidate commands**.
- The unchanged scripted opponent had **3 engine-rejected commands**, retained
  separately. These were public-mask-legal; do not conflate them with model
  illegal actions or claim zero rejections across both controllers.
- The first eight model-driven games additionally checked **5,909 D1/model-input
  rows byte-for-byte against SidecarObserver**, all exact.

Inference/feature construction, D1/history, sensor conversion, prior update,
candidates, root reconstruction, native search and joins count inside each
200-ms deadline. The Rust scorer uses two threads; Torch/BLAS uses one.
Proposal-only p99 was 16.908 ms under four simultaneous search processes. This is
reported as measured; it is not a claim that T4's separate isolated <=15-ms
proposer benchmark passed. Gate (b)'s comparison to A p99 remains for the real gate.

Lease-aware launcher `t6t8-search-final` exited 0. Four workers used disjoint
three-core sets (0–2, 3–5, 6–8, 9–11), all nice 10. The supervisor recorded peak
six processes and 4,992,299,008 bytes RSS; no console user, reclaim or expiry.
All owned jobs exited. The coordinator's pre-existing lease remains intact.

## Final standalone adapter smokes: PASS

All ran on 127x03 with the same final snapshot and random checkpoint, T=1 gate
sampling once per 250 ms, not the auxiliary intent-hazard head.
- P16 scripts: **4/4 terminal**, 2,729 decisions, zero illegal/rejected imitation
  actions, zero opponent rejections; exact seed/deck/seat pairing.
- H2H vs actual v7r4h s2902 1M: **4/4 terminal**, 2,285 decisions, zero
  illegal/rejected imitation actions, zero opponent rejections. Fixed physical
  decks/controller swaps checked from actual game receipts. v5/v4 mask
  asymmetry is recorded in each receipt.
- C56 scripts: **4/4 terminal**, 2,944 decisions, zero illegal/rejected imitation
  actions. Two unchanged script commands were engine-rejected (mask-legal),
  retained. Candidate deck membership in the frozen eval role and opponent deck
  membership in train were checked for all four games, including both seats.

No wins/scores are used by `audit_smokes.py` or claimed here. Native P16 evaluator
logs retain raw plumbing outputs, always tagged as synthetic in their receipts.

## Exactness and necessary CPU repair

Earlier independent replay verification passed on eight Stage 5 seeded C56
worlds: **7,304/7,304 D1 rows and collated model-input tensors byte-identical**.
Every saved public-stream replay reproduced its row hashes. Receipt:
`receipts-t6t8/skew-tensors-verification.json`. Four lightweight adapter tests
also passed from the first isolated snapshot.

Initial search runs revealed >250-ms work in the existing Stage 5 opponent
posterior BEFORE model inference. The owned `ExactFastPrior` replaces small
row-wise NumPy reductions/sorts with column operations. BOTH A and B use it,
so proposal quality remains their only algorithmic difference. No engine or
base Stage 5 source was edited. Posterior row order, state arrays, weights,
cumulative sums, resource arithmetic, derived facts, sampled states and RNG
state were verified against the original on eight recorded streams /328 events,
plus ability/Collector and phase-boundary cases. Parity is exact; observed
worst update decreased from 178.629 ms to 66.504 ms in that verifier.
Receipt: `receipts-t6t8/prior-parity-r1.json`.

Arm B preserves Stage 5b A's actual post-dedup candidate count. A originally draws
16 BEFORE script deduplication; B replaces up to eight unique additions with
imitation and fills to that same count, asserted at each searched root.

## Retained attempts and technical corrections

- `isolated-r1`: 03 search stopped after four complete games, three >250-ms
  decisions. Verified owned PID 3465080 was sent SIGTERM; exit 143 and all
  completed/partial evidence retained. No outcomes inspected for this decision.
  All three initial standalone routes completed four games with legal actions.
- `isolated-r2`: 11 original-prior search completed 20 games, four >250-ms
  decisions; zero candidate illegal/rejected commands, eight script rejections.
- `isolated-r3`: shared exact-fast-prior search passed 20 games: p50 4.885 ms,
  p99 200.380 ms, max 236.535 ms; zero overruns/illegal/rejected commands.
- Receipt review then corrected the C56 SMOKE harness's seat-1 deck assignment
  to keep the eval-pool deck with the candidate. The confirmatory runner already
  had this swap. All four routes were rerun on the final single snapshot; the
  final results above supersede neither erase nor hide earlier measurements.

## Files and launch readiness

Runtime code: `imitation/evaluation/{paths,snapshot,d1,events,candidates,search,
fast_prior,standalone,p16_adapter,run_p16}.py`.
Preparation/launch: `register.py`, `seed_audit.py`, `run_gate.py`.
Verification: `smoke.py`, `skew_replay.py`, `verify_skew_tensors.py`,
`verify_prior.py`, `synthetic_checkpoint.py`, `audit_smokes.py`, tests.

Authoritative final evidence: `receipts-t6t8/final/{summary,completion}.json`,
per-game receipts, legality/role audits and launcher exit receipts. All paths
are under this task's ownership. Raw outputs also remain on their source hosts.

PREREG drafts: `imitation/gate-b/PREREG.md`, `imitation/gate-c/PREREG.md`.
Game counts, arms, seed formulas/audit, analysis, bars and decision rules follow
DESIGN §§5.2/5.3. The common exact-prior CPU optimization is explicit. Checkpoint
SHA256 remains **TBD**. Existing prospective schedules are unfrozen.

Exact snapshot, smoke, audit, freeze and confirmation commands are in
`imitation/evaluation/LAUNCH.md`. When T5 selects a checkpoint, re-snapshot the
final model/evaluation source, requalify any changed model behavior/timing, and
freeze its full tree SHA256 in BOTH PREREGs/manifests before confirmatory games.
The final docs and read-only analysis utility added after game launch do not
modify the qualified snapshot. Do not silently relabel the tested source tree.

P16 uses the checkout's Python engine and the existing P16 deck/script/seed
protocol. This is not a claim of byte-identical engine source to the historical
pilot-runtime-v4 snapshot; actual runtime/gamedata are pinned at gate freeze.
