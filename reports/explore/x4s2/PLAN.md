# X4S2: stress test of the X4S student cutoff default (exploration, NEVER ADOPTABLE)

Written 2026-10-11T04:33Z by the X4S2 worker on 127x05. The coordinator (thread 0523ae6f) assigned this at about 04:30Z.

**Status: exploration only, NEVER ADOPTABLE.** R3a stays killed under its R3 Stage 1 gates. Nothing here admits any
arm to live play. The output is evidence for whether to preregister a K4+S-default Mac tier.

## Question
X4S ([RESULTS](../x4s/RESULTS.md)) found that making the R3a student the cutoff default (S-default) rescues
4-thread anytime W (K4) at shorter budgets, measured as loss vs v1, K4 → K4S:

| Budget | K4 | K4S |
|---|---:|---:|
| 160 ms | 27.8% | 18.2% |
| 140 ms | 47.3% | 22.2% |
| 120 ms | 89.0% | 26.0% |

Three caveats remain:

1. Student inference was charged at fleet speed inside a shorter budget, which flatters K4S.
2. There was only one opponent and five decks.
3. At 200 ms, S-default may cost about +2 pp.

X4S2 tests each caveat, in priority order.

## Arms ([plan.json](plan.json)): all 4 threads, coarse horizon 160, opponent = the exact X4S/S1 v1 policy

Every arm runs the K4 kernel from [anchor_x.py](anchor_x.py). It is S1's `anchor.py` with one change: it also
records `coarse_complete`, `coarse_scored` and `plays` in `deadline_stats`. Qualification proves its actions and
scores are identical to S1's. Here s = budget/200 and `inference_scale` = 1/s.

| Phase | Population | Arm | Rule | Scaling |
|---|---|---|---|---|
| **A** (priority 1) | X: X4S's five decks and its **same 600 reporting seeds**, paired with the X4S games | K4Sh-160/140/120/100 | S-default | **inference**: after each charged search-seat policy poll, sleep (1/s − 1) × measured poll wall time, inside the timer |
| A | X | K4Sf-140, K4Sf-120 | S-default | **prep**: sleep (1/s − 1) × the measured wall time of *all* pre-scoring decision work (observation, packet, poll, belief update and candidates; then belief sample and root), inside the timer |
| A | X | K4S-140r | S-default | none: replicates X4S K4S-140 to measure run-to-run drift |
| A | X | K4-100 | frozen K4 (WAIT default) | none |
| **B** (priority 2) | G: own deck ∈ the three L2-v4 decks (Hog 2.6, X-Bow cycle, Royal Hogs spawners); opponent ∈ the three held-out TIERS guard decks (Hog EQ, Goblinstein Royal Hogs, ArcherQueen Royal Delivery); 18 cells (seat i%2, own (i//2)%3, opponent (i//6)%3); **fresh seeds** | K4-200, K4S-200, K4-140, K4S-140, K4Sh-140 | as named | K4Sh: inference |
| **D** (spare capacity, declared at 04:57Z before any reporting game) | G, indices 540–1079 (fresh) | same five arms as B | as B | as B; dispatched last, stopped by time only, pooled with B as the G population |
| **C** (priority 3) | X, same 600 seeds | K4Sl-200, K4Sl-140 | **S-lite**: the student play is used only if the deadline hit, no refined play completed, **and the coarse scan was incomplete**; otherwise the frozen choice stands | none |

### What the scaling arms measure (finding during qualification, 04:38Z)
Smoke measured the charged search-seat poll at about 10 ms. The pre-scoring decision work
(observation → candidates → sample → root) is about 38 ms at fleet speed.

Under a **uniform** slow core of speed s, all work W inside the timer (in fleet-ms) takes W/s real ms. It must fit
in 200 − 8 real ms, so W ≤ 192·s. X4S's budget equivalence at fleet speed gives W ≤ 200·s − 8. This is the same
constraint up to the reserve, which differs by 8(1−s) ≤ 4 ms (at 100 ms). **Budget equivalence therefore already charges
inference and preparation at 1/s.** X4S caveat 1 ("inference charged at fleet speed flatters K4S") does not hold for
uniform slowdown. The measured ~10 ms poll already takes 5.0/6.3/7.1/8.3/10% of the 200/160/140/120/100 ms
budgets in the unscaled arms.

So K4Sh and K4Sf are **stress tests, not corrections**:
- **K4Sh** models a Mac whose inference is a further 1/s slower *relative to its search*, i.e. inference at speed s²
  (0.64× at the 160 ms point and 0.36× at 120 ms).
- **K4Sf** models all Python/preparation work being relatively 1/s slower than native rollouts. It adds about 20–29 ms
  at 140/120 ms.

If S-default still rescues K4 under these arms, the X4S conclusion is robust to non-uniform slowdowns of the student
and of preparation. The assignment's arms run as specified; only their interpretation changes. What budget
equivalence does not capture:
- the 8 ms real reserve;
- overrun lateness, which is under-penalized by the factor s (overruns are about 0.1% of decisions).

### Decisions recorded
- **Scaling shape.** The assignment asks for student inference scaled by 1/s. K4Sh does exactly that.
  - K4Sf extends the same relative-slowdown stress to all preparation work (observation, belief and candidates),
    at 140 and 120 ms only.
  - Rollouts are already scaled by the shorter budget.
  - Not scaled: the opponent, which has no deadline, and the X4S K4 references' own v1 poll. So the K4 references
    are flattered, which makes the K4Sh − K4 contrasts **conservative for S**.
  - In K4Sf:
    - pre-belief work (observation, packet, poll) is charged before the belief step;
    - the cancellable belief update and belief sample get the internal deadline t0 + (cutoff − t0)·s, so they do only
      the work a 1/scale core could do before the cutoff;
    - their actual duration, and that of candidates and root, is then charged at (1/s − 1)×, on success and on
      timeout alike.
  - The sleep is wall time with the core idle. The game's 5-core slot is dedicated, so this only shifts the deadline,
    as slower hardware would.
- **Pairing.** Phases A and C reuse the X4S reporting seeds 4503604807370496 + [0, 600) on the identical harness
  path. Contrasts against X4S arms (K4-b, K4S-b, K4-200) are paired by seed but come from a different run.
  K4S-140r measures that cross-run drift directly.
- **Guard decks.** The assignment's "L2 deck set" is used as in the TIERS r3 draft guard population: L2-v4 own decks
  (in R3a's training distribution) against held-out human opponent decks (in no R1 training matchup). The decks are
  transcribed into plan.json, and run.py asserts that every guard deck is in the pinned catalogue
  (sha256 80de4afb…). I did **not** run or touch `reports/explore/t1/select_guard_decks.py`; the decks are copied
  from the r3 draft text.
- **No K4h arms.** I did not add honest-scaled K4 arms, because K4 needs no student and would only get worse.

## Harness
This is X4S's [run.py](run.py), copied rather than edited. The following are all unchanged:
- observation;
- exact resumable belief;
- GC deferral;
- honest lateness, in which each positive overrun delays by ceil(overrun × 20) ticks;
- the 8 ms return reserve;
- d = 27 and capacity 1;
- alternating seats;
- the cached-R3a poll, which is one forward per poll.

The deltas are:
- every K4 kernel is anchor_x;
- `scale_mode` and `inference_scale` per arm;
- a worklist of `(population, index, arms)` blocks;
- the guard population;
- the `K4-anytime-slite` kernel;
- per-decision `poll_seconds`, `scale_sleep_seconds` and `prep_seconds`.

Every game records `threads`, `coarse_horizon`, `budget_ms`, `default_source`, `inference_scale`, `scale_mode`,
`population`, `kernel` and the total sleep. The runtime is the X4S runtime (repo, native 44874fd6, v1 d77005d5,
R3a 37509a43), copied locally on each host, with git `reports/explore/x4s2` overlaid.

## Seeds ([seed-audit.json](seed-audit.json))
- **X population:** a declared paired reuse of X4S reporting 4503604807370496 + [0, 600).
- **Fresh bank 2^52 + [5.48e9, 5.58e9):**
  - G reporting 4503605107370496 + [0, 1080) (B: 0–539, D: 540–1079; re-audited at 04:56Z);
  - smoke 4503605117370496 + [0, 8);
  - qualification 4503605127370496 + [0, 8).
- The audit found no overlap with 119 declared prior ranges at helper offsets {0, 13, 100000–100003, 271828–271829}.
- A raw scan of 6,496 repo seed literals finds none in the window. The nearest are 4503604907370496 (X4S's
  reservation end) and 4503609917370496.

## Compute, schedule and stops
- **Where and how:** 127x03 and 127x08 only, under `nice -n 19`, SCHED_OTHER, CUDA off, caches under /mpac.
- **Slots:** 12 disjoint 5-physical-core slots on cores 0–59, so 60 hardware threads (≤96). SMT siblings are left
  free, and the supervisor runs on core 62. A host with a console user gets 10 slots.
- **Supervisor:** a detached (setsid) [supervisor](supervise.py), copied from X4S, polls
  `/mpac/sdicks02/jobs/clasher/x4s2-20261011/STOP` every ≤10 s. It also enforces a per-host `--stop-at`, capped in
  code (08 ≤ 09:25Z, 03 ≤ 13:30Z), a 24 GiB MemAvailable floor and a 50 GiB owned-PSS cap. On a stop it TERMs and
  then KILLs only its own process group, verifies the group is empty, and exits within about 2 minutes.
- **Sync:** [sync.py](sync.py) on 05 pulls finished games every 90 s into
  `/mpac/sdicks02/jobs/clasher/x4s2-20261011/mirror/`.
- **127x08**, supervisor stop-at 09:15Z (drain ≤2 min; sync stops contacting 08 at 09:27Z):
  1. A indices with (i//50) odd: 300 blocks × 8 games;
  2. then B indices with (i//18) odd, in increasing order;
  3. then D indices with (i//18) odd.

  At about 92 games per slot-hour, 08 should finish A by about 08:30Z and part of B by 09:15Z. Unfinished blocks are
  excluded, and 08 is verified **empty** by 09:30Z.
- **127x03**, stop-at 13:30Z:
  1. A with (i//50) even;
  2. B with (i//18) even;
  3. C, all 600;
  4. then D indices with (i//18) even.

  Then, in a new output directory, any B blocks that 08 never started.
- **Interrupted blocks:** a durable `.started` marker is written before a block's first game. A block with a marker
  but no proof is excluded, and that (population, index, phase) is retired and never re-run. Only blocks without a
  marker are re-dispatched.

## Qualification (all before any reporting game)
1. **Unit tests.** 42 pass:
   - [test_sdefault.py](test_sdefault.py): full and lite rules on the injected clock, including lite keeping the wait
     after a complete coarse scan and using the student when the coarse scan is incomplete;
   - a 4-thread late-collector regression for `coarse_complete` (= every play has a pre-cutoff coarse score);
   - [test_charge.py](test_charge.py): the scaling charger, the scaled internal deadline for cancellable steps,
     and a mirrored prep sequence;
   - S1's anchor tests run against anchor_x;
   - S1's latency tests.
2. **The 125 frozen states ([qualify.py](qualify.py)):**
   - with no deadline, anchor_x K4, K4S and K4Sl each reproduce the frozen screen8 action, candidates and scores,
     and each other;
   - anchor_x equals S1 anchor under injected-clock cutoffs (1 thread);
   - a zero budget returns R3a;
   - under injected cutoffs, the S-default and S-lite rules are each checked, including S-lite with the 4-thread
     collector;
   - the root is immutable.
3. **No-deadline games** on qualification seeds (X index 0, G index 1): K4, K4S, K4Sl, K4Sh (inference scale 2) and
   K4Sf (prep scale 1.67) must produce **identical command hashes**.
4. **Smoke on 08** (4 A, 6 B and 4 C blocks; excluded):
   - metadata;
   - scale charge ≈ (1/s − 1) × poll time;
   - guard-deck card support, with no unknown tokens;
   - throughput.
   Smoke r3 also checks the production prep path: every K4Sf decision, scored or exiting on a belief, sample or
   pre-scoring cutoff, has sleep/prep = (1/s − 1)/(1/s) ± 0.02
   ([receipt](receipts/prep-charge-production-check.txt)).
5. **STOP test on 08** with the new supervisor: exit with zero processes left.
6. **Sol review** (gpt-6.1-sol, high effort) of run.py, anchor_x, sdefault, the supervisor, sync and qualification.
   Findings are fixed before launch.
7. **Freeze commit** of the plan, harness, seed audit and qualification receipts before the first reporting game.

## Analysis
- **Bootstrap:** 5,000 paired-seed bootstrap resamples (RNG 2026101105) per population; percentile 95% CIs,
  unadjusted. Only seeds whose new block completed count, and for X they need all nine X4S arms too.
- **Reported:**
  - loss per arm;
  - cutoff rate, student-default rate, coarse-complete-at-cutoff rate, overrun rate and fallback rate;
  - mean poll, scale-sleep and prep ms;
  - latency quantiles.
- **Readings (descriptive):**
  - **Survives honest scaling** at b: upper CI(K4Sh-b − X4S K4-b) < 0. The cost of honesty is K4Sh-b − X4S K4S-b,
    read against the K4S-140r − K4S-140 drift.
  - **Holds** at b: upper CI(K4Sh-b − X4S K4-200) ≤ +5 pp.
  - **Generalizes:** on the guard decks, upper CI(K4S-140 − K4-140) < 0 and upper CI(K4Sh-140 − K4-140) < 0. The
    200 ms cost on the guard decks is K4S-200 − K4-200.
  - **Lite:** K4Sl-200 − K4-200 and K4Sl-200 − K4S-200 for the full-speed cost; K4Sl-140 − K4S-140 for whether the
    rescue survives.
- **Sealing:** reporting games are not opened for outcomes until their phase ends or stops. Only progress counts are
  read during the run.
