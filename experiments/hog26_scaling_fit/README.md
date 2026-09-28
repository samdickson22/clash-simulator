# Scaling-fit preparation

This directory is outside the active collection source inventory. Preparation
here must not change either completed experiment or the scaling collector.

scaling_training.py preserves every original fitting/prediction function body.
Its only behavioral dependency change is the verified compact batch builder.
Synthetic tests confirm exact parameter equality after multiple updates for
both globals and entity/history. Model architecture, loss, optimizer, seeds,
epoch budget and full-game recurrence remain unchanged.

The installed sklearn1.7.2 histogram booster requires float64 input. Creating
all-game float32 features, indexing fitting rows, then converting to float64
would retain several large arrays. tree_storage.py instead builds only the
ordered fitting-game rows directly into one float64 matrix. Predictions use
one game at a time. Tests match the original feature values/order exactly and
prove excluded games are not read to build fitting features. A10GiB matrix
limit fails before allocation; it does not remove rows or change the model.

run_scaling_comparison.py now provides the1536-game comparison entry point.
It requires a passed readiness record matching its implementation, collection
plan, full combined data audit and memory verification. It preserves original
metrics/folds/seeds and refuses missing memory readiness before corpus access.
Remaining work: actual full-size memory checks, complete combined-data audit,
readiness publication and supervised execution. No fitting is authorized yet.
