# SOL independent core re-review r6

**Verdict: APPROVE.** Finding 21 is resolved, and the runtime-binding objections that kept findings 4, 8, 9, 16 and 19 partial are closed. No blocking or MAJOR issue remains in the reviewed core scope. No new code finding or false rejection was found. Existing finding 11 has minor final-manifest housekeeping outstanding; the mechanical proof must be refreshed and clean before freeze.

Reviewed `/mpac/sdicks02/repos/clasher-k4s-prep`, HEAD `962ecce2cf05223aada69746f2758bcf573c82f6` plus working-tree bytes. Read core reviews and author responses r1–r5. Governing preregistration: `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md`, SHA-256 `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a`. Contract: `reports/explore/k4s-confirm/K4S-SPEC.md`, SHA-256 `e80652d4859504eaf6a9256a3b3672a247a3f1993160ab17378587e7cdd93e53`. Locations below are relative to `reports/explore/k4s-confirm/`.

Independent review of the author's implementation. No SSH, network, commit/push, real game outcome data, or anything under `reports/explore/x4s2/receipts` was accessed. This review is the only file written; synthetic test writes were intercepted in memory. No builder, native game, qualification job or live STOP test was run. Mac, END, verifier and inherited OP implementations were not substantively reviewed. The allowed manifest verifier mechanically checked listed bytes, including excluded files.

## Finding 21: fix verified

`source_binding.snapshot()` now checks every `runtime-pin.json['files']` entry against `job/repo` (`77`), and every `native_source` entry against `job/native-source` (`78–79`). Missing files and changed bytes produce named errors. The existing input declarations remain checked (`68–74`). All errors contribute to `t1_matches_ef4c073a=false` (`80–82`); despite that historical field name, it now represents validity of the full checked snapshot.

It is sufficient to revalidate those source hashes against the unchanged, snapshot-bound pin at each checkpoint. Duplicating every hash in the snapshot is unnecessary: the pin bytes are already included in `inputs`, the new checks read the actual files each time, and any mismatch changes both the validity flag and diagnostics. The two new count fields are supplementary, not the evidence used to accept hashes.

The callers enforce this result:

- **Record:** `source_binding.py:105–108,119` recomputes the snapshot, writes diagnostics and exits 1 if invalid.
- **Final verification:** `105,110–119` recomputes it, requires equality to the start record and current validity, revalidates canonical receipts/game hashes, writes `passed=false` and exits 1 on failure.
- **Assembly:** `make_qualification_receipt.py:48–64` calls the actual snapshot again, compares it with both earlier records and explicitly requires current validity. Shared-source and native-source mutations after verification now write a FAIL receipt and exit 1 (`80–82`).
- **Driver:** `run_qualification.sh:4,10–17` pins, records before the batteries, verifies after games/STOP, then assembles under `set -euo pipefail`. A failed check prevents `QUALIFICATION-FINISHED`.

Independent memory-only controls changed or deleted each of the three originally demonstrated shared dependencies (`reports/explore/e1/policy.py`, `student-source/exit_r3/network.py`, `src/clasher/rl/c56_rollout_planner.py`) and two representative native-source entries (`src/lib.rs`, `Cargo.toml`). Each was tested at record, before final verification, and after verification at assembly: **30/30 rejected**, with the expected named source error, nonzero exit, and diagnostic binding/FAIL receipt. For assembly controls, both current-versus-start and current-versus-end checks also became false. The actual snapshot, receipt verifier, qualification inventory and assembler ran; their acceptance checks were not replaced with passing stubs.

## Per-finding disposition

| Finding | Status | Evidence / limits |
|---|---|---|
| 1 — Guard timestamp comparison | **RESOLVED / RETAINED** | Assembly keeps the timestamp-free projection and frozen guard SHA. A synthetic fresh timestamp passed in the baseline. |
| 2 — Inventory, failure propagation and smoke validation | **RESOLVED / RETAINED** | Checker/health bytes match r5. Canonical receipt validation and launcher test pass this round; prior complete checker/decision tests are retained. |
| 3 — Canonical descriptors and paired decks | **RESOLVED / RETAINED** | Prior resolution retained; schedule/reducer behavior was not rerun in this focused review. |
| 4 — Complete-runner injected equivalence | **RESOLVED** | The accepted bounded full-runner virtual-clock test and explicit one-thread override remain. Finding 21 closes its outstanding exact-runtime provenance objection. Real command equivalence was not rerun. |
| 5 — Rate inference, GC and WAIT indicators | **RESOLVED / RETAINED** | Prior numerical/reducer disposition retained. |
| 6 — OP sensitivity contract | **RESOLVED / RETAINED** | Prior resolution retained; inherited OP implementations were excluded. |
| 7 — Decision and game audit fields | **RESOLVED / RETAINED** | Runner, health and checker identities match r5; charged shared-validator invocation and recorded field semantics remain. |
| 8 — Identity/configuration and placement | **RESOLVED** | Current job pin checks across K4S modes and documented injected/zero overrides remain. Complete source/native/input pin validation now closes the outstanding runtime-identity dependency. |
| 9 — Binding through games/STOP and assembly | **RESOLVED** | Actual source snapshots bracket the driver phases and are rechecked at assembly; shared/native sources are now checked at each checkpoint. Eleven canonical receipts bind 32 synthetic games. |
| 10 — Earned crowns | **RESOLVED / RETAINED** | Prior resolution retained; no outcome data or outcome calculation was used this round. |
| 11 — Manifest completeness/final byte proof | **PARTIAL — MINOR HOUSEKEEPING** | Manifest verifier detects the current stale/unlisted entries below. Refresh after concurrent review streams finish and verify before freeze; builder was not run. |
| 12 — Qualification slots | **RESOLVED / RETAINED** | Actual launcher test confirms the canonical eleven planned slots. |
| 13 — STOP and receipt success propagation | **RESOLVED / RETAINED** | Assembly still requires owned interruption/running evidence and exits 1 after writing FAIL. Live STOP was not run. |
| 14 — Independently expected arm | **RESOLVED / RETAINED** | Filename-derived expected arm and independent cohort/metadata checks remain; checker SHA matches r5. |
| 15 — Driver inventory/game coverage | **RESOLVED** | Actual canonical receipt validator and source verifier accepted exactly eleven receipts/32 outcome-free synthetic game files with matching runtime runner/plan identities. |
| 16 — Historical source-binding boolean at assembly | **RESOLVED** | Actual assembler rechecks source/input identity, start/end links, canonical coverage, current inventory, battery links and artifact hashes. Post-verification shared/native mutations now fail. |
| 17 — Smoke empty/malformed SD1 evidence | **RESOLVED / RETAINED** | Health SHA matches r5; prior smoke tests and valid-path controls retained. |
| 18 — Qualification before freeze | **RESOLVED / RETAINED** | QUALIFICATION.md retains the every-named-host-before-freeze requirement and distinguishes launch rechecks. No host qualification assertion was independently validated. |
| 19 — Current native/model inputs and earlier artifact links | **RESOLVED** | Original r5 input/artifact fixes remain effective, and full runtime-pin source scope now closes their remaining dependency. All nine input and ten artifact mutation controls fail assembly. |
| 20 — Charged aliases and scan nullability | **RESOLVED / RETAINED** | Checker uses the shared outcome-blind validator; checker/health SHA identities match r5. Prior malformed/valid-path tests retained. |
| 21 — Complete runtime pin at snapshot/assembly | **RESOLVED** | Full declared source/native/input checks and 30 independent source mutation/deletion controls described above. |

“Retained” preserves the prior disposition without claiming a fresh test of unchanged or excluded subsystems. Findings 4/8/9/16/19 shared finding 21's single outstanding objection; all five are now closed.

## Independent checks and false-rejection assessment

- An unchanged outcome-free virtual fixture passed actual record, verify and assembly with exit 0, exactly eleven canonical receipts and 32 bound games. It includes job-rebound T1 plan bytes, recursive K4S inventory, declared reference files, all nine immutable inputs, shared/native pin entries, prior inventory/battery proofs and the ten verification artifacts. The aggregate checker receipt was synthetic; the game checker itself and native runtimes were not executed in this fixture.
- Each of the nine immutable inputs was independently altered after verification: assembly wrote FAIL and exited 1. JSON inputs were changed using valid trailing whitespace, preserving parseability and proving byte binding. A mismatching declared SD1 input SHA produced the expected runtime-pin-input error.
- Each of the ten bound artifacts was independently altered after verification while preserving required parsed values: assembly wrote FAIL and exited 1. Earlier battery links and current artifact comparisons remain enforced.
- Ignored K4S `__pycache__` bytes, unrelated job cache files and a job progress marker did not change the snapshot; assembly still passed. Reordering pin mapping entries retained snapshot validity. Changing actual pin-file bytes still requires equality to the earlier snapshot-bound pin.
- No false rejection was found for unchanged valid fixtures. Older snapshots lack the newly added count keys and belong to different source bytes; they are not same-version qualification evidence. Fresh qualification after a source change is already required by the procedure.
- The authored `test_launcher_matches_canonical_tasks()` passed by direct invocation, six scoped Python sources parsed, and `bash -n` passed for the qualification driver and both qualification shells. Python ran with bytecode output disabled, without filesystem test fixtures or cache output.

The virtual source inventory tests the checking rule; it does not independently establish the author's claimed real-job counts of 1709 source entries and 77 native-source entries or any host's qualification result. Native execution, full injected-clock games, host topology, live STOP and excluded review streams remain separately evidenced.

## Mechanical manifest result (existing finding 11)

Latest allowed `PYTHONDONTWRITEBYTECODE=1 python3 reports/explore/k4s-confirm/rebind.py verify`: **exit 1**, inventory **158**, classifications **61 identical / 14 rebound / 15 delta / 65 new**. Core/preparation bookkeeping failures:

- `PROGRESS.md`: SHA changed since manifest.
- `source_binding.py`: SHA changed since manifest (the reviewed r6 fix).
- `reviews/RESPONSE-CORE-r5.md`: present but not in manifest.
- `reviews/SOL-REVIEW-CORE-r5.md`: present but not in manifest.

Separately, verifier-stream bookkeeping staleness detected mechanically:

- `receipts/reducer-verifier-crosscheck.json`: SHA changed since manifest.
- `reviews/SOL-REVIEW-VERIFIER-r2.md`: present but not in manifest.

No Mac, END or `verifier/*` source hash failure was reported at this measurement. Neither verifier-stream file above was substantively read. The first mechanical check lacked the crosscheck-receipt failure; it appeared during concurrent work. These are final-manifest refresh requirements under existing finding 11, not a new runtime-pin validation defect. This review remains outside the worktree and introduces no new manifest entry.

## Reviewed source identities

```text
source_binding.py              568e016377fe63b84c266958d2982f704bda56ed4a12d6259dd7ce089f6116e5
make_qualification_receipt.py   fcdf768c4e2c7ee8c41bdd22dbcf8cc445c99286c33fae05657b0a364d43d790
run_qualification.sh           1d788704af244574ac0acd15f1492baaa9a2e1f3edda05c83b5e3f898df1ea65
qualification_binding.py       48644ca369eb246c4c43aaf64254a27e86a941eb9fc3fd69385113a2387701c0
pin.py                         440e59236f2dcf5fbf7e47fd69859fe0a72c91d8ecd15f93009307b37e13ce07
check_games.py                 83a92547c9f335daaceab56d872cf60700423e294346978cd1c013b484eefd9b
qual_tasks.py                  cc81b3172fc41f0fe1835e0cb9038ee96720998bde65a2836b4caba15657133e
health.py                      5bbe9beb4db6f40e9aab64fd2cf07aa57419e04ddfcbb2dccf4bb6351b51b697
run.py                         78d88a572a8637956492d0f8447569c2307454818bb03356007b9ff9938a5f13
DELTA-MANIFEST.json             d15715bae0b9ad94f16c296842d9b26a7c6da5d89591de4725f925eabdb821b7
```

**New findings: none.** Core code review is APPROVE; complete the existing final-manifest refresh before freeze.
