# E4 guard race fix: impact inventory (draft, 2026-10-12)

Prepared on 127x05 on branch `e4-guard-race-fix-20261012`, cut from origin/main 92acdf02 and rebased onto 5cc4c5bc. This is a **draft; nothing is adopted, staged or re-pinned.**
- No SSH to any host.
- No reads of the T1 job tree, except `END-08r2-DIAGNOSIS-r1.md`, which is also committed as `reports/explore/t1/receipts/END-08r2-DIAGNOSIS-r1.md`, ec6eb568.
- No outcome access.

All SHA-256 values are of the file bytes at origin/main 5cc4c5bc. "Commit" is the last commit touching the path.

## 0. The change

| File | Before | After (this branch) |
| --- | --- | --- |
| `…/mac-e4-package/e4v3/fleet_validity.py` | `94d0e7f2c20bfc139f5d95ccefb375f52293a06c2c78bee84e9442fc62bcb0ae` | `eae5db3f6feb76a1ad506738c88cc08686757a87891dffb47e0c5bd57d11ddb6` |
| `…/mac-e4-package/e4v3/tests/test_guard_census_race.py` | (new) | test only; not in any `measurement_files` inventory |
| `…/live-loop/v4/e4-guard-race-fix-20261012/{live_race.py,results.json}` | (new) | test receipt, kept outside `e4v3/` so the e4v3 runtime file list changes only by the test |

**Which inventories include the file.**
- `release_reference.py:240-241` builds the E4 measurement inventory from the `.py`/`.sh` files plus `spec-pins.json` directly under `e4v3/`. `tests/` is not included.
- So in every `measurement_files` / `runtime_files` / `measurement_source` inventory, **exactly one entry changes: `fleet_validity.py`.** The other 17 entries stay byte-identical, including the five A3 code SHAs, native 44874fd6, the guard freeze `FROZEN-T1.json` 24817e16 and the nine T1 guard modules.

**What the change does.** `ReportingGuard.__call__` re-derives ownership on the census snapshot with `owned_tree` and the same `known` start_ticks, then drops rows from `foreign_compute` / `foreign_active` that are now owned. A pid seen before exec (cmdline equal to its parent's) may re-pin its OP-3 identity once, at exec, and only if pid, pgid, start_ticks and uid are unchanged. No rule, threshold or reason code changes.

## 1. Who executes `fleet_validity.py`, and who only pins its bytes

| Consumer | Executes `ReportingGuard`? | Exposed to the race? |
| --- | --- | --- |
| E4 fleet reference (`fleet_reference.py:237-239`, monitor process) | yes | **yes**: workers are spawned after admit (`fleet_reference.py:125-130`) |
| E4 pool (`fleet_pool.py:90`), `classify_failure.py:15` | no; `classify_attempt` / `validate_*` only | no (functions unchanged) |
| E4 Mac session (`measure_tiers.py`) | no; doesn't import it | no; byte pin only (`tier_backend.validate_bundle:458` verifies `measurement_files`) |
| **K4S END reference** (`reports/explore/k4s-confirm/end_reference.py` 5cb4751e, `:295,334,361-363`) | **yes**, through the frozen `fleet_reference.reference_monitor` | **yes: same pattern.** It does `checkpoint("admit")` and then starts `K4SFleetBackground` with 10 spawn workers (`end_background.py:143-147`). |
| K4S END pool (`end_pool.py` 069c22e7, `:65,214,296,343-347`) | no; `classify_attempt` / `validate_*` | no |
| **K4S reporting now running on 03/04** (`supervise.py` a25c9076, `run.py`) | **no** | **no** (see §4) |

## 2. Pins, manifests and receipts that bind `fleet_validity.py` 94d0e7f2

The searches were `git grep 94d0e7f2` and `git grep fleet_validity` over origin/main. Each row below is either a hit or a container that binds one by SHA.

### 2a. T1 END bundles and A3 staging (E4 reference)

| Path | SHA-256 (commit) | Binding | Needed under the fix |
| --- | --- | --- | --- |
| `reports/explore/t1/receipts/END-A3-manifest-01-f6cebbaa.json` | `bd9804c32a6ba661…` (07ed3f6d) | `measurement_files` and `files` both carry 94d0e7f2 (lines 87, 1704) | **New END-A5 manifest for 01**, regenerated from the fix commit; only the fleet_validity entries change |
| `reports/explore/t1/receipts/END-A3-manifest-08-f6cebbaa.json` | `1bd8a4c734e79a61…` (07ed3f6d) | same (lines 88, 1706) | **New END-A5 manifest for 08** |
| Staged bundles: 01 `tiers-pins` `69b76fb1…`; 08 `cba1bc74…` | named in `END-reference-launch-receipt-01-r1.json` 382492f1 (57abcd49), `…-08-r2.json` f0e91ad1 (229de5cb), and their launch-preparation receipts | `--manifest-sha256` in the frozen argv; the bundle `measurement_files` include 94d0e7f2 | **New bundle tiers-pins, new argv pins, new V2 prepare proofs, repeat C3 preflights** on both hosts |
| Host runtime `…/t1-20261010-r1/end-a3-f6cebbaa-0108-r1/runtime` (01 and 08), and the `END-A3-package-f6cebbaa.tar` that `END-exit-push-REVIEW-r2.md` refers to | host-side, not inspected (C5, no SSH) | holds the 94d0e7f2 bytes; `validate_bundle` checks them at start and end | **Fresh A5 staging root** next to it, e.g. `end-a5-<fix8>-0108-r1`. The A3 runtime is not modified (it's the evidence for old attempts) |
| `reports/explore/t1/receipts/END-preparation-interface-20261011T1935Z.json` | `d4e086ae86867bef…` (d651b52c) | `measurement_source` lists 94d0e7f2 (line 49) | Historical record of the A3 interface. Superseded by a new A5 interface/health receipt; not edited |
| `reports/explore/t1/receipts/END-exit-push-REVIEW-r2.md` / `-r3.md` | `ec8d1a41dd7432bd…` (47491548) / `727486747e0ace0a…` (e6c73498) | review records quote E4 bytes incl. `fleet_validity.py 94d0e7f2` as staged | **No re-review of the wrapper.** `end_exit_push.sh` 0a87166f, `detach.sh`, verifier 753722c9 and `FROZEN-T1.json` are not E4 bytes and don't change. The "E4 bytes" statement in r2/r3 Check 5 is superseded for one file; the A5 staging receipt records the new set |
| `reports/explore/t1/receipts/END-copier-review-r1-20261012T0039Z.json` | `a4b34cecf6c843b3…` (9fee6c95) | file name only | none (historical) |
| `reports/explore/t1/receipts/END-reference-validity-STOP-08-r2-20261012T0331Z.json` | `8958eb5c7159b7b4…` (2444d4bc) | 08 r2 STOP evidence | none; it is cited in the A5 disclosure |
| `reports/explore/t1/receipts/amendment1-release-c14-tests.json` | `2fa1b1e33bf9790f…` (11dcb034) | file name in test listing | none |
| `reports/explore/t1/receipts/reference-attempt-roots-0108.json` | `405f35dc9ecd9ff8…` (3c811584), pinned by `FROZEN-T1.json` 24817e16 line 164 | the release-side roots must equal the descriptor's attempts (`release_reference.py:114-139`) | **Not edited.** A5 needs a **new** roots declaration for fixed-code attempts (§3). `FROZEN-T1.json` stays as is: its pin of the old file remains true, and `ReportingGuard` reads only the guard modules and OP-5/OP-6 entries from it |
| `reports/explore/t1/end_exit_push.sh` | `0a87166f…` (b5ea3ed1) | **constrains the job parent** to `$base` or `$base/fleet-end-attempts-0108/$host` (`:14-17`) | No change, if A5 attempts keep host-side paths in the existing host root under new basenames (§3) |
| `reports/explore/t1/release_reference.py` / `check_reference.py` | `f8b61c603a2680fe…` / `c848baa2f6748017…` (11dcb034) | read `measurement_source` and `identity.measurement_files` at release; they don't pin 94d0e7f2 | no code change. The A5 release evidence names the A5 commit and the A5 roots binding |

### 2b. TIERS preregistration records

| Path | SHA-256 (commit) | Binding | Needed |
| --- | --- | --- | --- |
| `reports/strategy_council_20260928/live-loop/v4/PREREG-SEARCH-TIERS-AMENDMENT-3-20261011.json` | `3e5627cb1861dc05…` (f6cebbaa) | `unchanged_files` lists fleet_validity 94d0e7f2 (line 264) | Not edited. **TIERS Amendment 5** (draft alongside) supersedes this one entry |
| `…/PREREG-SEARCH-TIERS-AMENDMENT-4-20261011.json` | `1428633affe95333…` (7d7a102e) | states "No e4v3 file changes", by reference to the A3 set | A5 notes that A4's helper constant (§2d) needs an erratum |
| `…/E4-END-INDEPENDENT-REVIEW-r1.md` | `9da980e18fdc88e2…` (732ea9bd) | notes that the OP-7 alternative "touches K4S-pinned fleet_validity.py (94d0e7f2)" | none (historical) |
| `…/e4v3/receipts/op5-op6-unit-20261010-r1/unit-tests.json` and the other e4v3 `receipts/*/unit-tests.json` / `syntax-checks.json` | historical test receipts | test runs over 94d0e7f2 | none; the A5 test receipt is new (§5) |

### 2c. K4S (FROZEN, manifests)

| Path | SHA-256 (commit) | Binding | Needed |
| --- | --- | --- | --- |
| `reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json` | **`c1fb1e9acb71a69d…`** (f231fbcb, K4S Amendment 2) | pins `…/e4v3/fleet_validity.py` 94d0e7f2 (line 96). Since A2, K4S END-JOB, the END pool descriptor, every `end_reference --k4s-manifest-sha256` and the Mac K4S sessions must name c1fb1e9a | **K4S companion re-pin** (a K4S Amendment 3: c1fb1e9a → new, one leaf), with Sol review. **Needed before any K4S END reference or Mac K4S session runs on fixed bytes.** Not needed for the running K4S reporting |
| Earlier versions of the same file: **d89cab16** (391d2006), 8bb20a75 (45f32c0f), 781d25ba (247ef6d4), 4c25d454 (962ecce2) | all pin fleet_validity 94d0e7f2 | **d89cab16** is the fleet manifest that K4S Amendment 2 kept for the fleet runtime | **Not re-pinned.** The fleet reporting runtime never imports `fleet_validity` (§4). Same precedent as A2: "fleet keeps d89cab16; END/Mac name c1fb1e9a" |
| `reports/explore/k4s-confirm/run-r1/oa1/FROZEN-K4S.json` | **`416f6e51e32e1900…`** (6ac7b641) | binds `K4S-MAC-MANIFEST.json` d89cab16 (line 83), so it binds 94d0e7f2 indirectly. It doesn't pin any e4v3 file directly (`re_pins_required.frozen_k4s.e4v3_files_pinned=false` in A3) | **No change.** It is the frozen job manifest of the running reporting (`K4S-LAUNCH-ADDENDUM.json`, `REPORTING-AUTHORIZATION-v2.json`) |
| `reports/explore/k4s-confirm/DELTA-MANIFEST.json` | `34eca2b74c034564…` (391d2006) | `k4s_sha256` d89cab16 (line 448) | no change |
| `reports/explore/k4s-confirm/mac/build_manifest.py` | `2e255fb939c2b172…` (f231fbcb) | lists `fleet_validity.py` among the frozen e4v3 helpers (line 24) | no code change; it is re-run with `--freeze` for the K4S re-pin |
| `reports/explore/k4s-confirm/end_pool.py` / `end_reference.py` / `end_background.py` | `069c22e7…` / `5cb4751e…` / `a872bd2d…` | `FROZEN_HELPERS` includes fleet_validity, verified against the K4S manifest | no code change. **The K4S END reference inherits the race** (§1). Whatever r3 does, the K4S END needs either this fix (via the K4S re-pin) or its own ruling before it runs |

### 2d. Mac / A4 registration and the Mac E4 session

| Path | SHA-256 (commit) | Binding | Needed |
| --- | --- | --- | --- |
| `reports/explore/mac-registration/stage_nocopy.py` | **`96abd8474d6410d6…`** (94df513d, A4 adopted; helper approved COORDINATOR 684195b3) | hard-coded `FROZEN_MEASUREMENT_FILES["fleet_validity.py"] = 94d0e7f2…` (line 57), described as "END-A3 measurement_files" | **One-constant change → new helper SHA. Needs an A4 erratum and a narrow Sol diff review** before the Mac is staged with fixed bytes. Otherwise the helper refuses a fixed runtime, or verifies a stale one |
| `reports/explore/mac-e4-session/receipts/phase-b-prep-20261011/runtime-verify-a3-r1.json` | `1a2c16167aa046dc…` (f56c08ff) | Mac runtime-a3 verified as a full tree at 76887b33 (manifest a4ae1b8e, 10764 files), so its e4v3 copy holds 94d0e7f2 | Mac runtime **re-staging or a one-file overlay, plus re-verify** under the fix commit. Mac timing doesn't execute the guard, but `validate_bundle` compares `measurement_files`, and PC2 wants one reviewed inventory. Mac is on **HOLD** (no staging or timing until go), so nothing in progress is touched |
| `reports/explore/mac-e4-session/receipts/phase-a-preflight-20261011/preflight/unit-tests-r1.log` | historical | test log naming the file | none |
| Mac K4S session | `K4S-MAC-MANIFEST` c1fb1e9a | see §2c | follows the K4S re-pin |

### 2e. Release production checks

| Item | Source | Needed |
| --- | --- | --- |
| **PC2** (reviewed E4 source) | `reports/explore/t1/RELEASE-PRODUCTION-CHECKS-20261010.md` ff0b7afe (24105954): "measurement source inventory must equal the final independently reviewed E4 commit, including END and pooling code" | The "final independently reviewed E4 commit" becomes the **fix commit after Sol APPROVE**. The PC2 reviewer must check the A5 attempts' `measurement_files` against that commit: 17 entries unchanged plus fleet_validity eae5db3f… |
| **PC1** (every original attempt) | same file; declaration `reference-attempt-roots-0108.json` | The reading becomes: host-root listing = A5 descriptor ⊎ old-code disclosure ⊎ RF1 exempt disclosure. This is a declared interpretation for the PC1 reviewer (§3) |
| `release_reference.prerequisites` | `:194-198, 242-247, 265-267` | **The descriptor may hold only fixed-code attempts:** `fleet_pool.py:107` runs `verify_files` on every attempt, including failed ones, against the pool's own e4v3 directory, and `:169-176` makes runtime and measurement files equal across hosts. So the old-code attempts (01 r1, 08 r2, 08 r3) **cannot** appear in an A5 descriptor |
| **R-ord post-exit "five A3 code SHAs" check** | COORDINATOR R-ord (b21b5a20 section, line 2300); `END-A6-INDEPENDENT-REVIEW-r1.md` 9d959d9f lines 28-33: measure_tiers 6066228b, fleet_reference c767a6e0, tier_backend 02e2139f, state_rows 3899276b, prepare_bundle a1c59fa3 | **fleet_validity is not one of the five**, so as written the check can't tell an old-code run from a fixed-code run. Under A5 it becomes **six code SHAs**: the five plus fleet_validity `eae5db3f…`. Native 44874fd6, 11 slots, warmup 300 and `poolable==true` are unchanged |

### 2f. Anything else

- **`classify_failure.py`** 9ab2f038 imports `classify_attempt`, which is unchanged, so no code change. Its bytes are in the inventory and don't change.
- **A6** (01, `END-A6-launch-receipt-01-20261012T011336Z.json` 45bd9dc3; verification `…-r5-20261012T0230Z.json` 797e02f1; seal da9230ad) ran on 94d0e7f2 and passed by about 0–20 ms (diagnosis §1). It is outside every root and never poolable, so it doesn't need re-running. It is disclosed in A5. Whether the reviewers want a fixed-code smoke in its place is an open item (A5 §6).
- **T1 guard freeze** (`FROZEN-T1.json` 24817e16 and the nine guard modules) doesn't pin any e4v3 file, so no change and no T1 re-freeze.
- **The `end-evidence`, plan, corpus, states, seeds, native, policy and calibration** inputs are unaffected.

## 3. Attempt roots with the frozen wrapper (no wrapper change)

`end_exit_push.sh` 0a87166f exits 90 unless the job parent is `$base` or `$base/fleet-end-attempts-0108/$host`. A new *host-side* root would therefore need a wrapper change and re-review. The cheapest equivalent is:

- **Host side:**
  - A5 attempts live in the existing host root under new basenames: `end-reference-<host>-0a87166f-a5-r1` and, if a technical repeat is needed, `-a5-r2`.
  - Nothing is moved or deleted.
- **Release side (05):**
  - A new committed declaration `reports/explore/t1/receipts/reference-attempt-roots-0108-a5.json` (schema `clasher.t1.reference-attempt-roots.v1`) names `BASE/fleet-end-attempts-0108-a5/<host>`.
  - It is committed and pushed **before the first A5 launch**, which `release_reference.attempt_roots` enforces through `registered_at <= identity.utc`.
  - L1 assembly copies only A5 attempts into the new root. Old-code attempts stay in the old release-side root.
- **PC1 reading (declared interpretation):** for each host, the original host-root listing equals A5 descriptor attempts ⊎ committed old-code disclosure ⊎ committed RF1 exempt disclosure, and the three sets are disjoint and exhaustive.

## 4. The K4S reporting running now on 03/04

**It does not use `fleet_validity.py`, and this fix can't affect it.**
- The running phase is `replacement-r1`: launch receipt `reports/explore/k4s-confirm/run-r1/receipts/replacement-r1-launch-receipt.json` 3b8a2943 (7ee26396), job `/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r1`, runtime pin 2252214e. Its latest sealed health checkpoint is `replacement-r1-20261012T034206Z` (f93e924c).
- It is launched via `launch.sh`, which runs `runtime.sh reports/explore/k4s-confirm/supervise.py` (`launch.sh:21`).
- `supervise.py` imports only K4S's own frozen copies of the T1 guard modules: `host_audit`, `system_bus`, `ssh_budget`, `apt_budget`, `idle_services`, `pin`, `common`, `cpu_accounting`.
- `run.py` imports no e4v3 module.
- `git grep` finds `fleet_validity` / `e4v3` only in K4S `end_*.py`, `mac/*` and tests, never in the reporting path.
- Its frozen job manifest `FROZEN-K4S.json` 416f6e51 doesn't list any e4v3 file. It binds `K4S-MAC-MANIFEST` d89cab16, which keeps pointing at 94d0e7f2 and is **not** re-pinned (§2c).
- This branch changes no K4S file and stages nothing. **No action on 03/04, and none is required.**

**Where K4S *is* affected: the future K4S END reference.**
- It runs the same `ReportingGuard` and spawns 10 background workers right after admission.
- On a host whose admit guard call takes ≳0.93 s (08 measured 1.24 s), it should be expected to fail with `foreign_compute` at the first sample after admission, exactly like E4 08 r2.
- This holds whether or not E4 08 r3 passes. The coordinator needs a K4S-side ruling before any K4S END reference: either adopt this fix via the K4S re-pin, or accept the risk.

## 5. Tests on this branch

These ran on 127x05 under `nice -n 19 taskset -c 120-123`, with Python 3.12.12 (a private uv install in the job directory). The command was `python -B -m unittest discover -s …/e4v3/tests`.

| Run | Result |
| --- | --- |
| Baseline, origin/main (94d0e7f2) | 91 tests, OK (skipped=2: torch unavailable) |
| New `test_guard_census_race.py` against **94d0e7f2** | **FAILED (failures=7)**: late census children flagged `foreign_compute`; pre-exec children de-owned; a foreign row lists the E4 worker 102 next to the real foreign 300. The pid-reuse test passes on both versions, as intended: it guards behavior that must not change |
| Full suite with the fix (eae5db3f) | **96 tests, OK (skipped=2, same torch skips)** |

The new tests:
1. a stubbed `processes()` returns the late spawn children only on the census call;
2. real foreign pythons are still flagged, including one with E4's own cmdline outside the E4 tree;
3. a reused pid with different start_ticks is not owned, whether its ppid is 1 or E4;
4. pre-exec vfork children in three snapshot orders are never de-owned;
5. the exec transition happens once only and must keep pid, pgid, start_ticks and uid.

**Live `/proc` check on 127x05.** The receipt is `e4-guard-race-fix-20261012/results.json`, produced by `live_race.py`. The check starts 10 real spawn workers between the ownership snapshot and the census, against the real host scan plus the synthetic pinned dbus row.
- On 94d0e7f2, 0/10 workers were owned, and **all 10 were flagged `foreign_compute`** in each of 3 runs. That reproduces 08 r2 deterministically.
- On eae5db3f, 10/10 were owned and none flagged, in each of 3 runs.
- On both versions, the 6 genuinely foreign python processes on 05 were still flagged.

That is the full extent of live exercise; nothing was run on a fleet host. Sol has not reviewed the fix.
