# S2 r4b: move the r4 candidate from safe_input r2 to safe_input r3 (ruling E5)

**Candidate:** `s1s2-r4b/` is a copy of `s1s2-r4/` (`cp -a`; r4's `SHA256SUMS` was verified before the copy, and `s1s2-r4/` is untouched). Written offline on 127x05 on 2026-10-12 from 22:56Z. No SSH, no commit, no push, no host access. `S2:L` means a line of `s2_end_evidence.py` in this directory.

**Authority:** safe-input-r3 (`README.md`, `ADOPTION.md`, `README-ERRATUM-receive-sha.txt`, `tests/test_e5.py`), `end-prep/E5-OIDS-ls-tree.txt`, and ruling E5 in `origin/main:reports/strategy_council_20260928/COORDINATOR.md` ("2026-10-12 21:28Z", read at origin/main 6313e14b).

**S1 is unchanged.** `s1_copy_end_sources.py` is still `b987ab9756dd05439f79bd924a0ce31df3c31b24b125a25d8d9cbba31d0fdc65`, and `tests/test_s1.py` is unchanged.

## What changed

| Change | Where |
|---|---|
| `safe_input.py` is now **byte-identical to `safe-input-r3/safe_input.py`**: SHA-256 `806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00`, single link, mode 0644. | `safe_input.py` |
| Pre-import pin `SAFE_INPUT_SHA256` = `806e5ebb…`, constants fingerprint `SAFE_INPUT_FINGERPRINT` = `33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592`, module name `_k4s_s2_safe_input_r3`. The loader is otherwise unchanged: it does a no-follow, single-link read and checks the SHA with `hashlib` on the bytes it executes. | `S2:104–106` |
| Loader refusal messages now name r3. | `S2:129`, `S2:135` |
| Docstring: the layer is r3. S2 grants no E-exemption, so the nine E5 names still refuse in S2. | `S2:41–47`, `S2:100` |

**E5 in S2: no grant, by design.** S2 has no runtime-tree role and no `git_plan`. It reads only the frozen closure (32 files), the pinned committed records and its CLI paths, and none of these is an E5 member. So S2 declares no `E5` exemption, and the nine E5 paths still refuse there by family. One control was added (below). The receive program SHA is not referenced by S2: S2 does not use `remote_receive`. For reference, the r3 bytes give `receive_program_sha256()` = `39a92e9d55f9ffefba57bae453677bad7c834f7761283268b84e40bb2d1210b4`, which I checked under `/usr/bin/python3` 3.8.10. That matches the erratum; the r3 README value `979b37a1…` is the documented error.

## Test changes (all intended)

| File | Change |
|---|---|
| `tests/test_s2_r4_git.py:316` | `copied_package` swaps the r3 SHA pin (it used to swap the r2 pin). |
| `tests/test_s2_r4_git.py:328` | The loader refusal message is now `is not the pinned safe_input r3`. |
| `tests/test_s2_gate_profile.py:176` | New canary in `PROFILE_CANARIES`: valid profile bytes at `…/tests/fixtures/native_friendly_completed_15_535_86.json` (an E5 path). Full `validate` entrypoint, audited: it refuses as a forbidden location, never opens the canary inode, and runs no git. +1 test. |

## Verification (127x05, 2026-10-12; every number is from this session, on the final bytes in `SHA256SUMS`)

| Interpreter | normal | `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **270 passed** | **270 passed** (1 warning) |
| `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` 3.12.12 (pytest 9.1.1 from `/dev/shm --target`) | **270 passed** | **270 passed** (1 warning) |

270 = 34 S1 + 53 `test_s2.py` + 137 `test_s2_gate_profile.py` + 46 `test_s2_r4_git.py`. The only warning under `-O` is pytest's `PytestConfigWarning` (assertions not executed under -O). Every run used `nice -n 19`, `-B`, `-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`, and its own `--basetemp` inside a fresh `mktemp -d /tmp/k4s-r4b-bt-*`, which was removed afterwards. S2's test root must lie below `/tmp/`.

**Mutation** (`tests/mutate_s2_r4.py`, unchanged; k4s-freeze 3.12.12, `-O`, `-x`, 16 jobs; scratch `/dev/shm/k4s-r4b-mut-s2`; finished 2026-10-12T23:11:47Z; `MUTATION-RESULTS-r4b.json`; the S2, layer and test SHAs recorded in the file equal the final bytes):
- **60 of 63 killed**; 0 invalid; driver rc 0.
- 3 NULL controls (unmodified source), all SURVIVED (236 passed each).
- The 3 survivors are r4's declared equivalents, and each JOINT counterpart was KILLED:
  - `R-bootstrap-si-sha-off` and `R-bootstrap-compare-off` → `R-bootstrap-both-off-JOINT` killed;
  - `W-check-absent-off` → `W-both-off-JOINT` killed.

The driver needed no change: every snippet still occurs exactly once.

## Not changed / still open (as in r4)

- The full-clone ruling (21:28Z) is not implemented in safe_input r3: `_git_preflight` still accepts a promisor config.
- The frozen-reader interim wrapper is as in r4 (`frozen_git_env`).
- Everything else in `RESPONSE-r3.md` (the r4 response) stands; only the layer version and pins changed.
