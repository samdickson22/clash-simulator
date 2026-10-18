# HP1 RL (b) results

Exploration; protocol: RL-PREREG.md. DEV screens select snapshots and support no gain claim. No G-E or G-B result yet.

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

Pending.

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

The RL owner was notified with the failure and containment receipts (steer returned thread_not_sendable; identical text delivered with auto). Remote actors/sync remain stopped pending an owner code fix and deployment instruction. Preserve all checkpoints and baseline cases.
