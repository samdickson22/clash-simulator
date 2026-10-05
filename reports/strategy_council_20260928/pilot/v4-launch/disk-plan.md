# Council pilot v4: disk plan (list only, nothing deleted)

Measured 2026-09-29 around 08:00 UTC, while Tier A v4 was running, using `nice -n 15 du`. Free space on `/System/Volumes/Data` was **14 GiB** (97% used). Swap was 18.9 of 20 GB used, which lives in `/System/Volumes/VM` on the same APFS container.

## 1. Space per run

A "run" here is one per-seed coordinator (one output dir, both arms). Checkpoint size comes from the council model. I built it from the snapshot and counted **2,604,979 parameters**: 10.4 MB of fp32 weights, 31.3 MB with the AdamW moments, so about **32 MB per checkpoint**. The warm-start corpus figures are estimates; they have not been measured.

| Item | Through the 1M diagnostic | Through 5M (full pilot) | Basis |
| --- | --- | --- | --- |
| PPO checkpoints, per arm | ~0.25 GB (≈5 periodic + boundary + 1M copy) | ~1.0 GB (≈24 periodic + boundaries + 100k/1M/5M copies) | `save_every=200` updates × 8 envs × 128 = 204,800 decisions per save; the trainer never prunes |
| PPO checkpoints, both arms | ~0.5 GB | ~2.0 GB | |
| Warm start, retained (game shards + compressed `corpus.npz`) | 2–5 GB | 2–5 GB | ~500k rows; entity features 128×32 fp32 before padding trim; compressed NPZ (unmeasured) |
| Warm start, transient merge memmaps (`initialization/.../merge-*`) | +5–12 GB peak | same | uncompressed `open_memmap` of every field in the same dir; deleted after the merge |
| Evaluation JSON, logs, monitor, budget ledger | <0.1 GB | ~0.1–0.2 GB | 384 diagnostic games; 2,832 final games per seed |
| **Retained per run** | **~2.5–5.5 GB** | **~4–7 GB** | |
| **Peak per run during the warm-start merge** | **+5–12 GB** | | |

**Total for 3 seeds:** about 8–17 GB retained at 1M and about 12–21 GB at 5M. Add one merge peak of 5–12 GB if the seeds are staggered so that no two merges overlap (launch the next seed after the previous seed's warm start ends). Preflight temp dirs are a few MB and are deleted.

**Other growth before the pilot starts:** the Tier A v4 attempt dir is 0.39 GB now. v3 reached 3.7 GB, so budget about +3.5 GB.

**Need:** at least **35 GiB free** before starting seed 2901, and at least 25 GiB free before each later seed. `launch.sh` refuses to start below `MIN_FREE_GB` (default 20). Raise it with `MIN_FREE_GB=35` for the first launch.

### What frees space without deleting anything

- **Swap (up to ~19 GB):** swap is released once the 8 Tier A emulators (about 3 GB RSS each) are shut down. Check with `sysctl vm.swapusage` and `df -h /System/Volumes/Data`.
- **`/tmp/android-sam` (1.6 GB):** per-boot `-read-only` qcow2 overlays, 8 × 209 MB. The emulator normally removes them on a clean exit.

Once both are back, free space should be about 30–34 GiB, which is enough for the 1M phase of all three seeds. The full 5M pilot, with one merge peak, is tight without at least one of the cleanups below.

## 2. Cleanup candidates, ranked (nothing deleted; Sam approves any removal)

Status key: **R** = reproducible (can be recreated from source or download), **E** = evidence (referenced by a ledger, declaration, report or decision; keep or archive off-machine), **U** = unknown (ask Sam).

| # | Size | Path | Status | Safety for the pilot | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | ~19 GB | swap (`/System/Volumes/VM`) | R | automatic | Returns when the emulators stop. No action needed. |
| 2 | 18.5 GB | `datasets/external/tv_royale_youtube_clocked_rotate_20260826` | R* | safe (not used by the pilot) | Raw YouTube downloads for the legacy TV-Royale imitation line. Derived set `datasets/derived/tv_royale_youtube_clocked_rotate_20260826` (0.43 GB) exists. *Re-download is not guaranteed if videos disappear. Best single candidate if archived first. |
| 3 | 16.3 GB | `~/.android/avd/clasher_current_oracle.avd` (6.4), `clasher_current.avd` (6.3), `clasher_play_oracle.avd` (3.6) | U | safe for the pilot | Legacy AVDs last written Aug 5–6. Tier A uses `clasher_reference_api35` under `~/.cache/clasher-native-reference/avd` instead. They may hold installed game state or logins. Ask Sam. |
| 4 | 15 GB | `~/.colima` | U | safe for the pilot | Docker/colima VM disk, outside this project. Ask Sam. |
| 5 | 7.3 / 7.0 / 5.2 / 4.3 / 0.8 GB | `artifacts/worktree-data/clasher-simulator-fidelity-20260913/reports/calibration_acceptance_2026091{6_v3,7_v4,8_v5}`, `..._20260921_v6`, `..._20260922_v7` | E | do not delete | Historical calibration acceptance attempts (v7 failed). Archive off-machine at most. |
| 6 | 6.2 GB | `artifacts/.../calibration_development_20260915` | **E (live)** | **never delete** | Contains `native-root-registry.sqlite`, which is listed in the v4 declaration's `historical_registries` (freshness checks). |
| 7 | 5.7 GB | `datasets/external/tv_royale_youtube_persistent_batch_v1_20260825` | R* | safe | Same kind as #2. |
| 8 | 5.3 + 2.4 GB | `~/.cache/clasher-native-reference/android-sdk`, `ndk-r27d-verified` | R | not while emulators or native tooling may be needed (Tier B, level probes) | SDK and NDK re-downloadable (NDK has a download receipt). The AVD (4.8 GB) and APKs (`nulls-…apk` 0.76 GB, `probe-apk-build-20260914` 0.76 GB) are **E**: native attestation and Tier B depend on them. `apk-probe-stage-1e505767` (0.93 GB) is R (unpacked from the APK). |
| 9 | 4.2 GB | `datasets/external/Clash-Royale-Replay-Dataset` | R | safe | Public third-party dataset. |
| 10 | 4.0 GB (132 dirs) | `checkpoints/` | U/E | safe for the pilot | Legacy policy lines (hog26_*, fresh_*, tv_*). Some are cited as champions or anchors in reports. Thinning intermediate `policy_v2_update_*` files while keeping finals would need a per-line audit. Largest: `tv_raw1000_completehand_v2_update40_headonly_seed1046901` (0.61 GB). |
| 11 | 3.7 GB | `reports/strategy_council_20260928/m0/readiness/tier-a-fresh-v3` | E | do not delete | Failed attempt, but the ledger holds its 1,024 claims and results, plus `operational-failure.json`. v1 (0.42 GB) and v2 (0.27 GB) are also E. |
| 12 | 3.1 + 0.9 GB | `artifacts/worktree-data/clasher-event-policy/{reports,datasets}` | E/U | safe for the pilot | Event-policy research evidence preserved by the consolidation. |
| 13 | 2.5 GB | `datasets/derived/*` | R | safe | Derived from `datasets/external` by scripts, but re-deriving is slow. |
| 14 | ~2.8 GB | other legacy `reports/*` (e.g. `persistent_batch_v1` 0.75, `v7_recovery_20260928` 0.24, `l40s4_pilot_20260824` 0.23, `evaluations` 0.23) | E/U | safe for the pilot | Mostly experiment evidence. |
| 15 | 1.6 GB | `/tmp/android-sam/emulator-*.qcow2` and crash db | R | only after **all** emulators have exited | Per-boot scratch overlays. Anything left behind after Tier A is garbage. |
| 16 | 1.3 / 0.76 / 0.54 / 0.40 / 0.35 / 0.27 / 0.20 GB | `datasets/external/{tv_royale_parquet_download, tv_royale_raw_validation, tv_royale_youtube_l40s_expansion_20260824, tv_royale_raw_pilot, tv_royale_youtube_fullmatch_l40s_pilot_20260824, CS541-…, KataCR}` | R | safe | Downloads. |
| 17 | ~3 GB | `~/Library/Caches/{Codex,pnpm,com.openai.codex,colima,…}`, `~/.npm` (2.0), `~/.cache/uv` (1.2) | R | safe (but **not** `~/.cache/uv` while anyone might `uv sync`; the pilot must not) | Tool caches outside the project. |
| 18 | 0.13 GB (572 dirs) | `__pycache__` in the repo (`tests/` 21 MB, `scripts/` 6 MB, `src/…`) | R | safe; tiny | Leave `.venv/**/__pycache__` and the snapshot's numba cache (`native-final-v4/src/clasher/__pycache__`, not hashed) alone. |
| — | 0.4 GB → ~4 GB | `m0/readiness/tier-a-fresh-v4` (prefixes, branches-*) and `native-final-v4/` | **E (live)** | **never move or delete during the pilot** | `require_pilot_admission` re-hashes the captures, all 1,024 branch artifacts and the calibration receipt at their absolute paths before every warm start, training job and evaluation command. |
| 19 | 0.10 GB | `m0/runtime-snapshots/native-{development-v1,final-v1,v2,v3,v3-staging}` | E | do not delete | Tiny, and they back earlier ledger declarations. |
| — | 8.4 GB | `.git` | — | not a candidate | `git gc` or pruning is out of scope (no reset/clean). |

**Best combination if Sam approves:** archive then remove #2 and #7 (about 24 GB of raw legacy video), and/or #3 (about 16 GB of legacy AVDs). Either one alone covers the full 5M pilot plus merge peaks with margin. Never touch #6, #11 or anything the v4 ledger or declaration references.
