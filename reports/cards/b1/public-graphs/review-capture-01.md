changesrequested — do not execute these versions.

Reviewed at `a156cf5b117cdbc0cd5045ed3a5d00cbbbc5d259`; exact hashes match:

- `capture_job.sh`: `584270134894a591cf53de4a84bc7a495ee3a41f1e86788ded610c649233845b`
- `capture_mixed.py`: `65d60b2e0ffeffb48b87e4364ec36b6fb8a1824826d0f3ac77cfc9ec4fba390f`

Blocking findings:

1. **Actual game tick/seat are never captured.** [capture_mixed.py:22](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/reports/cards/b1/public-graphs/tools/capture_mixed.py:22) constructs one `Runtime` and wraps only that instance’s `R.root`. `noncore_matches.main()` constructs another `Runtime`; each creates fresh Resources. The module-level graph hook reaches the game, but `context` remains empty. `calls > 0` therefore permits a receipt with no tick/seat. Bind instrumentation to the actual harness Resources and require valid context on every captured call, while preserving the original helper’s arguments, return and exception.

2. **The transfer manifest is incomplete.** [repro-host-inputs.sha256](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/reports/cards/b1/public-graphs/repro-host-inputs.sha256:1) binds eight inputs but neither copied script. The launcher checks `inputs.sha256`, whose complete transferred contents are unspecified. Provide the exact manifest binding both scripts at their fresh-J destinations alongside the eight existing inputs; verify it before and after execution. The six evaluator-file hashes match local frozen files and EVALUATOR.json. Actual 08 dev-root hashes remain a launch precondition.

3. **Cancellation does not establish lease retention.** [HOST-PLAN.md:5](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/reports/cards/b1/public-graphs/HOST-PLAN.md:5) records the outer `cpu_job.sh` PID, while Python runs in a separate session/group. TERM of the outer launch group can terminate the lease-owning supervisor while the wrapper drains Python. Specify a cancellation target and supervisor arrangement that keeps `cpu_job.sh` alive until TERM, five-second grace, KILL and non-zombie quiescence finish. Record wrapper PID and child PGID explicitly.

The public-row whitelist and unchanged-helper rethrow preserve the intended public-only methodology and existing fallback. Seed, deck, tier, seat and tick bound match the historical attempt; deadline timing can change its trajectory.

Before any revised launch, recheck fresh-J absence, exact old PIDs absent, STOP/completion/exit receipts, and all transferred hashes. Authorization remains limited to one baseline capture, with no fix/readiness claim.

The requested b2 `RESULTS.md` path was absent; I read the full available copy under `clasher-cards/reports/cards/r1-cards3/`, its receipts, and the source helper. No edits, SSH, jobs, project imports, tests or delegated descendants were performed.
