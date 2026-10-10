# K harness and X stage3 interface

K implementation: `planner.py:planner_class(base)` wraps the frozen E1 delay planner. `search_threads=1|4`, `coarse_horizon=160|80`; all complete scores use the planner's horizon160. `score_candidates(root, seat, candidates, deadline=absolute_monotonic_cutoff, fallback=action)` accepts `deadline=None` for unlimited scoring. The harness starts the200ms timer before public observation and uses start+192ms as the scoring cutoff.

X optional hooks, empty in every K arm:

```python
core.coarse_order = tuple(student_ordered_legal_play_ids)
core.refine_proposals = tuple(student_top8_legal_play_ids)
```

WAIT/WAIT10 and timed waits finish first. `coarse_order` reorders every legal immediate play's balanced scan without dropping any candidates. Duplicate/unknown IDs are ignored. After the full coarse scan, score-ranked top8 (original candidate order breaks ties) are unioned with eligible `refine_proposals`; all three styles at horizon160 determine final eligibility. A cutoff before the full scan retains only complete wait scores. A cutoff in refinement retains completed waits and completed refined plays. Partial and late scores never count. The final epsilon tie rule preserves original candidate order.

X must set these hooks before scoring and include student inference time in the same full-decision timer. K1 comparator leaves them empty. Supply a new stage3 plan/seed audit/config/output path; do not edit K's frozen plan or runtime. The K seed audit already discloses all earlier exploration ranges and helper offsets; stage3 uses the coordinator's separate seeds4503601517370496+[0,600).

`run.py` is the E1 game harness with symmetric delay27, capacity1, five-tick unmodified v1 polling, 10-tick search cadence, five decks/25 matchups and alternating seats. Current runner offers frozen K arms via `--config --out --workers --pairs --offset --arms`, with `--smoke` selecting the disjoint smoke range. A homogeneous pool must use either one-thread arms or four-thread arms. Workers pin1 or5 physical CPUs. `close()` drains the per-game executor.

Owned runtime: `/mpac/sdicks02/jobs/clasher/k-anytime-20261010-r1/repo` on03/01; native binarySHA44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2. It is a generic Linux E1/current-gil build with tick cancellation, without v3. No Mac or live admission follows from this interface. Qualification receipts accompany the implementation commit8237f993.
