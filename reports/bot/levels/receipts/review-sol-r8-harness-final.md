# Independent harness review r8 — 2026-10-16

**Verdict: YES to syncing the exact reviewed bytes and running the specified tests on01. YES, conditional on those tests passing, to one fresh four-case DEV all11 A/B run through the reviewed launcher. NO primary bank draw or primary pilot yet.** Remaining provenance findings below affect pilot acceptance; they do not prevent this bounded diagnostic with frozen inputs and a fresh output directory.

Source-only review of `/mpac/sdicks02/repos/clasher-bot-levels`; read r3 findings, current DESIGN/PROGRESS/HANDOFF, scope/player, requested tests and relevant factory/runtime/cache/match dependencies. No project imports, tests, remote commands, jobs, sync, implementation edits, commits or delegation performed. Only this report written. No new-version execution success is claimed.

## Findings

1. **P1, primary provenance: B0 implementation remains outside identity.** `run.py:26–40` hashes selected immediate source directories, excluding `bot/live`. `player.py:48–55` directly imports and uses `bot.live.levels.LevelRoot/Levels` for B0. Changing that file leaves `source_sha256` and the other identity fields unchanged, allowing completed B0 rows to resume alongside changed B0 behavior. Bind this actual dependency before claiming immutable A/B/B0 provenance. This does not affect the requested A/B-only diagnostic.

2. **P1, report provenance can pass without a v2 identity.** `report.py:126–149,169,209–213` does not require an identity, its protocol, or mandatory identity fields. A bank-backed launch lacking `identity` (or carrying `{}`), terminal rows and a zero parent completion can produce `quality_ok=True` without source/runtime/cache binding. `registered_report` in `test_harness.py:645–659` explicitly supplies `{}` and its tests expect success. Require a substantive v2 identity for an authoritative quality PASS; legacy output can remain readable with invalid/unverified quality. A fresh current-runner launch supplies identity, so the diagnostic may proceed with explicit receipt inspection.

3. **P2, primary completeness still defaults missing evidence to clean.** Outside all11 mode, `row_issues` (`run.py:99–105`) treats absent `failures`, `channels` and `child_exit_code` as zero/acceptable. A v2 terminal row with valid prior evidence and score but missing channel/failure diagnostics can be reused and counted clean by the primary report. The all11 `complete_diagnostics` check catches missing channels/failures, but is not applied to primary A/B/B0 runs. Require complete per-row diagnostics and verified exit evidence for primary resume/report acceptance. Fresh child output normally supplies these fields; this is a validator gap, not an observed game failure.

4. **Prior blockers substantially repaired.** Runtime, common scope, student/rollout model, vocabulary and cache preload now precede every resume decision, including all-done (`run.py:465–493`). Cache identity hashes the exact parsed bytes and canonical data; inherited loads/builds are frozen. Runtime sources/native/checkpoints/prior/environment script, effective variables, package versions and simulator implementation are bound. Both controllers' runtime prior digests are checked before/after; the inspected standard factories use that common prior. Numbered receipts use exclusive creation. Errors, native failures, rejected commands and child failures propagate nonzero while preserving detailed rows. SIGTERM cleanup verifies unreaped direct children and uses bounded TERM/KILL waits; fork registration masks termination and children cannot unwind into parent cleanup. These paths still need execution evidence.

5. **No new import-cycle or serial-model-preload blocker found.** `report` imports helpers from `run`; `run` never imports `report`. The exact base's `fc` path selects serial defaults, with no learned process pool. Parent model preload is inherited by game forks. Fair-level cache planning does not consult hidden opponent levels. Shared named parity checks require complete unique A/B rows, terminal results, matching full-command hashes, positive B roots and clean diagnostics. Preserve the accepted 22.1548% common-prior omission and B leaf-plus-scripted-crown semantics; no pooled LIVE inference follows.

## Bounded execution conditions

- Owner may sync these exact files and matching reviewed dependencies to01, then run the existing `cpu_job.sh 1 nice -n 10 "$PY" -m pytest -q -p no:cacheprovider bot/levels/test_harness.py bot/levels/test_scope.py bot/levels/test_configs.py`, under the existing environment and an outer `timeout --kill-after=10s 15m`. Retain terminal status/log. Tests are fixture-based; passing them does not establish native gates.
- After test PASS and deployed hash verification, use `timeout --kill-after=10s 15m bash bot/levels/run.sh 2 --bank <DEV-all11-bank> --out <fresh-output> --arms A,B --all11-gate --start 0 --count 4`. No `--foreground`; timeout must own the complete process group, including admission. Parent+2 game children reserve three slots. CPU only01, existing lease/nice controls, no duplicate jobs/exporters, no concurrent edits to hashed sources/inputs, no frozen-runtime writes.
- Derive all11 from existing DEV base1, retaining seeds/decks/seats/controllers and changing true/planner levels consistently; record original/derivative hashes. Verify both seats and R3a/v1 coverage manually: named checks do not enforce that coverage. Require parent exit0, eight complete terminal rows, four full-command hash matches, every B root count positive, zero errors/failures/rejections, report quality PASS and complete v2 receipts.
- Mandatory suite r6 remains failed; its separate fixture repair/review and substantive full-suite PASS remain required. Resolve the provenance findings before primary acceptance, then freeze inputs and record the fresh 100-case BASE before A/B/B0 games. Stop only verified owned processes on failure, preserve outputs, and use a separate reviewed rerun. No blanket Opus hold is needed.

SHA256, matched again at final source reread:

```text
de3a300074aec2a75f75a54fcdf3ea9b8ee48ca75fb952a2ca866f8df7486dfd  bot/levels/run.py
831d0b66323de470492dc2335948612a93b829f61fb1d87b0c2a403aa8d0b984  bot/levels/test_harness.py
88358f308f6621573d08f146d57a474e3dd02e0b28e55ffa8c01e5f89d6665a2  bot/levels/report.py
d6fcbbd8151710c7d7a4220db5c9e6790fb9efa336b1a4679154426414363165  bot/levels/run.sh
0ae75da5a978d9cac4a52125afc5cefcd123c58d170d285930ed1ff41e9065b2  bot/levels/scope.py
5eab866d622b8024f8b3c2f698996c972335e2adcbdcbdfd7007f0565503768d  bot/levels/player.py
```
