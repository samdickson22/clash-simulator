# Independent Sol harness review r3

2026-10-16T09:18:04Z. **Launcher APPROVED for the specified bounded DEV diagnostic, conditional on the new harness pytest passing first and matching reviewed deployment bytes. Gate PASS is NOT established.** On01 only for this approval: N=2, parent+2 children=3 slots, exact default serial `K4L-R-gs-rw-fc`, `--arms A,B --all11-gate --start 0 --count 4`, outer `timeout --kill-after=10s 15m` (including admission; no `--foreground`). Use a separate output directory and an all11 derivative of the existing DEV base1 bank, preserving seeds/decks/seat/controller and changing both true profiles and planner views to11; preserve original bank and record derivation/hash. No fresh pilot bank, pilot game, strategy/runtime/model promotion is approved.

Read-only review on127x05; supplied `clasher-bot-levels05` path is absent. Reviewed `/mpac/sdicks02/repos/clasher-bot-levels`, the worktree explicitly identified by current PROGRESS, HEAD `5b55e3aa853884861d00f1723a58626fd634346b`. Path discrepancy disclosed to requester. Read all four requested files, DESIGN/PROGRESS, original review and supporting callers. No tests/project-code execution, remote commands/jobs, GPU, delegation or implementation edits. Only this report written. Prior four tests/eight A games predate these fixes and do not validate them.

Sam's corrected direction applies: confident reversible work may proceed after required review/passing checks. Remaining failures/gates block acceptance on evidence, not a blanket Opus freeze. Original serial B tower metadata changes include leaf normalization PLUS scripted crown spell lethality/Lightning ordering; identical-state learned features remain frozen only at that layer. Pooled LIVE propagation is not prerequisite to a valid serial pilot, but that pilot is outside this approval.

1. **Resolved launcher/concurrency.** `run.sh:4–18` rejects disallowed hosts, N outside1..15 and explicit worker overrides before env/lease. Parser disables abbreviations, bounds workers and requires exact serial base (`run.py:193–215`). Wrapper reserves N+1 and preserves child status via exec. Existing env hides GPU, limits math/Rayon threads and hash seed. These controls cover this invocation, not concurrent duplicate launches or aggregate task reservations. Owner must retain existing leases/no-duplicate discipline. Outer timeout must target the whole owned process group: parent-only SIGTERM still bypasses Python finally (`:288–295`).

2. **P1 — resume identity remains incomplete.** `run.py:229–250` accepts successful rows BEFORE Runtime/preload. All-done resumes return without either validation. Identity checks source hashes, pins NAME, resolved runtime PATH, base/client/gate; rejects legacy/mismatched successful rows and wrong case/arm. Numbered exclusive launch receipts preserve history. However cache manifest is only written at `:257–260`, never included in row identity or compared against retained rows. Replacing L11/other cache contents at the same path permits old/new B results to mix. Runtime Python/prior/learned-model contents and effective `BOT_BELIEF_PRIOR`/`CLASHER_LOPP_MODELS` are likewise unbound; source hashing omits runtime.py, factory/other dependencies and external env.sh. Runtime verifies selected native/v1/R3a/gamedata pins only when actually constructed. Freeze/validate full manifest before accepting retained rows, including effective model/prior/runtime/source/cache digests. This blocks claiming general resume integrity; use a fresh DEV output and immutable inputs for this diagnostic.

3. **Cache readiness improved; hashes have timing limits.** Parent refuses missing exports, checks full L11 card/error coverage, computes all planner-known required levels, loads before forks and injects `rt._level_configs`; inherited build override refuses unexpected exports. All11 loads only11; regular B includes rarity floors and known own levels without hidden truth. Known per-card export errors remain explicit, not wholesale startup rejection; root rejects actually playable missing entries. Manifest includes support JSON plus export path/count/hash/errors, but hashes reread disk after loading: concurrent artifact replacement could make receipt describe different bytes from in-memory data. Freeze artifacts or hash the exact bytes parsed. No exporter should overlap this gate.

4. **P2 — errors/counts still do not propagate to acceptance.** Caught match errors write rows yet exit0 (`:177–190`); parent never exits nonzero for errors or child crashes (`:281–287`). Test explicitly expects error exit0. FAILURES remain scored, and report omits their counts/completeness. `len(cases)==count` does not prove unique/full indices: duplicates can satisfy it and launch conflicting writers to the same row. Require unique requested indices and both A/B arms for parity; parser currently permits A-only/B-only. Add parent-level failure/completeness checks. Until then shell0 is not PASS.

5. **Forced path connected, execution proof pending.** Child forwards `parity_all11`; factory uses constant11 for every rarity, forces ExactLevelRoot, injects cache, assigns root_fn; MultiSearchPlayer.act actually calls it (`players.py:173`). Force disables trivial bypass. All11 leaf_native returns None. Fake-child tests prove forwarding/diagnostic serialization, not native equivalence. Acceptance requires exactly eight terminal rows, zero errors/failures/unexplained rejected commands, four A/B full-command hash matches, both seats/controllers, and B `level_diagnostics.stats.roots>0`. No automatic parity assertion exists.

Suggested owner-only check on01, NOT executed:

```bash
ssh 127x01 'set -e; source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh; cd "$REPO"; timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -m pytest -q -p no:cacheprovider bot/levels/test_harness.py > /mpac/sdicks02/jobs/clasher/bot-levels/dev/pytest-harness-r3.txt 2>&1'
```

Reviewed SHA256 (unchanged at final reread):

```text
850ed7b540ede3665c6f51d717b6402fef2df10d34a0bfde138aaecc93b6005c run.py
d6fcbbd8151710c7d7a4220db5c9e6790fb9efa336b1a4679154426414363165 run.sh
62f9f9e25a58df32fa07681cf13d05406ae977ec1f9655acb5b11c45074cead4 test_harness.py
ba8a35199d6778391f08f5d14862c380983361c6e256152e9114062369ae0917 player.py
b0992c5ca633598ead83c52554d6930acc4b3afd7bde5989129880a285b08adc dev/env.sh
```

Rollback: retain all banks/receipts; stop only the diagnostic's owned process group on failure, preserve failed output, and make any corrected rerun separately reviewable. No implementation rollback is needed from this review.
