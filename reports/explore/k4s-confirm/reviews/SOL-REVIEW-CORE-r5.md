# SOL independent core re-review r5

**Verdict: APPROVE_WITH_FIXES.** Finding 20 is resolved. The native/model-input and artifact-link portions of finding 19 are fixed and reject the original mutation scenarios. One part of the exact-runtime proof remains incomplete: the snapshot and assembler do not revalidate shared source files declared by `runtime-pin.json`. Finding 21 below is MAJOR and must be fixed before accepting qualification as proof of the current runtime or freezing it. The core approach remains acceptable.

Reviewed `/mpac/sdicks02/repos/clasher-k4s-prep`, HEAD `962ecce2cf05223aada69746f2758bcf573c82f6` plus working-tree bytes. Governing preregistration: `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md`, SHA-256 `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a`. Contract: `reports/explore/k4s-confirm/K4S-SPEC.md`, SHA-256 `e80652d4859504eaf6a9256a3b3672a247a3f1993160ab17378587e7cdd93e53`. Read the four prior core reviews and author responses. Locations below are relative to `reports/explore/k4s-confirm/` unless otherwise specified.

This was an independent review of the author's changes. No network, SSH, commit/push, real game outcome data, or anything under `reports/explore/x4s2/receipts` was accessed. No implementation file was changed. This review is the only file written; synthetic test I/O was intercepted into memory. No manifest builder, qualification job, native game or live STOP test was run. Mac, END, verifier and inherited OP implementations were not substantively reviewed. The expressly allowed manifest verifier mechanically checked its listed files.

## Per-finding disposition

| Finding | Status | Evidence / remaining requirement |
|---|---|---|
| 1 — Guard timestamp comparison | **RESOLVED / RETAINED** | Timestamp-free projection remains in assembly at `11–12,37–38`; the frozen guard SHA remains checked. |
| 2 — Inventory, failure propagation and smoke validation | **RESOLVED** | Exact canonical inventory and nonempty/path requirements are retained. The complete synthetic checker binds 32 games; malformed charged decisions fail with exit 1. Smoke tests and valid-path controls pass. The field-validation dependency on 20 is closed. |
| 3 — Canonical descriptors and paired decks | **RESOLVED / RETAINED** | Prior resolution is not reopened; this round did not repeat the reducer/schedule review. |
| 4 — Complete-runner injected equivalence | **PARTIAL** | The previously accepted bounded virtual-clock comparison and explicit one-thread override remain. Runtime-input and game-pin fixes are correct, but shared runtime source binding still has finding 21. |
| 5 — Rate inference, GC and WAIT indicators | **RESOLVED / RETAINED** | Prior resolution is not reopened; numerical/reducer behavior was outside this focused re-review. |
| 6 — OP sensitivity contract | **RESOLVED / RETAINED** | Prior resolution is not reopened; inherited OP implementations were not re-reviewed. |
| 7 — Decision and game audit fields | **RESOLVED** | The shared validator now enforces charged scan/nullability and aliases (`check_games.py:180–196`, `health.py:15–24`). Runner SHA matches r4; scored/unscored bookkeeping remains consistent with these rules. |
| 8 — Identity/configuration and placement | **PARTIAL** | Required arm/settings/placement checks remain. The job pin is now checked across all K4S modes (`check_games.py:228–234`), and current native/model inputs are compared to plan/pin values (`source_binding.py:68–74`). Complete current-runtime identity still depends on 21. |
| 9 — Binding through games/STOP and assembly | **PARTIAL** | Before/after/assembly comparisons now include all nine INPUTS; final verification binds all ten ARTIFACTS. Source-tree and receipt/game rechecks remain. Shared pin-declared sources are still outside these comparisons; see 21. |
| 10 — Earned crowns | **RESOLVED / RETAINED** | Runner bytes match r4; outcome semantics were not re-exercised in this round. |
| 11 — Manifest completeness/final byte proof | **RESOLVED** | Allowed verifier exited 0: 155 files, 61 identical / 14 rebound / 15 delta / 65 new, failures `[]`. No out-of-scope staleness was present at this check. Builder was not run. |
| 12 — Qualification slots | **RESOLVED / RETAINED** | Canonical slots are retained; the launcher/inventory test passes. |
| 13 — STOP and receipt success propagation | **RESOLVED / RETAINED** | Assembly still requires owned interruption/running evidence and writes FAIL then exits 1 (`40–41,80–82`). Live STOP behavior was not rerun. |
| 14 — Independently expected arm | **RESOLVED / RETAINED** | Filename-derived arm and cohort/metadata comparisons remain at `check_games.py:88–94,129`. |
| 15 — Driver inventory/game coverage | **RESOLVED / RETAINED** | Actual shared receipt validation and source-binding receipt checks accepted eleven canonical receipts/32 games in the virtual fixture. Assembly still rechecks coverage and runtime runner/plan identities. |
| 16 — Historical source-binding boolean at assembly | **PARTIAL** | Actual current inventory versus both earlier records, battery links, artifact hashes, source snapshots and bound games are now rechecked (`make_qualification_receipt.py:48–64`). Native/model and artifact mutation controls fail. The shared-source limitation in 21 still permits a stale current-runtime proof. |
| 17 — Smoke empty/malformed SD1 evidence | **RESOLVED / RETAINED** | All three authored health tests pass with memory-only I/O; SD1 and scan/alias controls remain effective. |
| 18 — Qualification before freeze | **RESOLVED / RETAINED** | Prior procedure resolution is not reopened. No live qualification/admission procedure was executed. |
| 19 — Current native/model inputs and earlier artifact links | **PARTIAL** | All four native/model inputs, both corpus files, runtime/inherited pins and staging are now snapshot-bound. Current qualification inventory and earlier battery links are enforced; all ten verification artifacts are enforced. All original concrete mutation cases are closed. Remaining runtime-pin-declared source scope is finding 21. |
| 20 — Charged aliases and scan nullability | **RESOLVED** | Charged decisions call the same `health.sd1_errors` used by smoke. Ten independently mutated field relationships are rejected, with receipt hashes refreshed so rejection comes from validation. Valid belief/prescan/sample/single-candidate and scored paths are accepted. |

“Retained” records the prior disposition without claiming a new independent review of excluded or unchanged subsystems. Findings 4/8/9/16/19 share the one remaining objection below; they do not represent five different requested fixes.

## New finding

### 21. MAJOR — Hashing the runtime pin does not revalidate its shared source files

**Location:** `source_binding.py:57–76`, especially `68–75`; `make_qualification_receipt.py:48–64`. Supporting scope: `qualification_binding.py:6–9`, `pin.py:5–9,17–23`.

**Scenario:** `snapshot()` hashes the K4S tree, the frozen T1 tree, explicit references and the nine INPUTS. It parses `runtime-pin.json` but checks only `pin['inputs']`. It neither checks nor snapshots the files named by `pin['files']` or `pin['native_source']`. The older qualification inventory likewise covers only top-level K4S Python/shell files, its plan and four native/model inputs.

Consequently, change a shared runtime dependency such as `repo/reports/explore/e1/policy.py`, `repo/student-source/exit_r3/network.py` or `repo/src/clasher/rl/c56_rollout_planner.py` after qualification games. Leave `runtime-pin.json`, SD1 manifest, model inputs and receipts unchanged. The before/after/assembly snapshots remain identical, the historical SD1 check still ends in the unchanged manifest hash, every game's `runtime_pin_sha256` still matches, and assembly returns PASS for bytes that no longer match the pinned runtime. The existing `pin.verify()` checks those shared sources, but neither the source-binding verifier nor assembler calls it or implements its full checks.

The earliest SD1 check or a later launch check cannot substitute for the explicit current-runtime recheck at qualification assembly. This is an acceptance/provenance gap, not evidence that the author's successful development runs used changed files.

**Reproduction:** Ran the actual checker, `source_binding.snapshot()`/`verify_receipts()`/verify CLI, `qualification_binding.inventory()` and assembler against a complete outcome-free virtual fixture. Eleven canonical receipts bound 32 games; unchanged baseline produced PASS, exit 0. After final verification, independently changed each of the three pin-declared shared source files above. In each case the current snapshot was exactly equal to the start snapshot and the actual assembler still produced PASS, exit 0, with all checks true. A pin-declared native-source mutation was also undetected; the executable shared Python sources are sufficient to establish the MAJOR finding. Controls changing the covered K4S runner or the native/model inputs failed.

**Fix:** At record, final verification and assembly, revalidate the complete runtime pin: every `files` entry against `job/repo`, every `native_source` entry against `job/native-source`, and every `inputs` entry against `job`. Include the resulting source identities in the stable snapshot, or verify them against the unchanged snapshot-bound pin each time. Use a shared read-only verifier and collect mismatch errors so failure preserves the diagnostic FAIL receipt/nonzero exit behavior. No substantive review or modification of inherited OP implementations is needed to verify their declared hashes. Add shared-policy/network/planner mutation controls before final verification and after it; preserve acceptance of unchanged valid staged runtimes.

## Independent checks and false-rejection assessment

- **Complete virtual checker and assembler:** both accepted the unchanged baseline. The checker exercised all four modes, T1/K4S identity differences, eleven canonical slots, injected single-thread overrides, zero-mode budget/scale overrides, and scored/preparation/single-candidate charged paths. It bound exactly 32 games. Synthetic evidence contained no outcomes.
- **Input mutations:** independently changing any of the nine INPUTS after verification produced FAIL and exit 1 from assembly. A runtime-pin SD1-input declaration mismatch also set the snapshot validity flag false with the expected pin error.
- **Artifact mutations:** independently changing each of the ten ARTIFACTS while preserving its relevant success values produced FAIL and exit 1, including the formerly accepted belief-receipt replacement. Changing the earlier battery receipt link was independently rejected. Changing the covered runner was rejected by current source/inventory/runtime-receipt checks.
- **Runtime game pins:** hash-consistent receipt updates accompanying wrong game pin metadata were rejected in no-deadline, charged, zero and injected K4S groups. A missing runtime pin was rejected. T1 games retain their legitimate older schema.
- **Charged validator:** malformed chosen-action, fallback, extra-tick and overrun aliases; null scored scan fields; null SD1 default/P(play); and null scored coarse-order hash all failed with exit 1. The driver game hash was refreshed for each control. Ten valid K4/SD1 path combinations (scored, belief, prescan, sample, unscored single-candidate) passed the shared validator. The complete charged checker also accepted these paths with correct frozen/scan nullability.
- **Authored tests:** three health tests ran directly using actual functions with all synthetic filesystem writes intercepted into memory. The canonical launcher test ran with bytecode/cache output disabled: `PYTHONDONTWRITEBYTECODE=1 /mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q -p no:cacheprovider reports/explore/k4s-confirm/test_qual_tasks.py` — **1 passed**. Five scoped Python files parsed successfully.
- **Manifest:** `PYTHONDONTWRITEBYTECODE=1 python3 reports/explore/k4s-confirm/rebind.py verify` — **exit 0**, failures `[]`. There were no expected Mac/END/verifier hash-staleness failures to report separately at this measurement.

No false rejection was found in the legitimate synthetic paths exercised. The reported full-driver PASS receipts on 127x03 and 127x04 are consistent with this result; I did not inspect their game outputs or independently rerun those hosts. Those runs establish useful normal-path context but do not exercise post-qualification source mutations. Health bytes are identical to r4, and the new charged-validator invocation agrees with runner nullability/alias bookkeeping. No other scoped regression was found.

## Reviewed source identities

```text
source_binding.py              8e2863e08f2746c4a1234b5d0821a8acf0757cd51e4e202bdb56e0bc5faab0a2
check_games.py                 83a92547c9f335daaceab56d872cf60700423e294346978cd1c013b484eefd9b
make_qualification_receipt.py   fcdf768c4e2c7ee8c41bdd22dbcf8cc445c99286c33fae05657b0a364d43d790
health.py                      5bbe9beb4db6f40e9aab64fd2cf07aa57419e04ddfcbb2dccf4bb6351b51b697
qualification_binding.py       48644ca369eb246c4c43aaf64254a27e86a941eb9fc3fd69385113a2387701c0
pin.py                         440e59236f2dcf5fbf7e47fd69859fe0a72c91d8ecd15f93009307b37e13ce07
run.py                         78d88a572a8637956492d0f8447569c2307454818bb03356007b9ff9938a5f13
DELTA-MANIFEST.json             d15715bae0b9ad94f16c296842d9b26a7c6da5d89591de4725f925eabdb821b7
```
