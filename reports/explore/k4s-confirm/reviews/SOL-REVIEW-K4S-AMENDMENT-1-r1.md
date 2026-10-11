# SOL-REVIEW-K4S-AMENDMENT-1-r1

- **Reviewer:** GPT-6.1-Sol (codex, reasoningEffort high), T3 delegated task `k4s-amendment1-sol-review-r1`. The review was read-only.
- **Candidate:** the uncommitted worktree `/mpac/sdicks02/jobs/clasher/k4s-amendment1-20261011` on top of 6afcbbab.
- **Saved by:** the implementation worker, verbatim from the reviewer's final message.

---

The re-pin and regression test are correct. I request revision of the fleet-runtime guidance in both amendment records.

**Review-process disclosure:** A broad read of `FREEZE-RECORD-SKELETON.md` accidentally exposed a historical X4S outcome embedded in its c* provenance. I therefore cannot attest that this review preserved strict outcome-blindness. I do not reproduce that outcome here. A fresh, outcome-blind reviewer is needed for the required blind signoff. I used no SSH, ran no games, and opened no actual game or reporting receipts.

**Finding**

1. **[major] The FROZEN-K4S refinement omits the required runtime-byte constraint and overstates the fleet independence.**
   `PREREG-K4S-AMENDMENT-1-20261011.md:75,87–91` and the JSON's `effect.frozen_k4s_json` say the fleet manifest should retain `d89cab16…`, and justify this by saying fleet game code never loads the Mac manifest.

   That guidance is valid only while the authorization retains `freeze_commit=391d2006` **and the fleet runtime retains the original Mac manifest bytes**. `barrier.py:51` checks every listed file against the runtime tree; `barrier.py:61` separately checks the authorized commit. Thus, if FROZEN-K4S lists this manifest:

   - An old entry with amended runtime bytes fails the runtime check.
   - An amended entry with authorization still naming `391d2006` fails the commit check.

   This dependency affects fleet admission: both `supervise.py:37–38` and `run.py:348–349` invoke `reporting_release`. The absence of a direct Mac-manifest loader in game code does not eliminate that dependency.

   There is also a reading under which the coordinator's original wording holds: the barrier takes its commit from `authorization["freeze_commit"]`; it does not hardcode `391d2006`. A separately coordinator-authorized inventory and authorization bound to a committed amended tree could list the amended SHA. That is outside this candidate's current changes.

   **Required correction:** State in both records that preserving the current fleet authorization requires preserving the original manifest bytes in the fleet job runtime, while Mac/END use a separate amended runtime. Qualify the "must stay old" and new-test exclusion statements by the unchanged freeze authorization. Explicitly warn that deploying the amended manifest into a fleet runtime whose inventory still lists the old SHA blocks reporting admission. This requires record changes, not changes to the reviewed barrier or game code.

**Independent manifest verification**

The candidate HEAD is `6afcbbaba0a6748baafe3aca408b781f84989b7f`. Independently computed hashes match the records:

- Frozen TIERS file: `5d7de8e36890f0f8d086e77be5ec4e20de1b3cc1f48943bd06e8bbd103046124`.
- TIERS file at `6afcbbab` and in the candidate: `6066228b89601d6cf29ff456e9dee4848fa59886f319ff38ebabd49e3c101f2e`.
- Frozen Mac manifest: `d89cab16afdffa88d30e61eb1f4daea74e046703994f6aee7e74bfedc8d08f40`.
- Candidate Mac manifest: `8bb20a753bdb8f5f606ea2288336b1350f96a5199d158b2b8750317c26493009`.

Both manifests have exactly **77 leaf keys**, with identical key sets. Exactly two leaves differ: the `reused_readonly` TIERS pin and `measure_tiers_unmodified.sha256`. No other value changes; `frozen=true` and `status="FROZEN"` remain intact.

All **43 file-pin entries, representing 40 distinct paths**, match the candidate tree. Comparing frozen pins against `6afcbbab` identifies only the two occurrences of the TIERS-file hash mismatch. The only pinned path changed between the freeze and the base is `measure_tiers.py`; its production diff is exactly `import math`.

Calling the builder with the specified kernels and freeze flag, then applying its exact JSON serialization, reproduces the candidate **byte for byte**. I performed this reproduction in memory to avoid creating an output file. `build_manifest.py:68` derives the copied SHA from `reused[tiers_script]`; `k4s_logic.py:142–144` rejects disagreement. The second changed leaf is therefore required.

The complete candidate manifest loads successfully with `require_frozen=True`; the original reused-file pins reject the current TIERS bytes.

**Tests and regression**

All pytest executions used `nice -n 19 taskset -c 63`, the specified Python, `-B`, and disabled pytest caching.

- Before-state existing Mac suite: **88 passed / 7 failed**, reproduced by presenting the original manifest through an in-memory read overlay.
- Candidate Mac suite including the regression: **95 passed / 1 failed**. The new test passes, leaving **94 passed / 1 failed** among the existing 95 tests.
- Sole candidate failure: `test_manifest_loader_rejects_draft_for_mac_and_tamper`, at its existing `assert manifest["frozen"] is False`.
- Candidate END suites: **103 passed**.
- Before-state END check: **102 passed**, followed by the remaining spawned-process test passing after correcting a reviewer-wrapper issue involving the nonexistent `<stdin>` script. This establishes all 103 before-state cases across those runs.

The historical freeze result of 94/1 was supplied in the brief; I did not independently execute the freeze tree.

The regression is meaningful: it checks both manifest fields, verifies the new pin against actual tree bytes, and requires the old pin to raise the expected refusal. Its recorded SHA, `a0a70f7fa6f97898885db6a5eab328482d33851f1e3ea9db9163a0745dc9220e`, matches. No reviewed test was edited. Keeping the addition outside pinned `test_measure_k4s.py` preserves the single-pin scope.

**END, classifier, and record assessment**

The END correction is supported by code. `end_reference.k4s_pins`, `end_pool.pool_context`, and `end_background.frozen_helpers` load the complete frozen K4S manifest, including the TIERS pin. `check_end_pins` binds reference identity to the Mac manifest SHA, and `end_evidence.end_job` checks the END-JOB's SHA binding. END products intended for amended Mac sessions must consistently use the amended identity and compatible runtime bytes.

Leaving DELTA-MANIFEST and historical freeze records unchanged is consistent with retaining the original freeze evidence. The candidate adds the manifest mismatch and one unclassified regression file to the classifier discrepancy set. I found no runtime invocation of `rebind.verify`; END checks the unchanged kernel/scorer rows rather than requiring whole-inventory classifier success. I did not run the complete classifier because it reads inventoried receipt files.

The recorded freeze-record and TIERS-review SHAs match. No kernel, scorer, SD1, arm, seed, hypothesis, statistical gate, or c* value changes are present. Fleet admission remains subject to Finding 1. The claim that no END reference exists is not independently established for external job state; no candidate-tree END declaration/reference artifact was found.

Candidate status remained unchanged, and `git diff --check` passed. Pytest created only its synthetic temporary fixtures.

VERDICT: REVISE
