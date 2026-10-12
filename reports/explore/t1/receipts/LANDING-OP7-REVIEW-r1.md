# Landing review r1: 1cb46a13 (exact frozen OP-7 release lineage + PC4 evidence)

- **Reviewer:** independent Opus reviewer (read-only). No SSH, no edits to the repo or the job roots, no commits, no outcomes read.
- **Written:** 2026-10-12T08:48Z.
- **Landing:** `1cb46a138788a4dde81bc74f7313f07804e15bfc` on origin/main (parent 408f8779). Author T1 (Sol).
- **Authority:** COORDINATOR 9897216c (R1) and 3c29de85 (PC4 PASS); `END-PC4-LINEAGE-INVESTIGATION-r1.md` §3.3, §5.

## Verdict: **APPROVE**

All five release files are byte-exact copies of tag `t1-op7-freeze-ef4c073a`, and each equals its entry in the OP-7 manifest 488f6c8d. No protected file changed: FROZEN-T1, host_audit, ssh_budget, supervise, barrier, release_reference, check_reference, common, plan, schedule, and all 125 e4v3 files.

The reducer delta is exactly the prespecified OP-7 sensitivity additions. The SSH, apt and union readers in the landed tree give the same flags as the frozen tree on OP-7-written proofs. My rerun of the R1 landing tests passed (174/174), as did the full frozen `test_op7` (99/99).

The notes below are informational and need no action. The second PC4 run from the landed bytes, which 3c29de85 already requires, remains the end-to-end confirmation.

## 1. The five files are byte-exact (PASS)

Each hash is sha256 of `git show <rev>:reports/explore/t1/<f>`.

| file | ef4c073a | 1cb46a13 | 488f6c8d `files` entry | parent (main before) |
|---|---|---|---|---|
| ssh_sensitivity.py | bb124cc4 | bb124cc4 | bb124cc4716d…a0e5 | e643a342 |
| reduce.py | aebb2017 | aebb2017 | aebb2017d1ee…fe79 | fdea088c |
| apt_budget.py | c1578535 | c1578535 | c15785357a95…8618 | absent |
| cpu_accounting.py | 5ecae99d | 5ecae99d | 5ecae99d9097…c06f | absent |
| RELEASE-PRODUCTION-CHECKS-20261010.md | 9b0704e2 | 9b0704e2 | 9b0704e2e8c5…337a | ff0b7afe |

- The git blob IDs are also identical between the tag and the landing.
- `ef4c073a:reports/explore/t1/FROZEN-T1.json` has sha256 488f6c8daccc…b12e.
- The tag `t1-op7-freeze-ef4c073a` is an annotated tag and dereferences to ef4c073a4c69….

## 2. Added files (PASS, with note N1)

`git diff --name-status 1cb46a13^ 1cb46a13` lists 14 paths. Apart from the five files in §1:

- `receipts/release-lineage-op7-20261012.json` was added, as R1 requires.
- `receipts/PC4/` holds four files, each byte-identical to the reviewer's job-dir copy:

  | file | sha256 |
  |---|---|
  | ssh-sensitivity-pc4.json | ea3d44d3 |
  | PC4-REVIEWER-CHECK-RECEIPT.json | 48fe1011 |
  | PC4-REVIEW-r1.md | 11bbfc9a |
  | pc4_reviewer_check.py | 5c4cdada |

- `receipts/END-PC4-LINEAGE-INVESTIGATION-r1.md` (cb06af0b) is byte-identical to the job-dir file.
- `receipts/END-R1-PC4-LINEAGE-RULING-9897216c.md` is exactly the 37 lines that 9897216c added to COORDINATOR.md: a leading blank line plus the R1 section, so it is verbatim.
- **N1.** Two more paths are in the commit but not in the R1 enumeration:
  - `receipts/END-OP7-release-landing-validation.json` (added);
  - `PROGRESS-T1.md` (+2 lines: one checkpoint).

  Both are T1 bookkeeping with no code effect, and the validation receipt matches the lineage receipt's test records. I see no issue, but I'm recording them because the brief said "only".

## 3. Nothing else changed (PASS)

- The diff touches only `reports/explore/t1/`. The diff stat is 14 files, +48978/−9, and every deletion is a replaced line in reduce.py, ssh_sensitivity.py or the PC text.
- The following are unchanged between the parent and the landing:

  | file | sha256 |
  |---|---|
  | FROZEN-T1.json | 24817e16 |
  | host_audit.py | 5717d01c |
  | ssh_budget.py | 0c2759f5 |
  | supervise.py | d4028d92 |
  | barrier.py | 346d3c05 |
  | release_reference.py | f8b61c60 |
  | check_reference.py | c848baa2 |
  | common.py | 36e5eec3 |

  plan.json, schedule.py and test_reduce.py (e2ec8095) are also unchanged.
- **e4v3:** the tree at `…/mac-e4-package/e4v3` is 970bb619 at 8799a0d6, at the parent and at 1cb46a13 alike. `git diff 8799a0d6 1cb46a13 -- '*e4v3*'` is empty, and the 125 files are unchanged.
- The lineage receipt's `protected_file_SHA_before` and `protected_SHA_after` list 132 entries, all identical. Every one matches both the parent and the landing; I recomputed all 132.

## 4. Imports from main's ssh_budget 0c2759f5 (PASS)

- `ssh_sensitivity.py` bb124cc4 imports `lan_connection`. `apt_budget.py` imports `generation` and `total_ticks`.
- In main's 0c2759f5, all three definitions are byte-identical to the frozen OP-7 ssh_budget 0ef24fac. The only difference in that region is OP-7's extra `from cpu_accounting import Accounting,RULE` line, which these readers don't use.
- In the landing tree (cpython 3.12.12 e4v3-venv, `-B`), all modules import cleanly. `ssh_sensitivity.lan_connection`, `apt_budget.generation` and `apt_budget.total_ticks` are the very objects defined in ssh_budget, and `RULE == 'OP-7-observed-child-credit-v2'`.
- **Cross-tree reader check:**
  - I built 9 interference proofs with the **frozen** OP-7 writers (`apt_budget` and `ssh_budget` from ef4c073a). They cover apt ticks 0/30/31/600/601, LAN SSH ticks 0/31/601, and the legacy `{}`.
  - I evaluated `flagged`, `apt_flagged` and `union_flagged` with both the landed tree and the frozen tree. The outputs are **identical**, including the 0.5% boundary (30 not flagged, 31 flagged) and fail-closed legacy handling.
- **N2.** The full frozen `test_op7` fails 31/99 when run *inside the landing tree*. The cause is the test fixtures, not the reader:
  - `paired_apt()` fabricates its SSH meter with main's OP-6 `ssh_budget.begin/finish`, which emit no `cpu_accounting_rule`, so bb124cc4 correctly rejects it with "new phase requires matching apt and SSH v2 meters".
  - The other failures test OP-7 writers (`host_audit`, the `ssh_budget` accounting), which R1 deliberately leaves at OP-6.

  This is why R1 runs `test_op7` on the `git archive ef4c073a` export. It is not a landing defect.

## 5. Reducer aebb2017 (PASS)

- `outcome_release(ROOT,a.release)` is at line 120, before `load_blocks` at line 123, as in fdea088c.
- The only delta from fdea088c (`git diff 1cb46a13^ 1cb46a13 -- reduce.py`, +7/−1) is:
  - the import widened to `health_ledger,analyze,analyze_apt,analyze_union`;
  - `result['apt_sensitivity']` and `result['ssh_or_apt_sensitivity']`, each with `ledger_sha256` = the same sensitivity ledger sha;
  - `result['disclosure']['apt_flagged_blocks']` and `result['disclosure']['ssh_apt_flag_counts']` (= `sensitivity_ledger['flag_counts']`).

  That is two top-level result keys plus two disclosure sub-keys. They are exactly the prespecified OP-7 apt and union analyses, and R1's required keys `apt_sensitivity` and `ssh_or_apt_sensitivity` are present.
- **Primary analysis and RNG:**
  - Every line up to and including `result['timing']` is byte-unchanged.
  - The primary `rng=np.random.default_rng(seed)` is consumed only by `population_stats` and `timing_stats`, and both run before any sensitivity code.
  - Each sensitivity analysis creates its own generator through `rng_factory(seed)`.
  - bb124cc4's `analyze()` defaults (`flag_key='ssh_flagged'`, `flag_fn=flagged`, and the same rule string) keep the SSH analysis unchanged.
  - The frozen test `test_apt_sensitivity_is_separate_and_primary_rng_unchanged` and the union test both pass.

## 6. Lineage receipt `release-lineage-op7-20261012.json` (PASS, with notes N3–N4)

I recomputed every hash claim from git:

- **landed_files:** all five are byte-exact, and their `frozen_manifest_entry` values equal 488f6c8d.
- **Manifest:** `OP7_manifest_sha256` = 488f6c8d at ef4c073a.
- **Tag:** `frozen_source_tag` and `tag_dereferenced_commit` are correct.
- **Reviews:** OP-7 reviews r1, r2 and r3 (1f073ab8, c6cbfb1b, f7826322) equal both ef4c073a and the 488f6c8d entries.
- **Confirmation:** the confirmation-receipt sha 0c99826b equals ef4c073a.
- **Reducer:** `release_reducer_sha256` is aebb2017.
- **Stale-entry disclosure (required by R1, accurate):**
  - `FROZEN_T1_unchanged_sha256` 24817e16, `FROZEN_T1_stale_for_landed_release_files: true` and `FROZEN_T1_role` are all present.
  - `stale_existing_entries` pairs each landed pin with its retained E4/OP-6 pin, and each retained pin equals the parent bytes: reduce fdea088c, ssh_sensitivity e643a342, PC text ff0b7afe.
  - `new_release_dependencies_not_in_E4_freeze` correctly lists apt_budget and cpu_accounting, which are absent from 24817e16.
- **N3.** `OP7_confirmation.commit` = 1947830b is the coordinator confirmation commit. The receipt *file* at `path` does not exist in 1947830b's tree; it was added at 04633bdb and is verified at ef4c073a. The field means "confirmation commit", not "where the path lives". The receipt's own content names 1947830b as `coordinator_confirmation_commit`. This is ambiguous but not inaccurate.
- **N4.**
  - FROZEN-T1 24817e16 was already stale on main before this landing for six paths: barrier.py, test_barrier.py (from c5b2e059), corpus.py, test_corpus.py, run.py and PROGRESS-T1.md. It also lacks release_reference.py and check_reference.py.
  - The receipt discloses only the three files this landing changes, which is within R1's scope.
  - I'm recording the wider staleness so nobody treats 24817e16 as a complete manifest of the release tree. The release tree's binding is R5's descriptor and pins, not 24817e16.
- **Cosmetic.** The receipt's top-level `utc` (08:33:57Z) is earlier than the test `finish_utc` (08:37:30Z) recorded inside it.

## 7. Tests (PASS, rerun independently)

- **Setup:**
  - interpreter: `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` (3.12.12, numpy 2.2.6), unmodified; it still has no pytest afterwards;
  - private pytest 8.4.2 via `uv pip --target` into a /tmp scratch dir on `PYTHONPATH`;
  - flags: `PYTHONDONTWRITEBYTECODE=1 -B -p no:cacheprovider`, `nice -n 19 taskset -c 0-3`;
  - tree: a scratch `git clone --shared` checked out detached at 1cb46a13. The tests need a git checkout, so `git archive` is not enough. The clone stayed clean.
- **Landing set** (test_reduce, test_op6, test_barrier, test_release_reference, test_reference_packet, e4v3/tests): **174 passed** in 128.9s. This matches T1's 174 passed in 122.6s.
- **Full `test_op7` on the `git archive ef4c073a` export:** **99 passed**, which matches T1.
- The scratch clone, deps and temp dirs were removed afterwards. Only the small cross-check scripts and outputs remain, under `/tmp/sdicks02-landing-op7-review-r1/{scripts,xchk}`.

## Notes (none blocking)

- **N1:** PROGRESS-T1.md and END-OP7-release-landing-validation.json are in the commit beyond R1's enumerated list. Both are bookkeeping.
- **N2:** `test_op7` can't run in the landing tree because its fixtures use the OP-6 writers on main. The reader equivalence was confirmed directly.
- **N3:** `OP7_confirmation.commit` names the coordinator commit, not the path's home commit.
- **N4:** FROZEN-T1 24817e16 has pre-existing staleness beyond the three disclosed files.
- **Still pending (not a condition of this review; 3c29de85 already requires it):** the second PC4 run from the *landed* bytes with `-B`. It imports main's ssh_budget 0c2759f5, which §4 shows to be reader-compatible, and must reproduce the sidecar 48730da5 except for `utc`.
