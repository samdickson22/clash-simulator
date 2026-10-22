# Lease supervisor runbook (127x09 / 127x12 / 127x17, lease ends 2026-10-25T07:53:00Z)

`lease_supervisor.py` is stdlib Python 3.8. Run it with the host's `/bin/python3` from a reviewed, immutable
checkout. Review GO is required before any real workload, and RL launch is not approved. Don't use `run_guarded.sh`
on these hosts, because its process-group kill can hit processes we don't own.

## Limits enforced

| Limit | Value |
|---|---|
| Hosts | 127x09, 127x12, 127x17 only. The lease path is fixed at `/mpac/sdicks02/fleet-leases/<host>.json`, with no override |
| Clasher processes (all owners) | 96 on 09/17, 64 on 12, or the lease's `max_workers` if lower |
| Aggregate clasher PSS | 64 GiB, or the lease's `pss_cap_gb` if lower |
| Admission | MemAvailable minus the job's PSS > 28 GiB, load1 <= 90, GPU free minus the job's GPU GiB >= 8 (CPU-only jobs too) |
| nice | >= 10 for the supervisor, the CLI and every owned process (raised on each poll) |
| Grace | <= 1800 s, including a reserved 60 s for detection/kill checks. Kills land at least `EXIT_MARGIN` (600 s) plus 60 s before the current lease deadline |

The state directory is fixed at `/mpac/sdicks02/jobs/clasher/lease-20261022/<host>/` (`jobs/`, `logs/`,
`events.jsonl`, `lease-identity.json`, `RELEASE`, `HALT`). The supervisor creates it without following symlinks.
`jobs/`, `logs/`, records and persisted stop/log paths must satisfy the same rule. Unsafe records become
`uncertain` before adoption; admissions and lease release remain blocked. File writes use pinned parent directory
descriptors and non-following opens. These checks contain supervisor writes; they do not sandbox admitted commands.

## Commands (on the leased host)

```bash
C=/mpac/sdicks02/repos/<reviewed-clasher-checkout>; S=/mpac/sdicks02/jobs/clasher/lease-20261022
mkdir -p $S && cd $C
# 1. Watcher first, one per host (a second one is refused). It must be live before any admit, staging included.
setsid nohup /bin/python3 bot/pretrain_v1/lease_supervisor.py supervise --poll 30 \
  >> $S/supervisor-$(hostname -s).log 2>&1 < /dev/null &
/bin/python3 bot/pretrain_v1/lease_supervisor.py status        # expect supervisor_live: true
# 2. Admit work. Admissions are serialized per host; names are unique while a record is not `gone`.
/bin/python3 bot/pretrain_v1/lease_supervisor.py admit --name stage-extract-01 --workers 1 --pss-gb 2 \
  --grace 120 --cwd $C -- tar -xf /mpac/sdicks02/jobs/clasher/<archive>.tar -C /mpac/sdicks02/repos/<dest>
# 3. Finish early: stop owned jobs (contract below), then mark the lease ended.
/bin/python3 bot/pretrain_v1/lease_supervisor.py release
```

## Checkpoint/resume contract (every admitted command must honour it)

- Environment: `CLASHER_LEASE_STOP_FILE`, `CLASHER_LEASE_STOP_BY_UTC` (the latest time a stop starts),
  `CLASHER_LEASE_JOB` (the ownership token; don't strip it from children). `CUDA_VISIBLE_DEVICES` is empty unless
  `--gpu-gb` > 0.
- Stop sequence (on reclaim, release, expiry, sustained resource breach, a replaced lease or repeated supervisor
  errors): the supervisor writes the stop file, sends SIGTERM to every owned process, then SIGKILLs the remaining
  owned processes when the grace ends. For a reclaim, the grace counts from the lease file's mtime, less 60 s.
  Every poll tightens an existing kill deadline against the current lease end and reclaim deadline, including
  after restart. A grace <= 60 s can require immediate SIGKILL; choose a larger grace for checkpointing.
- On SIGTERM the job checkpoints atomically and exits. Choose `--grace` to cover a full checkpoint write.
- Resume: when `status` shows the record `gone`, admit again under the same name. The command must resume from
  its last checkpoint and be idempotent. The supervisor never restarts anything.

## Recovery and fail-closed behaviour

- If the supervisor dies, owned jobs keep running unsupervised and every admit is refused. Restart step 1. The new
  supervisor adopts validated records and their persisted (pid, starttime, boot_id) sets and doesn't relaunch
  anything. A scan omission retains an owned identity until a direct process check confirms exit or identity
  mismatch. Every release rechecks gone records and tokens with a fresh scan before ending the lease.
- A record in `intent` or unparsable/unsafe state blocks every admission and keeps the lease from being marked ended.
  Inspect it with `ps`/`/proc` and the job's token, stop anything live by hand (exact PIDs only), then move the
  file out of `jobs/`.
- Every successfully read lease deadline and reclaim origin is retained before later poll work, in memory and
  `deadline-bound.json`. Recovery and restart keep the most restrictive observed limits. Emergency recovery
  creates the contained job stop file and persists its stopping state/deadline before signalling it, so atomic
  checkpointers receive the same stop-file-before-TERM contract after lock or work-budget failures.
- Two failed polls in a row: the supervisor writes `HALT`, signals every recorded owned process (TERM, then KILL
  after each record's grace or persisted kill deadline, or before the hard stop) and never touches the lease. Admit stays refused until
  `HALT` is removed by hand after inspection. Emergency recovery validates record schema and current boot before
  signalling any saved PID/starttime pair. Old-boot records are never signalled.
- If resources can't be observed (for example a PermissionError on `smaps_rollup`), that counts as a breach: after
  two polls the newest owned job is shed.
- An unreadable lease for two polls stops owned work but never mutates the lease. A lease with a different
  project, coordinator, grantor or start time counts as replaced: our jobs stop and the file is left untouched.

## Lease checks and editor protocol

`--poll` accepts (0, 60] seconds. Actual poll starts use fixed monotonic deadlines spaced at most 30 s apart.
A poll has a 25 s wall-time budget, including scanning, PSS, logging and lock waits. State/lease lock acquisition
is bounded at 5 s, and GPU telemetry has a 5 s subprocess timeout. More than 5 s of scheduler lateness, a work
budget overrun or a lock timeout triggers immediate emergency draining and `HALT`. The 30 + 5 + 25 s bounds
reserve at most 60 s between lease checks while supervision can run. Detection and kill calculations always
reserve the full 60 s, regardless of `--poll`. Tests cover real elapsed spacing and blocked locks/telemetry.
An OS suspension or an uninterruptible kernel I/O operation can defeat user-space timers; on resumption a missed
monotonic deadline fails closed. Operator recovery remains necessary if the supervisor itself cannot execute.

The lease uses its existing inode as the shared lock, with no new lock file outside the allowed state paths:

1. Every reader opens the lease without following symlinks, takes `flock(LOCK_SH)`, verifies the handle's
   device/inode still matches the path, reads/parses the complete JSON, then closes the handle.
2. Every editor opens with `r+` **without truncating**, takes `flock(LOCK_EX)`, and verifies the same device/inode
   match. If it differs, close and reopen/retry. Read the latest JSON only after acquiring the lock, change only
   the intended fields, then seek to zero, write the complete JSON, truncate, flush and `fsync` before closing.
3. Never rename, replace, unlink or truncate the lease before acquiring its lock. Waiting editors must update
   the same inode and must re-read after acquiring the lock. The supervisor changes only `status` to `ended`
   under this protocol, preserving every other current field.

All lease editors and readers must adopt this protocol before operational use. The code does not claim atomic
CAS against noncooperating writers: ignoring the lock, writing an old snapshot, or replacing the inode can lose
updates. A crashed in-place edit can leave partial JSON; shared readers cannot see an in-progress cooperating
edit, and an incomplete edit after a crash fails closed as an unreadable lease. Lock waits are bounded; inode
mismatches retry when ending a lease and otherwise count as unreadable. No production lease is changed as part
of qualifying this implementation.

## Known limitations

- A descendant that clears its environment, calls `setsid` and loses its parent all within one poll, before the
  supervisor has seen it, is not owned. Keep children inheriting the environment.
- The reclaim grace is anchored to the lease mtime. A later unrelated touch of the file moves that anchor forward
  before initial detection, bounded by detection time. Once a job is stopping, its persisted kill deadline
  only tightens, including across restarts.
- If GPU telemetry fails at runtime, only GPU jobs are shed, though all admissions are refused. Shedding the
  newest job on a breach is per host and doesn't coordinate with other clasher owners.
- "Clasher process" means our uid with the job token, or a cmdline or cwd under `/mpac/sdicks02/repos/clasher*`
  or `/mpac/sdicks02/jobs/clasher/`. Interactive shells sitting in those directories count toward the caps.
- The supervisor itself isn't watched. Starting it, checking it's live and restarting it is an operator step.
