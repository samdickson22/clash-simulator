# Lease wrapper v2

For new jobs on 127x09/11/13/14/15/16:

```bash
ssh 127x15 'bash /mpac/sdicks02/repos/clasher-lease/run_v2.sh \
  --max-processes 8 --expected-pss-gb 2 cpu-UNIQUE-LABEL -- \
  /mpac/sdicks02/repos/clasher-lease/repo/.venv/bin/python -B \
  /mpac/sdicks02/repos/clasher-lease/repo/PATH_TO_JOB.py JOB_ARGUMENTS'
```

The **2026-10-08 r1 hotfix** is selected by `run_v2.sh` and the explicit
`run_v2_current.sh` symlink. Both point to `run_v2_hotfix_20261008_r1.sh`, which
executes the immutable `lease_watch_v2_hotfix_20261008_r1.py`. The original
`lease_watch_v2.py` stays in place for running supervisors, and the original
launcher is retained as `run_v2_pre_hotfix_20261008_r1.sh`. Existing supervisors
retain their loaded code; only new launches receive the fixes. Receipts include
`wrapper_revision: v2-hotfix-20261008-r1`.

Declare the **whole job's maximum processes and summed PSS**, including its
supervisor and every descendant. Allow at least two processes. PSS GB is decimal
and is enforced as the job's memory cap. Add `--gpu` for GPU jobs. Admission is
synchronous; admitted jobs detach, run from `clasher-lease/repo/`, inherit the
lease environment and run at nice ≥10. Use fresh labels. Rejections return nonzero
and write a failure receipt without launching work. `--foreground` stays attached.

Combined Clasher limits: **80 processes on 09/13/14/15**, **96 on 11/16**, **16
with a console user**, and **64 GB summed PSS**. Tighter policy/lease limits win.
GPU jobs require GPU permission and ≥8192 MiB free. The 80-process bound follows
this task's stricter headroom requirement; current policy tables/leases say 96.

Admission uses a separate `jobs/aggregate-v2.lock` to reserve declared maxima,
plus measured v1/unwrapped Clasher usage. PSS is summed once per verified PID.
The v1 lock, files and processes are preserved. Process tracking runs each second;
PSS, policy, lease and console controls are checked every 60 seconds and on each
admission. These are sampled backstops; workers must cap their own pools and memory.
Keep subprocesses in the supervised tree; do not launch untracked daemons.

Discovery admits only argv paths under `/mpac/sdicks02/repos/clasher/`,
`/mpac/sdicks02/repos/clasher-*/`, `/mpac/sdicks02/jobs/clasher/`,
`/mpac/sdicks02/envs/clasher-*/`, or `/mpac/sdicks02/tmp/{t5-,t11-,v4-}*/`.
Path-component boundaries are enforced. Roader repositories, `roader-shell`,
`.roadforge`, and desktop daemons are excluded even when another argument names
a Clasher path. Previously persisted external entries are reclassified on each
full check. Discovery reads only same-UID `/proc` argv for classification; it
does not open Roader repositories, jobs or caches. Nice checks and aggregate
process/PSS measurements cover Clasher only. Roader's separate declared lease
budget (≤32 processes on 09/13/14/15) is not measured or added to Clasher usage;
the existing 80-process Clasher caps remain in force.

V2 reservations survive an empty child PID set while the verified supervisor
PID/start time is alive. A missing own registry entry follows the normal child
reap/exit-receipt path and preserves the actual child status. New supervisors
use Linux child-subreaper mode to adopt and track descendants even if their
parent forks and immediately exits. Descendants are cleaned up before release;
the direct child's exit code remains recorded. Live old supervisors retain their
original behavior until their existing jobs finish.

Aggregate overage stops the newest admitted v2 job first. Reclaim, refusal, missing
or expired leases, and failed checks request stop from every v2 job. Each supervisor
signals only its own job: SIGTERM by default, or `CLASHER_CHECKPOINT_SIGNAL=SIGUSR1`
for a handler that **saves and exits**. Remaining descendants receive SIGTERM at
24 minutes and SIGKILL at 25 minutes, preserving v1's ≤26-minute cleanup bound.
V2 jobs stop/checkpoint at **2026-10-09 04:30Z**, with forced cleanup by **05:00Z**;
earlier leases tighten those deadlines. Reservations remain until descendants exit.

Inspect `jobs/LABEL.{log,launch.pid,state.json,exit.json}`. State reports aggregate
usage; exit receipts report declarations, admission usage and sampled peaks.
No exit receipt means unfinished. Host accounting is in `jobs/aggregate-v2.json`.

Some leased hosts lack `/mpac/sdicks02/cc/FLEET-SHARING.md`. V2 bundles the policy
limits read on 127x05; receipts identify their source/hash. A local policy supersedes
the snapshot; malformed/unreadable local policies fail closed. Redeploy policy
changes to hosts lacking that file. Live lease and console checks always run.

**Coordinator handoff:** V1 jobs keep their existing reclaim handling and need
the coordinator's planned **04:30Z stop / 05:00Z exit**; their unchanged code has
no fixed early-return deadline. V2 removes only this coordinator's reclaimed/expired
lease after **all** tracked Clasher jobs have exited. It never stops v1 or owner jobs.

Only new versioned launcher/supervisor files are staged to leased hosts with
`rsync -c`; launcher symlinks are switched atomically after checksum verification.
`test_watch_v2.py`, this guide, deployment evidence and smoke receipts stay here.
Run the test suite on a Clasher home host; process tests refuse command-center 127x05.
The hotfix suite runs on 127x01 from `/tmp/clasher-lease-v2-hotfix-20261008-r1/`
using synthetic lease/registry fixtures. It covers zero/nonzero fast exits,
forced missing-entry races, immediate fork/parent-exit cleanup, two concurrent
fast admissions, capacity reservation, PID reuse, argv classification and stale
Roader-entry removal, alongside the existing reclaim and resource-limit tests.

Hotfix validation: **47 tests passed on 127x01** (13.644 seconds). Versioned
files were checksum-verified and launchers switched on all six hosts. On 127x09,
`lease-v2-hotfix-fast-20261008-09r1` ran `/usr/bin/true` and wrote a clean `pass`,
exit-code-0 receipt at **2026-10-08 23:42:57Z**, without a supervision error or
Roader-related admission refusal. Its supervisor/child exited and its registry
reservation was removed. The previously cited epoch-grid job completed normally
at 23:41:44Z, before staging, with exit code 0 and no stop reason.

Evidence beside this guide:
`wrapper-v2-hotfix-tests-20261008-r1.log`,
`wrapper-v2-hotfix-deployment-20261008-r1.json`, and
`wrapper-v2-hotfix-smoke-127x09-20261008-r1.json`.
