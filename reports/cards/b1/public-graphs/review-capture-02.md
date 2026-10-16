**APPROVE review02 for one baseline capture only**, subject to the launch conditions below. Reviewed fixed HEAD `a156cf5b117cdbc0cd5045ed3a5d00cbbbc5d259`; no remaining blocker in the reviewed flow.

Prior findings are resolved:

- `CaptureRuntime` is installed before harness `main()` imports `Runtime`. Its actual `R.root` establishes tick/seat context and clears it in `finally`. The helper hook is installed after initialization; the helper’s per-call import resolves the patched module function. Original arguments, return value and `PublicGraphError` propagation are preserved.
- The exact manifest binds both scripts and eight host targets. Both script hashes and all six locally available evaluator files match; the four caller hashes also match `EVALUATOR.json`.
- Wrapper-only TERM leaves `cpu_job.sh` waiting while the separate child group receives TERM, five-second grace, KILL if needed, and non-zombie quiescence.

Launch conditions remain mandatory:

1. On **127x08**, establish fresh-J absence and exclusive creation at `/mpac/sdicks02/jobs/clasher/cards/b1/public-graphs-20261016-01`; verify the eight specified old PIDs absent and inspect actual STOP, mixed-complete and exit receipts.
2. Transfer these exact scripts and `repro-inputs.sha256` **as `inputs.sha256`**. Verify all ten targets before and after execution. Actual 08 dev-root files were unavailable locally; their manifest hashes remain host prerequisites.
3. Retain CPU admission **4**, nice **15**, optimization **0**, `NUMBA_DISABLE_JIT=1`, bytecode disabled and library threads **1**. Keep outputs under fresh J.
4. Confirm admitted `wrapper.pid`, `child.pgid` and outer lease PID before cancellation. Send TERM only to the wrapper PID; keep the supervisor alive through drain.
5. Inspect `capture.done`, positive calls, captured boards and actual game summary. Zero reproduced graph failures remains an honest baseline outcome, without a fix or readiness claim.

Recomputed current SHA256s, unchanged at final inspection:

```text
0a16f996a1cee5b69b4472656258017c8c4177b5c26f1e3b7274a7c0f13f601e  HOST-PLAN.md
fecaae0c851d5e6496de2b7859856f56a1355ec508c84a59c0ca546017197c9c  PROGRESS.md
cdf335ad6119a921ed1ff2c6f6dba1d8e4b7f6aa0b1f76540db9bea7a525b76e  repro-inputs.sha256
2bb98ae078c62e62c97a5661ae33c68f2d6c07c0cfad3ebd01619e298ed538ad  repro-host-inputs.sha256
a08439515bf25990ec470956a59922ccc76a9061578f6876d92e84311394b84e  review-capture-01.md
347b608061223992bf13fb3d02e4c4842a608aa3e3f157e776449123b2dd83ef  tools/capture_mixed.py
edeca48cf04b66e40337d30b92af834c6c4aeeb8d04b331643193256f5093bec  tools/capture_job.sh
```

Read the requested r1-cards3 phase report. Python AST and shell syntax checks passed. No edits, engine imports, runtime/project tests, SSH, jobs or descendants were performed.
