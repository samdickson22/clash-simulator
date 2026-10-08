# Lease wrapper v2

For new jobs on 127x09/11/13/14/15/16:

```bash
ssh 127x15 'bash /mpac/sdicks02/repos/clasher-lease/run_v2.sh \
  --max-processes 8 --expected-pss-gb 2 cpu-UNIQUE-LABEL -- \
  /mpac/sdicks02/repos/clasher-lease/repo/.venv/bin/python -B \
  /mpac/sdicks02/repos/clasher-lease/repo/PATH_TO_JOB.py JOB_ARGUMENTS'
```

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

Only `run_v2.sh` and `lease_watch_v2.py` are staged to leased hosts with `rsync -c`.
`test_watch_v2.py`, this guide, deployment evidence and smoke receipts stay here.
Run the test suite on a Clasher home host; process tests refuse command-center 127x05.
