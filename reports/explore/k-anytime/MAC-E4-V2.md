# Mac E4 v2 note: advancing K4 and K4h

Updated 2026-10-10T01:33:49Z.

Prepared on Linux after the completed K exploration. **No Mac access, transfer, measurement or live change occurred.** This note updates the search proposal for the existing [Mac E4 package](../../strategy_council_20260928/live-loop/v4/mac-e4-package/RUNBOOK.md); the package and its pins were not edited.

K4 and K4h both meet the frozen advance rule: loss change versus K0 is −27.17 pp, with paired 95% CIs [−31.67, −22.50] and [−31.67, −22.83] pp. Both have 19.33% loss and 100% point retention against the unlimited ceiling. K1 does not advance: 96.50% loss, +50.00 pp [46.00, 54.00] versus K0. **The four-thread Mac dependency remains.** Full data and qualification are in [RESULTS.md](RESULTS.md).

## Proposed v2 search cells

| Cell | Scheduling | Coarse horizon | Complete-score horizon | Linux full decision p50/p95/p99 |
|---|---|---:|---:|---:|
| K4 | WAIT/WAIT10 first, then timed waits, full coarse scan, top-8 refinement; four GIL threads | 160 | 160 | 114.6/187.9/193.3 ms |
| K4h | Same; recompute all three styles at 160 for retained plays | 80 | 160 | 115.7/183.3/193.1 ms |

Both cells use a 200 ms full-decision wall deadline with an 8 ms return reserve. The timer includes public observation, policy fallback sampling, belief, candidate generation, reconstruction, scoring, reduction and submission. Only scores complete before the 192 ms cutoff are eligible. WAIT and WAIT10 share their exact score. Epsilon ties retain original candidate order. The optional X ordering/proposal hooks stay empty for E4's K comparator cells.

The K study uses one sampled public hypothetical root, four scorer workers and five physical cores per game. The existing live E4 package has four sampled belief roots. **A v2 implementation must retain its four-root belief model and use a global pool of four scorer workers.** Do not nest four candidate workers inside each of four root workers. A candidate is eligible only after every required style/root contribution is complete before the common cutoff. Preserve the admitted reduction order across styles and belief roots. The WAIT-first policy must complete the shared WAIT score across the full belief-root set before starting plays. Native tick cancellation and private root ownership are required.

## Required Mac qualification

1. After Sam authorizes a specific future session, build a new generic arm64 GIL-release binary with the required W/tick-cancellation methods. Pin combat source, compiler, feature flags, Python ABI, templates, configuration, adapter and binary. The Linux binary is SHA `44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2`; it is a provenance reference only. No Linux/v3 binary is a Mac build.
2. Reproduce frozen screen8 no-deadline actions and scores for K4 across one/four workers on fixed train inputs. Reproduce all per-root contributions, retained score masks, final reduction and RNG/root immutability. Report K4h agreement and regret descriptively. Repeat injected-clock cases for zero budget, exact-cutoff exclusion, partial style/root work, WAIT10 aliasing and late worker completion.
3. Measure the complete four-root decision pipeline under the actual perception/emulator load. Include packet construction and all roots in the timer. Record cold and warm p50/p95/p99, cutoff frequency, fallback frequency, complete-play admission and actual >200 ms calls. Linux K4/K4h fallback is 0.75%/0.72%, with >200 ms fractions 0.48%/0.45%; neither rate is zero or a Mac guarantee.
4. Repeat the existing package's loaded native/perception measurement scope and preserve formal E4's separate real-gRPC, frame-to-submission, FPS/gap, command acceptance and P4 gates. A loaded replay receipt does not replace the eight-match integration gate.

The existing production fallback is WAIT; K sampled the sealed v1 policy at T=1 and used it only when no complete score was available. The future v2 configuration must explicitly declare the fallback behavior and qualify the real public-history v1 adapter if that fallback is adopted. No live fallback or wait-prior change is authorized by this note.

K1's one-core cutoff left legal plays but no complete play score in 85.80% of decisions. Merely completing waits first does not solve one-core throughput. Student ordering and extra refinement proposals must be evaluated against the declared K1 comparator and an absolute v1/unlimited anchor; a win against weak K1 alone is insufficient evidence of live suitability.

The companion [L2-v4 amendment draft](L2-V4-AMENDMENT-DRAFT.md) records the proposed configuration and remaining gates. Any confirmatory preregistration, formal amendment, Mac session and live deployment belong to the coordinator/owners' later authorization; none was performed by K.
