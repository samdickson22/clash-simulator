# Engine calibration, batch 1 (exploration)

## Result (2026-10-14)

All five batch-1 rules are calibrated from native recordings and accepted. The per-change gates were decided on train only.

| split | no-tower ≤¼ tile | no-tower HP exact | paired ≤¼ (fixtures better/worse) | winner agrees |
|---|---|---|---|---|
| train (513) | 50.72 → **62.26** | 64.97 → **71.98** | +11.22 pp [+10.08, +12.39] (407/46) | 381 → 377 |
| **validation (64, untouched)** | 57.64 → **66.37** | 66.79 → **72.49** | +9.30 pp [+6.37, +12.64] (50/6) | 45 → 48 |
| all 577 | 51.39 → **62.66** | 65.15 → **72.03** | +11.01 pp [+9.99, +12.09] (457/52) | 426 → 425 |

- The baseline is `baseL`, i.e. r2 rerun with the seeded RNG. The final engine is `c5d-minerend`. RoyaleSim 15.535 on the same corpus scores 78.8 / 81.8.
- **Live view** (scored only up to our battle's end), train: 55.31 → 67.79. No card with ≥8k unit-ticks loses >1 pp.
- **Standard view**, cumulative (base → final), train: Giant, Balloon and Xbow lose >1 pp, each within −1 pp under LOO.
- **Validation:** the per-card checks are small-sample. BombTower −8.4 pp comes from 64 fixtures, and the live view has no card below −1 pp.

See §6 for Python↔Rust parity and RUNTIME-R2-PLAN.md for the runtime plan.

Python reference engine (`src/clasher`), each change gated by the 577-fixture fidelity harness (FIDELITY.md recipe,
engine `clasher`, `--issue-offset -1`). **Decisions use split=train (513) only**; validation (64) is reported once at the end.
Work dir 127x05 `/mpac/sdicks02/jobs/clasher/bot-calib-r1/`; gate tool `bot/fidelity/compare_runs.py BASE NEW --split train`.

**Gate:** no-tower ≤¼ tile and no-tower HP exact must not decrease, and no card with ≥8k unit-ticks (train) may lose >1 pp
on ≤¼ tile. Because the harness scores our *frozen* final state after our battle ends, one earlier sudden-death crown can
add hundreds of alive-mismatch ticks to a small card. So every failing card also gets a **leave-one-fixture-out (LOO)**
delta. And since change 2, every run also carries a **live view** (`run.py` `res["live"]`): the same scoring, but only up
to our battle's end, so without frozen ticks. `compare_runs --view live` prints it.
- **Final rule (fixed at change 4 and re-checked for 1–3, which all pass it):** ACCEPT if
  - overall no-tower ≤¼ and HP exact do not decrease, in both the standard and the live view; and
  - every card (≥8k unit-ticks) that loses >1 pp in either view is within −1 pp under LOO in **both** views.
  - Changes 1–3 also passed the stricter "live view passes the full gate".
- The standard numbers are always the headline.

## 0. Harness determinism (prerequisite)

- **Diagnosis:** rerunning the r2 baseline gave the same train headline (50.7%), but 95/577 fixtures differed run to run.
  `BattleState.rng` is `random.Random()` with an OS seed (`battle.py:138`). It drives the Arrows volley jitter and radial
  spell spreads (`spells.py:382`, `:424`).
- **Change:** `bot/fidelity/engines.py` `OursEngine.reset` calls `b.rng.seed(0)`. This touches the harness only, not the engine.
- **Check:** two seeded full runs differ in 0/577 fixtures. Reference baseline is `base-s0`: train no-tower ≤¼ 50.72,
  HP exact 64.97. Noise between unseeded runs: ±0.1 pp overall, ≤0.3 pp per card.

## 1. Spirit HP data — ACCEPTED (LOO gate; strict gate fails on Wizard alone, a one-fixture cascade)

- **Diagnosis and derivation:** `tools/maxhp_survey.py train` reads native `max_hp` of each object's first frame, over
  the 513 train episodes (`maxhp-train.tsv`).
  - Native max_hp at level 11: IceSpirit 215 (822 bodies), FireSpirits 215 (792), ElectroSpirit 215 (952), and
    FirespiritHut's spawned FireSpirits 215 (1,137).
  - Our loader scales the level-1 base by the Common table: `stat_scaling.scale_stat`, 256% at level 11, truncating.
    So 84 → 215 and 90 → 230.
  - `gamedata.json` had 84 for IceSpirits (fixed earlier, see `meta.canonicalization.note`), but 90 for FireSpirits and
    ElectroSpirit. That gave 230 against native 215 on every tick, which is why HP exact was 0.0% for both.
  - HealSpirit (base 90) is not in the corpus, so it is unverifiable and left unchanged. IceSpirits_EV1 is an evolution, which the corpus doesn't have.
- **Change:** `gamedata.json` hitpoints 90 → 84 at all 5 paths: `spells[31]` FireSpirits, `spells[83]` ElectroSpirit, and 3
  nested FireSpirits spawn copies under `spells[111]` (FirespiritHut). The canonicalization note is extended. This is
  data only: no engine code changed, and the fingerprint is kept.
- **Test:** `tests/test_calibration_batch1.py::test_spirit_hitpoints_match_native_level11[Ice/Fire/Electro]`
  and `::test_firespirit_hut_spawns_native_hp_spirits` (max_hitpoints == 215). 3 of the 4 fail on the old data, all 4 pass now.
- **Harness, train, `base-s0` → `c1-spirithp`:**
  - no-tower ≤¼ 50.72 → **51.04** (+0.32). Paired +0.28 pp [+0.06, +0.52], better in 121 fixtures, worse in 34.
  - no-tower HP exact 64.97 → **66.91** (+1.94). Paired +1.91 [+1.58, +2.27], better 307, worse 10.
  - Tower HP exact 67.77 → 69.09.
  - Affected cards (≤¼ / HP exact): ElectroSpirit 71.3→72.7 / 0.0→79.5; FireSpirits 68.7→70.3 / 0.0→77.9;
    FirespiritHut 22.3→22.9 / 29.8→36.0; IceSpirit 70.8→70.2 / 76.1→75.7 (unchanged data; cascade).
  - **Worst regression: Wizard −1.73 pp** (20k unit-ticks). It is a cascade from 2 of 81 fixtures:
    - In `…0976`, our sudden-death crown came at 4438 instead of 5221. The frozen state then added +490 Wizard
      alive-mismatch ticks.
    - `…1120` lost 58 ticks.
    - LOO without 0976: −0.32 pp.
  - No other card with ≥8k unit-ticks is below −1 pp.
- **Live view, train (`baseL` → `c1L`):** ≤¼ 55.31 → 55.42, HP exact 70.53 → 72.36. No card below −1 pp; the worst is
  BabyDragon −0.64. Strict gate ACCEPT.
- **Decision:** accepted. It is a native-measured data correction with an overall HP-exact gain of +1.9 pp. The only
  standard-gate failure is one fixture's cascade, and it is absent from the live view.

## 2. Lane-2 spawn-ring mirror for 5-, 6- and 15-slot formations — ACCEPTED (LOO and live; strict standard gate fails on 7 small cards, all game-end cascades)

- **Diagnosis:** `tools/formation_survey.py train`. For every train play (19,199 events; 669 refused on an empty board), take
  the native first-frame positions of the units the play created. Compare them with our deploy of the same card at the
  same tap tile and side on an empty battle, once direct and once with `formation_offset` x-mirrored.
  - **Position** (mean nearest-unit distance, native units; median direct → mirror):
    - Bats path 2: 439 → **0** (339 events); path 1: 0 → 439 (388).
    - SkeletonArmy path 2: 416–437 → **24–37** (238); path 1: 36–50 → 416–440 (256).
    - 6-slot rings (MinionHorde, GoblinGang) are mirror-symmetric, so position can't tell them apart.
  - **Spawn order** (Kendall concordance of native object-id order with our spawn-index order, direct → mirror):
    - path 2: Bats 0.00 → **1.00**, MinionHorde 0.33 → **1.00**, GoblinGang 0.60 → **0.99**, SkeletonArmy 0.26 → **0.98**.
    - path 1, the same cards: direct 0.97–1.00.
    - The existing rules hold, with direct at 0.97–1.00: path 1 mirrors 2–3 slots (Minions, Skeletons, Rascals); path 2
      mirrors 4 slots (Goblins, RoyalHogs).
    - This holds for both sides.
  - swarms.md's Bats worsening was the harness cascade, not geometry: Bats geometry becomes exact.
  - The 5-slot base angle (180) needs no change: mirrored Bats match to 0 units.
- **Change:** `src/clasher/formations.py:53-65`. `lane_flip_x` adds path 2 with `slot_count in {4, 5, 6, 15}` (previously
  `== 4`). Comment at `balance.py:96-99` updated. Only counts seen in the corpus are changed; 7–14 and wider formations
  keep world order (unverified).
- **Test:** `tests/test_calibration_batch1.py::test_formation_matches_native_first_frame_and_order`. It checks 5 native
  first frames in native spawn order, ±2 units:
  - Bats path 2 for both sides;
  - Bats path 1 as a guard;
  - MinionHorde path 2;
  - GoblinGang path 2.

  Without the change 4 of the 5 fail (the path-1 guard passes either way); with it, all pass.
- **Harness, train, `c1-spirithp` → `c2-lane2mirror` (standard):**
  - no-tower ≤¼ 51.04 → **56.91** (+5.87). Paired +5.37 pp [+4.59, +6.14], better in 273 fixtures, worse in 14.
  - HP exact 66.91 → **67.22** (+0.31). Paired +0.76 [+0.30, +1.17].
  - Cards (≤¼): SkeletonArmy 30.1 → **53.5**, Bats 35.3 → **53.5**, GoblinGang 38.2 → **54.5**, MinionHorde 42.4 → **57.3**.
  - Bats HP exact 75.2 → 72.2. That is cascade: in the live view it goes 83.3 → 85.7.
  - **Strict per-card failures:** Balloon −3.2, Cannon −1.6, IceGolem, Miner, FireSpirits, Xbow, ArcherQueen.
    - Every one comes from fixtures where our engine now ends the battle at a different time. Examples:
      - `…1080`: we take a tower at 4111, native never does, and alive-mismatch goes 2.5k → 26k.
      - `…1141`: we lead at regulation (3601) while native goes to overtime until 5353.
      - `…0877` and `…1193`: overtime towers at 4622 and 4952.
    - LOO: each card is ≥ −1.00 pp (Cannon −1.00, Xbow −0.36; the others are positive).
  - **Live view (`c1L` → `c2L`):**
    - ≤¼ 55.42 → **62.82** (+7.40). Paired +5.96 [+5.22, +6.73], better in 280 fixtures, worse in 6.
    - HP exact 72.36 → 73.76.
    - No card below −1 pp; the worst is Wizard −0.39.
    - Cards: SkeletonArmy 32.1 → 58.0, Bats 39.6 → 64.5, GoblinGang 42.1 → 60.8, MinionHorde 44.4 → 60.6, Cannon 89.8 → 89.7.
- **Decision:** accepted.

## 3. Goblinstein formation — ACCEPTED (live passes strict; standard fails on ElectroSpirit alone, LOO +0.86)

- **Diagnosis:** the formation survey (train, 144 Goblinstein spawns; offsets from the tap in native units, ordered by
  native id).
  - Monster at (0, 0) and doctor at (+1000 on path 1 / −1000 on path 2, 3500 behind) in 130 spawns. Side 0, path 1: 49;
    side 0, path 2: 11; side 1, path 1: 12; side 1, path 2: 58.
  - The rest are edge clips (doctor y clipped to 31.75 or 0.25) or snapped taps.
  - Ours placed the monster on the 2-slot ring 3.5 tiles *forward*, often clamped (+1000 near the river), and the
    doctor with no lateral term.
  - Path vs tap x can't be told apart in the corpus: every path-1 tap has x < 9. The lane form is used.
  - No gamedata field explains the 1-tile lateral offset. Goblinstein is the only 1+1 mixed card in gamedata.
- **Change:** `src/clasher/formations.py:51-63`, a special case for `count == 1 and secondary_count == 1`. The primary
  returns (0, 0); the secondary returns (±1 tile toward centre by path, one summon radius behind). The existing
  battle.py clamp still clips the doctor at the arena edge (31.75).
- **The "dropped tap" (ep …0715, exec 5898) is a cascade, not a rule.**
  - Our battle ends at regulation (3601) with crowns 1–0. Native was 1–1 and went to overtime, so the play is never
    reached.
  - The fixture's one real refusal (Musketeer at 3287) is a tap on (3.5, 6.5). That is our still-standing blue left
    princess tower; native had lost it.
  - On an empty board the 5898 tap deploys exactly at native (4499, 28499) and (5499, 31750).
- **Test:** `tests/test_calibration_batch1.py::test_goblinstein_formation_matches_native`, 4 native taps (incl. edge clip).
- **Harness, train, `c2L` → `c3L-goblinstein`:**
  - Standard: no-tower ≤¼ 56.91 → **58.45** (+1.53), paired +1.88 [+1.31, +2.46], better in 96 fixtures, worse in 7.
    HP exact 67.22 → 67.81.
  - **Goblinstein ≤¼ 10.4 → 67.1, HP exact 50.2 → 71.9.** GoblinGang +1.3.
  - Strict failure: ElectroSpirit −1.27. LOO: +0.86 without `…0864`.
  - Live: no-tower ≤¼ 62.82 → 64.41, HP 73.76 → 74.33, no card below −1 pp (worst GoblinHut −0.31). Goblinstein 10.8 → 68.7.
  - Winner agrees 379 → 374 (train).
- **Decision:** accepted.
- **Remaining Goblinstein gap** (67 vs RoyaleSim 89): not diagnosed. The candidates are the tether or doctor movement.

## 4. Hut first-spawn timing — 4a FirespiritHut ACCEPTED, 4b GoblinHut ACCEPTED

- **Diagnosis:** `tools/hut_survey.py train`, all train plays (345 GoblinHut, 393 FirespiritHut). It finds the hut body
  and its children (same root and side, first frame within 2.5 tiles of the hut). spawner-huts.md's 3-episode numbers
  were partly wake-gated cases.
  - **FirespiritHut, native:**
    - first spirit at exec + **38** (178), 39 (121), 40 (21): 1900 ms;
    - period 100 ticks (5000 ms);
    - first spirit 1.5 tiles straight ahead (0, 1500) in 255/383.
  - **FirespiritHut, ours before:** exec + 79–80, 41 ticks late (deploy 1000 + `spawnStartTime` 3050).
  - **GoblinHut, native:**
    - first goblin at exec + **20** (96), 21 (45), 22 (10) when an enemy is near. These are 168 "on time" plays: the
      nearest enemy unit is at median 4.4 tiles at exec+20 and at most 7.6.
    - The other 177 are later, with the nearest enemy at median 11.4. So there is a wake gate.
    - In the late ones, taking wake = the first frame with an enemy unit within 7.5 tiles centre-to-centre, the first
      goblin appears **on the wake tick** in 84 of them (≤3 ticks in 101; only 28 have no enemy within 7.5 before the
      goblin).
    - So the clock runs while idle and a due wave fires on wake.
    - The range fits 6 + hut radius (1.0) + target radius.
    - Period 43–44 ticks (2200 ms), as ours already had.
  - **GoblinHut, ours before:**
    - +38 when awake (deploy 1000 + first delay 1000), 18 ticks late;
    - the wake gate was 6 + target radius only (no hut radius);
    - each sleep reset the clock, so a wake paid 1000 ms again.
- **Changes:**
  - **4a:** `src/clasher/balance.py:881-884` `_furnace_entry` `spawnStartTime` 3050 → 1000.
  - **4b1:** `src/clasher/cards/goblin_hut.py:13-17` `first_spawn_delay_ms` 1000 → 100. At `:38-44`, while asleep the
    clock advances, capped at the next threshold (no banking), and is no longer reset.
  - **4b2:** `goblin_hut.py:35` wake range 6.0 + **hut radius** + target radius.
- **Tests** (`tests/test_calibration_batch1.py`):
  - `test_firespirit_hut_first_spirit_at_native_1900ms` (39 ticks from the deploy call; 81 before);
  - `test_goblin_hut_first_spear_goblin_as_deploy_ends_when_enemy_in_range` (20–22);
  - `test_goblin_hut_fires_on_wake_without_new_delay` (≤1 tick after the walking enemy enters range).
  - HEAD fails both GoblinHut tests; 4b1 alone fails the wake test.
- **Timing check on the replays** (ours vs native first-child tick for the same play, train):

  | | before | after |
  |---|---|---|
  | GoblinHut awake, within ±2 ticks | 0/154 | **150/157** |
  | GoblinHut late, within ±2 ticks | 13/137 | **93/143** |
  | FirespiritHut, within ±2 ticks | 0/331 | **354/357** |

- **Harness 4a, train, `c3L-goblinstein` → `c4a-furnace`:**
  - Standard: no-tower ≤¼ 58.45 → **59.83** (+1.39), paired +1.13 [+0.75, +1.54], better in 115 fixtures, worse in 30.
    HP exact 67.81 → **69.66** (+1.85).
  - **FirespiritHut ≤¼ 23.7 → 43.4, HP exact 35.7 → 63.7.**
  - Strict failure: FireSpirits −1.18. LOO: +0.05 without `…1191`.
  - Live: ≤¼ 64.41 → 65.58, HP 74.33 → 75.93, no card below −1 pp (worst ElectroSpirit −0.41). FireSpirits +0.5.
  - Accepted.
- **Harness 4b (4b1 + 4b2), train, `c4a-furnace` → `c4b2-hutradius`:**
  - Standard: no-tower ≤¼ 59.83 → **60.01** (+0.18), paired +0.24 [−0.01, +0.50], better in 69 fixtures, worse in 47.
    HP exact 69.66 → **70.33** (+0.68), paired +0.70 [+0.40, +1.02].
  - **GoblinHut ≤¼ 30.4 → 34.9, HP exact 37.7 → 52.2.**
  - Strict failures:
    - standard: Giant −1.33 (LOO −0.60) and ArcherQueen (LOO −0.40);
    - live: Balloon −1.45 (LOO −0.89) and MinionHorde −1.09 (LOO −0.50).
    - Different cards fail in each view, and none is robust under LOO.
  - Live: ≤¼ 65.58 → 65.77, HP 75.93 → 76.70; GoblinHut 31.8 → 36.4 / 39.6 → 54.8.
  - Accepted under the final rule. It would not pass the stricter "live passes the full gate".
  - Step by step:
    - 4b1 alone: +0.15 ≤¼, GoblinHut 30.4 → 33.1 / 37.7 → 45.8.
    - 4b2 on top: +0.03 ≤¼, GoblinHut → 34.9 / 52.2.
    - Prince −1.5 pp is robust under LOO for 4b2 vs 4b1, but within −1 pp for 4b as a whole (vs c4a).
- **Remaining hut gap** (GoblinHut 35 vs RoyaleSim 67): 32 late GoblinHut wakes are now *earlier* than native. The
  7.5-tile estimate is loose, and the wake target set (air units, buildings) is unverified. Spear Goblin offsets (ours
  ±400/1100 vs native spread) and FirespiritHut walking are not addressed.

## 5. Miner — 5a ACCEPTED, 5b alone REJECTED, 5b+5c ACCEPTED, 5d ACCEPTED

- **5a, the second tower never engaging, is a 1-unit deploy nudge.**
  - In ep …0702 our Miner surfaced at (5.499, 25.5). The far princess tower was then at 9.001 against a 9.0 reach.
  - `tools/miner_land.py`: native Miners land **exactly on the tap in 572/601** train plays.
  - Ours got LogicSummoner's symmetric deploy snap: (−1,0) 214, (−1,−1) 148, (0,−1) 96, (0,0) 89.
  - MightyMiner is nudged natively, and ours already matched it.
  - **Change:** `src/clasher/battle.py:1398-1406` `_apply_symmetric_deploy_snap` skips `can_deploy_on_enemy_side` troops. The
    Miner is the only one; GoblinDrill is a building, already exempt.
  - **Test:** `test_miner_surfaces_on_the_exact_tap` (3 taps). At HEAD, 2 of the 3 fail.
  - **Harness (`c4b2` → `c5a-minersnap`):** standard ≤¼ 60.01 → **60.42** (+0.41), paired +0.41 [+0.18, +0.64]. HP exact
    70.33 → 70.55. Miner 47.4 → 51.9 / 34.0 → 37.2.
  - **Strict gate passes in both views.** Worst card: RoyalDelivery −0.68.
- **5b, the underground route (miner.md A).** Native tunnels follow a grid route; ours was a straight line.
  - Prototyped offline against native per-tick tunnel positions, on 572 exact-tap train Miners (`tools/miner_route.py`):

    | variant | position error median / p90 (native units) | landing tick ±1 |
    |---|---|---|
    | straight (ours) | 1428 / 2668 | 57/572 |
    | lane-cost ground A* | 1844 / 5051 | 53/572 |
    | uniform-cost A* | 1982 / 4644 | 411/572 |
    | reversed (goal→start) uniform A* | 416 / 6867 | 82/572 |
    | **per-leg reversed uniform A* via the destination lane's bridge** | **54 / 364** | **532/572** |

  - Model: uniform cost, water blocked, only the destination lane's bridge.
    - Each leg is searched from its goal (straight-first, diagonal-last).
    - Across the river the route is start → bridge entry, straight over the bridge, exit → tap.
    - The mover heads for cell centres at 650/tick in 250-unit substeps and drops a node when its projected remainder is
      < 1001, as ordinary ground routing does.
    - Native's first frame already shows one more move than ours, so the transport leads by one tick.
  - **Change:**
    - `src/clasher/pathfinding.py` (end of file): `native_spawn_path_route` and `native_spawn_path_trajectory`.
    - `src/clasher/cards/miner.py` `on_attach` (precomputed trajectory; travel = len−2 ticks) and `on_deploy_tick`
      (index-based).
    - MightyMiner's ability tunnel keeps the straight path (unverified).
  - **Test:** `test_miner_tunnel_follows_native_spawn_route` (ep …0746 native points ±400) and
    `test_miner_lands_on_native_tick_through_deploy` (fails at HEAD).
  - **Harness (`c5a` → `c5b-minerroute`):** Miner ≤¼ 51.9 → 64.4.
    - Overall standard ≤¼ **−0.09** and HP −0.12; live ≤¼ −0.15, paired HP −0.21 [−0.35, −0.07].
    - **Rejected alone.** The cause was 5c.
- **5c, the first-hit lag (miner.md C): our Miner was untargetable during its 1 s emergence.**
  - Native ep …0702: both towers lock on at 2528, while the Miner is still emerging (surfaced at ~2531). The first arrow
    lands at 2532.
  - Ours kept `_underground_deployment` (untargetable) until emergence ended, so the first hit came at 2551.
  - The old straight path landed 2 ticks early, which partly masked this lag. That's why 5b alone lost.
  - **Change:** `miner.py` `on_deploy_tick` arrival branch. A routed transport stops being underground on arrival, and the
    emergence is an ordinary deploy.
  - **Result:** in ep …0702 the first two Miners' 11 hit ticks each now equal native exactly, including the death tick.
  - **Test:** `test_miner_is_hit_during_emergence_like_native` (55–57 ticks; +75 before).
  - **Harness, 5b+5c (`c5a` → `c5c-minerhit`):**
    - standard ≤¼ 60.42 → **62.15** (+1.73), paired +1.80 [+1.29, +2.32], better in 108 fixtures, worse in 24;
    - HP exact 70.55 → **71.92** (+1.37); tower HP exact 71.79 → 73.47;
    - **Miner 51.9 → 72.4 / 37.2 → 69.6**; live 61.9 → 85.0 / 44.0 → 81.9;
    - no card below −1 pp in either view (worst RoyalHogs −0.48). **Strict ACCEPT.**
- **5d, the tunnel end.** Native snaps from ~836 units out, i.e. on the same "projected remainder < 1001" rule applied to the
  last node, not within speed (650) of it.
  - With the old end rule, side-1 Miners landed +0.4 ticks late on average, side 0 −0.5.
  - With the new rule, ours lands on native's sampled landing tick in 283/296 (side 0) and 225/234 (side 1). The distribution
    is 36:197, 37:129, 35:43 vs native 36:206, 37:133, 35:45.
  - **Change:** `pathfinding.py` `native_spawn_path_trajectory`, last-node rule.
  - **Harness (`c5c` → `c5d-minerend`):** ≤¼ 62.15 → **62.26**, paired +0.12 [+0.02, +0.22]; HP 71.92 → 71.98; Miner
    72.4 → 74.0 / 69.6 → 72.3.
  - Standard per-card failure: Musketeer −1.34. LOO −0.01 without `…0715`. Live is strict ACCEPT.
- **"Tower damage one tick late" (towers.md C).**
  - The episodes cited there (1088 Balloon, 1244 Royal Hogs) now match native tower HP tick for tick. 1166 is exact apart
    from one missing hog hit. Those lags were cascades of the earlier divergences.
  - Over 120 train episodes (`tools/tower_lag.py`), the first tower mismatch is "ours one frame late" in 71 cases.
    - 41 of these are the Miner's 39-damage crown-tower hit.
    - One traced case (ep …0746) is an Ice Spirit freeze at 4299 that clears our Miner's tower target. We re-acquire at
      4310 and hit at 4320; native hits at 4316.
  - Freeze/retarget timing is not established. Left open.
- **Not done:** a few Miner routes still miss (2 of 572 > 2 tiles), and the 7–14-slot formations are unverified.

## Per card, all 577 fixtures (cards with ≥8k unit-ticks; before = `baseL`, after = `c5d-minerend`)

| card | unit-ticks (final) | ≤¼ before | **≤¼ after** | Δ | HP exact before | **HP after** | Δ | RS 15.535 ≤¼ | RS 15.535 HP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Tower | 3381737 | 98.1 | **98.3** | +0.2 | 67.8 | **73.8** | +6.0 | 99.0 | 84.4 |
| SkeletonArmy | 637259 | 31.3 | **58.1** | +26.8 | 76.5 | **82.2** | +5.6 | 74.5 | 87.9 |
| GoblinGang | 382390 | 37.4 | **60.5** | +23.1 | 69.3 | **78.1** | +8.8 | 77.0 | 86.4 |
| Bats | 315728 | 35.5 | **60.9** | +25.5 | 75.3 | **76.9** | +1.6 | 80.0 | 90.2 |
| Goblins | 270311 | 58.9 | **63.3** | +4.3 | 73.4 | **76.0** | +2.6 | 72.8 | 81.1 |
| Minions | 240958 | 58.5 | **64.3** | +5.8 | 76.4 | **79.8** | +3.4 | 79.1 | 87.9 |
| GoblinHut | 202790 | 30.3 | **34.1** | +3.8 | 37.2 | **51.3** | +14.2 | 66.6 | 73.6 |
| Skeletons | 186846 | 64.1 | **68.6** | +4.5 | 78.7 | **79.9** | +1.2 | 81.5 | 88.7 |
| Archers | 185385 | 58.6 | **62.5** | +3.8 | 73.3 | **74.7** | +1.4 | 79.1 | 86.7 |
| Princess | 147716 | 54.0 | **61.0** | +6.9 | 74.5 | **77.2** | +2.7 | 77.9 | 87.8 |
| Wallbreakers | 131250 | 68.2 | **72.2** | +4.0 | 72.8 | **75.7** | +2.8 | 83.6 | 85.3 |
| Ghost | 127676 | 21.2 | **23.0** | +1.8 | 53.0 | **56.0** | +3.0 | 66.1 | 68.6 |
| Cannon | 125576 | 84.7 | **85.8** | +1.1 | 71.6 | **76.9** | +5.3 | 92.4 | 88.1 |
| FirespiritHut | 124445 | 23.0 | **46.0** | +22.9 | 30.0 | **65.0** | +35.0 | 68.2 | 51.9 |
| Firecracker | 118978 | 36.6 | **38.6** | +2.0 | 66.7 | **65.8** | -0.9 | 65.5 | 82.4 |
| Knight | 117807 | 59.2 | **63.0** | +3.8 | 60.1 | **64.0** | +3.9 | 81.2 | 81.7 |
| IceGolem | 111962 | 65.8 | **67.7** | +1.9 | 62.0 | **64.3** | +2.3 | 85.1 | 82.8 |
| BarbLog | 110609 | 62.2 | **67.6** | +5.4 | 0.0 | **0.0** | -0.0 | 79.6 | 82.8 |
| Berserker | 108738 | 59.6 | **64.0** | +4.4 | 64.2 | **67.6** | +3.4 | 76.5 | 81.0 |
| BombTower | 104086 | 84.0 | **83.5** | -0.5 | 67.1 | **70.5** | +3.4 | 92.3 | 86.3 |
| RoyalDelivery | 92907 | 71.0 | **75.0** | +4.0 | 81.3 | **83.8** | +2.5 | 83.4 | 86.6 |
| Tesla | 90033 | 89.8 | **90.0** | +0.1 | 75.4 | **77.9** | +2.5 | 88.3 | 77.5 |
| MinionHorde | 89182 | 43.5 | **61.4** | +17.9 | 73.8 | **79.7** | +5.9 | 75.5 | 85.5 |
| BlowdartGoblin | 82593 | 60.6 | **65.7** | +5.1 | 74.2 | **76.9** | +2.8 | 79.2 | 88.1 |
| RoyalHogs | 71906 | 75.9 | **79.2** | +3.2 | 76.0 | **78.8** | +2.8 | 81.8 | 87.0 |
| GoblinBarrel | 70990 | 71.4 | **72.0** | +0.7 | 79.2 | **79.4** | +0.2 | 84.9 | 87.8 |
| BabyDragon | 69861 | 56.2 | **60.5** | +4.4 | 63.3 | **67.9** | +4.6 | 75.8 | 78.2 |
| Goblinstein | 67467 | 9.8 | **69.1** | +59.3 | 50.4 | **75.6** | +25.2 | 89.3 | 91.0 |
| Valkyrie | 65753 | 61.0 | **63.4** | +2.4 | 59.2 | **60.1** | +0.9 | 78.9 | 79.4 |
| Musketeer | 64987 | 56.8 | **62.5** | +5.7 | 66.1 | **67.6** | +1.6 | 83.2 | 85.7 |
| Miner | 63270 | 47.6 | **74.9** | +27.3 | 33.7 | **73.5** | +39.7 | 92.4 | 89.4 |
| Rascals | 61778 | 42.0 | **45.4** | +3.4 | 64.1 | **65.2** | +1.1 | 75.8 | 83.8 |
| DarkPrince | 55470 | 54.7 | **60.9** | +6.1 | 62.1 | **67.1** | +5.0 | 74.0 | 75.0 |
| ElectroSpirit | 47440 | 71.9 | **75.8** | +4.0 | 0.0 | **81.8** | +81.8 | 85.3 | 0.0 |
| MightyMiner | 46268 | 54.3 | **60.3** | +6.0 | 47.0 | **51.6** | +4.6 | 73.2 | 69.4 |
| HogRider | 45181 | 70.4 | **75.8** | +5.4 | 64.2 | **69.5** | +5.3 | 89.3 | 86.5 |
| FireSpirits | 44207 | 69.3 | **72.0** | +2.7 | 0.0 | **77.8** | +77.8 | 85.5 | 0.0 |
| IceSpirit | 43027 | 71.5 | **75.3** | +3.9 | 76.8 | **79.3** | +2.5 | 89.3 | 0.0 |
| InfernoTower | 42676 | 91.2 | **90.6** | -0.6 | 70.6 | **71.6** | +1.0 | 93.8 | 87.0 |
| MiniPekka | 40366 | 58.8 | **66.2** | +7.4 | 57.6 | **63.9** | +6.4 | 82.6 | 83.8 |
| Giant | 33440 | 83.9 | **83.6** | -0.2 | 69.5 | **71.4** | +1.9 | 91.2 | 87.3 |
| Balloon | 30001 | 85.1 | **84.0** | -1.2 | 78.0 | **80.1** | +2.1 | 95.3 | 91.2 |
| Wizard | 24461 | 59.5 | **63.1** | +3.6 | 69.4 | **70.1** | +0.7 | 74.3 | 79.8 |
| Golem | 21577 | 73.7 | **78.1** | +4.4 | 61.8 | **67.4** | +5.6 | 94.0 | 91.0 |
| Prince | 20217 | 53.2 | **61.4** | +8.2 | 48.6 | **55.1** | +6.5 | 76.7 | 74.4 |
| Xbow | 17753 | 91.5 | **90.4** | -1.1 | 76.6 | **75.8** | -0.7 | 98.4 | 94.0 |
| ArcherQueen | 16683 | 54.8 | **59.0** | +4.3 | 62.8 | **63.9** | +1.1 | 74.6 | 79.3 |
| AngryBarbarians | 8635 | 58.4 | **69.1** | +10.7 | 51.0 | **62.7** | +11.7 | 75.3 | 77.6 |

- BarbLog HP exact stays 0.0. Our BarbLog Barbarian has 691 max HP; native has 716 (696 bodies, train). That is base 270
  vs 280 at 256%, a data fix of the same kind as #1. It is the top candidate for batch 2. All other card bodies' level-11
  max HP match native, per a deploy-each-card check against `maxhp-train.tsv`.

## 6. Rust parity (planner core `engine-rs`, clasher_core)

**Which fixes propagate as data:**
- Through the Python-built config (`differential.config()`):
  - spirit HP (stats);
  - FirespiritHut `spawnStartTime` and the GoblinHut first delay (spawner spec `first`);
  - the Goblinstein formation, via the lane-1 template plus `mirror_x`.
- Rust code changes were needed for the rest.
- Edits in `engine-rs/differential.py`:
  - `mirror_x = len(units) in (2,3,4,5,6,15)` (lane-2 mirror);
  - `skip_deploy_snap |= can_deploy_on_enemy_side` (Miner snap);
  - entity export `tunnel_path`.
- Edits in `engine-rs/src/`:
  - `astar.rs`: a negative cost marks an impassable cell; existing callers are unaffected.
  - `c56.rs`: `spawn_path_route` and `spawn_path_trajectory` (ports of the Python routing). `tunnel_move` follows the path
    and clears `underground` on arrival.
  - `lib.rs`: the Entity field `tunnel_path`. `apply_action` computes the routed duration. The deploy-end snap also covers
    routed tunnels, matching Python's `on_spawn`.
  - `spawn.rs`: GoblinHut wake range 6 + own + target radius; the clock runs while idle, capped.

**Build:** on 127x04, `jobs/clasher/bot-calib-r1/build.sh` with its own `CARGO_TARGET_DIR`, against the copy
`repos/clasher-bot-calib`. The .so files are in `jobs/.../so-{cal,head,r1}` on 05.

**Parity** (`bot/fidelity/rs_parity.py`):
- Every fixture's card plays are applied to Python and Rust in lockstep.
- `es_common.battle_digest` is compared with the Rust digest every tick, to the recording's end.
- The first mismatch is recorded along with the differing entities.

| | full-length digest parity (577) | first-mismatch classes |
|---|---|---|
| HEAD Python + HEAD Rust (and r1's pinned native: identical on 120/120) | 429 | IceGolemite 139+3, Princess/Tesla/Firecracker/RoyalHogs/SpearGoblin 1 each |
| calibrated Python + calibrated Rust | **427** | IceGolemite 137+4, others below |

- Against HEAD, 4 fixtures newly fail and 2 newly pass. None of the four is in code changed here; changed trajectories
  expose existing edge cases:
  - `…0813` and `…1222`: Rust fires one extra projectile at the range boundary. A Princess targets a Knight at 9.978 tiles
    against a 10.0 reach; in `…1222` it's a Firecracker.
  - `…0804` and `…1152`: Rust applies a 43-damage hit that Python doesn't. The targets are a Goblinstein doctor (after a
    Firecracker play) and a FirespiritHut. This is probably Firecracker shrapnel; not traced.
- Before the Rust edits (calibrated Python + HEAD Rust, 120 train fixtures): 24/120 parity, with first mismatches in
  Miner 33, Bats 16, SpearGoblin/Goblin_Stab 22, …. After: 78/120, and the 9 remaining Miner cases were fixed by the
  deploy-end snap.
- engine-rs tests `test_parity.py` (13), `test_stage4_goblinstein.py` (5) and `test_stage4_champions.py` (13) pass with
  both builds. `test_canonical_data.py` needs data files that are absent at HEAD too.
- **Not verified:** planner-level equivalence. rs_parity is a full-game replay; the planner's short rollouts use the same
  step and clone. Also not verified: the MightyMiner ability tunnel (unchanged).

## 7. Test suite

- **Full `tests/` (619 files), 32 shards with `--continue-on-collection-errors`:** calibrated 5,621 passed / 219 failed,
  vs a pristine HEAD export 5,524 / 210. Most failures in both are environmental: missing cv2, data files, checkpoints.
- **Tests failing only with the calibrated engine:**
  - Six tests asserted the replaced rules. Each is updated to the native-measured behaviour, with a comment citing the
    section here:
    - `test_enabled_troop_interactions.py`:
      - `…does_not_mirror_five_slot_formation`, renamed `…mirrors_five_slot_formation_on_path_two` (§2);
      - Bats ring at x=9.0 is now on path 2 and mirrored (§2);
      - Miner travel times now follow the routed path, and the Miner is targetable on arrival (§5b/5c). The helper
        `spawn_path_travel_tick_count` assertions are kept.
    - `test_scope_engine_cards.py`:
      - furnace start 3050 → 1000 (§4a);
      - GoblinHut sleep/wake test, renamed `…fires_due_wave_on_wake` (§4b).
  - Three `test_torch_simple_rolling_runtime.py` tests (Log, BarbarianBarrel) also fail at HEAD when run alone. They are
    order-dependent and unrelated.
  - `test_audit_tv_royale_youtube_portrait.py` is a cv2 import error.
- **After the updates:** `test_enabled_troop_interactions.py`, `test_scope_engine_cards.py` and
  `test_calibration_batch1.py`: 676 passed.

## Tools added (all exploration)
- `bot/fidelity/`:
  - `compare_runs.py`: the gate, with LOO and `--view live`;
  - `rs_parity.py` and `rs_parity_debug.py`: Python↔Rust lockstep parity;
  - `run.py`: the `live` view;
  - `engines.py`: seeded RNG.
- Scratch survey tools are in `/mpac/sdicks02/jobs/clasher/bot-calib-r1/tools/` (127x05):
  `maxhp_survey`, `formation_survey`, `hut_survey`, `hut_wake*`, `miner_land`, `miner_route`, `hits`, `tower_hits`,
  `tower_lag`, `tower_dmg_src`.
