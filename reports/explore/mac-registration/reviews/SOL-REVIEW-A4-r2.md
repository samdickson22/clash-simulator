# Sol review, TIERS Amendment 4, round 2

Reviewer: gpt-6.1-sol (high). T3 `delegate_task` id `macreg-a4-sol-review-r2`. Requested 23:00Z and completed by 23:03Z on 2026-10-11.

Note on the review input: after this round started, `stage_nocopy.py` changed only in its docstring timestamp. The coordinator had corrected the scope-message time from 22:33Z to 22:30:53Z. No code changed.

## Sol's text (verbatim)

VERDICT: REJECT

All seven round-1 findings are resolved. The new staging design requires an explicit coordinator ruling before use.

1. **RESOLVED: double runtime bootstrap.**
   - `student_reference.py:91` and `memory_check.py:34,59` use `bootstrap_runtime=False`. Frozen `TierBackend` makes the single `setup_imports` call.
   - I reran the real-runtime smoke independently. Main inference succeeded, Torch thread counts were `[1,1]`, and the spawned child exited successfully.
   - The glue test also detects an extra bootstrap.
2. **RESOLVED: silent `cp -c` data copying.**
   - `stage_nocopy.py:78–85` calls `clonefile(2)` directly. Failure is explicit.
   - Any later hard link or space-checked copy is recorded separately (`:97–117`), and a SHA mismatch fails closed. The placement tests passed.
   - This was a Linux-only review, so the actual Darwin clone operation remains untested.
3. **RESOLVED: receipts disconnected from current artifacts.**
   - `assemble_states.py:77–84`, `student_reference.py:69–99,132–140` and `seal_receipt.py:28–72` verify current artifact SHAs and stage relationships.
   - Sealing checks the actual reference keys, the fixture-plan ids, the canonical fingerprint and the END prefix.
   - The changed-reference and mixed-stage regressions passed.
4. **RESOLVED: memory workload enforcement and binding.**
   - `memory_check.py:66–73` requires the reviewed bundle and at least 2,000 unique agreement ids.
   - The main backend must retain the agreement set. Both children report their retained-id SHA and actual forward count, and the parent checks them (`:79–103`).
   - The receipt binds the sets, the reference receipt, the bundle manifest and the fixture files. `seal_receipt.py:62–65` checks those relationships and the workload summary.
   - The limitation that this is a Linux proxy for Mac CPU/MPS memory is now stated accurately. The full production memory check remains a Phase 3 requirement.
5. **RESOLVED: runtime provenance.**
   - `macreg_io.py:125–145` checks the committed END-A3 manifest SHA, equality of all 3,785 runtime files, measurement-file equality, package placement and native SHA `44874fd6`. My real-runtime smoke exercised these checks successfully.
   - I independently confirmed that the staging helper's 18 measurement pins equal committed END-A3.
   - Interpreter and package differences are disclosed.
6. **RESOLVED: invented B.4 edge rule.** `selection.py:188–190` now stops and escalates when the fill cannot satisfy "at least one each". Both amendment formats say so, and the regression passed.
7. **RESOLVED: empty captures and games.**
   - `build_sets.py:40` handles an empty capture safely; I exercised that path independently.
   - `build_sets.py:121–123` supplies the pinned capture inventory, and `selection.py:76–114` preserves the ranked slots of empty games.
   - The empty-game regression passed.
8. **BLOCKING: the runtime substitution exceeds the coordinator's authorized staging path.**
   - **Locations:** `stage_nocopy.py:147–150`; A4 Markdown `:110–125`.
   - The builder correctly established both decisive facts. `prepare_bundle.py` is pinned in `measurement_files`, and frozen preparation rejects pre-placed files (`prepare_bundle.py:28–33,98`).
   - The instruction explicitly required: **"If neither works, STOP and report."** Replacing `prepare_bundle.copy_file` at runtime is a third design. It is not the permitted pre-staging helper, because frozen preparation cannot accept that helper's pre-placed outputs; instead the helper changes the function that preparation executes. Byte-identical manifests show that the outputs are compatible. They do not show that the design is authorized under the stop condition.
   - **Required fix:** report that the authorized alternatives are blocked. Obtain an explicit coordinator ruling permitting this narrowly scoped runtime substitution, and record it in the A4 Markdown and JSON before use.
   - **Re-pin assessment:** the helper needs **no replacement of existing file-SHA pins**:
     - e4v3 bytes and measurement pins stay equal;
     - enforced placement preserves the runtime pins;
     - K4S manifest `c1fb1e9a` does not pin `prepare_bundle.py`;
     - no fleet file changes, so no FROZEN-K4S re-pin is needed.

     The helper is already SHA-bound in the A4 candidate. None of this removes the need for procedural authorization.
9. **MINOR: incorrect description of Amendment 3's pins.**
   - **Location:** A4 Markdown `:133`.
   - "None of them names `prepare_bundle.py`" is false: the committed Amendment 3 JSON records its `a1c59fa3…` after-SHA.
   - **Required fix:** say that existing records remain unchanged because the pinned file's bytes remain unchanged, and remove the claim that Amendment 3 does not name it.

**Independent validation.** Both requested suites passed 38/38 with no skips, and the real-runtime smoke passed. Every A4 `source_files` SHA and its Markdown SHA matched the reviewed working-tree files. I made no repository edits or commits, no SSH connections, and no reads of production `games/`, outcome files or heldout data.

## Builder response

- **8:** I accept this finding.
  - The A4 note and JSON now mark the staging helper **NOT AUTHORIZED FOR USE, pending an explicit coordinator ruling**. Until then the Mac stages with the frozen command unchanged.
  - I reported the stop to the coordinator at 23:03Z with both blocked options and the helper as a proposal.
  - If the coordinator permits the helper, the ruling will be recorded in the md and json before round 3. If the coordinator refuses, the helper is removed from A4.
- **9:** Fixed. The table row now says that Amendment 3 records `prepare_bundle.py`'s after-SHA `a1c59fa3`, that those bytes are unchanged, and that no record pins a file that changes. The JSON `re_pin_analysis` is updated to match.

## Coordinator ruling on finding 8 (issued 23:04Z; COORDINATOR 684195b3 at 23:04:25Z; first labelled about 23:07Z, corrected by the coordinator)

The coordinator **APPROVED** `stage_nocopy.py` as an external operational staging helper inside A4, under six conditions:
1. location and pinning;
2. clone → hard link → space-checked copy, SHA-verified;
3. `chmod a-w` on the source and bundle copies, recorded;
4. the byte-identical `tiers-pins.json` test kept as evidence;
5. session-time re-verification of the three SHAs, recorded in the session receipt;
6. no re-pins only while nothing frozen changes.

Implemented as follows:
- **Condition 3:** `read_only()` runs after placement.
- **Condition 5:** `--verify-bundle` / `verify_bundle()`.
- **Tests:** they check the modes, verification passing, and fail-closed behaviour on a writable or changed file.
- **Records:** the ruling is in the A4 md, under "Mac staging without a data copy", and in the json `mac_staging`.
