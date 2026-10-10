# X: ExIt r2 target fix and conditional R2 DAgger

Authority: coordinator 0523ae6f; §2 X and R2 in `PLAN-NEXT-20261010.md`
at commit `63b2d6d7`. Exploration lane; no multiplicity adjustment. This plan,
seed audit, target code and operational recipe are committed and pushed before
the first fit. Final EMA only; no intermediate checkpoint selection.

Common inputs: corpus manifest
`1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b`;
released v1 main-2026100802 step22552 EMA, width192, checkpoint
`d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed`;
public assets `3954af44678a5f397c22d1eaa4c6be9b3c7517b3c5fe0d0e3151f4ab9937c737`.
Human train manifest
`0546cfddcf79be12509953358fb499ac3be29493ba4a87893bfbfbbe0f179e68`.
R1 screen freeze `787e4c6a` refers to the freeze-file SHA prefix, not a git commit.
Held-out 64-game manifest:
`0ecce0f0f410ff7f1093994cdb62b44c4c141c3a4bddb237cf1427b0a512818f`.
Neither that slice nor evaluation games enter training.

| Arm | Target | Teacher fraction | Host | Steps | Human micro |
| --- | --- | --- | --- | --- | --- |
| X1 | raw-score softmax T=.003 | 1.0 | 127x09 | 4883 | 7168 (no human rows) |
| X2 | raw-score softmax T=.0001, exact ties split | 1.0 | 127x16 | 4883 | 7168 (no human rows) |
| X3 | per-root population z-score; softmax τ=.5 | 1.0 | 127x08, then released13/14 if needed | 4883 | 7168 (no human rows) |
| X4 | raw-score softmax T=.003 | .75 | 127x01 | 4883 | 3584 |
| X5 | X1, twice the optimizer steps | 1.0 | 127x04 | 9766 | 7168 (no human rows) |
| X6 | raw-score softmax T=.0001, exact ties split | .75 | 127x13, yields to X3 resume | 4883 | 3584 |

Every effective batch is8192. Train seed2026101001, **play weight1**, value
weight0; unchanged r1 AdamW lr3e-4, weight decay.05, 2000-step warmup and
qualified cosine schedule with the arm's total steps, clip1, EMA.999.
X1–4 and X6 process40,001,536 rows; X5 processes80,003,072. Teacher micro≤128.
Human thinning/IPW and source-conditional denominators remain r1. Z-score uses
only valid completed candidates, population variance, std floor1e-12; equal
scores and one-candidate roots yield uniform targets over valid candidates.
The same target function computes effective-batch denominators and micro losses.
The flag defaults off and must pass an off-equals-r1 optimizer/gradient test.

Actual loader6, prefetch4, complete-step order/index checks, scientific Torch
threads1; loader cores120–125, parent118/119/126. Periodic checkpoints250.
No random mmap advice. Home memory floor24GiB; leased aggregate PSS guard46GB,
hard limit48GB, ≤16 Clasher processes, nice≥10, ≥8GiB GPU free. Lease/reclaim
checked before launch and every10s. An owned STOP checkpoints only our trainer;
forced cleanup addresses only our process group. Stop fits by Oct11 05:15Z;
everything exits before lease expiry05:30Z. All caches and data stay under/mpac.
Use owned `pilot/detach.sh`: setsid-f, stdin closed, log/PID/PGID receipts.

Read-only, rate-limited53GB corpus staging for16 is authorized; every copied
corpus file is SHA-checked by TeacherStore before the first optimizer update.
04 retains r1 cores and no simulations, protecting A1's CPU seal.
Coordinator operational amendment2026-10-10 00:43Z explicitly releases08's GPU
to X3 until05:30Z today. GPU fit plus loader only, nice≥10, no simulations,
owned stop/PID/PGID. Quiet-file08 entry or coordinator reclaim triggers immediate
checkpoint/vacate. Guard begins checkpoint stop05:15Z, guaranteeing vacate by
05:30Z. Recipe, sampler, seeds, targets, rows and final EMA unchanged; exact
checkpoint continuation on13/14 only after their capacity workers vacate.
05 remains a command center with no builds/tests/training/simulations.
Any13/14 continuation needs capacity PROGRESS release plus an independent empty
nvidia-smi compute-process check. Never preempt capacity;13 is overflow/R2.
Coordinator utilization addendum received2026-10-10 01:13Z, labeled01:05Z,
adds X6 on released13. X1/X2/X4/X6 form the temperature×human-anchor2×2;
same train seed and inputs preserve paired recipe comparisons. Original
X1–X5 freeze/source hashes remain unchanged; X6 has its own seed audit and
SHA-pinned addendum committed/pushed before launch. Read-only corpus staging
is throttled153600KiB/s and every manifest-listed file SHA checked. X6 uses
owned `X6.STOP`; `X3.RESUME.REQUEST` on13 vetoes launch and requests an
immediate checkpoint stop of an active X6. The six-arm home03 controller sends
that request when08's X3 health reports a stop reason. It does not resume X3
automatically. Verify X6's checkpoint/exit and GPU idle before migrating X3;
X3 always takes priority. X6 yield is operational censoring/pause, not a kill.

Stage1: reuse the frozen r1 held-out64 whole games, seeds
4503601207370496+[0,64). Root-only gate probability recall at stochastic T1,
top8 recall among teacher-chosen plays, hard action agreement, and expected WAIT
retain r1 definitions. Whole-game5000-resample percentile95% intervals,
bootstrap seed80991010. Report all-WAIT agreement (teacher WAIT prevalence).
**Kill if play recall<.60, top8 recall<.50, hard agreement<.704, OR
student WAIT>1.5×teacher WAIT.** Incomplete/SHA-mismatched diagnostics never pass.

Stage2: only stage1 survivors play256 terminal h2h games vs released v1 on
4503601507370496+[0,256), five frozen train-archetype decks/25 matchups,
deck=i%5, opponent=floor(i/5)%5, seat=i%2, symmetric d27/capacity1, abilities
disabled, stochastic gate(c) T1 each5ticks. Whole-game bootstrap as above.
**Kill if loss upper95% CI≥.50.** Missing/nonterminal cases cannot pass.

Stage3 was replaced by coordinator decisions01:50/01:56 and the default-layer
equivalence ruling. The old degenerate K1-vs-v1 comparator remains historically
sealed and suspended by STAGE3.HOLD. Only the new S-default addendum and
versioned entrypoints admit replacement reporting after qualification/push.

Stage3: at most3 survivors across all six arms, ranked by lowest stage2 loss,
then highest stage1 hard agreement, then X1→X6. On600 paired seeds
4503601517370496+[0,600), every arm faces released v1 with one physical core,
threads1/coarse_horizon160/200ms deadline/8ms reserve. C-v1 has empty K1 hooks,
and uses v1's polled action on cutoff without a completed refined play. S-n
runs the final-EMA student's joint legal argmax (WAIT allowed) first inside the
timer, orders all coarse plays and adds top8 legal candidate/refinement
proposals; its no-complete-play cutoff uses the student's default. With any
complete refined play, retain the frozen best-complete-score rule. K0 is a
paired descriptive frozen baseline-search anchor. **Kill if upper paired95% CI
of loss(S-n)−loss(C-v1)≥0**; report S-n−K0 descriptively. This full student
package contrast does not separate the hook effect from the default effect.
Use5000 shared paired bootstrap resamples, existing X seed80991010.

No controls are pre-run. For each seed, C-v1, every selected S-n and K0 run
back-to-back on the SAME home03 host/core and nice19/SCHED_IDLE/Torch1 class.
Rotate fixed [C-v1, ranked survivors, K0] order by index modulo arm count.
An incomplete block is archived and entirely replayed, with every attempt
charged; never combine cases recorded under different load intervals.
K-v2 must finish reporting and have zero active timing game processes before
any replacement game. G STOP/full drain,24GiB floor and physical-affinity
checks precede work. Qualification on core60 is allowed; reporting cores0–59
are used only after timing release, with60–63 reserved for gates.

Qualification: C-v1 reproduces empty-hook K1 actions/scores125/125; S-n
reproduces K1 with identical student hooks and candidate list125/125.
Seven injected-clock tests pass. The v1 stand-in changed11/125 actions versus
empty-hook K1 (8.8% diagnostic, not a qualification failure); initial44/50
is retained. Fixture-only short HUDs are filled with known distinct tokens
from the fixed first train-archetype deck. Real games retain exact opening
orders. Seven admission/ranking/legal-default/stop-reap tests pass. Each raw
and translated
game JSON records threads/coarse_horizon/default_source. After the new
addendum is committed/pushed and K timing work exits, six disjoint wrapper
smokes (indices4/5, C-v1/S-standin/K0) must pass actual timer/opponent/polling/
legality/terminal checks before reporting. Smoke losses are excluded.
Entry points: game_pool_sdefault.py, stage3_block_worker.py,
game_worker_sdefault.py, k_stage3_sdefault.py, reduce_stage3_sdefault.py.
The new receipts stage3-sdefault-addendum.json and seed audit preserve every
original scientific hash and require a pushed prelaunch receipt.

Coordinator G01 restriction labeled01:43Z, received01:50Z: coordinator wrote
G STOP on01 at01:37:55Z. G stays off01 throughout the rest of X4 fitting and
may return only after explicit coordinator release. X never clears G stops or
restarts G. This supersedes the prior filler availability on01;03 remains
available to G until X gate admission requests its yield. X4's steps836–851
slowdown is disclosed operationally; recipe/source/optimizer/RNG lineage and
final EMA selection are unchanged.04 needs no intervention (coordinatorPSI0).

Coordinator G handoff amendment2026-10-10 01:45Z: G filler may occupy03
physical0–59 and01 physical0–39 until an X gate is ready. Before evaluation,
create the host-specific G STOP-03/STOP-01 and wait for every G ops process
on that host to exit. Do not signal/kill G or clear its stop. Current automatic
03 gates use controller_g_yield.py plus evaluation_g_yield.py: STOP precedes
process scan, at least two empty samples and24GiB home floor precede child
launch. Original controller_x6.py/addendum bytes remain sealed. Manual01
work must use the same handoff. Qualified on03 with fake G metadata and no
games; receipts g-admission-amendment.json/g-admission-qualification.json.

All simulations/diagnostics run on home01 leftovers/03, nice≥10/SCHED_IDLE,
physical cores without SMT duplication, memory floor24GiB. Load/affinity checks
and coordination with K precede claims. No CPU-heavy sims on leased hosts.

R2 is conditional on any stage2 survivor (independent of stage3 outcome).
Choose the same deterministic ranking above. Label approximately2M scored
teacher-root states from its own free-running games with unlimited W; reserve
4503601707370496+[0,32768), disjoint from reporting and helper RNG seeds. Stop
at a terminal-game boundary, retain exact completed prefix and count. Behavior
comes from the survivor, labels from independent unlimited W; never drive these
games with W's selected action. Refit from the survivor on the union of r1+r2
sealed rows with the survivor's target/fraction,4883×8192 and seed2026101001,
final EMA. Run stages1–3 again. Reusing the specified evaluation ranges is
adaptive exploration and is reported explicitly; no confirmatory claims.
If insufficient lease time remains for generation, fit and screens, report
resource censoring rather than claiming a scientific kill or a completed R2.

Fresh smoke range4503601527370496+[0,32) is separate from reporting/generation.
Seed audit covers game and helper offsets0,13,100000–100003,271828–271829;
new plan declarations are distinguished from historical consumed-game evidence.
Retain prior r1 multi-host inventory/range-review SHAs and fresh Clasher-only
host inventories. No roader paths, processes or mirrors are accessed.

RESULTS.md reports every arm's stage metrics, skip/kill reasons, pins, case
counts, training rows, throughput, metered GPU-wall hours and process CPU hours,
including failed/replayed attempts. PROGRESS-X.md carries timestamps, exact
commands, identities and durable checkpoints. Coordinator milestones<150words.
Only explicit owned paths are staged/committed; run clasher-secret-scan on the
staged diff and push each milestone.

Operational stage3 amendment: K-v2 may use later repair phase names (r3 etc).
A successful REPORTING*-DONE marker is required together with zero active
K-v2 timing processes, checked during blocks. Earlier literal-R2 guard is
archived in the original d0264ec9 stage3 freeze. Scientific design unchanged.
