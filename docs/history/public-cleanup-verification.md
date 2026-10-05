# Public cleanup verification

The comparison base is `3f2655757b22476e476d40a2686a1f40458285f4`, the main commit at the start of this cleanup. All edits and generated files stayed in the cleanup worktree. The main checkout supplied an existing Python environment and frozen inputs read-only.

## Scope

The changes move documentation and six utility entry points, update their references, remove three redistributed PDF copies, and add public documentation and artifact ignores. The root visualization module remains available through a compatibility symlink. Historical experiments are archived in place because runners validate source hashes, manifest paths, and process commands. Report directories and recorded acceptance pins stay in place.

Python changes remove unused imports, empty type-checking blocks, and unused local calculations. No functions, classes, public names, engine rules, or RL algorithms were changed. An AST comparison of changed Python files allowed only those reviewed edits and launcher path changes. The moved utilities were checked separately against their original ASTs. All 95 changed shell launchers passed their interpreter's syntax check.

Rust changes add parentheses matching existing operator precedence and whitespace around negative assignments. The build script defaults to a worktree-local Cargo target directory and accepts explicit build/interpreter overrides. Clippy completed with 29 warnings versus 48 before cleanup; remaining suggestions were left for separate review. The release build passed and `cargo clean` removed its intermediates.

## Test comparison

The segmented Python comparison has identical named outcomes after the complete-file fixture rerun. Local raw logs, JUnit XML, and comparison scripts are retained under the ignored `.cleanup-evidence/` directory.

| Python outcome | Pinned main | Final cleanup |
| --- | ---: | ---: |
| Passed | 5,909 | 5,909 |
| Failed | 232 | 232 |
| Errors | 54 | 54 |
| Skipped | 314 | 314 |
| Changed named outcomes | | 0 |

Failures and errors remain in the public checkout baseline. Missing frozen artifacts explain many of them; the cleanup does not claim that all failures are fixture-related or that the repository has a passing full suite.

The original Python baseline was interrupted before completion by the server restart. Its partial output was retained but not counted as a completed baseline. The replacement ran from a `git archive` copy of the pinned main commit. Both Python suites use the same Python 3.12 environment, dependencies, gamedata, one numerical-library thread, and nice 10. The native extension was built separately from each source version. No missing research fixtures were added to either Python suite.

Both runs later spent several minutes formatting the same large MPS geometry assertion. Interrupting the owned runners located them in Python `difflib.py` and saved their prefix JUnit results. A local collection-only plugin selected the same 683 unfinished nodes, leaving 5,825 completed nodes untouched. Each continuation used `--assert=plain` to avoid assertion expansion. All 6,508 collected test nodes are accounted for, plus a collection skip. The geometry case passed in both fresh segments. This is a segmented suite comparison, not a clean monolithic suite run; the earlier stall and possible order dependence remain unresolved.

The first cleanup segment also exposed eight fixture setup errors introduced by removing an apparently unused import. The final code restores that pytest fixture as an explicit same-name re-export. A rerun of the entire affected file passed all 11 tests. Final counts substitute that complete-file rerun, while the machine-readable receipt retains the initial outcomes.

The comparison commands, run from each respective source root, are:

```sh
export PYTHONDONTWRITEBYTECODE=1 CLASHER_ROOT="$PWD"
export PYTHONPATH="$PWD/src:$PWD:$PWD/engine-rs"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
nice -n 10 "$PYTHON" -B -m pytest tests -v \
  --continue-on-collection-errors --tb=short --junitxml="$EVIDENCE/python.xml"

export PYTHONPATH="$PWD/engine-rs:$PWD/src:$PWD"
nice -n 10 "$PYTHON" -B -m pytest engine-rs -v \
  --continue-on-collection-errors --tb=short --junitxml="$EVIDENCE/native.xml"
```

`PYTHON` names the installed interpreter and `EVIDENCE` names an output directory outside the compared source. Compare JUnit outcomes by class and test name, including subtests and collection errors, rather than comparing only totals.

The broader native comparison also has identical named outcomes after supplying the previously uncollected main-baseline cases. Both sides total 115 passed, 22 failed, nine collection errors, and 142 passing subtests in pytest's summaries. JUnit groups failing subtests into their parent cases, so its serialized case counts differ from pytest's summary counts. The 13 tests in `engine-rs/test_parity.py` all passed. Existing failures include missing frozen inputs and actual trajectory digest mismatches; this cleanup does not repair them.

The recovered native baseline omitted five modules that fail collection, five Stage 5B tests, and one Stage 5 regression. Only those missing cases were run against the archived base and its original extension. Their names do not overlap the saved baseline results. The final native receipt compares the union against the complete cleanup run.

The relocated CLI resolved worktree-local data paths, and its headless smoke completed one 128-step episode successfully.

## Simulator identity

The tracked base does not include `engine-speed/check_identity.sh` or the frozen baselines. The equivalent checks use byte-identical copies of the tracked P16, C56, broad-identity, and OQ drivers in a private input tree. `CLASHER_ROOT` and `PYTHONPATH` select the cleanup worktree's gamedata and engine. Deck files, recordings, and the policy checkpoint stay in that private tree and are not committed.

The completed pre-change P16 check covered 12 episodes and 15,949 digest boundaries with zero mismatches. C56 covered seven episodes and 2,900 boundaries with zero mismatches. The immutable admitted recorded/random receipts serve as the other pre-change baselines. Post-change P16 and C56 checks also passed with zero mismatches. All 24 random-placement episodes passed with zero mismatches, covering all 16 cards, 7,198 boundaries, and 231 pocket placements. The eight-game recorded replay was interrupted by a second server restart before its first receipt. It was later completed on f35 after the rebase described below.

For a locally supplied input tree with the original `reports/` topology, the wrapper equivalent is:

```sh
export CLASHER_ROOT="$PWD" PYTHONPATH="$PWD/src:$PWD"
ES="$INPUTS/reports/strategy_council_20260928/engine-speed"
C56="$INPUTS/reports/strategy_council_20260928/c56/engine"
nice -n 10 "$PYTHON" -B "$C56/tools/p16_identity.py" check \
  "$C56/p16_identity_baseline_admitted.json"
nice -n 10 "$PYTHON" -B "$ES/c56_identity.py" check \
  "$ES/c56_identity_baseline_canonical.json"
nice -n 10 "$PYTHON" -B "$ES/broad_identity.py" recorded check \
  "$ES/recorded_identity_baseline_admitted.json" --output "$EVIDENCE/recorded.json"
nice -n 10 "$PYTHON" -B "$ES/broad_identity.py" random check \
  "$ES/random_identity_baseline_admitted.json" --output "$EVIDENCE/random.json"
```

Check every command's exit status and the final receipt's episode count and mismatch list. Recorded mode compares outcome, crowns, ticks, and planner-call counts. P16/C56 and random mode check their richer digest/trace contracts. These are different coverage claims.

## Conservative audit limits

Ruff's selected rules `F401,F841,E9,F63,F7,F82` went from 87 findings to 20 across `src`, `tests`, `scripts`, and `engine-rs`. Imports with possible side effects, benchmark clone lifetimes, and calls whose unused return value does not prove the call dead were retained. The existing `robust` warning in `scripts/evaluate_l1_events_v2.py` was not repaired in a behavior-preserving cleanup.

Vulture and reference searches covered `src`, `tests`, `scripts`, `reports`, and `configs`. Referenced API/context-manager parameters remain. Historical report code, including two existing syntax errors in live-loop L2 analysis copies, remains attached to its original evidence. Fixing those reports or broad simulator/native regressions is separate work.

## Rebase onto main `786d6bdb8` (2026-10-05, f35)

The branch was rebased onto `786d6bdb8`, which adds Stage 6 Rust sources and report files, and its verification was rerun on f35. That machine runs Linux x86_64 with Python 3.12.13 and rustc 1.99.0. The rebase applied cleanly. The new main commit changes nothing under `src/` or `tests/`, so the Python suite comparison above still applies. A search of the rebased tree found no remaining use of any removed import, including the `stage2_matches` names, through either `from` imports or attribute access.

- **Native extension:** the release build of the rebased branch is byte-identical to main's. Both `clasher_core.abi3.so` files have SHA-256 `e5ad6d17…f2bf1a`. The Rust edits are therefore behaviour-neutral by construction.
- **Simulator identity:** the four modes use main's drivers and frozen baselines, with `CLASHER_ROOT` and `PYTHONPATH` pointing at the rebased tree. All had zero mismatches:
  - P16: 12 episodes, 15,949 boundaries.
  - C56: 7 episodes, 2,900 boundaries.
  - Random placement: 24 episodes.
  - Recorded: all 8 games, matching outcome, crowns, ticks and planner calls. This is the replay that was outstanding above.
- **Main on the same machine:** the same four modes also passed with zero mismatches, and `engine-rs/test_parity.py` passed 13/13.

