# X4S progress (exploration, NEVER ADOPTABLE)

Job root on hosts: /mpac/sdicks02/jobs/clasher/x4s-20261011 (127x03, 127x08; mirror on 127x05 under mirror/).
STOP file: <job>/STOP on each host. Hard stop 2026-10-11T14:00:00Z.

## Log (date -u)
- 2026-10-11T01:27Z: assignment received; read REVIEW-K, K, S1.
- 01:33Z: runtime staged on 03 from k-anytime-20261010-r1 + git s1/x4s overlay; inputs SHA-verified (native 44874fd6…, R3a 37509a43…, cal e3003533…, v1 d77005d5…); all 1,557 S1 runtime-pin-r2 files match. Mirrored to 08.
- 01:35Z: unit tests 31 passed (test_sdefault + S1 anchor/latency).
- 01:36Z: seed audit clean: reporting 4503604807370496+[0,600), smoke …4817…+[0,8), qualification …4827…+[0,8).
- 01:36Z: corpus qualification PASS on 03: K4/K4S frozen 125/125, K4S==K4 125/125, zero-budget→R3a 125/125, injected student default 124, root immutable 125.
- 01:36Z: no-deadline game qualification PASS on 08: K4 vs K4S command hashes identical on 2/2 qualification seeds.
- 01:39Z: STOP test PASS on 08: STOP 01:39:09Z, supervisor exit 01:39:11Z, 0 group processes left; STOP removed.
- 01:37–01:4xZ: smoke (8 seeds × 9 arms) on 03; ~35–50 s/game. Sol review r1 requested (task x4s-sol-review-r1).

## Resume notes
- Launch: repo/reports/explore/x4s/detach.sh LOG RECEIPT nice -n 19 taskset -c 62 bash repo/reports/explore/x4s/runtime.sh reports/explore/x4s/supervise.py --job J --phase P --range reporting --indices J/x4s-idx03.json|x4s-idx08.json
- Never reuse a phase directory; interrupted blocks are excluded and their seeds retired.
- 01:44Z: Sol review r1 (gpt-6.1-sol, task x4s-sol-review-r1): S-default rule, timer charge, RNG/candidate parity and pairing judged correct; 9 operational findings fixed: supervisor try/finally + flag-only signal handlers + timeouts; sync retires a host only after a successful post-stop pull with no live X4S process (nice 19 remote rsync); 50 GiB owned-PSS guard; fsync of games and block proofs; preparation-cutoff student plays counted as student_default; corpus clock budgets extended.
- 01:45Z: unit tests r2 31 passed; corpus qualification r2 PASS (same counts). Completed-play-kept/student-WAIT paths covered by unit tests only.
- 01:44Z: smoke complete: 72 games, 8 blocks, 425 s wall on 8 slots (~7 min per 9-game block); excluded, outcomes not inspected.
- 01:50Z: STOP test r2 PASS on 08 (new supervisor): STOP 01:50:15Z → exit 01:50:17Z, durable block written, 0 X4S processes left; STOP removed.
- 01:50Z: freeze commit 63538665 pushed (plan, harness, seed audit, qualification receipts); deployed bytes on 03/08 verified equal.
- 01:50:49Z / 01:50:50Z: REPORTING launched: reporting-03 (300 indices, (i//50) even) and reporting-08 (300, odd), 12 slots each, 5-core masks verified; sync puller on 05 (logs/sync-pid.json). Expected ~7 min per block per slot → ~3 h.
- 02:17Z: progress 03 50/300 blocks, 08 49/300; 98 blocks mirrored to 05; MemAvailable 118 GiB, owned PSS ≤3.8 GiB; no console users. ETA ~04:30Z.
- 02:45Z: progress 03 103/300, 08 104/300 blocks; 206 mirrored; healthy (MemAvailable 118 GiB, PSS ≤3.9 GiB, no console users). ETA ~04:35Z.
- 03:13Z: progress 03 164/300, 08 164/300 blocks; 328 mirrored; healthy. ETA ~04:25Z.
- 03:42Z: progress 03 225/300, 08 224/300; 449 mirrored; healthy. ETA ~04:20Z.
- 04:18:12Z (03) / 04:18:32Z (08): REPORTING COMPLETE, 300/300 blocks per host, rc 0, empty groups. 04:19Z STOP files placed on both hosts to retire sync; 04:20:39Z sync retired both hosts, 5,400 games mirrored. 127x08 holds zero X4S processes.
- 04:21Z: reduced (results.json); independent raw recount matches. RESULTS.md written.
