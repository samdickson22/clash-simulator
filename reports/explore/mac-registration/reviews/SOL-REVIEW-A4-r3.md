# Sol review, TIERS Amendment 4, round 3: whole amendment

Reviewer: gpt-6.1-sol (high). T3 `delegate_task` id `macreg-a4-sol-review-r3`. Requested about 23:06Z; completed by 23:10Z on 2026-10-11.

Input note: the coordinator corrected the ruling's time (23:04Z, COORDINATOR `684195b3`) after this round started. That edit changed only citation text: in the A4 md and json, the `stage_nocopy.py` docstring, the r2 review record and PROGRESS. No code and no rules changed. Sol's review cites the committed 23:04 UTC entry.

## Sol's text (verbatim)

VERDICT: APPROVE_WITH_CONDITIONS

Paths below are relative to `reports/explore/mac-registration/`. "A4.md" means `reports/strategy_council_20260928/live-loop/v4/PREREG-SEARCH-TIERS-AMENDMENT-4-20261011.md`.

8. **RESOLVED: authorization for the staging substitution.**
   - Committed `origin/main:reports/strategy_council_20260928/COORDINATOR.md:2163` explicitly approves the helper. The authoritative entry is 23:04 UTC, commit `684195b3`.
   - A4.md:108–114 and the JSON fields `mac_staging.status` and `ruling_conditions` record that approval and all six conditions.

9. **RESOLVED: Amendment 3 pin description.**
   - A4.md:147 and the JSON `re_pin_analysis` now correctly state that Amendment 3 records `prepare_bundle.py`'s after-SHA `a1c59fa3…`, and that those bytes remain unchanged.
   - I verified that entry in the committed Amendment 3 JSON.

10. **MINOR: inaccurate "every stage" runtime-verification claim.**
    - **Locations:** A4.md:76–79; `student_reference.py:145`; `seal_receipt.py:85`; `run_phase3.sh:37`.
    - **Problem:** the text says every stage checks all 3,785 runtime files, all measurement pins, package placement and the native SHA. That is true of only some stages:
      - selection, assembly, reference computation and the memory check invoke `setup_runtime()` / `verify_runtime()`;
      - the cross-check and the seal invoke only `add_e4v3()`, then validate artifacts and receipt relationships;
      - the frozen converter also lacks the full END-A3 runtime check.
    - **Required fix before adoption:**
      - narrow the wording so it names the stages that actually perform the full verification;
      - distinguish the other stages' pin and receipt checks;
      - regenerate the A4 JSON so its Markdown SHA matches.

      This is a documentation correction. I found no computation regression that would require changes to frozen code.

### The six staging conditions are implemented and recorded

1. **Location, pinning and scope.**
   - `stage_nocopy.py:191–206` rejects placement inside e4v3 or the runtime root, verifies all 18 measurement entries before importing, and checks the imported path.
   - It substitutes only the three fixture destinations at the bundle root; all other destinations use the frozen copy.
   - The helper SHA is `96abd8474d6410d6ba4342889e18d5caed5b455417535d44440d676041f653c7`.
2. **Placement and SHA checks.**
   - `:104–123` uses Darwin `clonefile(2)`, then a hard link, then a copy only when at least 10 GiB is calculated to remain.
   - A partial placement or a SHA mismatch fails closed. The placement tests passed.
3. **Read-only protection.**
   - `:124–137` removes all write bits from both source and destination and records their modes.
   - The hard-link mode assertions passed.
4. **Manifest equivalence.**
   - `tests/test_stage_nocopy.py:159–178` runs the real frozen preparation in Mac mode through both paths.
   - The manifest bytes, the checksum bytes and the bundle file sets match.
5. **Session verification.**
   - `stage_nocopy.py:140–172` requires exactly the three fixture files, read-only modes, receipt and manifest SHAs that match, and an unchanged manifest.
   - It writes timestamped evidence recording helper use, the methods and the SHAs.
   - Tests passed both for success and for rejection of writable or changed files.
   - Running it immediately before the session, and including its evidence in the session receipt, remain operational requirements.
6. **No re-pins, conditionally.**
   - All 18 helper pins equal both committed END-A3 host manifests and the verified runtime package.
   - The frozen session `validate_bundle()` verifies runtime and measurement files.
   - No existing file-SHA replacement is needed while frozen bytes remain unchanged.

### Findings 1–7 remain resolved

- Single-bootstrap behavior passed the real-runtime smoke.
- A clone failure cannot silently pass as a clone.
- Changed artifacts and mixed stages are rejected.
- The memory code requires at least 2,000 unique agreement inputs, exact retained-id sets and 2,001 child forwards, with workload bindings.
- Full runtime and native provenance checks passed.
- The uncovered B.4 fill case stops and escalates.
- Empty captures are safe, and empty games keep their ranked slots.

### Whole-amendment assessment

- **Rules:** B.1–B.7 match the adopted selection, cadence, overlap, fixture and reference rules. The `(tier, seed)` identity and the stop on an uncovered fill are clarifications, not replacement selection rules.
- **Outcome blindness:** outcome data take part in neither selection nor inference.
- **Phase 2 command:** one rsync SSH session, multiplexing disabled, the 32-file allowlist, remote nice 19 on core 63, and `bwlimit=32768`. Local verification hashes the files without unpickling them. The declared-window, settling and release obligations remain governed by proposal §C.2.
- **Phase 3:** the arguments match the frozen converter and builder interfaces.
- **Scope:** no change to any hypothesis, arm, seed, tier, gate, threshold or reducer.

### Independent validation

- Both requested suites passed 38/38, with no skips.
- The real-runtime smoke passed: six main inferences, Torch threads `[1,1]`, and a successful child exit.
- All 19 source SHAs, the Markdown SHA, the frozen-record SHAs and the test-log SHAs matched.
- I independently verified the 3,785-file runtime binding and the native SHA.

Still to come as execution evidence: production capture reproduction, the full memory gate, the pooled-END cross-check and actual Darwin cloning. I made no repository edits or commits, no SSH connections, and no reads of production games, outcomes or heldout data.

## Builder response

**10: Fixed.**
- A4.md item 5 now says the full runtime check runs once when `build_runtime.sh` creates the runtime. After that, the stages that load the runtime re-run it: `build_sets`, `assemble_states`, `student_reference compute`, and `memory_check` (the main process and both D6 children).
- It also lists the stages that do not: the frozen converter, which performs its own input-SHA, fingerprint and disk checks; and `cross-check` and `seal`, which check only the e4v3 pins and the artifact and receipt chain, carrying the recorded runtime binding forward without re-measuring it.
- Item 6 now names the stages that re-hash their inputs.
- The `run_phase3.sh` comment is corrected.
- The JSON was regenerated, so its Markdown SHA matches.

A confirmation round 4 was requested because the coordinator asked for a commit after APPROVE.
