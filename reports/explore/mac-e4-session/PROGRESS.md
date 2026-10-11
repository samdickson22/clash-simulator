# Mac E4 measurement session: operator progress (resumable)

Operator: Opus subagent `clasher-mac-e4-session-20261011-r1` on 127x05, for coordinator thread
`0523ae6f-baa3-4d4e-b233-b392671670db`. The task was assigned at about 20:13Z on 2026-10-11 under Sam's ~20:11Z replay-only
authorization ("you got it"). The session is replay only: no live games, client, ladder, emulator control or
detection evasion.

**Resume rule:** read this file top to bottom, then the latest checkpoint. All Mac state lives under
`/Users/sam/Desktop/code/clasher-mac-e4-tiers-20261011/` (Mac mini, via `ssh macmini-fleet`). Never touch Sam's
other trees (`~/Desktop/code/clasher`, `clasher-runtime-v4`, …); they are read-only sources.

## Gates for Phase B (TIERS Mac session)

| Gate | Status |
|---|---|
| G1. T1 END pooled fleet reference + reviewed T1-REGISTRATION packet committed on main | WAITING (END running on 01/08) |
| G2. `measure_tiers.py` 6066228b; bundle prepared after 6afcbbab | Mac runtime staged at d651b52c (post-6afcbbab); sha verified on Mac |
| G3a. Bundle/manifest identity (deterministic tiers-pins SHA, independently approved) | needs registration packet first |
| G3b. 5-min quiescence census: no foreign PID > 0.2 core | AT RISK (see blockers) |
| G3c. Perception ≥18 FPS on replay | pending preflight |
| G3d. arm64 build of the frozen tier Rust source | preflight build running |

## Mac staging layout (`$S` = `/Users/sam/Desktop/code/clasher-mac-e4-tiers-20261011`)

- `runtime/`: `git archive d651b52c` (T1's END post-merge source commit; e4v3/src/engine-rs trees identical to
  6afcbbab and origin/main at 20:19Z). 10,576 files verified by git blob hash against the commit.
  - Plus 33 runtime-pin files that were never committed to git. They come from `/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1`
    on 05, and each matches its `reports/explore/s1/receipts/runtime-pin-r2.json` SHA.
  - Plus the frozen **E1 native source** for `engine-rs`: `src/scripts.rs` 127c6980, `src/e1_commands.rs`
    fd757432 and `e1-source-manifest.json`. These are regenerated deterministically with committed
    `reports/explore/e1/stage_native.py` from git engine-rs. 76/77 entries match `native_source` in runtime-pin-r2,
    which is the source of Linux provenance native 44874fd6. The exception is `e1-source-manifest.json`, which is
    metadata only and not compiled; it is disclosed.
- `inputs/artifacts/`: R3a.pt 37509a43, v1.pt d77005d5, R3a-calibration.json e3003533; v3 load body.pt 8b6fde6f,
  hud.npz d09682eb, geometry.json 8104006c, split.json 3edbd25b. Two TRAIN matches:
  - `match-0`: seed 1975101190, copied from the 05 Linux-smoke bundle r6;
  - `match-1`: seed 1975100700, copied from the Mac's `clasher-runtime-v4/runtime-data/matches/v4-phase-a-1975100700`.
- `inputs/load-config.json`: v3-body-hud-only, 20 FPS, device mps, so the session is labelled PROVISIONAL-LOAD.
- `inputs/topology.json`: E=[0,1,2,3], P=[4..11]. Evidence is in `evidence/`: the ioreg logical-cpu-id/cluster-type
  dump, sysctl perflevel, and a QoS probe in which a background-QoS spin loads only indices 0–3 and a
  user-interactive spin loads 4–7. Needs independent review.
- `session.lock`: the coordinator session lease file, created by the operator. It is flocked from staging to cleanup.
- Python: the existing native arm64 venv `~/Desktop/code/clasher/.venv/bin/python`, used read-only. It is 3.12.13
  with torch 2.10.0 (MPS True), numpy 2.3.5, cv2 5.0.0, ultralytics 8.1.24, dill 0.4.1, psutil 7.2.2. This matches
  the 2026-10-08 Mac qualification packages.
- Toolchain: rustc/cargo 1.97.1, target aarch64-apple-darwin installed, Xcode CLT. The crates.io cache is present.

## Checkpoints

### 2026-10-11T20:35:18Z: Phase A preflight complete (non-counted)

Receipt: `receipts/phase-a-preflight-20261011/phase-a-summary.json` (plus runtime-staging.json, topology, evidence,
preflight logs). Results:
- runtime pins PASS;
- TRAIN admission PASS (2 matches);
- `test_measure_tiers` 33/33 on Mac Python 3.12.13; the full suite has 20 fleet-only errors (no `.git` in the
  archive runtime, Linux affinity);
- scratch arm64 build PASS in 31 s (native 0e7213ab, imports, E1 + W-screen8 methods present);
- MPS perception 20.01 FPS (p99 38.7 ms);
- **census preflight FAIL**: WindowServer 0.505 core and Codex Computer Use 0.222 core, both above the 0.2 limit.

### 2026-10-11T20:36Z: coordinator memory query (TIERS Amendment 3 in progress)

The coordinator reports that END is blocked: each TierBackend loads the whole 11.65 GB corpus (~11.5 GiB RSS).
Mac analysis:
- **RAM.** The Mac has 24 GiB unified memory. At 20:36:13Z: wired 4.6, active 7.0, inactive 7.0, free 1.0 GiB;
  swap 3.0/4.0 GiB already used.
- **Main process.** It holds one TierBackend for D1–D9. Its loader is `pickle.loads(read_bytes())`, which peaks at
  about 10.9 GiB of bytes plus about 11.5 GiB of objects, so roughly 22 GiB.
- **D6.** It spawns two sequential `forward_worker` children (cpu, then mps). Each builds its own full
  TierBackend while the main one stays resident: at least 23 GiB steady and about 34 GiB peak.
- **Perception worker.** It does not build a TierBackend; `validate_bundle` streams hashes.
- **Corpus.** The Mac bundle's `states.pkl` must also hold golden125, agreement2000 and packets1000 ids, so it
  is at least as large as the END corpus.
- **Verdict.** The Mac would OOM, or swap-thrash with invalid timing, even at the main load. The repair must
  cover the Mac path.

**Hold:** no Mac timing until the coordinator confirms the repaired loader (Amendment 3) and the pooled reference
are committed.

### 2026-10-11T20:41:58Z: coordinator rulings (sent ~20:37Z, labelled 20:42Z; correction record COORDINATOR 3c747c38); reviews launched

The coordinator accepted Phase A (b8792a6c). Rulings:
- Amendment 3 covers the Mac path: a streaming per-id load, capped at about 6 GiB total.
- Review split: Sol for code, Opus for the topology and overlay provenance.
- The coordinator arranges a quiet Mac window. Do not quit apps, and leave simonfarshid alone. Re-run the census at
  Phase B; if it fails, report the top consumers and do not start.
- Copy no bundle inputs until the END bundle identity and the registration packet are named.
- A K4S fresh clone is OK, and so is staging K4-states.pkl later with a SHA check.

New work:
- `verify_runtime_staging.py`: Mac runtime == expected (10,611 files, 0 missing/extra/differ, expected manifest
  cbe89896); receipt `runtime-verify-r1.json`.
- Reviews: Sol task `mac-e4-r1-sol-staging-review-r1`; Opus task `mac-e4-r1-opus-topology-review-r1`.

### 2026-10-11T20:49:39Z: Sol staging review APPROVE_WITH_CONDITIONS; all findings addressed

Sol reproduced `runtime-verify` PASS (10,611 files). No compiled-source defect; compiled sources and Cargo.lock match
the 44874fd6 provenance. Dispositions:
1. MAJOR, symlinks unverified: fixed. The verifier now requires `--mac-symlinks` and checks link paths and targets.
   Only `visualize_battle.py -> examples/visualize_battle.py` exists. A negative test with an injected link gives
   passes=false.
2. MINOR, duplicate or invalid listing paths: fixed. They are refused; a negative test raises "Duplicate listing path".
3. MINOR, native subtree was updated rather than replaced: fixed. engine-rs is now replaced by the stager output.
4. and 5. MINOR, perception preflight fidelity: fixed in r2 of the script (`set_num_interop_threads(1)`, per-frame
   flush, fixed post-warmup window). It was not re-run because of the Mac timing hold. Sol's recomputation of the
   r1 rows over the full window gives 20.0002 FPS.
6. MINOR, wording: `runtime-staging.json` corrected; 16 of the 17 pin deviations equal smoke, and scripts.rs differs
   intentionally.
7. NOTE: no action; a counted build and the gates are still required.

Re-verified with `runtime-verify-r2.json`: PASS, expected manifest cbe89896, symlinks equal.

### 2026-10-11T20:50:47Z: Opus topology/provenance review APPROVE_WITH_CONDITIONS; reviews complete, HOLD

See `receipts/reviews-20261011/REVIEWS.md`.
- **Topology:** marked reviewed and frozen at 20:50:00Z (Mac `inputs/topology.json` 2b2ec325, read-only).
- **Phase B checklist additions:**
  1. Apply END's PYTHONPATH additions (`runtime/imitation/evaluation/runtime_dependencies`,
     `runtime/reports/strategy_council_20260928/imitation`) unless Amendment 3 removes the need; confirm with the
     coordinator.
  2. Run the END-runtime content diff once the bundle is named. Allowed differences are scripts.rs plus the 12
     exit-r3 scripts.
  3. The libm ULP exactness risk is disclosed; D1 decides it.
  4. Census re-run in the coordinator's quiet window.
  5. Fresh counted build via build_tiers.sh.
- **K4S:** fresh partial clone `$S/k4s-commit-repo` (3cd0e58b, 465 MB, user Sam Dickson) for the procedure's local
  commits. K4-states.pkl will be staged later with a SHA check.
- **HOLD:** no Mac timing until the coordinator confirms Amendment 3 plus the pooled reference, and names the END
  bundle and registration packet.

### 2026-10-11T20:51:21Z: coordinator ~20:53Z rulings; HOLD until go

- **(a)** The Mac may use T1's import-path-only addition
  `PYTHONPATH += runtime/imitation/evaluation/runtime_dependencies:runtime/reports/strategy_council_20260928/imitation`.
  It must resolve only within the qualified bytes, with no other paths, and the exact environment goes in the
  session receipt. Drop it, and say so, if Amendment 3 removes the need.
- **(b)** The libm ULP risk is accepted as disclosed. If D1, D1b or D5 exactness fails, stop and report; there is no
  workaround.
- **(c)** When the END bundle is named: diff runtime content and measurement files, and verify the 05 copy against 01
  before staging.
- **Coming with Amendment 3:**
  - new `tier_backend.py` and `prepare_bundle.py`, plus `state_rows.py` and `convert_states.py`;
  - `states.pkl` unchanged at 0addf7c0, plus new `states-rows.json` and `.bin`;
  - K4S Amendment 2 re-pins `tier_backend.py` in the K4S Mac manifest.
- **When Amendment 3 lands, the Mac runtime must be re-staged:**
  1. a new runtime from the Amendment 3 commit, with the same 33 + E1 overlays, then `verify_runtime_staging.py`;
  2. re-run `test_measure_tiers` and the new tests on Mac Python 3.12;
  3. a fresh scratch build only if the Rust changes (the counted build is redone by build_tiers.sh anyway, bound to
     the new tiers-pins SHA).

  The current scratch native 0e7213ab is not reused for counting.

### 2026-10-11T22:15:31Z: Amendment 3 adopted (coordinator 22:09Z, 4ccbdd4f); Phase B prep, no timing

- Item 2, the Mac fixture (agreement2000/packets1000), is a **BLOCKER, HELD.** The coordinator's hold was sent at
  about 22:11Z (labelled ~22:16Z).
  - No frozen builder exists, and there are only 1,325 contract rows.
  - The raw captures are only on 03. No reads from 03 by anyone; copies only in an authorized gap between K4S
    rounds.
  - A design worker (clasher-mac-registration-inputs-design-20261011) will propose rules and an owner.
- Item 1: runtime re-staged at 76887b33 (post-f6cebbaa) in `$S/runtime-a3`.
  - Verified: tier_backend 02e2139f, state_rows 3899276b, prepare_bundle a1c59fa3, measure_tiers 6066228b,
    convert_states 7ce30683.
  - `runtime-verify-a3-r1` PASS: 10,764 files, expected manifest a4ae1b8e, same 33 + E1 overlays.
  - Mac Python 3.12: test_measure_tiers 33/33, test_state_rows 21/21, test_prepare_fleet_smoke 2/2. The full suite
    is 91 with the same 20 fleet-only errors.
- Item 3: `a3p_poll_check.py`, a reducer from sealed receipts only.
  - A3-P is applied to the frozen gate-4 variant v* (freeze if freeze_gc passes, else default). Both variants are
    reported.
  - Synthetic tests: correct verdicts; a tampered seal fails.
- Item 4: engine-rs is identical in runtime-a3. The counted build in-session (build_tiers.sh) binds to the new
  tiers-pins SHA automatically; no scratch rebuild is needed.
- Item 5: offline D-pattern RSS measurement running on 05 (core 58, nice 19).
  - The frozen Mac procedure specifies no free-memory or swap threshold; the 24 GiB MemAvailable rule is fleet-only.
    I'm proposing an operator pre-start check to the coordinator.

### 2026-10-11T22:30:46Z: Phase B prep items 1/3/4/5 done; item 2 is the builder's (Amendment 4); disk blocker

- Coordinator 22:27Z (89b28b6d):
  - The Mac fixture is built by `clasher-mac-registration-builder-20261011-r1` under TIERS Amendment 4, not by me.
  - The session will run about 6–6.5 h, so it needs an overnight quiet window.
  - The bundle is about 38.6 GB, with a staging peak of about 72 GiB.
  - Transfer later with `pigz -c | ssh | gunzip`, then SHA-verify on the Mac.
- **Disk:** no external volume; 62.75 GiB free after deleting my superseded scratch (old d651 runtime and build
  target). Regenerable caches (npm cacache and _npx, Homebrew) would bring it to at most about 65.7 GiB, below
  the 72 GiB peak. Sam's T3/canvasdoc worktrees (36 GiB) and the reference emulator SDK/AVD (13 GiB) are not
  touched. A macOS update is staged (MSUPrepareUpdate). Options were reported to the coordinator at 22:31Z.
- **A3-P reducer:** now refuses non-complete seals. Sol r1 REJECT, fixed; Sol r2 APPROVE_WITH_CONDITIONS (the v*
  rule needs a coordinator ruling).
- **D-pattern RSS r2b:** main 0.93 GiB, D6 child 0.78 GiB, concurrent 1.33 GiB (main VmRSS + child peak; Sol r2
  MINOR fixed). Each process is under 1 GiB; perception and MPS are excluded.
- **Memory pre-start check:** proposed (free+inactive+purgeable ≥4 GiB, free swap ≥0.5 GiB, no swapouts during the
  census); awaiting coordinator numbers.
- **HOLD:** no timing and no bundle staging.

### 2026-10-11T22:31:25Z: coordinator rulings (sent 22:30:53Z, labelled 22:33Z) recorded; software-update read

- **Disk:** option (b), no-copy hard-link or APFS-clone staging, goes to the Amendment 4 builder with Sol review.
  At staging time only npm `_cacache`, npm `_npx` and the Homebrew download cache may be freed. Never touch other
  threads' or projects' worktrees.
- **Memory precondition (operator, not a gate):** don't start unless free+inactive+purgeable ≥ 6 GiB, free swap
  ≥ 1 GiB, 0 swapouts during the 5-minute census, and free disk ≥ 10 GiB after staging. Record all readings in
  the session receipt.
- **macOS update** (read at 22:30:58Z):
  - AutomaticallyInstallMacOSUpdates=1, AutomaticDownload=1, Critical/ConfigData=1, App Store AutoUpdate=0.
  - macOS 27.0.1 is staged.
  - There is no passwordless sudo, so a Sol computer-use step will turn auto-install off for the window and
    restore it afterwards. Record both changes.
- **Sleep:** pmset sleep=1, prevented by Sam's `caffeinate -is` (PID 98902). Plan: run the session under its
  own `caffeinate -i`, pending coordinator objection.
- **Open rulings:** the A3-P v* combination rule, and the caffeinate wrapper.
- **HOLD:** no timing and no staging.

### 2026-10-11T22:32:19Z: coordinator rulings on the 22:35Z report

1. **A3-P v\* confirmed:** A3-P is applied to the frozen gate-4 variant (freeze if freeze_gc passes, else
   default). The existential reading is rejected. `a3p_poll_check.py` already implements this; no change.
2. **Session `caffeinate -i` approved:** operational only; record it in the session receipt.
3. **Software update:** the coordinator routes a Sol computer-use step at session time (turn off "Install macOS
   updates" and "Download new updates" for the window, then restore). The operator re-reads the
   `com.apple.SoftwareUpdate` prefs before and after and records them; the operator changes nothing itself.

**Phase B start checklist:**
- **Coordinator go:** pooled END reference, END bundle and registration packet named, Amendment 4 fixture with
  no-copy staging, quiet window and update step.
- **Re-verify the runtime** against the named END bundle: content diff (allowed: scripts.rs plus the 12 exit-r3
  scripts) and measurement-file equality.
- **Free the three caches** only if needed, then stage via the builder's reviewed no-copy step with SHA
  verification.
- **Memory precondition:** free+inactive+purgeable ≥ 6 GiB, free swap ≥ 1 GiB, 0 swapouts during the census,
  disk ≥ 10 GiB after staging.
- **Census:** must pass under the frozen census, otherwise report the top consumers and don't start.
- **Environment:** PYTHONPATH import-path addition; nice 10; OMP/OPENBLAS/MKL=1; run under `caffeinate -i`.
- **Run** the README locked heredoc (prepare_bundle --state-rows, build_tiers.sh, measure_tiers.py).
- **Afterwards:** A3-P, classify_failure if needed, commit the Mac summary receipt, restore update prefs (via
  Sol) and record them.
