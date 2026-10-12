# TIERS Amendment 5 (DRAFT, NOT ADOPTED): E4 reference-guard ownership race, fixed code and a fresh END reference series

> **STATUS: DRAFT, NOT ADOPTED.** Nothing here is in force. Prepared under RG1 step 3 (92acdf02). RG2 (d7d5245a) activated this path after 08 r3 failed with the same race signature. It is adopted only by a coordinator ruling after the review chain in §7. Until then every existing ruling stands unchanged: RG1, RG2, R-ord, L1, RF1 and C1–C8, C-a to C-d, c6387611. **No host is staged, re-pinned or touched by this draft.**

Prepared 2026-10-12 from about 03:40Z on 127x05, on branch `e4-guard-race-fix-20261012`.
- **r1 draft:** made from origin/main 92acdf02.
- **r2 draft:** rebased onto a57bab10, after Sol code review r1 (REQUEST_CHANGES) and Opus science review r1 (ADOPT_WITH_CHANGES, T1–T13 applied verbatim; T5 clause (ii) dropped because the exec exception is deleted).
- No SSH.
- No reads of reporting outcomes or of any reference timing values.
- The only T1 job-tree file read is the diagnosis.

Impact inventory: [`E4-GUARD-RACE-FIX-IMPACT-20261012.md`](E4-GUARD-RACE-FIX-IMPACT-20261012.md).

## 1. What this amendment changes, and what it does not

**Changes:**
1. **One E4 file.** `e4v3/fleet_validity.py` goes from 94d0e7f2 to `<R1-APPROVED SHA>`, the SHA recorded in the adoption ruling. It is the only change to any `measurement_files` / `runtime_files` / `measurement_source` entry. The r2 candidate under review is `016ae7d0ba8238b5af55356a9b33b3e467c02ef21087599535dbb16a2ef26cf3`.
2. **Every old-code END reference attempt is disclosed and excluded from pooling**, whatever it shows.
3. **A fresh END reference series runs on both counted hosts, 127x01 and 127x08,** under the fixed code, with new attempt names and a new release-side root declaration. It is preceded by a required fixed-code smoke (§7 R4).
4. **The R-ord post-exit code check** becomes a full comparison of the 18-entry `measurement_files` (§5.1).

**Does not change:**
- any hypothesis, arm, seed, tier, gate, threshold or reducer;
- the slot count (11), warmup (300 s), budgets, nice 10 and SCHED_OTHER, and the 24 GiB floor;
- the T1 guard modules, the rule set `frozen-t1-op1-op2-op3-op4-op5-op6-v1` and every stop reason. The E4 adapter's application of OP-3 identity pinning changes in one way only: (i) ownership is also derived on the census snapshot (union, start_ticks-protected, never outside the E4 ppid tree). This is a declared adapter-level relaxation, not a T1 rule change;
- the guard freeze `FROZEN-T1.json` 24817e16 and its nine modules;
- the END evidence and counted population;
- the corpus, states, native 44874fd6, policy and calibration;
- the pooling rule (END mode, ±5%, no exclusion);
- the technical-repeat rule (`classify_attempt` is unchanged);
- the wrapper `end_exit_push.sh` 0a87166f, `detach.sh` and the verifier 753722c9;
- the release checker `release_reference.py` f8b61c60 / `check_reference.py` c848baa2;
- any outcome-handling rule.

> *Drafter note (r2, not review text).* The r2 code also makes the adapter **stricter**, in the snapshot-1 derivation (`:144`) and in the census pass alike: a process whose pinned six-KEY identity has changed neither stays owned nor makes its new descendants owned (Sol r1 F3). On 94d0e7f2, such a parent's new children were admitted from the ownership snapshot on. This tightening isn't covered by T5 (i), so it is flagged to R3 under the R1 re-check clause (§7).

## 2. Cause

Source: `reports/explore/t1/receipts/END-08r2-DIAGNOSIS-r1.md`, ec6eb568.

**Two snapshots, one ownership decision.** `ReportingGuard.__call__` derives E4 ownership from one `/proc` snapshot (`fleet_validity.py:135,144` on 94d0e7f2), then runs the frozen T1 census on its own, later snapshot (`:155`, which calls `host_audit.census` and in turn `processes()`). `host_audit.foreign_compute` flags any `python*` process that `own_process` doesn't own, with no CPU threshold. E4 overrides `own_process` to mean "in the snapshot-1 owned set, with a matching pinned identity" (`:115-116`).

**Why the first sample lands on the spawn burst.**
- `fleet_reference.run` sends the admit checkpoint and then immediately spawns the 10 `FleetBackground` workers (`fleet_reference.py:125-130`; `replay_load.py:131-133`).
- The first 1 Hz guard sample after admission fires as soon as the admit call returns, whenever that call took ≥1 s.
- Workers spawned between the two snapshots are E4's own children (ppid = E4), yet they are flagged `foreign_compute`. That gives `validity_census` and the attempt fails, about 5 minutes after launch and before any warmup or timing.

**Host effect.**
- On 08 the admit call took 1.24 s, which made the failure near-deterministic (08 r2: workers 1317821–1317824 flagged).
- On 01, A6 passed with 0.928 s, a margin of about 0–20 ms.
- A live check on 05 with real spawn workers between the snapshots flags 10/10 E4 workers on 94d0e7f2 in each of 3 runs (`e4-guard-race-fix-20261012/results.json`).

**What it is not.** The failure isn't host interference, and the launch environment isn't implicated. 08 r3 (RG2) reproduced the signature, which confirms the diagnosis's prediction.

## 3. The fix (fleet_validity.py 94d0e7f2 → `<R1-APPROVED SHA>`; r2 candidate 016ae7d0, +16/−5)

1. **Identity-valid ancestry.** `owned_tree(rows, roots, known, pinned=None, keys=())` takes the pinned identities. A row whose pid already has a pinned six-KEY identity (`supervisor.KEYS`) that differs from the row is never owned, neither as a seed nor as a child. It therefore grants nothing to descendants. This applies at `:144` (snapshot 1) and in the census pass.
   - PID-reuse protection through `known` start_ticks is unchanged.
   - An identity-valid, already admitted descendant stays a seed even if it was reparented. That is the frozen behaviour of 94d0e7f2.
   - With `pinned=None`, `owned_tree` behaves exactly as on 94d0e7f2.
2. **Census pass, new.** After `self.audit.census(...)`:
   - E4 descendants **newly** reached on the census rows (`owned_tree(after, …) − current_owned`) are pinned with the unchanged `setdefault` of the six KEYS, provided the row's start_ticks equals `known`;
   - they are added to `current_owned` only if that pinned identity matches;
   - `foreign_compute` and `foreign_active` then drop the rows that `own_process` now owns.

   The pass never removes ownership and never replaces a pinned identity.
3. **Unchanged:** the `:147-151` six-KEY `known_identity.setdefault` loop and the `own_process` override are byte-for-byte as on 94d0e7f2. **No exec, pre-exec or identity-replacement exception exists.**

**Residual risk (accepted, not fixed).** A `/proc` scan may catch a spawn child in its vfork pre-exec window, when it still shows the parent's argv.
- That identity is then pinned.
- After exec the six-KEY identity differs, the child is permanently de-owned, and it is flagged `foreign_compute`. The attempt fails as `validity_census`, which is a technical-repeat candidate, before timing.
- The window is microseconds per spawn and has never been observed: A6 recorded 2449 capacity rows and 476 block rows, and the 08 r2/r3 flagged rows were all post-exec workers.
- Fixing it would need an identity-replacement rule, which Sol r1 F1/F2 showed weakens OP-3.

**Still true after the fix:**
- A process outside the E4 ppid tree is never owned, even with E4's cmdline.
- A reused pid with new start_ticks is never owned, whatever its ppid.
- A pinned identity is never replaced, under any condition.
- Every T1 rule and reason is untouched.

**Tests** (impact §5):
- the e4v3 suite is 101/101 OK with 2 torch skips, against a 91/91 baseline;
- the 10 new tests give 5 failures on 94d0e7f2: the three race positives, plus the denied-parent case with the child already in the ownership snapshot;
- Sol's exec and rearm negatives are rejected on both versions;
- the live check on 05 shows 10/10 owned on r2 and 0/10 on 94d0e7f2, with the 6 real foreign processes flagged on both versions.

### 3.1 Sol r1 response (REQUEST_CHANGES → r2)

| Sol r1 finding | r2 change | Regression tests (`tests/test_guard_census_race.py`) |
| --- | --- | --- |
| **F1 (HIGH):** the pre-exec allowance authenticates the generation, not the destination executable | **Exec/identity-replacement exception deleted entirely.** No pending or consumed state, and no replacement of a pinned identity. The `known_identity` behaviour is the frozen six-KEY one of 94d0e7f2; the vfork window is an accepted residual (§3) | `test_arbitrary_exec`, `test_arbitrary_exec_active` (flagged in both `foreign_compute` and `foreign_active`) |
| **F2 (HIGH):** "once" not enforced; late re-arming after reparenting | Deleted with F1, so no eligibility state exists | `test_repeated_exec` (exe-only, three steps), `test_late_rearm` (PID-1 reparenting sequence) |
| **F3 (MED):** census reconciliation admits descendants through an identity-rejected parent | `owned_tree` checks the pinned six-KEY identity of every seed and every newly admitted child, in both snapshots. A rejected parent grants nothing | `test_denied_parent_new_child` (child first seen in the census, and child present in both snapshots), `test_rejected_intermediate_late_grandchild` |
| Positive coverage | (unchanged race fix) | `test_spawn_children_seen_only_by_census_are_owned`, `test_late_grandchild_listed_before_its_parent_is_owned` (reverse row order) |

Sol's `probes.py`, run against r2, gives results identical to 94d0e7f2 for `arbitrary_exec`, `arbitrary_exec_active`, `repeated_exec`, `late_rearm` and `denied_parent_new_child`, and owns `[100, 102, 103]` for `grandchildren`.

## 4. Disclosure: every END-campaign execution of the 94d0e7f2 guard

None of these attempts is pooled under A5, whatever its status or content. That decision is made here, before any of their timing content is inspected, and is independent of it. Each is preserved unchanged, on its host and in `end-received/`, under L1/RF1 as already ruled.

| # | Attempt | Host | Launch (UTC) | Status | Receipts (repo) | Treatment under A5 |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | **A6** (A3 end-to-end run, `e4v3-unpoolable-smoke` profile, outside all roots) | 127x01 | 01:13:36Z (exit 0 at 02:08:47Z) | complete; independent review PASS_WITH_NOTES (b21b5a20); passed the race by about 0–20 ms | `END-A6-launch-receipt-01-20261012T011336Z.json` 45bd9dc3; `END-A6-approved-verification-r5-20261012T0230Z.json` 797e02f1; `END-A6-INDEPENDENT-REVIEW-r1.md` 9d959d9f | Disclosed. It never exercised the fixed census path, and is superseded as the end-to-end evidence by the required A5 smoke (§7 R4) |
| D2 | `end-reference-127x01-0a87166f-r1` (01 ref r1) | 127x01 | 02:57:15Z | exited 0 at 03:52:14Z, measurement present (exit-health receipt 20261012T0358Z); C-d 04:13:54Z; verifier ACK and L1 assembly per RG2. Probably a passing reference; timing unread. | `END-reference-launch-receipt-01-r1.json` 382492f1; `END-reference-exit-01-r1-health-20261012T0358Z.json` 1aef98c4; plus its launch-preparation, prelaunch and receive-prepare receipts | **Disclosed old-code attempt, not pooled.** C-d, verifier ACK and L1 assembly proceed as already ruled, into the old release-side root |
| D3 | `end-reference-127x08-0a87166f-r1` (08 r1) | 127x08 | 02:48:04Z (nice 19 refusal; exit 1 at 02:48:18Z) | RF1 exempt pre-identity refusal | `END-reference-launch-receipt-08-r1.json` b2c9969d; `END-reference-refusal-disclosure-08-r1.json` 898b236d | Remains an RF1 exempt disclosure. It never executed `ReportingGuard` (refused before `fleet-identity.json`) and is listed for completeness |
| D4 | `end-reference-127x08-0a87166f-r2` (08 r2) | 127x08 | 03:23:10Z | failed, `validity_census` / `foreign_compute`: E4 workers 1317821–1317824 at the first post-admission sample | `END-reference-launch-receipt-08-r2.json` f0e91ad1; `END-reference-validity-STOP-08-r2-20261012T0331Z.json` 8958eb5c; `END-08r2-DIAGNOSIS-r1.md` ec6eb568 | **Disclosed old-code attempt, not pooled** |
| D5 | `end-reference-127x08-0a87166f-r3` | 127x08 | 03:56:55Z (exit 1 at 04:02:43Z) | failed, `validity_census` / `foreign_compute`: 1 E4 spawn worker (ppid 1323459) at the first post-admission sample; C-d 04:24:23Z | its launch-preparation, launch, prelaunch, receive-prepare and STOP receipts (`END-reference-launch-preparation-08-r3.json` 6c0e8de6, `END-reference-launch-receipt-08-r3.json` edc18140, `END-reference-prelaunch-checks-08-r3.json` 5359d68c, `END-reference-receive-prepare-08-r3.json` 4cc61a1f, `END-reference-validity-STOP-08-r3-20261012T0403Z.json` 1e82d235) | **Disclosed old-code attempt, not pooled.** |

**Committed disclosure.** Before the first A5 launch, T1 commits a disclosure receipt `reports/explore/t1/receipts/END-A5-old-code-attempt-disclosure.json`. For D1–D5 it lists launch receipt, argv pin, exit.json, DURABLE-ACK status, manifest SHA, `fleet_technical_cause` and where the attempt is preserved. The disclosure states its status fields only and reads no timing values.

### 4.1 Sealing of old-code timing

No timing, deadline, speed or capacity content of D2, or of any D-attempt, is opened, summarised or compared before the A5 pool check is committed. The only things that may be cited before then are existence, status, exit code and SHAs. D-attempt content cannot select, replace, validate or trigger any A5 attempt. After the A5 pool check is committed, the one permitted use is this pre-declared descriptive comparison: the per-tier median wall ratio of D2 to the 01 A5 passing attempt, reported as "old-guard vs fixed-guard, same host". It affects no gate, pool, registration or release, and nothing else may be derived from D-attempt content. The disclosure receipt states that D2 is believed to be a complete attempt and is excluded only because of the code binding (fleet_pool.py:107,169-176; release_reference.py:265-267) and the A2/A3 condition 1 precedent.

## 5. Fresh reference series under the fixed code

### 5.1 Code and staging

- **E4 commit.** The commit that carries `fleet_validity.py` `<R1-APPROVED SHA>`, the SHA recorded in the adoption ruling, after Sol APPROVE (§7), merged to main. Its e4v3 inventory is the 18 A3 entries, with fleet_validity changed.
- **Staging.**
  - A new A5 runtime on 01 and 08 in a fresh staging root (e.g. `…/t1-20261010-r1/end-a5-<commit8>-0108-r1`). The A3 runtime stays untouched as the evidence for D2–D5.
  - New END-A5 bundle manifests (`tiers-pins.json`) for both hosts. They are regenerated from the same inputs, and only the fleet_validity entries change; T1 commits a diff receipt that proves this.
  - Both C3 preflights are repeated.
  - New argv pins (`--manifest-sha256`), new V2 prepare proofs committed ≥1 s before launch, and C-a pins.
- **Post-exit check (replaces R-ord's "five A3 code SHAs"):** the full `fleet-identity.json` `measurement_files` (18 entries) equals the A5 commit inventory, which includes the five A3 code SHAs and fleet_validity `<R1-APPROVED SHA>`; plus native 44874fd6, 11 slots, warmup 300 and `fleet-complete.poolable == true`.

  Any mismatch makes the attempt a failed attempt: preserve it under L1, then STOP and escalate.

### 5.2 Attempt roots (equivalent rule; no wrapper change)

The frozen wrapper accepts only `$base` or `$base/fleet-end-attempts-0108/$host` as the job parent (`end_exit_push.sh:14-17`), so a new host-side root would need a wrapper change and re-review. A5 instead uses:

1. **Host side.**
   - A5 attempts are immediate children of the **existing** host root `BASE/fleet-end-attempts-0108/<host>/`.
   - Basenames: `end-reference-<host>-0a87166f-a5-r<n>`, with n = 1, 2, 3, … sequential per host in launch order. At most two counted (non-exempt) A5 attempts per host. At most one RF1-exempt refusal per host across the whole END campaign: 08 has used it (D3); 01 has one. These are new names and never reuse a D2–D5 directory.
   - Nothing is moved, deleted or archived.
2. **Release side (05).**
   - A new declaration `reports/explore/t1/receipts/reference-attempt-roots-0108-a5.json` (schema `clasher.t1.reference-attempt-roots.v1`) names `BASE/fleet-end-attempts-0108-a5/127x01` and `…/127x08`.
   - It is committed **and pushed before the first A5 launch**. The push is recorded in a T1 receipt (origin ref, commit and observed UTC) before that launch, because `registered_at` is committer time and PC1 checks push time. The adoption ruling names this file (path, commit and SHA) as the only `attempt_roots` binding for release. The release-side root path differs from the host root (basename unchanged). This amends L1 item 2 for A5 attempts and is flagged to PC1 as a declared interpretation.
   - `release_reference.attempt_roots` enforces `registered_at <= identity.utc` for every attempt.
   - L1 assembly (a byte-identical plain copy of the ACKed `durable-measurement`, with the same basename) places **only A5 attempts** in the new root.
   - D2/D4/D5 stay assembled in the old release-side root under `reference-attempt-roots-0108.json` (405f35dc, unchanged, still pinned by `FROZEN-T1.json`).
3. **PC1 reading (declared interpretation, flagged to the PC1 reviewer).** For each host, the original host-root listing must equal the union of three sets, which must be disjoint and exhaustive:
   - (A5 descriptor attempts);
   - (D2/D4/D5 from the committed A5 disclosure);
   - (committed RF1-exempt disclosures: D3, plus at most one A5-series exempt refusal on 01).

   Any unexplained directory fails the packet. The A5 smoke (§7 R4) has job parent `$base`, so it is not in any host root.
4. **Why the old attempts can't be listed in the A5 descriptor.**
   - `fleet_pool.run` verifies every attempt's `measurement_files`, failed ones included, against its own e4v3 directory (`fleet_pool.py:107`).
   - It also requires identical runtime and measurement files across hosts (`:169-176`).
   - `release_reference` requires the passing attempt's `measurement_files` to equal `measurement_source` (`:265-267`).

   A mixed-code descriptor is therefore mechanically impossible. Disclosure is the only faithful treatment.

### 5.3 Pool and release constraints (unchanged code, restated for the A5 series)

- **Attempts per host.** 1–2 counted A5 attempts per host, in chronological order (`fleet_pool.py:96-97,106-113`; `release_reference.py:197`).
  - A passing attempt must come last.
  - An earlier attempt must be `passes=False` and `technical_repeat_candidate=True` under the unchanged `classify_attempt` (`fleet_pool.py:114-121`; `release_reference.py:223-224`).
  - An exactness failure never earns a repeat.
- **If both counted A5 attempts on a host fail:** STOP. `fleet_pool` raises "second failure requires outcome-blind amendment". A5 grants no third attempt.
- **END mode.** Both counted hosts must pass and pool within ±5%, with no exclusion (`fleet_pool.py:59-60`; `release_reference.py:206-207`).
- **RF1 C2** (at most one exempt pre-identity refusal per host per END campaign) **carries over.** The A5 series is the same END campaign. 08 has used its exemption (D3); 01 has not.
- **Carried over unchanged:** C1, C3–C8; C5/C6 pre-exec gate (parent nice 0, SCHED_OTHER, byte-identical argv, wrapper and E4 nice 10, no signal on wrong nice); C-a to C-d (verify no earlier than exit + 1300 s); L1 assembly; R-ord host independence ("launch 01 first" only if 01's window closes first); and the RG1 note: no SSH or ControlMaster session open to a host at its admission.
- **F9 still applies:** 08's reference finishes before B takes 08.
- **Release.** `release_reference.prerequisites` runs unchanged, with `measurement_source` = the A5 commit inventory and `attempt_roots` = the A5 roots binding. `check_reference` is re-run per C1, and the pool check is committed after completion as already required.

## 6. Deferral windows (per c6387611)

Each host is scheduled on its own (R-ord). A host's A5 launch, whether the smoke or a reference, may happen only inside a **clean window**:

**Conditions for a clean window:**
- **Prerequisites done:** A5 adopted; the host staged; C3 repeated; prepare proof committed; the A5 roots file pushed, with the push receipt; and, before any A5 reference launch, the passed A5 smoke (§7 R4).
- **Per host:** 01: D2's C-d (04:13:54Z), its verifier ACK and its L1 assembly. 08: D5's C-d (04:24:23Z), its verifier ACK and its L1 assembly. For both hosts, the committed `END-A5-old-code-attempt-disclosure.json` and the passed smoke (T7).
- **Fresh C2:** both actual apt runs (apt-daily and apt-daily-upgrade) have exited, motd stamps are fresh, and there are **≥2 h** of clearance to the host's next apt timer.
- **C1 proof** that no earlier wrapper of ours is alive on that host.
- **Duration basis:** 55 m 11 s (A6 observed) of run time, plus the C-d 1300 s before verification. This applies to the smoke as well as to a reference.

**If a host's window is missed,** its launch is **deferred, not relaxed**, to the first clean window after that host's next apt-daily, with a fresh C2. No margin is reduced.

**Illustration only.** C2 recomputes the real times at launch, because apt timers are randomised daily. From the A6 review, on 2026-10-12:
- 01's apt-daily is at 06:17:43Z and its apt-daily-upgrade at 13:36:48Z, so its post-apt-daily window must launch by about 11:36:48Z;
- 08's apt-daily is at 08:49:07Z.

A5 sets no absolute deadline. If the series slips past the TIERS schedule, that is reported as a schedule deviation, not resolved by relaxing a gate.

## 7. Review chain (all required before adoption)

| Step | Reviewer | Scope | Pass condition |
| --- | --- | --- | --- |
| R1 | **Sol** (GPT-6.1-Sol; Claude-written code) | `fleet_validity.py` diff 94d0e7f2 → `<R1-APPROVED SHA>` (r1 eae5db3f: REQUEST_CHANGES; r2 candidate 016ae7d0), `tests/test_guard_census_race.py` and the live-check script. Specifically: the union-not-subtract census pass; identity-valid ancestry in both snapshots; no replacement of any pinned identity; pid-reuse protection; no masking of real foreign processes; no change to T1 semantics | APPROVE. Each round goes back with the full brief, prior findings and responses (§3.1). If the approved diff changes behaviour beyond census-snapshot ownership derivation, or violates T5 (i), R3 re-checks before adoption. *(Drafter note: r2's identity-valid ancestry tightening, from Sol F3, is such a change, so a narrow R3 re-check is required.)* |
| R2 | **PC2** production packet reviewer | The "final independently reviewed E4 commit" is recorded as A3-reviewed E4 (E4-END-INDEPENDENT-REVIEW, 732ea9bd) plus the R1-approved one-file diff, with the inventory-diff receipt. Check that the A5 attempts' `measurement_files` equal that commit's inventory (17 unchanged entries plus `<R1-APPROVED SHA>`), including END and pooling code | Recorded at the production packet, as PC2 already requires. A5 asks the coordinator to tell the PC2 reviewer **now** that the reviewed commit moves |
| R3 | **Independent Opus science review** (high effort; not the drafter) | Outcome-blindness of A5; completeness of the D1–D5 disclosure; the "never pool old code" rule fixed in advance; the §5.2 PC1 interpretation; deferral and no-relaxation; whether the fix could bias timing (it changes only guard ownership, in the monitor process, at 1 Hz on the census core) | r1: ADOPT_WITH_CHANGES (`OPUS-SCIENCE-REVIEW-A5-r1.md`), T1–T13 applied. A narrow re-check of the r2 code delta per R1 |
| R4 | R3 reviewer and coordinator | **R4 (resolved): fixed-code smoke required** (A1 precondition; A2/A3 condition 1 precedent). Before the first A5 reference launch, one `e4v3-unpoolable-smoke` run on the A5 bytes passes on 08 (preferred: D ≥ 1 s exercises the race path) or on 01. It uses job parent `$base`, is outside all roots, and goes through the full C5/C6, C-a to C-d and verifier flow, with A6's pass criteria. It is disclosed, never pooled, and needs its own clean window (§6). A smoke failure means STOP and escalate; it uses no reference attempt. | Resolved (T7) |
| R5 | Coordinator | Adoption ruling. Companion actions are sequenced but are not prerequisites for the TIERS A5 series. (a) **K4S re-pin**, a K4S Amendment 3 changing `K4S-MAC-MANIFEST` c1fb1e9a by one leaf, with Sol review, before any K4S END reference or Mac K4S session. The **fleet d89cab16 and FROZEN-K4S 416f6e51 are not re-pinned**, and the running K4S reporting is not touched. Advisory (K4S is not governed by A5): running the K4S END on the old guard on a slow host uses up attempts on a known, near-deterministic false failure. (b) **A4 erratum** for `stage_nocopy.py` 96abd847 (`FROZEN_MEASUREMENT_FILES["fleet_validity.py"]`), with a narrow Sol diff review, then Mac runtime re-stage or overlay and re-verify before any Mac staging. Mac is on HOLD, so nothing in progress is affected. Under A2's "same amended bytes everywhere", no TIERS Mac session runs on a runtime that holds the superseded `fleet_validity` bytes once A5 is adopted. A4 B.6's pooled-S-forward gate binds the A5 pool. | Committed ruling |

## 8. Residual race outside this series

- **The K4S END reference runs the same `ReportingGuard`, with 10 workers spawned right after admission** (`k4s-confirm/end_reference.py:361-363`; `end_background.py:143-147`). The coordinator needs a separate K4S-side ruling before any K4S END reference: either adopt this fix through a K4S manifest re-pin, or accept the risk with disclosure.
- Any future E4 fleet reference on a slow host carries the same risk.

## 9. Open items for the reviewers

1. **Accepted vfork residual (R1, R3).** Without an exec exception, a spawn child caught pre-exec is de-owned after exec. That is a `validity_census` technical-repeat failure before timing (§3). R1 and R3 should confirm that accepting it is preferable to any identity-replacement rule.
2. **Ownership map.** The census pass means `owned_pid_start_ticks` can now include pids seen only in the census snapshot. It also keeps a pid owned in snapshot 1 even if its census row is rejected: `own_process` still compares the full tuple, so that row is flagged. This is more complete evidence, not a change in what qualifies. `validate_census` / `validate_admission` / `validate_blocks` don't read that field, and `fleet_pool` doesn't compare it across hosts.
3. **Order.** Adopting A5 makes D2's outcome irrelevant to pooling. Under outcome-blindness (§4.1), the adoption decision must not wait on, or be informed by, D2's timing content; only its existence and status may be cited.
