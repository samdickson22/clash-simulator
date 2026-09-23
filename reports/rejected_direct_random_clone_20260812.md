# Rejected direct `Random` clone

Date: 2026-08-12. A guarded `random.Random.__new__` plus exact
`getstate`/`setstate` path was evaluated against generic deepcopy. It applied
only to the exact built-in type with no extension attributes and retained the
generic path for subclasses or custom state.

On three fixed seed-2301 snapshots, 15 alternating pairs, and 500 whole battle
clones per row, median throughput changed from 2939.59 to 2946.13 clones/s.
The paired median was only +0.2223%, 9/15 pairs improved, and the bootstrap mean
95% CI crossed zero (-0.0291% to +2.5476%). The candidate therefore failed the
whole-clone attribution gate and was removed without spending a production
Oracle timing run.
