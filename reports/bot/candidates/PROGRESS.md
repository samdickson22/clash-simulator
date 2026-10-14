# Candidate quality for K4S-st: progress log (resumable)

Task: the bot lead's 2026-10-14 brief. These are exploration-tier arms that change only which policy proposals enter K4S-st's candidate set. Results go in [RESULTS.md](RESULTS.md).

## Code
- `bot/search/candidates.py` defines `K4C-` names, registered in `bot/eval/headline.py` `make_player`:
  - `r<N>`: R3a's top-N plays;
  - `k<M>`: K's top-M plays, appended after R3a's;
  - `@<ckpt>`: overrides the second proposer.
- `K4C-r8` is K4S-st.
- `bot/search/cand_run.py` is `bot.search.run`, plus per-decision diagnostics: plays_scanned, k_new and from_second.
- Arms:

  | brief # | name | proposals |
  |---|---|---|
  | 1 | `K4C-r16` | R3a top-16 |
  | 2 | `K4C-r8-k8` | union of R3a top-8 and K top-8 |
  | 3 | `K4C-r16-k16` | union of R3a top-16 and K top-16 |
  | 4 | `K4C-r0-k8` | K top-8 only |

  In every arm R3a is still the poller and the S-default.
- Arm 5 (reorder the coarse scan) is skipped because it cannot change anything:
  - With no cutoff (unbounded mode, as in K4S-st), `anchor.anytime` runs the coarse rollout for every play.
  - The top-8 selection and the argmax break exact ties by `original.index`, i.e. candidate-list position, not scan order.
  - So coarse_order only matters under a cutoff.

## K checkpoint
- Source: `bot-exit-r1-04/ckpt-it3K/step-002000.pt` on 04. It is identical on 08 (`bot-exit-r1/ckpt-it3K`).
- sha256: `ed5a4936c46ec184c3e618c20e8907753ac80f1efa30d03c910b9cc905038052`.
- Copied read-only to `/mpac/sdicks02/repos/clasher-bot-runtime/students/K-it3K-step002000.pt` on 03 and 04.
- The loader asserts this sha.
- K's threshold (0.5075 on-policy) is unused: only K's ranking is used.

## Runs (03, `/mpac/sdicks02/jobs/clasher/`)
- Runner: `bot-cand-bin/run.sh MODULE ARGS` (runtime r1 env, nice 10), detached with `bot/detach.sh`.
- `bot-cand-eq` (2026-10-14 13:13Z, PID 4305):
  - equivalence arms: `K4C-r8`, `K4C-r0-k8@R3a.pt` and `K4C-r8-k8@R3a.pt`, each expected to equal K4S-st in `bot-search-bc`;
  - smoke for the 4 real arms;
  - cases 0–9 vs R3a and v1.

  - **Result: equivalence holds.** `K4C-r8`, `K4C-r0-k8@R3a.pt` and `K4C-r8-k8@R3a.pt` each reproduce K4S-st's `command_sha256` on **20/20** games.
  - The 4 real arms differ on 20/20, as expected.
  - 140 games, 0 errors.
  - Diagnostics on these few games:
    - r16 adds about 1.5 plays per decision;
    - K's top-8 has about 1.1 plays per decision that are not in R3a's top-8.
- `bot-cand-ours` (13:17Z, PID 18719, 84 workers): `K4C-r16`, `K4C-r8-k8`, `K4C-r16-k16` and `K4C-r0-k8` × R3a and v1 × cases 0–299.
- `bot-cand-ours-r8` (13:17Z, PID 18730, 10 workers): `K4C-r8` (= K4S-st) on cases 0–49 × R3a and v1.
  - This is a load-matched CPU reference: the original K4S-st numbers come from a different point in 03's load.
- 04 has no room (109 python processes at 13:16Z), so everything runs on 03.

- **Interim, 13:38Z.** K4C-r16 is complete in ours: paired vs K4S-st both **+0.045 [+0.008, +0.082]**, so it qualifies for RoyaleSim. CPU is 0.429 s/decision vs 0.398 for the load-matched r8; rollouts are 41.0 vs 37.1.
- **Fresh-bank BASE**, drawn 2026-10-14 13:38Z on 05 with `int.from_bytes(os.urandom(6),'big')<<4`: **736861114989648**. It was drawn before any RoyaleSim result.

- **`bot-cand-ours` done at 14:04Z:** 2,400 games, 0 errors.
  - Paired vs K4S-st (`bot-search-bc`), both opponents:

    | arm | paired diff | qualifies |
    |---|---|---|
    | r16 | +0.045 [+0.008, +0.082] | yes |
    | r8-k8 | +0.038 [+0.003, +0.075] | yes |
    | r0-k8 | +0.038 [+0.003, +0.073] | yes |
    | r16-k16 | +0.018 [−0.020, +0.057] | no, below +0.02 |

  - Reproduce with `python -m bot.search.report $J/bot-cand-ours $J/bot-cand-ours-r8 $J/bot-search-bc --baseline K4S-st`.
- `bot-cand-rsim` (14:04Z, PID 181820, 90 workers): r16, r8-k8 and r0-k8 × R3a and v1 × cases 0–299, rsim15535, on the HEADLINE bank.

- **`bot-cand-rsim` done at 14:36Z:** 1,800 games, 0 errors.
  - Paired vs K4S-st (`bot-search-rsim-st`), both opponents:

    | arm | paired diff | holds? |
    |---|---|---|
    | **r16** | **+0.042 [+0.007, +0.077]** (R3a +0.073, v1 +0.010) | yes |
    | r0-k8 | +0.008 [−0.030, +0.045] | no |
    | r8-k8 | −0.020 [−0.057, +0.017] | no |

  - Only r16 holds.
  - Reproduce with `python -m bot.search.report $J/bot-search-rsim-st $J/bot-cand-rsim --baseline K4S-st`.
- `bot-cand-fresh-rsim` (14:36Z, PID 287438, 94 workers): K4C-r16 and K4S-st × R3a and v1 × cases 0–299, BASE 736861114989648, rsim15535.

- **`bot-cand-fresh-rsim` done at 14:56Z:** 1,200 games, 0 errors.
  - K4S-st scored 0.723 vs R3a and 0.867 vs v1.
  - K4C-r16 scored 0.747 vs R3a and 0.877 vs v1.
  - Paired r16 − st:

    | opponent | paired diff |
    |---|---|
    | R3a | +0.023 [−0.037, +0.083] |
    | v1 | +0.010 [−0.037, +0.057] |
    | **both** | **+0.017 [−0.020, +0.055]** |

  - The direction holds but the effect is not significant. It is smaller than on the HEADLINE bank, as expected for the best of 4 arms (winner's curse).
- `bot-cand-fresh-ours` (14:57Z, PID 350925, 94 workers): K4C-r16 and K4S-st × R3a and v1 × 300, BASE 736861114989648, ours, via `cand_run` (load-matched CPU).

- **`bot-cand-fresh-ours` done at 15:18Z:** paired r16 − st, both = +0.012 [−0.027, +0.050]. CPU is st 0.350 vs r16 0.429 s/decision; rollouts are 36.9 vs 41.3.
- Both engines pooled: +0.014 [−0.013, +0.042].
- `bot-cand-fresh-rsim2` (15:19Z, PID 421135): the same as fresh-rsim, cases 300–599.
  - Done at 15:38Z.
  - Cases 300–599: +0.028 [−0.010, +0.067].
  - **Cases 0–599: +0.022 [−0.004, +0.048]** (R3a +0.042, v1 +0.003).
- Total: 8,040 games, 0 errors.

## Status: DONE (15:40Z)
- RESULTS.md is written.
- Recommendation: K4S-st stays the best bot. r16 is a likely small gain but unconfirmed; K as a proposer does not transfer to RoyaleSim.
- No processes of this task are left running on 03.
2. Pair against K4S-st from `bot-search-bc`, using `bot.search.report --baseline K4S-st`.
3. Any arm at ≥ +0.02: run it in RoyaleSim (`bot-cand-rsim`), then a fresh-bank confirmation.
