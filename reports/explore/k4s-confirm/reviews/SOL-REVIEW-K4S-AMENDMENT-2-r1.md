# SOL-REVIEW-K4S-AMENDMENT-2-r1

- **Reviewer:** GPT-6.1-Sol (codex, reasoningEffort high), T3 delegated task `k4s-amendment2-sol-review-r1`.
- **Mode:** the review was read-only and stayed inside an explicit outcome-blind read boundary.
- **Candidate:** `/mpac/sdicks02/scratch/k4s-a2-wt`, detached at origin/main `4ccbdd4f`, plus the uncommitted candidate.
- **Saved by:** the implementation worker, verbatim from the reviewer's final message.

---

I respected the outcome-blind boundary. Restricted manifests were inspected only through the permitted field-filtering one-liners; other restricted access was hashing only. COORDINATOR access used the permitted grep with small context. I changed no repository files, used no SSH, contacted no Mac, and ran no games. Scratch artifacts and synthetic test fixtures stayed under `/tmp`.

All pytest runs used Python 3.12.12 with `nice -n 19 taskset -c 63`, `-B`, and `-p no:cacheprovider`.

- Candidate Mac suite: **98 passed / 1 failed**. The sole failure is the known draft-status assertion at `mac/test_measure_k4s.py:609`.
- Pre-amendment existing Mac suite, reproduced through an in-memory overlay of HEAD’s manifest and builder: **89 passed / 7 failed**. An initial reviewer-overlay encoding error was corrected before obtaining this result.
- New regression tests under the old manifest: **2 failed / 1 passed**, as recorded.
- Candidate END suites: **103 passed**, in 96.64 seconds. I did not independently rerun the historical END baseline.
- Builder regeneration using `--freeze --output /tmp/k4s-a2-review-r1-manifest.json`: byte-identical to the candidate, SHA **`c1fb1e9acb71a69d406c04d5a040dae734aa8fda57cae58f4f56363b591815de`**.
- `git diff --check` passed; final candidate status matched initial status.

Independent comparison confirms exactly three changed leaves, 77 → 78 leaves, with `frozen=true` and `status="FROZEN"`. All **44 pin entries covering 41 distinct files** match the candidate. The builder’s third pin change is necessary and acceptable: its enumerated dependency list must include `state_rows.py`, and the builder itself is pinned. Both amendment records disclose this consequence and the required preservation of original builder and manifest bytes in fleet runtimes.

The complete e4v3-local import closure, including lazy imports, is `{tier_backend.py, receipts.py, corpus_contract.py, state_rows.py}`. Neither `convert_states.py` nor `prepare_bundle.py` belongs to that runtime closure.

I found no K4S compatibility blocker. Packet lookups bind one row locally before admission and arrival timing; SD1 inference uses the retained agreement set; corpus measurements use `k4s_rows`. Production paths do not depend on legacy openings. END frozen pins differ only in `k4s_manifest_sha256`. The permitted fleet fields confirm original `d89cab16` / `26932fa8` bytes and authorization at `391d2006`. Recorded source, amendment, review, freeze-record, and regression-test hashes match.

1. **[minor] Complete the inherited residual disclosure.**  
   `PREREG-K4S-AMENDMENT-2-20261011.md:48` and `.json:61` omit two applicable A3 residuals. `mac/measure_k4s.py:144` loads the first K6 row before updating trace context at line 147, so GC during that load can retain the preceding variant’s label. `end_background.py:101` now includes per-state loading before search, changing background duty cycle; A3 also adds container storage and validation I/O.  
   **Suggested fix:** add these inherited effects to both records, citing A3’s residual discussion. This requires documentation only.

2. **[minor] Qualify the old-END-reference assertions by the inspected scope.**  
   `PREREG-K4S-AMENDMENT-2-20261011.md:167` says an old-SHA reference is “necessarily without a committed END-JOB” and that none exists; `.json:98` similarly categorizes old references as dev/dry. However, `.md:165` correctly states that external job state was not inspected.  
   **Suggested fix:** say no END-JOB exists **on the checked tree**, and preserve the two conditional recovery cases: unauthorized dev/dry references versus any externally discovered committed old-SHA authority requiring coordinator-authorized migration. The existing migration guidance is otherwise correct.

No blocker or major remains.

VERDICT: APPROVE
