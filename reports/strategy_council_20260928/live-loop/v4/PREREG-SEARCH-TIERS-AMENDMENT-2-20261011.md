# TIERS Amendment 2: approved outcome-blind import erratum

Prepared 2026-10-11T17:48:31Z on 127x05, branch `worker/t1-tiers-amendment2-20261011`, parent `66acf60c4b593a3841a0aac78d81892197aabecc`. Coordinator thread 0523ae6f authorized preparation at message 7746. Independent Claude Opus review APPROVE_WITH_CONDITIONS is retained in [review r1](TIERS-AMENDMENT-2-REVIEW-r1.md); coordinator disposition `6a2669ae9cab4a737697480f4c7208751d4d2841` authorizes integration before the END window.

`measure_tiers.py` uses `math.isfinite` to enforce Amendment 1's signed full-occupancy MHz ratio gate but omitted `import math`. The production change is one import. It makes the existing admission rule executable; no hypothesis, arm, seed, threshold, contrast, alpha, selection rule, outcome handling, or gate is changed. Preparation used source and synthetic metadata only, with no reporting outcomes, corpus payloads, Mac access, or running-job edits.

The new admission regression calls `validate_counts(..., dry_run=False)` with a conforming synthetic Amendment 1 manifest, then verifies that NaN, positive/negative infinity, and ratios .94/1.06 still fail closed. It reproduced `NameError: name 'math' is not defined` before the import; afterward all 33 tests in `test_measure_tiers.py` pass on 05 at nice19/core63. This pure-function test launches no Mac session or reference run.

| Source | Before SHA-256 | Candidate SHA-256 |
| --- | --- | --- |
| `measure_tiers.py` | `5d7de8e36890f0f8d086e77be5ec4e20de1b3cc1f48943bd06e8bbd103046124` | `6066228b89601d6cf29ff456e9dee4848fa59886f319ff38ebabd49e3c101f2e` |
| `tests/test_measure_tiers.py` | `f3198e6bf320c98b28e1a27446dceaccd1071f1dfee51bceb539ccc869546586` | `84b02676be66a08addb24935dc14251ef32f952e264f597c5ac8c8cd3514843b` |

The original [TIERS freeze record](PREREG-SEARCH-TIERS-FREEZE-20261010.json) remains byte-for-byte at SHA-256 `47aba25e306d787518ec41bac6ecbca88e3372c03f5b118aacda2c5b86ae217c`; its frozen document hashes stay valid. The separate [amendment record](PREREG-SEARCH-TIERS-AMENDMENT-2-20261011.json) binds this note and the new source/test hashes without rewriting historical evidence. The prospective END/Mac source inventory and derived bundle/source-manifest hashes must be regenerated and bound to the reviewed amendment commit. Historical qualified copies, receipts and T1 reporting manifests remain governed by their existing hashes, including r3 manifest `488f6c8daccc81bc13a0f388bb254fa994020806b9245b2e315c5ba237dcb12e`. The amendment does not authorize END, outcome release, or a Mac session.

Coordinator conditions recorded 2026-10-11T18:06:55Z (message 7785; disposition `6a2669ae`):

1. **Same amended bytes everywhere.** END reference, A6 smoke, pooling and every Mac session must use post-integration `measure_tiers.py` SHA-256 `6066228b89601d6cf29ff456e9dee4848fa59886f319ff38ebabd49e3c101f2e`. Prepare END/A6 bundles only after this integration. Any reference or smoke prepared or run on `5d7de8e3` is void and must be re-prepared and re-run under the existing technical-repeat rules; never patch prior receipts. Mixed old/new populations cannot be pooled. Bind regenerated inventories and bundles to this integration commit before use.
2. **Python validation scope.** Worker and independent-review validation ran on Python 3.8.10. Mac builds require Python 3.12 or later; that interpreter and a Mac session were not exercised here. The standard-library `import math` has the same behaviour on both. PC3 still independently requires the pool's Python 3.12 interpreter.

The frozen [K4S Mac manifest](../../../explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json) pins old `measure_tiers.py` bytes under `reused_readonly` and `measure_tiers_unmodified`. Coordinator disposition requires a companion outcome-blind K4S Amendment 1 to re-pin both entries to `6066228b` and regenerate its manifest hash, with independent Sol review before any K4S Mac session. The coordinator owns that companion; this change leaves K4S files and every running T1 reporting copy untouched. K4S fleet execution does not depend on this Mac pin.
