# Search noise results

All 1,664 preregistered terminal games completed. Simulator strength gate: FAIL.

The 95% intervals below bootstrap paired matchup means, 10,000 resamples. Each primary cell contains 128 games and 64 paired matchups. No completed confirmation outcome was excluded.

| Variant | Versus clean A | Versus C56 scripts |
| --- | --- | --- |
| A | 49.2% [47.7, 50.0] | 86.7% [80.5, 92.2] |
| B | 35.9% [30.5, 41.4] | 50.0% [39.8, 60.2] |
| C | 32.0% [25.8, 37.5] | 43.0% [32.0, 53.9] |
| D | 35.9% [30.5, 41.4] | 47.7% [36.7, 59.4] |

A has clean inputs. B has full noise. C replaces derived opponent state with a broad train-deck/uniform-elixir prior. D raises correct-event recall and precision to 90% with the frozen inference filter unchanged.

## Conditional strength cost by source

Repair effects are script score(repair) minus score(B), paired on the same worlds. Positive values mean that source costs strength in the full-noise setting. Effects interact and should not be added.

| Source repaired | Score with repair | Gain over B |
| --- | --- | --- |
| events | 66.4% [56.2, 75.8] | +16.4 pp [+7.8, +25.0] |
| hp | 49.2% [38.3, 60.2] | -0.8 pp [-9.4, +7.8] |
| hud | 47.7% [36.7, 58.6] | -2.3 pp [-11.7, +7.0] |
| latency | 47.7% [37.5, 57.8] | -2.3 pp [-10.2, +5.5] |
| board | 45.3% [35.2, 56.2] | -4.7 pp [-14.1, +4.7] |

Broad opponent prior C minus B: -7.0 pp [-14.1, +0.0] against scripts, -3.9 pp [-10.2, +2.3] head-to-head.
90% event gate D minus B: -2.3 pp [-10.9, +5.5] against scripts, +0.0 pp [-5.5, +5.5] head-to-head.

Event placement has zero direct effect in this adapter because neither the current opponent filter nor the public-board reconstruction consumes event coordinates. The coordinate invariance test passed. This does not establish that placement is unimportant to an actual vision tracker.

## Hog 2.6

| Variant | Versus A | Versus scripts |
| --- | --- | --- |
| A | 50.0% [50.0, 50.0] | 70.0% [50.0, 90.0] |
| B | 35.0% [20.0, 50.0] | 0.0% [0.0, 0.0] |
| C | 30.0% [15.0, 45.0] | 0.0% [0.0, 0.0] |
| D | 20.0% [5.0, 35.0] | 5.0% [0.0, 15.0] |

All seven family tables are in result.json. Family intervals are descriptive; Hog 2.6 has 20 games per condition and stratum.

## Noise fidelity and inference

Input corruption used 10-FPS packets, entity misses and coordinate jitter/tails, phantom bodies, 66.06% HP coverage with 0.0498 MAE on readable bars, 0.31% hand-slot errors and 2.92% displayed-elixir errors. Missing HP uses a fixed 50% estimate. The point-valued C56 script API requires usable confidence values. No simulator state was corrupted.

Event rates below are the injected channel counts, not a post-hoc rematching of insertions. Terminally censored events can remain pending. Derived-state diagnostics use scoring-only truth after decisions.

| Variant | Event recall | Event precision | All-event placement | Derived elixir MAE | 90% interval coverage / width |
| --- | --- | --- | --- | --- | --- |
| B | 0.646 | 0.674 | 0.583 | 1.545 | 0.888 / 7.822 |
| C | 0.647 | 0.672 | 0.583 | 3.499 | 0.829 / 9.000 |
| D | 0.897 | 0.900 | 0.807 | 0.747 | 0.993 / 6.596 |

B and D use the frozen v3 particle filter with validation-only calibration. C ignores events in its broad prior. The exact clean tracker cannot safely ingest contradictory noisy histories, so the event-source repair includes replacing this robust inference path with exact derivation. D changes detections only; it does not recalibrate the filter.

The model extrapolates P16 body statistics to C56, applies pooled both-side event metrics to opponents, uses independent per-frame body/HP/HUD errors, and inserts false events proportionally to true plays. The eight proxy card confusions are timing/spatial associations, not manually labelled classifications. The v3 posterior does not model champion resource events. These assumptions limit generalization.

Every controller polls at 100 ms and nominally searches every 200 ms. This shared cadence differs from historical Stage 5b. B/C/D add 150-ms image availability and max(100 ms, measured search time) command delay, quantized to engine ticks. These are simulated latency assumptions, not a concurrent live capture/search measurement.

## Recommendation

Current perception does not pass the preregistered simulator strength gate. Improve perception and its uncertainty handling before treating the search player as ready for the closed loop. A guarded diagnostic loop remains useful, but this experiment does not justify a strength-readiness claim.
The largest point-estimated repair is events, +16.4 pp [+7.8, +25.0]. Repair intervals are marginal; overlapping intervals do not establish a unique ranking.

## Verification and provenance

Input-copy purity, hidden-state poisoning, scoring-only diagnostics, coordinate invariance and Monte Carlo noise-rate tests passed. Clean-event games assert derived elixir and determined-hand parity. 2,003,097 exact checks passed.
Candidate decisions: 3,652,971; maximum wall time 850.8 ms; >250-ms decisions 124; truncated searches 26242; fallback searches 145; rejected candidate commands 82789. These timings do not certify a hard real-time deadline.
Manifest SHA-256: b4ec3f8d6ab47949f1db88bdda9a44bfdfe18f93602f75fc55b966c9aa1bf7eb. Receipt aggregate SHA-256: 8a7fb4cf31f558dd6cff350a649ab56543f890ac831e08ca91a0c0b10977e00d.
Seed audit, PREREG.md, source-copies.json, evaluation-manifest.json, tests-r3.log and all atomic confirmation receipts are retained. Three owned nice-10 workers used the required detach.sh launcher. The Python engine, gamedata, engine-rs and protected report directories were not edited.
