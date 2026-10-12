# K4S run r1, round r4 (final round): independent post-round audit (Proposal M, COORDINATOR 2c847954)

- Written at 2026-10-12T14:14:18Z (`date -u`) on 127x05. Auditor: Opus, read-only.
- **Audited:**
  - receipt commit `b5bc0c86`. `rounds/r4/RECEIPT.json` has sha256 `8aec45fa3aa66e74…`, identical at `b5bc0c86` and at origin/main `5a82cc857`;
  - `rounds/r4/RECEIPT-ERRATUM.md` (c5e69b6a, then 5a82cc85; current sha256 `c3e65b48…`);
  - checklist `CYCLE-CHECKLIST.md` at its latest commit, 2a6d8fae (cut-3 conditional read window; quiet-read v3). Its sha256 `99fa0b05…` equals `authority.checklist_sha256`;
  - cut-3 inventory commit 70d1bc459;
  - prior audit `ROUND-r3-AUDIT.md` and its rulings in COORDINATOR 94ad775b;
  - deployed health tool 05d0908f (commit 5fb5a398);
  - cut-3 read window: declared at 328fb83e, GO 8be7ca00, released 3f7240f9.
- **Method:**
  - I read repo bytes from `git archive origin/main` into scratch and recomputed every hash and count with my own scripts.
  - I used the 05 runner tree `/mpac/sdicks02/k4s-runner/run-r1` only for hash, listing and `diff`.
  - I read the GO receipt and the perception owner's cut-3 receipts read-only.
  - I ran the committed `checkpoint.py` test suite and an r4-shaped simulation in `/tmp` scratch.
  - No SSH, no edits outside this file, no commits. I opened no reporting outcome.

## Verdict: **PASS_WITH_NOTES**

- All seven checklist steps are evidenced and correct.
- All **76** evidence files listed in `evidence_sha256` exist at `b5bc0c86` and at origin/main, and match their hashes. No evidence file is unlisted. The 05 `rounds/r4` tree is byte-identical to the committed one (`diff -rq` clean).
- Every artifact hash cited in the receipt matches the committed bytes and the live copies on 05:
  - dispatch `3aa43065`;
  - authorization v6 `33e4526a`;
  - ledger before `153eb421` and after `649272bd` (the 05 live ledger is `649272bd`);
  - both qualification receipts;
  - history `94ee52e0`;
  - checklist `99fa0b05`;
  - `quiet-read-v3.cmd` `a293207e`;
  - deployed `checkpoint.py` `05d0908f`.
- I independently re-derived:
  - the 22 ledger events;
  - k;
  - the gates;
  - the exact 3000/900 coverage;
  - the dispatch arithmetic.
- The handshake order (quiet → GO → per-host release → per-host launch) holds on both hosts.
- **r4's natural end is guarded.** The deployed tool reads the expected counts (71/68) from dispatch 3aa43065 and flags any shortfall (finding 7).
- **Nothing blocks.** Finding 1, the timeout basis, is already corrected by the receipt erratum and was immaterial.

## Step-by-step verification

| Step | Result | Evidence checked |
|---|---|---|
| 1 STOP | ✅ | **STOP and exit:**<br>- `stop-touch`: 03 at **13:16:55.777Z**, 04 at **13:16:55.781Z**. Both are before 04's apt-daily-upgrade (13:27:59Z), which satisfies the 94ad775b ruling ("before 13:27:55Z").<br>- `supervisor-exit.json` and `stop-reason.json` read **owned_STOP** on both hosts, with foreign [], foreign_active [], console 0 and zero ssh/apt ticks.<br>- Exit 03 at 13:17:00Z (gone-check 13:17:01.124Z); exit 04 at 13:16:59Z (gone-check 13:17:00.286Z).<br><br>**Supervisor identity:** supervisor PIDs 2373197 and 1396984 equal the r3 `launch.json` and the admissions. dispatch_sha256 is `ab8b6238`, which equals history replacement-r3.<br><br>**Groups empty:** I checked the `ps -eo pgid,pid,stat` census myself (03 at 13:17:22Z, rc 0, 1249 lines; 04 at 13:17:24Z, rc 0, 1312 lines) against every PGID in the final admission:<br>- 03: 231 = 230 worker groups + 1 supervisor;<br>- 04: 229 = 228 + 1.<br><br>There are **0 live (non-zombie) members**. The worker groups equal completed + failed (219 + 11, 217 + 11). |
| 2 Drain | ✅ | **Completed-ID sets:** `complete-ids` equal the supervisor-exit completed lists, 219 (03) and 217 (04), with no duplicates. completed + failed + unstarted equals the r3 dispatch rows of each host exactly (286, 289).<br><br>**ACK bindings:** **436 = 219 + 217**, every line well-formed (`complete`/`hub_ack`/`returned` 64-hex, `ok=True`), IDs equal to the complete sets. The hub view has 436 entries, equal to the union, and each path is on the correct host's job.<br><br>**Copier exit (r3 F2c, now persisted):** STOP-COPY was written at 13:17:24.826Z. `ps -p 876522` and `ps -p 884802` gave **rc=1** at 13:17:34.263Z and 13:17:33.226Z.<br><br>**Copy health:** final copy-health reads revoked, final and sealed, with listed = durable = returned (219, 217), pending [] and no error, lifecycle or block error.<br><br>**Admissions:** hub = source (byte-identical), `active=false`, same identity as the exited copier, `finished_utc` 13:17:25Z. STOP-COPY was removed at 13:17:47.461Z and 13:17:47.465Z (`exists=no`). |
| 3 Inventory | ✅ | **Run order:** replace.py ran 13:17:49.778Z–13:17:50.748Z (rc 0). Validation read at 13:18:01.884Z, publish at 13:18:16.616Z, so **the ledger was published after the checks**. `published.txt` hashes equal the committed before/after ledgers and the dispatch.<br><br>**Ledger:**<br>- The 77 r3 events are an exact prefix of the 99 r4 events.<br>- **22 new events** have `lost` dicts equal to the 22 r3 failed dicts: 16 primary, 6 guard, all owned_STOP.<br>- Each event's `evidence_sha256` is its host's supervisor-exit sha (`cccb8683`/`91475244`, which equal `phase-meta` and the step-1 evidence).<br>- The 22 new replacement rows are in the dispatch byte-for-byte.<br><br>**Coverage:** counted 3761 = reporting 392 + r1 2399 + r2 534 + r3 436, no duplicates and no lost ID among them. Dispatch 139, disjoint from both. 3761 + 139 = **3900**, and the replacement-chain roots are exactly primary 0–2999 and guard 0–899, **each once**.<br><br>**Gates:**<br>- Cumulative lost: **73/150** primary and **26/45** guard (99 = 73 + 26).<br>- k values run 0…n−1 contiguously in every cell. Max k is **3/8** primary (cells 10 and 19) and **3/6** guard (cell 6).<br><br>All clear. |
| 4 Stage | ✅ | **Namespaces:** fresh `k4s-confirm-replacement-r4`, staged on 03 at 13:18:19Z and on 04 at 13:18:22Z, both after the publish.<br><br>**Staging checks:**<br>- extras sha checked on each host (`3ec8f9da…`, `4488d675…`);<br>- **overlay 175/175**, now persisted per file: 175 `OK` lines, 0 others, on each host;<br>- PREREG `9650972d…`;<br>- STOP links to `<job>.STOP`.<br><br>**Qualification launched:** 03 PGID 2573704, 04 PGID 1596026. |
| 5 Finalize | ✅ | **Qualification:**<br>- markers BELIEF-QUALIFIED, FINISHED, QUALIFIED and TESTS-PASS are present;<br>- both receipts are **PASS with 28/28 checks true**, 299 passed and 2 deselected;<br>- host and job match;<br>- the runtime pin equals the `launch.json` pin: 03 `4212ffd7`, 04 `711af336`;<br>- the runtime maps equal the smoke job's, and pin.verify is OK.<br><br>**Carry-over full hashes:** FROZEN `416f6e51…`, SMOKE-PASS `d3ed1c61…`/`5c4b7606…`, smoke-admission `e338db63…`/`9c4d636f…`. Dispatch copy `3aa43065`. No supervisor admission was present.<br><br>**Idle pin (03):** 2180947 / 139691386 / `16152ceb…`.<br><br>**Authorization v6 `33e4526a`:** the evidence copy equals the receipts copy. The field diff against v5 is only phase, dispatch path/sha, reporting_jobs, ledger path/sha and prior_jobs (+r3); the ruling text is unchanged.<br><br>**Barrier:** PASS 176, rc 0, fresh slot, who 0. 03 ended at 14:03:34Z and 04 at 14:03:35Z. Finalize ran at 14:03:16Z and 14:03:18Z, after the release. |
| 6 Prelaunch | ✅ | **apt-daily-upgrade fired after the cut and exited:**<br>- 04 fired at 06:27:59 PDT = **13:27:59Z** and was `inactive` at 13:28:22Z;<br>- 03 fired at 06:47:03 PDT = **13:47:03Z** and was `inactive` at 13:47:23Z.<br><br>**Quiet-read v3 (`a293207e`, bytes equal to the checklist command):** every read records its read_utc, full stdout and `rc=0`. Every read shows both units inactive, maint 0, who 0, and only the pinned helper (03 PID 2368, 04 PID 2296, unchanged).<br><br>**Two consecutive reads per host:**<br>- before the window: 13:47:38Z and 13:48:09Z on both hosts;<br>- before launch: 03 at 14:03:50Z and 14:04:21Z; 04 at 14:03:51Z and 14:04:22Z.<br><br>**Handshake:**<br>- "03/04 quiet" posted at 13:48:10Z;<br>- GO 8be7ca00 (commit 14:01:29Z, **`go_utc` 14:01:30Z**, received 14:01:48Z);<br>- perception claims at 14:02:19.5Z and 14:02:20.7Z (≥ go_utc + 30 s); sessions closed at 14:02:21.67Z (03) and 14:02:22.00Z (04);<br>- "released 127x03/127x04" received at 14:03:15Z (3f7240f9 commit 14:03:12Z);<br>- finalize 14:03:16Z; launches at **14:04:39Z** and **14:04:44Z**.<br><br>No K4S evidence falls inside 13:48:24Z–14:03:16Z. No timeout occurred.<br><br>**Stamps** (read_utc 14:04:22.811Z and 14:04:23.193Z, after the release and before the copiers):<br>- release-upgrade stamps are 13 h 06 m old (03) and 16 h 31 m old (04);<br>- updates-available is newer than the lists on both hosts (03 08:47:30 > 08:47:20; 04 11:20:18 > 11:20:08).<br><br>**Next timers:**<br>- 03 apt-daily at 20:36:30Z;<br>- 04 apt-daily at 00:25:02Z on 10-13;<br>- motd-news at 01:35:47Z and 02:15:31Z on 10-13.<br><br>These equal `window_limits`. |
| 7 Launch | ✅ | **Copier first, on each host:**<br>- 03: copier 2182223 at 14:04:33Z, registered, `launch.sh` at 14:04:35Z, admission at 14:04:38Z, `launch.json` at 14:04:39Z.<br>- 04: copier 2190563 at 14:04:37Z, `launch.sh` at 14:04:40Z, admission at 14:04:43Z, `launch.json` at 14:04:44Z.<br><br>`launch_phase.sh` rc 0.<br><br>**Registrations:** bound to the new PID, job, phase `replacement-r4` and source host, with `active=true`. The hub and source records are identical. The copier script equals committed `oa1/mirror_k4s.py` `47eb96d6`, which is the 05 deployed copy. Both copiers are live on 05 now.<br><br>**launch.json:** host is correct and dispatch is **3aa43065** on both hosts.<br><br>**Admission:** admitted, foreign 0, active 0, console 0.<br><br>**Post-launch check (14:05:04Z, 14:05:05Z):** the supervisor is alive, there is no STOP file, and the copier matches its registrations.<br><br>**History:** the history appends r4 / 3aa43065 / 14:04:39Z. |

## Arithmetic (recomputed)

- **Stopped r3:**
  - 03: 219 + 11 + 56 = 286;
  - 04: 217 + 11 + 61 = 289;
  - total 575, which equals the r3 dispatch ab8b6238.
- **ACKs:** 219 + 217 = **436**.
- **Failed and unstarted:** failed 11 + 11 = **22** (16 primary + 6 guard); unstarted 56 + 61 = **117**.
- **New dispatch:** 117 + 22 = **139** = 71 + 68.
  - The new replacements split 12 (03) / 10 (04). The never-started rows were re-placed by the frozen scheduler: 03 holds 59 and 04 holds 58.
  - Every carried row is content-identical except `dispatch` and `host`. Dispatch indices run 0–138 contiguously.
- **Ledger:** 77 + 22 = **99** events = 73 primary + 26 guard.
- **Losses by phase:** reporting 33, r1 22, r2 22, r3 22.
- **Coverage:** 392 + 2399 + 534 + 436 = **3761**; 3761 + 139 = **3900** = 3000 + 900.
- **Games:**
  - 103 × 8 + 14 × 10 = 964 (never-started; the 14 ten-game rows are subsample rows);
  - 22 × 8 = 176 (replacements);
  - total **1140**.
- **Time limits:**
  - **P2 timeout:** go_utc 14:01:30Z + 30 min = **14:31:30Z**. Releases came at 14:03:15Z, 1 min 45 s after go_utc.
  - **Window:** 04 launch to 04 release-stamp expiry (21:32:48Z) is 7 h 28 m 04 s. 03 launch to 03 apt-daily (20:36:30Z) is 6 h 31 m 51 s.
- **First r4 health (14:11:21Z, no anomalies):**
  - 03: 9 + 0 + 11 + 51 = 71;
  - 04: 10 + 0 + 11 + 47 = 68.

## Numbered findings

1. **LOW (already corrected). Timeout basis (task item 3).**
   - **What the receipt says.** `times.coordinator_go` and `times.timeout` use the 8be7ca00 commit time: 14:01:29Z, and 14:31:29Z for the timeout. The receipt says "no go_utc field published", and `evidence/step6/read-window.txt` carries the same basis.
   - **What is true.** A `go_utc` *was* published. It is in the GO receipt `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/supplement-go-receipt-cut3.json`:
     - sha256 `b08b77a46d01e5db6c59b19368ad91a469f10e93c25cf084c81e5c24decc59bf`;
     - mtime 14:01:30.95Z;
     - `"go_utc": "2026-10-12T14:01:30Z"`.
     8be7ca00 cites this receipt by path. The r3 erratum (0fd243c8) had also committed "from r4 on, the read-window timeout counts from the GO's `go_utc`", so this repeats r3 F2(d).
   - **Correction.** The correct values are **go_utc 2026-10-12T14:01:30Z** and **timeout 2026-10-12T14:31:30Z**. `RECEIPT-ERRATUM.md` (commit 5a82cc85, recorded 14:06:54Z) already makes this correction, citing the same file and sha. The receipt and its hashed `read-window.txt` stay as committed; the erratum supersedes them.
   - **Impact: none.** The difference is 1 s. Both releases came 28 min 15 s before either timeout, and no launch depended on a timeout.

2. **LOW. The driver-dead check was not persisted, and the disclosure has a time slip.**
   - `disclosures[0]` says "13:48:2xZ". The erratum corrects it to 13:48:24Z, with PGIDs 2573704 and 1596026 at 0 live members.
   - That read's output was not saved, which falls short of the r3 erratum's "every evidence file records the `date -u` of its read".
   - **Indirect corroboration:**
     - QUALIFICATION-FINISHED markers are present;
     - the qualification receipts are stamped 13:34:51Z (03) and 13:33:46Z (04), before "03/04 quiet";
     - the 14:04:38Z and 14:04:43Z host admissions list no process in either qualification PGID.
   - The hosts were therefore idle during the window. This is the stronger form of r3 F4, achieved by finishing qualification before "quiet".

3. **INFO. Exact-time and evidence-shape residuals (r3 F2/F5 mostly resolved).**
   - **Resolved since r3:**
     - the copier `ps` result is persisted;
     - one time per event (`finished_utc` for the copier, timer LAST for apt);
     - `read_utc` inside the quiet, stamp, census, finalize and barrier files;
     - per-file overlay output;
     - STOP-COPY write and removal evidenced.
   - **Remaining:**
     - `ack-bindings`, `hub-view` and `overlay-check` carry no in-file read time. They are bracketed by neighbouring evidence: 13:17:22–13:17:47Z and 13:18:16–13:18:22Z.
     - `replace-stdout.txt` is still rc + times only.
     - pin.verify is just "OK".
     - `quiet_posted` (13:48:10Z) and the copier cores (62/63) appear only in the receipt and PROGRESS.
   - None of this contradicts the asserted results.

4. **INFO. Undisclosed: 04's qualification overlapped 04's apt-daily-upgrade.**
   - 04's qualification ran 13:18:22–13:33:46Z. apt-daily-upgrade fired at 13:27:59Z and was inactive by 13:28:22Z.
   - Cut 2 had the same overlap (apt-daily at 11:20:06Z during the 11:10:57–11:26:04Z qualification), and the r3 audit did not flag it.
   - The checklist does not forbid it, and qualification passed 28/28. The receipt's disclosures don't mention it. The coordinator may want to note it.

5. **INFO (outside receipt scope; r3 F9 follow-up). The 04 DBus flag is persistent.**
   - The final r3 health read (13:16:40Z) shows `flags[dbus 213]` of 216 completed blocks on 04, against 0 of 218 on 03. The first r4 read shows 7 of 10 on 04 and 0 of 9 on 03. r2 showed the same pattern.
   - `checkpoint.py` counts it but doesn't alert on it.
   - I did not determine how PREREG-K4S treats OP-1 DBus-flagged blocks at reduction. The coordinator should confirm this before END/reduction, since it is a per-host systematic.

6. **INFO. Perception cut-3 receipts are not on origin/main.**
   - `l1/receipts/b08-supplemental-proof-export-20261012-r1/` is untracked in the shared checkout. It is the perception owner's to commit.
   - I used it read-only to confirm the claims (14:02:19.5Z/14:02:20.7Z), the session closes (14:02:21.67Z/14:02:22.00Z) and `go_utc` 14:01:30Z.
   - The cut-2 receipts (r3 F7) are now committed.

7. **INFO. r4's expected end is verified (task item 4).** The deployed `checkpoint.py` is `05d0908f`, which equals the committed copy and the 05 copy. Sol r6 APPROVE names `05d0908f…`.
   - **Expected counts:** `expected_counts()` resolves `replacement-r4` through `rounds/history.json` to `dispatch/replacement-r4.json`. It checks the sha against history (3aa43065) and against each host's `launch.json`, and yields **71/68**. The live r4 read at 14:11:21Z records `expected` 71/68 and LAUNCHDISPATCH `3aa43065` on both hosts.
   - **On a supervisor exit:**
     - a non-null reason is an anomaly;
     - complete < expected is an anomaly;
     - completed + failed + unstarted ≠ dispatched is an anomaly;
     - completed ≠ the count of `complete.json` files is an anomaly;
     - a null exit with unstarted > 0 is an anomaly;
     - any failed block is an anomaly.
     `supervise.py` writes `reason=None` (JSON `null`) on a natural end, and the remote grep yields `"reason": null`. I checked this on a copy of the real exit file.
   - **Tests.** The committed suite gives 125/125, also under `-O`.
   - **My simulation** used the real r4 history, dispatch and ledger:
     - null exit at 71/68 with lists 71/0/0 and 68/0/0 → **rc 0, no anomalies**;
     - 70 completed + 1 unstarted, 70 + 1 failed, short exit lists, owned_STOP at 71/68, or an r3 launch dispatch → **rc 2**, each with the specific anomaly.
   - **Residual notes:**
     - (a) The ACK-lag alert fires only above 15, so the end-of-run ACK/durability completeness must come from the planned final pass (PROGRESS 14:08:03Z, completion plan step 1). That pass should also do the step-2 drain for r4: STOP-COPY, copier `ps` exit, revoked health, inactive admissions.
     - (b) Health must run with `K4S_NS`/`K4S_PHASE` set to r4. The running watch has them. Omitting them fails closed (a wrong phase or namespace raises a launch-dispatch, exit or expected-count anomaly).
     - (c) At the observed rate (about 9–10 blocks per host in the first 7 min), r4 should end well inside the 20:36:30Z / 21:32:48Z limits.

8. **INFO. r3-audit follow-through: all resolved.**

   | r3 finding | r4 status |
   |---|---|
   | **F1** health tool can't flag a short null exit | **Fixed in code before the r4 launch.** 05d0908f was deployed at 12:14:17Z (commit 5fb5a398) after Sol r4/r5 REQUEST_CHANGES and r6 APPROVE. A hand check covered the interim until the first clean live runs (12:19:52Z, 12:24:43Z). The fix is verified in finding 7. |
   | **F2** exact-time labels | The r3 erratum (0fd243c8) is committed. In r4, (a), (b), (c) and (e) are honoured. (d), the go_utc basis, slipped again and is corrected by the r4 erratum (finding 1). |
   | **F3** quiet-read v2 pattern | Quiet-read v3 `a293207e` adds `apt-config` and `apt.systemd.dai`. It was tested read-only at 11:39:36Z and 11:40:07Z on both hosts, and `pattern-check.txt` shows v3 matches both names where v2 missed them. It is the checklist command, used for all 8 cut-3 reads. |
   | **F4** qualification during the window | This time qualification finished before "quiet" (13:33:46Z and 13:34:51Z), so the hosts were idle during the window. Residual in finding 2. |
   | **F5** summary-level evidence | Mostly resolved; residuals in finding 3. |
   | **F6** cut-3 timing | Followed: STOP at 13:16:55Z, before 13:27:55Z. The window limits are recorded. |
   | **F7** perception receipts | Cut 2 is committed; cut 3 is pending (finding 6). |
   | **F9** DBus on 04 | Persisting (finding 5). |

9. **No reporting outcome is exposed (task item 6).**
   - The receipt, ledger, dispatch, authorization, supervisor-exit, stop-reason, admission, launch, census, ACK, copy-health and health files carry only descriptors, counts, hashes and operational flags.
   - The only outcome-like keys in the 76 files are `scored` / `scored_hit` in the qualification receipts, which are deadline/belief fixture statistics, as in r3.
   - `outcomes_read: false` and `outcomes_sealed` / `sealed: true` hold throughout. I opened no game file.

10. **No arithmetic errors.** Every count in the receipt re-derives; see the Arithmetic section.
