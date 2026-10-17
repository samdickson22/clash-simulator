# Opponent cycle model: RESULTS (exploration)

Design: DESIGN.md. Code: bot/cyclemodel/{belief,preal,ab,ab_report,parity,replay80,fit_preal}.py, plus the hook in
bot/fullpool/belief.py.

**Summary (2026-10-17T03:45Z).**
- (c) Perfect-observation parity PASS (20/20 + 20/20 command hashes, plus 20/20 on the fixed tree).
- (b) Belief side on the 80 live battles: 0 errors; credits 282 real plays (v1) against a labelled ~303.
  - The translator owner's Mac-env shadow: 0 errors, no cutoff rise; decisions change 13–16% vs a 3–5% noise floor.
- (a) Sim A/B CYC-AB1 at L11: soft − hard +0.020 [−0.048, +0.088]; hard − clean −0.010. No harm, but the lever is not
  visible at L11.
- **Decision (the BOT LEAD):** no ship or live A/B unless the L16 sizing shows a real gap. Parked, default OFF.
- **Update 2026-10-17T10:49Z, CYC-L16-1 (L16, deployed -res, vs K4CW-r16, 200 paired, fresh bank): PASSES the
  pre-registered ship bar.** soft − hard +0.045 [−0.022, +0.112]; clean − hard +0.09 [+0.011, +0.169]; recovery 0.50.
  The flag-off package goes to the LIVE LEAD as a live A/B candidate.

## (c) Determinism: perfect-observation parity

**Unit level** (bot/cyclemodel/test_cycle.py, 38 pass). Against the frozen s1 Belief on 25 random legal opponent
streams, polled every 10 ticks, both without a deadline and with one, the following are bit-identical: rows, weights,
tick/refill/queue_len, elixir, events, and every sample.

**Player level** (bot/cyclemodel/parity.py; LIVE-AB1 cases, e16 vs Battle Log decks, vs R3a, live16402b-r3, on 08).
Command hashes with `BOT_CYCLE_MODEL` unset vs `soft`, on tree 7768d0497 (= origin/main 6ad1c9f2f + the model). Also
compared: `off` against the pre-change tree 6ad1c9f2f (bot/fullpool/res_check.py).

| twin | soft == off | off == pre-change main | soft == pre-change main | conflicts seen by the model |
|---|---|---|---|---|
| K4L-R-gs-mk1a1 | 20/20 | 20/20 | 20/20 | 0 |
| K4L-R-gs-rw-fc-t2-mk1a1 (lopp_fast path, as live) | 20/20 | 20/20 | 20/20 | 0 |

- Cases 0–19 were run on 08 at 02:12–02:24Z.
- Rows: 05/08 job dir `parity-r1.jsonl` (50d1d89e…) and `parity-base.jsonl` (4fa592fe…).
- The soft runs really ran the model: the class is FullPoolBelief over CycleBelief, cycle_stats is present, and it
  logged 0 conflicts. **PASS.**
- Extra check from the A/B smoke: in a noisy game with no cycle conflict (case 0), `cyc-hard` and `cyc-soft` gave
  identical hashes.

## (b, belief side) Offline replay of the 80 live battles (s41–s60)

bot/cyclemodel/replay80.py, on 08, 02:30Z. Output: job dir `r80-v0c.json` (196d1e1e…).
- **Method.**
  - The deployed translator's accepted opponent plays (guardfix/replay/dep-{0,1}.json) go in as `card` events. Its 435
    cycle-conflict drops go in as `card?`, with p = preal v0 from the translator owner's features.
  - The belief is the full-pool one (fullpool:11433651), polled every 10 ticks, `BOT_CYCLE_MODEL=soft`.
  - 9th distinct cards are not emitted (as in the diff): 1 of the 435.
- **Errors:** 0 in 80 battles.
- **Outcomes of the 434 emitted drops:**
  - 302 have a feasible real explanation: k\* = 0 for 190 (in hand in some row, or due at a pending refill), 1 for 97,
    2 for 15. Expected real plays credited (Σp) = 223.
  - 132 are phantom-only: no affordable explanation, so the state is unchanged.
- **Labelled sample 1** (40 distinct items; one drop appears twice in the 435):
  - Real 27: 26 have a feasible real explanation; 1 is phantom-only (s56-m01 3465 BattleRam).
  - Phantom 13: 11 are phantom-only and 2 are feasible (s43-m02 3155 Barbarians, s57-m03 3170 Skeletons; both
    spawner family, plays_between 3).
  - So the belief's own consistency (elixir bound plus cycle) separates the classes beyond p. A phantom right after the
    real play would need ~4 unseen plays within seconds, which isn't affordable.
- **Cost (loaded 08):**
  - Resolver p50 0.37 ms, p95 29 ms, max 111 ms. Whole update p95 30 ms, max 272 ms; the max includes a full-pool prior
    rebuild in the same poll, which is not the model.
  - The slow cases are the first conflict of a battle while ~100–130k prior rows remain. They cost one decision's
    search budget at most once per battle; later conflicts take ~1 ms. Max rows after any event: 5,559.

**Rerun after the Sol r1 fixes** (tree 579ddf11c52f, 02:40Z, job dir `r80-v0d.json` 68293ddd…). This supersedes the
numbers above; the hidden-cost bug had over-pruned k\* ≥ 2.
- **Errors:** 0.
- **The 434 emitted drops:**
  - 327 have a feasible real explanation: k\* = 0 for 198, 1 for 91, 2 for 25, 3 for 6, 4 for 7. Σp = 236.
  - 107 are phantom-only.
- **Labelled:** real 27/27 feasible; phantoms 9/13 rejected, 4 feasible.
- **Cost:** resolver p50 0.42 ms, p95 29 ms, max 121 ms; max rows 15,091.
- **Open:** the 7 cases with k\* = 4 are re-detections right after the real play, explained by four unseen plays. v0
  gives every troop with plays_between < 3 the same 0.73. The data-driven fix is P(real) v1 on sample 2, which
  separates plays_between 0/1/2. Not a belief change.
- **Parity on the fixed tree** (parity-r2.jsonl 7c4ebb1f…): soft == off, 20/20 (both twins, cases 0–9), 0 conflicts.

## P(real) v1 (final labels, 03:12Z)

**Labels:** sample 1 (40, simple random) plus sample 2 (160, stratified by kind;
guardfix/cycle-labels/sample2-labels-with-features.json 0837223e…). 200 distinct items: 137 real / 63 phantom.
- The translator owner's population estimate: ~303 of the 435 are real (95% 282–323).

**Model:** reports/bot/cycle-model/preal-v1.json (f9096e22…), from bot/cyclemodel/fit_preal.py with the pre-specified
L2 = 1 (L2 0.3 / 3 give leave-one-out log loss 0.218 / 0.257; not tuned). Features: kind, near a same-family spawner
(≤ 4 tiles), plays_between 1/2/3+, log ticks_since_same. Select it with `BOT_CYCLE_PREAL=<path>`; default v0.

**Leave-one-out:**

| model | log loss | Brier |
|---|---|---|
| v0 strata (fitted on sample 1, so partly in-sample) | 0.514 | 0.172 |
| **v1 logistic** | **0.229** | **0.056** |

**Calibration by cell** (observed real share vs mean predicted):

| cell | n | observed | predicted |
|---|---|---|---|
| troop, plays_between 0 | 19 | 0.21 | 0.23 |
| troop, plays_between 1 | 17 | 0.53 | 0.64 |
| troop, plays_between 2 | 29 | 0.97 | 0.92 |
| troop, plays_between 3+ | 32 | 1.00 | 0.95 |
| spawner family, plays_between 0 | 14 | 0.14 | 0.19 |
| spawner family, plays_between 1 | 15 | 0.80 | 0.68 |
| spawner family, plays_between 2 | 19 | 1.00 | 0.92 |
| spawner family, plays_between 3+ | 25 | 0.92 | 0.92 |
| spawner family near a same-family spawner | 16 | 0.00 | 0.09–0.32 |
| buildings | 14 | small cells | |

**80-battle replay with v1** (r80-v1.json d863bb40…, tree 579ddf11c52f):
- 0 errors; 327 feasible / 107 phantom-only.
- Credited real mass Σp = 282, against the population estimate of 303 (282–323).
- Credited mass by k\*: 0 → 177, 1 → 82, 2 → 18, 3 → 3.5, 4 → 1.0. The re-detections that needed 4 unseen plays now
  carry ≈ 0.1 each.

## Translator diff, C56 path, in the wall-clock live player (smoke)

The tree was main 593beb054 plus translator/cycle-soft-full-vs-main.diff (05/08 job dir
repo-difftest-593beb0543c7; a scratch copy, not a live tree). Run on 08 at 02:45Z:
`histnoise:raw:cyc-soft:LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1`, x4s C56 decks (no full-pool prior, so LivePlayer
installs `live_belief_class(rt)` = LiveBelief over CycleBelief), vs R3a, 3 games, `BOT_CYCLE_MODEL=soft`.
- **Errors:** 0 errors and 0 fast-error decisions.
- **Soft events:** 48 (16 per game) reached the belief; 6 ended phantom-only, 0 were rejected.
- **Search:** sources were search 353, default-it5s2 12 (3%).
- **Belief cost:** resolver max 3.6 ms; max rows 202 (the C56 prior is smaller than the full-pool one).

## (a) Sim A/B: pre-registration (written 2026-10-17T02:17Z, before any game)

**Bank and players.**
- Bank CYC-AB1: base 1185182611752721 = sha256('clasher cycle-model sim A/B CYC-AB1 2026-10-17T02:17Z') mod 2^52.
  e16bl decks (e16 vs the 91 Battle Log decks, opponent-decks-20261016.jsonl 3a7c4e78…), pin live16402b-r3.
- Cases 0–99, paired by (opponent, case). Opponents: LIVE-K4CW-r16 (strong) and R3a.
- Levels: our engine, both sides at the tournament-standard level 11 (equal levels), NOT max level 16. Sam's standing
  rule (10-17, via the BOT LEAD) is that follow-up play evaluations use max levels (16, max King towers) on a
  level-capable engine (RoyaleSim). CYC-AB1 finishes as launched.
- Candidate: the deterministic twin of the live player, K4L-R-gs-mk1a1 (full-pool belief, KF1 net; no wall, so arms
  are paired exactly and differ only in what the belief is told).

**Noise.** live-diag's injector `histnoise:raw` (bot/livediag/history_noise.py, main 566ddfd5b). Opponent spells are
never observed; phantoms come at p = 0.106 per observed non-spell play, 20 ticks later. Every decision is keyed by
(seed, seat, ordinal), so all noisy arms see the same raw stream.

**Arms.**
- **clean:** `K4L-R-gs-mk1a1`, perfect opponent history.
- **hard (today's live):** `histnoise:raw:cyc-hard:K4L-R-gs-mk1a1`. The deployed translator guard (a DerivedD1 mirror
  = `_consistent`) drops cycle conflicts and 9th cards from both the belief events and the D1 rows.
  `BOT_CYCLE_MODEL` is unset (exactly today's code).
- **soft (the hand-off):** `histnoise:raw:cyc-soft:K4L-R-gs-mk1a1` with `BOT_CYCLE_MODEL=soft` (eps 0.1, slack 2,
  cap 400000). The guard is the same on the D1 rows; a cycle conflict reaches the belief as `card?` with p = preal v0
  on sim features.

**Amendment (02:36Z, before any soft-arm result was read).** Sol review r1 found a hidden-cost weighting bug for k\* ≥ 2
(over-pruned explanations, overcharged elixir) and edge cases. The soft arm was stopped after ~40 games, unread
(moved to `cycab1/soft-bug-r0`), and restarted on tree 579ddf11c52f with the fixes, PGID 1264836 on 04. The clean and
hard arms (tree 725699ca87e7) don't run the model, and ab.py is unchanged, so they continue.

**Readout.**
- Primary: soft − hard win rate, pooled over both opponents, paired, with a 95% CI.
- Secondary: per opponent; clean − hard (the size of the problem in this harness); recovery
  = (soft − hard) / (clean − hard).
- Also reported:
  - noise counts per game: spells hidden, phantoms, conflicts, the phantom share of conflicts;
  - sim calibration of p: mean p on real vs phantom conflicts;
  - belief cycle_stats: hidden plays, rejected, max rows.
- Decision rule: ship the hand-off for the live gate if soft − hard ≥ 0 with the CI lower bound > −0.03 and no new
  errors. A positive CI excluding 0 is reported as a gain.

## (a) Sim A/B CYC-AB1: readout (03:39Z, all 600 games, 0 errors)

Job dir `cycab1/{clean,hard,soft}` (03/04, copied to 05). Summary: `python -m bot.cyclemodel.ab_report …` →
cycab1/report.json (0f8ec971…). Paired by (opponent, case); normal 95% CI on the per-pair differences.

| comparison | pooled (n 200) | vs LIVE-K4CW-r16 (n 100) | vs R3a (n 100) |
|---|---|---|---|
| win rate clean / hard / soft | 0.695 / 0.685 / 0.705 | 0.47 / 0.50 / 0.53 | 0.92 / 0.87 / 0.88 |
| hard − clean (size of the problem) | −0.010 [−0.081, +0.061] | +0.03 [−0.09, +0.15] | −0.05 [−0.12, +0.02] |
| **soft − hard (primary)** | **+0.020 [−0.048, +0.088]** | +0.03 [−0.09, +0.15] | +0.01 [−0.06, +0.08] |
| soft − clean | +0.010 [−0.061, +0.081] | +0.06 [−0.06, +0.18] | −0.04 [−0.11, +0.03] |

**Noise per game (soft arm; the hard arm matches):**
- 44 opponent plays; 3.6 spells hidden; 4.4 phantoms.
- 12.3 cycle conflicts, 2.1 of them phantoms (real share 0.83). This is ~2.3× live's 5.4 drops per battle, so the
  harness is a stress test.
- The model's work per game: 2.8 hidden plays, 2.0 phantom-only outcomes; resolver max 20 ms; max rows 1,095.
- Sim calibration of v0 p on sim features: mean 0.71 on real conflicts vs 0.65 on phantoms. The sim features (no
  positions) barely separate the classes, so the elixir/cycle check does the discriminating.

**Reading against the pre-registration:**
- Primary soft − hard = +0.02 with a CI of [−0.048, +0.088]. It is ≥ 0, but the lower bound is not > −0.03, so the
  pre-registered ship rule is **not met**: inconclusive, with no detectable harm and no detectable gain.
- The size of the problem in this harness (hard − clean) is −0.01 [−0.08, +0.06], not detectable. The deterministic
  twin's search barely suffers from a corrupted opponent hand/cycle belief here, so this sim can't size the lever at
  n = 200. Recovery (soft − hard)/(clean − hard) is undefined when clean − hard ≈ 0.

**Limits:**
- Our engine at level 11, not max levels (Sam's new rule applies to follow-ups).
- The twin has no fast tier.
- The D1 stream (pollers, candidate proposals) is guarded the same way in both noisy arms, so only the search belief
  differs.
- Sim P(real) uses v0 on position-free features; live uses the translator's features and v1.

**What it supports:** shipping is safe in sim (0 errors, no loss). Live value has to come from the live gate (decisions
change 13–16% of polls against a 3–5% noise floor, per the translator owner) or a live A/B behind the switch. A
confirmatory sim at max levels would need a RoyaleSim path for the history-noise injector.

## Live-diag sizing at L11 (relayed to this thread after the CYC-AB1 readout)

Full-pool mk1a1, our engine at L11, e16 vs Battle Log decks, BASE11. 200 paired games vs K4C-r16 and 100 vs R3a.
History noise calibrated per play to live: 24% cycle-dropped, ~7–8% phantoms, ~4 hidden spells per long game.
- **Live-like noise − clean:**
  - vs K4C-r16: −0.06 [−0.14, +0.025];
  - vs R3a: +0.06 [−0.01, +0.13];
  - pooled: 0.00 [−0.05, +0.05].
- **Spells only, with the guards:** −0.05 vs K4C-r16, so the phantoms add ~1 pp.
- **Upper bound** for what the cycle model could recover at L11: ~+5 pp vs strong opponents, ~0 vs weak. This agrees
  with CYC-AB1 (hard − clean −0.01 pooled; soft − hard +0.02 [−0.05, +0.09]).
- **Final L11 sizing (the BOT LEAD):** null. Noisy − clean vs K4C-r16 is −0.06 for the mk1a1 arm and +0.10 for the -res
  arm, averaging about +0.02, inside bank noise. The model stays parked, flag-off.
- The L16 cross-check (BASE13) is still running with live-diag. The BOT LEAD will ping only on a real clean − live gap.

## (b) Live gate, P(real) v1: PASS (the translator owner; d4c8eaf24 + translator diff 1fd4a18e…)

- **Translator replay, 80 battles, switch on:** accepted plays unchanged (1,353 = 1,353); 434 soft + 1 ninth.
- **Real-player shadow**, Mac env (FullPoolBelief over CycleBelief verified, `BOT_CYCLE_PREAL` = preal-v1.json, f1a2,
  k1a1, full-pool policies), 7 high-drop battles, off vs v1:
  - 0 errors, 0 native panics or failures; the search was never disabled.
  - cycle_stats per battle: soft 4–18, hidden_plays 0–5.5, phantom_only 1–15, max_ms ≤ 5.3, max_rows ≤ 190.
  - Decisions differ (off vs v1): s41-m01 10.1%, s41-m02 5.9%, s44-m01 1.3%, s47-m03 6.4%, s50-m03 1.3%,
    s60-m02 7.3%. That's fewer than with v0 (13–16%), since phantoms now weigh less.
  - Off-vs-off noise: 2.8% (s41-m01, this tree); 3.2% / 5.0% on the 593beb054 tree.
  - Default cutoffs were similar off vs v1. s57-m03 was discarded: the host was loaded during both arms, and its own
    noise repeat was 21%.
- **Packet check with v1 on:** 0 issues (s41-m01, s47-m03, s57-m03, s60-m02, s63-m01; every 3rd snapshot).
- **Suite** (bot/live, bot/players, bot/cyclemodel): the failure set is identical to d4c8eaf24 without the diff.
- **Not answerable by replay:** whether the changed decisions win more. So the package is ready to ship flag-off,
  pending the L16 sizing and the decision of the BOT LEAD and LIVE LEAD.

## Live-diag L16 sizing (BASE13 = 1869282966218; received after the parking decision)

**Setup:** RoyaleSim at L16 on both sides; s62 deck vs Battle Log decks; full-pool twins FP-LD-K4L-R-gs-rw-fc-c4-mk1a1
and -res; 100 paired cases each vs LIVE-K4CW-r16 and R3a; 800 rows, 0 errors. Data:
04:/mpac/sdicks02/jobs/clasher/bot-livediag/l16noise (+ l16noise-vsbase.json, -vsres.json).

**Noise per game** (histnoise `live`, cycle guard on): cycle_dropped 8.5, phantoms 3.5, spells_hidden 2.2,
ninth_dropped 0.03, out of ~43 enemy plays.

**Live-like noise − clean history:**
- base: −0.015 [−0.09, +0.065] (K4CW 0.00, R3a −0.03). **No gap**, matching the L11 null.
- -res: −0.055 [−0.13, +0.02] (K4CW −0.08 [−0.20, +0.04]). Possibly a gap, but not significant.
  - Under noise, -res banks more (elixir at Giant cross 3.84 → 4.23) and its undefended share rises from 4.8% to 6.5%.

**Reading:** the current base shows no gap at L11 or L16, so the model stays parked. If -res becomes the live player,
first replicate the -res sizing on a fresh bank. Only a replicated gap justifies running cyc-hard vs cyc-soft on -res
at L16 (the RoyaleSim path through `NoisyPlayer.bind_rsim`).

## Live-diag L16 replication (BASE17 = 1817277929115) and the two banks pooled

**BASE17:** L16, s62 deck, vs LIVE-K4CW-r16, 100 paired. Histnoise `live`: 11 cycle drops, 3.3 phantoms and 3.7 hidden
spells per ~47 enemy plays.

| comparison | BASE17 |
|---|---|
| base, live − clean | −0.05 [−0.16, +0.06] |
| -res, live − clean | −0.10 [−0.23, +0.02] |
| -res:live − base:live | +0.13 [0.00, +0.26] |

The BOT LEAD's un-park trigger (-res:live below base:live) did NOT replicate.

**Pooled over BASE13 + BASE17**, computed by me from live-diag's per-game rows (04 job dirs l16noise/rows and
rhcad-live/rows, read-only; paired, normal 95% CI). Caveat: BASE13 is the bank that raised the hypothesis.

| player | live − clean vs K4CW-r16 (n 200) | all opponents (n 300) |
|---|---|---|
| -res | **−0.09 [−0.178, −0.002]** | −0.07 [−0.137, −0.003] |
| base | −0.025 [−0.107, +0.057] | −0.027 [−0.089, +0.035] |

**Reading:**
- For -res (the deployed player, per live-diag), opponent-history noise costs ~7–9 pp vs strong opponents at L16. That
  is borderline significant over two banks, and it is the most a perfect cycle model could recover.
- For base, no gap.
- Whether to un-park (a pre-registered cyc-hard vs cyc-soft A/B on -res at L16 vs K4CW) is the BOT LEAD's call.

## CYC-L16-1: pre-registration (written 2026-10-17T09:37Z, before any game; the BOT LEAD's go of 09:3xZ)

**Question:** for the deployed player (-res, now the live default), does the soft cycle model recover the
opponent-history noise cost at L16 vs a strong opponent?

**Bank.** Base 5793454343180 = sha256('clasher cycle-model L16 A/B CYC-L16-1 2026-10-17') mod 9·10^12 + 10^12. That is
~3.9·10^12 from BASE13 and BASE17, so no seed overlap. 200 paired cases vs LIVE-K4CW-r16.
- Driver: live-diag's L16 Battle Log driver (RoyaleSim, cards and towers at L16 on both sides, Sam's s62 deck vs the 91
  Battle Log decks, seat alternating).
- Driver build: the same one as their rhcad-live run, confirmed with live-diag before launch and recorded in the
  readout.

**Player:** `res`, the -res full-pool serial twin with deadlines cleared, exactly as in the driver.

**Arms** (all on the same raw noisy stream, keyed per (seed, seat, ordinal)):
- **clean:** perfect opponent history.
- **hard (today's bot):** `raw+cychard`. Live-diag's `histnoise:raw` (spells unseen, phantoms; no guard), then the
  deployed translator guard (CycleGuardPlayer 'hard': a DerivedD1 mirror that drops cycle conflicts and 9th cards
  from both the belief events and the D1 rows).
- **soft:** `raw+cycsoft`. The same, but cycle conflicts reach the search belief as `card?` with p from P(real) v1
  (`BOT_CYCLE_PREAL` = reports/bot/cycle-model/preal-v1.json, f9096e22…). `BOT_CYCLE_MODEL=soft` is set only while this
  arm's player starts (bot/cyclemodel/l16_ab.py).

**Amendment (09:56Z, before any CYC-L16-1 row existed): driver provenance.**
- 08 arms (hard, soft): bank.json shows driver_sha256 b586a6a5…, factory 8268a194… (the 08 dk2 mirror) and
  source_commit 3d29d82e6 (verified by me).
- 04 clean arm: it was still queued in cpu_job when live-diag patched the shared driver in place (a `wintp` token, and
  a "nogit" source_commit fallback), so it loads driver 81b46c27… (sha computed by me) and factory 0b8181c8… (04
  deckopt2; live-diag: the same code as 8268a194… with patched ROOT paths).
- Live-diag confirms neither patch touches `res` / `--noise clean` or a git source tree. They froze the driver at
  81b46c27… until CYC-L16-1 finishes (further edits go to cadence-dev/).

**Readout:**
- **Primary:** soft − hard win rate, paired, normal 95% CI.
- **Ship bar (the BOT LEAD's):** CI lower bound > −0.03 AND point estimate > 0. If met, the flag-off package goes to the
  LIVE LEAD as a live A/B candidate.
- **Secondary:** clean − hard (the size of the problem on this bank), and recovery = (soft − hard) / (clean − hard).
- **Also reported:** errors and issues per arm; noise counts per game (drops, phantoms, hidden spells); the model's
  work (cyc_*, belief_*); undefended share and elixir at the Giant cross where the driver logs them.

## CYC-L16-1: readout (all 600 games done 10:47Z; 0 errors)

Job dir cycl16/{clean,hard,soft} (08/04, copied to 05). Paired by (opponent, index); normal 95% CI.
Files: cycl16/readout.json (48a8a2a2…) and live-diag's `bot.livediag.l16_report` output cycl16/l16_report.json
(c84cfaf9…); the two agree.

| arm | win rate vs LIVE-K4CW-r16 (n 200) |
|---|---|
| clean (`res`) | 0.670 |
| hard, today's (`res-cych` / raw) | 0.580 |
| soft + P(real) v1 (`res-cycs` / raw) | 0.625 |

| comparison | Δ [95% CI] |
|---|---|
| **soft − hard (primary)** | **+0.045 [−0.022, +0.112]** |
| clean − hard (size of the problem on this bank) | +0.090 [+0.011, +0.169] |
| soft − clean | −0.045 [−0.129, +0.039] |
| recovery (soft − hard) / (clean − hard) | 0.50 |

**Against the pre-registered ship bar** (CI lower bound > −0.03 AND point estimate > 0): −0.022 > −0.03 and +0.045 > 0,
so it **PASSES**. The gain itself is not significant at n = 200. On this fresh bank the noise cost for -res replicates
and is significant (+0.09), and the soft model recovers about half of it.

**Secondary (l16_report):**

| metric | clean | hard | soft |
|---|---|---|---|
| Giant reaction p50 / p90 (s) | 1.5 / 6.0 | 2.0 / 6.0 | 2.0 / 6.5 |
| undefended share | 0.016 | 0.023 | 0.023 |
| elixir at the Giant cross, p50 | 4.14 | 4.23 | 4.40 |
| CPU ms per decision (serial twin) | 401 | 423 | 415 |

**Noise per game** (the same in both noisy arms): 46 enemy plays; 3.5 spells hidden; 4.5 phantoms; 12.4 cycle
conflicts, ~2.0 of them phantoms.

**Model work per game (soft):** 12.4 soft plays; 2.6 unseen plays; 2.0 phantom-only; mean per-game max resolver
31 ms; mean max rows 1,392.

**Other row flags:** "unmapped public rows" (a RoyaleSim SpearGoblin_Dummy unit) in 73 / 73 / 71 rows of clean / hard
/ soft. The rate is the same in every arm and in live-diag's own rhcad-live (144/400), a harness quirk shared by all
arms.

**Caveats:**
- One bank, one opponent (the strong one, per the brief), deterministic serial twin (no wall clock).
- In live, the first-conflict resolver cost (≤ ~120 ms on loaded fleet hosts; ≤ 5.3 ms max_ms in the Mac-env shadow)
  should be watched in the live A/B's cutoff stats.
