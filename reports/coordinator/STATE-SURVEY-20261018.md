# Clasher state survey — 2026-10-18 UTC

Read-only survey from 127x05, started 2026-10-18T00:46:15Z; principal process snapshots 00:47:08–10Z, follow-ups through 00:50:38Z. This report is the only file created. No jobs, emulators, queues, Git refs, accounts or other threads were changed. Observations below are snapshots, not reservations or instructions to launch.

Path prefixes: R = `/mpac/sdicks02/repos`; J = `/mpac/sdicks02/jobs/clasher`; S = `/mpac/sdicks02/scratch`; Mac home = `/Users/sam`. Paths using these prefixes expand literally. Process ages are `etimes` seconds unless marked otherwise. PID=PGID where one number is given.

## Repos

All four requested directories are worktrees of the same repository, sharing refs and 113 registered worktrees. No fetch was performed. Ahead/behind below means HEAD versus the locally cached `origin/main`, not independently queried server state. main, bot/lead and live/lead track origin/main; cards/lead tracks origin/cards/lead (its own upstream comparison is reported below).

| Directory | Branch | HEAD | Subject | Ahead / behind | Changed tracked / untracked files |
| --- | --- | --- | --- | --- | --- |
| R/clasher | main | `4292e520550b4c19feaf305856508fd0a9588d9f` | Record authorized END cache08 retirement and reconciliation | 1 / 1694 | 191 / 13,303 |
| R/clasher-bot | bot/lead | `474cf6da97814fb947a32a2450a7e9e6eabc7e47` | Bot lead: rollout opponent-model arms null vs K4C-r16 (best +0.017 ours / -0.008 RoyaleSim); balanced-only = -41% rollouts at ~-0.01 (exploration) | 0 / 827 | 12 / 93 |
| R/clasher-live | live/lead | `feef63aabb5c54531409c70772d95faab79ec4db` | live-perc-r3: progress (form audit, HARD27) | 254 / 711 | 32 / 289 |
| R/clasher-cards | cards/lead | `153c56d2f350ebaea79c0dc5168f897a174cdc33` | Cards: progress (Claude-budget rule; publish to Sol) | 44 / 432 | 6 / 711 |

Counts were taken at approximately 00:46Z with all untracked files expanded, not collapsed directory counts. cards/lead is 0 ahead / 0 behind its configured origin/cards/lead upstream (same full SHA as HEAD); its 44/432 table entry is versus origin/main. Do not clean/reset these trees. HEAD commit times converted to UTC: main 2026-10-11T19:42:12Z; bot/lead 2026-10-14T21:30:46Z; live/lead 2026-10-18T00:15:02Z; cards/lead 2026-10-17T23:47:05Z.

Cached origin/main at 00:50:24Z: `5c1e2a7c7af8933b93e2c380da5273008d42da93`, subject `bot/fullpool/hz_report: wrong-lane defensive aim share (LIVE LEAD play-accounting definition) (exploration)`, commit UTC 2026-10-18T00:05:45Z. This is substantially newer than the BOT worktree's top-level documents; current BOT state was therefore also read with `git show origin/main:<path>`.

Recent worktrees from `git worktree list --porcelain`, ordered by directory mtime (not proven creation time):

| Path | HEAD | Branch / directory mtime UTC |
| --- | --- | --- |
| /tmp/wt-playaudit | `e88de4ef6c08914aca49b1b7b235b837b9d11e75` | live/play-audit; 2026-10-17T23:59:46Z |
| R/clasher-bot-lp1 | `11fca5cd4e0155153c589b9a7d4064947d2de214` | bot-lp1-analysis-20261017; 23:54:56Z |
| R/clasher-bot-sol6 | `5c1e2a7c7af8933b93e2c380da5273008d42da93` | detached; 23:49:37Z |
| R/clasher-bot-cannon-sol | `25b3fbb8ce4d916e5e4a3cea5205f8785a701a96` | detached; 23:48:25Z |
| /tmp/wt-policy-first | `0b46b0d342b3f4e34c0bce802f5df575c880e9a1` | live/policy-first; 23:07:48Z |
| J/live-multibody-20261015/wt-barrel | `d5d7d31ff210f9014a417a8060ab66cac672e11c` | detached; 23:04:53Z |
| /tmp/sdicks02-barrelsim-wt | `6a6708a147032d45f71bcde501056340d542bf8f` | detached; 22:58:02Z |
| /tmp/sdicks02-cannon-wt | `908aefefab9e9bd2124dbcb5396e6850bd2d94ad` | detached; 22:45:48Z |
| R/clasher-bot-deckopt3 | `22b55e92c204a1c304ef13fadd0c8eb991193324` | detached; 20:37:11Z |
| R/clasher-cards-release-d | `e315f7aa14ad9afc7da168e1fa856ab509e088bd` | cards/release-d; 19:25:14Z |

The four lead worktrees see the same full worktree registry; the table is a shared recent subset, not four independent inventories.

Progress/handoff/release search: ran `find <repo> -name '*.md' -mmin -2880 -not -path '*/.git/*'` in all four trees, deduplicated identical documents, and read current sections plus relevant historical closeouts. Important source locations:

- R/clasher has no `reports/bot/PROGRESS.md`, `reports/bot/HEADLINE.md`, or root `run-r1/PROGRESS.md`. Its recent memory note is `reports/live/memory-annotation/PROGRESS.md`; its PARKED/labels-only conclusion is superseded below.
- BOT: R/clasher-bot/reports/bot/{PROGRESS,HEADLINE,HANDOFF}.md are October 16 snapshots. Current versions are the origin/main blobs, especially `reports/bot/{PROGRESS,HEADLINE,HEADLINE-MAX-20261017b,NOSEARCH-20261017,NOSEARCH-NS2-20261017}.md`, and `{fullpool,live-diag,hp1,lvg2,prior-tb,spell-hold}/PROGRESS.md`.
- LIVE: R/clasher-live/reports/live/PROGRESS.md (mtime 2026-10-18T00:13:59Z), loop/PROGRESS.md (00:21:47Z), loop/HANDOFF.md (00:16:21Z), loop/BABYSITTER-BRIEF.md (00:12:37Z), perception/PROGRESS-R3.md (00:15:02Z), memory-route/{FIELD-PARITY,READER-PLAN,PROBE-160402020}.md. The probe is newer than the lead's last entry.
- CARD: R/clasher-cards/reports/cards/PROGRESS.md (2026-10-17T23:47:04Z), COVERAGE.md, release/RELEASES.md; release worktree R/clasher-cards-release-d. Historical B1/B2/runtime/nulls handoffs retain older failures and accepted gates.
- The nested `reports/explore/k4s-confirm/run-r1/PROGRESS.md` exists in bot/live/cards (470 lines, same old preflight instructions). The old `reports/strategy_council_20260928/COORDINATOR.md` copies disagree and are historical; do not apply their old launch/seal procedures to today's BOT-FIRST work.

## Running jobs per host

Host measurements use `uptime`, `nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv`, `who`, and `ps -eo ...` with `/proc/PID/cwd`. `who` returned no sessions on 01/04/08/05. This does not mean the machines are free of other users' noninteractive jobs. Tables identify parent/controller and primary Python processes; loader/fork children are grouped.

### 127x01 — 2026-10-18T00:47:08Z

Uptime 24 days 12 min; load 41.74 / 42.30 / 42.94; GPU 100%, 29,012 MiB.

| Work | PID / PGID; age | Actual cwd / output |
| --- | --- | --- |
| YOLO h31, 12 epochs | 400885 / 400885; 4503; 30 loader children | J/live-yolo-20261016; runs/h31 |
| YOLO h32, 12 epochs | 471553 / 471553; 3931; 30 loader children | J/live-yolo-20261016; runs/h32 |
| h35 queue, waiting for h31 | 469622 / 469622; 3946 | J/live-yolo-20261016/chain-h35.sh |
| h36 queue, waiting for h32 | 533408 / 533408; 3473 | J/live-yolo-20261016/chain-h36.sh |
| Deck final2 D-top4-01 | wrapper 528327 / 528327; 3505; Python 528524 | R/clasher-bot-deckopt3-src-7df775763; J/bot-deckopt3/final2/D-top4-01 |
| Deck final2 Bsup-top4-01 | wrapper 528371 / 528371; 3505; Python 528686 | same cwd; J/bot-deckopt3/final2/Bsup-top4-01 |
| K1 x25 / x29 generation | groups 823378 / 872504; Python 823523 / 872671; ages 1011 / 596 | Python cwd J/bot-fullpool/repo-c7081871c8b2; outputs K1-x25 / K1-x29 |
| Fullpool filler, alive | 3754988 / 3754988; 11673 | J/bot-fullpool/repo-0ab8a84e8f06; queue J/bot-fullpool/filler/queue |
| Protected historical hub mirror | 516161 / 516161; 782007; children 516178,516179 | R/clasher; J/hub_mirror_v2.sh |

Alive YOLO eval loops in cwd J/live-yolo-20261016, model: PID=PGID(age at initial host snapshot): h31 400888(4503); h32 471555(3931); w2a 495720(71835)/495722(71835); n2 741609(40204); y4n 796675(39626); w5c 866669(68068)/866671(68068); x1c 1176671(64698)/1176673(64698); h1 1310186(33918); h2 1362700(33384); y1c 1493158(61341)/1493160(61341); y2h 1800313(57978)/1800315(57978); h7 1864781(27955); h8 1919897(27400); z1x 2073471(54753); y3h 2108423(54327)/2108425(54327); q4 2362347(47850); h13 2479000(22068); h14 2561070(21417); q1 3054261(47202); h18 3201018(16291); h19 3285908(15648); h27 3901888(10418); h28 3971327(9801). These often sleep between artifact checks; alive does not imply a trainer is still running for that model.

Additional h31 evaluators 408838/408840 and h32 480269/480271 are alive. Mirror processes 1259458 (R/clasher-bot, bot-exit-r1-01 →04) and 1786877 (J/bot-fullpool, →04) are alive.

### 127x04 — 2026-10-18T00:47:09Z; process follow-up 00:50:11Z

Uptime 19 days 2:46; load 58.46 / 72.57 / 82.08; GPU 94%, 13,990 MiB.

| Work | PID / PGID; age | Actual cwd / output |
| --- | --- | --- |
| YOLO h37; h34 has completed | 244832 / 244832; 266 at 00:50:11Z | J/live-yolo-20261016; runs/h37 |
| Deck final2 C-top4 | wrapper 3422609 / 3422609; 3739; Python 3425814 | R/clasher-bot-livediag-par-7df775763; J/bot-deckopt3/final2/C-top4 |
| HP1 S0 ef | wrapper 3453624 / 3453624; 3632; Python 3688024 | J/bot-hp1-s0-20261017/source; runs/ef |
| LVG2 lane4 | 2185827 / 2185827; 7836; Python 3688439 | controller cwd J/bot-cycle/lvg2; Python cwd R/clasher-bot-cycle-pt1-68816487f; es9-k4cw |
| LV2 shards at first snapshot | PGIDs 54427,63596,66534,109549,208380; Python 54577,63778,66731,109734,208600 | Python cwd J/bot-fullpool/repo-52c55e33bade; lv2/l1,a05-r2,a04-r2,a08-r2,a03-r4 |
| Fullpool filler, alive | 3990711 / 3990711; 11837 at follow-up | J/bot-fullpool/repo-0ab8a84e8f06; J/bot-fullpool/filler/queue |

At 00:50:11Z the first four LV2 groups above had finished; a03-r4 group 208380 remained (age 543). No new gate is needed merely because those processes disappeared.

Alive YOLO eval loops in cwd J/live-yolo-20261016, model: PID=PGID(age at initial host snapshot): y2c 234416(59178)/234418(59178); q5 243188(49512); h37 244835(83); h16b 621441(19385); y3c 663329(56112)/663331(56112); h3 828991(34724); q2 1095967(52962); n4 1434593(41132); h29 1679903(9544); h6b 1775099(31626); c1 1864390(38153); h33 2448411(6504); h10 2515249(28596); h22 2700751(16046); h12 3048509(25606); w2b 3238503(68264); w4b 3262045(68071)/3262047(68071); h24 3492973(12903); h34 3504495(3382); h16 3618627(22544); x1b 3629513(65148)/3629515(65148); y1b 4013649(62210)/4013651(62210); n1 4194059(44941). h37's additional evaluators253977/253979 and h34's3542411/3542413 were also observed;3542413 remained at follow-up.

Mirrors 1801987 (R/clasher-bot, bot-exit-r1-04 →08) and 2486342 (J/bot-fullpool, →08) are alive. The old chain-h33/chain-h34/chain-h37 controllers are no longer alive: their successors have run; h37 started about 00:45:46Z.

### 127x08 — 2026-10-18T00:47:10Z; process follow-up 00:50:12Z

Uptime 24 days 2:50; load 86.60 / 87.58 / 90.74; GPU 99%, 28,824 MiB.

| Work | PID / PGID; age | Actual cwd / output |
| --- | --- | --- |
| Label-volume queue B | controller 3520559; age 9670 at follow-up; trainer 181065 / 3520559, age 3654 | J/live-yolo-20261016/chain-volb.sh; current vol1s23, later vol3s23 |
| Label-volume queue A | controller 3520561; age 9670; trainer 650759 / 3520561, age 44 | same cwd, chain-vola.sh; vol0s13 completed, current vol1s13, later vol3s13 |
| PF1 shards s0 / s1 | wrappers 149174 / 149217; age 3865 each; Python 149487 / 149822 | R/clasher-bot-livediag-par-7df775763; J/bot-livediag/pf1/{s0,s1} |
| Deck final2 A-top4 | wrapper 167804; age 3741; Python 415082 | same cwd; J/bot-deckopt3/final2/A-top4 |
| LVG2 lanes | 3773236,3773841,3774346; ages 7847,7844,7841 | controller cwd J/bot-cycle/lvg2; Python cwd R/clasher-bot-cycle-pt1-68816487f |
| Current LVG2 Python | 464258 / 3773236; 503011 / 3773841; 503438 / 3774346 | hr9-k4cw, base-r3a, sk8-r3a respectively |
| PT1 / Valkyrie follow-on waiters | 4066938,4066980,4109218; ages 5848,5848,5559 | /home/sdicks02; J/bot-cycle/pt1/{resume-after,resume-v}.sh; wait for the LVG2 lanes |
| LV2 current shards | PGIDs 433128,578048,592294,606387,628198,643127; ages 1804,610,498,387,215,103 | wrappers cwd J/bot-fullpool/repo-0ab8a84e8f06; Python cwd repo-52c55e33bade; outputs lv2/a13,a15–a19 |
| Fullpool filler, alive | 3227738; age 11803 | J/bot-fullpool/repo-0ab8a84e8f06; J/bot-fullpool/filler/queue |
| NS2 controller, waiting | 3706685; age 8331 | /home/sdicks02; J/bot-ns2-20261017/controller.py |
| CARD final pipeline, alive | 4007414 / 4007414; age 6217; children 4007818,4010551 | controllers cwd /home/sdicks02; J/cards/release-d/final/tools/{pipeline.sh,gates.py} |
| CARD graph stress child | 589632 / 4007414 at first snapshot | J/cards/release-d/final/repo-eval; tools/graph_stress.py, 6 seeds |

Alive older CARD waiters (not active compute): 584735/587598 in J/cards/b2m/fid, 3404782 in J/cards/runtime, 3629588 in J/cards/b1b2/fid; ages at follow-up 144354/144349/166927/111633. They wait on old sentinel/log conditions; do not interpret them as unfinished current release gates.

Alive YOLO eval loops in cwd J/live-yolo-20261016, model: PID=PGID(age at initial host snapshot): h5 251600(32272); h9 653524(29307); h11 1152114(25987); w4c 1364787(68075)/1364789(68075); h15 1551916(23016); x1h 1773798(64847)/1773800(64847); n3 1990440(44857); h17 1991360(20044); y1h 2201663(61701)/2201665(61701); h20 2438058(16884); h23 2592303(15934); y2s 2639921(58338)/2639924(58338); y3s 3072219(55107)/3072223(55107); h25 3190853(11848); n5 3228590(41038); q3 3517156(51881); n6 3639532(38117); h4 4040090(35204); q6 4165571(48205). Extra h23 evaluator2487775 and new vol0s13 evaluators646817/646819 are alive. Mirrors1178335 (R/clasher-bot, bot-exit-r1 →04) and724602 (J/bot-fullpool, →01) are alive.

### Persistent queue consumers and queue contents

Old ExIt queue consumers are still alive with cwd R/clasher-bot. Script for each is R/clasher-bot/bot/exit/gpu_queue.sh; no associated training job was observed for these queues:

- 01, under J/bot-exit-r1-01: cpuqka/QUEUE PID 1516721 (age 296633), cpuq6/QUEUE 2084764 (288370), cpuq7/QUEUE 2925089 (277065).
- 04, under J/bot-exit-r1-04: cpuq/QUEUE 3045524 (309780), cpuq2/QUEUE 3192422 (307518), cpuqka/QUEUE 3964180 (296632), cpuq6/QUEUE 363971 (288370), cpuq7/QUEUE 1222266 (277064).
- 08, under J/bot-exit-r1: cpuq/QUEUE 2525950 (310442), cpuq2/QUEUE 2581995 (309537), cpuqka/QUEUE 3544192 (296633), cpuq6/QUEUE 4115451 (288370), cpuq7/QUEUE 792386 (277064).

Fullpool filler queue files/next markers were read at 00:49:23Z: 01 queue has 660 lines, next=323; 04 has 779 lines, next=780; 08 has 1126 lines, next=1127. They are append/requeue histories, not pending-job counts. Logs show deliberate `0 parked-* true` lines rejected as bad lines, shedding/requeueing on load, and advancing to LV2. Do not replay the files from line 1. Both volume chains on08 and h35/h36 chains on01 have live owners; h31/h32/h34/h37 predecessor chain files remain on disk after their controllers exit.

### 127x05 and 127x03

05 at 00:46:52Z: uptime 24 days 9 min; load 3.19 / 3.33 / 11.34; NVIDIA driver unavailable. No Clasher trainer/eval workload observed. Clasher cwd processes included coordinator Claude PID/PGID 588684 (age 1047 at 00:49:11Z), shell 623623 with pkttyagent 623653, and **release waiter 3875522 / 3875522**, age 1536, running `/tmp/clasher-release-d-wait-4007414.sh` from R/clasher. The latter remained alive despite the CARD note saying the lead waiter was stopped. Survey shells/short sleeps are excluded.

03 was tried exactly once at 00:46Z with `ssh -o BatchMode=yes -o ConnectTimeout=6 127x03 true`: exit255, `ssh: connect to host 127x03 port 22: No route to host`. Nothing on03 was verified. Hosts09–18 were not contacted.

## Mac/live

Read-only `ssh macmini-fleet` observations 2026-10-18T00:47:55Z–00:49:11Z; final `__RC=0` markers were parsed, and intermediate failures retained separately.

- **No live driver:** `pgrep -fl '[d]rive\.py'` returned no matches, explicit DRIVER_RC=1. Historical s84 driver PID82920 is gone. No BlueStacks process was observed. Latest binding handoff says BlueStacks is permanently OFF; the throwaway account **bigdiddle** has moved to MuMu.
- **MuMu app open, guest STOPPED:** app PID/PGID33766, elapsed48:23 at00:48:27Z. At00:49:11Z, `mumutool info all` reported index0/state=stopped; port26624 has no listener. There is no current running CR process/root/battle available to validate. adb servers remain PID25270 on5047, PID68675 on5051, PID70534 on5053; no adb connection/start was attempted in this survey.
- **Publisher alive, showing a pause card:** video_supervisor.py PID13848, mediamtx13850, display_feed.py67172, ffmpeg59343, all PGID13848. At00:49:11Z display/state.json says driver=false, source=LADDER PAUSED, video.kind=card, 30fps; error says no on-screen BlueStacks window. Feed log switched to CARD at00:08:35Z. No live MuMu-window stream has been established by the observed stack. Retargeting remains work, not a verified completion.
- caffeinate23740 (-dimsu) and15826 (-is) are alive. Free disk at00:47:55Z: `df -h /` reports **9.4Gi available** on the460Gi volume, below the11.5Gi Null's boot floor.
- Actual session root is `/Users/sam/clasher-live/loop/runs`, not loop/sessions (the latter is absent). Newest session is s84/m06. session.json and session-config.json mtime **2026-10-18T00:05:11Z**; frames.jsonl/events.jsonl and video/001707.jpg last changed **00:05:10Z**. These are stopped-session files, not a live heartbeat.
- `/Users/sam/clasher-live/loop/status.txt` is stale: still says s84 continuous/PID82920, timestamp2026-10-17T23:44:14Z. Do not use it as liveness evidence. Current display/state.json is being updated and says no session.
- Last vision ladder: s84, Royal Arena, x1h896 detector + x2a hand reader, `LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-wint`, manifest80fceab6, SUBMIT_COUNT=1, TOWER_SCORE_GATE=0.9. Current saved deck: Skeletons7, Archers8, Valkyrie7, Cannon9, Fireball7, Zap9, ElectroSpirit8, HogRider8; King7 (levels from final deck registration, identities also checked in Mac deck.json).
- Native boundary exit was verified at **00:05:31Z**, per S/live-loop/evidence/s84-r3/fps-hold-native-exit-receipt.json and loop handoff. FPS hold began at m05 (8.84fps); m06 had p95 71.11ms/FPS8.96. m05 was interrupted by a Google Play security/sign-in prompt: incomplete, crowns unverified, loss−30→2127 inferred from next settled VS. No final m06 result is in the checked RESULTS lines; do not invent a final trophy total.
- Archives: s81–s83 reported verified/pruned; s84 m04→m05→m06 was released to one nice19 sender at4000KiB/s despite idle Screen Sharing. m05 is now documented verified/pruned; m06 video still exists on Mac. Verify remaining copy/SHA receipts before further pruning. Null's07:50Z stop trigger was explicitly cancelled; no08:00–14:00Z capture GO exists tonight.

## Per-lead state + next steps

### BOT — strongest bot / simulator evaluations

Current authority/plan is in the **origin/main** PROGRESS blob, not the stale bot/lead file. Sam requires max card/tower levels on both sides for play-quality comparisons; account levels are secondary for actual spending decisions. Strong search-opponent results stay separate from weak pools. Sam chooses the live deck.

Latest completed daily quoted bot: **K4L-R-gs-mk1a1-res**. HEADLINE-MAX-20261017b: RoyaleSim16.402/L16 R3a+v1 pool **0.8825 [0.8600,0.9038]**, strong LIVE-K4CW-r16 **0.6467 [0.5733,0.7200]**, rext-bc separately under15.535 **0.9425 [0.9200,0.9650]**. Fresh bank3905522882501520; rext bank2701262821741664. C56-alias differences span zero. Fixed-bank continuity P1 .93250/v3 .93889 is selection-biased, not the fresh headline.

Latest live search adds -lb/-wint. Best legacy fast student remains RLr5v10, SHA256 `e188e2aeb9a6828ffbef237aa327e495eb39ca5f8322ae18aa70c63cb81bba19`; fullpool live copy reported SHA256 `a6565cabe728e8842405cb7a9e040970893566596b11980ad7ddf867df3dddcc`. Distinguish these from f1a2 and human-init v2 checkpoints.

Completed/parked: learned leaf/value designs failed clean held-out sibling gates; receding-horizon learned variants lost; SCALE1 search scaling was nonmonotone (K8−K4−0.068 [−0.118,−0.015]); K2 Mac bench66ms exceeds60ms; rlfp1 stopped/null; soft cycle v2 null; owner v1.4c inconclusive; SC1 sh5+0.040 [−0.029,+0.109], no ship. WINT-ACC1 confirmed no clear harm (−0.010 [−0.06,+0.04] vs strong), so -wint stays. Do not restart these as abandoned jobs.

Active/queued work to collect:

- **Deckopt3 final2:** J/bot-deckopt3/final2 on01/04/08, fresh base1217618782281. Reference is the current Hog/Valkyrie deck, not the earlier Giant deck. Interim screen says Bats→Valkyrie +0.13 in PEKKA/Hog strata; no new-card replacement clearly better. Lead ETA **04:30–05:30Z**. Final row comparison must wait for all arms. At00:50:37/38Z completed fixed/ref directories coexist with incomplete top4 rows: C-top4 321 files, A-top4 146; raw counts are not accepted game counts until audited.
- **PF1 policy-first:** J/bot-livediag/pf1; 150 paired account-level cases, search vs rl5-alone vs f1a2-alone against K4CW-fp/R3a. s2 finished00:44:14Z, 300 row files/all10 child statuses0; s0=281 and s1=294 files at00:50:38Z, still running. No combined final readout yet. Earlier NOSEARCH strong search−rl5 +0.03 [−0.09,+0.15] is inconclusive; NS2 confirmation is queued, not complete.
- **NS2:** controller-status at00:50:07Z says preflight=false, smoke=false, blocks={}; controller alive behind higher-priority deckopt3/LV2 work. J/bot-ns2-20261017; bank1587927595246112, 3600 scored games planned. ETA **6–10 admitted hours**, queue wait additional/unbounded.
- **LVG2 upgrades:** J/bot-cycle/lvg2 on04/08; several100-row jobs complete, hr9-k4cw/base-r3a/sk8-r3a/es9-k4cw partial. Collect ranked affordability readout from both hosts; no current finish ETA. PT1 and Valkyrie add-on waiters already own follow-ons. PT1's old partial shards were deliberately retired, not resumable scored data.
- **HZ1 horizon / LV2 levels:** J/bot-fullpool/{hz1,lv2} on04/08; filler consumers alive. HZ1 has completed attempts for38/40 shards; s32 has no finished attempt and s39-r2 has13 row files, unfinished, at00:50:38Z. No HZ1 compute observed now while fillers run LV2. Reconcile queue/retry history before concluding completion or relaunching. GoblinHut unmapped rows remain primary-valid, with predeclared exclude-GoblinHut sensitivity; do not silently discard them. LV2 has many complete and partial retry dirs; deduplicate by keys and require identical duplicates.
- **HP1 human-init:** J/bot-hp1-s0-20261017 on04, ef running; S0 complete summary still pending. P1 J/bot-hp1-p1-20261017 has overlay-b/cap1-b/cap2-b/lag-b exit0 artifacts (cap2 completed20 steps); lag2 resume and final pin-check acceptance are not present in inspected log set. Original overlay failed; preserve it. No HP1 GPU trainer observed; GPU window must be arranged with LIVE, not taken from YOLO.
- Cannon/barrel sim diagnosis and LP1 lag-projection analysis have existing worktrees R/clasher-bot-cannon-sol and R/clasher-bot-lp1. Collect their artifacts before assigning replacements; no corresponding active heavy process was observed on05.

### LIVE — perception, play loop, memory route

Vision findings are substantial but not all released. Barrel AUDIT.md:84 barrels,81 tower hits,0 well-spelled landings; translator registered0 in103 battles because projectile boxes/events were discarded. Spells-field patch04fd2d4a9 was rebased to actual live adapter2b6c44e2; parity passed. Translator's track-based barrel path has a3/3 smoke and a38-battle gate pending in the last lead update. New fields/patches are not proof of installed live behavior.

Wizard/knight audit is done: Hero Wizard0/36 correctly identified, most read as knight; other hero bodies similarly collapse. Perception decision: train heroes as base classes, preserve existing head; HARD26=177 hero frames, HARD27=104 form frames. Evo classes map to KataCR evolution classes where supported. h37 is already running although the progress file still describes merging lists before it starts: verify exactly which list bytes it loaded.

At00:49:23Z h31 last completed epoch9/12, h32 epoch8/12, h34 completed12/12, vol0s13 completed12/12, vol1s23 epoch6/12. Training continues on all3 GPUs. h35/h36 wait on01; vol1/vol3 chains own08 follow-ons. Rough projection only:01 successors start after tens of minutes; full volume chains need hours; no guaranteed finish time was published. Scoring receipt S/live-perc-r3/scoring/ROUND1.md already exists: h24/25/27/28/29 lack required old-deck eval coverage; h16/h22 have stronger own-Bats recall but pending re-tests/translator checks. Do not infer a ship from isolated improvements. Jev quality gate failed; Sol labelling remains current.

Per-play accounting is DONE at R/clasher-live/reports/live/play-accounting/PLAY-ACCOUNTING.md (00:02:28Z):116 battles/3911 executed plays; no systematic mapping/mirror bug,96.8% same-lane landing proxy; empty spots51.7%, wrong-lane proxy24.3–26.8%. These are descriptive proxies with coverage limits, not all tactical mistakes. BOT metrics were updated accordingly. Remaining detailed owner/tower audits and m06 result/archives still need reconciliation.

**Memory route is approved for play but NOT working yet.** Sam's00:01Z field cap and00:12Z “go straight to memory” supersede older labels-only/PARKED/screen-only statements. M1 install/login/root was reported by lead; later probe and this survey show the guest is now stopped. No validated160402020 ARM64 offsets or live reader/integration exist in the checked evidence.

Authoritative newer status: R/clasher-live/reports/live/memory-route/PROBE-160402020.md, recorded00:22:11Z. Target ARM64 libg SHA256 `347afc57c8d168bb67d0defa488a89f76297025cac1e8544b5182bb7e70ff433`, buildID `b08850c3912220ba36f1057c3e951b0e578a4691`. Hasty x86_64/160402012 global0x1aeef98 is outside target load ranges. Older ARM64/160402002 lead0x1a569a8/context0x28 is only a candidate, not a verified binding.

S/memory-route/hcr_reader_arm64_probe is compiled (SHA256 `6637b62df3210288ff26cad74f556584cfede19139df57074080ad8ca02a3a20`); diagnostic reader hcr_reader_arm64 SHA256 `2da5078523944efa1f90944488d684e64ddc6385a09d162076f361c6d178d348`. Neither was pushed/executed: endpoint gate failed first. Plan/65-row FIELD-PARITY exists, all “our use” cells blank pending integration decisions. Source review uses O_RDONLY/pread and no opponent private blocks. No fair-information runtime test or screen-validation pass can yet be claimed.

Next dependency is Sam restoring the same MuMu guest/endpoint and starting a manual Training Camp battle, confirming own side. Then reviewed narrow offset discovery/public-field validation; state builder and MuMu input/stream integration remain separate unfinished work. Lead's earlier optimistic ETA was probe~1h, first memory battle~2–3h if layouts carry; prep plan budgets1–3 engineering days. Both predate the stopped guest and are conditional, not deadlines.

### CARD — full pool / live16402d

Pool definition is122 cards (C56+66); scope metadata121 excludes MergeMaiden because it deploys no body. Real entities do not imply verified mechanics. live16402c/r1-cards3 are released read-only on04/08 (and historically03), native SHA256 `326ce6f93c4db6a7bd15b667960a2d3ed40a0d48eab3badc9ddd181521996732`. Mac remains live16402b-r3-mac, native8072e577 prefix; never overwrite a loaded native.

C1 merged f273b0abe; admission-class merge **`d5d7d31ff210f9014a417a8060ab66cac672e11c`** accepted the4 documented Log differences (574/577 fixture and598/600 root equality, final states equal/Python-matching). Suite m5 passed21 phases/134 rows. live16402d adds those fixes, GoblinGiant rider graph, Void/Tornado overlays. Final source/pins **`89692ef4db3be1e89cf9354c074762f565992f02`**, native5b2e45d7 prefix, gamedata df93121d prefix.

Final pipeline J/cards/release-d/final on08 is still alive. At00:49:48Z all15 existing phase .exit files were0 (smokes, None-stat, objects, totality, headline, mixed); graph stress had completed2/6 seed records by00:48:37Z and had no final exit/result yet. **Neither R/clasher-bot-runtime/live16402d nor r1-cards4 exists on04/08. Publication and release-d merge are pending.** Earlier~80min estimate has elapsed; current remaining ETA is unestablished.

Publishing was reassigned from cancelled Opus release owner to Sol `cards-live16402d-publish-sol-r1`; do not start a second publisher/waiter. Release worktree HEAD is e315f7aa14ad9afc7da168e1fa856ab509e088bd. Belief robustness is DONE/approved, code **`74978f6dda24b01fb353e1be77726335b018185a`**; player.py must travel with its matching r3 belief.py. Exact-level cache/per-seat support already merged (3ea58c365/7fa5bbadd); pooled-L11 evidence remains a documented open item. Mac rebuild/adoption awaits LIVE's window, disk and explicit pin coordination.

## Open items / waiting on Sam

- **Immediate:** MuMu guest0 is stopped/26624 unavailable. Sam must restore it and supply a safe manual battle/own-side confirmation for the existing reader owner. Prior lead root uid0/PID3553/base0x793daf4000 are historical, not reusable current measurements. No need to re-ask whether read-only memory is allowed; that decision is recorded.
- **Memory boundary:** read only; no writes/injection/spoofing/anti-detection. Never opponent hand, next card or true elixir, even evaluation-only. Cap observations to what ClashAI/Hasty actually feed; neither-fed fields prohibited, one-only fields require adjudication, unmatched fields dropped or taken to Sam. Do not bulk-read both players to determine ownership. Complete the field-use table and non-privilege tests before input reaches the bot.
- Sam handles credentials, membership/trial/payment/admin prompts. No new account/spending actions are implied by this survey. Preserve rare-wild freeze pending Hog/upgrade break-even; LVG2 says ElectroSpirit's boosted/base level needs verification before spending. Sam chooses the deck.
- Disk9.4Gi cannot support the planned Null's boot floor11.5Gi. The next Null's block/07:50Z trigger is cancelled/postponed, not an automatic scheduled resume. Memory takes priority; any space decision must preserve verified data and existing Mac paths.
- Collect PF1, HP1 smoke/S0, LVG2 and deck final2 results already present before new experiments. HZ1's incomplete s32/s39 retry history needs owner reconciliation; final aggregate readout is absent. Finish CARD stress/publication and confirm host receipts before announcing a release.
- Live release queue before the memory pivot was BUILDING_BODY → CAL → policy-first, each at a forced break; rubble fast-death208-battle replay, barrel gate, log-only per-play module and stream retarget remain unverified deliveries. The BlueStacks retirement changes their deployment target; re-establish which pieces still apply before installation.
- New coordinator should read existing artifacts/owners rather than sending messages to retired threads. This survey contacted no threads and verified no app-owned agent lifecycle state; process liveness does not prove a coordinator/helper thread is active.

## Risks (things a new coordinator could break or duplicate)

- Shared Git refs plus stale/dirty lead worktrees: origin/main blobs, local edits and installed runtime copies differ. Temp-index publication is common; checking out/resetting/syncing an entire tree could destroy unrelated work. Full tracked/untracked counts are large.
- Detached chains, fillers, cpu_job claims, NS2 controller and PT1 waiters survive agent retirement. They can launch successors autonomously. Recreating a job because its agent is gone duplicates work. Existing filler requeues require deterministic duplicate audits, not concatenation.
- Old eval loops/ExIt queues and CARD sentinels remain alive after trainers/gates finish. Process-name matching alone overstates current compute; bare PID exit alone does not establish failure. Protected01 PGID516161 is the historical hub mirror.
- Current observations show full GPU use and sizeable CPU loads. Historical “idle GPU”,03 allocations and no-user receipts are obsolete. 05 is light-only;03 is unreachable;09–18 belong to another project.
- Mac status.txt falsely advertises a live PID; publisher liveness currently means a pause card, not gameplay. MuMu app liveness does not mean its guest exists. Never restart BlueStacks: account moved, runtime permanently retired.
- Never put the literal driver filename in Mac commands; use `[d]rive\.py`. Preserve __RC parsing; SSH's reported status can hide failures, and final successful commands can mask earlier pipeline failures.
- Memory approval has a specific fair-information cap; Hasty/ClashAI historical hidden/eval fields do not expand it. ARM64 scaffold compilation and old bindings are not target validation. Preserve exact build identity and stop on failed probes.
- Existing fullpool/runtime roots are immutable. Source merges, prep gates, Linux release, Mac build and active-pin adoption are different states. live16402d is not published at this snapshot; never change active pins just because source is ready.
- Avoid a second SCK capture client, broad process kills, emulator lifecycle changes or unverified archive deletion. Preserve capture/driver ownership and checksum-before-prune receipts. Sparse form/bat accuracy and provisional trophy/crown rows are not complete gates/results.
- Latest standing coordination rules: Sol for watches/scoring/reviews/mechanical work, Opus code/decisions only; say less; explicit steer, same-message auto only on thread_not_sendable, never queue. Earlier blanket Opus holds/old STRICT SILENCE approval machinery were superseded by later BOT plan; use the latest dated decision and actual ownership.
