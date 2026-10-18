# HP1 RL (b) results

Exploration; protocol: RL-PREREG.md. DEV screens select snapshots and support no gain claim. The v2 DEV baseline is complete; DEV snapshot screen results appear below; G-B status is reported separately.

## Smoke and launch (2026-10-18T05:20:14Z)

Staged source: `bf9c566784b01994862aff36882f202a4dea68f3`. Six model/vocab SHA256SUMS entries checked on 01 and again on 08. Source files unchanged.

Smoke PASS under the owner-corrected criterion: 24 attempted games, 21 retained, 3 unmapped-public-row errors, no other errors. Both engines and LIVE-K4CW-r16-fp exercised. Learner exited after updates 1 (critic warmup, version 0) and 2 (version 1); policy-00001.pt exists and all numeric statistics are finite.

Parity: deploy_parity=true; CPU logp maximum error 2.0265579223632812e-06; CUDA 2.86102294921875e-06; self-KL=0 on both.

Update 2: ratio_dev0=2.86102294921875e-05; KL=0.0012690617445633434. The initial brief demanded KL<0.001 and was reported FAIL. The owner corrected the smoke limit to **KL<0.05**: logged KL averages over PPO epochs after optimizer steps; ratio_dev0 is the pre-step no-drift check. The registered collapse bound remains 0.5. This decision is recorded in HELPER-STATE.md; no source changes.

Learner plays/game: 42.166667 / 50.333333; deploy-would-play/game: 37.000000 / 44.833333.

Retained smoke games (mean reported game CPU seconds; startup level-config build wall time is additional):

- ours/K4CW: n=2, CPU s/game=54.695025, learner plays/game=30.500000.
- ours/rest: n=8, CPU s/game=45.069814, learner plays/game=48.375000.
- rsim16402/K4CW: n=4, CPU s/game=69.144298, learner plays/game=40.000000.
- rsim16402/rest: n=7, CPU s/game=29.839692, learner plays/game=58.000000.

All three dropped games had unmapped_unit:SpearGoblin_Dummy. Own deck was Sam’s fixed Hog/Archers/Cannon/Skeletons/Fireball/Zap/ElectroSpirit/Valkyrie deck. Full seat-ordered decks:

- g=3, opponent=f1a2: `[['SpearGoblins', 'Bomber', 'Tombstone', 'GoblinHut', 'Fireball', 'MiniPekka', 'Minions', 'Giant'], ['Skeletons', 'HogRider', 'Archers', 'Cannon', 'Zap', 'ElectroSpirit', 'Fireball', 'Valkyrie']]`.
- g=20, opponent=v1: `[['Skeletons', 'HogRider', 'ElectroSpirit', 'Archers', 'Fireball', 'Valkyrie', 'Cannon', 'Zap'], ['Valkyrie', 'GoblinHut', 'Musketeer', 'Giant', 'Knight', 'Archers', 'Fireball', 'Bomber']]`.
- g=23, opponent=self: `[['BattleRam', 'Barbarians', 'GoblinHut', 'Goblins', 'GoblinCage', 'SpearGoblins', 'MiniPekka', 'Giant'], ['ElectroSpirit', 'Fireball', 'Skeletons', 'Cannon', 'Archers', 'Valkyrie', 'HogRider', 'Zap']]`.

Production receipts (PID=PGID for each detached session):

- 127x01 learner: PID/PGID 2909006, launch 2026-10-18T05:18:30Z.
- 127x01 actor-b1: PID/PGID 2910210, launch 2026-10-18T05:18:39Z.
- 127x01 mirror: PID/PGID 2910234, launch 2026-10-18T05:18:39Z.
- 127x01 helper-guard: PID/PGID 2914455, launch 2026-10-18T05:19:04Z.
- 127x08 actor-b2: PID/PGID 2652454, launch 2026-10-18T05:18:40Z.
- 127x08 remote-sync: PID/PGID 2652437, launch 2026-10-18T05:18:39Z.
- 127x08 ge-v2: PID/PGID 2656038, launch 2026-10-18T05:19:05Z.

Learner: 01 GPU 0, cpu_job 5; actor block 1: 01, 16 workers, cpu_job 18; actor block 2: 08, 16 workers, cpu_job 18 (waiting for admission at last check). 04 actor block 3 deferred while host load exceeds cap 70. Light guard pauses/resumes only owned 01 actor block 1 above/below the load thresholds and sets stop files on registered KL/deploy-play collapse triggers.

G-E baseline queued on 08: fast-v2 only, Sam L16 60 cases per K4CW-fp/R3a and dd1 60 cases vs K4CW-fp, DEV offsets 0/+200000, sequential runs with 8 workers through the PF1 driver’s cpu_job. Driver and pool hashes matched the registered pins.

Hourly mirror is running. Its startup attempt copied the available files but returned rsync 23 because learner-state.pt does not exist until the first update; check the next mirror after update 1. Raw games/models remain outside git.

## Screens and confirms

DEV comparisons select snapshots and support no gain claim. Gate conclusions require a fresh-bank G-B confirm.

## Watch and remaining actor launch (2026-10-18T05:55:16Z)

04 source/models staged from 01; all six SHA256SUMS entries passed. Actor block 3 started with 12 workers through cpu_job 14, cap 70. All three actor blocks are now admitted. 01 learner and guards remain alive; no collapse trigger or unexpected actor error.

- 127x04 actor-b3: PID/PGID 1203513, launch 2026-10-18T05:52:47Z.
- 127x04 remote-sync: PID/PGID 1203459, launch 2026-10-18T05:52:47Z.
- 127x04 helper-guard04: PID/PGID 1203435, launch 2026-10-18T05:52:47Z.

The 04 guard pauses/resumes only its actor-b3 receipt PGID above load 70 / below 54, and resumes it when STOP_ACTORS arrives. It is a lightweight process under cpu_job 2; it changes no source files.

Latest completed learner update at check: 2, version 0 (critic warmup); score 0.623967; plays/game 47.260331; deploy-would-play/game 42.409091; explained variance -0.129674; KL null because policy is frozen during warmup. No snapshot is due yet. GPU memory: 0, 10551 MiB, 48682 MiB.

Primary 01 aggregate (includes synced remote summaries): 760 attempted, 632 retained, 128 permitted unmapped-public-row errors, no unexpected errors. Host 1-minute loads at check (01/08/04): 39.63/152.46/31.55. 01/04 remain within caps; 08 jobs were admitted through cpu_job and run below higher-priority workloads.

Baseline remains incomplete: Sam 18/120 rows, 0 problems under PF1 fullpool_clean.problems; no finished.json yet, dd1 not started. PF1 treats SpearGoblin_Dummy as an expected visual-only drop. Driver/pool hashes rechecked against the registered pins. No screen score or confirm is reported.

Mirror bootstrap after update 1 succeeded using the existing durable files/directories; state presence confirmed on 04. The original hourly mirror continues. Resume state and full receipt/status snapshot are on 01 at HELPER-STATE.md and helper-latest-check.json.

## Remote policy publication failure (2026-10-18T06:23:16Z)

Three workers in 08 actor block 2 crashed with FileNotFoundError for run/policies/policy-00002.pt at actor.py:273, before the game try/except, so these are worker failures in actor-b2.log rather than game error rows. The other 13 workers remained active until containment.

Root-cause inference from the trace and source: remote_sync.sh lists/copies policy files, then fetches the live LATEST pointer. A learner update between the two can expose a policy file not included in that copy. The same directory-then-live-pointer pattern is used for snapshot LIST. The next sync eventually copied policy-00002.pt, but the crashed workers do not restart.

- 127x08 actor-b2: SIGTERM own receipt PGID 2652454; group absent at verification 2026-10-18T06:21:55Z.
- 127x08 remote-sync: SIGTERM own receipt PGID 2652437; group absent at verification 2026-10-18T06:21:55Z.
- 127x04 actor-b3: SIGTERM own receipt PGID 1203513; group absent at verification 2026-10-18T06:21:55Z.
- 127x04 remote-sync: SIGTERM own receipt PGID 1203459; group absent at verification 2026-10-18T06:21:55Z.
- 127x04 helper-guard04: SIGTERM own receipt PGID 1203435; group absent at verification 2026-10-18T06:21:55Z.

08 actor block 2 and its sync were stopped; 04 actor block 3, sync and guard were stopped to contain the same distributor bug (no 04 worker crash observed). These block numbers are spent. Completed remote rollouts/summaries were flushed to 01 separately, without policy sync. No source changes were made.

The 01 learner/actor block 1, load/collapse guard, hourly mirror and 08 baseline eval continue. Latest check: update5/version2, KL0.0049283520, deploy-would-play/game43.616327, no collapse. Baseline Sam77/120 clean-so-far; dd1 pending, no completed screen/confirm. Hourly mirror succeeded at its next scheduled pass.

The RL owner was notified with the failure and containment receipts (steer returned thread_not_sendable; identical text delivered with auto). At this incident report, remote actors/sync were stopped pending an owner code fix; repair/restart is recorded below. Preserve all checkpoints and baseline cases.

## Remote repair and replacement blocks (2026-10-18T06:54:17Z)

Owner-approved fix `6ca53032bd67ba8369908c4cf4f4395edc3275dc` was deployed by exact git archive to 08 and 04 after checking all live owned PGIDs for source references. None used those trees; baseline08 was verified on PF1. Old trees retained as source-before-sync-fix. Both remotes passed all six model/vocab checksums; actor.py and remote_sync.sh matched the fixed commit. 01 learner, actor1 and source remain untouched on the original source commit.

- 127x08 actor-b4: PID/PGID 3095237, launched 2026-10-18T06:28:36Z.
- 127x08 remote-sync-r2: PID/PGID 3095213, launched 2026-10-18T06:28:36Z.
- 127x04 actor-b5: PID/PGID 1492609, launched 2026-10-18T06:28:37Z.
- 127x04 helper-guard04-b5: PID/PGID 1492559, launched 2026-10-18T06:28:37Z.
- 127x04 remote-sync-r2: PID/PGID 1492518, launched 2026-10-18T06:28:37Z.

Block4 has16 workers under cpu_job18; block5 has12 under cpu_job14 and cap70, with its own lightweight block5 load guard. Both new blocks were admitted and healthy at the latest check. Retired blocks2/3 and their receipts remain preserved and are never reused. The scheduled watch prompt now names the repaired topology.

## DEV v2 baseline complete (2026-10-18T06:54:17Z)

fast-v2 at registered tau0, DEV bank; selection reference only. Sam L16 base3690083941500208, 60 cases per K4CW-fp/R3a; dd1 base3690083941700208, 60 K4CW-fp cases. All180 rows match the declared case identities and return problems(row)==[]; both finished.json files contain eight zero statuses. Driver, populations, vocab, model, row bank hashes, levels and exact arguments passed validation.

| Row | Opponent | n | Score | Plays/game | CPU s/game | W/D/L |
|---|---|---:|---:|---:|---:|---|
| sam | LIVE-K4CW-r16-fp | 60 | 0.516667 | 47.066667 | 240.205770 | 31/0/29 |
| sam | R3a | 60 | 0.583333 | 48.716667 | 53.572977 | 35/0/25 |
| dd1 | LIVE-K4CW-r16-fp | 60 | 0.533333 | 47.066667 | 109.843775 | 32/0/28 |

Baseline compact per-case reference and validation manifest: JOB/helper-ge-v2-readout.json on08 and01, SHA256 `a1f6f1385057c900a6fcb480157ac37b98e09ee923fc8ac4669841d72bb12360`. Raw rows remain untouched. Stable checks reuse validation only if every row size/mtime and bank/finished hashes remain unchanged. No snapshot contrast or G-B gate has run.

Latest watch: update8/v5, KL=0.00805364, deploy-would-play/game=41.141667, explained_var=0.922132; no collapse, no new worker failures or shortfalls. Only snapshot v5 exists; first G-E screen is due at v10. Historical actor-b2.log retains the three already-contained FileNotFoundError traces. No owner status message was sent for successful restart or baseline completion.

## DEV screen v10 (2026-10-18T08:51:33Z)

Snapshot SHA256 `0e474348e4f69f42805ac54a6d7cdfb92a6169f6e369cccc8b0274341e335f2d`. All180 rows passed validation, paired exactly to the frozen fast-v2 baseline by full case identity. Both row runs finished with eight zero statuses; driver, pool, vocab, decode, level and case arguments matched the registration.

| Row | Opponent | Pairs | v10 score | v2 score | Paired difference | v10 plays/game | v2 plays/game |
|---|---|---:|---:|---:|---:|---:|---:|
| sam | LIVE-K4CW-r16-fp | 60 | 0.633333 | 0.516667 | +0.116667 | 47.400000 | 47.066667 |
| sam | R3a | 60 | 0.733333 | 0.583333 | +0.150000 | 52.333333 | 48.716667 |
| dd1 | LIVE-K4CW-r16-fp | 60 | 0.666667 | 0.533333 | +0.133333 | 47.350000 | 47.066667 |

Equal-weight screen score: **+0.133333**. All three differences nonnegative: True. Registered Sam play-rate sanity: True. Candidate predicate (screen >=+0.03, all differences >=0, Sam play sanity): True. DD1 plays/game are reported above for inspection. These DEV estimates are selection results, never gains.

Snapshot training record: update13/v10, train score=0.618474, KL=0.01470507, deploy-would-play/game=42.939759. Validation/readout: JOB/helper-ge-v10-readout.json on08/01, SHA256 `fc93149244982dd9c6ba48e276bbae10291b75bce29002331252b5810b99d47d`. Raw rows retained.

## First G-B launch and actor expansion (2026-10-18T09:04:51Z)

The first qualifying DEV candidate v10 was submitted immediately to G-B on CONFIRM1 (2715349865347232), registered before its first game at 2026-10-18T08:51:28Z. Receipt on08: gb-v10-confirm1, PID/PGID4142369. The bank is now used and cannot support another confirm. Sequential PF1 runs use eight workers, arms fast-v10/fast-v2/fast-f1a2, Sam300 cases per opponent, account150 per opponent with the exact53 PF1 strata, and dd1200; offsets0/+100000/+200000. G-B is incomplete; no confirm conclusion is available.

DEV screen v20 also started on08 at2026-10-18T08:52:01Z, ge-v20 PID/PGID4147276. Its frozen checkpoint provenance is in helper-ge-v20-checkpoint.json; Sam120 and dd160 rows remain in progress. The v2 baseline and completed v10 screen will not be rerun.

The coordinator/owner authorized more actors after observing learner starvation. This expands the original one-block01 allocation while retaining the unchanged learner flags and source. Existing fixed remote syncs are reused; no source replacement.

- 127x04 actor-b6: PID/PGID2669474, launched2026-10-18T08:57:27Z.
- 127x04 actor-b7: PID/PGID2669525, launched2026-10-18T08:57:27Z.
- 127x04 helper-guard-scale04: PID/PGID2669446, launched2026-10-18T08:57:27Z.
- 127x01 actor-b8: PID/PGID722372, launched2026-10-18T08:58:12Z.
- 127x01 helper-guard-scale01: PID/PGID722312, launched2026-10-18T08:58:12Z.
- 127x08 actor-b9: PID/PGID4187956, launched2026-10-18T08:58:15Z.

Target workers:04=40 (existing block5 W12 + block6 W16 + block7 W12),01=24 (block1 W16 + block8 W8),08=32 (block4 W16 + block9 W16). Each actor uses cpu_job W+2 at nice15. Block8 is admitted; at the command-dated09:01 check, blocks6/7/9 and the aggregate04 guard were waiting admission behind newly active unrelated work. Block5 remains paused under high04 load. Retired blocks2/3 are never reused.

Thermal check before adding01 block8: active actor-core MHz min1071.585, mean1117.847, max1152.724. New01 guard owns8 only at cap56, retaining the original block1 guard and hard cap60. The04 replacement guard owns5/6/7 at cap70 with budgeted resume; the original block5-only guard was stopped via its own receipt. Existing01 learner/source/block1 remain untouched.

Before scaling, updates18..24 ran from07:49:50Z to08:50:49Z: **5.903252 updates/hour**, with296 finished rollout files at the08:54:34Z preflight. At09:01:30Z backlog was145. Post-scale throughput is pending at least three completed updates after actual block8 admission08:58:17Z; no increase is claimed yet. The regular watch records timestamps, admission and backlog, and will report growing backlog over960 without changing learner flags.

## Overload placement and partial-scale throughput (2026-10-18T09:53:09Z)

On the owner’s overload decision, 08 actor block4 and queued block9 were stopped with SIGTERM to their own receipt PGIDs only, verified absent at 2026-10-18T09:24:30Z. The existing sync remained until the local finished rollout count reached zero and all32 game-summary file hashes matched on the learner. Sync PGID3095213 was then stopped and verified absent at 2026-10-18T09:24:56Z. Evidence: JOB/helper-retire08-actors.json and helper-retire08-sync.json on08/01. The running v10 G-B and v20 G-E were preserved. No new actor/eval work starts on08 while PTR1 is active; new screens use04/01 under cpu_job.

- 127x04/actor-b10.receipt.json: PID/PGID2873259, launch2026-10-18T09:25:25Z.
- 127x04/helper-guard-scale04-r2.receipt.json: PID/PGID2873227, launch2026-10-18T09:25:25Z.

Block10 W16/cpu_job18 replaces the canceled, unadmitted block6 W16 reservation one-for-one. 04 target remains40 workers: block5 W12 + block7 W12 + block10 W16. The new aggregate guard owns only5/7/10 at cap70; prior aggregate and block5-only guards are historical. Retired2/3/4/6/9 are never reused. 01 learner/source/blocks1/8 remain unchanged.

At 2026-10-18T09:51:13Z, blocks7/10 were admitted, block5 and7 paused by load control, and block10 had16 live workers; the guard was alive. 04 load=79.47, no console user. 08 PTR1 remained active (130 processes); no RL actors or sync remained there. 01 load=43.16, blocks1/8 had24 workers total.

Pre-scale updates18..24 at 2026-10-18T07:49:50Z..2026-10-18T08:50:49Z measured5.903252 updates/hour. The first measurable partial-scale window update26=2026-10-18T09:10:07Z, update27=2026-10-18T09:25:28Z, update28=2026-10-18T09:49:22Z measured**3.057325 updates/hour**, so an increase has **not** been demonstrated. This window includes retirement of08 actors and waiting/paused04 capacity; it is not an isolated comparison of actor counts. Primary finished-rollout backlog=43, below960; no learner-bottleneck alert. Learner flags are unchanged.

Latest train update28/v25: score0.679167, KL0.03240959, plays/game50.162500, deploy plays/game45.808333, explained variance0.946652. No collapse or new worker errors; old block2 traces remain historical. Hourly mirror succeeded at its latest pass. v20 Sam120/120 is clean and finished, dd1 awaits the existing driver’s admission; G-B Sam115/1800 is incomplete. No new screen score or confirm conclusion.

## DEV screen v20 (2026-10-18T10:23:51Z)

Snapshot SHA256 `9ce172c58ae3d9de5d0e2145619dbabdb2738a5e6abb02ca4917a39c08e161cb`. All180 rows passed validation, paired exactly to the frozen fast-v2 baseline by full case identity. Both row runs finished with eight zero statuses; driver, pool, vocab, decode, level and case arguments matched the registration.

| Row | Opponent | Pairs | v20 score | v2 score | Paired difference | v20 plays/game | v2 plays/game |
|---|---|---:|---:|---:|---:|---:|---:|
| sam | LIVE-K4CW-r16-fp | 60 | 0.616667 | 0.516667 | +0.100000 | 47.333333 | 47.066667 |
| sam | R3a | 60 | 0.666667 | 0.583333 | +0.083333 | 53.366667 | 48.716667 |
| dd1 | LIVE-K4CW-r16-fp | 60 | 0.633333 | 0.533333 | +0.100000 | 44.666667 | 47.066667 |

Equal-weight screen score: **+0.094444**. All three differences nonnegative: True. Registered Sam play-rate sanity: True. Candidate predicate (screen >=+0.03, all differences >=0, Sam play sanity): True. DD1 plays/game are reported above for inspection. These DEV estimates are selection results, never gains.

Snapshot training record: update23/v20, train score=0.626556, KL=0.02510351, deploy-would-play/game=41.701245. Validation/readout: JOB/helper-ge-v20-readout.json on08/01, SHA256 `3c6ca58528a1c03cedb29bcc4f899a25dbdb74234306e1f3039ac058ee48eb21`. Raw rows retained.

## Amendment deployment corpus registration (2026-10-18T10:42:48Z)

Amendments1–3 registered at source `579c8a51c599f35e08a45dc6298b8ada497fdfcf` are accepted for deployment. Before any new smoke, training or G-S game uses the corpus table: `/mpac/sdicks02/jobs/clasher/bot-hp1-rl-20261018/models/corpus-decks-v1.jsonl`, SHA256 `16ca9bfbc72b028ffdb44d4497db8464dff60f0560ce6eb098a48ee12f149b8e`, 40188 deck rows; command timestamp 2026-10-18T10:42:45Z. The table remains outside git. It is included in models/SHA256SUMS and checked on01/04.

Opponent mix: corpus40%, frozen frequency table30%, random legal30%; RoyaleSim redraw exclusions GoblinHut, Graveyard and SuspiciousBush on both seats. Training own-deck totals sam50%, meta30%, rand20%, with SEARCH17% of the expanded league. Old-source actors may overlap only until newly admitted replacement blocks are confirmed. No new-source game has started at this registration.

G-S uses Amendment2 ALL-16/ALL-acct on S-CONFIRM1=3262629447693008, unused. DEV ALL-16 references use base3690083941900208, cases60 per SEARCH/K4CW-fp/R3a, arms res-lb-RF-wintp and fast-v2; later snapshots use the identical cases. Existing G-B remains unchanged. Source deployment, smoke and learner extension results will be appended as they land.

## Amendment smoke failure and exclusion probe (2026-10-18T11:04:35Z)

The amendment smoke failed on an unmapped RoyaleSim spell row, so the run1 learner restart, new-mix actor rotation and G-S reference games remain on hold. Original run1 and already-running G-B/G-E work continue.

The failed game was g11000004 (RoyaleSim, own-deck kind sam, opponent self): translator key unmapped_spell:SkeletonBalloon/0, count26. The opponent deck contained BlowdartGoblin, Barbarians, Berserker, ElectroWizard, RoyalDelivery, SkeletonBalloon, SkeletonDragons and Cannon. Final smoke artifacts retain 5 attempted games, 4 valid and 1 void; no SEARCH game or learner update completed. This failed the owner's zero-error smoke requirement.

Own smoke actor PGID1517606 and learner PGID1510823 were terminated and verified gone at 10:57:52Z; only smoke-run2 STOP files were written. The queued new ALL-16 reference PGID3525612 on04 was terminated and verified gone at 10:57:53Z before any reference game. Main run1 was untouched. Artifacts: helper-smoke2-failure-readout.json and helper-amendment-failure-allhosts.json on01; raw smoke-run2 rows retained. Failure already reported to the owner.

The owner authorized a separate 1,024-game, reviewed-actor probe on08, probe-rsim1: fixed Sam versus uniformly sampled full-pool decks, R3a only, RoyaleSim only, no excluded cards. This diagnostic intentionally retains unmapped-error cases, does not train or evaluate a gate, and will produce coverage.json with per-card opponent draws and void attribution. New-mix use waits for the owner to register the derived exclusion set.

## DEV screen v30 (2026-10-18T11:26:31Z)

Snapshot SHA256 `cf0f23f1a908d23d5e17413684ea5c53f4f906e303bdb5756126060d80b05888`. All180 rows passed validation, paired exactly to the frozen fast-v2 baseline by full case identity. Both row runs finished with eight zero statuses; driver, pool, vocab, decode, level and case arguments matched the registration.

| Row | Opponent | Pairs | v30 score | v2 score | Paired difference | v30 plays/game | v2 plays/game |
|---|---|---:|---:|---:|---:|---:|---:|
| sam | LIVE-K4CW-r16-fp | 60 | 0.633333 | 0.516667 | +0.116667 | 45.350000 | 47.066667 |
| sam | R3a | 60 | 0.800000 | 0.583333 | +0.216667 | 49.316667 | 48.716667 |
| dd1 | LIVE-K4CW-r16-fp | 60 | 0.700000 | 0.533333 | +0.166667 | 44.916667 | 47.066667 |

Equal-weight screen score: **+0.166667**. All three differences nonnegative: True. Registered Sam play-rate sanity: True. Candidate predicate (screen >=+0.03, all differences >=0, Sam play sanity): True. DD1 plays/game are reported above for inspection. These DEV estimates are selection results, never gains.

Snapshot training record: update33/v30, train score=0.720165, KL=0.03803619, deploy-would-play/game=42.045267. Validation/readout: JOB/helper-ge-v30-readout.json on08/01, SHA256 `92f528e8a78d9b1f77042c5d4ed655276123bb9179b9ae63a4b2228580bb3c2e`. Raw rows retained.
