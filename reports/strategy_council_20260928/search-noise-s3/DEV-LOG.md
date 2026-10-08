# Development log

- v1: seven unit tests pass; original 24 recorded P16 games pass exactness checks against srp-public and deck-free D1 at every observation.
- Initial two trace generation attempts failed at final serialization because empty static unit groups were not handled by the body/card map. No trace/terminal receipt was written. Logs and exit receipts retained as s3-dev-generate-{0,1}-v1. Corrected static template traversal before further development. v2 generation uses unchanged fresh seeds. No confirmation exists.

- v1 fresh dev replay: raw 90% intervals undercovered due to timing offsets; calibration radius about 0.15–0.19 restored coverage near 90% at widths 4–5 versus legacy 6–8. N97/N90 MAE was worse than legacy. Public board diagnostics showed many unmatched births per actual event. v2 adds four-tick execution-time quadrature, retains 120-tick public event association history, groups multi-body births over 40 ticks, and uses Bayes miss-versus-board-FP odds for unmatched births. These changes precede all confirmation and use development only. v1 source and metrics retained.

- v2: fresh dev shows affordability rejection still shifts resource mass upward and worsens MAE despite improved hand concentration. v3 explicitly repairs insufficient-resource branches to the public minimum affordable cost before subtracting it; accept/reject prior mass remains the measured event confidence. This is a robust resynchronization update, not an exact Bayesian action-policy model. No action-policy fit or game outcomes are used.
