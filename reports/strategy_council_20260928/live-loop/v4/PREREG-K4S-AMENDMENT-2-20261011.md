# PREREG-K4S Amendment 2: re-pin `tier_backend.py` and add `state_rows.py` after TIERS A3 (outcome-blind)

- **Recorded:** 2026-10-11T22:15:42Z (`date -u`), by the implementation worker on 127x05, under authorization of coordinator thread 0523ae6f (COORDINATOR.md commit 4ccbdd4f, 22:07 UTC entry, execution item 2: "K4S Amendment 2 re-pins `tier_backend.py` and adds `state_rows.py` in the K4S Mac manifest, with Sol review").
- **Study:** PREREG-K4S, frozen at 391d2006 (fill fab6e03f; freeze record json `478068b6…` / md `24623ff8…`), amended once before: [K4S Amendment 1](PREREG-K4S-AMENDMENT-1-20261011.md) (45f32c0f; md `e01f11b6…` / json `79b92686…`).
- **Base tree:** origin/main 4ccbdd4f (TIERS Amendment 3 merged at f6cebbaa and adopted).
- **Machine record:** `PREREG-K4S-AMENDMENT-2-20261011.json`, in this directory.

## 1. Outcome-blind status

This amendment is **outcome-blind**. It was written without reading any K4S confirmatory outcome or reporting receipt, and without reading any TIERS or T1 game outcome. Its only input is a byte change to reused read-only TIERS code, made by TIERS Amendment 3, which is itself outcome-blind. Its content is fully determined by that byte change, by the import graph of the new TierBackend, and by the manifest builder.

**Blinding disclosure.**
- **Author:** the author opened no K4S confirmatory receipt or outcome. Reading COORDINATOR.md for the A3 adoption entry also showed operational K4S fleet status lines (completed/lost block counts, apt/motd guard stops, replacement-round rulings). Those are operational counts with no game result. Running `rebind.py verify` printed the *file names* of `run-r1/health/*.json` receipts; none was opened. The A1 record read as a template quotes the frozen design input c\* = 0.9.
- **Reviewer:** every Sol round ran under an explicit outcome-blind read boundary that excludes `run-r1/`, `end/`, every receipt directory and any game outcome.

None of this can affect a mechanically determined re-pin.

## 2. Cause: TIERS Amendment 3

TIERS Amendment 3 ([record](PREREG-SEARCH-TIERS-AMENDMENT-3-20261011.md), md `761ebc0d…` / json `3e5627cb…`; Sol APPROVE r4, [review](TIERS-AMENDMENT-3-REVIEW-SOL.md) `18baa4ea…`) is merged at f6cebbaa and was adopted at 22:07 UTC.

- **The change that matters to K4S:** `e4v3/tier_backend.py` goes from `b04d201de7a95a36669e5c11898a297ba8f324d1a658f2987ec5ba244671add7` to `02e2139f9ddc6e795e8e102f278ccd5cc53363c55d8a90288b4715adb724ca1d`. `TierBackend.__init__` now imports the new `e4v3/state_rows.py` (`3899276bb99a8b29c6777cf8b476440bee1c1c493612a97539550d2e35bbf755`) and reads the fixture one state at a time.
- **Condition 5 of A3** requires this companion re-pin and the `state_rows.py` addition under independent Sol review.
- **The failure:** the K4S Mac manifest `8bb20a75…` pins `tier_backend.py` `b04d201d…` under `reused_readonly`. On any post-A3 tree, `k4s_logic.load_k4s_manifest` → `verify_pinned` raises `PreconditionRefusal: Pin mismatch (reused read-only TIERS files): …/tier_backend.py`, so every K4S Mac session and every END step fails closed. `K4SBackend` subclasses `TierBackend`, so the old pin cannot be kept.

## 3. K4SBackend compatibility with the Amendment 3 TierBackend

**Verdict: COMPATIBLE. No K4S code change is needed or made.** I read `mac/k4s_backend.py`, `mac/k4s_logic.py`, `mac/measure_k4s.py`, `end_reference.py`, `end_background.py` and `end_pool.py` against the 02e2139f `TierBackend`. Nothing in K4S needs `self.rows`, `self.inputs` or `by_id` fully materialized.

**What A3 changed in `TierBackend`:** only `dry_opening_orders`, `__init__` (now `_load_inputs`), `close()` and `validate_bundle`. The views it introduces:
- `rows` is a stream;
- `by_id` is a one-state cache, where a miss loads that state and evicts the previous one;
- `inputs` is kept only for `sets.agreement`, or for every row in a Linux dry run.

Every decision method K4S calls is byte-unchanged: `prepare_work`, `configure`, `policy_input`, `check_d1`, `work`/`_work`, `core`, `activate` and `infer`.

| K4S use | Where | Behaviour under A3 |
|---|---|---|
| `super().__init__(bundle, runtime_root, native)`, then K4S unpickles its **own** 300-state corpus into `self.k4s_rows` | `k4s_backend.py` | Unaffected. K4S never reads `self.rows`, `self.inputs` or `self.openings`. |
| `k4s_work(row)` → `prepare_work` / `configure` / `policy_input(verify=False, tracker_state=…)` / `check_d1` on `k4s_rows` | `k4s_backend.py` | Byte-unchanged methods on K4S's own rows. Production rows must carry `d1_before`, so `openings` is used only in the dry-run legacy path, where A3 computes it with the same result. |
| K1–K4: corpus exactness, loaded speed, deadline corpus | `measure_k4s.Measurements` | Only `backend.k4s_rows[...]`, so there is no fixture lookup. |
| SD1 agreement: `backend.infer(identity, "cpu")` for `bundle["sets"]["agreement"][:limit]` | `measure_k4s.Measurements.sd1_agreement` | Exactly the retained set. The bundle is validated by the same `validate_bundle`, and in a dry run every input is retained. |
| K5/K6: `row = backend.by_id[packet["id"]]`, then `prepare_work(row)`, then `wait_until(due)`, then `k4s_work` | `measure_k4s.PacketDecisions.run` | A single-id lookup. A miss loads that one state **before** `wait_until`, outside the timer. The row is bound to a local, so eviction is harmless, and `prepared_work` matches by id. |
| END (a)–(c): `be.work(row, 'K4')`, `be.k4s_work(row)`, `prepare_work` before `entered` | `end_reference.measure` | Only `be.k4s_rows`. |
| END background: `backend.work(backend.by_id[identity], tier)` | `end_background.py:101` | A single-id lookup as the argument of `work()`, the same pattern A3 audited for `FleetBackground`. |
| `close()` | inherited | Now also releases the state-rows descriptor. `Session.close` and the END cleanup already call it. |

**Disclosed residuals, inherited from A3; no change is made here:**
1. **K5/K6 pre-arrival load time.** A heavy fixture state (05: lookup p99 0.22 s, max 0.31 s) can make `entered` later than `scheduled`. The 200 ms budget still starts at `entered`. K4S gate 5 uses the frozen `receipts.gc_summary`, which counts a late poll only when a GC event spans the scheduled instant.
   - A3-P (the all-cause poll-lateness check) is a TIERS adoption condition. This amendment does **not** add a K4S analogue, because that would be a gate change.
   - **Open item for the coordinator:** decide whether K4S K5/K6 should report the same all-cause lateness descriptively.
2. **Heap and GC.** The K4S main process still holds its own K4S corpus objects, so A3's reduction in GC traversal applies only to the TIERS fixture part.
   - No pre-A3 K4S Mac receipt exists to compare against. Per COORDINATOR.md, Phase C has not run.
3. **Descriptor on a failed constructor.** If `K4SBackend.__init__` fails after `super().__init__`, the read-only descriptor stays open until the process exits. Examples are a K4S corpus SHA mismatch, a duplicate state, or a kernel that fails to load. This is a fail-closed refusal path and has no measurement effect.
4. **K6 GC labels** (A3 residual 1, D8 analogue). `PacketDecisions.run` looks up the first row of a variant (`measure_k4s.py:144`) before it sets that variant's trace context (`measure_k4s.py:147`). GC triggered while that first state loads is therefore labelled with the previous trace context.
5. **END background duty cycle and I/O** (A3 residuals 3 and 4). `end_background.py:101` now loads each state (`pread`, SHA-256, unpickle) before the search, on the slot's own pinned cores, so background slots spend part of their time loading rather than searching. They stay CPU-busy, and the frozen MHz comparison still applies. Bundles also carry `states-rows.bin`, and `validate_bundle` hashes it at start and end, which adds storage and I/O.

**K4S's own Mac memory footprint (recorded, not changed).** `K4SBackend.__init__` still runs `pickle.loads(Path(corpus).read_bytes())` on the frozen T1 K4 corpus `a97b1fbf…`. A local copy on 05 (`/mpac/sdicks02/jobs/clasher/t1-20261010-r1/corpus-publication-staging-r1/K4-states.pkl`; size only, not re-hashed) is 2,829,766,847 bytes (2.64 GiB on disk). A3 estimates about 3 GiB resident and about 6 GiB peak during construction (the bytes and the objects at once). That is K4S's own memory on top of:
- the amended TierBackend, which A3 measured at 0.37–0.41 GiB RssAnon and ≤0.87 GiB peak on the 1,325-row END fixture; this was not measured on the Mac fixture;
- the replay-load worker's own amended TierBackend;
- torch and the models.

The Mac has 24 GiB unified memory with only about 1 GiB free at idle (coordinator figure). **This is a Mac-session risk for Phase C.** It is not measured here (no Mac contact) and not changed: changing K4S's corpus load would be a K4S code change and a larger amendment.

## 4. The manifest change

| | Path | SHA-256 |
|---|---|---|
| Frozen F-8 at 391d2006 | `reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json` | `d89cab16afdffa88d30e61eb1f4daea74e046703994f6aee7e74bfedc8d08f40` |
| After Amendment 1 (45f32c0f) | same path | `8bb20a753bdb8f5f606ea2288336b1350f96a5199d158b2b8750317c26493009` |
| **After Amendment 2** | same path | **`c1fb1e9acb71a69d406c04d5a040dae734aa8fda57cae58f4f56363b591815de`** |

**Exactly three leaves differ** (77 → 78 leaf keys):

| Key | Old | New |
|---|---|---|
| `reused_readonly[…/e4v3/tier_backend.py]` | `b04d201d…` | `02e2139f9ddc6e795e8e102f278ccd5cc53363c55d8a90288b4715adb724ca1d` |
| `reused_readonly[…/e4v3/state_rows.py]` | absent | `3899276bb99a8b29c6777cf8b476440bee1c1c493612a97539550d2e35bbf755` |
| `k4s_files[reports/explore/k4s-confirm/mac/build_manifest.py]` | `26932fa87d9638c080c0d1611b2c2f73c5401ae8ac424b863474a42c7d75f449` | `2e255fb939c2b1720749a8a38e99a4a66e397f1149f4d63f7a24d62cb82343f7` |

**Why the builder's own pin moves.** The manifest must be regenerated by its builder, and `test_manifest_is_current_and_measure_tiers_unmodified` asserts `on_disk == build_manifest.build(...)`. Adding a reused pin therefore requires adding the file to the builder's `E4V3_REUSED` list, and `build_manifest.py` is itself pinned in `k4s_files`. The builder diff is data only: one comma, one comment line and `"state_rows.py"` appended to that tuple. No logic changes.

```
-               "fleet_end.py", "fleet_profile.py", "fleet_validity.py", "fleet_pool.py", "fleet_reference.py")
+               "fleet_end.py", "fleet_profile.py", "fleet_validity.py", "fleet_pool.py", "fleet_reference.py",
+               # TIERS Amendment 3: TierBackend.__init__ imports state_rows (K4S Amendment 2)
+               "state_rows.py")
```

`build_manifest.py` is not an END measurement source (`k4s_logic.END_MEASUREMENT_FILES`). The END frozen pins (`end_frozen_pins`) therefore change **only** in `k4s_manifest_sha256`.

**Which files K4S now imports through TierBackend.** I checked this by reading the code, and a new regression test checks it mechanically with an AST import closure that includes lazy imports. From `tier_backend.py` the e4v3-local closure is {`tier_backend.py`, `receipts.py`, `corpus_contract.py`, `state_rows.py`}, and `state_rows.py` imports stdlib only. `state_rows.py` is the only new member, and all four are now pinned.

Not pinned, by design:
- **`convert_states.py` (7ce30683):** the one-time Linux converter. Neither K4S, TierBackend nor `state_rows` imports it, and A3 condition 4 says the Mac never converts.
- **`prepare_bundle.py` (a1c59fa3):** a staging tool that no K4S runtime path imports. It was not pinned before either; its bytes for staging are bound by A3 condition 1.

**How the file was produced:** I regenerated it mechanically with the builder on the 4ccbdd4f tree plus the builder edit. Nothing in the JSON was edited by hand:

```
python -B reports/explore/k4s-confirm/mac/build_manifest.py --root <tree> \
  --kernel reports/explore/k4s-confirm/anchor_x.py --kernel reports/explore/k4s-confirm/sdefault.py --freeze
```

**Verification:**
- **Leaf diff:** a key-by-key comparison shows exactly the three leaves above; `git diff` shows 2 changed lines and 1 added line.
- **Freeze status:** `frozen` is still `true` and `status` is still `"FROZEN"`.
- **No other pin moved:** I hashed all 40 distinct file pins of `8bb20a75` against 4ccbdd4f, and only `tier_backend.py` mismatched.
- **Unchanged pins:**
  - `measure_tiers_unmodified` (`6066228b…`);
  - the kernel (`sdefault.py` `0448db50…`, `anchor_x.py` `cf528473…`), the scorer, and the SD1 manifest `b8ce7b4c…`;
  - the corpus, native provenance and references;
  - every `end_files` pin, every other `k4s_files` pin and every other `reused_readonly` pin.
- **Behaviour check:**
  - `load_k4s_manifest(new, c1fb1e9a…, <tree>, require_frozen=True)` succeeds.
  - The same call on `8bb20a75` refuses with `Pin mismatch (K4S Mac files): …/build_manifest.py`. `tier_backend.py` would fail next.

## 5. Tests

I ran `nice -n 19 taskset -c 63 /mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q -p no:cacheprovider …` on Python 3.12.12, on 127x05.

| Tree | K4S Mac suite (`reports/explore/k4s-confirm/mac`) | END (`test_end_reference.py`, `test_end_background.py`) |
|---|---|---|
| After A1 (as recorded) | 95 passed / 1 failed (96) | 103 passed |
| 4ccbdd4f, before this amendment | **89 passed / 7 failed (96)** | 103 passed |
| After the re-pin, existing tests | **95 passed / 1 failed (96)** | **103 passed** |
| After the re-pin, with the new regression file | **98 passed / 1 failed (99)** | 103 passed |

**Failures at 4ccbdd4f before the amendment.** Six are caused by A3, through the `tier_backend.py` pin mismatch:
- `test_manifest_is_current_and_measure_tiers_unmodified`
- `test_cli_refuses_uncommitted_tiers_receipts`
- `test_cli_refuses_without_tiers_completion_receipt`
- `test_cli_refuses_bad_tiers_sha_and_standalone_without_authorization`
- `test_cli_refuses_incomplete_tiers_session`
- `test_cli_tiers_exactness_failure_writes_no_measurement_summary`

The seventh, `test_manifest_loader_rejects_draft_for_mac_and_tamper`, is the known by-construction failure: it asserts `frozen is False` on the committed manifest. It is the **only** failure left after the re-pin.

**New regression file:** `mac/test_k4s_amendment2.py`, SHA `16fcb2bbc15c80cea8f69cb377f0a52bb622f9aed7a66a43f45b2ca4247d36d1`. It holds three tests:
- `test_verify_pinned_accepts_amended_tier_backend_and_state_rows_and_rejects_old`: the committed manifest carries `02e2139f…` and `3899276b…`; the builder lists `state_rows.py`; `verify_pinned` accepts both against the live tree and refuses the old `b04d201d…` pin.
- `test_every_e4v3_module_reachable_from_tier_backend_is_pinned`: the AST import closure from `tier_backend.py` is a subset of `reused_readonly`.
- `test_backend_consumers_use_only_single_id_lookups`: `k4s_backend.py`, `measure_k4s.py`, `end_reference.py` and `end_background.py` never read `.rows`, `.inputs`, `.openings` or `.state_rows`, and use `.by_id` only as a subscript.

With the old `8bb20a75` manifest restored, the first two tests fail and the third passes.

The file is **new and unpinned**, as in Amendment 1. `test_measure_k4s.py` is pinned in `k4s_files` (`edd6956b…`) and was not edited.

## 6. Effect and scope

**What this amendment does NOT affect:**
- **The K4S fleet game run on {127x03, 127x04}.** FROZEN-K4S.json `416f6e51…` pins no e4v3 file. It does list:
  - `mac/K4S-MAC-MANIFEST.json` = `d89cab16…` and `mac/build_manifest.py` = `26932fa8…`, i.e. the 391d2006 bytes;
  - `REPORTING-AUTHORIZATION` `freeze_commit` = 391d2006.

  Fleet reporting stays on the **d89cab16 / 391d2006 bytes**. Its job runtime trees must keep those original bytes for both files. Deploying main's `mac/` (`c1fb1e9a…` manifest, `2e255fb9…` builder) into a fleet runtime would block reporting admission (`barrier.py:51`). Do not list `mac/test_k4s_amendment1.py` or `mac/test_k4s_amendment2.py`. The A1 rules on separating the fleet runtime from the Mac/END runtime apply unchanged.
- **Everything else frozen:** arms, cells, seeds, N, hypotheses H1–H4, gates, margins, alpha, SD1 (manifest `b8ce7b4c…`, R3a bytes), c\* = 0.9, the K4S kernel and scorer, the corpus, the native binary, DELTA-MANIFEST deltas and every other frozen file. No frozen decision rule changes.

**What it does affect.** The K4S Mac manifest of record becomes **`c1fb1e9a…`** for **Mac sessions and for every END step that loads the K4S manifest**. It supersedes `8bb20a75…` (A1) for that use.

- **Mac sessions.**
  - Pass `--k4s-manifest-sha256 c1fb1e9acb71a69d406c04d5a040dae734aa8fda57cae58f4f56363b591815de`.
  - The runtime tree must hold A3's `tier_backend.py` `02e2139f…` and `state_rows.py` `3899276b…`, i.e. main at or after the commit carrying this amendment.
  - The TIERS Mac bundle the session reuses must pin `states-rows.json` and `states-rows.bin`, which A3's `validate_bundle` now requires. Per A3 condition 4, it is staged with `prepare_bundle.py --state-rows`, and the Mac never converts.
- **END producer and pooler.** `end_reference.k4s_pins`, `end_pool.pool_context` and `end_background.frozen_helpers` all load the K4S manifest with `require_frozen=True`, which verifies every pin, including the two new ones. The Mac checks the reference's `pins.k4s_manifest_sha256` against its own manifest SHA (`check_end_pins`). Therefore:
  - the K4S **END-JOB declaration's `k4s_manifest_sha256`**, the END pool descriptor's `k4s_manifest.sha256` and every `end_reference.py --k4s-manifest-sha256` must name **`c1fb1e9a…`**;
  - each must run from an amended runtime holding A3's bytes.
  - **No committed END work on the checked tree:** no `END-JOB.json` exists on 4ccbdd4f, and COORDINATOR.md shows no K4S END window declared. External job state was not inspected (no ssh).
  - **Bundles:** each K4S END fleet-reference bundle must also pin `states-rows.json` / `states-rows.bin`, prepared with A3's `prepare_bundle.py --state-rows` and never patched. Per A3 condition 2, hosts that share a fixture use byte-identical container copies. K4S's cross-host `bundle_model_files` compares `states.pkl` but not the container; each container is SHA-bound to that `states.pkl` and to per-row SHAs.
  - **Old references:** no END-JOB exists on the checked tree (4ccbdd4f); external job state was not inspected. A K4S END reference produced under `8bb20a75…` or on `b04d201d` bytes cannot serve an amended Mac session. The A1 §5 recovery cases apply with `c1fb1e9a…` in place of `8bb20a75…`:
    - **(i) Without a committed END-JOB** (a dev or dry run, outside valid END authority): it is not valid for authorized END/Mac use. Exclude it from the reporting reference and produce it fresh under an END-JOB naming `c1fb1e9a…`, from the amended tree.
    - **(ii) Bound to any externally discovered committed END-JOB naming an earlier manifest SHA** (`d89cab16…` or `8bb20a75…`): the declaration is append-only (`end_evidence.immutable`), and `end_evidence.end_job` refuses a different `k4s_manifest_sha256`. A coordinator disposition and an explicitly authorized END-authority migration are required before any amended re-run. This amendment does not implement one, and the immutable declaration must not be edited, replaced or patched.
- **Records not edited:**
  - `DELTA-MANIFEST.json`, which still records `mac/build_manifest.py` `26932fa8…` and the manifest `d89cab16…`;
  - `FREEZE-RECORD-SKELETON.md`, the freeze record and the Amendment 1 record;
  - `run-r1/addendum/K4S-LAUNCH-ADDENDUM.{md,json}`, which names `8bb20a75…` as the amended manifest.

  They describe earlier states and are superseded for Mac/END use only. `rebind.py verify` on main now additionally reports `mac/build_manifest.py` (sha changed) and `mac/test_k4s_amendment2.py` (present but not in manifest). It is a prep-time classifier, not a runtime gate, and `end_reference.py` reads DELTA-MANIFEST only for the unchanged kernel/scorer rows.

## 7. Files

**Changed:**
- `reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json`: `8bb20a75…` → `c1fb1e9a…`.
- `reports/explore/k4s-confirm/mac/build_manifest.py`: `26932fa8…` → `2e255fb9…` (data only: `state_rows.py` added to `E4V3_REUSED`).

**Added:**
- `reports/explore/k4s-confirm/mac/test_k4s_amendment2.py` (`16fcb2bb…`)
- this record and its JSON
- `reports/explore/k4s-confirm/reviews/SOL-REVIEW-K4S-AMENDMENT-2-r*.md`

**Review:** GPT-6.1-Sol at high reasoning effort. Results are recorded below and in the JSON.

| Round | Verdict | Findings | Resolution |
|---|---|---|---|
| r1 | **APPROVE** | 2 non-blocking minors | Documentation only, applied after approval: §3 residuals 4 (K6 GC labels) and 5 (END background duty cycle and I/O) added; §6 old-reference text scoped to the checked tree, with the A1 cases (i) and (ii) restated. |
| r2 | **APPROVE** | none | Confirmation round: both r1 minors resolved accurately and consistently in md and json; manifest, builder and test bytes unchanged since r1. |

r1 independently regenerated the manifest byte-identically (`c1fb1e9a…`), confirmed the three changed leaves and the import closure, and measured the Mac suite at 98 passed / 1 failed (89 / 7 on the pre-amendment overlay) and the END suites at 103 passed.
