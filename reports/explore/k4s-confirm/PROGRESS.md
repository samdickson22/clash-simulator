# PREREG-K4S freeze-fill preparation: progress

Worker: Opus 5.5 (1M), running on 127x05 for coordinator thread 0523ae6f; assigned 2026-10-11 ~13:10Z.
Job name: clasher-prereg-k4s-freeze-prep-20261011-r1.
Scope: prepare every freeze fill. **No freeze and no reporting game.**

## Fixed facts
- PREREG: `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md`, sha256 `9650972d…` (verified 13:07Z on origin/main 756a6559).
- c\* = 0.9 (COORDINATOR.md 11:46Z entry, commit 6ef5e2ff).
- T1 runtime: `ef4c073a` is on branch `origin/worker/t1-op7-apt-20261010`, **not** an ancestor of main. Its
  `reports/explore/t1/` tree is read with `git show/archive ef4c073a`. No T1 job directory is read or written.
- Inherited runtime: the X4S-2 job on 03 carries `s1-runtime-pin-r2.json`, sha256 `f81f3655…`. That equals T1's
  `inherited_runtime_pin_sha256`, so the K4S runtime is staged from `/mpac/sdicks02/jobs/clasher/x4s2-20261011`
  (repo, native, native-source, inputs, corpus) and verified file by file against that pin.
- Work tree: the dedicated worktree `/mpac/sdicks02/repos/clasher-k4s-prep` (detached at origin/main). The shared
  checkout is never modified.
- Compute: 127x03 only, nice 19, ≤ 96 threads, ≤ 60 GB. Job dir `/mpac/sdicks02/jobs/clasher/k4s-prep-20261011/`.
  STOP file: `…/k4s-prep-20261011/STOP`.

## Log (UTC from `date -u`)
- 13:07Z: read r3, CONFORMANCE-r2, RECHECK-r3, COORDINATOR K4S entries and the c\* record. 03: 0 console users, load 0.1.
- 13:12Z: copied T1 ef4c073a code into this directory. Applied the mechanical path rebinding (`rebind.py`) to 14 infra files.
- 13:14Z: K4S-SPEC.md written (the record and reduction contract). Delegated: verifier (Haiku max, independent, task
  k4s-verifier-r1), seed audit (Haiku max, k4s-seed-audit-r1), Mac script and procedure (Opus high, k4s-mac-script-r1).
- 13:19Z: staged the dev runtime on 03 at `k4s-prep-20261011/qual-03-dev`. 1557/1557 inherited files and 77 native-source
  files verified against pin f81f3655. Corpus `8b188918…` equals T1's 01 qualification corpus. STOP is a symlink to `../STOP`.
- 13:21Z: SD1-MANIFEST.json built on 03 (torch 2.10.0+cu128, CPU float32, 1 thread). `sd1_manifest.py check` passes.
- 13:24Z: first 125-state run: all equality checks pass (K4 == T1 anchor, K4S == K4, SD1Policy == CachedPolicy).
  Injected budgets were refined to hit the completed-play case. Game-level qualification launched in 7 slots (35 cores).
- 13:30Z: dev 125-state qualification PASS (125/125 on every equality; injected: 181 SD1-play defaults, 560 SD1-WAIT
  keeps, 139 completed-play keeps). No-deadline command hashes: K4 (K4S runtime) == T1 ef4c073a K4-200 == K4S-200 on
  qualification seeds 0 and 1. Charge share within 0.008 of 1−c on belief/sample/scored paths, 0 decisions outside
  ±0.02. Zero budget returned the SD1 default on 560/560 decisions.
- 13:33Z: inherited T1 suite plus K4S tests pass on 03. The OP-5 tests need 4 committed receipts, exported by
  `git show` (reference-files.json).
- 13:34Z: STOP test: STOP touched 13:34:31.909Z, game aborted 13:34:31.928Z; 0 owned processes left; STOP removed.
- 13:35Z: seed audit (Haiku) PASS: 13/13 named banks, 0 overlaps, 0 non-declaration literals. The verifier (Haiku,
  independent) agrees with the reducer on every decision for a full synthetic tree. Verifier round 2 (exact
  `verifier_view` compare) launched.
- 13:39Z: Mac script (Opus) delivered, 73 tests pass. It found a **TIERS blocker**: frozen `measure_tiers.py`
  (sha `5d7de8e3…`) uses `math.isfinite` at l.70 without `import math`. I verified this.
- 13:40Z: Sol review r1 of the core harness launched. Delta 8 (end_reference.py, end_pool.py) written and
  logic-tested. It cannot execute: the T1 K4 corpus is stored only under T1 job dirs.

- 13:44Z: Sol core review r1: APPROVE_WITH_FIXES (4 MAJOR, 3 MINOR). Sol Mac+END review r1: REJECT (2 BLOCKER,
  7 MAJOR); an Opus fix agent was launched (task k4s-mac-end-fix-r1). Verifier r2: exact `verifier_view` compare,
  169/169 items match the reducer in 3 synthetic scenarios (receipts/reducer-verifier-crosscheck.json).
- 13:50–13:57Z: core fixes:
  - canonical descriptor validation, in the runner and in the reducer with a blind-ledger replay;
  - strict `check_games` with a nonzero exit, plus smoke charge and field checks in `health.py`;
  - guard-receipt projection compare;
  - `frozen_action` and slot/attempt/tick/crowns/draw fields;
  - the inherited OP-6/OP-7 sidecar sensitivity, and rate CIs with per-game numerator/denominator, GC and WAIT-spiral
    tables.
  New: a full-runner virtual-clock T1 vs K4S comparison. Native budgets are enforced in virtual time and the poll-cost
  cycle is coprime with the poll cadence. Trial on qual seed 5: identical command hash, 0/241 decision mismatches;
  coverage 22 belief cutoffs, 128 scored cutoffs, 5 overruns.
- 13:58Z (coordinator update): perception released 127x04 early (receipt `04-allocation-release-20261011-r1.json`,
  SHA 5f59f7f8; A2 complete; 03/08 transports retired, c2cef696).
  - **Planned K4S host set {127x03, 127x04}.** The host set is left blank for the coordinator.
  - 04 is available on the same terms as 03 (nice 19, STOP, ≤96 threads, ≤60 GB). No ssh to 01/08.
  - **04 storage rule:** never modify or delete anything under `/mpac/sdicks02/jobs/clasher/` or
    `/mpac/sdicks02/repos/clasher-v4-cache/` on 04. My 04 job dir is therefore `/mpac/sdicks02/jobs-k4s/k4s-prep-20261011/`,
    with STOP `/mpac/sdicks02/jobs-k4s/k4s-prep-20261011/STOP`. `who` at 13:58Z: 0 users, load 0.0.
- 2026-10-11T13:59:10Z: copied the pinned S1 base from 03 to `04:…/jobs-k4s/k4s-prep-20261011/base-s1` over the LAN (pin
  sha f81f3655… verified). Staging re-verifies every file.

- 2026-10-11T14:08:24Z: dev pipeline on 03 (qual-03-dev2) and 04 (qual-04-dev).
  - The game stage passes on both hosts with identical hashes: no-deadline K4 = T1 = K4S; virtual-clock full runner
    T1 vs K4S has 0 mismatches over 452 decisions (51 belief cutoffs, 229 scored cutoffs, 17 overruns); charge share
    max deviation 0.0072.
  - Test stage found two host-environment issues:
    - The verifier tests need a git checkout. They run on the 05 checkout instead (95 passed).
    - T1 `test_op7::test_fresh_reaps_cannot_renew_stale_orphan_debt` needs host uptime above about 16.85 days (its
      fixture start_ticks is 145613425), so it fails on 04 at 12.7 days. It now runs via `test_op7_boottime.py` with
      a pinned CLOCK_BOOTTIME; T1 bytes are unchanged and the deviation is disclosed.
  - T1 END host check (Haiku research, spot-checked): T1 END needs neither 03 nor 04 for compute (Amendment 1 pool =
    counted hosts 01+08). 03 holds T1's corpus durability copy (storage only). Recorded in FREEZE-RECORD-SKELETON §E.
  - Sol core r2 and the Mac/END fix agent are running.

## Status
| Item | Status |
|---|---|
| 1 SD1 manifest + supersession draft + exit-r3 pointer draft | drafted (SD1-MANIFEST.json, SD1-SUPERSESSION-DRAFT.md) |
| 2 Seed audit | PASS (seed-audit.json, SEED-AUDIT-RECEIPT.md); re-run at the freeze commit |
| 3 Harness + delta manifest + reducer + verifier + Sol review | built; Sol r1 and verifier r2 running |
| 4 Qualification on 03 | dev PASS; final run after review |
| 5 K4S Mac script + procedure (N2) | drafted (mac/); needs Sol review |
| 6 Freeze-record skeleton | pending |

## Running processes (127x03)
None (dev qualification finished at 13:33Z).

## Next
Sol r1 fixes; Sol review of mac/ and END; final fresh qualification on 03 (`qual-03-r1`); freeze-record skeleton; commit.
