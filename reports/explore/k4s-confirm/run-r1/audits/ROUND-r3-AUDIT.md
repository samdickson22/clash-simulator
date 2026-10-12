# K4S run r1, round r3: independent post-round audit (Proposal M, COORDINATOR 2c847954)

- Written at 2026-10-12T11:38:17Z (`date -u`) on 127x05. Auditor: Opus, read-only.
- **Audited:**
  - receipt commit `ece533d8` (origin/main at audit time). `rounds/r3/RECEIPT.json` has sha256 `0fa8685fe6d6ded1…` (matches) and schema `clasher.k4s.round-receipt.v2`;
  - checklist `CYCLE-CHECKLIST.md` at its latest commit, c77f4db9 (cut-2 perception window; quiet-read v2 from 3c1379b5). Its sha256 is `fed13194…`, which equals `authority.checklist_sha256`;
  - cut-2 inventory commit `e0dff18f`;
  - rulings 38ed75a2 and 9acbe743, GO c00317cf and release 1b7f3a60;
  - deployed health tool commit 00926208;
  - prior audit `ROUND-r2-AUDIT.md`.
- **Method:**
  - I read repo bytes from `git archive origin/main` into scratch and recomputed every hash and count with my own scripts.
  - I used the 05 runner tree `/mpac/sdicks02/k4s-runner/run-r1` only for hash, listing and mtime comparisons.
  - I also read the perception owner's B gap-export receipts and the GO receipt, read-only, to corroborate the release order.
  - No SSH, no edits outside this file, no commits.
  - I opened no reporting outcome. I read only descriptors, counts, hashes, health data and qualification fixtures.

## Verdict: **PASS_WITH_NOTES**

- All seven checklist steps are evidenced.
- All **69** evidence files listed in `evidence_sha256` exist and match their hashes. No evidence file is unlisted, and the 05 evidence tree is byte-identical to the committed one (`diff -rq` clean).
- Every artifact hash cited in the receipt matches the committed bytes: dispatch, authorization v5, ledger before and after, both qualification receipts, history and checklist.
- I independently re-derived:
  - the ledger events;
  - k;
  - the gates;
  - the dispatch arithmetic;
  - the exact 3000/900 coverage.
- The handshake order (quiet → GO → per-host release → per-host launch) holds on both hosts.
- **Nothing blocks cut 3.** Finding 1 must be fixed in code, or explicitly accepted by the coordinator, **before the r4 launch (step 7 of cut 3)**. The cut-3 STOP and inventory can proceed either way.

## Step-by-step verification

| Step | Result | Evidence checked |
|---|---|---|
| 1 STOP | ✅ | **STOP and exit:**<br>- `stop-touch`: 03 at 11:09:30.516Z, 04 at 11:09:30.532Z, both before 04's apt-daily (11:20:06Z).<br>- `supervisor-exit.json` and `stop-reason.json` read **owned_STOP** on both hosts, with foreign [], foreign_active [], console 0 and zero ssh/apt ticks.<br>- Exit 03 at 11:09:31Z (gone-check 11:09:31.876Z); exit 04 at 11:09:33Z (gone-check 11:09:33.884Z).<br><br>**Supervisor identity:** supervisor PIDs 2116555 and 1140717 equal the r2 `launch.json` and the admission files. dispatch_sha256 is `1df20188`, which equals the history entry for replacement-r2.<br><br>**Groups empty:** I checked the `ps -eo pgid,pid,stat` census myself (03 at 11:09:48Z, rc 0, 1242 lines; 04 at 11:09:49Z, rc 0, 1311 lines) against every PGID in the final admission:<br>- 03: 280 groups = 268 + 11 + 1 supervisor;<br>- 04: 278 groups = 266 + 11 + 1.<br><br>No non-zombie member and no PID equal to any group remains, so **0 live members**. |
| 2 Drain | ✅ | **Completed-ID sets:** they equal the supervisor-exit completed lists, 268 (03) and 266 (04), with no duplicates and no overlap with failed or unstarted.<br><br>**ACK bindings:** the binding listing has exactly those IDs, each `ok=True`, **534 = 268 + 266**. The hub view has 534 entries, equal to the union, and each path is on the correct host's job.<br><br>**Copy health:** final copy-health reads revoked, final and sealed, with listed = durable = returned (268, 266), pending [] and no error, lifecycle or block error.<br><br>**Copier admissions:** hub and source admissions are `active=false`, with an identical identity (copiers 485959 and 494063) and finished at 11:10:02Z and 11:10:01Z. |
| 3 Inventory | ✅ | **Run order:** replace.py ran at 11:10:25Z (rc 0). The 05 mtimes show validation at 11:10:36.56Z, then publish at 11:10:51.84Z, so **the ledger was published only after the checks**. `published.sha256` equals the committed ledgers and dispatch, and the 05 live copies.<br><br>**Ledger:**<br>- The r2 events (55) are an exact prefix of the r3 events.<br>- **22 new events** have `lost` dicts equal to the 22 r2 failed dicts: 16 primary, 6 guard, all owned_STOP.<br>- Each event's `evidence_sha256` is its host's supervisor-exit sha (834fc247 or 37aafa6a).<br>- Every new replacement row is in the dispatch byte-for-byte, and its ID is new.<br><br>**Coverage:** 3325 completed (reporting 392 + r1 2399 + r2 534, no duplicates) + 575 dispatched = **3900**. The replacement-chain roots are exactly primary 0–2999 and guard 0–899, **each once**.<br><br>**Gates:**<br>- Cumulative lost: **57/150** primary and **20/45** guard (55 + 22 = 77 = 57 + 20).<br>- k is a 0-based index within each cell, and every cell's values run 0…n−1. Max k is **3/8** primary (cell 19, 4 replacements) and **2/6** guard (cell 6, 3 replacements).<br><br>All clear. |
| 4 Stage | ✅ | **Namespaces:** fresh `k4s-confirm-replacement-r3`, staged on 03 at 11:10:54Z and on 04 at 11:10:57Z, both after the publish.<br><br>**Staging checks:**<br>- extras sha checked on each host;<br>- overlay 175/175;<br>- PREREG `9650972d…`;<br>- STOP links to `<job>.STOP`.<br><br>**Qualification launched:** 03 PGID 2360714, 04 PGID 1383353. |
| 5 Finalize | ✅ | **Qualification:**<br>- markers BELIEF-QUALIFIED, FINISHED, QUALIFIED and TESTS-PASS are present;<br>- both receipts are **PASS with 28/28 checks true**, 299 passed and 2 deselected;<br>- host and job match;<br>- the runtime pin sha equals the `launch.json` pin: 03 `b93816cc`, 04 `7a3d52ea`;<br>- the runtime maps equal the smoke job's, and pin.verify is OK.<br><br>**Carry-over full hashes:** FROZEN `416f6e51…`, SMOKE-PASS `d3ed1c61…`/`5c4b7606…`, smoke-admission `e338db63…`/`9c4d636f…`. No supervisor admission was present.<br><br>**Idle pin (03):** 2180947 / 139691386 / `16152ceb…`.<br><br>**Authorization v5 `7f3f7b5e`:** the field diff against v4 is only phase, dispatch path/sha, reporting_jobs, ledger path/sha and prior_jobs; the ruling text is unchanged.<br><br>**Barrier:** PASS 176, rc 0, on 03 at 11:27:45Z and 04 at 11:27:47Z. |
| 6 Prelaunch | ✅ | **04's apt-daily ran and exited:** the timer fired at 11:20:06Z (04:20:06 PDT). The unit was `inactive` at 11:20:32Z, with apt lists at 11:20:08Z and updates-available at 11:20:18Z.<br><br>**Quiet-read v2:** `rounds/r3/quiet-read-v2.cmd` sha256 is **08aabe92…** (matches), and its bytes equal the checklist command. Every read records its full stdout and `rc=0`, and the output format is v2's (`helper=`, `maint_lines=<<>>`, `maint=`, `who=`). Every read shows both units inactive, maint 0, who 0, and only the pinned helper (03 PID 2368, 04 PID 2296, unchanged).<br><br>**Two consecutive reads per host:**<br>- window: 03 at 11:20:32Z and 11:21:04Z; 04 at 11:20:33Z and 11:21:04Z;<br>- prelaunch: 03 at 11:27:55Z and 11:28:26Z; 04 at 11:27:56Z and 11:28:27Z.<br><br>**Handshake:**<br>- "03/04 quiet" posted at 11:21:05Z, with qualification disclosed;<br>- GO c00317cf (commit 11:22:38Z, `go_utc` 11:22:39Z, received 11:22:52Z);<br>- **04:** perception session closed at 11:24:24.955Z, released relayed at 11:24:49Z, copier at 11:28:42Z, launched at **11:28:49Z**;<br>- **03:** session closed at 11:26:18.581Z, released relayed at 11:26:38Z, copier at 11:28:37Z, launched at **11:28:44Z**.<br><br>Each launch follows its own host's release. No timeout occurred.<br><br>**Stamps** (05 mtimes 11:28:27.9Z and 11:28:28.3Z, after the releases and before the copiers): release-upgrade is 10.5 h old (03) and 13.9 h old (04), and updates-available is newer than the apt lists on both hosts. |
| 7 Launch | ✅ | **Copier first:** the copier started before the supervisor on each host.<br>- 03: copier 876522 at 11:28:37Z, registration at 11:28:38Z, `launch.sh` at 11:28:40Z, admission at 11:28:43Z, `launch.json` at 11:28:44Z.<br>- 04: copier 884802 at 11:28:42Z, registration at 11:28:42Z, `launch.sh` at 11:28:45Z, admission at 11:28:47Z, `launch.json` at 11:28:49Z.<br><br>The registrations are bound to the new PID, job, phase replacement-r3 and source host. The hub and source records are identical, as in r2.<br><br>**launch.json:** host is correct and dispatch is **ab8b6238** on both hosts.<br><br>**Admission:** admitted, foreign 0, active 0, console 0; the supervisor is alive and there is no STOP file.<br><br>**Dispatch ab8b6238:** **575 rows** = 553 never-started + 22 replacements. Per host **286 / 289**, dispatch indices 0–574 contiguous, and games 553×8 + 22×10 = **4644**.<br><br>**History:** the history appends r3 / ab8b6238 / 11:28:44Z. `history_sha256` `8aeee040` equals the committed and 05 copies. |

## Arithmetic (recomputed)

- **Stopped r2:**
  - 03: 268 + 11 + 276 = 555;
  - 04: 266 + 11 + 277 = 554;
  - total 1109, which equals the r2 dispatch.
- **ACKs:** 268 + 266 = **534**.
- **Failed and unstarted:** failed 11 + 11 = **22** (16 primary + 6 guard); unstarted 276 + 277 = **553**.
- **New dispatch:** 553 + 22 = **575** = 286 + 289.
- **Ledger:** 55 + 22 = **77** events = 57 primary + 20 guard.
- **Losses by phase:** reporting 33, r1 22, r2 22.
- **Coverage:** 392 + 2399 + 534 = **3325**; 3325 + 575 = **3900** = 3000 + 900.
- **Games:** 553 × 8 + 22 × 10 = **4644**.
- **First r3 health (11:34:04Z, no anomalies):**
  - 03: 4 + 11 + 271 = 286;
  - 04: 4 + 11 + 274 = 289.

## Numbered findings

1. **MEDIUM. Disclosure (b): the health tool can't flag a short null-reason exit in r3 or any later phase. Fix it in code before the r4 launch at cut 3.**
   - **Confirmed in `tools/checkpoint.py`** (aa898ab2, the deployed 05 copy, which equals the committed one):
     - `EXPECTED` has entries only for reporting, r1 and r2.
     - For `replacement-r3`, `exp` is `None`, so `(exp and comp<exp)` is false. A supervisor exit with reason `null` therefore raises no anomaly, however few blocks completed.
     - In the same `done` branch, the copier-liveness checks are skipped.
     - The runner states that it checks this by hand at each read. No hand-check evidence is in the receipt; that is outside its scope.
   - **r3 itself is barely exposed.** It is due to end at the cut-3 owned STOP, and a non-null reason is always flagged. At r2's rate (about 556 blocks in 2 h 12 min) its 575 rows would not finish before about 13:46Z.
   - **r4 is exposed.** It is the first phase after the last scheduled P2 cut, so its expected end is a natural `null` exit. That is exactly the path this check exists to guard, and a dropped or unstarted block would otherwise pass unflagged.
   - **Recommendation:** yes, fix it in code before the r4 launch.
     - Derive the per-host expected count from the phase's dispatch file (`dispatch/<phase>.json`, rows by host) instead of a hard-coded map.
     - Fail closed, with an anomaly, when the phase has no dispatch or no expected count.
     - Route it through a narrow Sol review, as for F2.
   - **If the fix can't be reviewed in time,** the coordinator should explicitly accept a recorded hand check at every r4 read and at r4's end, with evidence:
     - `supervisor-exit` completed + failed equals the host's dispatch rows;
     - unstarted = [] on any `null` exit.

2. **LOW. Exact-time residuals (r2 F4 is resolved; these are smaller).** The receipt contains no `~`, but:
   - (a) The `cut` label says "04 apt-daily 11:20:02Z", while `times.apt_daily_04_fired` and the timer evidence say **11:20:06Z**. 11:20:02Z is the scheduled time from r2's read.
   - (b) `copier_exit_03` and `_04` (11:10:10Z and 11:10:08Z) are the copy-health `utc`. The admissions record `finished_utc` as **11:10:02Z** and **11:10:01Z**.
   - (c) No evidence file directly proves that the copier PID exited (no wait or `ps` output). The proof is indirect: `active=false`, `finished_utc` and `revoked=true`.
   - (d) `coordinator_go` is the runner's receipt time, 11:22:52Z. The GO receipt has `go_utc` 11:22:39Z and the commit is at 11:22:38Z. Measured from the coordinator's GO, the P2 timeout would be 11:52:39Z, not 11:52:52Z. This is immaterial, since both releases came before 11:27Z.
   - (e) The stamps/timer files carry no `date -u` read time. I placed them with 05 mtimes, and systemd's relative output brackets 03 within 11:28:17–11:28:58Z, which is consistent. The quiet-read files carry their time only in the file name.

   For r4: record the exact copier-exit and stamp-read `date -u` in the evidence, and use one time per event.

3. **LOW (coordinator-owned). The quiet-read v2 pattern is narrower than v1 in one respect.**
   - `grep -E "[0-9]{4} +(apt|…) "` requires a space after the 15-character comm. It therefore misses `apt.systemd.dai`, which is the apt-daily script itself, and `apt-config`. v1's `^(apt|…)` prefix match caught both. I verified this on sample lines.
   - The risk is mitigated: the same command checks `apt-daily.service` and `apt-daily-upgrade.service` with `systemctl is-active`, and those are what run that script.
   - The runner ran the ruled command exactly, so this is not a runner deviation.
   - **For cut 3,** the coordinator may want `apt[-.a-z]*` or similar.

4. **INFO. Disclosure (a): qualification ran during the perception window.**
   - It covered the whole window on both hosts:
     - 03: PGID 2360714, 11:10:54–11:27:12Z;
     - 04: PGID 1383353, 11:10:57–11:26:04Z;
     - perception: GO at 11:22:39Z, sessions closed at 11:24:24.96Z (04) and 11:26:18.58Z (03).
   - It was disclosed in the "03/04 quiet" post (PROGRESS 11:21:22Z) and acknowledged in the GO text (c00317cf), so the coordinator granted GO with knowledge. This complies with the checklist and with r2 audit F5.
   - **No effect on either party:**
     - the export was SHA-verified at both ends, with exit 0;
     - qualification passed 28/28, including the charge checks.
   - If cut 3 declares a window, keep the same disclosure. To make "quiet" mean idle, the alternative is to start qualification after release, at a cost of about 16 min.

5. **INFO. r2 F3 residuals (summary-level evidence).**
   - The overlay check is persisted as a one-line summary with a 16-hex overlay-list prefix, not as per-file output. pin.verify is just "OK".
   - The STOP-COPY write and removal are not evidenced.
   - `replace-stdout.txt` holds only `rc=0` and a time.
   - None of this contradicts the asserted results.

6. **INFO. Cut-3 timing, from the 11:28Z timer and stamp reads.**
   - **apt-daily-upgrade:** 04 at **13:27:55Z** and 03 at 13:46:58Z. The cut-3 owned STOP must land before 13:27:55Z, about 7 min after the nominal 13:20Z.
   - **Other timers:** 03 apt-daily at 20:36:30Z; 04 apt-daily at 00:25:02Z on 10-13; motd-news at 01:35:47Z (03) and 02:15:31Z (04) on 10-13.
   - **Release-upgrade stamp ages:** 04's stamp (2026-10-11T21:32:48Z) reaches 24 h at **2026-10-12T21:32:48Z**, and 03's at 2026-10-13T00:57:44Z.
   - **Consequence for r4:** if r4 launches about 13:30Z, its window must end before about 21:32Z, or the step-6 stamp-refresh rule applies to 04.

7. **INFO. The perception receipts cited by 1b7f3a60 are not on origin/main.**
   - `l1/receipts/b08-gap-export-20261012-r1/` is untracked in the shared checkout.
   - I used it only to corroborate the release order. It is the perception owner's to commit, not K4S's.

8. **INFO. R2-audit follow-through: all resolved in r3.**

   | r2 finding | r3 status |
   |---|---|
   | **F1** `aptquiet_remote.sh` | Shelved: the committed file is a refusing stub, and the original is in `tools/shelved/`. Step 6 uses only `quiet-read-v2.cmd` (08aabe92, hashed in the receipt, matches the checklist). v1 is kept as `quiet-read.cmd` (6fb0eefe) and was used only for the 09:09–09:10Z read-only test. |
   | **F2** `checkpoint.py` | RECEIPT-ERRATUM records the diff (52cd4583). Sol reviews r1–r3 are done. The deployed `aa898ab2` (00926208) equals the committed copy and the 05 running copy, so the r2 divergence is closed. |
   | **F3** hash gaps | 69 step 1–7 evidence files are hashed, and all match. Residuals are in finding 5. |
   | **F4** exact times | There are no rounded times. Residuals are in finding 2. |
   | **F5** k gate | The stricter count reading, `replacement_k` ≥ **8/6**, appears in the checklist step 3, `authority.k_gate`, and the tool (line 115: `kmax['primary']>=8 or kmax['guard']>=6`). Current values are 3/8 and 2/6. |
   | Disclosure | Repeated in r3; see finding 4. |

9. **INFO. The first r3 health read flagged dbus on 04.** The 11:34:04Z read shows `flags[dbus 1]` on 04 for one completed block. The tool counts it but doesn't alert on it, and earlier rounds had the same metric. This is outside the receipt's scope, but worth watching in r3 health.

10. **No reporting outcome is exposed.**
    - The receipt, ledger, dispatch, supervisor-exit, stop-reason, admission, launch, authorization and health files carry only descriptors, counts, hashes and operational flags.
    - The only outcome-like keys are `scored` / `scored_hit` in the qualification receipts, which are fixture statistics.
    - `outcomes_read: false` and `sealed: true` throughout.

11. **No arithmetic errors.** Every count in the receipt re-derives; see the Arithmetic section.
