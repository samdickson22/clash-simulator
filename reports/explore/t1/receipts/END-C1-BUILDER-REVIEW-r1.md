# T1 END C1: descendant builder protection review r1 (builder-only)

- **Reviewer:** Claude Opus 5.5, the independent reviewer of driver r1–r3. I did not write the builder, the driver or the tests (author: GPT-6.1-Sol worker). This is a read-only review, written at 2026-10-12T12:43Z (`date -u` 12:42:36Z at the start of writing).
- **Subject:** origin/main **e75da724**.
  - `reports/explore/t1/prepare_release_descendant.py`, sha256 **dd644cdc…7259** (was 86ae8202 at f45a3ad8).
  - Delta `receipts/END-C1-builder-protection-r1.diff`, sha256 **815710b2…6aa6**. It is byte-identical to `git diff f45a3ad8 e75da724 -- prepare_release_descendant.py` and to the job-dir copy.
  - `release_run.py` is **9ffbd2e1…8bca**; `git diff f45a3ad8 e75da724 -- release_run.py` is empty.
  - The committed `END-C1-RELEASE-DRIVER-REVIEW-r3.md` is byte-identical to my r3.
- **Scope kept:**
  - No SSH, no edits except this file, no commits.
  - I did not run the builder, `switch` or the driver on `<R>` or on real data.
  - The only non-synthetic reads were of git metadata in the shared clone (`for-each-ref refs/private`, hooks, `cat-file -e` on 9bb349b1 paths) and the SHA-256 hashes of the runbook's builder directory.
  - Everything else ran on a `git archive e75da724` export and on throwaway repos in `/tmp`, using e4v3-venv 3.12.12 (`-B`, `PYTHONDONTWRITEBYTECODE=1`, `nice -n 19`) and git 2.25.1.
  - Tools are in `/tmp/sdicks02/c1rev/builder-r1/tools/`: `mut_b1.py`, `alias_probe.py`, `headmove_sim.sh`. Outputs are `mut-b1.txt`, `alias-probe.json` and `headmove-sim.txt` beside them.

## Verdict: **APPROVE_WITH_CONDITIONS**

**Builder dd644cdc is approved to run once on `<R>`, after the coordinator's state-change GO, under BC1 and BC2.**

The r3 C1 fix is correct and complete for the stated threat:
- The builder refuses the protection ref.
- It creates the new ref only if absent, with a zero-old CAS.
- It checks the protection ref's value before any write and after `update-ref`.

No alias of `refs/private/t1-registration-20261012` can be written, and the protection ref survived every probe.

Both conditions are **runbook/operator-only**, so the builder and driver SHAs do not change:
- **BC1** closes a dangling-symref deref escape.
- **BC2** puts the HEAD-move `switch` under the same clean environment as the checks.

## 1. Fix correctness

The delta has exactly three behavioural changes, plus the `PRIVATE_REF` import:

| Requirement | Implementation | Verified |
| --- | --- | --- |
| Refuse the protection ref | `require(private_ref != PRIVATE_REF)`, before any git call | Exact name refused with `ValueError`, loose or packed, and no refs added |
| Absent-only creation | `git update-ref <ref> <commit> 0000…0000` (40 zeros, SHA-1 repo), meaning "must not exist" | An existing target is refused ("reference already exists") and its value is unchanged (rerun probe and test) |
| Protection value before | `rev-parse PRIVATE_REF == PRIVATE_COMMIT` as the first git call, before the clean check, `read-tree`, any object write or any ref write | Yes |
| Protection value after | The same check immediately after `update-ref`; raises `ValueError` | Yes. Fail-closed: the new ref stays, but the operator stops on any exception (runbook) |

**Alias probes** (`alias_probe.py`, 21 cases, synthetic). In every case the protection ref stayed at base.

| Candidate name | Outcome |
| --- | --- |
| exact (loose / packed) | `ValueError` (refusal) |
| `refs/private//t1-…`, trailing `/`, `/./`, `x/../`, trailing `\n`, trailing space, `.lock`, `@{0}`, `^{}` | git refuses the bad refname, so nothing is written |
| `…/t1-registration-20261012/child` (loose / packed) | D/F lock conflict, so nothing is written |
| symref `refs/private/alias` → protection (loose / packed) | CAS derefs to the existing protection ref, giving "already exists", so nothing is written |
| re-run onto an existing private ref | CAS refuses, so nothing is written |
| case variant `refs/private/T1-REGISTRATION-…` | Builds a *distinct* ref on Linux. Harmless: the protection ref is unchanged and the driver uses the exact full name |
| nested `refs/private/refs/private/t1-registration-20261012` | Builds a distinct ref. **No shadowing:** `rev-parse` of the full name takes the exact-path rule first |
| fresh name (loose / packed protection) | Builds; positive control |
| **dangling symref** `refs/private/dangling` → `refs/heads/escaped` | **Builds and creates `refs/heads/escaped`** at the private descendant (finding B4, condition BC1) |

**Point-at and shadow.**
- The new ref is always a direct ref to a fresh two-parent commit, which can never equal 9bb349b1. The builder never runs `symbolic-ref`.
- Nothing the builder writes can change what the full name `refs/private/t1-registration-20261012` resolves to.
- I also forced the worst case: a dangling symref targeting `refs/heads/refs/private/t1-registration-20261012`. `rev-parse` of the full name still returns 9bb349b1; it only adds an "ambiguous" warning on stderr, which `check_output` ignores.

**B4 (low): dangling-symref deref escape.**
- `update-ref` without `--no-deref` follows a pre-existing symbolic ref at the target name. If the target dangles, the zero-old CAS passes and the ref is created **outside `refs/private/`**. That can be a `refs/heads/*` branch that a push of `--all`/`--mirror` or that branch would carry.
- The driver's `refs/remotes` exclusion does not see local heads.
- **Ordinary "fresh name" checks miss it:** `git rev-parse --verify -q <ref>` and `git show-ref <ref>` both report a dangling symref as absent (rc 1); only `git symbolic-ref -q <ref>` exposes it.
- Present state of the shared common dir: `refs/private/` holds only the loose protection ref (9bb349b1, not symbolic), with no packed `refs/private` entries and no active hooks. So the risk is latent, not live.
- `--no-deref` would replace a dangling symref in place, staying inside `refs/private/`, and still refuses a symref to the protection ref (probed). That is the better code fix whenever the builder is next revised. For now, BC1 closes it operationally without changing the SHA.

**Minor (informational):** `rev-parse PRIVATE_REF` uses DWIM. It would fall through to `refs/heads/refs/private/…` only if the real protection ref were *deleted* and such a branch existed. The approved driver uses the same idiom, so this is not a builder regression. `show-ref --verify` / `for-each-ref <exact>` would be the stricter form in a later revision.

## 2. Mutants

**Full rerun** (`mut_b1.py`): the r3 list, with the D12 pattern updated to the new `update-ref` line as the author did, plus 11 new protection mutants BP1–BP11. The unmodified suite passed 55/55 on 3 runs (`-m unittest`). **Result: 108 killed, 7 survived.**

- **Required:** R1–R24, AL1/AL2/AL5, T2c and **D1, D3, D5 are all KILLED**. This agrees with the author's `END-C1-conditions-mutant-rerun.txt` (100/104).
- **D7 (rename detection in the builder diff): equivalent.** The temp index starts from `read-tree 9bb349b1` and only gains `update-index --add --cacheinfo` entries at allowlisted names. Without `--replace`, git refuses D/F conflicts both ways (probed: rc 128, "appears as both a file and as a directory"). So the diff has no deletions, rename/copy pairing cannot occur, and `--name-only` output is identical. I probed it with `diff.renames=copies`: same output.
- **D8 (no post-build allowlist check): equivalent,** by the same argument. The changed set is a subset of the allowlist by construction. The check stays as defence in depth.
- **T2g / T2h: acceptable residual.** They live in the unchanged driver 9ffbd2e1 and are signal-delivery windows between bytecodes in `_main`/`execute_guarded` that no deterministic unit test can hit. I accepted them in r3 by inspection; nothing in this delta touches them.
- **New protection mutants:**

| Mutant | Result |
| --- | --- |
| BP1 drop exact-name refusal | KILLED (the test expects `ValueError`, while CAS alone gives `CalledProcessError`) |
| BP2 plain `update-ref` (no CAS) | KILLED |
| BP3 no refusal and no CAS | KILLED |
| BP5 drop after-check | KILLED |
| BP6 after-check moved before `update-ref` | KILLED |
| BP8 CAS old = 9bb349b1 | KILLED |
| BP10 after-check existence-only | KILLED |
| BP11 refusal only of `PRIVATE_REF/…` children | KILLED |
| BP7 CAS old = `""` | SURVIVED, **equivalent** (git documents empty and zero as the same "must not exist") |
| **BP4** drop the before-check; **BP9** before-check existence-only | **SURVIVED: test gap** (B5) |

**B5 (low, test-only).** `test_changed_protection_ref_before_build` still passes when the before-check is removed, because the after-check also raises `ValueError`, but only after objects and `refs/private/fresh` were written. The code is correct by inspection and by my probes (the before-check is the first git call). The test should assert that `refs/private/fresh` is absent after the refusal. This is non-blocking.

**B6 (low, test-only).** In `test_release_run.py`, `if __name__ == '__main__': unittest.main()` now sits **before** `MacGateContractTests`, `MacBindingTests` and `BuilderRefTests`. `python -B test_release_run.py` runs **43** tests and silently skips all 12 new ones, including every builder-ref test (reproduced). The author's receipts and both mutant runners use `-m unittest`, which runs 55, so the evidence holds. Move the guard to the end of the file at the next test edit. Until then, any receipt must use `-m unittest` and show 55.

## 3. Runbook HEAD-move step (C2/C3/C5)

**Simulation** (`headmove_sim.sh`). I built a synthetic linked worktree mirroring `<R>`: a private base, a divergent public Mac source, `tiers-session-r1/` absent from the base, and `e4v3` at 555. The builder ran under `env -i … -B`, then the literal runbook `switch --detach`, then the literal post-checks:

| Fault injected | Caught by |
| --- | --- |
| none | **all checks pass**; e4v3 still 555 |
| switched to base instead of descendant | HEAD, parents |
| switched to the public source | HEAD, parents, allowlist |
| untracked file / ignored file / modified tracked file before the switch | `status --porcelain --ignored` (`switch` carries all three across with rc 0, so the status check is load-bearing) |
| protection ref moved after the switch | protection check |
| e4v3 755 / 1555 | `stat -c %a` ≠ `555` (exact string, so special bits are also caught) |
| read-only Mac parent dir | `switch` rc 128 *before* any change: HEAD unchanged, tree clean, then caught by HEAD/parents. Clean fail-closed, no partial state |

The post-checks catch a wrong HEAD, a dirty tree, a moved protection ref and a lost mode 555. The 3-token parent check (`descendant base source`, in order) is strong. Real `9bb349b1` lacks `reports/explore/mac-e4-session/tiers-session-r1`, so `switch` must create it. If the frozen `<R>` has a non-writable parent, the switch fails cleanly as above; checking `test -w` first would save a stop/ruling round-trip.

**Gap (BC2).** The runbook places the `switch` command itself outside the clean environment: only the *checks* run "under the same clean environment". `git -C <R>` does not override an inherited `GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE`. A stray `GIT_DIR` pointing at the shared clone would detach and rewrite *another thread's* checkout or index. The `<R>` post-checks would then fail (HEAD unchanged), but only after the foreign tree was touched. Hooks: the shared clone has none active, but `-c core.hooksPath=/dev/null` costs nothing.

**C3 / C5 / C4 text:**
- The runbook pins builder dd644cdc and Mac-route driver 9ffbd2e1. It requires a committed-only directory, a fresh `refs/private/` name that is never the protection ref, `env -i` with HOME and `PATH=/usr/bin:/bin`, `-B`, and `nice`/`taskset`.
- The cited builder directory currently hashes to dd644cdc (builder) and 9ffbd2e1 (`release_run.py`), at e75da724.
- The 14-day route is restricted to 42219e57 with HEAD at 9bb349b1 and an empty diff, never r3.
- **C3, C4 and C5 are satisfied. C2 is satisfied apart from BC2.**

## 4. Nothing else changed

- Between f45a3ad8 and e75da724, `reports/explore/t1/` changes only:
  - the builder (+5/−2, the reviewed delta);
  - tests (+188, additions only);
  - the runbook, PROGRESS and receipts.
- `release_run.py` is byte-identical (9ffbd2e1), and no other `.py` changed. The builder's module docstring, `main()`, the allowlist logic, the temp index, the `100644 blob` gate and the commit construction are unchanged.

## Conditions

**BC1. Fresh-ref pre-check (runbook/operator; no SHA change).**
- Immediately before the builder, from `<R>` under the clean environment, record that the target name is wholly unused:
  - `git symbolic-ref -q "$release_fresh_ref"` exits 1;
  - `git for-each-ref "$release_fresh_ref"` is empty;
  - `git for-each-ref "$release_fresh_ref/"` is empty;
  - `$(git rev-parse --git-common-dir)/$release_fresh_ref` does not exist.
- After the builder, record that:
  - `git symbolic-ref -q "$release_fresh_ref"` still exits 1;
  - `git rev-parse "$release_fresh_ref"` equals the receipt `commit`;
  - `git for-each-ref --contains <commit> refs/heads refs/tags refs/remotes` is empty.
- Alternatively, add `--no-deref` and a symref refusal to the builder. That is a new SHA and needs another narrow review.

**BC2. Run the HEAD move in the clean environment.** Use exactly:
```
env -i HOME="$HOME" PATH=/usr/bin:/bin \
  git -c core.hooksPath=/dev/null -C <R> switch --detach "$release_descendant_sha"
```
- Run the post-checks under the same `env -i`.
- Optionally `test -w <R>/reports/explore/mac-e4-session` first; a failure there stops for a ruling.

## Suggested (non-blocking)

- B5: assert `refs/private/fresh` is absent in `test_changed_protection_ref_before_build`, which kills BP4/BP9.
- B6: move `if __name__ == '__main__'` to the end of `test_release_run.py`.
- At the next builder revision: use `update-ref --no-deref` and resolve the protection ref with `show-ref --verify` / exact `for-each-ref` instead of DWIM `rev-parse`.

## Re-review scope

- **BC1/BC2:** runbook text plus the operator receipt only. I can verify them without a code review.
- The builder dd644cdc and the driver 9ffbd2e1 need no further code review for the Mac route.
