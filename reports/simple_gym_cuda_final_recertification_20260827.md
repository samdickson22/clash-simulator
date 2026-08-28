# Final Simple PyTorch Gym CUDA recertification (2026-08-27)

Status: passed with an explicit residual-boundary disclosure. Exact source
`9f54de4e` and exact integrated newer-main archive `52118254` preserve all
tested behavior and improve the recurrent wrapper handoff. The handoff itself
meets its four-copy/one-sync design target; the complete wrapper still contains
two recurrent-policy DtoH copies and synchronizations outside that handoff.

## Exact provenance

| Artifact | Identity |
|---|---|
| Source | `9f54de4eac9e219f8837dd9d1fe9b218efb2ddef` |
| Integrated newer-main candidate | `521182544c5d52de0251c2449f17c6edf5a69b92` |
| Integration Git tree | `8b6dab2423397bf8de71fc23e956c29e26127452` |
| Tested archive | `clasher-main-final-integration-9f54de4e-52118254.tar` |
| Archive SHA-256 | `85161addda30a29b7a06dc53c7b5264a42077dce6fc3f6ebf7e8ebda359e55a5` |
| Comparison source | `36cd5ec996c6077c4c8066ada6f071222ecc73ca` |
| Comparison integration | `c91ca56d3fcb71c40b94fb93bed3c62191fb25bd` |

The frozen environment used Python 3.12.14, PyTorch 2.10.0+cu128, and the same
physical RTX A6000 UUID (`GPU-c813c4f4-5323-343e-9df9-82d0a1189abf`) as the
immediately preceding optimization profile. The tested pod was the only paid
pod and was terminated after two independent checksum-verified local copies.
Final active pod count: zero.

No simulator source, model, dataset, checkpoint, Desktop checkout, or active
training process was edited by this recertification leg.

## Focused CUDA gates

The exact archive passed 154 tests in 80.38 seconds. The scope included:

- slot-bound attack locks and the integrated attack-lock runtime;
- tick and selective-reset CUDA Graph replay;
- river movement, rolling spells, and collision/navigation;
- rollout/recurrent storage and collector graph-address safety;
- the real Simple-PyTorch newer-main backend; and
- CPU/CUDA coalesced-handoff shape, dtype, value, and one-helper-sync tests.

## Deterministic terminal episodes

The source runtime completed two CUDA Graph replays for each policy at seed
`202608263`. Both results exactly match the accepted `504444ea` terminal
evidence:

| Policy | Terminal boundary | Result | Digest |
|---|---:|---|---|
| noop | tick 6,000 | regulation, overtime, tiebreak; draw | `d14d2c7b5d41fed9784b521c9ee31c27b7d9a10903954dbf792abf73cd0c4226` |
| first-legal | tick 3,600 | regulation crown; player 1 | `0430c8f45ab028d590bbdb293ff25dd3f936ec172aa6f9bbd7af786e83981fc1` |

Every row-tick was native and committed, the terminal boundary was reached,
repetitions were deterministic, and fallback remained zero. The validator's
per-tick full-boundary digest copies make its wall time unsuitable as a
throughput measure; throughput is measured separately below.

## Source graph performance

Batch 128, entity/effect capacity 128, first-legal policy, three synchronized
100-tick trials:

```text
417.347, 417.215, 416.861 row-ticks/s
median: 417.215 row-ticks/s
```

The prior exact `36cd5ec9` median on the same GPU was 416.075 row-ticks/s, so
the final source is +0.274%. The 100-tick transition digest is unchanged:

```text
5f8ac1972d2302ac5c3408aa3a266ba78e4cc2b498e1c56de8f7c97b2592dfb8
```

One raw graph tick records 10 host submissions (one `cudaGraphLaunch` plus nine
first-legal action-selection kernels), zero marked synchronizations, 14,505
actual CUDA kernels/nodes, and a 5.35 MB peak allocation delta. The preceding
source recorded 14,516 nodes; the slot-bound target-lock change removes 11
more nodes (-0.076%). Profiled kernel device time was 308.716 ms for this
single trace versus 311.284 ms previously, but a single profiled duration is
diagnostic rather than a confidence bound.

## Actual recurrent collector throughput

The model is the real 494-token, 2,572,503-parameter default recurrent policy,
using public-mask v2 and integrated CUDA Graph execution at decision interval
8.

| Shape | Prior `c91ca56d` | Final `52118254` | Change |
|---|---:|---:|---:|
| B6/full48 actor decisions/s | 25.804 | 25.912 | +0.418% |
| B6 native row-ticks/s | 103.217 | 103.649 | +0.418% |
| B128/8 actor decisions/s | 101.289 | 101.863 | +0.567% |
| B128 native row-ticks/s | 405.158 | 407.453 | +0.567% |

Every selected action was legal under the public mask. Exact rollout digests
are unchanged:

```text
B6/full48:  9a477653dc3832323559453f429578fbf520b7fc813885cd61544262fbe0e31b
B128/8:    98de937cdb0f42115daff05e44efe88f0f21f3ba667f9bb78d2e1a3b8042095c
```

The checkpoint metadata still declares `execution_mode=cuda-graph` with digest
`ae34af4785e40f714a254b6138d901138eca348a13529efa93bf53e5dafef9c0`.

## Coalesced handoff accounting

The wrapper was profiled as a complete one-decision call and the raw recurrent
collector was profiled separately at the same boundary. Copy directions come
from Kineto device event names; synchronization-helper calls were counted by a
temporary profiler-side wrapper without changing source.

| Metric | Prior wrapper | Final raw boundary | Final full wrapper |
|---|---:|---:|---:|
| DtoH device events | 31 | 2 | 6 |
| Marked CUDA runtime synchronizations | 33 | 2 | 3 |
| Host `cudaMemcpyAsync` APIs | 174 | 131 | 150 |

Therefore the coalesced staging handoff adds exactly:

```text
4 DtoH dtype-slab copies
1 _synchronize_cuda_stream call
```

The 4/1 handoff target passes at both batch 6 and batch 128. Relative to the
previous complete wrapper, total DtoH events fall from 31 to 6 (-80.6%) and
marked synchronizations fall from 33 to 3 (-90.9%). The final total is not
misreported as 4/1: isolated phase evidence attributes the remaining two DtoH
events and two synchronizations to recurrent policy inference. Removing those
would be a separate policy-sampling optimization.

Wrapper host-launch count changes only from 3,405 to 3,408 at batch 6 and from
3,397 to 3,400 at batch 128; coalescing transfers is not kernel fusion. Actual
raw decision nodes fall from 120,011 to 119,921 at batch 6 and from 120,008 to
119,919 at batch 128.

The coalesced device slabs increase the B6/full48 timed peak allocation from
86.5 MB to 110.6 MB (+27.8%). B128 remains exactly 988.6 MB. This memory cost
is reported rather than hidden; it is small relative to A6000 capacity but is
a real tradeoff.

## Profiler semantics and limitations

- Absolute throughput comes from synchronized timers outside the profiler.
- Host launch/copy/sync counts use CPU CUDA-runtime events below the measured
  marker.
- Actual kernels/nodes and memcpy directions use Kineto device events directly.
- CUDA Graph replay events are not assigned back to ATen calls through CPU
  annotation ancestry, which Kineto does not reliably preserve.
- The profiler-closing synchronization lies outside the measured marker.
- This is one physical A6000; it proves the bounded gate, not cross-host
  variance or a statistical confidence interval.
- Batch 128 integrated collection uses eight decisions to bound the paid run;
  batch 6 uses the exact current 48-decision default.

## Evidence and teardown

Compact structured evidence is committed under
`reports/profiles/simple_gym_final_a6000_20260827`. Complete raw traces, tables,
logs, and their SHA-256 manifest are preserved at:

```text
/Users/sam/.codex/evidence/clasher-pytorch-final-recert-20260827
```

The prior-wrapper direction audit cites the exact previous trace SHA values.
All final raw files passed `sha256sum -c` both under `/private/tmp` and under
the durable evidence path. The paid pod was then terminated successfully and
the provider returned zero active pods.
