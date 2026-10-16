# Independent source review r5 — supported-card scope

**Verdict: APPROVED for the owner to run `python -m pytest -q -p no:cacheprovider bot/levels/test_scope.py bot/levels/test_configs.py` on 01 through the existing `cpu_job.sh 1` and `nice -n 10`, with the pinned dev environment, GPU hidden, single-thread settings, no bytecode, bounded admission/execution timeout and a distinct receipt.** These fixtures construct lightweight fake resources; neither starts Runtime, an exporter, native simulation or worker pool. Match deployed source hashes first. This is diagnostic execution approval, not a passing-test claim or permission to draw the pilot bank.

Read-only source review on 127x05, `/mpac/sdicks02/repos/clasher-bot-levels`, HEAD `5b55e3aa853884861d00f1723a58626fd634346b`. Read the five requested files, current DESIGN/PROGRESS, r1/r2/r3 receipts and limited supporting consumers/test imports. Did not inspect current run/report/test_harness/gates, execute project code/tests, contact remote hosts, launch jobs, use GPU, delegate, or edit implementation. Only this report written. Runtime mapping/tower passes and scope counts are supplied/recorded evidence, not independently executed here.

**No new concrete scope/projection blocker found.**

- `scope.py:17–34` hashes the complete canonical JSON while preserving list order, including deck/card order and frequencies. Restriction deep-copies rows, keeps relative order and original weights, and counts overlapping exclusions once. No renormalization is required: the belief consumer builds cumulative weights from retained frequencies. Receipt includes both digests, deck counts, original/omitted frequency and omitted fraction. The accepted 2,500/2,925 decks and 15,371/69,380 omitted frequency represent a conditional population; neither digest proves live-prior equivalence.
- `scope.py:37–49` preserves a separate original snapshot, rejects both runtime and environment overrides, and checks both snapshots on subsequent installation. Immutability is checked at installation boundaries, rather than enforced by read-only containers. `test_scope.py:10–38` covers order/weight retention, source independence, idempotence, restricted-prior mutation, empty restriction and environment override. Original-snapshot mutation rejection and digest sensitivity to row ordering are sensible additional focused assertions, but no failing implementation behavior was found.
- `player.py:32–37` installs before construction for A/B/B0. `bank.py:37–51` projects against the original catalog and checks identical deck **and** overlap against the restricted catalog for every eligible source row, before sampling. A mismatch aborts rather than silently changing the population. `bank.py:69–86` records scope and refuses a different existing registration. Policy `make_poller` consumes policy/builder/costs, not the prior. The parent-owned early-install/manifest/resume integration remains outside this review and must bind the scope identity before accepting rows.

**Root coverage is required before bank/games.** `root.py:192–200` now raises on an unmapped producer or absent body delta, resolving the two silent-retention findings from r2. Missing playable/body exports already raise at `:161–168,196–197`. Existing `test_configs.py:28–38` exercises only `tower()` directly and does not establish these paths.

The fixtures already being written should exercise `payload()` for both seats: unknown producer; known producer with missing card export; known producer with exports but no matching body; successful ordinary body/shot, tower shot, spell carrier and secondary payload. Assert exact damage/HP, projectile max_hp=1, qualification and rejection messages. Preserve ordinary-shot support: Resources synthesizes shots from troop/building templates, so `body_delta`'s name fallback (`root.py:128`) is intentional and cannot simply become a strict class-match rejection. First-producer ambiguity (`:105–108`) remains the previously disclosed limitation; this review demonstrates no new affected pilot case.

The accepted serial tower metadata semantics remain unchanged. This review does not waive runtime/support, exact-root, fair-information, forced-all11 parity, snapshot/cut/pool transport or harness acceptance gates, and grants no pooled LIVE authority. No strategy redesign or further uncertain irreversible decision is needed for the approved lightweight checks.

SHA256, unchanged at final reread:

```text
0ae75da5a978d9cac4a52125afc5cefcd123c58d170d285930ed1ff41e9065b2 scope.py
16c631a39c1f9757c416896c8b449111bfa4ab9fcb280f1c574121aee4b84951 test_scope.py
d33cd3b1597cc7c4fa277a6211a4caee1fcc0a2188244466f8f66514dc373202 bank.py
5eab866d622b8024f8b3c2f698996c972335e2adcbdcbdfd7007f0565503768d player.py
4ec56d835fd85a055926ccc77e71cf328024291caa0e67addb57adea19aac394 root.py
1fdc2ceb92de1050cb7d9ef0b0e7aac2b49d3c0b124f1d6f8d6df542a56887b3 test_configs.py
d5b5044217d270f5a9276ba4ea0c5f8463d393d7e69982f139b7ea8fad5e66dd DESIGN.md
f87f822c408829c4444cfafc6730232711fefaf76d1e9e7a6a1b226eb07eefb2 PROGRESS.md
```
