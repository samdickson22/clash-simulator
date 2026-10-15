# Wall-deadline cost of the best bot (exploration, 2026-10-15)

**Question.** Live play needs a per-decision deadline. How much strength does K4C-r16 lose under one?

**Setup.**
- RoyaleSim 15.535, the HEADLINE-v1 bank, cases 0–299 against v1 and against R3a. 3,000 games, 0 errors.
- Run on 127x03 from 00:51Z to 03:37Z: 12 groups of 5 pinned physical cores, SMT siblings left idle.
- Honest lateness is included: decision time delays the command.
- Each arm is paired against the unbounded K4C-r16 on the same cases (`bot-headline-r16-rsim15535`, via
  `bot/eval/pair_by_name.py`).
- Code: `bot/live/headline_wall.py` and `bot/live/player.py`. Out dir: `03:/mpac/sdicks02/jobs/clasher/live-wall-rsim15535`.

**Reference.** The unbounded K4C-r16 scores 0.900 vs v1 and 0.797 vs R3a.

| arm (4 threads) | cutoff default | B−A vs R3a [95% CI] | B−A vs v1 [95% CI] |
|---|---|---|---|
| K4CW-r16-w200 | R3a | −0.087 [−0.143, −0.030] | −0.033 [−0.073, +0.007] |
| K4CW-r16-w150 | R3a | −0.143 [−0.203, −0.083] | −0.050 [−0.100, +0.000] |
| K4CW-r16-w120 (proxy for a ~0.6× Mac) | R3a | −0.233 [−0.293, −0.173] | −0.170 [−0.227, −0.117] |
| **LIVE-K4CW-r16-w150** | it5s2 | −0.087 [−0.143, −0.030] | −0.013 [−0.060, +0.033] |
| **LIVE-K4CW-r16-w200** | it5s2 | **−0.070 [−0.127, −0.013]** | **−0.020 [−0.067, +0.027]** |

**Reading.**
- A deadline costs real strength, about 7–9 pp against R3a even at 150–200 ms.
- it5s2 is a better cutoff default than R3a. Against v1, the LIVE tiers are statistically even with the unbounded
  bot.
- Below about 150 ms, strength collapses. The Mac's per-core speed, compared with the fleet's, picks the tier:
  - LIVE-w200 if the Mac is at or above about 1× fleet speed;
  - LIVE-w150 otherwise;
  - it5s2 alone if the Mac is far slower.
- **Deployed tier pending the Mac timing: `LIVE-K4CW-r16-w200-t4`.**
