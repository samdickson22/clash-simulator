# S4 r4b (b3-r4b): safe_input r2 → r3 and ruling E5 through the layer

**Candidate:** `b3-r4b/` is a copy of `b3-r4/` (`cp -a`; r4's `SHA256SUMS` was verified before the copy, and `b3-r4/` is untouched). Written offline on 127x05 on 2026-10-12 from 22:56Z. No SSH, no commit, no push, no host access. `S4:L` means a line of `assemble_fleet_reference.py` in this directory.

**Authority:** safe-input-r3 (`README.md` §0/§8, `ADOPTION.md` rule 0.8 and the S4 row, `README-ERRATUM-receive-sha.txt`, `tests/test_e5.py`), `end-prep/E5-OIDS-ls-tree.txt`, and ruling E5 in `origin/main:…/COORDINATOR.md` ("2026-10-12 21:28Z", read at origin/main 6313e14b).

## What changed

| Change | Where |
|---|---|
| `safe_input.py` is now **byte-identical to `safe-input-r3/safe_input.py`**: SHA-256 `806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00`, single link. | `safe_input.py` |
| Pre-import pin `SAFE_INPUT_SHA256` = `806e5ebb…` and `SAFE_INPUT_FINGERPRINT` = `33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592`; module `_k4s_s4_safe_input_r3`. Refusal messages now name r3. A production run still re-checks the fingerprint at planning (`S4:666`, unchanged), so an in-process edit of `E5_RUNTIME_MEMBERS` refuses too. | `S4:81–83`, `S4:108`, `S4:114` |
| **Removed the component-level E5 hook.** Gone: `E5_RUNTIME_EXEMPT`, `PRODUCTION_PINS["e5_runtime_exempt"]` (so the key is no longer a pin key, and synthetic pins that carry it refuse as malformed), the E5 validation in `check_exemptions`, `walk_runtime_e5()` and `git_blob_oid()`. S4 keeps no E5 list. | `check_exemptions` `S4:391`; the deleted functions were in r4 `S4:134–137, 194, 404–415, 429–484` |
| **Runtime tree role carries E5**: `exemptions=("E4", "E5")`. `si.walk_tree` lists the nine exact E5 paths under `e5`, name-gated with `e5_rel` (only the leaf family is lifted). | `runtime_policy` `S4:405–412`; `RuntimeInventory.__init__` `S4:426` |
| **E5 entries are hashed only by `si.hash_e5`**: descriptor gate, `st_nlink == 1`, and the bytes must hash to the pinned git blob OID. The result's `git_oid` is kept and the bytes are never returned or parsed. A mismatch refuses with `Runtime E5 entry is not its pinned git blob`. | `RuntimeInventory.sha` `S4:432–435` |
| S1 runtime-pin names that are exact E5 paths skip the plain `si.gate_names` (which has no E5 flag and would refuse by family). They are gated with E5 by the walk and by `si.hash_e5`. A pinned E5 name that is missing from the runtime still refuses as `Incomplete frozen runtime`. A walked E5 entry that is not a runtime member still refuses. | `S4:468`, `S4:475` |
| **Repository git-plan role carries E5**: `exemptions=("E1", "E4", "E5")`. The nine paths are in its `exact` names and in the plan members, so `si.git_plan` phase 1 pins every E5 entry present at HEAD (mode 100644, blob OID = layer pin) from **metadata only**. A changed or mode-755 committed E5 entry refuses the whole plan with zero object reads. Committed E5 blobs are never requested. | `Committed.__init__` `S4:548–558` |
| **Binding**: every runtime E5 member must be the E5 entry committed at HEAD of `--repository`, with the same OID (`Committed.check_e5`). `plan_bundle` also requires every walked E5 entry to have been hashed. | `S4:585–590`, `S4:709–710` |
| The receipt still records `e5_runtime_exempt` (sorted runtime E5 paths). The manifest's `runtime_files` carries their SHA-256. E5 files are never copied into the bundle. | `S4:904`, `S4:977` |

**Receive program SHA:** S4 does not reference it (S4 does not use `remote_receive`). For the record, the r3 bytes give `receive_program_sha256()` = `39a92e9d55f9ffefba57bae453677bad7c834f7761283268b84e40bb2d1210b4` (checked under `/usr/bin/python3` 3.8.10), which matches the erratum.

**Real E5 bytes were never read.** The tests substitute OIDs for synthetic bytes through `monkeypatch.setattr(A.si, "E5_RUNTIME_MEMBERS", …)`, which is safe_input's documented test mode: only OIDs may change, and `e5_blob_oid()` refuses any other change. The ruled list itself is typed into the tests and compared with the layer's tuple.

## Tests (`test_s4_r4_git.py`, E5 section `:281–486`; it replaces r4's 13 E5-hook tests with 27)

| Test | What it shows |
|---|---|
| `test_e5_list_is_the_ruled_list_from_the_layer` (`:337`) | `si.E5_RUNTIME_MEMBERS` == the nine (path, OID) pairs of ruling E5 / `E5-OIDS-ls-tree.txt`, typed in the test. S4 has no `E5_RUNTIME_EXEMPT`, no pins key and no `walk_runtime_e5`. The runtime role's exemptions are `{E4, E5}`. |
| `test_e5_key_in_synthetic_pins_refused` (`:344`) | The removed key cannot come back through the test-only pins. |
| `test_e5_each_ruled_member_accepted_hash_only[m0..m8]` (`:350`) | **Each of the nine** goes through the full `A.main` path (synthetic bytes in the runtime and committed at HEAD, OIDs substituted): accepted; the `runtime_files` SHA equals the bytes; not copied into the bundle; recorded in the receipt; opened exactly once (inode audit). The ids avoid family tokens in `tmp_path`. |
| `test_e5_all_nine_together` (`:364`) | All nine in one run. |
| `test_e5_tenth_or_moved_family_member_refused_unread[tenth, moved, case, neighbour]` (`:379`) | Each of these holds the same bytes as a ruled member and is listed in the S1 pin list: `scripts/other_public_games.py` (a **10th family-matching member**), `tools/check_games.py` (a moved copy), `…/Check_games.py` (a case variant) and `…_15_535_87.json` (a neighbouring fixture name). Each refuses `[name]` in the walk, and its inode is never opened. |
| `test_e5_changed_committed_oid_refused_before_any_object_read[bytes, mode-755]` (`:388`) | **A changed OID refuses before any blob read**: phase-1 `[exemption] … is not the pinned 100644 blob`, the `object_reads` counter is unchanged, no object id is requested, and `cat-file --batch` never runs. |
| `test_e5_committed_members_are_never_read` (`:403`) | Happy path with all nine: no committed E5 blob OID reaches `cat-file --batch`. |
| `test_e5_changed_runtime_bytes_refused` (`:412`) | Runtime bytes that do not hash to the pinned OID refuse (`si.hash_e5`). |
| `test_e5_runtime_member_not_committed_at_head_refused` (`:419`) | The runtime↔HEAD binding. |
| `test_e5_hard_linked_or_symlinked_member_refused_unread` (`:424`) | `[nlink]` / `[symlink]`; the outcome canary is never opened. |
| `test_e5_member_must_be_a_runtime_member` (`:437`) | The fixture JSON outside the S1 pin list refuses. |
| `test_e5_parse_or_ordinary_read_attempts_refused_unopened[py, fixture]` (`:446`) | **Parse attempts refuse.** S4's only parse path, `RuntimeInventory.read_pinned` (`si.read_bytes`), refuses `[name]`. So do `si.read_bytes`, `si.read_json`, `si.sha256_input` and `si.open_input` on the runtime role. The file is mode 000, so any open would be EACCES, and the audit shows its inode is never opened. `plan.read` of the committed E5 entry refuses `[policy]` (not a planned file). |
| `test_e5_widened_list_refused_by_the_layer` (`:472`) | A 10th entry added to the constant: the layer refuses `[policy]`. |
| `test_production_run_refuses_an_in_process_edited_e5_list` (`:478`) | Production: an OID-only in-process edit refuses through the fingerprint re-check. |

Other test edits: `test_s4_r4_git.py:490` (`PINNED` is the r3 SHA), `:520` (the message is r3), the module docstring, and the import of `Audit`; `test_assemble_fleet_reference.py:264` (the World pins no longer carry `e5_runtime_exempt`).

## Verification (127x05, 2026-10-12; every number is from this session, on the final bytes in `SHA256SUMS`)

The frozen root is the r4 method (README): `git archive origin/main` (6313e14b) of the same 43 paths into `mktemp -d /dev/shm/k4s-r4b-frozen-XXXXXX`. Before export, every path was put through `si.name_gate` with 0 refusals. The export was removed afterwards.

| Interpreter | `K4S_FROZEN_ROOT` set, normal | set, `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **463 passed** | **463 passed** (1 warning) |
| `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` 3.12.12 (pytest 9.1.1 from `/dev/shm --target`) | **463 passed** | **463 passed** (1 warning) |

463 = 338 `test_assemble_fleet_reference.py` + 125 `test_s4_r4_git.py` (r4: 111 − 13 hook tests + 27 E5 tests). The warning is pytest's `-O` assertion-rewrite notice. Every run used `nice -n 19`, `-B`, `-p no:cacheprovider`, and was started from `/tmp` with `--basetemp` inside a fresh `mktemp -d /tmp/k4s-r4b-bt-*` (removed). The no-frozen-root variant was not re-run this round.

**Mutation** (`mutate_s4_r4.py`; k4s-freeze 3.12.12, `-O`, `-x`, frozen root set, 12 jobs; scratch `TemporaryDirectory` `/dev/shm/b3r4b-mut-*`; finished 2026-10-12T23:10:59Z; `MUTATION-RESULTS-r4b.json`; the assembler, layer and test SHAs recorded in the file equal the final bytes):
- **37 of 41 killed**; 0 invalid; driver rc 0.
- 3 NULL controls, all SURVIVED.
- Survivors, all declared equivalents:
  - `N Sources leaf gate off`, `N --out name gate off` and `N guard job remote gate off` are as in r4. Their JOINTs were killed, except the guard-job one, which has no JOINT, as in r4.
  - **`X E5 all-hashed check off`** (new) is masked: every walked E5 entry must be a member (the stray check), and `members()` hashes every member. → `X E5 non-members accepted and all-hashed check off JOINT` was **KILLED**.
- **Driver fallout (fix only).** Six of r4's seven E5-hook mutants target code that no longer exists and were removed; `X E5 non-members accepted` still applies and was kept. Nine mutants of the r4b E5 adoption were added (38 − 6 + 9 = 41). The kept mutant and the eight non-equivalent new ones were all **KILLED**:
  - runtime role without E5;
  - E5 hashed by `sha256_input`;
  - pin entries gated without the E5 flag;
  - non-members accepted (kept);
  - the JOINT;
  - runtime↔HEAD binding skipped;
  - committed OID not compared;
  - repository role without E5;
  - E5 paths not planned at HEAD.

  `R runtime role without the E4 exemption` was re-pointed to the new snippet; it was KILLED, by a fixture error, which the r4 driver counts as killed. The r4 equivalent `X E5 walk always used` was dropped together with its code.

## Still open (unchanged by r4b)

- **Full clone (21:28Z):** a production `--repository` must be the runner-owned full clone. safe_input r3 does not refuse a promisor clone, and S4 does not add that check.
- **E4 OID ratification line:** see `OPEN-QUESTIONS.md`.
- `DESIGN.md` and `OPEN-QUESTIONS.md` each carry an r4b note at the top. Their r4 E5-hook text is superseded.
