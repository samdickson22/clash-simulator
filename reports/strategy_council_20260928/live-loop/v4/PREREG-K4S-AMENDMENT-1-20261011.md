# PREREG-K4S Amendment 1: re-pin `measure_tiers.py` after TIERS A2 (outcome-blind)

- **Recorded:** 2026-10-11T18:15:41Z (`date -u`), by the implementation worker on 127x05, under authorization of coordinator thread 0523ae6f (COORDINATOR.md commit 6a2669ae, line "Companion K4S rebind required").
- **Study:** PREREG-K4S, frozen at 391d2006 (fill fab6e03f; freeze record json `478068b6…` / md `24623ff8…`).
- **Base tree:** origin/main 6afcbbab (TIERS Amendment 2 merged).
- **Machine record:** `PREREG-K4S-AMENDMENT-1-20261011.json`, in this directory.

## 1. Outcome-blind status

This amendment is **outcome-blind**. It was written without reading any K4S confirmatory outcome or reporting receipt, and without reading any TIERS or T1 game outcome. The one prior-study exposure is disclosed below: pre-freeze X4S-2 exploratory numbers, already frozen into the design. Its only input is a byte change to a reused read-only TIERS file, made by an erratum that is itself outcome-blind. Nothing in the amendment depends on any result: its content is fully determined by the A2 byte change and the manifest builder.

**Blinding disclosure.**
- **Author:** the author opened no K4S confirmatory receipt or outcome. Grepping COORDINATOR.md for "K4S" did show coordinator summary lines quoting pre-freeze X4S-2 exploratory numbers. Those numbers are design inputs already frozen into PREREG-K4S, including the c\* = 0.9 record.
- **Sol r1:** the r1 reviewer reported reading the X4S c\* provenance in `FREEZE-RECORD-SKELETON.md`. That is a prior study's frozen input, not a K4S outcome.
- **Sol r2 and later:** each later round reviewed under an explicit outcome-blind read boundary that excludes those files and every receipt. r2 reported compliance.

Neither exposure can affect a mechanically determined re-pin.

## 2. Cause: TIERS Amendment 2

TIERS Amendment 2 is merged on main at 6afcbbab.

- **The change:** it is an erratum that adds one line, `import math`, to `reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/measure_tiers.py`. This changes the file's SHA-256 from `5d7de8e36890f0f8d086e77be5ec4e20de1b3cc1f48943bd06e8bbd103046124` to `6066228b89601d6cf29ff456e9dee4848fa59886f319ff38ebabd49e3c101f2e`.
- **Review:** `TIERS-AMENDMENT-2-REVIEW-r1.md`, SHA `021c8f4477a2eebd04614672f6a66e52f0513e813efc7eb66501c48dc70031af`. Its condition 4 raises this cross-study pin break.
- **Disposition:** COORDINATOR.md, commit 6a2669ae.

The frozen K4S Mac manifest (F-8) pins the old bytes. On any post-A2 tree, `k4s_logic.load_k4s_manifest` → `verify_pinned(runtime_root, reused_readonly, …)` raises `PreconditionRefusal: Pin mismatch (reused read-only TIERS files): …/measure_tiers.py`, so every K4S Mac session fails closed. K4S imports only `measure_tiers.GCTrace` from that file, and the added import does not change GCTrace.

## 3. The change

| | Path | SHA-256 |
|---|---|---|
| Old (frozen F-8) | `reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json` | `d89cab16afdffa88d30e61eb1f4daea74e046703994f6aee7e74bfedc8d08f40` |
| **New (amended)** | same path | **`8bb20a753bdb8f5f606ea2288336b1350f96a5199d158b2b8750317c26493009`** |

**One semantic pin changes.** The pin `reused_readonly["reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/measure_tiers.py"]` goes from `5d7de8e3…` to `6066228b…`.

The builder also requires one derived field. `measure_tiers_unmodified.sha256` is defined in `mac/build_manifest.py` as `reused[tiers_script]`, and the loader refuses if the two disagree ("measure_tiers.py statement disagrees with its read-only pin"). It changes to the same value. Its `path` and `statement` are unchanged.

**How the file was produced:** I regenerated it mechanically with the manifest's own builder on the 6afcbbab tree, without editing it by hand:

```
python -B reports/explore/k4s-confirm/mac/build_manifest.py --root <tree> \
  --kernel reports/explore/k4s-confirm/anchor_x.py --kernel reports/explore/k4s-confirm/sdefault.py --freeze
```

**Verification:**
- **Key-by-key diff, old vs new:** both have the same 77 leaf keys, and exactly 2 leaves differ, the pin and its derived statement copy. `git diff` shows 2 changed lines.
- **Freeze status:** `frozen` is still `true` and `status` is still `"FROZEN"`.
- **No other pin moved:** I hashed all 43 file pins in the old manifest against 6afcbbab. Only these two entries mismatched, and between 391d2006 and 6afcbbab no other pinned file changed.
- **Unchanged pins:** the kernel (`sdefault.py` `0448db50…`, `anchor_x.py` `cf528473…`), scorer, SD1 manifest (`b8ce7b4c…`), corpus, native provenance, every `k4s_files` / `end_files` pin and every other `reused_readonly` pin.
- **Behaviour check:** `load_k4s_manifest(new, 8bb20a75…, <6afcbbab tree>, require_frozen=True)` succeeds. The same call on the frozen d89cab16 manifest refuses with the pin mismatch above.

## 4. Tests

I ran `nice -n 19 taskset -c 63 /mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q reports/explore/k4s-confirm/mac`, using Python 3.12.

| Tree | Result |
|---|---|
| At the freeze, as recorded at 391d2006 | 94 passed / 1 failed (95) |
| 6afcbbab, before this amendment | **88 passed / 7 failed (95)** |
| After the re-pin, existing suite | **94 passed / 1 failed (95)** |
| After the re-pin, with the new regression test | **95 passed / 1 failed (96)** |

**Failures at 6afcbbab before the amendment.** Six of these are caused by A2:
- `test_manifest_is_current_and_measure_tiers_unmodified`
- `test_cli_refuses_uncommitted_tiers_receipts`
- `test_cli_refuses_without_tiers_completion_receipt`
- `test_cli_refuses_bad_tiers_sha_and_standalone_without_authorization`
- `test_cli_refuses_incomplete_tiers_session`
- `test_cli_tiers_exactness_failure_writes_no_measurement_summary`

The seventh, `test_manifest_loader_rejects_draft_for_mac_and_tamper`, is the known by-construction failure from the freeze: it asserts `frozen is False` on the committed manifest. It is the **only** failure left after the re-pin.

**New regression test:** `mac/test_k4s_amendment1.py::test_verify_pinned_accepts_amended_measure_tiers_pin_and_rejects_old`, SHA `a0a70f7f…`. It asserts that the committed manifest carries `6066228b…` in both fields, that `verify_pinned` accepts it against the live tree, and that `verify_pinned` refuses the old `5d7de8e3…` pin with "Pin mismatch … measure_tiers.py".
- **No reviewed test edited:** the test is in a **new, unpinned** file. `mac/test_measure_k4s.py` is itself pinned in `k4s_files` (`edd6956b…`), so adding the test there would have changed a second manifest pin.

**END tests:** `test_end_reference.py` and `test_end_background.py` give 103 passed, both before and after the re-pin. They build their own manifests.

## 5. Effect and scope

**What this amendment does NOT affect:**
- **The K4S fleet game run on {127x03, 127x04}**, provided its runtime keeps the frozen 391d2006 bytes; see the FROZEN-K4S.json item below.
- **Everything else frozen:** arms, cells, seeds, N, hypotheses H1–H4, gates, margins, alpha, SD1 (manifest `b8ce7b4c…`, R3a bytes), c\* = 0.9, the K4S kernel and scorer, the corpus, the native binary, DELTA-MANIFEST deltas and every other frozen file. No frozen decision rule changes.

**What it does affect.** The K4S Mac manifest of record becomes `8bb20a75…` for **Mac sessions and for every END step that loads the K4S manifest**.

- **Mac sessions.** Pass `--k4s-manifest-sha256 8bb20a753bdb8f5f606ea2288336b1350f96a5199d158b2b8750317c26493009`. The runtime tree must hold `measure_tiers.py` = `6066228b…`, i.e. main at or after the commit carrying this amendment.

- **END producer/pooler.** `end_reference.k4s_pins`, `end_pool.pool_context` and `end_background.frozen_helpers` all call `load_k4s_manifest(…, require_frozen=True)`. That verifies **every** `reused_readonly` pin, including `measure_tiers.py`, under the END runtime root.
  - **Correction to earlier notes:** the TIERS-A2 review (condition 4) and the coordinator note say END pooling doesn't pin this file. That is true only of `end_pool.frozen_helpers`. END does depend on the pin transitively.
  - **Why END must use the amended SHA:** the Mac also checks `pins.k4s_manifest_sha256` in the fleet reference against its own manifest SHA (`check_fleet_provenance` → `check_end_pins`, "measured on a different k4s_manifest_sha256"). So the END-JOB `k4s_manifest_sha256`, the END pool descriptor `k4s_manifest.sha256` and every `end_reference.py` invocation must name **`8bb20a75…`**, with a runtime root holding the amended manifest and `measure_tiers.py` `6066228b…`.
  - **Failure mode if they don't:** an END reference produced under `d89cab16` would be refused by every amended Mac session.
  - **No committed END work on the checked tree:** no K4S END window has been declared, per COORDINATOR.md (18:00Z: "END prep only, until I declare the K4S END window"). No END-JOB declaration or END reference is present on the checked main tree (6afcbbab). External job state is unknown: it was not inspected, because this worker had no ssh.
  - **Recovery if old-SHA END work exists anyway.** A reference produced under `d89cab16…` cannot serve an amended Mac session in either of the two cases below:
    - **(i) Produced without a committed END-JOB**, i.e. outside valid END authority, such as a dev or dry run. It is not valid for authorized END/Mac use, although dry-run validation can accept it (`k4s_logic.check_fleet_reference`, `dry_run=True`). Exclude it from the reporting reference and produce the reference fresh under an END-JOB that names `8bb20a75…`, from the amended tree. TIERS-A2 condition 5 likewise says END bundles are prepared only from the amended tree.
    - **(ii) Bound to a committed END-JOB that names `d89cab16…`.** Existing technical-repeat rules are **not** sufficient, because the END-JOB declaration is append-only.
      - `end_evidence.immutable` requires its fixed path to be added in exactly one commit and never modified, deleted or re-added.
      - `end_evidence.end_job` refuses a different `k4s_manifest_sha256`.
      - Later rounds keep the same frozen inputs (`end_pool.py` round checks).
      - **What is required:** a coordinator disposition and an explicitly authorized END authority migration before any amended re-run. This amendment does **not** implement such a migration.
      - **What must not happen:** the immutable declaration must not be edited, replaced or patched.

- **FROZEN-K4S.json (the K4S runner's fleet job manifest).** Fleet reporting admission runs `barrier.reporting_release` at `run.py:348–349` and `supervise.py:37–38`. For every file FROZEN-K4S.json lists, it asserts two things:
  - the SHA matches the fleet runtime tree (`barrier.py:51`; `j/repo` in supervise, `ROOT` in run.py);
  - the SHA matches `git show <authorization.freeze_commit>:<name>` (`barrier.py:61`).

  No fleet game code loads the K4S Mac manifest. The fleet's only dependency on it is this byte identity, and only if FROZEN-K4S.json lists the file.
  - **Under the current fleet authorization** (`REPORTING-AUTHORIZATION.json` freeze_commit = 391d2006): if FROZEN-K4S.json covers mac/, its `mac/K4S-MAC-MANIFEST.json` entry must be the frozen `d89cab16…`. The **fleet job runtime trees must also keep those original bytes**, i.e. the 391d2006 runtime on 03/04 and its job `repo` copies. Do not list `mac/test_k4s_amendment1.py`, which does not exist at 391d2006.
  - **Warning, two ways to block reporting admission:**
    - **Amended bytes in the fleet runtime:** deploying the amended manifest (`8bb20a75…`) into a fleet runtime whose FROZEN-K4S.json lists `d89cab16…` blocks reporting admission (barrier.py:51).
    - **Amended SHA in FROZEN-K4S.json:** listing `8bb20a75…` while the authorization names 391d2006 also blocks it (barrier.py:61).
  - **Mac/END runtime:** Mac sessions and END run from a **separate, amended runtime** (main at or after the commit carrying this amendment) and use `8bb20a75…`, as above. The fleet game runtime and the Mac/END runtime must not be mixed.
  - **Where the coordinator's wording does hold:** the barrier reads the commit from `authorization.freeze_commit`; 391d2006 is not hard-coded. A separately coordinator-authorized FROZEN-K4S.json and REPORTING-AUTHORIZATION bound to a committed tree that holds the amended manifest could list `8bb20a75…`.
    - **Not done here:** that would re-key the fleet admission identity, and this amendment does not do it.
    - **Recommendation:** keep the fleet job manifest on the frozen 391d2006 bytes and keep the amended SHA to Mac/END. Changing the fleet authorization is the coordinator's call.

- **Records not edited.** `DELTA-MANIFEST.json`, `FREEZE-RECORD-SKELETON.md` and the freeze record (`PREREG-K4S-FREEZE-20261011.{json,md}`) still name `d89cab16…`. They describe the frozen tree at 391d2006 and are not edited. This amendment supersedes their F-8 SHA for Mac/END use only.
  - **Expected `rebind.py verify` output on main:** it will additionally report `mac/K4S-MAC-MANIFEST.json` (sha changed) and `mac/test_k4s_amendment1.py` (unclassified). On main it already reports `FREEZE-RECORD-SKELETON.md`, which was filled at the freeze.
  - **rebind is not a gate:** it is a prep-time classifier and no runtime path invokes it. `end_reference.py` reads DELTA-MANIFEST only for the kernel/scorer rows, which are unchanged.

## 6. Files

**Changed:**
- `reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json`: `d89cab16…` → `8bb20a75…`.

**Added:**
- `reports/explore/k4s-confirm/mac/test_k4s_amendment1.py`
- this record and its JSON
- `reports/explore/k4s-confirm/reviews/SOL-REVIEW-K4S-AMENDMENT-1-r*.md`

**Review:** GPT-6.1-Sol at high reasoning effort.

| Round | Verdict | Findings | Resolution |
|---|---|---|---|
| r1 | REVISE | 1 major | Added the FROZEN-K4S runtime-byte constraint. |
| r2 | REVISE | 1 major, 2 minor | Split old-SHA END recovery into two cases; scoped the blinding claim and the external-state wording. |
| r3 | **APPROVE** | 1 non-blocking minor | Applied after approval, as the reviewer's own suggested wording only: case (i) now reads "not valid for authorized END/Mac use". |

r3 independently measured the Mac suite at 95 passed / 1 failed and the END suites at 103 passed.
