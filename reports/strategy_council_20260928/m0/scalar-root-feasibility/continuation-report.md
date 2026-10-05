# Scalar development continuation study

**All 512 declared branches completed with zero failures.** The fixed 32-root bank produced **31/32 scalar non-wait-informative families** under the unchanged rule: a difference in mean match score above zero, or a difference in normalized mean Crown HP margin greater than 1%. This exceeds the 16-family design-feasibility target in the scalar study. Native consequential coverage and admission remain unestablished.

The study used seed 260928903, all four candidate roles and all four agreed reacting continuation conditions. Both controllers reacted every five ticks, with only the root owner's first action replaced by the declared candidate. The prefix reserve was not applied to continuations. Every branch reached a true terminal outcome, at ticks 2507–6001. No roots were replaced and no completed branches were rerun.

Twenty-one families separated non-wait candidates by mean match score; 31 separated them by mean HP margin. The one uninformative family was `m260928903-episode-17` (IceSpirit, seat 1, enemy-cluster context). Its result remains in all accounting.

| Focal card | Non-wait informative | Score-separated | Margin-separated |
|---|---:|---:|---:|
| Archers | 2/2 | 2/2 | 2/2 |
| Cannon | 2/2 | 1/2 | 2/2 |
| DarkPrince | 2/2 | 1/2 | 2/2 |
| Fireball | 2/2 | 1/2 | 2/2 |
| Giant | 2/2 | 0/2 | 2/2 |
| Goblins | 2/2 | 1/2 | 2/2 |
| HogRider | 2/2 | 2/2 | 2/2 |
| IceGolem | 2/2 | 1/2 | 2/2 |
| IceSpirit | 1/2 | 1/2 | 1/2 |
| Knight | 2/2 | 2/2 | 2/2 |
| Log | 2/2 | 1/2 | 2/2 |
| Musketeer | 2/2 | 1/2 | 2/2 |
| Prince | 2/2 | 2/2 | 2/2 |
| Skeletons | 2/2 | 2/2 | 2/2 |
| Tesla | 2/2 | 1/2 | 2/2 |
| Zap | 2/2 | 2/2 | 2/2 |

Each class has 128 branches (32 families × four conditions). Scalar-best family exposures include exact score/margin ties, so their counts may sum above 32.

| Candidate class | Mean match score | Mean normalized HP margin | Scalar-best family exposures |
|---|---:|---:|---:|
| Immediate play | 0.5078 | 0.0154 | 6 |
| Wait | 0.5625 | 0.0570 | 11 |
| Alternate card | 0.5391 | 0.0188 | 9 |
| Displaced placement | 0.5625 | 0.0273 | 10 |

These are descriptive results under the frozen scripted continuations, not estimates of playing strength or native ranking accuracy. Every non-wait class participates in an informative non-wait pair in 31 families. Waiting has zero such exposures by definition; its scalar-best exposure count is reported separately.

Every root was reconstructed from its saved public prefix/actions. All prefix packet hashes and both selected-root public archives matched before branching. Per-branch immutable claims bind the study plan, root packet, candidate and condition; compressed decision traces and terminal score/HP results are saved beneath `continuations-seed-260928903/`. Failed or interrupted claimed branches would be retained rather than silently rerun; none occurred.

The independent audit verified the exact 512-branch grid, all 373,256 decision boundaries, every trace hash, first forced actions, five-tick cadence, true terminal boundaries, WDL scores, HP normalization and family/pair aggregation. The denominator remained the root owner's full initial Crown HP 10928. The 1% margin threshold and score floor 0 were declared before outcomes and were not adjusted.

Actual dependency sources and inputs stayed unchanged throughout execution and final verification. The capture ruleset is SHA256 `daa58b28cf4e45d753e83ca69a76794285b63704e62363ee58e617af3a30ecc3`. The workspace game-data file was also pinned because the global spell registry reads it; Fireball, Log and Zap source entries were checked identical between those two files before execution. Other native/workspace card-stat differences were not hidden. Initial scalar hands remain the first four declared deck cards; native shuffle equivalence is unproven.

Unrelated package changes are recorded separately in `independent-verification.json`, including the new compact-frame/level-extension modules and changes to calibration, ownership, transport, prefix collection and training code outside the active dependency set. They did not alter the scalar producer's dependency pins. The source window was released only after final verification.

The bounded run used two CPU workers and took approximately 24.5 minutes; changing background machine load makes this a coverage study rather than a throughput benchmark. It made no native calls and produced no training labels. The bank and all outcomes remain opened development evidence.

Key artifacts:

- `continuations-seed-260928903/study-plan.json`: frozen design, input/source pins and all selected requests; SHA256 `b9c7e4815ccf4d4fe862ddae5c01e862b8e2e58a66ea5d6bcddb365c83ea4c4e`.
- `continuations-seed-260928903/summary.json`: all family means, separations, preferred classes and missing-case accounting.
- `continuations-seed-260928903/independent-verification.json`: independent checks, per-card/class distributions and source-drift inventory.
- Each family/condition/role directory: immutable claim, complete terminal result and compressed decision trace.
