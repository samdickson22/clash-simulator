# LIVE integration: (a) event-card fusion, (b) end-to-end replay on REAL perception (exploration tier)

Owner: `live-integ-ab-owner-r1` (parent: LIVE LEAD), 127x05 worktree `live/lead`, 2026-10-15. Log: [PROGRESS.md](PROGRESS.md).
Exploration tier: thresholds chosen on validation; no preregistration. **Heldout was never listed or opened**: the
perception dump goes through `live/perception/common.HeldoutGuard`; the replay refuses any match that the registered split
(`t1-split.json`, sha `3edbd25b…`, checked) doesn't mark `validation` (`ValueError`, not `assert`). CPU only, niced:
01 ≤16 processes, 05 ≤4 cores.

**Data.** `dump_records.py` ran LivePerception (the TorchScript export, CPU fp32, the live code path) over all **64 validation
matches** (~10 FPS; 53,388 processed frames). Each frame record stores pred + truth, plus the event-head peaks and the
low-score units, so tracker variants replay offline in seconds. Files: `/mpac/sdicks02/jobs/clasher/live-integration-20261015/dump/`
on 01 and 05 (21 MB).

## TL;DR

**(a) Event-card fusion** (`live/perception/events.py`).
- Each event is emitted **once**, after a confirmation hold, with the card fused from the newborn unit's body.
- Troops are emitted early when the body agrees with the event head.
- Full val, W = 1 s, with the deployed config (threshold .6, hold 500):
  - all events: P/R .874/.749 → **.909/.794**;
  - opponent troops: .905/.843 → .933/.883;
  - opponent spells: .740/.479 → .773/.507;
  - latency: median 150 → 225 ms, p90 525 → 625 ms.
- The even-half F1 pick (threshold .5, hold 700) reaches F1 .855 against .807, and .851 against .802 on the held-out odd half.
- **Most of the gain comes from the hold**, which decides the card later. Body votes flip few cards; their value is early emission.
  The remaining wrong cards are errors the body head shares, since both heads sit on the same backbone.
- **Royal Ghost is a perception blind spot**: an ignore region in the dense labels.

**(b) Real perception → LiveTranslator → LivePlayer** on all 64 val matches (it5s2) and on 28 (K4CW-w200-t4, clean host).
- **No crashes:** 0 translator and 0 decision errors in every arm.
- **Agreement with the same bot on the true engine state** (exact; same card on true plays):

  | arm | it5s2 | K4CW |
  |---|---|---|
  | own floor (reseed) | 1.000 | 0.857; 0.863 |
  | dense-label truth record | 0.948; 0.953 | 0.862; 0.878 |
  | **deployed stack** (fused events + resync) | **0.856; 0.836** | **0.741; 0.714** |
  | step-C default (births) | 0.819; 0.816 | births-rs 0.725 |

- **Opponent plays reaching the bot:** step-C births reached 0.35, and the original event tracker 0.57.
  - The deployed stack reaches **0.775** at precision 0.949.
  - The even-half config reaches 0.807 at precision 0.915.
- **Resync-capable cycle tracker** (`bot/live/resync.py`, new) is the main fix:
  - a perceived opponent play that contradicts the mirrored cycle now triggers inference of the missed plays instead of being
    dropped (302/330 such drops were true plays);
  - stream-guard drops 330 → 78; plays reached 0.594 → 0.775.
- **Fixed a live bug:** a single skipped 5-tick poll (any stall over 250 ms) killed the fast tier for the rest of the match.
- **HUD clock:** it must be anchored at match start. Unanchored, it misreads regulation vs overtime in half of the mid-match
  windows.
- **Empirical-noise arm:** `PERC-emp:<player>` uses noise measured on val. The exact HEADLINE commands are below (not run).

## (a) Event-card fusion

### Design

The tracker in `live/perception/events.py` still finds tracks the same way. What changed is **when and how a track is emitted**.

- **Confirmation hold.** When a track crosses the threshold, it is held until exec + `hold_ms`. It is then emitted **once**, with the
  fused card.
- **Why not re-emit?** Re-emitting a revised event would break the bot side: the translator feeds every accepted play into the
  frozen D1/OwnCycle mirrors and the belief, and none of them can retract a play. With the hold, `translate.py` and `births.py`
  need no change.
- **Card votes.** Votes come from newborn units on the same side within `unit_radius` of the event, from exec − 150 ms on.
  - Units of a card already present nearby in [exec − 1.5 s, exec − 150 ms] don't vote.
  - A vote is the per-frame max detection score per card, averaged over the frames since exec, so a swarm counts once.
  - The fused card is the top-voted newborn card if its vote is ≥ `vote_min` and the head gives it a share ≥ `prior_min`.
    Otherwise it is the event head's argmax.
- **Early emission.**
  - When the head and the bodies agree (`agree_frames` = 2 frames' worth of score), the event is emitted before the hold ends.
  - A body-less spell (Arrows, EQ, Fireball, Lightning, Log, Poison, Rocket, Tornado, Zap) is emitted at the crossing if
    its head share is ≥ `early_share`.
- `hold_ms = 0` reproduces the original tracker exactly (tested).

### Selection

- **Grid:** 386 configurations (threshold, hold, vote_min, prior_min, radius, agree, early).
- **Rule:** best all-events F1 at W = 1 s on the **even half** of val. Configurations within 0.01 of it are broken by lowest
  median latency.
- **Selected:** threshold .5, hold 700 ms, vote_min .35, prior_min .02, radius 2.5, agree 2, early_share .6.
- **On the held-out odd half:** all-events F1 rises from .802 (original tracker) to **.851**. The best possible on odd is .856,
  so selection optimism is small.

### Full validation (64 matches, 2,826 events)

Match rule as in perception RESULTS: same side and card, detection time in [exec, exec + W], Hungarian.

| tracker | W | all P/R (F1) | opp P/R | opp spell P/R | opp troop+bldg P/R | own P/R | latency median / p90 ms | cards revised by bodies |
|---|---|---|---|---|---|---|---|---:|
| original (thr .6) | 1000 | 0.874/0.749 (0.807) | 0.873/0.749 | 0.740/0.479 | 0.905/0.843 | 0.874/0.749 | 150 / 525 | 0 |
| original (thr .6) | 1500 | 0.898/0.770 (0.829) | 0.899/0.771 | 0.818/0.529 | 0.919/0.855 | 0.897/0.769 | 150 / 525 | 0 |
| original (thr .5) | 1000 | 0.792/0.753 (0.772) | 0.790/0.758 | 0.589/0.521 | 0.852/0.840 | 0.795/0.748 | 125 / 450 | 0 |
| hold 700 only, no body votes (thr .5) | 1000 | 0.874/0.837 (0.855) | 0.857/0.829 | 0.648/0.577 | 0.922/0.916 | 0.891/0.844 | 775 / 875 | 0 |
| fused, no early emission | 1000 | 0.875/0.839 (0.857) | 0.854/0.828 | 0.646/0.577 | 0.919/0.915 | 0.896/0.850 | 775 / 875 | 59 |
| **fused, selected (thr .5, hold 700)** | 1000 | 0.869/0.841 (**0.855**) | 0.853/0.831 | 0.646/0.577 | **0.917/0.919** | 0.885/0.850 | **225 / 800** | 61 |
| fused, selected | 1500 | 0.892/0.863 (0.877) | 0.879/0.857 | 0.702/0.627 | 0.933/0.936 | 0.905/0.869 | 225 / 800 | 61 |
| **fused, high-precision (thr .6, hold 500)** | 1000 | **0.909**/0.794 (0.848) | 0.902/0.787 | **0.773**/0.507 | 0.933/0.883 | 0.916/0.801 | 225 / 625 | 57 |
| fused, high-precision | 1500 | 0.943/0.823 (0.879) | 0.940/0.819 | 0.863/0.566 | 0.958/0.907 | 0.946/0.827 | 225 / 625 | 57 |

- **Opponent troops (selected vs original):** false negatives 162 → 83, false positives 91 → 86.
- **Opponent spells:** TP 171 → 206, but FP 60 → 113. That is the cost of threshold .5; the thr .6 variant keeps spell FP low.
- **Latency added** (matched pairs, selected vs original): median +50 ms, p90 +450 ms.

### What the fusion does and doesn't do

1. **The hold is most of the gain.** Hold alone gives F1 .855, but at a median latency of 775 ms: deciding the card later lets the
   head's card mass accumulate over more frames.
2. **Body votes rarely flip the card.** They flip only ~60 events across all of val. Their real value is **early emission**:
   median latency drops 775 → 225 ms at no F1 cost, because a troop is emitted as soon as its newborn body agrees.
3. **Remaining wrong-card troop events can't be fixed by votes.** Most are cases where the body head mislabels the newborn the same
   way: true Valkyrie, bodies say Goblins; true Princess, bodies say GoblinGang. The two heads share a backbone, so their errors
   are correlated.
   - The "85/140 wrong-card troop FPs" figure in perception RESULTS came from epoch 20 at thr .5. The final model with the hold already
     fixes most of those cases.
4. **Royal Ghost is a known perception blind spot.** The dense labels make Ghost an ignore region, so a Ghost unit is never
   detected.
   - Its play events still exist in the event head, but nothing confirms them.
   - The bot never sees a Ghost on the board, its own included. In val match 1975100748, where both decks have Ghost, Ghost rows
     are the main difference between the dense-label truth record and the true engine state.
   - Fixing it needs labels for Ghost while visible.

## (b) End-to-end replay on real perception

### Harness (`bot/live/real_replay.py`)

Each validation match is replayed from the dump. Every arm has its own translator and LivePlayer, with the same seeds and the same
opening order. All arms decide at the same 5-tick polls, **on the first frame of each poll window**, as LiveSession does.

- **Reference `ref`:** the **true engine state** from the match recording (`bot.live.replay.T1Match`): every hit-point object by
  its spawning card, the own HUD, and the accepted plays.
- **Frame alignment:** perception records are mirrored into the same frame. The perception frame is a y-flip, T1's seat-1 frame is
  a 180° rotation, so the record is mapped x → 18 − x and the tower sides are swapped.
- **Own plays** in every perception arm come from the true plays. Live, they come from our own commands.
- **Plays before the first dumped frame** reach every arm as the same true history.

| arm | input |
|---|---|
| `ref` / `reseed` | true engine state; `reseed` shifts search and poll seeds by +7. This is **the bot's own noise floor**: for the wall-clock search tier it includes timing jitter. |
| `ref-eps` | true state with every unit moved +0.01 tile (sensitivity check) |
| `truth` | dense-label truth record (the perception schema's ceiling) + true play events |
| `births` / `births-rs` | perception, opponent plays from unit births (step C's default) / plus resync |
| `head` | perception, opponent plays from the original event tracker (`pred.events`) |
| `fused` / `fused-rs` | perception + fused tracker, even-half pick (thr .5, hold 700) / plus resync |
| `fused-prov` / `fused-prov-rs` | perception + fused tracker, **deployed config** (thr .6, hold 500) / plus resync |
| `fused+births-rs` | fused events + birth-derived plays, de-duplicated (`BothTranslator`), resync |
| `fused-hud-rs` | `fused-rs` with the tick from the HUD clock path, ClockTracker anchored at match start, exactly as LiveSession (per-frame poll windows, catch-up polls) |
| `fused-noanchor-rs` | the same without the start anchor |

### it5s2 (fast tier): 64 validation matches, 21,139 decisions per arm (`JOB/replay-fast4`)

Agreement is with the same bot on the true engine state. CIs are bootstrap over matches. "same card" means the same hand slot on
`ref`'s plays.

| arm | exact | 95% CI | play/wait same | ref plays: exact | same card | card+≤2 tiles | ref WAITs kept | plays when ref waits | agree w/ truth record | decision errors |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| reseed (floor) | 1.000 | [1.000, 1.000] | 1.000 | 1.000 (n=6595) | 1.000 | 1.000 | 1.000 | 0 | 0.948 | 0 |
| ref-eps | 0.997 | [0.996, 0.998] | 1.000 | 0.991 | 0.998 | 0.997 | 0.999 | 8 | 0.947 | 0 |
| truth record | 0.948 | [0.932, 0.961] | 0.981 | 0.864 | 0.953 | 0.911 | 0.986 | 205 | 1.000 | 0 |
| births (step-C default) | 0.819 | [0.795, 0.841] | 0.938 | 0.523 | 0.816 | 0.661 | 0.954 | 675 | 0.827 | 0 |
| births-rs | 0.826 | [0.801, 0.847] | 0.942 | 0.527 | 0.814 | 0.667 | 0.961 | 564 | 0.834 | 0 |
| head (original tracker) | 0.836 | [0.812, 0.857] | 0.940 | 0.570 | 0.830 | 0.702 | 0.957 | 623 | 0.846 | 0 |
| fused | 0.843 | [0.820, 0.863] | 0.943 | 0.587 | 0.838 | 0.715 | 0.959 | 596 | 0.852 | 0 |
| fused-rs | 0.857 | [0.834, 0.877] | 0.950 | 0.608 | 0.843 | 0.735 | 0.970 | 438 | 0.867 | 0 |
| fused-prov | 0.838 | [0.814, 0.859] | 0.941 | 0.574 | 0.831 | 0.707 | 0.958 | 618 | 0.848 | 0 |
| **fused-prov-rs (deployed)** | **0.856** | [0.833, 0.877] | 0.949 | 0.603 | 0.836 | 0.725 | 0.971 | 417 | 0.866 | 0 |
| fused+births-rs | 0.854 | [0.831, 0.874] | 0.948 | 0.602 | 0.840 | 0.730 | 0.969 | 455 | 0.864 | 0 |
| fused-hud-rs | 0.858 | [0.835, 0.878] | 0.951 | 0.611 | 0.847 | 0.737 | 0.970 | 441 | 0.864 | 0 |
| fused-noanchor-rs | 0.658 | [0.617, 0.695] | 0.687 | 0.041 | 0.099 | 0.064 | 0.938 | 904 | 0.658 | 0 |

Opponent plays reaching the bot. A play reached = an accepted play of the same card within 3 tiles and −10..+60 ticks of a true play.
Inferred (resync) plays are excluded from accepted/precision and counted separately.

| arm | true opp plays | reached | recall | wrong plays accepted | precision | stream-guard drops | resyncs (plays inferred) / failed | late events retimed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| truth record | 1385 | 1385 | 1.000 | 0 | 1.000 | 0 | — | 0 |
| births | 1385 | 480 | 0.347 | 52 | 0.902 | 670 | — | 1202 |
| births-rs | 1385 | 620 | 0.448 | 74 | 0.893 | 508 | 119 (166) / 352 | 1202 |
| head | 1385 | 792 | 0.572 | 66 | 0.923 | 331 | — | 403 |
| fused | 1385 | 897 | 0.648 | 96 | 0.903 | 358 | — | 754 |
| fused-rs | 1385 | **1118** | **0.807** | 104 | 0.915 | 129 | 132 (173) / 39 | 754 |
| fused-prov | 1385 | 823 | 0.594 | 56 | 0.936 | 330 | — | 662 |
| **fused-prov-rs (deployed)** | 1385 | 1073 | **0.775** | **58** | **0.949** | 78 | 151 (221) / 42 | 662 |
| fused+births-rs | 1385 | 1056 | 0.762 | 151 | 0.875 | 281 | 184 (313) / 158 | 908 |

**Crashes:** none. Every arm has 0 translator errors and 0 decision errors across 64 matches × 21,139 decisions.

**Other translator counters:** 149 `cycle_conflict_dropped:0` per arm. These are our own plays: the recordings start mid-match, so
our opening order is a guess, the same in every arm. `ref` has 8 opponent-side drops of its own for the same reason.

### LIVE-K4CW-r16-w200-t4 (search tier)

Wall-clock search with 4 threads and a 200 ms budget, on clean 127x05 (cores 2–5, nice 19): **28 validation matches, 4,903
decisions per arm** (`JOB/replay-k4cw-rs`). The `ref` decisions took p50 113 ms and p95 192 ms; 13.1% ended on the it5s2 default,
consistent with the clean Mac-bench baseline.

- **The 01 half is excluded.** A second set of 36 matches ran on 127x01 (`JOB/replay-k4cw-rs-01`). 01 was at load ~85, so the
  search missed its deadline on **80%** of decisions and fell back to it5s2: p50 192 ms, and reseed agreement 1.0 shows it was not
  searching.
- **Nothing in the 01 half is a K4CW measurement.** It's listed under Files only to explain the gap. Lesson: wall-clock tiers
  can't be measured on a loaded shared host.

| arm | exact | 95% CI | play/wait same | ref plays: exact | same card | card+≤2 tiles | ref WAITs kept | plays when ref waits | agree w/ truth record | decision errors |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **reseed (floor)** | **0.857** | [0.842, 0.872] | 0.947 | 0.628 (n=1508) | 0.863 | 0.727 | 0.959 | 139 | 0.806 | 0 |
| truth record | 0.862 | [0.828, 0.890] | 0.945 | 0.653 | 0.878 | 0.755 | 0.954 | 155 | 1.000 | 0 |
| births-rs | 0.725 | [0.690, 0.754] | 0.885 | 0.304 | 0.699 | 0.460 | 0.913 | 297 | 0.729 | 0 |
| fused-rs (even-half config) | 0.743 | [0.708, 0.771] | 0.889 | 0.345 | 0.706 | 0.507 | 0.919 | 274 | 0.747 | 0 |
| **fused-prov-rs (deployed)** | **0.741** | [0.707, 0.771] | 0.889 | 0.343 | **0.714** | 0.508 | 0.918 | 277 | 0.745 | 0 |
| fused-hud-rs (+ anchored HUD clock) | 0.723 | [0.688, 0.752] | 0.885 | 0.292 | 0.694 | 0.456 | 0.915 | 290 | 0.722 | 0 |

**Opponent plays reaching the bot**, same 28 matches (683 true plays):

| arm | reached | wrong accepted |
|---|---|---:|
| fused-rs | 0.814 | 45 |
| **fused-prov-rs** | **0.785**, precision **0.950** | 28 |
| births-rs | 0.432 | — |

**Reading.**
- With the same input and other seeds, K4CW repeats its exact action 0.857 of the time (0.863 same card): that is its own floor.
- The dense-label truth record sits **at the floor** (0.862).
- The deployed real-perception stack is **0.741 exact (−0.116 vs the floor)** and 0.714 same card on true plays (−0.15). The
  previous default (births) is 0.725.
- These numbers are higher than step C's engine replay (reseed 0.79), because all arms here decide on the first frame of the
  poll window and the reference reads the same frame.
- `fused-hud-rs` vs `fused-rs` (−0.02) is within the CI. The two arms are identical except for the tick path, so for the search
  tier this is timing jitter plus the half-tick rounding of the HUD tick.


### Fusion config decision (LEAD rule: decided by bot-level results)

- **The two configs tie on agreement:** it5s2 0.857 vs 0.856, and the K4CW CIs overlap.
- **The even-half pick** (thr .5, hold 700) gets 3.2 pp more true plays to the bot (0.807 vs 0.775).
- **The high-precision config** (thr .6, hold 500) lets **44% fewer wrong plays** through (58 vs 104; precision 0.949 vs 0.915).
  A fake play, a spell especially, corrupts the opponent elixir and cycle tracking.
- **Deployed: thr .6 / hold 500.** It is now `live/perception/events.py:LIVE_DEFAULT`, which LivePerception uses by default.
  `fusion={'hold_ms': 0}` restores the original tracker.

### Resync-capable cycle tracker (`bot/live/resync.py`)

**The stream guard was the biggest loss.** It mirrors the frozen DerivedD1 tracker and dropped an opponent play whenever the card
was still in the mirrored cycle queue. 302 of 330 such drops (fused events) were TRUE plays: earlier missed plays had left the mirror
un-rotated.

`ResyncTranslator` handles these instead of dropping them:
- **Still dropped:** a ninth distinct card, and the same card again within 80 ticks (a duplicate detection; real repeats need four
  other plays first).
- **Otherwise it infers the missing plays:** the fewest plays (1–4) of known hand cards (revealed and not queued; longest-unplayed
  first). They are inserted between the last accepted opponent play and the new one.
- **Verification:** the whole history must replay cleanly through a fresh DerivedD1.
- **On success:**
  - it rewrites the public D1 rows, the enemy PublicEvent stream, the plays and the mirror;
  - it sets `resynced`;
  - the caller restarts the player, which rebuilds its frozen trackers (D1Tracker, belief) from the corrected history on the next
    `act`.

Fair information: only public plays and their times are used; inferred rows are hand cards the opponent already revealed, flagged
`injected=True`. An inferred play also charges its elixir cost, which the missed play really cost.

**Hooks**, all minimal; no frozen file was edited:
- `LiveSession` (`bot/live/translate.py`): it stores the MatchContext and restarts the player after a resync (3 lines).
- `PercPlayer` (`bot/live/perc.py`): empirical arms use the resync translators and restart the inner player.
- `real_replay` arms with the `-rs` suffix.

**Effect** (deployed config, 64 matches):
- Plays reaching the bot: 0.594 → 0.775. With the even-half config, 0.648 → **0.807**.
- Stream-guard drops: 330 → 78.
- Precision: 0.936 → 0.949.
- it5s2 agreement: 0.838 → 0.856, and the bot makes 30% fewer plays where `ref` waits (618 → 417).
- About 40 conflicts per 64 matches still can't be resolved (`resync_failed`): too few known hand cards, or no consistent placement.

**Tests:**
- 15 integration tests; with glueC's 23 that makes **38 pass**. They include fair-information invariance with resync, duplicate
  rejection, and restart of both tiers.
- A bug found by the first full run is fixed and has a test: the rebuilt mirror lacked the resynced play.

### LiveSession poll gap (live bug, fixed)

**The bug:** the frozen 5-tick D1 gate (`imitation/evaluation/standalone.py`) raises when two polls are not exactly 5 ticks apart.
It raises *before* updating its state, so after **one** skipped poll every later poll fails. Any capture or perception stall over
250 ms would end the fast tier (it5s2 only WAITs) for the rest of the match.

**The fix:** `LiveSession` now runs catch-up polls on the current record with `can_act=False`. The test is mutation-checked:
without the fix it shows `fast-error` on every decision after the gap.

### Clock

- **Anchored at match start** (`ClockTracker.anchor(0, ts)`, as the live loop will do): tick error median 0, p95 0.5. This matches
  `fused-rs` at the bot level (0.858 vs 0.857).
- **Without the anchor** the HUD clock is **unusable** in half the windows that start mid-match. The perceived clock has MAE 4.4 s,
  so it gets regulation vs overtime wrong: +2,400 ticks around tick 2400, about −700 around 3600. Agreement drops to 0.66.
- **The live loop must anchor at match start.** If it can't, it should hold off on the phase-transition and overtime
  interpretation until the clock and phase agree for several seconds.

### Reading

1. **The schema's ceiling** (the dense-label truth record vs the true state) is 0.948 exact and 0.953 same card for it5s2. The
   biggest entity difference we found is Royal Ghost, never in the perception schema (match 1975100748); hidden Tesla and the
   record/frame timing contribute too.
2. **The deployed stack** (fused events, resync, anchored HUD clock) gets it5s2 to **0.856–0.858 exact**: 0.84 same card on true
   plays, 0.60 exact on true plays. The step-C default (births only) reached 0.819; the original tracker without resync, 0.836.
3. **The remaining gap to the truth record** (−0.09 exact) is unit recall (0.81; crowds) and opponent plays. 22.5% of opponent
   plays still don't reach the bot; spells are the largest share, with spell-event recall 0.57.
4. **Play/wait decisions** are 95% the same. The bot plays when `ref` waits on 417 of 14,544 `ref` WAITs (2.9%), mostly from
   HUD and elixir transitions and false unit detections.

### Empirical perception noise for win-rate runs (`bot/live/empirical.py`, `bot/live/empirical-val.json`)

`fit` measures the noise on the 64 validation matches with the deployed tracker. The values below are what `EmpiricalNoise` samples:

| quantity | value |
|---|---|
| unit recall, owner-only match ≤ 1 tile | 0.811 (per card in the JSON) |
| detection persistence (Markov per true unit) | P(hit given hit) 0.922, P(hit given miss) 0.341: misses are strongly correlated, unlike the step-C arms' independent flicker |
| card confusion when detected | full confusion matrix per true card |
| position / hp residual sd | 0.11 / 0.16 tiles; hp 0.07 (empirical samples) |
| false-positive units per frame | 0.18 (ours), 0.20 (opponent); card distribution and distance to the nearest true unit |
| hand slot / next error | 1.15% / 1.5% |
| elixir residual | empirical samples (sd 0.35, mostly at transitions) |
| tower alive flips | 0.02% |
| opponent play events | troop recall 0.924, spell recall 0.574, card right when detected 0.98 / 0.98, latency median 225 / p90 625 ms, spurious events 0.59 per minute |

**Arms** (`bot/live/perc.py`); all use the resync translators:
- `PERC-emp:<player>`: opponent plays from the event stream (the deployed stack);
- `PERC-emp-births:<player>`: births only;
- `PERC-emp-both:<player>`: events + births.

**Smoke:** a 2-game `headline_wall` smoke on 01 (`PERC-emp`, `PERC-emp-both` vs v1) completed full games, with 0 errors.

### Win-rate command at measured perception quality (not run; for the LEAD to schedule)

Stage `bot/` exactly as in `reports/live/bot/RESULTS.md` §4. `bot/live/empirical-val.json` travels with it.

```bash
# from 05
rsync -a --delete /mpac/sdicks02/repos/clasher-live/bot/ 127x03:/mpac/sdicks02/repos/clasher-live-eval/bot/
ssh 127x03
cd /mpac/sdicks02/repos/clasher-live-eval
export PYTHONPATH=$PWD CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1 PYTHONHASHSEED=0 \
       OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
# fast tier: 4 arms x 2 opponents x 300 = 2,400 games, 1 core each, ~35-40 s/game -> ~25 min on 60 cores
nice -n 5 $PY -B -m bot.live.headline_wall --out /mpac/sdicks02/jobs/clasher/live-perc-emp-ours --cores <CORES> --group 1 \
  --engine ours --opponents v1,R3a --games 300 \
  --candidate LIVE-fast-it5s2,PERC-events:LIVE-fast-it5s2,PERC-emp:LIVE-fast-it5s2,PERC-emp-births:LIVE-fast-it5s2
# search tier (the deployed bot): 2 arms x 2 x 300 = 1,200 games, 5-core groups, ~50 s/game -> ~1.4 h on 60 cores
nice -n 5 $PY -B -m bot.live.headline_wall --out /mpac/sdicks02/jobs/clasher/live-perc-emp-k4cw-ours --cores <CORES> --group 5 \
  --engine ours --opponents v1,R3a --games 300 \
  --candidate LIVE-K4CW-r16-w200-t4,PERC-emp:LIVE-K4CW-r16-w200-t4
# pairing (same base/indices): perception cost in win rate
$PY bot/eval/pair_by_name.py /mpac/sdicks02/jobs/clasher/live-perc-emp-ours LIVE-fast-it5s2 \
    /mpac/sdicks02/jobs/clasher/live-perc-emp-ours PERC-emp:LIVE-fast-it5s2
$PY bot/eval/pair_by_name.py /mpac/sdicks02/jobs/clasher/live-perc-emp-k4cw-ours LIVE-K4CW-r16-w200-t4 \
    /mpac/sdicks02/jobs/clasher/live-perc-emp-k4cw-ours PERC-emp:LIVE-K4CW-r16-w200-t4
```

**Caveats:**
- The empirical noise is from **renderer-domain** validation frames. The official-client domain gap is unmeasured, so this is a
  best case.
- The synthesiser's perfect record has no Ghost blind spot.
- Spurious unit and event placement is approximate: near a random true unit, or uniform on the opponent's half.
- Seat 1 works the same as in `PERC-p42`.

## Files

| file | what |
|---|---|
| `live/perception/events.py` | body-fusion hold, early emission, `LIVE_DEFAULT` |
| `live/perception/infer.py` | `step_prepared` (pixel-cache input, exposes peaks + low-score units); uses `LIVE_DEFAULT` |
| `live/perception/dump_records.py`, `eval_fusion.py` | validation dump; offline tracker grids + split-half selection |
| `live/perception/eval_events.py` | lazy `finetune2` import (no behaviour change) |
| `bot/live/real_replay.py` | the (b) harness, `BothTranslator`, `report` |
| `bot/live/resync.py` | resync-capable opponent cycle tracking |
| `bot/live/empirical.py`, `empirical-val.json` | measured noise model and its fitted stats |
| `bot/live/perc.py` | `emp`, `emp-births`, `emp-both` arms |
| `bot/live/translate.py` | LiveSession: poll-gap catch-up, resync restart hook |
| `bot/live/test_integration.py` | 15 tests |

**Data and results** (05 and 01): `/mpac/sdicks02/jobs/clasher/live-integration-20261015/`:
- `dump/`: the validation dump;
- `eval/`: grids, `empirical-val.json`;
- `replay-fast4/`: the final it5s2 run;
- `replay-k4cw-rs/` (05) and `replay-k4cw-rs-01/` (01): the K4CW run;
- superseded: `replay-fast`, `-fast2`, `-fast3`, `replay-k4cw` (no resync, provisional config), `replay-k4cw-rs-bug`.

## Reproduce

```bash
J=/mpac/sdicks02/jobs/clasher/live-integration-20261015
# 01, live/perception: dump (16 shards x 1 thread, ~70 min on loaded 01)
python dump_records.py /mpac/sdicks02/jobs/clasher/live-perception-20261014/export-final $J/dump --shard K --nshards 16 --threads 1
python eval_fusion.py $J/dump $J/eval/grid-even.json --half even --workers 4      # also --half odd, all; --grid hold-only
# repo root (bot venv; CLASHER_BOT_RUNTIME + CLASHER_LIVE_FAST as in reports/live/bot)
python -m bot.live.real_replay --tier fast --shard K --nshards 16 --out $J/replay-fast4
python -m bot.live.real_replay --tier search --wall-ms 200 --threads 4 \
    --arms ref,reseed,truth,births-rs,fused-rs,fused-prov-rs,fused-hud-rs --out $J/replay-k4cw-rs
python -m bot.live.real_replay report $J/replay-fast4
python -m bot.live.empirical fit --dump $J/dump --out bot/live/empirical-val.json --fusion '<LIVE_DEFAULT json>'
pytest -q bot/live/test_integration.py bot/live/test_live.py
```
