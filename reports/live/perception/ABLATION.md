# What part of perception noise costs win rate? (exploration, 2026-10-15)

**Setup.**
- Fast tier: it5s2, one forward pass per decision. Engine: ours. Opponents: v1 and R3a, 300 HEADLINE cases each,
  same base. 4,200 games, 0 errors.
- Run on 127x03 (`/mpac/sdicks02/jobs/clasher/live-perc-ablate-ours`).
- **Baseline:** `PERC-emp`, the empirical val-measured noise of the deployed ft-r2 stack (`bot/live/empirical-val.json`).
- **Arms:** each `PERC-emp-x<part>` removes one noise component. Each arm is paired per case with the existing
  `PERC-emp` and perfect-sight `LIVE-fast-it5s2` rows (`live-perc-winrate-ours/fast`).

**Reference points.**
- Perfect sight: 0.660 vs R3a, 0.883 vs v1.
- PERC-emp vs perfect sight: R3a −0.137 [−0.197, −0.077], v1 −0.113 [−0.163, −0.063].

| arm (noise removed) | vs PERC-emp: R3a | vs PERC-emp: v1 | vs perfect: R3a | vs perfect: v1 |
|---|---|---|---|---|
| **xunits** (all unit noise) | **+0.073 [+0.013, +0.137]** | **+0.060 [+0.007, +0.117]** | −0.063 | −0.053 |
| xrecall (unit misses only) | +0.040 [−0.020, +0.100] | +0.047 [−0.013, +0.107] | −0.097 | −0.067 |
| xfp (phantom units only) | +0.020 [−0.040, +0.080] | **+0.077 [+0.023, +0.130]** | −0.117 | −0.037 |
| xev (all opponent events perfect and instant) | +0.020 [−0.037, +0.080] | +0.027 [−0.027, +0.080] | −0.117 | −0.087 |
| xspell (spell events only) | −0.010 [−0.063, +0.043] | −0.003 [−0.053, +0.043] | −0.147 | −0.117 |
| xhud (hand, elixir, towers) | +0.010 [−0.057, +0.070] | +0.020 [−0.033, +0.077] | −0.127 | −0.093 |
| **xunits-xhud-xev** (floor check) | +0.132 [+0.070, +0.195] | +0.113 [+0.057, +0.170] | **−0.005 [−0.062, +0.050]** | **+0.000 [−0.047, +0.047]** |

**Reading.**
- **The method is sound.** With unit, HUD and event noise all removed, the arm is level with perfect sight.
- **Unit noise is the main lever.** It accounts for about half of the gap (+0.06 to +0.07). It splits into misses
  (+0.04 to +0.05) and phantom units (+0.02 to +0.08). Both matter.
- **Spell events matter little for win rate.** Making spells perfect changes nothing measurable. Making all events
  perfect gives +0.02 to +0.03, within noise. This contradicts the replay-agreement analysis, which ranked missed
  events first. Win rate is the metric we judge by, so units come first.
- **The HUD is small.** It's +0.01 to +0.02.
- The single components don't add up to the whole: units + events + HUD ≈ +0.10, against a total of ≈ +0.13. The
  remainder is interaction.

**Consequence for perception round 2.** Prioritise unit recall (swarms, merged peaks) **and** unit false positives.
Spell-event work comes second. Royal Ghost remains a live-only fix that this metric can't see.

## Follow-up 1: unit threshold (round-1 model, 2026-10-15 13:53Z)

**Setup.** 1,800 games on 03, 0 errors, code from main 5cb79878 (the hand fix e1b468ec is NOT included). The
unit-detection threshold was raised from the deployed 0.4. Only the unit stats were refitted
(`empirical-val-r1u50.json`, `-r1u55.json`):
- at 0.5: recall .760, phantoms .053/.057 per frame;
- at 0.55: recall .730, phantoms .027/.029.

| arm | vs fresh PERC-emp: R3a | vs fresh PERC-emp: v1 | vs perfect: R3a | vs perfect: v1 |
|---|---|---|---|---|
| fresh PERC-emp (same code) | — | — | −0.137 [−0.200, −0.073] | −0.067 [−0.120, −0.013] |
| **unit threshold 0.5** | +0.020 [−0.040, +0.080] | +0.020 [−0.033, +0.073] | −0.117 | −0.047 |
| unit threshold 0.55 | +0.017 [−0.050, +0.087] | −0.037 [−0.090, +0.017] | −0.120 | −0.103 |

**Reading.**
- 0.5 is consistent with the phantom-cost proxy, which predicted about +0.02, but it isn't significant at n = 300 per
  opponent. 0.55 is null to negative.
- **Decision (exploration):** move the deployed unit threshold to **0.5**. The evidence leans that way and the
  downside is small. Round 2 picks its own threshold with the same sweep.
- The fresh PERC-emp re-measured on current code matches the old one: R3a +0.000, v1 +0.047, both n.s.
