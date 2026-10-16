# Noise-robust decisions: results (bot lead worker, exploration)

Status: r4 DONE. Revealed-set fix: screen +0.022 (K4L, n=600); fresh bank NOT CONFIRMED +0.013 [−0.003, +0.028] (section 6b); LIVE LEAD checks section 7. r5: three reviewed defects fixed (section 9), awaiting re-review. Design: DESIGN.md.
Log: PROGRESS.md.

## 1. Screens (ours engine, HEADLINE cases 0–299, PERC-emp = empirical-val.json, unit threshold 0.4)

**Screening player.**
- `LIVED-K4L-R-gs-rw-fc` is the deterministic twin of LIVE-K4L-R-gs-rw-fc-w200-t4-p4: unbounded, serial.
- Every arm is paired per case with `PERC-emp:` on the same player. The perfect-sight column pairs with the player
  without PERC.

(tables filled from bot/noise/report.py at the end of each wave)

## 2. Diagnostics

- **Raw perceived units vs truth** (60 game-seats, cases 1000–1029; `bot/noise/tune.py`):
  - recall .69, i.e. 1.6 missing per poll, mostly swarm bodies;
  - 0.10 phantoms per poll;
  - 2% wrong body.
- **Opponent elixir in the K4L root** (bel1): mean error +1.7–1.9 vs R3a, −0.3 to −1.5 vs v1; mean |error|
  1.8–2.5.
- **Oracle decomposition** (orc1, 28 games, 3,183 K4L decisions). Agreement with the true-sight twin's action
  (base 61.9%):
  - true units +5.5 pp;
  - true opponent elixir +1.1 pp;
  - true opponent belief sample +1.9 pp;
  - both +16.4 pp.

## 3. Proposed hooks for the LIVE LEAD

(see end of run)

## 4. Fresh bank (PRE-REGISTERED 2026-10-15T18:14:25Z, before any game)

**Bank and stats.**
- BASE = **919328127031168**, from `int.from_bytes(os.urandom(6), 'big') << 4`, drawn 2026-10-15T18:14:25Z.
- Cases: x4s_setup(i, BASE), i = 0..599, vs R3a and vs v1. Engine: ours (bot/noise/run.py, the HEADLINE protocol).
- Noise: **`PERC-emp-sr1u50`**, the deployed reference per the LIVE LEAD 16:39Z.
  - stats bot/live/empirical-val-r1u50.json, sha256 c84464ba28b5504cb28c9f3bd536b17792656c5677b9c6fd506ee7d9291442cf
  - perc.py 6e1656f1…, empirical.py 94df10a8… (main 5c1d37e7)
  - runtime pins r1-total

**Arms.** These are deterministic twins: no deadline, so every search completes, as on the Mac, where the 200 ms
deadline does not bind for K4L.
- **C** = `LIVEMR-K2-D`: K4L-R-gs-rw with K=2 learned samples, sample 1 from its own determinized root (an
  independent opponent belief sample).
- **B** = `LIVEMR-K1`: K4L-R-gs-rw, bit-identical to LIVED-K4L-R-gs-rw-fc on the screen.
- The pooled live form `LIVE-MRK<n>-D-w<ms>-t4-p4` is bit-identical to its serial twin when the deadline does not
  bind (command hash 4a18597e…, K3-D, case 1500).
- **Noisy:** PERC-emp-sr1u50:C vs PERC-emp-sr1u50:B.
- **Perfect sight:** C vs B.

**Why K2-D.** It is the only screen variant with a positive point estimate on every noise version and opponent:

| screen | Δ(C−B) |
|---|---|
| PERC-emp R3a | +0.076 [−0.015, +0.168] (n=131) |
| sr1u50 R3a | +0.027 [−0.042, +0.092] (n=261) |
| sr1u50 v1 | +0.014 [−0.041, +0.064] (n=295) |
| PERC-emp v1 | +0.000 (n=170) |

It was selected among ~6 multi-root variants and ~5 filters, so the screen carries a winner's curse.

**Decision rule.**
1. **Primary:** the pooled (R3a + v1, 1,200 paired cases) Δ = mean score(C) − score(B) under PERC-emp-sr1u50,
   paired by (opponent, index), with a 95% bootstrap CI (4000 resamples, seed 0).
   - **CONFIRMED** iff the CI lower bound > 0. Otherwise NOT CONFIRMED (null or negative).
   - Δ vs R3a alone (the coordinator's primary metric) is reported with its CI, but is not the claim test.
2. **Perfect sight:** the pooled Δ(C−B) is reported with its CI. Adoption needs a point estimate ≥ −0.01.
3. **Timing** (separate run): `LIVE-MRK2-D-w200-t4-p4` and `LIVE-K4L-R-gs-rw-fc-w200-t4-p4` on quiet pinned 4-core
   groups on 03 (SMT siblings idle). Adoption needs fleet p99 ≤ 400 ms. p50/p95/p99, the default share and the Mac
   projection (÷2.8) are reported.
4. **Also reported from the same games:** the K4L gap on the fresh bank, PERC-emp-sr1u50:B vs B.

## 4b. Fresh-bank verdict (computed by the bot lead at 2026-10-15T20:31Z; the worker was cut off by a T3 restart)

Data: 127x03:/mpac/sdicks02/jobs/clasher/bot-noise/fb1/{a,b,d}, cases 0–599 vs R3a and v1, 4,800 games, 0 errors,
0 duplicates. Bootstrap: 4,000 resamples, seed 0, paired by (opponent, index), as pre-registered.

| comparison | pooled (R3a + v1) | R3a | v1 |
|---|---|---|---|
| **noisy (sr1u50) C − B, primary** | **+0.015 [−0.013, +0.042]** | +0.033 [−0.008, +0.075] | −0.003 [−0.038, +0.032] |
| perfect sight C − B | +0.008 [−0.013, +0.028] | 0.000 [−0.035, +0.033] | +0.015 [−0.008, +0.038] |

Win rates (n = 600 each): noisy B 0.630 / 0.880, noisy C 0.663 / 0.877; perfect sight B 0.832 / 0.945, C 0.832 / 0.960.

**Verdict: NOT CONFIRMED.** The primary CI includes 0, so LIVEMR-K2-D is not adopted and the timing run is moot.

**Noise gap of the live search bot on this unselected bank:** PERC-emp-sr1u50:K1 − K1 = **−0.202 [−0.245, −0.162]** vs
R3a and **−0.065 [−0.095, −0.035]** vs v1. This is the best estimate of what deployed perception costs K4L.

## 5. Evidence-ranked opponent revealed set (r3/r4)

**Problem** (aud1, HEADLINE 0–99, 194 games): the deployed translator's opponent card set is first-come, the first
8 distinct cards of accepted plays. Under sr1u50 it holds a card the opponent never played in 164/194 games. A true
card is then locked out (its plays and units are dropped) in 124/194 games.

**Fix:** bot/noise/livefix/revealed.py `RevealedSet`. It is one object for play acceptance and the board sanitizer,
and it evicts weakly evidenced cards. Proposed bot/live patch: reports/bot/noise-robust/revealed-set.patch.

### 5a. Screen scr1 (K4L twin `LIVED-K4L-R-gs-rw-fc`)

HEADLINE cases 0–299 × R3a/v1; 3,000 games, 0 errors. Each arm is paired with the baseline
`AUD:PERC-emp-sr1u50` by (opponent, index): 95% bootstrap, 4000 resamples, seed 0. The arms ran r3's code (see 5d).

| arm − baseline | R3a (n=300) | v1 (n=300) | pooled (n=600) |
|---|---|---|---|
| **fix** PERCRe2b10 | +0.013 [−0.017, +0.047] | +0.030 [+0.000, +0.060] | **+0.022 [+0.000, +0.043]** |
| oracle revealed set (diagnostic, reads truth) | +0.020 [−0.040, +0.080] | +0.043 [−0.003, +0.090] | +0.032 [−0.005, +0.070] |
| reseeded baseline PERCs1 (noise-only control) | +0.007 [−0.057, +0.077] | −0.013 [−0.063, +0.037] | −0.003 [−0.043, +0.037] |
| perfect sight | +0.203 [+0.143, +0.267] | +0.083 [+0.040, +0.130] | +0.143 [+0.107, +0.182] |

Mean score of the baseline: 0.617 (R3a), 0.857 (v1).

**Translator audit per game** (baseline → fix):
- games with a wrong card in the final set: R3a 0.87 → 0.76, v1 0.78 → 0.55;
- true opponent unit-records dropped by the sanitizer: R3a 17 → 1, v1 40 → 2;
- true cards missing from the final set: R3a 0.67 → 0.44, v1 0.97 → 0.62.

The oracle revealed set is worth only +0.032 of the +0.143 perfect-sight gap, so the lock-out is a minor part of
the noise gap on this screen. The fix recovers about 2/3 of the oracle's value.

### 5b. Clean-channel no-op check (floorchk)

Setup: `-xunits-xev-xhud`, cases 0–14 × R3a/v1. Fix vs baseline: **30/30 identical command hashes**, Δ 0.000.

### 5c. Fast tier (scr1f, `LIVE-fast-it5s2`)

HEADLINE cases 0–299 × R3a/v1: 0–149 on 03 and 150–299 on 04 (04 dir scr1f-hi04), 2,400 games, 0 errors. The 115
overlapping games (03 ran slightly past 149) have identical command hashes and scores on both hosts. Same pairing
and bootstrap as 5a.

| arm − baseline | R3a (n=300) | v1 (n=300) | pooled (n=600) |
|---|---|---|---|
| **fix** PERCRe2b10 | +0.010 [−0.020, +0.043] | +0.020 [−0.010, +0.053] | **+0.015 [−0.007, +0.037]** |
| oracle revealed set | +0.010 [−0.047, +0.063] | +0.027 [−0.020, +0.073] | +0.018 [−0.018, +0.055] |
| perfect sight | +0.080 [+0.020, +0.140] | +0.073 [+0.023, +0.123] | +0.077 [+0.037, +0.115] |

Mean score of the baseline: 0.580 (R3a), 0.810 (v1).

**Translator audit** (baseline → fix):
- true opponent unit-records dropped: R3a 23 → 1, v1 49 → 2 per game;
- games with a wrong card: R3a 0.87 → 0.72, v1 0.79 → 0.51.

### 5d. Defect fixed after the screen (r4)

An eviction rebuilt the opponent mirror up to the record tick. A lagged opponent event later in the same record
then raised 'public time moved backwards'. PercPlayer turned that into a WAIT and lost the record's remaining
events. A live session would have got the exception. Fix: rebuild up to the stream guard's time. Regression tests
fail on the old code and pass on the fix. The fresh bank (section 6) runs the fixed code.

## 6. Fresh bank for the revealed-set fix (PRE-REGISTERED 2026-10-15T23:10:27Z, before any game)

**Bank and stats.**
- BASE = **4405930208510496**, from `int.from_bytes(os.urandom(6), 'big') << 4`, drawn 2026-10-15T23:10:27Z. It is
  not 919328127031168 (section 4).
- Cases: x4s_setup(i, BASE), i = 0..599, vs R3a and vs v1, through bot/noise/run.py on the ours engine.
- Noise: `PERC-emp-sr1u50`, stats bot/live/empirical-val-r1u50.json, sha256
  c84464ba28b5504cb28c9f3bd536b17792656c5677b9c6fd506ee7d9291442cf.
- Runtime pins: r1-total.

**Code** (main at this commit; sha256):

| file | sha256 |
|---|---|
| bot/noise/livefix/revealed.py | 63e2277a2ebff25c3363833a3d517b2f094d428f6df6ae69029ba250f5fd54dc |
| bot/noise/livefix/resync.py | 2e6a697a895d7621fe4a94736199b5eb7c2167d620657191daa0cfeca34aed14 |
| bot/noise/livefix/translate.py | c071f732e433ac088b4cc9eeceb5fcefca6a14e63d1fce530a7cef968d4c5e75 |
| bot/noise/revfix.py | b2edfe8a03227c2cf5927e4304670e0f432db6a216784749ee42f86f84039f2e |
| bot/noise/audit.py | dc3ce86d67d872d82f8964a129e7f856d9857f45564fadc89983d65fcd08af52 |
| bot/live/perc.py | 6e1656f1… |
| bot/live/empirical.py | 94df10a8… |
| bot/live/translate.py | 5361deb0… |
| bot/live/resync.py | 77e177f8… |
| proposal patch reports/bot/noise-robust/revealed-set.patch | 90835df8a1e3cdb6250bf1c61b20c1142653946f8392384b6c72830299f7653a |

**Arms** (same noise stream, same player):
- **F** = `AUD:PERCRe2b10-emp-sr1u50:LIVED-K4L-R-gs-rw-fc` (the fix);
- **B** = `AUD:PERC-emp-sr1u50:LIVED-K4L-R-gs-rw-fc` (the deployed translator).

AUD is a read-only audit wrapper.

**Decision rule.**
1. **Primary:** the pooled Δ = mean score(F) − score(B) over R3a + v1, 600 cases each, paired by (opponent, index),
   with a 95% bootstrap CI (4000 resamples, seed 0; bot/noise/report.py pooled row).
   - **CONFIRMED** iff the CI lower bound > 0. Otherwise NOT CONFIRMED.
2. **Also reported:** Δ vs R3a alone, with its CI (LIVE LEAD requirement d), and Δ vs v1 alone. Neither is the
   claim test.
3. **Also reported:** perc_errors per arm (it must be 0 for F), evictions, and dropped true unit-records.

**Hosts:** cases 0–439 run on 03 (80 workers), 440–599 on 04 (`bot/exit/cpu_job.sh 30`). The results are merged by
(arm, opponent, index).

## 6b. Fresh-bank verdict (computed 2026-10-16T00:10Z by the r4 worker)

**Data:** 127x03:/mpac/sdicks02/jobs/clasher/bot-noise/{fb2 (cases 0–439), fb2-hi03 (520–599), fb2-hi04 (440–519,
copied from 04)}.
- 2,400 games, 0 errors, 0 duplicate keys.
- Every chunk ran main 6f85e8df (identical code.sha256).

**Analysis:** `bot.noise.report fb2,fb2-hi03,fb2-hi04 --ref AUD:PERC-emp-sr1u50:LIVED-K4L-R-gs-rw-fc`, the
pre-registered bootstrap. Output: fb2/verdict-r4.json.

| F − B (fix − deployed translator), sr1u50 | Δ [95% CI] | n |
|---|---|---|
| **pooled R3a + v1 (primary)** | **+0.013 [−0.003, +0.028]** | 1200 |
| R3a alone (LIVE LEAD requirement d) | +0.017 [−0.008, +0.042] | 600 |
| v1 alone | +0.008 [−0.007, +0.025] | 600 |

Mean scores: B 0.633 / 0.873 and F 0.650 / 0.882 (R3a / v1). Decision timing is unchanged: p50/p95/p99 is
358/767/946 ms for F vs 354/750/928 ms for B (R3a).

**Verdict: NOT CONFIRMED.** The CI lower bound is −0.003, not > 0. The point estimate is positive and consistent
with the screen (+0.022), and the fix never hurt measurably. But a gain of ~+0.01–0.02 is below what 1,200 pairs
can confirm.

**Mechanism** (audit, B → F, per game):
- true opponent unit-records dropped by the sanitizer: R3a 24 → 1, v1 36 → 2;
- true cards missing from the final set: R3a 0.63 → 0.32, v1 0.93 → 0.52.

F made 827 evictions: 760 removed a card the opponent never played, and 519 admitted a true card.
perc_errors = 0 in both arms, which confirms the r4 rebuild fix.

The translator problem is real and the fix largely repairs it. The win-rate value is small because the oracle
revealed set itself is worth only ~+0.03 (screen 5a). Most of the noise gap (perfect sight +0.14) is elsewhere: unit
positions, missed units, and opponent belief/elixir (section 2, orc5).

## 7. LIVE LEAD acceptance checks for reports/bot/noise-robust/revealed-set.patch

**(a) Evidence comes only from public perception: MET.**
- RevealedSet's inputs are the perceived opponent play events (`accept_events` → `reject`/`allows`/`victim`) and
  the card names of perceived board units (`assign` → `observe_board`). Unit scores are not used.
- `spawns` uses public card data only.
- Test `test_fair_information_invariance` injects opponent-private truth into every record: deck, hand, elixir, true
  card ids of units and events, and the true revealed set. Packet arrays, events, public rows, members and every
  counter stay identical.
- The PERCRoracle arm reads truth, but it is a harness diagnostic and is not in the patch.

**(b) Play acceptance and the board sanitizer share one object: MET.**
- `LiveTranslator.revealed` is the only RevealedSet.
- `accept_events` gates a 9th card with `self.revealed.allows(name)`, and `ninth_enemy_card_dropped` now counts
  there.
- `board_card_ok` uses `self.revealed.allows(card)` / `members()`.
- Test `test_board_and_sanitizer_share_the_set`: a board-admitted card is kept by the sanitizer, and the evicted card
  is rejected for both plays and units.

**(c) Eviction re-syncs the cycle tracker with replayed plays: MET (after the r4 fix).**
- `ResyncMixin._admit` → `_rebuild` re-runs the stream guard and resync over the perceived opponent plays. W's plays
  are removed and X's rejected ones added.
- It then rewrites `public_events`, `plays[1]`, `events` and the opponent mirror, and sets `resynced`. That makes
  `restart_if_resynced` rebuild the player's D1/belief trackers.
- Test `test_repeated_plays_evict_the_weak_card_and_resync` checks that a fresh replay of the public history equals
  the mirror.
- r4 fixed a defect here (5d): the mirror ran ahead of lagged events and raised. The new tests
  `test_lagged_play_eviction_keeps_time_monotone` and `test_board_eviction_then_lagged_event_in_the_same_record`
  pass, and a mutation check confirms both fail on the old code.
- On the patched bot/live: test_revealed 11/11, LIVE suite 52 passed / 2 skipped / 3 deselected. The deselected
  tests fail identically on unpatched main: a wall-clock test at load 100, and two missing `labels_v4`.

**(d) Δ under PERC-emp-sr1u50 for K4L vs R3a, paired:**
- fresh bank: **+0.017 [−0.008, +0.042] (n=600)**;
- screen: +0.013 [−0.017, +0.047] (n=300).

**Recommendation:** the patch is safe to adopt. It is a no-op on a clean channel (30/30 identical hashes), has no
timing cost, and repairs the translator's revealed set (24 → 1 dropped true unit-records per game). Its win-rate
gain is NOT CONFIRMED (+0.013 pooled). Adopting it is the LIVE LEAD's call, on correctness grounds, not as a
measured strength gain.

## 8. Off-vocabulary cards and class-only unknowns (design constraint from the BOT LEAD, 2026-10-16)

The constraint comes from perception round 3, which adds class-only `UNKNOWN_UNIT`/`UNKNOWN_BUILDING` detections
and a proxy table that maps named off-vocab cards to C56 proxies, with the TRUE id kept in the revealed set. Where
the patch stands, and the extension points:

**(a) True ids that are not C56 names: NOT YET MET.** Today it holds proxy names.
- RevealedSet is keyed by plain strings with no vocabulary check, so it can hold any id.
- But `accept_events` calls `card_name()` (C56 name, or the PROXY name, or None = dropped) BEFORE the RevealedSet
  check, and `members()` reads `translator.plays[1]`, which holds the names fed to D1 (i.e. proxies). So the set
  holds proxy names.
- Consequences: two off-vocab cards with the same proxy share one slot. A proxy that equals a card the opponent
  really has is merged with it. For a non-C56 id, `spawns()` returns False, so a troop is treated as spell-like by the
  weakness rule.
- Extension point:
  1. Key the set by a `true_id` carried on each accepted public row (`row['true_id']`, default = name). Call
     `allows`/`reject`/`victim` with the true id, and keep the proxy name only for D1/events/packet.
  2. Have `members()` read `{row.get('true_id', name)}` (a parallel list next to `plays[1]`).
  3. Take `spawns(id)` from the proxy table's unit class (troop/building/spell), which the CARD LEAD table should
     carry.
  4. Map the board path's unit card through the same table before `observe_board`.

  These are small edits in translate.py (`accept_events`, `assign`, `card_name` returning (true_id, proxy)) and
  revealed.py (`members`). Behaviour on all-C56 games is unchanged when true_id == name.

**(b) Class-only unknowns as pending evidence: PARTLY MET** (they never occupy a slot), with no evidence kept.
- Today `assign` drops a unit whose class is not a card before `observe_board` (counted `unmapped_card_unit:<cls>`),
  so a class-only detection can never take one of the 8 slots or evict anything.
- Extension point:
  1. Add `RevealedSet.observe_unknown(tick, cls, x, y)`, which appends to `self.pending[cls]` (outside `members()`
     and the cap).
  2. When a named detection or play later matches it (place and time window), move its records into `board[card]`
     / `seen[card]` and drop them from `pending`.
  3. Never let `pending` evict, or admit through `victim`.
- A class-only unit cannot enter the search root (it has no card config), so the sanitizer keeps dropping it.

Neither extension changed the screened or fresh-bank code.

## 9. Review r5: three reviewed defects fixed (correctness only; no new bank, the strength verdict stands)

An independent review reproduced three defects in the r4 patch. All three are fixed in bot/noise/livefix (the patch
is regenerated; bot/live on main is untouched). Every new test fails on the r4 code (mutation-checked against the
r4 tree) and passes on the fix.

**1. Board-only admissions never reached the belief.** A card admitted on board evidence alone (e.g. Giant, its play
never perceived) went to `admitted` only. Replay and the player restart saw seven cards, so the mirror, the events
and every sampled opponent deck lacked it.
- Fix: `_admit` puts an inferred play row in the history (`injected=True, board=True`), via
  `RevealedSet.board_play`. Its time is the first sighting of the card's persistent run minus `deploy_ticks` = 20,
  never after the stream guard's time; its place is that unit's position. `board_plays` keeps it, and every later
  rebuild re-inserts it.
- Injected rows are not play evidence (`plays()` and `contradicted()` skip them), so the eviction rule is unchanged.
- Tests: `test_board_admission_reaches_the_belief_after_restart` runs a LiveSession whose stub player restarts a live
  belief; all 16 belief samples hold exactly the 8 cards, Giant included. `test_board_play_survives_a_later_eviction`.

**2. Same-frame ordering defeated the shared set.** The sanitizer (`assign`) ran before a play-triggered eviction in
`accept_events`. So a frame that evicted HogRider for Giant kept HogRider's units in its packet and dropped Giant's.
- Fix: `LiveTranslator.refilter` runs after `accept_events` and only when the set's `version` changed in that frame.
  It drops the units of cards that are no longer allowed. It gives the newly allowed units (dropped by the sanitizer,
  so never seen by the tracker) the tracker's read-only body choice, so no observation is counted twice.
  `board_dropped` is corrected, so each unit is counted once, by its final decision.
- Test: `test_same_frame_eviction_refilters_the_board` (both cards' units on board in the evicting frame).

**3. Catch-up polls manufactured persistence evidence.** After a gap (2400 → 2465), LiveSession repeats one snapshot
over 12 catch-up polls, so one Giant sighting became 11 board records and evicted.
- Fix: LiveSession tags each record with its source frame (`_frame` = the frame's own tick) and marks catch-up
  records `_synthetic`. `observe_board` skips synthetic polls and a repeated frame identity (default: the record
  tick), counted in `board_evidence_skipped`.
- Tests: `test_catch_up_polls_are_not_board_evidence`, `test_catch_up_after_a_gap_keeps_real_persistence`,
  `test_repeated_frames_are_idempotent`.

**Invariants kept.**
- `test_fair_information_invariance` passes.
- There is still one RevealedSet object.
- The `_admit` monotone-time fix and its two tests are unchanged.
- Clean channel: floorchk-r5 gives 30/30 identical command hashes, Δscore 0.000 and 0 restarts. It is also 60/60
  hash-identical to r4's floorchk across both arms.

**Verification.**
- Tests: test_revealed 17/17 (harness and as bot/live/test_revealed.py).
- LIVE suite on the patched bot/live, compared with unpatched main in two environments:
  - 03 bot-only tree (pinned runtime): 67 passed (50 + 17 new), 9 failed, 3 skipped. Main gives 50 / 9 / 3.
  - 05 full repo (no runtime pins): 64 passed, 13 failed, 2 skipped. Main gives 47 / 13 / 2.
  - Each environment fails the same tests with and without the patch. All 9 failures on 03 are missing non-bot
    modules; all 13 on 05 are missing runtime/student files. The two failure sets do not overlap, so every LIVE test
    passes in at least one environment with the patch applied.
- Smoke smoke-r5: `AUD:PERCRe2b10-emp-sr1u50:LIVED-K4L-R-gs-rw-fc` vs R3a and v1, HEADLINE cases 300–319, 40 games.
  0 errors, 0 exceptions, perc_errors 0, 47 evictions in 26 games, 1–2 true unit-records dropped per game.
- Patch: reports/bot/noise-robust/revealed-set.patch, sha256 b1d81add72f82966fce1800437c290512d40bf231ddd2b67d7ba84def4dca7b1.
