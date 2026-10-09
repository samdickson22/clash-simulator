# Lease wrapper v2

For new jobs on 127x09/13/14/15/16 (11 and 18 are offline):

```bash
ssh 127x15 'bash /mpac/sdicks02/repos/clasher-lease/run_v2.sh \
  --max-processes 8 --expected-pss-gb 2 cpu-UNIQUE-LABEL -- \
  /mpac/sdicks02/repos/clasher-lease/repo/.venv/bin/python -B \
  /mpac/sdicks02/repos/clasher-lease/repo/PATH_TO_JOB.py JOB_ARGUMENTS'
```

The **2026-10-09 r3 hotfix** is selected by `run_v2.sh` and the explicit
`run_v2_current.sh` symlink. Both point to `run_v2_hotfix_20261009_r3.sh`, which
executes the immutable `lease_watch_v2_hotfix_20261009_r3.py`. Original, r1 and r2
supervisor/launcher files remain unchanged on the leased hosts. Existing
supervisors retain their loaded code; only new launches receive the fixes.
Receipts include `wrapper_revision: v2-hotfix-20261009-r3`.

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
signals its child's isolated process group and verified descendants outside that
group: SIGTERM by default, or `CLASHER_CHECKPOINT_SIGNAL=SIGUSR1` for a handler
that **saves and exits**. Linux subreaper adoption covers immediate parent exits
and descendants that call `setsid`. Group signals require a live PID/start-tick
anchor in the original child session; stale/reused identities are excluded.

SIGTERM, SIGINT and SIGHUP to an r2/r3 supervisor request normal cleanup rather than
exiting immediately. The requested signal is forwarded to the full child tree.
Every stop path has a **120-second grace**, configurable with
`--stop-grace-seconds SECONDS`; remaining children then receive SIGKILL. Checkpoint
USR1/USR2 handlers get SIGTERM halfway through that grace. Repeated supervisor
signals do not restart grace. Adopted/new descendants receive the current stop
signal, even after the direct child exits. The supervisor reaps children, writes
the exit receipt (including the direct child's actual status), then releases its
aggregate reservation. Signal receipts have `stop_reason=signal:SIGTERM` (or
`signal:SIGINT` / `signal:SIGHUP`). A stopped supervisor returns 75; `exit_code`
in its receipt is the child's actual status, including negative signal numbers.

V2 jobs stop/checkpoint at **2026-10-09 04:30Z** and must exit by **05:00Z**;
earlier leases tighten both deadlines. Default grace forces surviving trees near
**04:32Z**. A separate hard cutoff starts KILL **60 seconds before** the exit
deadline, even with a longer configured grace, leaving polling/reaping headroom.
Reservations remain until descendants exit. State/exit receipts include
`supervisor_start`, `child_start` (when observed), `child_pgid`, `child_sid` and
`stop_grace_seconds`.

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

Only new versioned launcher/supervisor and operator-helper files are staged with
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

Historical r1 evidence beside this guide:
`wrapper-v2-hotfix-tests-20261008-r1.log`,
`wrapper-v2-hotfix-deployment-20261008-r1.json`, and
`wrapper-v2-hotfix-smoke-127x09-20261008-r1.json`.

## R2/r3 validation and deployment

The identity-verified r1 SIGTERM reproduction ran on home host **127x01**:
supervisor 826006/start 129687106 exited with -15, child 826008/start 129687120
kept running, and no exit receipt was written. Only that synthetic child group
was subsequently terminated. See `wrapper-v2-hotfix-reproduce-20261009-r2.json`.

**58 tests passed on 127x01** (20.534 seconds), covering TERM/INT/HUP to the whole
tree, bounded grace then KILL, direct-child status, receipts, registry cleanup,
leader exit, escaped sessions, launch-time signals, reclaim of multiple trees,
and accelerated scheduled stop/deadline cleanup of every fixture job. Deadline
tests require all child PIDs gone and receipts completed before the accelerated
exit deadline. Test fixtures never use live leases or discover other home jobs.
Run `test_watch_v2.py` in `/tmp/clasher-lease-v2-hotfix-20261009-r2/` on 127x01.

R2 was deployed by checksum rsync to **09/13/14/15/16**. Both launcher symlinks
select r2; checksums of the original and r1 files and identities of running
supervisors remained unchanged. On 09, `lease-v2-hotfix-signal-20261009-09r2`
ran a stubborn three-generation synthetic tree beside live jobs. TERM to its
verified supervisor reached all three children, followed by KILL after a
one-second grace. At **2026-10-09 00:57:32Z**, its receipt recorded
`stop_reason=signal:SIGTERM`, `exit_code=-9`, `status=stopped`; all child PIDs
were gone and the reservation was released. Existing jobs kept running.

Evidence: `wrapper-v2-hotfix-tests-20261009-r2.log`,
`wrapper-v2-hotfix-deployment-20261009-r2.json`,
`wrapper-v2-hotfix-smoke-127x09-20261009-r2.json`,
`wrapper-v2-hotfix-r1-scheduled-20261009-r2.json`, and
`wrapper-v2-hotfix-operator-tests-20261009-r2.log`.

Final review added **r3** without replacing any running r2 code. Linux's
[subreaper attribute is not inherited across fork](https://man7.org/linux/man-pages/man2/PR_SET_CHILD_SUBREAPER.2const.html);
r3 re-enables it in the detached supervisor before launching its child. A new
regression detaches the supervisor, immediately exits the direct child with 7,
and leaves a stubborn descendant in a separate session. R3 adopts, kills and
reaps that descendant, retains exit code 7, writes a stopped receipt, and removes
its registry entry. **59 wrapper tests passed on 127x01** (21.177 seconds), plus
**2 operator fixture tests**. Original/r1/r2 immutable files were verified
unchanged while both launcher symlinks switched to r3 on all five hosts.
See `wrapper-v2-hotfix-tests-20261009-r3.log`,
`wrapper-v2-hotfix-operator-tests-20261009-r3.log`,
`wrapper-v2-hotfix-deployment-20261009-r3.json` and
`wrapper-v2-hotfix-smoke-127x09-20261009-r3.json`.
The final r3 signal smoke on 09 passed at **01:04:18Z** with
`signal:SIGTERM`, child status -9, no orphans and registry release. A second
leased-host smoke passed at **01:05:29Z**: a detached job's direct child exited
with 7 while its stubborn descendant escaped into a separate session. R3 adopted
and killed the descendant, retained status 7 and released accounting. See
`wrapper-v2-hotfix-smoke-detached-127x09-20261009-r3.json`.

## Coordinator procedure for running old wrappers, 2026-10-09

**Do not signal an r1 or v1 supervisor.** Its default signal action exits without
cleaning its child or writing an exit receipt. At 04:30Z, TERM its verified
**child process group**, leaving the supervisor alive to reap and write receipts.
The deployed `stop_wrapped_job_v2_hotfix_20261009_r3.py` helper does this for all
captured v2 jobs (including r1/r2/r3) and wrapped T11 v1 jobs on each host. It verifies PID/start
ticks, child PGID/SID and host identity, also stops adopted descendants outside
the group, sends TERM to all captured trees before waiting, and KILLs verified
survivors after 120 seconds. Reused PIDs receive no signal. It does not edit the
lease, aggregate registry, receipts or running wrapper code. Two operator tests
also passed against immutable r1 on 127x01; read-only capture was verified on
each deployed host. Repeatable fixture tests are in
`test_operator_v2_hotfix_20261009_r3.py`.

At **04:29Z**, capture fresh identities (labels and PIDs can change as shards
finish; do not use the earlier inventory as a stop list):

```bash
lease_operator=/mpac/sdicks02/repos/clasher-lease/stop_wrapped_job_v2_hotfix_20261009_r3.py
for h in 127x09 127x13 127x14 127x15 127x16; do
  ssh "$h" "nice -n 10 python3 -B $lease_operator --capture" > "/tmp/clasher-r1-stop-$h.json"
done
```

At **04:30Z**, run all host stops together. The JSON manifests explicitly bind
each signal to the captured child/supervisor PID and start tick:

```bash
for h in 127x09 127x13 127x14 127x15 127x16; do
  ssh "$h" "nice -n 10 python3 -B $lease_operator --stop --grace-seconds 120" \
    < "/tmp/clasher-r1-stop-$h.json" > "/tmp/clasher-r1-stop-$h.log" 2>&1 &
done
wait
```

Check every host log and every captured label's `jobs/LABEL.exit.json`, then
confirm no live PID/start pair from those trees and no corresponding v2 entry
remain in `jobs/aggregate-v2.json`. Keep a stop command failure or missing receipt
open for inspection; do not erase reservations or invent receipts. Old wrappers
may report `fail` with a negative child exit status when their group is externally
stopped before they observe the scheduled stop; that is a real exit receipt.
No `pkill -f`, owner-path operations, tailscale, crontab or commits are involved.

At the **00:52Z** inventory, perception jobs `t7-epoch-offload-*` on 09/13/14/15
and exploration `cpu-delay-fixes-*` on all five hosts were r1; every known child
used its direct child's isolated group. T11 on 16 was **v1**, label
`t11-v2-main-2026100821-loader6-r3`, supervisor 4092116/start 129174844, child
group 4092118/start 129174849. Its worker argv already specifies stop at **04:20Z**;
the coordinator's 04:30Z group stop remains the backstop if it is still running.
Historical snapshots are retained in `wrapper-v2-hotfix-running-jobs-20261009-r2.json`;
the final helper's fresh read-only captures are in
`wrapper-v2-hotfix-running-jobs-20261009-r3.json`.

R1's internal scheduled path already kills tracked descendants correctly, but
its initial 04:30Z signal reaches only the direct child. Source code sends TERM
to verified descendants at +24 minutes and KILL at +25 minutes (about **04:55Z**),
and has a separate 05:00Z KILL condition. An accelerated r1 test on 127x01 used
a stubborn three-generation tree: parent TERM at 00:53:55.721Z, both descendants
TERM at 00:53:56.177Z, KILL/receipt at 00:53:56.642Z before the test's
00:53:57.614Z exit deadline, with no orphan and an empty registry. The external
group procedure makes all leased child work stop at 04:30Z and gives ample
cleanup time; r1's internal path provides another backstop. V1 has no fixed
04:30Z/05:00Z schedule, so the coordinator must cover T11 explicitly.

The r1 internal proof used a foreground supervisor. Detached r1/r2 supervisors
do not inherit the launcher's subreaper flag and can miss an immediate orphan
that escaped the original group before sampling. Thus the internal-stop evidence
applies to **tracked** descendants; it is not proof for untracked daemons.
The four current r1 perception supervisors are detached; their sampled children
all share their verified child PGID/SID, which the operator backstop stops in
full. Current r1 exploration supervisors are foreground. R3 fixes adoption for
both modes. Capture at 04:29Z and inspect any missing receipt or surviving tree
before the 05:00Z deadline.
