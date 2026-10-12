# END 08 r2 failure diagnosis (r1)

Written 2026-10-12 ~03:38Z on 127x05. This was a read-only diagnosis: no SSH, no edits to repo or job trees, no backends. Code was read via `git show origin/main:`. The six e4v3 files match the r2 `fleet-identity.json` measurement_files SHAs (fleet_reference c767a6e0, replay_load 1d0e12cc, telemetry 808d6fab, fleet_validity 94d0e7f2, fleet_pool 572ad682, measure_tiers 6066228b). Local computation was only `nice -n 19 taskset -c 63 python3 -I`. Scratch was /tmp/sdicks02-diag-08r2, holding copies of fleet_validity and receipts used to run the frozen `classify_attempt`.

## Verdict

**This is a race in E4's guard adapter, not host interference.** The guard decides ownership from one `/proc` snapshot, then runs the T1 census on a second, later snapshot. The first 1 Hz sample after admission landed on the burst in which the 10 FleetBackground workers are spawned. Workers spawned between the two snapshots were E4's own children, but the guard treated them as `foreign_compute`.

The launch environment is not implicated (nice, SSH, console). On 08 the race is close to deterministic, because 08's admission guard call takes longer than 1 s. A6 on 01 passed by only about 0–20 ms.

## 1. Root cause

### How ownership is registered

- `fleet_reference.py:46`: `owned = Array([E4 pid, 0×10, 0])`.
- `:125`: `monitor.start(); owned[-1]=monitor.pid`.
- `:126`: the admit checkpoint.
- `:127-129`: `FleetBackground(...)` and `with background_load` → `replay_load.py:131-133` starts the 10 spawn workers, then waits for ready (up to 600 s), calling `check()` → `check_external` = `check_monitor` (`replay_load.py:227-228`).
- `:130`: `owned[index]=worker.pid` runs only after `__enter__` returns.

The `owned` array lagging behind is **not** the defect by itself. The guard takes `roots = owned ∪ {monitor}` (`fleet_validity.py:143`) and adds every descendant through `owned_tree` (`fleet_validity.py:21-37`), which follows ppid. Workers whose ppid is the E4 pid are therefore owned *if they are in the snapshot*. This is why the per-process `Census.owned` flag in A6 lagged, while `owned_pid_start_ticks` still listed all 13 pids.

### The defect: two snapshots in `ReportingGuard.__call__`

1. `fleet_validity.py:135`: `current = self.audit.processes()` is snapshot 1. At `:144`, `current_owned = owned_tree(current, …)`.
2. `fleet_validity.py:155`: `self.audit.census(...)` calls `host_audit.processes()` again (`host_audit.py:151`, plus identity_collect re-scans at `:160-175`). This is snapshot 2, which is later.
3. `host_audit.foreign_compute` (`host_audit.py:70-93`) flags **any** process whose argv0 starts with `python` unless `own_process` matches. It applies no CPU threshold, so the 5–19 tick counts are irrelevant.
4. `own_process` is overridden at `fleet_validity.py:115-116` to mean `pid in self.current_owned`, i.e. snapshot 1.

A worker forked after snapshot 1 passed its pid slot but before snapshot 2 is therefore foreign. `reason=foreign_compute` (`:180`) → `passes=False` → `telemetry.py:206-207` raises in the monitor → `check_monitor` (`fleet_reference.py:58-59`) raises `FleetTechnicalError('validity_census')`, called from `replay_load.py:137` inside `__enter__`.

### Evidence from r2

The r2 capacity row 0 is the only row. It has `phase=reference-warmup` and is the first 1 Hz sample, not the admission receipt.

- Its `owned_pid_start_ticks` contains 9 pids: E4 1316329, the resource tracker 1316604, monitor 1317794, and **workers 1317815–1317820**.
- `foreign_compute` contains exactly **workers 1317821–1317824**:
  - start_ticks 157508911–917;
  - ppid is E4, pgid is the wrapper 1316322;
  - affinity [0..4], inherited before `sched_setaffinity`;
  - snapshot_monotonic 1575089.417.
- The scan reaches high pids last, because `/proc` iterates in ascending pid order. Snapshot 1 reached pid 1317820 (started at tick 909 ≈ 1575089.09) but not 1317821 (tick 911 ≈ .11). The census snapshot reached them at .417.

`guard-admission.json` passed cleanly with 3 owned pids: E4, the tracker and the monitor. Its `foreign_compute` and `foreign_active` lists are empty.

### Timing: why the first sample hits the spawn

The monitor's `origin` is set when `monitor_worker` starts. The admit request is already waiting, so `control()` runs the admit guard call immediately. If that call takes D seconds:

| | r2 on 08 | A6 on 01 |
|---|---|---|
| admit-guard duration D (= interval_seconds − gap) | **1.24 s** | **0.928 s** |
| first sample `now` vs admit reply | +0.001 s | +0.072 s |
| worker spawn burst (start_ticks; boottime ≈ monotonic) | .05 → .17, ~12 ms/worker | .88 → 1.00, ~12 ms/worker |
| snapshot 1 reached high pids at | now + ~40–60 ms (mid-burst) | after now + ~49–59 ms (after the burst) |
| result | 4 foreign → FAIL | all 13 owned → PASS (margin ≈ 0–20 ms) |

The rule:
- If D ≥ 1 s, the overdue sample fires the moment the reply is sent, at the same instant E4 starts spawning, so the workers are certain to straddle the two snapshots.
- If D < 1 s, the sample fires 1 − D after spawning starts. The test passes only if 1 − D + L > S, where S ≈ 120 ms is the spawn span and L ≈ 50 ms is the time snapshot 1 takes to reach the high pids. That means roughly **D < 0.93 s**.

A6 had D = 0.928.

### Why 08 is slower

At admission, 08 is about 0.3 s slower than 01, and the reasons are structural:
- The pre-census part takes ~0.37 s on 08 against ~0.24 s on 01. That part includes `seed.admit`, and the OP-5 08 seed/join (`fleet_validity.py:103-104`) applies to 08 only.
- The census part takes ~0.87 s on 08 against ~0.69 s on 01 (the admission `ssh_family_sample.seconds`). 08 also meters an idle service, `v4-validation-cache-renewed-20261010-08r1`.

### Launch environment: not implicated

- Wrapper and E4 ran at nice 10, SCHED_OTHER.
- `ssh_connection_snapshot` on the workers ("129.65.221.15 … .18 22") is inherited SSH_CONNECTION from the launch session. `foreign_compute` doesn't use it, ssh_family core_fraction was 0, and the console count was 0.
- The host had 1280 processes and load ≈1.1, about the same as A6 (1288 processes, load ≈1.0).

### Rare secondary hazard (same code)

Python 3.12 spawn uses `_posixsubprocess` (vfork/exec). A snapshot taken in the pre-exec window would record the parent's cmdline. `known_identity.setdefault` (`fleet_validity.py:150`) would then permanently de-own that pid after exec. That window is microseconds wide and wasn't observed, but the fix below should cover it.

### Repeat risk for r3 as is

**It is timing-dependent but strongly biased toward failure on 08. I estimate about 80–95% failure.**
- Failure happens whenever D ≳ 0.93 s. On 08 D was 1.24 s, and the reasons for the extra time are structural.
- 01 itself sits right at the threshold, with A6 at 0.928 s.
- The only source of a pass is run-to-run variance in D, for example warmer caches on a second run. A 25% drop in D can't be counted on.
- A failure happens about 5 minutes after launch, at admission + ~1 s, before any warmup or timing. So it carries no timing or selection information.

## 2. Pool and release rules

**r2 is index 0, counted, and earns exactly one technical repeat.**
- Under RF1 item 4 (536bf5bd) and C1 (15b10ef2), r2 is 08's first counted attempt. r1 is the exempt pre-identity refusal: `fleet_technical_cause=null`, files = {failure.json}, refused at `fleet_reference.py:34`.
- r2 doesn't meet the C1 exemption: it sealed `fleet-identity.json` and has `fleet_technical_cause='validity_census'`. So L1 applies (9f919cb3): it is assembled and counted.

**Running the frozen `fleet_validity.classify_attempt` on the received r2 seal gives** `{'passes': False, 'technical_repeat_candidate': True, 'exactness_failure': False, 'cause': 'validity_census'}`.
- The receipt status is failed.
- `validity_census` is in the allowed set (`fleet_validity.py:296`).
- It is substantiated because `capacity.jsonl` row 0 has `passes: False` (`:300-307`).
- The error text has no exactness keywords, and exactness-tiers and belief-exactness both pass.
- So `fleet_pool.run` (`fleet_pool.py:114-121`) accepts r2 as a non-final repeat candidate.
- `release_reference` (`:223-224`) requires every attempt but the last to have passes=False and technical_repeat_candidate=True. r2 satisfies this.

**r3 is the single technical repeat.** `fleet_pool.py:96-97` allows at most 2 attempts per host, and `release_reference.py:197` requires 1–2. C2 says no second exempt refusal is available for 08.

**If r3 also fails:**
- `fleet_pool.py:122-123` raises "No passing attempt; second failure requires outcome-blind amendment".
- END mode can't exclude a counted host (`fleet_pool.py:59-60`; `counted_hosts` = [127x01, 127x08]). The **whole END pool and release is blocked**, not just 08, until an outcome-blind amendment is made. 01's result alone can't be pooled.
- Both 08 attempts must stay in the root and descriptor (`release_reference.attempt_roots`), so a third launch is impossible without that amendment.

## 3. Mitigation without code changes

**No launch-procedure lever reliably lowers the risk.**
- The race depends on the admit guard call taking less than ~0.93 s. That duration is internal to the frozen guard: T1 census, OP-5 seed admission and idle-service metering, all pinned.
- Spawn timing and order are fixed in code.
- Marginal, unreliable tilts:
  - have no SSH or ControlMaster sessions to 08 open at admission;
  - have no extra processes of ours on 08;
  - possibly launch with warm caches.

  None of these is likely to remove ~0.3 s, and C5 limits what we can do on the host anyway.

**A code fix is the only real fix.** The minimal change is to the guard adapter (`fleet_validity.py`, `ReportingGuard.__call__`, immediately after line 155). It re-derives ownership on the census snapshot, so E4 descendants that appear between the snapshots are owned. Pid-reuse protection through `known` start_ticks is kept.

```diff
         after, foreign, active, cpu = self.audit.census(self.job, self.previous, block_ids=list(self.blocks))
+        # E4 descendants spawned between the ownership snapshot (:135) and the
+        # census snapshot are still E4's: re-derive ownership on the census rows.
+        late = owned_tree(after, roots, self.known) - self.current_owned
+        for r in after:
+            if r["pid"] in late and r["cmdline_sha256"] != next((p["cmdline_sha256"] for p in after if p["pid"] == r["ppid"]), None):
+                identity = tuple(r[k] for k in self.supervisor.KEYS)
+                if self.known_identity.setdefault(r["pid"], identity) == identity:
+                    self.current_owned.add(r["pid"])
+        foreign = [r for r in foreign if not self.audit.own_process(self.job, r)]
+        active = [r for r in active if not self.audit.own_process(self.job, r)]
```

The `cmdline != parent cmdline` clause skips pre-exec vfork children; they are picked up by the next sample. The same guard should also be applied in the `:147-151` loop. The fix also needs a unit test in which a stubbed `processes()` returns the children only on the census call.

**What a fix touches:**
- `fleet_validity.py` is in `measurement_files` and `runtime_files`. Changing it requires:
  - the K4S manifest re-pin (c1fb1e9a → new; per 2026-10-11 22:28 "if … touches any pinned e4v3 file, another re-pin follows"), plus the fleet runtime bundle pins;
  - the R-ord post-exit "five A3 code SHAs" check;
  - an E4 code review (Sol);
  - PC2 re-review;
  - new A3 staging on the hosts.
- **Critically, the pool binds code across hosts and across attempts.**
  - `fleet_pool.py:107` checks every attempt (failed ones too) against the pool's own directory with `verify_files(..., identity["measurement_files"])`.
  - `:169-176` checks that `runtime_files` and `measurement_files` match across hosts with `assert_exact`.
  - So a fixed 08 r3 can't be pooled with 01's old-code reference, or with 08 r2. The code route therefore implies an outcome-blind amendment **and a re-run of 01** under the fixed code. 01's window (cutoff 04:17:43Z) would be lost, so the c6387611 deferral would apply.

## 4. The 01 reference in progress

**This failure mode can't hit 01 later.**
- `background_load` is entered **once** (`fleet_reference.py:129`). The warmup and all 3 repeats (`:151-180`) run inside that one `with` block. Nothing else spawns processes: there are no per-repeat or per-phase spawns.
- `guarded_block` checkpoints and the 1 Hz samples call the same guard, but they no longer see any new E4 process.
- A6, which ran the same code on 01, kept a constant 13 owned pids across all 2449 capacity rows and 476 block rows, with no new descendants.
- The single exposure is the first sample after admission, about 5 minutes after launch (≈03:02Z). A failure there exits within seconds. With no exit pushed by 03:31Z, 01 almost certainly got past it.
- 01 remains exposed to the ordinary guard failure modes (foreign compute, SSH, console, memory, MHz), but not to this one. Its files aren't on 05 yet (only PREPARED.json), so its D couldn't be checked directly.

## Recommendation: (a) r3 now, as is, while preparing (c) in parallel

**Why r3 first, and why not (b):**
- (b) isn't offered because no procedural mitigation materially changes the odds.
- r3 as is is likely to fail (~80–95%), but trying it is cheap and carries no information risk:
  - it costs the normal prep plus ~5 minutes of 08;
  - a failure happens before warmup or timing.
- Its success is the **only** route that keeps 01's old-code reference poolable and avoids re-pinning, re-review and re-running 01.

**Why the code route can wait for r3:**
- The code-fix route (c) needs an outcome-blind amendment and a 01 re-run whatever happens. Because the pool binds code across attempts, using up r3 makes nothing worse on that path.
- Launch r3 under the full C5/RF1 procedure (fresh C2, V2 prepare proof, argv pin, nice gate). Have no SSH or ControlMaster sessions open to 08 at admission.

**At the same time:**
- draft the `fleet_validity.py` fix and test above;
- prepare the outcome-blind amendment: a code fix, re-pin, E4 review and PC2, then a fresh reference series on both hosts with the old-code attempts disclosed.

If r3 fails with the same signature (foreign E4 spawn children whose ppid is the E4 pid, at the first post-admission sample), STOP and go to that amendment.

If the coordinator would rather not launch an attempt expected to fail, the alternative is (c), taken now as an amendment-backed re-run of both hosts. Plain (c), "code fix then r3", is **not** viable on its own, because of the pool's cross-host and cross-attempt code binding.
