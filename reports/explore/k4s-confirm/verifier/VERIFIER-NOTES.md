# PREREG-K4S independent integer-count verifier: notes

## Authorship and independence

- **Author:** Claude Haiku 5.5 (`claude-haiku-5-5`), working as the independent verifier author for the
  PREREG-K4S confirmatory study. The reducer is written by a different author.
- **Did not read** `reports/explore/k4s-confirm/reduce.py` or any `reduce*.py` in k4s-confirm, in round 1 or round 2.
  Nothing under `reports/explore/x4s2/receipts` and no game outcome data was opened. No ssh, no git commit or push,
  no network.
- **Sources read (round 2):** `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md` (governs),
  `reports/explore/k4s-confirm/K4S-SPEC.md` (the updated spec, §3, §6.7, §7), and this verifier's round-1 files.
- **Imports:** standard library and numpy only.

## Round 2 changes

Round 1 matched the reducer's decisions exactly on the full 3000/900 synthetic tree, but `--compare` matched by
meaning and left many items unmatched or ambiguous. Round 2 removes that matching.

1. **`--compare` is exact and key by key (spec §6.7).** The verifier emits a top-level `verifier_view` with the spec's
   keys: `schema`, `counts`, `contrasts`, `sequence`, `admitted`, `veto_pass`, `usable_cells`, `validity_inside`.
   `compare_verifier_view` walks the verifier's block and the reducer's `verifier_view` together:
   - The key sets of every dict must be equal. Each missing or extra key is one mismatch.
   - Integers must be `int`. A bool is not an int, a float is not an int, and `None` matches only `None`.
   - Bounds are `[num, den]` pairs. They match when the two are equal as Fractions, with integer parts and a nonzero
     denominator. So `[14, 2]` matches `[7, 1]`.
   - `sequence` is compared in order, element by element, with its length.
   - `usable_cells` is compared as a multiset (see objection O6).
   - A missing `verifier_view` in the reducer output, or a missing one from the verifier, is one mismatch.
   The result reports `items`, `matched`, `mismatched` and each mismatch's path with both values. Any mismatch is exit 2.
   The old `unmatched` and `ambiguous` lists are gone.
2. **Release barrier (§7).** The receipt must have `study` = `PREREG-K4S`. Each item must be exactly
   `{path, sha256}`, the path must be repo-relative (no absolute path, no `..`), and the sha256 must be 64 lowercase
   hex digits. `git show commit:path` must hash to the declared value, and the working-tree bytes must equal the
   committed bytes. The completion receipt uses the §7 field names: `reporting_complete`, `outcomes_sealed`,
   `counted_primary_blocks` (3000) and `counted_guard_blocks` (900). These are integers, not bools.
   Exactly one of `end_reference` + `end_recheck` or `ratio_unavailable_declaration`, and exactly one of
   `tiers_summary` or `tiers_release`. Any other item name is refused.
3. **`replaces` (§3).** `replaces` must be the logical original id, `{pop}-{logical:04d}`. The immediately lost
   replacement is refused. Round 1 accepted both forms.
4. **Tests.** 95 tests, up from 41. They cover the release shape and every refusal, the replacement rule (chain
   accepted with the original id, immediate-lost id refused, single-level original required), a hand-built
   `verifier_view` that matches itself and an equal-rational variant, 33 single-item perturbations that must each fail,
   the verifier's own view against its own output, a tampered count that exits 2, and a reducer with no
   `verifier_view` that exits 2.

## Files

| File | Role |
|---|---|
| `verify_k4s.py` | The verifier. CLI: `--root`, `--ledger`, `--release`, `--synthetic`, `--c-star {0.9,0.8}`, `--compare`, `--out`, `--repo`. |
| `test_verify_k4s.py` | Pytest suite. Synthetic trees only. Test-only sizes come from the `--test-counts` hook, which is accepted only with `--synthetic` and a `SYNTHETIC` marker. |
| `VERIFIER-NOTES.md` | This file. |

Exit codes: 0 clean, 1 flags only (including `SUSPENDED` validity and `c_star` mismatch), 2 refusal, errors, or
comparison mismatch.

## Transcription (constant → source)

| Constant | Value | Source |
|---|---|---|
| `COORDINATOR` | `0523ae6f-baa3-4d4e-b233-b392671670db` | Spec §7; r3 §4.5 |
| `SEAL_STUDY` | `PREREG-K4S` | Spec §7 |
| Primary seed base | `4503605807370496` | r3 §3.4; spec §2 |
| Guard seed base | `4503605817370496` | r3 §3.4; spec §2 |
| Primary n / subsample | 3000 / 600 (`i < 600`) | r3 §3.1, §3.3; spec §3 |
| Guard n / subsample | 900 / 300 (`i < 300`) | r3 §3.1, §3.3; spec §3 |
| Cells | 50 primary, 18 guard (`i mod cells`) | r3 §3.3 |
| Rotation divisor | `⌊L/50⌋` primary, `⌊L/18⌋` guard, `mod 8` | r3 §3.1; spec §3 |
| CORE order | K4-200, K4S-200, K4-180, K4S-180, K4-160, K4S-160, K4S-140, K4S-120 | r3 §3.1; spec §1 |
| Subsample arms | K4-140 after rotated position 3, K4-120 after position 6 | r3 §3.1; spec [I-2] |
| Replacement index | `n + cells·k + cell`, 0-based `k`, bank `k ≤ 11` (primary), `k ≤ 9` (guard) | r3 §3.4; spec §3 |
| Replacement caps | 10% of n: 300 primary, 90 guard | r3 §3.4 |
| Bootstrap | R = 10000, `default_rng(2026101170)`; order P_full, G_full, P_sub, G_sub; cells ascending | r3 §5.1; spec §6.3 |
| Percentile | exact `Fraction`; position `(R-1)·q`, q = 1/40 and 39/40; linear; ×100/n | spec §6.3 |
| Margins | Δ_ref ≤ 10 (B) / ≤ 5 (A, A(0.9)); Δ_same < 0 strict; Δ_ref^G ≤ 15 (B) / ≤ 10 (A, A(0.9)); veto ≤ 5 | r3 §1.2; spec §6.5 |
| Sequence | H1 B(0.8), H2 B(0.7), H3 B(0.6), H4 A(0.9), H5 A(0.8), H6 A(0.7), H7 A(0.6); H4 dropped at c* = 0.8 | r3 §1.2, §1.3; spec §6.5 |
| Validity | 10 ≤ 100·losses(K4-200, P_full)/n ≤ 30, inclusive | r3 §5.4; spec §6.5 |
| Arm budgets and kernels | 200 c ms; `K4-anytime` (K4), `K4-anytime-sdefault` (K4S); `SD1` default source; `full` rule | r3 §2.3, §3.1; spec §1 |

## Interpretations (K4S-SPEC §9 and my own choices)

These are the choices the verifier makes where the text is open. The reducer may read them differently, so the
coordinator should check them against the reducer.

1. **Replacement `k` is 0-based.** Only a 0-based `k` fills the banks exactly: 12 × 50 = 600 primary, 10 × 18 = 180 guard.
   `k` counts every lost block in the (population, cell), replacement losses included, in ledger order.
2. **Game file location.** `<root>/<id>/games/<id>-d27-<arm>.json`, where `<id>` is the block's own id (for a
   replacement, its replacement index). The `games` map key in `complete.json` must equal that file name.
3. **`replaces` is the logical original id (§3).** It is refused if it names the immediately lost replacement.
4. **Replacements inherit** the lost block's logical index, rotation, arm set and cell ([I-1]). The verifier checks
   the replacement's own descriptor against its logical index.
5. **Subsample membership uses the logical index.** `L < 600` (primary) and `L < 300` (guard).
6. **Cell-level bootstrap draws happen only for non-empty cells.** No cell is empty in the configured sizes.
7. **Δ_same(0.8) is on primary full.** K4-160 is on every block. Δ_same(0.7) and (0.6) are on primary subsample,
   where K4-140 and K4-120 exist.
8. **Losses come from `metadata.winner` and the descriptor's `seat`.** Any stored `loss` or `draw` field is ignored (§6.2).
9. **`freeze_manifest_sha256` must be non-null in every counted game** (§5: null only in qualification and smoke).
10. **`c_star` is an input.** The verifier does not derive it from X4S-2 phase E. A games-versus-`--c-star`
    mismatch is a flag.
11. **Under c* = 0.8**, the veto is reported as descriptive (r3 §1.3). Usable 0.9 is False, because A(0.9) is not tested.
12. **`verifier_view.sequence` lists every step of the c\* sequence, in test order.** A step after a failure has
    `tested: false` and `passed: null`. (O5.)
13. **Full analyses carry the 8 core arms. Subsamples carry all 10.** Each `counts` entry has `n` equal to its analysis's n.

## Spec objections (r3 governs)

These are my own objections, written from the spec as it stands. Each one is a place where I had to pick a reading.

- **O1. §7 item count.** §7 says "six items", but the list gives seven when the end pair is used
  (completion, end_reference, end_recheck, production_checks, verifier_receipt, mac, tiers). The verifier accepts
  either form, and the coordinator should fix the count.
- **O2. Authorization is not verifiable from the repository.** `coordinator_thread` and `authorization_message_id`
  are strings the receipt declares. The seal proves the bytes, not that the authorization happened. Something outside
  the verifier has to tie the message id to a real authorization.
- **O3. Whose HEAD (A3, still open).** "Commit is an ancestor of HEAD" does not say which repository's HEAD. The
  verifier uses `--repo`, which defaults to its own checkout. The spec should name the branch (e.g. `origin/main`).
- **O4. Rational form.** §6.7 says `[num, den]` but does not require lowest terms or a positive denominator. The
  verifier accepts any nonzero denominator that is equal as a Fraction. The spec should require lowest terms with a
  positive denominator, so that the two sides can be compared as written.
- **O5. Sequence contents.** §6.7 does not say whether untested steps appear, or what `passed` is for them. I include
  every step with `tested: false` and `passed: null`. The spec should say so.
- **O6. `usable_cells` order.** §6.7 gives `["0.9", "0.8"]` as an example and does not fix the order. The verifier
  emits descending order and compares as a multiset. Fixing the order in the spec would let it compare as a list.
- **O7. Validity and usable cells.** §6.5 says a SUSPENDED result reports admissions "marked suspended", but §1.5 does
  not say whether usable cells are then forced to empty. The verifier computes usable cells as before and reports
  `validity_inside` separately. The spec must say which is meant.
- **O8. Percentile convention.** §6.3 cites "the T1 convention" but gives the formula in full. The verifier implements
  linear interpolation at position `(R−1)·q`, which matches numpy's default `linear` method. The coordinator should
  confirm this against T1's bounds, which I did not read in round 2.
- **O9. Replacement ledger.** §3 does not say whether a lost replacement's `k` counts in its cell's bank. The verifier
  counts it, which is what the 600 / 180 bank arithmetic requires, and the spec should say so.
- **O10. Release timing.** `authorized_at_utc` is not checked against any commit time, so it is informational only.
  The spec should either bind it or say that it is not checked.

## Ambiguities resolved since round 1

- **A1 (item shape).** Resolved by §7: `items[name] = {path, sha256}`.
- **A2 (completion field names).** Resolved by §7: `counted_primary_blocks`, `counted_guard_blocks`.
- **A5 (`replaces`).** Resolved by §3: always the logical original.
- A3 (whose HEAD) is still open (O3). A4, A6–A14 are unchanged from round 1 (see the spec; they are reflected in the code).

## Not implemented (out of scope for this task)

- §6.6 secondary outputs: F1, the flagged-block sensitivity on `default_rng(2026101171)`, the matchup-cluster
  bootstrap on `2026101172`, per-host and per-seat tables, mechanism rates, latency, draws-as-half, and monotonicity.
  None of them can change admission.
- Derivation of c* from X4S-2 phase E, and the c_e mapping from c_M (the Mac measurement).
- Verification of the TIERS release barrier contents. The seal checks only its declared sha256 and its working-tree bytes.
- Interference flags (OP-6/OP-7), and matchup or per-host analyses.

## Test results

Command: `nice -n 19 /mpac/sdicks02/venvs/t1-verifier/bin/python -m pytest -q reports/explore/k4s-confirm/verifier`
Result: **95 passed in 3.87s.**

The brief's interpreter `/mpac/sdicks02/repos/clasher/.venv/bin/python` does not exist. The test venv is Python 3.12 with
numpy and pytest.
