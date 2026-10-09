# Frozen student-screen execution

These scripts execute the coordinator's 2026-10-09 freeze. They do not edit the
plan, seeds, sampler, losses, optimizer or checkpoint selection. Runtime snapshots
use the unchanged `imitation/exit_r1/` sources at `f98d8926`, with the generation
snapshot's accepted engine and serving dependencies.

All data, logs, checkpoints and task environments live at host-local
`/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1/`.
Only small receipts and aggregate results belong in Git.

`select_cutoff.py` admits exactly the completed-game prefixes in the frozen
controller progress record: 13,169 / 17,980 / 18,428 games on 03 / 04 / 08.
The 40 games sealed during stop drainage are excluded. `stage_pack.sh` stages
these games on 03 and calls the frozen packer. The source-index and every source
game seal are preserved. `verify_corpus.py` checks each copied packed file.

`prepare_fit.sh`, `verify_human.py` and `check_ready.py` verify the human training
store and the released v1 checkpoint (step 22,552, width 192). Task-local NumPy
2.3.5 matches the accepted teacher feature arithmetic. The existing qualified
CUDA 11.8 Torch 2.7.1 environment is exposed to each isolated task environment;
shared environments are unchanged. `finish_prepare.py` completes checks after
the detached initial copies.

`run_fit.sh` passes the frozen recipe explicitly. `fit_runtime.py` wraps the
unchanged trainer with synchronized timing and the existing T5 read-only mmap
page-release helper. Batch tensors, sampling and loss normalization are unchanged.
It requests checkpoint-and-exit at the memory/headroom floors. Leased training
also uses the current lease-aware supervisor.

`staged_controller.py` replaces the original all-final `report_controller.py` under
coordinator authorization at22:19Z. The frozen plan requires common per-seed
pairing, with no simultaneous/interleaved execution requirement. A single
`staged_pool.py` consumes immutable stage queues per home host:56 physical workers
on03 now,60 on04 and44 on01 after their GPU trainers exit.08 runs no reporting
CPU games. The600 common init-W reference and64 held-out teacher games begin
first; each student's256 head-to-head and600 fallback games follow its final4883
EMA seal. S-human runs on03, S-teacher on04, S-mix on01.

`staged_freeze.py` calls the unchanged B4 freeze API with only available genuine
checkpoints, pins every input and retains each stage SHA. Private seat-specific
policy generators keep action RNG independent of other loaded checkpoints.
`canonicalize_stages.py` runs only after every fit and every reporting task is
complete. It validates stage inputs/checkpoints against the final freeze and the
exact3168 case identities/seeds/seats/terminal flags. New reducer-view copies
change only the provenance envelope; immutable raw receipts retain their original
freeze SHA and receive a SHA manifest. Four meaningful provenance tests pass,
including changed-runtime/checkpoint/seed rejection. No metrics or kills run
before all stages complete; every pair uses the same common init reference.

Reporting uses the previously qualified E1 native SHA f387b2d2..., restored under
a dated reporting-only amendment after the generation native rejected startup.
No game was created in that failed launch; its1289.014866 CPU-seconds are retained
in final costs. Missing E1 support files are copied byte-for-byte from its sealed
runtime into the reporting source snapshot before the first game, and pinned.
Corpus/fit inputs and the frozen student package remain unchanged.

The held-out teacher games remain outside every training input. The frozen
agreement/reducer code supplies the primary diagnostics and kill decisions.
`supplement.py` adds the remaining required whole-game bootstrap intervals,
play prevalence ratios and execution counters, checking primary-rate equality
against the frozen implementation. All intervals use 5,000 resamples, seed
80991010, percentile 95%, with complete game seeds as the unit.

Owned stop files: `PACK.STOP`, `FIT.STOP`, `REPORTING.STOP`, `CONTROLLER.STOP`
under the task job directory. A reporting-pool stop releases its own workers
without touching caches or other owners' processes. No simulation runs on 09.

After default and expandable allocation failed at dense step239, the coordinator
authorized S-human micro3584, with the same effective8192 rows and order.
`run_fit_loader6_micro3584.sh` applies the dated runtime amendment at the original
optimizer-step call and resumes exact, untouched checkpoint200. The checkpoint
recipe fingerprint remains7168; runtime and segment evidence record the actual3584.
Global denominators, one clip/optimizer/scheduler/EMA update per effective batch
remain unchanged. Floating-point accumulation order changes, so this micro
continuation is not claimed bit-identical. Both failed08 replays are archived
and charged, alongside the failed09 attempt. S-mix/S-teacher remain unchanged.

The coordinator-directed loader6 amendment uses `loader_prefetch.py` through `run_fit_loader6.sh`: six actual workers/prefetch4, no mmap_random_advice. Complete steps use the unchanged deterministic mixture sampler, and both complete index vectors are checked in the parent. `qualify_loader.py` compares two GPU updates from identical exact checkpoints, including every RNG and optimizer state. Qualification receipts record the bit-exact comparison. The six loader workers use distinct cores120–125; parent cores118/119/126, Torch threads1. Aggregate parent/loader PSS is guarded at46GB on leased hosts only, home MemAvailable at24GiB; leased09 also uses the versioned capture-extension supervisor with12 declared processes/48GB cap and Oct11 deadline. The8GiB GPU reserve applies only to leased hosts. S-human resumes on owned08 from exact checkpoint108, nice19, checkpoints every200 steps, stop file and≤5-minute reclaim. Failed09 unsaved updates are archived and replayed, with costs retained. Other arms checkpoint every250 steps. Initial fit segments and train-only qualification costs are retained. `collect_results.py` renders all arm CIs, decisions and resource totals only after the controller has complete final fits and reporting cases.
