# Lease supervisor runbook (127x09 / 127x12 / 127x17, lease ends 2026-10-25T07:53:00Z)

`lease_supervisor.py` is stdlib Python 3.8. Run it with the host's `/bin/python3` from a reviewed, immutable
checkout. The read-only owner-lease design and R34 fixes require a fresh independent R35 review before any
watcher or workload launch. No RL launch is approved. Don't use `run_guarded.sh`
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
`events.jsonl`, `lease-identity.json`, `deadline-bound.json`, `status.json`, `ended.json`, `RELEASE`, `HALT`).
The supervisor creates it without following symlinks.
`jobs/`, `logs/`, records and persisted stop/log paths must satisfy the same rule. Unsafe records become
`uncertain` before adoption; admissions and our ended receipt remain blocked. File writes use pinned parent directory
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
# 3. Finish early: drain owned jobs, then write our own ended.json receipt.
/bin/python3 bot/pretrain_v1/lease_supervisor.py release
```

## Checkpoint/resume contract (every admitted command must honour it)

- Environment: `CLASHER_LEASE_STOP_FILE`, `CLASHER_LEASE_STOP_BY_UTC` (the latest time a stop starts),
  `CLASHER_LEASE_JOB` (the ownership token; don't strip it from children). `CUDA_VISIBLE_DEVICES` is empty unless
  `--gpu-gb` > 0.
- Stop sequence (on reclaim, release, expiry, sustained resource breach, a replaced lease or repeated supervisor
  errors, refused=true or sustained lease unreadability): the supervisor writes the stop file and saves the
  stopping record before SIGTERM, then SIGKILLs remaining owned processes when their grace ends. For reclaim
  or refusal, grace counts from our first observation of either true flag, less 60 s. File mtime is never used.
  Every poll tightens an existing kill deadline against the retained lease end and flag deadline, including
  after restart. A grace <= 60 s can require immediate SIGKILL; choose a larger grace for checkpointing.
- On SIGTERM the job checkpoints atomically and exits. Choose `--grace` to cover a full checkpoint write.
- Resume: when `status` shows the record `gone`, admit again under the same name. The command must resume from
  its last checkpoint and be idempotent. The supervisor never restarts anything.

## Recovery and fail-closed behaviour

- If the supervisor dies, owned jobs keep running unsupervised and every admit is refused. Restart step 1. The new
  supervisor adopts validated records and their persisted (pid, starttime, boot_id) sets and doesn't relaunch
  anything. A scan omission retains an owned identity until a direct process check confirms exit or identity
  mismatch. Every drain rechecks gone records and tokens with a fresh scan before writing our ended receipt.
- A record in `intent` or unparsable/unsafe state blocks every admission and blocks our ended receipt.
  A fully validated current-boot intent can be recovered only when a fresh scan finds its ownership token.
  Otherwise inspect it with `ps`/`/proc` and the job's token, stop anything live by hand (exact PIDs only), then
  move the file out of `jobs/`.
- Every validated lease deadline and first observed reclaim/refused origin is retained before later poll work, in memory and
  `deadline-bound.json`. Recovery and restart keep the most restrictive observed limits. Emergency recovery
  creates the contained job stop file and persists its stopping state/deadline before signalling it, so atomic
  checkpointers receive the same stop-file-before-TERM contract after lock or work-budget failures.
- `generation.lock` serializes admission's final stop gate, intent/spawn/publication, normal record updates and
  emergency record updates. Emergency writes HALT first. Admissions recheck stop state before and after spawn.
  An emergency that times out on this lock may notify and signal validated current-boot identities or freshly
  scanned tokens, but cannot write job records. It never overwrites a newer generation with a stale snapshot or
  adopts an empty gone record. A child created during recovery retains its durable intent token and is stopped
  before admission returns. Failed job-record publication still sends exact signals after the stop file exists.
  The first recovery origin is retained separately in `deadline-bound.json`, including across failed saves and
  restart. Normal polling merges this state under `observation.lock` before saving, so a concurrent recovery
  origin cannot be erased. Intent records without observed owned work continue blocking the ended receipt.
- Two failed polls in a row: the supervisor writes `HALT`, signals every recorded owned process (TERM, then KILL
  after each record's grace or persisted kill deadline, or before the retained lease end) and never writes the lease. Admit stays refused while
  HALT or a persisted global stop request remains; clearing HALT alone never clears a latched stop. Emergency recovery validates record schema and current boot before
  signalling any saved PID/starttime pair. Old-boot records are never signalled.
- If resources can't be observed (for example a PermissionError on `smaps_rollup`), that counts as a breach: after
  two polls the newest owned job is shed.
- A missing, unreadable, invalid-JSON or incomplete-schema snapshot refuses admission immediately. Existing
  jobs retry on the next poll, with no HALT or reclaim inferred from that read failure. The first failed-read
  observation time is persisted across restart. Only a fully validated readable snapshot resets it. At exactly
  300 seconds jobs can continue; more than 300 seconds of observed unreadability starts checkpoint/draining
  with the normal job grace. The known lease expiry and hard stop still apply during this retry window.
  Decoder depth, Unicode and integer-conversion errors follow this same retry path. Reads are bounded to 1 MiB;
  integer tokens are bounded to 1024 characters on Python 3.8 and 3.12. Parsed caps outside the finite numeric
  range are invalid. Parsed true flags still latch before schema rejection. Emergency uses cached deadlines
  even when its external lease reload or validation fails.
- A valid snapshot with a different project, coordinator, grantor or start time stops only our jobs. An inode
  change alone is expected during atomic replacement and does not mean lease identity changed.

## Read-only owner lease and our completion receipt

The owner lease at `/mpac/sdicks02/fleet-leases/<host>.json` is strictly read-only. The watcher never writes,
truncates, renames, unlinks or locks it. RoadForge and other editors may use atomic rename, in-place writes,
flock or no locks. No change to their editor protocol is required. Each poll opens the lease by PATH anew,
reads at most 1 MiB, closes the handle, then parses the snapshot. There is no cached descriptor or inode check.
A replacement during a read may leave that read seeing the old snapshot; the next poll reopens the path.

Any parsed dictionary containing literal `"reclaim": true` or `"refused": true` latches stopping immediately,
before checking its project, identity, dates or other schema fields. For example, `{"refused": true}` is enough.
The first observation time, reason, snapshot hash and flags are persisted before later fallible work. No later
edit, cleared flag, file removal or restart can erase that stop request or extend its deadline. `refused`
uses reason `refused` and the same <=30-minute grace. Malformed JSON is unreadable, even if its text contains a
flag-like fragment. A valid but incomplete dictionary containing only false flags is also unreadable and does
not reset the five-minute timer. Missing reclaim is never interpreted as true.

The supervisor writes `<state>/<host>/status.json` on completed polls. Once stopping is required, it writes
`<state>/<host>/ended.json` and exits only after every validated job is gone and a fresh final scan finds no
owned work. Intent or uncertain records block this receipt. Receipts contain the current boot, job states,
`jobs_drained`, the original lease identity, observed lease path/SHA-256/flags, the latched trigger snapshot and
`owner_lease_updated: false`. A missing or unreadable path has no parsed flags; readable invalid JSON still has
a snapshot hash. This receipt describes our jobs alone. It does not assert that the owner lease is ended or
that another owner's work has drained. The coordinator can merge our ended status using its own editor.
There is no additional external messaging requirement; Sam can relay a coordinator request by writing a true
reclaim flag to the lease path.

## Poll timing

`--poll` accepts (0, 60] seconds. Actual poll starts use fixed monotonic deadlines spaced at most 30 s apart.
A poll has a 25 s wall-time budget, including scanning, PSS, logging and lock waits. Only our state/observation
locks use flock, with a 5 s bound; GPU telemetry has a 5 s subprocess timeout. More than 5 s of scheduler
lateness, a work-budget overrun or an own-lock timeout triggers emergency draining and HALT. The 30 + 5 + 25 s
bounds allow at most 60 s between lease checks while supervision can run. Detection and kill calculations
reserve the full 60 s regardless of `--poll`. Tests cover elapsed spacing and blocked own locks/telemetry.
An unrelated scan/resource/cadence failure remains a separate reason to drain, even while a lease read is in
its retry window. Emergency recovery retries the lease without external writer locks, retains every known
deadline and writes checkpoint stop files before signalling. It enforces cached bounds on saved identities
before reloading the external lease, then tightens them again after a successful read. A decoder or read budget
failure cannot preempt those cached stops. Unreadability alone does not force immediate KILL.

An OS suspension or uninterruptible kernel I/O can defeat user-space timers. On resumption, a missed monotonic
deadline fails closed. Operator recovery remains necessary if the supervisor cannot execute.

## Known limitations

- A descendant that clears its environment, calls `setsid` and loses its parent all within one poll, before the
  supervisor has seen it, is not owned. Keep children inheriting the environment.
- A flag must be visible in a snapshot we read. A writer that sets and clears it entirely between polls can
  escape observation. After first observation its persisted deadline only tightens. External mtime and inode
  changes cannot reset the origin. The 60 s reserve covers detection plus subsequent kill checks within the
  1800 s allowance, assuming a request stays visible until observed.
- If GPU telemetry fails at runtime, only GPU jobs are shed, though all admissions are refused. Shedding the
  newest job on a breach is per host and doesn't coordinate with other clasher owners.
- "Clasher process" means our uid with the job token, or a cmdline or cwd under `/mpac/sdicks02/repos/clasher*`
  or `/mpac/sdicks02/jobs/clasher/`. Interactive shells sitting in those directories count toward the caps.
- The supervisor itself isn't watched. Starting it, checking it's live and restarting it is an operator step.

## Operational boundary for this revision

This implementation starts no watchers, extracts no archives, stages no files on leased hosts and touches no
remote host or production lease. The verified archives already under 09/12/17 jobs/clasher remain unextracted.
The main owned-compute allocation remains 01 next-M100, 02 next-S100 and 08 M25. The 07 audits are complete. Hosts 13-16 remain
another owner's; 11/18 are excluded. A later independent review must cover this design change. R33's GO for
cooperating editors does not cover it, and R34 was NO-GO. No leased BC resume, GL/GPU workload or full RL harness GO is implied.
