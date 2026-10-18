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
