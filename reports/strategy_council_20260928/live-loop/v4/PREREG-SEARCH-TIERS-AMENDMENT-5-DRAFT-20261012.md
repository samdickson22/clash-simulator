# TIERS Amendment 5 (DRAFT, NOT ADOPTED): E4 reference-guard ownership race, fixed code and a fresh END reference series

> **STATUS: DRAFT, NOT ADOPTED.** Nothing here is in force. Prepared under COORDINATOR ruling RG1 step 3 (92acdf02): "parallel draft, not adopted". It is adopted only by a coordinator ruling after the review chain in §7. Under RG1 that ruling is expected only if 08 r3 fails with the same signature, or if the coordinator re-rules. Until then every existing ruling stands unchanged: RG1, R-ord, L1, RF1 and C1–C8, C-a to C-d, c6387611. **No host is staged, re-pinned or touched by this draft.**

Prepared 2026-10-12 from about 03:40Z on 127x05, on branch `e4-guard-race-fix-20261012` (from origin/main 92acdf02, rebased onto 5cc4c5bc).
- No SSH.
- No reads of reporting outcomes or of any reference timing values.
- The only T1 job-tree file read is the diagnosis.

Impact inventory: [`E4-GUARD-RACE-FIX-IMPACT-20261012.md`](E4-GUARD-RACE-FIX-IMPACT-20261012.md).

## 1. What this amendment changes, and what it does not

**Changes:**
1. **One E4 file.** `e4v3/fleet_validity.py` goes from 94d0e7f2 to eae5db3f. It is the only change to any `measurement_files` / `runtime_files` / `measurement_source` entry.
2. **Every old-code END reference attempt is disclosed and excluded from pooling**, whatever it shows.
3. **A fresh END reference series runs on both counted hosts, 127x01 and 127x08,** under the fixed code, with new attempt names and a new release-side root declaration.
4. **The R-ord post-exit code check grows from five SHAs to six.**

**Does not change:** any hypothesis, arm, seed, tier, gate, threshold or reducer; the slot count (11); warmup (300 s); budgets; nice 10 and SCHED_OTHER; the 24 GiB floor; OP-1 to OP-6, including their rule set `frozen-t1-op1-op2-op3-op4-op5-op6-v1` and every stop reason; the guard freeze `FROZEN-T1.json` 24817e16 and its nine modules; the END evidence and counted population; the corpus, states, native 44874fd6, policy and calibration; the pooling rule (END mode, ±5%, no exclusion); the technical-repeat rule (`classify_attempt` is unchanged); the wrapper `end_exit_push.sh` 0a87166f; `detach.sh`; the verifier 753722c9; and the release checker `release_reference.py` f8b61c60 / `check_reference.py` c848baa2. No outcome-handling rule changes.

## 2. Cause

Source: `reports/explore/t1/receipts/END-08r2-DIAGNOSIS-r1.md`, ec6eb568.

**Two snapshots, one ownership decision.** `ReportingGuard.__call__` derives E4 ownership from one `/proc` snapshot (`fleet_validity.py:135,144`), then runs the frozen T1 census on its own, later snapshot (`:155`, which calls `host_audit.census` and in turn `processes()`). `host_audit.foreign_compute` flags any `python*` process that `own_process` doesn't own, with no CPU threshold. E4 overrides `own_process` to mean "in the snapshot-1 owned set" (`:115-116`).

**Why the first sample lands on the spawn burst.**
- `fleet_reference.run` sends the admit checkpoint and then immediately spawns the 10 `FleetBackground` workers (`fleet_reference.py:125-130`; `replay_load.py:131-133`).
- The first 1 Hz guard sample after admission fires as soon as the admit call returns, whenever that call took ≥1 s.
- Workers spawned between the two snapshots are E4's own children (ppid = E4), yet they are flagged `foreign_compute`. That gives `validity_census` and the attempt fails, about 5 minutes after launch and before any warmup or timing.

**Host effect.**
- On 08 the admit call took 1.24 s, which made the failure near-deterministic (08 r2: workers 1317821–1317824 flagged).
- On 01, A6 passed with 0.928 s, a margin of about 0–20 ms.
- A live check on 05 with real spawn workers between the snapshots flags 10/10 E4 workers on 94d0e7f2 in each of 3 runs (`e4-guard-race-fix-20261012/results.json`).

**Secondary hazard.** A snapshot taken during a child's vfork pre-exec window records the parent's cmdline. `known_identity.setdefault` (`:150`) would then de-own that pid permanently after exec.

**What it is not.** The failure isn't host interference, and the launch environment isn't implicated.

## 3. The fix (fleet_validity.py 94d0e7f2 → eae5db3f)

1. **Snapshot-1 pass.** The `:147-151` loop moves into `ReportingGuard.pin_identity(rows, tree)` and behaves exactly as before, with one exception: a pid whose recorded identity was taken pre-exec may re-pin **once**, at exec. The transition requires all of the following:
   - the pid was recorded while its cmdline_sha256 equalled its parent's in the same snapshot;
   - pid, pgid, start_ticks and uid are unchanged;
   - the pid is in the ppid/start_ticks `owned_tree` of the E4 roots.

   Any other identity change still de-owns the pid permanently (frozen OP-3).
2. **Census pass, new.** After `self.audit.census(...)`, ownership is re-derived on the census rows with `owned_tree(after, roots, self.known)`, under the same `known` start_ticks protection against pid reuse, and pinned through `pin_identity`. The result is unioned into `current_owned`, never subtracted. Then `foreign_compute` and `foreign_active` drop the rows that `own_process` now owns.

**Still true after the fix:**
- A process outside the E4 ppid tree is never owned, even with E4's cmdline.
- A reused pid with new start_ticks is never owned, whatever its ppid.
- Every T1 rule and reason is untouched.

**Tests** (impact §5):
- the e4v3 suite is 96/96 OK with 2 torch skips, against a 91/91 baseline;
- the new tests fail 7 times on 94d0e7f2;
- the live check on 05 shows 10/10 owned on the fix, with the 6 real foreign processes still flagged on both versions.

## 4. Disclosure: every END-campaign execution of the 94d0e7f2 guard

None of these attempts is pooled under A5, whatever its status or content. That decision is made here, before any of their timing content is inspected, and is independent of it. Each is preserved unchanged, on its host and in `end-received/`, under L1/RF1 as already ruled.

| # | Attempt | Host | Launch (UTC) | Status as of drafting | Receipts (repo) | Treatment under A5 |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | **A6** (A3 end-to-end run, `e4v3-unpoolable-smoke` profile, outside all roots) | 127x01 | 01:13:36Z (exit 0 at 02:08:47Z) | complete; independent review PASS_WITH_NOTES (b21b5a20); passed the race by about 0–20 ms | `END-A6-launch-receipt-01-20261012T011336Z.json` 45bd9dc3; `END-A6-approved-verification-r5-20261012T0230Z.json` 797e02f1; `END-A6-INDEPENDENT-REVIEW-r1.md` 9d959d9f | Disclosed. Its role as the A3 memory/exactness end-to-end evidence stands for the 17 unchanged files. Whether a fixed-code smoke replaces it is review item R4 |
| D2 | `end-reference-127x01-0a87166f-r1` (01 ref r1) | 127x01 | 02:57:15Z | in progress or exited; result unknown to the drafter; past the single exposure point per the diagnosis §4 | `END-reference-launch-receipt-01-r1.json` 382492f1, plus its launch-preparation, prelaunch and receive-prepare receipts | **Disclosed old-code attempt, not pooled.** C-d, verifier ACK and L1 assembly proceed as already ruled, into the old release-side root |
| D3 | `end-reference-127x08-0a87166f-r1` (08 r1) | 127x08 | 02:48:04Z (nice 19 refusal; exit 1 at 02:48:18Z) | RF1 exempt pre-identity refusal | `END-reference-launch-receipt-08-r1.json` b2c9969d; `END-reference-refusal-disclosure-08-r1.json` 898b236d | Remains an RF1 exempt disclosure. It never executed `ReportingGuard` (refused before `fleet-identity.json`) and is listed for completeness |
| D4 | `end-reference-127x08-0a87166f-r2` (08 r2) | 127x08 | 03:23:10Z | failed, `validity_census` / `foreign_compute`: E4 workers 1317821–1317824 at the first post-admission sample | `END-reference-launch-receipt-08-r2.json` f0e91ad1; `END-reference-validity-STOP-08-r2-20261012T0331Z.json` 8958eb5c; `END-08r2-DIAGNOSIS-r1.md` ec6eb568 | **Disclosed old-code attempt, not pooled** |
| D5 | `end-reference-127x08-0a87166f-r3` (08 r3), **only if it runs** under RG1 step 1 | 127x08 | n/a | n/a | its launch and STOP receipts, when committed | **Disclosed old-code attempt, not pooled, whatever its result.** If r3 *passes*, this amendment is not adopted (§8) |

**Committed disclosure.** Before the first A5 launch, T1 commits a disclosure receipt `reports/explore/t1/receipts/END-A5-old-code-attempt-disclosure.json`. For D1–D5 it lists launch receipt, argv pin, exit.json, DURABLE-ACK status, manifest SHA, `fleet_technical_cause` and where the attempt is preserved. The disclosure states its status fields only and reads no timing values.

## 5. Fresh reference series under the fixed code

### 5.1 Code and staging

- **E4 commit.** The commit that carries `fleet_validity.py` eae5db3f after Sol APPROVE (§7), merged to main. Its e4v3 inventory is the 18 A3 entries, with fleet_validity changed.
- **Staging.**
  - A new A5 runtime on 01 and 08 in a fresh staging root (e.g. `…/t1-20261010-r1/end-a5-<commit8>-0108-r1`). The A3 runtime stays untouched as the evidence for D2–D5.
  - New END-A5 bundle manifests (`tiers-pins.json`) for both hosts. They are regenerated from the same inputs, and only the fleet_validity entries change; T1 commits a diff receipt that proves this.
  - Both C3 preflights are repeated.
  - New argv pins (`--manifest-sha256`), new V2 prepare proofs committed ≥1 s before launch, and C-a pins.
- **Six-SHA post-exit check (replaces R-ord's "five A3 code SHAs"):**
  - measure_tiers 6066228b, fleet_reference c767a6e0, tier_backend 02e2139f, state_rows 3899276b, prepare_bundle a1c59fa3, **fleet_validity eae5db3f**;
  - plus native 44874fd6, 11 slots, warmup 300 and `fleet-complete.poolable == true`.

  Any mismatch makes the attempt a failed attempt: preserve it under L1, then STOP and escalate.

### 5.2 Attempt roots (equivalent rule; no wrapper change)

The frozen wrapper accepts only `$base` or `$base/fleet-end-attempts-0108/$host` as the job parent (`end_exit_push.sh:14-17`), so a new host-side root would need a wrapper change and re-review. A5 instead uses:

1. **Host side.**
   - A5 attempts are immediate children of the **existing** host root `BASE/fleet-end-attempts-0108/<host>/`.
   - Basenames: `end-reference-<host>-0a87166f-a5-r1` and, only as the single technical repeat, `-a5-r2`. These are new names and never reuse a D2–D5 directory.
   - Nothing is moved, deleted or archived.
2. **Release side (05).**
   - A new declaration `reports/explore/t1/receipts/reference-attempt-roots-0108-a5.json` (schema `clasher.t1.reference-attempt-roots.v1`) names `BASE/fleet-end-attempts-0108-a5/127x01` and `…/127x08`.
   - It is committed **and pushed before the first A5 launch**. `release_reference.attempt_roots` enforces `registered_at <= identity.utc` for every attempt.
   - L1 assembly (a byte-identical plain copy of the ACKed `durable-measurement`, with the same basename) places **only A5 attempts** in the new root.
   - D2/D4/D5 stay assembled in the old release-side root under `reference-attempt-roots-0108.json` (405f35dc, unchanged, still pinned by `FROZEN-T1.json`).
   - The A5 release evidence binds the **A5** roots file.
3. **PC1 reading (declared interpretation, flagged to the PC1 reviewer).** For each host, the original host-root listing must equal the union of three sets, which must be disjoint and exhaustive:
   - (A5 descriptor attempts);
   - (D2/D4/D5 from the committed A5 disclosure);
   - (RF1 exempt disclosures: D3).

   Any unexplained directory fails the packet.
4. **Why the old attempts can't be listed in the A5 descriptor.**
   - `fleet_pool.run` verifies every attempt's `measurement_files`, failed ones included, against its own e4v3 directory (`fleet_pool.py:107`).
   - It also requires identical runtime and measurement files across hosts (`:169-176`).
   - `release_reference` requires the passing attempt's `measurement_files` to equal `measurement_source` (`:265-267`).

   A mixed-code descriptor is therefore mechanically impossible. Disclosure is the only faithful treatment.

### 5.3 Pool and release constraints (unchanged code, restated for the A5 series)

- **Attempts per host.** 1–2 A5 attempts per host, in chronological order (`fleet_pool.py:96-97,106-113`; `release_reference.py:197`).
  - A passing attempt must come last.
  - An earlier attempt must be `passes=False` and `technical_repeat_candidate=True` under the unchanged `classify_attempt` (`fleet_pool.py:114-121`; `release_reference.py:223-224`).
  - An exactness failure never earns a repeat.
- **If both A5 attempts on a host fail:** STOP. `fleet_pool` raises "second failure requires outcome-blind amendment". A5 grants no third attempt.
- **END mode.** Both counted hosts must pass and pool within ±5%, with no exclusion (`fleet_pool.py:59-60`; `release_reference.py:206-207`).
- **RF1 C2** (at most one exempt pre-identity refusal per host per END campaign) **carries over.** The A5 series is the same END campaign. 08 has used its exemption (D3); 01 has not.
- **Carried over unchanged:** C1, C3–C8; C5/C6 pre-exec gate (parent nice 0, SCHED_OTHER, byte-identical argv, wrapper and E4 nice 10, no signal on wrong nice); C-a to C-d (verify no earlier than exit + 1300 s); L1 assembly; R-ord host independence ("launch 01 first" only if 01's window closes first); and the RG1 note: no SSH or ControlMaster session open to a host at its admission.
- **F9 still applies:** 08's reference finishes before B takes 08.
- **Release.** `release_reference.prerequisites` runs unchanged, with `measurement_source` = the A5 commit inventory and `attempt_roots` = the A5 roots binding. `check_reference` is re-run per C1, and the pool check is committed after completion as already required.

## 6. Deferral windows (per c6387611)

Each host is scheduled on its own (R-ord). A host's A5 launch may happen only inside a **clean window**:

**Conditions for a clean window:**
- **Prerequisites done:** A5 adopted; the host staged; C3 repeated; prepare proof committed; the A5 roots file pushed.
- **Fresh C2:** both actual apt runs (apt-daily and apt-daily-upgrade) have exited, motd stamps are fresh, and there are **≥2 h** of clearance to the host's next apt timer.
- **C1 proof** that no earlier wrapper of ours is alive on that host. For 08 this means after D4, or D5 if it ran, has had its C-d.
- **Duration basis:** 55 m 11 s (A6 observed) of run time, plus the C-d 1300 s before verification.

**If a host's window is missed,** its launch is **deferred, not relaxed**, to the first clean window after that host's next apt-daily, with a fresh C2. No margin is reduced.

**Illustration only.** C2 recomputes the real times at launch, because apt timers are randomised daily. From the A6 review, on 2026-10-12:
- 01's apt-daily is at 06:17:43Z and its apt-daily-upgrade at 13:36:48Z, so its post-apt-daily window must launch by about 11:36:48Z;
- 08's apt-daily is at 08:49:07Z.

A5 sets no absolute deadline. If the series slips past the TIERS schedule, that is reported as a schedule deviation, not resolved by relaxing a gate.

## 7. Review chain (all required before adoption)

| Step | Reviewer | Scope | Pass condition |
| --- | --- | --- | --- |
| R1 | **Sol** (GPT-6.1-Sol; Claude-written code) | `fleet_validity.py` diff 94d0e7f2 → eae5db3f, `tests/test_guard_census_race.py` and the live-check script. Specifically: the union-not-subtract census pass; the one-shot pre-exec transition (`old[:4] == identity[:4]`, KEYS order pid/pgid/start_ticks/uid); pid-reuse protection; no masking of real foreign processes; no change to T1 semantics | APPROVE. Each round goes back with the full brief, prior findings and responses |
| R2 | **PC2** production packet reviewer | The "final independently reviewed E4 commit" becomes the R1-approved commit. Check that the A5 attempts' `measurement_files` equal that commit's inventory (17 unchanged entries plus eae5db3f), including END and pooling code | Recorded at the production packet, as PC2 already requires. A5 asks the coordinator to tell the PC2 reviewer **now** that the reviewed commit moves |
| R3 | **Independent Opus science review** (high effort; not the drafter) | Outcome-blindness of A5; completeness of the D1–D5 disclosure; the "never pool old code" rule fixed in advance; the §5.2 PC1 interpretation; deferral and no-relaxation; whether the fix could bias timing (it changes only guard ownership, in the monitor process, at 1 Hz on the census core) | APPROVE or APPROVE_WITH_CONDITIONS, with conditions adopted |
| R4 | R3 reviewer and coordinator | Whether A6's A3 end-to-end evidence carries over, or a short fixed-code unpoolable smoke on 01 is needed before the references (cost: one window) | Ruling recorded |
| R5 | Coordinator | Adoption ruling. Companion actions are sequenced but are not prerequisites for the TIERS A5 series: (a) **K4S re-pin**, a K4S Amendment 3 changing `K4S-MAC-MANIFEST` c1fb1e9a by one leaf, with Sol review, before any K4S END reference or Mac K4S session. The **fleet d89cab16 and FROZEN-K4S 416f6e51 are not re-pinned**, and the running K4S reporting is not touched. (b) **A4 erratum** for `stage_nocopy.py` 96abd847 (`FROZEN_MEASUREMENT_FILES["fleet_validity.py"]`), with a narrow Sol diff review, then Mac runtime re-stage or overlay and re-verify before any Mac staging. Mac is on HOLD, so nothing in progress is affected | Committed ruling |

## 8. If 08 r3 passes

This draft is **not adopted** in that case. Under RG1, 01 r1 (D2) plus 08 r3 can be pooled under the old code, and no re-pin or re-run follows.

The race is still in the code, though:
- **The K4S END reference runs the same `ReportingGuard`, with 10 workers spawned right after admission** (`k4s-confirm/end_reference.py:361-363`; `end_background.py:143-147`). The coordinator needs a separate K4S-side ruling before any K4S END reference: either adopt this fix through a K4S manifest re-pin, or accept the risk with disclosure.
- Any future E4 fleet reference on a slow host carries the same risk.

## 9. Open items for the reviewers

1. **One-time transition (R1).** The pre-exec rule trusts a pid that was seen once with its parent's cmdline to make one identity transition. The pid must already be in E4's ppid/start_ticks tree, so this grants no ownership outside the tree. R1 should confirm that this is acceptable under OP-3.
2. **Cross-host equality.** The census-pass union means `owned_pid_start_ticks` can now include pids seen only in the census snapshot. That is more complete evidence, not a change in what qualifies. `validate_census` / `validate_admission` / `validate_blocks` don't read that field, and `fleet_pool` doesn't compare it across hosts.
3. **Order.** Adopting A5 makes D2's outcome irrelevant to pooling. Under outcome-blindness, the adoption decision must not wait on, or be informed by, D2's timing content; only its existence and status may be cited.
