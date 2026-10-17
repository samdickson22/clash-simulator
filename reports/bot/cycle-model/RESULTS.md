# Opponent cycle model: RESULTS (exploration)

Design: DESIGN.md. Code: bot/cyclemodel/{belief,preal,ab,parity}.py, plus the hook in bot/fullpool/belief.py.

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

## (a) Sim A/B: pre-registration (written 2026-10-17T02:17Z, before any game)

**Bank and players.**
- Bank CYC-AB1: base 1185182611752721 = sha256('clasher cycle-model sim A/B CYC-AB1 2026-10-17T02:17Z') mod 2^52.
  e16bl decks (e16 vs the 91 Battle Log decks, opponent-decks-20261016.jsonl 3a7c4e78…), pin live16402b-r3.
- Cases 0–99, paired by (opponent, case). Opponents: LIVE-K4CW-r16 (strong) and R3a.
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
