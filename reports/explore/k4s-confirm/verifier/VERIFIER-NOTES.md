# PREREG-K4S independent integer-count verifier: notes

## Authorship and independence

- **Author:** Claude Haiku 5.5 (`claude-haiku-5-5`), working as the independent verifier author for the
  PREREG-K4S confirmatory study. The reducer is written by a different author.
- **Did not read** `reports/explore/k4s-confirm/reduce.py` or any `reduce*.py` in k4s-confirm, in round 1 or round 2.
  Nothing under `reports/explore/x4s2/receipts` and no game outcome data was opened. No ssh, no git commit or push,
  no network.
- **Sources read (round 3):** `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md` (governs,
  sha256 `9650972d…`), `reports/explore/k4s-confirm/K4S-SPEC.md` at sha256 `e80652d4…` (§2, §3, §5, §6.1–6.2, §6.7,
  §7; the spec changed during round 3, and this is the text the round-3 verifier implements),
  `reports/explore/k4s-confirm/guard-decks.json` read as data only, pinned by sha256 `6d51628b…`, and the round-2
  files. The Sol review `reviews/SOL-REVIEW-VERIFIER-r1.md` is the source of the round-3 findings.
- **Still not read:** `reduce.py` and any `reduce*.py`, all game outcome data, `x4s2` receipts. No ssh, no network,
  no git commit or push.
- **Imports:** standard library and numpy only.

## Round 4 changes (Sol review r2, finding 6 and minor findings 9 and 10)

Findings 1–5, 7 and 8 were resolved in review r2 and are unchanged.

1. **MAJOR 6: c\* is bound to the frozen plan.** `load_plan` reads `reports/explore/k4s-confirm/plan.json` as data
   (default `--plan` = `../plan.json` relative to the verifier). Its `c_star` must be the number 0.9 or 0.8. The
   output records `plan.path`, `plan.sha256` and `plan.c_star`, and `c_star` comes from the plan. Every game's
   `metadata.c_star` must equal it. `--c-star`, if given, must equal the plan's value, or the run is refused with exit 2
   before any game is read. Refusals produce no decisions and no view.
   - A `--plan` other than the frozen file is a test fixture. It runs only with `--synthetic`, and it must carry
     `"synthetic_marker": "SYNTHETIC"`. The frozen plan must not carry the marker. A production run with another plan
     is refused.
   - Regressions: (a) a frozen 0.8 plan against consistent 0.9 CLI and games is refused, both with `--c-star 0.9`
     (REFUSED) and without it (games disagree, ERRORS, no view). (b) A frozen 0.8 plan with games recording 0.8, under
     the normal invocation with no `--c-star`, runs and gives labels H1, H2, H3, H5, H6, H7. (c) The default plan is
     the real `plan.json` (0.9), and the output's `plan.sha256` equals the file's hash.
   - Other tests: the CLI disagreeing with the plan is refused, a plan with a `c_star` other than 0.9 or 0.8 is refused,
     and a non-JSON plan is refused.
2. **MINOR 9: release-refusal tests.** The three production-refusal read-spy cases now run on a tree without the
   SYNTHETIC marker. Each asserts its own reason: "no release receipt", "coordinator", "cannot read release receipt".
   The tests also assert that neither the plan nor the comparison file is read. The `--synthetic` and `--test-counts`
   refusals also assert their own reasons. New post-parse seal cases (a real repository with a valid receipt, then a
   mutation) are "git show" for a missing committed item, "sha256" for a bad digest, and "working-tree bytes differ".
   Each asserts that no block, game or comparison file is read.
3. **MINOR 10: notes.** The exit-code line no longer lists c\* mismatch as flags-only. A c\* mismatch is now a refusal
   (exit 2). O5 is resolved. O11 is resolved, and the plan binding is documented above.

## Round 3 changes (Sol review r1, all eight findings)

1. **BLOCKER: no read after a seal refusal.** `main()` returns at once on a `Refusal`, and `--compare` is read only
   on the path that reaches the reduction. `test_no_game_or_comparison_file_is_read_after_a_seal_refusal` and
   `test_other_refusals_read_no_game_or_comparison` install a read spy (reads only, through `Path.open`,
   `read_bytes` and `read_text`) and assert that no game file, no block file and no comparison file is opened.
2. **MAJOR: hub acknowledgement is a separate durable file.** A block whose `complete.json` host is not `127x01`
   counts only if `<root>/<id>/hub-ack.json` exists (spec §6.1). A `hub_ack` key in `complete.json` is not proof, and
   the old flag is gone. Missing means a counting error and the block is not counted. The file's content is not
   specified, so only its existence is checked. Tests: remote host with no file, a `complete.json` key with no file,
   and a remote host with the file.
3. **MAJOR: ledger replayed in event order** (`check_ledger`, spec §3 "Ledger replay"). Originals start active. A lost
   block must be the active block of its logical original. A replacement can be lost only after an earlier event
   allocated it, and its descriptor must match that allocation. Each allocation makes the replacement active. The
   counted block for a logical original must be its final survivor (`reduce_tree`). Bank and population caps are
   unchanged. Tests: future loss before allocation, a disconnected chain, losing an original twice, a valid two-step
   chain, and an unlisted replacement.
4. **MAJOR: the `winner` key must exist.** A missing key is an error, not a draw. Only an explicit JSON `null` is a
   draw. Tests: missing key (error), explicit null (draw), and a missing key end to end.
5. **MAJOR: the §2 deck mapping is verified independently.** `guard-decks.json` is loaded only after its sha256 matches
   `6d51628b…`, and otherwise the run is refused. `scheduled_decks` implements §2: primary own = `primary[cell mod 5]`,
   opponent = `primary[(cell div 5) mod 5]`; guard own = `l2[(cell div 2) mod 3]`, opponent = `guard[cell div 6].cards`.
   Each descriptor's `own_index` and `opponent_index` must match, and each game's `own_deck` and `opponent_deck` must
   equal the scheduled deck as a sorted list. Fixtures carry the real decks. Tests: wrong descriptor index, guard
   `opponent_index`, a wrong game deck, one arm with another opponent deck, shuffled order (accepted), and the pinned hash.
6. **MAJOR: c\* is an input check.** A game whose `metadata.c_star` is missing, or differs from `--c-star`, is an
   error, so no decision or view is produced. The old `c_star_mismatch` flag is gone. The c\*=0.8 positive test now
   generates games recording 0.8, and the sequence labels stay H1, H2, H3, H5, H6, H7. Mismatch refusal tests added.
7. **MINOR: rationals in lowest terms, positive denominator** (spec §6.7). `same_rational` requires `den > 0` and
   `gcd(|num|, den) = 1`, and compares exactly with the verifier's canonical pair. `[14,2]`, `[-7,-1]`, `[0,5]`,
   `[7,0]` and `[1,1.0]` are mismatches. The old acceptance test is reversed.
8. **MINOR: `usable_cells` is compared as a set** (spec §6.7), after checking that each entry is a valid cell string.
   Duplicates in the reducer's list therefore match, as the set rule says. A `0.5` or a non-string is a mismatch.

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
| `verify_k4s.py` | The verifier. CLI: `--root`, `--ledger`, `--release`, `--synthetic`, `--plan` (default `../plan.json`), `--c-star {0.9,0.8}` (optional; must equal the plan), `--compare`, `--out`, `--repo`. |
| `test_verify_k4s.py` | Pytest suite. Synthetic trees only. Test-only sizes come from the `--test-counts` hook, which is accepted only with `--synthetic` and a `SYNTHETIC` marker. |
| `VERIFIER-NOTES.md` | This file. |

Exit codes: 0 clean, 1 flags only (including `SUSPENDED` validity), 2 refusal (seal, flags, a `--c-star` that differs
from the plan), errors (including a game `c_star` that differs from the plan), or comparison mismatch.

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
10. **`c_star` is the frozen plan's value.** The verifier reads `plan.json` `c_star` as data (round 4, §6.2) and does not
    derive it from X4S-2 phase E. A game whose `metadata.c_star` is missing or differs from the plan is an input error,
    and no decision or view is produced. A `--c-star` that differs from the plan is a refusal.
14. **Hub acknowledgement content** is not specified. The verifier requires `<id>/hub-ack.json` to exist, and does not
    check its content.
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
- **O4. Rational form (resolved in round 3).** Spec §6.7 does require `[num, den]` in lowest terms with a positive
  denominator. Round 2 misread it. The verifier now refuses noncanonical forms.
- **O5. Sequence contents (resolved in round 4).** Spec §6.7 says every step appears, and a step after the first failure
  has `tested: false, passed: null`. The verifier does this.
- **O6. `usable_cells` (resolved in round 3).** Spec §6.7 says the list is compared as a set. The verifier emits the
  spec's order (0.9, 0.8, 0.7, 0.6) and compares sets of valid cell strings. Round 2 misread the spec.
- **O11. Frozen c\* binding (resolved in round 4).** The verifier reads `plan.json` `c_star` as data, records its path and
  sha256, and uses it for every metadata check and for the sequence. `--c-star` must agree with it, or the run is refused.
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

Round 4 command: `cd /mpac/sdicks02/repos/clasher-k4s-prep && nice -n 19 /mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q -p no:cacheprovider reports/explore/k4s-confirm/verifier`
Result: **149 passed in about 9s.** (Round 3 had 132; round 2 had 95.)

The brief's interpreter `/mpac/sdicks02/repos/clasher/.venv/bin/python` does not exist. The test venv is Python 3.12 with
numpy and pytest.
