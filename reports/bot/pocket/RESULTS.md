# Does K4L-R-gs under-attack the pocket with true state? (exploration)

2026-10-16, worker of the BOT LEAD (question from Sam via the coordinator). Exploration tier, not preregistered.
Hosts 127x08 (K4L games) and 127x04 (references). Code:
- `bot/pocket/diag.py`: logger, search counterfactual, forced replays;
- `bot/pocket/analyze.py`: summaries;
- `bot/pocket/live_replay.py`: offline LiveSession → LivePlayer replay of logged live matches;
- `bot/pocket/variant.py`: the `K4P-*` fix arms.

Status: **done** (2026-10-16 ~01:40Z).

**Answer.** With true state, K4L-R-gs pushes the pocket at the same rate as live: 25–31% of post-tower plays in
sim, 27% in the offline live replay, 24–29% live. That is about 10× the human-imitation reference R3a (2–3%).
- **Not a perception artefact.**
- **Not costly bot-side under-attack either.** The search does have a measurable bias against the pocket (the
  balanced coarse scan cuts pocket plays; the leaf values king damage about 8× below princess damage). But:
  - forcing the search's best pocket push instead of its wait/defensive choice is outcome-neutral, Δ 0.000
    [−0.023, +0.023] over 300 forced replays;
  - fixing the coarse-scan cut (`K4P-pw2`) is neutral, +0.003 [−0.008, +0.015];
  - fixing the leaf (`K4P-kc100`) is harmful, −0.060 [−0.083, −0.037].

**Question.** In live ladder play the bot often defends instead of pushing the pocket after taking an enemy princess
tower. Is that a perception artefact, or does K4L-R-gs under-attack the pocket even with true state?

## 1. Code findings: mask, candidates, horizon, leaf

**Placement mask: the pocket opens.**
- Engine rule (`src/clasher/arena.py` `get_deploy_zones`): when an enemy princess tower dies, that half (x 0–8 or
  9–17) opens 4 rows past the river (own-frame rows 17–20) plus the two bridge tiles of that lane.
- The planner's public mask (`src/clasher/rl/public_action_mask.py` `_deploy_zone`) reproduces this from the public
  tower fractions (global features 11/12 ≤ 1e-4). In the true-state games, after a tower falls the mask holds about
  35–70 pocket-legal troop/building actions per decision (smoke games; full numbers in §2).

**Candidates (K4L-R-gs = K4C-r16's list).** `C56RolloutPlanner.candidates`:
1. scripted `balanced` decision, WAIT, `balanced` top-4;
2. R3a's top-16 legal plays (`CandidateSearchPlayer`, r16);
3. 16 random legal samples;
4. timed waits.

Then a balanced coarse rollout over every play, and the top-8 + waits are rescored (balanced + learned)/2.
- The scripted placement rule (`src/clasher/rl/c56_scripted.py` `ranked_actions`) scores a troop with no threat
  by `4.2·exp(−|y − desired|/3) − lane − 0.32·cost`. `desired` is 6.5 for balanced and 13.5 for building-targeters
  (or pressure style). Pocket rows (y 17.5–20.5) are therefore never the scripted top choice. Pocket candidates can
  only come from R3a's proposals or the random samples.
- Inside rollouts our own side is scripted `balanced` too, so no rollout ever continues a pocket push with a second
  pocket play.

**Horizon.** 160 ticks = 8 s (20 ticks/s), after the 27-tick command delay. A medium-speed troop placed at row 17–20
reaches the king tower (row ~29) within it. A slow tank only gets there near the horizon's end.

**Leaf (native `leaf.rs` = Python `defense_v2`): king damage is nearly worthless after one tower.**
- `objective_v1` = 0.55·crowns/3 + 0.25·princess_pressure + 0.10·king_pressure + …;
  `defense_v2` adds 0.08·board + 0.12·danger.
- With one enemy princess tower down, `king_pressure` weight = 0.25, so a full king tower (4,824 HP) is worth
  0.10 × 0.25 = **0.025**, or 5.2e-6 per HP.
- The other princess tower (3,052 HP) is worth 0.25 × 0.5 = 0.125 plus a crown (0.183) when it dies, so 4.1e-5 per
  HP before the crown.
- **Per HP, damage to the king is valued about 8× less than damage to the remaining princess tower, and about 20×
  less including the crown.** Only a king kill (terminal ±2) is valued highly, and 160 ticks rarely reaches it.
- A pocket troop walks to the king tower (its lane tower is gone), so the leaf credits its damage almost nothing.
  The troop's board value (0.08 term) is the same wherever it is placed.

**Card levels (live is 1–4).** Not run.
- The Python engine supports card levels, but crown towers only at levels 10–12 (`clasher.tower_scaling.tower_stat`
  raises otherwise). A level 1–4 battle therefore cannot be built.
- The fair planner root (`R.root`) is level-11 regardless. The s6 live session also ran without levels
  (`session-config.json` has none), so live K4L plans on level-11 stats too.
- A uniform level change scales troop and tower HP and damage by the same per-level multiplier, so troop:tower
  ratios, and with them pocket value, change little. Mixed levels (cards 1–4 against higher towers) could matter
  but need tower stats below level 10.

## 2. True-state measurement: K4L-R-gs pockets, far more than the human-imitation references

**Setup.** HEADLINE cases 0–299 × R3a, v1 in our engine (true state, level 11), logged by `bot.pocket.diag`.
- Games: 600 K4L-R-gs, 0 errors. References: R3a and v1 as the candidate.
- "Took the first tower": the candidate destroyed an enemy princess tower before losing one of its own.
- Post-tower decisions: every searched decision from that tick to the end of the game. For R3a and v1, every play.
- Classes (own frame): pocket = troop/building in rows 17–20 on the dead tower's half (the engine's expanded zone);
  bridge = rows 13–16; back = rows ≤ 12; spells separate.

**After K4L takes the first tower** (162 games vs R3a, 222 vs v1):

| | K4L vs R3a | K4L vs v1 | R3a vs R3a | R3a vs v1 | v1 vs R3a (partial) |
|---|---:|---:|---:|---:|---:|
| games where the candidate took the first tower | 162 / 300 | 222 / 300 | 54 / 150 | 89 / 150 | 26 / 77 |
| plays in the pocket (all plays) | **23.8%** | **31.2%** | 2.1% | 1.8% | 14.9% |
| pocket share of troop plays | 27.6% | 35.9% | 2.4% | 2.0% | 17.6% |
| back (rows ≤ 12) share of plays | 39.9% | 35.5% | 66.4% | 61.3% | 42.9% |
| back plays with an enemy unit in our half | 59.5% | 44.2% | 59.1% | 40.1% | 61.2% |
| bridge share | 21.7% | 18.5% | 21.4% | 22.6% | 26.8% |
| games with ≥ 1 pocket play | 151 / 162 | 211 / 222 | 17 / 54 | 24 / 89 | 23 / 26 |
| median time to first pocket play | 14.2 s | 11.8 s | 39.8 s | 49.0 s | 41.0 s |
| score after taking the first tower | 0.981 | 0.991 | 0.815 | 0.910 | 0.615 |

R3a reference columns: cases 0–149 (127x04 `ref`); 150–299 (`ref-b`) agree (R3a vs R3a pocket 1.3%, vs v1 1.1%).

**Was the pocket legal and offered?** Shares are of K4L's post-tower searched decisions:

| | vs R3a | vs v1 |
|---|---:|---:|
| a pocket placement was legal (affordable troop/building in hand) | 58.2% | 59.4% |
| … and ≥ 1 pocket play was among the candidates | 88.8% | 90.5% |
| … of which from R3a's top-16 | 55.6% | 65.2% |
| … and ≥ 1 pocket play survived into the learned work set (top-8) | **43.5%** | 53.3% |
| K4L chose the pocket when one was in the work set | 34.2% | 34.2% |
| when a pocket play was legal, K4L chose: pocket / wait / back | 14.9% / 39.9% / 25.0% | 18.2% / 43.9% / 20.8% |

- The mask opens the pocket correctly. A pocket play is a candidate at about 90% of the decisions where one is
  legal.
- **The bottleneck is the balanced coarse scan.** It cuts pocket plays from the learned work set at about half of
  those decisions (§1: the scripted balanced opponent and our scripted follow-ups both play away from the pocket).

**Matched to the live definition** (`live/loop/pocket.py`):
- Stretch = from an enemy princess tower's death to the next enemy tower death or the end of the game.
- Pocket = any play, spells included, in rows ≥ 17 within 5 tiles of the dead tower's lane x.

| | stretches | plays | pocket | enemy side | own side |
|---|---:|---:|---:|---:|---:|
| K4L-R-gs, true-state sim, vs R3a | 282 | 4,164 | **25.2%** | 33.1% | 65.3% |
| K4L-R-gs, true-state sim, vs v1 | 426 | 4,392 | **30.9%** | 40.8% | 57.7% |
| R3a, sim, vs R3a / vs v1 | 100 / 52 | 1,938 / 851 | 2.8% / 2.6% | 8.7% / 10.2% | 91.1% / 89.7% |
| live, perception r1 (LIVE LEAD) | 13 | 100 | 29% | – | 63% |
| live, perception r5e3 (LIVE LEAD) | 5 | 29 | 24% | – | – |

**The live pocket rate (24–29%) equals the true-state sim rate (25–31%).** Better perception did not raise it, and
perfect information in sim does not either. **So the live behaviour is not a perception artefact; it is how
K4L-R-gs plays.**

One caveat on the live definition: its ±5-tile lane window excludes spells on the king. In s6-m01 the bot's
Fireball on the enemy king (row 26, col 7) counts as not pocket.

## 3. Counterfactual

**Search counterfactual (`--cf-every 20`).** Sample: post-tower decisions where K4L did not play the pocket and a
pocket play was legal. At each one, on the decision's own root, I re-scored with K4L-R-gs's scorer
((balanced + learned)/2 + timed-wait bonus):
- the chosen action;
- WAIT;
- up to 3 pocket tiles per legal troop card, plus the candidate list's own pocket plays.

This was done at horizons of 160, 320 and 480 ticks. Logging plus counterfactual is output-neutral: 4/4 smoke games
had identical `command_sha256`.

| best pocket vs chosen | vs R3a (n = 2,795) better / worse | vs v1 (n = 3,074) better / worse |
|---|---|---|
| 160 ticks (the search's horizon) | 7.6% / 81.1% | 7.5% / 72.8% |
| 320 ticks | 36.5% / 45.3% | 34.4% / 40.4% |
| 480 ticks | 38.7% / 36.9% | 36.4% / 32.2% |
| 480 ticks, learned-opponent term only | 45.7% / 26.6% | 42.6% / 21.7% |

- The remaining rows are ties, mostly positions already won (both options terminal +2).
- At its own horizon the scorer prefers K4L's choice almost always; that is partly selection: the choice was the
  argmax of these same 160-tick rollouts.
- At 320–480 ticks the best pocket push is about even with the choice. Against the learned opponent it is ahead
  roughly 2:1.
- So the 160-tick, balanced-heavy scorer is biased against the pocket. Whether that costs games is the
  forced-replay question below.

**Forced replays (true outcomes).**
- **Sample.** 300 post-tower decisions, at most one per game, 150 per opponent, drawn from the counterfactual rows
  (`analyze pick`, seed 0). In each, K4L chose a wait (186) or an own-half play (114). Each was still open in the
  scorer's 160-tick view, i.e. not every option a terminal ±2.
- **Method.** Each game is replayed from the start: identical up to that tick (deterministic), then at that
  decision the best pocket push by the 320-tick score is played instead, and K4L-R-gs continues. The forced action
  was applied in 300/300 games.

| forced pocket push − K4L's choice | n | Δ score [95% CI] | better / worse games | Δ crowns for / against | Δ enemy-king damage | Δ tower HP dealt / lost (k) |
|---|---:|---|---|---|---:|---|
| vs R3a | 150 | −0.020 [−0.060, +0.013] | 2 / 5 | +0.013 / +0.007 | +4.5% | +0.22 / +0.18 |
| vs v1 | 150 | +0.020 [−0.013, +0.053] | 5 / 2 | +0.047 / +0.040 | −2.6% | −0.16 / +0.16 |
| **both** | 300 | **0.000 [−0.023, +0.023]** | 7 / 7 | +0.030 / +0.023 | +1.0% | +0.03 / +0.17 |

- At decisions where K4L defended or waited after taking a tower, pushing the pocket instead does not win more.
- It trades a little crown pressure for about as much counter-damage (own towers lose 0.17k HP more on average).
- Defending is not a mistake there; the two options are equal in outcome.

### Live stretches replayed offline (all valid runs)

**Setup.** `bot.pocket.live_replay` runs the LIVE harness unedited on the runs' `perception.jsonl` (exact
`LiveSession.step` records; reconstructed for live1–s5-m02) and `session-config.json`:
`LiveTranslator` → `LiveSession` → `LivePlayer` with the rl5-v10 fast tier (sha256 e188e2ae…).
- The search tier is K4L-R-gs, the deterministic twin of LIVE-K4L-R-gs-rw-fc-w200-t4-p4, so no wall-clock
  cutoffs.
- Two replay-only adjustments, both mirroring the live driver: the HUD elixir is floored at the replayed bot's own
  pending reservations (as `live/loop/drive.py`), and the fractional record tick is floored to an int.
- 24 runs (s2-m02 and s4-m01 skipped as invalid); 72 replays (K4L-R-gs, K4P-pw2, K4P-kc100-pw2), 0 errors.
- 23 post-tower stretches, classed with the live definition.
- In s6-m01 the replay reproduces the live Fireball on the enemy king (tick 1100 vs live 1103, same tile).

| search on live perception | plays | pocket | own side |
|---|---:|---:|---:|
| K4L-R-gs (replay) | 173 | **27.2%** (47) | 60.1% |
| K4P-pw2 | 177 | 33.3% (59) | 55.4% |
| K4P-kc100-pw2 | 198 | 48.5% (96) | 34.3% |
| live as played (LIVE LEAD, r1 + r5e3) | 129 | 28% | – |

**Search counterfactual on the live roots** (198 decisions; best pocket push vs the chosen action):

| horizon | live roots: pocket better / worse | true-state sim (both opponents) |
|---|---|---|
| 160 ticks | 9.1% / 83.8% | 7.5% / 77% |
| 320 ticks | 40.4% / 50.5% | 35% / 43% |
| 480 ticks | 42.9% / 46.5% | 38% / 35% |
| 160 ticks, learned-opponent term only | 46.0% better | 30% better |

- In 4 of the 198 decisions a pocket push's learned rollout kills the king (2.0) while the choice does not.
  Example: s6-m01 tick 880, enemy king at 16%, pocket Minions at (20, 14) scores 1.09 vs 0.21. The balanced
  coarse scan had cut it from the work set; `K4P-pw2` plays it.

**Perfect sight.** A live log has no ground-truth board, so the exact moment cannot be rebuilt with true state.
The replayed live roots are the bot's perception-plus-belief reconstruction. The true-state comparison is
statistical instead:
- the same bot in our engine with full information (§2) has the same pocket rate (25–31% vs 27%);
- it has the same own-side share (58–65% vs 60%);
- its counterfactual profile is the same (table above).

Perception (unit misses, `board_dropped`) does not explain the defending.

## 4. Fix screen (paired vs K4L-R-gs, HEADLINE cases 0–299, ours)

Arms are `bot/pocket/variant.py` `K4P-*`. Every arm runs K4L-R-gs's exact code path until a princess tower is
down.
- Check: `K4P-kc0` (the post-tower Python path with no change) reproduces K4L-R-gs's `command_sha256` on 16/16
  games.
- Baseline: K4L-R-gs's own logged run, 0.820 [0.777, 0.863] vs R3a and 0.940 [0.913, 0.967] vs v1.

| arm | what | vs R3a | vs v1 | pooled | sim pocket share (live definition) |
|---|---|---|---|---|---|
| `K4P-pw2` | pocket tiles added as candidates; best 2 pocket plays forced into the learned work set | +0.000 [−0.020, +0.020] | +0.007 [−0.007, +0.020] | **+0.003 [−0.008, +0.015]** | 32% / 36% (from 25% / 31%) |
| `K4P-kc100` | king credit κ = 1 (both kings, once a princess tower of that side is down) | −0.107 [−0.147, −0.067] | −0.013 [−0.037, +0.010] | **−0.060 [−0.083, −0.037]** | 32% / 36% |
| `K4P-kc100-pw2` | both | −0.153 [−0.235, −0.082] (85 cases; stopped) | – | – | – |

- No fix improves the bot. `pw2` raises pocket play by 5–7 pp at no cost and no gain.
- The king credit hurts. With a pocket share similar to `pw2`'s, its harm comes from distorting the leaf
  elsewhere: it also inflates own-king danger once we lose a tower, and it overrides the princess/crown terms.
- None of these is worth a fresh bank.
- If the LIVE LEAD wants more visible pocket play, `pw2` is the only harmless option. It costs about 2–6 extra
  learned rollouts at post-tower decisions; its speed in the live variant was not measured.

## 5. Verdict

**Bot-side under-attack: no.**
1. **Rate.** The live pocket rate (24–29%) is the true-state rate (25–31% in sim, 27% replaying the live
   perception). Perception does not lower it, and full information does not raise it.
2. **Search.** The scorer is biased against the pocket at its 160-tick horizon:
   - the balanced coarse scan keeps a pocket play in the work set at only 44–53% of decisions where one is a
     candidate;
   - the defense-v2 leaf values king HP about 8× below princess HP once one tower is down;
   - at 320–480 ticks the best pocket push is about level with K4L's choice.
3. **Outcomes.** That bias does not cost games:
   - forced pocket pushes at K4L's wait/defensive decisions: Δ 0.000 [−0.023, +0.023] (300 replays);
   - removing the coarse-scan cut: +0.003 [−0.008, +0.015];
   - adding king credit: −0.060.

   Caveat: after taking the first tower, K4L already wins 98–99% of HEADLINE games vs R3a and v1. The sim has
   little room to show a pocket benefit against these opponents. Stronger live opponents could differ, and only
   live or fresh-bank data can show that.
4. **Defending is often the right call.** 45–60% of K4L's back plays after the tower answer an enemy unit
   already in our half. Waiting (40–44% of decisions with a legal pocket) mostly banks elixir while the tower lead
   holds.

**Live caveats for the LIVE LEAD.**
- `bot/live/translate.py` counts a tower *missing* from a perception record as alive at 100%. A destroyed
  tower that perception stops reporting would close the pocket mask and erase the crown from the leaf.
  - In s6-m01 the records carry `alive: false`, so it was fine there. Worth an assertion in the loop.
- The live pocket metric excludes king-targeted spells. In s6-m01 a Fireball on the king counts as "not pocket".
- Level 1–4 was not simulated: crown towers exist only at levels 10–12 in our engine.

## Reproduce

Job dirs on 127x08 and 127x04, `/mpac/sdicks02/jobs/clasher/bot-pocket/`:

| dir | host | contents |
|---|---|---|
| `main` | 08 | K4L-R-gs, logged + counterfactual |
| `ref` | 04 | R3a/v1 cases 0–149 |
| `ref-b` | 08 | R3a/v1 cases 150–299 |
| `forced`, `force-jobs.jsonl` | 08 | forced replays and their job list |
| `pw2`, `kc100pw2` | 08 | fix screens |
| `kc100-a`, `kc100-b` | 04 | kc100 screen (`kc100-copy` on 08 merges both for the report) |
| `eq-kc0` | 04 | equivalence check |
| `live/out` | 04 | live replays (`live/` holds the run copies) |

Commands:
- `python -m bot.pocket.analyze {stats,live,cf,pick,forced} DIRS`
- `python -m bot.search.report main pw2 kc100-copy --baseline K4L-R-gs`
- `python -m bot.pocket.live_analyze live/out`

The live replays run from an origin/main tree (`/mpac/sdicks02/repos/clasher-bot-pocket`, runner `run-main.sh`).
- Runner (04/08): `/mpac/sdicks02/jobs/clasher/bot-pocket/run.sh MODULE ARGS` (bot-lopp-run.sh env + r1-total pins).
- Smoke: 4 K4L-R-gs games with logging + counterfactual have the same `command_sha256` as plain
  `bot.eval.headline` (4/4; dirs `bot-pocket/smoke-cf`, `bot-pocket/smoke-plain` on 08).
