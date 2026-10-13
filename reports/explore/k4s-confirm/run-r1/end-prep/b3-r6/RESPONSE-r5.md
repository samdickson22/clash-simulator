# S4 (b3) r5: response to SOL-REVIEW-END-FULL-r1

CANDIDATE, needs Sol review. Offline only. Predecessor: `b3-r4b`, which is immutable and was copied with `cp -a`
after its SHA256SUMS verified. The vendored layer is unchanged: `safe_input.py` is safe_input r3 `806e5ebb…`,
133606 bytes.

## END-FULL-F1 (BLOCKING): bootstrap reads preceded ancestor/role confinement

**Defect (r4b S4:86–108).** `load_safe_input` opened `abspath(__file__)/../safe_input.py` by full pathname with a
leaf-only `O_NOFOLLOW`. Its nlink and SHA checks ran only after content was read, so a canary behind an ancestor alias
was fully consumed before the refusal. The bootstrap-r1 kit reproduces this on the immutable r4b file:
`bootstrap-r1/tests/test_kit_selftest.py::test_kit_reproduces_end_full_f1_on_the_r4b_candidates[s4]` shows all 133606
canary bytes read.

**Fix.** The r4b loader is replaced by the canonical bootstrap r1 (`bootstrap-r1/k4s_bootstrap_r1.py`, SHA-256
`5611c604…`), pasted verbatim:

| Where (`assemble_fleet_reference.py`) | What |
|---|---|
| :87–91 | The pins stay outside the region: `SAFE_INPUT_SHA256`, the new `SAFE_INPUT_SIZE = 133606`, `SAFE_INPUT_FINGERPRINT` and `SAFE_INPUT_MODULE`. |
| :93–248 | The canonical region, byte-identical. |
| :159, :166 | Normalized absolute path (:159) and the OUTCOME-family name gate on every component (:166), both with no system call. |
| :174 | Walk from `/`: every ancestor `O_DIRECTORY\|O_NOFOLLOW` relative to its parent fd, and `fstat` must report a directory. |
| :186 | The leaf is `fstatat`'d without following (regular, nlink 1, exactly 133606 bytes) before it is opened. |
| :192 | `O_NOFOLLOW\|O_NONBLOCK` open relative to the parent, then `fstat` (same dev/ino, regular, nlink 1, size) before any read. |
| :208, :215 | Exact-size read with an EOF probe (:208), then the SHA-256 pin (:215). |
| :227 | The verified bytes are compiled under a `<k4s-bootstrap …>` filename, with linecache seeded, so nothing re-opens the path. |
| :251–258 | `load_safe_input(path=None)`. The default is `k4s_bootstrap_default_path(__file__, …)`, with no `abspath` or `realpath` before `si` exists. The refusal convention is still `RuntimeError` at import, and the fingerprint is still checked (:256). |
| :261 | `si = load_safe_input()`. |

The production in-process fingerprint re-check is unchanged. The module docstring records r5.

The rest of the file is byte-identical to r4b: `diff` of r4b :119–end against r5 :262–end is empty (see PROGRESS).
That includes the assembler reading its own source through `si` roles (`own = absolute(os.path.abspath(__file__),
…)`). That read happens after the layer exists and goes through si's canonical-root walk, so it is not part of this
finding.

**Regression tests (`test_s4_r5_bootstrap.py`, new; explicit `ok()` raises, no bare assert):**

- `test_embedded_bootstrap_is_the_canonical_text`: region SHA-256 `5611c604…`, byte-equal to bootstrap-r1.
- `test_layer_pins_match_the_vendored_file_and_the_old_loader_is_gone`.
- `test_end_full_f1_alias_substitutions_before_bootstrap[script|import-<scenario>]`: the kit runs the assembler as
  `--help` and as an import against every scenario, with each alias substituted before the bootstrap. Expected
  results:
  - zero canary opens and bytes, unchanged atime, nothing executed;
  - a `RuntimeError` starting with `k4s bootstrap refused:`;
  - the control reads the layer inode exactly once, all 133606 bytes, hashing to the pin;
  - in `swap-ok`, the decoy never runs.
- `test_post_hash_swap_to_a_same_size_edited_layer_runs_the_verified_bytes`,
  `test_fingerprint_still_checked_after_the_bootstrap` and `test_explicit_path_goes_through_the_same_gates`.

**Changed expectations.** In `test_s4_r4_git.py::test_loader_pins_the_layer[other-bytes]`, the longer layer now
refuses at the size pin, before any read: `k4s bootstrap refused: leaf is not a single-link regular file of the pinned
size`. The `fingerprint`, `hard-link` and `control` cases are unchanged.

**Mutation driver.** In `mutate_s4_r4.py`, the three loader mutants now target the embedded r5 lines (SHA compare;
fingerprint; a JOINT removing both nlink checks). The new guards are mutated by `bootstrap-r1/mutate_adopter.py`; the
results are in `MUTATION-RESULTS-r5-*.json` here.

## Earlier findings: preserved

All S4 rows of the Disposition table are unaffected; only the loader block changed:

- S4-R2-F1 (hard links), S4-R2-F2 (strict END), S4-R2-F3 (synthetic pin reader);
- S4-R3-F1 (Git indirection), S4-R3-F2 (outcome-name family), S4-R3-F3 (E4 metadata ordering);
- the E5 grant.

Their controls are in the unchanged `test_assemble_fleet_reference.py` and `test_s4_r4_git.py` (only the one
expectation above changed). They pass in every mode below, with the frozen-consumer tests enabled through a 43-path
code/metadata export (`git archive 6313e14b`; every path name-gated before export, 0 refused).

**The two real-Q6 tests are deselected** in every run (`-k "not test_production_q6"`, verified by `--collect-only`).
One exception, disclosed in `bootstrap-r1/PROGRESS.md`: in the first 3.12 normal run, my `--deselect` arguments used
absolute paths that did not match pytest node ids, so the two tests ran once. They read only the 353 KB T1 Q6 index
(`states-rows.json`) and `lstat` the two containers, as in r3/r4b. They read no outcome, `games/` or `complete.json`.
All final runs use `-k`.

## Verification (final bytes in `SHA256SUMS`; 127x05; `nice -n 19 taskset -c 0-7`, `-B`, `-p no:cacheprovider`)

| Interpreter | normal | `-O` |
|---|---:|---:|
| k4s-freeze 3.12.12 | 522 passed, 2 deselected (real-Q6, never run) | 522 passed, 2 deselected (real-Q6, never run) |
| /usr/bin/python3 3.8.10 | 522 passed, 2 deselected (real-Q6, never run) | 522 passed, 2 deselected (real-Q6, never run) |

Each count is 461 delivered (r4b) tests plus 61 new.

**Mutation** (3.12 `-O`):

- `MUTATION-RESULTS-r5-behaviour.json`: 27/27 predicted entrypoint-level kills; 4 equivalents and the NULL survived;
  28 unit mutants (2 killed here).
- `MUTATION-RESULTS-r5-with-text.json`: 59/59 killed; NULL survived.
- `MUTATION-RESULTS-r4-driver-on-r5.json`: the r4 driver rerun on the r5 bytes, with its three loader mutants
  retargeted. Result: 36/41 killed, 0 invalid, 3 NULL survived. The survivors are the 4 r4b equivalents, which are
  unchanged, plus `L sha pin off`. The r4 test files' only other-bytes layer is longer, so the new size pin refuses
  it first. The same-size case is in the r5 test file, where this guard is killed (`R sha compare off` in the
  behaviour campaign). The JSON lists `L sha pin off` as `survived_unexplained` because it was produced before the
  entry was added. After the run, `L sha pin off` was added to the driver's EQUIVALENT table with that reason; no
  other driver byte changed.
- The canonical guards themselves: `../bootstrap-r1/MUTATION-RESULTS-bootstrap-py{312,38}-O.json`, 60 killed / 6
  survived each (4 declared equivalents with killed JOINTs, plus 2 NULL).
