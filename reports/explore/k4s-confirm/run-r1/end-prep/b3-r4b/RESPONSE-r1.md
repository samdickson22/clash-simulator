# RESPONSE to SOL-REVIEW-END-PKG1-r1, S4 (b3-r1 → b3-r2)

- **Reviewed bytes (r1):** assembler `00f4dea5…`, tests `4b74e866…` and DESIGN `950ecb7a…`. These match the review (re-hashed in `b3-r1/`).
- **Candidate:** `b3-r2/` was created as a copy of `b3-r1/`; no other file was edited.
- **Rulings applied (binding):**
  - COORDINATOR 2026-10-12 15:41Z (`fa89baa9`): Q2–Q6 and Q9.
  - 16:00Z scope ruling (`1aa63a16`): TOCTOU is an accepted residual; every other finding is required.
- **Line references:** `A:` is `assemble_fleet_reference.py` and `T:` is `test_assemble_fleet_reference.py`, both in b3-r2.

## S4-F1 (blocking): runtime and measurement inventory reads bypass confinement

**Change.** Every name and every entry is confined before its bytes are read.

- **Name rules.** `relative()` (A:185) refuses an absolute path, `''`, `.`, `..`, a backslash or a NUL.
- **Outcome locations, refused by name only** (`outcome_free()` A:194; `no_t1_launch_namespace()` A:206):
  - a `games` or `hub-blocks` component;
  - a leaf in the `complete.json` family, `interference.json`, `hub-ack.json` or `end-raw.json`;
  - a `k4s-confirm-*` or `k4s-end-guard-*` job component;
  - one of FROZEN-T1's five launch namespaces.
- **Alias walk.** `walk()` (A:212) lstats each component from its declared root and refuses a symlink anywhere. The one exception is the pinned root-level alias `visualize_battle.py → examples/visualize_battle.py` (exact link text required). This alias is a tracked git symlink and a member of T1's END `runtime_files`. Without the exception, the production runtime would be refused.
- **Request sources.** `absolute()` (A:245) applies the same walk to request sources, from `/`. It also requires `normpath`-normal paths.
- **Opening.** `open_confined()` (A:258) opens with `O_NOFOLLOW`, and the fstat `(st_dev, st_ino)` must equal the walked lstat.
- **Runtime inventory.**
  - `runtime_python()` (A:361) replaces `rglob('*.py')` with an `os.scandir` walk that does not follow links. It refuses every non-pinned symlink (A:372) and every outcome or job directory (A:375); these directories are never listed.
  - For parity with Python 3.12 `rglob`, directories and special files named `*.py` are included and then refused as non-files. I verified on 3.12.12 that `rglob` matches file symlinks and does not descend into symlinked directories.
  - `runtime_files()` (A:382) confines every S1 runtime-pin entry (A:400) and the S1 metadata JSONs before hashing.
  - The single outcome-named membership file, `imitation/model/receipts/throughput-0935/complete.json`, is bound by path and by SHA `d1492d0f…` from T1's A3 manifests (A:416). Its bytes were not opened by me (see OPEN-QUESTIONS R2).
- **Measurement inventory.** `measurement_files()` (A:349) walks each entry; a symlink or non-file is refused.
- **Evidence items.** Every item is name-checked and walked before it is hashed.

**The four reviewer controls.** Each control asserts its refusal message, uses a canary file at mode 000, and checks that the canary path never reached `open_confined` (the `opened` fixture records every content open):

| Reviewer control | Test |
|---|---|
| Absolute runtime-pin entry | T:546 |
| `../synthetic-marker.json` | T:553 |
| Runtime `.py` symlink to a `games/` canary | T:560 |
| Measurement `.py` symlink outside the tree | T:567 |

**Further controls:**

| Control | Test |
|---|---|
| Entry through a symlinked directory | T:574 |
| `games/` and `complete.json` inventory names | T:582 |
| `games/` directory in the runtime tree is never descended | T:594 |
| Exception with the wrong SHA | T:600 |
| Alias with wrong text, as a regular file, or as an absolute link | T:605 |
| Symlinked S1 pin JSON | T:617 |
| Symlinked ancestor in a request source | T:625 |
| Seven outcome or job-tree request paths | T:642 |
| Evidence artifact that is a symlink, under `games/`, or under `end/` | T:648 |
| Leaf replaced or symlink-swapped after the walk | T:671 |
| Symlinked `--out` parent: refused, nothing written | T:684 |

**Write side.** Copies are made from the confined descriptor while being hashed, into `O_CREAT|O_EXCL|O_NOFOLLOW` targets (A:743, A:737). The `--out` parent is lstat-walked (A:721). `remove_stage` does not follow links (A:792).

**TOCTOU.** Replacement of an ancestor directory between the walk and the open is the accepted residual. This is stated in README and DESIGN §C.2.

## S4-F2 (required): enforce the ruled production inputs

**Change.** `PRODUCTION_PINS` (A:86) is enforced unless the test-only switch is set (`active_pins()` A:334). The values were verified as follows.

**Q6 state bytes.** I ran `sha256sum` on the 05 copies in `end-a5-pool-context-20261012-r1/bundle/`:

| File | SHA-256 |
|---|---|
| `states.pkl` | `0addf7c0176c358e19f816a1079208eea370a2764d43a44fc9c1993811ead6f1` |
| `states-rows.json` | `bcd307770b70394878f7da17a97e4a1baa10f6efd7ea06d6b4240901dc0336e5` |
| `states-rows.bin` | `8cc2f611e867dc3891cdab643365193be685057b802cf73847c7fd6c91d6a1cb` |

These equal `files[]` in the committed `END-A3-manifest-01/08-f6cebbaa.json`.

**T1 own-tier `sets`.**
- The canonical SHA is `d84b07f6de0ac1cffbbb199221b6fbd795e9f7169aebcbdc445bba282e0c3ae2`: golden 125, speed 4×300.
- It is identical in both committed A3 manifests and in six A3/A5 `tiers-pins.json` files on 05 (listed in README). One of these is the pool-context manifest f81c9288, which equals `manifest_sha256` in `END-A5-reference-approved-argv-08-r1.json`.
- Checked at A:546. The test on 05 confirms every speed ID is in the real Q6 index (T:1270).

**Admissions.**
- The pinned set is exactly {bus, idle} on 03 and {bus} on 04 (A:651).
- The bus identity must equal the r4 committed row: 03 PID 2049 / 1273, 04 PID 2005 / 1032 (A:665).
- On 03, the idle `service` identity must equal PID 2180947 / ppid 2180946 / pgid 2180934 / start_ticks 139691386 / cmdline `16152ceb…` / uid 3822945 (A:672).

**Committed Q2 copy.** The copy is not committed yet, so the assembler requires an argument binding.
- `--committed-admission NAME REPOSITORY_PATH SHA256` is mandatory for exactly the host's pinned set (`committed_bindings()` A:471).
- The path must be under `reports/explore/k4s-confirm/`, not under `end/`, end in `.json` and contain the host name.
- The SHA of the HEAD blob in `--repository` must equal the argument (`git_blob()` A:459).
- The request source must be that committed file (A:658), and its SHA must equal the argument.
- Without the argument the assembler refuses (T:819).

**Other pins:**
- measurement inventory `42b8986d…` (A:520);
- topology = T1's 128-CPU value (A:563);
- frozen models, FROZEN-T1 and the plan, as in r1.

**Fresh guard jobs.**
- The `-rdRR-aNN` (attempt) or `-pfNN` (preflight) suffix is mandatory (A:130).
- The job path must not exist at assembly time (A:632).

**Topology.** S4 cannot observe the target host. The pin is T1's value; the binding check remains the live `validate_topology` in the S5 preflight (OPEN-QUESTIONS R5).

**Evidence location.** The evidence must be `--repository/reports/explore/k4s-confirm/end-evidence.json` and equal its HEAD blob (A:571, A:574). Each item's `repository_path` must be `reports/explore/k4s-confirm/<path>` and not under `end/` (A:593). All items must share one commit (A:605). This matches S2's builder rule.

**Test-only mode.**
- `K4S_S4_SYNTHETIC_PINS` must name a pins file with `"marker": "SYNTHETIC"`, the pins schema and every key.
- The `--out` name must contain `SYNTHETIC` (A:733).
- The manifest gets `k4s_s4_synthetic: SYNTHETIC-TEST-ONLY` (A:708). The receipt gets `production_pins: false` and `status: SYNTHETIC-TEST-ONLY` (A:778).
- So test mode cannot emit an unmarked manifest. The frozen consumers ignore unknown keys, so S3/S5 must refuse a marked manifest (README).

**Tests.**

| Check | Test |
|---|---|
| Constants equal the verified values | T:749 |
| Production is the default and refuses synthetic inputs | T:768 |
| Each model, index and bin pin is enforced, by moving one synthetic pin to its production value | T:782 |
| Sets pin | T:787 |
| Measurement, freeze and plan pins | T:792 |
| 03 without idle: the reviewer's omission probe now refuses, in the request and in the CLI binding | T:802 |
| 04 with idle | T:809 |
| Binding argument checks | T:819, T:832 |
| Committed copy vs work tree vs argument | T:837 |
| Identity, uid, host and service count | T:859 |
| Test-mode marker, keys and `--out` name | T:872 |
| Job suffix and freshness | T:896–913 |
| Evidence HEAD and location | T:525 |
| One commit | T:519 |

**Inputs not enforceable in S4.** "Use only their authorized copies on 05" is enforced by SHA, not by path: A2 staging may copy them into the K4S namespace. "Maintain distinct fresh guard jobs for preflights and each attempt" is enforced through naming and non-existence; distinctness across bundles is procedural (S3).

## S4-F3 (required): state-index acceptance weaker than the frozen loader

**Change.** I did both things the brief preferred:

- The index bytes are pinned (`bcd30777…`).
- `check_state_index()` (A:427; called at A:540) mirrors `state_rows.StateRows.__init__` (`state_rows.py:34-61`) without unpickling:
  - schema;
  - `pickle_protocol == 5`, as an int;
  - the source pin and `verified`;
  - the container pin;
  - row count equal to `source.rows`;
  - rows contiguous from 0 with positive lengths;
  - final length equal to `container.bytes`;
  - unique IDs;
  - container file size equal to the index length.

  It is stricter than the frozen loader on integer types, string IDs and 64-hex row SHAs.

**Tests.**
- T:1019–1044 covers 13 mutants, including the reviewer's protocol 999 and offset 77, plus a container-size mismatch.
- **Reuse of the frozen validation offline:** T:1160 runs the real frozen `StateRows` on each of the 13 mutants. Each is refused by both the frozen loader and the mirror. A control confirms the frozen loader pins the index bytes.
- **Real index:** on 05 the real Q6 index passes the mirror (T:1258). The frozen `StateRows` accepts it (T:1270) with a sparse stand-in container of the pinned size; no pickle is loaded.
- The mandatory S5 preflight is not replaced by these checks.

## General S4 observations in the review

- **`frozen_python()` did not propagate `-O`.** Fixed (T:1083). It passes `-O` when `sys.flags.optimize` is set, asserted by T:1091. The CLI subprocess test also inherits `-O`.
- **The real-consumer tests patch three policy-model SHA constants and use synthetic states and admissions.** This is unchanged for `validate_bundle`, because the real models cannot be used offline. Added: the real Q6 index through the mirror and the frozen `StateRows`, and the real T1 sets against it (T:1258, T:1270). DESIGN §D states what remains synthetic.
- **The test guard `repo/` is a file tree, not the Q3 git clone.** Acknowledged. This is S3's responsibility (Q3 ruled: Option A plus preflight `git cat-file -e`). Stated in DESIGN §D.
- **DESIGN descriptions of unavailable T1 inputs and old draft questions should be reconciled with fa89baa9.** Done:
  - DESIGN header, §0, §A.3, §A.5, §B.5 and §F are updated, and §C and §D are rewritten.
  - OPEN-QUESTIONS marks Q1–Q6 and Q9 as ruled, with their commits, and adds R1–R5. These cover the committed-admission path, the one hashed outcome-named runtime file, stale identity pins, `-pfNN`, and the topology pin.
- **Add the reviewer regressions and boundary probes with refusal-before-access expectations.** Done for the six S4 probes: the four F1 probes, the F2 omission and the F3 protocol/offset. The reviewer's scratch files in `/tmp/sol-end-pkg1-r1-*` were not used. The controls were rewritten from the review text.

## Verification

- **Command:** `cd /tmp && K4S_FROZEN_ROOT=/tmp/b3r2-wt nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B [-O] -m pytest -q -p no:cacheprovider <b3-r2>/test_assemble_fleet_reference.py`. Here `/tmp/b3r2-wt` is a detached worktree of origin/main `1aa63a16`, removed after the session.
- **Results:**
  - **164 passed** normally;
  - **164 passed** under `-O`;
  - without `K4S_FROZEN_ROOT`: **139 passed, 25 skipped**.
- **Name rules on the real lists:** every name in `runtime-pin-r2.json` (1,557) and in T1's A3 `runtime_files` (3,785) passes the r2 rules, with zero refusals (checked with the r2 functions).

**Mutation check under `-O`.** Each mutant was applied to a scratch copy in `/tmp`; scratch copies were deleted afterwards. **33 of 33 killed.**
- Two mutants, `lstat→stat` and "walk ignores symlinks", were killed by fixture-setup errors: the pinned alias in every synthetic runtime then fails.
- A separate targeted variant ("symlinks ignored unless an alias is pinned") was killed by five F1 tests: T:567, T:617, T:625, T:648 and T:684.

| Mutant | Result | Killing tests (first few) |
|---|---|---|
| F1 relative() unchecked | KILLED | evidence `Unsafe relative path` ×2, T:546, T:553 |
| F1 walk ignores symlinks | KILLED | fixture setup (140 errors) |
| F1 lstat→stat (follow links) | KILLED | fixture setup (140 errors) |
| F1 runtime scan accepts symlinks | KILLED | T:560 |
| F1 outcome_free no-op | KILLED | T:582, T:642 (several) |
| F1 runtime games dir descended | KILLED | T:594 |
| F1 open without inode check | KILLED | T:671 |
| F1 open follows links | KILLED | T:671 |
| F1 exception SHA unchecked | KILLED | T:600 |
| F1 T1 launch namespace allowed | KILLED | T:642 |
| F1 --out parent not walked | KILLED | T:684 |
| F2 synthetic marker unchecked | KILLED | T:872 |
| F2 synthetic out name unchecked | KILLED | T:872 |
| F2 sets pin removed | KILLED | T:787 |
| F2 model pins not passed | KILLED | T:782 ×3 |
| F2 index pin not passed | KILLED | T:782 |
| F2 topology pin removed | KILLED | topology pin case |
| F2 measurement pin removed | KILLED | T:768, T:792 |
| F2 admission set subset | KILLED | T:802, T:941 |
| F2 committed set subset | KILLED | T:802, T:819 |
| F2 committed blob unchecked | KILLED | T:832, T:837 |
| F2 admission not committed copy | KILLED | T:837 |
| F2 bus identity unpinned | KILLED | T:859 |
| F2 idle identity unpinned | KILLED | T:859 |
| F2 guard job freshness removed | KILLED | T:907 |
| F2 evidence HEAD blob unchecked | KILLED | T:525 |
| F2 one-commit check removed | KILLED | T:519 |
| F3 protocol unchecked | KILLED | T:1037 ×2, T:1160 ×2 |
| F3 contiguity unchecked | KILLED | T:1037 ×3, T:1160 |
| F3 final length unchecked | KILLED | T:1037, T:1160 |
| F3 container size unchecked | KILLED | T:1044 |
| F3 duplicate IDs unchecked | KILLED | T:1037, T:1160 |
| copy digest unchecked | KILLED | T:718 |

## Not done or not claimed

- **No production-mode end-to-end run.** The runtime tree, the END evidence and the committed Q2 admissions do not exist yet.
- **Not re-hashed:** the 11 other Q6 copies on 05.
- **No host access, no SSH, no commits.**
