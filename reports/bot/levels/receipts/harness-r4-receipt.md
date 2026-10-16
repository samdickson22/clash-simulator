# Harness r4 review receipt

2026-10-16T09:41:11Z. Source edits on 127x05, worktree
`/mpac/sdicks02/repos/clasher-bot-levels`, branch `bot/levels`.
No tests, syncs, jobs, exports, commits, or pushes run for this follow-up.
Fresh independent review is required before execution. No pilot-readiness claim.

## Changes

- `run.py`: complete JSON-frozen v2 identity before any successful-row reuse,
  including all-done resumes. Runtime construction is followed immediately by
  the owner's scope installation, then parent policy/model/vocabulary/cache
  preload. Identity binds source/factory/policy/runtime Python/native files,
  referenced weights/prior/gamedata/vocabulary, external env.sh, effective
  behavior variables, runtime pins/path, scope receipt and effective prior,
  loaded config/vocabulary, and B's exact raw/canonical cache digests.
- Cache reads are parsed once into lc.levels; subsequent loads use the frozen
  objects only. No missing exports are built. Known error records are retained;
  absent coverage is rejected. configs.py was not edited.
- Both constructed controllers' actual rt.PRIOR digests are recorded before
  and after play and must equal the restricted scope digest. A mismatch fails
  closed. A secondary prior mismatch preserves an original game traceback.
- Duplicate/missing case indices are rejected. All11 requires A+B. Named
  checks cover complete unique rows/diagnostics, terminal results, zero errors,
  native failures, rejected commands and child failures, controller prior
  equality, command-hash parity, and B roots exercised.
- Errors/failures propagate to child and parent nonzero status. Existing full
  rows/tracebacks survive wait-status recording. Parent SIGTERM cleanup signals
  only waitpid-verified direct children, waits at most 5 seconds before SIGKILL,
  and bounds reaping to another 2 seconds. Forked children cannot unwind into
  inherited parent cleanup. Numbered launch/completion receipts retain identity
  and evidence status.
- `report.py`: reports errors/failures/rejections/prior failures, missing or
  incomplete rows and pairs, duplicate/unexpected rows, identity mismatches,
  bank provenance and parent completion status. Invalid rows are excluded from
  score/paired statistics. Named all11 checks are shared with the runner. CLI
  returns nonzero for incomplete/invalid/unregistered evidence.
- `test_harness.py`: added focused mocked/synthetic tests for input tampering,
  all-done preflight ordering, cache freezing, completeness, parity failure
  modes, controller prior drift, preserved tracebacks, nonzero parent status,
  and verified/bounded signal cleanup. These tests have not been executed.

Only run.py, test_harness.py and report.py were changed in this follow-up.
run.sh is unchanged. bank.py, configs.py, scope.py and owner fixtures were not
edited by this worker. Legacy successful outputs fail closed; use fresh DEV output.

## SHA256

```text
de3a300074aec2a75f75a54fcdf3ea9b8ee48ca75fb952a2ca866f8df7486dfd bot/levels/run.py
831d0b66323de470492dc2335948612a93b829f61fb1d87b0c2a403aa8d0b984 bot/levels/test_harness.py
88358f308f6621573d08f146d57a474e3dd02e0b28e55ffa8c01e5f89d6665a2 bot/levels/report.py
d6fcbbd8151710c7d7a4220db5c9e6790fb9efa336b1a4679154426414363165 bot/levels/run.sh (unchanged)
```

## Suggested next check, only after fresh review and matching-byte deployment

On 127x01, under the existing CPU/nice protocol:

```bash
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
cd "$REPO"
timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -m pytest -q -p no:cacheprovider bot/levels/test_harness.py bot/levels/test_scope.py
```

Only after passing tests and fresh review of exact bytes: retain r3's bounded
DEV envelope (01 only, N=2, parent+2=3 slots, A/B, all11 derivative of DEV base1,
start0/count4, fresh output, outer group timeout15m/kill-after10s). No real pilot
bank, pilot run, or promotion was performed by this worker.

## Coordination

Future/resumed work must batch updates and send parent/owner only actionable
questions, changed blockers/failures, or material results. Default at most three
short lines/80 words, with one receipt path; put details in files. No routine
acknowledgments, healthy polling, or unchanged-state messages. Clarifications use
direct-parent t3_thread_send(mode=auto), never user-input tools. No descendants
were spawned by this worker.
