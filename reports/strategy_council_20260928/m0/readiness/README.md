# M0 readiness implementation

The separate `training-readiness-v2` evaluator and public candidate interface are implemented. The saved protocol is a draft, with no families, source freeze, coverage receipt or measurement floors. It cannot pass admission. No native collection, gameplay fitting, oracle search, or paid compute was launched for this work.

## Implemented

- `src/clasher/rl/training_readiness_v2.py`: strict Pydantic records, public candidate generation, development repetition validation, prospective protocol validation, branch enumeration and independent decision evaluation.
- `src/clasher/rl/public_scripted_opponent.py`: `ranked_plays(packet)` exposes legal immediate plays ordered by descending score, then action ID. The ordinary `decide` path retains per-slot maxima and the existing recommendation behavior.
- `scripts/training_readiness_v2.py`: create a draft from the exact approved strategy bytes, enumerate branch declarations, or evaluate supplied JSONL receipts. Output files use exclusive creation. The CLI does not freeze protocols or launch branches.
- `tests/test_training_readiness_v2.py`: synthetic accounting checks, explicitly distinct from native evidence.

Candidates have four roles: highest-ranked immediate play, ordinary five-tick wait, best different-card play, and best first-card placement at least two tiles away. Root eligibility requires two affordable distinct cards and that displaced placement. Ineligible roots raise; the collector must retain failures rather than silently replacing roots. Original controller recommendations are preserved separately in family records.

The evaluator requires all 32 families and all four declared style conditions per candidate and engine. It validates duplicate/missing/undeclared branches and root, public-packet, protocol and action provenance. Families must have distinct independence identities and roots, balanced seats, and fresh acceptance roles to freeze. HP thresholds use the root owner's full starting Crown HP, currently explicitly scoped to level 11 (10,928 HP).

Non-wait coverage never filters failure accounting. Scalar ties are pessimistic; one reference-best comparator is selected by fixed role order and retained across four conditions. Reports expose class counts, insufficient class exposure, regrets, ties, sign patterns, above-floor events, and automatic repeated-harm blocks. Mechanism review is required for above-floor events and can add blocks; it cannot waive automatic ones.

Noise floors require at least two receipt-distinct observations per identical execution identity in each engine. They use maximum same-engine repeat differences and separately declared rounding allowances. Changed execution identities cannot masquerade as repetitions. WDL spacing is not a noise allowance. Material non-reproducibility blocks freezing. The stored records do not authenticate artifacts by themselves; the eventual collector must verify actual receipt content and source pins.

## Validation

- Focused tests: `tests/test_training_readiness_v2.py` and `tests/test_public_scripted_opponent.py`.
- Readiness module: targeted mypy with imports followed silently.
- New module, script and tests: Ruff checks and formatting.
- Ephemeral behavioral comparison: 120 decisions matched the original HEAD controller exactly, including action ID, score and reason, across three styles, both seats, varied hands/elixir and visible threats. No historical source was replaced to run this check.

## Remaining before freeze

1. Finish and stabilize the other M0 source changes, then pin the actual source and configurations.
2. Define and inspect the independent 32-family generator across tactical situations and the 16-card scope. The implemented helper generates candidate roles from a supplied public root; it does not manufacture or collect the root bank.
3. Run the scalar development coverage study with the four declared continuation conditions.
4. Run actual identical-execution repetitions in both engines, retain artifact receipts and document serialization/rounding allowances. This change contains no invented repetition data.
5. Inspect feasibility/noise, freeze all declarations prospectively, then collect a fresh Tier A attempt with verified transport/public serialization and terminal handling. The branch planner is not a native execution runner.

The optional teacher order is explicit: Tier A, admitted search scope, 64/256-game strength checks, fresh oracle-candidate reference checks, then labels. Historical v7 evaluators, runner, ledgers and source/evidence files were not edited by this work.

## Development execution follow-up

A separate development runner and concrete commands are now available in [execution-workflow.md](execution-workflow.md). The coordinator completed two identical scalar executions on an existing opened-development root; their terminal score and normalized margin matched exactly. [scalar-study-observation.json](scalar-study-observation.json) binds both result hashes. The native counterpart is unrun, and missing own-hand/next-card level telemetry keeps these branches explicitly ineligible for full-contract acceptance. The new runner rejects fresh acceptance until the v2 capture/exposure ownership adapter is implemented.

The subsequent [public-v4 runner update](public-v4-runner-update.md) distinguishes valid explicit unknown levels from measured channel coverage. Current development projection structures validate even with own levels unknown; calibration remains separately unestablished. Prior pinned receipts remain unchanged. See [v2-capture-ownership-next.md](v2-capture-ownership-next.md) for the bounded next adapter connecting prospective root declarations to capture and branch claims.
