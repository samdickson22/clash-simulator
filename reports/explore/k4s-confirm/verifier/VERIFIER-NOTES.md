# PREREG-K4S independent integer-count verifier: notes

## Authorship and independence

- **Author:** Claude Haiku 5.5 (`claude-haiku-5-5`), working as the independent verifier author for the
  PREREG-K4S confirmatory study. The reducer is written by a different author.
- **Did not read** `reports/explore/k4s-confirm/reduce.py` or any `reduce*.py` in k4s-confirm. Nothing under
  `reports/explore/x4s2/receipts` and no game outcome data was opened. No ssh, no git commit or push, no network.
- **Sources read:** `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md` (governs) and
  `reports/explore/k4s-confirm/K4S-SPEC.md`. The T1 verifier header (`git show ef4c073a:reports/explore/t1/verifier/verify_t1.py`)
  was read for layout and style only. Nothing is imported from it.
- **Imports:** standard library and numpy only.

## Environment note

The brief's interpreter `/mpac/sdicks02/repos/clasher/.venv/bin/python` does not exist (there is no `.venv` in
that checkout). Tests were run with `/mpac/sdicks02/venvs/t1-verifier/bin/python` (Python 3.12.12, numpy 2.5.3,
pytest 9.1.1), under `nice -n 19`.

## Files

| File | Role |
|---|---|
| `verify_k4s.py` | The verifier. CLI: `--root`, `--ledger`, `--release`, `--synthetic`, `--c-star {0.9,0.8}`, `--compare`, `--out`, `--repo`. |
| `test_verify_k4s.py` | Pytest suite. Synthetic trees only. Test-only sizes come from the `--test-counts` hook, which is accepted only with `--synthetic` and a `SYNTHETIC` marker. |
| `VERIFIER-NOTES.md` | This file. |

Exit codes: 0 clean, 1 flags only (including `SUSPENDED` validity and `c_star` mismatch), 2 refusal, errors, or
comparison mismatches, unmatched items, or ambiguous matches.

## Transcription (constant → source)

| Constant | Value | Source |
|---|---|---|
| `COORDINATOR` | `0523ae6f-baa3-4d4e-b233-b392671670db` | Spec §7; r3 §4.5 |
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

These are the choices the verifier makes where the text is open. Each one is also a place where the reducer might
read it differently, so the coordinator should check them against the reducer.

1. **Replacement `k` is 0-based.** Only a 0-based `k` fills the banks exactly: 12 × 50 = 600 primary, 10 × 18 = 180 guard.
2. **Game file location.** `<root>/<id>/games/<id>-d27-<arm>.json`, where `<id>` is the block's own id (for a
   replacement, its replacement index). The `games` map key in `complete.json` must equal that file name.
3. **`replaces` may be the immediate lost id or the logical original id.** Both are accepted. The logical index is
   resolved through the chain.
4. **Replacements inherit** the lost block's logical index, rotation, arm set and cell ([I-1]). The verifier checks
   the replacement's own descriptor against its logical index, so a wrong rotation or cell is an error.
5. **Subsample membership uses the logical index.** `L < 600` (primary) and `L < 300` (guard).
6. **Cell-level bootstrap draws happen only for non-empty cells.** No cell is empty in the configured sizes.
7. **Δ_same(0.8) is on primary full.** K4-160 is on every block. Δ_same(0.7) and (0.6) are on primary subsample,
   where K4-140 and K4-120 exist.
8. **Losses come from `metadata.winner` and the descriptor's `seat`.** Any stored `loss` or `draw` field is ignored
   (§6.2).
9. **`freeze_manifest_sha256` must be non-null in every counted game** (§5: null only in qualification and smoke).
10. **`c_star` is an input.** The verifier does not derive it from X4S-2 phase E. A games-versus-`--c-star`
    mismatch is a flag.
11. **Under c* = 0.8**, the veto is reported as descriptive (r3 §1.3). Usable 0.9 is False, because A(0.9) is not tested.

## Ambiguities found in the spec and r3 (r3 governs)

- **A1 (release item shape).** §7 says each item's `git show commit:path` hashes to a declared sha256. It does not
  say how the receipt declares path and sha256. I used `items[name] = {"path": ..., "sha256": ...}`.
- **A2 (completion receipt fields).** §7 item 1 requires `reporting_complete`, `outcomes_sealed`, and "3000 / 900
  counted", without field names. I read `counted.primary == 3000` and `counted.guard == 900`. Confirm the names.
- **A3 (commit ancestry).** §7 says the commit must be an ancestor of HEAD. It does not say whose HEAD. I use the
  repository at `--repo` (default: the verifier's own repository).
- **A4 (replacement caps).** r3 §3.4 gives both "300 primary / 90 guard in total" and "k ≤ 11 / k ≤ 9" per cell.
  With 0-based `k` the per-cell bank alone allows 600 primary, so the total cap binds first. Both are enforced.
- **A5 (`replaces` field).** Spec §3 says `replaces` is "the logical original id", while §3's logical-index rule
  says to follow the chain. These agree only for a single-level replacement. See interpretation 3.
- **A6 (game file location and key).** Spec §6.1 says "`<id>/complete.json` + `games/`". §5 says
  `games/{pop}-{index:04d}-d27-{arm}.json`. The directory is ambiguous. See interpretation 2.
- **A7 (guard subsample is unequal).** L < 300 spread over 18 cells gives 16 or 17 rows per cell. r3 does not say
  so. The stratified bootstrap handles it, because `n_c` is per cell.
- **A8 (subsample bootstrap stream).** r3 §5.1 says "shared across all contrasts within a population". The
  subsample analyses resample different row sets, so they are separate draws. The spec's RNG order is what
  makes the subsample draws reproducible, and that order is an implementation choice.
- **A9 (veto under c* = 0.8).** r3 §1.3 says K4@0.9 and K4S@0.9 "become descriptive". Spec §6.5 still calls the
  veto a gate. I report it as descriptive at c* = 0.8. It cannot admit anything either way, because A(0.9) is
  not tested.
- **A10 (c* provenance).** r3 §1.3 says the coordinator applies the phase E rule before freeze and records it.
  The verifier takes `--c-star` as input and flags a mismatch with the games' `c_star`. The phase E rule itself
  is outside this tool.
- **A11 (hub acknowledgement).** §4.4 says blocks are "hub-acknowledged when the host is not 127x01". The format
  is not given. I flag an unacknowledged non-01 block (key `hub_ack`), but I do not gate on it, because §6.2 does
  not list it among the counting rules.
- **A12 (`study` string).** §5 gives `study` = `PREREG-K4S` "(with SEALED)". I check the `PREREG-K4S` prefix.
- **A13 (block that fails counting).** §6.2 says "a block counts if ...". A failing block is not counted, which
  makes the logical count short, which is an error. I report the failure directly. Both paths fail closed.
- **A14 (unreplaced loss).** §6.2 does not say what to do with a ledger loss whose replacement is null. I treat it
  as an error, since the logical count would fall short anyway.

## Not implemented (out of scope for this task)

- §6.6 secondary outputs: F1, the flagged-block sensitivity on `default_rng(2026101171)`, the matchup-cluster
  bootstrap on `2026101172`, per-host and per-seat tables, mechanism rates, latency, draws-as-half, and
  monotonicity. None of them can change admission.
- Derivation of c* from X4S-2 phase E, and the c_e mapping from c_M (the Mac measurement).
- Verification of the TIERS release barrier contents. The seal checks only its declared sha256.
- Interference flags (OP-6/OP-7), and matchup or per-host analyses.

## Comparison (`--compare`)

- Matching is by meaning, not by path. A reducer leaf matches when each alias group occurs in its normalised
  path (lowercase, `Δ` spelled out, only `a-z0-9`). Groups cover the analysis (`primary`/`pfull`, `full`/`sub`),
  the arm (`K4S-180` → `k4s180`, `k4s09`), the quantity (`loss`, `draw`), the contrast (`dref09`, `deltaref09`,
  `dsame08`), the bound (`lower`, `upper`), the hypothesis (`h1`, `passed`), admission (`admission`, `08`), and
  usable (`usable`, `08`).
- Missing, ambiguous and conflicting matches are reported and make the exit 2. Nothing is guessed. A `frac` item
  that matches both an exact and a float twin takes the exact one. A float match is accepted within 1e-9.
- The reducer's leaf names are not known to me. A reducer that names things very differently will show up as
  `unmatched`, which is the intended failure mode. The coordinator should read the unmatched list.

## Test results

Command: `nice -n 19 /mpac/sdicks02/venvs/t1-verifier/bin/python -m pytest -q reports/explore/k4s-confirm/verifier`
Result: **41 passed in 2.78s.**

Coverage: seal refusal (no release and no SYNTHETIC, wrong coordinator, hash mismatch, missing item, non-ancestor
commit, wrong completion counts, and a bad release refusing before any game bytes); SYNTHETIC marker and flag
gating; loss and draw rule on integer tables; replacement chain (two levels), wrong index, cell mismatch, per-cell
bank cap, population 10% cap, unreplaced loss, missing logical block, arm set against descriptor, SHA-256 of a
tampered game, non-terminal game, and qualification records in counted blocks; exact percentile by hand and at an
integer position; bootstrap RNG consumption; strict SUP and inclusive margins; within-one-step flag; sequence stops
at the first failure; H4 dropped at c* = 0.8; level A falling back to B; veto inclusive at 5; usable cells; validity
window inclusive at 10% and 30%; end-to-end CLI; `--compare` on its own output (all matched), and a tampered count
caught (exit 2).

**Full-size check (outside the repo, not committed):** a 3000/900 synthetic tree with 33,000 games and 3 replacements
loads and counts correctly (3000 and 900 logical blocks, 600 and 300 in the subsample). The verifier ran in
about 4 seconds wall, and two runs gave identical JSON. Exit 1 there is expected: the synthetic K4-200 loss rate
(33.3%) is outside the validity window, so the run reports SUSPENDED. Primary K4-200, K4S-180 and K4S-160 losses (1000 each) match an independent recount from the
game files.
