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
| Grace | <= 1800 s. Poll interval in (0, 60] s. Kills land at least `EXIT_MARGIN` (600 s) plus one poll before the hard stop |

The state directory is fixed at `/mpac/sdicks02/jobs/clasher/lease-20261022/<host>/` (`jobs/`, `logs/`,
`events.jsonl`, `lease-identity.json`, `RELEASE`, `HALT`). The supervisor creates it.

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
  owned processes when the grace ends. For a reclaim, the grace counts from the lease file's mtime, less one poll.
- On SIGTERM the job checkpoints atomically and exits. Choose `--grace` to cover a full checkpoint write.
- Resume: when `status` shows the record `gone`, admit again under the same name. The command must resume from
  its last checkpoint and be idempotent. The supervisor never restarts anything.

## Recovery and fail-closed behaviour

- If the supervisor dies, owned jobs keep running unsupervised and every admit is refused. Restart step 1. The new
  supervisor adopts the records and their persisted (pid, starttime, boot_id) sets and doesn't relaunch anything.
- A record in `intent` or unparsable state blocks every admission and keeps the lease from being marked ended.
  Inspect it with `ps`/`/proc` and the job's token, stop anything live by hand (exact PIDs only), then move the
  file out of `jobs/`.
- Two failed polls in a row: the supervisor writes `HALT`, signals every recorded owned process (TERM, then KILL
  after the maximum grace or before the hard stop) and never touches the lease. Admit stays refused until
  `HALT` is removed by hand after inspection.
- If resources can't be observed (for example a PermissionError on `smaps_rollup`), that counts as a breach: after
  two polls the newest owned job is shed.
- An unreadable lease for two polls stops owned work but never mutates the lease. A lease with a different
  project, coordinator, grantor or start time counts as replaced: our jobs stop and the file is left untouched.

## Known limitations

- A descendant that clears its environment, calls `setsid` and loses its parent all within one poll, before the
  supervisor has seen it, is not owned. Keep children inheriting the environment.
- Ending the lease takes `flock(LOCK_EX)` on the lease file, re-reads and compares the bytes, then does an atomic
  rename, only changing `status`. Editors that don't take the flock can still be lost if they write inside that
  window. It is not a general CAS.
- The reclaim grace is anchored to the lease mtime. A later unrelated touch of the file moves that anchor forward
  (bounded by detection time).
- If GPU telemetry fails at runtime, only GPU jobs are shed, though all admissions are refused. Shedding the
  newest job on a breach is per host and doesn't coordinate with other clasher owners.
- "Clasher process" means our uid with the job token, or a cmdline or cwd under `/mpac/sdicks02/repos/clasher*`
  or `/mpac/sdicks02/jobs/clasher/`. Interactive shells sitting in those directories count toward the caps.
- The supervisor itself isn't watched. Starting it, checking it's live and restarting it is an operator step.
