# Hog 2.6 phase-balanced structured ranker MPS gate

Status: **rejected for training; CPU required**.

The current 458,417-parameter production-shaped structured action-value head was
tested on 20 newly collected phase-balanced game shards. Ten games (87 roots)
formed the train canary and ten disjoint games (86 roots) formed validation.
Those source shards were later rejected for an inconsistent convenience
`best_actions` field. The MPS result remains applicable because this fitter's
loss consumes the intact candidate outcome/crown/damage arrays and never reads
`best_actions`; no rejected model or corpus is promoted by this diagnostic.
The exact NPZ SHA-256 values were:

- train: `f5d3b028020e98b326d7d00e95137a43d12c15317d2a40b7ebf206037e686658`
- validation: `ae86abb87b51686705616dc81a9399aabb9dbd6b6d2e575a140433f855dc5405`

At batch size 96, the 87-root train canary used one optimizer step per epoch and
appeared finite. At batch size 32, the third minibatch reproduced the historical
MPS masked-attention failure: first-epoch mean training loss became `NaN`, all
reported pairwise accuracies collapsed to zero, and the old fitter wrote a
corrupted checkpoint/report (`0b890b308e7e1439f93b86f9b50362f1fa8d20141ae9657846138cfbbb8cc74c`).
This proves that a one-batch MPS smoke is insufficient.

The fitter now rejects non-finite loss, total gradient norm, individual
gradients, and parameters before publication. Repeating the exact batch-32
canary exits nonzero at gradient clipping with no checkpoint or report written;
the captured failure log SHA-256 is
`a6b4902d84a8ba902e81474e20924acf4b9ee169c3e96ed24c68fd3bbb08a3e1`.
The matched CPU batch-32 control completed with finite first-epoch loss
`0.6953206062316895`; its report SHA-256 is
`2b7e21450be006271335239396d5eb9ed48d79b1236b0de877bf8e4cacf21787`.
The frozen three-seed runner now refuses non-CPU devices. This is specific to
the auxiliary Transformer action ranker; it does not revoke independently
verified MPS support for the rewritten battle gym.
