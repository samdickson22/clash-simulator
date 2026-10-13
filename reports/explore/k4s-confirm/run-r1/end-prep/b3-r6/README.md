# b3-r6: K4S END fleet-reference bundle assembler (S4), CANDIDATE r6 (B1: runtime-pin-r2 dict shape; L4)

## r6 (current; 2026-10-13, offline on 127x05; `b3-r6/` = copy of `b3-r5/`, which is untouched)

- **B1** (`INTEGRATION-AUDIT-r1` B1, `S4-REFUSAL-b3r5-runtime-pin-files-shape.md`):
  - `RuntimeInventory.members()` (`assemble_fleet_reference.py:610-615`) now follows frozen `prepare_bundle.py:42`
    exactly: names = `set(files)`. That is the keys of the pinned dict `{name: sha256}` (or a list's items, which the
    frozen `set()` also accepts).
  - Every other shape refuses with `S1 runtime pin lacks a files dict (or list) of names`.
  - The per-file SHAs are never compared, as in the frozen code. 17 of the 1557 differ from the runtime bytes at P',
    exactly S9's `tracked_pin_sha_differs_from_git`.
  - Evidence and the finding → fix → test table: `RESPONSE-r6.md`.
- **Fixtures** now write the real dict shape: `test_assemble_fleet_reference.py:144-145` and `:589-590`, and
  `test_s4_r4_git.py:564`.
- **New** `test_s4_r6_runtime_pin.py` (21 tests). Three of them use the REAL pinned bytes (read-only):
  - the S9 runtime copy against `git cat-file` at the S9 commit in repo-full;
  - the real bytes through the full assembly;
  - `members()` on the real S9 runtime, against frozen `prepare_bundle.runtime_pins` and S9's manifest.
- **L4:** the receipt already carried **`assembler_sha256`** (`:1125`). r6 adds the same field to both stderr summary
  lines (`:1179`, `:1184`). Tested.
- **Unchanged:**
  - the canonical bootstrap r1 region `:95-250` (region SHA-256 = `test_s4_r5_bootstrap.CANONICAL_SHA256`, which
    passes);
  - `safe_input.py` (safe-input-r3);
  - the request schema;
  - every pin. No pin covers the assembler bytes.
- **Tests:** frozen root = the same 43-path `git archive` export of 6313e14b in `/dev/shm`, name-gated first (0
  refused). The two real-Q6 tests are deselected with `-k "not test_production_q6"`, verified by `--collect-only`
  before every run. Counts: 336 + 125 + 61 + 21 = 543.

  | Interpreter | normal | `-O` |
  |---|---:|---:|
  | k4s-freeze 3.12.12 (pytest 9.1.1) | **543 passed, 2 deselected** | **543 passed, 2 deselected** |
  | /usr/bin/python3 3.8.10 (pytest 8.3.5 via PYTHONPATH) | **543 passed, 2 deselected** | **543 passed, 2 deselected** |

- **Mutation** (`mutate_s4_r6.py` → `MUTATION-RESULTS-r6.json`, 3.12 `-O`): **13/13 KILLED**. Every mutant failed all
  of its named tests and the suite. NULL 2/2 survived.
- **Production proof:** 6/6 PASS on 127x05 (table and tiers-pins SHAs in `RESPONSE-r6.md`, raw record in
  `PROOF-r6.json`). Every bundle was deleted afterwards.
- **Running:** `run_tests_r6.sh <py312|py38> <normal|O> [--collect-only]`. It expects the frozen export at
  `/dev/shm/b3r6/frozen-*`; see the r4 text for how to build it. Equivalent:

  ```
  cd /tmp && K4S_FROZEN_ROOT=$FR PYTHONDONTWRITEBYTECODE=1 nice -n 19 taskset -c 0-7 <python> -B [-O] -m pytest -q \
      -p no:cacheprovider -k "not test_production_q6" <b3-r6>/test_assemble_fleet_reference.py <b3-r6>/test_s4_r4_git.py \
      <b3-r6>/test_s4_r5_bootstrap.py <b3-r6>/test_s4_r6_runtime_pin.py
  ```

---

## r5 header (kept)

## r5 ( 2026-10-13, offline on 127x05; `b3-r5/` = copy of `b3-r4b/`, which is untouched)

- **END-FULL-F1:** the assembler reads its vendored safe_input r3 only through the canonical bootstrap r1. The
  bootstrap is pasted verbatim at `assemble_fleet_reference.py:93–248` (region SHA-256 `5611c604…`, equal to
  `../bootstrap-r1/k4s_bootstrap_r1.py`). Its checks, in order:
  - a normalized absolute path, with the default from `__file__` and never resolved;
  - the outcome-name families on every component;
  - an `O_DIRECTORY|O_NOFOLLOW` walk from `/`;
  - a regular, single-link leaf of exactly 133606 bytes, checked before any read;
  - an exact read, the SHA-256 pin, and execution of exactly those bytes.

  The fingerprint pin and the production in-process re-check are unchanged. Finding → change → tests:
  `RESPONSE-r5.md`.
- **Unchanged:** everything after the loader is byte-identical to r4b. The layer is safe_input r3 `806e5ebb…`. The
  new pin `SAFE_INPUT_SIZE = 133606` is at :89.
- **New tests:** `test_s4_r5_bootstrap.py` (61), the same set as S2's: the conformance kit on the assembler as a
  script and as an import, against every alias scenario.
- **Changed:** one expectation in `test_s4_r4_git.py` (`other-bytes` now refuses at the size pin).
  `mutate_s4_r4.py`'s three loader mutants are retargeted, and it now passes `-k "not test_production_q6"`.
- **Tests** (frozen root: the same 43-path `git archive` export of 6313e14b in `/dev/shm`, every path name-gated
  first; the **two real-Q6 tests are deselected in every run** with `-k "not test_production_q6"`, verified by
  `--collect-only`; see the disclosure in RESPONSE-r5). Each count is 461 + 61:

  | Interpreter | normal | `-O` |
  |---|---:|---:|
  | k4s-freeze 3.12.12 | **522 passed, 2 deselected** | **522 passed, 2 deselected** |
  | /usr/bin/python3 3.8.10 (pytest 8.3.5) | **522 passed, 2 deselected** | **522 passed, 2 deselected** |

- **Mutation** (`../bootstrap-r1/mutate_adopter.py`, 3.12 `-O`; `MUTATION-RESULTS-r5-*.json`):
  - *Behaviour campaign:* all 27 predicted entrypoint-level mutants were killed. The 4 equivalents and the NULL
    survived. Of the 28 unit mutants, 2 were killed here anyway.
  - *With the canonical-text test:* 59/59 killed.
  - The r4 driver was rerun on the r5 bytes: `MUTATION-RESULTS-r4-driver-on-r5.json`.
- **Running:**

  ```
  cd /tmp && K4S_FROZEN_ROOT=$FR nice -n 19 taskset -c 0-7 <python> -B [-O] -m pytest -q -p no:cacheprovider \
      -k "not test_production_q6" <b3-r5>/test_assemble_fleet_reference.py <b3-r5>/test_s4_r4_git.py <b3-r5>/test_s4_r5_bootstrap.py
  ```

---

## r4b header (kept)

### r4b ( 2026-10-12 from 22:56Z, offline on 127x05; `b3-r4b/` = copy of `b3-r4/`, which is untouched)

- **Layer**: `safe_input.py` is byte-identical to `safe-input-r3/safe_input.py` (`806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00`). The assembler pins that SHA and the fingerprint `33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592` (`assemble_fleet_reference.py:81–83`).
- **E5**:
  - The component hook is removed (`E5_RUNTIME_EXEMPT`, the `e5_runtime_exempt` pin key, `walk_runtime_e5`).
  - The runtime role carries `("E4", "E5")`. The nine `si.E5_RUNTIME_MEMBERS` are hashed only by `si.hash_e5` (pinned blob OID) and never parsed.
  - The repository role carries `("E1", "E4", "E5")`, with the nine as git-plan members. Phase 1 pins them by metadata, and they are never read.
  - Every runtime E5 member must equal the committed HEAD entry (`Committed.check_e5`).
  - Any 10th family-matching member, a moved copy or a case variant refuses by name.
- **Tests** (frozen root = the same 43-path `git archive` export, now of origin/main 6313e14b, in `/dev/shm`): **463 passed** on each of k4s-freeze and e4v3-venv, normal and `-O` (338 + 125).
- **Mutation** (`mutate_s4_r4.py`, `-O`): **37/41 killed**, 0 invalid, 3/3 NULL controls survived. The 4 survivors are declared equivalents (3 from r4, plus `X E5 all-hashed check off`, whose JOINT was killed) (`MUTATION-RESULTS-r4b.json`).
- Finding → change, test list and caveats: `RESPONSE-r4b.md`. `DESIGN.md` and `OPEN-QUESTIONS.md` have r4b notes at the top.
- **Running:** as in r4 below, with `b3-r4b` and `--json MUTATION-RESULTS-r4b.json`.
- In the r4 text below, the "safe_input r2 / f9ca4926 / 6661ca0b" and "E5 hook, production list EMPTY" statements are superseded.

---

## r4 text (kept)

## b3-r4: K4S END fleet-reference bundle assembler (S4), CANDIDATE r4 (safe_input adoption)

Offline candidate, written on 127x05 on 2026-10-12 (from 21:28Z, `date -u`), in `b3-r4/` (copy of `b3-r3b/`, untouched). Nothing has been run against 03/04; nothing is committed or pushed; no SSH. It answers `reviews/SOL-REVIEW-END-S2S4-r3.md` (S4-R3-F1/F2/F3) by adopting the shared `safe_input` r2 layer (P2-1, P2-4), and implements E1 materialised (D2), E4 through the layer's pinned blob OIDs, and the E5 hook (production list EMPTY). Finding → change: `RESPONSE-r3.md`. Design: `DESIGN.md` (§C, §D, §G are r4). Coordinator items: `OPEN-QUESTIONS.md` §r4 (E5 values still to be recorded: blocking for a production assembly at origin/main).

## r4 files

| File | Role |
|---|---|
| `assemble_fleet_reference.py` | The assembler. Every read/write through `safe_input` roles and `si.Writer`; every git call through `si.git_run`/`si.git_plan`. |
| `safe_input.py` | The shared layer, byte-identical to `safe-input-r2/safe_input.py` (SHA-256 `f9ca49267dd350cf7ca6fc64b25ce93f53d8e63e9326356dbc72574ec380b648`; constants fingerprint `6661ca0b7635a3a66d8ab6612b5617435f06128d6e18b6bf96e25594a624d367`). The assembler verifies both before use (pin recorded in the code, `SAFE_INPUT_SHA256` / `SAFE_INPUT_FINGERPRINT`). |
| `test_assemble_fleet_reference.py` | r3/r3b suite, adapted to r4 (RESPONSE-r3 "Intentional … changes"). |
| `test_s4_r4_git.py` | New r4 regression controls (git indirection, metadata-before-blob, name families, E5, loader pins, ordering, pinned reads). |
| `mutate_s4_r4.py`, `MUTATION-RESULTS-r4.json` | r4 mutation driver and its results on the final bytes. |
| `RESPONSE-r3.md` | r4 response (finding → change, file:line). |
| `SHA256SUMS` | SHA-256 of every file in this directory. |
| earlier | `mutation_check_r3*.py`, `mutation-r3b.json`, `RESPONSE-r1.md`, `RESPONSE-r2.md` (kept; they describe r3 code). |

## Running the r4 tests

```
FR=$(mktemp -d /dev/shm/k4s-frozen-XXXXXX)
git -C /mpac/sdicks02/repos/clasher archive <origin/main> -- <the 43 paths below> | tar -x -C "$FR"
cd /tmp && K4S_FROZEN_ROOT=$FR nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B [-O] -m pytest -q -p no:cacheprovider \
    <b3-r4>/test_assemble_fleet_reference.py <b3-r4>/test_s4_r4_git.py
K4S_FROZEN_ROOT=$FR nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B <b3-r4>/mutate_s4_r4.py --jobs 12 --json OUT
rm -rf "$FR"
```

The 43 exported paths (origin/main `15048bd4`): every regular file directly in `reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/` (`git ls-tree origin/main <e4v3>/`, blobs only), `reports/explore/k4s-confirm/plan.json`, `reports/explore/t1/FROZEN-T1.json`, the nine `reports/explore/t1/{common,host_audit,idle_services,system_bus,ssh_transport,perception_confirmation,owned_supervisor,ssh_budget,parent_source_seed}.py`, the four seeds (`reports/explore/t1/receipts/op5-parent-source-127x0{3,8}.json`, `…/op5-parent-generation-127x08.json`, `…/l1/receipts/a21-a2-preparation-20261010-r1/08-transport-identity-20261010T172047Z.json`), and `reports/explore/t1/receipts/{END-A5-runtime-manifest-inventory-diff,END-A3-manifest-01-f6cebbaa,END-A3-manifest-08-f6cebbaa}.json`. None matches a family name (checked before export). For the e4v3 venv (py3.12.12), pytest 9.1.1 was installed with `uv pip install --target` into `/dev/shm` and supplied by `PYTHONPATH`; no venv was modified.

## Verification (127x05, 2026-10-12; every number from this session, on the final bytes in `SHA256SUMS`)

| Interpreter | `K4S_FROZEN_ROOT` set, normal | set, `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **449 passed** | **449 passed** (1 warning: pytest's assertion-rewrite notice) |
| `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` 3.12.12 (pytest 9.1.1 from `/dev/shm`) | **449 passed** | **449 passed** (same warning) |

Without `K4S_FROZEN_ROOT` (k4s-freeze, normal): **424 passed, 25 skipped** (the frozen-consumer and real-Q6 tests). 449 = 338 in `test_assemble_fleet_reference.py` + 111 in `test_s4_r4_git.py`. The two `test_production_q6*` tests ran (they read the 353 KB T1 Q6 index on 05, as in r3b). Frozen-consumer subprocesses inherit `-O`. All runs used `nice -n 19`, `-B`, `-p no:cacheprovider`, from `/tmp`.

**Mutation (`mutate_s4_r4.py`, k4s-freeze 3.12.12, `-O`, `-x`, frozen root set, 12 jobs; `MUTATION-RESULTS-r4.json`, finished 22:48:29Z; assembler, layer and test SHAs recorded inside and equal to the final bytes):** **34 of 38 killed**; 0 invalid; 3 NULL controls all SURVIVED. The 4 survivors are declared equivalents:
- `N Sources leaf gate off` (the full-path `si.name_gate` pass covers every leaf first) → `N Sources both gates off JOINT` killed;
- `N --out name gate off` (`si.check_absent(<out>)` gates the same leaf) → `N --out leaf never gated JOINT` killed;
- `N guard job remote gate off` (the leaf is fixed by `JOB_NAME`, which no family matches; the parent is gated when the remote `si.Policy` is built);
- `X E5 walk always used` (the E5 walk has `walk_tree`'s semantics; identical with an empty map).
A first campaign on earlier test bytes (31/37) exposed one real gap (manifest/receipt mode not asserted: added to the happy path, now killed) and one misclassification (a mutant that errors in a fixture is now counted KILLED; documented in the driver).

**Scratch:** frozen export `/dev/shm/k4s-r4-frozen-*` (43 files), mutation copies `/dev/shm/b3r4-mut-*`, pytest under `/tmp/pytest-of-sdicks02`; all removed except pytest's own retention of its last base temps.

---

## r3/r3b notes (kept; superseded wherever r4 above, DESIGN §C/§G or RESPONSE-r3 differ)

### b3-r3 header (historic)

Offline candidate, written on 127x05 on 2026-10-12 (stamped `2026-10-12T17:17:40Z` by `date -u`). Nothing here has been run against 03/04, and nothing here is committed. It answers `reviews/SOL-REVIEW-END-PKG1-r2.md` (S4: REQUEST_CHANGES) and implements the coordinator's exemption rulings E1–E3 (COORDINATOR `2026-10-12 16:55Z`, commit ab1715910). `RESPONSE-r2.md` maps each finding to a change. The design is in `DESIGN.md`; coordinator items are in `OPEN-QUESTIONS.md`. `RESPONSE-r1.md` is r2's response, kept unchanged.

## Files

| File | Role |
|---|---|
| `assemble_fleet_reference.py` | The assembler (stdlib only). In `--repository` it runs only `git cat-file blob HEAD:<fixed path>` and `git ls-tree -z HEAD -- visualize_battle.py` (E1). |
| `test_assemble_fleet_reference.py` | Offline tests (pytest). |
| `mutation_check_r3.py` | New in r3. Mutation check of the r3 gates: scratch copies in a fresh temp dir, suite under `-O`. |
| `DESIGN.md` | The guard job, bundle layout, check order (§C) and tests (§D). |
| `OPEN-QUESTIONS.md` | Ruled items are marked (R1–R3 by E1–E3). New r3 items are R6 and R7. |
| `RESPONSE-r2.md` | r3: finding → change (file:line), with the mutation table. |
| `RESPONSE-r1.md` | r2's response to the r1 review (unchanged). |

## Modes

- **Production (default).** The constants in `PRODUCTION_PINS` (`assemble_fleet_reference.py:107`) are enforced:
  - `states.pkl` `0addf7c0176c358e19f816a1079208eea370a2764d43a44fc9c1993811ead6f1`;
  - `states-rows.json` `bcd307770b70394878f7da17a97e4a1baa10f6efd7ea06d6b4240901dc0336e5`;
  - `states-rows.bin` `8cc2f611e867dc3891cdab643365193be685057b802cf73847c7fd6c91d6a1cb`;
  - the three frozen models;
  - T1's own-tier `sets`, with canonical SHA `d84b07f6de0ac1cffbbb199221b6fbd795e9f7169aebcbdc445bba282e0c3ae2`;
  - the measurement inventory `42b8986d…`;
  - FROZEN-T1 and the K4S plan;
  - the 128-CPU topology;
  - the admissions (E3), pinned from r4: 03 needs exactly a system bus admission plus an idle service admission (PID 2180947); 04 needs exactly a system bus admission.
    - Each must be the copy committed at HEAD of `--repository`, at exactly `reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>`. For example: `…/127x03-system-bus-admission.json`, `…/127x03-idle-services.json`, `…/127x04-system-bus-admission.json`.
    - Each is named by `--committed-admission NAME REPOSITORY_PATH SHA256`. The assembler refuses to run without these arguments.
    - A stale identity is refused, with a message that names the needed coordinator re-pin ruling.
- **Test only.** Setting `K4S_S4_SYNTHETIC_PINS=/abs/pins.json` selects test mode.
  - The pins file is read through the same gates as every other input (r3, S4-R2-F3).
  - It must carry `"marker": "SYNTHETIC"`, the pins schema and every pin key.
  - It cannot widen or move the E1/E2 exemptions. Only the E2 SHA may differ, for synthetic bytes.
  - Test mode also:
    - requires an `--out` whose name contains `SYNTHETIC`;
    - adds `"k4s_s4_synthetic": "SYNTHETIC-TEST-ONLY"` to the manifest;
    - writes a receipt with `production_pins: false` and `status: SYNTHETIC-TEST-ONLY`.

  The frozen consumers ignore unknown manifest keys, so any production step (S3/S5/runbook) must refuse such a manifest or receipt.

## What r3 changes (SOL-REVIEW-END-PKG1-r2)

- **Hard links (S4-R2-F1).** Every regular-file leaf must have `st_nlink == 1`. This is checked twice:
  - in the lstat walk (`walk()`), before the file is opened;
  - at the descriptor gate (`open_confined()`): an `fstat` of the `O_NOFOLLOW|O_NONBLOCK` descriptor, before any read, hash or copy.

  This applies to every input class:
  - the request;
  - synthetic pins;
  - runtime members, including the E1 target and the E2 file;
  - S1 metadata;
  - measurement entries;
  - Q6 models and state rows;
  - sets;
  - END evidence and its artifacts;
  - the guard freeze, modules, admissions and seeds;
  - the assembler's own file, whose hash goes in the receipt.
- **One location helper (S4-R2-F2).** `location_free()` gates the **complete absolute path** before any `lstat` or open. `walk()` calls it, so every input goes through it. It also gates every auxiliary location:
  - `--repository`;
  - `--out`;
  - the guard-job parent;
  - committed-admission paths;
  - evidence item paths;
  - `git cat-file` paths;
  - seed paths.

  It refuses:
  - outcome, block and job names;
  - FROZEN-T1's launch namespaces;
  - **the strict END namespace**: any `k4s-confirm` component followed by `end`, i.e. `reports/explore/k4s-confirm/end/` wherever it is rooted. The runtime walk refuses that directory without listing it.
- **Synthetic pins (S4-R2-F3).** They are read with `read_confined(*absolute(...))`.
- **E1.** `visualize_battle.py` is exempt only if all of these hold:
  - `--repository` HEAD has it as a mode-120000 entry whose blob is exactly `examples/visualize_battle.py` (`git ls-tree` + `git cat-file`);
  - the runtime has it as the same root-level link.

  The link is never opened. The target is walked and opened by its own path, and passes the hard-link gate.
- **E2.** `imitation/model/receipts/throughput-0935/complete.json` is exempt only at that runtime path, with SHA `d1492d0f…` in production.
  - It is hashed once and never parsed (tested by the audit hook and a `parse_json` probe).
  - Any other `complete.json` is refused.
- **E3.** The admission path must be exactly the E3 path. The identities stay pinned from r4.

## Production consequences (new; see OPEN-QUESTIONS R6, R7)

- **Every input must be a single-link regular file.** Stage copies with plain `cp`, never `cp -l`, `cp -al` or `ln`.
  - The three Q6 files in `t1-20261010-r1/end-a5-pool-context-20261012-r1/bundle/` have `st_nlink == 1`. I checked this with `stat -c %h` only.
  - The real runtime tree, evidence and admissions do not exist yet, so their link counts are unverified.
- **The runtime tree given to S4 must not contain `reports/explore/k4s-confirm/end/`.** The runbook uses the repository as the runtime root (`--runtime-root R … --repository R`), and the END-JOB is committed under `end/`. So S4's runtime must be a staged copy that excludes the END namespace.
  - By the runbook rule, that namespace holds no `.py` and no runtime-pin name. Excluding it therefore does not change the frozen `runtime_files` membership. This is an **inference** until the tree exists.
  - The host-side `validate_bundle` hashes only the listed `runtime_files` (`receipts.verify_files`) and does not recompute membership, so it would not detect this difference. Details are in OPEN-QUESTIONS R6.
- **E1 needs the committed entry at `--repository` HEAD.** Verified at origin/main `fa32ab3f`: `120000 blob a79f7391… visualize_battle.py`, whose blob is `examples/visualize_battle.py`. It is the only tracked symlink.

## Where the pins come from (unchanged from r2; verified then, read-only)

- **Q6 bytes:** `sha256sum` of `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-a5-pool-context-20261012-r1/bundle/{states.pkl,states-rows.json,states-rows.bin}`. The results equal `files[]` in committed `reports/explore/t1/receipts/END-A3-manifest-01-f6cebbaa.json` and `-08-`.
- **Sets:** the canonical SHA of `sets` is the same in both committed A3 manifests and in the six T1 A3/A5 `tiers-pins.json` manifests on 05 listed in r2.
- **Admission identities:** the process rows of committed `run-r1/rounds/r4/evidence/step7/127x0{3,4}-host-admission.json`, and `reports/explore/t1/receipts/idle-services-admission-127x03.json`.
- **E1/E2:** `runtime_files` of the committed A3 manifests. E1 is also checked against the git tree, as above. I did not open the bytes of `throughput-0935/complete.json`.

## Refusals (each has a test that asserts the message)

r2's refusals are kept (names, aliases, outcome names, changes after checking, production pins, admissions, test-only mode, guard job, evidence, state index). r3 adds:

- **Hard links:**
  - `Hard-linked input refused (<label>)` from the walk, in 22 input classes × {consistent SHAs, stale SHAs};
  - the same for `--request`, through the E1 alias walk, and for the assembler file itself;
  - `Hard-linked input refused at open (st_nlink N)` from the descriptor gate: a link made after the walk, and a link made between planning and the copy pass.
- **Strict END namespace:**
  - a sealed END receipt used as `sets` (the reviewer's reproduction);
  - `end/attempt-00.json`, `end/registry/…`, `end/END-JOB.json` and `…/k4s-confirm/end/pools/…` used as a request source;
  - END-namespace runtime members, and the END directory in the runtime tree (never listed);
  - `runtime_root`, `--repository`, `--out` or a committed-admission path inside it;
  - an evidence item, `git cat-file` path or seed path inside it.
- **Auxiliary locations:**
  - `--repository` under `games/`, a job tree or the END namespace (refused by name, before `lstat`);
  - `--out` under `games/`, the END namespace, a job tree, a T1 launch namespace, or named `end-raw.json`; nothing is written;
  - a guard-job parent in an outcome, T1 or END location.
- **Synthetic pins:**
  - through a symlinked parent;
  - under `games/` or the END namespace, or named `complete.json`;
  - hard-linked;
  - a relative or non-normalized path;
  - a widened or moved E1/E2.
- **E1:** a regular file with the same text, a different link text, or no entry at HEAD.
- **E2:** a `complete.json` at any other path; a production SHA other than `d1492d0f…`.
- **E3:** any admission path other than the exact E3 path; a stale bus or idle identity.

## Accepted residual (coordinator scope ruling, COORDINATOR 2026-10-12 16:00Z, commit 1aa63a16)

**TOCTOU:** an ancestor directory could be replaced between the lstat walk and the open. On our single-operator, non-adversarial hosts this is accepted as a residual risk.

The leaf case is still detected. The open uses `O_NOFOLLOW`, and the descriptor must have the walked `(st_dev, st_ino)` and `st_nlink == 1` before any read.

No other residual is claimed. Pre-existing aliases (symlinks or hard links) and forbidden locations are **not** covered by this residual. They are refused statically.

## Running the tests

```
cd /tmp && K4S_FROZEN_ROOT=<read-only detached worktree of origin/main> \
  nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B [-O] -m pytest -q -p no:cacheprovider \
  /mpac/sdicks02/k4s-runner/run-r1/end-prep/b3-r3/test_assemble_fleet_reference.py
cd /tmp && K4S_FROZEN_ROOT=<same> nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B \
  /mpac/sdicks02/k4s-runner/run-r1/end-prep/b3-r3/mutation_check_r3.py --jobs 6
```

Results on 127x05 with origin/main `fa32ab3f` (a detached worktree in `/tmp`, removed afterwards):
- 252 passed normally;
- 252 passed under `-O`;
- without `K4S_FROZEN_ROOT`: 227 passed and 25 skipped;
- mutation check: 27 of 27 mutants killed under `-O`.

The two Q6 production-byte tests run only where the T1 copies exist (05). They read only the 353 KB index.

## r3b: ruling E4 (COORDINATOR 2026-10-12 17:12Z), candidate `b3-r3b/`

`b3-r3b/` is a copy of `b3-r3/` with one change: the single E2 exemption is replaced by the exact four-entry E4 list of tracked `complete.json` files. It is stamped `2026-10-12T17:44:20Z`, offline on 127x05, and nothing is committed. Details and the mutation table are in `RESPONSE-r2.md` § r3b.

**The list.** `E4_COMPLETE_JSON` holds exact paths and SHAs:
- E2 `imitation/model/receipts/throughput-0935/complete.json` `d1492d0f…`;
- `live-loop/v4/emulator-host/complete.json` `0a490639…`;
- `live-loop/v4/l1/receipts/b08-gap-export-20261012-r1/complete.json` `9c84b7a8…`;
- `live-loop/v4/l1/receipts/b08-supplemental-proof-export-20261012-r1/complete.json` `724ee1d7…`.

**Hashing only.** These are never parsed, followed or aliased, and they still pass the location and hard-link gates where they are opened. Each SHA was confirmed against `git show origin/main:<path> | sha256sum` at `d482ab3d` (hashing only). They are the only tracked `complete.json` paths there.

**Fail-closed.** The assembler refuses in these cases:
- the `--repository` HEAD tree (the build commit) tracks any other path with a `complete.json` component;
- an E4 entry is not `100644 blob` or its blob SHA differs;
- the runtime tree on disk has any `complete.json` entry outside the exact paths;
- an E4 entry present in the runtime is a link, is hard-linked, is not a regular file, or has another SHA.

Runtime membership is unchanged: the three non-member E4 files are checked, but they are never runtime members and are never copied.

**Test mode** cannot widen, narrow or move the list. Only the SHAs may differ, for synthetic bytes, and the output is still stamped SYNTHETIC-TEST-ONLY.

**New git commands on `--repository`:**
- `git ls-tree -r -z --full-tree HEAD`;
- `git cat-file blob <oid>` per E4 entry present (hashed only).

**New files:**
- `mutation_check_r3b.py`: the r3 mutants plus 17 E4 mutants;
- `mutation-r3b.json`: its result.

`mutation_check_r3.py` is kept as it was in b3-r3. Its "E2 production SHA" mutant no longer applies to this code.

**Results on 127x05** (origin/main `d482ab3d`, detached worktree in `/tmp`, removed afterwards):
- 328 passed normally;
- 328 passed under `-O`;
- without `K4S_FROZEN_ROOT`: 303 passed and 25 skipped;
- mutation check: 43 of 43 killed under `-O`.

To run it, use the commands above with `b3-r3b/` and `mutation_check_r3b.py`.

**Production consequences:**
- Any future tracked `complete.json`, including under `end/`, makes S4 refuse until a new ruling.
- The staged runtime copy must hold no untracked `complete.json`.

`DESIGN.md` and `OPEN-QUESTIONS.md` are unchanged. Their E2-only text is superseded by this section.
