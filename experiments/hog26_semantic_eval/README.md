This directory reviews all eight completed semantic residual fits, then freezes
inference and paired comparisons on the previously opened 384-game diagnostic.
It does not train, select epochs, calibrate, or authorize acceptance.

Before diagnostic access, the fitting authority check requires the exact 30-file
inventory, unchanged model/data/source pins, matching memory readiness, valid
prediction arrays, and exact reuse of the globals WDL probabilities and priors.
The fitting review retains all 60 slices in both distributions, plus margin point
differences against the numeric residual model and tree.

The evaluator then freezes every checkpoint and reference. Each model is evaluated
on 288 fresh games from seen families and 96 from excluded families. Paired cluster
bootstrap intervals compare margin errors with the matching numeric residual
seed/fold and the matching tree fold. The probability arrays passed to the paired
statistic are identical; only margin differences are interpreted. Every paired
point must reproduce the difference between the published MAEs.

After all eight evaluations complete, `review_diagnostic.py` verifies the exact
18-file inventory, coverage, WDL identity and presence of both paired comparisons.
It preserves all slice reports. Late coverage remains inadequate for acceptance,
and repeated use of this opened diagnostic cannot turn it into a final test.

Use the shared Python environment, with this directory first in `PYTHONPATH`,
followed by `hog26_semantic_margin`, `hog26_public_semantics`,
`hog26_residual_margin`, `hog26_scaling_review`, `hog26_scaling_eval`,
`hog26_seed_transfer`, `hog26_scaling_fit`, `hog26_data_scaling`,
`hog26_scalar_pilot`, `src` and the workspace root.

Run `review_semantic.py --output` with a new fitting review path, then
`evaluate_semantic.py --mode pin --fitting-review ... --pin ...`. Once the pin is
published, preserve all Python in this directory. The supervisor runs inference
under the shared lock and 18 GiB guard. Run `review_diagnostic.py` after completion.
