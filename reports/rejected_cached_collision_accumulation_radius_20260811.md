# Rejected cached collision-accumulation radius candidate

Date: 2026-08-11

## Candidate

Reuse `Entity._collision_radius` inside
`BattleState._accumulate_troop_collision_for` instead of reading the immutable
card-stat value at runtime. The normalized entity field is exact, data driven,
and card general, but representative rollout evidence did not meet the
acceptance threshold.

## Shared-load conditions

Measurements were bounded, single process, and run at low priority while a
Clasher 64-environment/12-actor MPS training phase and one RoadForge CPU process
shared the host. Alternating order and paired comparisons were used. These
conditions make the aggregate medians less reliable than paired direction.

## Evidence

All fixed-seed hashes matched between runtime and cached variants:

- random rollout: `8bcf61259509b1f2f80750fa29ccaf695ba9f11e46b46e2967069d2d90fce432`
- balanced-strategy rollout: `67faf6c5e975db614868686ead0c2515840dfd02729342a228127e837f22844d`
- stable-root oracle: `9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`
- crowded engine: `d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`

Aggregate median rates appeared higher for cached reads: random rollout
`+0.50%`, strategy rollout `+1.17%`, oracle labels `+0.92%`, and crowded engine
`+0.51%`. Paired trials contradicted that apparent rollout gain:

- random rollout: paired median `-0.51%`, 3/7 pairs positive;
- balanced strategy: paired median `-0.11%`, 3/7 pairs positive;
- stable-root oracle: paired median `+0.92%`, 3/5 pairs positive;
- crowded engine: paired median `+1.35%`, 9/11 pairs positive.

The engine-only result is too small to outweigh the negative/noisy
production-shaped rollout pairs. The candidate source, tests, and temporary
drivers were removed; no optimization commit was created.
