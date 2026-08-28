# Simple PyTorch Gym CUDA optimization profile (2026-08-27)

Status: exact before/after A6000 evidence. The accepted pre-optimization
checkpoint was profiled before the optimization commits, and the optimized
source plus its newer-main integration were then re-profiled on the same pod.
No simulator, model, dataset, checkpoint, or live Desktop training file was
edited by this profiling leg.

## Provenance

| Artifact | Exact identity |
|---|---|
| Pre-optimization checkpoint | `7c5349f46cea4aa6793887cf34c98f041d5ebb97` |
| Accepted source predecessor | `504444ea400ff8bf595c0386ff000afe2c1f3490` |
| Pre-optimization integration | `b1ff9f1e2e1380071cca62afab68afdbb5dfdef9` |
| Shared pre-optimization `src/clasher/torch_sim` tree | `cad04dbbc9cd8d4a39c9c79227dcbf65caae38b0` |
| Pre-optimization integration archive | SHA-256 `599686cc4886792f5a2668cc5fc4bfd8474f87493c264aae116ce15b4171966b` |
| Optimized source | `36cd5ec996c6077c4c8066ada6f071222ecc73ca` |
| Optimized integration | `c91ca56d3fcb71c40b94fb93bed3c62191fb25bd` |
| Optimized integration archive | SHA-256 `3bd83979db91405d4ce572e58b3518e55252915fb04b90caab15e04bc0eec745` |

Both extracted archives used frozen Python 3.12 environments with PyTorch
2.10.0+cu128. The device was one NVIDIA RTX A6000, compute capability 8.6,
with 48 GB VRAM. It was the only paid pod and was terminated after evidence
copy; the final active-pod count was zero.

The raw compressed Chrome traces, tables, JSON, logs, and complete SHA-256
manifests are preserved outside Git at:

```text
/Users/sam/.codex/evidence/clasher-pytorch-optimization-20260827/preopt
/Users/sam/.codex/evidence/clasher-pytorch-optimization-20260827/optimized
```

The committed compact copies are under
`reports/profiles/simple_gym_preopt_a6000_20260827` and
`reports/profiles/simple_gym_optimized_a6000_20260827`. The raw after-profile
table filenames retain the generic harness's `accepted_eager` label; the
structured `after.json`, runtime type, and checkpoint metadata all identify
those runs as the integrated production `cuda-graph` route.

## Accounting method

- Absolute throughput comes from separate synchronized timers, never profiler
  wall time.
- Host launch, memcpy, allocation, and synchronization counts use CUDA runtime
  API CPU events below the measured `record_function` marker.
- CUDA Graph node/device kernel executions and device durations come directly
  from Kineto CUDA events. They are not inferred from CPU annotation ancestry.
- Annotation events, memcpy events, memset events, and actual kernel events are
  reported separately.
- A profiler-closing `torch.cuda.synchronize()` is outside the measured marker
  and excluded from synchronization counts.
- Source throughput uses batch 128, entity/effect capacity 128, and the stable
  first-legal policy. The direct before/after comparison is 3x10 ticks; the
  optimized absolute gate also uses 3x100 ticks.
- Integrated throughput uses the actual 494-token, 2,572,503-parameter default
  recurrent policy, decision interval 8, and the training wrapper. Batch 6
  uses the exact current 48-decision rollout default. Batch 128 uses eight
  decisions to keep paid profiling bounded.

## Source-runtime result

| Metric | Pre-opt `7c5349f4` | Optimized `36cd5ec9` | Change |
|---|---:|---:|---:|
| B128 graph row-ticks/s, same 3x10 window | 409.456 | 415.351 | +1.44% |
| Optimized B128 graph row-ticks/s, 3x100 | - | 416.075 | absolute after gate |
| Host submission APIs per tick | 10 | 10 | unchanged: 1 graph + 9 eager action-selection kernels |
| Actual CUDA device kernels/nodes per tick | 15,138 | 14,516 | -4.11% |
| Device memcpy events per tick | 1,001 | 952 | -4.90% |
| Profiled kernel device time | 313.884 ms | 311.284 ms | -0.83% single-trace observation |
| Peak allocated delta during graph replay | 5.35 MB | 5.35 MB | unchanged |

The same-window final transition digest is identical before and after:

```text
2eb49b28460e30053b5e815f2eb9d012860812813bc69a99a6b871b1f410140e
```

The optimized 3x100 trials were 416.075, 416.247, and 415.939 row-ticks/s and
shared one deterministic digest. The longer-window digest differs from the
10-tick digest because it covers 100 ticks, not because the repetitions
diverged.

CUDA Graph capture increased from one captured tick graph to three production
graphs (tick, selective reset, and selective reset with replacement decks).
Despite that expanded capture surface, the isolated optimized source capture
was 0.466 seconds on this run; integrated capture was 0.376 seconds at batch 6
and 0.348 seconds at batch 128. Capture-time measurements are initialization
costs, not rollout throughput.

## Real integrated recurrent collector

The accepted `b1ff9f1e` integration did not instantiate
`SimpleCudaGraphRunner`; its actual production collector was eager. The
pre-optimization run therefore profiles both that accepted eager route and an
uncommitted in-memory graph-wrapper diagnostic. The optimized `c91ca56d`
integration makes CUDA Graph execution the explicit production contract and
fails construction rather than silently falling back.

| Shape | Accepted pre-opt eager | Pre-opt graph probe | Optimized production graph | Optimized vs accepted |
|---|---:|---:|---:|---:|
| B6, 48 decisions: actor decisions/s | 5.554 | 23.791 | 25.804 | 4.646x (+364.6%) |
| B6: native row-ticks/s | 22.215 | 95.166 | 103.217 | 4.646x |
| B128, 8 decisions: actor decisions/s | 74.140 | 99.214 | 101.289 | 1.366x (+36.6%) |
| B128: native row-ticks/s | 296.558 | 396.856 | 405.158 | 1.366x |

The measured rollout digests are byte-identical across accepted eager,
pre-optimization graph probe, and optimized production graph execution:

```text
B6 / 48:  9a477653dc3832323559453f429578fbf520b7fc813885cd61544262fbe0e31b
B128 / 8: 98de937cdb0f42115daff05e44efe88f0f21f3ba667f9bb78d2e1a3b8042095c
```

Every selected recurrent action was legal under public-mask contract v2 in
all four throughput legs. The exact optimized archive also passed 108 focused
CUDA tests spanning graph replay, selective reset, river movement, rolling
spells, collision/navigation, rollout/recurrent storage, and the real
Simple-PyTorch training route.

## Launch, synchronization, and memory result

One raw device-resident decision contains eight native ticks. Counts below
exclude training-wrapper host conversion unless explicitly noted.

| Metric | Pre-opt accepted eager B6 | Optimized graph B6 | Reduction |
|---|---:|---:|---:|
| Host launch APIs | 125,668 | 3,103 | 97.53% |
| Actual CUDA device kernels/nodes | 125,651 | 120,011 | 4.49% |
| Host memcpy APIs | 8,525 | 131 | 98.46% |
| Peak allocated memory | 283.96 MB | 63.40 MB | 77.67% |

| Metric | Pre-opt accepted eager B128 | Optimized graph B128 | Reduction |
|---|---:|---:|---:|
| Host launch APIs | 125,664 | 3,099 | 97.53% |
| Actual CUDA device kernels/nodes | 125,635 | 120,008 | 4.48% |
| Host memcpy APIs | 8,525 | 131 | 98.46% |
| Peak allocated memory | 5.309 GB | 0.934 GB | 82.40% |

The full timed-rollout peak allocations fell from 309.1 MB to 86.5 MB at
batch 6 (-72.0%) and from 5.384 GB to 0.989 GB at batch 128 (-81.6%).

The raw collector still records two stream synchronizations per decision; the
isolated recurrent-policy phase accounts for those two. The existing training
wrapper records 33 synchronizations because it materializes the collected PPO
batch as host NumPy arrays. That count is unchanged and is not hidden by the
graph result. It is outside the dense runtime graph but remains a future
end-to-end training optimization target.

## Phase evidence and remaining bottleneck

| Batch-6 isolated phase | Pre-opt host launches | Optimized host launches |
|---|---:|---:|
| Observe | 677 | 677 |
| Public mask v2 | 119 | 119 |
| Recurrent policy | 333 | 333 |
| Bridge step, eight ticks | 122,908 | 1,828 (8 graph launches) |
| Selective reset | 817 | 9 (1 graph launch) |

The optimized decision still executes 120,011 actual CUDA kernels/nodes. CUDA
Graphs remove Python/driver submission overhead; they do not fuse the captured
PyTorch graph's internal operations. The bridge-step phase alone executes
117,922 device kernels. The remaining eager work outside the tick/reset graphs
accounts for approximately three thousand host submissions per decision.

In the pre-optimization eager bridge profile, `aten::cumsum` was the largest
correlated device-time family: 776 calls and 186.6 ms across one eight-tick
decision. In a graph replay, Kineto does not reliably map captured device nodes
back to the original ATen CPU calls, so the after trace reports low-level
kernels rather than pretending to have source attribution. The dominant
float scan family remains six kernels and about 26.5 ms in the optimized
single-tick trace. This is the clearest remaining device-side fusion target;
the current evidence does not claim it was eliminated.

## Conclusion

The optimized source removes 4.1% of internal tick kernels and improves the
same-window raw graph runtime by 1.44%. The larger production gain comes from
making the graph runner and captured selective reset the real newer-main
collector contract: 4.65x at the current small batch, 1.37x at batch 128,
roughly 97.5% fewer host launches, and 72-82% lower measured peak allocation.
The measured policy-visible rollouts remain digest-identical. These results do
not imply that the remaining 120k device nodes are fused, that host batch
materialization is synchronization-free, or that a single A6000 run provides
cross-host confidence bounds.
