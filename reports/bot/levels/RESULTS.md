# Level-aware search pilot: interim evidence (exploration)

2026-10-16, resumed by Sol high. [Progress and audit](PROGRESS.md), [design](DESIGN.md).
**No primary pilot bank drawn or A/B outcomes collected.** Mandatory remaining gates are being completed.
BOT LEAD accepted the reversible serial design and fixed supported-card scope before outcomes.

## Verified evidence

- RoyaleSim mixed-level reset: level-6 towers have 3312/2030 HP; Musketeer at L4/7/11 has 375/496/721 HP.
  Original job log `rsim-probe-01.txt`, SHA256 `287e3d23b993713dd29ab81ac5a19274950ec1033a55c1ba5bb15718d0a2df95`.
- Harness DEV base 1: four A games, repeated twice. All four command hashes, own logs and tower HP match;
  eight wins, zero errors/rejected deployments/search failures/translator diagnostics. First run 96.364 CPU
  s/game and 98.576 wall s/game; repeat 97.321 CPU s/game and 99.505 wall s/game. Four original unit tests passed.
  [Receipt](receipts/harness-dev-audit.json). This is runner determinism evidence, not level-aware strength.
- Fresh pinned-runtime mapping: **121/121** cached L11 exports match the native JSON. The initial raw-Python
  comparison was 3/121 because disk JSON changes coordinate tuples to lists. No export stats were changed.
  [Executed schema/tower receipt](receipts/gates-schema-towers-r2.txt), SHA256
  `cd30432de666b2e58929f59702c358b630298f36bb7c93127038b93a31b04645`.
- Tower checks: **13/13 pass** — eight HP/damage curve checks at L10/12 and five L4–8 HP checks against RoyaleSim.
  The earlier Archers catalogue alias failure is preserved in [the failed receipt](receipts/gates-towers-r1.txt).
- Two regression tests pass: cached tuple/list representation versus real damage differences, and tower-shot
  HP preservation. [Receipt](receipts/pytest-configs-r2.txt), SHA256
  `615346574e154b3beff92a0c3300cc216b1d715cbac6441c7dbf923797c8c68f`.
- Existing exports at L4/5/6/7/9 contain 118 cards and three explicit errors: Clone, Earthquake, Tornado.
  L11 contains 121 cards, zero errors. All original export logs are preserved under receipts.

## Fixed scope and interpretation

No selected true-deck projection is lost (0/54). The belief catalog restriction removes 425/2925 decks,
15,371/69,380 frequency weight = **22.15479965%**, identically for every experimental arm and policy controller.
The original projection catalog stays immutable; selected projection equality is asserted before bank creation.
[Scope audit](receipts/scope-audit-r1.json), SHA256
`c7f2c5beac6c67da79ddb4295900978b6ae6f41af40d8dbe5fb841005ef8334d`.
This is a conditional-population physics pilot, not literal current-live-prior equivalence. Missing playable or
identified body exports fail closed. There are no outcome-dependent exclusions or silent L11 substitutions.

A uses L11 roots/config/native; B0 uses the existing root-only scaler; B uses exact own levels, a fixed fair
opponent estimate, tower curves and per-seat rollout templates. B's crown metadata changes both leaf evaluation
and scripted crown spell lethality/Lightning ordering. Identical-state learned features remain equal at that
layer; the complete public view is not claimed invariant. [Bounded source diagnostic](receipts/leaf-diagnostic-astra-r1.md).
The pilot is serial; it makes no pooled LIVE integration or immediate promotion claim.

## Still required

- Forced all-L11 A/B command parity, both seats and controllers, with nonzero B root execution.
- Exact observation-to-root body/shot/carrier/child fixtures; mixed-seat deploy and Fireball impact checks.
- Real raw-fc worker transport with explicit profile A→B→A content changes/reuse, plus snapshot parity.
- Fair-information roots and decisions under identical public states and different hidden true levels, both seats.
- Final reviewed launcher, full immutable provenance before resume, complete/error-free outcome acceptance.
- Original deferred probes on 03: first admission timed out without running; one bounded retry is queued.

s27-m02 is preserved for a later offline diagnostic, not a causal conclusion. No account/emulator actions,
frozen-runtime edits, pin/model changes or LIVE deployment occurred. Rollback selects standard A outside the
experimental factory, preserving all original catalogs and receipts.
