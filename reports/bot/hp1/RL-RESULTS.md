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

## RoyaleSim coverage probe and amendment 4 smoke (2026-10-18T11:29:44Z)

The reviewed-actor probe stopped at 677/1024 attempted games, with 239 valid games, 433 translator voids (63.96%) and 5 unexpected OwnCycle exceptions. All-error rate: 64.70%. It is a partial diagnostic, not a completed coverage or gate result. Own PGID776145 was terminated and verified absent; run1 was unchanged.

All121 pool cards appeared on the opponent side: draw count min26, median45, max65. Reviewed case reconstruction matched all239 valid deck lists and all433 translator-error traceback decks. Every recorded translator key mapped to its source/spawning card and that card occurred in the opponent deck. No logged error-key dictionary was truncated. Multiple implicated cards may occur in one game; per-card void counts therefore overlap.

| Source card | Opponent draws | Games voided by its translator keys |
|---|---:|---:|
| Fisherman | 55 | 55 |
| GiantBuffer | 56 | 53 |
| GoblinCurse | 40 | 28 |
| GoblinDemolisher | 53 | 51 |
| GoblinDrill | 39 | 38 |
| GoblinGiant | 48 | 44 |
| GoblinHut | 36 | 36 |
| Graveyard | 40 | 26 |
| MegaKnight | 48 | 23 |
| MovingCannon | 41 | 38 |
| Phoenix | 39 | 39 |
| RamRider | 47 | 45 |
| SkeletonBalloon | 58 | 58 |
| SuspiciousBush | 45 | 45 |
| ThreeMusketeers | 49 | 2 |
| WitchMother | 37 | 36 |

Five additional games raised OwnCycle.play card-not-in-list exceptions: ElectroGiant twice, Tombstone, RamRider and GoldenKnight once each. These exceptions interrupt the match before its translator summary, so additional translator faults in those five cases are censored. The full121-card table, key counts/mapping evidence, case IDs, hashes and containment receipt are in08/01 JOB/probe-rsim1/coverage.json, SHA256 d1666d7cad127fc3b871968042571e13b3823c472e8a7f241f8851ae6dd4164c. No cases were silently dropped or retried. Remaining347 cases were not run after containment.

The owner registered Amendment4 at 095785f4422079f048a0d9503e714c7fe4e38683: the16 translator-implicated cards plus ElectroGiant, Tombstone and GoldenKnight form the19-card RoyaleSim exclusion set. It removes50.97% of corpus deck weight; every G-S result will state that it covers the RoyaleSim-playable49.03% only. Our-engine training still draws from the full mix. Sam's non-SEARCH environment share is split RoyaleSim.25 / our-engine.148 as registered.

At command time 2026-10-18T11:29:41Z, the new commit was staged as source-095785f44 and repo-095785f44220 on01/04/08, with seven model/vocab/corpus hashes checked. Smoke3 is active on01 (learner receipt1835525, actor13 receipt1840684); no restart or production rotation has happened. Zero errors, including OwnCycle exceptions, remain mandatory for smoke PASS. Prepared next steps use EXTEND_LEAGUE=1 and the registered19-card set for new ALL-16 DEV references.

## Amendment 4 smoke3 PASS (2026-10-18T11:53:12Z)

Amendment4 source 095785f4422079f048a0d9503e714c7fe4e38683 passed smoke3: 24/24 games, zero errors including no OwnCycle or unmapped-key exceptions, normal learner/actor exits. Engine counts: RoyaleSim15 / ours9. Own-deck kinds: sam13 / meta7 / rand4. Opponents include K4CW4 and SEARCH5. Mean actor plays/game40.708333.

Learner update1 was critic warmup and update2 wrote version1; both records were finite. Update2 ratio_dev0=2.95639038086e-05, KL=0.00164185812375, passing the owner-corrected KL<.05 bound; learner plays/game41.333333 and33.333333. policy-00001.pt SHA256 775a896b70ed6eaee1b8ad0bac967836305705874c827b6afe228d60769e3429. SEARCH mean CPU seconds/game188.143019 (5games). CPU details:

| Engine/opponent | Games | CPU seconds/game | Plays/game |
|---|---:|---:|---:|
| ours/K4CW | 2 | 205.559362 | 35.000000 |
| ours/rest | 7 | 87.950738 | 33.857143 |
| rsim16402/K4CW | 2 | 202.611730 | 40.500000 |
| rsim16402/SEARCH | 5 | 188.143019 | 48.800000 |
| rsim16402/rest | 8 | 67.527781 | 43.125000 |

Pass artifact:01 JOB/helper-smoke3-pass.json, SHA256 3db8bfd834644da9c0aaedf418c3c5fdd8be7fb9d1fe61b00c8603b270cf1055; raw rows retained. Corpus SHA256 16ca9bfbc72b028ffdb44d4497db8464dff60f0560ce6eb098a48ee12f149b8e. The boundary restart controller was launched on01 with own receipt PGID2017958, using EXTEND_LEAGUE=1 and the approved defaults. At 2026-10-18T11:53:09Z it was waiting for the next completed primary update; extension, next-update verification and actor replacement remain pending. No duplicate learner is launched.

G-S references and all-deck evaluations use the registered19-card exclusion set; their claims cover only49.03% of corpus deck weight. Original-engine training retains the full deck mix.

## Amendment 4 residual errors and expanded coverage limit (2026-10-18T12:14:49Z)

The source095 deployment completed its planned restart and actor admission, then encountered six additional OwnCycle.play exceptions in214 attempted games (208 valid). Error cards: RoyalHogs, Berserker, Heal, Assassin, Miner and SpearGoblins. The Heal failure was on our meta deck; the other five cards were on the opponent side. No game with an error kept a rollout. Full reconstructed cases and tracebacks:01 JOB/helper-amendment4-errors.json, SHA256 4e637b49f9d80be214c6d45525831b1f39806266f828719790c3cbe04cd733aa.

The helper stopped all10 new actor groups14–23 and the new ALL-16 reference through their own receipts, verified absent. Old actor groups had already been retired only after the replacements were admitted. Learner-r2 remained running; its seven-member extension and successful resumed update48/v45 were verified (KL.04070027, deploy plays/game40.804878). Old G-B/G-E jobs were preserved. The failure was reported once to the owner; source code was unchanged.

Before further games, owner commit32828b32c27eca852a2151c5fb2a826c6ff0451d registered the six cards in the exclusion set (now25), tolerated recorded RoyaleSim training errors up to5% per hour, and permitted a G-S erroring row to rerun with --only after its card joins the set by a dated prereg note. Failed rows and prior banks remain retained; retries will be identified explicitly and paired arms kept on the same resulting case.

The new25-card set leaves **28.886295% of corpus deck weight RoyaleSim-playable** (118779/411195); excluded weight is71.113705%. This supersedes the19-card set's49.03% coverage for future G-S results. Corpus SHA256 16ca9bfbc72b028ffdb44d4497db8464dff60f0560ce6eb098a48ee12f149b8e; calculation artifact01 JOB/helper-328-corpus-coverage.json, SHA256 daf8978edc982dafa89ebc5d80ffabdb519695b3432490723c9f947980c98c26. Our-engine training still uses the full deck mix.

New source/repo trees are being staged at32828b32c on01/04/08. Learner-r2 stays on its existing095 source and flags. Fresh actor numbers24–33 are allocated for resumption; no14–23 block is reused. Hourly residual-error monitoring will count only RoyaleSim attempts from this new cohort across hosts, with fixed60-minute windows anchored to the cohort's first admission. Partial-window rates are recorded; the >5% stop rule is applied when each complete hourly window closes. File observations are timestamped at collection (at most about75seconds after a game through sync and minute checks). Error rows remain preserved and keep no rollout.

## G-S DEV reference index0 retry registration (2026-10-18T12:20:08Z)

The stopped19-card ALL-16 reference retained one failed row: evals/gs-dev-refs-all16-a4/rows/000000-01.json, id0-0000, index0, fast-v2 versus SEARCH. Its issue was opponent command rejections; the opponent deck included Miner. The original row and bank remain unchanged.

Owner commit32828b32c27eca852a2151c5fb2a826c6ff0451d has dated Miner and the other five new cards into the25-card exclusion set. Before the retry's first game, this note registers an explicit --only0 rerun at DEV+400000 with --cases60 retained (so opponent seed spacing stays61), source328, the25-card set, both reference arms and all three opponents. Output: evals/gs-dev-refs-all16-328-only0; expected3 paired cases /6 arm rows. Any changed opponent deck from the new exclusion set will be retained in the new bank and identified.

The source328 full reference uses a separate fresh output, evals/gs-dev-refs-all16-328, on all180 cases /360 arm rows. The retry is a recovery/consistency artifact and will not be double-counted in the full reference. All paired arms must share the same resulting case identity. Neither run is a gain claim; current corpus-weight coverage is28.886295%.

## Expanded exclusion cohort launch receipts (2026-10-18T12:28:27Z)

Owner source32828b32c27eca852a2151c5fb2a826c6ff0451d was staged and all7 model/vocab/corpus hashes checked on01/04/08. Learner-r2 remains on095 source with the same flags; update49/v46 already includes8 SEARCH games. No learner restart occurred for the25-card exclusion change.

Fresh actor receipts (cpu_job workers+2, nice15):

| Host | Block | Workers | Own PGID | Launch UTC |
|---|---:|---:|---:|---|
| 127x01 | 24 | 8 | 2275111 | 2026-10-18T12:22:40Z |
| 127x01 | 25 | 8 | 2275566 | 2026-10-18T12:22:42Z |
| 127x01 | 26 | 8 | 2275859 | 2026-10-18T12:22:44Z |
| 127x01 | 27 | 8 | 2276234 | 2026-10-18T12:22:46Z |
| 127x04 | 28 | 24 | 51807 | 2026-10-18T12:22:47Z |
| 127x04 | 29 | 24 | 52117 | 2026-10-18T12:22:48Z |
| 127x04 | 30 | 24 | 52433 | 2026-10-18T12:22:50Z |
| 127x08 | 31 | 24 | 1362601 | 2026-10-18T12:22:51Z |
| 127x08 | 32 | 24 | 1362960 | 2026-10-18T12:22:53Z |
| 127x08 | 33 | 24 | 1363245 | 2026-10-18T12:22:54Z |

Targets are32 workers on01 and72 on each remote; actual admission and load pauses are recorded in HELPER-STATE and the launch ledger. At the latest startup check,01 had24 admitted workers (16 paused) and block27 waiting admission;04/08 each had72 admitted workers. Load guards own only their new cohort, cap60 on01 and100 on remotes (04 drops to70 with a user). Prior empty guards were retired after the new guards admitted. Existing fixed04/08 sync processes were reused. All prior blocks14–23 remain spent.

The minute monitor helper-error-rate-328 on08 records only this cohort's RoyaleSim attempts and errors, across hosts, in complete60-minute windows anchored to first admission. Its first window closes at13:22:45Z (deadline converted from the recorded admission epoch by command). At12:26:26Z the partial window had3 errors /63 attempts (4.7619%): Minions, GiantSkeleton and Bats OwnCycle exceptions. This partial estimate supports no hourly conclusion. No failed game writes a rollout. The monitor stops the cohort when a completed hour exceeds5%; an our-engine error is outside that tolerance. Latest command time: 2026-10-18T12:28:23Z. A throughput change is pending sufficient post-admission updates.

G-S25-card full references (360 rows,8workers) and the registered --only0 retry (6rows,2workers) launched on04 at12:23:39Z, own PGIDs59243 and59213 respectively. Failed19-card row/bank remain retained. Analysis scripts are prepared only and will run after exact row counts and successful statuses. Future G-S results state corpus-weight coverage28.886295%, not the earlier19-card scope.

## DEV screen v40 (2026-10-18T12:30:11Z)

Snapshot SHA256 `b5cdb7387383f85a8c2c85ebac5b45cb3d63867f4e82a196b51aaf8eb5341054`. All180 rows passed validation, paired exactly to the frozen fast-v2 baseline by full case identity. Both row runs finished with eight zero statuses; driver, pool, vocab, decode, level and case arguments matched the registration.

| Row | Opponent | Pairs | v40 score | v2 score | Paired difference | v40 plays/game | v2 plays/game |
|---|---|---:|---:|---:|---:|---:|---:|
| sam | LIVE-K4CW-r16-fp | 60 | 0.633333 | 0.516667 | +0.116667 | 48.200000 | 47.066667 |
| sam | R3a | 60 | 0.750000 | 0.583333 | +0.166667 | 49.766667 | 48.716667 |
| dd1 | LIVE-K4CW-r16-fp | 60 | 0.666667 | 0.533333 | +0.133333 | 46.150000 | 47.066667 |

Equal-weight screen score: **+0.138889**. All three differences nonnegative: True. Registered Sam play-rate sanity: True. Candidate predicate (screen >=+0.03, all differences >=0, Sam play sanity): True. DD1 plays/game are reported above for inspection. These DEV estimates are selection results, never gains.

Snapshot training record: update43/v40, train score=0.758333, KL=0.03650655, deploy-would-play/game=39.387500. Validation/readout: JOB/helper-ge-v40-readout.json on08/01, SHA256 `de8407d4f6482acdb856e1896c16511467e1e7a1414f06d76821d8a7b58da789`. Raw rows retained.

## OwnCycle source fix and explicit DEV recovery registration (2026-10-18T12:42:27Z)

The 25-card DEV reference retained an error on case `0-0015`, search arm versus SEARCH: `ValueError("'Barbarians' is not in list")`. Its own 04 receipt PGID was stopped and verified absent; 30 rows and the failure artifact remain intact. No case was discarded or silently retried. The separate prior `--only 0` retry completed six clean arm rows / three paired cases with both exit statuses zero and passed the exact-case validator; this recovery artifact is not counted in the full reference.

The owner registered the OwnCycle early-refill fix in source `084331b6db52097905b3f2a47aae233e7158acbd` and restored the 19 probe exclusions. Exact archives, STAGED-REV, separate source/repo/facade paths and all seven model checks passed on 01/04/08. Learner-r2 remains running unchanged. A fresh actor rotation uses reserved blocks 34–45; capacity is replaced through ordinary admission, with original guards retained until their actors retire. A new OwnCycle error requires stopping the affected new-source cohort and reporting the exact case.

Before the fresh G-S DEV reference and failed-case retries, the pinned corpus coverage was recomputed: 201606/411195 = 49.02929267% RoyaleSim-playable weight, with 50.97070733% excluded (19 cards). Corpus SHA remains the registered model manifest value; full command-derived provenance is in `helper-084-corpus-coverage.json` (artifact SHA `bed5358a1d8daa5b9d80da0566b0aebfa910de68e4ed461378a81716405b77de`). G-S results will state this restricted scope. Fresh reference output is `evals/gs-dev-refs-all16-084`; the explicit earlier-error retry uses `--cases 60 --only 0,15` in `evals/gs-dev-refs-all16-084-only0-15`, on all three opponents and both reference arms. This preserves the seed spacing; paired arms share the resulting source-084 case. All old source-095/328 banks and errored rows are retained. The retry is a separate recovery artifact, not extra full-reference cases. S-CONFIRM1 remains unused.

The source-328 cohort produced updates 50–53 at 12:28:46, 12:32:01, 12:34:44 and 12:37:12 UTC: 21.3438735 updates/hour versus the earlier 5.9032523/hour baseline. This short observational window changes deck mix, exclusions and SEARCH cost; it is not an isolated actor-count causal comparison. Backlog was 221 at the watch, below 960, with no collapse.

Original G-E v50 was frozen and launched once on 08, `ge-v50.receipt.json`, while the G-S reference was contained. Its checkpoint metadata records the same-step source/copy SHA checks. It is a DEV selection screen only. Legacy G-B v10 continues on CONFIRM1; no second confirm is launched.

## OwnCycle-fixed actor rotation and fresh DEV launch receipts (2026-10-18T12:47:35Z)

Source-fix rotation launch state was read at 2026-10-18T12:47:31Z. The controller remains `waiting_admission`; admission is respected and no actor or learner flags are changed. Small first replacement blocks on 04/08 permit an admitted transition before retiring a larger old block. Final planned capacities are 01:32, 04:72 and 08:72 workers, governed by load caps60/100/100 (04 becomes70 if a console user is present). Learner-r2 stays on its existing source and receipt. Fixed remote sync receipts are reused.

- 127x01 new_guard block —: own PGID 2460391, launch 2026-10-18T12:43:29Z.
- 127x04 new_guard block —: own PGID 188202, launch 2026-10-18T12:43:30Z.
- 127x08 new_guard block —: own PGID 1493256, launch 2026-10-18T12:43:30Z.
- 127x01 new_actor block 34: own PGID 2460746, launch 2026-10-18T12:43:32Z.
- 127x01 new_actor block 35: own PGID 2460960, launch 2026-10-18T12:43:33Z.
- 127x01 new_actor block 36: own PGID 2461190, launch 2026-10-18T12:43:33Z.
- 127x01 new_actor block 37: own PGID 2461385, launch 2026-10-18T12:43:34Z.
- 127x04 new_actor block 38: own PGID 188898, launch 2026-10-18T12:43:35Z.
- 127x04 new_actor block 39: own PGID 189076, launch 2026-10-18T12:43:36Z.
- 127x04 new_actor block 40: own PGID 189254, launch 2026-10-18T12:43:36Z.
- 127x08 new_actor block 41: own PGID 1493912, launch 2026-10-18T12:43:37Z.
- 127x08 new_actor block 42: own PGID 1493945, launch 2026-10-18T12:43:37Z.
- 127x08 new_actor block 43: own PGID 1494011, launch 2026-10-18T12:43:37Z.
- 127x04 restore_capacity_extra block 44: own PGID 217997, launch 2026-10-18T12:47:09Z.

The once-only controller is 08 `helper-rotate-084.receipt.json`, PGID1492586. The new-source error monitor is 08 PGID1492537; any OwnCycle error after the approved fix contains the new cohort and records the exact case. Old source-328 actors are retired only after their respective replacements admit; old guards are retired only after their owned actors are gone. Blocks34–45 are all reserved, including extras44/45 before launch. Full durable state is mirrored to01 after each controller phase.

The fresh full G-S DEV reference (04 PGID189765) and explicit `--only 0,15` recovery (04 PGID189789) were detached once with8/2workers, CPU leases10/4 and nice15. They target360 and12 arm rows respectively. Both fresh outputs remain separate from historical failed banks; completed rows must all be clean with successful finished statuses before standalone validation. No confirm bank is used and no gate outcome is claimed. The source084 corpus scope is49.02929267% RoyaleSim-playable weight.

## Cycle-fidelity failures and amended training gate registration (2026-10-18T13:09:45Z)

The source084 early-refill patch still failed on actor case g40000027/v53 (RoyaleSim meta vs rl5): `Rage` was not in the own-cycle list. The fresh cohort's own groups were stopped and verified absent. Its G-S recovery also retained a `Barbarians` OwnCycle failure at case0-0015 and opponent command rejections at case0-0000; both fresh reference groups are stopped, with all rows retained. Evidence: `helper-source084-failure.json` on04/01/local05, SHA `6cac8c28286dcd9f514cb297126e288de89f407a1c347dbddc131223022db72f`. The actor policy-v53 checkpoint and calibration were preserved under04 `failures/source084/`, and the exact reviewed sampler case is in `helper-source084-actor-case.json` (seed2746899485152571, our seat1). No simulator replay was run.

The subsequent bbcb320 short gate also failed at DEV case0-0015: retained live-player errors were `Barbarians` not-in-list and public-play-inconsistent-with-ordinary-cycle. These were live-model errors, distinct from the framework exception. Its single retained raw row and bank are in `helper-gate-bb-failure.json`, SHA `fde9b178cf1f87d71c792a55c0de5d1c997f4665851b63cd15262f49b4862fad`. The DEV own group, gate guard and actor46 were stopped and verified absent; actor46 had remained in CPU admission and produced zero games. No bb production rotation or08 staging occurred. These two failures were each reported once to the owner; all earlier banks remain intact.

The owner then registered `8f5272934f456e930aa250bba45eaa9b3c259b71`: G-S uses `--keep-going`, retains unclean rows, and excludes a failed case from **every arm** in the readout. More than5% dropped among a row's input cases invalidates that row; it is not a gate pass/fail estimate. Every readout will report per-row dropped counts, IDs and causes, and SEARCH-opponent rejections separately. Later snapshot/confirm comparisons must take the union of failures across all arms, including cached reference failures, so the case mask remains identical. G-E and G-B protocols remain unchanged. The19-card exclusion set still restricts G-S to201606/411195 =49.02929267% of corpus weight.

A fresh source8f training gate is launched through a one-use controller-r2: actor47 on04,12workers, MAX_GAMES8,96 unique attempted games. It waits for all96 and normal worker completion; pass requires at most5% recorded RoyaleSim errors among RoyaleSim attempts, with zero our-engine/worker crashes. An early partial percentage is not a gate outcome. The full DEV reference is independently launched into fresh `evals/gs-dev-refs-all16-8f`,60cases per opponent, both reference arms, `--keep-going` (360arm rows). An earlier controller's SSH-to-self preflight failed before any child launch; that orchestration issue was corrected locally with a fresh r2 receipt/state, preserving the failed empty preflight. No product code changed.

A separate conditional controller is already launched and waits for the completed training-gate pass artifact. Only then it stages/sha-checks08, rechecks01/04, and resumes production using reserved fresh blocks48–58 through ordinary CPU admission and owned load guards. It reuses the already-launched full reference and the fixed remote sync groups. Learner-r2 and its flags stay unchanged. Under the amended registration, production residual RoyaleSim errors, including OwnCycle/unmapped games, remain recorded and subject to the5% hourly stop threshold; our-engine errors remain immediate failures. No short-gate outcome or gain is claimed here. S-CONFIRM1 remains unused.

## Amended training gate pass and production resumption (2026-10-18T13:21:32Z)

The amended source8f training gate passed at 2026-10-18T13:15:53Z:96 unique attempts,58 RoyaleSim games with1 recorded error (1.72413793%, at most5%), and38 our-engine games with0 errors. All12 workers recorded8 attempts and the actor group exited. The only error was caseg47000033/v58, Sam versusf1a2: `ArcherQueen` not-in-list in the frozen student's cycle tracker. Its full traceback remains in `helper-gate-8f-pass.json` on01/local05 (artifact SHA `b5bfcf6888014782f67fe3a3de673e6a0b298f6e455bec9b45cfea5a4a7be2c8`). The threshold applies to the completed gate, not an early partial ratio. This short implementation gate is not a policy-strength result. The gate result was sent once to the owner.

The existing conditional controller recognized the pass, staged source8f on08, reverified the exact source/repo trees and all7 model hashes on01/04/08, and launched production through CPU admission. Learner-r2 and its flags are unchanged; fixed remote sync groups are reused. Durable state was `waiting_admission` at 2026-10-18T13:20:50Z; new load guards own only the new blocks. Any old08 actor is retired only after its replacement admits. All48–58 are reserved by this active controller even before a receipt/BLOCKS entry exists. The already-launched full `--keep-going` DEV reference is reused, not duplicated.

- 127x08 error_monitor_launch block —: PGID1718968 at 2026-10-18T13:17:25Z.
- 127x01 guard_launch block —: PGID2773583 at 2026-10-18T13:18:28Z.
- 127x04 guard_launch block —: PGID460544 at 2026-10-18T13:18:28Z.
- 127x08 guard_launch block —: PGID1725371 at 2026-10-18T13:18:29Z.
- 127x01 actor_launch block 48: PGID2774102 at 2026-10-18T13:18:29Z.
- 127x01 actor_launch block 49: PGID2774215 at 2026-10-18T13:18:30Z.
- 127x01 actor_launch block 50: PGID2774308 at 2026-10-18T13:18:30Z.
- 127x01 actor_launch block 51: PGID2774387 at 2026-10-18T13:18:30Z.
- 127x04 actor_launch block 52: PGID461034 at 2026-10-18T13:18:31Z.
- 127x04 actor_launch block 53: PGID461245 at 2026-10-18T13:18:32Z.
- 127x04 actor_launch block 54: PGID461473 at 2026-10-18T13:18:32Z.
- 127x08 actor_launch block 55: PGID1725903 at 2026-10-18T13:18:33Z.
- 127x08 actor_launch block 56: PGID1726103 at 2026-10-18T13:18:34Z.
- 127x08 actor_launch block 57: PGID1726318 at 2026-10-18T13:18:35Z.

The production error monitor applies the registered5% completed-hour RoyaleSim threshold, including OwnCycle/unmapped errors; our-engine errors remain immediate failures. New empty load guards preserve collapse monitoring until their replacements admit. Per-row G-S drops remain a separate readout decision: union across arms, counts/causes reported, more than5% cases dropped makes that row invalid. G-S scope remains49.02929267% of corpus weight. The full DEV reference is incomplete, so no selection/gate outcome is reported for it.

G-E v50's original08 wrapper remained in admission with zero banks and zero games. Its own PGID1466486 was stopped and verified absent; the same frozen checkpoint (SHA `3be8ad0b4bceb373d6070b648a632581f887af7a7f56f66323ebeb6e2840b24b`), PF1 pins and paired DEV cases were placed on04 with fresh `ge-v50-r2.receipt.json`, PGID427485 at13:14:20Z. This is the sole active v50 screen. Original receipt/log/checkpoint metadata are retained. The validated v2 raw reference and cached paired scores were copied08→04 for local readout:184 files matched SHA checks, row size/mtime manifests matched without restoration, and no baseline game was rerun. The standalone v50 readout waits for120 Sam+60dd1 clean rows and both successful finished files. Legacy G-B v10 continues on its used CONFIRM1 bank; S-CONFIRM1 remains unused.

## Registered G-S drop limits and archetype reporting (2026-10-18T13:53:37Z)

Registered drop-limit implementation at 2026-10-18T13:53:33Z: RL-PREREG origin/main `4167a3c263e4e3d303b222d4008186d13c22af38` permits at most10% dropped input cases for SEARCH-opponent rows and5% for K4CW-fp/R3a. The earlier provisional invalidity of SEARCH4/60 is superseded:4/60=6.6667% is within the new limit. The existing source8f games, raw errors, cases and paired masks remain unchanged; no reference is rerun.

The four currently recorded dropped SEARCH cases are0-0015 (hog),0-0030 (giant),0-0039 (royalgiant),0-0047 (air), all live_errors. Each archetype accounts for1/4 drops; none exceeds50%. This is provisional drop accounting while the full360-row reference continues, not a completed reference or gate result.

Both prepared external readouts now list every dropped case, opponent deck, archetype and per-arm cause. They report per-row archetype counts; when an archetype contains strictly more than half the drops, its retained-case paired estimate and bootstrap interval appear separately, and the pooled estimate carries a concentration qualification. A wholly dropped archetype has n=0 and no estimable difference. Boundary checks(6/60 SEARCH valid,7 invalid;3/60 other valid,4 invalid), strict-majority checks and syntax checks passed. These helpers remain unlaunched until their complete input counts and finished statuses are available. Evaluation source stays8f; analysis records protocol commit `4167a3c263e4e3d303b222d4008186d13c22af38`. All G-S results retain the49.0292926714% RoyaleSim-playable corpus-weight scope.

Prepared readout SHA256s(command-checked):
59dfe1296759dd675e0f4021fee02cccae7aadb898b64b9852c0380cbd64c23e  /tmp/clasher-hp1rl-helper-sol/helper-gs-dev-reference-8f-readout.py
d933c66fe367f62cc012e36521a4da06281fd4bb30d5c2d6ebdce161fbd98d02  /tmp/clasher-hp1rl-helper-sol/helper-gs-snapshot-8f-readout.py


Version70 original G-E and G-S DEV screens launched once on04 through normal CPU admission. Frozen checkpoint SHA `c63aad2f4c0975a685813b4ba81d4c0520d9a062e4460986a20bf5faee70099b`, copied and checked at 2026-10-18T13:52:33Z; G-E PGID710603 at 2026-10-18T13:52:36Z, G-S PGID710649 at 2026-10-18T13:52:37Z. G-E retains its original120Sam+60dd1 clean-case protocol; G-S uses180 identical ALL-16 DEV cases, source8f and --keep-going. Both are selection work only; standalone readouts wait for successful completion. Version60 screens and version50's remainingdd1 row continue without duplication.

## DEV screen v50 (2026-10-18T14:24:27Z)

Snapshot SHA256 `3be8ad0b4bceb373d6070b648a632581f887af7a7f56f66323ebeb6e2840b24b`. All180 rows passed validation, paired exactly to the frozen fast-v2 baseline by full case identity. Both row runs finished with eight zero statuses; driver, pool, vocab, decode, level and case arguments matched the registration.

| Row | Opponent | Pairs | v50 score | v2 score | Paired difference | v50 plays/game | v2 plays/game |
|---|---|---:|---:|---:|---:|---:|---:|
| sam | LIVE-K4CW-r16-fp | 60 | 0.666667 | 0.516667 | +0.150000 | 47.366667 | 47.066667 |
| sam | R3a | 60 | 0.750000 | 0.583333 | +0.166667 | 46.300000 | 48.716667 |
| dd1 | LIVE-K4CW-r16-fp | 60 | 0.666667 | 0.533333 | +0.133333 | 43.316667 | 47.066667 |

Equal-weight screen score: **+0.150000**. All three differences nonnegative: True. Registered Sam play-rate sanity: True. Candidate predicate (screen >=+0.03, all differences >=0, Sam play sanity): True. DD1 plays/game are reported above for inspection. These DEV estimates are selection results, never gains.

Snapshot training record: update53/v50, train score=0.708333, KL=0.04013484, deploy-would-play/game=35.150000. Validation/readout: JOB/helper-ge-v50-readout.json on04/01/local05, SHA256 `02ca92f5f913b2f1e00d6fd8be95d589c0d419c467a93a806e2a462f244beb87`. Raw rows retained.

## Source8f rotation completion and measured throughput (2026-10-18T14:31:31Z)

The source8f actor rotation completed at 2026-10-18T14:01:29Z, after each remote replacement admitted through CPU admission. The remaining08 legacy groups31/32/33 and their old load/error monitors retired by owned receipts. New block58 (PGID1997962) launched13:59:20Z and admitted14:01:06Z, restoring08 to72 workers;01 has32 and04 has72. Load guards retain caps01≤60,04≤100 without a console user/70 with one,08≤100. Learner-r2 remains unchanged on its existing source and flags. Fixed remote sync groups are reused.

Post-rotation updates78–84, from2026-10-18T14:03:47Z to2026-10-18T14:21:26Z, measured **20.396601 updates/h**, versus the pre-scale reference5.903252/h. An increase is observed in this short window; source, league, rollout lag and guard activity prevent an isolated causal actor-count claim. Finished rollout backlog was337 at2026-10-18T14:23:00Z, below the960 reporting threshold. Evidence: `JOB/helper-cohort-8f-throughput.json` on01/local05, SHA `66d8f2f6e8b64168bbff12b0923e8e0f83f1ecaf7e0ed9da904f816dc3fd7ed6`. The source8f monitor's first completed60-minute RoyaleSim window recorded15 errors/1879 attempts (0.798297%), below the registered5% tolerance. The next window remains incomplete; no per-game tolerance breach is claimed. This is implementation/throughput evidence, not a strength result.

Version80 G-E and ALL-16 G-S DEV screens were launched once on04 under normal CPU admission: G-E PGID910704 at2026-10-18T14:22:39Z, G-S PGID910748 at2026-10-18T14:22:39Z. Frozen checkpoint SHA `c892887a7d037ee37fe83edf3edc2a5eac550626a1f1cc4a526e0ece774e0b7f` was copied and checked at2026-10-18T14:22:35Z; source and copied bytes matched. Their exact registered cases and standalone readouts follow the existing60/70 screens. No screen is a gain claim.

The missing Amendment1 secondary search-arm reference on the original G-E Sam DEV pool cases was launched separately on04, `gs-dev-search-ge-reference-8f.receipt.json`, PGID941867 at2026-10-18T14:26:51Z. It runs only res-lb-RF-wintp,60 cases per K4CW-fp/R3a, with source8f and --keep-going; no fast-v2 baseline game is repeated. This reference is separate from the primary all-deck corpus G-S reference. Future primary G-S results retain the49.02929267% RoyaleSim-playable corpus-weight scope and the registered10% SEARCH/5% other drop limits.

## G-S DEV all-deck reference validation (source8f) (2026-10-18T15:02:51Z)

The full source8f ALL-16 DEV reference validated at2026-10-18T15:00:57Z:360 raw arm rows,180 exact input cases,8 zero finished statuses, unchanged source/driver/factory/pool/vocab/corpus/model/level pins. The readout applied the registered10% SEARCH/5% K4CW-fp/R3a limits and an identical union-of-arm-failures mask. All three opponent rows are valid. Scope: **49.0292926714% of corpus deck weight is RoyaleSim-playable** (50.9707073286% excluded by the19-card set). This reference supports later DEV selection; it is not an RL gain or G-S confirm result.

| Opponent | Input pairs | Dropped | Retained | fast-v2 score [95% CI] | Search score [95% CI] | v2 − search [95% CI] | v2/search plays per game |
|---|---:|---:|---:|---|---|---|---|
| SEARCH | 60 | 4 | 56 | +0.339286 [+0.214286, +0.464286] | +0.732143 [+0.607143, +0.839286] | -0.392857 [-0.553571, -0.232143] | 49.892857/41.821429 |
| LIVE-K4CW-r16-fp | 60 | 0 | 60 | +0.550000 [+0.433333, +0.683333] | +0.716667 [+0.600000, +0.816667] | -0.166667 [-0.333333, +0.000000] | 48.250000/41.650000 |
| R3a | 60 | 0 | 60 | +0.700000 [+0.583333, +0.816667] | +0.800000 [+0.700000, +0.900000] | -0.100000 [-0.266667, +0.050000] | 46.100000/39.966667 |

Dropped cases (each excluded from every arm; all causes live_errors):

- 0-0015: opponent archetype **hog**, deck Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
- 0-0030: opponent archetype **giant**, deck Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
- 0-0039: opponent archetype **royalgiant**, deck Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
- 0-0047: opponent archetype **air**, deck Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.

Each of hog/giant/royalgiant/air accounts for1/4 drops (25%); no archetype exceeds50%. SEARCH drops4/60=6.6667% are valid under the pre-confirm registered10% limit. Other opponents drop0/60. Estimates are pooled over retained cases; the full per-arm raw errors and causes remain in the readout.

| Opponent | Archetype | Retained pairs | v2 − search [95% CI] |
|---|---|---:|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] |
| SEARCH | bait | 5 | -0.600000 [-1.000000, -0.200000] |
| SEARCH | giant | 9 | -0.222222 [-0.666667, +0.222222] |
| SEARCH | hog | 8 | -0.125000 [-0.500000, +0.250000] |
| SEARCH | other | 23 | -0.608696 [-0.782609, -0.391304] |
| SEARCH | siege | 7 | -0.142857 [-0.571429, +0.285714] |
| LIVE-K4CW-r16-fp | air | 9 | +0.000000 [-0.444444, +0.444444] |
| LIVE-K4CW-r16-fp | bait | 3 | -0.333333 [-1.000000, +0.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | -0.200000 [-0.533333, +0.133333] |
| LIVE-K4CW-r16-fp | hog | 10 | -0.100000 [-0.500000, +0.300000] |
| LIVE-K4CW-r16-fp | other | 14 | -0.214286 [-0.500000, +0.071429] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | -0.250000 [-0.625000, +0.250000] |
| R3a | air | 11 | +0.000000 [-0.272727, +0.272727] |
| R3a | bait | 6 | +0.000000 [-0.666667, +0.666667] |
| R3a | giant | 14 | +0.000000 [-0.285714, +0.285714] |
| R3a | hog | 6 | -0.333333 [-0.666667, +0.000000] |
| R3a | other | 19 | -0.105263 [-0.421053, +0.210526] |
| R3a | siege | 4 | -0.500000 [-1.000000, +0.000000] |

Recorded SEARCH-opponent rejection totals, including discarded raw rows: {"fast-v2": 1, "res-lb-RF-wintp": 6}. Missing rejection metrics in early-error raw rows: {"fast-v2": 0, "res-lb-RF-wintp": 0}. These missing metrics are reported as missing, not assumed observed zero. Our-seat rejections and translator drops remain unclean.

The first04 analysis group PGID1103157 never admitted or ran Python. After the complete reference and v60/v70 artifacts were staged04→08 with every file's SHA/size/mtime verified and all pinned dependencies matched, that owned queued group was terminated and verified gone; no game was rerun. Fresh08 reference readout receipt PGID2402727 launched15:00:40Z and completed successfully. Cache copied08/04/01/local05: `JOB/helper-gs-dev-reference-8f-readout.json`, SHA `4df65c0db2c4b77ecebb091b37fc5ca9628f3b3fa91e070945677006157e0e90`. Validation metadata preserve all360 rows, exact cases and original errors. Snapshot60's standalone paired readout is now launched on the validated cache; later selection results are reported separately. No confirm bank has been used by this reference.

## G-S DEV screen v60 (source8f; selection only) (2026-10-18T15:04:13Z)

Snapshot60 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `d1c812aaca252b2965a139e1757185bb2cc4cf94180eaaaabea6857d8da2e983`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v60 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v60 − search [95% CI] | v60 − v2 [95% CI] | v60/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.589286 [+0.464286, +0.714286] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.142857 [-0.303571, +0.035714] | +0.250000 [+0.089286, +0.410714] | 42.321429/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.750000 [+0.633333, +0.850000] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.033333 [-0.116667, +0.183333] | +0.200000 [+0.050000, +0.350000] | 46.583333/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.833333 [+0.733333, +0.916667] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.033333 [-0.083333, +0.150000] | +0.133333 [+0.000000, +0.266667] | 49.466667/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v60 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. S-CONFIRM1 remains unused at this screen's publication. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.500000 [-1.000000, +0.000000] | -0.250000 [-0.750000, +0.000000] |
| SEARCH | bait | 5 | -0.400000 [-0.800000, +0.000000] | +0.200000 [-0.400000, +0.800000] |
| SEARCH | giant | 9 | -0.111111 [-0.444444, +0.222222] | +0.111111 [-0.222222, +0.444444] |
| SEARCH | hog | 8 | +0.125000 [-0.250000, +0.500000] | +0.250000 [-0.250000, +0.750000] |
| SEARCH | other | 23 | -0.173913 [-0.434783, +0.130435] | +0.434783 [+0.217391, +0.652174] |
| SEARCH | siege | 7 | +0.000000 [-0.428571, +0.428571] | +0.142857 [+0.000000, +0.428571] |
| LIVE-K4CW-r16-fp | air | 9 | +0.000000 [-0.444444, +0.444444] | +0.000000 [-0.444444, +0.444444] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.333333 [+0.000000, +1.000000] | +0.666667 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | -0.133333 [-0.466667, +0.200000] | +0.066667 [-0.200000, +0.333333] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.300000 [-0.100000, +0.700000] | +0.400000 [+0.100000, +0.700000] |
| LIVE-K4CW-r16-fp | other | 14 | -0.071429 [-0.214286, +0.000000] | +0.142857 [-0.142857, +0.428571] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.125000 [+0.000000, +0.375000] | +0.375000 [+0.125000, +0.750000] |
| R3a | air | 11 | +0.181818 [+0.000000, +0.454545] | +0.181818 [+0.000000, +0.454545] |
| R3a | bait | 6 | +0.000000 [-0.666667, +0.666667] | +0.000000 [-0.500000, +0.500000] |
| R3a | giant | 14 | +0.071429 [-0.142857, +0.285714] | +0.071429 [-0.142857, +0.285714] |
| R3a | hog | 6 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +0.666667] |
| R3a | other | 19 | -0.052632 [-0.210526, +0.105263] | +0.052632 [-0.263158, +0.368421] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on08 after SHA/size/mtime-verified staging of completed04 outputs and matching pinned dependencies, through detachedcpu_job2/nice15. Readout `JOB/helper-gs-dev-v60-8f-readout.json` on08/04/01/local05, SHA `e38b34724399b25258e88764fd612a834a9b048ddcf393191cad94c935b25a78`.

## G-S DEV screen v70 (source8f; selection only) (2026-10-18T15:05:13Z)

Snapshot70 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `c63aad2f4c0975a685813b4ba81d4c0520d9a062e4460986a20bf5faee70099b`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v70 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v70 − search [95% CI] | v70 − v2 [95% CI] | v70/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.678571 [+0.553571, +0.803571] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.053571 [-0.214286, +0.089286] | +0.339286 [+0.196429, +0.482143] | 43.732143/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.716667 [+0.600000, +0.816667] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.000000 [-0.166667, +0.166667] | +0.166667 [+0.016667, +0.300000] | 44.300000/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.866667 [+0.783333, +0.950000] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.066667 [-0.066667, +0.200000] | +0.166667 [+0.050000, +0.283333] | 44.233333/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v70 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| SEARCH | bait | 5 | -0.400000 [-0.800000, +0.000000] | +0.200000 [+0.000000, +0.600000] |
| SEARCH | giant | 9 | -0.111111 [-0.444444, +0.222222] | +0.111111 [-0.222222, +0.444444] |
| SEARCH | hog | 8 | +0.125000 [-0.375000, +0.625000] | +0.250000 [-0.250000, +0.750000] |
| SEARCH | other | 23 | +0.000000 [-0.217391, +0.217391] | +0.608696 [+0.391304, +0.826087] |
| SEARCH | siege | 7 | +0.000000 [-0.428571, +0.428571] | +0.142857 [+0.000000, +0.428571] |
| LIVE-K4CW-r16-fp | air | 9 | +0.111111 [-0.222222, +0.444444] | +0.111111 [-0.222222, +0.444444] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [-1.000000, +1.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | -0.066667 [-0.333333, +0.200000] | +0.133333 [-0.200000, +0.466667] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.100000 [-0.400000, +0.600000] | +0.200000 [-0.200000, +0.600000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.000000 [-0.285714, +0.285714] | +0.214286 [-0.071429, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | -0.125000 [-0.500000, +0.250000] | +0.125000 [-0.250000, +0.500000] |
| R3a | air | 11 | +0.090909 [+0.000000, +0.272727] | +0.090909 [+0.000000, +0.272727] |
| R3a | bait | 6 | +0.166667 [-0.666667, +0.833333] | +0.166667 [+0.000000, +0.500000] |
| R3a | giant | 14 | -0.071429 [-0.357143, +0.214286] | -0.071429 [-0.285714, +0.142857] |
| R3a | hog | 6 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +0.666667] |
| R3a | other | 19 | +0.157895 [-0.052632, +0.368421] | +0.263158 [+0.105263, +0.473684] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on08 after SHA/size/mtime-verified staging of completed04 outputs and matching pinned dependencies, through detachedcpu_job2/nice15. Readout `JOB/helper-gs-dev-v70-8f-readout.json` on08/04/01/local05, SHA `3e7853341eb12263063cc146b87ca41fdee10ba0044ceb997ebcb83669dbfad2`.

## DEV screen v60 (2026-10-18T15:09:30Z)

Snapshot SHA256 `d1c812aaca252b2965a139e1757185bb2cc4cf94180eaaaabea6857d8da2e983`. All180 rows passed validation, paired exactly to the frozen fast-v2 baseline by full case identity. Both row runs finished with eight zero statuses; driver, pool, vocab, decode, level and case arguments matched the registration.

| Row | Opponent | Pairs | v60 score | v2 score | Paired difference | v60 plays/game | v2 plays/game |
|---|---|---:|---:|---:|---:|---:|---:|
| sam | LIVE-K4CW-r16-fp | 60 | 0.666667 | 0.516667 | +0.150000 | 47.966667 | 47.066667 |
| sam | R3a | 60 | 0.833333 | 0.583333 | +0.250000 | 47.866667 | 48.716667 |
| dd1 | LIVE-K4CW-r16-fp | 60 | 0.750000 | 0.533333 | +0.216667 | 43.450000 | 47.066667 |

Equal-weight screen score: **+0.205556**. All three differences nonnegative: True. Registered Sam play-rate sanity: True. Candidate predicate (screen >=+0.03, all differences >=0, Sam play sanity): True. DD1 plays/game are reported above for inspection. These DEV estimates are selection results, never gains.

Snapshot training record: update63/v60, train score=0.676230, KL=0.04289149, deploy-would-play/game=36.508197. Validation/readout: JOB/helper-ge-v60-readout.json on04/01/local05, SHA256 `a9e7eaa912586f106167fa5da4037e77a6d4cd243348ac9fbe1bae007dae00b0`. Raw rows retained.

## DEV screen v70 (2026-10-18T15:09:39Z)

Snapshot SHA256 `c63aad2f4c0975a685813b4ba81d4c0520d9a062e4460986a20bf5faee70099b`. All180 rows passed validation, paired exactly to the frozen fast-v2 baseline by full case identity. Both row runs finished with eight zero statuses; driver, pool, vocab, decode, level and case arguments matched the registration.

| Row | Opponent | Pairs | v70 score | v2 score | Paired difference | v70 plays/game | v2 plays/game |
|---|---|---:|---:|---:|---:|---:|---:|
| sam | LIVE-K4CW-r16-fp | 60 | 0.800000 | 0.516667 | +0.283333 | 43.066667 | 47.066667 |
| sam | R3a | 60 | 0.850000 | 0.583333 | +0.266667 | 47.700000 | 48.716667 |
| dd1 | LIVE-K4CW-r16-fp | 60 | 0.650000 | 0.533333 | +0.116667 | 44.700000 | 47.066667 |

Equal-weight screen score: **+0.222222**. All three differences nonnegative: True. Registered Sam play-rate sanity: True. Candidate predicate (screen >=+0.03, all differences >=0, Sam play sanity): True. DD1 plays/game are reported above for inspection. These DEV estimates are selection results, never gains.

Snapshot training record: update73/v70, train score=0.683398, KL=0.04350179, deploy-would-play/game=35.471042. Validation/readout: JOB/helper-ge-v70-readout.json on04/01/local05, SHA256 `f31f3079ace3d564c6504e7d2cc7925a33afc0eb815fcb479e375a03f2d251e7`. Raw rows retained.

## G-S DEV screen v80 (source8f; selection only) (2026-10-18T15:26:00Z)

Snapshot80 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `c892887a7d037ee37fe83edf3edc2a5eac550626a1f1cc4a526e0ece774e0b7f`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v80 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v80 − search [95% CI] | v80 − v2 [95% CI] | v80/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.535714 [+0.410714, +0.660714] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.196429 [-0.375000, -0.035714] | +0.196429 [+0.035714, +0.357143] | 46.160714/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.716667 [+0.600000, +0.833333] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.000000 [-0.150000, +0.150000] | +0.166667 [+0.016667, +0.316667] | 45.133333/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.900000 [+0.816667, +0.966667] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.100000 [-0.033333, +0.233333] | +0.200000 [+0.083333, +0.316667] | 43.616667/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v80 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| SEARCH | bait | 5 | -0.200000 [-0.600000, +0.000000] | +0.400000 [+0.000000, +0.800000] |
| SEARCH | giant | 9 | -0.333333 [-0.777778, +0.111111] | -0.111111 [-0.555556, +0.333333] |
| SEARCH | hog | 8 | +0.250000 [-0.250000, +0.625000] | +0.375000 [+0.125000, +0.750000] |
| SEARCH | other | 23 | -0.347826 [-0.608696, -0.086957] | +0.260870 [+0.000000, +0.521739] |
| SEARCH | siege | 7 | +0.000000 [-0.571429, +0.571429] | +0.142857 [-0.285714, +0.571429] |
| LIVE-K4CW-r16-fp | air | 9 | -0.111111 [-0.444444, +0.222222] | -0.111111 [-0.444444, +0.222222] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [-1.000000, +1.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.000000 [-0.333333, +0.333333] | +0.200000 [-0.066667, +0.466667] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.100000 [-0.300000, +0.500000] | +0.200000 [-0.200000, +0.600000] |
| LIVE-K4CW-r16-fp | other | 14 | -0.071429 [-0.285714, +0.142857] | +0.142857 [-0.214286, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.125000 [+0.000000, +0.375000] | +0.375000 [+0.125000, +0.750000] |
| R3a | air | 11 | +0.181818 [+0.000000, +0.454545] | +0.181818 [+0.000000, +0.454545] |
| R3a | bait | 6 | +0.333333 [-0.333333, +0.833333] | +0.333333 [+0.000000, +0.666667] |
| R3a | giant | 14 | +0.071429 [-0.142857, +0.357143] | +0.071429 [-0.142857, +0.285714] |
| R3a | hog | 6 | -0.166667 [-0.500000, +0.000000] | +0.166667 [+0.000000, +0.500000] |
| R3a | other | 19 | +0.105263 [-0.157895, +0.368421] | +0.210526 [+0.000000, +0.473684] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on08 after SHA/size/mtime-verified staging of completed04 outputs and matching pinned dependencies, through detachedcpu_job2/nice15. Readout `JOB/helper-gs-dev-v80-8f-readout.json` on08/04/01/local05, SHA `9725b28da9398ba136d6fd731704240c4ff243afc33e1e4a07c9b4e55f31cc7d`.

## DEV screen v80 (2026-10-18T15:33:43Z)

Snapshot SHA256 `c892887a7d037ee37fe83edf3edc2a5eac550626a1f1cc4a526e0ece774e0b7f`. All180 rows passed validation, paired exactly to the frozen fast-v2 baseline by full case identity. Both row runs finished with eight zero statuses; driver, pool, vocab, decode, level and case arguments matched the registration.

| Row | Opponent | Pairs | v80 score | v2 score | Paired difference | v80 plays/game | v2 plays/game |
|---|---|---:|---:|---:|---:|---:|---:|
| sam | LIVE-K4CW-r16-fp | 60 | 0.683333 | 0.516667 | +0.166667 | 44.300000 | 47.066667 |
| sam | R3a | 60 | 0.783333 | 0.583333 | +0.200000 | 48.433333 | 48.716667 |
| dd1 | LIVE-K4CW-r16-fp | 60 | 0.733333 | 0.533333 | +0.200000 | 44.600000 | 47.066667 |

Equal-weight screen score: **+0.188889**. All three differences nonnegative: True. Registered Sam play-rate sanity: True. Candidate predicate (screen >=+0.03, all differences >=0, Sam play sanity): True. DD1 plays/game are reported above for inspection. These DEV estimates are selection results, never gains.

Snapshot training record: update83/v80, train score=0.732794, KL=0.04417272, deploy-would-play/game=36.684211. Validation/readout: JOB/helper-ge-v80-readout.json on04/01/local05, SHA256 `0327f97f6180e103bb9b6a3b5fe88f33eb45515c95914fb71cc98efaf068edf9`. Raw rows retained.

## Original DEV SEARCH secondary reference: invalid translator coverage (2026-10-18T15:35:10Z)

The original-G-E-case SEARCH reference finished all120 raw rows with eight zero worker statuses. Full deck/seed/seat/opponent identities match the frozen fast-v2 Sam DEV cases, and source8f, driver, factory, pool, vocab and L16 levels were checked. The readout additionally checks translator unmapped/missing/no_template counters, beyond the driver's `problems(row)`. **Both secondary opponent rows are invalid**: 14/60 K4CW-fp cases (23.3333%) and18/60 R3a cases (30%) contain `unmapped_unit:SpearGoblin_Dummy`, exceeding the5% limit. All32 affected decks include GoblinHut. The original-pool sampler retains those decks: its `--opp-exclude` argument does not filter cases without `--opp-decks`. No case or game was retried or silently discarded.

This is the Amendment1 original-BattleLog-pool secondary reference, not Amendment2's ALL-16 reference. **The ALL-16 primary reference remains valid**, and its RoyaleSim-playable corpus-weight scope remains49.0292926714% (50.9707073286% excluded). No policy strength or G-S pass/fail claim is made from this invalid secondary. Production continues under its separate completed-hour error tolerance.

LIVE-K4CW-r16-fp: 14/60 dropped, 46 retained, valid=False. Archetypes {"air": 2, "bait": 2, "giant": 8, "other": 2}. Retained-case pooled estimate; >50% of drops concentrated in giant, see separate estimates.

- 0-0001 / giant: MiniPekka, BattleRam, GoblinCage, Goblins, GoblinHut, Giant, Barbarians, SpearGoblins; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 178}.
- 0-0007 / giant: Giant, Wizard, GoblinBarrel, Barbarians, Rocket, GoblinHut, Bomber, Knight; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 538}.
- 0-0009 / bait: GoblinBarrel, SkeletonDragons, Barbarians, Knight, Valkyrie, Arrows, Goblins, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 1198}.
- 0-0010 / air: Knight, BabyDragon, MiniPekka, GoblinHut, Giant, Goblins, Fireball, Minions; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 54}.
- 0-0020 / other: Archers, GoblinHut, GoblinGang, Minions, Musketeer, Fireball, Knight, Tombstone; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 182}.
- 0-0025 / bait: GoblinHut, GoblinBarrel, Barbarians, Valkyrie, Goblins, Knight, Arrows, SkeletonDragons; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 78}.
- 0-0030 / giant: Arrows, GoblinHut, Goblins, Fireball, Tombstone, SpearGoblins, Giant, GoblinCage; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 1938}.
- 0-0041 / giant: Fireball, Bomber, Giant, Barbarians, MiniPekka, MegaMinion, GoblinHut, Valkyrie; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 286}.
- 0-0042 / air: Goblins, Minions, Giant, Fireball, Knight, MiniPekka, BabyDragon, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 308}.
- 0-0044 / giant: Bomber, Valkyrie, GoblinCage, Fireball, Tombstone, Giant, MiniPekka, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 44}.
- 0-0046 / giant: GoblinHut, Fireball, BattleRam, Giant, GoblinCage, Barbarians, Valkyrie, Musketeer; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 150}.
- 0-0050 / other: Arrows, Archers, SpearGoblins, Knight, Fireball, Minions, Goblins, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 236}.
- 0-0054 / giant: Fireball, Valkyrie, GoblinHut, Bomber, Barbarians, Giant, MegaMinion, MiniPekka; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 670}.
- 0-0055 / giant: Fireball, Giant, Knight, Musketeer, GoblinHut, Bomber, Valkyrie, Archers; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 108}.

R3a: 18/60 dropped, 42 retained, valid=False. Archetypes {"air": 1, "bait": 2, "giant": 11, "hog": 2, "other": 2}. Retained-case pooled estimate; >50% of drops concentrated in giant, see separate estimates.

- 1-0005 / other: Valkyrie, Goblins, SpearGoblins, Tombstone, Bomber, GoblinCage, Skeletons, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 1578}.
- 1-0006 / giant: Goblins, Giant, MiniPekka, BattleRam, GoblinCage, Barbarians, SpearGoblins, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 386}.
- 1-0011 / giant: GoblinHut, Tombstone, Giant, MiniPekka, SpearGoblins, Fireball, Bomber, Minions; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 366}.
- 1-0013 / giant: Knight, SpearGoblins, GoblinHut, MiniPekka, Giant, Goblins, Valkyrie, GoblinCage; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 496}.
- 1-0014 / giant: Skeletons, MiniPekka, Fireball, GoblinHut, Giant, Tombstone, Bomber, Goblins; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 764}.
- 1-0019 / giant: Valkyrie, MiniPekka, Tombstone, Fireball, Giant, Musketeer, GoblinHut, GoblinCage; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 714}.
- 1-0024 / giant: MiniPekka, Giant, Barbarians, Bomber, Fireball, Valkyrie, MegaMinion, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 1736}.
- 1-0027 / giant: Goblins, GoblinHut, Archers, Valkyrie, Minions, Giant, MiniPekka, Bomber; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 436}.
- 1-0028 / giant: Knight, SpearGoblins, GoblinCage, Goblins, MiniPekka, Giant, GoblinHut, Fireball; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 426}.
- 1-0029 / giant: Bomber, Valkyrie, Fireball, MiniPekka, Barbarians, MegaMinion, Giant, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 884}.
- 1-0030 / other: Skeletons, GoblinHut, Valkyrie, SpearGoblins, Bomber, Goblins, Tombstone, GoblinCage; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 606}.
- 1-0035 / hog: HogRider, Valkyrie, Wizard, MegaMinion, GoblinHut, BombTower, MiniPekka, SpearGoblins; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 314}.
- 1-0040 / bait: GoblinHut, SkeletonDragons, Barbarians, Valkyrie, Knight, Arrows, GoblinBarrel, Goblins; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 416}.
- 1-0041 / bait: GoblinHut, GoblinBarrel, Arrows, SkeletonDragons, Barbarians, Goblins, Valkyrie, Knight; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 516}.
- 1-0047 / air: BabyDragon, Knight, Minions, Giant, GoblinBarrel, MiniPekka, Fireball, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 578}.
- 1-0048 / giant: SpearGoblins, Giant, Goblins, Fireball, Arrows, GoblinHut, GoblinCage, Tombstone; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 192}.
- 1-0052 / giant: GoblinCage, MiniPekka, Goblins, Barbarians, GoblinHut, Giant, BattleRam, SpearGoblins; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 680}.
- 1-0058 / hog: MiniPekka, Valkyrie, Wizard, HogRider, SpearGoblins, BombTower, MegaMinion, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 224}.

These paired estimates are descriptive retained-case comparisons only. Each comparison excludes the same failed case from both arms. Original G-E readouts remain unchanged and retain their clean-case requirements. Giant contains >50% of drops in each row (8/14 K4CW-fp,11/18 R3a), so its paired estimates are reported separately; pooled interpretation is qualified. All CIs use4000 case-bootstrap draws, Random(0), sorted[100]/[3899], computed on08 under cpu_job2/nice15.

| Policy | Opponent | Retained pairs | Policy − search [95% CI], qualified pooled | Giant retained pairs | Giant policy − search [95% CI] | Policy/search plays |
|---|---|---:|---|---:|---|---|
| v2 | LIVE-K4CW-r16-fp | 46 | -0.282609 [-0.434783, -0.130435] | 12 | -0.166667 [-0.500000, +0.166667] | 47.956522/45.065217 |
| v2 | R3a | 42 | -0.190476 [-0.357143, -0.023810] | 17 | -0.117647 [-0.411765, +0.176471] | 48.119048/41.595238 |
| v10 | LIVE-K4CW-r16-fp | 46 | -0.152174 [-0.326087, +0.021739] | 12 | +0.083333 [-0.166667, +0.333333] | 45.956522/45.065217 |
| v10 | R3a | 42 | -0.047619 [-0.238095, +0.142857] | 17 | +0.176471 [-0.117647, +0.470588] | 49.809524/41.595238 |
| v20 | LIVE-K4CW-r16-fp | 46 | -0.152174 [-0.304348, +0.000000] | 12 | +0.000000 [-0.416667, +0.416667] | 47.652174/45.065217 |
| v20 | R3a | 42 | -0.047619 [-0.238095, +0.142857] | 17 | +0.176471 [-0.117647, +0.470588] | 47.428571/41.595238 |
| v30 | LIVE-K4CW-r16-fp | 46 | -0.152174 [-0.347826, +0.043478] | 12 | +0.166667 [-0.250000, +0.583333] | 44.000000/45.065217 |
| v30 | R3a | 42 | +0.047619 [-0.095238, +0.190476] | 17 | +0.294118 [+0.117647, +0.529412] | 47.619048/41.595238 |
| v40 | LIVE-K4CW-r16-fp | 46 | -0.152174 [-0.326087, +0.021739] | 12 | -0.250000 [-0.583333, +0.083333] | 46.608696/45.065217 |
| v40 | R3a | 42 | -0.023810 [-0.214286, +0.166667] | 17 | +0.176471 [-0.176471, +0.529412] | 49.309524/41.595238 |
| v50 | LIVE-K4CW-r16-fp | 46 | -0.130435 [-0.326087, +0.065217] | 12 | +0.083333 [-0.333333, +0.500000] | 45.869565/45.065217 |
| v50 | R3a | 42 | -0.023810 [-0.190476, +0.142857] | 17 | +0.235294 [+0.000000, +0.529412] | 44.261905/41.595238 |
| v60 | LIVE-K4CW-r16-fp | 46 | -0.086957 [-0.260870, +0.086957] | 12 | +0.083333 [-0.166667, +0.333333] | 44.913043/45.065217 |
| v60 | R3a | 42 | +0.047619 [-0.119048, +0.214286] | 17 | +0.235294 [-0.058824, +0.529412] | 45.976190/41.595238 |
| v70 | LIVE-K4CW-r16-fp | 46 | -0.021739 [-0.217391, +0.152174] | 12 | +0.333333 [+0.000000, +0.666667] | 43.217391/45.065217 |
| v70 | R3a | 42 | +0.095238 [-0.071429, +0.261905] | 17 | +0.176471 [-0.176471, +0.529412] | 44.880952/41.595238 |
| v80 | LIVE-K4CW-r16-fp | 46 | -0.086957 [-0.260870, +0.086957] | 12 | +0.083333 [-0.250000, +0.416667] | 43.326087/45.065217 |
| v80 | R3a | 42 | +0.000000 [-0.166667, +0.166667] | 17 | +0.176471 [-0.117647, +0.470588] | 46.047619/41.595238 |

Full per-archetype estimates, clean compact search scores, raw row SHA/size/mtime manifests, exact case identities and cached policy-readout SHA provenance are in `JOB/helper-gs-search-ge-secondary-readout.json` on08/04/01/local05, SHA `296f4dbc9f864d3d6a400caf8381f2a28a0d256829fa4a72d2602e373ce6cadb`. Reference output `evals/gs-dev-search-ge-reference-8f` remains intact on04 and in verified08 analysis staging. Standalone analysis receipt `gs-dev-search-ge-reference-8f-readout.receipt.json` PGID2616102 launched15:33:28Z and exited normally. This invalid reference will not be rerun without a dated owner protocol decision. S-CONFIRM1 remains unused; this work consumes no confirm bank.

## G-E moves to ALL-16 plus dd1; v110 launch receipts (2026-10-18T15:41:33Z)

Registered protocol `b6cc6237958777898c6dbb6e60f3382bd9bf3ba2` (owner15:36:01Z) now uses ALL-16 DEV plus dd1. New snapshots run only the candidate arm on the already registered ALL-16 cases (DEV+400000,60 per SEARCH/K4CW-fp/R3a), reusing the completed v2/search references. The equal screen is [ALL-16 K4CW-fp vN−v2 + ALL-16 R3a vN−v2 + dd1 vN−v2]/3; SEARCH contributes no weight. Report vN−search per ALL-16 row; a sole dd1 SEARCH reference has been queued because none existed, allowing that secondary contrast too once validated. No source/archive replacement, actor/learner restart or baseline rerun. Source8f and primary RoyaleSim-playable corpus-weight scope49.0292926714% remain.

At2026-10-18T15:37:05Z snapshot110 copied01→04 with matching SHA `04068fc9b87d0f3c8bcf9246187ea4738b4277dc649651243355a7b9299bc35a`. Exactly two candidate jobs launched04 at2026-10-18T15:37:09Z:

- `ge-v110.receipt.json`, PGID1416522: **dd1 only**,60 cases vs K4CW-fp, original pinned PF1 source and DEV+200000.
- `gs-dev-v110-8f.receipt.json`, PGID1416566: ALL-16 candidate180 rows, source8f, --keep-going. These rows serve both revised G-E and the G-S DEV selector; no duplicate ALL-16 games.

Both via ordinary cpu_job/W8/nice15 admission,04cap100/70 if who. No BattleLog Sam row is launched for110 or later. Already-running90/100 wrappers remain intact; their existing Sam rows become historical artifacts, and only their ALL-16+dd1 rows will enter revised screens. Historic G-E up through80 remains published under its earlier definition; no cross-definition pooled comparison.

`ge-dd1-search-reference-8f.receipt.json` PGID1436340 queued04 at2026-10-18T15:39:46Z: search-only,60 dd1 cases at3690083941700208, same frozen case identity, source8f/keep-going. This is the first dd1 SEARCH reference, not a rerun of v2 or the invalid original-Sam reference. Keep every raw error; readout applies5% K4CW-fp validity and reports dropped IDs/decks/causes/archetypes, including any >50% concentration separately. dd1−v2 remains the registered score contribution; an unavailable/invalid dd1 search reference must be labelled, never imputed or used for a strength claim.

Prepared only (not launched): `helper-ge-all16-readout.py N` validates completed GS DEV readout plus clean dd1, computes the revised equal mean, and reports SEARCH separately; `helper-ge-dd1-search-readout.py` requires60 rows+8 zero statuses. Both syntax checked and staged04/08. Neither can run before complete inputs. Required future result publisher `publish-ge-all16-screen.py N`; use its distinct readout filename `helper-ge-vN-all16-readout.json`, not the retired original-Sam helper.

Original-Sam secondary failure was published cdb3d08f5df7513cbed6df376e3fac39dcff6282 and reported once to owner; no retry. ALL-16 reference and production continue unchanged; S-CONFIRM1 unused.

## G-S DEV screen v90 (source8f; selection only) (2026-10-18T15:57:31Z)

Snapshot90 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `68ff703ef417d246f354de426a5282ea223d785cc239a95a3cb3937248e2ee65`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v90 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v90 − search [95% CI] | v90 − v2 [95% CI] | v90/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.500000 [+0.375000, +0.625000] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.232143 [-0.392857, -0.071429] | +0.160714 [-0.017857, +0.339286] | 45.767857/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.633333 [+0.500000, +0.750000] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | -0.083333 [-0.233333, +0.050000] | +0.083333 [-0.066667, +0.233333] | 47.966667/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.800000 [+0.683333, +0.900000] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.000000 [-0.150000, +0.150000] | +0.100000 [-0.033333, +0.233333] | 46.533333/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v90 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.500000 [-1.000000, +0.000000] | -0.250000 [-0.750000, +0.000000] |
| SEARCH | bait | 5 | -0.600000 [-1.000000, -0.200000] | +0.000000 [-0.600000, +0.600000] |
| SEARCH | giant | 9 | -0.222222 [-0.555556, +0.000000] | +0.000000 [-0.555556, +0.555556] |
| SEARCH | hog | 8 | -0.125000 [-0.500000, +0.250000] | +0.000000 [-0.375000, +0.375000] |
| SEARCH | other | 23 | -0.173913 [-0.391304, +0.043478] | +0.434783 [+0.173913, +0.695652] |
| SEARCH | siege | 7 | -0.142857 [-0.714286, +0.428571] | +0.000000 [-0.571429, +0.571429] |
| LIVE-K4CW-r16-fp | air | 9 | -0.111111 [-0.444444, +0.222222] | -0.111111 [-0.444444, +0.222222] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [-1.000000, +1.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | -0.133333 [-0.466667, +0.200000] | +0.066667 [-0.133333, +0.266667] |
| LIVE-K4CW-r16-fp | hog | 10 | -0.100000 [-0.300000, +0.000000] | +0.000000 [-0.400000, +0.400000] |
| LIVE-K4CW-r16-fp | other | 14 | -0.071429 [-0.357143, +0.214286] | +0.142857 [-0.214286, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.000000 [+0.000000, +0.000000] | +0.250000 [-0.250000, +0.625000] |
| R3a | air | 11 | +0.000000 [-0.363636, +0.363636] | +0.000000 [-0.272727, +0.272727] |
| R3a | bait | 6 | +0.166667 [-0.666667, +0.833333] | +0.166667 [+0.000000, +0.500000] |
| R3a | giant | 14 | +0.000000 [-0.285714, +0.285714] | +0.000000 [-0.285714, +0.285714] |
| R3a | hog | 6 | -0.333333 [-0.666667, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| R3a | other | 19 | +0.052632 [-0.157895, +0.263158] | +0.157895 [-0.105263, +0.421053] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. Completed04 artifacts also have a SHA/size/mtime-verified08 staging copy; this does not rerun games. Readout `JOB/helper-gs-dev-v90-8f-readout.json` on08/04/01/local05, SHA `dd2f64a7e8860d343ffdddc606311d34bca7c26b03c4fbb23b5f12100295ee80`.

## Revised ALL-16 plus dd1 DEV screen v90 (selection only) (2026-10-18T15:58:20Z)

Revised G-E per15:36:01Z registration `b6cc6237958777898c6dbb6e60f3382bd9bf3ba2`: reuse the completed180-case ALL-16 candidate and validated frozen search/v2 references; add the clean60-case dd1 row. No new BattleLog-pool Sam DEV row is scheduled. Checkpoint `68ff703ef417d246f354de426a5282ea223d785cc239a95a3cb3937248e2ee65`. ALL-16 scope:49.0292926714% of corpus weight RoyaleSim-playable. Raw unclean cases remain preserved and identically masked across ALL-16 arms under the registered10% SEARCH/5% other limits. dd1 remains clean-only, exactly paired to the frozen v2 dd1 cases.

| Row | Opponent | Pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---|---:|---:|---|---|---|
| all16 | SEARCH | 56 | +0.160714 | -0.232143 [-0.392857,-0.071429] | 45.767857/49.892857 | True |
| all16 | LIVE-K4CW-r16-fp | 60 | +0.083333 | -0.083333 [-0.233333,+0.050000] | 47.966667/48.250000 | True |
| all16 | R3a | 60 | +0.100000 | +0.000000 [-0.150000,+0.150000] | 46.533333/46.100000 | True |
| dd1 | LIVE-K4CW-r16-fp | 60 | +0.233333 | not available: no registered dd1 search reference | 42.850000/47.066667 | True |

Equal screen (ALL-16 K4CW-fp, ALL-16 R3a, dd1 K4CW-fp vs v2): 0.1388888888888889; screen valid=True, all three nonnegative=True, ALL-16 play sanity=True, dd1 plays in20..65=True, candidate predicate=True. SEARCH is reported separately and is excluded from this equal mean. Registered G-S SEARCH selector=False; the G-E candidate predicate alone does not qualify G-S. These are DEV selection contrasts, never gains. This uses a changed screen dataset; historical BattleLog Sam screen means are retained as history, not pooled with this definition.

all16/SEARCH: dropped4/60, IDs ["0-0015", "0-0030", "0-0039", "0-0047"]; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
all16/LIVE-K4CW-r16-fp: dropped0/60, IDs []; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60, IDs []; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


ALL-16 full per-archetype CIs and raw case details in `JOB/helper-gs-dev-v90-8f-readout.json`; SHA `dd2f64a7e8860d343ffdddc606311d34bca7c26b03c4fbb23b5f12100295ee80`. Revised composite readout `JOB/helper-ge-v90-all16-readout.json` on08/04/01/local05, SHA `b0a3f3f0efe9d6d8f6155672afe28a1f9c9c2d134de6cf32d0832e68fb6ee9b0`; raw row hashes, bank/finished records and checkpoint revalidated by detached cpu_job2/nice15 analysis. No baseline rerun.

## DD1 SEARCH reference launch correction and updated throughput (2026-10-18T16:00:39Z)

At2026-10-18T15:54:52Z, the sole dd1 SEARCH reference's first receipt PGID1436340 was verified already gone, with no bank and zero games. Its wrapper incorrectly supplied `--pool` v3.2; the reviewed DD1 driver asserts that dd1 is defined on its default v1 pool, so it exited before any case was attempted. Original log/receipt retained, log SHA `7f249603230803a30df420e7b59a56b8d48553b3bc9cb83ccf5b82318c89300b`, evidence `helper-ge-dd1-search-launch-repair.json`. This is an orchestration correction, not a source change or a failed-game retry.

Fresh replacement `ge-dd1-search-reference-8f-r2.receipt.json` PGID1549886 launched04 at2026-10-18T15:55:14Z, fresh out `evals/ge-dd1-search-reference-8f-r2`, same60 dd1 paired cases/base3690083941700208, SEARCH-only/source8f/keep-going/cpu_job10/W8/nice15. No explicit pool argument. The v1 pool SHA is pinned by the frozen dd1v2 bank, not the ALL-16 v3.2 bank. Previous failed output remains intact. At15:59:38Z replacement was still waiting ordinary admission with zero rows; no admission bypass or duplicate game run.

Prepared dd1 SEARCH validator now reads the fresh r2 output and validates its pool against the frozen dd1 bank: SHA `e52b08138f8bc5f1b90d784e2aa79576878071d6f0ac42850f82c44b06c0035f`. It is not launched until60 rows+8 zero statuses. Composite revised-G-E helper SHA `6e3f47b7e41d7180c4b7089b9af7735a63b5a98fd677c583c30d5ece07a01b09` also pins dd1 to the v1 bank and asserts full cached-reference file counts/bank/finish bytes; v90 analysis completed successfully with this validation. Both are external analysis helpers only, staged04/08 and syntax checked; product source remains8f.

Postrotation throughput interval refreshed at2026-10-18T16:00:34Z: updates78..122, timestamps2026-10-18T14:03:47Z..2026-10-18T16:00:30Z, observed22.61887762updates/h versus baseline5.90325225/h. Increase observed. This is a confounded observational interval (source mix, rollout lag, load guards and concurrent eval load), not an isolated causal claim; learner flags unchanged. Current evidence `helper-cohort-8f-throughput.json`01/local05; initial short-window artifact retained separately on01.

## 08 SSH outage recovery rule and04 v120 screen receipts (2026-10-18T16:30:24Z)

Owner reports08's sshd unresponsive from about16:20Z (ping responds), probably memory pressure. At2026-10-18T16:30:20Z, direct08 PGID/memory/local-rollout status remains **unknown**; no process death or unrecoverable loss is inferred. No new job, source replacement, actor or analysis was launched on08. The initial v120 preflight failed on its08 read-only SSH test before any copy or launch; logs/receipts for existing work are retained. The outage is recorded in `helper-08-outage.json`01/local05. Partial host watches preserve current01/04 checks and explicitly mark08 unknown instead of discarding the entire watch.

The owner's recovery rule remains active for every later check: once SSH answers, audit only own receipt PGIDs, measure per-worker RSS and host MemAvailable, then size08 actors so MemAvailable remains at least20GB (use20GiB as a conservative floor). Shrink by retiring whole owned blocks and, when headroom permits, relaunch smaller fresh-numbered blocks through ordinary cpu_job/nice15 admission. Leave room for P1-lag; no unowned process is signalled. Keep or restart own sync until local completed `v*.npz` count is0 and all stable `games-*.jsonl` source/destination hashes agree on01. Report only an unrecoverable loss to owner. Prepared local helpers `audit-08-recovery.py` and `verify-08-drain.py` collect receipt/RSS/MemAvailable and stable source/destination hash evidence; neither has run on08 during the outage, and neither signals processes.

Passive01 evidence at16:28:56Z: error-monitor state mirrored from08 was freshly checked16:28:24Z, still monitoring with closed-hour counts15/1879,33/3102,20/2876 (all below5%). Current hour3 waspartial3/323; no completed-hour claim. Fresh08 block55/56/58 summaries arrived on01 around16:28; block57's last observed summary was16:22:33. This proves some outbound activity, not that every08 PGID survived. Full receipt/memory/local-drain audit still required when SSH recovers. No new owner loss report.

Continue independent04 screens: snapshot120 was copied01→04 with matching SHA `e5fefb56803597ee536c5ee29c1656bd776f41b5d06ec8b46c6d2c6e66091ecc` at2026-10-18T16:26:44Z. Sole04 launches at2026-10-18T16:26:49Z: `ge-v120.receipt.json` PGID1759795 (dd1-only60clean cases), `gs-dev-v120-8f.receipt.json` PGID1759850 (ALL-16 candidate180rows/source8f/keep-going; shared G-E/G-S data). Normal CPU admission, W8/nice15, cap100 or70with who. No BattleLog Sam row and no08 job.01/04 dedupe was checked;08 SSH preflight was skipped only under the explicit outage hold for these known04-only new-version jobs. Existing100/110 and sole dd1-search-reference-r2 jobs continue; no duplicate games or reference reruns.

Latest partial watch16:27:29Z: learner update130/v127 at16:24:35Z, KL0.05602220 (below registered production0.5 collapse threshold), deploy35.46559,score0.70445344,EV0.95356345,backlog191<960;01/04loads46.39/85.62,no console users,noSTOP/alerts/newworkerfailure.08 GPU/memory/process status intentionally unknown. Production learner/source/flags and actor guards unchanged. S-CONFIRM1 remains unused; legacyG-B is known active only through last direct08 check, with current08 liveness to audit.

## 08 memory recovery:64actors, persistent20GiB floor and verified rollout drain (2026-10-18T16:44:28Z)

08 SSH recovered: readiness succeeded16:31:01Z, full own-receipt/memory audit at2026-10-18T16:31:34Z. All own actor55/56/57/58 groups, sync-r3, load/error guards and G-Bv10 survived; no unowned process was signalled and no system service was restarted. MemAvailable was26.600563GiB on a125.633GiB host (no swap). RSS measurements guided a smaller actor cohort; RSS includes shared pages, so it is not treated as private physical memory.

| Initial block | Workers | Median worker RSS GiB | p90 worker RSS GiB | Max worker RSS GiB |
|---|---:|---:|---:|---:|
| 55 | 8 | 1.424086 | 1.515862 | 1.515862 |
| 56 | 24 | 1.330439 | 1.474689 | 1.547096 |
| 57 | 24 | 1.355602 | 1.442112 | 1.542641 |
| 58 | 16 | 1.186749 | 1.317692 | 1.381180 |

Retired only actor58's own PGID1997962 at2026-10-18T16:35:40Z, verified gone, preserving atomic finished rollouts and every log. MemAvailable rose from24.992355to43.747349GiB. Newblock59 was unused in all01/04/08 receipts/BLOCKS; launched source8f/defaults W8/cpu_job10/nice15 at2026-10-18T16:37:05Z, PGID2990840, and admitted with all8workers. Total08 actor capacity is now**64workers**, down from72:55W8+56W24+57W24+59W8. Before launch, memory budgeting used worst observed p90workerRSS1.515862GiB, a20GiB floor and6GiB extra parent/headroom reserve; available43.299774GiB. No learner/source/flags or01/04 actor changes.

Persistent memory/load guard `helper-memory-08-r2.receipt.json` PGID3011850 launched16:40:11Z and admitted. It owns only receipted actor55/56/57/58/59 groups (58historical/gone), checks every10s, retires whole own blocks if MemAvailable<24GiB to protect the20GiB floor, applies CPUloadcap100 and permits load-driven resume only with at least28GiB available. New block numbers are required after any retirement. A bounded expiring drain hold is supported through this guard; the main STOP_ACTORS path still resumes own paused groups so they exit. Original08loadguard1725371 was retired only after the memory successor was admitted; first memory guard2977886 was handed off to r2 and verified gone.

Hourly error monitoring successor `helper-error-rate-8f-r2.receipt.json` PGID2977910 launched/admitted16:35:12Z. It retired only old own monitor1718968, saved `helper-error-rate-8f-before-memory-rotation.json`, and preserved exactly the anchor, monotone file offsets and completed-hour counts; cohort adds59 and retains58history. Confirmed monitoring/threshold rules unchanged (recorded Rsimerrors<=5% per completed hour; our-engine errors immediate). No duplicate monitor remains.

**Drain verification PASS at2026-10-18T16:41:16Z**: own sync-r3 PGID1225169 remained running; source NPZ count0 before/after, all256 games-*.jsonl hashes matched01, source metadata/hashes stable during the check. Earlier checks honestly reported changing/pending production; no file was dropped. The memory guard briefly paused its own actor groups under a90s expiring hold to obtain this stable snapshot, then the hold was removed16:41:25Z and only the guard performed budgeted resume. No manual actor CONT bypass. New production naturally replenishes the sync queue afterward. Postrotation audit2026-10-18T16:42:37Z: MemAvailable35.647717GiB, activeblock59has8workers,58gone, resumed production;20GiBfloor met. Sync stays running and later checks retain the floor/RSS/drain/hash requirements.

Evidence01/local05: `helper-08-memory-audit-initial.json`, `helper-08-memory-audit.json`, `helper-08-memory-rotation.json`, guard/error handoff artifacts, `helper-08-drain-verification.json`, and receipts under01`helper-remote-receipt-evidence/`. Owner outage hold is cleared in`helper-08-outage.json` with the permanent memory rule recorded. No unrecoverable loss was observed, so no owner status/loss message was sent. Existing G-Bv10 remains intact and is evaluated only after3300exactcleanrows/allfinishedzero.

Independent04 snapshot130 queued once at2026-10-18T16:41:13Z (G-Sat2026-10-18T16:41:14Z): dd1-only receiptPGID1855766, ALL-16candidate receiptPGID1855825. Frozencheckpoint SHA `7da74fa4741229a41e454924f872bc4931c946e2b8b193142303de23a9a7fee2` copied/verified01→04same-step2026-10-18T16:41:09Z. No BattleLog Sam scheduling, reference rerun or new08 eval. Existing100/110/120 work continues under admission; readouts wait for complete rows/statuses. DEV selection only; no G-S confirm bank consumed.

## G-S DEV screen v100 (source8f; selection only) (2026-10-18T16:52:50Z)

Snapshot100 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `63ad7b8beb0621b5e6c545e961fd9c55ecfc5933dd0fc57a7a0629580a80109f`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v100 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v100 − search [95% CI] | v100 − v2 [95% CI] | v100/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.553571 [+0.428571, +0.678571] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.178571 [-0.321429, -0.035714] | +0.214286 [+0.053571, +0.375000] | 45.232143/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.750000 [+0.633333, +0.850000] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.033333 [-0.116667, +0.183333] | +0.200000 [+0.050000, +0.350000] | 42.300000/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.866667 [+0.783333, +0.950000] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.066667 [-0.066667, +0.200000] | +0.166667 [+0.050000, +0.300000] | 44.766667/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v100 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| SEARCH | bait | 5 | -0.400000 [-0.800000, +0.000000] | +0.200000 [-0.400000, +0.800000] |
| SEARCH | giant | 9 | -0.111111 [-0.444444, +0.222222] | +0.111111 [-0.222222, +0.444444] |
| SEARCH | hog | 8 | +0.250000 [-0.250000, +0.625000] | +0.375000 [-0.125000, +0.875000] |
| SEARCH | other | 23 | -0.304348 [-0.478261, -0.130435] | +0.304348 [+0.086957, +0.521739] |
| SEARCH | siege | 7 | -0.142857 [-0.571429, +0.285714] | +0.000000 [-0.571429, +0.571429] |
| LIVE-K4CW-r16-fp | air | 9 | +0.000000 [-0.555556, +0.555556] | +0.000000 [-0.333333, +0.333333] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.133333 [-0.200000, +0.466667] | +0.333333 [+0.066667, +0.600000] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.200000 [-0.200000, +0.600000] | +0.300000 [-0.100000, +0.700000] |
| LIVE-K4CW-r16-fp | other | 14 | -0.142857 [-0.357143, +0.000000] | +0.071429 [-0.214286, +0.357143] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.000000 [-0.375000, +0.375000] | +0.250000 [-0.250000, +0.625000] |
| R3a | air | 11 | +0.090909 [-0.181818, +0.363636] | +0.090909 [-0.181818, +0.363636] |
| R3a | bait | 6 | +0.333333 [-0.333333, +0.833333] | +0.333333 [+0.000000, +0.666667] |
| R3a | giant | 14 | +0.071429 [-0.142857, +0.357143] | +0.071429 [-0.142857, +0.285714] |
| R3a | hog | 6 | -0.166667 [-0.500000, +0.000000] | +0.166667 [+0.000000, +0.500000] |
| R3a | other | 19 | +0.105263 [-0.105263, +0.315789] | +0.210526 [+0.000000, +0.421053] |
| R3a | siege | 4 | -0.250000 [-0.750000, +0.000000] | +0.250000 [+0.000000, +0.750000] |

All raw rows and errors are retained. Standalone analysis ran on127x08 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v100-8f-readout.json` on08/04/01/local05, SHA `b976043bfd3d41d2afc75ff4b2d25e188286990abc88c15b8f1350198a082c79`.

## G-S DEV screen v110 (source8f; selection only) (2026-10-18T16:53:45Z)

Snapshot110 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `04068fc9b87d0f3c8bcf9246187ea4738b4277dc649651243355a7b9299bc35a`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v110 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v110 − search [95% CI] | v110 − v2 [95% CI] | v110/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.714286 [+0.589286, +0.821429] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.017857 [-0.160714, +0.125000] | +0.375000 [+0.232143, +0.517857] | 44.625000/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.766667 [+0.650000, +0.866667] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.050000 [-0.116667, +0.216667] | +0.216667 [+0.083333, +0.350000] | 45.683333/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.866667 [+0.783333, +0.950000] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.066667 [-0.083333, +0.216667] | +0.166667 [+0.050000, +0.300000] | 41.933333/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v110 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | +0.250000 [+0.000000, +0.750000] | +0.500000 [+0.000000, +1.000000] |
| SEARCH | bait | 5 | -0.200000 [-0.600000, +0.000000] | +0.400000 [+0.000000, +0.800000] |
| SEARCH | giant | 9 | +0.000000 [-0.333333, +0.333333] | +0.222222 [-0.222222, +0.666667] |
| SEARCH | hog | 8 | +0.125000 [-0.250000, +0.500000] | +0.250000 [+0.000000, +0.500000] |
| SEARCH | other | 23 | -0.043478 [-0.260870, +0.173913] | +0.565217 [+0.391304, +0.782609] |
| SEARCH | siege | 7 | -0.142857 [-0.571429, +0.285714] | +0.000000 [-0.428571, +0.428571] |
| LIVE-K4CW-r16-fp | air | 9 | +0.333333 [+0.000000, +0.666667] | +0.333333 [+0.000000, +0.666667] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [-1.000000, +1.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | -0.133333 [-0.466667, +0.266667] | +0.066667 [-0.133333, +0.266667] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.200000 [-0.300000, +0.600000] | +0.300000 [+0.100000, +0.600000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.142857 [+0.000000, +0.357143] | +0.357143 [+0.142857, +0.642857] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | -0.250000 [-0.625000, +0.000000] | +0.000000 [-0.625000, +0.625000] |
| R3a | air | 11 | +0.090909 [-0.181818, +0.363636] | +0.090909 [-0.181818, +0.363636] |
| R3a | bait | 6 | +0.333333 [-0.333333, +0.833333] | +0.333333 [+0.000000, +0.666667] |
| R3a | giant | 14 | +0.000000 [-0.285714, +0.285714] | +0.000000 [-0.214286, +0.214286] |
| R3a | hog | 6 | -0.333333 [-0.666667, +0.000000] | +0.000000 [-0.500000, +0.500000] |
| R3a | other | 19 | +0.157895 [-0.105263, +0.421053] | +0.263158 [+0.105263, +0.473684] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x08 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v110-8f-readout.json` on08/04/01/local05, SHA `f6ccfc976362b44bb706491faf328f270b4b5083e54698bf34ad1f284508ebf5`.

## DD1 SEARCH reference: invalid translator coverage, retained paired readout (2026-10-18T16:54:56Z)

The sole dd1 SEARCH reference completed60 raw rows and eight zero worker statuses at2026-10-18T16:46:03Z. Full identity is exactly the frozen v2 dd1 bank (v1 pool, base3690083941700208), source8f, L16, clean perception, res-lb-RF-wintp; all pins and case deck/seed/seat/own-index identities validated. Standard problems(row) is supplemented by the registered unmapped/missing/no_template translator-counter check.

**Reference INVALID: 16/60 dropped (26.6667%), above5% K4CW-fp limit.** All16 errors are `unmapped_unit:SpearGoblin_Dummy` from GoblinHut decks, cases0-0000..0-0007 and0-0024..0-0031. All16drops are classified **giant** (>50% concentration,100% here). All raw rows/errors remain intact; no retry or silent filtering. This is the original dd1 secondary search comparison, not the all-deck G-S primary. ALL-16 references remain valid; primary G-S scope remains49.0292926714% RoyaleSim-playable corpus weight. The separate old-driver clean dd1 vN-v2 contribution is reported as registered; an invalid dd1 vN-search comparison supports no strength/gate claim.

The following retained-case differences are descriptive only; identical failure masks apply to every arm in each comparison. Pooled estimates are qualified by the concentrated Giant drops; separate Giant estimates are included. Bootstrap4000Random(0),sorted[100]/[3899], executed under detachedcpu_job2/nice15 on08 after byte/SHA/size/mtime/pin-verified completed-input staging.

| Policy | Retained pairs | Policy-search, qualified pooled [95% CI] | Retained Giant pairs | Giant policy-search [95% CI] | Policy/search plays |
|---|---:|---|---:|---|---|
| v2 | 44 | -0.181818 [-0.386364,+0.022727] | 32 | -0.250000 [-0.437500,-0.062500] | 47.863636/52.545455 |
| v90 | 44 | +0.090909 [-0.113636,+0.295455] | 32 | +0.062500 [-0.156250,+0.312500] | 42.772727/52.545455 |

All drop cases and decks:

- 0-0000 / giant: Musketeer, BattleRam, GoblinCage, Giant, GoblinHut, Fireball, Valkyrie, Barbarians; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 782}.
- 0-0001 / giant: GoblinHut, Musketeer, Giant, Barbarians, GoblinCage, Valkyrie, BattleRam, Fireball; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 550}.
- 0-0002 / giant: GoblinHut, BattleRam, Valkyrie, Barbarians, Musketeer, Giant, GoblinCage, Fireball; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 122}.
- 0-0003 / giant: Musketeer, Barbarians, BattleRam, Valkyrie, GoblinCage, Fireball, GoblinHut, Giant; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 208}.
- 0-0004 / giant: GoblinHut, GoblinCage, Giant, Barbarians, BattleRam, Musketeer, Valkyrie, Fireball; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 408}.
- 0-0005 / giant: Musketeer, BattleRam, GoblinCage, Fireball, Valkyrie, Barbarians, Giant, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 142}.
- 0-0006 / giant: GoblinCage, Fireball, BattleRam, Musketeer, Barbarians, Valkyrie, GoblinHut, Giant; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 464}.
- 0-0007 / giant: Fireball, Barbarians, Giant, BattleRam, Musketeer, GoblinHut, GoblinCage, Valkyrie; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 748}.
- 0-0024 / giant: Minions, Giant, Fireball, SpearGoblins, MiniPekka, Bomber, GoblinHut, Tombstone; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 130}.
- 0-0025 / giant: Tombstone, SpearGoblins, MiniPekka, Minions, Bomber, Giant, Fireball, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 554}.
- 0-0026 / giant: Tombstone, GoblinHut, Minions, Fireball, MiniPekka, Giant, SpearGoblins, Bomber; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 188}.
- 0-0027 / giant: Minions, Bomber, Giant, Tombstone, SpearGoblins, MiniPekka, Fireball, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 778}.
- 0-0028 / giant: Bomber, SpearGoblins, MiniPekka, Minions, GoblinHut, Fireball, Giant, Tombstone; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 104}.
- 0-0029 / giant: Fireball, MiniPekka, GoblinHut, Bomber, SpearGoblins, Minions, Tombstone, Giant; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 234}.
- 0-0030 / giant: MiniPekka, Bomber, Fireball, Tombstone, Giant, SpearGoblins, Minions, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 250}.
- 0-0031 / giant: MiniPekka, Giant, Minions, Bomber, SpearGoblins, Tombstone, GoblinHut, Fireball; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 574}.

Readout `JOB/helper-ge-dd1-search-reference-8f-readout.json`08/04/01/local05, SHA `a5c9b1128ec5fb8886ba0027d2d96b215e0a4f04553c1baeaa918c439064d998`; finished data `evals/ge-dd1-search-reference-8f-r2`04 and immutable verified08 staging. Actual standalone08 successor receipt `ge-dd1-search-reference-8f-readout-r2.receipt.json` PGID3087701 launched16:51:12Z, normal mechanical validation exit. Its never-admitted04 predecessor1898985 was stopped only by own receipt after input staging; original receipt/log preserved. The failed first wrapper with --poolv3 had0games and remains preserved separately. No source changes, baseline rerun, confirm bank use or policy-strength claim.

## Revised ALL-16 plus dd1 DEV screen v110 (selection only) (2026-10-18T16:55:50Z)

Revised G-E per15:36:01Z registration `b6cc6237958777898c6dbb6e60f3382bd9bf3ba2`: reuse the completed180-case ALL-16 candidate and validated frozen search/v2 references; add the clean60-case dd1 row. No new BattleLog-pool Sam DEV row is scheduled. Checkpoint `04068fc9b87d0f3c8bcf9246187ea4738b4277dc649651243355a7b9299bc35a`. ALL-16 scope:49.0292926714% of corpus weight RoyaleSim-playable. Raw unclean cases remain preserved and identically masked across ALL-16 arms under the registered10% SEARCH/5% other limits. dd1 remains clean-only, exactly paired to the frozen v2 dd1 cases.

| Row | Opponent | Pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | vN-v2 row valid |
|---|---|---:|---:|---|---|---|
| all16 | SEARCH | 56 | +0.375000 | -0.017857 [-0.160714,+0.125000] | 44.625000/49.892857 | True |
| all16 | LIVE-K4CW-r16-fp | 60 | +0.216667 | +0.050000 [-0.116667,+0.216667] | 45.683333/48.250000 | True |
| all16 | R3a | 60 | +0.166667 | +0.066667 [-0.083333,+0.216667] | 41.933333/46.100000 | True |
| dd1 | LIVE-K4CW-r16-fp | 60 | +0.200000 | +0.068182 [-0.090909,+0.250000] (INVALID search reference; descriptive only) | 41.383333/47.066667 | True |

Equal screen (ALL-16 K4CW-fp, ALL-16 R3a, dd1 K4CW-fp vs v2): 0.19444444444444445; screen valid=True, all three nonnegative=True, ALL-16 play sanity=True, dd1 plays in20..65=True, candidate predicate=True. SEARCH is reported separately and is excluded from this equal mean. Registered G-S SEARCH selector=False; the G-E candidate predicate alone does not qualify G-S. These are DEV selection contrasts, never gains. This uses a changed screen dataset; historical BattleLog Sam screen means are retained as history, not pooled with this definition.

all16/SEARCH: dropped4/60, IDs ["0-0015", "0-0030", "0-0039", "0-0047"]; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
all16/LIVE-K4CW-r16-fp: dropped0/60, IDs []; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60, IDs []; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


DD1 SEARCH reference: 16/60 dropped, valid=False, limit5%; causes/decks retained below. This does not change the separate clean dd1 vN-v2 score contribution. Retained-case comparison; >50% drop archetypes giant

- 0-0000 / giant: Musketeer, BattleRam, GoblinCage, Giant, GoblinHut, Fireball, Valkyrie, Barbarians; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 782}.
- 0-0001 / giant: GoblinHut, Musketeer, Giant, Barbarians, GoblinCage, Valkyrie, BattleRam, Fireball; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 550}.
- 0-0002 / giant: GoblinHut, BattleRam, Valkyrie, Barbarians, Musketeer, Giant, GoblinCage, Fireball; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 122}.
- 0-0003 / giant: Musketeer, Barbarians, BattleRam, Valkyrie, GoblinCage, Fireball, GoblinHut, Giant; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 208}.
- 0-0004 / giant: GoblinHut, GoblinCage, Giant, Barbarians, BattleRam, Musketeer, Valkyrie, Fireball; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 408}.
- 0-0005 / giant: Musketeer, BattleRam, GoblinCage, Fireball, Valkyrie, Barbarians, Giant, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 142}.
- 0-0006 / giant: GoblinCage, Fireball, BattleRam, Musketeer, Barbarians, Valkyrie, GoblinHut, Giant; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 464}.
- 0-0007 / giant: Fireball, Barbarians, Giant, BattleRam, Musketeer, GoblinHut, GoblinCage, Valkyrie; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 748}.
- 0-0024 / giant: Minions, Giant, Fireball, SpearGoblins, MiniPekka, Bomber, GoblinHut, Tombstone; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 130}.
- 0-0025 / giant: Tombstone, SpearGoblins, MiniPekka, Minions, Bomber, Giant, Fireball, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 554}.
- 0-0026 / giant: Tombstone, GoblinHut, Minions, Fireball, MiniPekka, Giant, SpearGoblins, Bomber; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 188}.
- 0-0027 / giant: Minions, Bomber, Giant, Tombstone, SpearGoblins, MiniPekka, Fireball, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 778}.
- 0-0028 / giant: Bomber, SpearGoblins, MiniPekka, Minions, GoblinHut, Fireball, Giant, Tombstone; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 104}.
- 0-0029 / giant: Fireball, MiniPekka, GoblinHut, Bomber, SpearGoblins, Minions, Tombstone, Giant; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 234}.
- 0-0030 / giant: MiniPekka, Bomber, Fireball, Tombstone, Giant, SpearGoblins, Minions, GoblinHut; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 250}.
- 0-0031 / giant: MiniPekka, Giant, Minions, Bomber, SpearGoblins, Tombstone, GoblinHut, Fireball; translator drops: {"unmapped_unit:SpearGoblin_Dummy": 574}.

DD1 giant retained paired vN-search (descriptive if reference invalid): {"n": 32, "mean": 0.0, "ci95": [-0.15625, 0.1875]}.

DD1 other retained paired vN-search (descriptive if reference invalid): {"n": 12, "mean": 0.25, "ci95": [-0.16666666666666666, 0.6666666666666666]}.

DD1 concentrated-drop archetype giant separately: {"n": 32, "mean": 0.0, "ci95": [-0.15625, 0.1875]}; pooled interpretation qualified.

ALL-16 full per-archetype CIs and raw case details in `JOB/helper-gs-dev-v110-8f-readout.json`; SHA `f6ccfc976362b44bb706491faf328f270b4b5083e54698bf34ad1f284508ebf5`. Revised composite readout `JOB/helper-ge-v110-all16-readout.json` on08/04/01/local05, SHA `9e3e44059e9f8d7d1df1486de81631466c06ac043d6e1e3eb175435a13fee107`; raw row hashes, bank/finished records and checkpoint revalidated by detached cpu_job2/nice15 analysis. No baseline rerun.

## ALL-16 two-row DEV screen v90 (selection only) (2026-10-18T17:05:32Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v90−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `68ff703ef417d246f354de426a5282ea223d785cc239a95a3cb3937248e2ee65`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.160714 | -0.232143 [-0.392857,-0.071429] | 45.767857/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.083333 | -0.083333 [-0.233333,+0.050000] | 47.966667/48.250000 | True |
| R3a | 60 | +0.100000 | +0.000000 [-0.150000,+0.150000] | 46.533333/46.100000 | True |

Equal two-row screen=0.09166666666666667; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v90": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v90": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v90": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v90": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v90-all16-only-readout.json`, SHA `22d9945adfcbea2f655a04c637e2d99f7eb1002c0269a8c4ecd23ed7a7897e68`; underlying ALL-16 readout SHA `dd2f64a7e8860d343ffdddc606311d34bca7c26b03c4fbb23b5f12100295ee80`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## ALL-16 two-row DEV screen v100 (selection only) (2026-10-18T17:06:48Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v100−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `63ad7b8beb0621b5e6c545e961fd9c55ecfc5933dd0fc57a7a0629580a80109f`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.214286 | -0.178571 [-0.321429,-0.035714] | 45.232143/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.200000 | +0.033333 [-0.116667,+0.183333] | 42.300000/48.250000 | True |
| R3a | 60 | +0.166667 | +0.066667 [-0.066667,+0.200000] | 44.766667/46.100000 | True |

Equal two-row screen=0.18333333333333335; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v100": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v100": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v100": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v100": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v100-all16-only-readout.json`, SHA `c592d83a85f640e9d96ce1e72e751ec6b91d1947a0a77a78a8584544be48233b`; underlying ALL-16 readout SHA `b976043bfd3d41d2afc75ff4b2d25e188286990abc88c15b8f1350198a082c79`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## ALL-16 two-row DEV screen v110 (selection only) (2026-10-18T17:07:05Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v110−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `04068fc9b87d0f3c8bcf9246187ea4738b4277dc649651243355a7b9299bc35a`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.375000 | -0.017857 [-0.160714,+0.125000] | 44.625000/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.216667 | +0.050000 [-0.116667,+0.216667] | 45.683333/48.250000 | True |
| R3a | 60 | +0.166667 | +0.066667 [-0.083333,+0.216667] | 41.933333/46.100000 | True |

Equal two-row screen=0.19166666666666665; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v110": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v110": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v110": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v110": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v110-all16-only-readout.json`, SHA `029248eaf5cabf221c991fc05afd55ac4ff44f47bbd08ccc644af530617c47dd`; underlying ALL-16 readout SHA `f6ccfc976362b44bb706491faf328f270b4b5083e54698bf34ad1f284508ebf5`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## G-E/G-B dd1 retired; two-row screens and candidate OFF1 orchestration (2026-10-18T17:08:23Z)

Apply the 2026-10-18T16:56:33Z registration3a9c34f80578565501e9c4cec138fad995f30065. dd1 is retired from both G-E and G-B; all existing raw rows and receipts are retained. On04 the active owned groups ge-v100(1235871),ge-v120(1759795),ge-v130(1855766) were SIGTERM/CONT by their own receipts and verified gone at17:02:31Z. ge-v110 and the completed dd1 SEARCH reference were already gone. Their ALL-16 candidate counterparts remain running or completed. No dd1 game is retried.

The sole G-Bv10 group4142369 is still producing its retained account row. Own boundary controller helper-gb-no-dd1 PGID3162918 was detached through cpu_job2/nice15 at17:03:00Z and admitted; it watches the successful account finished record, retires that owned group before its superseded dd1 stage, and preserves any race artifacts. State is helper-gb-no-dd1-state.json. The prepared G-B readout now validates exactly2700 clean paired arm rows (1800Sam+900account),two finished records with8zero statuses each. RowA primary bootstrap lower>0,other retained cells' point differences>=−.03,and registered Sam plays sanity determine clears_gate. Original launch bank ledger retains its historical definition; analysis explicitly records the superseding protocol. No G-B outcome exists yet, CONFIRM1 remains used, no second G-B is launched.

Future G-E games are a single ALL-16 candidate row180cases (60perSEARCH/K4CW-fp/R3a) reused for G-S selection, with frozen search/v2 references. New helper-ge-all16-only-readout.py validates cached candidate/reference bytes,bank/finished hashes,size/mtime and checkpoint,then averages onlyK4CW-fp/R3a vN−v2. SEARCHvN−search is reported separately; dd1 is not an input. New distinct results preserve earlier screen definitions as history. Two-row v90/v100/v110 screens are+.09166667/+.18333333/+.19166667 respectively; all are valid and nonnegative on both contributing cells,with sane plays. Their SEARCHcontrasts remain−.23214286/−.17857143/−.01785714,so none qualifies for G-S. DEVselection only; no gains or gate outcome.

v140 was launched once on04 at17:05:36Z,sole gs-dev-v140-8f.receipt.json PGID2027107. Frozen checkpointSHAaae1f22db7577e713864c2d5ef200327abe22962a1e261294955ac504465a954 was copied01→04 and verified at17:05:32Z. The new launcher creates no dd1 or BattleLogSam job. Because04 had only about13GiB MemAvailable after retiring dd1,its detached admission wrapper waits outside any CPU lease for24GiB before ordinary cpu_job10 admission; no admission bypass or learner flag change. Existing120/130 ALL-16 runs remain untouched.

For every actual qualifying G-S candidate,the new once-per-version helper-gs-offdeck-run-8f.sh runs amendment2 OFF1 frequency2746836719317424 and uniform2746836719517424 on our engine/max/every card,100cases each vsR3a/K4C-r16,candidate+v2. It validates the completed qualifying proof and checkpoint,records a distinct candidate ledger,and is launched via launch-gs-offdeck.py only after a dated results publication. This does not consume a G-S confirm bank. The prepared confirm wrapper's duplicated off-deck tail was removed; its six primary/secondary rows remain unchanged. Negative v110 guard was checked to reject before any remote command,publication or game. Both shell scripts and the updated launch/readout helpers passed syntax checks. No OFF1 candidate or G-S confirm has been launched because no selector is satisfied.

Source8f,learner-r2/source095,models/corpus and masks10%SEARCH/5%K4CW/R3a remain unchanged; scope49.0292926714% corpus weight RoyaleSim-playable. On08 the persistent memory guard additionally retired new block59W8 at16:59:12Z before the20GiB floor; remaining production blocks55W8/56W24/57W24 total56workers. Blocks58/59 stay retired,not reused. Fixed remote_sync-r3 stays alive; the earlier guarded drain verified0finishedNPZ and all256games-file SHA256s matching01 at16:41:16Z. Memory floor/load/error guards and future drain checks remain active. No unrecoverable loss occurred and no recovery status was sent to owner.

## G-S DEV screen v130 (source8f; selection only) (2026-10-18T17:24:17Z)

Snapshot130 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `7da74fa4741229a41e454924f872bc4931c946e2b8b193142303de23a9a7fee2`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v130 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v130 − search [95% CI] | v130 − v2 [95% CI] | v130/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.660714 [+0.535714, +0.785714] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.071429 [-0.232143, +0.089286] | +0.321429 [+0.160714, +0.482143] | 45.500000/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.866667 [+0.766667, +0.950000] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.150000 [+0.016667, +0.283333] | +0.316667 [+0.166667, +0.450000] | 41.633333/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.816667 [+0.716667, +0.916667] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.016667 [-0.133333, +0.166667] | +0.116667 [-0.016667, +0.250000] | 47.616667/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v130 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | +0.000000 [-0.750000, +0.750000] | +0.250000 [+0.000000, +0.750000] |
| SEARCH | bait | 5 | -0.400000 [-0.800000, +0.000000] | +0.200000 [+0.000000, +0.600000] |
| SEARCH | giant | 9 | -0.111111 [-0.444444, +0.222222] | +0.111111 [-0.222222, +0.444444] |
| SEARCH | hog | 8 | +0.125000 [-0.375000, +0.625000] | +0.250000 [-0.250000, +0.750000] |
| SEARCH | other | 23 | -0.086957 [-0.304348, +0.130435] | +0.521739 [+0.304348, +0.739130] |
| SEARCH | siege | 7 | +0.000000 [-0.571429, +0.571429] | +0.142857 [-0.428571, +0.714286] |
| LIVE-K4CW-r16-fp | air | 9 | +0.111111 [-0.333333, +0.555556] | +0.111111 [-0.222222, +0.444444] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [-1.000000, +1.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.133333 [-0.200000, +0.466667] | +0.333333 [+0.000000, +0.600000] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.400000 [+0.100000, +0.700000] | +0.500000 [+0.200000, +0.800000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.142857 [+0.000000, +0.357143] | +0.357143 [+0.142857, +0.642857] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.000000 [+0.000000, +0.000000] | +0.250000 [-0.250000, +0.625000] |
| R3a | air | 11 | +0.090909 [-0.181818, +0.363636] | +0.090909 [-0.181818, +0.363636] |
| R3a | bait | 6 | +0.166667 [-0.333333, +0.666667] | +0.166667 [-0.333333, +0.666667] |
| R3a | giant | 14 | -0.214286 [-0.571429, +0.142857] | -0.214286 [-0.428571, +0.000000] |
| R3a | hog | 6 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +0.666667] |
| R3a | other | 19 | +0.157895 [-0.105263, +0.421053] | +0.263158 [+0.105263, +0.473684] |
| R3a | siege | 4 | -0.250000 [-0.750000, +0.000000] | +0.250000 [+0.000000, +0.750000] |

All raw rows and errors are retained. Standalone analysis ran on127x08 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v130-8f-readout.json` on08/04/01/local05, SHA `6502d2923efdcad206118804b900a2da69267e0555459f4d9b53b7221aeca450`.

## ALL-16 two-row DEV screen v130 (selection only) (2026-10-18T17:25:10Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v130−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `7da74fa4741229a41e454924f872bc4931c946e2b8b193142303de23a9a7fee2`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.321429 | -0.071429 [-0.232143,+0.089286] | 45.500000/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.316667 | +0.150000 [+0.016667,+0.283333] | 41.633333/48.250000 | True |
| R3a | 60 | +0.116667 | +0.016667 [-0.133333,+0.166667] | 47.616667/46.100000 | True |

Equal two-row screen=0.21666666666666667; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v130": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v130": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v130": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v130": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v130-all16-only-readout.json`, SHA `48ce7eb9fa7a6688666f85bdbefcc5ce01840298471594270811cadda4fd3ba2`; underlying ALL-16 readout SHA `6502d2923efdcad206118804b900a2da69267e0555459f4d9b53b7221aeca450`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## G-S DEV screen v120 (source8f; selection only) (2026-10-18T17:26:17Z)

Snapshot120 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `e5fefb56803597ee536c5ee29c1656bd776f41b5d06ec8b46c6d2c6e66091ecc`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v120 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v120 − search [95% CI] | v120 − v2 [95% CI] | v120/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.642857 [+0.517857, +0.767857] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.089286 [-0.232143, +0.071429] | +0.303571 [+0.160714, +0.446429] | 46.107143/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.766667 [+0.650000, +0.866667] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.050000 [-0.100000, +0.200000] | +0.216667 [+0.100000, +0.333333] | 44.633333/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.850000 [+0.750000, +0.933333] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.050000 [-0.083333, +0.183333] | +0.150000 [+0.016667, +0.300000] | 43.950000/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v120 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | +0.000000 [-0.750000, +0.750000] | +0.250000 [+0.000000, +0.750000] |
| SEARCH | bait | 5 | -0.200000 [-0.800000, +0.400000] | +0.400000 [-0.400000, +1.000000] |
| SEARCH | giant | 9 | +0.000000 [-0.333333, +0.333333] | +0.222222 [-0.222222, +0.666667] |
| SEARCH | hog | 8 | -0.125000 [-0.500000, +0.250000] | +0.000000 [-0.375000, +0.375000] |
| SEARCH | other | 23 | -0.130435 [-0.347826, +0.086957] | +0.478261 [+0.260870, +0.695652] |
| SEARCH | siege | 7 | +0.000000 [-0.428571, +0.428571] | +0.142857 [+0.000000, +0.428571] |
| LIVE-K4CW-r16-fp | air | 9 | +0.222222 [+0.000000, +0.555556] | +0.222222 [+0.000000, +0.555556] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [-1.000000, +1.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | -0.133333 [-0.400000, +0.200000] | +0.066667 [-0.200000, +0.333333] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.100000 [-0.300000, +0.500000] | +0.200000 [+0.000000, +0.500000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.071429 [-0.142857, +0.285714] | +0.285714 [+0.071429, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.125000 [+0.000000, +0.375000] | +0.375000 [+0.125000, +0.750000] |
| R3a | air | 11 | +0.000000 [-0.363636, +0.363636] | +0.000000 [-0.363636, +0.363636] |
| R3a | bait | 6 | +0.333333 [+0.000000, +0.666667] | +0.333333 [-0.333333, +0.833333] |
| R3a | giant | 14 | +0.000000 [-0.285714, +0.285714] | +0.000000 [-0.285714, +0.285714] |
| R3a | hog | 6 | -0.166667 [-0.500000, +0.000000] | +0.166667 [-0.333333, +0.666667] |
| R3a | other | 19 | +0.105263 [-0.157895, +0.368421] | +0.210526 [+0.052632, +0.421053] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x08 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v120-8f-readout.json` on08/04/01/local05, SHA `afda8b8f92db41d24f48e9ea5dba6196debe327768c49c3a539f88b7896a0b3d`.

## ALL-16 two-row DEV screen v120 (selection only) (2026-10-18T17:26:48Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v120−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `e5fefb56803597ee536c5ee29c1656bd776f41b5d06ec8b46c6d2c6e66091ecc`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.303571 | -0.089286 [-0.232143,+0.071429] | 46.107143/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.216667 | +0.050000 [-0.100000,+0.200000] | 44.633333/48.250000 | True |
| R3a | 60 | +0.150000 | +0.050000 [-0.083333,+0.183333] | 43.950000/46.100000 | True |

Equal two-row screen=0.18333333333333335; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v120": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v120": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v120": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v120": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v120-all16-only-readout.json`, SHA `9fd0319ce1d449a64de1c79088332938abb52837b5b9d25569ace3c35e2e9140`; underlying ALL-16 readout SHA `afda8b8f92db41d24f48e9ea5dba6196debe327768c49c3a539f88b7896a0b3d`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## Completed ALL-16 v120/v130; untouched v140 placement and G-B boundary (2026-10-18T17:30:54Z)

Both completed ALL-16 DEV candidates v120 and v130 validated under source8f and the10%SEARCH/5%other union-mask rules. Each has180candidate arm rows,8zero worker statuses,all exact cases/levels/checkpoint/pins verified,and the same four known SEARCHlive-error cases retained in raw data and dropped from every arm. Neither candidate has another dropped case; all candidate play rates are sane. Their valid SEARCH contrasts versus search are−.08928571(CI−.23214286,+.07142857) and−.07142857(CI−.23214286,+.08928571),respectively,so neither qualifies for G-S. Scope remains49.0292926714% of corpus weight RoyaleSim-playable.

The current two-row G-E scores,using only ALL-16 K4CW-fp/R3a vN−v2,are+.18333333 forv120(contrasts+.21666667,+.15000000) and+.21666667 forv130(contrasts+.31666667,+.11666667). These are DEV selection contrasts,not gains. SEARCH contributes no weight; no dd1 input was used. Completed artifacts were staged04→08 with every file's SHA256,size,mtime,dependency pins and checkpoint checked. Each standalone GS readout then two-row GE readout ran once under detached cpu_job2/nice15. Results and receipts are preserved on01/04/08/local05,remote receipts only in01's evidence subdirectory. Publications: GS130b767f3a5fdec42cd1597cff2d0f499e86cc106b8,GE130f8a84344e925f14d8a468bfdcfcde904bdce7283,GS120d7d750f85d3b1c79c8b7e8a27f3609d4f5b068c2,GE120816e7264dbb01a3bab4ab18154f85b26d91fe727.

The sole v140 ALL-16 screen was moved from04's never-admitted memory queue to08. Before any move,08 had52,179,628,032bytes available and an active20GiB floor guard; PTR1 was absent.04's own receipt2027107 was proved to have zero Python workers and no bank/game/output,then terminated/continued and verified gone at17:28:14Z. Original04receipt/log remain untouched. The same checkpointSHAaae1f22db7577e713864c2d5ef200327abe22962a1e261294955ac504465a954 was copied and SHAchecked04/08 in the move; all seven08model hashes passed again. Fresh sole08receipt gs-dev-v140-8f-r2 PGID3354792 launched17:28:21Z through ordinary cpu_job10/nice15; metadata and helper-gs-v140-placement.json preserve the host change and preflight. No game was discarded or retried,no source/sync/actor replacement,no admission bypass. Future v140 analysis uses its actual08output directly,not the empty04location. Persistent08memory/load guard and fixed sync remain active; actors55W8/56W24 only,retired57/58/59 stay retired.

G-Bv10 completed its retained account row at17:27:56Z with900arm rows and8zero worker statuses. The admitted boundary controller retired own outer group4142369 at that boundary,verified it absent and preserved zero dd1 rows. The original Sam row has1800arm rows and8zero statuses. A single fresh registered2700-row readout launched08 PGID3362232 at17:29:18Z after all counts/statuses,helper hash and memory preflights passed. Its result is published separately only after full validation; no G-B outcome is inferred from these completion counts. CONFIRM1 remains used; S-CONFIRM1 has not been used.

The separate OFF1 candidate wrapper now records a dated completion/exit-status marker after its two descriptive rows. Its prepared readout helper-gs-offdeck-readout-8f.py(SHA218f3c832f61faf4190d2f9a2b90b133e79cc148e61be9d35e1306f226692030) is syntax-checked only and has not run:no qualifying G-S candidate or OFF1 data exists yet. It requires both completed400-arm-row directories,exact100case identities/deck orders/seed/seat peropponent,our-engine/max/terminal rows with no errors,matching qualifying proof/checkpoint/allmodel hashes,and the registered OFF1 frequency/uniform bases. It reports paired N−v2 with4000Random(0)CI100/3899,per-opponent archetypes,plays and the registered point<−.05 overfit flags. Launch through the staged hp1_run.sh py environment under detached cpu_job2/nice15 after completion. It is separate from G-S's primary pass; the prepared six-row confirm wrapper has no duplicated OFF1 tail. No new simulator/probe/product code or source changes were made.

## G-B v10 CONFIRM bank 2715349865347232: registered result (2026-10-18T17:31:39Z)

Registered G-B v10 on single-use CONFIRM bank2715349865347232,checkpoint SHA`0e474348e4f69f42805ac54a6d7cdfb92a6169f6e369cccc8b0274341e335f2d`. Under protocol`3a9c34f80578565501e9c4cec138fad995f30065`,rowC/dd1 is retired;2700clean arm rows cover300Sam-L16 paired cases perK4CW-fp/R3a and150account paired cases peropponent. Both finished records have8zero statuses; full cases/bank/driver/pool/vocab/model/levels/thresholds were independently validated.

**G-B clears_gate=False**: rowA vN−v2=+0.046667,95%pairedCI[-0.033333,+0.123333]; primary lower>0=False; other retained rows>=−.03=True; registered Sam plays sanity=True. Every paired CI uses4000case draws,Random(0),sorted100/3899. f1a2 comparisons are secondary.

| Row/opponent | Pairs | vN score | v2 score | f1a2 score | vN−v2 [95%CI] | vN−f1a2 [95%CI] |
|---|---:|---:|---:|---:|---|---|
| sam/LIVE-K4CW-r16-fp | 300 | 0.513333 | 0.466667 | 0.276667 | +0.046667 [-0.033333,+0.123333] | +0.236667 [+0.160000,+0.310000] |
| sam/R3a | 300 | 0.666667 | 0.653333 | 0.370000 | +0.013333 [-0.053333,+0.080000] | +0.296667 [+0.230000,+0.360000] |
| account/LIVE-K4CW-r16-fp | 150 | 0.446667 | 0.360000 | 0.186667 | +0.086667 [-0.013333,+0.186667] | +0.260000 [+0.173333,+0.346667] |
| account/R3a | 150 | 0.606667 | 0.613333 | 0.306667 | -0.006667 [-0.100000,+0.086667] | +0.300000 [+0.206667,+0.393333] |

PF1 behaviour is reported for every arm/cell; no secondary metric is substituted for the registered primary rule.

| Row/opponent | Arm | Plays/game | Plays/min | Reaction p50/p90 seconds | Reaction events | Idle-play share | Undefended share | CPU s/game |
|---|---|---:|---:|---|---:|---:|---:|---:|
| sam/LIVE-K4CW-r16-fp | fast-v10 | 49.500000 | 14.38 | [1.65, 5.9] | 10623 | 0.353 | 0.0 | 104.550919 |
| sam/LIVE-K4CW-r16-fp | fast-v2 | 47.263333 | 14.12 | [1.65, 5.9] | 10147 | 0.346 | 0.0 | 100.330674 |
| sam/LIVE-K4CW-r16-fp | fast-f1a2 | 38.660000 | 12.16 | [2.15, 6.65] | 9448 | 0.445 | 0.029 | 102.725903 |
| sam/R3a | fast-v10 | 47.723333 | 13.93 | [1.4, 6.4] | 9915 | 0.388 | 0.009 | 54.310091 |
| sam/R3a | fast-v2 | 49.003333 | 14.07 | [1.4, 6.4] | 10186 | 0.371 | 0.004 | 55.179618 |
| sam/R3a | fast-f1a2 | 40.253333 | 12.33 | [2.15, 6.65] | 9400 | 0.499 | 0.043 | 71.244919 |
| account/LIVE-K4CW-r16-fp | fast-v10 | 45.153333 | 13.84 | [1.65, 5.9] | 4692 | 0.373 | 0.1 | 128.055345 |
| account/LIVE-K4CW-r16-fp | fast-v2 | 45.726667 | 13.93 | [1.65, 5.65] | 4819 | 0.355 | 0.0 | 131.309322 |
| account/LIVE-K4CW-r16-fp | fast-f1a2 | 37.246667 | 12.05 | [2.15, 6.65] | 4466 | 0.482 | 0.0 | 139.103887 |
| account/R3a | fast-v10 | 47.313333 | 13.88 | [1.4, 6.65] | 5011 | 0.39 | 0.0 | 38.880345 |
| account/R3a | fast-v2 | 49.833333 | 14.15 | [1.4, 6.9] | 5307 | 0.371 | 0.027 | 40.359152 |
| account/R3a | fast-f1a2 | 39.506667 | 12.31 | [2.15, 6.65] | 4715 | 0.539 | 0.017 | 49.228348 |

Complete standalone readout `JOB/helper-gb-v10-b2715349865347232-readout.json`, SHA`646590cf92c07784f9d21b28e57c1164abf03363a3a5edb5e05b7928494aac51`, includes raw manifests,exact cases,allmodel/pin hashes,finished records and underlying PF1 counts. RowC artifacts,if any,are preserved but excluded by registration. DEV selection contrasts were never used as confirm evidence. This G-B result concerns comparison to v2; replacing search live requires the distinct G-S gate.

## G-S DEV screen v140 (source8f; selection only) (2026-10-18T17:57:47Z)

Snapshot140 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `aae1f22db7577e713864c2d5ef200327abe22962a1e261294955ac504465a954`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v140 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v140 − search [95% CI] | v140 − v2 [95% CI] | v140/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.589286 [+0.464286, +0.714286] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.142857 [-0.339286, +0.053571] | +0.250000 [+0.071429, +0.428571] | 48.732143/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.800000 [+0.700000, +0.900000] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.083333 [-0.050000, +0.216667] | +0.250000 [+0.100000, +0.400000] | 44.233333/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.900000 [+0.816667, +0.966667] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.100000 [-0.016667, +0.216667] | +0.200000 [+0.066667, +0.333333] | 42.466667/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v140 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | +0.000000 [-0.750000, +0.750000] | +0.250000 [+0.000000, +0.750000] |
| SEARCH | bait | 5 | -0.600000 [-1.000000, +0.200000] | +0.000000 [-0.600000, +0.600000] |
| SEARCH | giant | 9 | -0.444444 [-0.888889, +0.000000] | -0.222222 [-0.666667, +0.333333] |
| SEARCH | hog | 8 | -0.125000 [-0.750000, +0.500000] | +0.000000 [-0.500000, +0.500000] |
| SEARCH | other | 23 | +0.000000 [-0.217391, +0.217391] | +0.608696 [+0.391304, +0.782609] |
| SEARCH | siege | 7 | +0.000000 [-0.571429, +0.571429] | +0.142857 [-0.285714, +0.571429] |
| LIVE-K4CW-r16-fp | air | 9 | +0.111111 [-0.222222, +0.444444] | +0.111111 [+0.000000, +0.333333] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.666667 [+0.000000, +1.000000] | +1.000000 [+1.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.066667 [-0.266667, +0.333333] | +0.266667 [+0.000000, +0.533333] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.300000 [+0.000000, +0.600000] | +0.400000 [+0.000000, +0.800000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.000000 [-0.214286, +0.214286] | +0.214286 [-0.071429, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | -0.250000 [-0.625000, +0.000000] | +0.000000 [-0.500000, +0.500000] |
| R3a | air | 11 | +0.000000 [-0.363636, +0.363636] | +0.000000 [-0.363636, +0.363636] |
| R3a | bait | 6 | +0.333333 [+0.000000, +0.666667] | +0.333333 [+0.000000, +0.666667] |
| R3a | giant | 14 | +0.071429 [-0.142857, +0.285714] | +0.071429 [-0.142857, +0.285714] |
| R3a | hog | 6 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +0.666667] |
| R3a | other | 19 | +0.157895 [-0.052632, +0.368421] | +0.263158 [+0.000000, +0.526316] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x08 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v140-8f-readout.json` on08/04/01/local05, SHA `c409b58d3986f04870877f1b1b722b6b4cd62f35d7f7cab126ae9318bf9ba5f7`.

## ALL-16 two-row DEV screen v140 (selection only) (2026-10-18T17:58:46Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v140−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `aae1f22db7577e713864c2d5ef200327abe22962a1e261294955ac504465a954`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.250000 | -0.142857 [-0.339286,+0.053571] | 48.732143/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.250000 | +0.083333 [-0.050000,+0.216667] | 44.233333/48.250000 | True |
| R3a | 60 | +0.200000 | +0.100000 [-0.016667,+0.216667] | 42.466667/46.100000 | True |

Equal two-row screen=0.225; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v140": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v140": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v140": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v140": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v140-all16-only-readout.json`, SHA `15a92527e2a7b3a7fdf4aa25f9500e176383cd432f3d24e62ac30a4f3175f14a`; underlying ALL-16 readout SHA `c409b58d3986f04870877f1b1b722b6b4cd62f35d7f7cab126ae9318bf9ba5f7`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## ALL-16 v140 selection readout;04 memory retirement and v160 queue (2026-10-18T18:00:21Z)

v140 ALL-16 DEV completed180candidate rows with8zero worker statuses at17:55:27Z. The sole08standalone readout PGID3564561 launched17:56:37Z after full completion,validated exact cases/checkpoint/pins/levels and revalidated every cached reference row's bytes/metadata. SEARCH drops remain the same four live-error cases (hog,giant,royalgiant,air,one each;no majority),identically masked across candidate/v2/search;other rows have zero drops. All rows are valid under10%SEARCH/5%other limits and all candidate play rates are sane. SEARCH v140−search=−.14285714,95%pairedCI[−.33928571,+.05357143],so no G-S candidate or bank is triggered. Scope remains49.0292926714% RoyaleSim-playable corpus weight. GS publication18ec9852d22ada1f9d4980e0bdafd5fcf96ce126 is verified; full readout is copied08/04/01/local05.

The distinct two-row G-E readout PGID3572597 launched17:57:41Z after the GS validation and completed normally,with no dd1 or new games. Equal ALL-16 K4CW-fp/R3a v140−v2 screen=+.225000,valid/sane/nonnegative;SEARCH is reported separately and excluded from the mean. This is DEV selection only,not a gain and not a G-S trigger. GE publication450529f57df56e2bc557af2758eef1c063ee3c7c is verified; never rerun either v140 analysis or publisher.

At17:56:06Z04's MemAvailable had fallen to4,209,082,368bytes while all three owned24-worker blocks were running. Block53's workers had median RSS1.960556GiB. To prevent memory-related worker/sshd failure,the helper SIGTERM'd the group from its own actor-b53 receipt PGID461245 and verified it gone;MemAvailable rose to53,515,890,688bytes. Blocks52/54 remain48workers total. No source,model,learner flag,sync or unowned process was changed. The existing04load guard still owns52/53(history)/54 with cap100,or70ifwho shows a user;its historical53slot is dead and must not be reused. The global hourly error guard retains53's completed summaries and counters. No replacement block was launched;future replacements need a fresh number and admitted load/error guard coverage first.

04's fixed remote_sync-r2 stayed running. All24closed block53games files matched01 SHA256s at17:57:08Z;no block53finished NPZ remained on04 at17:58:41Z. Incomplete games terminate without a rollout;atomic completed files and all logs/artifacts were preserved. No unrecoverable loss was observed and no recovery-status message was sent to owner. On08 the current streaming drain check17:52:47Z saw10→11pendingNPZ and one changing games file;this is incomplete synchronization during production,not data loss. Its sync remains alive and the last stable0NPZ/all256file-hash PASS17:09:46Z is separately preserved. The permanent08floor and memory/load guard remain active;32workers55/56 only,retired57/58/59 remain retired.

The memory retirement allowed the existing v150 queue to admit normally at17:56:13Z,under its unchanged sole04receipt2207609. No v150 game was duplicated or moved. New v160 was launched once04 at17:58:48Z,gs-dev-v160-8f.receipt.json PGID2368793,ONE shared ALL-16 candidate180rows only. CheckpointSHAd12b4ea6e988224968817f0f071f449cc7f2e982f75820666e41ceab85e5713c was copied01→04 and SHAchecked in the same step at17:58:44Z. Metadata and receipts are preserved01/04/local05. It uses the same frozen references/source8f/case bank/keep-going and ordinary cpu_job10/nice15 admission after the memory precondition;no BattleLogSam/dd1/reference game is launched.

A generic external queue-placement helper move-gs-queue-to08.pyN is prepared/syntax-checked only,not launched. It refuses before mutation without44GiB08headroom,an active20GiB guard,absentPTR1 and no target receipt/output;then proves its04source was never admitted and has no bank/game before retiring only its receipted group. It must never be used for already-admitted v150. Further G-B confirms require a newly drawn and dated bank before games;none was registered this check. G-Bv10's published failed result and owner notification remain complete and are not repeated. S-CONFIRM1 remains unused. Whole RL training continues;the same scheduled watch stays enabled.

## G-S DEV screen v150 (source8f; selection only) (2026-10-18T18:26:12Z)

Snapshot150 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `c8f70d24b5b4c091dcfff356a000b2ff432e4e6a46a0b005331bab4d434d5be8`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v150 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v150 − search [95% CI] | v150 − v2 [95% CI] | v150/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.660714 [+0.535714, +0.785714] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.071429 [-0.250000, +0.107143] | +0.321429 [+0.178571, +0.464286] | 44.982143/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.783333 [+0.683333, +0.883333] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.066667 [-0.066667, +0.200000] | +0.233333 [+0.100000, +0.366667] | 42.200000/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.900000 [+0.816667, +0.966667] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.100000 [-0.016667, +0.216667] | +0.200000 [+0.083333, +0.316667] | 40.466667/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v150 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| SEARCH | bait | 5 | -0.400000 [-0.800000, +0.000000] | +0.200000 [+0.000000, +0.600000] |
| SEARCH | giant | 9 | +0.111111 [+0.000000, +0.333333] | +0.333333 [+0.000000, +0.666667] |
| SEARCH | hog | 8 | +0.250000 [-0.375000, +0.750000] | +0.375000 [-0.125000, +0.875000] |
| SEARCH | other | 23 | -0.173913 [-0.478261, +0.086957] | +0.434783 [+0.173913, +0.652174] |
| SEARCH | siege | 7 | +0.000000 [-0.428571, +0.428571] | +0.142857 [-0.285714, +0.571429] |
| LIVE-K4CW-r16-fp | air | 9 | +0.222222 [-0.222222, +0.666667] | +0.222222 [+0.000000, +0.555556] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.333333 [+0.000000, +1.000000] | +0.666667 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | -0.066667 [-0.333333, +0.200000] | +0.133333 [-0.133333, +0.400000] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.200000 [-0.300000, +0.600000] | +0.300000 [+0.100000, +0.600000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.000000 [-0.214286, +0.214286] | +0.214286 [-0.071429, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.000000 [+0.000000, +0.000000] | +0.250000 [-0.250000, +0.625000] |
| R3a | air | 11 | +0.000000 [-0.272727, +0.272727] | +0.000000 [-0.272727, +0.272727] |
| R3a | bait | 6 | +0.333333 [-0.333333, +0.833333] | +0.333333 [+0.000000, +0.666667] |
| R3a | giant | 14 | +0.142857 [+0.000000, +0.357143] | +0.142857 [+0.000000, +0.357143] |
| R3a | hog | 6 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +0.666667] |
| R3a | other | 19 | +0.105263 [-0.105263, +0.315789] | +0.210526 [+0.000000, +0.421053] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v150-8f-readout.json` on08/04/01/local05, SHA `0d083e7b58408847587ac77c8ad2e93364862b08d9a47d20527fcff27ef4eb14`.

## ALL-16 two-row DEV screen v150 (selection only) (2026-10-18T18:26:34Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v150−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `c8f70d24b5b4c091dcfff356a000b2ff432e4e6a46a0b005331bab4d434d5be8`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.321429 | -0.071429 [-0.250000,+0.107143] | 44.982143/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.233333 | +0.066667 [-0.066667,+0.200000] | 42.200000/48.250000 | True |
| R3a | 60 | +0.200000 | +0.100000 [-0.016667,+0.216667] | 40.466667/46.100000 | True |

Equal two-row screen=0.21666666666666667; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v150": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v150": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v150": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v150": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v150-all16-only-readout.json`, SHA `f96fdaabbbe7caac18e7bf6a4731d181e0031daa48a223e060be4224546a6d5e`; underlying ALL-16 readout SHA `0d083e7b58408847587ac77c8ad2e93364862b08d9a47d20527fcff27ef4eb14`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## Memory guard retirement, stable sync drain and snapshot170 launch (2026-10-18T18:27:30Z)

At 2026-10-18T18:27:26Z, the existing 08 memory guard's whole-block retirement of owned block56 was audited: PGID1726103 is gone. Its recorded trigger at18:06:20Z was25,728,446,464 bytes available; after retirement73,126,924,288 bytes. 08 now retains only block55W8; blocks56/57/58/59 stay retired. Fresh per-workerRSS and MemAvailable measurements are in `helper-08-memory-audit.json`; at18:24:28Z MemAvailable55.9944GiB and block55medianRSS2,271,438,848bytes. The20GiB floor remains active with the same memory guard and hourly error monitor, with no new actor or source/learner change. All24 retired block56 game logs match01, stable source, with0 finished block56 rollouts. Bounded drain hold through the existing guard produced a stable full drain at18:26:35Z:0NPZ before/after, all256 game-log hashes match01, no source changes. Hold removed18:26:55Z; existing guard owns budgeted resume and fixedsync-r3 stays alive. No unrecoverable loss. Closed Rsim hour4=35/3263(1.07263%), below5%; hour5 partial, no completed-hour claim.

Snapshot150 ALL-16 DEV analysis and the two-row G-E screen were published separately. SEARCH contrast remains negative, no G-S selector. The only ongoing candidate screens are160 and170 on04; no dd1 or BattleLog Sam job scheduled. Snapshot170 was launched once at18:26:42Z, receiptPGID2549061, checkpointSHA `cfffaecb7b67e8a9abf83d47161a854498ea83f74e80a734fea5e97a38807013` verified01/04 at `2026-10-18T18:26:38Z`. It uses the existing source8f, same180 ALL-16 DEVcases and cached references, `--keep-going`,24GiB memory admission outside the ordinaryCPU10/W8lease,nice15,100loadcap(70withconsole). No reference games rerun. At18:26:57Z160 had168/180rows and170 had0rows; no analysis of incomplete inputs.

04 remains blocks52/54=48workers after the earlier53 retirement;08 block55=8workers;01 blocks48..51=32workers. No replacement block or flag change. Training remains ongoing; registered gates and same-thread watch remain active.

## G-S DEV screen v160 (source8f; selection only) (2026-10-18T18:52:54Z)

Snapshot160 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `d12b4ea6e988224968817f0f071f449cc7f2e982f75820666e41ceab85e5713c`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v160 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v160 − search [95% CI] | v160 − v2 [95% CI] | v160/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.625000 [+0.500000, +0.750000] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.107143 [-0.267857, +0.053571] | +0.285714 [+0.142857, +0.428571] | 47.446429/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.766667 [+0.650000, +0.866667] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.050000 [-0.100000, +0.200000] | +0.216667 [+0.066667, +0.366667] | 44.266667/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.850000 [+0.766667, +0.933333] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.050000 [-0.083333, +0.166667] | +0.150000 [+0.016667, +0.283333] | 45.266667/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v160 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| SEARCH | bait | 5 | -0.400000 [-0.800000, +0.000000] | +0.200000 [-0.400000, +0.800000] |
| SEARCH | giant | 9 | -0.111111 [-0.333333, +0.000000] | +0.111111 [-0.333333, +0.555556] |
| SEARCH | hog | 8 | +0.000000 [-0.500000, +0.500000] | +0.125000 [+0.000000, +0.375000] |
| SEARCH | other | 23 | -0.086957 [-0.304348, +0.130435] | +0.521739 [+0.347826, +0.739130] |
| SEARCH | siege | 7 | +0.000000 [-0.571429, +0.571429] | +0.142857 [+0.000000, +0.428571] |
| LIVE-K4CW-r16-fp | air | 9 | -0.111111 [-0.555556, +0.333333] | -0.111111 [-0.444444, +0.222222] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.333333 [+0.000000, +1.000000] | +0.666667 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.133333 [-0.200000, +0.466667] | +0.333333 [+0.133333, +0.600000] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.100000 [-0.300000, +0.500000] | +0.200000 [+0.000000, +0.500000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.071429 [-0.142857, +0.285714] | +0.285714 [+0.000000, +0.571429] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | -0.125000 [-0.375000, +0.000000] | +0.125000 [-0.375000, +0.625000] |
| R3a | air | 11 | -0.090909 [-0.454545, +0.272727] | -0.090909 [-0.363636, +0.181818] |
| R3a | bait | 6 | +0.166667 [-0.333333, +0.666667] | +0.166667 [-0.333333, +0.666667] |
| R3a | giant | 14 | +0.142857 [+0.000000, +0.357143] | +0.142857 [+0.000000, +0.357143] |
| R3a | hog | 6 | -0.166667 [-0.500000, +0.000000] | +0.166667 [-0.333333, +0.666667] |
| R3a | other | 19 | +0.105263 [-0.105263, +0.315789] | +0.210526 [+0.000000, +0.421053] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v160-8f-readout.json` on08/04/01/local05, SHA `1133753bc78a258b6df1bd96c401f30b2dbfaab3955bf862c56544b8065eb937`.

## ALL-16 two-row DEV screen v160 (selection only) (2026-10-18T18:53:16Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v160−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `d12b4ea6e988224968817f0f071f449cc7f2e982f75820666e41ceab85e5713c`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.285714 | -0.107143 [-0.267857,+0.053571] | 47.446429/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.216667 | +0.050000 [-0.100000,+0.200000] | 44.266667/48.250000 | True |
| R3a | 60 | +0.150000 | +0.050000 [-0.083333,+0.166667] | 45.266667/46.100000 | True |

Equal two-row screen=0.18333333333333335; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v160": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v160": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v160": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v160": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v160-all16-only-readout.json`, SHA `80235b48506bc8154634fd10ba20c11c9f39e54dcbef345ab5937c9adb9c0af1`; underlying ALL-16 readout SHA `1133753bc78a258b6df1bd96c401f30b2dbfaab3955bf862c56544b8065eb937`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## G-S DEV screen v170 (source8f; selection only) (2026-10-18T18:55:17Z)

Snapshot170 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `cfffaecb7b67e8a9abf83d47161a854498ea83f74e80a734fea5e97a38807013`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v170 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v170 − search [95% CI] | v170 − v2 [95% CI] | v170/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.571429 [+0.446429, +0.696429] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.160714 [-0.321429, +0.000000] | +0.232143 [+0.089286, +0.375000] | 45.392857/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.783333 [+0.666667, +0.883333] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.066667 [-0.083333, +0.216667] | +0.233333 [+0.100000, +0.366667] | 44.300000/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.900000 [+0.816667, +0.966667] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.100000 [-0.016667, +0.216667] | +0.200000 [+0.083333, +0.316667] | 46.366667/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v170 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| SEARCH | bait | 5 | -0.400000 [-0.800000, +0.000000] | +0.200000 [+0.000000, +0.600000] |
| SEARCH | giant | 9 | -0.222222 [-0.555556, +0.000000] | +0.000000 [-0.444444, +0.444444] |
| SEARCH | hog | 8 | +0.000000 [-0.500000, +0.500000] | +0.125000 [+0.000000, +0.375000] |
| SEARCH | other | 23 | -0.130435 [-0.391304, +0.130435] | +0.478261 [+0.260870, +0.695652] |
| SEARCH | siege | 7 | -0.142857 [-0.571429, +0.285714] | +0.000000 [-0.428571, +0.428571] |
| LIVE-K4CW-r16-fp | air | 9 | +0.222222 [+0.000000, +0.555556] | +0.222222 [+0.000000, +0.555556] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.333333 [-1.000000, +1.000000] | +0.666667 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.066667 [-0.200000, +0.333333] | +0.266667 [+0.000000, +0.533333] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.000000 [-0.400000, +0.400000] | +0.100000 [-0.200000, +0.400000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.071429 [-0.142857, +0.285714] | +0.285714 [+0.071429, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | -0.125000 [-0.500000, +0.250000] | +0.125000 [-0.250000, +0.500000] |
| R3a | air | 11 | +0.090909 [-0.181818, +0.363636] | +0.090909 [-0.181818, +0.363636] |
| R3a | bait | 6 | +0.166667 [-0.333333, +0.666667] | +0.166667 [+0.000000, +0.500000] |
| R3a | giant | 14 | +0.142857 [+0.000000, +0.357143] | +0.142857 [+0.000000, +0.357143] |
| R3a | hog | 6 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +0.666667] |
| R3a | other | 19 | +0.105263 [-0.157895, +0.368421] | +0.210526 [+0.000000, +0.421053] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v170-8f-readout.json` on08/04/01/local05, SHA `2222020f0768a26ad88b7277a717900db12aebf94b47117d731490be2d576bd3`.

## ALL-16 two-row DEV screen v170 (selection only) (2026-10-18T18:55:29Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v170−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `cfffaecb7b67e8a9abf83d47161a854498ea83f74e80a734fea5e97a38807013`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.232143 | -0.160714 [-0.321429,+0.000000] | 45.392857/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.233333 | +0.066667 [-0.083333,+0.216667] | 44.300000/48.250000 | True |
| R3a | 60 | +0.200000 | +0.100000 [-0.016667,+0.216667] | 46.366667/46.100000 | True |

Equal two-row screen=0.21666666666666667; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v170": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v170": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v170": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v170": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v170-all16-only-readout.json`, SHA `40cc9a7c191db08f7bd64efc4f79d21b9f77c005522eb81c252cb5d08974bec5`; underlying ALL-16 readout SHA `2222020f0768a26ad88b7277a717900db12aebf94b47117d731490be2d576bd3`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## Snapshot180 launch and never-admitted memory-queue placement (2026-10-18T19:23:15Z)

At 2026-10-18T19:23:11Z, snapshot180 was frozen/copied01→04 with matched command SHA `e770d2c714a0442a60be9fdf39eef6b4fc51a54ac062adc0471d37b2b030677a` at `2026-10-18T19:21:55Z`. It uses the existing source8f, same180 ALL-16 DEVcases and reused v2/search references, `--keep-going`, one candidate arm only; these rows serve both the registered two-row G-E and G-S DEV selector. No Sam/dd1/reference games were scheduled.

The initial04 receiptPGID2881363 launched19:21:59Z remained in24GiB memory admission with no Python, no bank and no game/output. After target08 preflight showed107,872,157,696bytes available, the active20GiB memory guard and no PTR1, the owned04 group was retired and verified gone at19:22:29Z before moving. All seven08 model SHA256SUMS passed; frozen checkpoint SHA matched04/08. The sole fresh08 replacement receipt `gs-dev-v180-8f-r2.receipt.json` PGID4154506 launched19:22:36Z under normalcpu_job10/W8/nice15/cap100. Original04 receipt/log retained. Placement evidence `JOB/helper-gs-v180-placement.json` on01/04/08/local05. No game was rerun or discarded, and CPU admission was preserved.

Current source8f/corpus SHA16ca9bfbc72b028ffdb44d4497db8464dff60f0560ce6eb098a48ee12f149b8e/statistical4167/G-Eprotocol3a9 remain fixed. RoyaleSim-playable scope49.0292926714% of corpus weight. Existing01learner-r2/source095, actor cohorts01=48..51/04=52,54/08=55, guards and fixed syncs remain unchanged. 08's20GiB memory floor and P1-lag reservation stay active. No new actor/source/restart/learner flag was introduced. Completed G-B10 failed and every completed ALL-16 SEARCH selector through170 is negative; S-CONFIRM1 remains unused and no OFF1/confirm game is scheduled.

## G-S DEV screen v180 (source8f; selection only) (2026-10-18T19:53:23Z)

Snapshot180 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `e770d2c714a0442a60be9fdf39eef6b4fc51a54ac062adc0471d37b2b030677a`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v180 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v180 − search [95% CI] | v180 − v2 [95% CI] | v180/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.535714 [+0.410714, +0.678571] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.196429 [-0.375000, -0.017857] | +0.196429 [+0.053571, +0.357143] | 43.803571/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.800000 [+0.700000, +0.900000] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.083333 [-0.050000, +0.216667] | +0.250000 [+0.100000, +0.400000] | 45.433333/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.833333 [+0.733333, +0.916667] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.033333 [-0.083333, +0.150000] | +0.133333 [+0.016667, +0.266667] | 45.616667/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v180 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| SEARCH | bait | 5 | -0.400000 [-1.000000, +0.400000] | +0.200000 [-0.400000, +0.800000] |
| SEARCH | giant | 9 | -0.222222 [-0.666667, +0.222222] | +0.000000 [-0.333333, +0.333333] |
| SEARCH | hog | 8 | +0.125000 [-0.375000, +0.625000] | +0.250000 [-0.250000, +0.750000] |
| SEARCH | other | 23 | -0.217391 [-0.478261, +0.043478] | +0.391304 [+0.173913, +0.608696] |
| SEARCH | siege | 7 | -0.285714 [-0.714286, +0.285714] | -0.142857 [-0.428571, +0.000000] |
| LIVE-K4CW-r16-fp | air | 9 | +0.111111 [-0.222222, +0.444444] | +0.111111 [-0.222222, +0.444444] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [-1.000000, +1.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.000000 [-0.266667, +0.266667] | +0.200000 [-0.133333, +0.533333] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.400000 [+0.100000, +0.700000] | +0.500000 [+0.200000, +0.800000] |
| LIVE-K4CW-r16-fp | other | 14 | -0.071429 [-0.285714, +0.142857] | +0.142857 [-0.214286, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.125000 [+0.000000, +0.375000] | +0.375000 [+0.125000, +0.750000] |
| R3a | air | 11 | +0.090909 [+0.000000, +0.272727] | +0.090909 [+0.000000, +0.272727] |
| R3a | bait | 6 | +0.166667 [+0.000000, +0.500000] | +0.166667 [-0.500000, +0.833333] |
| R3a | giant | 14 | +0.000000 [-0.285714, +0.285714] | +0.000000 [-0.214286, +0.214286] |
| R3a | hog | 6 | -0.500000 [-0.833333, -0.166667] | -0.166667 [-0.500000, +0.000000] |
| R3a | other | 19 | +0.157895 [-0.052632, +0.368421] | +0.263158 [+0.105263, +0.473684] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x08 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v180-8f-readout.json` on08/04/01/local05, SHA `94474038d866db2a719bcda71841ee474040990785f92d016044150ef0017bfd`.

## ALL-16 two-row DEV screen v180 (selection only) (2026-10-18T19:53:50Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v180−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `e770d2c714a0442a60be9fdf39eef6b4fc51a54ac062adc0471d37b2b030677a`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.196429 | -0.196429 [-0.375000,-0.017857] | 43.803571/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.250000 | +0.083333 [-0.050000,+0.216667] | 45.433333/48.250000 | True |
| R3a | 60 | +0.133333 | +0.033333 [-0.083333,+0.150000] | 45.616667/46.100000 | True |

Equal two-row screen=0.19166666666666665; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v180": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v180": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v180": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v180": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v180-all16-only-readout.json`, SHA `5335335228e38d64af7d60403e64d421fe0af199259d99200b6deaee53a5a380`; underlying ALL-16 readout SHA `94474038d866db2a719bcda71841ee474040990785f92d016044150ef0017bfd`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## 04 memory containment and snapshot190 launch (2026-10-18T19:54:21Z)

At 2026-10-18T19:54:18Z,04's owned block52 was retired before predicted memory exhaustion. The earlier13,533,814,784bytes available and growing median workerRSS2,960,846,848bytes were measured from commands; own receipt PGID461034 was SIGTERM/CONT for paused-group exit, verified gone at `2026-10-18T19:52:28Z`. Available memory recovered to84,410,540,032bytes. Existing block54W24, loadguard and fixedsync-r2 remain; no unowned process/GPU was touched and no learner/source/flag changed. All24closed block52 game logs are stable and SHA256-match01, with0 finished rollout files at `2026-10-18T19:53:21Z`; evidence `JOB/helper-04-memory-retire-b52.json` on04/01/local05. All completed atomic files/logs were preserved. No irrecoverable loss. Block52 is spent/retired and is never revived. No smaller actor replacement was launched.

The sole snapshot190 shared ALL-16 DEV job launched04 at19:52:46Z, receipt `gs-dev-v190-8f.receipt.json` PGID3056774, after resource recovery. It admitted normally and had a runtime bank at19:53:50Z. Frozen checkpointSHA `54b68c00461a3892bff1598a7afd1f51429ea3c58e09045208c1d328050573e2` was copied01→04 and verified at `2026-10-18T19:52:42Z`. Source8f/cached v2+search references/19 exclusions/keep-going/180case candidate arm/cpu10W8nice15/memory24GiB pre-admission/loadcap100(70console) unchanged. No Sam/dd1/reference game was scheduled. Snapshot180 completed raw inputs and its separate published G-S/G-E readouts; its SEARCH comparison remains negative, so no OFF1 or confirm bank was used.

Current production cohorts:01blocks48..51W8each=32workers,04block54W24=24,08block55W8=8. Retired04blocks52/53 and08blocks56..59 remain gone; existing guards keep their historical cohort entries and ignore retired groups. Re-measure throughput only after stable post-retirement updates; no capacity or causal claim is made here. The20GiB08 memory floor/P1-lag reservation, fixedsyncs and hourly error monitor remain active with original counters.

## G-S DEV screen v190 (source8f; selection only) (2026-10-18T20:23:06Z)

Snapshot190 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `54b68c00461a3892bff1598a7afd1f51429ea3c58e09045208c1d328050573e2`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v190 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v190 − search [95% CI] | v190 − v2 [95% CI] | v190/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.535714 [+0.410714, +0.660714] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.196429 [-0.375000, -0.017857] | +0.196429 [+0.053571, +0.339286] | 44.910714/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.800000 [+0.700000, +0.900000] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.083333 [-0.066667, +0.216667] | +0.250000 [+0.100000, +0.400000] | 45.166667/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.883333 [+0.800000, +0.950000] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.083333 [-0.050000, +0.216667] | +0.183333 [+0.050000, +0.316667] | 45.633333/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v190 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| SEARCH | bait | 5 | -0.400000 [-0.800000, +0.000000] | +0.200000 [-0.400000, +0.800000] |
| SEARCH | giant | 9 | -0.222222 [-0.666667, +0.222222] | +0.000000 [-0.333333, +0.333333] |
| SEARCH | hog | 8 | +0.125000 [-0.500000, +0.625000] | +0.250000 [-0.250000, +0.750000] |
| SEARCH | other | 23 | -0.304348 [-0.565217, -0.043478] | +0.304348 [+0.086957, +0.521739] |
| SEARCH | siege | 7 | +0.000000 [-0.571429, +0.571429] | +0.142857 [+0.000000, +0.428571] |
| LIVE-K4CW-r16-fp | air | 9 | +0.111111 [-0.222222, +0.444444] | +0.111111 [-0.222222, +0.444444] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.133333 [-0.200000, +0.466667] | +0.333333 [-0.066667, +0.666667] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.300000 [-0.100000, +0.700000] | +0.400000 [+0.100000, +0.700000] |
| LIVE-K4CW-r16-fp | other | 14 | -0.071429 [-0.285714, +0.142857] | +0.142857 [-0.214286, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.000000 [-0.375000, +0.375000] | +0.250000 [+0.000000, +0.500000] |
| R3a | air | 11 | +0.090909 [-0.181818, +0.363636] | +0.090909 [+0.000000, +0.272727] |
| R3a | bait | 6 | +0.333333 [-0.333333, +0.833333] | +0.333333 [+0.000000, +0.666667] |
| R3a | giant | 14 | +0.071429 [-0.142857, +0.357143] | +0.071429 [-0.142857, +0.285714] |
| R3a | hog | 6 | -0.333333 [-0.666667, +0.000000] | +0.000000 [-0.666667, +0.666667] |
| R3a | other | 19 | +0.157895 [-0.052632, +0.368421] | +0.263158 [+0.105263, +0.473684] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v190-8f-readout.json` on08/04/01/local05, SHA `565e168670aa77dd0945c64f35116048c12976acb254caa179de0817604311a8`.

## ALL-16 two-row DEV screen v190 (selection only) (2026-10-18T20:23:26Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v190−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `54b68c00461a3892bff1598a7afd1f51429ea3c58e09045208c1d328050573e2`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.196429 | -0.196429 [-0.375000,-0.017857] | 44.910714/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.250000 | +0.083333 [-0.066667,+0.216667] | 45.166667/48.250000 | True |
| R3a | 60 | +0.183333 | +0.083333 [-0.050000,+0.216667] | 45.633333/46.100000 | True |

Equal two-row screen=0.21666666666666667; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v190": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v190": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v190": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v190": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v190-all16-only-readout.json`, SHA `c56a66f70d75e145ebe11d9c3098b9229ce539c94de22852af44fee77fcdc356`; underlying ALL-16 readout SHA `565e168670aa77dd0945c64f35116048c12976acb254caa179de0817604311a8`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## Snapshot200 shared DEV launch and resource watch (2026-10-18T20:23:51Z)

Snapshot200's sole shared ALL-16 DEV candidate arm launched04 at20:22:01Z with receipt `gs-dev-v200-8f.receipt.json` PGID3214051, normal CPU admission/runtime parent visible20:22:30Z. Frozen checkpointSHA `6135271992ebed82673d7ddd691981ee5d05060f2525c3f42f85cc84d5fdab0f` matched01/04 at `2026-10-18T20:21:57Z`. Source8f, the same180cases, cached v2/search reference,19exclusions, `--keep-going`, cpu10/W8/nice15,24GiB memory admission and100loadcap(70console) remain. No Sam/dd1/reference game was scheduled, and no source/learner/actor/guard/flag changed. Snapshot190 completed and its separately published G-S/G-E readouts did not meet the SEARCH selector; S-CONFIRM1 and OFF1 remain unused.

At 2026-10-18T20:23:48Z, the latest completed-hour error window6=26/2362(1.1007621%) stayed below5%; prior completed hours0..5 also stayed below5%. Hour7 is partial and is not labelled a pass. Existing error-monitor counters/anchor and memory guard are preserved. Current production cohorts remain01blocks48..51W8each,04block54W24,08block55W8;04blocks52/53 and08blocks56..59 remain retired.08MemAvailable95.8023GiB at20:21:41Z meets the permanent20GiB floor; worker55medianRSS3,456,929,792bytes/p903,731,955,712bytes.04MemAvailable71.8541GiB at20:21:41Z, worker54medianRSS2,214,346,752bytes at20:22:30Z. No capacity refill or causal throughput claim.

## G-S DEV screen v200 (source8f; selection only) (2026-10-18T20:52:57Z)

Snapshot200 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `6135271992ebed82673d7ddd691981ee5d05060f2525c3f42f85cc84d5fdab0f`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v200 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v200 − search [95% CI] | v200 − v2 [95% CI] | v200/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.535714 [+0.410714, +0.660714] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.196429 [-0.357143, -0.017857] | +0.196429 [+0.035714, +0.357143] | 45.910714/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.800000 [+0.700000, +0.900000] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.083333 [-0.050000, +0.216667] | +0.250000 [+0.116667, +0.383333] | 41.116667/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.850000 [+0.750000, +0.933333] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.050000 [-0.083333, +0.183333] | +0.150000 [+0.033333, +0.283333] | 40.750000/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v200 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | +0.000000 [+0.000000, +0.000000] | +0.250000 [+0.000000, +0.750000] |
| SEARCH | bait | 5 | -0.600000 [-1.000000, -0.200000] | +0.000000 [-0.600000, +0.600000] |
| SEARCH | giant | 9 | -0.333333 [-0.777778, +0.111111] | -0.111111 [-0.444444, +0.222222] |
| SEARCH | hog | 8 | -0.250000 [-0.750000, +0.250000] | -0.125000 [-0.625000, +0.375000] |
| SEARCH | other | 23 | -0.173913 [-0.434783, +0.086957] | +0.434783 [+0.260870, +0.652174] |
| SEARCH | siege | 7 | +0.142857 [-0.285714, +0.571429] | +0.285714 [+0.000000, +0.571429] |
| LIVE-K4CW-r16-fp | air | 9 | +0.111111 [-0.333333, +0.555556] | +0.111111 [-0.222222, +0.444444] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.133333 [-0.133333, +0.400000] | +0.333333 [+0.133333, +0.600000] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.200000 [-0.200000, +0.600000] | +0.300000 [-0.100000, +0.700000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.000000 [-0.214286, +0.214286] | +0.214286 [-0.071429, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.000000 [-0.375000, +0.375000] | +0.250000 [+0.000000, +0.500000] |
| R3a | air | 11 | +0.181818 [+0.000000, +0.454545] | +0.181818 [+0.000000, +0.454545] |
| R3a | bait | 6 | +0.166667 [-0.333333, +0.666667] | +0.166667 [+0.000000, +0.500000] |
| R3a | giant | 14 | +0.000000 [-0.285714, +0.285714] | +0.000000 [-0.214286, +0.214286] |
| R3a | hog | 6 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +0.666667] |
| R3a | other | 19 | +0.105263 [-0.105263, +0.315789] | +0.210526 [+0.000000, +0.421053] |
| R3a | siege | 4 | -0.500000 [-1.000000, +0.000000] | +0.000000 [-0.750000, +0.750000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v200-8f-readout.json` on08/04/01/local05, SHA `c4e60cfcc2d87f8ef3a83a187732c43588e2d5610e8f6f0b34a5564d3c343ad5`.

## ALL-16 two-row DEV screen v200 (selection only) (2026-10-18T20:53:16Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v200−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `6135271992ebed82673d7ddd691981ee5d05060f2525c3f42f85cc84d5fdab0f`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.196429 | -0.196429 [-0.357143,-0.017857] | 45.910714/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.250000 | +0.083333 [-0.050000,+0.216667] | 41.116667/48.250000 | True |
| R3a | 60 | +0.150000 | +0.050000 [-0.083333,+0.183333] | 40.750000/46.100000 | True |

Equal two-row screen=0.2; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v200": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v200": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v200": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v200": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v200-all16-only-readout.json`, SHA `9672895c1a068663568f3b2a4e70ffc6c1532550d28421ef52c5b33249f3af92`; underlying ALL-16 readout SHA `c4e60cfcc2d87f8ef3a83a187732c43588e2d5610e8f6f0b34a5564d3c343ad5`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## Snapshot210 shared DEV launch and resource watch (2026-10-18T20:53:43Z)

Snapshot210's sole shared ALL-16 DEV candidate arm launched04 at20:52:01Z, receipt `gs-dev-v210-8f.receipt.json` PGID3372648, admitted normally. Frozen checkpointSHA `0518ce80632b50d8923b7b0761700fd0b06072ae7fa1d51fd597844d2232de8d` matched01/04 at `2026-10-18T20:51:57Z`. It retains source8f, the same180cases, cached v2/search references,19exclusions, `--keep-going`, cpu10/W8/nice15,24GiB memory admission and100loadcap(70console). These single-arm candidate rows serve both the registered two-row G-E and G-S DEV selector. No Sam/dd1/reference game was scheduled; no source/learner/actor/guard/flag changed. Snapshot200 completed and its separately published readouts did not meet the SEARCH selector; S-CONFIRM1 and OFF1 remain unused.

At 2026-10-18T20:53:39Z, the latest completed-hour error windows0..6 remain below5%; hour7 is partial and is not labelled a pass. Existing monitor counters/anchor and memory guard are preserved. Current production cohorts remain01blocks48..51W8each,04block54W24,08block55W8; retired blocks remain gone.08MemAvailable93.7159GiB at20:51:41Z meets the permanent20GiB floor; worker55medianRSS3,757,723,648bytes/p904,120,395,776bytes.04MemAvailable64.8070GiB at20:51:41Z, worker54medianRSS2,542,616,576bytes at20:52:16Z. No capacity refill or causal throughput claim.

## G-S DEV screen v210 (source8f; selection only) (2026-10-18T21:23:06Z)

Snapshot210 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `0518ce80632b50d8923b7b0761700fd0b06072ae7fa1d51fd597844d2232de8d`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v210 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v210 − search [95% CI] | v210 − v2 [95% CI] | v210/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.660714 [+0.535714, +0.785714] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.071429 [-0.250000, +0.107143] | +0.321429 [+0.142857, +0.500000] | 45.946429/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.783333 [+0.666667, +0.883333] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.066667 [-0.066667, +0.200000] | +0.233333 [+0.100000, +0.366667] | 45.816667/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.866667 [+0.783333, +0.950000] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.066667 [-0.066667, +0.200000] | +0.166667 [+0.033333, +0.300000] | 42.083333/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v210 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-1.000000, +0.500000] | +0.000000 [-0.750000, +0.750000] |
| SEARCH | bait | 5 | -0.600000 [-1.000000, -0.200000] | +0.000000 [-0.600000, +0.600000] |
| SEARCH | giant | 9 | -0.111111 [-0.444444, +0.222222] | +0.111111 [-0.333333, +0.555556] |
| SEARCH | hog | 8 | +0.125000 [-0.375000, +0.625000] | +0.250000 [-0.250000, +0.750000] |
| SEARCH | other | 23 | -0.043478 [-0.260870, +0.173913] | +0.565217 [+0.347826, +0.782609] |
| SEARCH | siege | 7 | +0.142857 [-0.285714, +0.571429] | +0.285714 [-0.285714, +0.714286] |
| LIVE-K4CW-r16-fp | air | 9 | +0.111111 [-0.333333, +0.555556] | +0.111111 [-0.222222, +0.444444] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.000000 [-0.200000, +0.200000] | +0.200000 [-0.066667, +0.466667] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.200000 [-0.300000, +0.600000] | +0.300000 [+0.000000, +0.600000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.000000 [-0.214286, +0.214286] | +0.214286 [-0.071429, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.125000 [+0.000000, +0.375000] | +0.375000 [+0.125000, +0.750000] |
| R3a | air | 11 | +0.090909 [-0.181818, +0.363636] | +0.090909 [-0.181818, +0.363636] |
| R3a | bait | 6 | +0.500000 [+0.166667, +0.833333] | +0.500000 [+0.166667, +0.833333] |
| R3a | giant | 14 | +0.000000 [-0.285714, +0.285714] | +0.000000 [-0.214286, +0.214286] |
| R3a | hog | 6 | -0.333333 [-0.666667, +0.000000] | +0.000000 [-0.500000, +0.500000] |
| R3a | other | 19 | +0.157895 [-0.052632, +0.368421] | +0.263158 [+0.105263, +0.473684] |
| R3a | siege | 4 | -0.250000 [-0.750000, +0.000000] | +0.250000 [-0.500000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v210-8f-readout.json` on08/04/01/local05, SHA `acc1e4ee1db86283af92c75ab07b7ef00a45ced88fde6f23e2f4ce8b8aa58f31`.

## ALL-16 two-row DEV screen v210 (selection only) (2026-10-18T21:23:24Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v210−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `0518ce80632b50d8923b7b0761700fd0b06072ae7fa1d51fd597844d2232de8d`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.321429 | -0.071429 [-0.250000,+0.107143] | 45.946429/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.233333 | +0.066667 [-0.066667,+0.200000] | 45.816667/48.250000 | True |
| R3a | 60 | +0.166667 | +0.066667 [-0.066667,+0.200000] | 42.083333/46.100000 | True |

Equal two-row screen=0.2; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v210": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v210": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v210": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v210": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v210-all16-only-readout.json`, SHA `9c186cf2adc4f3c41bc7ce73f9a4c1f3085653859c500be9cd97785371b97b97`; underlying ALL-16 readout SHA `acc1e4ee1db86283af92c75ab07b7ef00a45ced88fde6f23e2f4ce8b8aa58f31`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## Snapshot220 shared DEV launch and resource watch (2026-10-18T21:23:51Z)

Snapshot220's sole shared ALL-16 DEV candidate arm launched04 at21:22:10Z, receipt `gs-dev-v220-8f.receipt.json` PGID3528343, admitted normally. Frozen checkpointSHA `09ee1d1d4a77541e6a55a1e80e4bb129fe292765f875026d2e6184b947e0f3c4` matched01/04 at `2026-10-18T21:22:06Z`. It retains source8f, the same180cases, cached v2/search references,19exclusions, `--keep-going`, cpu10/W8/nice15,24GiB memory admission and100loadcap(70console). These single-arm candidate rows serve both the registered two-row G-E and G-S DEV selector. No Sam/dd1/reference game was scheduled; no source/learner/actor/guard/flag changed. Snapshot210 completed and its separately published readouts did not meet the SEARCH selector; S-CONFIRM1 and OFF1 remain unused.

At 2026-10-18T21:23:47Z, closed error window7=14/1899(0.7372301%) remains below5%, as do closed windows0..6. Window8 is partial and is not labelled a pass. Existing monitor counters/anchor and memory guard are preserved. Current production cohorts remain01blocks48..51W8each,04block54W24,08block55W8; retired blocks remain gone.08MemAvailable91.3341GiB at21:21:44Z meets the permanent20GiB floor; worker55medianRSS4,049,633,280bytes/p904,382,949,376bytes.04MemAvailable58.8557GiB at21:21:44Z, worker54medianRSS2,853,261,312bytes at21:22:30Z. No capacity refill or causal throughput claim.

## G-S DEV screen v220 (source8f; selection only) (2026-10-18T21:52:54Z)

Snapshot220 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `09ee1d1d4a77541e6a55a1e80e4bb129fe292765f875026d2e6184b947e0f3c4`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v220 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v220 − search [95% CI] | v220 − v2 [95% CI] | v220/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.642857 [+0.517857, +0.767857] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.089286 [-0.232143, +0.053571] | +0.303571 [+0.125000, +0.482143] | 46.696429/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.766667 [+0.650000, +0.866667] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.050000 [-0.083333, +0.183333] | +0.216667 [+0.050000, +0.366667] | 43.750000/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.800000 [+0.700000, +0.900000] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.000000 [-0.133333, +0.133333] | +0.100000 [-0.016667, +0.233333] | 46.466667/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v220 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [-0.750000, +0.750000] |
| SEARCH | bait | 5 | -0.200000 [-0.600000, +0.000000] | +0.400000 [-0.400000, +1.000000] |
| SEARCH | giant | 9 | -0.111111 [-0.333333, +0.000000] | +0.111111 [-0.333333, +0.555556] |
| SEARCH | hog | 8 | +0.125000 [-0.375000, +0.625000] | +0.250000 [-0.375000, +0.750000] |
| SEARCH | other | 23 | -0.086957 [-0.304348, +0.130435] | +0.521739 [+0.304348, +0.739130] |
| SEARCH | siege | 7 | -0.142857 [-0.571429, +0.285714] | +0.000000 [-0.428571, +0.428571] |
| LIVE-K4CW-r16-fp | air | 9 | +0.111111 [-0.333333, +0.555556] | +0.111111 [-0.333333, +0.555556] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.333333 [+0.000000, +1.000000] | +0.666667 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.000000 [-0.266667, +0.266667] | +0.200000 [-0.066667, +0.466667] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.200000 [-0.200000, +0.600000] | +0.300000 [-0.100000, +0.700000] |
| LIVE-K4CW-r16-fp | other | 14 | -0.071429 [-0.285714, +0.142857] | +0.142857 [-0.142857, +0.428571] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.000000 [+0.000000, +0.000000] | +0.250000 [-0.250000, +0.625000] |
| R3a | air | 11 | +0.000000 [-0.272727, +0.272727] | +0.000000 [-0.272727, +0.272727] |
| R3a | bait | 6 | +0.166667 [-0.333333, +0.666667] | +0.166667 [+0.000000, +0.500000] |
| R3a | giant | 14 | -0.142857 [-0.500000, +0.214286] | -0.142857 [-0.357143, +0.000000] |
| R3a | hog | 6 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +0.666667] |
| R3a | other | 19 | +0.052632 [-0.157895, +0.263158] | +0.157895 [-0.105263, +0.421053] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v220-8f-readout.json` on08/04/01/local05, SHA `f63c946198eedbfa6beb8b43b3671e1851342d5e001eb85ed049470c142709a7`.

## ALL-16 two-row DEV screen v220 (selection only) (2026-10-18T21:53:20Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v220−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `09ee1d1d4a77541e6a55a1e80e4bb129fe292765f875026d2e6184b947e0f3c4`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.303571 | -0.089286 [-0.232143,+0.053571] | 46.696429/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.216667 | +0.050000 [-0.083333,+0.183333] | 43.750000/48.250000 | True |
| R3a | 60 | +0.100000 | +0.000000 [-0.133333,+0.133333] | 46.466667/46.100000 | True |

Equal two-row screen=0.15833333333333333; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v220": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v220": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v220": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v220": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v220-all16-only-readout.json`, SHA `0c1009b1ff421419cf51c6d2bc485e2f34643bccf51246f3c12bd4333c6bfba5`; underlying ALL-16 readout SHA `f63c946198eedbfa6beb8b43b3671e1851342d5e001eb85ed049470c142709a7`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## Snapshot230 shared DEV launch and resource watch (2026-10-18T22:22:44Z)

Snapshot230's sole shared ALL-16 DEV candidate arm launched04 at22:22:13Z, receipt `gs-dev-v230-8f.receipt.json` PGID3832182, under normal CPU admission. Frozen checkpointSHA `da7df3532ea8a948597a8d9aa2aab2786dfa6a4afde977e5083d027f9bd9c4dd` matched01/04 at `2026-10-18T22:22:09Z`. It retains source8f, the same180cases, cached v2/search references,19exclusions, `--keep-going`, cpu10/W8/nice15,24GiB memory admission and100loadcap(70console). These single-arm candidate rows serve both the registered two-row G-E and G-S DEV selector. No Sam/dd1/reference game was scheduled; no source/learner/actor/guard/flag changed. All completed screens through220 remain published and unchanged; no analysis was rerun this watch. S-CONFIRM1 and OFF1 remain unused.

At 2026-10-18T22:22:41Z, closed error window8=12/1915(0.6266319%) remains below5%, as do closed windows0..7. Window9 is partial and is not labelled a pass. Existing monitor counters/anchor and memory guard are preserved. Current production cohorts remain01blocks48..51W8each,04block54W24,08block55W8; retired blocks remain gone.08MemAvailable86.6797GiB at22:21:48Z meets the permanent20GiB floor; worker55medianRSS4,724,154,368bytes/p905,042,384,896bytes.04MemAvailable44.6290GiB at22:21:48Z, worker54medianRSS3,435,737,088bytes. No capacity refill or causal throughput claim.

## G-S candidate v230: OFF1 sanity registered before games (2026-10-18T22:54:52Z)

Before the first off-deck sanity game for G-S candidate v230, register the completed qualifying proof `helper-gs-dev-v230-8f-readout.json` SHA `66a776caf4c230e45193e25faa8f0337b6be1b494edefafdd7bbd56588dfbfa6` and checkpoint SHA `da7df3532ea8a948597a8d9aa2aab2786dfa6a4afde977e5083d027f9bd9c4dd` at 2026-10-18T22:54:48Z. Under protocol3a9c34f80578565501e9c4cec138fad995f30065, use amendment2 OFF1 frequency base2746836719317424 and uniform base2746836719517424, our engine/max/every card,100cases each vsR3a andK4C-r16, arms student:v230@tau0 and student:v2@tau0. These descriptive rows consume no S-CONFIRM bank and are run once per candidate separately from the primary G-S gate.

## G-S v230 confirm bank 3262629447693008: registered before games (2026-10-18T22:55:15Z)

Before the first G-S confirm game, register version230 on bank3262629447693008. Selector: valid ALL-16 DEV SEARCH point >=0, proved by `helper-gs-dev-v230-8f-readout.json` SHA `66a776caf4c230e45193e25faa8f0337b6be1b494edefafdd7bbd56588dfbfa6`. This is selection only, not a policy-strength claim. Checkpoint `/mpac/sdicks02/jobs/clasher/bot-hp1-rl-20261018/evals/checkpoints/policy-00230.pt`, SHA `da7df3532ea8a948597a8d9aa2aab2786dfa6a4afde977e5083d027f9bd9c4dd`; source `8f5272934f456e930aa250bba45eaa9b3c259b71`; corpus SHA `16ca9bfbc72b028ffdb44d4497db8464dff60f0560ce6eb098a48ee12f149b8e`. Registration UTC2026-10-18T22:55:11Z. First bank is S-CONFIRM1; no G-S bank ledger, confirm receipt or primary output was present on01/04/08 at preflight. No game has yet been started by this registration.

Primary ALL-16 uses200cases per SEARCH/K4CW-fp/R3a at bank+400000; ALL-acct150peropponent at bank+500000, LV2King9 table with rarity floors, all three arms fast-v230/search/fast-v2. Exact19-card exclusions and all-deck mix are those registered. Scope:49.0292926714% RoyaleSim-playable corpus weight (50.9707073286% excluded). Identical case masks across all arms,10% SEARCH/5% K4CW-fp/R3a drop limits and strict>50% archetype concentration reporting. Paired bootstrap4000Random(0),sorted100/3899. Primary SEARCH pooled lower>0,K4bothpoints>=0,R3both>=-.03,play-rate sanity per registration. Amendment1 secondary and off-deck rows are descriptive and do not enter primary pass. Sam/account log re-read before registration; the explicit Oct18 registered Hog Sam deck/levels remain selected.

## G-S DEV screen v230 (source8f; selection only) (2026-10-18T22:55:38Z)

Snapshot230 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `da7df3532ea8a948597a8d9aa2aab2786dfa6a4afde977e5083d027f9bd9c4dd`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v230 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v230 − search [95% CI] | v230 − v2 [95% CI] | v230/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.732143 [+0.607143, +0.839286] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | +0.000000 [-0.160714, +0.160714] | +0.392857 [+0.232143, +0.553571] | 43.642857/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.816667 [+0.716667, +0.900000] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.100000 [-0.016667, +0.216667] | +0.266667 [+0.116667, +0.416667] | 45.083333/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.866667 [+0.783333, +0.950000] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.066667 [-0.066667, +0.200000] | +0.166667 [+0.050000, +0.300000] | 41.516667/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v230 − search point estimate≥0): **True**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [-0.750000, +0.750000] |
| SEARCH | bait | 5 | -0.200000 [-0.800000, +0.400000] | +0.400000 [-0.400000, +1.000000] |
| SEARCH | giant | 9 | +0.111111 [+0.000000, +0.333333] | +0.333333 [+0.000000, +0.666667] |
| SEARCH | hog | 8 | +0.250000 [-0.250000, +0.625000] | +0.375000 [-0.125000, +0.875000] |
| SEARCH | other | 23 | -0.043478 [-0.304348, +0.217391] | +0.565217 [+0.347826, +0.739130] |
| SEARCH | siege | 7 | +0.000000 [-0.428571, +0.428571] | +0.142857 [-0.285714, +0.571429] |
| LIVE-K4CW-r16-fp | air | 9 | -0.111111 [-0.444444, +0.222222] | -0.111111 [-0.444444, +0.222222] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.333333 [+0.000000, +1.000000] | +0.666667 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.133333 [-0.133333, +0.400000] | +0.333333 [+0.000000, +0.600000] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.400000 [+0.100000, +0.700000] | +0.500000 [+0.200000, +0.800000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.000000 [-0.214286, +0.214286] | +0.214286 [-0.142857, +0.571429] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.000000 [+0.000000, +0.000000] | +0.250000 [-0.250000, +0.625000] |
| R3a | air | 11 | +0.181818 [+0.000000, +0.454545] | +0.181818 [+0.000000, +0.454545] |
| R3a | bait | 6 | +0.166667 [-0.666667, +0.833333] | +0.166667 [+0.000000, +0.500000] |
| R3a | giant | 14 | +0.000000 [-0.285714, +0.285714] | +0.000000 [-0.285714, +0.285714] |
| R3a | hog | 6 | -0.166667 [-0.500000, +0.000000] | +0.166667 [+0.000000, +0.500000] |
| R3a | other | 19 | +0.105263 [-0.105263, +0.315789] | +0.210526 [+0.000000, +0.421053] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v230-8f-readout.json` on08/04/01/local05, SHA `66a776caf4c230e45193e25faa8f0337b6be1b494edefafdd7bbd56588dfbfa6`.

## ALL-16 two-row DEV screen v230 (selection only) (2026-10-18T22:56:18Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v230−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `da7df3532ea8a948597a8d9aa2aab2786dfa6a4afde977e5083d027f9bd9c4dd`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.392857 | +0.000000 [-0.160714,+0.160714] | 43.642857/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.266667 | +0.100000 [-0.016667,+0.216667] | 45.083333/48.250000 | True |
| R3a | 60 | +0.166667 | +0.066667 [-0.066667,+0.200000] | 41.516667/46.100000 | True |

Equal two-row screen=0.21666666666666667; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=True. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v230": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v230": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v230": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v230": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v230-all16-only-readout.json`, SHA `960c81291d09ecc856c432672ed054ab4906d15393a49b851ef7eb7ac54e690f`; underlying ALL-16 readout SHA `66a776caf4c230e45193e25faa8f0337b6be1b494edefafdd7bbd56588dfbfa6`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## v230 first G-S selector: OFF1 and S-CONFIRM1 launched; v240 screen (2026-10-18T22:58:46Z)

At 2026-10-18T22:58:42Z, the first G-S DEV selector is v230: mechanically valid ALL-16 SEARCH candidate−search point0.0, paired95% CI[-0.160714286,+0.160714286]. This is DEV selection only, not a strength or gate claim. The separately published G-S screen and two-row G-E screen retain all raw files, identical three-arm case masks and the49.0292926714% RoyaleSim-playable corpus-weight scope.

OFF1 was published before games in2a8d14ca25a202499ef66d0657893c5d221446ea and launched once on04 at22:54:54Z, ownPGID4000317. It runs our-engine/max/every-card frequency and uniform rows,800 total arm games, v230/v2, descriptive only. S-CONFIRM1 bank3262629447693008 was prepublished in24238033c2ba313b6a00432d51cd450627f61132 at2026-10-18T22:55:11Z; the sole04 confirm receiptPGID4004319 launched22:55:29Z. The bank ledger now records S-CONFIRM1 as used. Six sequential rows include two primary ALL rows(3150 arm rows total) followed by four descriptive H2H/STR rows; OFF1 is separate. Primary and secondary results are pending. No second G-S confirm can start while this one is active.

Snapshot240 was copied01→04 and SHA-verified at2026-10-18T22:54:28Z, SHA `36eac59f6fef706652bb0c8395a96ca3e79cb4f29fe348207a5afcd6ca0a1a90`. The sole shared ALL-16 DEV job04PGID3997869 launched22:54:32Z with180 candidate arm rows,source8f,keep-going,cached v2/search references,cpu_job10/W8/nice15,normal24GiB memory admission/cap100(or70 with who). No Sam,dd1 or reference games were added. At2026-10-18T22:57:45Z,240 had7 rows and no finished record; confirm ALL-16 had all8 workers in initial build,OFF1 frequency had24 arm-game records. Both230 readout groups had exited normally.

Memory/RSS audit2026-10-18T22:57:45Z:04 MemAvailable32985567232bytes; remaining production54W24 median workerRSS3789893632bytes. Retired52/53 remain gone.08 audit22:53:40Z MemAvailable83.9833145GiB; remaining55W8 medianRSS5076842496bytes,retired56..59 gone. Existing guards/fixed syncs remain; no new actor/guard/source/learner flags.08 stable drain22:55:21Z had0NPZ before/after and all256 game-log SHA256s matching01. The expiring guard hold was removed22:55:34Z and guard budgeted resume verified22:56:14Z,with no hold left. No irrecoverable loss.

Primary-result formatting helper `publish-gs-primary-result.py` is prepared and syntax-checked only; no scoring or publication is performed by preparation. Primary readout still requires completed3150 rows and both primary8-zero finished records through the staged runtime/cpu_job2/nice15. Secondary descriptive analysis remains to prepare before its completed tails are read. All completed screens≤230 are immutable; no historical game/readout/publisher rerun.

## G-S DEV screen v240 (source8f; selection only) (2026-10-18T23:23:08Z)

Snapshot240 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `36eac59f6fef706652bb0c8395a96ca3e79cb4f29fe348207a5afcd6ca0a1a90`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v240 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v240 − search [95% CI] | v240 − v2 [95% CI] | v240/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.607143 [+0.482143, +0.732143] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.125000 [-0.285714, +0.035714] | +0.267857 [+0.107143, +0.428571] | 48.107143/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.700000 [+0.583333, +0.816667] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | -0.016667 [-0.166667, +0.150000] | +0.150000 [+0.000000, +0.316667] | 47.133333/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.800000 [+0.700000, +0.900000] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.000000 [-0.133333, +0.133333] | +0.100000 [-0.033333, +0.233333] | 48.283333/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v240 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| SEARCH | bait | 5 | -0.200000 [-0.800000, +0.400000] | +0.400000 [-0.400000, +1.000000] |
| SEARCH | giant | 9 | -0.222222 [-0.666667, +0.222222] | +0.000000 [-0.333333, +0.333333] |
| SEARCH | hog | 8 | +0.125000 [-0.250000, +0.500000] | +0.250000 [-0.250000, +0.750000] |
| SEARCH | other | 23 | -0.173913 [-0.434783, +0.086957] | +0.434783 [+0.130435, +0.695652] |
| SEARCH | siege | 7 | +0.000000 [-0.428571, +0.428571] | +0.142857 [+0.000000, +0.428571] |
| LIVE-K4CW-r16-fp | air | 9 | -0.111111 [-0.555556, +0.333333] | -0.111111 [-0.444444, +0.222222] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | -0.133333 [-0.466667, +0.266667] | +0.066667 [-0.200000, +0.333333] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.300000 [-0.100000, +0.700000] | +0.400000 [+0.100000, +0.700000] |
| LIVE-K4CW-r16-fp | other | 14 | -0.071429 [-0.357143, +0.214286] | +0.142857 [-0.285714, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.000000 [+0.000000, +0.000000] | +0.250000 [-0.250000, +0.625000] |
| R3a | air | 11 | +0.090909 [-0.181818, +0.363636] | +0.090909 [-0.181818, +0.363636] |
| R3a | bait | 6 | +0.000000 [-0.666667, +0.666667] | +0.000000 [-0.500000, +0.500000] |
| R3a | giant | 14 | -0.071429 [-0.285714, +0.142857] | -0.071429 [-0.357143, +0.214286] |
| R3a | hog | 6 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +0.666667] |
| R3a | other | 19 | +0.000000 [-0.263158, +0.263158] | +0.105263 [-0.105263, +0.315789] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v240-8f-readout.json` on08/04/01/local05, SHA `b438a9779f5f1d1397029d568ff3616b7958c71b9b813a5ad504c832bac47cd4`.

## ALL-16 two-row DEV screen v240 (selection only) (2026-10-18T23:23:36Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v240−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `36eac59f6fef706652bb0c8395a96ca3e79cb4f29fe348207a5afcd6ca0a1a90`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.267857 | -0.125000 [-0.285714,+0.035714] | 48.107143/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.150000 | -0.016667 [-0.166667,+0.150000] | 47.133333/48.250000 | True |
| R3a | 60 | +0.100000 | +0.000000 [-0.133333,+0.133333] | 48.283333/46.100000 | True |

Equal two-row screen=0.125; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v240": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v240": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v240": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v240": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v240-all16-only-readout.json`, SHA `88bbe7b09eaf98ebc0f23f0e6397120a9a062e1f617b608c270baeb1bd81556f`; underlying ALL-16 readout SHA `b438a9779f5f1d1397029d568ff3616b7958c71b9b813a5ad504c832bac47cd4`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## 04 actor54 memory retirement; completed data preserved (2026-10-18T23:23:52Z)

At2026-10-18T23:23:25Z,04's last production actor block54W24 was intentionally retired by its own receiptPGID461473. Memory kept declining through v240/OFF1/primary-confirm startup, from38.15GiB at22:53 to29,179,781,120availablebytes at2026-10-18T23:00:31Z; median54workerRSS3801788416bytes. Whole own group TERM+CONT, verified gone2026-10-18T23:00:34Z, availablememory recovered to120026304512bytes. No unowned process/GPU was signalled. Existing04loadguard460544 and fixedsync-r21492518 remain; no new actor,guard,source or learnerflag was introduced. Production04 now has **zero active actors**:52/53/54 are retired/spent and must not be revived.01 retains48..51W8=32 and08 retains55W8=8.

At2026-10-18T23:21:54Z, all24 closed54game-log SHA256s matched01,source stable,finished54rollouts0. Atomic completedfiles and logs remain preserved. Artifact `JOB/helper-04-memory-retire-b54.json` on04/01/local05; actual rollout block identity uses int(g)//1000000==54. Sync remains alive. No irrecoverable loss.

S-CONFIRM1v230/OFF1 remain the sole registered candidate confirmation/sanity jobs, admitted and active. v240 finished180rows/eightzero statuses at23:15:12 and has one freshGS readout; it is not a new G-S selector(SEARCHv240−search−.125,CI[-.285714286,+.035714286]). No OFF1v240 or second confirm was launched. Snapshot250 was absent at23:22check. Primary v230 result is still pending; all strength/gate claims await the registered primary readout. Resource/capacity effects are observational; no causal throughput claim or learnerflag change.

## v230 OFF1 invalid: our-engine errors preserved; v250 DEV launched (2026-10-19T00:25:44Z)

G-S candidate v230 OFF1 is **INVALID** under the registered strict no-error/no-drop sanity rule. Both game rows completed with400 arm records each(800 total),wrapperexit0 at2026-10-18T23:58:32Z;13 arm games contain our-engine exceptions(frequency4,uniform9),all vsK4C-r16. The sole prepared validator04PGID261548 launched00:22:24 through stagedRuntime/cpu_job2/nice15 and stopped on the first error before producing a successful readout. Both gamePGID4000317 and validatorPGID261548 were verified gone at00:24:13. No failed game or analysis was retried,no case dropped,no score/overfit/strength claim. Mechanical full-case validation did not complete; record counts and the complete error/file inventory are preserved.

All13 errors report `no matching exact body template for /HealPulse from <spell> L16`,in games whose decks contain Heal. This is an observed simulation failure,not a policy-strength result. The separate RoyaleSim primary S-CONFIRM1v230 continues; it is not complete and has no gate result. No second G-S confirm was launched. Owner was notified once via the prescribed steer→thread_not_sendable→identicalauto delivery at00:24; notification marker records the message id.

| Sampler | Arm | Opponent | Index | Error | Seat0 deck | Seat1 deck |
|---|---|---|---:|---|---|---|
| offfreq | v230 | K4C-r16 | 56 | ValueError('no matching exact body template for /HealPulse from Earthquake L16') | Giant,Rocket,Knight,MiniPekka,Earthquake,Arrows,Bomber,Heal | GoblinCage,Arrows,Giant,BombTower,GoblinHut,Goblins,ElectroSpirit,HogRider |
| offfreq | v2 | K4C-r16 | 56 | ValueError('no matching exact body template for /HealPulse from Arrows L16') | Giant,Rocket,Knight,MiniPekka,Earthquake,Arrows,Bomber,Heal | GoblinCage,Arrows,Giant,BombTower,GoblinHut,Goblins,ElectroSpirit,HogRider |
| offfreq | v230 | K4C-r16 | 74 | ValueError('no matching exact body template for /HealPulse from Arrows L16') | Skeletons,IceWizard,ElectroSpirit,InfernoTower,MiniPekka,Arrows,FireSpirits,BombTower | Wizard,Arrows,Heal,GoblinDrill,GoblinHut,Tombstone,Giant,Goblins |
| offfreq | v2 | K4C-r16 | 74 | ValueError('no matching exact body template for /HealPulse from Arrows L16') | Skeletons,IceWizard,ElectroSpirit,InfernoTower,MiniPekka,Arrows,FireSpirits,BombTower | Wizard,Arrows,Heal,GoblinDrill,GoblinHut,Tombstone,Giant,Goblins |
| offrand | v230 | K4C-r16 | 28 | ValueError('no matching exact body template for /HealPulse from BarbLog L16') | GoblinGiant,FirespiritHut,RoyalGiant,WitchMother,EliteArcher,FireSpirits,Heal,IceWizard | GoblinDrill,ElectroSpirit,Goblins,SkeletonWarriors,RoyalDelivery,Lightning,LittlePrince,IceSpirit |
| offrand | v230 | K4C-r16 | 63 | ValueError('no matching exact body template for /HealPulse from Earthquake L16') | DartBarrell,GoblinMachine,BossBandit,Knight,GoblinHut,GoblinCurse,SuspiciousBush,Berserker | BlowdartGoblin,Hunter,AngryBarbarians,Heal,Earthquake,GoblinGang,Snowball,LavaHound |
| offrand | v230 | K4C-r16 | 79 | ValueError('no matching exact body template for /HealPulse from Graveyard L16') | EliteArcher,Heal,Graveyard,Elixir Collector,Musketeer,Goblins,Zap,Lightning | Knight,Zap,RoyalHogs,SpearGoblins,FireSpirits,Vines,HogRider,EliteArcher |
| offrand | v230 | K4C-r16 | 95 | ValueError('no matching exact body template for /HealPulse from BarbLog L16') | LittlePrince,MiniPekka,Fireball,BarbLog,Graveyard,Heal,RamRider,Miner | Xbow,Ronin,Knight,Balloon,DartBarrell,ElixirGolem,FirespiritHut,FireSpirits |
| offrand | v2 | K4C-r16 | 63 | ValueError('no matching exact body template for /HealPulse from GoblinCurse L16') | DartBarrell,GoblinMachine,BossBandit,Knight,GoblinHut,GoblinCurse,SuspiciousBush,Berserker | BlowdartGoblin,Hunter,AngryBarbarians,Heal,Earthquake,GoblinGang,Snowball,LavaHound |
| offrand | v2 | K4C-r16 | 79 | ValueError('no matching exact body template for /HealPulse from Graveyard L16') | EliteArcher,Heal,Graveyard,Elixir Collector,Musketeer,Goblins,Zap,Lightning | Knight,Zap,RoyalHogs,SpearGoblins,FireSpirits,Vines,HogRider,EliteArcher |
| offrand | v2 | K4C-r16 | 95 | ValueError('no matching exact body template for /HealPulse from BarbLog L16') | LittlePrince,MiniPekka,Fireball,BarbLog,Graveyard,Heal,RamRider,Miner | Xbow,Ronin,Knight,Balloon,DartBarrell,ElixirGolem,FirespiritHut,FireSpirits |
| offrand | v230 | K4C-r16 | 17 | ValueError('no matching exact body template for /HealPulse from Graveyard L16') | SkeletonWarriors,MinionHorde,GoblinDrill,Fisherman,RageBarbarian,GoblinDemolisher,Tornado,Tesla | Minions,Graveyard,LittlePrince,IceWizard,Heal,SkeletonArmy,DarkPrince,Wallbreakers |
| offrand | v2 | K4C-r16 | 50 | ValueError('no matching exact body template for /HealPulse from Arrows L16') | AngryBarbarians,IceGolem,Heal,Goblins,Tombstone,Musketeer,BabyDragon,Arrows | BombTower,SpearGoblins,Archers,RoyalGiant,BattleHealer,IceWizard,DarkWitch,GoblinBarrel |

All raw logs/launch records remain04. Full inventory `JOB/helper-gs-candidate-v230-off1-invalidity.json` on04/01/local05 includes every error row/deck,raw-file SHA256/size/mtime,launch parameters,finish record and failed-validator log SHA. `helper-off1-source-hold.json` holds additional affected our-engine OFF1 games pending owner fix/decision; the orchestration launcher refuses before SSH/publication/game. No product code,source archive,model,learner flag or existing job was edited.

Snapshot250 was copied01→04 and SHA-verified2026-10-19T00:22:30Z,checkpointSHA0b22dbbe7f40e11fb087d627a2df06c93c3356e5fac935d7ee00ac3888456279. Sole04DEVPGID262926 launched00:22:34,one180-arm-rowALL16candidate/source8f/keep-going/sharedGS+two-rowGE/cachedreferences/cpu10W8nice15/normal24GiBmemoryadmission/cap100or70Who. No Sam/dd1/reference game was added. S-CONFIRM1 remains consumed by sole v230 confirmationPGID4004319.

Secondary-only validator `helper-gs-secondary-readout-8f.py` is prepared04/08/local05,SHAee0fb53128701c93495d2f401cb50edec71bd4c1fa9212d91def2b438743bd74,syntaxchecked/noanalysisexecuted. It refuses beforeRuntime/scoring until allfourH2H/STRtails have2200 totalarmrows/fourfinishedrecordswith8zero. It reconstructs pinnedv1H2H/v3STR/PF153stratumcases,seeds,seats,deckorders/accountlevels; validatesmodel7/source/checkpoint/registration/pins; computes union masks,drop validity,archetype/concentration and paired4kRandom0CIs. Descriptive only,never a primary gate. Local `publish-gs-secondary.py` formats a completed artifact only. Runtime remains untested until actual completed tails.

## G-S DEV screen v250 (source8f; selection only) (2026-10-19T00:53:04Z)

Snapshot250 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `0b22dbbe7f40e11fb087d627a2df06c93c3356e5fac935d7ee00ac3888456279`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v250 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v250 − search [95% CI] | v250 − v2 [95% CI] | v250/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.535714 [+0.410714, +0.660714] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.196429 [-0.357143, -0.035714] | +0.196429 [+0.035714, +0.357143] | 46.714286/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.833333 [+0.733333, +0.916667] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.116667 [+0.000000, +0.233333] | +0.283333 [+0.150000, +0.416667] | 40.416667/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.916667 [+0.850000, +0.983333] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.116667 [+0.000000, +0.233333] | +0.216667 [+0.116667, +0.316667] | 45.933333/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v250 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | +0.000000 [+0.000000, +0.000000] | +0.250000 [+0.000000, +0.750000] |
| SEARCH | bait | 5 | -0.600000 [-1.000000, -0.200000] | +0.000000 [-0.600000, +0.600000] |
| SEARCH | giant | 9 | -0.222222 [-0.666667, +0.222222] | +0.000000 [-0.333333, +0.333333] |
| SEARCH | hog | 8 | -0.125000 [-0.500000, +0.250000] | +0.000000 [-0.500000, +0.500000] |
| SEARCH | other | 23 | -0.130435 [-0.304348, +0.043478] | +0.478261 [+0.260870, +0.695652] |
| SEARCH | siege | 7 | -0.285714 [-0.857143, +0.428571] | -0.142857 [-0.571429, +0.285714] |
| LIVE-K4CW-r16-fp | air | 9 | +0.000000 [-0.333333, +0.333333] | +0.000000 [-0.333333, +0.333333] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.133333 [-0.133333, +0.400000] | +0.333333 [+0.133333, +0.600000] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.300000 [-0.100000, +0.700000] | +0.400000 [+0.100000, +0.700000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.071429 [+0.000000, +0.214286] | +0.285714 [+0.000000, +0.571429] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.125000 [+0.000000, +0.375000] | +0.375000 [+0.125000, +0.750000] |
| R3a | air | 11 | +0.090909 [+0.000000, +0.272727] | +0.090909 [+0.000000, +0.272727] |
| R3a | bait | 6 | +0.166667 [-0.666667, +0.833333] | +0.166667 [+0.000000, +0.500000] |
| R3a | giant | 14 | +0.142857 [+0.000000, +0.357143] | +0.142857 [+0.000000, +0.357143] |
| R3a | hog | 6 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +0.666667] |
| R3a | other | 19 | +0.157895 [-0.052632, +0.368421] | +0.263158 [+0.105263, +0.473684] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v250-8f-readout.json` on08/04/01/local05, SHA `494129114e45eac3b35eecd1a0f042ea2a4f3fc4a16465c59480d33846125819`.

## ALL-16 two-row DEV screen v250 (selection only) (2026-10-19T00:54:11Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v250−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `0b22dbbe7f40e11fb087d627a2df06c93c3356e5fac935d7ee00ac3888456279`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.196429 | -0.196429 [-0.357143,-0.035714] | 46.714286/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.283333 | +0.116667 [+0.000000,+0.233333] | 40.416667/48.250000 | True |
| R3a | 60 | +0.216667 | +0.116667 [+0.000000,+0.233333] | 45.933333/46.100000 | True |

Equal two-row screen=0.25; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v250": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v250": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v250": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v250": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v250-all16-only-readout.json`, SHA `b1334b14288795e3d093ad3925de52b40ac40fc3e26903da497790dd89e395c8`; underlying ALL-16 readout SHA `494129114e45eac3b35eecd1a0f042ea2a4f3fc4a16465c59480d33846125819`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## v260 ALL-16 DEV launched; sole v230 primary continues (2026-10-19T01:54:27Z)

At2026-10-19T01:54:23Z,snapshot260 was staged once01→04. Its frozen checkpointSHA `3061dbb486f497ed31e2dd141a9b823d0c4ed7d1de91da4bf890573f0983a475` was verified on both hosts in the copy step2026-10-19T01:53:21Z. Sole04 `gs-dev-v260-8f.receipt.json` PGID719360 launched01:53:25Z and entered normal CPU admission/runtime(initial bank present,zero rows at01:53:55). It is one180-arm-rowALL16 candidate evaluation,source8f,keep-going,shared G-S selector/two-row G-E screen; cached v2/search references are reused. cpu_job10/W8/nice15,24GiB memory admission outside CPU lease,cap100(noWho)/70Who. Global01/04/08receipt/output preflight passed; no prior260job/output was present. No Sam,dd1 or reference game was added. No game was retried or duplicate job launched.

The sole v230 S-CONFIRM1 primary confirmationPGID4004319 continues,1,390/1,800ALL16 arm rows at01:53:55,ALL-acct not started. Its3150 primary rows/two8-zero finish records are still required before the prepared primary validator. No early analysis or gate claim. No second confirm or bank draw. ALL completedDEVthrough250remainpublished/immutable; negativeGS250SEARCHcontrast did not select another candidate.

OFF1v230 remains invalid with13our-engine errors; complete raw/error inventory and publication0cfb6277da1406e25d336d592b8da8da4ceab9ba are preserved. Its owner failure was already delivered once. No owner fix/decision was found in newest01state/origin protocol; `helper-off1-source-hold.json` remains and the launcher refuses before any further affected OFF1game/publication/SSH. No retry,redraw or repeated failure notification. The separate RoyaleSim primary/DEV jobs continue.

Fullwatch01:52:52:learnerupdate263/v260 at01:50:56,KL.0588684161,deploy36.0083333,plays40.4458333,score.672916667,EV.951008916;backlog92<960,noSTOP/alerts/newworkerfailure. Loads01/08/04=47.17/8.5/8.44,MemGiB40.679/68.811/86.091,noWho.08only55W8,workerRSSmedian7141408768bytes/20GiBfloor met;existing memory/error guards and sync stay.04 has no production actors;52/53/54 remain retired.01 retains48..51W8=32. No new actor,guard,sync,source,learner restart or flag change. Capacity/throughput effects remain observational,no causal claim.

## G-S DEV screen v260 (source8f; selection only) (2026-10-19T02:25:04Z)

Snapshot260 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `3061dbb486f497ed31e2dd141a9b823d0c4ed7d1de91da4bf890573f0983a475`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v260 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v260 − search [95% CI] | v260 − v2 [95% CI] | v260/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.625000 [+0.500000, +0.750000] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.107143 [-0.267857, +0.053571] | +0.285714 [+0.142857, +0.428571] | 43.500000/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.733333 [+0.616667, +0.833333] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.016667 [-0.133333, +0.166667] | +0.183333 [+0.033333, +0.333333] | 46.566667/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.933333 [+0.866667, +0.983333] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.133333 [+0.016667, +0.250000] | +0.233333 [+0.133333, +0.333333] | 42.000000/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v260 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | +0.000000 [+0.000000, +0.000000] | +0.250000 [+0.000000, +0.750000] |
| SEARCH | bait | 5 | -0.400000 [-0.800000, +0.000000] | +0.200000 [-0.400000, +0.800000] |
| SEARCH | giant | 9 | +0.000000 [-0.333333, +0.333333] | +0.222222 [+0.000000, +0.555556] |
| SEARCH | hog | 8 | +0.125000 [-0.250000, +0.500000] | +0.250000 [-0.250000, +0.750000] |
| SEARCH | other | 23 | -0.217391 [-0.478261, +0.043478] | +0.391304 [+0.217391, +0.608696] |
| SEARCH | siege | 7 | +0.000000 [-0.571429, +0.571429] | +0.142857 [-0.285714, +0.571429] |
| LIVE-K4CW-r16-fp | air | 9 | -0.111111 [-0.555556, +0.333333] | -0.111111 [-0.555556, +0.333333] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.333333 [+0.000000, +1.000000] | +0.666667 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.000000 [-0.333333, +0.333333] | +0.200000 [-0.066667, +0.466667] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.000000 [-0.400000, +0.400000] | +0.100000 [-0.200000, +0.400000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.142857 [+0.000000, +0.357143] | +0.357143 [+0.142857, +0.642857] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | -0.125000 [-0.375000, +0.000000] | +0.125000 [-0.250000, +0.500000] |
| R3a | air | 11 | +0.181818 [+0.000000, +0.454545] | +0.181818 [+0.000000, +0.454545] |
| R3a | bait | 6 | +0.500000 [+0.166667, +0.833333] | +0.500000 [+0.166667, +0.833333] |
| R3a | giant | 14 | +0.142857 [+0.000000, +0.357143] | +0.142857 [+0.000000, +0.357143] |
| R3a | hog | 6 | -0.166667 [-0.500000, +0.000000] | +0.166667 [+0.000000, +0.500000] |
| R3a | other | 19 | +0.105263 [-0.157895, +0.368421] | +0.210526 [+0.052632, +0.421053] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v260-8f-readout.json` on08/04/01/local05, SHA `346db2aad12bc8d429e75801b05be6da6201e7b2e20f59f4d2691d5424b6272b`.

## ALL-16 two-row DEV screen v260 (selection only) (2026-10-19T02:25:29Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v260−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `3061dbb486f497ed31e2dd141a9b823d0c4ed7d1de91da4bf890573f0983a475`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.285714 | -0.107143 [-0.267857,+0.053571] | 43.500000/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.183333 | +0.016667 [-0.133333,+0.166667] | 46.566667/48.250000 | True |
| R3a | 60 | +0.233333 | +0.133333 [+0.016667,+0.250000] | 42.000000/46.100000 | True |

Equal two-row screen=0.20833333333333331; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v260": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v260": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v260": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v260": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v260-all16-only-readout.json`, SHA `49bde32f5aec187e81434ae3cce7b28d053fb1fa074ebd354c024bf20707a33e`; underlying ALL-16 readout SHA `346db2aad12bc8d429e75801b05be6da6201e7b2e20f59f4d2691d5424b6272b`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## v270 ALL-16 DEV launched; sole v230 account primary continues (2026-10-19T03:53:07Z)

At2026-10-19T03:53:04Z, snapshot270 was staged once01→04. Frozen checkpoint SHA `d90748e67bebdad10ca7f5f151308aeb9832c089839a1ddb23e9f8101df13dfc` was verified on both hosts in copy step2026-10-19T03:52:30Z. Sole04 `gs-dev-v270-8f.receipt.json` PGID1317272 launched2026-10-19T03:52:34Z and entered normal admission/runtime: bank present,zero rows at2026-10-19T03:52:47Z. One180-arm-row ALL16 candidate, source8f/keep-going/shared G-S selector+two-row G-E, cached v2/search references reused. cpu_job10/W8/nice15,24GiB memory admission outside CPU lease,cap100(noWho)/70Who. Global01/04/08 ALLreceipt/output preflight passed/no prior270job/data. No Sam,dd1 or reference games; no retry or duplicate job.

Sole v230 S-CONFIRM1 PGID4004319 continues: ALL16 complete1800/8zero02:25:00, ALL-acct651/1350 at2026-10-19T03:52:47Z, no finished account row. TOTAL3150+two8zero required before prepared primary validator; no early analysis/gate claim/second confirm or bank draw. All completed DEVthrough260 published/immutable. OFF1v230 remains invalid/preserved/published/owner failure delivered once. No new owner fix/decision in state/protocol; source hold remains, no further affected OFF1games or retries.

Fullwatch2026-10-19T03:52:42Z: learner update274/v271 at2026-10-19T03:48:04Z, KL0.05604007914662361,deploy34.98760330578512,plays39.50413223140496,score0.7148760330578512,EV0.954349935054779; backlog136<960/noSTOP/alerts/newworkerfailure. Loads01/08/04=46.61/8.81/8.35, MemGiB34.394/58.782/101.309,noWho. Production01=48..51W8=32,08only55W8=8,04zero(retired52/53/54). Existing guards/syncs remain; no newactor/guard/source/cohort/learner restart/flag.08floor20GiB met. Capacity/throughput observational/confounded,no causalclaim or blindrefill.

## G-S DEV screen v270 (source8f; selection only) (2026-10-19T04:23:05Z)

Snapshot270 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `d90748e67bebdad10ca7f5f151308aeb9832c089839a1ddb23e9f8101df13dfc`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v270 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v270 − search [95% CI] | v270 − v2 [95% CI] | v270/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.696429 [+0.571429, +0.803571] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.035714 [-0.196429, +0.125000] | +0.357143 [+0.214286, +0.500000] | 45.553571/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.800000 [+0.700000, +0.900000] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.083333 [-0.033333, +0.200000] | +0.250000 [+0.116667, +0.383333] | 45.750000/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.900000 [+0.816667, +0.966667] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.100000 [-0.016667, +0.216667] | +0.200000 [+0.083333, +0.333333] | 45.833333/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v270 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| SEARCH | bait | 5 | +0.000000 [-0.600000, +0.600000] | +0.600000 [+0.200000, +1.000000] |
| SEARCH | giant | 9 | +0.111111 [+0.000000, +0.333333] | +0.333333 [+0.000000, +0.666667] |
| SEARCH | hog | 8 | +0.125000 [-0.250000, +0.500000] | +0.250000 [-0.250000, +0.750000] |
| SEARCH | other | 23 | -0.130435 [-0.391304, +0.130435] | +0.478261 [+0.260870, +0.695652] |
| SEARCH | siege | 7 | +0.000000 [-0.571429, +0.571429] | +0.142857 [+0.000000, +0.428571] |
| LIVE-K4CW-r16-fp | air | 9 | +0.111111 [+0.000000, +0.333333] | +0.111111 [-0.222222, +0.444444] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [-1.000000, +1.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.133333 [-0.200000, +0.466667] | +0.333333 [+0.066667, +0.600000] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.300000 [+0.000000, +0.600000] | +0.400000 [+0.100000, +0.700000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.000000 [-0.214286, +0.214286] | +0.214286 [+0.000000, +0.428571] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | -0.125000 [-0.375000, +0.000000] | +0.125000 [-0.250000, +0.500000] |
| R3a | air | 11 | +0.181818 [+0.000000, +0.454545] | +0.181818 [+0.000000, +0.454545] |
| R3a | bait | 6 | +0.333333 [-0.333333, +0.833333] | +0.333333 [+0.000000, +0.666667] |
| R3a | giant | 14 | +0.071429 [+0.000000, +0.214286] | +0.071429 [-0.142857, +0.285714] |
| R3a | hog | 6 | -0.166667 [-0.500000, +0.000000] | +0.166667 [+0.000000, +0.500000] |
| R3a | other | 19 | +0.105263 [-0.105263, +0.315789] | +0.210526 [+0.000000, +0.421053] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v270-8f-readout.json` on08/04/01/local05, SHA `eafc8f851f73ce8e6d8f9efdbbe5ae4c3bf410d7317f9ea4c385a553792bd8e5`.

## ALL-16 two-row DEV screen v270 (selection only) (2026-10-19T04:23:28Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v270−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `d90748e67bebdad10ca7f5f151308aeb9832c089839a1ddb23e9f8101df13dfc`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.357143 | -0.035714 [-0.196429,+0.125000] | 45.553571/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.250000 | +0.083333 [-0.033333,+0.200000] | 45.750000/48.250000 | True |
| R3a | 60 | +0.200000 | +0.100000 [-0.016667,+0.216667] | 45.833333/46.100000 | True |

Equal two-row screen=0.225; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v270": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v270": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v270": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v270": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v270-all16-only-readout.json`, SHA `68f136ba3a124d22a67839d201a5474991b9b478d144ebf6d18c6863a10795d4`; underlying ALL-16 readout SHA `eafc8f851f73ce8e6d8f9efdbbe5ae4c3bf410d7317f9ea4c385a553792bd8e5`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## v280 ALL-16 DEV launched; v230 primary validation after completed rows (2026-10-19T05:24:37Z)

Snapshot280 was staged once01→04, frozen checkpoint SHA `d7db2a4953ec53c4daa626c49708c7933eb181745d4a6c236c1a4de82ff24928` verified on both hosts in copy step2026-10-19T05:22:58Z. Sole04 `gs-dev-v280-8f.receipt.json` PGID1773359 launched2026-10-19T05:23:02Z; runtime bank present,zero rows at05:23:36. One180-arm-rowALL16candidate/source8f/keep-going/sharedGS+two-rowGE/cachedv2-searchrefs/cpu_job10W8nice15/24GiBmemoryadmission outsideCPUlease/cap100noWho or70Who. Global01/04/08ALLreceipts+outputs preflight passed,no prior280job/data. NoSam/dd1/referencegames or retries. CompletedDEVthrough270 remain published and immutable. No actor,guard,sync,source,learnerrestart or flag change. OFF1 source hold remains after already-published/notified v230 invalidity; no retry or repeated notification.

Solev230primary inputs completed3150armrows withtwo8-zero finish records(ALL1602:25:00/ALLacct05:09:36). Runtime launcher initially exited before Python because required BOT_RL_BANK was omitted(PGID1771144),preserved receipt/log; helper-gs-v230-primary-launch-env-rejection.json records no validator/scoring/game execution. Corrected launcher supplied registered bank3262629447693008 and retained fresh receipt gs-v230-b3262629447693008-primary-readout-r2/PGID1775918 at05:23:28. Same preregistered helper59a06... executed once, no scoring retry or game rerun. Primary result is published separately immediately upon completion,without waiting for four descriptive tails. H2H16was95of400 at05:23:36; otherthree tails notstarted. No bank redraw/reuse/second confirm.

## G-S v230 bank 3262629447693008: registered primary result (2026-10-19T05:26:12Z)

G-S v230, bank3262629447693008: **FAIL**. Mechanical validation completed on 3,150 arm rows, two primary finished records with eight zero statuses each, exact cases/decks/levels/checkpoint and pinned dependencies. The primary result uses ALL-16 and ALL-acct only. Secondary H2H/STR and OFF1 are descriptive and do not change the primary decision.

RoyaleSim-playable scope: **49.0292926714% of corpus weight** (50.9707073286% excluded); registered 19-card exclusions. Source `8f5272934f456e930aa250bba45eaa9b3c259b71`, statistical protocol `4167a3c263e4e3d303b222d4008186d13c22af38`, checkpoint SHA `da7df3532ea8a948597a8d9aa2aab2786dfa6a4afde977e5083d027f9bd9c4dd`, corpus SHA `16ca9bfbc72b028ffdb44d4497db8464dff60f0560ce6eb098a48ee12f149b8e`. Bank was registered before games in `24238033c2ba313b6a00432d51cd450627f61132` at 2026-10-18T22:55:11Z. Paired bootstrap: 4,000 Random(0) draws, sorted indices100/3899.

Pooled primary SEARCH candidate − search: **+0.061584 [-0.005865, +0.126100]**. Validity True; SEARCH lower>0 False; both K4 point estimates≥0 False; both R3 point estimates≥−0.03 True; candidate plays sanity {"all16/LIVE-K4CW-r16-fp": true, "all16/R3a": true, "all16/SEARCH": true, "allacct/LIVE-K4CW-r16-fp": true, "allacct/R3a": true, "allacct/SEARCH": true}. Invalid cells: []. Invalid rows produce no gate pass/fail claim.

| Cell | Retained/input | Candidate score [95% CI] | Search score [95% CI] | v2 score [95% CI] | Candidate − search [95% CI] | Candidate − v2 [95% CI] | Candidate/search/v2 plays |
|---|---:|---|---|---|---|---|---|
| all16/SEARCH | 198/200 | +0.636364 [+0.570707, +0.702020] | +0.661616 [+0.595960, +0.722222] | +0.474747 [+0.404040, +0.545455] | -0.025253 [-0.111111, +0.055556] | +0.161616 [+0.075758, +0.247475] | 46.207071/44.292929/48.363636 |
| all16/LIVE-K4CW-r16-fp | 198/200 | +0.727273 [+0.666667, +0.787879] | +0.762626 [+0.702020, +0.818182] | +0.545455 [+0.479798, +0.616162] | -0.035354 [-0.116162, +0.045455] | +0.181818 [+0.106061, +0.257576] | 44.065657/42.939394/44.904040 |
| all16/R3a | 199/200 | +0.849246 [+0.798995, +0.899497] | +0.864322 [+0.814070, +0.909548] | +0.793970 [+0.738693, +0.849246] | -0.015075 [-0.075377, +0.045226] | +0.055276 [-0.005025, +0.115578] | 42.190955/40.271357/45.527638 |
| allacct/SEARCH | 143/150 | +0.496503 [+0.419580, +0.580420] | +0.314685 [+0.237762, +0.391608] | +0.279720 [+0.209790, +0.356643] | +0.181818 [+0.076923, +0.286713] | +0.216783 [+0.118881, +0.314685] | 48.209790/44.587413/46.678322 |
| allacct/LIVE-K4CW-r16-fp | 149/150 | +0.684564 [+0.610738, +0.758389] | +0.489933 [+0.409396, +0.570470] | +0.429530 [+0.348993, +0.510067] | +0.194631 [+0.093960, +0.288591] | +0.255034 [+0.154362, +0.355705] | 45.114094/47.268456/45.671141 |
| allacct/R3a | 147/150 | +0.768707 [+0.700680, +0.836735] | +0.646259 [+0.571429, +0.727891] | +0.557823 [+0.476190, +0.639456] | +0.122449 [+0.034014, +0.210884] | +0.210884 [+0.115646, +0.306122] | 46.557823/45.176871/47.013605 |

Every cell uses the union of unclean cases across all three arms, removed identically from every arm. Validity limits:10% SEARCH,5% K4/R3. All raw rows and errors are preserved, with no failed-case retry.

- all16/SEARCH: 2/200 drops; valid True; causes {"live errors": 2}; archetypes {"air": 1, "royalgiant": 1}. Retained-case pooled estimate; no archetype contains >50% of drops.
  - 0-0080 / royalgiant / Mirror,Elixir Collector,Bats,RoyalGiant,LittlePrince,AngryBarbarians,IceGolem,AxeMan: {"fast-v2": {"details": ["1: ValueError(\"'AngryBarbarians' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "fast-v230": {"details": ["1: ValueError(\"'AngryBarbarians' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "res-lb-RF-wintp": {"details": ["1: ValueError(\"'AngryBarbarians' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}}
  - 0-0117 / air / Princess,Balloon,Mirror,MiniSparkys,RoyalHogs,Archers,Wizard,BabyDragon: {"fast-v2": {"details": ["0: ValueError(\"'RoyalHogs' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "fast-v230": {"details": ["0: ValueError(\"'RoyalHogs' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "res-lb-RF-wintp": {"details": ["0: ValueError(\"'RoyalHogs' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}}
- all16/LIVE-K4CW-r16-fp: 2/200 drops; valid True; causes {"live errors": 2}; archetypes {"other": 1, "siege": 1}. Retained-case pooled estimate; no archetype contains >50% of drops.
  - 1-0027 / siege / Xbow,Bats,Prince,Elixir Collector,Witch,Pekka,Bowler,Wizard: {"fast-v2": {"details": ["0: ValueError(\"'Witch' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "fast-v230": {"details": ["0: ValueError(\"'Witch' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "res-lb-RF-wintp": {"details": ["0: ValueError(\"'Witch' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}}
  - 1-0033 / other / Tesla,Berserker,Rascals,Mirror,MinionHorde,Archers,LittlePrince,GiantSkeleton: {"fast-v2": {"details": ["0: ValueError(\"'MinionHorde' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "fast-v230": {"details": ["0: ValueError(\"'MinionHorde' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "res-lb-RF-wintp": {"details": ["0: ValueError(\"'MinionHorde' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}}
- all16/R3a: 1/200 drops; valid True; causes {"ValueError(\"'LittlePrince' is not in list\")": 1}; archetypes {"other": 1}. Retained-case pooled estimate; >50% of drops are other; consult the separate archetype paired estimate.
  - 2-0146 / other / Elixir Collector,FirespiritHut,Clone,Log,LittlePrince,Knight,SkeletonDragons,Poison: {"fast-v2": {"details": [], "problems": ["ValueError(\"'LittlePrince' is not in list\")"]}, "fast-v230": {"details": [], "problems": ["ValueError(\"'LittlePrince' is not in list\")"]}, "res-lb-RF-wintp": {"details": [], "problems": ["ValueError(\"'LittlePrince' is not in list\")"]}}
- allacct/SEARCH: 7/150 drops; valid True; causes {"live errors": 7}; archetypes {"giant": 1, "other": 4, "royalgiant": 1, "siege": 1}. Retained-case pooled estimate; >50% of drops are other; consult the separate archetype paired estimate.
  - 0-0012 / other / Elixir Collector,ElectroDragon,SpearGoblins,BombTower,Archers,RoyalDelivery,Wizard,Minions: {"fast-v2": {"details": ["1: ValueError(\"'Archers' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "fast-v230": {"details": ["1: ValueError(\"'Archers' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "res-lb-RF-wintp": {"details": ["1: ValueError(\"'Archers' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}}
  - 0-0024 / other / BossBandit,IceWizard,Mirror,RoyalDelivery,RoyalHogs,EliteArcher,Wizard,Rage: {"fast-v2": {"details": ["1: ValueError(\"'RoyalHogs' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "fast-v230": {"details": ["1: ValueError(\"'RoyalHogs' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "res-lb-RF-wintp": {"details": ["1: ValueError(\"'RoyalHogs' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}}
  - 0-0038 / other / IceSpirit,BattleRam,Elixir Collector,BarbLog,ElectroSpirit,InfernoTower,SpearGoblins,Prince: {"fast-v2": {"details": ["1: ValueError(\"'ElectroSpirit' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "fast-v230": {"details": ["1: ValueError(\"'ElectroSpirit' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "res-lb-RF-wintp": {"details": ["1: ValueError(\"'ElectroSpirit' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}}
  - 0-0039 / siege / Fireball,Elixir Collector,ElectroDragon,Lightning,Xbow,Wallbreakers,BarbarianHut,MegaMinion: {"fast-v2": {"details": ["0: ValueError(\"'Xbow' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "fast-v230": {"details": ["0: ValueError(\"'Xbow' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "res-lb-RF-wintp": {"details": ["0: ValueError(\"'Xbow' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}}
  - 0-0064 / royalgiant / Mirror,Ghost,HogRider,Bomber,Barbarians,RoyalGiant,Heal,ArcherQueen: {"fast-v2": {"details": ["1: ValueError(\"'Barbarians' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "fast-v230": {"details": ["1: ValueError(\"'Barbarians' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "res-lb-RF-wintp": {"details": ["1: ValueError(\"'Barbarians' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}}
  - 0-0132 / other / Elixir Collector,Monk,MegaMinion,FireSpirits,Musketeer,Assassin,Skeletons,DartBarrell: {"fast-v2": {"details": ["1: ValueError(\"'Musketeer' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "fast-v230": {"details": ["1: ValueError(\"'Musketeer' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "res-lb-RF-wintp": {"details": ["1: ValueError(\"'Musketeer' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}}
  - 0-0148 / giant / Elixir Collector,Bats,Witch,Berserker,AngryBarbarians,Golem,BarbLog,Vines: {"fast-v2": {"details": ["1: ValueError(\"'AngryBarbarians' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "fast-v230": {"details": ["1: ValueError(\"'AngryBarbarians' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "res-lb-RF-wintp": {"details": ["1: ValueError(\"'AngryBarbarians' is not in list\")", "1: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}}
- allacct/LIVE-K4CW-r16-fp: 1/150 drops; valid True; causes {"live errors": 1}; archetypes {"giant": 1}. Retained-case pooled estimate; >50% of drops are giant; consult the separate archetype paired estimate.
  - 1-0089 / giant / Tornado,Elixir Collector,Berserker,BarbLog,AngryBarbarians,SkeletonDragons,ElectroDragon,Golem: {"fast-v2": {"details": ["0: ValueError(\"'AngryBarbarians' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "fast-v230": {"details": ["0: ValueError(\"'AngryBarbarians' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}, "res-lb-RF-wintp": {"details": ["0: ValueError(\"'AngryBarbarians' is not in list\")", "0: ValueError('public play inconsistent with ordinary cycle')"], "problems": ["live errors"]}}
- allacct/R3a: 3/150 drops; valid True; causes {"ValueError(\"'RoyalGiant' is not in list\")": 1, "ValueError(\"'Wallbreakers' is not in list\")": 1, "ValueError(\"'Xbow' is not in list\")": 1}; archetypes {"other": 1, "royalgiant": 1, "siege": 1}. Retained-case pooled estimate; no archetype contains >50% of drops.
  - 2-0060 / other / Mirror,ElectroSpirit,SkeletonArmy,Tornado,Wallbreakers,MightyMiner,Heal,Ronin: {"fast-v2": {"details": [], "problems": ["ValueError(\"'Wallbreakers' is not in list\")"]}, "fast-v230": {"details": [], "problems": ["ValueError(\"'Wallbreakers' is not in list\")"]}, "res-lb-RF-wintp": {"details": [], "problems": ["ValueError(\"'Wallbreakers' is not in list\")"]}}
  - 2-0066 / siege / Mirror,Earthquake,FirespiritHut,IceSpirit,Xbow,AxeMan,Ronin,BattleHealer: {"fast-v2": {"details": [], "problems": ["ValueError(\"'Xbow' is not in list\")"]}, "fast-v230": {"details": [], "problems": ["ValueError(\"'Xbow' is not in list\")"]}, "res-lb-RF-wintp": {"details": [], "problems": ["ValueError(\"'Xbow' is not in list\")"]}}
  - 2-0098 / royalgiant / DarkMagic,SkeletonKing,Elixir Collector,Knight,RoyalGiant,Mirror,Vines,FireSpirits: {"fast-v2": {"details": [], "problems": ["ValueError(\"'RoyalGiant' is not in list\")"]}, "fast-v230": {"details": [], "problems": ["ValueError(\"'RoyalGiant' is not in list\")"]}, "res-lb-RF-wintp": {"details": [], "problems": ["ValueError(\"'RoyalGiant' is not in list\")"]}}

| Cell | Contrast | Archetype | Paired estimate [95% CI] |
|---|---|---|---|
| all16/SEARCH | fast-v230 - res-lb-RF-wintp | air | +0.153846 [-0.115385, +0.384615] |
| all16/SEARCH | fast-v230 - res-lb-RF-wintp | bait | -0.142857 [-0.500000, +0.214286] |
| all16/SEARCH | fast-v230 - res-lb-RF-wintp | giant | -0.136364 [-0.295455, +0.022727] |
| all16/SEARCH | fast-v230 - res-lb-RF-wintp | hog | +0.040000 [-0.200000, +0.280000] |
| all16/SEARCH | fast-v230 - res-lb-RF-wintp | other | -0.033898 [-0.169492, +0.101695] |
| all16/SEARCH | fast-v230 - res-lb-RF-wintp | royalgiant | -0.142857 [-0.571429, +0.285714] |
| all16/SEARCH | fast-v230 - res-lb-RF-wintp | siege | +0.043478 [-0.173913, +0.260870] |
| all16/SEARCH | fast-v230 - fast-v2 | air | +0.346154 [+0.115385, +0.538462] |
| all16/SEARCH | fast-v230 - fast-v2 | bait | +0.428571 [+0.071429, +0.714286] |
| all16/SEARCH | fast-v230 - fast-v2 | giant | +0.022727 [-0.159091, +0.181818] |
| all16/SEARCH | fast-v230 - fast-v2 | hog | +0.160000 [-0.120000, +0.440000] |
| all16/SEARCH | fast-v230 - fast-v2 | other | +0.118644 [-0.033898, +0.271186] |
| all16/SEARCH | fast-v230 - fast-v2 | royalgiant | +0.285714 [+0.000000, +0.714286] |
| all16/SEARCH | fast-v230 - fast-v2 | siege | +0.130435 [-0.043478, +0.304348] |
| all16/SEARCH | fast-v2 - res-lb-RF-wintp | air | -0.192308 [-0.423077, +0.038462] |
| all16/SEARCH | fast-v2 - res-lb-RF-wintp | bait | -0.571429 [-0.785714, -0.285714] |
| all16/SEARCH | fast-v2 - res-lb-RF-wintp | giant | -0.159091 [-0.363636, +0.045455] |
| all16/SEARCH | fast-v2 - res-lb-RF-wintp | hog | -0.120000 [-0.320000, +0.080000] |
| all16/SEARCH | fast-v2 - res-lb-RF-wintp | other | -0.152542 [-0.305085, -0.016949] |
| all16/SEARCH | fast-v2 - res-lb-RF-wintp | royalgiant | -0.428571 [-0.857143, -0.142857] |
| all16/SEARCH | fast-v2 - res-lb-RF-wintp | siege | -0.086957 [-0.260870, +0.086957] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | air | -0.142857 [-0.357143, +0.071429] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | bait | +0.000000 [-0.315789, +0.315789] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | giant | +0.000000 [-0.235294, +0.235294] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | hog | +0.000000 [-0.225806, +0.225806] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | other | -0.016667 [-0.133333, +0.100000] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | royalgiant | -0.125000 [-0.500000, +0.250000] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | siege | -0.055556 [-0.277778, +0.111111] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | air | +0.071429 [-0.071429, +0.214286] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | bait | +0.263158 [+0.000000, +0.526316] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | giant | +0.117647 [-0.088235, +0.323529] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | hog | +0.193548 [-0.032258, +0.419355] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | other | +0.200000 [+0.083333, +0.316667] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | royalgiant | +0.375000 [-0.250000, +0.875000] |
| all16/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | siege | +0.222222 [+0.055556, +0.444444] |
| all16/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | air | -0.214286 [-0.392857, -0.035714] |
| all16/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | bait | -0.263158 [-0.578947, +0.105263] |
| all16/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | giant | -0.117647 [-0.323529, +0.117647] |
| all16/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | hog | -0.193548 [-0.387097, +0.000000] |
| all16/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | other | -0.216667 [-0.350000, -0.083333] |
| all16/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | royalgiant | -0.500000 [-0.875000, -0.125000] |
| all16/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | siege | -0.277778 [-0.555556, -0.055556] |
| all16/R3a | fast-v230 - res-lb-RF-wintp | air | +0.043478 [-0.086957, +0.173913] |
| all16/R3a | fast-v230 - res-lb-RF-wintp | bait | -0.125000 [-0.312500, +0.000000] |
| all16/R3a | fast-v230 - res-lb-RF-wintp | giant | -0.022727 [-0.181818, +0.136364] |
| all16/R3a | fast-v230 - res-lb-RF-wintp | hog | +0.033333 [-0.133333, +0.200000] |
| all16/R3a | fast-v230 - res-lb-RF-wintp | other | -0.035088 [-0.122807, +0.052632] |
| all16/R3a | fast-v230 - res-lb-RF-wintp | royalgiant | +0.090909 [+0.000000, +0.272727] |
| all16/R3a | fast-v230 - res-lb-RF-wintp | siege | -0.055556 [-0.277778, +0.111111] |
| all16/R3a | fast-v230 - fast-v2 | air | +0.130435 [-0.043478, +0.304348] |
| all16/R3a | fast-v230 - fast-v2 | bait | +0.062500 [-0.125000, +0.250000] |
| all16/R3a | fast-v230 - fast-v2 | giant | +0.022727 [-0.113636, +0.159091] |
| all16/R3a | fast-v230 - fast-v2 | hog | +0.066667 [-0.100000, +0.233333] |
| all16/R3a | fast-v230 - fast-v2 | other | +0.000000 [-0.105263, +0.105263] |
| all16/R3a | fast-v230 - fast-v2 | royalgiant | +0.363636 [+0.090909, +0.636364] |
| all16/R3a | fast-v230 - fast-v2 | siege | +0.000000 [-0.166667, +0.166667] |
| all16/R3a | fast-v2 - res-lb-RF-wintp | air | -0.086957 [-0.304348, +0.130435] |
| all16/R3a | fast-v2 - res-lb-RF-wintp | bait | -0.187500 [-0.375000, +0.000000] |
| all16/R3a | fast-v2 - res-lb-RF-wintp | giant | -0.045455 [-0.204545, +0.113636] |
| all16/R3a | fast-v2 - res-lb-RF-wintp | hog | -0.033333 [-0.233333, +0.166667] |
| all16/R3a | fast-v2 - res-lb-RF-wintp | other | -0.035088 [-0.157895, +0.087719] |
| all16/R3a | fast-v2 - res-lb-RF-wintp | royalgiant | -0.272727 [-0.545455, +0.000000] |
| all16/R3a | fast-v2 - res-lb-RF-wintp | siege | -0.055556 [-0.277778, +0.111111] |
| allacct/SEARCH | fast-v230 - res-lb-RF-wintp | air | +0.136364 [-0.136364, +0.409091] |
| allacct/SEARCH | fast-v230 - res-lb-RF-wintp | bait | +0.428571 [+0.214286, +0.714286] |
| allacct/SEARCH | fast-v230 - res-lb-RF-wintp | giant | -0.129032 [-0.354839, +0.096774] |
| allacct/SEARCH | fast-v230 - res-lb-RF-wintp | hog | +0.181818 [-0.090909, +0.454545] |
| allacct/SEARCH | fast-v230 - res-lb-RF-wintp | other | +0.300000 [+0.125000, +0.475000] |
| allacct/SEARCH | fast-v230 - res-lb-RF-wintp | royalgiant | +0.000000 [-1.000000, +1.000000] |
| allacct/SEARCH | fast-v230 - res-lb-RF-wintp | siege | +0.416667 [+0.166667, +0.666667] |
| allacct/SEARCH | fast-v230 - fast-v2 | air | +0.000000 [-0.272727, +0.272727] |
| allacct/SEARCH | fast-v230 - fast-v2 | bait | +0.285714 [+0.000000, +0.571429] |
| allacct/SEARCH | fast-v230 - fast-v2 | giant | +0.032258 [-0.161290, +0.225806] |
| allacct/SEARCH | fast-v230 - fast-v2 | hog | +0.363636 [+0.136364, +0.590909] |
| allacct/SEARCH | fast-v230 - fast-v2 | other | +0.325000 [+0.150000, +0.475000] |
| allacct/SEARCH | fast-v230 - fast-v2 | royalgiant | +0.500000 [+0.000000, +1.000000] |
| allacct/SEARCH | fast-v230 - fast-v2 | siege | +0.333333 [+0.083333, +0.583333] |
| allacct/SEARCH | fast-v2 - res-lb-RF-wintp | air | +0.136364 [-0.181818, +0.454545] |
| allacct/SEARCH | fast-v2 - res-lb-RF-wintp | bait | +0.142857 [-0.142857, +0.428571] |
| allacct/SEARCH | fast-v2 - res-lb-RF-wintp | giant | -0.161290 [-0.387097, +0.064516] |
| allacct/SEARCH | fast-v2 - res-lb-RF-wintp | hog | -0.181818 [-0.409091, +0.045455] |
| allacct/SEARCH | fast-v2 - res-lb-RF-wintp | other | -0.025000 [-0.175000, +0.150000] |
| allacct/SEARCH | fast-v2 - res-lb-RF-wintp | royalgiant | -0.500000 [-1.000000, +0.000000] |
| allacct/SEARCH | fast-v2 - res-lb-RF-wintp | siege | +0.083333 [-0.250000, +0.416667] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | air | +0.368421 [+0.052632, +0.631579] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | bait | +0.500000 [+0.166667, +0.833333] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | giant | +0.285714 [+0.107143, +0.464286] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | hog | +0.096774 [-0.096774, +0.290323] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | other | +0.187500 [+0.020833, +0.354167] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | royalgiant | -0.666667 [-1.000000, +0.000000] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - res-lb-RF-wintp | siege | +0.071429 [-0.214286, +0.357143] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | air | +0.421053 [+0.157895, +0.684211] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | bait | +0.000000 [-0.500000, +0.500000] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | giant | +0.535714 [+0.357143, +0.714286] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | hog | +0.129032 [-0.129032, +0.387097] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | other | +0.208333 [+0.020833, +0.395833] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | royalgiant | +0.000000 [+0.000000, +0.000000] |
| allacct/LIVE-K4CW-r16-fp | fast-v230 - fast-v2 | siege | +0.071429 [-0.142857, +0.285714] |
| allacct/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | air | -0.052632 [-0.368421, +0.263158] |
| allacct/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | bait | +0.500000 [+0.166667, +0.833333] |
| allacct/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | giant | -0.250000 [-0.500000, +0.035714] |
| allacct/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | hog | -0.032258 [-0.290323, +0.193548] |
| allacct/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | other | -0.020833 [-0.145833, +0.125000] |
| allacct/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | royalgiant | -0.666667 [-1.000000, +0.000000] |
| allacct/LIVE-K4CW-r16-fp | fast-v2 - res-lb-RF-wintp | siege | +0.000000 [-0.357143, +0.285714] |
| allacct/R3a | fast-v230 - res-lb-RF-wintp | air | +0.263158 [+0.000000, +0.526316] |
| allacct/R3a | fast-v230 - res-lb-RF-wintp | bait | +0.181818 [+0.000000, +0.454545] |
| allacct/R3a | fast-v230 - res-lb-RF-wintp | giant | +0.275000 [+0.125000, +0.425000] |
| allacct/R3a | fast-v230 - res-lb-RF-wintp | hog | +0.173913 [-0.086957, +0.478261] |
| allacct/R3a | fast-v230 - res-lb-RF-wintp | other | -0.069767 [-0.232558, +0.069767] |
| allacct/R3a | fast-v230 - res-lb-RF-wintp | royalgiant | +0.000000 [+0.000000, +0.000000] |
| allacct/R3a | fast-v230 - res-lb-RF-wintp | siege | -0.100000 [-0.300000, +0.000000] |
| allacct/R3a | fast-v230 - fast-v2 | air | +0.210526 [+0.000000, +0.421053] |
| allacct/R3a | fast-v230 - fast-v2 | bait | +0.363636 [+0.000000, +0.727273] |
| allacct/R3a | fast-v230 - fast-v2 | giant | +0.375000 [+0.200000, +0.550000] |
| allacct/R3a | fast-v230 - fast-v2 | hog | +0.173913 [+0.000000, +0.391304] |
| allacct/R3a | fast-v230 - fast-v2 | other | +0.093023 [-0.069767, +0.255814] |
| allacct/R3a | fast-v230 - fast-v2 | royalgiant | -1.000000 [-1.000000, -1.000000] |
| allacct/R3a | fast-v230 - fast-v2 | siege | +0.100000 [-0.200000, +0.400000] |
| allacct/R3a | fast-v2 - res-lb-RF-wintp | air | +0.052632 [-0.210526, +0.315789] |
| allacct/R3a | fast-v2 - res-lb-RF-wintp | bait | -0.181818 [-0.636364, +0.272727] |
| allacct/R3a | fast-v2 - res-lb-RF-wintp | giant | -0.100000 [-0.300000, +0.100000] |
| allacct/R3a | fast-v2 - res-lb-RF-wintp | hog | +0.000000 [-0.217391, +0.217391] |
| allacct/R3a | fast-v2 - res-lb-RF-wintp | other | -0.162791 [-0.325581, +0.000000] |
| allacct/R3a | fast-v2 - res-lb-RF-wintp | royalgiant | +1.000000 [+1.000000, +1.000000] |
| allacct/R3a | fast-v2 - res-lb-RF-wintp | siege | -0.200000 [-0.600000, +0.200000] |

Pooled SEARCH interpretation: Retained-case pooled estimate; no archetype contains >50% of drops.
- Pooled SEARCH air: +0.145833 [-0.041667, +0.333333].
- Pooled SEARCH bait: +0.142857 [-0.107143, +0.357143].
- Pooled SEARCH giant: -0.133333 [-0.266667, +0.000000].
- Pooled SEARCH hog: +0.106383 [-0.085106, +0.276596].
- Pooled SEARCH other: +0.101010 [-0.010101, +0.202020].
- Pooled SEARCH royalgiant: -0.111111 [-0.555556, +0.333333].
- Pooled SEARCH siege: +0.171429 [+0.000000, +0.371429].

Full readout `JOB/helper-gs-v230-b3262629447693008-primary-readout.json`, SHA `c4777c29ede7fa856f142d5c390705b13c77b05d098e9cd2a348aac4d66b1236`. Primary readout completed 2026-10-19T05:25:36Z; raw case/row manifests, per-arm rejection counts and all recorded errors remain in the full artifact. Secondary and OFF1 progress at this readout is descriptive only; their eventual readouts are published separately.

## G-S DEV screen v280 (source8f; selection only) (2026-10-19T05:53:04Z)

Snapshot280 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `d7db2a4953ec53c4daa626c49708c7933eb181745d4a6c236c1a4de82ff24928`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v280 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v280 − search [95% CI] | v280 − v2 [95% CI] | v280/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.660714 [+0.535714, +0.785714] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.071429 [-0.250000, +0.107143] | +0.321429 [+0.178571, +0.464286] | 42.732143/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.816667 [+0.716667, +0.916667] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.100000 [-0.033333, +0.233333] | +0.266667 [+0.116667, +0.416667] | 46.933333/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.833333 [+0.733333, +0.916667] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.033333 [-0.116667, +0.166667] | +0.133333 [+0.000000, +0.266667] | 44.150000/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v280 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-1.000000, +0.500000] | +0.000000 [-0.750000, +0.750000] |
| SEARCH | bait | 5 | -0.200000 [-0.600000, +0.000000] | +0.400000 [+0.000000, +0.800000] |
| SEARCH | giant | 9 | +0.000000 [-0.333333, +0.333333] | +0.222222 [+0.000000, +0.555556] |
| SEARCH | hog | 8 | +0.125000 [-0.500000, +0.750000] | +0.250000 [-0.250000, +0.625000] |
| SEARCH | other | 23 | -0.130435 [-0.391304, +0.130435] | +0.478261 [+0.260870, +0.695652] |
| SEARCH | siege | 7 | +0.000000 [-0.571429, +0.571429] | +0.142857 [-0.285714, +0.571429] |
| LIVE-K4CW-r16-fp | air | 9 | -0.111111 [-0.444444, +0.222222] | -0.111111 [-0.444444, +0.222222] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.333333 [+0.000000, +1.000000] | +0.666667 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.200000 [+0.000000, +0.400000] | +0.400000 [+0.133333, +0.666667] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.300000 [-0.100000, +0.700000] | +0.400000 [+0.100000, +0.700000] |
| LIVE-K4CW-r16-fp | other | 14 | -0.071429 [-0.285714, +0.142857] | +0.142857 [-0.214286, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.125000 [+0.000000, +0.375000] | +0.375000 [+0.125000, +0.750000] |
| R3a | air | 11 | +0.090909 [-0.181818, +0.363636] | +0.090909 [+0.000000, +0.272727] |
| R3a | bait | 6 | +0.166667 [-0.333333, +0.666667] | +0.166667 [-0.333333, +0.666667] |
| R3a | giant | 14 | +0.000000 [-0.285714, +0.285714] | +0.000000 [-0.214286, +0.214286] |
| R3a | hog | 6 | -0.500000 [-0.833333, -0.166667] | -0.166667 [-0.666667, +0.333333] |
| R3a | other | 19 | +0.210526 [+0.000000, +0.421053] | +0.315789 [+0.105263, +0.526316] |
| R3a | siege | 4 | -0.250000 [-0.750000, +0.000000] | +0.250000 [-0.500000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v280-8f-readout.json` on08/04/01/local05, SHA `8d14607782cbfcf1dc509563de69ebac0fb2720697d15045337f7b79bfe0d240`.

## ALL-16 two-row DEV screen v280 (selection only) (2026-10-19T05:53:38Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v280−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `d7db2a4953ec53c4daa626c49708c7933eb181745d4a6c236c1a4de82ff24928`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.321429 | -0.071429 [-0.250000,+0.107143] | 42.732143/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.266667 | +0.100000 [-0.033333,+0.233333] | 46.933333/48.250000 | True |
| R3a | 60 | +0.133333 | +0.033333 [-0.116667,+0.166667] | 44.150000/46.100000 | True |

Equal two-row screen=0.2; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v280": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v280": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v280": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v280": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v280-all16-only-readout.json`, SHA `64b9edd9a0268ed120c12d819354914404aaa82da76a6262e442821641f2e9a2`; underlying ALL-16 readout SHA `8d14607782cbfcf1dc509563de69ebac0fb2720697d15045337f7b79bfe0d240`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## Preemptive retirement of owned01 block48; learner continues (2026-10-19T06:55:34Z)

Owned01actor block48/W8/receiptPGID2774102 was retired preemptively at2026-10-19T06:53:47Z to restore room for the unchanged learner. Fresh MemAvailable fell from31,886,331,904bytes at06:23:54 to26,185,289,728bytes at06:52:51; pre-signal26068332544bytes, worker RSS median3274321920.0bytes/max3602448384bytes. Exact own receipt, source8f launch and all10group members/8worker descendants were checked before TERM+CONT. Group gone verified; no unowned process was signalled. MemAvailable after49828794368bytes; follow-up49864138752bytes at2026-10-19T06:54:56Z.

All8closed games-b48 worker logs retain identical SHA256/size/mtime after retirement. Existing atomic completed NPZ files remain in the canonical01queue for the active learner;18block48files were present immediately after retirement. No delete/redraw/retry/source change. Complete receipt/process/RSS/memory/signal/closed-log evidence is in `JOB/helper-01-memory-retire-b48.json` on01/04/local05. Expected retirement is not a worker crash or unrecoverable-loss incident.

Production now01ONLY49..51W8=24 plus08ONLY55W8=8,32workers total;04zero. Block48isSPENT/neverrevive or reuse,alongside04retired52/53/54 and08retired56..59. Existing01guard2773583 retains48history/deadignored and49..51coverage; existing08memory/error guards and04/08syncs stay. The hourly error guard retains historical48offsets/windows/anchor. No new block,guard,errorcohort,source,learner restart or flags. Anyfuture>=60capacity still requires globalreceipts/BLOCKSpreflight and admitted load/memory/errorcoverage before games. No blind refill or causal throughput claim.

Learner-r201PGID2061155/source095 continues unchanged. Pre-retirement fullwatch2026-10-19T06:53:17Z:update291/v288,KL0.06661569259953327,deploy37.30578512396694,plays41.90909090909091,score0.6942148760330579,EV0.9471723437309265,backlog209<960,noSTOP/collapse/newworkerfailure. These readings precede retirement and do not estimate its performance effect. NoDEVongoing/ALLthrough280published immutable;290snapshotabsent06:52:26. v230primaryVALIDFAILalreadyreported once/neverrerun; sole wrapper4004319continues descriptive tails only. OFF1invalidity/sourcehold remains with no new owner fix/decision or repeated notification.

## v290 ALL-16 DEV launched; v230 STR descriptive tails continue (2026-10-19T07:24:08Z)

At2026-10-19T07:24:05Z,snapshot290 was staged once01→04. Frozen checkpoint SHA `8374a61e4493e0e29df464308eca651ca22bedcbeb60718b450e70e398c9d0db` was verified on both hosts in copy step2026-10-19T07:23:05Z. Sole04 `gs-dev-v290-8f.receipt.json` PGID2380163 launched2026-10-19T07:23:08Z and entered normal admission/runtime: bank present,zero rows at2026-10-19T07:23:24Z. One180-arm-rowALL16candidate/source8f/keep-going/sharedGS+two-rowGE/cachedv2-searchrefs/cpu_job10W8nice15/24GiBmemoryadmissionoutsideCPUlease/cap100noWho or70Who. Global01/04/08ALLreceipt/output preflight passed/no prior290job/data. NoSam,dd1,referencegames,retries or duplicate jobs. All completedDEVthrough280 remain published and immutable.

v230 primary3150VALIDFAIL,publicationc352c64ccc86e3f54f17831ca1802004c27a6cd2/owner already notified once,remains closed. Solewrapper4004319 continues four descriptive tails: H2H16400+8zero06:05:45,H2Hacct400+8zero07:00:22,STR16143/800 at2026-10-19T07:23:24Z,STRacct notstarted. Total2200+four8zero required before prepared secondary Runtimevalidator,no early analysis. S-CONFIRM1used/no secondconfirm or bankreuse. OFF1v230invalidity/sourcehold remains,preserved and owner already notified; no fix/decision in lateststate/prereg,no affected newOFF1game or repeatedping.

Fullwatch2026-10-19T07:23:23Z:learnerupdate294/v291 at2026-10-19T07:18:18Z,KL0.06736529854374315,deploy33.3125,plays37.75416666666667,score0.6958333333333333,EV0.9556105136871338,backlog121<960/noSTOP/alerts/newworkerfailure. Loads01/08/04=45.84/8.71/8.42,MemGiB41.986/42.868/113.550,noWho. Production01ONLY49..51W8=24+08ONLY55W8=8=32total/04zero;01retired48/04retired52..54/08retired56..59staygone/spent/no revival. Existingguards/errorhistory/syncs/source8f/learner095/flagsunchanged. No actor,guard,cohort,source,sync,learnerrestart or flag change. No blindcapacityrefill or causalthroughputclaim. Fresh01audit confirms48gone,remaining3blocks8workers each;08floor20GiB met. Natural08drain07:22:51PASS0NPZbeforeafter/all256SHA01match/stablesource,no hold created this check.

## G-S DEV screen v290 (source8f; selection only) (2026-10-19T07:56:49Z)

Snapshot290 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `8374a61e4493e0e29df464308eca651ca22bedcbeb60718b450e70e398c9d0db`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v290 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v290 − search [95% CI] | v290 − v2 [95% CI] | v290/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.678571 [+0.553571, +0.803571] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.053571 [-0.196429, +0.107143] | +0.339286 [+0.178571, +0.500000] | 43.357143/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.850000 [+0.750000, +0.933333] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.133333 [+0.000000, +0.266667] | +0.300000 [+0.150000, +0.433333] | 43.550000/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.883333 [+0.800000, +0.966667] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.083333 [-0.050000, +0.200000] | +0.183333 [+0.066667, +0.316667] | 43.483333/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v290 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | +0.250000 [+0.000000, +0.750000] | +0.500000 [+0.000000, +1.000000] |
| SEARCH | bait | 5 | +0.000000 [+0.000000, +0.000000] | +0.600000 [+0.200000, +1.000000] |
| SEARCH | giant | 9 | -0.222222 [-0.666667, +0.222222] | +0.000000 [-0.333333, +0.333333] |
| SEARCH | hog | 8 | +0.000000 [-0.375000, +0.375000] | +0.125000 [-0.375000, +0.625000] |
| SEARCH | other | 23 | -0.086957 [-0.347826, +0.173913] | +0.521739 [+0.304348, +0.739130] |
| SEARCH | siege | 7 | +0.000000 [-0.571429, +0.571429] | +0.142857 [-0.428571, +0.714286] |
| LIVE-K4CW-r16-fp | air | 9 | +0.222222 [-0.222222, +0.666667] | +0.222222 [-0.222222, +0.666667] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.000000 [-1.000000, +1.000000] | +0.333333 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.133333 [-0.133333, +0.400000] | +0.333333 [+0.000000, +0.600000] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.400000 [+0.100000, +0.700000] | +0.500000 [+0.200000, +0.800000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.071429 [-0.142857, +0.285714] | +0.285714 [+0.071429, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | -0.125000 [-0.375000, +0.000000] | +0.125000 [-0.250000, +0.500000] |
| R3a | air | 11 | +0.000000 [-0.272727, +0.272727] | +0.000000 [-0.363636, +0.363636] |
| R3a | bait | 6 | +0.166667 [-0.666667, +0.833333] | +0.166667 [+0.000000, +0.500000] |
| R3a | giant | 14 | +0.142857 [+0.000000, +0.357143] | +0.142857 [+0.000000, +0.357143] |
| R3a | hog | 6 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +0.666667] |
| R3a | other | 19 | +0.157895 [-0.052632, +0.368421] | +0.263158 [+0.105263, +0.473684] |
| R3a | siege | 4 | -0.250000 [-0.750000, +0.000000] | +0.250000 [-0.500000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v290-8f-readout.json` on08/04/01/local05, SHA `6ddd307afab7d936e2df4a86266d1996d0cea68800ccb03eafc8ef1bdf17b1ae`.

## ALL-16 two-row DEV screen v290 (selection only) (2026-10-19T07:57:31Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v290−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `8374a61e4493e0e29df464308eca651ca22bedcbeb60718b450e70e398c9d0db`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.339286 | -0.053571 [-0.196429,+0.107143] | 43.357143/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.300000 | +0.133333 [+0.000000,+0.266667] | 43.550000/48.250000 | True |
| R3a | 60 | +0.183333 | +0.083333 [-0.050000,+0.200000] | 43.483333/46.100000 | True |

Equal two-row screen=0.24166666666666664; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v290": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v290": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v290": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v290": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v290-all16-only-readout.json`, SHA `c247373b148cafbbd34e0d5115aefc27749b04204282f604eb9791b41ebb2837`; underlying ALL-16 readout SHA `6ddd307afab7d936e2df4a86266d1996d0cea68800ccb03eafc8ef1bdf17b1ae`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## v300 ALL-16 DEV launched; v230 final descriptive tail continues (2026-10-19T09:24:35Z)

At 2026-10-19T09:24:32Z, snapshot300 was staged once01→04. Frozen checkpoint SHA `fe1f8cf50f3159a8f7e67c9ed7d0ffc92be989cca02ff664f5aab863bfde78a1` was verified on both hosts in copy step 2026-10-19T09:23:05Z. Sole04 `gs-dev-v300-8f.receipt.json` PGID2982664 launched 2026-10-19T09:23:09Z and entered normal admission/runtime: bank present, 0/180 rows at 2026-10-19T09:23:30Z. One180-arm-rowALL16candidate/source8f/keep-going/sharedGS+two-rowGE/cachedv2-searchrefs/cpu_job10W8nice15/24GiBmemoryadmissionoutsideCPUlease/cap100noWho or70Who. Global01/04/08ALLreceipt/output preflight passed/no prior300job/data. No Sam, dd1, reference games, retries or duplicate jobs. All completed DEV through290 remain published and immutable.

v230 primary3150VALIDFAIL, publication c352c64ccc86e3f54f17831ca1802004c27a6cd2/owner already notified once, remains closed. Solewrapper4004319 continues the final descriptive account STR tail: 355/600 at 2026-10-19T09:23:30Z. H2H16 and H2Hacct each400+8zero; STR16 800+8zero at08:35:30. Total2200+four8zero required before prepared secondary Runtimevalidator, no early analysis. S-CONFIRM1used/no secondconfirm or bankreuse. OFF1v230invalidity/sourcehold remains preserved and owner already notified; no fix/decision in latest state/prereg, no affected newOFF1game or repeated ping.

Fullwatch 2026-10-19T09:23:43Z: learnerupdate304/v301 at 2026-10-19T09:15:08Z, KL0.08393487910393115, deploy35.06666666666667, plays39.1625, score0.725, EV0.9606746435165405, backlog200<960/noSTOP/alerts/newworkerfailure. Loads01/08/04=49.33/8.52/8.34, MemGiB35.452/33.266/108.717, noWho. Production01ONLY49..51W8=24+08ONLY55W8=8=32total/04zero;01retired48/04retired52..54/08retired56..59staygone/spent/no revival. Existing guards/errorhistory/syncs/source8f/learner095/flags unchanged. No actor,guard,cohort,source,sync,learnerrestart or flag change. No blind capacity refill or causal throughput claim. Fresh01audit confirms48gone, remaining3blocks8workers each;08floor20GiB met with 33.263GiB. Natural08drain 2026-10-19T09:23:01Z is INCOMPLETE only: NPZbefore3/after0, hash lags3, changing files0; pending synchronization is not loss. Prior stable PASS08:52:45 preserved. No hold created this check; current08memory below44GiBboundedholdhelperheadroom, so no forced pause for proof. Sync stays.

## G-S DEV screen v300 (source8f; selection only) (2026-10-19T09:54:22Z)

Snapshot300 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `fe1f8cf50f3159a8f7e67c9ed7d0ffc92be989cca02ff664f5aab863bfde78a1`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v300 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v300 − search [95% CI] | v300 − v2 [95% CI] | v300/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.660714 [+0.535714, +0.785714] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.071429 [-0.232143, +0.071429] | +0.321429 [+0.142857, +0.500000] | 46.714286/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.800000 [+0.700000, +0.900000] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.083333 [-0.050000, +0.216667] | +0.250000 [+0.100000, +0.400000] | 41.366667/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.900000 [+0.816667, +0.966667] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.100000 [-0.016667, +0.216667] | +0.200000 [+0.083333, +0.333333] | 42.050000/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v300 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | +0.250000 [+0.000000, +0.750000] | +0.500000 [+0.000000, +1.000000] |
| SEARCH | bait | 5 | -0.400000 [-0.800000, +0.000000] | +0.200000 [-0.400000, +0.800000] |
| SEARCH | giant | 9 | -0.222222 [-0.666667, +0.222222] | +0.000000 [-0.444444, +0.444444] |
| SEARCH | hog | 8 | +0.125000 [-0.250000, +0.500000] | +0.250000 [-0.250000, +0.750000] |
| SEARCH | other | 23 | -0.043478 [-0.217391, +0.130435] | +0.565217 [+0.347826, +0.782609] |
| SEARCH | siege | 7 | -0.142857 [-0.571429, +0.285714] | +0.000000 [-0.571429, +0.571429] |
| LIVE-K4CW-r16-fp | air | 9 | -0.222222 [-0.666667, +0.222222] | -0.222222 [-0.666667, +0.222222] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.333333 [+0.000000, +1.000000] | +0.666667 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.133333 [-0.133333, +0.400000] | +0.333333 [+0.133333, +0.600000] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.200000 [-0.200000, +0.600000] | +0.300000 [-0.100000, +0.700000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.071429 [-0.142857, +0.285714] | +0.285714 [+0.071429, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.125000 [+0.000000, +0.375000] | +0.375000 [+0.125000, +0.750000] |
| R3a | air | 11 | +0.090909 [-0.181818, +0.363636] | +0.090909 [+0.000000, +0.272727] |
| R3a | bait | 6 | +0.333333 [-0.333333, +0.833333] | +0.333333 [+0.000000, +0.666667] |
| R3a | giant | 14 | +0.071429 [-0.142857, +0.285714] | +0.071429 [+0.000000, +0.214286] |
| R3a | hog | 6 | +0.000000 [+0.000000, +0.000000] | +0.333333 [+0.000000, +0.666667] |
| R3a | other | 19 | +0.105263 [+0.000000, +0.263158] | +0.210526 [-0.052632, +0.473684] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v300-8f-readout.json` on08/04/01/local05, SHA `08e5f785078e317ae3ca1ac421f56da2061aefb87146b0e35332f5e8670a6665`.

## G-S v230 bank 3262629447693008: descriptive secondary rows (2026-10-19T09:54:52Z)

G-S v230, bank3262629447693008: Amendment1 **secondary descriptive rows**, outside the primary pass rule. Mechanical validation completed on2,200 arm rows and four finished records with eight zero statuses each. These are Sam-deck H2H mirror rows and BattleLog STR rows; they do not establish performance across the full corpus or change the separately reported primary G-S decision.

Source `8f5272934f456e930aa250bba45eaa9b3c259b71`, checkpoint SHA `da7df3532ea8a948597a8d9aa2aab2786dfa6a4afde977e5083d027f9bd9c4dd`, statistical protocol `4167a3c263e4e3d303b222d4008186d13c22af38`. Original bank registration `24238033c2ba313b6a00432d51cd450627f61132` at 2026-10-18T22:55:11Z. Paired bootstrap:4,000 Random(0) draws, sorted100/3899. All rows valid:False; invalid rows:["str16/LIVE-K4CW-r16-fp", "str16/R3a"]. Invalid cells retain their raw data and have no strength/pass/fail claim.

| Cell | Retained/input | Arm | Score [95% CI] | Plays/game | Paired contrast [95% CI] |
|---|---:|---|---|---:|---|
| h2h16/SEARCH | 200/200 | fast-v230 | +0.550000 [+0.480000, +0.620000] | 47.885000 | fast-v230 - fast-v2: +0.180000 [+0.090000, +0.270000] |
| h2h16/SEARCH | 200/200 | fast-v2 | +0.370000 [+0.305000, +0.440000] | 46.475000 | fast-v230 - fast-v2: +0.180000 [+0.090000, +0.270000] |
| h2hacct/SEARCH | 200/200 | fast-v230 | +0.660000 [+0.590000, +0.725000] | 46.975000 | fast-v230 - fast-v2: +0.295000 [+0.200000, +0.390000] |
| h2hacct/SEARCH | 200/200 | fast-v2 | +0.365000 [+0.300000, +0.435000] | 47.555000 | fast-v230 - fast-v2: +0.295000 [+0.200000, +0.390000] |
| str16/LIVE-K4CW-r16-fp | 151/200 | fast-v230 | +0.715232 [+0.642384, +0.781457] | 46.311258 | fast-v230 - res-lb-RF-wintp: -0.019868 [-0.119205, +0.079470] |
| str16/LIVE-K4CW-r16-fp | 151/200 | res-lb-RF-wintp | +0.735099 [+0.668874, +0.801325] | 44.139073 | fast-v230 - res-lb-RF-wintp: -0.019868 [-0.119205, +0.079470] |
| str16/R3a | 154/200 | fast-v230 | +0.863636 [+0.805195, +0.915584] | 43.811688 | fast-v230 - res-lb-RF-wintp: +0.058442 [-0.019481, +0.136364] |
| str16/R3a | 154/200 | res-lb-RF-wintp | +0.805195 [+0.740260, +0.863636] | 43.493506 | fast-v230 - res-lb-RF-wintp: +0.058442 [-0.019481, +0.136364] |
| stracct/LIVE-K4CW-r16-fp | 150/150 | fast-v230 | +0.520000 [+0.440000, +0.600000] | 46.193333 | fast-v230 - res-lb-RF-wintp: +0.073333 [-0.026667, +0.173333] |
| stracct/LIVE-K4CW-r16-fp | 150/150 | res-lb-RF-wintp | +0.446667 [+0.366667, +0.526667] | 44.553333 | fast-v230 - res-lb-RF-wintp: +0.073333 [-0.026667, +0.173333] |
| stracct/R3a | 150/150 | fast-v230 | +0.806667 [+0.740000, +0.866667] | 46.553333 | fast-v230 - res-lb-RF-wintp: +0.180000 [+0.086667, +0.273333] |
| stracct/R3a | 150/150 | res-lb-RF-wintp | +0.626667 [+0.546667, +0.706667] | 44.100000 | fast-v230 - res-lb-RF-wintp: +0.180000 [+0.086667, +0.273333] |

Pooled H2H descriptive scores/difference across the two mirror rows:

- fast-v230: +0.605000 [+0.557500, +0.650000].
- fast-v2: +0.367500 [+0.320000, +0.415000].
- difference: +0.237500 [+0.172500, +0.305000].

Unclean cases use a union across both paired arms and are removed identically. Limits10% SEARCH/5% K4/R3. All raw rows are retained; no failed game was retried.

- h2h16/SEARCH: 0/200 dropped; validTrue; archetypes{}. Retained-case pooled descriptive estimate; no archetype contains >50% of drops.
- h2hacct/SEARCH: 0/200 dropped; validTrue; archetypes{}. Retained-case pooled descriptive estimate; no archetype contains >50% of drops.
- str16/LIVE-K4CW-r16-fp: 49/200 dropped; validFalse; archetypes{"air": 5, "bait": 1, "giant": 36, "hog": 1, "other": 6}. Retained-case pooled descriptive estimate; >50% of drops in giant; consult separate archetype estimate.
  - 0-0002 / other / GoblinGang,Knight,GoblinHut,Archers,Tombstone,Fireball,Minions,Musketeer: {"res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 310}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 310}}}
  - 0-0003 / other / Knight,Musketeer,Archers,GoblinHut,Fireball,Tombstone,GoblinGang,Minions: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 228}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 228}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 50}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 50}}}
  - 0-0004 / giant / Giant,MiniPekka,Valkyrie,Archers,Bomber,GoblinHut,Minions,Goblins: {"res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 62}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 62}}}
  - 0-0015 / giant / Skeletons,Barbarians,Musketeer,GoblinHut,Arrows,Archers,Knight,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 564}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 564}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 580}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 580}}}
  - 0-0019 / giant / Fireball,Tombstone,Goblins,Skeletons,Giant,Bomber,MiniPekka,GoblinHut: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 258}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 258}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 466}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 466}}}
  - 0-0020 / giant / Fireball,Giant,Barbarians,GoblinHut,Musketeer,BattleRam,GoblinCage,Valkyrie: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 54}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 54}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 762}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 762}}}
  - 0-0021 / air / Knight,MiniPekka,Fireball,Giant,GoblinHut,BabyDragon,Minions,Goblins: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 236}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 236}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 332}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 332}}}
  - 0-0022 / giant / Knight,SpearGoblins,Giant,GoblinCage,Goblins,MiniPekka,GoblinHut,Fireball: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 258}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 258}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1524}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1524}}}
  - 0-0034 / giant / Goblins,GoblinCage,Giant,SpearGoblins,GoblinHut,Barbarians,MiniPekka,Valkyrie: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 488}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 488}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 186}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 186}}}
  - 0-0038 / air / Fireball,Giant,Minions,Knight,MiniPekka,GoblinBarrel,GoblinHut,BabyDragon: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1028}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1028}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 312}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 312}}}
  - 0-0041 / other / Tombstone,Skeletons,GoblinHut,SpearGoblins,Valkyrie,Bomber,Goblins,GoblinCage: {"res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 84}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 84}}}
  - 0-0047 / giant / Giant,Valkyrie,MiniPekka,Minions,Archers,Goblins,GoblinHut,Bomber: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 672}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 672}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 190}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 190}}}
  - 0-0052 / other / SpearGoblins,Tombstone,Skeletons,Goblins,Bomber,Valkyrie,GoblinHut,GoblinCage: {"res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 204}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 204}}}
  - 0-0053 / giant / Tombstone,MiniPekka,Knight,Bomber,GoblinCage,Valkyrie,GoblinHut,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 100}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 100}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 250}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 250}}}
  - 0-0054 / giant / GoblinHut,Bomber,Tombstone,SpearGoblins,Giant,Fireball,Minions,MiniPekka: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 396}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 396}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 918}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 918}}}
  - 0-0056 / giant / SpearGoblins,Fireball,MiniPekka,Goblins,Knight,GoblinHut,Giant,GoblinCage: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 498}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 498}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 490}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 490}}}
  - 0-0059 / giant / Barbarians,Giant,GoblinCage,GoblinHut,Musketeer,Fireball,Valkyrie,BattleRam: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 918}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 918}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 490}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 490}}}
  - 0-0062 / giant / Skeletons,SpearGoblins,Arrows,GoblinHut,Fireball,Tombstone,GoblinCage,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 276}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 276}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 438}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 438}}}
  - 0-0063 / giant / GoblinHut,Giant,MiniPekka,Goblins,Fireball,SpearGoblins,GoblinCage,Knight: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 596}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 596}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1166}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1166}}}
  - 0-0064 / giant / Minions,Giant,SpearGoblins,Tombstone,Fireball,GoblinHut,MiniPekka,Bomber: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 40}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 40}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 338}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 338}}}
  - 0-0067 / giant / Goblins,Arrows,GoblinHut,Tombstone,SpearGoblins,Fireball,GoblinCage,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 130}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 130}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 2512}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 2512}}}
  - 0-0070 / giant / Giant,Barbarians,MiniPekka,GoblinHut,Valkyrie,MegaMinion,Fireball,Bomber: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 408}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 408}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1442}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1442}}}
  - 0-0071 / bait / Knight,GoblinHut,Barbarians,SkeletonDragons,Goblins,Arrows,Valkyrie,GoblinBarrel: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 214}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 214}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 154}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 154}}}
  - 0-0083 / giant / Knight,Goblins,SpearGoblins,MiniPekka,GoblinHut,Fireball,GoblinCage,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 150}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 150}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 934}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 934}}}
  - 0-0092 / air / Goblins,Minions,MiniPekka,Fireball,Knight,BabyDragon,GoblinHut,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 130}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 130}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 694}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 694}}}
  - 0-0094 / other / GoblinHut,Minions,Fireball,GoblinGang,Knight,Tombstone,Archers,Musketeer: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 416}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 416}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 74}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 74}}}
  - 0-0096 / giant / MiniPekka,Valkyrie,GoblinHut,Tombstone,Fireball,GoblinCage,Musketeer,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 18}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 18}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 76}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 76}}}
  - 0-0102 / giant / GoblinHut,Bomber,Knight,Valkyrie,Fireball,Giant,Musketeer,Archers: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 262}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 262}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 238}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 238}}}
  - 0-0103 / giant / Bomber,Knight,Valkyrie,Fireball,Giant,GoblinHut,Musketeer,Archers: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 550}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 550}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 236}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 236}}}
  - 0-0110 / giant / MiniPekka,MegaMinion,Barbarians,Valkyrie,Fireball,Bomber,GoblinHut,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 118}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 118}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 376}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 376}}}
  - 0-0112 / air / GoblinBarrel,Giant,Fireball,GoblinHut,Knight,Minions,BabyDragon,MiniPekka: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 38}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 38}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 460}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 460}}}
  - 0-0113 / giant / Tombstone,GoblinHut,Giant,Fireball,Bomber,MiniPekka,SpearGoblins,Minions: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 8}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 8}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 12}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 12}}}
  - 0-0115 / giant / Fireball,Tombstone,Valkyrie,MiniPekka,GoblinHut,GoblinCage,Bomber,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 504}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 504}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 564}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 564}}}
  - 0-0119 / giant / Fireball,GoblinHut,MiniPekka,Tombstone,Bomber,Giant,Valkyrie,GoblinCage: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 144}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 144}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1450}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1450}}}
  - 0-0121 / giant / MiniPekka,Giant,Bomber,GoblinHut,Tombstone,SpearGoblins,Minions,Fireball: {"res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 292}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 292}}}
  - 0-0124 / giant / MegaMinion,Valkyrie,Giant,Fireball,Barbarians,MiniPekka,GoblinHut,Bomber: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 76}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 76}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 96}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 96}}}
  - 0-0129 / giant / GoblinHut,Fireball,GoblinCage,Giant,Tombstone,SpearGoblins,Arrows,Goblins: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 186}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 186}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1286}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1286}}}
  - 0-0131 / hog / ElectroSpirit,Valkyrie,Knight,GoblinHut,Pekka,HogRider,Arrows,Fireball: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 356}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 356}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 792}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 792}}}
  - 0-0133 / air / MiniPekka,Knight,BabyDragon,Fireball,Minions,GoblinBarrel,Giant,GoblinHut: {"res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 382}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 382}}}
  - 0-0145 / giant / Knight,Archers,GoblinHut,Musketeer,Arrows,Giant,Barbarians,Skeletons: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 354}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 354}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 504}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 504}}}
  - 0-0155 / giant / Giant,GoblinHut,SpearGoblins,Goblins,Fireball,Arrows,Tombstone,GoblinCage: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 542}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 542}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1218}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1218}}}
  - 0-0158 / giant / SpearGoblins,Goblins,GoblinHut,Giant,Fireball,GoblinCage,Arrows,Tombstone: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1568}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1568}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 306}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 306}}}
  - 0-0162 / giant / Valkyrie,MiniPekka,Tombstone,Fireball,Giant,Bomber,GoblinCage,GoblinHut: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 412}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 412}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 56}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 56}}}
  - 0-0173 / giant / Musketeer,GoblinHut,Archers,Bomber,Valkyrie,Giant,Knight,Fireball: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 662}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 662}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1168}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1168}}}
  - 0-0174 / giant / Barbarians,GoblinBarrel,Giant,Wizard,Rocket,Knight,Bomber,GoblinHut: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 182}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 182}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 420}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 420}}}
  - 0-0176 / other / Tombstone,Bomber,Valkyrie,GoblinCage,Goblins,Skeletons,GoblinHut,SpearGoblins: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 270}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 270}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 130}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 130}}}
  - 0-0177 / giant / Archers,Valkyrie,Musketeer,Giant,GoblinHut,Fireball,Knight,Bomber: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 172}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 172}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 234}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 234}}}
  - 0-0186 / giant / GoblinCage,SpearGoblins,Giant,GoblinHut,Tombstone,Fireball,Goblins,Arrows: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 712}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 712}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 474}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 474}}}
  - 0-0194 / giant / MegaMinion,Barbarians,Bomber,MiniPekka,Giant,GoblinHut,Fireball,Valkyrie: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 396}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 396}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 138}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 138}}}
- str16/R3a: 46/200 dropped; validFalse; archetypes{"air": 2, "bait": 2, "giant": 31, "hog": 3, "other": 8}. Retained-case pooled descriptive estimate; >50% of drops in giant; consult separate archetype estimate.
  - 1-0003 / giant / GoblinCage,Bomber,Giant,Tombstone,Knight,Valkyrie,GoblinHut,MiniPekka: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1410}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1410}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 846}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 846}}}
  - 1-0010 / other / Tombstone,Bomber,GoblinCage,Valkyrie,Skeletons,GoblinHut,SpearGoblins,Goblins: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 948}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 948}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1504}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1504}}}
  - 1-0013 / other / GoblinHut,Valkyrie,Bomber,GoblinCage,Tombstone,Skeletons,Goblins,SpearGoblins: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1040}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1040}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 424}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 424}}}
  - 1-0017 / giant / GoblinHut,Knight,Fireball,GoblinCage,Giant,MiniPekka,SpearGoblins,Goblins: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 474}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 474}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 310}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 310}}}
  - 1-0019 / other / Fireball,Arrows,Goblins,Minions,Archers,GoblinHut,SpearGoblins,Knight: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 236}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 236}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1088}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1088}}}
  - 1-0023 / giant / Barbarians,GoblinBarrel,Wizard,Bomber,GoblinHut,Rocket,Knight,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 464}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 464}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 570}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 570}}}
  - 1-0025 / air / BabyDragon,Minions,Knight,Giant,GoblinHut,Fireball,MiniPekka,Goblins: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 864}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 864}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 818}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 818}}}
  - 1-0026 / giant / Arrows,Giant,Goblins,GoblinHut,Fireball,GoblinCage,SpearGoblins,Tombstone: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 162}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 162}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1498}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1498}}}
  - 1-0028 / hog / HogRider,SpearGoblins,MegaMinion,Valkyrie,GoblinHut,MiniPekka,BombTower,Wizard: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 422}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 422}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 422}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 422}}}
  - 1-0029 / giant / Tombstone,Goblins,Giant,Arrows,Fireball,GoblinCage,SpearGoblins,GoblinHut: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 302}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 302}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1056}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1056}}}
  - 1-0033 / other / GoblinGang,GoblinHut,Musketeer,Archers,Fireball,Tombstone,Minions,Knight: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 166}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 166}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 686}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 686}}}
  - 1-0040 / giant / Wizard,Bomber,Barbarians,Knight,GoblinBarrel,Rocket,GoblinHut,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 286}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 286}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 678}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 678}}}
  - 1-0045 / bait / Barbarians,Valkyrie,Knight,Goblins,GoblinBarrel,Arrows,SkeletonDragons,GoblinHut: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 210}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 210}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1008}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1008}}}
  - 1-0048 / giant / SpearGoblins,GoblinHut,Goblins,Giant,Tombstone,GoblinCage,Fireball,Arrows: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 490}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 490}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 2094}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 2094}}}
  - 1-0053 / giant / Bomber,MiniPekka,GoblinHut,Valkyrie,Giant,Barbarians,Fireball,MegaMinion: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 816}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 816}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 854}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 854}}}
  - 1-0061 / giant / Wizard,Giant,GoblinBarrel,Bomber,Knight,GoblinHut,Rocket,Barbarians: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 222}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 222}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 244}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 244}}}
  - 1-0067 / giant / Knight,Goblins,Giant,MiniPekka,SpearGoblins,GoblinCage,GoblinHut,Fireball: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 760}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 760}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1124}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1124}}}
  - 1-0074 / other / GoblinHut,Arrows,Knight,Minions,SpearGoblins,Fireball,Archers,Goblins: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 164}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 164}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 492}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 492}}}
  - 1-0079 / giant / Bomber,Knight,Tombstone,GoblinHut,Giant,Valkyrie,MiniPekka,GoblinCage: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 112}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 112}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 444}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 444}}}
  - 1-0089 / giant / Goblins,GoblinHut,GoblinCage,Arrows,Fireball,Tombstone,SpearGoblins,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 400}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 400}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1422}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1422}}}
  - 1-0094 / giant / Arrows,Tombstone,GoblinCage,Fireball,Giant,GoblinHut,SpearGoblins,Skeletons: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1016}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1016}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 472}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 472}}}
  - 1-0095 / giant / Musketeer,GoblinHut,Valkyrie,Giant,Fireball,Knight,Archers,Bomber: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 662}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 662}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 304}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 304}}}
  - 1-0098 / giant / Bomber,Giant,GoblinHut,Valkyrie,Fireball,GoblinCage,MiniPekka,Tombstone: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 432}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 432}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 458}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 458}}}
  - 1-0102 / giant / Knight,Giant,Bomber,GoblinHut,Rocket,GoblinBarrel,Wizard,Barbarians: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1022}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1022}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 546}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 546}}}
  - 1-0103 / giant / Goblins,Arrows,Fireball,GoblinCage,SpearGoblins,Giant,Tombstone,GoblinHut: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 354}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 354}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 836}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 836}}}
  - 1-0106 / giant / Goblins,Valkyrie,MiniPekka,GoblinHut,SpearGoblins,Knight,Giant,GoblinCage: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 616}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 616}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 594}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 594}}}
  - 1-0107 / hog / Knight,Arrows,HogRider,GoblinHut,Fireball,ElectroSpirit,Valkyrie,Pekka: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 394}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 394}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1026}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1026}}}
  - 1-0108 / giant / Tombstone,GoblinHut,Fireball,Skeletons,MiniPekka,Bomber,Goblins,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 418}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 418}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 266}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 266}}}
  - 1-0110 / other / SpearGoblins,Skeletons,Goblins,GoblinHut,Valkyrie,Bomber,Tombstone,GoblinCage: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1648}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1648}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1236}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1236}}}
  - 1-0113 / giant / Skeletons,Knight,Giant,Musketeer,Arrows,Archers,GoblinHut,Barbarians: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 584}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 584}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 792}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 792}}}
  - 1-0115 / giant / GoblinHut,Goblins,MiniPekka,Archers,Giant,Valkyrie,Bomber,Minions: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 384}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 384}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1024}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1024}}}
  - 1-0137 / giant / Giant,Bomber,Goblins,Fireball,Skeletons,Tombstone,MiniPekka,GoblinHut: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 512}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 512}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 422}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 422}}}
  - 1-0140 / giant / MiniPekka,GoblinHut,Minions,Giant,SpearGoblins,Fireball,Tombstone,Bomber: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1404}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1404}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 352}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 352}}}
  - 1-0144 / other / Musketeer,GoblinGang,Fireball,Minions,Tombstone,Knight,GoblinHut,Archers: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 484}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 484}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 124}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 124}}}
  - 1-0150 / giant / Goblins,Archers,Bomber,Giant,GoblinHut,Minions,Valkyrie,MiniPekka: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 80}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 80}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 348}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 348}}}
  - 1-0151 / giant / Bomber,Archers,Knight,GoblinHut,Valkyrie,Musketeer,Giant,Fireball: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1302}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1302}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 404}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 404}}}
  - 1-0157 / other / Goblins,Knight,SpearGoblins,Fireball,GoblinHut,Archers,Minions,Arrows: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 146}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 146}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 636}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 636}}}
  - 1-0164 / air / Minions,GoblinHut,BabyDragon,Knight,Giant,MiniPekka,GoblinBarrel,Fireball: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 264}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 264}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 572}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 572}}}
  - 1-0168 / giant / GoblinHut,Valkyrie,BattleRam,Giant,Fireball,Musketeer,Barbarians,GoblinCage: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 344}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 344}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 812}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 812}}}
  - 1-0172 / giant / MegaMinion,Bomber,Fireball,MiniPekka,Barbarians,GoblinHut,Valkyrie,Giant: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 64}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 64}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 466}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 466}}}
  - 1-0177 / bait / SkeletonDragons,Knight,Arrows,Valkyrie,GoblinBarrel,GoblinHut,Goblins,Barbarians: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1096}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1096}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1556}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1556}}}
  - 1-0180 / giant / Fireball,Knight,Goblins,GoblinHut,Giant,GoblinCage,SpearGoblins,MiniPekka: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 296}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 296}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 766}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 766}}}
  - 1-0182 / giant / GoblinHut,Valkyrie,Bomber,MiniPekka,Fireball,Giant,Barbarians,MegaMinion: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 208}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 208}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1406}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1406}}}
  - 1-0183 / giant / Bomber,Knight,Valkyrie,Archers,GoblinHut,Giant,Musketeer,Fireball: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 488}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 488}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 1214}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 1214}}}
  - 1-0186 / giant / Fireball,Arrows,SpearGoblins,Tombstone,GoblinHut,GoblinCage,Giant,Goblins: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 808}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 808}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 298}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 298}}}
  - 1-0187 / hog / Valkyrie,HogRider,ElectroSpirit,Fireball,Knight,Pekka,GoblinHut,Arrows: {"fast-v230": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 264}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 264}}, "res-lb-RF-wintp": {"error": null, "live_errors": {"0": [], "1": []}, "problems": ["translator drops: {\"unmapped_unit:SpearGoblin_Dummy\": 732}"], "unmapped": {"unmapped_unit:SpearGoblin_Dummy": 732}}}
- stracct/LIVE-K4CW-r16-fp: 0/150 dropped; validTrue; archetypes{}. Retained-case pooled descriptive estimate; no archetype contains >50% of drops.
- stracct/R3a: 0/150 dropped; validTrue; archetypes{}. Retained-case pooled descriptive estimate; no archetype contains >50% of drops.

| Cell | Archetype | Paired contrast [95% CI] |
|---|---|---|
| h2h16/SEARCH | hog | +0.180000 [+0.090000, +0.270000] |
| h2hacct/SEARCH | hog | +0.295000 [+0.200000, +0.390000] |
| str16/LIVE-K4CW-r16-fp | air | +0.071429 [-0.214286, +0.357143] |
| str16/LIVE-K4CW-r16-fp | bait | unavailable |
| str16/LIVE-K4CW-r16-fp | giant | -0.071429 [-0.232143, +0.089286] |
| str16/LIVE-K4CW-r16-fp | hog | +0.086957 [-0.217391, +0.391304] |
| str16/LIVE-K4CW-r16-fp | other | -0.034483 [-0.189655, +0.120690] |
| str16/R3a | air | -0.090909 [-0.272727, +0.000000] |
| str16/R3a | bait | unavailable |
| str16/R3a | giant | +0.102041 [-0.040816, +0.244898] |
| str16/R3a | hog | +0.023256 [-0.116279, +0.162791] |
| str16/R3a | other | +0.078431 [-0.058824, +0.215686] |
| stracct/LIVE-K4CW-r16-fp | air | -0.055556 [-0.333333, +0.222222] |
| stracct/LIVE-K4CW-r16-fp | giant | +0.142857 [-0.107143, +0.392857] |
| stracct/LIVE-K4CW-r16-fp | hog | +0.093750 [-0.046875, +0.234375] |
| stracct/LIVE-K4CW-r16-fp | other | +0.050000 [-0.125000, +0.225000] |
| stracct/R3a | air | +0.352941 [+0.117647, +0.588235] |
| stracct/R3a | giant | +0.200000 [-0.050000, +0.450000] |
| stracct/R3a | hog | +0.246154 [+0.076923, +0.400000] |
| stracct/R3a | other | +0.020833 [-0.125000, +0.166667] |

Full readout `JOB/helper-gs-v230-b3262629447693008-secondary-readout.json`, SHA `a5ffd1a1a608606bf192f2bacf360ba3e7a29e54672e917cfaf6b46620c75cee`, completed 2026-10-19T09:54:30Z. Exact bank/case identities, row hashes/sizes/mtimes, model hashes, errors and rejection counts are retained in the artifact. This publication consumes no bank and makes no primary gate claim.

## ALL-16 two-row DEV screen v300 (selection only) (2026-10-19T09:55:16Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v300−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `fe1f8cf50f3159a8f7e67c9ed7d0ffc92be989cca02ff664f5aab863bfde78a1`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.321429 | -0.071429 [-0.232143,+0.071429] | 46.714286/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.250000 | +0.083333 [-0.050000,+0.216667] | 41.366667/48.250000 | True |
| R3a | 60 | +0.200000 | +0.100000 [-0.016667,+0.216667] | 42.050000/46.100000 | True |

Equal two-row screen=0.225; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v300": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v300": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v300": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v300": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v300-all16-only-readout.json`, SHA `e60ce7ce7e0e5213f9668ce68e8221b9a16514680f2bfb11b7018d814029ffc8`; underlying ALL-16 readout SHA `08e5f785078e317ae3ca1ac421f56da2061aefb87146b0e35332f5e8670a6665`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## v310 ALL-16 DEV launched; completed v230 results remain closed (2026-10-19T10:54:32Z)

At 2026-10-19T10:54:28Z, snapshot310 was staged once01→04. Frozen checkpoint SHA `ad3fcb9d484099679b99c417af20a0a5bebbd3a0bb255987b037f71fb4173333` was verified on both hosts in copy step 2026-10-19T10:53:08Z. Sole04 `gs-dev-v310-8f.receipt.json` PGID3424168 launched 2026-10-19T10:53:11Z and entered normal admission/runtime: bank present, 0/180 rows at 2026-10-19T10:53:16Z. One180-arm-rowALL16candidate/source8f/keep-going/sharedGS+two-rowGE/cachedv2-searchrefs/cpu_job10W8nice15/24GiBmemoryadmissionoutsideCPUlease/cap100noWho or70Who. Global01/04/08ALLreceipt/output preflight passed/no prior310job/data. No Sam, dd1, reference games, retries or duplicate jobs. All completed DEV through300 remain published and immutable.

v230 primary3150VALIDFAIL and descriptive secondary2200 completed, published and owner already notified once. Secondary ALL-16 STR K4/R3 cells are INVALID (49/200 and46/200 union drops exceed5%); no strength claim for invalid cells. All raw rows, drops, decks, causes and provenance preserved. S-CONFIRM1used/closed/no bankreuse; no new confirmation bank. OFF1v230invalidity/sourcehold remains preserved and owner already notified; no owner fix/decision in latest state/prereg, no affected newOFF1game or repeated ping. No prior readout, game or publisher rerun.

Fullwatch 2026-10-19T10:53:49Z: learnerupdate313/v310 at 2026-10-19T10:52:37Z, KL0.07311474285362397, deploy32.90833333333333, plays37.3, score0.7229166666666667, EV0.9561228156089783, backlog50<960/noSTOP/alerts/newworkerfailure. Loads01/08/04=49.71/8.58/0.74, MemGiB33.196/26.635/121.610, noWho. Production01ONLY49..51W8=24+08ONLY55W8=8=32total/04zero;01retired48/04retired52..54/08retired56..59staygone/spent/no revival. Existing guards/errorhistory/syncs/source8f/learner095/flags unchanged. No actor,guard,cohort,source,sync,learnerrestart or flag change. No blind capacity refill or causal throughput claim. Fresh01audit confirms48gone, remaining3blocks8workers each;08floor20GiB met with 26.634GiB; existing08guard owns24GiBretirementtrigger/28GiBresumemargin. Natural08drain 2026-10-19T10:53:06Z is INCOMPLETE only: NPZbefore2/after4, hash lags2, changing files2; pending synchronization is not loss. Last stable PASS retained separately. No hold created this check; current08memory below44GiBboundedholdhelperheadroom, so no forced pause for proof. Sync stays.

## G-S DEV screen v310 (source8f; selection only) (2026-10-19T11:24:05Z)

Snapshot310 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `ad3fcb9d484099679b99c417af20a0a5bebbd3a0bb255987b037f71fb4173333`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v310 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v310 − search [95% CI] | v310 − v2 [95% CI] | v310/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.607143 [+0.482143, +0.732143] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.125000 [-0.267857, +0.017857] | +0.267857 [+0.125000, +0.410714] | 44.482143/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.816667 [+0.716667, +0.916667] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.100000 [-0.033333, +0.250000] | +0.266667 [+0.116667, +0.400000] | 43.883333/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.900000 [+0.816667, +0.966667] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.100000 [-0.033333, +0.233333] | +0.200000 [+0.066667, +0.333333] | 42.916667/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v310 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| SEARCH | bait | 5 | -0.400000 [-0.800000, +0.000000] | +0.200000 [-0.400000, +0.800000] |
| SEARCH | giant | 9 | +0.000000 [-0.333333, +0.333333] | +0.222222 [+0.000000, +0.555556] |
| SEARCH | hog | 8 | -0.125000 [-0.500000, +0.250000] | +0.000000 [-0.375000, +0.375000] |
| SEARCH | other | 23 | -0.173913 [-0.391304, +0.043478] | +0.434783 [+0.217391, +0.652174] |
| SEARCH | siege | 7 | +0.142857 [-0.285714, +0.571429] | +0.285714 [-0.285714, +0.714286] |
| LIVE-K4CW-r16-fp | air | 9 | +0.000000 [-0.555556, +0.555556] | +0.000000 [-0.444444, +0.444444] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.333333 [+0.000000, +1.000000] | +0.666667 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.000000 [-0.333333, +0.333333] | +0.200000 [-0.066667, +0.466667] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.400000 [+0.100000, +0.700000] | +0.500000 [+0.200000, +0.800000] |
| LIVE-K4CW-r16-fp | other | 14 | +0.000000 [-0.214286, +0.214286] | +0.214286 [-0.071429, +0.500000] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.125000 [+0.000000, +0.375000] | +0.375000 [+0.125000, +0.750000] |
| R3a | air | 11 | +0.000000 [-0.363636, +0.363636] | +0.000000 [-0.272727, +0.272727] |
| R3a | bait | 6 | +0.500000 [+0.166667, +0.833333] | +0.500000 [+0.166667, +0.833333] |
| R3a | giant | 14 | +0.000000 [-0.214286, +0.214286] | +0.000000 [-0.285714, +0.285714] |
| R3a | hog | 6 | -0.166667 [-0.500000, +0.000000] | +0.166667 [+0.000000, +0.500000] |
| R3a | other | 19 | +0.263158 [+0.105263, +0.473684] | +0.368421 [+0.157895, +0.578947] |
| R3a | siege | 4 | -0.250000 [-0.750000, +0.000000] | +0.250000 [+0.000000, +0.750000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v310-8f-readout.json` on08/04/01/local05, SHA `70c2a9c7a7a72e20a26891059f910dfebc5f988c8dceb803bc36d44bb96a65c7`.

## ALL-16 two-row DEV screen v310 (selection only) (2026-10-19T11:24:50Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v310−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `ad3fcb9d484099679b99c417af20a0a5bebbd3a0bb255987b037f71fb4173333`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.267857 | -0.125000 [-0.267857,+0.017857] | 44.482143/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.266667 | +0.100000 [-0.033333,+0.250000] | 43.883333/48.250000 | True |
| R3a | 60 | +0.200000 | +0.100000 [-0.033333,+0.233333] | 42.916667/46.100000 | True |

Equal two-row screen=0.23333333333333334; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v310": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v310": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v310": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v310": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v310-all16-only-readout.json`, SHA `044504cb980ced38d39b329d37d07262faf736ae2c1227a8bc74b9a64ec1a370`; underlying ALL-16 readout SHA `70c2a9c7a7a72e20a26891059f910dfebc5f988c8dceb803bc36d44bb96a65c7`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.

## Existing08 memory guard retired final block55; learner continues (2026-10-19T11:55:25Z)

The existing08 memory guard PGID3011850 retired its last owned actor block55W8, receiptPGID1725903, at 2026-10-19T11:29:32Z. This was its registered whole-block24GiB preemption rule: MemAvailable 25766211584bytes before (<25769803776byte trigger, still ≥21474836480byte floor), 130593992704bytes after; fresh 130581659648bytes at 2026-10-19T11:53:43Z. The receipt group is verified gone. All55..59 are spent and will never be revived or reused. No manual signals, game/analysis/actor/guard/sync job, replacement, source change, learner restart or learner flag change was made by this check.

All eight closed block55 game logs have unchanged SHA/size/mtime across 2026-10-19T11:52:49Z and 2026-10-19T11:53:43Z. Natural drain PASS at 2026-10-19T11:53:05Z: zero completedNPZ before/after, stable08source, all256 log SHA256 values match01. No raw/log deletion or killed-case retry by this helper; existing sync drained completed files normally. Evidence `JOB/helper-08-memory-retire-b55.json` on08/04/01/local05 contains the guard event, receipts, group exit checks and all eight closed-log manifests; `helper-08-drain-verification.json` and `helper-08-drain-last-pass.json` retain full transfer proof. No unrecoverable loss or owner incident ping. Existing08 memoryguard3011850/errorguard2977910/fixedsync1225169 remain alive even with zero production actors. Hourly error cohort retains55..59history, offsets and anchor; no reset or replacement cohort.

Production now01ONLY49..51W8=24total,04zero,08zero. 01retired48 and04retired52..54 remain gone. WholeRL training remains active; learner-r2PGID2061155/source095, actor source8f, corpus and model pins unchanged. Fullwatch 2026-10-19T11:53:57Z: update317/v314 at 2026-10-19T11:52:04Z, KL0.08242915857931957, deploy35.24166666666667, plays39.43333333333333, score0.7708333333333334, EV0.9551469087600708, backlog18<960; no stop, new worker failure or alert. Loads01/08/04 50.5/0.31/0.64, MemGiB 29.355/121.605/121.600, noWho. Observations use a changed cohort and support no causal capacity/throughput claim or automatic refill. Completed GS/GE through310 and v230 primary/secondary publications remain immutable. OFF1 source hold remains pending owner decision; no retry or repeat notification. Same30minute watch stays enabled while wholeRL is active.

## 01 memory headroom: retire owned block49 without replacement (2026-10-19T14:24:23Z)

At 2026-10-19T14:23:32Z, helper intentionally retired its own 01 actor block 49 (8 workers, receipted PGID 2774215) to preserve learner memory headroom. Available memory fell from 32,460,283,904 bytes at 13:22:56Z to 27,298,463,744 at 13:55:17Z and 23,840,845,824 at 14:22:57Z; immediate pre-signal measurement was 23805820928 bytes. Only this owned group received TERM then CONT, and the group was verified gone. No new actor, guard, source, learner flag, or restart was introduced.

Available memory after retirement was 53638533120 bytes, with follow-up 53590200320 bytes at 2026-10-19T14:24:00Z. All eight closed block49 logs retained identical SHA256, size and mtime across verification. The 29 completed block49 NPZ files present after retirement remained in the canonical queue for normal learner consumption; no completed files were deleted. Learner, existing guard, and blocks50/51 remained alive. Production now consists of 16 workers on 01 only; 04 and 08 remain at zero. Block49 is spent and must never be revived or reused; no replacement or automatic refill is authorized. Existing guard membership and hourly error history, offsets and anchor remain unchanged; dead historical groups are ignored.

Artifact `helper-01-memory-retire-b49.json` is preserved on 01/04/local05. SHA256 `0f2510b37a42ebcfef4792e20e06be9907cd03a791ecffcca32a27cb7ae230f1`, measured 2026-10-19T14:24:20Z. This is an intentional resource retirement with preserved logs and completed queue, not an unexpected worker failure or irrecoverable loss. Primary v230 FAIL, secondary two STR16 invalid cells, OFF1 invalidity/source hold, completed DEV screens and learner configuration remain unchanged.

## ALL16 DEV v320 launch and resource watch (2026-10-19T14:54:36Z)

The sole v320 ALL16 DEV candidate screen launched on 04 at 2026-10-19T14:53:32Z (receipted PGID 386740). All-host root receipts and eval-output preflight at 14:53:15Z found no prior v320 job or data. Checkpoint policy-00320.pt was frozen from 01 to 04 at 2026-10-19T14:53:28Z; both SHA256 values matched `0460ea4ddb0dcd962638c81521fd36201dfaf7697749942aae5e756bc2e62b34` in that copy step. Checkpoint metadata is preserved on 01/04/local05; the remote receipt is evidence-only on 01. Runtime bank existed at 2026-10-19T14:54:05Z; progress was 0/180 rows with no finished receipt. The admitted job must not be moved or duplicated.

This is one 180-arm-row ALL16 candidate using unchanged source8f, fixed model/corpus pins, the registered DEV bank, SEARCH/K4CW-fp/R3a, and cached v2/search reference games. The same candidate data serves G-S selection and the amended two-row G-E screen. No Sam/dd1/reference games or confirmation bank is added. Normal admission uses 24 GiB available-memory headroom before taking a CPU lease, cpu_job10 with eight workers, nice15, cap100 without Who or70 with Who, PYTHONHASHSEED0 and NUMPY_MADVISE_HUGEPAGE0. Results require 180 rows plus eight zero exits before any fresh analysis, with all-host receipt/artifact deduplication. All completed screens through310 remain immutable; snapshot330 was absent at 14:52:56Z.

Full watch 2026-10-19T14:54:04Z: learner update 323/v320 completed 2026-10-19T14:51:48Z, KL 0.07483142789453268, deploy plays 35.62396694214876, plays 39.86363636363637, score 0.6859504132231405, EV 0.9534412622451782; backlog 17 below960 and no stop condition, new worker failure or shortfall. Production remains16 workers on01 blocks50/51 only; blocks48/49 and all04/08 production blocks stay retired. Existing guards, hourly error anchor/offsets and fixed syncs remain alive. No actor, guard, sync, source, learner restart/flags, replacement or capacity refill was introduced. Latest01 memory audit 2026-10-19T14:52:56Z: 50336911360 available bytes, eight workers each on50/51,48/49 gone; RSS includes shared pages and is not additive private memory. 08 natural drain passed at14:53:04Z with no queued NPZ, all256 log hashes matching01 and stable source; no irrecoverable loss. Primary230 FAIL, secondary invalid cells and OFF1 invalidity/source hold remain unchanged, with no repeated owner notifications.

Launch evidence measured 2026-10-19T14:54:32Z. Preflight artifact SHA256 `f6ddd1ddf92a942bda66361e1337cfb1fd57f767c451b9ccdf2cc919b50f63b1`.

## G-S DEV screen v320 (source8f; selection only) (2026-10-19T15:24:09Z)

Snapshot320 ALL-16 DEV analysis passed mechanical validation:180 candidate arm rows,8 zero finished statuses, exact cases and frozen checkpoint SHA `0460ea4ddb0dcd962638c81521fd36201dfaf7697749942aae5e756bc2e62b34`. The cached reference's360 files, byte hashes, sizes, mtimes, bank and finished records were rechecked. Every comparison uses the union of failures across candidate, fast-v2 and search; no case is retained for only one arm. Scope: **49.0292926714% of corpus weight is RoyaleSim-playable** (50.9707073286% excluded). Source8f/registered protocol4167.

| Opponent | Retained/input | Dropped | v320 score [95% CI] | Search score [95% CI] | v2 score [95% CI] | v320 − search [95% CI] | v320 − v2 [95% CI] | v320/search/v2 plays per game |
|---|---:|---:|---|---|---|---|---|---|
| SEARCH | 56/60 | 4 | +0.607143 [+0.482143, +0.732143] | +0.732143 [+0.607143, +0.839286] | +0.339286 [+0.214286, +0.464286] | -0.125000 [-0.285714, +0.035714] | +0.267857 [+0.089286, +0.446429] | 46.357143/41.821429/49.892857 |
| LIVE-K4CW-r16-fp | 60/60 | 0 | +0.783333 [+0.683333, +0.883333] | +0.716667 [+0.600000, +0.816667] | +0.550000 [+0.433333, +0.683333] | +0.066667 [-0.083333, +0.216667] | +0.233333 [+0.083333, +0.383333] | 44.016667/41.650000/48.250000 |
| R3a | 60/60 | 0 | +0.833333 [+0.733333, +0.916667] | +0.800000 [+0.700000, +0.900000] | +0.700000 [+0.583333, +0.816667] | +0.033333 [-0.083333, +0.150000] | +0.133333 [+0.000000, +0.266667] | 45.033333/39.966667/46.100000 |

All rows valid: True; candidate play-rate sanity by opponent: {"LIVE-K4CW-r16-fp": true, "R3a": true, "SEARCH": true}. Registered DEV SEARCH selection predicate (valid SEARCH row and v320 − search point estimate≥0): **False**. This is DEV selection only, never a gain or G-S confirm result. This DEV screen consumes no confirm bank; confirm usage is recorded separately. A separate completed G-B pass can also select a G-S candidate.

Dropped cases, with causes, opponent-deck archetypes and identical exclusions from every arm:

- SEARCH: 4/60 dropped (6.6667%), limit10%; causes {"live errors": 4}.
  - 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats.
  - 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog.
  - 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball.
  - 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon.
  - Drop-archetype counts {"air": 1, "giant": 1, "hog": 1, "royalgiant": 1}; Retained-case pooled estimate; no archetype contains more than half of drops.
- LIVE-K4CW-r16-fp: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.
- R3a: 0/60 dropped (0.0000%), limit5%; causes {}.
  - Drop-archetype counts {}; Retained-case pooled estimate; no archetype contains more than half of drops.

| Opponent | Archetype | Retained pairs | Candidate − search [95% CI] | Candidate − v2 [95% CI] |
|---|---|---:|---|---|
| SEARCH | air | 4 | -0.250000 [-0.750000, +0.000000] | +0.000000 [-0.750000, +0.750000] |
| SEARCH | bait | 5 | -0.400000 [-0.800000, +0.000000] | +0.200000 [-0.400000, +0.800000] |
| SEARCH | giant | 9 | -0.222222 [-0.666667, +0.222222] | +0.000000 [-0.555556, +0.555556] |
| SEARCH | hog | 8 | -0.125000 [-0.500000, +0.250000] | +0.000000 [-0.500000, +0.500000] |
| SEARCH | other | 23 | +0.000000 [-0.260870, +0.217391] | +0.608696 [+0.391304, +0.826087] |
| SEARCH | siege | 7 | -0.142857 [-0.571429, +0.285714] | +0.000000 [-0.428571, +0.428571] |
| LIVE-K4CW-r16-fp | air | 9 | +0.000000 [-0.555556, +0.555556] | +0.000000 [-0.444444, +0.444444] |
| LIVE-K4CW-r16-fp | bait | 3 | +0.333333 [+0.000000, +1.000000] | +0.666667 [+0.000000, +1.000000] |
| LIVE-K4CW-r16-fp | giant | 15 | +0.066667 [-0.200000, +0.333333] | +0.266667 [+0.000000, +0.533333] |
| LIVE-K4CW-r16-fp | hog | 10 | +0.300000 [-0.100000, +0.700000] | +0.400000 [+0.100000, +0.700000] |
| LIVE-K4CW-r16-fp | other | 14 | -0.142857 [-0.428571, +0.142857] | +0.071429 [-0.214286, +0.357143] |
| LIVE-K4CW-r16-fp | royalgiant | 1 | +0.000000 [+0.000000, +0.000000] | +0.000000 [+0.000000, +0.000000] |
| LIVE-K4CW-r16-fp | siege | 8 | +0.125000 [+0.000000, +0.375000] | +0.375000 [+0.125000, +0.750000] |
| R3a | air | 11 | +0.090909 [-0.181818, +0.363636] | +0.090909 [+0.000000, +0.272727] |
| R3a | bait | 6 | +0.000000 [-0.500000, +0.500000] | +0.000000 [-0.500000, +0.500000] |
| R3a | giant | 14 | +0.000000 [-0.214286, +0.214286] | +0.000000 [-0.285714, +0.285714] |
| R3a | hog | 6 | -0.166667 [-0.500000, +0.000000] | +0.166667 [+0.000000, +0.500000] |
| R3a | other | 19 | +0.105263 [-0.105263, +0.315789] | +0.210526 [-0.052632, +0.473684] |
| R3a | siege | 4 | +0.000000 [+0.000000, +0.000000] | +0.500000 [+0.000000, +1.000000] |

All raw rows and errors are retained. Standalone analysis ran on127x04 on completed validated raw inputs with matching pinned dependencies, through detachedcpu_job2/nice15. No games were rerun. Readout `JOB/helper-gs-dev-v320-8f-readout.json` on08/04/01/local05, SHA `196f7b34c7bea29c5c1d667bd989b754618dff70d37e232deff6e6152e84e38f`.

## ALL-16 two-row DEV screen v320 (selection only) (2026-10-19T15:24:52Z)

G-E under registration `3a9c34f80578565501e9c4cec138fad995f30065`: equal mean of ALL-16 K4CW-fp and R3a paired contrasts v320−v2, reusing the validated reference and completed candidate rows. SEARCH is reported separately. dd1 has been retired and contributes no cases or score. Checkpoint `0460ea4ddb0dcd962638c81521fd36201dfaf7697749942aae5e756bc2e62b34`. RoyaleSim-playable scope49.0292926714% of corpus weight. All unclean raw rows remain preserved; candidate/v2/search share the union mask, with10% SEARCH/5% other drop limits.

| Opponent | Retained pairs | vN − v2 | vN − search [95% CI] | vN/v2 plays per game | Valid |
|---|---:|---:|---|---|---|
| SEARCH | 56 | +0.267857 | -0.125000 [-0.285714,+0.035714] | 46.357143/49.892857 | True |
| LIVE-K4CW-r16-fp | 60 | +0.233333 | +0.066667 [-0.083333,+0.216667] | 44.016667/48.250000 | True |
| R3a | 60 | +0.133333 | +0.033333 [-0.083333,+0.150000] | 45.033333/46.100000 | True |

Equal two-row screen=0.18333333333333335; screen valid=True, both nonnegative=True, registered plays sane=True, G-E candidate predicate=True. G-S SEARCH selector=False. DEV selection only; no gain or G-S gate claim. Historical BattleLog Sam and ALL-16+dd1 means use earlier definitions and are not a direct trend comparison.

all16/SEARCH: dropped4/60; causes {"live errors": 4}; archetypes {"hog": 1, "giant": 1, "royalgiant": 1, "air": 1}. Retained-case pooled estimate; no archetype contains more than half of drops.

- 0-0015 / hog: Monk, Bomber, GoblinMachine, Elixir Collector, Barbarians, Mirror, HogRider, Bats; {"fast-v320": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Barbarians' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0030 / giant: Golem, Elixir Collector, Berserker, ElectroDragon, AngryBarbarians, Tornado, SkeletonDragons, BarbLog; {"fast-v320": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat1: ValueError(\"'AngryBarbarians' is not in list\")", "seat1: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0039 / royalgiant: Mirror, Elixir Collector, Monk, RoyalGiant, Barbarians, Earthquake, Giant, Snowball; {"fast-v320": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'Earthquake' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
- 0-0047 / air: Tornado, Berserker, Elixir Collector, BarbLog, ElectroDragon, Golem, AngryBarbarians, BabyDragon; {"fast-v320": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "res-lb-RF-wintp": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}, "fast-v2": {"problems": ["live errors"], "details": ["seat0: ValueError(\"'ElectroDragon' is not in list\")", "seat0: ValueError('public play inconsistent with ordinary cycle')"]}}
all16/LIVE-K4CW-r16-fp: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.

all16/R3a: dropped0/60; causes {}; archetypes {}. Retained-case pooled estimate; no archetype contains more than half of drops.


Validated readout `JOB/helper-ge-v320-all16-only-readout.json`, SHA `602ecc620a3552230bd51c161aea2fe31e5f9cff3c169bfd79236afc12b5b6f4`; underlying ALL-16 readout SHA `196f7b34c7bea29c5c1d667bd989b754618dff70d37e232deff6e6152e84e38f`. Candidate/reference row hashes, size/mtime, bank/finished records and checkpoint were revalidated by a new detached cpu_job2/nice15 two-row analysis; no reference games or prior statistical readouts rerun.
