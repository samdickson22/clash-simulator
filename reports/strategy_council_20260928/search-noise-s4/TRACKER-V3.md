# Tracker v3: development results

**N97 development target met:** among 12,174 validation decisions, 2,511 (20.63%) have hand mass ≥90%; 91.52% of these hands are correct. The same-trace public-derived reference resolves 21.36%, so T3 reaches 96.6% of its rate. This exceeds the ≥85% conditional-accuracy goal and is comparable to the S3 ~16% reference rate on a different population. No tracker-v3 strength confirmation was run.

N90 and N64 remain uninformative at the ≥90% threshold: N90 resolves only one validation decision; N64 resolves none. Their sparse/absent high-confidence samples cannot establish calibration.

## Matched dev validation

56 fresh script-v-script worlds, both observer seats, identical N97/N90/N64 public traces. Indices 0–27 are calibration/development; 28–55 validation. The v2 model version was frozen before any calibration-output inspection and no model parameter changed after that inspection. Final validation was inspected only after all 56 complete replay receipts and four successful supervisors existed. This is development validation, not strength confirmation. Decisions sample tick modulo 20 = 10, following S2/S3.

| Event level | Tracker | Resolved hand ≥90% | Accuracy when resolved | Elixir MAE | 90% coverage | Width |
|---|---|---:|---:|---:|---:|---:|
| N97 | T3 | 20.626% | 91.52% (2511 samples) | 0.649 | 90.00% | 2.600 |
| N97 | T2 | 2.062% | 49.40% (251 samples) | 0.649 | 90.00% | 2.600 |
| N97 | ELT | 8.461% | 76.99% (1030 samples) | 1.509 | 73.05% | 3.428 |
| N97 | R-derived | 21.357% | 100.00% (2600 samples) | 0.000 | 100.00% | 0.000 |
| N90 | T3 | 0.008% | 100.00% (1 samples) | 0.763 | 88.96% | 2.678 |
| N90 | T2 | 0.033% | 0.00% (4 samples) | 0.763 | 88.96% | 2.678 |
| N90 | ELT | 1.577% | 61.46% (192 samples) | 4.126 | 34.41% | 4.930 |
| N90 | R-derived | 21.357% | 100.00% (2600 samples) | 0.000 | 100.00% | 0.000 |
| N64 | T3 | 0.000% | n/a | 0.916 | 90.73% | 4.134 |
| N64 | T2 | 0.000% | n/a | 0.916 | 90.73% | 4.134 |
| N64 | ELT | 0.000% | n/a | 7.186 | 3.92% | 2.439 |
| N64 | R-derived | 21.357% | 100.00% (2600 samples) | 0.000 | 100.00% | 0.000 |

T3 and T2 have identical resource outputs on these traces. T3 uses the unchanged T2 integer resource lattice and S3 radii (N97 0.0682; N90 0.1104; N64 0.8909). ELT is unchanged with the S2 event-confidence/timestamp adapter scaled to each event level.

## Reliability curves (validation)

Bins describe reported mass of the most likely resolved hand; ambiguous branch hands contribute zero mass. Entries are mean claimed mass → observed accuracy (sample count). These are descriptive correlated decisions, not independent Bernoulli trials. Full calibration and validation curves for every tracker are in dev-summary-v2.json.

### N97

| Mass bin | T3 claim → accuracy (n) | T2 claim → accuracy (n) | ELT claim → accuracy (n) |
|---|---|---|---|
| 0–25% | 8.8% → 20.3% (723) | 3.3% → 1.2% (8830) | 3.5% → 3.2% (7456) |
| 25–50% | 39.3% → 42.5% (1758) | 37.0% → 6.0% (1344) | 34.3% → 6.0% (1698) |
| 50–70% | 61.7% → 69.6% (1983) | 59.5% → 15.5% (753) | 60.5% → 20.5% (443) |
| 70–80% | 75.3% → 85.0% (1542) | 76.3% → 19.7% (346) | 76.8% → 49.4% (605) |
| 80–90% | 85.4% → 90.3% (3657) | 85.4% → 27.4% (650) | 85.1% → 64.4% (942) |
| 90–95% | 92.2% → 91.0% (2325) | 92.0% → 48.8% (246) | 92.3% → 66.8% (382) |
| 95–99% | 95.6% → 97.8% (186) | 95.6% → 80.0% (5) | 97.2% → 82.9% (644) |
| 99–100% | — | — | 99.3% → 100.0% (4) |
### N90

| Mass bin | T3 claim → accuracy (n) | T2 claim → accuracy (n) | ELT claim → accuracy (n) |
|---|---|---|---|
| 0–25% | 14.2% → 22.3% (1922) | 5.3% → 0.6% (8884) | 6.7% → 4.6% (7447) |
| 25–50% | 38.3% → 46.0% (4286) | 36.0% → 3.7% (2261) | 36.9% → 14.4% (2317) |
| 50–70% | 60.1% → 76.8% (3805) | 59.2% → 7.2% (828) | 58.9% → 32.3% (1350) |
| 70–80% | 74.8% → 84.6% (1653) | 75.5% → 26.1% (161) | 74.7% → 40.8% (395) |
| 80–90% | 82.6% → 86.6% (507) | 83.2% → 0.0% (36) | 85.2% → 44.4% (473) |
| 90–95% | 91.4% → 100.0% (1) | 90.6% → 0.0% (4) | 92.2% → 60.9% (184) |
| 95–99% | — | — | 95.3% → 75.0% (8) |
| 99–100% | — | — | — |
### N64

| Mass bin | T3 claim → accuracy (n) | T2 claim → accuracy (n) | ELT claim → accuracy (n) |
|---|---|---|---|
| 0–25% | 12.9% → 30.3% (8849) | 3.0% → 0.3% (12088) | 8.5% → 1.3% (10069) |
| 25–50% | 32.7% → 54.5% (3212) | 30.3% → 0.0% (86) | 33.3% → 6.3% (2027) |
| 50–70% | 55.3% → 70.8% (113) | — | 56.1% → 21.8% (78) |
| 70–80% | — | — | — |
| 80–90% | — | — | — |
| 90–95% | — | — | — |
| 95–99% | — | — | — |
| 99–100% | — | — | — |

## Inference and fairness

The cycle filter maintains a 64-state, deck-free public queue mixture constrained by compatible train-prior decks. Accepted/rejected/confused event branches, latent missed plays in every event gap, and a persistent restart component let subsequent legal reveals recover cycle state. Fixed-lag T2 event/body fusion supplies corroboration and possible missed births. The board input contains only public token/position triples; event IDs are deduplication keys. No hidden deck, hand, actual resource, entity ID or engine RNG enters inference.

Hand mass conservatively sums fully resolved branch/deck hands. Unresolved inner queue orders contribute zero, as in the ELT comparison diagnostic. Cached deck-presence marginals avoid a quadratic prior scan. A missed-play hazard reduces hand confidence between observed events. No fitted confidence multiplier or validation-selected threshold was applied.

Approximation limits: resource and cycle beliefs remain factored; only the eight heaviest branches receive explicit latent-play expansion; pruned mass enters a broad restart state; public-body evidence can misassociate spawns; and the action-policy likelihood is approximate. Passing the requested ≥90%-mass conditional-accuracy target does not mean every probability bin is perfectly calibrated. Below 90%, T3 is often conservative.

## Verification and retained evidence

All 24 original P16 recorded games pass, 23,058 observations and zero elixir/hand/cycle/next errors. Perfect q=1 retains the unchanged exact ELT path; subsequent changes affect only the noisy path. The final 22-test suite passes, including exact phase/cap behavior, hidden-card/RNG invariance, bit-identical T2/T3 resource distributions, synthetic recovery, conservative mass bounds and cached-prior factorization.

Development v1 was interrupted for performance, with only verified dev child PIDs signaled; supervisors reaped CPU and preserved failure receipts. Original code is retained in dev-versions/v1/. V2 inference hashes are in dev-code-freeze-v2.json; the later dev replay wrapper adds only per-index locking and immutable receipt reuse. DEV-LOG.md records failed development tests and corrections. None affected frozen S4 confirmation.

The optional exact dev reference was recomputed separately at the correct pre-action boundary (public event tick < observation tick), with zero resource/known-hand errors across all 56 traces. Original replay receipts remain unchanged; dev_summary.py substitutes the audited control-only receipts. T3/T2/ELT inputs and metrics were unaffected.

Raw traces and per-decision replay receipts remain on 04/08. Only source, small evidence and summaries are mirrored to 05. No engine/gamedata edits, confirmation tuning, or commits.
