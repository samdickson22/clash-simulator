# rocheck-r1: K4S END backend writes into its input trees (RO-1 step 1, dynamic close-the-class check, 127x05)

**Verdict: CLEAN.** I ran everything S5 `preflight()` does before `loaded_hold`, on 05, with the real native, corpus, bundle and runtime. The input trees (runtime, bundle and end-inputs) were read-only copies. The only write attempt into them was the known one: `es_common.py:20` `RESULTS.mkdir(exist_ok=True)`. It ran once per process (reference process plus the background worker). Against the pre-created empty read-only `engine-speed/results` dir it raised `FileExistsError`/EEXIST, which `exist_ok` absorbs, so the import went through. Apart from that there were no write attempts, no EACCES/EPERM/EROFS anywhere, and nothing on stderr. The before/after inventory diff is empty for all four observed trees (the repository included).

The ruling's fix (an empty read-only `engine-speed/results` dir) is sufficient for this phase. EEXIST takes precedence over EACCES for `mkdir` of an existing entry under a read-only parent. This was confirmed both by a separate self-test and by this run.

## What ran (driver `driver/rocheck_driver.py`, launcher `run.sh`)

- **Tool:** a read-only copy of the deployed `k4s_end_preflight.py`. Its SHA-256 equals the TOOLS-FINAL pin; it is listed in the hash section below.
- **Code paths:** the driver uses the tool's own `Frozen(runtime_root)` (S5's frozen sys.path and import order) and `frozen_namespace(a, F)` (`a` = the 03 l01 launch argv `run ...`, with `/mpac/sdicks02/jobs/clasher/k4s-end-r1` mapped to the scratch base). It then replays `preflight()` lines 756-879 in order:
  1. frozen_helpers
  2. frozen_identity: real native and corpus hashes, bundle `validate_bundle`, K4S pins, SD1, executing_sources
  3. guard_tools: imports fleet_reference and telemetry
  4. reporting_profile: `end_evidence` → 44 `git show` + 44 `git merge-base --is-ancestor` per process, against a full clone at P' 98566c03
  5. physical_cpus: passed on 05
  6. backend_and_corpus: `ER.backend(r)` = K4SBackend → TierBackend (fair_player → differential → es_common), the 2.8 GB K4 pickle, 300 corpus states, `L.check_corpus`
  7. spawn `Array`/`Pipe` creation
  8. topology: passed, 2 clusters
  9. `K4SFleetBackground` started and taken to readiness: ready in about 55 s, and the worker ran 6 corpus work units before the stop
  10. `__exit__` (check + close, worker exit code 0), then `ER.cleanup_steps(state)`, which passed
- **Never called:** `measure()`, pool_context, producer_claim, K4SStore, registry or claim. There was no host contact.
- **Skipped (host-specific or not applicable):**
  - reference_monitor and guard_admission (127x03 dbus/identity guard)
  - guard_job_fresh (03 Q4 guard parent)
  - bundle_parity (the compare bundle is not staged here; it is a pure manifest comparison)
  - end_job_read_only (S5 also skips it: no `--end-job-sha256`)
  - The S5 pre-`preflight()` safe_input checks (listings, bundle_stamp, guard_repo, repository_clone, pre_import_pins). These are reads; their only writes go through `si.Writer` into the preflight `out` dir, which is outside the input trees.
- **Load:** ONE background mask (the first of 10, `[5..9]`) instead of 10, to keep 05 light. The worker code path is identical per slot.
- **Run window:** launched 2026-10-14T00:10:51Z, exited rc=0 at 00:12:49Z.

### Deviations (none touch a write path)
- **Interpreter:** `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -B`, Python 3.12.12, torch 2.10.0+cpu, numpy 2.2.6. The host venv is uv cpython 3.12.13.
- **Environment:**
  - Same as the launch argv: OMP/OPENBLAS/MKL_NUM_THREADS=1.
  - Same as `frozen_git_env`: inherited GIT_* stripped; the P2-4 GIT_* keys and GIT_CONFIG_PARAMETERS set.
  - Not set: PYTHONHASHSEED, because the S5 argv does not set it.
  - Added: PYTHONPATH=audit dir and ROCHECK_LOG_DIR. The full environment is in `logs/env.txt`.
- **cwd:** the empty `rocheck-r1/work/` (still empty afterwards). The host cwd is not pinned.
- **Scheduling:** `nice -n 19 taskset -c 8-23`.
- **Host-identity shims in `audit/sitecustomize.py`, every use logged:**
  - `platform.node()` → "127x03"
  - `os.getpriority` → 10 when the real value is 19
  - `os.sched_setaffinity` → logged no-op, so processes stayed on 8-23 rather than the plan masks 0-4 and 5-9
- **Repository:** the same tool chain needs `<base>/repository`, a full clone at P'. I built it by `git fetch` from `end-prep/repo-full` (a read of repo-full). It was left writable, as on the host, and inventoried.

## Tracing method
- **Audit hook:** a Python audit hook (`sys.addaudithook`) runs in every process via `sitecustomize.py` on PYTHONPATH. Spawn children inherit it: 3 processes were seen (reference 111142, resource tracker 111967, background worker 234708), all of which exited normally. Each process logs per-pid JSONL to `tracelog/`.
- **What it records:**
  - open with a w/a/x/+ mode or WRONLY/RDWR/CREAT/TRUNC/APPEND/EXCL flags
  - os.mkdir/rename(replace)/remove/rmdir/symlink/link/chmod/chown/truncate/utime
  - shutil.*, tempfile.mkstemp/mkdtemp, sqlite3.connect
  - subprocess/exec, ctypes.dlopen, mmap, socket.bind, chdir
  - each event with an 8-frame stack
- **Raised OSErrors:** a `sys.monitoring` RAISE callback logs every raised OSError with EACCES/EPERM/EROFS/EDQUOT/ENOSPC/EEXIST, including ones the code catches.
- **Self-test:** the hook was checked beforehand in /tmp. It caught the write open, mkdir, rename, mkstemp, EACCES on a read-only dir, and EEXIST for `mkdir(exist_ok=True)` under a read-only parent.
- **Native code:** writes from clasher_core, torch or git bypass the hook. They are covered by (a) `chmod -R a-w` on the runtime, bundle and end-inputs trees (and the `bundles/` parent), so any write fails loudly, with no failure seen and stderr empty, and (b) full lstat inventories (type, size, mode, mtime_ns, ctime_ns, ino, nlink) before and after, of runtime (4734 entries), bundle (111), end-inputs (3) and repository (13059). The diff was **empty** in all four.

## Every write attempt (`logs/analysis.json` has full stacks)

**Inside the input trees** (runtime, bundle, end-inputs, repository, base):

| pid | op | path | frame | result |
|---|---|---|---|---|
| 111142 (reference) | os.mkdir | runtime/reports/strategy_council_20260928/engine-speed/results | es_common.py:20 `<module>` via pathlib.mkdir (fair_player → differential → es_common, from TierBackend.__init__) | EEXIST, absorbed by exist_ok |
| 234708 (background) | os.mkdir | same | same | EEXIST, absorbed by exist_ok |

Nothing else wrote inside the trees: there were no other audited ops there and no inventory change.

**Outside** (these matter for the END environment):

| pid | op | path | frame |
|---|---|---|---|
| 111142, 234708 | open(w)+remove | /tmp/<random> (one per process) | tempfile._get_default_tempdir (stdlib probe for a writable TMPDIR; triggered by torch/stdlib import) |
| 111142 | tempfile.mkstemp + open + remove + ftruncate on fd | /dev/shm/pym-111142-* (unlinked immediately) | multiprocessing.heap Arena (`context.Array` for phase/owned) |
| 111142, 234708 | open(w) | /dev/null (8 opens) | dill `_dill.py:164` get_file_type and `_pyio` (import-time probes) |
| 111142 | open(w) on fd | pipe | multiprocessing popen_spawn_posix (spawn handshake) |
| 111142 | open(a) | rocheck-r1/logs/driver-steps.jsonl | harness only (my driver's step log) |

- Nothing was written under `$HOME`: no `~/.cache`, torch, numba or XDG output. A find over HOME, /tmp, /dev/shm, /var/tmp and work/ for the run window found only the `/dev/shm` dir mtime (the arena above) and an unrelated `/tmp/k4s-r2t-*` tree. That tree belongs to another thread's test; none of my PIDs ran mkdtemp.
- **Subprocesses:** only `git -C <base>/repository show <commit>:<path>` and `git ... merge-base --is-ancestor`, 44 of each per process (88 per process, 176 total), with `GIT_OPTIONAL_LOCKS=0`. The repository inventory is unchanged.
- **Other events:** ctypes.dlopen of torch `libtorch_global_deps.so` (×2) and `None` (×2), one anonymous `mmap` (fd 8, 4096 bytes: the arena).
- **Failures:** none. The driver and background worker both exited 0 and cleanup passed. The two EEXIST raises above are the only watched-errno raises; there were no EACCES, EPERM or EROFS raises.

## Implications for END
- Within this phase, the runtime, bundle and end-inputs trees need no write access beyond the existing empty `engine-speed/results` dir.
- The END processes need a writable TMPDIR (default /tmp) for the stdlib tempdir probe, and a writable /dev/shm for the multiprocessing Arena.
- **Not covered:** this check covers the pre-hold phase only. The hold and `measure()` (search work in the reference slot at scale, deadlines) were not exercised, apart from the 6 background corpus work units run before stop.

## Files
- `run.sh` (launcher), `driver/rocheck_driver.py`, `driver/inventory.py`, `driver/analyze.py`, `audit/sitecustomize.py`, plus read-only copies of `driver/k4s_end_preflight.py` and `driver/launch-argv.json`
- `logs/run.log`, `logs/driver-steps.jsonl`, `logs/env.txt`, `tracelog/audit-<pid>.jsonl` (3 files), `logs/analysis.json`, `logs/inventory-{before,after}.json`
- `logs/sha-*.txt` (copy verification: runtime 4316 files and bundle 69 files match their sources byte for byte; native and corpus SHAs below), `logs/copy.log`, `logs/verify-copies.log`
- The big copies (runtime, bundle, end-inputs, repository) were deleted after the run; see `logs/cleanup.log`.

## Generated evidence hashes (from commands, not typed)

```
# sha256sum (generated 2026-10-14T00:14:52Z)
c779345116c1bf6c0ab28af8751a36489642c5b9c870326f516361f54bf115f5  driver/k4s_end_preflight.py
b5224b99e58bed7f97d5f20efcb7dff418cb567b30e65603942e6884bebecc6a  driver/launch-argv.json
e06fddee91a438a0b5f65ba9228d4dc80bf67e61e5837b330702d9ec938ca984  driver/rocheck_driver.py
feb086fae4ebe8da555046a9c7e8359de1095999870b2b9614843e94acccb616  driver/inventory.py
ba6a0382f2e4ebaf88009e4397f30be6837b69c8f98325a50774b1488a402303  driver/analyze.py
3a044b7be3d7157c22850745aad7e5212a995458b409ac7fac57731d6c8d5d03  audit/sitecustomize.py
0d113f5bbfa418432fdfbe32b306323398acf2a1d8104c86d4106ee53b111016  run.sh
03ca280f00fb64a9380fbd679acba7458fbb7d18616613efe21585fc1c826f7f  logs/run.log
17b8e05630621e24831a16b740db28a8ac042d45e9986198a1b1bf92cb02afa1  logs/driver-steps.jsonl
c733fc135f5f572202a6b0920c78940754e69c5b4005de68b25a969cf0b4c2dd  logs/analysis.json
ae45f55b60967abc4a0458fe385c79e947ed47e25c7724b6ba329fbd4c72446d  logs/inventory-before.json
ae45f55b60967abc4a0458fe385c79e947ed47e25c7724b6ba329fbd4c72446d  logs/inventory-after.json
e226a0c74b90a01ddd317b314b94e702006adfd856341b6cb1f40fc8e4fbb49b  logs/env.txt
8ec46ff803c7b90c0df666a9c7a677e745af1262a07fddc87da6e48c483c3a7c  tracelog/audit-111142.jsonl
9f184cd0f5189fdc6716364d0c10b09d06c449a6d1b1967b07d46fbc16a8ae4a  tracelog/audit-111967.jsonl
a73caad90cf7cac7695fd5f9ecae30562298492b0ff3a87e956a366e34b52e36  tracelog/audit-234708.jsonl
# copy verification (input copies)
44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2  /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/base/end-inputs-r1/clasher_core.abi3.so
a97b1fbf6cbc33a7b65aa5fc91eb0acdd07c922aaf0737620a849163aaadbfe8  /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/base/end-inputs-r1/K4-states.pkl
# runtime/bundle copy listings
6a65c59c2e3ead716c8825afbd1778761645696e0a1361b282b35a81c16b092c  logs/sha-runtime-src.txt
6a65c59c2e3ead716c8825afbd1778761645696e0a1361b282b35a81c16b092c  logs/sha-runtime-copy.txt
9f76e83ff5d2254b370d6bf357393ad38ea99f872c297fbeeb1feac6f8f325a1  logs/sha-bundle-src.txt
9f76e83ff5d2254b370d6bf357393ad38ea99f872c297fbeeb1feac6f8f325a1  logs/sha-bundle-copy.txt
# bundle tiers-pins.json (copy)
5082e8b21f687c7e92af9e93ed5c1b0c21e9af858ad3ab90955ed49e07fd1b03  ./tiers-pins.json
```
