# S1/S2 r5: response to SOL-REVIEW-END-FULL-r1

CANDIDATE, needs Sol review. Offline only. Predecessor: `s1s2-r4b`, which is immutable and was copied with
`cp -a` after its SHA256SUMS verified.

**S1 is unchanged.** `s1_copy_end_sources.py` has the same bytes as r4b, which was APPROVED (SHA-256 in `SHA256SUMS`;
equality with r4b is checked in `PROGRESS`). The vendored layer is unchanged: `safe_input.py` is safe_input r3
`806e5ebb…`, 133606 bytes.

## END-FULL-F1 (BLOCKING): bootstrap reads preceded ancestor/role confinement

**Defect (r4b S2:109–135).** `load_safe_input` opened `abspath(__file__)/../safe_input.py` by full pathname with a
leaf-only `O_NOFOLLOW`. It checked nlink and SHA only after reading, so a canary behind an ancestor alias was fully
consumed before the refusal. The bootstrap-r1 kit reproduces this on the immutable r4b file:
`bootstrap-r1/tests/test_kit_selftest.py::test_kit_reproduces_end_full_f1_on_the_r4b_candidates[s2]` shows all 133606
canary bytes read through an ancestor alias.

**Fix.** The r4b loader is replaced by the canonical bootstrap r1 (`bootstrap-r1/k4s_bootstrap_r1.py`, SHA-256
`5611c604…`), pasted verbatim:

| Where (`s2_end_evidence.py`) | What |
|---|---|
| :109–113 | The pins stay **outside** the canonical region: `SAFE_INPUT_SHA256`, the new `SAFE_INPUT_SIZE = 133606`, `SAFE_INPUT_FINGERPRINT` and `SAFE_INPUT_MODULE`. |
| :115–270 | The canonical region, byte-identical to bootstrap-r1. |
| :181, :188 | No system call: normalized absolute path (:181), and every component through the safe_input r3 OUTCOME families (:188, casefolded fullmatch). |
| :196 | Component-wise walk from `/`: every ancestor opened `O_DIRECTORY\|O_NOFOLLOW` relative to its parent fd, and `fstat` must report a directory. |
| :208 | The leaf is `fstatat`'d without following: regular, `st_nlink == 1`, exactly 133606 bytes, before it is opened. |
| :214 | `O_NOFOLLOW\|O_NONBLOCK` open relative to the parent, then `fstat` (same dev/ino, regular, nlink 1, size) before any read. |
| :230, :237 | Exactly 133606 bytes are read, EOF is confirmed (:230), and the SHA-256 is checked (:237). |
| :249 | Exactly those bytes are compiled under a `<k4s-bootstrap …>` filename, with linecache seeded, so the path is never re-opened. |
| :273–279 | `load_safe_input(path=None)`. The default path is `k4s_bootstrap_default_path(__file__, "safe_input.py")`: no `abspath`, no `realpath`, so an alias stays visible to the walk. The refusal convention is still `RuntimeError` at import. The constants fingerprint is checked after the bootstrap (:277), unchanged. |
| :282 | `si = load_safe_input()` still runs before any other S2 code touches a path. |

The module docstring records r5.

**Regression tests (`tests/test_s2_r5_bootstrap.py`, new):**

- `test_embedded_bootstrap_is_the_canonical_text`: the region between the BEGIN and END lines has SHA-256
  `5611c604…` and equals `bootstrap-r1/k4s_bootstrap_r1.py` byte for byte. The pins are outside the region, so the
  comparison needs no substitution.
- `test_layer_pins_match_the_vendored_file_and_the_old_loader_is_gone`: the pins equal the vendored file, and
  `si.__k4s_bootstrap__ == ("k4s-bootstrap-r1", path, pin, 133606)`. The code before `si = …` contains no
  `abspath(`/`realpath(`, and only the bootstrap's three `os.open` and two `os.read` calls.
- `test_end_full_f1_alias_substitutions_before_bootstrap[script|import-<scenario>]`: the bootstrap-r1 conformance kit
  runs S2 itself, as `build --help` and as an import, against every kit scenario. Each alias is substituted **before**
  the bootstrap runs:
  - ancestor symlinks into `games/`, higher up, and to a target with no outcome name;
  - leaf symlinks, hard links (nlink 2), and wrong sizes;
  - same-size mismatching bytes, a FIFO leaf, a directory leaf;
  - the `..`-through-alias, `/./` and `//` forms;
  - eleven outcome-named ancestor directories, including case and casefold variants.

  The kit asserts zero canary opens and zero bytes (recorders), an unchanged kernel atime, and no execution marker.
  The refusal must be a `RuntimeError` starting with `k4s bootstrap refused:`. The control reads the layer inode once,
  exactly 133606 bytes hashing to the pin. In `swap-ok`, a decoy renamed over the path right after hashing never
  runs.
- `test_post_hash_swap_to_a_same_size_edited_layer_runs_the_verified_bytes`: the fingerprint passes although the path
  now names an edited same-size layer.
- `test_fingerprint_still_checked_after_the_bootstrap` and `test_explicit_path_goes_through_the_same_gates`.

**Changed expectations in an existing test.** In `tests/test_s2_r4_git.py::test_loader_refuses_a_layer_with_other_bytes`,
the layer with one extra comment line now refuses at the **size pin**, before any byte is read. The expected message
is now `k4s bootstrap refused: leaf is not a single-link regular file of the pinned size`, where r4b expected `is not
the pinned safe_input r3`. This is stronger, not weaker: same-size different bytes are still refused by the SHA (kit
scenario `same-size-mismatch`). The hard-link and fingerprint tests are unchanged and pass.

**Test harness portability.** `tests/audit_run.py` gained six lines and is now Python 3.8-portable. On Python ≤ 3.10,
`pathlib` keeps `os.stat`/`os.lstat`/`os.open` as accessor class attributes, so the recorder's Python wrappers were
bound as methods and got an extra positional argument. Twelve audit-recorded tests then failed on 3.8 with
`os_open() takes from 2 to 3 positional arguments but 4 were given`. The r4b package fails **the identical 12 tests**
on 3.8; this was checked in a scratch copy, see PROGRESS. The fix rebinds those three accessor attributes as
`staticmethod(wrapper)`, so 3.8 records exactly what 3.12 records. It changes nothing on 3.12, which has no accessor.

**Mutation drivers.** The three r4 loader mutants in `tests/mutate_s2_r4.py` now target the embedded r5 lines (SHA
compare; fingerprint; a JOINT removing both nlink checks), so the r4 driver still runs. The new guards are mutated by
`bootstrap-r1/mutate_adopter.py`; see Verification below.

## Earlier findings: preserved

Every repaired earlier finding in the review's Disposition table is unchanged in r5. Only the loader block
(:101–139 in r4b) and the docstring paragraph changed in `s2_end_evidence.py`; `diff` against r4b is in PROGRESS.

- S2-R2-F1 (filesystem/auxiliary roles), S2-R2-F2 (missing/empty profile) and S2-R3-F1 (Git replacement/env): their
  controls are in the unchanged `tests/test_s2.py`, `tests/test_s2_gate_profile.py` and `tests/test_s2_r4_git.py`,
  and all pass in every mode below.
- The S1 approval is untouched: identical bytes, and its 34 controls pass.

## Verification (final bytes in `SHA256SUMS`; 127x05; `nice -n 19 taskset -c 0-7`, `-B`, `-p no:cacheprovider`)

| Interpreter | normal | `-O` |
|---|---:|---:|
| k4s-freeze 3.12.12 | 331 passed | 331 passed |
| /usr/bin/python3 3.8.10 | 331 passed | 331 passed |

Each count is 270 delivered (r4b) tests plus 61 new.

**Mutation** (3.12 `-O`):

- `MUTATION-RESULTS-r5-behaviour.json`: 27/27 predicted entrypoint-level kills; 4 equivalents and the NULL survived;
  28 unit mutants (2 killed here).
- `MUTATION-RESULTS-r5-with-text.json`: 59/59 killed; NULL survived.
- `MUTATION-RESULTS-r4-driver-on-r5.json`: the r4 driver rerun on the r5 bytes, with its three loader mutants
  retargeted. Result: 59/63 killed, 0 invalid, 3 NULL survived. The survivors are the 3 r4 equivalents, which are
  unchanged, plus `L-sha-pin-off`. The r4 test files' only other-bytes layer is longer, so the new size pin refuses
  it first. The same-size case is in the r5 test file, where this guard is killed (`R sha compare off` in the
  behaviour campaign). The JSON lists `L-sha-pin-off` as `survived_unexplained` because it was produced before the
  entry was added. After the run, `L-sha-pin-off` was added to the driver's EQUIVALENT table with that reason; no
  other driver byte changed.
- The canonical guards themselves: `../bootstrap-r1/MUTATION-RESULTS-bootstrap-py{312,38}-O.json`, 60 killed / 6
  survived each (4 declared equivalents with killed JOINTs, plus 2 NULL).
