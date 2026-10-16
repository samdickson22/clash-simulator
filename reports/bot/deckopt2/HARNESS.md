# Real-level deck search harness

These scripts orchestrate existing players and simulators. They do not change search scoring or the deployed planner's level handling.

The job root is `/mpac/sdicks02/jobs/clasher/bot-deckopt2`. Account collections, Battle Log rows, banks, models, checkpoints and raw games stay in that job directory and are not committed. The code snapshot is intended to be copied there; sibling script imports and recorded helper hashes refer to that location.

## Stages

1. Preserve the original current-level C56 screen, using both deterministic LD players.
2. Build the resource-feasible B plans from the official rarity-aware upgrade arrays and the frozen account inventory. Screen 32 decks with the reserve player on a fresh bank, eight cases per opponent policy.
3. Lock finalists from the completed screens and register an independent projected validation bank, 150 cases per policy. Projected games are optional after true-deck validation and only when CPU is idle; otherwise record them as not run.
4. Draw a second independent bank for the true Battle Log decks. Use the same C56 finalists and upgrade vectors, full-pool R3a/v1, and the specified strong opponent. Evaluate both serial full-pool players, 150 cases per policy. rext-bc is unavailable for this variant.

`pipeline.py` manages the projected stages. It registers the projected validation bank but does not automatically admit those games: true-deck validation determines the deck decision, and projected work is optional after completion and a fresh idle-capacity audit. `fullpool_pipeline.py` waits for the gate, replay proof, strong smoke and finalist selection before starting true-deck validation. `refresh-loop.sh` collects projected rows and refreshes `REPORT.md`; full-pool workers immediately copy each completed row to the coordinator. `fullpool_report.py` keeps true-deck inference separate.

Every bank records its `os.urandom` entropy, `date -u` timestamp, SHA, source/config/model hashes and cases before games start. New banks must have disjoint case seeds from earlier banks. Do not redraw a bank because of outcomes.

## Planning and truth

The projected players are `LD-K4L-R-gs-rw` and `LD-K4L-R-gs-rw-res`. They retain deployed root/belief handling and no wall deadline. Only RoyaleSim truth receives our actual planned card levels, account tower level and independently sampled opponent population-prior levels. No ExactLevelRoot is installed.

The full-pool source snapshot is `1a65dcd1a00c5e3f891228df878d3bbebe4de187`, with Linux `live16402b-r3`. The delivered package at `2fa5d496` adds only an inactive Mac runtime pin relative to that source. `release-reconciliation.json` records the comparison and matching model files.

Full-pool construction starts with the actual live bundle factory, then applies the approved serial configuration before `start`:

```python
own.search.set_deadline(None, 1)
own.search.native_threads = 1
own.search.pool_size = 0
own.search.chunks = 4
own.deadline_seconds = None
observed.rec.deadline_seconds = None
assert observed.deadline_seconds is None
```

The last two lines matter: Recorder caches the factory's deadline. Clearing only the inner player leaves simulator lateness dependent on elapsed wall time. The failed preflight demonstrating this is retained separately; it is not a validation game.

Use explicit f1a2 with its calibration sidecar. Relative to `K4L-R-gs-rw-fc-c4-mk1a1`, the fallback default is f1a2 rather than R3a. Before freezing, run `fullpool_repeat.py` on one identical case twice and require matching command/state hashes and zero cutoff/lateness. `repeat-proof.json` binds the adapter, worker and player configuration.

The strong opponent gets a separate Runtime with C56 LiveBelief, the original it5s2 fast tier and extended R3a proposer. The process-wide belief/fast environment overrides are unset; settings are applied per instance. Both sides assert and log their actual belief and fast checkpoint at start. `fullpool_strong_smoke.py` checks the complete path. `fullpool_entry.py` verifies the exact installed RoyaleSim binary, data, calibration and placement sources before loading runtimes.

## Resources and resuming

Use the shared fixed `/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh` on the compute host. Each controller must have its own `bot/detach.sh` session and process group. Keep `PYTHONHASHSEED=0`, `NUMPY_MADVISE_HUGEPAGE=0`, CPU-only execution and one numerical-library thread. Follow current host authorization, admission caps and game-worker limits; do not infer room from raw Python counts alone.

Projected `pool.py` routes are exclusive fixed job indices. SIGUSR1/SIGTERM drains all current games; wait for every owned controller and child to finish before repartitioning missing indices. Keep the same bank, completed rows and in-flight outcomes.

The full-pool queue atomically claims whole cases on the coordinator. All candidate/player arms of a case run on one worker and host, with randomized arm order. Small independent controllers can join as admission room appears. A crashed claim is never automatically released: first inspect the verified owned PID, retained rows and error record. Do not silently retry or exclude an unclean game.

Read `PROGRESS.md`, `status.json`, both `pipeline-status.json` files, launch receipts and controller errors before resuming. Do not start duplicate coordinators. A STOP marker pauses future claims or orchestration; it does not invalidate an existing bank.

## Analysis and deliverables

`clean.py` treats opponent deploy refusals as ordinary behavior. Our refusals, native failures, live errors and nonterminal/error games remain flags. Historical raw issue tags are preserved and interpreted without rewriting rows.

Win rate is primary; draws are nonwins. Each paired percentile bootstrap uses 20,000 within-policy case resamples, with identical indices for candidate and baseline. Report pointwise 95% intervals, without a multiplicity adjustment. Weak pool is R3a+v1 only. Strong and rext-bc have separate rows. Projected pooled weights four policies equally; full-pool pooled weights its three policies equally.

The registered recommendation rule requires pooled lower 95% CI above zero and strong-opponent lower CI at least zero for both players. Rank every eligible finalist by mean pooled win rate; otherwise retain the baseline. Validation alone supports the claim.

Report reaction-time proxies, undefended Giant-push share and cutoff rates separately from win-rate inference. Serial cutoff rates are zero by construction; candidate-specific wall200 effects are unmeasured. Keep the unpinned wall smoke and the owner's pinned timing as separate observations.

The final plan lists the eight cards, tested levels, exact ordered upgrades, held and wild copies, remaining gold spend, committed spending and total against the original budget. Recheck affordability against later authoritative account/cost changes. Do not buy upgrades, spend gems or change the live deck from these scripts.

C56-projected and full-pool plans are separate artifacts. Give true-deck validation precedence if the full-pool bundle is deployed. The search covers the registered candidate set and heuristic resource allocations, not all possible decks or upgrade allocations.

Own card scope remains C56 for this run. A later owned-full-pool rerun needs a new candidate set, complete empirical public vocabulary, updated inventory and fresh banks; retain the r3 pin and per-side construction safeguards.

Projected validation can use the serial fc-c4 reduction only after five LD/fc-c4 command/state/terminal comparisons per player match, including two strong-opponent cases with reserve activity verified. Implementation-check rows are separate from scored validation. A mismatched comparison retains original LD. The validation entry binds the choice to the registered bank and parity receipt hashes.

The full-pool translator deliberately drops SpearGoblin_Dummy, a predeclared Goblin Hut garrison sprite with no engine counterpart. Its raw counter is named unmapped_unit. fullpool_clean.py exempts only that declared visual counter. Recovery after the initial overly strict stop keeps the game function frozen, waits original producers to exit, hashes every preserved row, and completes only missing arms on each partial case’s original host. The independent bank is never redrawn. fullpool/resume-manifest.json binds the orchestration amendment and unchanged game worker.

The true-deck bank stays at450cases/4500games. No additional01/03admissions are allowed after the48-worker allocation (04:40,01:4,03:4). fullpool_interim.py freezes one descriptive snapshot once225complete paired case blocks exist. It reports actual per-policy counts and equal-policy-weight paired bootstrap CIs, reusing each policy’s case indices for every arm. Completion-time selection can bias this interim; it changes no finalist, upgrade vector, sample size, or final decision rule.
