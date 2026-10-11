# SOL-REVIEW-K4S-AMENDMENT-1-r3

- **Reviewer:** GPT-6.1-Sol (codex, reasoningEffort high), T3 delegated task `k4s-amendment1-sol-review-r3`.
- **Mode:** the review was read-only and stayed inside an explicit outcome-blind read boundary.
- **Saved by:** the implementation worker, verbatim from the reviewer's final message.

---

**PREREG-K4S Amendment 1 — independent read-only review, round 3**

**Reviewer:** GPT-6.1-Sol, high reasoning effort.  
**Candidate:** `/mpac/sdicks02/jobs/clasher/k4s-amendment1-20261011`, detached at `6afcbbaba0a6748baafe3aca408b781f84989b7f`, plus the uncommitted candidate.

The mechanical amendment is correct. All round-2 substantive findings are resolved. One non-blocking wording issue remains; no blocker or major remains.

**Boundary and execution**

I respected the outcome-blind read boundary. I did not open the freeze skeleton, c* records, actual job/reporting/game receipts, PROGRESS files, or RESULTS files. Freeze records were accessed only through `sha256sum`. COORDINATOR access used only the permitted `grep -n "END window\|Companion K4S rebind\|FROZEN-K4S"`. The sole X4S-2 access was hashing `sdefault.py` through `sha256sum` and the explicitly permitted builder.

I created or edited no repository files, staged or committed nothing, used no SSH, and ran no games. All executed commands ran under `nice -n 19 taskset -c 63`. The permitted pytest suites used `-B`, `-p no:cacheprovider`, and synthetic fixtures under `/tmp`.

**Finding**

1. **[minor] Non-blocking: qualify "not a valid reference" by its authorized use.**

   Amendment Markdown line 96 and JSON `effect.end_status.recovery_without_end_job` categorically describe a reference without a committed END-JOB as invalid, including dev/dry references.

   A reference without END authority can pass dry-run validation: `k4s_logic.py:895–896` skips pooled-provenance verification when `dry_run=True`. The existing `test_measure_k4s.py:413–422` explicitly demonstrates dry-run acceptance and Mac-mode refusal of the same reference without provenance. I independently reproduced that distinction using synthetic inputs entirely in memory.

   Suggested wording: **"It is not valid for authorized END/Mac use."** Interpret "discard" as excluding it from the reporting reference.

   This is non-blocking because the enclosing paragraph already addresses references serving amended Mac sessions. The prescribed fresh production under a committed amended END-JOB is correct.

**Round-2 resolutions**

- **Finding 1 [major] — resolved.** The two recovery cases now distinguish absence of committed authority from an immutable declaration bound to the old SHA. `end_reference.py:305` requires `end_job` before claiming an attempt; `end_evidence.py:356–364` enforces the declaration's single-addition history; line 428 rejects a different manifest SHA. `end_pool.py:495–500,539–546` retains and revalidates frozen inputs across rounds. Ordinary technical repeats cannot migrate an old-SHA declaration. Requiring coordinator disposition and explicitly authorized authority migration, while stating that this amendment implements neither and forbids patching the declaration, accurately describes the constraint.
- **Finding 2 [minor] — resolved.** The opening blinding statement acknowledges the disclosed prior exploratory exposure and scopes unread outcomes appropriately. JSON `outcome_access_scope` removes the earlier ambiguity.
- **Finding 3 [minor] — resolved.** Both records consistently distinguish the checked main tree from unknown external state. Git filename inspection independently confirmed that `6afcbbab` contains no registered END namespace, END-JOB declaration, or `end-reference.json`.

The round-1 fleet-runtime correction remains intact. I rechecked both runtime-byte and authorized-commit checks at `barrier.py:51,61`, and their admission call sites. Separate frozen fleet and amended Mac/END runtimes remain necessary under the unchanged fleet authorization; external authorization state was not inspected.

**Independent manifest verification**

- Frozen manifest SHA: `d89cab16afdffa88d30e61eb1f4daea74e046703994f6aee7e74bfedc8d08f40`.
- Candidate manifest SHA: `8bb20a753bdb8f5f606ea2288336b1350f96a5199d158b2b8750317c26493009`.
- Both manifests have identical **77-leaf** key sets. Exactly **two leaves** change: the `measure_tiers.py` reused-readonly pin and builder-derived `measure_tiers_unmodified.sha256`.
- `frozen: true` and `status: "FROZEN"` remain unchanged.
- Calling `build(root, kernel=[anchor_x.py, sdefault.py], freeze=True)` and serializing with `json.dumps(indent=2, sort_keys=True) + "\n"` reproduces candidate bytes exactly, entirely in memory.
- All **43 pin entries covering 40 distinct paths** match candidate bytes.
- The only pinned path changed between freeze and base is `measure_tiers.py`; its diff adds only `import math`. Both source SHAs match the records.
- The amended manifest loads with `require_frozen=True`; the original reused-readonly pins refuse specifically on `measure_tiers.py`.
- The new regression meaningfully verifies new-pin acceptance and old-pin refusal. Its recorded SHA matches. No reviewed test changed.

**Tests**

Using the specified Python interpreter:

| Suite | Independently measured result |
|---|---|
| Complete Mac suite, including regression | **95 passed, 1 failed**, 2.58 seconds |
| `test_end_reference.py test_end_background.py` | **103 passed**, 91.70 seconds |

The sole Mac failure is exactly `test_manifest_loader_rejects_draft_for_mac_and_tamper`, at `test_measure_k4s.py:609`, asserting `manifest["frozen"] is False` against the intentionally frozen manifest.

Initial attempts encountered reviewer-selected temporary paths whose parent did not exist. Correcting the `/tmp` basetemp paths produced the results above; those setup errors were not candidate defects. Historical and before-amendment totals were not rerun in round 3.

**Record and scope assessment**

The JSON parses successfully. Markdown and JSON agree on the cause, identities, single semantic pin, derived field, test counts, blinding disclosure, fleet constraints, and END recovery. Recorded manifest, TIERS review, regression, and freeze-record hashes match.

The amendment preserves all other pins and frozen decisions. Its identity change affects Mac sessions and the END products supplying them; fleet operation remains unaffected subject to preserving the documented frozen runtime bytes. The FROZEN-K4S note satisfies that qualification.

Final Git status matched initial status, and `git diff --check` passed.

VERDICT: APPROVE
