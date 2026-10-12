# PREREG-K4S confirmatory run r1: progress (resumable)

Runner: Claude Opus 5.5 (1M), 127x05, for coordinator thread 0523ae6f; assigned 2026-10-11 ~18:00Z.
Job name: clasher-k4s-confirm-run-20261011-r1. Outcomes: **SEALED** (no loss/win/contrast is computed, viewed or logged).

## Fixed facts
- Freeze commit `391d2006` (2026-10-11T17:45:00Z), fill `fab6e03f`. All 32 freeze-record SHAs re-verified at 391d2006 (18:00Z).
- Frozen overlay = `git archive 391d2006 reports/explore/k4s-confirm` (175 files; no k4s-confirm diff 391d2006..0d600fe4).
- Runner worktree (detached at 391d2006): `/mpac/sdicks02/repos/clasher-k4s-run`. Runner scratch: `/mpac/sdicks02/k4s-runner/`.
- Jobs: 03 `/mpac/sdicks02/jobs/clasher/k4s-confirm-r1` (STOP -> `…/k4s-confirm-r1.STOP`);
  04 `/mpac/sdicks02/jobs-k4s/k4s-confirm-r1` (STOP -> `…/k4s-confirm-r1.STOP`). Stage files in `<job>-stage/`.
- Never: ssh 01/08; touch 03 T1 corpus copy; touch 04 `/mpac/sdicks02/jobs/clasher/` or `clasher-v4-cache`.

## Log (UTC, `date -u`)
- 17:59Z: vacancy 03/04: who empty, load 0.00, no foreign compute, MemAvailable ~121 GiB. SSH from 05 arrives over LAN 129.65.221.15.
- 18:00Z: LAUNCH BLOCKERS sent to coordinator (msg k4s-run-r1-blockers-20261011-1): B1 hub/ACK (frozen mirror.py is 01-only
  and 8-game-only; no frozen path writes hub-ack for 03/04), B2 job manifest FROZEN-K4S.json never produced at the freeze,
  B3 REPORTING-AUTHORIZATION.json needs a coordinator message id. Proposed OA-1 `mirror_k4s.py` (hub 05) + B2 builder, Sol-reviewed.
- 18:00:58Z: staged both jobs (pin f81f3655: 1557 inherited + 77 native-source verified; native 44874fd6; corpus 8b188918);
  overlay 175/175 byte-identical to 391d2006 on both hosts.
- 18:01:15Z: launch-time qualification driver started detached, NICE=10: 03 pid/pgid 707325, 04 pid/pgid 3949214.

- 18:00:17Z: coordinator rulings (3badf70d): **B1 approved as K4S OA-1** (new mirror_k4s.py, hub 127x05; Sol must approve
  before use; tests for 8/10-game blocks, hub-ack write-back, guard classifies copier children as owned); **B2 approved**
  (FROZEN-K4S.json from 391d2006; Sol reviews builder + output; commit as receipt); B3 after smoke PASS; a K4S freeze
  addendum (OA-1 SHA, Sol verdicts, B2 manifest SHA) must be committed before any reporting game.
- 18:05Z: authored `oa1/mirror_k4s.py`, `oa1/build_job_manifest.py`, `oa1/test_mirror_k4s.py` (8 pass vs frozen
  ssh_transport.copier_activity). Builder dry run sha 426fe4c5…, 176 files; frozen barrier.reporting_release dry run PASS
  (dummy auth, test only, deleted).
- B4 (found 18:04Z; operational, no frozen bytes): barrier needs `git show 391d2006:…` in /mpac/sdicks02/repos/clasher on
  03/04 (object absent; checkouts at db1d17a01) -> fetch commit objects only (FETCH_HEAD; no ref/worktree change);
  barrier needs PREREG r3 bytes at $J/repo/<path> -> copy byte-verified from 391d2006 after qualification.

- 18:16:57Z / 18:17:24Z: **launch-time qualification PASS** 03 / 04, 28/28 checks each, 299 tests pass, STOP drain 0.60 s /
  0.65 s, K4==T1 and K4S==K4 no-deadline hashes equal, injected-clock 0 mismatches. Receipts `receipts/launch-qualification-127x03.json`
  (f985a32c…) and `-127x04.json` (a11c978c…). Runtime pins 03 65e5beae…, 04 a99ca55b…. Only source diffs vs prep r3: the
  approved audit_seeds.py fix + its test (not runtime).
- 18:19Z: B4 done: 391d2006 objects fetched by SHA into /mpac/sdicks02/repos/clasher on 03/04 (FETCH_HEAD only; HEAD db1d17a0
  unchanged); PREREG r3 (9650972d) copied byte-verified into both staged repos.
- 18:21–18:24Z: OA-1 live integration (synthetic random-byte fixtures, test job dirs removed afterwards): 8- and 10-game blocks
  acked on 05 and written back on 03 and 04; corrupt block refused; frozen census classified copier children
  `ssh_family_budget` (never foreign/active). First run exposed a stall (one bad block aborted the pass) -> fixed (per-block isolation).
- 18:22Z: **03 admission ruling requested**: perception v4 validation cache service PID 2180947 (frozen SERVICE_PIDS['127x03'])
  is foreign unless pinned via frozen idle_services.py. Recommended (a) pin it. Waiting.
- 18:26Z: final B2 manifest FROZEN-K4S.json sha cecb2f59… (176 files, binds both launch receipts). Sol review r1 of OA-1 + B2
  delegated (task k4s-run-r1-sol-oa1-b2-review-r1; review file reviews/SOL-REVIEW-OA1-B2-r1.md).
- 18:27Z: dispatches generated with frozen schedule.py (canonical() on every row): smoke 16 blocks (8/host, 10 arms, 80 games/host)
  sha 5ff0b681…; reporting 3900 blocks / 33000 games, 16500 per host, cell imbalance 0, sha 78335dc4….

- 18:22Z: coordinator ruling (a) (d999d016): admit 03 with the frozen idle-service pin. 18:27:34Z pinned via frozen
  `idle_services.py --job $J` on 03: PID 2180947, start_ticks 139691386, cmdline 16152ceb… = T1's committed pin exactly.
- 18:28Z: END prep (authorized read-only copy): `K4-states.pkl` a97b1fbf… + `corpora.json` 3501e2ac… (= git 81f2483e) copied
  from the 05 bundle `t1-20261010-r1/corpus-publication-staging-r1` to `$J/end-corpus/` on 03/04, chmod 444, SHA-verified;
  source unchanged (read only). No END measurement until the coordinator declares the K4S END window.
- 18:30Z: STOP-path decision (operational): the frozen supervisor allows one smoke per job (launch-claim) and smoke_pass needs
  8/8 complete, so a supervisor STOP inside the counted smoke would void it. As T1 did (per-attempt job dirs), the supervisor
  STOP path is exercised in a separate excluded drill job per host `k4s-confirm-r1-stopdrill` (own staging + qualification,
  smoke-phase supervisor, STOP after ~2 min, verify drain < 5 min and 0 owned processes; outcomes never read).
- 18:31Z: drill jobs staged (overlay 175/175 OK) and qualifying: 03 PGID 724883, 04 PGID 3964459.

- 18:33Z: **Sol r1 OA-1/B2: REJECT** (3 MAJOR: ACK-return permanence, registration race/successor revocation, stale receipt
  on failed revocation; 2 MINOR: manifest wording, smoke freeze-sha spec note). B2 inventory/barrier compatibility passed.
- 18:36Z: fixes (lock, verified ACK return + retry, ownership-checked verified revocation, --revoke recovery, path/symlink/arm
  hardening); 21 tests pass; live re-run on 03/04 OK (oa1test3, removed). mirror_k4s.py 4a5d9e9f…, manifest 454b5f54….
  Response `reviews/RESPONSE-OA1-B2-r1.md`. **Sol r2 delegated** (k4s-run-r1-sol-oa1-b2-review-r2).

- 18:47Z: drill qualification PASS on 03 and 04 (k4s-confirm-r1-stopdrill). Coordinator note (~18:30Z): **K4S Amendment 1**
  committed 45f32c0f (Sol APPROVE r3), amended Mac manifest 8bb20a75… (was d89cab16). Binding: fleet reporting keeps
  391d2006 bytes (FROZEN-K4S.json pins mac/K4S-MAC-MANIFEST.json at d89cab16; amended manifest never deployed to the
  reporting runtime); END only from a SEPARATE staged amended tree (post-6afcbbab measure_tiers.py + 45f32c0f) and every END
  declaration/run names 8bb20a75, never d89cab16; freeze addendum cites Amendment 1 with OA-1 and the B2 manifest SHA.

- 18:48Z: coordinator (f442b968): MINOR 5 disposition accepted (record in addendum, no frozen change); STOP drill approved;
  if Sol r3 does not approve, STOP and report before another round. (My status message was labelled 18:53Z but sent 18:48:23Z.)
- 18:5xZ: Sol r2 REJECT (new MAJOR 6 transport descendants, 7 unverified ACK on restart) -> fixed: process-group
  transports drained, signals as stop requests, remote pgrep quiescence before register/revoke with double confirm,
  full hub-block verification before any return + at copier start, quarantine + re-copy; 35 tests; live 03/04 OK.
  Test-harness slip: a bare `setsid … &` forked; two test copiers ran ~40 s on deleted test jobs; stopped by exact PID.
  18:57Z: response r2 written; **Sol r3 (final) delegated**. Manifest now 416f6e51….
- 18:58–19:00Z: **STOP drill PASS** (excluded, k4s-confirm-r1-stopdrill, drill qualification 28/28 both): admitted 0 foreign;
  8 blocks in flight; STOP touched 19:00:30.347Z (03) / 19:00:30.718Z (04); supervisors gone 19:00:32.062Z / 19:00:33.462Z
  (≈1.7 s / 2.7 s); reason owned_STOP; 8 failed / 0 completed (excluded, never inspected); 0 owned groups; STOP targets
  removed. Receipt `receipts/stop-drill.json`.

- 19:05Z: **Sol r3 (final) OA-1/B2: REJECT.** Resolved: 1, 2, 4, 5 (coordinator), 7. Still PARTIAL: 3/6 (root SIGKILL leaves a
  separately-sessioned local transport alive after the job lock is released; registration/--revoke don't drain it;
  drain failure reduced to a block error). New MINOR 8 (re-copy needs --ignore-times). B2 manifest 416f6e51 compatible.
  Per coordinator rule (18:48Z): STOPPED; findings sent to coordinator; no further round without a ruling. No launch.

- 19:07Z r4 authorized → 19:18Z Sol r4 REJECT (new MAJOR 9 recovery kills unverified procs, 10 ledger failure) → stopped.
  19:19Z r5 (no-signal design) authorized → 19:31Z Sol r5 REJECT (new MAJOR 11 drain syscall errors) → stopped.
  19:32Z r6 (narrow) authorized → 19:39Z Sol r6 REJECT (new MAJOR 12 --revoke outside lifecycle boundary) → stopped.
  19:40Z S1 (delete recovery mode) authorized → 19:54Z **Sol r7 APPROVE_WITH_FIXES** (12/11/6/10 RESOLVED; MINOR 13 fixed
  as prescribed, 48 tests). Live regressions on 03/04 after every round (synthetic fixtures, removed).
- 19:55Z: B2 + OA-1 final bytes + review trail committed 6ac7b641 (mirror_k4s.py 47eb96d6…, FROZEN-K4S.json 416f6e51…).
  Freeze addendum `addendum/K4S-LAUNCH-ADDENDUM.{md,json}` composed 19:55:15Z.

- 19:55:47Z / 19:55:52Z: **counted smoke launched** (03 sup 761064, 04 sup 4001173; copiers on 05 4095807/4105420); both
  admitted 0 foreign/active, no console. 20:03Z: 8/8 complete, 0 failed, 8/8 hub-ACK durable+returned per host, no stop
  reason; copiers STOP-COPY → exited, revoked (verified both sides). **20:04:14Z SMOKE-PASS both** (80 games/host, 0 errors;
  interfered 03=0, 04=3 (dbus), charge max dev ≤0.008). smoke-admission 03 e338db63…, 04 9c4d636f….
  Next: B3 request to coordinator (manifest 416f6e51 + smoke receipts) → REPORTING-AUTHORIZATION.json → reporting launch.

- 20:04:59Z: coordinator REPORTING AUTHORIZATION (msg …9bac571d…, COORDINATOR fa34fcb0). 20:05:50Z/55Z first launch in
  k4s-confirm-r1 REFUSED by frozen owned_supervisor.pin (one supervisor phase per job; smoke used it) before admission; no
  game; copiers revoked. 20:07:31Z coordinator ack (…12fbbb0f…): distinct reporting namespace per T1 precedent.
  Staged k4s-confirm-reporting-r1 on 03/04 from the qualified runtime (overlay 175/175, pin OK, SMOKE-PASS/manifest/dispatch
  byte-identical; 03 idle pin re-verified = T1 identity). REPORTING-AUTHORIZATION-v2 (reporting_jobs updated). Barrier PASS.
- **20:08:22Z / 20:08:27Z: SEALED REPORTING LAUNCHED** 03 sup 776314 / 04 sup 4015460 (nice 10, core 61, 11 slots, 11 inflight,
  1939 queued); copiers on 05: 03 1322045 (core 62), 04 1331157 (core 63). Receipt receipts/reporting-launch-receipt.json.

- 21:32:49Z 04 foreign_compute stop (motd release-check; supervisor continued); ruling (a) 21:39Z (11105b3f), disclosure committed.
- 22:06:15Z 04 ubuntu_apt_average_budget stop (apt-daily 22:05:58Z + motd updates-available apt-check); supervisor EXITED
  (186 completed / 22 failed / 1742 unstarted). Escalated. Ruling ~22:12Z: OPTION A (stop 03, one blind inventory of both
  phases, fresh namespace replacement-r1 on both, fresh qualification, motd stamp/timer checks, authorization cites ruling).
- 22:12:08.897Z 03 owned STOP → supervisor gone 22:12:12Z (206 completed / 11 failed / 1733 unstarted); 0 owned groups.
  Both reporting copiers exited+revoked after 186/206 ACKs returned. (A 04-only replace.py draft was run first under the
  superseded windowed ruling; never used; kept in superseded-draft-r1/.)
- 22:12Z frozen replace.py over both phases (04 first) with a 05 symlink hub view: ledger 33 events (primary 25, guard 8),
  max k primary 1 / guard 0; dispatch replacement-r1.json 3508 rows (3475 never-started + 33 replacements), 1754/host,
  29080 games; coverage 392 counted + 3508 = all 3000/900 logical blocks once.
- 22:13Z fresh namespaces k4s-confirm-replacement-r1 staged (overlay OK, PREREG 9650972d); fresh qualification running
  (03 PGID 990201, 04 PGID 26640).

- 22:29Z fresh qualification PASS 28/28 both (03 b912da99, 04 08d4651d); runtime byte-identical to smoke job (pin maps, inputs,
  plan); SMOKE-PASS/smoke-admission/FROZEN-K4S 416f6e51 carried over byte-identical; 03 idle pin re-verified; auth v3 (cites
  afe83faa); barrier PASS. **22:30:38Z / 22:30:42Z replacement-r1 LAUNCHED** 03 sup 1002822 / 04 sup 37363 (11 inflight,
  1743 queued each); copiers 03 702958 / 04 711250. K4S Amendment 2 (19ed3815): fleet unaffected; END/Mac must name c1fb1e9a.

## Running (owned PGIDs only)
- CURRENT: replacement-r1 in k4s-confirm-replacement-r1: 03 sup PGID 1002822, 04 sup PGID 37363; copiers on 05 702958 / 711250.
  (Reporting-phase PGIDs below are dead/superseded.)
- 03: reporting supervisor PGID 776314 (+ its block groups) in /mpac/sdicks02/jobs/clasher/k4s-confirm-reporting-r1
- 04: reporting supervisor PGID 4015460 (+ block groups) in /mpac/sdicks02/jobs-k4s/k4s-confirm-reporting-r1
- 05: OA-1 copiers PGID 1322045 (03) / 1331157 (04); logs run-r1/copier/127x0{3,4}-reporting.log
- Health: tools/k4s_health.py every 20 min → health/*.json + PROGRESS line + coordinator note.
- Resume after a session restart: check these PGIDs with ps; if a copier died, restart it with the same
  `K4S_JOBNAME=k4s-confirm-reporting-r1` copier command (normal start = recovery; never --revoke); supervisors are never relaunched
  in the same job (frozen launch-claim) — any supervisor loss goes to the coordinator (replacement rules).

## Running (stale header kept for history)
- none (drill qualification drivers exited 0).

## Next
1. Qualification receipts (03/04) -> commit under run-r1/receipts/.
2. Coordinator ruling on B1/B2/B3; author + Sol-review `mirror_k4s.py` and the manifest builder.
3. Excluded smoke (8 blocks/host, all 10 arms) -> SMOKE-PASS -> coordinator go -> reporting dispatch.

## Health checkpoints (SEALED, health only)
- 2026-10-11T20:15:30Z SEALED health: 127x03 complete 8 acked 7 hub 7/6 failed 0 inflight 11 queued 1931 reason None who 0 flags[0 SSHFLAG 0 APTFLAG 0]; 127x04 complete 7 acked 7 hub 7/7 failed 0 inflight 11 queued 1932 reason None who 0 flags[2 SSHFLAG 0 APTFLAG 0]; no anomalies
- 2026-10-11T20:25:48Z SEALED health: 127x03 complete 24 acked 24 hub 24/24 failed 0 inflight 11 queued 1915 reason None who 0 flags[0 SSHFLAG 0 APTFLAG 0]; 127x04 complete 22 acked 22 hub 22/22 failed 0 inflight 11 queued 1917 reason None who 0 flags[17 SSHFLAG 0 APTFLAG 0]; no anomalies
- 2026-10-11T20:37:09Z SEALED health: 127x03 complete 42 acked 42 hub 42/42 failed 0 inflight 11 queued 1897 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 44 acked 44 hub 44/44 failed 0 inflight 11 queued 1895 reason None who 0 flags[dbus 39 ssh 0 apt 0 idle 0]; no anomalies
- 2026-10-11T20:47:17Z SEALED health: 127x03 complete 61 acked 61 hub 61/61 failed 0 inflight 11 queued 1878 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 59 acked 59 hub 59/59 failed 0 inflight 11 queued 1880 reason None who 0 flags[dbus 54 ssh 0 apt 0 idle 0]; no anomalies
- 2026-10-11T20:57:17Z SEALED health: 127x03 complete 77 acked 77 hub 77/77 failed 0 inflight 11 queued 1862 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 77 acked 77 hub 77/77 failed 0 inflight 11 queued 1862 reason None who 0 flags[dbus 72 ssh 0 apt 0 idle 0]; no anomalies
- 2026-10-11T21:12:15Z SEALED health: 127x03 complete 104 acked 103 hub 103/103 failed 0 inflight 11 queued 1835 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 102 acked 102 hub 102/102 failed 0 inflight 11 queued 1837 reason None who 0 flags[dbus 97 ssh 0 apt 0 idle 0]; no anomalies
- 2026-10-11T21:22:14Z SEALED health: 127x03 complete 119 acked 118 hub 118/118 failed 0 inflight 11 queued 1820 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 120 acked 120 hub 120/120 failed 0 inflight 11 queued 1819 reason None who 0 flags[dbus 115 ssh 0 apt 0 idle 0]; no anomalies
- 2026-10-11T21:37:10Z SEALED health: 127x03 complete 147 acked 147 hub 147/147 failed 0 inflight 11 queued 1792 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 135 acked 135 hub 135/135 failed 11 inflight 11 queued 1793 reason None who 0 flags[dbus 130 ssh 0 apt 0 idle 0]; ANOMALIES: 127x04: failed blocks 11; 127x04: STOP "reason": "foreign_compute"
- 2026-10-11T21:48:50Z SEALED health: 127x03 complete 164 acked 164 hub 164/164 failed 0 stopevent - inflight 11 queued 1775 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 157 acked 157 hub 157/157 failed 11 stopevent "utc": "2026-10-11T21:32:49Z" "reason": "foreign_compute" inflight 11 queued 1771 reason None who 0 flags[dbus 146 ssh 0 apt 0 idle 0]; lost primary 8 guard 3; no anomalies
- 2026-10-11T21:58:56Z SEALED health: 127x03 complete 182 acked 182 hub 182/182 failed 0 stopevent - inflight 11 queued 1757 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 174 acked 173 hub 174/173 failed 11 stopevent "utc": "2026-10-11T21:32:49Z" "reason": "foreign_compute" inflight 11 queued 1754 reason None who 0 flags[dbus 163 ssh 0 apt 0 idle 0]; lost primary 8 guard 3; no anomalies
- 2026-10-11T22:08:53Z SEALED health: 127x03 complete 199 acked 199 hub 199/199 failed 0 stopevent - inflight 11 queued 1740 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 186 acked 186 hub 186/186 failed 22 stopevent "utc": "2026-10-11T22:06:15Z" "reason": "ubuntu_apt_average_budget" inflight 11 queued 1742 reason ubuntu_apt_average_budget who 0 flags[dbus 175 ssh 0 apt 0 idle 0]; lost primary 16 guard 6; ANOMALIES: 127x04: failed blocks 22 (acknowledged 11); 127x04: STOP "utc": "2026-10-11T22:06:15Z" "reason": "ubuntu_apt_average_budget"; 127x04: progress reason ubuntu_apt_average_budget; 127x04: supervisor exited ("reason": "ubuntu_apt_average_budget", complete 186/1950)
- 2026-10-11T22:41:59Z SEALED health: 127x03 complete 11 acked 11 hub 11/11 failed 0 stopevent - inflight 11 queued 1732 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 11 acked 11 hub 11/11 failed 0 stopevent - inflight 11 queued 1732 reason None who 0 flags[dbus 6 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-11T22:52:00Z SEALED health: 127x03 complete 33 acked 33 hub 33/33 failed 0 stopevent - inflight 11 queued 1710 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 31 acked 31 hub 31/31 failed 0 stopevent - inflight 11 queued 1712 reason None who 0 flags[dbus 26 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-11T23:01:58Z SEALED health: 127x03 complete 46 acked 46 hub 46/46 failed 0 stopevent - inflight 11 queued 1697 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 46 acked 46 hub 46/46 failed 0 stopevent - inflight 11 queued 1697 reason None who 0 flags[dbus 41 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-11T23:11:59Z SEALED health: 127x03 complete 64 acked 63 hub 63/63 failed 0 stopevent - inflight 11 queued 1679 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 64 acked 64 hub 64/64 failed 0 stopevent - inflight 11 queued 1679 reason None who 0 flags[dbus 59 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-11T23:21:54Z SEALED health: 127x03 complete 81 acked 81 hub 81/81 failed 0 stopevent - inflight 11 queued 1662 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 81 acked 81 hub 81/81 failed 0 stopevent - inflight 11 queued 1662 reason None who 0 flags[dbus 76 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-11T23:31:52Z SEALED health: 127x03 complete 99 acked 99 hub 99/99 failed 0 stopevent - inflight 11 queued 1644 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 101 acked 101 hub 101/101 failed 0 stopevent - inflight 11 queued 1642 reason None who 0 flags[dbus 96 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-11T23:41:47Z SEALED health: 127x03 complete 119 acked 119 hub 119/119 failed 0 stopevent - inflight 11 queued 1624 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 119 acked 118 hub 118/118 failed 0 stopevent - inflight 11 queued 1624 reason None who 0 flags[dbus 113 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-11T23:51:44Z SEALED health: 127x03 complete 140 acked 139 hub 139/139 failed 0 stopevent - inflight 11 queued 1603 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 140 acked 140 hub 140/140 failed 0 stopevent - inflight 11 queued 1603 reason None who 0 flags[dbus 135 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T00:01:41Z SEALED health: 127x03 complete 159 acked 159 hub 159/159 failed 0 stopevent - inflight 11 queued 1584 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 158 acked 158 hub 158/158 failed 0 stopevent - inflight 11 queued 1585 reason None who 0 flags[dbus 153 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T00:11:39Z SEALED health: 127x03 complete 178 acked 178 hub 178/178 failed 0 stopevent - inflight 11 queued 1565 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 179 acked 178 hub 178/178 failed 0 stopevent - inflight 11 queued 1564 reason None who 0 flags[dbus 173 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T00:21:33Z SEALED health: 127x03 complete 199 acked 199 hub 199/199 failed 0 stopevent - inflight 11 queued 1544 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 199 acked 198 hub 198/198 failed 0 stopevent - inflight 11 queued 1545 reason None who 0 flags[dbus 193 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
