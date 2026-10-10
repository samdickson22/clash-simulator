# A19 r5 + A20 r1 combined candidate: final diff-only verification

**Reviewer:** the independent Claude reviewer of A19 r2, r4 and r5 (90762bcb…) and A20 r1 (c1e50fa4…), for coordinator 0523ae6f. Written 2026-10-10, about 05:01–05:15Z.

**Review was read-only.**
- **127x05 (nice 19):** all suites ran on Python 3.12.12, with `-B`. The candidate directory was hashed before and after the run and is byte-unchanged; no `__pycache__` was created.
- **127x04:** two read-only SSH probes at 05:02Z and 05:04Z: `find`, `sha256sum` under nice 19 / ionice 3, `ps`, `who` and `/proc/meminfo`. Nothing was written, locked or signalled. The seal (2499718/2499719, CPU 52) was not disturbed.
- **Reviewer's own files:** this file and `reviews/a19-a20-final-verify-artifacts/`. Scratch went to `/tmp/sdicks02/fv-mdxR` on 05. Nothing was committed.

## Verdict: APPROVE

The combined candidate (package 7efbcbd1…, plan 0fe6fe3a…) is approved for freeze and for issuing the records in §5.

| Prior condition | Status |
|---|---|
| E1 | Satisfied exactly |
| E2 | Satisfied in the template; the coordinator must carry the fields into the FROZEN record |
| E3 | Satisfied |
| C1 | Satisfied |
| C2 / cap | Satisfied |
| C3 | Satisfied |
| R1 | Satisfied |
| R2 | Satisfied |

**Production delta from held A20.** The only production change from held A20 r1 is the one E1 constant.

**Launch is not authorized by this review.** O1–O9 and `execution_cap_authority_sha256` are launch-time state, and at 05:02Z O2 and O4 are still unmet (§4).

**Coordinator addendum: the OPERATOR r3 documentation supplement** (manifest 765369f4…) **is verified and should be bound by the freeze** (§6).
- Its runtime-enforced field lists equal exactly what `authenticate()`/`authenticate_a20()` read.
- Its values match §5, and records built literally from its JSON authenticate.
- One classification erratum: `allow_serial_verify_handoff` is runtime-checked, not merely documentary.

## 1. Production delta and fixtures (check 1)

| Check | Result |
|---|---|
| `check_package.py --manifest-sha256 7efbcbd1…` (3.12.12, `-I`) | **PASS**. It rehashes 50 package members, 5 held manifests and their members (A19 r2–r5, A20 r1, held bytes unchanged), and 347 A18 frozen pins. It also confirms 19 original plan fields, exactly 11 runtime files and the E2/E3 bindings. |
| All 35 candidate files | SHAs match the brief and every pin in CANDIDATE-STATUS, test-receipt, integration-delta and staging receipt. |
| **E1 diff, regenerated** with `diff -u` (held A20 `composed-runtime` vs candidate) | **Byte-identical to b5286c36…**. `diff -r` over the 11 files reports a single changed line: `a19_authority.py:52`, `datetime(2026,10,11,4,…)` → `datetime(2026,10,13,4,…)`. The other 10 files are byte-equal, and the message string is unchanged. |
| **r5 → combined diff, regenerated** from the held r5 `a19_*.py` | **Byte-identical to c692f081…**. It touches only the authority (source set gains `a20_io.py`, `authenticate_a20` call, cap 11→13, output parent `…-r5-a20-r1`), one import in the launcher, one import in the worker, and the new `a20_io.py`. That is exactly the A20 diff I reviewed plus E1. |
| r5 files byte-equal in combined | Kernel, reduce, common, a2, resources, pool and handoff. The D1–D4 hunks therefore carry forward byte-identically. |
| Plan 0fe6fe3a vs held A20 plan eca06114 | A recursive diff finds exactly one leaf: `operational_body_verification.source_files_sha256.a19_authority.py`, a24a89bb… → 0df943e9…. The 19 scientific fields are still canonically equal to 68e24722. |
| **Fixture diff, regenerated** from the five named originals | **Byte-identical to 496e4088…**. See below. |

The fixture diff is **test-only**:
- `test_a19_authority.py`: only `setUp` is replaced, by my `ComposedAuthority` fixture shape. Every test method and assertion is unchanged.
- `test_a19_real_handoff.py`: the subprocess `PYTHONPATH` now follows `a19_handoff.__file__`.
- `test_a20_integration.py`: points at the new plan filename.
- `test_a20_io.py`: R2, `unittest.main()` moved below `BufferBudget`.
- `test_rev_a20.py`: the cap tests were flipped as I asked in §7.3, and a deadline-expiry test was added.

The other 10 test and helper files are byte-identical to their r5 or A20 originals.

## 2. Tests (check 2)

| Run | Result |
|---|---|
| **Full composed suite**, run as the REVIEW-CHECKS command but with `A20_REAL_DIR=/tmp/sdicks02/a20-review-data` (the two real 04 records, 16.1 MB and 31.3 MB) | **235 ran, 235 OK, 0 skipped, 0 failures, 0 errors** (226.8 s, `full-composed-suite-real-records.log` 4292897c…). The author's receipt reported 234 + 1 skip; the skip was `RealRecordEquivalence`, which **passes** here on the composed bytes. The 235 executions cover 213 unique test IDs; the rest are inherited repeats. |
| **My A19 r5 reviewer tests on the combined runtime** (`test_rev_a19_r5_on_combined.py` = e1f16db6… with only `L1`/`PKG` re-pointed to `composed-runtime`; `taskset -c 40`) | **20/20 PASS** (253 s). The STOP race was 18/18 `SERIAL_VERIFY_SUPERSEDED`: 14 runner-stop-check and 4 supervisor-sigterm. The outcome JSONs are byte-equal to r5's (f3548310…, 43e6075d…) because the race phases are seeded. |
| **My A20 reviewer tests** (candidate `test_rev_a20.py` d5832c52… = 4fec068b… plus the fixture hunk) | Ran inside the full suite: 25 original tests, one replaced (Oct-13 accepted), two added, and the real-record test included. All pass. |
| **New exact-records test** (`test_final_exact_records.py`, 15 tests) | **15/15 PASS** (`exact-records-tests.log`). See below. |

The exact-records test feeds the composed `authenticate()` with records shaped exactly as in §5. It uses the **real** plan 0fe6fe3a, the **real** A19 r5 and A20 r1 drafts and the **real** original approval 19401ce4. Only host-bound checks are stubbed: the frozen `authenticate_plan`, the SSH wrapper hash, interpreter/cwd/PYTHONPATH and the clock.

The valid set authenticates, and both frozen plan calls are made, the second with P. Each of the following is **rejected**:
- Oct-13 04:00:01Z;
- `now == deadline`;
- an Oct-11 allocation checked after Oct-11;
- a 9th A1 key;
- a changed A1 field;
- an A1 approval bound to 7d2a92bc;
- `APPROVE_A20` as the decision;
- the base r5 10-file map in the A19 freeze;
- the held-A20 authority pin a24a89bb in the A19 freeze;
- A20 records bound to eca06114;
- the r5 output parent;
- the r4 draft as `request.amendment`;
- a 12th `.py` file in the code root.

## 3. 04 deploy (check 3)

Read-only at 05:02Z, `/mpac/sdicks02/jobs/clasher/v4-a19-a20-combined-r2`:
- **Contents.** Exactly 15 files: `code/` holds **exactly 11** `.py` files, and the other four are `A19-r5-DRAFT.md`, `A20-r1-DRAFT.md`, `execution-plan.json` and `source-pins.json`. There are no other files, no subdirectories besides `code/`, and no auxiliary or test Python.
- **Hashes.** All 15 SHAs equal the staging receipt 5d2840d1…. The 11 code SHAs equal `source-pins.json` d37002f2…, the plan is 0fe6fe3a… and the drafts are 2b09f87a… and 6b027d79….
- **Launch-time pins on 04.** These also match:
  - SSH wrapper `v4-a1-parallel-r5/bin/ssh` = 623d2587…, equal to the plan's `ssh_wrapper_sha256`;
  - `coordinator-approval-A1-r2.json` = 19401ce4…;
  - `execution-plan-a1-deployment-r2.json` = 68e24722….
- **Directories that must not exist yet.** `v4-a19-parallel-verification-r5-a20-r1`, `v4-a19-parallel-verification-r5` and `v4-a19-review-r5` are all absent, so there is no output collision and no base deploy to mix with (C3).

## 4. Conditions (check 4)

**E1. Satisfied.**
- The single constant is now 2026-10-13T04:00Z.
- `deadline == 2026-10-13T04:00:00Z` is accepted, and +1 s is rejected (candidate tests and mine).
- `now >= deadline` is rejected, and an earlier approved deadline still expires.
- Guard, worker and handoff are unchanged.

**E2. Satisfied in the template.**
- `A19-FREEZE-REQUIRED-FIELDS.json.in` binds `incorporated_amendment_sha256=b43a3979…` and `review_response_sha256=273b0826…`. I rehashed both from `amendments/…r4-DRAFT.md` and `prepared/amendment19-review-r5/REVIEW-RESPONSE.md`.
- The code does not enforce these two fields. The coordinator must put them in the issued FROZEN record (§5.3).

**E3. Satisfied.**
- `OPERATOR-A19-BASE-CORRECTED.md` says 23 = 10 + 13 and "A2 binds only the original serial receipt".
- The combined OPERATOR says 11 production files and 0 auxiliary. The plan's `auxiliary_files_sha256={}`, and the code root is enforced (tested).

**C1. Satisfied.** The full composed suite passes: 235/235 with real records. The authority tests now run on the composed shape with their assertions unchanged.

**C3. Satisfied.**
- The deploy directory is fresh and exact (§3).
- OPERATOR names `…/v4-a19-a20-combined-r2/code/a19_launcher.py`.
- The old r5 deploy directory does not exist.

**R1. Satisfied.** The erratum text is in `A20-FREEZE-REQUIRED-FIELDS.json.in` and covers both the lock holders and the error ordering.

**R2. Satisfied** in the candidate `test_a20_io.py`.

**Decision string.** `APPROVE_LOCAL_IO_LOCK_SCOPE` is required, and `APPROVE_A20` is rejected (tested).

**Live state, 05:02Z (informational; O-conditions are not met yet).**
- The seal is still running: 2499719 on CPU 52, 07:29 elapsed, with no `seal-exit`. So O4 is unmet.
- X5 fit 3727520 and supervisor 3727388 are still running. So O2 is unmet.
- MemAvailable is 107 GiB, and there are no console users.

**Non-blocking documentation nits (no re-pin needed).**
- **N1.** The combined `OPERATOR.md` still cites `a19-r5-to-a20-r1.diff`; the combined diff is `a19-r5-to-combined-r2.diff`.
- **N2.** The base-corrected O5 "≈1.87×" describes the frozen scope only. For the combined run, use O9 first-wave telemetry.
- **N3.** The combined OPERATOR does not restate the full command. Use the base-corrected command verbatim, changing **only** the script path to `/mpac/sdicks02/jobs/clasher/v4-a19-a20-combined-r2/code/a19_launcher.py`. Keep everything else as it is:
  - cwd `…/v4-a1-dryrun-preparation-r2/execution`;
  - the exact `PYTHONPATH`;
  - `CLASHER_SSH_SLOT=a19-r5`;
  - `PATH` with `v4-a1-parallel-r5/bin`;
  - `nice -n19 ionice -c3 taskset -c47`;
  - `/mpac/sdicks02/envs/clasher-gpu/bin/python -B`.

## 5. Exact records to issue

Throughout this section:
- **P** = `0fe6fe3a1a864811e33e4b8358feea9157b4578771f2ff92237700b366ccfe72`
- **S** = the 11-entry map below, identical to `source-pins.json` d37002f2…. Its canonical JSON SHA (sorted keys, `(',',':')`) is `b0e15d56b926ed6f2132fa2bc8099893e45fed95c33273b691dc832d58230cbd`.

| File | SHA-256 |
|---|---|
| `a19_a2.py` | `36c6b364234ef3be47a86294c836b29fc313e7313dc9f20bf0189fd05985518e` |
| `a19_authority.py` | `0df943e946f543c63b642482713353c3fdb861c9685c470f276285e25d58bdb2` |
| `a19_common.py` | `c4f1b9bae3aa88982a275700078fef4941aea3218258ca904080dba2a7d88d3c` |
| `a19_handoff.py` | `f652aaf57ec1fe887d8c00143756afd9bc8f4f8c73ac6770ef4ae481a3a28f87` |
| `a19_kernel.py` | `5ec530be87b47b90d93e48dce9a77d0b1cb85be45e131408f6d0fa692fdcaee4` |
| `a19_launcher.py` | `20153d397b4fb26bc6b2b5ca983bfec64d34d8d2eea52430cfbc4362d5afbf35` |
| `a19_pool.py` | `f686a6f9d9f11ceba74328a8ed66f7b31d6e5fe8eab2c26d13a11955e50c3c22` |
| `a19_reduce.py` | `8a30e2a87b6ed8e7001e42f68fd12a5b503224356e0054686397382905288c4c` |
| `a19_resources.py` | `9661b4aca2c05d3fee3c1e013c06bdc5044406cbb373c731ddc603e7ba1a8eb0` |
| `a19_worker.py` | `9681395125f6280e157b4fed312c0e52aa6c8dc52d8ad16080915b7fe469f1b3` |
| `a20_io.py` | `da583414af5554417cd58b2f199f6466fa54cd731163ec62540afc1ec12bc7f0` |

**Issue the records in this order:**
1. A20 FROZEN
2. `APPROVE_LOCAL_IO_LOCK_SCOPE`
3. A19 FROZEN
4. `APPROVE_PARALLEL_BODY_VERIFICATION`
5. revised `APPROVE_A1`, which is independent of the others
6. the request

**Legend:**
- **[E]** = enforced by code.
- **[D]** = documentary, required by review.
- **[L]** = launch-time value, determined only at issuance or launch.
- **[I]** = issuance-time SHA of an earlier record.

### 5.1 Revised `APPROVE_A1` — exactly 8 keys [E], no extras allowed

This is a copy of `amendments/coordinator-approval-A1-r2.json` (19401ce4…) with **only** `execution_plan_sha256` replaced. A 9th key is rejected.

| Key | Value |
|---|---|
| `decision` | `APPROVE_A1` |
| `execution_plan_sha256` | **P** |
| `freeze_sha256` | `bd5b76433bf7eda6908ffe77418af3ae5dee27d87362ebb47d86c5721b17e7bc` |
| `file_layer_review_sha256` | `ff45e9edbffa606e020f3c91a4349074e2f19b0cbe431c44b1e70c359358d635` |
| `assembly_sha256` | the 24-entry map `"1"`…`"24"`, copied verbatim from 19401ce4 |
| `evidence_recovery_sha256` | `1adf50de13504df27a3c135e9e73a9b6861c99954f5f6795f80c380f36a1e35c` |
| `evidence_recovery_approval_sha256` | `64b1ebe435aa0a5cca2c9189e500fc43e279532cfae4aa4a671e3534497b4f60` |
| `a18_bindings` | the 6-entry map, copied verbatim from 19401ce4 |

**Cross-check.** The canonical JSON SHA of the correct record is `c8075ac820b0a5f4bcbe26a9d8f973cbe01821e57e5f17e929127153bb8b4acb`. The file-byte SHA depends on serialization; it is what the request pins.

### 5.2 A20 `FROZEN`, then `APPROVE_LOCAL_IO_LOCK_SCOPE`

**A20 FROZEN:**

| Key | Value |
|---|---|
| `decision` [E] | `FROZEN` |
| `execution_plan_sha256` [E] | **P** |
| `base_a19_plan_sha256` [E] | `7d2a92bc06315c7a1fcabc2636c9818cec1784446ee35fd6b9b5399c28f4fc12` |
| `adapter_sha256` [E] | `da583414af5554417cd58b2f199f6466fa54cd731163ec62540afc1ec12bc7f0` |
| `amendment_sha256` [E] | `6b027d792f5a3baa2524725db34a05f3a23798c88fef363e39737064da36fc15`, rehashed from the deployed `A20-r1-DRAFT.md` |
| `a20_review_sha256` [D] | `c1e50fa4096697c1616f3d44dab23cf82378b8cc11bc076b4e0d4dcd92c4cd7f` |
| `final_verify_review_sha256` [D] | SHA of this file |
| `source_pins_sha256` [D] | `d37002f25f41f57dcb208d0b0a31492b8f4193ba6ec8d72a273b9dcaf180654a` |
| `r1_erratum` [D] | verbatim from `A20-FREEZE-REQUIRED-FIELDS.json.in` |

**`APPROVE_LOCAL_IO_LOCK_SCOPE`.** All keys are enforced [E]:

| Key | Value |
|---|---|
| `decision` | `APPROVE_LOCAL_IO_LOCK_SCOPE` |
| `a20_freeze_sha256` [I] | SHA of the A20 FROZEN file |
| `execution_plan_sha256` | **P** |
| `base_a19_plan_sha256` | `7d2a92bc…` |
| `adapter_sha256` | `da583414…` |
| `amendment_sha256` | `6b027d79…` |
| `hosts` | `["127x04"]` |
| `authorized_stages` | `["a1-verify","a2-build-bounds","a2-verified-bounds"]` |
| `serial_runner_changed` | `false` |
| `B_authorized` | `false` |
| `heldout_opening_authorized` | `false` |

### 5.3 Combined A19 `FROZEN`

| Key | Value |
|---|---|
| `decision` [E] | `FROZEN` |
| `execution_plan_sha256` [E] | **P** |
| `source_files_sha256` [E] | **S**, all 11 entries |
| `amendment_sha256` [E] | `2b09f87a742a072bcb411708a332331c9463669efb2465903c54b6a0efea3839`, rehashed from the deployed `A19-r5-DRAFT.md` |
| `incorporated_amendment_sha256` [D, E2] | `b43a39790c4977e8f2c9548429578901a5a44ca4d9e13868e5b80374c9351cef` (the r4 draft is normative except as amended by D1–D4 and A20) |
| `review_response_sha256` [D, E2] | `273b082622ea08b16ad1190dade51e9010e6090e30fc3da83697cb0ca7298d84` |
| `independent_review_sha256` [D] | `c2a092da8c24a098e384f13673cc8151109498d3a272677609263b7f6b10ac43` |
| `r4_delta_review_sha256` [D] | `8820200841ce1161deb753414d18a30ac9fa0dcc7659ac12aadbd1e480dab202` |
| `r5_recheck_review_sha256` [D] | `90762bcb23e1059bb657790b24a82b27d7d9d1dc2347a903585301e17e499266` |
| `a20_review_sha256` [D] | `c1e50fa4096697c1616f3d44dab23cf82378b8cc11bc076b4e0d4dcd92c4cd7f` |
| `final_verify_review_sha256` [D] | SHA of this file |
| `base_r5_package_sha256` [D] | `4e8ba2bd669eaaf4ff82f885caf7ffecb702dfe796f52f61174ddb9c530de64d` |
| `final_combined_package_manifest_sha256` [D] | `7efbcbd17d00d344b2b100e8923b06f1769f36e22db60fdde3e7816515da943c` |
| `a20_freeze_sha256` [D, I] | SHA of the A20 FROZEN file |

### 5.4 `APPROVE_PARALLEL_BODY_VERIFICATION`

| Key | Value |
|---|---|
| `decision` [E] | `APPROVE_PARALLEL_BODY_VERIFICATION` |
| `a19_freeze_sha256` [E, I] | SHA of the A19 FROZEN file |
| `a20_freeze_sha256` [E, I] | SHA of the A20 FROZEN file |
| `execution_plan_sha256` [E] | **P** |
| `original_execution_plan_sha256` [E] | `68e2472255ba5d1b79ec9f45217aa14208a31b6c44ccec890af332909efe8bc8` |
| `original_approval_sha256` [E] | `19401ce4ccb70fced9d530234015861693328e4e0cebfa650dd78e9344374b88` |
| `source_files_sha256` [E] | **S** |
| `amendment_sha256` [E] | `2b09f87a…`, equal to the A19 freeze |
| `authorized_stages` [E] | `["a1-verify","a2-build-bounds","a2-verified-bounds"]` |
| `hosts` [E] | `["127x04"]` |
| `seal_root` [E] | `/mpac/sdicks02/jobs/clasher/v4-a1-body-seal-20261009-r4` |
| `seal_binding` [E] | `authenticated-r4-exit-then-pin-actual-bytes` |
| `B_authorized` / `heldout_opening_authorized` [E] | `false` / `false` |
| `handoff_policy` [E] | `verify-then-retire` |
| `exclusive_physical_cpus` [E] | `[0,1,2,3,4,5,6,7,8,9,10,11,47]` |
| `excluded_siblings` [E] | `[64,65,66,67,68,69,70,71,72,73,74,75,111]` |
| `no_new_clasher_launches` / `x5_actual_exit_required` [E] | `true` / `true` |
| `output_parent` [E] | `/mpac/sdicks02/jobs/clasher/v4-a19-parallel-verification-r5-a20-r1` |
| `allow_serial_verify_handoff` [E] | `true`, as a JSON boolean. `authenticate()` does not check it; the runtime does:<ul><li>if the key is missing, the launcher's `op[...]` read raises a KeyError at the pre-check;</li><li>if the value is anything other than `True`, `a19_handoff.py:50` rejects it with "Explicit serial handoff approval required". That check runs only **after** the full parallel verification, just before STOP, so a wrong value wastes the whole parallel run.</li></ul> |
| **`valid_until_utc`** [E, **L**] | The coordinator's actual 04 **execution** allocation end, which must be later than the issue/launch time and ≤ `2026-10-13T04:00:00Z`. If no explicit execution allocation exists, ≤ `2026-10-11T04:00:00Z`. |
| **`execution_cap_authority_sha256`** [D, **L**] | SHA of the coordinator's 04 execution-allocation record that justifies any `valid_until_utc` after 2026-10-11T04:00Z. Service renewal alone is not enough. |
| `x5_supervisor_exit_required` [D] | `true` (O2) |
| `r3_worker_exit_required` [D] | `true` (O6) |
| `min_mem_available_at_launch_bytes` [D] | `85899345920` (O3) |
| **`max_local04_compressed_bytes_observed`** [D, **L**] | O7 preflight maximum; must be < 536870912 |
| **`o7_preflight_receipt_sha256`** [D, **L**] | SHA of the O7 receipt: path-list SHA, sizes, max and UTC |
| **`o9_telemetry_plan_sha256`** [D, **L**] | SHA of the arranged first-wave per-lock telemetry plan: read-only `/proc` fdinfo sampling, nice 19, CPU 47, counted in the 16-process / 48 GB caps |
| **O1–O6 receipts** [D, **L**] | Recommended `launch_conditions_receipt_sha256`, binding these items: <ul><li>O1: lease and no G on 0–11/47 and 64–75/111, plus a fresh inventory</li><li>O2: X5 fit/loaders **and** supervisor 3727388 gone</li><li>O3: MemAvailable ≥ 80 GiB</li><li>O4: authenticated seal exit</li><li>O5: throughput note</li><li>O6: R3 worker exited</li><li>O8: no new `127x04.io.lock` ops</li></ul> |

### 5.5 Request

Every entry is enforced [E]. Base the request on `REQUEST-TEMPLATE.json` 5c90840a…, filling these entries:

| Entry | Value |
|---|---|
| `stage` | `a1-verify` |
| `stage_approval` | `null` |
| `verification_plan` | `{path: /mpac/sdicks02/jobs/clasher/v4-a19-a20-combined-r2/execution-plan.json, sha256: P}` |
| `amendment` | `{…/v4-a19-a20-combined-r2/A19-r5-DRAFT.md, 2b09f87a…}` |
| `a20_amendment` | `{…/A20-r1-DRAFT.md, 6b027d79…}` |
| `original_plan` | `{…/v4-a1-parallel-r5/execution-plan-a1-deployment-r2.json, 68e24722…}` |
| `original_approval` | `{…/coordinator-approval-A1-r2.json, 19401ce4…}`. Both are verified on 04 today. |
| `a1_approval`, `a19_freeze`, `a20_freeze`, `a20_approval`, `operational_approval` | `{path, sha256}` of the issued files [I] |

The request's own SHA is passed to `--request-sha256` [L].

### 5.6 OPERATOR r3 supplement binding (combined A19 FROZEN extras [D])

Add these two documentary keys to the combined A19 FROZEN record (§5.3):
- `operator_supplement_manifest_sha256` = `765369f481977b3ffa47a7bc2122299cf750ad0927f1b6636b1f5c8312d66d0c`
- recommended: `approval_field_spec_sha256` = `d7280e00257552f50c0679caf6ca062d48a3e6ba110cc237e4b2280232340d57`

See §6.

### 5.7 A2 later

Each A2 stage needs a separate `APPROVE_A2` with `verification_execution_plan_sha256=`**P**, as in r5 §6. This review confers no A2, B or held-out authority.

## 6. Addendum: OPERATOR r3 documentation supplement (`prepared/amendment19-a20-operator-r3/`)

**Bytes and scope.**
- All four members match the manifest 765369f4…: OPERATOR 4827030e…, field spec d7280e00…, doc check ee2f1823… and diff ae316500….
- The manifest binds base package 7efbcbd1… and plan P.
- The supplement holds no Python and no runtime, plan, test or deploy bytes. The candidate package still passes its checker, and the 04 deploy is as verified in §3.
- **The diff regenerates** byte-identically from the held combined `OPERATOR.md` b7fc7da0… with `diff -u --minimal` (labels `held-combined-r2/` and `operator-r3/`). It is a documentation rewrite only.

**Mechanical check against the code** (`test_operator_r3_spec.py`, 5 new tests plus 15 inherited; with the base class, 35 executions, all OK; `operator-r3-spec-tests.log`).
- **Records built literally from the spec authenticate.** Every record was built by reading `APPROVAL-FIELD-SPEC.json` only, then merging its enforced keys, documentary extras and operational extras. Placeholders were filled only with issuance-time record SHAs and a deadline. The composed `authenticate()` passes on the real plan and drafts, and both frozen plan calls are made.
- **Cap boundary holds.** With the same records, a deadline of Oct-13 04:00:01Z is rejected.
- **Enforced key sets equal what the code reads:**

  | Record | Spec "enforced" keys | Code that reads them |
  |---|---|---|
  | Operational approval | 21 keys | the `op[...]` reads in `authenticate()` plus `operational[...]` in `authenticate_a20()`, **exactly** |
  | A19 FROZEN | 4 keys | the `freeze[...]` reads in `authenticate()`, exactly |
  | A20 FROZEN | 5 keys | the reads in `authenticate_a20()`, exactly |
  | A20 approval | 11 keys | the reads in `authenticate_a20()`, exactly |
  | A1 approval | 8 keys | `APPROVAL_FIELDS`, with `extra_fields_allowed=false` |

- **A1 values.** The spec's A1 record equals 19401ce4 key-for-key, all 24 assembly hashes and all six A18 bindings included, except `execution_plan_sha256` = P.
- **Source maps.** Both 11-file maps equal `source-pins.json`.

**Agreement with my §9/§5 expectations.**
- Every runtime-enforced value is identical, and the decision strings are exact.
- The spec states the deadline as "explicit 04 execution allocation, ≤ Oct-13 04Z, else ≤ Oct-11 04Z", which is correct.

**Findings (non-blocking, no re-pin needed):**
- **S1 (classification).** The spec lists `allow_serial_verify_handoff` under "operational_and_documentary_extras". It is in fact **runtime-required**:
  - `authenticate()` does not check it.
  - If the key is missing, the launcher's `op[...]` read fails at the pre-check.
  - If the value is anything other than `true`, `a19_handoff.py:50` fails, but only *after* the full parallel verification.

  The spec's value, `true`, is correct. The coordinator must treat the field as mandatory (see the §5.4 row).
- **S2 (documentary omissions).** The spec does not list these recommended extras from §5:
  - `r3_worker_exit_required` (O6);
  - `o7_preflight_receipt_sha256` and `o9_telemetry_plan_sha256` (launch-time);
  - in the A19 freeze: `independent_review_sha256` c2a092da…, `r4_delta_review_sha256` 8820200841ce…, `base_r5_package_sha256` 4e8ba2bd… and `final_verify_review_sha256`.

  None is checked at runtime, so adding them is recommended but not required.
- **S3.** Its prose cites the author's receipt (234 + 1 skip). The skipped real-record test passes in my rerun (235/235, §2).
- **S4.** `documentation-check.json` lists 20 operational keys and omits `a20_freeze_sha256`. The spec and OPERATOR do include it, enforced by `authenticate_a20`.
- **N1 and N3 from §4 are resolved.** The stale diff filename is gone, and the launch script path is explicit. Still, use the base-corrected command for the full environment.

**Should the final freeze bind it? Yes.** Put `operator_supplement_manifest_sha256=765369f4…` in the combined A19 FROZEN record (the spec already has a placeholder for it), and preferably also `approval_field_spec_sha256=d7280e00…`. This pins only documentation. It is not an execution-plan change, and the code never reads it. Issue in this order:
1. A20 FROZEN
2. A20 approval
3. A19 FROZEN (binding the supplement)
4. operational approval
5. revised `APPROVE_A1`
6. the request

## Summary

**APPROVE**, including the OPERATOR r3 supplement. Bind it in the A19 FROZEN record via `operator_supplement_manifest_sha256=765369f4…`, and treat `allow_serial_verify_handoff=true` as mandatory (S1).
- **Production delta.** The delta from held A20 is exactly the E1 constant. Both diffs regenerate byte-identically, the fixture diff is test-only, and the plan differs only in the authority pin.
- **Tests.** The full composed suite **235/235, 0 skipped**, including the real-record test on 05. My r5 tests: 20/20 on the combined runtime, with 18/18 SUPERSEDED. My new exact-records tests on the real plan and drafts: 15/15, including the Oct-13 boundary.
- **04 deploy.** Exactly 11 code files, all byte-equal to the pins, and no stray directories.
- **Launch.** Still blocked by O2/O4 and the other [L] items.

## Reviewer artifacts (`reviews/a19-a20-final-verify-artifacts/`)

| File | SHA-256 |
|---|---|
| `test_final_exact_records.py` | `068489abdacb62ab589a2a28523a56d75517162d4979ff362de91f6f7e0ecb92` |
| `exact-records-tests.log` (15/15) | `637352fbf6203f877de0814932fcc3d976d7064bea5d43472598b7433c5c8864` |
| `full-composed-suite-real-records.log` (235/235) | `4292897c77614cb8fdd74988d78591255466718dad197c04864e6b97a13f623a` |
| `test_rev_a19_r5_on_combined.py` | `b740d160bf3cb71192bf7765c3927313f245ddc512317d2462ff10ccf4fd45e3` |
| `reviewer-r5-tests-on-combined.log` (20/20) | `c4ec7d4c0c3ee7a6ef4a2388badf5be8f661fdffd21d0fe4904da78c3ea6ecd6` |
| `stop-race-outcomes-measured.json` | `f3548310cf1f0696016cef3858c0991e4924a79ce654022473bbdf0d92feb020` |
| `stop-race-outcomes-sweep.json` | `43e6075d8942f8a721d9ba54bfa77fc9a40270812785792429eae42a0d012b4d` |
| `test_operator_r3_spec.py` | `3522d1375ea85c21afbbe0f3e1e80d67a229876400d1a7e150ab4ccfbd2f0372` |
| `operator-r3-spec-tests.log` (35 OK) | `cea307feb44fcaf8eeed41cf7937abb5c74330f4570da1492eb01a2dae21d9bf` |
