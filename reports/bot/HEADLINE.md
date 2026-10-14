# HEADLINE: our best bot vs a fixed opponent pool (exploration, tracked daily)

The single tracked number is **pool score**: the candidate's mean score (win 1, draw 0.5, loss 0) against each pool
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

## Tracked numbers

| date (UTC) | engine | candidate | pool score [95% CI] | vs v1 | vs R3a | vs scripted-balanced | vs scripted-pressure | games | notes |
|---|---|---|---|---|---|---|---|---:|---|
| 2026-10-14 03:50 | ours (Python C56) | K4S-b64 | **0.864 [0.847, 0.882]** | 0.830 [0.787, 0.870] | 0.633 [0.580, 0.687] | 0.997 [0.990, 1.000] | 0.996 [0.990, 1.000] | 1200 | first run, bot-headline-r1 on 03. Scripted opponents are saturated, so the R3a and v1 columns carry the signal. |
| — | RoyaleSim 15.535 | K4S-b64 | pending | | | | | | adapter in progress |

