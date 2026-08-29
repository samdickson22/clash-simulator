# Simple Gym terminal-counterfactual production gate

## Decision

Accept the exact resident fork, explicit phase-scheduled root bank, and
terminal-continuation API for offline structured action-value corpus
production. The retained source tip is `d03a8f7e` on
`codex/pytorch-terminal-counterfactual`, descended from the safe integrated
authority `41d13fed`.

Do not claim online or end-to-end dense-root readiness. A full 16-root
phase-balanced H200 run completed correctly, but including root construction it
produced only 0.309 candidate slots/s (0.180 unique candidates/s). The next
production design should microbatch phase roots and/or use shorter tactical
horizons while retaining terminal calibration samples. First-N early roots are
not an acceptable benchmark.

## Retained implementation

- `c161d4c0`: exact device-resident runtime row forks. One source row may be
  repeated into many preallocated speculative rows. Every retained action,
  combat, effect, lifecycle, status, movement, outcome, and projection plane is
  copied; immutable setup drift fails before mutation.
- `37008194`: rollout bridge forks also preserve previous action/reward/start
  history, reward baselines, and reset state. CUDA Graph tick captures remain
  valid after a fork.
- `aa593bb3`: model-neutral terminal evaluator for
  `[source battle, candidate, two seats]` first actions. It preserves exact
  public structured roots and returns terminal winner, learner value, crowns,
  Crown Tower HP, tower damage received, action success, decision/native-tick
  counts, admission, and terminal recurrent state. The source rollout is never
  mutated, and early-terminal rows freeze while other candidates continue.
- `6f549624` and `81c807a6`: real recurrent/public-mask-v2 benchmark and CUDA
  profiler harness.
- `aa65ad65`: speculative continuation projection is actor-only. The source PPO
  collector retains its privileged critic; candidates expose no critic or
  opponent-private state.
- `24a3631b`: fixed-capacity resident root banks accept explicit target ticks,
  preserve the actual tick/phase/overtime flags and recurrent hidden/cell state,
  and copy heterogeneous live rows into a preallocated evaluator.
- `32bbd96d`: root copying accepts eager or CUDA-Graph-backed source bridges.
- `d03a8f7e`: phase collection advances from the live row assigned to the next
  target. A regression test covers an early source terminating while its paired
  no-op source continues into late regulation and overtime.

The production training adapter constructs a resident `batch * candidates`
arena with the same serialized setup, capacities, reward contract, recurrent
policy, public-mask-v2 semantics, and CUDA Graph runtime mode as the source.
The tested workload is base plus five alternatives.

## Behavior gates

- Full local Simple/RL surface after phase-root integration:
  `439 passed, 263 skipped`.
- Focused H100 CUDA fork/evaluator/backend/mask/rollout/Graph surface:
  `65 passed, 8 platform skips`.
- CPU and Apple MPS exact repeated-row continuation tests pass. The real
  494-token recurrent actor/public-mask-v2 bounded benchmark also completes on
  MPS. MPS remains eager and is not CUDA speed evidence.
- Six-way mixed terminal tests prove that regulation winners freeze at eight
  ticks while live rows continue to the twelve-tick test tiebreak, including
  terminal recurrence, crowns, damage, admission, and native-tick accounting.

## Exact CUDA terminal evidence

The final code retains the established full-episode digests on H100 CUDA Graph:

| Policy | Final tick | Reason | Winner | Digest |
| --- | ---: | --- | ---: | --- |
| no-op | 6000 | overtime tiebreak | draw | `d14d2c7b5d41fed9784b521c9ee31c27b7d9a10903954dbf792abf73cd0c4226` |
| first-legal | 3600 | regulation crown | 1 | `0430c8f45ab028d590bbdb293ff25dd3f936ec172aa6f9bbd7af786e83981fc1` |

Both commands used two deterministic replays. Every row tick was native and
committed, fallback was zero, and the terminal boundary was reached. This
re-certifies the post-MPS descendant directly; no pre-MPS A6000 speed result is
reused as current evidence.

## Counterfactual throughput

H100 PCIe, Torch `2.10.0+cu128`, public-mask-v2 tensor actor semantics,
decision interval eight, entity capacity 56:

| Workload | Time | Candidate decisions/s | Native ticks/s | Peak allocated/reserved |
| --- | ---: | ---: | ---: | ---: |
| 1 source x 6 branches, tick 128 to terminal | 144.239 s | 18.053 | 144.427 | 55.5 / 197.1 MB |
| 8 sources x 6 branches, tick 128 to terminal | 302.205 s | 72.557 | 580.279 | 196.6 / 1077.9 MB |

The one-source final digest is
`37ce278fe8fc175f5b0670275c8ae4c48c09e0a1354c083a8a5ef806b4be50e9`.
The earlier three-repetition gate produced that digest every time. The
eight-source run shows roughly fourfold throughput scaling versus one source,
while remaining far from the throughput needed to query every 16 decisions
online.

The eight-source full run preceded the actor-only projection flag and is used
only as a scaling diagnostic. The subsequent actor-only short-window A/B kept
the same transition digest and changed throughput by only `+0.09%`.

The four-decision actor-only profiler recorded 8,958 host launch APIs, nine
explicit synchronizations, nine D2H events, and 504,203 CUDA device events.
Peak memory is modest. Tiny policy/mask kernels and synchronization dominate.

### Full phase-balanced gate

The production benchmark now defaults to the frozen 16-root schedule rather
than first-N eligible roots. On an H200 with Torch `2.10.0+cu128`, it captured
and evaluated roots at exactly:

`256, 608, 968, 1328, 1688, 2048, 2400, 2760, 3120, 3480, 3600, 4192, 4552, 4912, 5272, 5632`.

This covers early, mid, late regulation, overtime, and triple elixir. Actual
ticks matched every target. Roots through 3480 came from the dynamic source;
3600 onward came from the paired no-op source, preserving logical state after
the dynamic source's terminal boundary.

| Full-mix measure | Result |
| --- | ---: |
| Root slots x candidates | 16 x 6 = 96 |
| Unique candidates | 56 |
| Continuation-only time | 159.786 s |
| Terminal candidate slots/s | 0.6008 |
| Continuation decisions/s | 111.881 |
| Native ticks/s | 894.754 |
| End-to-end wall time, including root construction | 310.46 s |
| End-to-end candidate slots/s | 0.3092 |
| End-to-end unique candidates/s | 0.1804 |
| Peak allocated/reserved | 333.97 MB / 1.65 GB |

The result digest is
`76fdefc74cbe22959bf6058ddc0c45e985892cd779e5f322efd406583ffb1c42`.
The evaluator's fail-closed contract requires every branch to reach terminal,
remain admitted/committed, and use zero fallback before emitting this result.

Eight roots had only no-op as a unique legal candidate; the remaining eight
had six unique candidates. Accordingly, the 96-slot number is useful for
resident execution throughput, while 56 is the honest number of distinct
labels. This is a successful correctness gate and a failed online-throughput
gate, not an end-to-end readiness claim.

## Rejected optimizations

Two experiments were removed completely:

1. Reusing the already-projected post-step policy boundary reduced short-window
   launch APIs from 9,334 to 7,300, but changed B8 throughput only
   29.025 to 29.120 terminal candidates/s (`+0.33%`). It was reverted.
2. A combined CUDA Graph for tensor public masking plus recurrent actor forward
   captured after disabling PyTorch `Categorical` argument validation. It
   changed the rollout digest, improved B8 throughput only to 29.190
   candidates/s (`+0.57%`), and increased peak memory. It was never committed.

Dropping speculative privileged-critic projection is retained for the public
state contract, not sold as a speed win: B8 throughput was 29.025 versus 29.051
candidates/s with the same digest, while peak allocation fell from about
191.0 MB to 185.8 MB.

## Evidence files

Machine-readable evidence is under
`reports/profiles/simple_terminal_counterfactual_20260828/`. The phase-balanced
archive is `/private/tmp/clasher-phase-root-bank-d03a8f7e.tar.gz`, SHA-256
`d3854e4d599ce378e2f07cf1ca28d20d6967d9ecb692a022703a6668634583ee`.

The task-owned H100 pod `8192a69653854f9f98dc4622cfa2da50` and phase-gate
H200 pod `a3b733d10e324e78869fbc033fc8b125` were terminated. Active paid GPU
pod count was verified as zero. An unrelated external CPU pod was not touched.
