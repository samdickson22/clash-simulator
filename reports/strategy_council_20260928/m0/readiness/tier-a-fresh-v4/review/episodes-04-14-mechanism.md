# Tier A v4: mechanism review of the above-floor events in episodes 04 and 14

**Review of opened evidence. This is not a re-evaluation.** The frozen evaluator's `blocked` status for `m0-tier-a-fresh-v4` stands. Under strategy.md Tier A, review may add blocks and may never remove them.

How this review was done:
- It is a read-only analysis of recorded branches.
- No emulator or adb was used. No source was edited. Nothing was written to the ledger.
- Scalar trajectories were replayed in-process from the frozen snapshot `runtime-snapshots/native-final-v4` with the live controllers, the same way `run_readiness_v2._execute_job_body` runs them.
- Every replay reproduced its recorded scalar decision stream exactly, and the terminal HP matched.
- The native side comes from `native_frame` in the reference `decisions.jsonl.gz`. It is recorded every 5 ticks. Native `targetX/targetY` equals the object's position on the previous tick (checked against scalar where the two engines agree), so native gives both t−1 and t on each recorded frame.

## Verdict

| | episode-04 | episode-14 |
|---|---|---|
| Event | scalar prefers **wait**; reference comparator displaced_placement. Score regret 0, margin regret 0.0409, signs [-1,1,1,0] | scalar prefers **displaced_placement**; reference comparator alternate_card. Score regret 0 (tie at 0.5), margin regret 0.0084, signs [1,-1,1,-1] |
| Engine-divergent branches | 1 of 16: wait, balanced/balanced | 2 of 16: alternate_card, balanced/balanced and defense/balanced (same trajectory) |
| First state divergence | ticks 3136-3139, which is 881+ ticks after root 2255. A sub-tick 0.013-tile position offset on an owner-1 Goblin as it retargets | ticks 1646-1649, which is 961 ticks after root 685. Before this all objects matched within 0.004 tiles. An owner-0 Goblin stalls in native but walks at full speed in scalar beside its own Knight at the right-bridge mouth |
| First HP / action divergence | HP at 3295; action at 3355 (the same Goblins play, one decision earlier in native) | HP at 1675; action at 1690 |
| Classification | **Chaotic amplification** of sub-tile movement drift through the tie-sensitive half-tile pathfinder. There is no wait-specific mechanism | **Local movement-interaction discrepancy with native evidence.** The root cause is not isolated. It is amplified chaotically into a margin-only difference. Both engines lose these branches |
| Systematic bias or exploit? | No | No |
| Add a block? | **No** | **No.** Recommend a targeted probe/regression instead (below) |

Neither event meets the repeatable-harm definition:
- ep04 has 1 of 4 continuations favouring the comparator. The rule needs at least 3 of 4.
- ep14 has a margin regret below 1%.

Neither is material. In both families the event exists only because of the listed divergent branches. Replace those branches with the scalar values and the reference ranking equals the scalar ranking.

## Episode-04 (root owner 0, root tick 2255, balanced/balanced wait)

### Candidates and margins

The root cards were:
- immediate: Goblins, action 165;
- wait: the controller plays Goblins one tile over at root+5, action 166;
- alternate: Dark Prince, action 741;
- displaced: Goblins, action 132.

Margin in HP = root-owner remaining Crown HP minus enemy remaining Crown HP. Every branch is a win (score 1).

| role | b/p | b/b | d/p | d/b | mean (normalized) |
|---|---|---|---|---|---|
| wait, scalar | 6647 | **4871** | 4035 | 4489 | 5010.5 (0.4585) |
| wait, reference | 6647 | **2456** | 4035 | 4489 | 4406.8 (0.4033) |
| displaced, both engines | 5027 | 4871 | 5027 | 4489 | 4853.5 (0.4441) |

All 15 other branches in this family are identical across engines. Scalar's preference for wait comes from balanced/pressure, where the two engines agree and wait beats displaced by 1620 HP. The only engine difference is wait b/b:
- scalar 9729/4858;
- reference 7314/4858.

That 2415 HP is damage to owner 0's left Princess Tower, from tick 3485 onward, and it happens only in native. With the scalar value in that cell, the reference would also rank wait first.

### Alignment: scalar job-00138 against reference job-00139

1. **Ticks 2255-3135: exact match.**
   - Every position is within 0.004 tiles.
   - HP, tower HP and elixir are identical.
   - All 177 decision pairs are identical.
2. **Ticks 3136-3139: drift is born.** Owner-1 Goblin `5000070` (scalar 266) retargets from Goblin 61, which is dying, to Goblin 64 (scalar retargets at 3138).
   - At 3139 native has it at (4.990, 20.021) and scalar at (4.977, 20.024), a gap of 0.013 tiles. That is about 1/8 of one tick of Goblin travel.
   - The gap grows to 0.047 by 3185. At 3195 a Goblin-Goblin body push stretches it to 0.20 tiles.
3. **Ticks 3209-3230: the pathfinder amplifies the drift.** Owner-0 Archers 5000067/68 (scalar 258/259) lose their Goblin target and walk toward Goblin 71 across the river.
   - Native Archer 67 heads almost straight up the lane, toward node (4.25, 12.25).
   - Scalar picks node (3.75, 12.25) and ends 0.21 tiles away. Archer 68 ends 0.55 tiles away.
   - **Counterfactual (scalar only, /tmp):** at tick 3210, give scalar's `ground_path_waypoint` the native target position (3.099, 17.762) instead of scalar's (3.04, 17.688). Scalar then returns native's node (4.25, 12.25).
   - The choice is a near-tie that flips non-monotonically when the target moves about 0.03 tiles: a target x of 3.00, 3.07 or 3.13 gives node 4.25, and 3.04, 3.10 or 3.20 gives node 3.75. So scalar reproduces native's decision when given native's inputs. This step amplifies an existing difference; it is not a new rule mismatch.
4. **Tick 3295: first HP difference.** The Archers' attack cycle is shifted, so native arrows hit Dark Prince `5000060` about 5 ticks earlier: 976 HP against scalar's 1200 at 3295, equal again at 3300. At 3355 Dark Prince has 304 HP in native and 528 in scalar.
5. **Tick 3355: first action divergence.**
   - Owner 0's controller plays the same Goblins action (1389) at 3355 in native and at 3360 in scalar.
   - Elixir is identical in both engines (4.8135), and every command is accepted.
   - The cause is the different observed state. It is not transport or controller timing.
6. **After that the fight diverges.** In native, owner 0's left-lane defense (Goblins and two new Archers) is gone by 3450. Owner-1 Dark Prince `5000075`, with the Musketeer and Archers, then reaches the owner-0 left Princess Tower, which drops from 2784 to 369 HP between 3485 and 3600. In scalar that Dark Prince is stopped at y≈13.8 by Archers that survived, and the tower stays at 2784.

### Classification

This is chaotic amplification:
- The seed is a sub-tick movement offset during a routine retarget, 880 ticks after the root. It is too small to resolve at 5-tick native resolution.
- It passes through a pathfinder tie that scalar resolves exactly like native when given native's inputs.
- It then passes through a 5-tick controller reaction, and finally changes one Princess Tower.

Nothing about the candidate "wait" is involved. The same divergence could appear in any branch whose trajectory passed through this state. This is not a mechanics bug that could be fixed, and not an exploit.

## Episode-14 (root owner 1, root tick 685, alternate_card balanced/balanced = defense/balanced)

### Candidates and margins

The root cards were:
- immediate: Ice Golem at the right bridge, action 813;
- displaced: Ice Golem at the left bridge, action 824;
- alternate: Zap, action 1443, after which the controller plays Ice Golem at 690;
- wait: Ice Golem at root+5.

| role | b/p | b/b | d/p | d/b | mean score | mean margin (normalized) |
|---|---|---|---|---|---|---|
| alternate, scalar | +436 (W) | **−4647** (L) | +2 (W) | **−4647** (L) | 0.5 | −2214 (−0.2026) |
| alternate, reference | +436 (W) | **−3901** (L) | +2 (W) | **−3901** (L) | 0.5 | −1841 (−0.1685) |
| displaced, both engines | −3627 (L) | +193 (W) | −3627 (L) | −670 (W) | 0.5 | −1933 (−0.1769) |

This is a margin tie-break between two candidates whose reference means differ by only 92 HP:
- scalar ranks displaced 281 HP ahead;
- reference ranks alternate 92 HP ahead.

The balanced/balanced and defense/balanced alternate branches are one identical trajectory in both engines:
- scalar loses 0-1 at 3601 (6281/10928);
- native reaches 0-0 at 3600 and loses in overtime at 4303 (6915/10816).

### Alignment: scalar job-00460 against reference job-00461

1. **Ticks 685-1645: exact match.**
   - Every object is within 0.004 tiles, apart from one 0.007 blip at 885 that disappears again.
   - HP, towers, elixir and all decisions are identical.
   - (Native 3000xxx/4000xxx area and projectile objects are excluded from the matching.)
2. **Ticks 1646-1650: first divergence, starting from matched state.**
   - Owner-0 Goblins and a Knight kill the last owner-1 Skeleton (about 1646) and retarget to the owner-1 right Princess Tower.
   - Goblin `5000038` (scalar 91, 37 HP) is in the river just left of the right bridge, at (12.834, 15.356).
   - Native positions (t−1 / t): 1645 (12.834, 15.356); 1649 (12.857, 15.242); 1650 (12.869, 15.288).
   - So the native Goblin moves only about one tick's worth of distance in four ticks: it effectively stalls. It then advances at 0.05-0.09 tiles/tick until about 1655.
   - Scalar: 1646 (12.875, 15.230) and 1647 (12.948, 15.136), which is full walking speed toward route node (13.25, 14.75). At 1648 it takes a one-tick body push of (−133, +268) logic units (0.30 tiles) from the Knight, which puts it at (12.905, 15.388). At 1650 it is at (12.916, 15.584).
   - The Knight agrees to 0.002 tiles at 1649 (13.306, 14.443 in both engines). The divergence is in the Goblin's own movement.
   - Scalar has no body contact at 1646-1647: the Goblin-Knight distance is 1.25 tiles, and the collision vector is (−29, −29) then (0, 0). Scalar avoidance (`_native_avoidance`) decays to 0 and first fires at 1648. So native's stall at 1646-1648 is not explained by the contact scalar models.
   - The likely candidates are the timing of native avoidance onset around the Knight ahead, or a route-rebuild or retarget latency for a Goblin standing off-grid in the river. 5-tick frames cannot tell these apart.
3. **Counterfactual (scalar only, /tmp).** Overwriting the four owner-0 unit positions with native's values at 1650 does **not** resynchronise scalar.
   - By 1655 the scalar Goblin is again 0.29 tiles ahead: 0.125 tiles/tick against native's 0.068.
   - The difference is a continuing movement-rule mismatch while the Goblin shadows the Knight onto the bridge. It is not a one-off offset.
4. **Tick 1675: first HP difference.** Different Goblins absorb the Princess Tower's shots (5000037 and 5000038 have swapped HP).
5. **Tick 1690: first action divergence.** Owner 1 plays action 741 in scalar and 760 in native.
6. **After that** the trajectories diverge completely. The 746 HP margin gap at the end comes from about 1000 ticks of chaotic evolution.

### Classification

This is a local movement mismatch that native evidence confirms:
- The state matched before 1645.
- A 0.3-tile Goblin offset appeared within 4 ticks, and overriding positions does not resynchronise scalar.
- The situation is a light unit walking just behind a heavier friendly unit at a bridge mouth.

The mechanism is not isolated, so this review does **not** claim a specific code bug.

Each occurrence has a small effect (where one Goblin stands). Here it was amplified into a margin-only difference, and both engines lose this branch. It is not tied to a candidate class, and it gives the scalar-preferred candidate no advantage that could be exploited. It is not wait-related.

Recommendation, not a block:
- Add a per-tick native probe of a Goblin trailing a Knight onto a bridge after its target dies, using job-00461 frames 1640-1660 as the fixture seed.
- Track it as a Tier B targeted-probe item.

## Wait-bias scan across all 32 v4 families

Definitions:
- For each family, c* is the reference-best non-wait candidate (by mean score, then mean margin).
- Normalized margin uses the family's `starting_crown_hp` (10928).
- Δ = (scalar wait − c*) − (reference wait − c*). A positive Δ means scalar rates wait relatively higher than the reference does.

| family | ref-best non-wait | wait − c* score (scalar / ref) | wait − c* margin (scalar / ref) | Δ margin (scalar − ref) | diverging branches |
|---|---|---|---|---|---|
| 00 | immediate_play | +0.000 / +0.000 | -0.2207 / -0.2207 | +0.0000 | — |
| 01 | alternate_card | +0.000 / +0.000 | -0.3272 / -0.3272 | +0.0000 | — |
| 02 | displaced_placement | +0.500 / +0.500 | -0.0118 / -0.0118 | +0.0000 | — |
| 03 | alternate_card | +0.500 / +0.000 | -0.0463 / -0.0913 | +0.0450 | alternate 2, displaced 2 |
| 04 | displaced_placement | +0.000 / +0.000 | +0.0144 / -0.0409 | +0.0552 | wait 1 |
| 05 | displaced_placement | +0.000 / +0.000 | -0.1702 / -0.1702 | +0.0000 | — |
| 06 | immediate_play | +0.000 / +0.000 | +0.0000 / +0.0000 | +0.0000 | — |
| 07 | alternate_card | -0.500 / -0.500 | -0.1633 / -0.1633 | +0.0000 | — |
| 08 | displaced_placement | +0.000 / +0.000 | -0.1583 / -0.1583 | +0.0000 | — |
| 09 | alternate_card | +0.000 / +0.000 | +0.1878 / +0.0741 | +0.1136 | alternate 2 |
| 10 | immediate_play | +0.000 / +0.000 | -0.0875 / -0.0875 | +0.0000 | — |
| 11 | alternate_card | +0.000 / +0.000 | -0.2499 / -0.2174 | -0.0325 | alternate 2 |
| 12 | immediate_play | +0.000 / +0.000 | +0.0000 / +0.0000 | +0.0000 | immediate 1, wait 1, displaced 1 |
| 13 | alternate_card | -0.500 / -0.500 | -0.2846 / -0.2846 | +0.0000 | — |
| 14 | alternate_card | -0.500 / -0.500 | -0.0461 / -0.0802 | +0.0341 | alternate 2 |
| 15 | alternate_card | +0.000 / +0.000 | -0.2352 / -0.2352 | +0.0000 | immediate 2, displaced 2 |
| 16 | alternate_card | -0.500 / -0.500 | -0.0153 / -0.0153 | +0.0000 | — |
| 17 | displaced_placement | +0.000 / +0.000 | -0.0838 / -0.0838 | +0.0000 | — |
| 18 | alternate_card | +0.000 / +0.000 | -0.0065 / -0.0065 | +0.0000 | displaced 2 |
| 19 | alternate_card | +0.500 / +0.500 | +0.0662 / +0.0662 | +0.0000 | — |
| 20 | alternate_card | +0.000 / +0.000 | -0.0954 / -0.0954 | +0.0000 | — |
| 21 | displaced_placement | +0.250 / +0.250 | -0.1628 / -0.1883 | +0.0255 | wait 2 |
| 22 | immediate_play | +0.500 / +0.500 | +0.2069 / +0.2069 | +0.0000 | alternate 2 |
| 23 | immediate_play | +0.000 / +0.000 | +0.0000 / +0.0000 | +0.0000 | — |
| 24 | immediate_play | -0.250 / -0.750 | -0.2811 / -0.3447 | +0.0636 | immediate 2 |
| 25 | alternate_card | +0.000 / +0.000 | -0.1478 / -0.1472 | -0.0006 | immediate 1, wait 1, displaced 1 |
| 26 | alternate_card | +0.000 / +0.000 | -0.1662 / -0.1662 | +0.0000 | — |
| 27 | alternate_card | +0.000 / +0.000 | +0.0227 / +0.0227 | +0.0000 | — |
| 28 | alternate_card | +0.000 / +0.000 | -0.3389 / -0.3389 | +0.0000 | displaced 1 |
| 29 | alternate_card | -0.250 / -0.250 | -0.0097 / -0.0097 | +0.0000 | — |
| 30 | immediate_play | +0.000 / +0.000 | +0.0000 / +0.0000 | +0.0000 | — |
| 31 | alternate_card | +0.000 / +0.000 | -0.1236 / -0.1236 | +0.0000 | — |

### Summary

- **Δ is zero in 24/32 families.** It is positive in 6 (03, 04, 09, 14, 21, 24) and negative in 2 (11, 25). The mean Δ is +0.0095, about 104 HP. The mean score Δ is +0.031, positive in 2 families (03, 24) and never negative.
  - A 6-of-8 sign split is not significant (one-sided binomial p ≈ 0.14).
  - The 8 families are not a random sample of a single mechanism.
- **The wait branch itself is the diverging branch in only 2 of the 6 positive families:**
  - ep04: sub-tile drift 880 ticks after the root (above);
  - ep21: a Musketeer offset of 0.06 tiles at about tick 5010, in overtime, 4890 ticks after the root. The first action divergence is at 5410.

  Both are late chaotic drift.
- **In the other four (03, 09, 14, 24), the wait branches agree across engines.** Δ > 0 there because scalar *under-rates a play*:
  - alternate_card in ep03, ep09 and ep14;
  - immediate in ep24.

  Across the attempt, collapsing identical paired branches into unique divergent trajectories, and counting a trajectory shared by several roles once under each role:
  - alternate_card is scalar-worse in 5 of 6 (03, 09, 11 b/b, 14, 22, against 11 d/b);
  - displaced is scalar-better in 4 of 6 (12 d/b, 15, 18, 28, against 03 and 25);
  - immediate is mixed, 2 of 4 (12, 15 against 24, 25);
  - wait is scalar-better in 3 of 4 (04, 12, 21, against 25).

  The mechanisms differ where they are known (ep04 pathfinder-amplified drift; ep14 Goblin/Knight movement). This is worth flagging for Tier B targeted probes. It is not a demonstrated single repeatable mechanism.
- **In this design, "wait" is almost never a distinct strategy.** In 29 of 32 families the wait branch's root owner plays at root+5 ticks, and in 20 of them it plays exactly the immediate action. So wait mostly means "the immediate play, 0.25 s later". Scalar over-rating wait would amount to mis-ranking a 5-tick delay, and none of the reviewed divergences depends on that delay.

**Conclusion on bias:** there is no evidence of a systematic scalar preference for waiting that could be exploited. The slight positive tilt in Δ comes mostly from scalar being pessimistic about some non-wait plays in a few chaotically divergent trajectories. That pattern (mainly alternate_card) should be watched in Tier B but does not justify a block here.

## Relation to episode-03 (reviewed separately by another agent; not duplicated here)

Branch-level structure only:
- In ep03 all eight **wait** branches agree across engines.
- ep03 diverges in **alternate_card** (pressure pair: scalar loses where native wins; first action divergence at 395, root at 175) and in **displaced_placement** (balanced pair: scalar loses where native wins; first action divergence at 790).
- So ep03's "scalar prefers wait" comes from scalar *under-rating the plays* through win/loss reversals.
- ep04's comes from scalar *over-rating the wait branch* in one condition, through late drift.

These are different branches, at different distances from the root, with different directions. No shared mechanism with ep04 is shown.

ep03 does share a *direction* with ep14 (and ep09): scalar is more pessimistic than native about the alternate_card trajectory. Whether ep03's first state divergence is a body-movement interaction like ep14's belongs to the ep03 review.

## Reproduce (scratch, not retained)

The scripts are in `/tmp/rv0414/`. Run them with `CLASHER_ROOT=<snapshot>` from `runtime-snapshots/native-final-v4` using its `.venv/bin/python -B`.

| script | what it does |
|---|---|
| `replay.py <ep> <condition> <role> [--window a:b] --out f.json` | scalar replay with per-tick state dump |
| `cmp.py` | native/scalar object alignment |
| `towers.py` | tower HP differences |
| `units.py` | object listings |
| `wp_hook.py`, `wp_cf.py` | pathfinder waypoints and counterfactual |
| `phase_hook.py`, `avoid_hook.py` | per-phase movement and avoidance state |
| `override.py` | position-override counterfactual |
| `waitbias.py` | 32-family table (uses `/tmp/v4rows.json`, built from every `branches-*/job-*/result.json`) |
