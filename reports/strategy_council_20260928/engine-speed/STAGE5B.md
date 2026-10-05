# Stage 5b: PASS

The deadline player completed all 384 preregistered terminal games. Strength gate PASS; strict 250 ms wall gate PASS.

## Implementation

The Stage 5 public model, scripts, engine, prior and candidate set are unchanged. The live adapter in stage5b-r3/deadline_player.py uses a configurable 200 ms wall deadline and two Rust candidate workers. The driver starts the clock before public sensor conversion. Work follows the existing candidate priority: script top choice, no-op, script ranks, ability/policy proposals, then samples. Each candidate requires all three opponent-style rollouts; incomplete scores are discarded. Workers check the deadline between ticks and continuation decisions and join before return. If no candidate finishes, the first public-legal script candidate is returned. The Stage 5 sequential path remains available with deadline_seconds=None and threads=1.

Results reduce in original priority order with the original 1e-9 tie tolerance. For a fixed completed candidate set, results do not depend on thread completion order. Scheduling can change which candidates finish before the deadline. This cooperative cutoff is not an operating-system realtime guarantee under arbitrary preemption.

## Tests

All 200 Stage 5 roots reproduce the exact recorded action, ordered candidate scores, continuation digests and full MT state trace hashes with 1, 2 and 4 workers. Eight tests pass: two tests exercise the actual driver setup for fixed-world head-to-head and Stage 5 continuity pairing, plus the six original focused tests, including the Stage 5 stunned-push regression, expired-budget legal fallback, mid-rollout cancellation, partial-result exclusion, priority ties and thread invariance. The parity receipt is stage5b/parity.json. The Python engine, public scripts and gamedata entry hashes pass preservation checks.

## Preregistered results

PREREG-C56-deadline-r3.md, schedule.json, seed-audit.json and evaluation-manifest.json precede every evaluation game. Primary head-to-head: 128 wins, 0 draws, 256 games; score 0.500000, paired-matchup 95% CI [0.500000, 0.500000]. Required score >=0.47 and lower bound >0.42. Continuity against C56 scripts: 116 wins, 0 draws, 128 games; score 0.906250, CI [0.843750, 0.960938]. Confidence intervals use 10,000 percentile bootstrap resamples of paired means, RNG 40404043. 

For head-to-head, each paired world keeps its two decks fixed and swaps the deadline and baseline controllers, so both controllers use each deck once. Human decks follow the same role-held-out eval/eval_ood planning and train opponent catalogs as Stage 5, restricted to deck identities supported by its train-only prior; this is not deck-identity holdout. All 384 final-registration outcomes are retained, with no interim strength analysis or player retuning.

The first attempt stopped with 59 terminal receipts when the unchanged Stage 5 baseline rejected an unsupported held-out opponent deck on pair 27. Its receipts and source pins remain in stage5b/. A second attempt stopped with 111 terminal receipts after pre-outcome design review identified a deck/controller confound in holding the family-selected deck with the candidate in both seats. Its evidence remains in stage5b-r2/. No strength results were inspected in either interrupted attempt. The final registration uses entirely fresh seeds, supported human decks, and identical seeded worlds/decks with controllers swapped between the two games. Both interrupted attempts are excluded from acceptance because neither completed; no completed confirmatory outcome was selected or discarded.

Every one of the 128 paired matchup means is exactly 0.5, so the registered paired bootstrap has zero observed variance and returns [0.5, 0.5]. A descriptive final audit found identical action logs, terminal ticks and winners in 124/128 world pairs. The other four had different action traces but the same world winner. The zero-width interval reflects the observed pair means on this fixed schedule.

## Timing and host load

All 384 games: 348102 candidate decisions, p99 111.061 ms, searched p99 161.331 ms, max 229.814 ms; 0 decisions above 250 ms. Deadline-truncated decisions: 84; no-complete-candidate fallbacks: 0. Baseline timing is separate: p99 234.264 ms, max 716.140 ms, overruns 1815.

Three nice-10 evaluation processes ran concurrently, with up to two native search workers per process. Host launch snapshots in stage5b-r3/host-worker*.txt and per-game load/nice records document other work. Snapshots also record three C56 extraction workers, an Android emulator consuming several cores and a RoadForge job; live-loop training was active during preparation. One-minute load averages at game completion ranged from 8.404 to 28.047 on 12 physical cores; no unrelated job was stopped or modified. All-decision timing includes sensor conversion, public history, candidates, root reconstruction and native search; only pregame initialization/warmup is excluded.

Public-state verifier checks: 590192. Rejected candidate/opponent commands: [3, 9]. All results are retained. The public combat model remains approximate, so public-legal candidates can occasionally fail engine application, as in Stage 5.

Manifest SHA256: 4cd1fdd26d2d5fee2348fd290b077e0a01b6c58bbb0c67dd70d595ef98e99cca. Receipt aggregate SHA256: 1a72738bbd6cfb7c63797e15dc46d1517b1a8eebb59ec02e2d5a039eeb8b6ae5. Every worker exits zero; the analyzer requires all 192 paired matchups and unchanged source pins.

## Files and scope

Changed runtime sources: src/clasher/rl/c56_rollout_planner.py and engine-rs/src/scripts.rs. Added engine-rs/test_stage5b_deadline.py. Added engine-speed/PREREG-C56-deadline.md and the r2/r3 replacement registrations, STAGE5B.md, and stage5b/, stage5b-r2/, stage5b-r3/ artifacts. The active live adapter and final evaluation are in stage5b-r3/. Build and parity receipts are in stage5b/. Both interrupted attempts remain preserved. Updated engine-speed/PROGRESS.md. Stage 5 evidence and its private extension remain unchanged. No forbidden Git operation or protected data/runtime directory was changed. Owned Cargo intermediates were cleaned while idle, and the private build target is absent. All three attempt directories total 88.95 MB, below the 500 MB cap. No owned worker remains.

Final audit: stage5b-r3/final-audit.json verifies 460 pinned files, all 384 full-game timing counts, registration before every game, nice 10/two-thread settings, worker exits, entry preservation and unchanged Stage 5 native binary/receipt hashes. Only the two declared runtime sources differ from the entry hashes.
