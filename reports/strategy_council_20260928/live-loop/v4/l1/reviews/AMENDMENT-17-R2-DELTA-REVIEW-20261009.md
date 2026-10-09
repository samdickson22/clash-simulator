# Amendment 17 r2 — delta review (code only)

Reviewer: independent Claude reviewer for coordinator 0523ae6f, 2026-10-09. The review was read-only. Tests, mutants and a probe ran on 127x04 under nice 19 in `/tmp/a17r2rev` (since removed), using `/mpac/sdicks02/envs/clasher-gpu/bin/python` 3.12, because the system python 3.8 and the repo `.venv` lack scipy. The 127x08 qualification directories were read only; both 08 runs had already exited 0. The §5 post-run check is out of scope.

## Verdict: REQUIRED CHANGES (one small guard)

## 1. Bytes

| Item | Recomputed | Status |
|---|---|---|
| r2 package | cfa5d4be…9277 | match |
| Draft | 58debcf4…5b03 | match |
| Delta | f7b66c05…a092 | match |
| Snapshot manifest | fb55483e…f14a | match |
| Test receipt | 7ace1401…175b | match |
| Reviewer tests (`test_reviewer_a17.py` in snapshot) | 985ad06b…cd3f | byte-identical |

- **Snapshot:** 333 files on disk, and all 333 match the manifest, with no extra or missing file. The delta's new and unchanged lists together cover exactly the manifest, with no hash differences. The unchanged-A16 list is identical to r1's, which was verified against A16 `2ced1534`.
- **Changes vs r1 (manifest d5635020):** exactly 5 files.
  - `evidence_recovery_a17_v4.py` and `dominance_orchestration_assembly_a17_v4.py`: the diffs are only the R17-1/2/3 guards.
  - `test_evidence_recovery_a17_v4.py`, `test_approval_shape_a17_v4.py` and `test_reviewer_a17.py`: tests.
  - The other A17 code files are byte-equal to r1.
- **Frozen records:** all are committed with no diff and match their pins:
  - `16-FREEZE` cae72ebd
  - supplement 3e5c04b8
  - `16-FILE-LAYER` approval 730c86e8
  - `16-delta` eafa80ff
  - `12-FREEZE` bd5b7643
  - `15-FREEZE` 33e3a071
  - A16 review 4e486c2c
- **r1 package unchanged:** package 7e773ec2, draft d9fa01eb, delta 518bf690, manifest d5635020 and test receipt a8d7b27b.

## 2. Enforcement

- **R17-1 (enforced).** `load_recovery` line 36 admits replacement hosts only in `('127x08','127x04')`. Host 02, leased 09/13 and 14/15 are refused, and so is OLD_QUAL on any host. The 09r1 corroboration run cannot be admitted.
- **R17-2 (enforced for stress).**
  - `verify_stress` lines 76–80 check every `c['source_sha256']` entry at the worker's parent, using the same idiom as A16 lines 41–42.
  - It also checks `<plan dir>/qualify_whole_match_v4.py == eba6349d`.
  - Both checks come before `io.hashes`, which rehashes on the host.
- **R17-3 (enforced).** The A1 approval holds a single scalar `evidence_recovery_approval_sha256`. Each of the 24 authorities must equal it (line 75), so the binding is identical across all 24 by construction. The approval file is actually rehashed (line 76). `load_recovery` re-opens the same receipt via `pinned`, which also rehashes it.
- **Gap (new, blocking): the qualifier is not pinned for replacement qualifications.**
  - The qualifier file is not one of the 27 contract sources. Neither `load_recovery` nor the unchanged A16 `verify_qualifications` checks it.
  - On 127x08, `v4-a17-qualification-08r1` (complete a7eb2600, plan 234f48ce) pins its plan-dir qualifier at **77c809f8**. It satisfies every check the code applies:
    - allowed host;
    - fresh SHA;
    - worker 70e8deaf;
    - all 27 sources at the worker's parent;
    - the 3 cells with 444/796/2416 frames;
    - `pass_nonclock=true`.
  - **The code would admit it if the recovery record listed it.** My probe confirmed this: a fixture plan pinning a 77c809 qualifier passes `verify_qualifications(qualification_view(...))` with no error.
  - "Corroboration only" is therefore a statement, not an enforced rule. Today only §5 item 3, a procedural check, prevents admission.
  - Scientific risk is low, because the verifier re-does all raw byte comparisons itself. But this is exactly the asymmetry R17-2 closed for stress.
  - 08r2 (complete 380da25b, plan 7429e5fe) pins the plan-dir qualifier at eba6349d. Note that both plans also pin `v4-vectorized-capture-r1/qualify_whole_match_v4.py` = 77c809, so the guard must key on the plan directory, not on the worker's directory.

## 3. Tests and mutants (127x04)

- **Tests:** the baseline passes: 147 executions OK with a single `-m unittest` over the 4 modules; the receipt's count of 116 used a different collection. The reviewer module alone passes 55 executions.
- **Mutants:** every mutant was killed by its intended test.

| Mutant | Killing test |
|---|---|
| M1: add 127x09 to the host allowlist | `test_leased_qualification_hosts_refused` (×3) |
| M2: qualifier check by presence only | `test_stress_bad_qualifier` (×3) |
| M3: source closure checks only the first entry | `test_stress_missing_source` (×3) |
| M4: approval binding checked for epoch 1 only | `test_epoch24_other_approval` |
| M5: approval rehash removed | `test_a1_changed_approval_receipt` |

## 4. Required change

**R17r2-1.**
- **Guard:** in `verify_replacement_evidence`, after `load_recovery` and before `verify_qualifications`, add a step that does the following for each replacement spec:
  - read its plan with `io.read(host, spec['plan'], spec['plan_sha256'])`;
  - require `plan['pins'][str(Path(spec['plan']).parent/'qualify_whole_match_v4.py')] == eba6349d…`.

  Putting the guard there, rather than inside `load_recovery`, leaves the verbatim reviewer fixtures valid.
- **Tests:** add one test showing that a 77c809 plan-dir qualifier is refused while eba6349d is accepted, and one mutant showing that removing the guard is killed.
- **Re-review:** a diff-only confirmation is enough.

## Summary

- **Bytes:** all r2 SHAs match, all 333 snapshot files match, and the delta covers the manifest exactly. The A12/A15/A16 freeze records and the r1 package are unchanged, and only 5 files changed vs r1.
- **Reviewer tests:** byte-identical (985ad06b) and passing.
- **Enforcement:** R17-1 (hosts 08/04 only; 09/13 refused), R17-2 (the 27-source closure plus the eba6349d qualifier on stress) and R17-3 (one approval SHA identical across 24 epochs, actually rehashed) are all enforced in code.
- **Mutants:** all 5 of my mutants on 04 were killed.
- **REQUIRED CHANGE:** replacement qualifications don't pin the qualifier. The 08r1 receipt on owned 08 used qualifier 77c809, yet passes every code check, and my probe confirmed admission. Add a plan-directory qualifier pin (eba6349d) for each replacement qualification, plus one test. A diff-only confirmation then suffices.
