# b3-r2: K4S END fleet-reference bundle assembler (S4), CANDIDATE r2

Offline candidate, written on 127x05 on 2026-10-12. Nothing here has been run against 03/04, and nothing here is committed. It answers `reviews/SOL-REVIEW-END-PKG1-r1.md` (S4); `RESPONSE-r1.md` maps each finding to a change. The design is in `DESIGN.md`, and coordinator items are in `OPEN-QUESTIONS.md`.

## Files

| File | Role |
|---|---|
| `assemble_fleet_reference.py` | The assembler (stdlib only; it runs `git cat-file blob HEAD:<path>` and nothing else in `--repository`). |
| `test_assemble_fleet_reference.py` | Offline tests (pytest). |
| `DESIGN.md` | The guard job, bundle layout, check order (§C) and tests (§D). |
| `OPEN-QUESTIONS.md` | Ruled items are marked; new r2 items are R1–R5. |
| `RESPONSE-r1.md` | Finding → change (file:line), plus the mutation table. |

## Modes

- **Production (default).** The constants in `PRODUCTION_PINS` (`assemble_fleet_reference.py:86`) are enforced:
  - `states.pkl` `0addf7c0176c358e19f816a1079208eea370a2764d43a44fc9c1993811ead6f1`;
  - `states-rows.json` `bcd307770b70394878f7da17a97e4a1baa10f6efd7ea06d6b4240901dc0336e5`;
  - `states-rows.bin` `8cc2f611e867dc3891cdab643365193be685057b802cf73847c7fd6c91d6a1cb`;
  - the three frozen models;
  - T1's own-tier `sets`, with canonical SHA `d84b07f6de0ac1cffbbb199221b6fbd795e9f7169aebcbdc445bba282e0c3ae2`;
  - the measurement inventory `42b8986d…`;
  - FROZEN-T1 and the K4S plan;
  - the 128-CPU topology;
  - the admissions: 03 needs exactly a system bus admission plus an idle service admission (PID 2180947), and 04 needs exactly a system bus admission. Each must be the copy committed at HEAD of `--repository`, named by `--committed-admission NAME REPOSITORY_PATH SHA256`. The assembler refuses to run without these arguments.
- **Test only.** Setting `K4S_S4_SYNTHETIC_PINS=/abs/pins.json` selects test mode. The file must carry `"marker": "SYNTHETIC"`, the pins schema and every pin key. Test mode also:
  - requires an `--out` whose name contains `SYNTHETIC`;
  - adds `"k4s_s4_synthetic": "SYNTHETIC-TEST-ONLY"` to the manifest;
  - writes a receipt with `production_pins: false` and `status: SYNTHETIC-TEST-ONLY`.

  The frozen consumers ignore unknown manifest keys, so any production step (S3/S5/runbook) must refuse such a manifest or receipt.

## Where the pins come from (all verified in this session, read-only)

- **Q6 bytes:** `sha256sum` of `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-a5-pool-context-20261012-r1/bundle/{states.pkl,states-rows.json,states-rows.bin}`. The results equal `files[]` in committed `reports/explore/t1/receipts/END-A3-manifest-01-f6cebbaa.json` (bd9804c3) and `-08-` (1bd8a4c7).
- **Sets:** the canonical SHA of `sets` is the same in both committed A3 manifests and in these T1 manifests on 05 (only `sets` and `files` were parsed):
  - `end-a5-pool-context-20261012-r1/bundle/tiers-pins.json` (f81c9288, which is `manifest_sha256` in committed `END-A5-reference-approved-argv-08-r1.json`);
  - `end-a5-0775b704-0108-r1-shipping/smoke-bundle/tiers-pins.json` (c84d65ed);
  - `end-a5-CANDIDATE-base-20261012-r1/A3-input-bundles/127x0{1,8}/tiers-pins.json` (bd9804c3 / 1bd8a4c7);
  - `end-a5-CANDIDATE-0775b704-0108-r1/reference-base-bundles/127x0{1,8}/tiers-pins.json` (5df0fa00 / 93daf063).
- **Admission identities:** the process rows of committed `run-r1/rounds/r4/evidence/step7/127x0{3,4}-host-admission.json`, and `reports/explore/t1/receipts/idle-services-admission-127x03.json`.
- **Runtime alias and outcome-named exception:** `runtime_files` of the committed A3 manifests. The `throughput-0935/complete.json` bytes were not opened.

## Refusals added in r2 (each has a test that asserts the message)

- **Names and aliases:**
  - an unsafe inventory name (absolute, `..`, empty, `.`, backslash, NUL);
  - a symlink in any path component, except the pinned `visualize_battle.py` alias;
  - a symlink anywhere in the runtime tree;
  - a mismatched or non-symlink alias.
- **Outcome locations:**
  - an outcome-, block- or job-tree name: `games`, `hub-blocks`, the `complete.json` family, `interference.json`, `hub-ack.json`, `end-raw.json`, `k4s-confirm-*`, `k4s-end-guard-*`, or one of the T1 launch namespaces;
  - a `games`/`hub-blocks` directory in the runtime tree;
  - a wrong SHA on the outcome-named exception.
- **Changes after checking:**
  - a leaf replaced, or swapped for a symlink, between the check and the open;
  - a source that changes during the copy;
  - a symlinked `--out` parent.
- **Production pins:**
  - each model, index or bin pin, the sets pin, the topology pin and the measurement pin;
  - the FROZEN-T1 and plan pins.
- **Admissions:**
  - 03 without its idle admission, or 04 with one;
  - a missing, duplicate, unknown or misplaced `--committed-admission`;
  - a mismatch between HEAD, the work tree and the argument SHA;
  - an admission that is not the committed copy;
  - a bus or idle identity, uid, host or service count different from the pin.
- **Test-only mode:** a pins file with a missing or wrong marker or missing keys; an `--out` whose name lacks `SYNTHETIC`.
- **Guard job:** a job name without its `-rdRR-aNN`/`-pfNN` suffix, or a job that already exists.
- **Evidence:**
  - END evidence that is not at `REPO/reports/explore/k4s-confirm/end-evidence.json`, or not equal to its HEAD blob;
  - an item whose `repository_path` is not `reports/explore/k4s-confirm/<path>`, or that lies under `end/`;
  - items that span more than one commit.
- **State index (the frozen `StateRows` checks):** protocol, contiguity, positive lengths, final length, row count, duplicates, verified source, container pins, and container size.

## Accepted residual (coordinator scope ruling, COORDINATOR 2026-10-12 16:00Z, commit 1aa63a16)

**TOCTOU:** an ancestor directory could be replaced between the lstat walk and the open. On our single-operator, non-adversarial hosts this is accepted as a residual risk. The leaf case is still detected: the open uses `O_NOFOLLOW` and checks that `(st_dev, st_ino)` matches. No other residual is claimed.

## Running the tests

```
cd /tmp && K4S_FROZEN_ROOT=<read-only detached worktree of origin/main> \
  nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B [-O] -m pytest -q -p no:cacheprovider \
  /mpac/sdicks02/k4s-runner/run-r1/end-prep/b3-r2/test_assemble_fleet_reference.py
```

Results with origin/main 1aa63a16:
- 164 passed, both normally and under `-O`;
- without `K4S_FROZEN_ROOT`: 139 passed and 25 skipped.

The two Q6 production-byte tests run only where the T1 copies exist (05). They read the 353 KB index only.
