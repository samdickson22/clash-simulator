# PREREG-K4S Amendment 3 (DRAFT): re-pin `fleet_validity.py` after TIERS A5 (outcome-blind)

- **Status: DRAFT for review. Not adopted.** Nothing in this draft is in force until the coordinator adopts it. No host action was taken for it.
- **Drafted:** 2026-10-12T04:56Z (`date -u`), by the K4S run-r1 runner on 127x05, at the request of coordinator thread 0523ae6f ("TIERS Amendment 5 is adopted (COORDINATOR 46ab6923, main 8799a0d6) … please draft K4S Amendment 3 … Keep it as a draft only, with no host actions").
- **Study:** PREREG-K4S, frozen at 391d2006 (fill fab6e03f), amended by [Amendment 1](PREREG-K4S-AMENDMENT-1-20261011.md) (45f32c0f) and [Amendment 2](PREREG-K4S-AMENDMENT-2-20261011.md) (f231fbcb).
- **Base tree:** origin/main 13c3dbe4 (TIERS Amendment 5 merged at 8799a0d6, adopted at 46ab6923).
- **Machine record:** `PREREG-K4S-AMENDMENT-3-20261012.json`, in this directory.

## 1. Outcome-blind status

This amendment is **outcome-blind**. Its only input is a byte change to reused read-only TIERS code (`e4v3/fleet_validity.py`), made by TIERS Amendment 5, which is itself outcome-blind. Its content is fully determined by that byte change and by the frozen manifest builder.

**Blinding disclosure.**
- **Author:** the author is also the K4S run-r1 runner. In that role they see sealed operational counts only (completed/acked/failed blocks, ledger event counts, stop causes); the runner's tools never read a game outcome, and none was read for this draft. No K4S, TIERS or T1 game outcome, contrast or reporting result was opened. `E4-GUARD-RACE-FIX-IMPACT-20261012.md` was read for its binding inventory (§2c, §4); it reports guard failure signatures (`foreign_compute`) and timings, not game outcomes.
- **Reviewer:** any review round should run under the A2 read boundary (exclude `run-r1/` receipts and health, `end/`, every receipt directory and any game outcome).

## 2. Cause: TIERS Amendment 5

TIERS Amendment 5 (draft record `PREREG-SEARCH-TIERS-AMENDMENT-5-DRAFT-20261012.md`, merged at 8799a0d6, adopted at COORDINATOR 46ab6923; Sol r3 APPROVE) fixes a census-ownership race in the E4 reporting guard.

- **The change that matters to K4S:** `e4v3/fleet_validity.py` goes from `94d0e7f2c20bfc139f5d95ccefb375f52293a06c2c78bee84e9442fc62bcb0ae` to `0775b704905324d70f9a43bc580bcbba1548cb2d2a4835c84ff61a0d8b64ae0f`.
- **The race:** `ReportingGuard` built its owned set from one `/proc` snapshot, but `host_audit.census` rescans `/proc`. Own descendants that first appeared in the rescan (spawn workers started right after admission) were counted as foreign. On a host whose admit census is slow (127x08: 1.24 s), the first sample after admission failed with `foreign_compute`. T1's E4 08 r2 and r3 failed exactly this way.
- **The fix (21 lines):**
  - `owned_tree(rows, roots, known, pinned=None, keys=())` gains two optional parameters: a row whose pinned identity changed is neither owned nor grants children. The defaults keep the old behaviour.
  - After the census, `ReportingGuard` re-derives ownership on the rescanned rows under the same `start_ticks` and identity rules, adds late own descendants, and recomputes `foreign` / `active` with the frozen classifier.
- **Why K4S needs it:** K4S END's reference (`end_reference.py:295,334`) starts the frozen `fleet_reference.reference_monitor`, which constructs `fleet_validity.ReportingGuard(bundle, manifest, owned)` (`fleet_reference.py:237-239`), and then starts `K4SFleetBackground` with 10 spawn workers right after `checkpoint("admit")`. That is the E4 pattern, so the K4S END reference inherits the race (impact note §1, §4). The coordinator holds K4S END until this is ruled on (92acdf02).
- **The failure without this amendment:** on the A5 tree, the K4S Mac manifest `c1fb1e9a…` pins `fleet_validity.py` `94d0e7f2…` under `reused_readonly`. `k4s_logic.load_k4s_manifest` → `verify_pinned` raises `PreconditionRefusal: Pin mismatch (reused read-only TIERS files): …/fleet_validity.py`. Every K4S Mac session and every END step (`end_reference.k4s_pins`, `end_pool.pool_context`, `end_background.frozen_helpers`) fails closed. Keeping the old pin would mean running K4S END on a runtime with the known-racy guard, which A5 R5(a)/T12 advises against.

## 3. Compatibility

**Verdict: COMPATIBLE. No K4S code change is needed or made.**

| K4S use of `fleet_validity` | Where | Under A5 |
|---|---|---|
| `ReportingGuard`, via the frozen `fleet_reference.reference_monitor` | `end_reference.py:295,334` | This is the fixed code. The constructor signature `ReportingGuard(bundle, manifest, owned)` is unchanged; K4S passes nothing new. |
| `FleetTechnicalError` | `end_reference.py:293` | Unchanged. |
| `validate_census`, `validate_admission`, `validate_blocks(…, require_measurement=False)` | `end_reference.py:396-399`, `end_pool.py:343-347` | Byte-unchanged functions. |
| `classify_attempt` | `end_pool.py:296` | Byte-unchanged. |
| `FROZEN_HELPERS` pin check against the K4S manifest | `end_pool.py:65,214`, `end_background.frozen_helpers` | Verifies the new pin once the manifest names `0775b704…`. |
| `owned_tree` | not called by K4S | The new parameters are optional with backward-compatible defaults. |

The END test suites (`test_end_reference.py`, `test_end_background.py`) pass unchanged on the A5 tree (§5).

## 4. The manifest change

| | Path | SHA-256 |
|---|---|---|
| Frozen F-8 at 391d2006 | `reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json` | `d89cab16afdffa88d30e61eb1f4daea74e046703994f6aee7e74bfedc8d08f40` |
| After Amendment 1 (45f32c0f) | same path | `8bb20a753bdb8f5f606ea2288336b1350f96a5199d158b2b8750317c26493009` |
| After Amendment 2 (f231fbcb) | same path | `c1fb1e9acb71a69d406c04d5a040dae734aa8fda57cae58f4f56363b591815de` |
| **After Amendment 3 (this draft)** | same path | **`74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357`** |

**Exactly one leaf differs** (78 leaf keys before and after):

| Key | Old | New |
|---|---|---|
| `reused_readonly[reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/fleet_validity.py]` | `94d0e7f2c20bfc139f5d95ccefb375f52293a06c2c78bee84e9442fc62bcb0ae` | `0775b704905324d70f9a43bc580bcbba1548cb2d2a4835c84ff61a0d8b64ae0f` |

**The builder does not change.** `fleet_validity.py` was already in `build_manifest.E4V3_REUSED`, so `build_manifest.py` stays `2e255fb9…` (A2) and its own `k4s_files` pin does not move. `fleet_validity.py` is not an END measurement source (`k4s_logic.END_MEASUREMENT_FILES`), so the END frozen pins change **only** in `k4s_manifest_sha256`.

**How the file was produced:** regenerated mechanically by the frozen builder on the A5 tree. Nothing in the JSON was edited by hand:

```
python -B reports/explore/k4s-confirm/mac/build_manifest.py \
  --kernel reports/explore/k4s-confirm/anchor_x.py --kernel reports/explore/k4s-confirm/sdefault.py --freeze
```

**Verification:**
- **Leaf diff:** a key-by-key comparison against `c1fb1e9a…` shows exactly the leaf above; `git diff` shows 1 changed line.
- **Freeze status:** `frozen` is still `true` and `status` is still `"FROZEN"`.
- **No other pin moved:** every other `reused_readonly` pin, every `k4s_files` and `end_files` pin, `measure_tiers_unmodified` (`6066228b…`), the kernel, the scorer, the SD1 manifest `b8ce7b4c…`, the corpus, native provenance and references all verify on 13c3dbe4. The new regression test checks the `reused_readonly` part mechanically.
- **Behaviour:** `verify_pinned` accepts `0775b704…` on the A5 tree and refuses `94d0e7f2…` with `Pin mismatch … fleet_validity.py`.

## 5. Tests

`nice -n 19 taskset -c 63 /mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q -p no:cacheprovider …`, Python 3.12.12, on 127x05, tree 13c3dbe4.

| Tree | K4S Mac suite (`mac/`, incl. the new file) | END (`test_end_reference.py`, `test_end_background.py`) |
|---|---|---|
| 13c3dbe4 with the A2 manifest `c1fb1e9a…` | **94 passed / 8 failed (102)** | not re-run |
| 13c3dbe4 with the A3 manifest `74314eda…` | **101 passed / 1 failed (102)** | **103 passed** |

**Failures with the A2 manifest on the A5 tree:**
- six caused by the `fleet_validity.py` pin mismatch: `test_manifest_is_current_and_measure_tiers_unmodified`, `test_cli_refuses_uncommitted_tiers_receipts`, `test_cli_refuses_without_tiers_completion_receipt`, `test_cli_refuses_bad_tiers_sha_and_standalone_without_authorization`, `test_cli_refuses_incomplete_tiers_session`, `test_cli_tiers_exactness_failure_writes_no_measurement_summary` (the same six A2 recorded for its own pin);
- the new `test_verify_pinned_accepts_amended_fleet_validity_and_rejects_old`;
- the known by-construction `test_manifest_loader_rejects_draft_for_mac_and_tamper`, which asserts `frozen is False` on the committed manifest. It is the **only** failure after the re-pin.

**New regression file:** `mac/test_k4s_amendment3.py`, SHA `5f41d93ddb2c7e1db38502735af0973c6519cf5f70ba51ed616a6e9054d5c1c7`, three tests:
- `test_verify_pinned_accepts_amended_fleet_validity_and_rejects_old`: the committed manifest carries `0775b704…`; the builder lists `fleet_validity.py`; `verify_pinned` accepts the new pin and refuses `94d0e7f2…`.
- `test_every_other_reused_pin_unchanged_from_amendment_2`: every other `reused_readonly` pin verifies on the amended tree.
- `test_fleet_reporting_runtime_never_imports_fleet_validity`: `run.py`, `supervise.py`, `host_audit.py`, `launch.sh` and `runtime.sh` never name `fleet_validity`; among the top-level K4S `.py`/`.sh` files, only the END modules and their tests name `fleet_validity` or `e4v3`.

The file is new and unpinned, as in A1 and A2. No pinned test was edited.

## 6. K4S artifacts that bind `fleet_validity.py` `94d0e7f2`

Searches: `git grep 94d0e7f2`, `git grep fleet_validity`, `git grep -E 'c1fb1e9a|8bb20a75|d89cab16'` over `reports/explore/k4s-confirm` and the K4S records on 13c3dbe4, plus the runner's local directory `/mpac/sdicks02/k4s-runner/run-r1/`.

**Direct pins (by SHA):**

| Artifact | SHA-256 (commit) | Disposition |
|---|---|---|
| `mac/K4S-MAC-MANIFEST.json`, the A2 manifest of record for Mac/END | `c1fb1e9a…` (f231fbcb) | **Re-pinned by this amendment** → `74314eda…` |
| Earlier versions of the same file: `d89cab16…` (391d2006), `8bb20a75…` (45f32c0f), and the pre-freeze `781d25ba…` (247ef6d4), `4c25d454…` (962ecce2) | historical | Not edited. `d89cab16` stays the fleet reporting manifest (below). |

**Indirect bindings (they bind a manifest SHA that pins `94d0e7f2`):**

| Artifact | Binds | Disposition |
|---|---|---|
| `run-r1/oa1/FROZEN-K4S.json` `416f6e51…` (6ac7b641), and `run-r1/candidates/oa1/FROZEN-K4S.json` | manifest `d89cab16` (line 83), builder `26932fa8` (line 86); no e4v3 file listed | **No change.** Frozen job manifest of the running reporting. |
| `run-r1/receipts/REPORTING-AUTHORIZATION*.json`, `reporting-launch-receipt.json`, `replacement-r1-launch-receipt.json` | FROZEN-K4S `416f6e51` / freeze 391d2006; the r1 launch receipt cites `c1fb1e9a` as the A2 Mac/END manifest | No change; operational receipts of the running reporting. |
| `run-r1/addendum/K4S-LAUNCH-ADDENDUM.{md,json}`, `make_addendum.py` | `d89cab16` (fleet), `8bb20a75` (A1 Mac/END) | Not edited; historical. |
| `DELTA-MANIFEST.json` (391d2006), `FREEZE-RECORD-SKELETON.md`, `PREREG-K4S-FREEZE-20261011.{md,json}` and its Opus check | `d89cab16` | Not edited; historical. |
| `PREREG-K4S-AMENDMENT-1-20261011.{md,json}`, `PREREG-K4S-AMENDMENT-2-20261011.{md,json}`, `mac/test_k4s_amendment1.py`, `mac/test_k4s_amendment2.py`, `reviews/SOL-REVIEW-K4S-AMENDMENT-{1,2}-r*.md` | `8bb20a75` / `c1fb1e9a` | Not edited; superseded for Mac/END use only. Both test files still pass on the amended manifest (they check their own leaves). |
| `run-r1/PROGRESS.md` | names `94d0e7f2` in a runner note | Text only; not a pin. |
| `end_reference.py` `5cb4751e`, `end_pool.py` `069c22e7`, `end_background.py` `a872bd2d`, `end_evidence.py` | `FROZEN_HELPERS` verified against the K4S manifest **by module, not by SHA** | No code change; they follow the manifest of record. |
| `mac/build_manifest.py` `2e255fb9` | lists `fleet_validity.py` in `E4V3_REUSED` (no SHA) | No change; re-run with `--freeze`. |
| **External:** K4S END-JOB declaration, END pool descriptor, END reference bundles | — | **None exists.** No `END-JOB.json` on 13c3dbe4, and K4S END has never been declared or run (held, 92acdf02). The END corpus copy on 03 (`k4s-confirm-r1/end-corpus/`) holds only `K4-states.pkl` and `corpora.json`, no code. |

## 7. Effect and scope

**What this amendment does NOT affect: the K4S fleet reporting running on {127x03, 127x04}.**
- It runs `launch.sh` → `runtime.sh reports/explore/k4s-confirm/supervise.py` and `run.py` from the 391d2006 overlay. At 391d2006, `git grep -E 'fleet_validity|e4v3'` over `reports/explore/k4s-confirm` hits only `END-RUNBOOK.md`, `end_*.py`, `test_end_*.py`, `mac/*` and reviews, never the reporting path. `supervise.py` imports only K4S's own frozen copies of the T1 guard modules.
- Its frozen job manifest `FROZEN-K4S.json` `416f6e51…` lists no e4v3 file. It binds `K4S-MAC-MANIFEST` `d89cab16…`, which keeps pointing at `94d0e7f2…` and is **not** re-pinned. This is the A2 precedent: the fleet keeps `d89cab16`; Mac/END name the amended manifest.
- Its runtime trees must keep the 391d2006 bytes of `mac/K4S-MAC-MANIFEST.json` and `mac/build_manifest.py`. Deploying main's `mac/` into a fleet runtime would block reporting admission (`barrier.py:51`). Do not list `mac/test_k4s_amendment{1,2,3}.py` there.
- The P2 replacement cycles (next cut ~08:40Z) stage the same frozen overlay and are unaffected.
- **No host action is taken or required.**

**Everything else frozen is unchanged:** arms, cells, seeds, N, hypotheses H1–H4, gates, margins, alpha, SD1, c\* = 0.9, the kernel and scorer, the corpus, the native binary, DELTA-MANIFEST deltas and every other frozen file. No frozen decision rule changes.

**What it does affect, once adopted.** The K4S Mac manifest of record for **Mac sessions and every END step** becomes **`74314eda…`**, superseding `c1fb1e9a…` (A2) for that use.
- **Mac K4S sessions:** pass `--k4s-manifest-sha256 74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357`, from a runtime holding `fleet_validity.py` `0775b704…` (main at or after the adopting commit). Per A5 T12, no Mac session runs on a runtime holding `94d0e7f2`.
- **END:** the K4S END-JOB declaration's `k4s_manifest_sha256`, the END pool descriptor's `k4s_manifest.sha256` and every `end_reference.py --k4s-manifest-sha256` must name **`74314eda…`**, and each must run from an amended runtime. Because no END-JOB exists, A2 §6 case (ii) (an immutable declaration naming an earlier SHA) does not arise. Any dev or dry-run END output made on `94d0e7f2` bytes is not valid for authorized END use (A2 §6 case (i)).
- **K4S END stays held.** This amendment removes the known guard race from the K4S END runtime; it does not declare an END window. That needs a separate coordinator ruling.

## 8. Files

**Changed:**
- `reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json`: `c1fb1e9a…` → `74314eda…`.

**Added:**
- `reports/explore/k4s-confirm/mac/test_k4s_amendment3.py` (`5f41d93d…`)
- this record and its JSON.

**Review:** pending. Per the coordinator's routing, this draft is posted for coordinator review; a Sol review of the manifest/test bytes can follow on request.
