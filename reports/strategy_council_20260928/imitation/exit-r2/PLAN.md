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

Every effective batch is8192. Train seed2026101001, **play weight1**, value
weight0; unchanged r1 AdamW lr3e-4, weight decay.05, 2000-step warmup and
qualified cosine schedule with the arm's total steps, clip1, EMA.999.
X1–4 process40,001,536 rows; X5 processes80,003,072. Teacher micro≤128.
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

Stage3: at most3 stage2 survivors, selected by lowest stage2 point loss;
ties: highest stage1 hard agreement, then X1→X5 order. Each orders K1's anytime
coarse scan and adds top8 legal proposals, playing against the unchanged v1
policy. Control is plain K1 with empty hooks against that same v1 policy;
arm/control share seed, decks and seat. Both actors retain K's v1 fallback
polling; only own search hooks use the student. Use own600 control games,
because K's original reporting seeds differ. With200ms wall deadline
and8ms reserve, on600 paired seeds4503601517370496+[0,600). Common init reference,
same deck/seat schedule, whole paired bootstrap. **Kill if loss-change upper
CI≥0.** Explicit contrast is loss(arm)−loss(control); opponent is v1 in both.
Coordinator clarified this before any reporting games; use versioned v2 X
evaluation entrypoints and passed v2 wrapper qualification. K's harness at `reports/explore/k-anytime/` is the primary harness;
if it is unready at2026-10-10 06:00Z, freeze the already-declared fallback to
r1(b) E1 deadline W-screen8. Record that decision before affected games.

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
