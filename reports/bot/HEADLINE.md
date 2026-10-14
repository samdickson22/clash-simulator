# HEADLINE: our best bot vs a fixed opponent pool (exploration, tracked daily)

The single tracked number is **pool score in RoyaleSim (15.535.29 rules)**, with our engine as a second column (DECISION-ENGINE.md). Pool score is: the candidate's mean score (win 1, draw 0.5, loss 0) against each pool
opponent, averaged with equal weight over opponents. It is reported in each engine. Every row is exploration-tier.

## Protocol HEADLINE-v1 (fixed 2026-10-14)

- **Match loop:** `bot/players/ours.py:play_match`, the X4S harness loop.
  - Symmetric 27-tick command lag with one outstanding command.
  - Every seat is polled every 5 ticks from tick 90; search acts on 10-tick multiples.
  - Abilities are off. Level 11. Full 3 + 2 min.
- **Engines:**
  - **ours:** Clasher Python engine, C56. The X4S-pinned runtime is `clasher-bot-runtime/r1`, with native
    44874fd6, v1 d77005d5 and R3a 37509a43.
  - **RoyaleSim:** royalesim 0.1.34 with `client_arms("15.535.29")`, the arm that best matched the native recordings
    (FIDELITY.md). Driven through `bot/players/royalesim_match.py` once that lands.
- **Cases:** `x4s_setup(i, BASE)` for i = 0…299, with `BASE = 1455777415631152`.
  - BASE is a fresh bank, `int.from_bytes(os.urandom(6),'big') << 4`, drawn 2026-10-14.
  - Case i puts the candidate in seat i%2, with X-deck i%5 against X-deck (i//5)%5. Both decks are shuffled by
    `Random(BASE+i)`.
  - The same cases are used against every opponent and in every engine.
- **Pool P1 (fixed):**
  - `v1`: the human-prior imitation policy, T=1 sampling;
  - `R3a`: the root-distilled student with its calibrated gate;
  - `scripted-balanced` and `scripted-pressure`: `PublicScriptedOpponent`, C56.
- **Candidate (the "best bot"):** `K4S-b64`.
  - This is the K4 W-screen8 public search with the R3a student as cutoff default, run with a **deterministic
    64-rollout budget** instead of a wall-clock deadline (`SearchPlayer(mode='budget', budget=64, default='R3a')`).
  - It is hardware-independent and reproducible.
  - A full decision is about 45 rollouts, so b64 is close to the unbounded KU.
- **Statistics:** 95% bootstrap CI over games per opponent. The pool CI resamples games within each opponent.
- **Run:**

  ```
  CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1 python -m bot.eval.headline \
      --out DIR --candidate K4S-b64 --opponents v1,R3a,scripted-balanced,scripted-pressure --games 300 --workers 96
  python -m bot.eval.summarize DIR
  ```

## Protocol HEADLINE-v2 (2026-10-14, coordinator request: external opponents)

Everything is as in v1 (same cases, BASE, candidate and match loop), with two changes:
- **Engine:** RoyaleSim only. The external opponents are RoyaleSim-native and act on RoyaleSim state.
- **Pool P2 = P1 ∪ external.** The external members are:
  - RoyaleGym's shipped scripted opponents, from upstream RoyaleGym `royalegym/opponents.py` (MIT), wrapped by
    `bot/players/royalesim_opponents.py`: `rgym-patient` (ready=3), `rgym-push`, `rgym-defend` and
    `rgym-first-affordable`;
  - `rext-*`: any RoyaleLearn/RoyaleImitate reference policies plus a policy trained with RoyaleLearn's own trainer
    on our decks, when available (`reports/bot/external-opponents/`).
- **No ClashAI code or checkpoints** (license unclear).
- **Scores reported:** pool-v2 (all members, equal weight), external-only, and P1, so the v1 number stays continuous.

## Tracked numbers

| date (UTC) | engine | candidate | pool score [95% CI] | vs v1 | vs R3a | vs scripted-balanced | vs scripted-pressure | games | notes |
|---|---|---|---|---|---|---|---|---:|---|
| 2026-10-14 03:50 | ours (Python C56) | K4S-b64 | **0.864 [0.847, 0.882]** | 0.830 [0.787, 0.870] | 0.633 [0.580, 0.687] | 0.997 [0.990, 1.000] | 0.996 [0.990, 1.000] | 1200 | first run, bot-headline-r1 on 03. Scripted opponents are saturated, so the R3a and v1 columns carry the signal. |
| 2026-10-14 04:35 | **RoyaleSim 0.1.34, 15.535.29 rules (primary from now on)** | K4S-b64 | **0.851 [0.833, 0.869]** | 0.797 [0.750, 0.840] | 0.617 [0.563, 0.673] | 0.993 [0.983, 1.000] | 0.997 [0.990, 1.000] | 1200 | bot-headline-rsim-r1 on 03, same 1200 cases. Paired RoyaleSim − ours: vs v1 −0.033 [−0.093, +0.023], vs R3a −0.017 [−0.077, +0.047]. |
| 2026-10-14 05:00 | RoyaleSim 15.535, **HEADLINE-v2** | K4S-b64 | pool-v2 0.923 [0.913, 0.932]; external-only 0.994 [0.989, 0.998]; P1 0.851 | 0.797 | 0.617 | 0.993 | 0.997 | 2400 | External opponents: rgym-patient 0.983, rgym-push 1.000, rgym-defend 0.997, rgym-first-affordable 0.997, all **saturated**. The trained external policy (rext-rlppo) is pending. Until then **read P1 and the per-opponent v1/R3a numbers**, not pool-v2. |
| 2026-10-14 06:26 | ours (Python C56) | **K4S-st** (new best bot) | **0.892 [0.877, 0.908]** | 0.860 [0.820, 0.900] | 0.720 [0.670, 0.770] | 0.997 | 0.993 | 1200 | R3a's top-8 plays added to the search's candidates (bot/search). Paired pool vs K4S-b64: +0.028 [+0.008, +0.049]. |
| 2026-10-14 06:26 | **RoyaleSim 15.535 (primary)** | **K4S-st** (new best bot) | **0.901 [0.885, 0.916]** | 0.890 [0.853, 0.923] | 0.723 [0.670, 0.773] | 0.997 | 0.993 | 1200 | Paired pool vs K4S-b64: **+0.050 [+0.029, +0.071]**. Same cases. See search-scaling/RESULTS.md. |
| 2026-10-14 08:05 | RoyaleSim 15.535, HEADLINE-v2 | K4S-st | pool-v2 0.947; external-only 0.994 [0.989, 0.998]; P1 0.901 | 0.890 | 0.723 | 0.997 | 0.993 | 2400 | External opponents: rgym-defend 1.000, rgym-first-affordable 1.000, rgym-patient 0.980, rgym-push 0.997 (saturated). |
| 2026-10-14 08:05 | RoyaleSim 15.535, **fresh-bank confirmation** (BASE 594368345275696, not the HEADLINE bank) | K4S-st vs K4S-b64 | R3a+v1 pool: st 0.798 [0.765, 0.828] vs b64 0.718 [0.682, 0.752] | st 0.857 / b64 0.803 | st 0.740 / b64 0.633 | — | — | 1200 | Paired st − b64: vs R3a **+0.107 [+0.047, +0.167]**, vs v1 +0.053 [+0.000, +0.107]. The gain is not a selection artefact of the HEADLINE bank. |

