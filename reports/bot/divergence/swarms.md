# Swarm-card divergence (SkeletonArmy, Bats, GoblinGang, MinionHorde)

Read-only on the engine. 7 train episodes (714, 847, 933, 1080, 1303, 700, 960 suffixes of v4-phase-a-19751007xx/01xxx).
Scratch: `/tmp/sdicks02/swarm-div/` on 127x05. Runs on 03: `debug_traj.py` ×3 episodes only.
Counterfactuals monkeypatch `formation_offset` locally; repo source untouched. Denominators differ from FIDELITY.md.

## (1) Where the error starts

**a. Spawn ring is right, but x-mirrored for some path-2 groups.** Path 2 = anchor x ≥ 12.5k
(`native_tilemap.py:103`). Nearest-neighbour distance, truth→ours at spawn, native units (direct / x-mirror):

| episode, card, group | n | path | direct median/max | mirror median/max |
|---|---:|---:|---:|---:|
| 714 SkeletonArmy t619 (14533,8619) | 15 | 2 | 420 / 925 | **66 / 276** |
| 847 SkeletonArmy t1357 (14530,18398) | 15 | 2 | 443 / 925 | **61 / 61** |
| 847 SkeletonArmy t2741 (12540,29400) | 15 | 2 | 443 / 925 | **80 / 80** |
| 714 SkeletonArmy t1177 (5468,6600) | 15 | 1 | **4 / 150** | 464 / 962 |
| 1080 Bats t2540 (14500,13500) | 5 | 2 | 439 / 441 | **0 / 0** |
| 1080 Bats t3004 (1527,6500) | 5 | 1 | **0 / 0** | 422 / 493 |
| 1303 MinionHorde t3135 (17180,25544) | 6 | 2 | **0 / 0** | 271 / 640 |

Bats 5000017 starts at truth (13507,14493) and ours (13862,14751), a constant 438 offset that equals the mirror residual.
Both sit still until ~2631 and both start moving ~2686, so spawn timing matches. Path-1 and 6-slot groups are exact.

**b. Dynamics after a correct spawn.** GoblinGang first frames are exact (700: 36/36 within ¼ tile; 960: 71/72). Median
ticks from spawn to first >¼-tile error: GG 700 = 55 (p25 25); GG 960 = 27 (p25 9); SA 714 = 4 (driven by the mirror).
Median speed, first 40 ticks (mT/tick, truth vs ours): GG 700 46.5/46.5; GG 960 17.2/14.4; SA 714 33.5/41.9; SA 847 43.5/40.8.
No consistent bias. Unknown.

**c. Deaths and counts.** GG 700 has 215 truth units vs 112 ours; Ghost diverges first at tick 896. Alive-mismatch for GG
is 57% over 7 episodes. Mechanism: unknown.

## Counterfactual (7 episodes; no-tower % of unit-ticks within ¼ tile)

| variant | SkeletonArmy | Bats | GoblinGang | MinionHorde |
|---|---:|---:|---:|---:|
| baseline | 24.8 | 32.5 | 25.6 | 26.3 |
| lane-2 flip, primary count ∈ {5,15} | **48.9** | 29.8 | 25.6 | 26.0 |
| lane-2 flip, primary count ≥ 5 | **48.8** | 30.0 | 25.6 | **44.8** |

Caveats: Bats worsens (alive-mismatch 18%→57%, unit-ticks 13k→18k), so the flip changes fights there, not just
geometry. The MinionHorde gain conflicts with the t3135 check, unexplained. Seven episodes only.

## (2) Root-cause hypotheses, ranked

1. **Missing lane-2 x-mirror for large formations (confirmed for SkeletonArmy and Bats).**
   `formations.py:53-57` flips x only for lane 1 with 2–3 slots and lane 2 with 4. `formations.py:148` applies it.
   `balance.py:96-100` says larger formations keep world order; the data contradict that on path 2 only.
   Call chain: `battle.py:1578` → `_spawn_unit_at_angle` (`battle.py:1642`) → `formation_offset` (`battle.py:1661`).
2. **5-slot base angle (possible).** `formations.py:67` sets base 180. Under mirror it becomes 0. May explain the
   residual Bats mismatch better than the flip. Unverified.
3. **Per-index radius for slots > 6 (minor).** `formations.py:82-84` scales radius by `((i*3)%7)/6`. Sets differ by up
   to ~150 mT. Explains the mirror max of 276, not the large errors.
4. **Post-spawn separation/avoidance or targeting (not established).** GG first frames are exact yet diverge 27–55 ticks
   later. SA 714 member 5000012 jitters ±100–400 mT per 16 ticks while truth walks smoothly. `entities.py` not read. Unknown.
5. **Unit deaths and counts (not established).** GG 700 loses half its units. Combat, spawner or target choice: unknown.

## (3) Fix sketch and verification

- Sketch, not applied: at `formations.py:53-57`, flip lane-2 x for primary count ≥ 5 (or {5,15}). Keep the 2–4-slot rules.
  Re-check Bats 1080, which gets worse.
- Verify on the full corpus on 03 (`--issue-offset -1 --workers 40`, FIDELITY.md recipe), compared with
  `/mpac/sdicks02/jobs/clasher/bot-fid-r2/clasher/`. Accept only if SA and MH gain and no card regresses, Bats included.
  Add a regression test on first-frame geometry for 847 t1357 and 1080 t2540.
- Not done: full-corpus run, `entities.py` review, 2/3/4-slot path-2 cases (no data in my set).
