# s5s6s7-r6: re-pin to S9 r6 (SOL-FIXCHECK-END-INTEGRATION-r5)

Scope: Sol's r5 fix-check found U8 (the END-JOB builder pins) FIXED and U10 (S9 symbolic destination ref) NOT FIXED.
U10 is fixed in Part A (`s3s9s10-r6`), which changed S9; the runner rebuilt the production runtime with it
(`end-staging/RUNTIME-r6-READY`). This round only re-pins the A6 builder to that S9 and manifest and regenerates the
proof. Diff: `DIFF-r6.patch` = `diff -ruN s5s6s7-r5 s5s6s7-r6` (SHA256SUMS / PROGRESS excluded).

| Item | Change (file:line) | Named tests | Status |
|---|---|---|---|
| Builder pins → S9 r6 + RUNTIME-r6-READY manifest | `k4s_a6_builder.py:240` `FROZEN_RUNTIME_MANIFEST_SHA256` = `9d6ab1f7386894727035c14a95c518b54e9472c9cb90eb6d023c589fe2269b43`, `:249` `S9_PATH` = `s3s9s10-r6/s9_end_runtime.py`, `:250` `S9_SHA256` = `bdc2deeb96bf60a16b8877ffa2038760673d60bb63edcde8d947195fdfdcf3a7` (`FROZEN_RUNTIME` path unchanged), all written by `tests/adopt_pins.py` from the markers (marker / package names r5 → r6 only). It refuses unless every S9-FINAL row matches the bytes, RUNTIME-r6-READY names exactly the production manifest and the same S9, the manifest hashes to it, and its `script_sha256` is S9 r6. Record: `ADOPTED-S9-RUNTIME.json` | `test_r5.py::test_u8_builder_constants_equal_the_adopted_record`, `::test_u8_adopted_record_matches_the_sibling_s9_package` (s3s9s10-r6 SHA256SUMS, S9 bytes / size, S9-FINAL SHA), `::test_u8_adopted_record_matches_the_production_runtime_manifest` (manifest bytes, `script_sha256` / commit / members, RUNTIME-r6-READY SHA), `::test_u8_recorded_proof_is_of_these_bytes`; `test_a6_builder.py::test_frozen_inputs_are_pinned[*]`, `::test_r5_frozen_inputs_bind_runtime_to_adopted_s9[8]`, `::test_real_a6_builder_proof_frozen_and_s9` | re-pinned |
| Proof regenerated | `audit-rerun/rerun.sh` (label and scratch path r6 only): build, then self-check on a scratch copy of `repo-full/.git` ONLY (P' plus a scratch END-JOB commit, `diff-tree` = exactly END-JOB.json), frozen `end_evidence` + `end_job` at X, then S9 r6 `equivalence` on the production runtime; then the audit's two drivers | `builder-proof/{BUILD,END-JOB,SELF-CHECK}.json`, `builder-proof/RERUN-1-build-selfcheck.log`; `audit-rerun/*.out`, `X` | **OK** |
| TOOLS-FINAL | unchanged: copied as is; the six files are byte-identical (re-checked by command) | `test_pins.py` | unchanged |

Nothing else changed. The gate, host tool, S5, the wrappers, the verifier, the host program and safe_input are
byte-identical to r5. The canonical bootstrap regions are unchanged. Counts: README §r6, `TEST-RUN-r6.txt`.
Mutation: the U8 subset on the new pins (J17–J26; J23's target follows the pin), with NULL controls N09–N11:
`MUTATION-RESULTS-r6-py312-O.json` and `MUTATION-RESULTS-r6-py38-O.json`, 10/10 killed and 3/3 NULLs survived in each.
