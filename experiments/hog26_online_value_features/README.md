# One-decision public value features

`PublicFeatureState` reproduces the existing814-column value input from one audited public frame at a time. It computes current numeric/body summaries through the frozen functions and reconstructs lags1,5,20 from only20 prior masked public-global vectors and their confidences.

The encoder accepts the exact nine public fields. It uses four current hand slots; an optional fifth next-card slot is ignored as in the cache builder. Metadata and labels are rejected. A fresh state requires the game-reset clock, later calls require increasing decision clocks, and callers must supply the complete decision stream at the audited recording cadence. Invalid inputs do not advance history. Returned arrays and cloned histories are independent; the compiled layout/body table are shared immutable resources.

Four tests cover stream/batch byte parity, fractional and missing confidence, bounded history, reset, clone/input ownership, unprimed or invalid input refusal, and ignored next-card data. This is an unwired encoder prototype: it changes neither the visibility mask nor a live policy.

The separate audit pins16 evenly spaced complete training games before reading their public arrays. It compares every streamed frame with the audited feature cache, checks an independently cloned continuation and a divergent clone, and retains source/game hashes. It never loads outcome arrays for encoding or scoring.

Run `supervise.py --mode pin` to freeze all five Python files. Run `--mode audit` only after the active comparison and boundary audit release the shared lease. All outputs are exclusive and preserved. Encoding parity does not establish model accuracy, calibration, simulator acceptance or counterfactual ranking.
