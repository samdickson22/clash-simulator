# K4S run r1, round r2: independent post-round audit (Proposal M, COORDINATOR 2c847954)

- Audit started at 2026-10-12T09:04:23Z (`date -u`) on 127x05. Auditor: Opus delegate, read-only.
- **Audited:**
  - receipt commit `b5530e98`, which is origin/main at audit time;
  - `rounds/r2/RECEIPT.json`, with sha256 `95e93ac89416d89a…` (matches);
  - checklist `CYCLE-CHECKLIST.md`, with sha256 `12865ae6…` (matches `authority.checklist_sha256`);
  - inventory commit `408f8779`;
  - policy commits afe83faa, adc12f36, 2c847954, 89b28b6d and 4d5791da;
  - Sol reviews ROUND-PY-r1 and ROUND-SH-r1.
- **Method:**
  - Repo bytes came from `git show origin/main:<path>`.
  - The 05 runner tree `/mpac/sdicks02/k4s-runner/run-r1` was used only for hash and listing comparisons.
  - No SSH, no edits, no commits.
  - Only descriptors, counts, hashes, health data and qualification fixtures were read. No reporting outcome was opened.

## Verdict: **PASS_WITH_NOTES**

- All seven checklist steps are evidenced, and every hash cited in the receipt matches the committed bytes. I independently re-derived the r2 ledger, the dispatch arithmetic and the exact 3000/900 coverage.
- No finding invalidates the r2 launch.
- **Before the ~11:10Z cut 2 prelaunch:** findings 1 and 2 need action, or an explicit coordinator acceptance. Neither is a BLOCK.

## Step-by-step verification

| Step | Result | Evidence checked |
|---|---|---|
| 1 Owned STOP | ✅ | **STOP and exit:**<br>- STOP touched at 08:37:46.543Z (03) and 08:37:46.567Z (04), before the 08:47:17Z 03 apt-daily.<br>- `supervisor-exit.json` reads owned_STOP on both hosts: sha 03 `bffde5d4…`, 04 `c11ae500…`. `stop-reason.json` also reads owned_STOP, with no foreign process, no console and zero apt/ssh ticks.<br><br>**Supervisor identity:** supervisor PIDs 1002822 and 37363 equal r1 `launch.json` (sha `b864703e…` / `420f7ec1…`). The dispatch sha is 46eba59b, which equals the history.<br><br>**Worker groups:**<br>- Recorded PGIDs: 1217 = 1205+11+1 and 1206 = 1194+11+1, i.e. one group per started block plus the supervisor.<br>- live_members 0.<br>- The 05 copy has 1216 `exits/` and 1216 `descriptors/` entries for 03, which equals completed + failed. |
| 2 Drain | ✅ (counts only, see F3) | **Exit lists:**<br>- 03: 1205/11/538 completed/failed/unstarted, summing to 1754.<br>- 04: 1194/11/549, summing to 1754, which equals EXPECTED for replacement-r1.<br><br>**ACKs:** acks_bound 1205+1194 = **2399**. The 05 `hub-view/replacement-r1` has exactly 2399 entries, plus 392 in `reporting`.<br><br>**Copiers:**<br>- Copiers 702958 and 711250 equal the 05 `copier/*-replacement-r1-pid.json`.<br>- copier_final reads revoked/final, with no lifecycle or fatal error.<br>- Hub and source admissions are inactive.<br><br>The returned marker and the complete-set equality are only asserted in the receipt and PROGRESS (F3). |
| 3 Inventory | ✅ | **Ledger lineage:**<br>- ledger_before `19580caa` equals the committed `blind-ledger-r1.json` and the 05 `blind-ledger-before-r2.json`.<br>- ledger_after `4a56abf3` equals the committed `blind-ledger-r2.json`, the 05 live ledger and `ledger/work-r2/blind-ledger.json`, so the working copy was promoted.<br>- The r1 events (33) are an exact prefix of the r2 events (55).<br><br>**New events:**<br>- 22 new events: **16 primary, 6 guard**, all `owned_STOP`.<br>- Their `lost` dicts equal the 22 supervisor-exit failed dicts byte-for-byte (sorted JSON).<br>- `evidence_sha256` binds each event to its host's supervisor-exit sha.<br><br>**Canonical rows:**<br>- Each replacement keeps cell, seat, own/opponent, rotation, subsample, order and population.<br>- seed − index is a single constant per population across all 1109 rows.<br>- There are no duplicate IDs.<br><br>**Dispatch contents:** every new replacement ID is in the dispatch. The never-started rows equal the 1087 unstarted dicts, apart from host and dispatch.<br><br>**Coverage:**<br>- 2791 completed (reporting 392 + r1 2399, no duplicates) plus 1109 dispatched, with no overlap.<br>- Replace-chain roots give exactly primary 0–2999 and guard 0–899, each once.<br><br>**Gates (cumulative and max k):**<br>- Cumulative lost 41/150 primary and 14/45 guard.<br>- Max k: primary 2/9, guard 1/7. |
| 4 Fresh namespace and qualification | ✅ | **Namespace:** `k4s-confirm-replacement-r2` on 03 (`jobs/clasher`) and 04 (`jobs-k4s`).<br><br>**Qualification** (committed receipts, sha 03 `201b8fc5…`, 04 `3e6d4058…`):<br>- **PASS, 28/28 checks true** on both hosts.<br>- The host and job match.<br>- Tests: 299 passed, 2 deselected.<br>- The check set is identical to r1. |
| 5 Finalize | ✅ | **Runtime pin:** the qualification `runtime-pin.json` sha equals launch.json `runtime_pin_sha256` on both hosts: 03 `5ce48005…`, 04 `7419760c…`.<br><br>**Carry-over:**<br>- The prefixes match the full hashes of the committed files: SMOKE-PASS d3ed1c61 / 5c4b7606, smoke-admission e338db63 / 9c4d636f, FROZEN 416f6e51.<br>- The copier script `47eb96d6…` equals the reviewed `oa1/mirror_k4s.py`.<br>- The 03 idle pin is recorded as PID 2180947 / 139691386 / 16152ceb.<br><br>**Dispatch:** 1df20188 has 1109 rows (1087 never-started + 22 replacements), per-host **555/554**, dispatch indices 0–1108, and Σ games 8938 (1076×8 + 33×10).<br><br>**Authorization v4** (`af5b96d7…`):<br>- It keeps the 20:04:59Z bindings, with `reporting_jobs`, phase, dispatch path/sha and ledger updated.<br>- The `ruling` text is exactly the corrected citation set (76887b33 22:10:17Z; afe83faa 22:11 UTC / 22:11:53Z; adc12f36; 2c847954; erratum file).<br><br>**Barrier:** "PASS 176 files" is asserted only (F3). |
| 6 Prelaunch | ✅ (see F1, F4, F5) | **03 timer and stamps:**<br>- apt-daily LAST 08:47:17Z, after the cut.<br>- apt lists 08:47:20Z < updates-available 08:47:30Z.<br>- release-upgrade 00:57:44Z, 8.0 h old at launch.<br><br>**04 stamps:**<br>- No timer at this cut.<br>- lists 22:06:04Z < updates 22:06:15Z.<br>- release-upgrade 21:32:48Z, 11.4 h old at launch and about 13.6 h at the 11:10Z cut, so fresh under the 24 h rule.<br><br>**Handshake ordering is correct:**<br>- "03 quiet" 08:47:47Z, after apt-daily's lists/stamps settled.<br>- Coordinator GO 08:48:14Z (PROGRESS).<br>- Builder read 08:49:03–08:51:29Z (4d5791da).<br>- Builder receipt fa8e700a committed 08:51:48Z.<br>- Coordinator forwarded "released" 08:52:17Z.<br>- **03 launch 08:57:13Z**.<br>- The 30-min timeout (09:18:14Z) was not reached. |
| 7 Launch | ✅ | **Copiers:** the copier was started before the supervisor on each host. 03: copier 485959 at 08:57:06Z, supervisor at 08:57:13Z. 04: copier 494063 at 08:57:11Z, supervisor at 08:57:17Z.<br><br>**launch.json:**<br>- The host is correct.<br>- dispatch_sha256 = **1df20188** on both hosts.<br>- sha 03 `1d917968…`, 04 `ea88e4d5…`.<br><br>**Admission:** admitted, foreign 0, active 0, who "".<br><br>**History:**<br>- The history appends replacement-r2 / 1df20188.<br>- `history_sha256` b462ac84 equals the committed file and the 05 copy.<br><br>**First health check:** the r2 health at 08:58:05Z shows 544+11 = 555 and 543+11 = 554, with no anomalies. |

## Numbered findings

1. **MEDIUM. `tools/aptquiet_remote.sh` is new, unreviewed code run on 03/04 in step 6. It fails open, and it can't run under the mandated strict mode. Action is needed before cut 2.**
   - **Status:** it was committed in b5530e98; the 05 copy's mtime is 08:40Z. Proposal M allows "no new code … frozen tools only", and 4d5791da (08:52Z) requires review before any new script that touches a host.
   - **Strict-mode failure:** under the checklist's `bash -euo pipefail`, the script aborts with no output in exactly the quiet state:
     - `systemctl is-active` exits 3 for inactive units;
     - `grep` exits 1 when no process matches.

     I confirmed both abort locally with control pipelines. So the recorded `apt_units: inactive`, `apt_processes: 0` cannot have come from a strict-mode run.
   - **Fail-open without pipefail:** a failed `ps` yields `procs=0`, which is the fail-open pattern Sol flagged in R2-6.
   - **r2 is still covered:** other evidence independently corroborates the quiet state:
     - the frozen host admission (0 foreign, 0 active);
     - the apt-lists and stamp timestamps;
     - the 08:58:05Z health (apt flags 0).
   - **Before the cut-2 prelaunch:**
     - either get the script reviewed and fixed (capture and check `ps`/`systemctl` exit status, and tolerate grep's no-match exit);
     - or do the step-6 reads inline under strict mode, with `ps` captured and checked before filtering.

     Record which was done.

2. **MEDIUM. The `checkpoint.py` change is not purely mechanical, and the receipt under-describes it.**
   - **Mechanical, correct parts:**
     - NS default to replacement-r2;
     - per-host `EXPECTED` 555/554, which equals the dispatch;
     - the `exp[h]` unwrap;
     - the `watch.sh` default phase.
   - **Substantive part:** the same diff deletes the 11105b3f per-phase alert (≥24 primary or ≥7 guard lost) and adds a gate that reads the ledger:
     - cumulative ≥150/45 out of 300/90;
     - max `replacement_k` ≥9/7.

     This matches Option A and Proposal M. Its logic is correct against the ledger schema: it reproduces 41/14 and k {primary 2, guard 1}, as in the 08:58:05Z health.
   - **Problems:**
     - (a) The receipt's `health_tool_change` omits this gate rewrite.
     - (b) **Provenance.** This logic was already running from 2026-10-11T22:41:59Z: the committed health JSON (277cfc78) carries `cumulative_lost` and the "cumulative …/300" summary. The committed tool at 7ee26396 (da2d5bd1) still had the old rule. So for about 10 h the health tool that ran was not the committed one.
     - (c) No review since Sol OPS-TOOLS r1, although it SSHes to hosts.
   - **Recommendation:** record a PROGRESS disclosure, and get coordinator acceptance or a review before more edits.

3. **LOW. Receipt hash gaps.** The checklist says "commit RECEIPT.json with every hash". Several steps are recorded only as counts or booleans, with no hash and no committed artifact:
   - **Step 1:** the final owned-supervisor admission and the `ps` census output. The `stop-reason.json` files are committed but not hashed in the receipt: 03 `3ebe49247ac18253…`, 04 `9c9d985fe3bc5be8…`.
   - **Step 2:** the completed-ID set, the ACK/returned set, the final copy-health and the hub/source admission records. The hub-view inventory is not hashed either.
   - **Step 4:** extras-tar sha, overlay 175/175 and PREREG 9650972d appear in PROGRESS only.
   - **Step 5:** the barrier output, the idle-pin read and the runtime-equality evidence are booleans only. Carry-over appears as 8-hex prefixes; they do match the full hashes.
   - **Step 7:** the `launch_phase.sh` copier registrations.

   Nothing I could check contradicts these assertions, but they are operator-attested. Sol R2-1/R2-2 asked for them to be persisted. **Recommendation:** add them to the r3 receipt.

4. **LOW. Receipt timestamps are imprecise.**
   - The receipt has `coordinator_go: "~…08:48Z"` and `released_forwarded: "…08:52Z"`, while PROGRESS has the exact `date -u` values 08:48:14Z and 08:52:17Z. The checklist requires copied `date -u` times.
   - The builder's own "released" time (08:51:50Z) is not in the repo. The nearest evidence is fa8e700a, committed at 08:51:48Z.
   - The ordering holds either way.

5. **INFO. "03 quiet" did not mean 03 was idle.**
   - K4S's own fresh qualification on 03 (PGID 2102837, 08:39:43–08:54:59Z) ran through apt-daily (08:47:17Z), the "quiet" post and the builder read.
   - This complies with the checklist, which requires only that the phase has exited.
   - Qualification passed 28/28, including the charge-share tolerance checks, and the builder read was bounded by SHA checks. So there is no effect on either party.
   - It should be disclosed to the coordinator and the builder for future windows.

6. **INFO. `max_k` is a 0-based per-cell index.** For example, primary cell 10 has replacement_k 0, 1, 2, so three replacements.
   - The receipt, checkpoint and gates all use that index, consistently with r1.
   - Whether the Option A "k limit 11/9" refers to an index or a count is at most a 1-step difference, and the current value is far from the gate.
   - Worth one line from the coordinator.

7. **INFO. Timers for the next window.**
   - 04 apt-daily is at 11:20:02Z, only 10 min after the ~11:10Z cut.
   - The motd-news timers (03 09:31:08Z, 04 10:52:04Z) fall inside r2. They are not the motd release-upgrade check, and r1's health record shows no anomaly across motd-news.
   - Both release-upgrade stamps stay fresh through 11:10Z.

8. **No reporting outcome is exposed.**
   - The receipt, ledger, dispatch, supervisor-exit, stop-reason, launch, authorization and health files carry only design descriptors, counts, hashes and operational flags.
   - The "scored"/"charge" fields in the qualification receipts are qualification-fixture statistics, not reporting games.
   - `outcomes_read: false` and `sealed: true` throughout.

9. **No arithmetic errors found.** Every count in the receipt re-derives:
   - 1205+11+538 = 1194+11+549 = 1754;
   - 2399 ACKs;
   - 22 = 16+6;
   - 41+14 = 55 ledger events;
   - 2791+1109 = 3900;
   - 1087+22 = 1109 = 555+554;
   - 8938 games;
   - 1217/1206 PGIDs.
