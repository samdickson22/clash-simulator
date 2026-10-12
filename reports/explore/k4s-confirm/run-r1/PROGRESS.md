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

- 00:57:44Z 03 motd release stamp refreshed with NO stop (check exited between census samples).
- 01:07Z **standing policy P2 approved (adc12f36)**: stop BOTH hosts (owned STOP) before each known apt timer (~08:40Z, ~11:10Z,
  ~13:20Z), one blind inventory (frozen replace.py), fresh replacement-rN round after the update has run (pre-trigger stale
  motd stamps with one login, record timers/stamps). At 08:40Z only: after 03's apt finishes post "03 quiet" to the coordinator,
  wait for the builder's "released" (max 30 min), then relaunch. Cycle automation: tools/round.sh (Sol review requested).

- 02:2xZ **Proposal M adopted (2c847954)**: every P2 cycle by hand from CYCLE-CHECKLIST.md; round.py/round.sh shelved (Sol
  REJECTs r1/r2 kept); after each round commit rounds/rN/RECEIPT.json and post "round rN receipt committed <sha>" → Opus audit;
  blocking findings stop the next cycle.

- 03:5xZ coordinator 92acdf02: E4 ReportingGuard snapshot race (fleet_validity 94d0e7f2 -> fix eae5db3f in Sol review) also
  affects K4S end_reference.py: NO K4S END reference until ruled; a fix would require re-pinning K4S manifest c1fb1e9a.
  Reporting (supervise/run.py) unaffected.

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
- 2026-10-12T00:31:32Z SEALED health: 127x03 complete 216 acked 216 hub 216/216 failed 0 stopevent - inflight 11 queued 1527 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 218 acked 218 hub 218/218 failed 0 stopevent - inflight 11 queued 1525 reason None who 0 flags[dbus 213 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T00:41:27Z SEALED health: 127x03 complete 237 acked 237 hub 237/237 failed 0 stopevent - inflight 11 queued 1506 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 240 acked 239 hub 239/239 failed 0 stopevent - inflight 11 queued 1503 reason None who 0 flags[dbus 234 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T00:51:24Z SEALED health: 127x03 complete 258 acked 258 hub 258/258 failed 0 stopevent - inflight 11 queued 1485 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 260 acked 260 hub 260/260 failed 0 stopevent - inflight 11 queued 1483 reason None who 0 flags[dbus 255 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T01:01:20Z SEALED health: 127x03 complete 280 acked 280 hub 280/280 failed 0 stopevent - inflight 11 queued 1463 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 280 acked 280 hub 280/280 failed 0 stopevent - inflight 11 queued 1463 reason None who 0 flags[dbus 275 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T01:11:44Z SEALED health: 127x03 complete 299 acked 299 hub 299/299 failed 0 stopevent - inflight 11 queued 1444 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 302 acked 300 hub 300/300 failed 0 stopevent - inflight 11 queued 1441 reason None who 0 flags[dbus 295 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T01:21:40Z SEALED health: 127x03 complete 321 acked 321 hub 321/321 failed 0 stopevent - inflight 11 queued 1422 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 322 acked 321 hub 322/321 failed 0 stopevent - inflight 11 queued 1421 reason None who 0 flags[dbus 317 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T01:33:28Z SEALED health: 127x03 complete 346 acked 346 hub 346/346 failed 0 stopevent - inflight 11 queued 1397 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 345 acked 345 hub 345/345 failed 0 stopevent - inflight 11 queued 1398 reason None who 0 flags[dbus 340 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T01:48:22Z SEALED health: 127x03 complete 376 acked 376 hub 376/376 failed 0 stopevent - inflight 11 queued 1367 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 376 acked 376 hub 376/376 failed 0 stopevent - inflight 11 queued 1367 reason None who 0 flags[dbus 371 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T02:01:37Z SEALED health: 127x03 complete 404 acked 404 hub 404/404 failed 0 stopevent - inflight 11 queued 1339 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 404 acked 404 hub 404/404 failed 0 stopevent - inflight 11 queued 1339 reason None who 0 flags[dbus 399 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T02:16:31Z SEALED health: 127x03 complete 435 acked 435 hub 435/435 failed 0 stopevent - inflight 11 queued 1308 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 434 acked 434 hub 434/434 failed 0 stopevent - inflight 11 queued 1309 reason None who 0 flags[dbus 429 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T02:27:38Z SEALED health: 127x03 complete 457 acked 457 hub 457/457 failed 0 stopevent - inflight 11 queued 1286 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 457 acked 456 hub 456/456 failed 0 stopevent - inflight 11 queued 1286 reason None who 0 flags[dbus 451 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T02:42:31Z SEALED health: 127x03 complete 488 acked 488 hub 488/488 failed 0 stopevent - inflight 11 queued 1255 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 489 acked 488 hub 488/488 failed 0 stopevent - inflight 11 queued 1254 reason None who 0 flags[dbus 483 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T02:57:24Z SEALED health: 127x03 complete 521 acked 521 hub 521/521 failed 0 stopevent - inflight 11 queued 1222 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 519 acked 519 hub 519/519 failed 0 stopevent - inflight 11 queued 1224 reason None who 0 flags[dbus 514 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T03:12:17Z SEALED health: 127x03 complete 550 acked 550 hub 550/550 failed 0 stopevent - inflight 11 queued 1193 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 550 acked 548 hub 548/548 failed 0 stopevent - inflight 11 queued 1193 reason None who 0 flags[dbus 543 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T03:27:12Z SEALED health: 127x03 complete 582 acked 581 hub 582/581 failed 0 stopevent - inflight 11 queued 1161 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 582 acked 581 hub 581/581 failed 0 stopevent - inflight 11 queued 1161 reason None who 0 flags[dbus 576 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T03:42:06Z SEALED health: 127x03 complete 613 acked 613 hub 613/613 failed 0 stopevent - inflight 11 queued 1130 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 612 acked 612 hub 612/612 failed 0 stopevent - inflight 11 queued 1131 reason None who 0 flags[dbus 607 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T03:57:00Z SEALED health: 127x03 complete 646 acked 645 hub 645/645 failed 0 stopevent - inflight 11 queued 1097 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 643 acked 642 hub 642/642 failed 0 stopevent - inflight 11 queued 1100 reason None who 0 flags[dbus 637 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T04:12:00Z SEALED health: 127x03 complete 675 acked 675 hub 675/675 failed 0 stopevent - inflight 11 queued 1068 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 673 acked 673 hub 673/673 failed 0 stopevent - inflight 11 queued 1070 reason None who 0 flags[dbus 668 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T04:26:55Z SEALED health: 127x03 complete 705 acked 705 hub 705/705 failed 0 stopevent - inflight 11 queued 1038 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 702 acked 702 hub 702/702 failed 0 stopevent - inflight 11 queued 1041 reason None who 0 flags[dbus 697 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T04:41:54Z SEALED health: 127x03 complete 738 acked 738 hub 738/738 failed 0 stopevent - inflight 11 queued 1005 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 734 acked 734 hub 734/734 failed 0 stopevent - inflight 11 queued 1009 reason None who 0 flags[dbus 729 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T04:57:21Z SEALED health: 127x03 complete 772 acked 771 hub 771/771 failed 0 stopevent - inflight 11 queued 971 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 767 acked 767 hub 767/767 failed 0 stopevent - inflight 11 queued 976 reason None who 0 flags[dbus 762 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T04:59:33Z Erratum (coordinator): the windowed-rounds ruling 76887b33 was recorded at 22:10:17Z, not ~22:13Z. Option A afe83faa is 22:11 UTC (commit 22:11:53Z), not ~22:12Z. The committed r1 authorization is left as evidence. From r2 on, citations follow receipts/AUTHORIZATION-CITATION-ERRATUM-20261012.md.
- 2026-10-12T05:05:32Z K4S Amendment 3 ADOPTED (main 133f3ae4, Sol r1 APPROVE). Mac/END manifest of record is 74314eda; END is no longer held for the guard race but still needs reporting complete, an END window and a runbook ruling. The fleet overlay keeps d89cab16 and FROZEN 416f6e51; never deploy the amended mac/ into reporting. Sol non-blocking note (A2-comparison test) is deferred to cleanup.
- 2026-10-12T05:17:13Z SEALED health: 127x03 complete 814 acked 814 hub 814/814 failed 0 stopevent - inflight 11 queued 929 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 806 acked 806 hub 806/806 failed 0 stopevent - inflight 11 queued 937 reason None who 0 flags[dbus 801 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T05:36:20Z SEALED health: 127x03 complete 854 acked 851 hub 851/851 failed 0 stopevent - inflight 11 queued 889 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 848 acked 846 hub 846/846 failed 0 stopevent - inflight 11 queued 897 reason None who 0 flags[dbus 841 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T05:55:27Z SEALED health: 127x03 complete 886 acked 886 hub 886/886 failed 0 stopevent - inflight 11 queued 857 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 883 acked 883 hub 883/883 failed 0 stopevent - inflight 11 queued 860 reason None who 0 flags[dbus 878 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T06:14:33Z SEALED health: 127x03 complete 920 acked 919 hub 919/919 failed 0 stopevent - inflight 11 queued 823 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 915 acked 915 hub 915/915 failed 0 stopevent - inflight 11 queued 828 reason None who 0 flags[dbus 910 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T06:33:38Z SEALED health: 127x03 complete 952 acked 952 hub 952/952 failed 0 stopevent - inflight 11 queued 791 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 946 acked 946 hub 946/946 failed 0 stopevent - inflight 11 queued 797 reason None who 0 flags[dbus 941 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T06:52:44Z SEALED health: 127x03 complete 991 acked 991 hub 991/991 failed 0 stopevent - inflight 11 queued 752 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 983 acked 982 hub 982/982 failed 0 stopevent - inflight 11 queued 761 reason None who 0 flags[dbus 977 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T07:11:53Z SEALED health: 127x03 complete 1029 acked 1029 hub 1029/1029 failed 0 stopevent - inflight 11 queued 714 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 1020 acked 1020 hub 1020/1020 failed 0 stopevent - inflight 11 queued 723 reason None who 0 flags[dbus 1015 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T07:30:59Z SEALED health: 127x03 complete 1068 acked 1068 hub 1068/1068 failed 0 stopevent - inflight 11 queued 675 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 1057 acked 1056 hub 1056/1056 failed 0 stopevent - inflight 11 queued 686 reason None who 0 flags[dbus 1051 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T07:50:17Z SEALED health: 127x03 complete 1106 acked 1106 hub 1106/1106 failed 0 stopevent - inflight 11 queued 637 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 1096 acked 1096 hub 1096/1096 failed 0 stopevent - inflight 11 queued 647 reason None who 0 flags[dbus 1091 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies
- 2026-10-12T08:09:29Z SEALED health: 127x03 complete 1147 acked 1147 hub 1147/1147 failed 0 stopevent - inflight 11 queued 596 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 1135 acked 1135 hub 1135/1135 failed 0 stopevent - inflight 11 queued 608 reason None who 0 flags[dbus 1130 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 25/300 guard 8/90; ledger max k {'primary': 1, 'guard': 0}; no anomalies

## P2 cut 1 (r1 -> r2), 2026-10-12
- 08:37:46.543Z / 08:37:46.567Z joint owned STOP of replacement-r1 (03 sup 1002822, 04 sup 37363). Supervisors exited
  08:37:48Z / 08:37:51Z (owned_STOP): 03 1205 completed / 11 failed / 538 unstarted; 04 1194 / 11 / 549. Recorded PGIDs
  (03 1217, 04 1206) have 0 live members. complete.json sets == exit lists.
- Drain: hub ACK + returned marker bound for all 1205 + 1194 blocks; copiers 702958 / 711250 exited, revoked, final, no
  errors; hub and source admissions inactive; STOP-COPY removed.
- Inventory (frozen replace.py @391d2006, working ledger): 22 new events (all owned_STOP; primary 16, guard 6) == failed
  blocks; cumulative lost primary 41/150, guard 14/45; max k primary 2/9, guard 1/7. dispatch replacement-r2.json
  1df20188 (1109 rows = 1087 never-started + 22 replacements; 555 / 554; 8938 games); exact coverage 2791 counted + 1109.
  Ledger before-r2 19580caa -> 4a56abf3.
- 08:39:43Z / 08:39:46Z k4s-confirm-replacement-r2 staged (extras sha OK, overlay 175/175, PREREG 9650972d); qualification
  running (03 PGID 2102837, 04 PGID 1128505).
- 2026-10-12T08:48:14Z coordinator GO to builder (03 read window); 03 r2 launch held until "released" or 30 min (2026-10-12T09:18:14Z); 04 may proceed.
- 2026-10-12T08:52:17Z coordinator forwarded "released" (builder receipt fa8e700a); 03 r2 launch released from hold.
- 08:55Z qualification PASS 28/28 both (03 08:54:59Z, 04 08:55:51Z); runtime == smoke job; pin.verify re-hash OK; carry-over
  416f6e51 / SMOKE-PASS / smoke-admission byte-identical; 03 idle pin OK; auth v4 (corrected citations); barrier PASS 176 both.
- **08:57:13Z / 08:57:17Z replacement-r2 LAUNCHED**: 03 sup 2116555, 04 sup 1140717 (admitted, 0 foreign/active, no console).
  Copiers on 05: 03 485959 (core 62), 04 494063 (core 63). Receipt rounds/r2/RECEIPT.json. Next cut ~11:10Z (04 apt 11:20:02Z).
## Running (owned PGIDs only) -- CURRENT
- replacement-r2 in k4s-confirm-replacement-r2: 03 sup PGID 2116555, 04 sup PGID 1140717; copiers on 05 485959 / 494063.
- 2026-10-12T09:09:08Z Round r2 audit PASS_WITH_NOTES (audits/ROUND-r2-AUDIT.md 4b89ddc2, retained verbatim); the r2 launch stands.
  Cut-2 rulings applied (see rounds/r2/RECEIPT-ERRATUM.md):
  - F1: aptquiet_remote.sh shelved (stub refuses); step-6 uses the coordinator's inline strict-mode command.
  - F2: checkpoint.py diff 7ee26396..b5530e98 sha 52cd4583 (gate rewrite; ran uncommitted 2026-10-11T22:37:02Z to
    2026-10-12T08:58:42Z) disclosed; Sol review requested via the coordinator; tool still in use (health only).
  - F3/F4: r3 receipt persists and hashes step evidence, with exact times (checklist step 7).
  - F5: k is the frozen 0-based index (count = k + 1); the stricter count reading applies: escalate at max k ≥8/6.
  - DISCLOSURE: K4S's own r2 qualification on 03 (PGID 2102837, 08:39:43Z to 08:54:59Z) was running during apt-daily,
    the "03 quiet" post (08:47:47Z) and the builder's read (08:49:03Z to 08:51:29Z). "03 quiet" certified only that the
    reporting phase had exited, the apt units were inactive, there were no apt processes and no console user.
  - Quiet-read test 09:08Z (read-only): both hosts maint=1 at baseline (boot-time unattended-upgrade-shutdown
    --wait-for-signal: 03 PID 2368, 04 PID 2296). One 04 read at 09:08:15Z showed maint=2 (transient, unidentified).
    Coordinator ruling requested before the cut-2 prelaunch.
- 2026-10-12T09:10:36Z Quiet-read v2 (coordinator ruling; cmd sha 08aabe92) tested read-only 09:09:53Z and 09:10:24Z on both hosts: rc 0, units inactive, maint=0, who=0, helper 03 PID 2368 (lstart Wed Sep 23 17:37:32 2026 local) / 04 PID 2296 (Mon Sep 28 15:01:03 2026 local). Two consecutive quiet reads per host. Max k gate 8/6 adopted.
- 2026-10-12T09:08:53Z SEALED health: 127x03 complete 22 acked 21 hub 21/21 failed 0 stopevent - inflight 11 queued 522 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 20 acked 20 hub 20/20 failed 0 stopevent - inflight 11 queued 523 reason None who 0 flags[dbus 17 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 41/300 guard 14/90; ledger max k {'primary': 2, 'guard': 1}; no anomalies
- 2026-10-12T09:13:43Z SEALED health: 127x03 complete 31 acked 31 hub 31/30 failed 0 stopevent - inflight 11 queued 513 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 31 acked 30 hub 30/30 failed 0 stopevent - inflight 11 queued 512 reason None who 0 flags[dbus 27 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 41/300 guard 14/90; ledger max k {'primary': 2, 'guard': 1}; no anomalies
- 2026-10-12T09:18:33Z Sol checkpoint review r1 REQUEST_CHANGES retained verbatim (reviews/SOL-REVIEW-CHECKPOINT-r1.md ea349ac1). Candidate fix in tools/candidate-r2/ (R1 k>=8/6, R2 fail-closed validated ledger + exit 2 receipt, R3 per-population union of ledger lost IDs and current-phase failed IDs via new outcome-blind FAILEDIDS read cross-checked with LOSTPOP; no asserts) with 44 offline tests (pass, also under -O). NOT deployed: the running tool stays b5530e98 (health only); 8/6 and cumulative totals applied by hand until Sol r2.
- 2026-10-12T09:25:48Z SEALED health: 127x03 complete 56 acked 56 hub 56/56 failed 0 stopevent - inflight 11 queued 488 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 54 acked 54 hub 54/54 failed 0 stopevent - inflight 11 queued 489 reason None who 0 flags[dbus 51 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 41/300 guard 14/90; ledger max k {'primary': 2, 'guard': 1}; no anomalies
- 2026-10-12T09:34:07Z Sol checkpoint review r2 REQUEST_CHANGES retained verbatim (reviews/SOL-REVIEW-CHECKPOINT-r2.md ad600653). Fixed: k alert (8/6) now evaluated right after ledger validation, before the unknown-host return, so it is kept alongside cumulative UNKNOWN. +8 tests (gate with current_failed=None; main() mismatch/timeout/ssh rc 255): 52/52 pass, also under -O; the 7 new alert tests fail on the bb5d7685 candidate. Still NOT deployed.
- 2026-10-12T09:42:12Z checkpoint.py DEPLOYED: Sol checkpoint r3 APPROVE (reviews/SOL-REVIEW-CHECKPOINT-r3.md 4e252cce). tools/checkpoint.py = candidate aa898ab2 (was b5530e98 40cca772, kept at tools/shelved/checkpoint.py.b5530e98); tests tools/test_checkpoint.py e1ae76e8 + fixtures/blind-ledger-r2.json 4a56abf3; 52/52 pass in place (also -O). Automatic 8/6 k and union cumulative alerts now replace the manual application; manual cross-check kept at each inventory.
- 2026-10-12T09:44:54Z SEALED health: 127x03 complete 96 acked 96 hub 96/96 failed 0 stopevent - inflight 11 queued 448 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 90 acked 90 hub 90/90 failed 0 stopevent - inflight 11 queued 453 reason None who 0 flags[dbus 87 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 41/300 guard 14/90 (union; already in ledger 0/0); ledger max k {'primary': 2, 'guard': 1}; no anomalies
- 2026-10-12T10:01:24Z Coordinator: cut 2 adds a perception-owner read window on both 03 and 04 (read-only copy of pinned perception files to 08). After joint STOP + 04 apt-daily + quiet-read v2 (2 consecutive per host): post "03/04 quiet"; hold each host's r3 launch until its "released" or 30 min from GO.
- 2026-10-12T10:05:43Z SEALED health: 127x03 complete 138 acked 138 hub 138/138 failed 0 stopevent - inflight 11 queued 406 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 135 acked 135 hub 135/135 failed 0 stopevent - inflight 11 queued 408 reason None who 0 flags[dbus 132 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 41/300 guard 14/90 (union; already in ledger 0/0); ledger max k {'primary': 2, 'guard': 1}; no anomalies
- 2026-10-12T10:24:48Z SEALED health: 127x03 complete 179 acked 179 hub 179/179 failed 0 stopevent - inflight 11 queued 365 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 171 acked 171 hub 171/171 failed 0 stopevent - inflight 11 queued 372 reason None who 0 flags[dbus 168 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 41/300 guard 14/90 (union; already in ledger 0/0); ledger max k {'primary': 2, 'guard': 1}; no anomalies
- 2026-10-12T10:43:56Z SEALED health: 127x03 complete 218 acked 218 hub 218/218 failed 0 stopevent - inflight 11 queued 326 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 213 acked 213 hub 213/213 failed 0 stopevent - inflight 11 queued 330 reason None who 0 flags[dbus 210 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 41/300 guard 14/90 (union; already in ledger 0/0); ledger max k {'primary': 2, 'guard': 1}; no anomalies

## P2 cut 2 (r2 -> r3), 2026-10-12
- 11:09:30.516Z / 11:09:30.532Z joint owned STOP of replacement-r2 (03 sup 2116555, 04 sup 1140717); exits 11:09:31Z /
  11:09:33Z owned_STOP: 03 268/11/276, 04 266/11/277. Recorded PGIDs (03 280, 04 278) 0 live (ps rc 0). complete sets ==
  exit lists. Drain: 268 + 266 ACK bindings OK; copiers 485959 / 494063 exited 11:10:10Z / 11:10:08Z, revoked/final, no
  errors, admissions inactive, same identity.
- Inventory 11:10:25Z (frozen replace.py @391d2006): +22 events (owned_STOP; primary 16, guard 6); cumulative 57/150,
  20/45; max k 3/8, 2/6 (manual cross-check, gates CLEAR). Dispatch replacement-r3.json ab8b6238 (575 rows = 553 + 22;
  03 286 / 04 289; 4644 games); exact coverage 3325 + 575. Ledger 4a56abf3 -> 153eb421.
- 11:10:54Z / 11:10:57Z k4s-confirm-replacement-r3 staged (extras sha OK, overlay 175/175, PREREG 9650972d); qualification
  running (03 PGID 2360714, 04 PGID 1383353).
- 2026-10-12T11:21:22Z 04 apt-daily fired 11:20:06Z; quiet-read v2 x2 per host (11:20:32Z/33Z, 11:21:04Z) all quiet; posted "03/04 quiet" at 11:21:05Z (disclosed: K4S r3 qualification running on both). Holding r3 launches for per-host "released" / 30 min from GO.
- 2026-10-12T11:22:52Z coordinator GO to perception (COORDINATOR c00317cf); r3 launch held per host until "released" or 2026-10-12T11:52:52Z.
- 2026-10-12T11:24:49Z coordinator relayed "released 127x04" (perception session closed, exit 0); 03 still held.
- 2026-10-12T11:26:38Z coordinator relayed "released 127x03" (perception session closed, exit 0); both hosts released.
- 11:26:04Z / 11:27:12Z qualification PASS 28/28 (04 / 03); runtime == smoke; pin.verify OK; carry-over byte-identical; 03 idle
  pin OK; auth v5 7f3f7b5e; barrier PASS 176 (11:27:45Z / 11:27:47Z); prelaunch quiet-read v2 x2 per host OK; stamps fresh.
- **11:28:44Z / 11:28:49Z replacement-r3 LAUNCHED**: 03 sup 2373197, 04 sup 1396984 (admitted, 0 foreign/active, no console);
  copiers 03 876522 (core 62), 04 884802 (core 63), registrations match. Receipt rounds/r3/RECEIPT.json (evidence hashed).
  Next cut ~13:20Z (04 apt-daily-upgrade 13:27:55Z; 03 13:46:58Z).
## Running (owned PGIDs only) -- CURRENT
- replacement-r3 in k4s-confirm-replacement-r3: 03 sup PGID 2373197, 04 sup PGID 1396984; copiers on 05 876522 / 884802.
  Health: K4S_NS=k4s-confirm-replacement-r3 K4S_PHASE=replacement-r3 tools/watch.sh
- 2026-10-12T11:38:55Z SEALED health: 127x03 complete 13 acked 13 hub 13/13 failed 0 stopevent - inflight 11 queued 262 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 14 acked 14 hub 14/14 failed 0 stopevent - inflight 11 queued 264 reason None who 0 flags[dbus 11 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 57/300 guard 20/90 (union; already in ledger 0/0); ledger max k {'primary': 3, 'guard': 2}; no anomalies
- 2026-10-12T11:40:25Z Round r3 audit PASS_WITH_NOTES retained (audits/ROUND-r3-AUDIT.md 1506eb25). Quiet-read v3 (rounds/r4/quiet-read-v3.cmd a293207e; adds apt-config|apt.systemd.dai) tested read-only 11:39:36Z and 11:40:07Z on both hosts: rc 0, units inactive, maint=0, who=0, helpers at baseline; offline pattern check: v3 catches apt.systemd.dai and apt-config, v2 did not. Checklist step 6 now v3.
- 2026-10-12T11:42:16Z Round r3 audit F1: candidate checkpoint.py (tools/candidate-r4/) derives per-host expected completions from the phase's own dispatch via rounds/history.json, sha-bound to history and to launch.json (new LAUNCHDISPATCH read); on supervisor exit the SUPEXITN counts must account for every dispatched block (null exit: unstarted 0, completed == complete.json count); any missing/mismatched input is an anomaly. 74/74 tests (also -O, SyntaxWarning as error). NOT deployed; Sol review requested. r4 hand check at every read if not approved by launch.
- 2026-10-12T11:42:44Z r3 RECEIPT-ERRATUM (audit F2 labels): apt fire 11:20:06Z; copier exits 11:10:02Z (03) / 11:10:01Z (04) from finished_utc; GO go_utc 11:22:39Z, timeout 11:52:39Z; stamp-read times from mtimes.
- 2026-10-12T11:53:17Z Sol checkpoint review r4 REQUEST_CHANGES retained (reviews/SOL-REVIEW-CHECKPOINT-r4.md 4cf7860f). Candidate fixed: LAUNCHDISPATCH and SUPEXITN remote readers now parse JSON strictly (full 64-hex string compared whole; the three exit collections must be lists) and print INVALID otherwise; main() re-validates (SHA64 fullmatch; exit_counts = exactly three nonnegative decimal ints). +37 extraction-to-main tests run the real template with bash on synthetic files: 111/111 (also -O); 32 fail on the cae34ed5 candidate. Still NOT deployed; hand check at cut 3 and every r4 read.
- 2026-10-12T11:53:56Z SEALED health: 127x03 complete 47 acked 47 hub 47/47 failed 0 stopevent - inflight 11 queued 228 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 45 acked 45 hub 45/45 failed 0 stopevent - inflight 11 queued 233 reason None who 0 flags[dbus 42 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 57/300 guard 20/90 (union; already in ledger 0/0); ledger max k {'primary': 3, 'guard': 2}; no anomalies
- 2026-10-12T11:55:37Z handcheck.py v2 (coordinator: keep using; local-only): any missing/malformed input -> UNKNOWN + flag (exit 2); records its own sha256 (e2027200). Tested on 9 synthetic cases + real receipt. A stray handcheck-UNKNOWN.json written into health/ by one of my own tests (fallback-path bug, fixed) was deleted; never committed.
- 2026-10-12T12:06:19Z Sol checkpoint review r5 REQUEST_CHANGES retained (reviews/SOL-REVIEW-CHECKPOINT-r5.md fea303cb). Candidate: both readers capture output+status first (if out=$(...); then KEY $out; else KEY INVALID); parse() rejects unknown/empty/duplicate keys (anomaly, exit 2). +14 tests incl. python3 PATH shim (valid stdout then exit 7) per reader and both: 125/125 (also -O); 13 fail on 96df3861. Full real template parses cleanly (14 keys). Not deployed; hand check continues.
- 2026-10-12T12:09:28Z SEALED health: 127x03 complete 80 acked 80 hub 80/80 failed 0 stopevent - inflight 11 queued 195 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 78 acked 77 hub 78/77 failed 0 stopevent - inflight 11 queued 200 reason None who 0 flags[dbus 75 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 57/300 guard 20/90 (union; already in ledger 0/0); ledger max k {'primary': 3, 'guard': 2}; no anomalies
- 2026-10-12T12:14:17Z checkpoint.py DEPLOYED: Sol checkpoint r6 APPROVE (reviews/SOL-REVIEW-CHECKPOINT-r6.md 609d62c1). tools/checkpoint.py = 05d0908f (round r3 audit F1: expected counts from the phase dispatch; strict remote readers; strict parse), tests 536a5b2d (125/125, also -O). Previous aa898ab2 + tests e1ae76e8 kept in tools/shelved/. Hand check retires after the first clean live run on the new tool; manual cross-check stays at each inventory.
- 2026-10-12T12:24:43Z SEALED health: 127x03 complete 111 acked 110 hub 110/110 failed 0 stopevent - inflight 11 queued 164 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 108 acked 108 hub 108/108 failed 0 stopevent - inflight 11 queued 170 reason None who 0 flags[dbus 105 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 57/300 guard 20/90 (union; already in ledger 0/0); ledger max k {'primary': 3, 'guard': 2}; no anomalies
- 2026-10-12T12:25:02Z First live runs on checkpoint.py 05d0908f clean (12:19:52Z, 12:24:43Z): expected 286/289 from dispatch ab8b6238, LAUNCHDISPATCH matches on both hosts, no anomalies. Hand check RETIRED after the final record replacement-r3-20261012T122443Z-handcheck.json (OK). Manual cross-check stays at each inventory.
- 2026-10-12T12:40:00Z SEALED health: 127x03 complete 142 acked 142 hub 142/142 failed 0 stopevent - inflight 11 queued 133 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 141 acked 141 hub 141/141 failed 0 stopevent - inflight 11 queued 137 reason None who 0 flags[dbus 138 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 57/300 guard 20/90 (union; already in ledger 0/0); ledger max k {'primary': 3, 'guard': 2}; no anomalies
- 2026-10-12T12:40:46Z Coordinator: cut 3 may carry a perception read window (~160 proof files from 03/04, pending package review). After quiet-read v3 x2: post "03/04 quiet"; then GO -> per-host hold until "released" / 30 min from go_utc, or "no window" -> launch r4.
- 2026-10-12T12:47:45Z Cut-3 read window DECLARED (COORDINATOR 328fb83e): perception supplemental export on 03 and 04. After quiet-read v3 x2 post "03/04 quiet"; hold r4 per host until "released" or 30 min from GO go_utc.
- 2026-10-12T12:55:19Z SEALED health: 127x03 complete 172 acked 172 hub 172/172 failed 0 stopevent - inflight 11 queued 103 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 171 acked 171 hub 171/171 failed 0 stopevent - inflight 11 queued 107 reason None who 0 flags[dbus 168 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 57/300 guard 20/90 (union; already in ledger 0/0); ledger max k {'primary': 3, 'guard': 2}; no anomalies

## P2 cut 3 (r3 -> r4), 2026-10-12
- 13:16:55.777Z / 13:16:55.781Z joint owned STOP of replacement-r3 (03 sup 2373197, 04 sup 1396984); exits 13:17:00Z /
  13:16:59Z owned_STOP: 03 219/11/56, 04 217/11/61. Recorded PGIDs (03 231, 04 229) 0 live (ps rc 0). complete sets ==
  exit lists. Drain: 219 + 217 ACK bindings OK; copiers 876522 / 884802 finished_utc 13:17:25Z, ps -p rc 1 at 13:17:34Z /
  13:17:33Z, revoked/final, no errors, admissions inactive.
- Inventory 13:17:49.778Z (frozen replace.py @391d2006, rc 0): +22 events (owned_STOP; primary 16, guard 6); cumulative
  73/150, 26/45; max k 3/8, 3/6 (manual cross-check, CLEAR). Dispatch replacement-r4.json 3aa43065 (139 rows = 117 + 22;
  03 71 / 04 68; 1140 games); exact coverage 3761 + 139. Ledger 153eb421 -> 649272bd.
- 13:18:19Z / 13:18:22Z k4s-confirm-replacement-r4 staged (extras sha OK, overlay 175/175, PREREG 9650972d); qualification
  running (03 PGID 2573704, 04 PGID 1596026). Read window declared (328fb83e).
- 2026-10-12T14:01:48Z GO to perception supplement (COORDINATOR 8be7ca00); r4 held per host until "released" or 30 min from go_utc.
- 2026-10-12T14:03:15Z coordinator relayed "released 127x03" and "released 127x04" (perception supplement sessions closed, exit 0).
- 13:27:59Z / 13:47:03Z apt-daily-upgrade fired on 04 / 03; quiet-read v3 x2 per host (13:47:38Z, 13:48:09Z); "03/04 quiet" 13:48:10Z
  (r4 qualification already finished: 04 13:33:46Z, 03 13:34:51Z PASS 28/28). GO 8be7ca00 (14:01:29Z); both released 14:03:15Z.
- 14:03Z finalize both (runtime == smoke, pin.verify OK, carry-over, 03 idle pin), auth v6 33e4526a, barrier PASS 176; prelaunch
  quiet-read v3 x2 (14:03:50Z, 14:04:21Z); stamps fresh (04 release stamp valid to 21:32:48Z).
- **14:04:39Z / 14:04:44Z replacement-r4 LAUNCHED** (final round): 03 sup 2589813, 04 sup 1612061; copiers 2182223 / 2190563.
  Receipt rounds/r4/RECEIPT.json. Expected end: null exit with 71 / 68 completed.
## Running (owned PGIDs only) -- CURRENT
- replacement-r4 in k4s-confirm-replacement-r4: 03 sup PGID 2589813, 04 sup PGID 1612061; copiers on 05 2182223 / 2190563.
  Health: K4S_NS=k4s-confirm-replacement-r4 K4S_PHASE=replacement-r4 tools/watch.sh
- 2026-10-12T14:08:03Z Completion plan (coordinator: sealed only; release, END and Mac each need explicit GO):
  1. After the r4 null exits (71/68): final durability/ACK pass over every counted block of all 5 phases. Per block:
     hub-ack bound (hub 127x05, host, job, phase, block, complete sha), returned marker bound, and game-file SHA-256 ==
     complete.json games map. Hash only; no game content parsed.
  2. counted-inventory.json in the frozen end_evidence format ({host, phase, descriptor} rows = the raw exit
     descriptors; 3000/900 logical blocks exactly once; no lost id counted). Completion receipt with the §7/END fields:
     reporting_complete, outcomes_sealed, counted_primary_blocks 3000, counted_guard_blocks 900, counted_host_phases,
     completed_at_utc, blind_ledger_sha256, counted_inventory_sha256.
  3. Sealed reducer/verifier = PREREG §4.5 "fails closed before it opens any game bytes": run each with NO release
     receipt and record the refusal. reduce.py calls barrier.outcome_release before load_blocks; verify_k4s.py raises
     Refusal("no release receipt") before any game file. Nothing outcome-bearing is computed, printed or committed. If
     either tool would get past its barrier, STOP and report.
- 2026-10-12T14:16:12Z SEALED health: 127x03 complete 19 acked 19 hub 19/19 failed 0 stopevent - inflight 11 queued 41 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 16 acked 16 hub 16/16 failed 0 stopevent - inflight 11 queued 41 reason None who 0 flags[dbus 13 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 73/300 guard 26/90 (union; already in ledger 0/0); ledger max k {'primary': 3, 'guard': 3}; no anomalies
- 2026-10-12T14:16:33Z Round r4 audit PASS_WITH_NOTES retained (audits/ROUND-r4-AUDIT.md 311061f8). Coordinator: at r4 completion do the step-2 drain by hand as part of the final durability pass (STOP-COPY, copier exit, revoked health, inactive admissions, each recorded with a hash); HOLD the reducer and verifier (even sealed) pending the DBus-flag investigation (04 ~97% of blocks OP-1 DBus-flagged vs 0% on 03); completion receipt and durability/ACK verification may proceed.
- 2026-10-12T14:25:49Z DBus ruling (COORDINATOR after 3f7240f9; investigation audits/K4S-DBUS-FLAG-INVESTIGATION-r1.md cc1c56ff retained): R1 OP-1 DBus flags descriptive (no stop/exclusion/sensitivity); R2 outcome-blind disclosure before any reduction (then reducer/verifier sealed-only allowed); R3 no DBus-exclusion analysis; R4 after r4 + copier off: 30-min read-only 04 system-bus baseline over one long-lived ssh (nice 19), gates END (<1% clearly -> END as frozen); R5 04 DBus level known; alert only on change.
- 2026-10-12T14:30:41Z SEALED health: 127x03 complete 47 acked 47 hub 47/47 failed 0 stopevent - inflight 11 queued 13 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 47 acked 47 hub 47/47 failed 0 stopevent - inflight 11 queued 10 reason None who 0 flags[dbus 44 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 73/300 guard 26/90 (union; already in ledger 0/0); ledger max k {'primary': 3, 'guard': 3}; no anomalies
- 2026-10-12T14:44:30Z SEALED health (final r4): 127x03 complete 71 acked 71 hub 71/71 failed 0 stopevent - inflight 0 queued 0 reason None who 0 flags[dbus 0 ssh 0 apt 0 idle 0]; 127x04 complete 68 acked 68 hub 68/68 failed 0 stopevent - inflight 0 queued 0 reason None who 0 flags[dbus 65 ssh 0 apt 0 idle 0]; lost this phase primary 0 guard 0; cumulative primary 73/300 guard 26/90 (union; already in ledger 0/0); ledger max k {'primary': 3, 'guard': 3}; null exits 71/0/0 and 68/0/0; no anomalies
- 14:44:10Z final r4 health: null exits 71/0/0 (03 14:43:51Z), 68/0/0 (04 14:40:39Z). Drain by hand: 139 ACK bindings OK;
  copiers 2182223 / 2190563 finished 14:44:54Z, ps rc 1 14:45:02Z, revoked/final, admissions inactive; STOP-COPY removed.
- **14:45:34Z REPORTING COMPLETE**: final_pass over 5 phases x 2 hosts: 3900 counted (3000 primary / 900 guard, each logical
  block once), all 33000 game files sha-matched (hash only), all ACK/returned bindings OK. counted-inventory f10ab943,
  REPORTING-COMPLETION.json. Ledger 649272bd (99 events: primary 73, guard 26).
- 2026-10-12T14:46:15Z R2 DBus disclosure committed (completion/DBUS-FLAG-DISCLOSURE.md): 04 1906/1931 flagged (98.7%), 03 0/1969;
  SSH/apt/idle 0; interference_any_flag count 1459/447 (nothing excluded); §5.3(2) drops 0.
- 14:45:20Z R4 04 bus baseline running (30 min, one ssh, nice 19) -> end-gate/04-dbus-baseline-r1/.
- 2026-10-12T14:48:09Z Sealed reducer/verifier runs (rounds/final/sealed/SEALED-RUNS.md): no --release; reduce.py fails closed in barrier.outcome_release before load_blocks (rc 1, no output); verify_k4s.py REFUSED 'no release receipt' (rc 2). Audit-hook guard: 0 accesses to final-view/hub-blocks/games. strace unusable (openat2 unknown; ptrace denied) - attempts recorded.
- 2026-10-12T15:06:16Z ERRATUM: v1 counted-inventory envelope not the frozen end_evidence format (END would refuse). completion-v2/ candidate (inventory 22c41cb7, completion 3794d953; rows identical) validated by frozen counting(); final_pass.py envelope fixed. Coordinator to rule which receipt is of record.
- 2026-10-12T15:07:07Z K4S END plan draft committed for review (end-plan/; research by delegated Opus high; B1 confirmed and fixed as candidate completion-v2; B2/B3 confirmed from code). Nothing launched.
- 2026-10-12T15:15:56Z R4 04 bus baseline DONE (end-gate/04-dbus-baseline-r1/RESULT.md): 14:45:20Z-15:15:33Z, 1800 samples, pid 2005/1032 throughout; whole 0.0359% core; max 30-s 0.0993%, 600-s 0.0400%; 0 windows >0.7%. Clearly <1% (idle host; not under END load).
- 2026-10-12T15:16:31Z Coordinator: R4 PASSED (END with frozen DBus threshold). END attempt rule: one launch SSH closed before admission; no copier during timing; C5 no SSH from any thread to the timed host. Process: probe.sh accepted post hoc (read-only /proc under R4); from now on EVERY new host-touching script (B2 copier, B3 assembler, any other) is reviewed BEFORE it runs.
- 2026-10-12T15:23:40Z END plan ADOPTED_WITH_CHANGES (review audits/K4S-END-PLAN-REVIEW-r1.md b69f015d retained; COORDINATOR after 4af19c23). completion-v2 (23604d1c) is the record of truth; RC-1 disclosure completion-v2/RC1-DISCLOSURE.md. Next: plan v2 + scripts S1-S7 offline for Sol review; target 03 launch ~02:00-04:00Z 10-13.
- 2026-10-12T15:25:27Z END plan v2 committed (end-plan/K4S-END-PLAN-v2.md): review RC-1..RC-9 + coordinator rulings folded in; scripts S1-S7 being authored offline (s1s2-r1, s5s6s7-r1, b3-r1) for Sol review; nothing touches a host until reviewed + authorized.
- 2026-10-12T15:40:32Z B3 candidates (end-prep/b3-r1: DESIGN 950ecb7a, OPEN-QUESTIONS 0ec3d6f1, assemble_fleet_reference.py 00f4dea5, tests 4b74e866; 92/92 incl. -O vs real frozen consumers) committed as candidates (not used). New issues: guard seed git lookups on hosts (Q3), 33 non-git runtime-pin files (Q5), T1 states/sets source (Q6).
- 2026-10-12T15:41:57Z Coordinator S4 rulings: Q3 Option A (guard job repo = K4S-owned git clone with b2f9e25e+ce042b97; S5 runs git cat-file -e first); Q5 runtime = END-JOB commit (>=133f3ae4, e4v3 = 74314eda pins) + the 33 non-git runtime-pin-r2 files ONLY from bytes already on 05 matched by SHA (T1 A5 runtime trees on 05 or K4S overlay copy on 05; read-only; missing -> stop for ruling); Q6 T1 states 0addf7c0 at t1-20261010-r1/end-a5-pool-context-20261012-r1/bundle/states.pkl + A3 rows bcd30777/8cc2f611 on 05 (byte-exact, sha both ends); Q2 approved (latest K4S system-bus-admission + 03 idle-services via S1 mechanism, committed before END-JOB); Q4 approved (fresh guard job per attempt); Q9 confirmed. S4 bundled with others for Sol.
- 2026-10-12T15:59:44Z Sol END package 1 r1 REQUEST_CHANGES (reviews/SOL-REVIEW-END-PKG1-r1.md retained). Coordinator: TOCTOU residual accepted; all other findings required (S1 F1-F4, S2 F1-F3, S4 F1-F3, census/MHz mismatch diagnosis). Overnight target may slip; correctness first.
- 2026-10-12T16:12:21Z Perception final-dependencies window (COORDINATOR 0ae37ef1): quiet-read v3 x2 per host 16:11:43Z/16:12:16Z all quiet (helpers baseline); posted "03/04 quiet (final-dependencies window)"; no K4S END host step until both releases.
- 2026-10-12T16:14:56Z Coordinator relayed released 127x03 and 127x04 (perception final-dependencies window closed; no further perception source access). 03/04 reserved for K4S END; each host step still needs Sol review + coordinator authorization. S5/S6/S7 candidates committed (end-prep/s5s6s7-r1; 155 pass, -O 145 + 11 skipped verifier-refuses-O).
- 2026-10-12T16:41:30Z Package 1 r2 ready: S1+S2 r2 (end-prep/s1s2-r2; 86/86 incl -O, verified by me) and S4 r2 (end-prep/b3-r2 12928087; 164/164 incl -O with frozen root, verified by me).
- 2026-10-12T16:42:53Z Coordinator: pkg1 r2 routed to Sol (-> reviews/SOL-REVIEW-END-PKG1-r2.md). (b) accepted (re-pin ruling needed after any reboot/03 cache restart before S4 runs). (a) accepted in principle as exactly two enumerated exceptions (symlink exact committed link text, never followed; training receipt path+SHA, never parsed; no patterns/prefixes), final after Sol. /usr/bin/python3 on hosts stays unverified until host steps (S1 fail-at-first-login acceptable). Package 2 to be sent as ONE message incl. S5-S7 fcb74fd2.
- 2026-10-12T16:55:45Z Sol pkg1 r2 (reviews/SOL-REVIEW-END-PKG1-r2.md e347219d; COORDINATOR ab171591): S1 APPROVE (offline); S2 REQUEST_CHANGES (R2-F1 shared location gate on every explicit input + full-entrypoint zero-forbidden-open controls; R2-F2 profile content validation, no silent default, correct profile_source); S4 REQUEST_CHANGES (R2-F1 BLOCKING st_nlink==1 gate + inode canary; R2-F2 auxiliary END-location confinement; R2-F3 synthetic pins through confinement). E1 symlink exact committed link text, target through hard-link gate; E2 training receipt exact path+SHA d1492d0f hash-only; E3 stale admission identities refused -> re-pin ruling; admissions under reports/explore/k4s-confirm/end-guard-admissions/. S2+S4 r3 asap, not waiting for pkg2.
