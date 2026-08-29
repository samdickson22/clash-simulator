# Simple Gym terminal-counterfactual production gate

## Decision

Accept the exact resident fork and terminal-continuation API for structured
action-value corpus production. The retained source tip is `aa65ad65` on
`codex/pytorch-terminal-counterfactual`, descended from the safe integrated
authority `41d13fed`.

Do not claim that dense terminal supervision is cheap yet. The implementation
is exact and production-shaped, but a single source root expanded to six full
terminal branches still takes about 144 seconds on an H100 from tick 128. The
next optimization target is the real recurrent policy/public-mask decision
path, not simulator state cloning or VRAM.

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

The production training adapter constructs a resident `batch * candidates`
arena with the same serialized setup, capacities, reward contract, recurrent
policy, public-mask-v2 semantics, and CUDA Graph runtime mode as the source.
The tested workload is base plus five alternatives.

## Behavior gates

- Full local Simple/RL surface: `434 passed, 263 skipped`.
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
`reports/profiles/simple_terminal_counterfactual_20260828/`. The final archive
is `/private/tmp/clasher-terminal-counterfactual-aa65ad65.tar.gz`, SHA-256
`42f65e23bc237d0ca5afb05e401ef9cc4321c2b0079cd28c640f90bdaafe6e57`.

The task-owned H100 pod `8192a69653854f9f98dc4622cfa2da50` was terminated.
An unrelated external CPU pod remained active and was not touched.
