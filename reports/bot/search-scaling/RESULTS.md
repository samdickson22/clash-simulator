# Does more search compute make K4S stronger? (exploration)

2026-10-14, by a bot-lead sub-agent. This is exploration tier with no preregistration. All runs were on 127x03.

**Protocol:** HEADLINE-v1 (`reports/bot/HEADLINE.md`):
- cases 0–299 per opponent, base 1455777415631152;
- win 1, draw 0.5, loss 0;
- 95% bootstrap CIs over games (4,000 draws).

**Paired difference:** arm − K4S-b64 on the same case indices.
- Baseline logs: `/mpac/sdicks02/jobs/clasher/bot-headline-r1/`, and `bot-headline-rsim-r1/` for RoyaleSim.
- "both" is the equal-weight mean over R3a and v1, with cases resampled within each opponent.

Code is in `bot/search/` (`players.py`, `run.py`, `report.py`, `diag_roots.py`). It is registered in `bot/eval/headline.py` `make_player` under the prefix `K4S-<tokens>`. No frozen code was edited.

## Validity checks
- **Exact wrapper.** K4S-m1, my wrapper with one root and the frozen scorer, reproduces K4S-b64's `command_sha256` on:
  - 60/60 games in our engine;
  - 20/20 games in RoyaleSim.

  Every arm differs from the baseline only in the knob it names.
- **Determinism.** Every arm uses no wall clock and has no budget cut (0 hits).
- **Errors.** No games errored, in any arm.

## Table: our engine (Python C56), opponents R3a and v1

- **CPU s/decision** is the candidate's process time inside `act` on searched decisions.
- **s/game** is that time summed per game.
- **Rollouts/decision** counts single-root rollouts at the arm's horizon. This column does not depend on host load.

| arm | what changes | CPU s/decision | CPU s/game | rollouts/decision | vs R3a | vs v1 | paired diff vs R3a | paired diff vs v1 | **paired diff, both** |
|---|---|---:|---:|---:|---|---|---|---|---|
| K4S-b64 (baseline) | – | 0.325† | 40† | 35.1† | 0.633 [0.580, 0.687] | 0.830 [0.787, 0.870] | – | – | – |
| A: K4S-m4 | 4 determinizations, mean score | 1.095 | 132 | 140.5 | 0.613 [0.557, 0.667] | 0.802 [0.755, 0.846] (298) | −0.020 [−0.080, +0.040] | −0.030 [−0.084, +0.020] | −0.025 [−0.064, +0.015] |
| B: K4S-w48 | 48 random legal samples, not 16 | 0.472 | 56 | 54.5 | 0.603 [0.547, 0.660] | 0.867 [0.827, 0.903] | −0.030 [−0.097, +0.033] | +0.037 [−0.013, +0.087] | +0.003 [−0.038, +0.043] |
| B: **K4S-st** | R3a's top-8 plays become candidates | 0.332 | 39 | 37.0 (37.3 on m1's cases) | **0.720 [0.670, 0.770]** | 0.860 [0.820, 0.900] | +0.087 [+0.027, +0.147] | +0.030 [−0.020, +0.080] | **+0.058 [+0.018, +0.100]** |
| B: K4S-stl | as st, but appended last (loses ties) | 0.243‡ | 29‡ | 37.0 | 0.710 [0.657, 0.760] | 0.877 [0.840, 0.913] | +0.077 [+0.017, +0.137] | +0.047 [−0.003, +0.097] | +0.062 [+0.023, +0.102] |
| B: K4S-sr | as st, plus forced 3-style refine | 0.241‡ | 28‡ | 41.7 | 0.723 [0.673, 0.773] | 0.870 [0.830, 0.907] | +0.090 [+0.030, +0.150] | +0.040 [−0.010, +0.090] | +0.065 [+0.025, +0.107] |
| B: K4S-st-w48 | st and w48 combined | 0.451 | 52 | 56.6 | 0.680 [0.627, 0.733] | 0.890 [0.853, 0.923] | +0.047 [−0.020, +0.113] | +0.060 [+0.010, +0.110] | +0.053 [+0.013, +0.095] |
| C: K4S-h320 | 320-tick rollouts, not 160 | 0.428 | 53 | 31.0 (×320 t) | 0.603 [0.547, 0.660] | 0.737 [0.687, 0.787] | −0.030 [−0.093, +0.033] | **−0.093 [−0.153, −0.033]** | **−0.062 [−0.107, −0.017]** |

† The baseline cost comes from K4S-m1 on cases 0–29 against both opponents (60 games, identical computation to b64).

‡ stl and sr ran at a different point in 03's load. Their CPU seconds are therefore not comparable with st's 0.33. Compare rollouts/decision instead: st ≈ stl ≈ baseline + 2, and sr ≈ baseline + 6.

## Full HEADLINE-v1 P1 rows for K4S-st (both engines)

| engine | candidate | vs v1 | vs R3a | vs scripted-balanced | vs scripted-pressure | **pool P1** | pool paired diff vs b64 |
|---|---|---|---|---|---|---|---|
| ours (Python C56) | K4S-b64 | 0.830 [0.787, 0.870] | 0.633 [0.580, 0.687] | 0.997 | 0.997 | 0.864 [0.847, 0.881] | – |
| ours (Python C56) | **K4S-st** | 0.860 [0.820, 0.900] | 0.720 [0.670, 0.770] | 0.997 | 0.993 | **0.892 [0.877, 0.908]** | **+0.028 [+0.008, +0.049]** |
| RoyaleSim 15.535 | K4S-b64 | 0.797 [0.750, 0.840] | 0.617 [0.563, 0.673] | 0.993 | 0.997 | 0.851 [0.833, 0.869] | – |
| RoyaleSim 15.535 | **K4S-st** | 0.890 [0.853, 0.923] | 0.723 [0.670, 0.773] | 0.997 | 0.993 | **0.901 [0.885, 0.916]** | **+0.050 [+0.029, +0.071]** |

RoyaleSim paired differences for K4S-st − K4S-b64:

| opponent | paired difference |
|---|---|
| R3a | +0.107 [+0.043, +0.170] |
| v1 | +0.093 [+0.040, +0.147] |
| both | +0.100 [+0.060, +0.142] |
| scripted-balanced | +0.003 |
| scripted-pressure | −0.003 |

The scripted opponents are saturated in both engines.

CPU s/game (whole match, both seats) for K4S-st is 45–78 in ours and 41–72 in RoyaleSim, about the same as b64.

## What "st" changes, exactly
K4S already runs the cached R3a student at every poll. Before this change it used the student's top-8 legal plays only as `coarse_order`, which changes the coarse-scan *order*, not the scores or the candidate set.

K4S-st passes those same 8 plays as `policy_proposals` to the frozen `C56RolloutPlanner.candidates`. These are the student's ranking of plays, ignoring its play/wait gate.
- **Position in the list:** after the script decision, WAIT and the 4 scripted ranked plays; before the 16 random legal samples.
- **Deduplication and masking:** duplicates are dropped and the public mask applies.

Each new play is then scored exactly like any other play:
- a balanced 160-tick coarse rollout;
- if it ranks in the top 8, pressure and defense rollouts as well.

On average about 2 student plays per decision were not already candidates (+2.2 rollouts per decision on the same cases, about +4% compute). Nothing else changes: not the scorer, the waits, the S-default, nor any rng stream.

**Mechanism checks.**
- **stl:** the student plays are appended last, so they lose the frequent exact ties. It gives the same gain, +0.062. The gain therefore comes from the *new candidates*, not from tie-breaking.
- **sr:** forcing the student plays into the full refinement adds nothing, +0.065 ≈ +0.058.
- **st-w48:** adding more random samples on top of st adds nothing, +0.053.

## Why the other axes don't help
- **A: determinizations.** Mean over M=4 roots costs 3.4× and gives −0.025 [−0.064, +0.015].
  - `diag_roots` (8 roots, 2 games, ~70 decisions each) shows the belief collapses early. Eight samples hold about 2.1–2.3 distinct opponent (hand, cycle) states, and 8 only at tick 90, because the human-deck prior identifies these catalog decks after a few plays.
  - Across all 600 m4 games, a single root's argmax differs from the mean-choice on 4.0% of decisions. The chosen action's score SD across roots is 0.0015.
  - Hidden information is not the bottleneck here. This may differ against off-catalog decks, which these tests do not cover.
- **The scorer is near-tied.** The median gap between the best and second-best candidate is 0.0004–0.0005 in phi units. More samples of the same weak evaluator do not separate candidates.
- **B: random width.** More *random* candidates (w48) are neutral at +0.003. Better candidates, from st, help.
- **C: horizon.** A 320-tick horizon *hurts*, −0.062 [−0.107, −0.017], mostly vs v1 (−0.093). The leaf phi is a static potential (crowns, tower HP, king pressure, board value, danger ETA, elixir), which is reasonable at either horizon. The likely cause is the 16 s of scripted self- and opponent-play inside the rollout: it diverges further from how real opponents play, and its noise outweighs the longer look-ahead.

## Recommendation
- **Adopt K4S-st as the new best bot** (HEADLINE candidate). It is K4S-b64 with the R3a student's top-8 plays as search candidates.
  - **Pool P1:** 0.864 → 0.892 in ours and 0.851 → 0.901 in RoyaleSim. The paired pool gains are +0.028 [+0.008, +0.049] and +0.050 [+0.029, +0.071].
  - **Cost:** about +4% compute.
- **Raw compute does not scale strength.** More roots, more random candidates and longer rollouts were neutral or negative. The lever is *candidate quality*.
- **Next steps:**
  - Try a stronger or larger proposer, e.g. student top-16 or a v1 top-k.
  - Try a better leaf evaluator (value net) in place of the near-tied phi.
  - Do not spend more CPU on rollouts.

Raw logs on 127x03, under `/mpac/sdicks02/jobs/clasher/`:

| directory | contents |
|---|---|
| `bot-search-a` | m4 |
| `bot-search-bc` | w48, st, h320 |
| `bot-search-m1` | m1 equivalence check |
| `bot-search-st2` | st-w48, stl, sr |
| `bot-search-st-p1` | st vs the scripted bots |
| `bot-search-rsim-st` | K4S-st in RoyaleSim, all four P1 opponents |
| `bot-search-rsim-m1` | m1 equivalence check in RoyaleSim |
| `bot-search-diag/` | `diag_roots` output |

Reproduce with `python -m bot.search.report <dirs> [--opponents ...]`.
