# Independent review r1: TIERS Amendment 2 (import-math erratum)

- **Candidate:** `e521800b40d8fddb694b40801b994a0e6affd256` on `worker/t1-tiers-amendment2-20261011`, parent `66acf60c`, not merged.
- **Reviewer:** Claude Opus 5.5, independent and read-only, on 127x05, 2026-10-11.
- **Method:** I used a scratch detached worktree (now deleted), ran everything under `nice -n 19 taskset -c 63`, and used Python 3.8.10. I did no ssh, read no outcomes or heldout data, and wrote nothing to the worker branch.

## Verdict: APPROVE_WITH_CONDITIONS

The erratum is correct, minimal and outcome-blind. The test is a genuine regression test, and every claimed hash reproduces. The conditions concern scope that the note leaves out: merging changes a hash that the **frozen K4S Mac manifest** pins, and it fixes an ordering constraint on the END fleet references. Neither condition requires a change to `measure_tiers.py` or to the test.

## Verified claims

| Claim | Result |
| --- | --- |
| The commit touches exactly 4 paths, with 86 insertions and 0 deletions | Yes |
| `measure_tiers.py` before SHA is `5d7de8e3…6124` | Yes, the parent blob |
| `measure_tiers.py` after SHA is `6066228b…1f2e` | Yes |
| Test before/after SHAs are `f3198e6b…` and `84b02676…` | Yes |
| Note SHA is `fc53c1ef…` | Yes |
| The candidate amendment JSON is `5a642aa8…141b` | Yes |
| The freeze JSON is still `47aba25e…217c` | Yes. Neither the freeze JSON nor Amendment 1 is touched by the commit |
| Since parent 66acf60c, origin/main changes none of the 4 paths | Yes (origin/main is at b53de100) |

## Findings

1. **Production diff: PASS.** The only production hunk is `+import math`, at line 6. It sits alphabetically between `json` and `multiprocessing` in the stdlib import block, and nothing else in the file changed. Pyflakes 3.2.0 on the parent bytes reports exactly `70:17 undefined name 'math'`, plus the long-standing unused `sys`. On the candidate it reports no undefined names anywhere in the 14 e4v3 modules or the 6 test files. `py_compile` passes on all of them. The rest of the pyflakes output is unused imports and variables, which don't affect behaviour.

2. **Regression test: PASS, and it is a genuine regression test.**
   - **Old source, new tests:** `test_mac_amendment_1_reference_ratios_validate_without_a_session` raises `NameError: name 'math' is not defined`; the other 32 tests pass.
   - **New source, new tests:** 33 out of 33 pass. The full e4v3 suite, run with `unittest discover`, passes 70 out of 70.
   - **New source, old tests:** 32 out of 32 pass. The test file only adds lines (+24, −0), so no existing test is weakened.
   - **Why the old suite missed the bug:** the old tests also pass 32 out of 32 on the old source. No existing test reached the non-dry `validate_counts` branch.
   - **The test is meaningful.** The conforming manifest's own `validate_counts(..., False)` call is what fails on the old bytes, so it acts as a positive control. The NaN subtest is the one that matters, because `abs(nan-1) > .05` is False, so `math.isfinite` is the only guard against NaN. The ±inf and .94/1.06 subtests check that the existing out-of-gate rejection still holds. All of the data is synthetic.

3. **Amendment text is outcome-blind and in scope: PASS.**
   - The note and JSON name no outcomes and change no hypothesis, arm, seed, threshold, contrast, alpha or gate.
   - They say the prospective END/Mac source inventory and bundle/source-manifest hashes must be regenerated and bound to the amendment commit.
   - They keep historical receipts and T1 r3 manifest `488f6c8d` under their existing hashes.
   - I confirmed there is no effect on T1's running r3 reporting jobs: they run from freeze `ef4c073a` and don't execute e4v3 code.
   - I also confirmed there is no effect on any frozen decision rule: the Amendment 1 gate already existed in the frozen text and is now executable as written.

4. **CONDITION (major): cross-study pin break with the frozen K4S Mac manifest.** The amendment never mentions K4S.
   - **The pin:** `reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json` is frozen as K4S F-8 at SHA `d89cab16…`. It pins `measure_tiers.py` at `5d7de8e3` twice: under `measure_tiers_unmodified`, and under `reused_readonly`.
   - **How it fails:** `k4s_logic.load_k4s_manifest` calls `verify_pinned(runtime_root, reused_readonly, …)`. On the candidate tree I confirmed it raises `PreconditionRefusal: Pin mismatch (reused read-only TIERS files): …/measure_tiers.py`. `test_measure_k4s.py::test_manifest_is_current_and_measure_tiers_unmodified` will also fail once merged. So after merge, every K4S Mac session fails closed.
   - **K4S END pooling is unaffected:** `end_pool.frozen_helpers` pins only fleet_end, fleet_profile and fleet_validity.
   - **Condition:** before or alongside merge, the coordinator must decide on a companion K4S outcome-blind erratum that rebinds `reused_readonly` and `measure_tiers_unmodified` to `6066228b` and regenerates the K4S Mac manifest SHA. K4S only imports `measure_tiers.GCTrace`, so it is not functionally affected. The alternative is to record explicitly that K4S Mac runs from a runtime root holding the old bytes, but the TIERS and K4S Mac sessions share a TIERS-built native and pins, so that is fragile. The TIERS note should also cross-reference the K4S pin. Today it says only that the pin regenerates "after disposition".

5. **CONDITION (moderate): all END/A6/pool/Mac steps must use the same `measure_tiers.py` bytes. State this ordering explicitly.**
   - **Where the live tree is checked:** `fleet_pool.py:107/137`, `prepare_fleet_smoke.py:29`, `tier_backend.validate_bundle:425` and T1's `release_reference.pool_inputs` all verify the recorded `measurement_files`, which include `measure_tiers.py`, against the *live* e4v3 directory.
   - **What breaks:** an END fleet reference or A6 smoke bundle prepared or run on `5d7de8e3` cannot be pooled, checked or released from a post-amendment tree. A mixed population, with some hosts on the old bytes and some on the new, is unpoolable.
   - **Why it's recoverable:** as far as I can see, no END reference or A6 smoke has run yet. They are scheduled for T1's END window, and the repo holds no fleet-identity receipts.
   - **Condition:** the disposition must state that END and A6 bundles are prepared only after merge, from the amended tree. Any reference already run on the old bytes is void and must be re-run under the existing technical-repeat rules, not patched. The note's generic "regenerate prospective END/Mac inventories" is right, but it doesn't spell out this ordering or that a mixed population is unpoolable.

6. **Minor: the validation interpreter differs from the Mac's.** The tests ran on Python 3.8.10, while `build_tiers.sh` requires Python 3.12 or later on the Mac. This doesn't matter for `import math`, but the JSON's `validation` block should say the Mac interpreter was not exercised. The non-dry Mac-only branches of `measure_tiers.py` (Darwin/mps/authorized) are still only statically checked, and this bug lived in exactly that kind of code.

7. **Same-class sweep (finding 4 in the brief): no further undefined names.**
   - Pyflakes found no undefined names in any of these:
     - the 14 e4v3 production modules and 6 test files;
     - the 167 modules on the Mac/END import path: reports/explore/s1, e1 planner, src/clasher/live capture/perception/selection, imitation/model/inference, reports/explore/t1 guard modules, k4s-confirm/mac, engine-speed/stage5 and search-noise-s6;
     - a wider set of 598 files covering src/clasher, imitation/model and k4s-confirm.
   - The only parse failures were in `src/clasher/rl/readiness_*.py`. Python 3.8 can't parse their syntax, and they are not on the TIERS path.
   - An AST scan for stdlib `module.attr` uses in e4v3 found nothing missing. Its two hits on `importlib.util` are false positives, because the module is imported explicitly.
   - Grepping for APIs removed in Python 3.12 (imp, distutils, utcnow and similar) found nothing.
   - **Limitations:** this doesn't cover names that are resolved dynamically. That includes the T1 guard modules loaded with `importlib.import_module`; their files were scanned, but the import binding was not. It also doesn't cover the Rust native module.

8. **Informational (no change requested; out of erratum scope).**
   - `measure_tiers.py:68` checks `relative_to_pooled_median` without a local `isfinite`, so a NaN would pass that line. The producer, `fleet_pool` (lines 10 and 30), already refuses non-finite and non-positive inputs, so this is a defence-in-depth gap, not a live fail-open.
   - Because of floating-point rounding, a ratio of exactly .95 or 1.05 is rejected at both gates. That is frozen behaviour and doesn't change here.

## Disposition checklist for the coordinator

- [ ] Merge e521800b as is. No code or test change is required.
- [ ] Decide on the K4S companion rebind (finding 4) before any K4S Mac session.
- [ ] Record the END/A6 ordering, that a mixed population is unpoolable, and the voiding of any reference run on the old bytes (finding 5).
- [ ] After merge, regenerate the e4v3 measurement inventory and bundle pins, and bind them to the merge commit.
- [ ] Optionally, note in the amendment JSON that the Mac interpreter (Python 3.12 or later) was not exercised (finding 6).
