# Public-v4 runner update

The development runner now opts into `public_reference_builder(..., public_contract_version=4)`. Its structural check requires both entity-level arrays and both five-slot own-hand/next-card level arrays, then validates shapes, dtypes and value/confidence consistency. Explicit unknown level 0 with confidence 0 is valid; all-known telemetry is not a schema requirement.

Every decision records level coverage by owner. Result receipts aggregate observed/visible counts separately for bodies, towers, the four own-hand slots and the next-card slot. These are observation opportunities across decisions, not independent entities or families. Native coverage counts confidence above zero; the packet retains the actual confidence value rather than converting it into certainty.

`public_contract_valid` now describes structural v4 validity. `public_calibration_established` is a separate false field until measurement evidence establishes calibration. Acceptance-compatible branch emission requires both. Structurally valid unknown channels therefore do not manufacture an acceptance pass. No nominal level-11 values are filled into missing native own-card channels.

The offline archived-root check in `public-v4-projection-check.json` verifies both perspectives at tick 90 with valid structures and explicit unknown own levels. It does not execute a native game or establish source calibration.

Earlier plans and the completed scalar repetition receipts retain their original source hashes and semantics. They were not rewritten. The new source changes invalidate their execution pins; prepare a new named plan after source stabilization before any further run. The previous two-game scalar result remains legitimate evidence about its earlier pinned execution only.

The next capture/exposure implementation boundary is documented in [v2-capture-ownership-next.md](v2-capture-ownership-next.md). No new ownership framework or native collection was launched in this update.

Validation completed: 39 focused readiness/controller tests passed, including structural acceptance of explicit unknown levels, rejection of fabricated nonzero levels with zero confidence, legacy/v4 scalar execution, and independent measurement-count reporting. Ruff passed, and `readiness_execution.py` passed targeted mypy. The native-contract agent independently validated its adapter changes; this runner update did not contact a native process.
