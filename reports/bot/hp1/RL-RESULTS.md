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
