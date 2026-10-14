# Candidate quality for K4S-st: wider and other proposers (exploration)

2026-10-14, by a bot-lead implementation sub-agent, on 127x03. This is exploration tier, not preregistered. The log is in [PROGRESS.md](PROGRESS.md).

**Question.** K4S-st beat K4S-b64 by adding R3a's top-8 plays to the search's candidates. Do more proposals, or proposals from a stronger proposer, help further? The stronger proposer is ExIt student **K**: 0.863 vs v1, +0.120 paired vs R3a.

**Answer: not reliably.**
- **R3a top-16 (r16)** gains about +0.04 on the HEADLINE bank in both engines. On a fresh bank the gain shrinks and is not significant: +0.022 [−0.004, +0.048] over 600 cases in RoyaleSim, and +0.014 [−0.013, +0.042] over 300 cases in both engines.
- **K as proposer (r0-k8), or merged with R3a's list (r8-k8):**
  - gains about +0.04 in our engine;
  - is null in RoyaleSim, the primary engine.
- **Combining both (r16-k16)** gives nothing, even in ours.

**K4S-st stays the best bot.**

## Arms

All arms are in `bot/search/candidates.py` and registered as `K4C-…` in `make_player`.
- Only the `policy_proposals` list passed to the frozen `C56RolloutPlanner.candidates` changes. It sits after the script decision, WAIT and the 4 scripted ranks, and before the 16 random samples.
- R3a stays the 5-tick poller, the coarse-scan hint and the S-default cutoff default.
- The scorer, waits, top-8 refine and rng streams are unchanged.

| brief # | name | proposals |
|---|---|---|
| — | `K4C-r8` | R3a top-8. **This is K4S-st.** |
| 1 | `K4C-r16` | R3a top-16. The first 8 come from the cache; the forward is re-run for the rest and asserted to match. |
| 2 | `K4C-r8-k8` | R3a top-8, then K's top-8 (duplicates dropped; R3a's win ties) |
| 3 | `K4C-r16-k16` | R3a top-16 ∪ K's top-16 |
| 4 | `K4C-r0-k8` | K's top-8 only |

**K checkpoint:**
- path: `/mpac/sdicks02/repos/clasher-bot-runtime/students/K-it3K-step002000.pt` on 03 and 04, read-only;
- source: `bot-exit-r1-04/ckpt-it3K/step-002000.pt`;
- sha256 `ed5a4936c46ec184c3e618c20e8907753ac80f1efa30d03c910b9cc905038052`, asserted at load.
- Only K's ranking is used; its play threshold is ignored.

**Arm 5 (reorder the coarse scan) is skipped because it cannot change anything.**
- K4S-st has no cutoff, so `anchor.anytime` runs the coarse rollout for every play.
- Both the top-8 selection and the argmax break exact ties by candidate-list position.
- The scan order therefore only matters under a deadline.

**Validity checks:**
- **Equivalence:** these all reproduce K4S-st's `command_sha256` on 20/20 games each (cases 0–9 × R3a and v1; `bot-cand-eq`):
  - `K4C-r8`;
  - `K4C-r0-k8@R3a.pt`, i.e. the K-proposer path loaded with R3a's checkpoint;
  - `K4C-r8-k8@R3a.pt`.
- **No errors:** 0 errors in any run, 8,040 games in total.
- **Determinism:** deterministic, with no wall clock.

## Results

**Statistics:**
- HEADLINE-v1: cases 0–299 × {R3a, v1}; win 1, draw 0.5, loss 0.
- 95% bootstrap CIs, 4,000 draws.
- Paired = arm − K4S-st on the same cases.
- "both" = equal-weight mean over R3a and v1, with cases resampled within each opponent.
- K4S-st baselines: `bot-search-bc` (ours) and `bot-search-rsim-st` (RoyaleSim), the games behind HEADLINE.md.

**CPU column:** the candidate's process time inside `act` on searched decisions, in our engine.
- All arms in the ours table ran concurrently on 03, so they are comparable with each other.
- The load-matched K4S-st is `K4C-r8` (identical computation, 100 games run alongside): 0.398 s.
- K4S-st's original 0.332 s was measured at a different load. Compare **rollouts/decision** instead, which does not depend on load.

| arm | CPU s/decision | rollouts / decision | plays scanned / decision | ours: vs R3a | ours: vs v1 | **ours: paired vs K4S-st (both)** | RoyaleSim: vs R3a | RoyaleSim: vs v1 | **RoyaleSim: paired vs K4S-st (both)** |
|---|---:|---:|---:|---|---|---|---|---|---|
| K4S-st (= K4C-r8) | 0.398 | 37.1 | 16.9 | 0.720 | 0.860 | – | 0.723 | 0.890 | – |
| 1: K4C-r16 | 0.429 | 41.0 | 21.3 | 0.753 | **0.917** | **+0.045 [+0.008, +0.082]** | **0.797** | 0.900 | **+0.042 [+0.007, +0.077]** |
| 2: K4C-r8-k8 | 0.409 | 37.6 | 17.75 | 0.777 | 0.880 | +0.038 [+0.003, +0.075] | 0.740 | 0.833 | −0.020 [−0.057, +0.017] |
| 3: K4C-r16-k16 | 0.447 | 43.2 | 23.6 | 0.737 | 0.880 | +0.018 [−0.020, +0.057] | not run (below +0.02) | | |
| 4: K4C-r0-k8 | 0.359 | 36.7 | 16.8 | 0.770 | 0.887 | +0.038 [+0.003, +0.073] | 0.757 | 0.873 | +0.008 [−0.030, +0.045] |

Per-opponent paired differences:

| arm | ours: R3a | ours: v1 | RoyaleSim: R3a | RoyaleSim: v1 |
|---|---|---|---|---|
| r16 | +0.033 [−0.027, +0.090] | +0.057 [+0.013, +0.100] | +0.073 [+0.020, +0.127] | +0.010 [−0.033, +0.053] |
| r8-k8 | +0.057 [+0.003, +0.110] | +0.020 [−0.027, +0.070] | +0.017 [−0.040, +0.073] | −0.057 [−0.103, −0.010] |
| r16-k16 | +0.017 [−0.040, +0.073] | +0.020 [−0.030, +0.073] | – | – |
| r0-k8 | +0.050 [+0.000, +0.103] | +0.027 [−0.023, +0.077] | +0.033 [−0.023, +0.090] | −0.017 [−0.063, +0.030] |

### Fresh-bank confirmation (r16 only)

The fresh bank is **BASE 736861114989648**, drawn with `os.urandom` on 2026-10-14 13:38Z, before any RoyaleSim result. K4S-st and K4C-r16 play R3a and v1 on it.

| engine | cases | K4S-st vs R3a / v1 | r16 vs R3a / v1 | paired vs R3a | paired vs v1 | **paired, both** |
|---|---|---|---|---|---|---|
| RoyaleSim | 0–299 | 0.723 / 0.867 | 0.747 / 0.877 | +0.023 [−0.037, +0.083] | +0.010 [−0.037, +0.057] | +0.017 [−0.020, +0.055] |
| ours | 0–299 | 0.723 / 0.897 | 0.750 / 0.893 | +0.027 [−0.030, +0.087] | −0.003 [−0.047, +0.040] | +0.012 [−0.027, +0.050] |
| both engines, mean per case | 0–299 | | | | | +0.014 [−0.013, +0.042] |
| RoyaleSim | 300–599 | 0.713 / 0.873 | 0.773 / 0.870 | +0.060 [+0.000, +0.123] | −0.003 [−0.047, +0.043] | +0.028 [−0.010, +0.067] |
| **RoyaleSim, extended** | **0–599** | 0.718 / 0.870 | 0.760 / 0.873 | +0.042 [−0.002, +0.083] | +0.003 [−0.030, +0.037] | **+0.022 [−0.004, +0.048]** |

For comparison, the HEADLINE bank pooled over both engines gives **+0.043 [+0.021, +0.067]**.

**CPU, load-matched on the fresh bank in ours:**

| bot | s/decision | rollouts/decision |
|---|---:|---:|
| K4S-st | 0.350 | 36.9 |
| r16 | 0.429 | 41.3 |

So r16 costs about +12% rollouts and +10–20% CPU.

## Reading

- **More R3a proposals (r16).**
  - Ranks 9–16 add 4.4 plays per decision; the refine stays top-8.
  - On the bank it was selected on, r16 gains +0.04 in both engines, consistently across seats.
  - On an independent bank it gains +0.022 [−0.004, +0.048] in RoyaleSim over 600 cases, and +0.012 in ours over 300 cases. Neither is significant.
  - All 5 paired estimates are positive. The gain is mostly vs R3a (RoyaleSim: +0.073 on the HEADLINE bank, +0.042 on the fresh bank); vs v1 it is about 0 in RoyaleSim.
  - Selecting the best of 4 arms on one bank inflates its estimate. The honest estimate is a small positive effect, about +0.02, that 600 cases cannot resolve.
- **K as a proposer.**
  - K's top-8 has only 1.4 plays per decision outside R3a's top-8; the union picks one of them on 6.8% of decisions.
  - Replacing R3a's list with K's, or merging them, helps in ours (+0.038) but not in RoyaleSim (+0.008 and −0.020).
  - A stronger standalone policy is not a better proposer for this search. This repeats the K4S-st@student:D null, and here R3a stays the default.
  - What K adds is mostly plays that win under our engine's rollout model and do not transfer to RoyaleSim.
- **Bigger unions don't stack.** r16-k16 scans the most plays (23.6) and gains less than either component (+0.018). The top-8 refine is fixed, so extra coarse-only candidates mostly add coarse-scan ties and noise.
- **Overall:** candidate quality was the lever for b64 → st, about +0.06–0.10. Its marginal value beyond st is now small. The near-tied phi scorer (median top-2 gap of 0.0005) is the limit, not the candidate list.

## Recommendation

- **K4S-st stays the HEADLINE best bot.** No arm passed the fresh-bank confirmation at 95%.
- **K4C-r16 is the strongest candidate variant.**
  - It is a likely small gain: about +0.02 in the primary engine, mainly vs R3a.
  - It costs about +12% rollouts.
  - It is the only arm worth more cases. A ≥1,200-case fresh bank per opponent in RoyaleSim would resolve +0.02.
- **Drop K as a proposer.** It does not transfer to RoyaleSim, and its gain in ours is engine-specific.
- **Drop wider unions.**
- **For the next real lever**, look past the candidate set to the scorer: the near-tied phi and the scripted rollout opponents.

Raw logs are on 127x03 under `/mpac/sdicks02/jobs/clasher/`:

| directory | contents |
|---|---|
| `bot-cand-eq` | equivalence checks and smoke |
| `bot-cand-ours` | 4 arms, ours, HEADLINE bank |
| `bot-cand-ours-r8` | load-matched K4S-st |
| `bot-cand-rsim` | 3 arms, RoyaleSim, HEADLINE bank |
| `bot-cand-fresh-rsim`, `bot-cand-fresh-rsim2` | fresh bank, RoyaleSim, cases 0–299 and 300–599 |
| `bot-cand-fresh-ours` | fresh bank, ours |

Reproduce with:

```
python -m bot.search.report <dirs> --baseline K4S-st --opponents R3a,v1
python bot/eval/pair_by_name.py BASEDIR K4S-st ARMDIR K4C-r16
```

Runner: `bot-cand-bin/run.sh {bot.search.cand_run|bot.eval.headline} ARGS`.
