# ExIt r1 adapter and generation plan

Exploration only. No live player replacement or L2 player pin changes.

Teacher: native W-screen8, explicit `wait_screen8=True`, horizon160, independent
public-prior root/RNG, d27 capacity1, 10-tick search decisions. Emit v6 every5ticks.
Timed10/20/40tick WAITs expand into per-poll WAIT rows. Screened-out candidate
scores remain present with `root_valid=false`; no fabricated scores. Multiple
timed WAIT probabilities sum into WAIT for soft CE. Pending-command waits are
retained in the data and excluded from student supervision.

Eight own-deck entries: five highest-frequency train archetype decks from the
frozen C56 catalog, plus L2 Hog2.6, X-Bow cycle and Royal Hogs spawners, transcribed
from L2 `register.py`. Both seats alternate; all64deckmatchups repeat. Opponents
rotate equally across W-screen8, released-v1 stochastic gate-c, baseline search,
and public balanced/pressure/defense scripts. Ability commands disabled for all.
Generation seeds start4503599727370496; 04index offset100000000. Acceptance and
tuning seeds start4503599708370496 and are disjoint. These are not reporting
seeds for the future student screen.

Target **6M scored root decisions combined**, with expanded poll rows reported separately:
ceilings4M on03,6M on04,4M on08. The lightweight fleet controller stops all three
at6M combined completed roots (polling can overshoot by completed in-flight games).
03 uses46workers+supervisor+spawntracker <=48, cores62–127;
04 uses94+2 <=96, cores30–127, after coordinator's T5release. Memory floor24GiB,
nice10/SCHED_IDLE/setsid, checks each second. Stop files interrupt at the next
simulation tick, including in-flight games. Only completed games are sealed.
No leased CPU sims, no05heavy work, no01generation. 08 joined by explicit coordinator
instruction:94workers+2supervision <=96,nice19/SCHED_IDLE, cores0–125, leaving126/127
free. Its own stop file interrupts in-flight games; verified pilot vacation1.409s
with renewed cache service2095380still running. No GPU work. An early08perception
stop reduces its contribution;03/04can continue to the combined6M target.
08indexoffset200000000; excluded vacation pilot300000000.

Student adapter: explicit `--init-checkpoint` (v2when selected, releasedv1now),
`--teacher-ratio` fraction (T:H = r:(1-r)), `--temperature .1`, `--play-weight 4`,
optional `--value-weight`. Human samples retain T11's epoch wait thinning and IPW.
Teacher conditional card/tile CE divides by play probability mass, so waits do
not drown those heads. Ratio0uses the unchanged qualified loss/optimizer.
Human-only, mixed and teacher-only arms share a step budget; dev/heldout/student
game screen plan freeze remains coordinator-owned. Kill recall<50% of teacher, or fallback
score delta<=0against v2fallback. No NLL-only adoption.

Capacity configurations: widths192/288/384/768, four layers, six heads,
FFN4*width, tile64. **Width192 is the live proposer candidate**. Wider candidates
are offline-only teachers because their measured single-core p99 exceeds15ms.
Probe includes public feature building and top8, 1000calls at10/25/64entities,
core63, synthetic inputs, releasedv1weights at192/randomweights at other widths.
Runtime latency is not a strength result. Before continuing a capacity arm past
25% of schedule, compare devNLL at matched rows; kill gain<.005. The adapter's
`kill_scan` implements this condition; orchestration must supply matched control
scores. No capacity training is launched by this worker.

Coordinator revision10:56Z: round1 stops at6M roots (~39M expanded rows);
anything beyond is DAgger round2. After E1, do not expand beyond about64 workers
per host on physical cores. B3/B4 screen infrastructure is now in scope; no
reporting games run before the coordinator freezes the exploration plan.
