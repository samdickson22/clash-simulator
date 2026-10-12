# Addendum r1 to release review 977c4dfb (REVIEW-T1-RELEASE-BARRIER-R2-20261010T1842Z.md)

- **Reviewer:** independent Opus reviewer, read-only. No outcomes read.
- **Written:** 2026-10-12T08:48Z.
- **Authority:** R1 9897216c §3; investigation §5.
- **Companion:** `LANDING-OP7-REVIEW-r1.md` (verdict APPROVE).

## Statement being amended

977c4dfb line 53 says: "`reduce.py`, `common.py` and `barrier.py` are unchanged since 64608f6f."

That statement was true for the branch it reviewed, 11dcb034, where reduce.py was 7216fa50, the same as 64608f6f. It no longer holds for main. All hashes below are sha256 of the git blobs.

| file | 64608f6f / 11dcb034 (reviewed) | c5b2e059 → 597b0964 (admitted) | 1cb46a13^ | 1cb46a13 (landing) |
|---|---|---|---|---|
| reduce.py | 7216fa50 | fdea088c | fdea088c | **aebb2017** |
| common.py | 36e5eec3 | 36e5eec3 | 36e5eec3 | 36e5eec3 |
| barrier.py | 346d3c05 | 346d3c05 | 346d3c05 | 346d3c05 |
| release_reference.py | 9cab934c (64608f6f) | f8b61c60 | f8b61c60 | f8b61c60 |
| check_reference.py | 62dff3ad (64608f6f) | c848baa2 | c848baa2 | c848baa2 |

## Confirmations

1. **barrier, release_reference, check_reference and common are untouched by the OP-7 landing.**
   - All four have the same bytes at 1cb46a13^ and 1cb46a13.
   - barrier.py and common.py are also byte-identical to what 977c4dfb reviewed.
   - release_reference.py and check_reference.py have their c5b2e059 integration bytes, which R1 names as the release lineage ("run from main's lineage, which carries c5b2e059's barrier, release_reference and check_reference"). Their pre-integration revisions at 64608f6f are outside this addendum.
2. **The reducer chain since 977c4dfb has two steps. Both add only prespecified descriptive sensitivity analyses.**
   - **7216fa50 → fdea088c** (OP-6 d60586b3, merged in c5b2e059 and confirmed by 9118153b):
     - each row gains `complete_sha256=sha(f)`, and no statistic reads it;
     - after `result['timing']`, the OP-6 `ssh_sensitivity` analysis plus `disclosure.ssh_flagged_blocks` are added.

     This step was already on main before the landing. The 977c4dfb claim had silently gone stale at c5b2e059. OP-6 confirmation 9118153b covers it ("The reducer's primary path is unchanged in values and RNG stream").
   - **fdea088c → aebb2017** (OP-7, landed byte-exact from ef4c073a / 488f6c8d) is the only reducer delta in this landing, +7/−1:
     - the import is widened to `analyze_apt` and `analyze_union`;
     - `result['apt_sensitivity']` and `result['ssh_or_apt_sensitivity']` are added, each with `ledger_sha256`;
     - `disclosure.apt_flagged_blocks` and `disclosure.ssh_apt_flag_counts` are added.

     These are exactly the OP-7 prespecified apt and SSH∪apt analyses, as PC4 text 9b0704e2 requires. They are `DESCRIPTIVE_ONLY` with `selection_eligible=False`.
3. **The primary analysis and its RNG are unchanged.**
   - From 7216fa50 to aebb2017, every line through `result['timing']` is unchanged except the unread `complete_sha256` row field. That covers `stratified_counts`, `population_stats`, `timing_stats`, selection and `load_blocks` logic.
   - `outcome_release` still runs (line 120) before `load_blocks` (line 123), so 977c4dfb's "Reducer order" finding still holds.
   - The primary generator `np.random.default_rng(cfg['bootstrap']['seed'])` is consumed only by the primary and timing statistics, and those finish before any sensitivity code runs.
   - Each sensitivity analysis draws from a fresh `rng_factory(seed)`.
   - plan.json and schedule.py are unchanged by the landing.
   - The frozen tests `test_apt_sensitivity_is_separate_and_primary_rng_unchanged` and `test_union_sensitivity_and_both_flag_counts_never_change_primary_rng` pass on the ef4c073a export (99/99).
   - The landing-tree `test_reduce` and barrier suites pass (174/174 in the R1 set).

## Residual

Sensitivity code runs before `write(a.out)`, so a sensitivity assertion would abort the reducer before it writes the primary result. That is the same design OP-6 F2 accepted.

PC4, already passed under 3c29de85, plus the pending second PC4 run from the landed bytes are the pre-release guards. R6 must also confirm that the reducer's emitted ledger equals the PC4 sidecar except for `utc`.

As amended here, the conclusions of 977c4dfb are unchanged: barrier gate, no outcome reads before release, reducer ordering, Amendment 1/E4 compatibility.
