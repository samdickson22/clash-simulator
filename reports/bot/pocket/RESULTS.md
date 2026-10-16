# Does K4L-R-gs under-attack the pocket with true state? (exploration)

2026-10-16, worker of the BOT LEAD (question from Sam via the coordinator). Exploration tier, not preregistered.
Hosts 127x08 (K4L games) and 127x04 (references). Code: `bot/pocket/diag.py` (logger, search counterfactual,
forced replays), `bot/pocket/analyze.py` (summaries). Status: **in progress** (sections marked TODO pending).

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

**Card levels.** The LIVE LEAD asked for a level 1–4 variant. The Python engine supports card and tower levels
(`PlayerState.card_levels`, `tower_level`). The native search root does not: `C56RolloutPlanner.import_root`
raises on any card level ≠ 11, and the native config carries level-11 stats. So K4L cannot run below level 11
without a new native build; not done here.

## 2. True-state measurement (TODO)

## 3. Counterfactual (TODO)

## 4. Verdict (TODO)

## Reproduce
- Runner (04/08): `/mpac/sdicks02/jobs/clasher/bot-pocket/run.sh MODULE ARGS` (bot-lopp-run.sh env + r1-total pins).
- Smoke: 4 K4L-R-gs games with logging + counterfactual have the same `command_sha256` as plain
  `bot.eval.headline` (4/4; dirs `bot-pocket/smoke-cf`, `bot-pocket/smoke-plain` on 08).
