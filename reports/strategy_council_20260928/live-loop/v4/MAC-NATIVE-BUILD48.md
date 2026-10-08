# Mac native build48 verification

Completed 2026-10-08T18:21:57.704172+00:00. **PASS**: build48 native installed only under `/Users/sam/Desktop/code/clasher-runtime-v4`; runtime tests **36/36**, including both formerly failing zero-delay S6 comparisons.

- Mac native SHA256: `9263a8f72d18c202cf490e2e3f8fec214243d51ef91104990fb049458f831180`.
- Toolchain: `rustc 1.97.1 (8bab26f4f 2026-07-14)`, aarch64-apple-darwin. Existing toolchain; no installation or sudo. Build followed `engine-rs/build.sh`, release/extension-module, one Cargo job, nice 10; 41.24 seconds.
- Source: git `main` at `326b2a86f1ae9e5ea38b95b8fcfe5d6cd53a4e99` from 127x05. **66/66 build48 source hashes matched** before and after verification. Complete hashes are in `MAC-NATIVE-BUILD48.json` and `mac-native-build48/build-identity.json`. Build48 pins SHA256: `10c6a5e0514b4a5a310b2bea691cc5903969896165327fb3a6bf838e919e5055`. The fleet Linux native SHA is platform-specific and is not the Mac binary pin.
- `NativeScripts.rollout` now exposes `full_rng=False`.

## Verification

| Check | Result |
|---|---|
| P16 admitted identity | **12/12**, zero mismatches |
| C56 canonical identity | **7/7**, zero mismatches |
| Random admitted identity | **24/24**, zero mismatches |
| Recorded admitted identity | **8/8**, zero mismatches; all fresh replays, merged through original checker |
| Stage 5 replay | **200/200 roots**, 3,993 candidates, exact admitted action/trace hashes; 180.01 seconds |
| Stage 6 regressions | **69/69** methods, including build48 holdout reductions; 397.176 seconds |
| Full isolated runtime suite | **36/36**; 26.516 seconds |

Verification used at most two nice-10 lanes, with BLAS threads limited to one. Every gate process checked the loaded native path and SHA. The four historical identity drivers retain their existing Python/admitted-baseline semantics; Stage 5 and Stage 6 explicitly compare native behavior. Qualified gate drivers/fixtures came from the sealed build48 Linux isolated tree; the input ledger is `mac-native-build48/qualified-gate-source-pins.json`. Stage 5's adapter only relocates its native-path assertion from `stage6/native` to this runtime's `engine-rs`; its algorithm and baseline were unchanged.

## Latency smoke

The new binary completed **58 first-attempt mock submissions** across 1 frozen-train replay match(es), on MPS with configured total delay **27 ticks**, without emulator/renderer actions. The run loaded the new native SHA in every provenance record. No audit errors; 0 search deadline overruns. Processed 99.912% at 19.982 FPS.

| Frame to first-attempt submission completion, ms | Samples | p50 | p95 | p99 |
|---|---:|---:|---:|---:|
| New build48 smoke | 58 | 187.76 | 264.38 | 269.20 |
| Historical same replay match(es) | 58 | 173.87 | 291.93 | 341.52 |
| Historical full Mac calibration | 228 | 186.06 | 284.92 | 333.95 |

Against the same historical match(es), smoke p50 changed +13.89 ms and p99 -72.32 ms. Active search p50/p99: 56.60/101.48 ms now versus 54.97/101.82 ms historically. Smoke uses the configured 27-tick total delay; original 228-submission calibration used provisional 28 ticks. Short smoke with a different sample count and scheduling; not a controlled binary-only speedup or full latency requalification. Original calibration and 27-tick timing profile were retained. The smoke is below the full-suite sample requirement; no full latency or production qualification is claimed.

## Isolation and receipts

The original runtime `engine-rs` symlink was preserved as `engine-rs.pre-build48-link` and replaced by a real directory. Symlinked verification-report trees were similarly preserved and copied into the isolated root. Prior differing gate files were retained under `mac-native-build48/prior-gates`. The shared `.venv` was used read-only; no packages were installed.

Postflight checked **3,850 live-checkout tracked file hashes** and **42,508 engine-rs/.venv metadata entries**: zero changes. Live native remains `3ae315d98fafd01cf2c0651cde05b6e9f1b6105adbbf97c7f685565fca61aa7a`. No Python engine/gamedata edits, emulator/renderer/APK actions, data deletion, or git commits.

An initial test-wrapper attempt lacked the macOS multiprocessing `__main__` guard and was excluded. Its verified process tree was terminated, the wrapper fixed, and all 36 tests rerun successfully. Initial recorded attempts stopped before game execution because the frozen pilot checkpoint was absent. The pilot tree was isolated, the exact checkpoint copied from the qualified fleet tree (SHA256 `c7aae667e45073bfab442b9d36a4b2c45bca7321df442d8ebfac419e191dc522`), and all eight recorded games replayed fresh. Failed-attempt evidence is retained.

Primary receipt: `MAC-NATIVE-BUILD48.json`. Build, source/input hashes, test/identity logs, isolation audit, original latency receipt, smoke raw logs/provenance, and comparison: `mac-native-build48/`. `runtime-mac-latency.json` now records both the historical measurement's original native pin and the installed build48 pin, the passing tests, and the separate smoke. This report, JSON receipt, updated latency receipt, and compact evidence are mirrored to 127x05.

Fleet build48 qualified the private native core. This update does not change the existing full Stage 6/S122 admission blocker for the ThreeMusketeers Python controller, or the separate formal-v4/emulator-on prerequisites.
