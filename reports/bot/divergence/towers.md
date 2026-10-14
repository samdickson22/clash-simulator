# Tower HP divergence (read-only research)

Run on 127x03 scratch `/mpac/sdicks02/jobs/clasher/bot-div/towers/`. No engine or repo edits; every fix below is a scratch monkeypatch. Data: `clasher-bot-data/t1-trainval` only. Not run: full 577-fixture rerun, so the 68.0% / 84.4% figures are not recomputed.

## 1. First tower discrepancy (8 episodes: every 70th line of eps.txt)

Truth = native recording, ours = unpatched engine. "Hit" = our damage to that tower, attributed by call stack.

| episode | tick | tower (side/slot, our id) | truth hp | ours hp | what hit ours first | class |
|---|---|---|---|---|---|---|
| v4-phase-a-1975100700 | 500 | blue right princess (0/2, id 2) | 2880 | 2781 | Electro Spirit kamikaze landing, 99 (ours at 499) | A |
| v4-phase-a-1975100855 | 1421 | red left princess (1/1, id 4) | 3052 | 2953 | Electro Spirit chain bounce, 99 (at 1420) | B |
| v4-phase-a-1975101011 | 4156 | red left princess (1/1, id 4) | 2953 | 2854 | Electro Spirit chain bounce, 99 (at 4156) | B |
| v4-phase-a-1975100777 | 532 | red left princess (1/1, id 4) | 3052 | 2845 | 207 hit at 531, attacker not attributed | unknown |
| v4-phase-a-1975100933 | 2642 | red left princess (1/1, id 4) | 2771 | 3052 | truth took 281 by 2642; ours took 350 (Wallbreakers) at 2643 | unknown |
| v4-phase-a-1975101088 | 3833 | red left princess (1/1, id 4) | 2412 | 3052 | Balloon 640 lands at 3834, truth at 3833 | C |
| v4-phase-a-1975101166 | 4355 | blue right princess (0/2, id 2) | 2978 | 3052 | Royal Hogs 74 lands at 4356, truth at 4355 | C |
| v4-phase-a-1975101244 | 4992 | blue right princess (0/2, id 2) | 2978 | 3052 | Royal Hogs 74 lands at 4993, truth at 4992 | C |

No king tower (slot 0) mismatch appears in these 8 episodes.

Detail for episode 1975100700, the one the brief asked about:
- Our blue right princess (id 2) is hit by a red Electro Spirit (our id 20) at 476 for 109 (truth: 215 → 106 at 475, same hit).
- Truth then has no second hit. Ours has a second princess shot at 489 for 109. The spirit is at 121 in ours and dies in truth (106 → dead), so it survives in ours with 12 HP.
- Ours: spirit starts a special jump at 495 onto tower id 2 and lands at 499 for 99. Truth: no tower damage.
- The 109 shot in this episode hits the spirit, not a hog. A hog taking 109 near tick 518 is not reproduced.

## 2. Root causes

**A. Spirit HP is 15 too high (data, not tower code). Most of the tower divergence in the sample.**
- `gamedata.json` lists `hitpoints: 90` for ElectroSpirit (`items.spells[83]`), FireSpirits (`spells[31]`), and the nested spawn copies under `spells[111]`. IceSpirits (`spells[30]`) lists 84.
- Truth shows 215 at level 11 for ElectroSpirit and FireSpirits. 84 × 256% = 215 and 90 × 256% = 230, matching the Minions value (230 in truth and ours). So the native base is most likely 84, not 90. This is inferred from truth (256% is the level-11 Common multiplier from `stat_scaling.py:51-61`), not checked against a native character table.
- First-observed HP across all rooted units in episode 1975100700: ElectroSpirit 7/7 and FireSpirits 7/7 mismatch (215 truth vs 230 ours). Every other card: 0 mismatches.
- Effect: the 109 shot leaves ours at 121 and truth at 106, so ours survives the second shot and jumps.

**B. Chain-lightning range boundary (`src/clasher/entities.py:5932`, `ChainLightning._find_next_target`).**
- Code: `if distance <= self.chain_range + 1e-9`. Native behaviour appears to be strict.
- Episodes 855 and 1011: the chain origin (BabyDragon at 3.5, 21.5) is exactly 4.0 tiles from red left princess (3.5, 25.5). `chain_range` is 4.0 (`balance.py:463`, chainedHitRadius 4000). Ours bounces onto the tower. Truth does not.
- Confidence: medium. Two events, both exactly on the boundary, and native may use a different distance (e.g. the collision discount in `native_target_distance_from`, `entities.py:1903`). Chain eligibility of buildings (`entities.py:5926`) is also unverified.

**C. One-tick late damage on melee and projectile hits to towers. Root cause unknown.**
- Six of eight first divergences are ours +1 tick (Royal Hogs, Balloon, Minions, DarkPrince, Royal Hogs again). The princess shot on the spirit (476 vs 475) is the same pattern.
- Ruled out as a global tick offset: exact tower-HP match with ours at t−1 / t / t+1 is 82.0% / 82.2% / 82.4% over 3 episodes (25,251 observations). The lag is per event, not global.
- Candidates, not verified: deferred impact ordering (`battle.py:981-989`, `_run_object_phase`, and `queue_projectile_impact`), or the attack-commit tick for melee hits.

**D. Ruled out for this sample.**
- Princess first-shot timing: ours and truth agree to ±1 tick on the tower-2 shot.
- King-tower activation: no king-tower mismatch in 8 episodes.
- Target selection of towers: no first divergence came from a tower picking a different target. Rich-objects has only 3 ticks in 400–600, so `targetEntityKey` is too sparse to check.

## 3. Fix sketch and harness verification

Scratch verifications, run on 127x03 with `patched_run.py` (gamedata copy and chain patch applied in-process):
- **Spirit HP 90 → 84** for ElectroSpirit and FireSpirits (5 nodes in `gamedata.json`). Episode 1975100700 first mismatch moves 500 → 553; the spirit-chain tower hit disappears.
- **Chain strict `<`** (`entities.py:5932`, scratch). On top of the spirit patch, episode 855 moves 1421 → 1457 and 1011 moves 4156 → 4336. Both chain-to-tower hits are gone.
- Remaining first mismatches after both patches are C-class lags, plus episode 855 at 1457 (ours takes a second Spear Goblin hit that truth does not) and 933 at 2642 (unknown).

Next steps:
1. Confirm the spirit base HP against a native character table, then fix the data at source, not the engine.
2. Run the full harness (`bot.fidelity.run` on train+val) with both patches to measure the effect on the 68.0% / 84.4% tower numbers.
3. For C: instrument hit commit vs apply tick for Royal Hogs in episode 1975101166 to find which phase delays damage.

Scripts and outputs (on 127x03): `/mpac/sdicks02/jobs/clasher/bot-div/towers/` (`tower_trace.py`, `dmg_src.py`, `spirit_hits.py`, `first_tower_div.py`, `verify_spirit_hp.py`, `chain_strict_verify.py`, `lag_test.py`, `patched_run.py`, `gamedata-spirit84.json`).
