# SOL-REVIEW-K4S-AMENDMENT-1-r2

- **Reviewer:** GPT-6.1-Sol (codex, reasoningEffort high), T3 delegated task `k4s-amendment1-sol-review-r2`.
- **Mode:** the review was read-only and stayed inside an explicit outcome-blind read boundary.
- **Saved by:** the implementation worker, verbatim from the reviewer's final message.

---

**PREREG-K4S Amendment 1 — independent read-only review, round 2**

Reviewed candidate tree `/mpac/sdicks02/jobs/clasher/k4s-amendment1-20261011`, detached at `6afcbbab`, including its uncommitted amendment. Round 1 Finding 1 is fully resolved. The mechanical re-pin is correct. One remaining substantive issue concerns recovery guidance for an END job already bound to the old manifest.

**Boundary and execution**

I respected the outcome-blind read boundary. I did not open the freeze skeleton, c* records, X4S-2 files, receipt directories, job/reporting/game receipts, PROGRESS files, or results files. Freeze records were accessed only through `sha256sum`. COORDINATOR access was limited to the permitted `grep -n 'END window\|Companion K4S rebind\|FROZEN-K4S'` lines. END namespace inspection used Git filenames only.

I created no files, edited nothing, staged or committed nothing, used no SSH, and ran no games. Every executed command used `nice -n 19 taskset -c 63`.

**Findings**

1. **[major] An existing old-SHA END job cannot be recovered through ordinary technical repeats alone.**

   The amendment Markdown at line 95 and JSON `effect.end_status` instruct that any reference produced under `d89cab16…` must be re-run under existing technical-repeat rules.

   A valid reference produced through the frozen producer requires an END-JOB declaration: `end_reference.py:305` calls `end_evidence.end_job`. That declaration binds `k4s_manifest_sha256`, and `end_evidence.py:428` rejects a different manifest SHA. It is also immutable: lines 356–364 require its fixed path to have been added in exactly one commit and never modified, deleted, or re-added. Later rounds retain the same frozen inputs (`end_pool.py:539–546`).

   Therefore, an existing committed END-JOB naming `d89cab16…` cannot admit an amended rerun naming `8bb20a75…`. Patching or replacing that declaration also fails the existing authority checks. I reproduced both refusals using synthetic inputs entirely in memory.

   **Required correction:** distinguish references produced outside valid END authority from references associated with a committed old-SHA END-JOB. For the latter, state that existing repeat rules alone are insufficient: coordinator disposition and an explicitly authorized authority migration would be required before an amended rerun. This amendment does not implement that migration. Do not prescribe editing the immutable declaration.

   No END namespace exists in the checked base commit, so this is a conditional recovery defect, not evidence that current END work needs migration.

2. **[minor] The opening blinding claim contradicts the new disclosure.**

   Markdown line 10 says the amendment was written without reading any game outcome, win rate, or loss rate from X4S-2. Line 13 discloses that the author saw pre-freeze X4S-2 exploratory numbers. The disclosure is useful, and nothing found suggests the re-pin depends on those numbers, but the categorical opening statement is too broad.

   **Suggested correction:** scope the claim to unread K4S confirmatory outcomes and acknowledge the disclosed prior exploratory exposure. Likewise, define JSON `outcome_access: false` as confirmatory outcome access, rather than leaving its scope ambiguous.

3. **[minor] JSON retains an unqualified claim about external END state.**

   JSON `effect.end` ends with "no END reference exists yet," while `effect.end_status` correctly says external job state was not inspected.

   **Suggested correction:** use the qualified statement consistently: no END declaration/reference is present on the checked main tree; external state is unknown. Qualify the Markdown "Nothing to redo yet" label similarly.

**Round 1 resolution**

The revised fleet guidance accurately describes:

- Runtime-byte verification at `barrier.py:51`.
- Verification against `authorization.freeze_commit` at `barrier.py:61`.
- Admission call sites at `run.py:348–349` and `supervise.py:37–38`.
- Both admission-blocking failure modes.
- Preservation of original manifest bytes in fleet runtimes under the unchanged authorization.
- Separate amended Mac/END runtimes.
- The alternative requiring separately authorized inventory and authorization changes.

The fleet-independence claim is now appropriately conditional. I verified these code paths, without inspecting external authorization or job receipts.

**Independent verification**

- Frozen manifest SHA: `d89cab16afdffa88d30e61eb1f4daea74e046703994f6aee7e74bfedc8d08f40`.
- Candidate manifest SHA: `8bb20a753bdb8f5f606ea2288336b1350f96a5199d158b2b8750317c26493009`.
- Both manifests have the same **77 leaves**; exactly **two** differ: the TIERS pin and builder-required `measure_tiers_unmodified.sha256`.
- `frozen: true` and `status: "FROZEN"` remain intact.
- The TIERS source diff adds only `import math`; old/new source SHAs match the records.
- Builder output reproduces candidate bytes exactly **with one boundary qualification**: I supplied the unchanged `reports/explore/x4s2/sdefault.py` candidate SHA from the frozen manifest rather than opening that forbidden file.
- Of **43 pin entries covering 40 paths**, I independently hashed **42 entries covering 39 paths**. The remaining entry is that forbidden X4S-2 candidate.
- The actual amended manifest loader succeeds with `require_frozen=True`; the old reused-readonly pin set refuses specifically on `measure_tiers.py`.
- JSON parses successfully. Manifest, TIERS source, TIERS review, regression-test, and freeze-record SHAs match their recorded values. Test-count arithmetic is consistent.
- The new regression test passes and meaningfully checks acceptance of the amended pin and refusal of the old pin. The pinned reviewed test remains unchanged.

**Test limitation**

I ran **28 unmodified, boundary-safe Mac tests: 28 passed**, including the new regression. I separately reproduced the known frozen-versus-draft assertion failure in memory at `test_measure_k4s.py:609`.

I did **not** independently reproduce the full **95 passed / 1 failed** suite or the **103 END passes**. The full suites create temporary receipts/files; builder calls also hash the forbidden X4S-2 candidate. Those totals remain reported evidence, consistent with the supplied round-1 review, rather than round-2 measurements.

The remaining required revision is to the END recovery record; the manifest and regression implementation need no change.

VERDICT: REVISE
