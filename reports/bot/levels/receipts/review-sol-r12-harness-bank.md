# Independent source review R12 — final harness and pinned population

2026-10-16. Worktree: `/mpac/sdicks02/repos/clasher-bot-levels`, 05.

**Decision: conditionally APPROVE the specified owner-only tests on01, then one fresh four-case forced-all11 A/B diagnostic after those tests pass. No remaining source blocker found for the accepted serial pilot. Conditionally APPROVE drawing the fresh primary 100-case bank and running A/B/B0 only after every execution and provenance condition below passes. Primary readiness is not established by this source review.**

Read DESIGN, PROGRESS, SCOPE, HANDOFF, R8 review, R9 implementation receipt, R11 focused review and owner raw-snapshot audit. Inspected run/report/bank, their tests, scope/profile/player, relevant config/cache, B0 root and match/launcher dependencies. No project code executed or imported; no tests, synchronization, remote commands, jobs, source/runtime modifications, commits or descendants. Only this review was written. R8's 86 passing tests cover earlier bytes and do not validate R9 or the new bank test.

## Findings

1. **R8 B0 identity blocker resolved.** `run.py:37–41` now includes the actual `bot/live/levels.py` bytes in every source manifest, including A/B/B0 primary invocations. This dependency is checked before runtime construction, after preload and in each child. `resume_done` compares the complete newly constructed identity before reusing a clean row. `test_resume_binds_content_and_behavior` changes B0 source content and requires resume rejection; `test_B0_receipt_requires_actual_root_dependency` separately requires the B0 source entry in a B0 report identity. The scaler's `clasher` imports fall under the runtime source manifest.

2. **R8 empty/legacy report identity blocker resolved.** `identity_problems` requires v2 protocol, all emitted top-level fields, nonempty source/runtime digest maps, native/v1/R3a pins, package records, consistent restricted/effective-prior digests and B raw/canonical cache digests. `report.expected_run` records those problems for every launch; `quality_ok` rejects any such problem. Missing, empty, partial and legacy identities therefore cannot yield authoritative quality PASS. The new tests explicitly require provenance problems, preventing a passing test caused solely by a row mismatch. Old data remains readable as unverified evidence. This validates receipt structure and consistency; complete source/runtime manifest contents still require the owner's matching-byte inspection, as specified below.

3. **R8 primary diagnostic blocker resolved.** `diagnostics_complete` requires a nonnegative integer failure-counter map, both seats' nonnegative integer rejection counters, and an actual integer child exit code; booleans and missing/None exits fail. `row_issues` applies this independently of all11 mode, so incomplete evidence cannot be reused or included in clean primary scores/pairs. Child validation deliberately uses `require_exit=False`; the parent supplies wait-status evidence through `record_exit`. Thus the fix does not make healthy children fail before their exit is known. Regression cases cover all three arms for resume, primary reports with all11 disabled, malformed evidence, and successful/error child paths.

4. **Exact-byte identity and resume behavior remain coherent.** The bank digest uses the same bytes parsed for cases. Export manifests hash both the raw bytes actually parsed and canonical loaded objects; inherited cache loads are frozen and missing exports cannot be built in children. Full runtime/model/vocabulary/scope/cache preparation precedes even an all-done resume. Source/runtime changes during preparation abort. Before/after controller-prior observations bind both controllers to the common restricted prior. Errors, failure counters, rejected commands, nonterminal games and bad child exits prevent clean acceptance and propagate failure. Exclusive numbered launch receipts preserve earlier invocations. Use fresh output for the new-byte DEV run: an old launch identity remains part of report history and cannot be silently upgraded by a later successful launch.

5. **Explicit snapshot preserves bank API, registration and scope.** `build(rt, base, n, out_path, *, source=None)` preserves existing four-positional-argument callers and the former default source. CLI `--source` reaches that parameter. One `read_bytes()` supplies both parsing and the recorded source SHA; source order and duplicate rows remain meaningful population weights. Eligible rows still use trophies >=600, the immutable original catalog's projection and equality to the restricted projection. Seeds, shuffles, level sampling, alternating seats and paired controller schedule are unchanged. Bank creation remains exclusive; re-registration ignores only `created`, compares the source name/hash, population, constants, scope and all cases, and refuses a changed bank without overwriting it.

6. **Population freeze is the original DEV input, not a redesign.** Snapshot SHA is `b00ae7df0caa96358cbe0b6fdd9ed0dfb0becd7b270e80de96cca40c2cfd7440`, matching the source SHA recorded in `harness-dev-cases.json`. The current live log is byte-identical by `cmp`. Existing scope receipt records 54/54 unchanged projections, 2,500/2,925 retained catalog decks and omitted weight 15,371/69,380 (22.15479965%). Primary must explicitly name the snapshot; the compatible default remains mutable. Changing the live log after registration cannot affect a bank built from the explicit snapshot. Runner identity then binds the entire registered bank.

7. **Tests are meaningful, with bounded coverage limits.** New `test_bank.py` contains real newline escapes in its JSONL writes, not literal backslash+n data. It writes distinct snapshot/live rows, mutates the default live log, rebuilds the same explicit-source bank and requires identical registration and frozen row provenance. Existing `test_bank_determinism` exercises the preserved API, timestamp preservation, unchanged output bytes, trophy cutoff, seat/controller schedule and refusal to replace a different bank. Explicit snapshot-content tampering and alternate-path handling lack dedicated tests; the inspected comparison includes both source hash and source name, so these are nonblocking coverage limits. Protocol tests use fixtures; they do not substitute for native gates or the requested DEV games.

8. **R11 raw-snapshot handoff is consistent with its acceptance rule.** Read both raw difference lists in `gates-r11-owner-audit.json`: ten differences per seat, all absent `spell_name` becoming empty String, with matching entity indices/ids/classes/owners. Numeric/position ranges agree and normalized snapshots are equal. The owner receipt reports 254/254, 32 public bodies, cut/snapshot/pool 30/30/30, final cache sizes [1,2,2] and four fair decisions. This resolves the reported raw-default question on the supplied evidence. The audit references underlying receipt SHA `11e2cf3b00b465437df396d8b0852701298cc43fbdf5be51d69e92cb408f672c`; this reviewer did not independently fetch that on01 terminal receipt. Retain the owner's terminal0 log and exact deployed-byte verification. Historical R6 failure remains preserved.

## Conditional owner execution authority

1. Verify deployed bytes against this review and the previously reviewed dependencies, pinned runtime, environment and existing lease wrapper. No concurrent edits to hashed source/input/cache; no overlapping owned exporters/jobs. On01 only, existing `dev/env.sh`, GPU hidden, thread limits one and hashseed zero. Run the existing `cpu_job.sh 1 nice -n 10 "$PY" -m pytest -q -p no:cacheprovider bot/levels/test_harness.py bot/levels/test_scope.py bot/levels/test_configs.py bot/levels/test_bank.py`, bounded by `timeout --kill-after=10s 15m`. Preserve complete log and terminal status. Failure blocks dependent work.

2. After matching-byte test PASS, use the unchanged reviewed launcher: `timeout --kill-after=10s 15m bash bot/levels/run.sh 2 --bank <all11-dev-cases.json> --out <fresh-output> --arms A,B --all11-gate --start 0 --count 4`. Existing wrapper reserves parent plus two game children (three slots). Preserve original DEV base1 bank and derivative hashes; change only the diagnostic true/planner levels consistently. Require both seats and R3a/v1 coverage, eight complete unique clean terminal rows, four of four full-command hash matches, positive root calls in every B row, zero errors/native failures/rejections/child failures, parent exit0, report quality PASS and complete v2 provenance. No success is inferred from merely launching or from fixture tests.

3. Only after these conditions and all mandatory native gates pass at the reviewed bytes may the owner preregister a fresh `int.from_bytes(os.urandom(6),'big') << 4` BASE and the existing decision rule, then create the absent primary 100-case bank using explicit `--source reports/bot/levels/receipts/opponent-decks-snapshot.jsonl`. Verify snapshot SHA above, 54-row population/projection/scope receipts, frozen bank SHA and complete runtime/cache/source manifests before any primary outcome. Keep that bank immutable and run all A/B/B0 cases through the existing reviewed launcher/resource controls. Any failed check, changed reviewed behavior, input mismatch or unmet condition blocks primary execution; preserve evidence and obtain review for repairs. No additional permission is required once the stated gates pass at these bytes.

Accepted interpretation remains a serial conditional-population physics pilot with B crown metadata affecting leaf and scripted crown decisions. This review authorizes no pooled LIVE inference, deployment, pin/model change or frozen-runtime write. No compute on05/09–18 and no GPU work.

## Reviewed SHA256

```text
c52a449ed196e1fbda0298ee60c061d897e49d19acaccbe5760986e1d2d35695  bot/levels/run.py
43c943c2b2b1065215737191c114a9f0cbdf5398c860d09e6a77f5df215798e7  bot/levels/report.py
f927bf232dd5ee67f4a39402a2343eebff517cfb2942ddaa0653ca606a0a2cea  bot/levels/test_harness.py
7a705926bd69a3b1a31f2951bc0ef53f69b931e09158a3ee4e79c3c437d56620  bot/levels/bank.py
0d21af2288182c9c134546ce5141f78820ce6e8bbb409b3cc681c485a7ab98a7  bot/levels/test_bank.py
d6fcbbd8151710c7d7a4220db5c9e6790fb9efa336b1a4679154426414363165  bot/levels/run.sh (unchanged)
822cee2a73d9de27a069e99cc6dd21eb04686aecc552c7a5cd59f826796e00e5  bot/live/levels.py
0ae75da5a978d9cac4a52125afc5cefcd123c58d170d285930ed1ff41e9065b2  bot/levels/scope.py
2a828a846173ea33cbb0a11fc06566ce2e213f28769063dd079cdeaa270d72df  bot/levels/profile.py
5eab866d622b8024f8b3c2f698996c972335e2adcbdcbdfd7007f0565503768d  bot/levels/player.py
9fc73a910c4ee121a74f79cc53405ed2b93ad4eb3e042c5764ce79fdb3e18da3  bot/levels/configs.py
fb6321a0ce198fdd32de0902280306d4b1eaa11524ad67e322fd96fd88aa91e8  bot/levels/root.py
2e4eaf6a1691b34bec4f1aaf54221fc2923a419edb3aed676bee11f36d30b4c3  bot/levels/gates.py
16c631a39c1f9757c416896c8b449111bfa4ab9fcb280f1c574121aee4b84951  bot/levels/test_scope.py
762bc666079119d5559fac29401d59f2c3fbc8798bee83168b06b675bbcb0be0  bot/levels/test_configs.py
321d9e45068c84fa07603995bbb137f803ffcc3377733f57748627bca7a7d19d  bot/players/royalesim_match.py
a58a47875588691677a165f07678f48af103970f980b1f3b0baef8731fdeb1cd  bot/search/players.py
b00ae7df0caa96358cbe0b6fdd9ed0dfb0becd7b270e80de96cca40c2cfd7440  reports/bot/levels/receipts/opponent-decks-snapshot.jsonl
9943c757498af397381af397a4149c5ecb42f45fa21abfb5df5499bf810f5a6b  reports/bot/levels/receipts/harness-dev-cases.json
b7fa6a80cdffef71c08b9ff243fed0c1d8b93ffd2710d0cd931357d2d9188afc  reports/bot/levels/receipts/gates-r11-owner-audit.json
```

Coordination: automatic final result only; no duplicate completion message. Future blockers needing input go directly to the owning parent, at most two sentences and one receipt path. No descendants.
