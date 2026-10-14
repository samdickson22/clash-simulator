# s5s6s7-r5: response to SOL-REVIEW-END-INTEGRATION-r1 (finding 1, U4 ruling)

Scope: Part B (`s5s6s7-r4`) items of `reviews/SOL-REVIEW-END-INTEGRATION-r1.md` (63fae416) and COORDINATOR 10:33Z
(05c733d1): finding 1 (U8, BLOCKING) and the U4 interpreter ruling. Finding 2 (S11/S9 git write aliases) is Part A
(`s3s9s10-r5`). Diff-only round: `DIFF-r5.patch` = `diff -ruN s5s6s7-r4 s5s6s7-r5` (SHA256SUMS / PROGRESS excluded).
Line numbers are r5. Counts and mutation evidence: README §r5, `TEST-RUN.txt`, `MUTATION-RESULTS-r5-py*-O.json`.

| Item | Fix (file:line) | Named tests | Status |
|---|---|---|---|
| **U4** (ruling: the interpreter P' `runtime.sh` actually executes) | `k4s_end_launch_gate.py:109` `HOST_PYTHON = "/mpac/sdicks02/repos/clasher/.venv/bin/python"` (was the bare uv binary), `:110` `RUNTIME_SH_REL` (where it is taken from: `runtime.sh` at P' 98566c03 ends `exec /mpac/sdicks02/repos/clasher/.venv/bin/python -B "$@"`, read with `git show` from `repo-full`). The one constant feeds `validate_argv` (`:423`, plus the unchanged `-B`-only and FORBIDDEN_TOKENS checks) and `compose_argv` (`:1016`, `[HOST_PYTHON, "-B"]`, both kinds) and the build-argv record (`:1103`). Nothing else pins the END/preflight interpreter: S5 records `sys.version` only, the wrappers' `$python=/usr/bin/python3` is the loader for the host tool, the host program's postexec matches `basename` `python*`, and the builder's `FROZEN_PYTHON` is the 05-side frozen-reader interpreter (= S9 `DEFAULT_PYTHON` = the production manifest's `python`, now enforced, below). So no TOOL_PINS file changed | `test_r5.py::test_u4_host_python_is_the_runtime_sh_venv_interpreter`, `::test_u4_compose_argv_emits_the_venv_python_with_exactly_b[end/preflight]`, `::test_u4_validate_argv_accepts_only_the_venv_python` (real constant accepted for both kinds; bare uv, `python3`, `python3.12`, e4v3 venv, a `..` alias, `/usr/bin/python3` refused; `-O`/`-I`/`-BO`/`-b`/`-BB` refused), `::test_u4_runtime_sh_at_p_prime_executes_exactly_host_python` (integration, gated git reader, read only), `::test_u4_s10_probe_interpreter_is_the_same_string` (S10 r5 `HOST_PYTHON` literal == gate's); existing `test_r4.py` build-argv/launch tests and `test_s7_gate.py` Site fixture (stand-in renamed to the venv layout) | **Tool aligned** (S7 + S10 identical string). Qualification (the venv's site-packages on both hosts) remains the S10 probe's authorized host step |
| **Finding 1** (U8 builder pinned to r3 S9 / old manifest) | `k4s_a6_builder.py:239-240` `FROZEN_RUNTIME` / `FROZEN_RUNTIME_MANIFEST_SHA256` and `:249-250` `S9_PATH` / `S9_SHA256` now name the **adopted S9 (s3s9s10-r5)** and the **production runtime manifest rebuilt with it**, written by `tests/adopt_pins.py` from the markers `s3s9s10-r5/S9-FINAL` and `end-staging/RUNTIME-r5-READY` (every value computed; refuses unless each S9-FINAL row equals the bytes of the chain it lists, RUNTIME-r5-READY names exactly the production manifest and the same S9, the manifest hashes to it and its `script_sha256` is that S9). Record: `ADOPTED-S9-RUNTIME.json`. New structural binding so the two pins can never drift apart again: `frozen_inputs` (`:407`) parses the pinned manifest and requires `script_sha256 == S9_SHA256` (`:418`) and `commit == P'`, `repository == REPO_FULL`, `python == FROZEN_PYTHON` (`:420`); `self_check` records the manifest's builder and member-set SHA (`:485`, `:518`) | `test_a6_builder.py::test_r5_frozen_inputs_bind_runtime_to_adopted_s9` (8: ok; manifest built by another S9; `script_sha256` absent; other commit / repository / python; manifest pin; S9 bytes; each re-pinned so the pin alone never decides), `::test_frozen_inputs_are_pinned[none/runtime-manifest/frozen-file/s9]` (the real production inputs: the healthy control Sol saw fail now passes), `::test_real_a6_builder_proof_frozen_and_s9` (real P', frozen code, adopted S9, production manifest), `::test_self_check_verdicts_with_stub_drivers`; **contract tests** `test_r5.py::test_u8_builder_constants_equal_the_adopted_record` (portable: builder constants == record == the adopted package's S9 path / production runtime path; record binds manifest → S9, P', frozen python), `::test_u8_adopted_record_matches_the_sibling_s9_package` (when `s3s9s10-r5` is beside: its SHA256SUMS entry, the S9 bytes/size and the S9-FINAL marker SHA), `::test_u8_adopted_record_matches_the_production_runtime_manifest` (the real manifest bytes, its `script_sha256`/commit/members, the RUNTIME-r5-READY marker SHA), `::test_u8_recorded_proof_is_of_these_bytes` (builder-proof/ made by this builder against these pins) | **CLOSED offline** |
| Finding 1 proof regenerated | `audit-rerun/rerun.sh` reads every pin from `ADOPTED-S9-RUNTIME.json`, re-hashes the manifest and S9, runs `adopt_pins.py --check`, then build → self-check into `builder-proof/` (scratch copy of `repo-full/.git` ONLY, P' + END-JOB scratch commit, frozen `end_evidence`+`end_job`, adopted S9 `equivalence` on the same production runtime), then the audit's two drivers. S9 for the drivers is copied from the S9-FINAL chain only (each row checked) and imported directly (the one non-path substitution: `import s9_end_runtime as S9` instead of via `s10_stage_host`) | `builder-proof/{BUILD,END-JOB,SELF-CHECK}.json`, `builder-proof/RERUN-1-build-selfcheck.log`, `RERUN-2-audit-only.log`; `audit-rerun/{frozen_job_drive,s9_equiv_drive}.out`, `X` | build → frozen end_job → S9 r5 equivalence **OK** (see README §r5) |

## Pins and chains

- Canonical bootstrap region: byte-identical in all five Python components (`test_f1_bootstrap.py`, unchanged).
- Pin chain (`tests/repin.py`): only the gate's own bytes changed (U4), so only its SHA moved; the gate pins nothing
  that changed. safe_input, host tool, S5, both wrappers, verifier and host program are byte-identical to r4.
- TOOLS-FINAL (written before any other r5 edit; never changed afterwards): the six S10 TOOL_PINS files are
  byte-identical to r4 (`TOOLS-FINAL`).
- New builder pin chain: S9-FINAL + RUNTIME-r5-READY → `tests/adopt_pins.py` → builder constants +
  `ADOPTED-S9-RUNTIME.json` → `test_r5.py` contract tests (+ `adopt_pins.py --check` in `rerun.sh`).

## Every r4 fix kept

All r4 tests pass unchanged except the fixtures adapted to the two new contracts (`test_s7_gate.py` stand-in python
path; `test_a6_builder.py` `frozen_inputs` now returns the manifest, and its `[s9]` case now refuses first at the
manifest's builder binding). r4 mutant J18's edit target moved with the manifest read (`sha_bytes(raw) == …`).

## Open / disclosed

1. **Deviation from the literal review pins (disclosed by the coordinator):** Sol's required fix named r4 S9
   80c15b5f / manifest 1fa0ebf5. Finding 2 changed S9, so the adopted S9 is r5 and the runner rebuilt the production
   runtime with it; the builder pins those (S9-FINAL / RUNTIME-r5-READY), not the r4 values.
2. `RUNTIME-r5-READY` is mode 0644 (S9-FINAL is 0444). The record stores its SHA; the contract test fails if it changes.
3. U4 qualification (the venv's resolved site-packages / torch import on 03 and 04) is the S10 probe's authorized host
   step, not provable offline.
4. U11 (S8) remains deferred by the coordinator; not closed here.
