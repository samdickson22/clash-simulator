# Phase A independent reviews (2026-10-11)

Both reviews were requested by the operator under the coordinator's ~20:37Z split: Sol for code, Opus for the
topology and provenance. Neither reviewer edited or committed anything.

## GPT-6.1-Sol (high): staging code, APPROVE_WITH_CONDITIONS

Task `mac-e4-r1-sol-staging-review-r1`, completed about 20:47Z. Sol reran the verifier and reproduced PASS (10,611
files). The compiled Rust sources and Cargo.lock match the runtime-pin-r2 `native_source` provenance of 44874fd6;
the only mismatch is the disclosed non-compiled `e1-source-manifest.json`. Ancestry, `measure_tiers.py` 6066228b,
the 33 overlays and the 11 qualified sources were all checked.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | MAJOR | `verify_runtime_staging.py` ignored symlinks | Fixed: `--mac-symlinks` checks paths and targets. Negative test fails closed. |
| 2 | MINOR | Duplicate listing paths overwrote each other | Fixed: duplicate, absolute and `..` paths are refused. Negative test raises. |
| 3 | MINOR | engine-rs was updated, not replaced | Fixed: the subtree is replaced by the stager output. |
| 4 | MINOR | Perception preflight lacked `set_num_interop_threads(1)` and per-frame flush | Fixed in script r2. Not re-run because of the Mac timing hold. |
| 5 | MINOR | FPS window excluded the boundaries | Fixed: fixed post-warmup window. Sol's recomputation of the r1 rows is 20.0002 FPS. |
| 6 | MINOR | `runtime-staging.json` said all 17 deviations equal smoke | Fixed: 16 equal smoke; `scripts.rs` differs by design. |
| 7 | NOTE | Build or import PASS is not D1 exactness | Agreed: the counted build and all gates remain. |

The re-verification receipt is `../phase-a-preflight-20261011/runtime-verify-r2.json`: PASS, expected manifest
cbe898966750355fdb4e9aa6e9a9d0349851ae4c901815211fbfe94685f4568b, with the single symlink
`visualize_battle.py -> examples/visualize_battle.py`.

## Claude Opus 5.5 (high): topology and overlay provenance, APPROVE_WITH_CONDITIONS (both parts)

Task `mac-e4-r1-opus-topology-review-r1`, completed about 20:49Z.

**A. Topology E=[0-3], P=[4-11] is established.**
- ioreg `logical-cpu-id` and `cluster-type` agree with the e/p-core counts and with sysctl perflevel.
- The background-QoS spin loads only E 0–3 (about +0.93 core), so Mach index i equals logical-cpu-id i.
- 8–11 are P by ioreg and by complement. The frozen code uses only the P/E partition.
- Do not map by node name: the nodes are named cpu10–13 but have logical-cpu-id 8–11.
- Condition: mark the topology reviewed before the bundle is prepared.
- **Done 2026-10-11T20:50:00Z.** The Mac `inputs/topology.json` is now sha256
  2b2ec325629db5bb902b8d868ba037219b59cf53312d781408713ea35236f2f6, made read-only, with a `node_name_note`. It is
  not to be edited again.

**B. The overlay provenance is sound and the most defensible reconstruction.** Compared with T1's END runtime on 05
(`t1-20261010-r1/end-bundle-preparation-r1/runtime`, 3,775 pins):
- 13 files differ and 1 is missing:
  - `engine-rs/src/scripts.rs` is different by design (the Mac compiles the E1 source; END runs the provenance .so);
  - 12 non-importable `exit-r3` operations scripts differ;
  - `visualize_battle.py` is missing; it is untracked and never imported.
- The runtime-pin `files` entry for `scripts.rs` (fd6f32fe) predates W-screen8 and is stale. The compile source is
  `native_source` 127c6980, and `tier_backend` calls `rollout_e1`.
- `search-noise-s6/delay.py` differs from the pin only in a `wait_screen8` branch, which is unused (`wait_screen8=False`).
- The extra Mac files do not shadow any module.

Findings that carry into Phase B:
- **HIGH:** END needed `PYTHONPATH += runtime/imitation/evaluation/runtime_dependencies:runtime/reports/strategy_council_20260928/imitation`
  before `states.pkl` would unpickle (`own_cycle`; coordinator position 7987; `END-C3-preflight-01-20261011T2032Z.json`).
  The Mac must use the same environment addition, unless Amendment 3's loader makes it unnecessary.
- **MEDIUM:** the engine's f64 `exp`/`sin`/`cos` go through the platform libm, so glibc and macOS may differ by
  1 ulp. This is not removable by provenance. D1/D1b/D5 exactness fail closed if it happens.
  - Partial prior evidence: the 2026-10-08 Mac build48 passed the c56, p16 and random combat-identity gates against
    the admitted Linux baselines.
- **When the END bundle is named:**
  - diff shared runtime names by content; the expected differences are exactly `scripts.rs` plus the 12 `exit-r3`
    scripts;
  - require the measurement files to be identical;
  - list any END-only names;
  - compare the Python, torch and numpy versions and the PYTHONPATH;
  - check that the 05 copy equals 01's (runtime-pins SHA 5f981696).
- Never stage from the shared 05 working tree: its `HEAD` `measure_tiers.py` is 5d7de8e3.
