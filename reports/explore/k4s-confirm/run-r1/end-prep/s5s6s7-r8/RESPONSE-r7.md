# s5s6s7-r7: ruling PF-4 (04 l00 preflight failure, background_ready affinity readback)

**Scope.**
- COORDINATOR c14b40e8 (2026-10-14 00:59Z entry), PF-4 items 1 and 2, the offline part of item 1's pin updates.
- This directory is the runner's `cp` of `s5s6s7-r6`, with the runner's one affinity edit and repin; the worker continued it. r6 is unchanged.
- Offline on 127x05: no ssh, no host, no network, nothing committed.
- Read boundary: no `games/`, `complete.json`, end-raw, end-complete, reducer or verifier output was opened. The 04 l00 / 03 l01 preflight metadata (`preflight-result.json`, `argv.nul`, file sizes) and the staged runtime and bundle are the only real data read.

**Diffs.**
- `DIFF-r7.patch` = `diff -ruN s5s6s7-r6 s5s6s7-r7` restricted to production files and TOOLS-FINAL.
- `DIFF-r7-tests.patch` = the same for `tests/`.

| Item | Change (r7 file:line) | Tests | Status |
|---|---|---|---|
| PF-4.1 affinity check | `k4s_end_preflight.py:880-887` (runner's edit, kept): one readback per pinned mask, each a non-empty subset of its mask, masks pairwise disjoint. The readback is recorded first (`:873-877`, `result["slot_evidence"]`) with exactly the frozen END's four fields (`end_reference.py:371-374`) | `tests/test_r7.py`: `test_pf4_regression_data_is_the_recorded_04_slot_evidence` (the literal == 04 l00's recorded evidence); `test_pf4_observed_04_readbacks_pass` (asserts equality would refuse it, then the run passes binding); `test_pf4_full_mask_readbacks_still_pass`; `test_pf4_non_subset_or_overlapping_masks_refused[cpu-of-the-next-mask, reference-cpu, empty-readback, overlapping-masks, fewer-workers-than-masks]`; `test_pf4_slot_evidence_is_recorded_exactly_as_the_frozen_end` (AST-equal to the frozen expression; frozen file hashed against its closure pin) | fixed (ruled form) |
| PF-4.2 class table | `CLASS-TABLE-PF4.md`: 51 rows; SAME 18, STRICTER 15 (each kept with a written ruling, or fixed: C15), LOOSER 0, S5-ONLY 18; dynamic-state section; offline evidence `pf4-evidence/` | — | done |
| C20 MHz window (class finding) | `k4s_end_preflight.py:936-956`: only hold rows from the first hold row + the frozen `warmup_seconds` on are compared, as END compares only post-warm-up rows (`end_reference.py:375-403`). Fewer than 2 such rows → recorded `unavailable`, not gated. r6 compared every hold row (stricter and looser than END) | `test_pf4_mhz_window_leaves_out_the_frozen_warmup` (compared rows = exactly the post-warm-up rows of `capacity.jsonl`), `test_pf4_mhz_gate_still_applies_after_the_warmup`, `test_pf4_hold_shorter_than_the_warmup_is_recorded_not_gated` | fixed |
| D4 error outside a check (class finding) | `k4s_end_preflight.py:1026-1029`: `ok` requires `"error" not in result`. r6 sealed `passed` with exit 0 when an exception was raised while no check row was open (e.g. the frozen background `__exit__` after `loaded_hold`). END fails the body in that case (`end_reference.py:222-230`) | `test_pf4_error_outside_any_check_fails_the_run` | fixed (was LOOSER) |
| C14 nice readback (kept, STRICTER) | `:878-879` unchanged | `test_pf4_priority_readback_still_required[reference, background]` | kept, reason in the table |
| Test fakes | `tests/fake_frozen.py`: `fake["layout"]` (search, masks, census), `fake["warmup_seconds"]` (default 0.2 s for the sub-second test hold), `fake["exit_fails"]`; the fake `compare_mhz` now refuses fewer than 2 rows like `fleet_profile.py:61-62` and reports the first compared timestamp | existing suites unchanged and passing | test-only |
| Pins | `tests/repin.py`: `k4s_end_launch_gate.py:55` `PREFLIGHT_SHA256` follows the new preflight; nothing else moved (`repin.py --check` clean) | `test_pins.py` | done |
| TOOLS-FINAL | rewritten from computed hashes. Only `k4s_end_preflight.py` changes (r7 SHA/size in the file); the other five rows are byte-identical to r6. Marker `TOOLS-FINAL-READY` | `test_pins.py` | final |
| Canonical bootstrap | the BEGIN..END region is byte-identical to r6 (region SHA equal by command) | `test_f1_bootstrap.py` | unchanged |
| Mutation | `tests/mutate.py` + PF01-PF12 and NULL N12 (`test_r7.py`) | `MUTATION-RESULTS-r7-py312-O.json`, `MUTATION-RESULTS-r7-py38-O.json` | 12/12 killed, N12 survived, on both |

**Operational flags (runner and coordinator; no code change).**
1. 04 l00's guard wrote `allowlist-occurrences.jsonl` and `parent-source-seed-admission.json` into `/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-pf00`. They are in its seal. A 04 l01 on the pf00 bundle will refuse at `guard_job_fresh`, as RC-3 requires. 04 l01 needs a fresh `-pf01` guard job and bundle. The 03 pf00 job is still fresh: 03 l01 failed before the guard started.
2. D5 residual: the 04 "no login during the hold" check counts `sshd` processes by name. A pre-auth `sshd` fork from any connection to port 22 counts as a login and fails the 04 preflight (no attempt is consumed). Kept per RC-2/RC-7; the coordinator may want to rule on it.
3. A 04 hold of exactly 900 s can never be binding (the measured span is < 900 s). The runner's 1200 s is fine.
