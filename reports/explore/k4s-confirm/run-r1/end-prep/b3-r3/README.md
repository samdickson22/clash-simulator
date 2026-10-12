# b3-r3: K4S END fleet-reference bundle assembler (S4), CANDIDATE r3

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
