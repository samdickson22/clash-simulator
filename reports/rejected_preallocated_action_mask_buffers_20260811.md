# Rejected preallocated rollout action-mask buffers

Date: 2026-08-11

The candidate allowed the exact scalar/fast action-mask builders to fill a
caller-owned row and reused learner/opponent mask buffers in CPU rollouts. Its
fixed off/shadow/on unit probes and full-rollout digests matched the allocated
path, but production-shaped timing did not establish a reliable gain.

Both screens used seed 2301, 8 environments, 32 decisions, 8 warmup decisions,
7 alternating matched pairs, 2 Torch threads, the exact fast path, and
`nice -n 10`. A RoadForge reconstruction and a Clasher MPS imitation fit were
active; an unrelated Clasher pytest process also appeared during the strategy
screen.

| workload | allocated median seconds | preallocated median seconds | paired gain median | paired gain stdev |
| --- | ---: | ---: | ---: | ---: |
| stationary random | 1.500212 | 1.503360 | +0.86% | 2.96 points |
| balanced strategy | 1.633092 | 1.563148 | +0.59% | 2.93 points |

Random had three regressing pairs; strategy had one regression and several
near-zero pairs. The unpaired median-rate calculation was -0.21% random and
+4.47% strategy, demonstrating host drift rather than a stable source effect.
The paired medians are below the threshold needed to justify the broader
action-mask API and buffer lifetime complexity.

All random rows produced digest
`8bcf61259509b1f2f80750fa29ccaf695ba9f11e46b46e2967069d2d90fce432`;
all strategy rows produced
`67faf6c5e975db614868686ead0c2515840dfd02729342a228127e837f22844d`.
The 30 direct output-buffer/action-mask tests passed before rejection.

All candidate source, test, and benchmark-driver hunks were removed. This
report is retained only as an uncommitted audit artifact; no optimization
commit was created.
