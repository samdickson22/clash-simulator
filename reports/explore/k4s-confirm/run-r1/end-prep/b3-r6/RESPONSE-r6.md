# b3-r6 response: INTEGRATION-AUDIT-r1 B1 (and L4)

Sources: `end-staging/INTEGRATION-AUDIT-r1/REPORT.md` rows B1 and L4; `end-staging/S4-REFUSAL-b3r5-runtime-pin-files-shape.md`.
`b3-r6/` is a copy of `b3-r5/` (SHA256SUMS verified before the copy; `b3-r5/` untouched). Line numbers are for the
b3-r6 bytes in `SHA256SUMS`.

## B1: S4 required a list; the pinned runtime-pin-r2 holds a dict

### Evidence for the rule S4 now follows

- **Frozen rule** (read-only, S9 runtime copy `runtime-98566c032d0b/runtime/…/e4v3/prepare_bundle.py:36-52`):
  `names = set(json.loads(source.read_text())["files"])`, then `names.update(<every *.py>)`. For a dict this is the
  key set; for a list, the item set. The frozen code accepts both shapes. It never reads the dict's per-file SHAs:
  `runtime_pins` hashes the bytes on disk, and `tier_backend.validate_bundle` (`:450-469`) checks only
  `manifest["runtime_files"]`.
- **Real bytes:** `reports/explore/s1/receipts/runtime-pin-r2.json` in the S9 runtime equals the blob at the S9
  build commit of `repo-full` (`git cat-file`, read-only). Its SHA-256 is S4's `S1_RUNTIME_PIN_SHA256`. `files` is a
  dict with 1557 entries, and every value is 64-hex.
- **Must the per-file SHAs match the runtime bytes? No.** 17 of the 1557 values differ from the bytes at P'. Those
  17 are exactly the list S9 records as `tracked_pin_sha_differs_from_git` in `runtime-manifest.json`. A comparison
  would therefore refuse every production run, and the frozen code makes no such comparison. S4 now ignores the
  values, as the frozen code does. (S9 checks that the values are 64-hex. That is S9's own input check, not the frozen
  rule, and S4 does not copy it. A mutant that adds it is killed; see below.)
- **List form:** the frozen `set()` accepts a list, so S4 accepts a list of names too. The task allowed this only if
  the frozen code accepts both, which it does. A list is reachable only with synthetic pins, because the production
  SHA pin fixes the dict bytes.
- **Unchanged and stricter than the frozen rule:**
  - only `runtime-pin-r2.json` is read (no fallback to `runtime-pin.json`; r4 ruling);
  - names must be `str` and pass `relative()`, then the name gates;
  - `si.loads_strict` refuses duplicate keys;
  - any other shape is refused. This covers a string, which the frozen `set()` would split into characters.

### Finding → fix → tests

| Finding | Fix (file:line) | Named tests |
|---|---|---|
| B1: list-only shape check | `assemble_fleet_reference.py:610-615`, `RuntimeInventory.members()`. `isinstance(listed, (dict, list))` and str names, with the new message `S1 runtime pin lacks a files dict (or list) of names`. `names = {relative(n) for n in listed}` gives the keys for a dict. Docstrings updated at `:42-44` and `:562` | `test_s4_r6_runtime_pin.py`: `test_r6_real_pin_bytes_are_the_pinned_dict_in_runtime_and_git`, `test_r6_real_pin_bytes_through_members_in_synthetic_world`, `test_r6_real_runtime_membership_equals_frozen_rule_and_s9`, `test_r6_dict_membership_is_the_keys_not_the_values`, `test_r6_list_form_gives_the_same_set_as_frozen`, `test_r6_other_files_shapes_refused[10 shapes]`, `test_r6_dict_keys_are_gated_like_list_items` |
| B1: per-file SHAs (decision) | not compared (`:612` comment); the frozen rule never reads them | `test_r6_dict_per_file_shas_are_never_compared[4 values]`, `test_r6_real_runtime_membership_equals_frozen_rule_and_s9` (the 17 differences equal S9's record) |
| B1: the fixture wrote a list, so the suite never ran the real shape | `test_assemble_fleet_reference.py:144-145`: World writes `{name: sha256}`. `:589-590`: `runtime_pin_names` writes a dict. `test_s4_r4_git.py:564`: dict | the whole suite now runs the dict shape, including the frozen parity test `test_frozen_runtime_rule_parity`, where frozen `prepare_bundle.runtime_pins` reads the dict fixture |
| B1: regression on the REAL pinned bytes | — | `test_r6_real_pin_bytes_through_members_in_synthetic_world` puts the real 1557-entry bytes through the full assembly in a synthetic world (placeholders for every name; E5 stand-ins as `add_e5` does). `test_r6_real_runtime_membership_equals_frozen_rule_and_s9`: `RuntimeInventory.members()` on the real S9 runtime with production pins = frozen `prepare_bundle.runtime_pins` on the same tree (subprocess, the runtime's own e4v3) = S9's `runtime_files_sha256` and count |

## L4: the assembler's own SHA-256

- Already present in the bundle receipt as **`assembler_sha256`**
  (`assemble_fleet_reference.py:1125`; the value comes from the confined read at `:1166`, set at `:1172`).
- r6 also adds it to both one-line stderr summaries, so the runner can record it without opening the receipt:
  - dry run, `:1177-1179`;
  - real run, `:1183-1184`.
- Test: `test_r6_receipt_and_summary_carry_assembler_sha256`. It checks that the receipt, the dry-run summary and
  the real-run summary all equal the SHA-256 of the file. It also checks `safe_input_sha256`.
- Before r6, no test checked the receipt value, so this test is new coverage.

## Preserved

- The canonical bootstrap r1 region (`:95-250`) is byte-identical to b3-r5. Its region SHA-256 equals
  `test_s4_r5_bootstrap.CANONICAL_SHA256`, and that test passes.
- `safe_input.py` is byte-identical to `safe-input-r3/safe_input.py`.
- No pin covers the assembler bytes inside the code. The old `MUTATION-RESULTS-r4*/r5*` files record b3-r5's SHA
  and are kept as history. `SHA256SUMS` is regenerated.
- The request schema and the runtime membership are unchanged, so the six requests stay valid. The proof below shows
  this.

## Mutation, tests, proof

See README.md (r6 section), `MUTATION-RESULTS-r6.json` and `PROOF-r6.json`.

## Production proof on 127x05 (six real requests)

- Driver: `proof_driver_r6.py` (a copy of the scratch driver that was run). It runs this directory's
  `assemble_fleet_reference.py` (sha256 `76b7b7cf4b9a7ebf9cbcaa46a6d6f1baefca36b40148f6f104d5055cafa4dd63`, equal to every receipt's `assembler_sha256`), with:
  - the `e4v3-venv` interpreter, `-I -B`, `env -i` (PATH/HOME/LANG), cwd `/tmp`, `nice -n 19 taskset -c 8-15`;
  - `--repository end-prep/repo-full` (receipt `repository_head` = the S9 commit);
  - for each request, the committed admissions from `requests/make_requests.out.json`, given as
    `--committed-admission NAME reports/explore/k4s-confirm/end-guard-admissions/<host>-NAME SHA256`;
  - `--out` in a fresh `mkdtemp` under `/dev/shm/b3r6-proof-*`.
- The requests ran one at a time. Each bundle was deleted right after its SHAs were recorded, and the scratch
  directory was then removed. Raw record: `PROOF-r6.json`.
- In every bundle, `runtime_files` has 4307 entries with canonical SHA-256 `fc3dbeb42a7737ab844f1f6033ff42b19cd1d514f9670631e36cc7f72a2008e7`. That equals the requests'
  `runtime_files_sha256` and S9's `runtime-manifest.json`. All six receipts have `production_pins` true and status
  CANDIDATE.

| request | result | tiers-pins.json sha256 | assembly-receipt.json sha256 | runtime files | bundle bytes |
|---|---|---|---|---|---|
| `request-127x03-pf00.json` | PASS (rc 0) | `ca4ce6ef49d460ecce37bad3c6d29229b03a10697b8cd69148163c9cb8d17499` | `ef3f44602cf0e971d497bbd09e32438614dca5c9cbd76b797ba81bc6cf3bc173` | 4307 | 23475396144 |
| `request-127x03-rd00-a00.json` | PASS (rc 0) | `783db178f76c79c358b1e806138072396f6eb72e8b1e1b405a531bfb953d9001` | `0147ce651b36a8d580ac1a9a51c7c0dcac49e5f0a9f882ef3bfbac423cf6b93b` | 4307 | 23475396152 |
| `request-127x03-rd00-a01.json` | PASS (rc 0) | `ab2be9d4155adc4b4c263ec3b33bbd26b68e1d8ed1b5eea6b9f53643808e791d` | `c30dc7b2dd49c91e1a76e1fd00e829461a061b11495de31928dfc6cfdd24fddb` | 4307 | 23475396152 |
| `request-127x04-pf00.json` | PASS (rc 0) | `fd8c9ee5e8fc262f49f17961b62668b2daa156e1c49bfbc26be93754e00faa0f` | `e7d34970ea603b6b1c3c87d3e4bbd00881bbece91db330e9f5b85584a187099d` | 4307 | 23475391999 |
| `request-127x04-rd00-a00.json` | PASS (rc 0) | `2fb48c3e71ca4dbc6be3300cf557eba94d0f6eab36d994385ef1ac7d92f2fb6e` | `da781efa33e10f060986badb37063a5acd900caa8046029944ea48934cebbd6b` | 4307 | 23475392007 |
| `request-127x04-rd00-a01.json` | PASS (rc 0) | `d1292b2eff22e2449237187d6bc8d8dc45e623d43f164bd639a920a549d2a458` | `8ad13c2997c0d4ff7c94de2296bc00098664183d3a1409cb255afaa3509a2df1` | 4307 | 23475392007 |

The 03-pf00 manifest equals the one the audit built with its IA-P1 scratch patch (`ca4ce6ef…`, REPORT B1).

## Mutation (`mutate_s4_r6.py`, 3.12 `-O`)

13/13 KILLED. In each, every named test failed and the suite (`-x`) failed too. NULL controls: 2/2 SURVIVED.

| mutant | result | named killing tests |
|---|---|---|
| B1 list only (the b3-r5 rule) | KILLED | `test_r6_real_runtime_membership_equals_frozen_rule_and_s9`, `test_r6_real_pin_bytes_through_members_in_synthetic_world`, `test_r6_dict_membership_is_the_keys_not_the_values`, `test_happy_path_bundle` |
| B1 dict only (a list refused) | KILLED | `test_r6_list_form_gives_the_same_set_as_frozen` |
| B1 membership = the dict values | KILLED | `test_r6_dict_membership_is_the_keys_not_the_values`, `test_r6_real_runtime_membership_equals_frozen_rule_and_s9` |
| B1 per-file SHAs compared (stricter than frozen) | KILLED | `test_r6_dict_per_file_shas_are_never_compared[ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff]`, `test_r6_real_runtime_membership_equals_frozen_rule_and_s9`, `test_r6_real_pin_bytes_through_members_in_synthetic_world` |
| B1 per-file SHAs must be 64-hex (S9's shape rule, not frozen) | KILLED | `test_r6_dict_per_file_shas_are_never_compared[None]`, `test_r6_dict_per_file_shas_are_never_compared[7]` |
| B1 a string accepted as an iterable of names | KILLED | `test_r6_other_files_shapes_refused[string]` |
| B1 name type check off | KILLED | `test_r6_other_files_shapes_refused[list-int]`, `test_r6_other_files_shapes_refused[list-null]`, `test_r6_other_files_shapes_refused[list-list]` |
| B1 shape check off | KILLED | `test_r6_other_files_shapes_refused[null]`, `test_r6_other_files_shapes_refused[int]`, `test_r6_other_files_shapes_refused[no-files]`, `test_r6_other_files_shapes_refused[top-list]` |
| B1 dict keys not path-checked | KILLED | `test_r6_dict_keys_are_gated_like_list_items`, `test_f1_dotdot_runtime_pin_entry_refused_before_read` |
| L4 receipt assembler_sha256 dropped | KILLED | `test_r6_receipt_and_summary_carry_assembler_sha256` |
| L4 receipt assembler_sha256 = the request SHA | KILLED | `test_r6_receipt_and_summary_carry_assembler_sha256` |
| L4 dry-run summary assembler_sha256 dropped | KILLED | `test_r6_receipt_and_summary_carry_assembler_sha256` |
| L4 real-run summary assembler_sha256 dropped | KILLED | `test_r6_receipt_and_summary_carry_assembler_sha256` |
