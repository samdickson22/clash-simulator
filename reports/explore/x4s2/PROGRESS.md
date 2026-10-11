# X4S2 progress (exploration, NEVER ADOPTABLE)

- **Job root:** `/mpac/sdicks02/jobs/clasher/x4s2-20261011` on 127x03 and 127x08. The 05 mirror is under `mirror/`.
- **STOP file:** `<job>/STOP` on each host.
- **Hard stops:**
  - 127x08: supervisor stop-at 09:15Z, sync no-contact from 09:27Z; it must be empty by 09:30Z;
  - 127x03: 13:30Z.

## Log (date -u)
- 2026-10-11T04:24Z: assignment received. Read the X4S plan, results and harness, S1 anchor, and the TIERS r3 guard
  population. 03 and 08 are idle, with no console users. The A2 sshd sessions are present and untouched.
- 04:27Z: runtime staged on 03 and 08 by local copies of the X4S runtime. SHAs verified: native 44874fd6, v1 d77005d5,
  R3a 37509a43. Guard decks transcribed from the pinned catalogue (sha 80de4afb…).
- 04:30Z: unit tests: 35 passed (test_sdefault with the lite rule, test_anchor_x, s1 test_latency).
- 04:31Z: seed audit clean. Fresh bank: G 4503605107370496+[0,540), smoke …5117…+[0,8), qualification …5127…+[0,8).
- 04:32Z: launched three jobs:
  - smoke on 08: 14 blocks, 70 games;
  - no-deadline game qualification on 03;
  - corpus qualification on 03.
- 04:33Z: PLAN.md written. Sol review r1 requested (task `x4s2-sol-review-r1`).
- 04:35Z: corpus qualification r0 aborted by me (own process group), then relaunched as r1. The X4S budget grid never
  reached "coarse complete, no refined play", so I added the exact injected budget for that case.
- 04:35Z: card support passes. All 27 guard-population cards resolve to known `card_action` tokens and have loader
  definitions (`logs/card-support.json`).
- 04:37Z: smoke r1 on 08: 70 games, 0 metadata or charge problems. The charged poll measured ~10 ms. Pre-scoring
  preparation measured ~38 ms at fleet speed, so budget equivalence already scales in-timer work. K4Sh and K4Sf are
  reframed as relative-slowdown stress tests (PLAN).
- 04:36Z: no-deadline r1: K4, K4S, K4Sl and K4Sh (scale 2) give identical command hashes on X0 and G1.
- 04:39Z: STOP test on 08 passed: STOP 04:39:13Z, supervisor exit 2 s later, 0 processes left. STOP removed.
- 04:40Z: Sol r1 (gpt-6.1-sol, high effort): 2 blockers, 4 should-fixes. All six fixed:
  - prep charge on timeouts;
  - `coarse_complete` = len(first) == plays;
  - prep timing on every exit;
  - durable `.started` markers;
  - sync no-contact ceiling;
  - charge and late-collector tests.
- 04:44Z: corpus qualification r2 passed. 125/125 for K4, K4S and K4Sl frozen-equal; anchor_x == anchor under
  injected cutoffs; zero budget → R3a. S-lite: 93 student defaults and 31 kept-after-complete-coarse on 1 thread; on 4
  threads it is rule-consistent.
- 04:47Z: Sol r2 found 2 blockers in the K4Sf timeout charge (double charge; cancellable steps progressing at fleet
  speed). Fixed with scaled internal deadlines for belief update and sample, plus per-step charges. Sync calls are now
  bounded with process-group kill.
- 04:48Z: unit tests r3: 42 passed. 05 sync puller restarted with the hardened version (pgid 1471676).
- 04:55Z: smoke r3 (prep and inference arms): 0 problems. Every K4Sf decision has sleep share = target ± 0.02 on all
  exit paths. No-deadline r3: K4, K4S, K4Sl, K4Sh and K4Sf give identical hashes on X0 and G1.
- 04:56Z: Sol r3: **no blockers**. Its should-fix (production-path timeout coverage) is answered by the smoke r3
  per-decision check; the nit is fixed.
- 04:56Z: freeze commit **de48533f** pushed. Before any reporting game, I added a spare-capacity **Phase D** (G indices
  540–1079, B's arms, dispatched last, stopped by time only). G reporting count is now 1080, re-audited clean.
  Worklists updated: 08 has 840 blocks, 03 has 570 (A+B) plus 870 (C+D). Deployed bytes verified equal on 03 and 08.
- 04:56:58Z: amendment **c1ddfacf** pushed, then **REPORTING launched**:
  - **rep08** on 127x08: 840 blocks, stop-at 09:15Z, child pgid 3513853;
  - **rep03** on 127x03: 570 blocks, stop-at 13:30Z, child pgid 294835. It chains to **rep03C** (C + D, 870 blocks)
    unless STOP is present.

  Both hosts run 12 disjoint 5-core masks (0–59) with no console users. The 05 sync pulls every 90 s.
- 04:58Z: 05 backstop `tools/vacate08.sh` (pgid 2451588) set up. At 09:12Z it touches STOP on 08, then polls until zero
  X4S2 processes and writes `logs/vacate08.jsonl`. It stops contacting 08 by 09:25Z.
- 05:23Z: rep03 at 53 blocks / 483 games; rep08 at 55 / 477. That is about 1,100 games/h per host. 108 blocks
  mirrored to 05. MemAvailable 118 GiB, owned PSS ≤3.5 GiB, no console users, no worker errors.
  ETA: 08 finishes A ~07:10Z and B-odd ~08:25Z, then D-odd until the 09:15Z stop. 03 finishes A+B ~08:20Z and C+D
  ~10:40Z.
- 05:51Z: rep03 at 124 blocks / 1,023 games; rep08 at 123 / 1,013. 236 blocks mirrored. MemAvailable 118 GiB, PSS
  ≤3.6 GiB, no errors, no console users. On schedule.
- 06:21Z: rep03 at 191 blocks / 1,580 games; rep08 at 189 / 1,558. 380 blocks mirrored. Healthy, with no errors and
  no console users. Phase A (300 blocks per host) ETA ~07:10Z.
- 06:50Z: rep03 at 263 blocks / 2,135 games; rep08 at 259 / 2,105. 521 blocks mirrored. Healthy. Phase A completes
  ~07:10Z.
- 07:19Z: **Phase A complete**: 600/600 X blocks (300 per host), 4,800 games, 0 interrupted. Reduced with `--pops X`,
  so G stays sealed until B/D end ([receipts/results-phaseA.md](receipts/results-phaseA.md)).
  - **K4Sh** (inference stressed 1/s), loss %: 21.7 / 23.2 / 24.0 / 25.5 at 160 / 140 / 120 / 100 ms. vs X4S K4:
    −6.2 [−10.3, −2.2], −24.2, −65.0, and at 100 ms vs K4-100 −74.5 pp. vs X4S K4S: +3.5 [0.0, 6.8], +1.0, −2.0 pp.
  - **K4Sf** (all prep stressed): 22.2 at 140 and 23.8 at 120. vs K4S: +0.0 and −2.2.
  - **Drift:** K4S-140r − X4S K4S-140 = −0.7 [−4.5, 3.2].
  - **K4-100:** 100.0%.
- 07:19Z: rep03 at 354 blocks and rep08 at 344, now in B. Healthy.
- 07:28Z: **coordinator update** received (logged at 07:30Z): perception A2 stage 2 started, so the 127x08 hard stop
  moves from 09:30Z to **12:30Z**; 03 stays at 13:30Z. A coordinator STOP on 08 still overrides everything.
  Actions:
  - the 05 backstop was replaced at 07:28:32Z (pgid 2781061): it touches STOP on 08 at 12:15Z, censuses to zero and
    makes no contact after 12:27Z;
  - sync restarted at 07:28:44Z (pgid 2803592) with 08 stopped-at 12:15Z and no contact after 12:27Z;
  - supervisor ceiling for 08 set to 12:25Z;
  - PLAN Amendment 1 added: phases E (threshold: K4/K4S/K4Sl-180, K4Sl-160) and F (guard decks at 120 ms) under
    plan-ext.json. A–D are unchanged, and rep08 still stops at 09:15Z, with its never-started blocks re-run in rep08L.
- 07:50Z: rep03 at 468 blocks / 3,263 games; rep08 at 459 / 3,212. 924 blocks mirrored. Healthy. Phase B ends
  ~08:20Z: 03 finishes rep03 and chains to rep03C.
- 08:17:25Z: rep03 exited cleanly: 570/570 blocks, rc 0, empty group. rep03C (C + D) started 08:17:5xZ.
- 08:20:40Z: **Phase B complete**: 540/540 G blocks (270 per host), 2,700 games, 0 interrupted. Reduced with
  `--g-max 540`, so D stays sealed ([receipts/results-phaseB.md](receipts/results-phaseB.md)). Loss %:

  | Arm | 200 ms | 140 ms |
  |---|---:|---:|
  | K4 | 23.7 | 58.7 |
  | K4S | 24.1 | 27.2 |
  | K4Sh | – | 24.3 |

  Contrasts:
  - K4S − K4: 200 ms +0.4 [−2.4, 3.1]; 140 ms −31.5 [−36.7, −26.3];
  - K4Sh-140 − K4-140: −34.4;
  - K4S-140 − K4-200: +3.5 [−1.3, 8.1].
- 08:52Z: rep03C at 328/870 blocks (C has 600 two-game blocks, then D-even); rep08 at 684/840 (in D-odd). Healthy.
  At 09:15Z rep08 stops; chain08 then runs rep08L (never-started D-odd), then rep08EF.
- 09:15:08Z: rep08 hit its planned stop-at. Supervisor exit at 09:15:09Z with an empty group. 772 blocks complete; the
  12 interrupted D-odd blocks (marker, no proof) are retired. leftover.py found 56 never-started D-odd blocks, and
  **rep08L** started on them at ~09:15:50Z. rep08EF (E-odd then F-odd) follows, to 12:15Z.
- 09:31:49Z: rep08L exited cleanly: 56/56 blocks, rc 0, empty group. D-odd is complete except the 12 retired blocks.
  **rep08EF** (E-odd, then F-odd; plan-ext.json) started 09:31:59Z, stop-at 12:15Z.
- 09:41Z: **Phase C complete**: 600/600 X blocks in rep03C, 0 interrupted. Reduced X only (A + C); E stays sealed
  ([receipts/results-phaseAC.md](receipts/results-phaseAC.md)). Loss %: K4Sl-200 20.8, K4Sl-140 21.8.
  - K4Sl-200 − K4-200: +2.3 [−0.3, 5.0].
  - K4Sl-200 − K4S-200: +0.2 [−1.8, 2.2].
  - K4Sl-140 − K4-140: −25.5.
  - K4Sl-140 − K4S-140: −0.3.

  So the lite rule does not remove the ~+2 pp at 200 ms. At 200 ms, student defaults are 0.5% (lite) vs 0.8% (full)
  of decisions, so the default rule is unlikely to be the source. rep03C is in D-even (72/270, ETA ~10:35Z), then
  rep03EF. rep08EF started E-odd.
- 10:12Z: rep03C at 787/870 blocks (D-even ETA ~10:35Z); rep08EF at 187 blocks / 766 games (E-odd ETA ~10:35Z, then
  F-odd to ~12:05Z). 03 projection: E-even ~10:35–11:40Z, F-even ~11:40–13:10Z. Healthy, with no console users.
- 10:34:00Z: rep03C exited cleanly: 870/870 blocks, rc 0, empty group. rep03EF (E-even, then F-even; plan-ext)
  started 10:34:25Z, stop-at 13:30Z.
- 10:35Z: **Phase D complete**. G population (B + D) has 1,068 seeds; 12 D blocks were interrupted and retired. F
  stays sealed ([receipts/results-phaseBD.md](receipts/results-phaseBD.md)). Loss %:

  | Arm | 200 ms | 140 ms |
  |---|---:|---:|
  | K4 | 26.7 | 58.6 |
  | K4S | 26.4 | 27.2 |
  | K4Sh | – | 23.5 |

  Contrasts:
  - K4S − K4: 200 ms −0.3 [−2.2, 1.7]; 140 ms −31.4 [−34.9, −27.6];
  - K4S-140 − K4-200: +0.6 [−2.8, 3.9];
  - K4Sh-140 − K4S-140: −3.7 [−6.9, −0.6] (unadjusted).
- 10:41Z: rep08EF finished E-odd (300/300 X blocks) and is now in F-odd (342 blocks total). rep03EF at 28 blocks
  (E-even; ETA ~11:40Z). Healthy.
- 11:04Z: rep03EF at 140/300 E-even blocks. rep08EF at 189 F-odd blocks (~330 blocks/h, so it should cover most of
  F-odd's 540 by 12:15Z). Healthy.
- 11:33Z: rep03EF at 279 blocks (E-even 280/300; E completes ~11:40Z). rep08EF F-odd at 369/540. Healthy.
- 11:36:50Z: **Phase E complete**: 600/600 X blocks (300 per host), 0 interrupted. Reduced X (A + C + E); F stays
  sealed ([receipts/results-phaseACE.md](receipts/results-phaseACE.md)). Loss % at 180 ms: K4 19.3, K4S 17.2,
  K4Sl 18.8; K4Sl-160 20.0.
  - K4S-180 − K4-180: −2.2 [−5.2, 0.8].
  - K4-180 − K4-200: +0.8 [−2.5, 4.2].
  - K4-180 − K4-160: −8.5 [−12.5, −4.3].
  - K4Sl-160 − K4-160: −7.8 [−11.5, −4.2].
  - K4Sl-160 − K4S-160: +1.8 [−1.2, 4.8].

  K4 holds to 0.9× and breaks between 0.9× and 0.8×. The S-default sign flips between 1.0× and 0.9×.
- 12:00:00Z: rep08EF exited cleanly: 840/840 blocks (E-odd 300, F-odd 540), rc 0, empty group. **127x08 had zero
  X4S2 processes at 12:00:53Z**; chain08 is done. The 05 backstop still touches STOP on 08 at 12:15Z and records the
  vacancy census. rep03EF at 451 blocks: E-even done, F-even 151/540, ETA ~13:10Z (stop-at 13:30Z).
- 12:15:16Z: 05 backstop touched STOP on 127x08. The census at 12:15:16Z found **0 X4S2 processes: VACANT**
  ([receipts/vacate08.jsonl](receipts/vacate08.jsonl)). The remaining sdicks02 processes on 08 belong to other
  threads (tailscaled, v4 validation-cache service) and were not touched.
- 12:16:12Z: sync did its final pull of 08 and retired it. 05 makes no further contact with 127x08.
- 12:41Z: rep03EF at 709/840 blocks (F-even 409/540); ETA ~13:05Z, before the 13:30Z stop. Healthy.
- 13:01:01Z: rep03EF exited cleanly: 840/840 blocks (E-even 300, F-even 540), rc 0, empty group. 127x03 had 0 X4S2
  processes at 13:01:23Z. STOP placed on 03 at 13:01Z; sync retired 03 at 13:01:41Z and exited (both hosts retired).
  The 05 backstop and sync have exited.
- 13:02Z: **final reduction**: 16,980 new games (3,948 blocks, 12 retired) plus 5,400 paired X4S games.
  - **F** (guard decks, 120 ms), loss %: K4 92.1, K4S 22.8 (−69.4 [−72.2, −66.3]), K4Sh 21.0.
  - **Pooled X + G:** K4S − K4 at 200 ms = +0.6 [−0.8, 2.2] over 1,668 seeds.
  - RESULTS.md written. **X4S2 complete.** No X4S2 processes remain on 03, 08 or 05.
