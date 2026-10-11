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
