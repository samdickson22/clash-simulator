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
