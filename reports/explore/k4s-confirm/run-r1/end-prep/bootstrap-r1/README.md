# bootstrap-r1: the canonical K4S END bootstrap (END-FULL-F1)

CANDIDATE, needs Sol review. Offline only. Built and tested on 127x05, 2026-10-13.

This package fixes **END-FULL-F1** (SOL-REVIEW-END-FULL-r1, BLOCKING). It provides one stdlib bootstrap that every
K4S END component uses to read its pinned stdlib-loaded file before the shared layer exists. In S2/S4/S1b/S3/S9/S10
that file is the vendored `safe_input.py`. In the S5/S6/S7 shell wrappers it is the host tool. The package also has a
conformance kit that the other workers can reuse against their own entrypoints.

The fix is a complete normalized-path, name, and ancestor walk, plus regular-file, single-link, and size checks, all
done **before any byte is read**. Only then does it read, hash, and execute exactly the verified bytes. Nothing is
re-opened by pathname after hashing.

The vendored layer stays **safe_input r3**: `safe-input-r3/safe_input.py`, SHA-256
`806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00`, 133606 bytes, constants fingerprint `33f594ed…`.
Its reader program SHA-256 is `2d2f212d73b49176c53b1a03a621b64fbc6a8d4c15bd18051ac31f91016a6152`. Its receive
program SHA-256 is `39a92e9d55f9ffefba57bae453677bad7c834f7761283268b84e40bb2d1210b4`, which is the value those bytes
produce. The r3 README misprints it; see `safe-input-r3/README-ERRATUM-receive-sha.txt`. The conformance suite
asserts all three values through the bootstrap (`test_safe_input_loads_and_executes_through_the_bootstrap`).

## Files

| File | Role |
|---|---|
| `k4s_bootstrap_r1.py` | **Canonical Python snippet.** Paste it verbatim, BEGIN…END lines included. It is also importable as a module, which is how the tests load it. |
| `k4s_bootstrap_loader_r1.py` | **Canonical shell loader program.** It is the snippet above byte for byte, plus a small `main`. It is run as `python3 -I -S -c "$k4s_loader" …`. |
| `k4s_bootstrap_shell_r1.sh` | **Canonical shell fragment.** It embeds the loader in one single-quoted word. Paste it verbatim into the wrappers. |
| `build_shell_fragment.py` | Regenerates the fragment from the loader. A test checks that the delivered fragment equals its output. |
| `CANONICAL-READY` | Marker with the SHA-256 of the three canonical files. These files never change under this marker. |
| `tests/k4s_bootstrap_kit.py`, `tests/kit_harness.py` | **Conformance kit** (reusable). |
| `tests/test_bootstrap_conformance.py` | Tests the snippet in-process: every guard, the name-gate conformance, the execution semantics, and the text invariants. |
| `tests/test_kit_selftest.py` | Runs the kit against canonical entrypoints in all three modes. Its negative controls are the pre-r5 loader and the immutable S2/S4 r4b candidates; the kit must flag their canary consumption. |
| `tests/test_shell_loader.py` | Runs the shell form as real processes: every scenario, pass-through, verify-only, `sha256sum` never invoked, exclusive metadata creation, and the real S6 r2 host tool. |
| `mutate_bootstrap.py`, `mutate_adopter.py` | Mutation drivers for the canonical text and for an adopter's embedded copy. |
| `MUTATION-RESULTS-*.json` | Mutation results on the final bytes. |
| `PROGRESS.md` | Resumable work log. |

Canonical SHA-256 (also in `CANONICAL-READY`):

```
5611c6049b5495a6cec283bd57ee662bcb4601873fb0300ece32e27ed8da760b  k4s_bootstrap_r1.py         (8372 bytes)
378c2b138677d7c8077fb24d25baff7decc54cea3b723949d5cb73bc31cf8332  k4s_bootstrap_loader_r1.py  (9986 bytes)
1ed816fa777c3121454796d18977f68a19bf824e5bd0d9c45adfc91225333f77  k4s_bootstrap_shell_r1.sh   (10976 bytes)
```

## The contract (`k4s_bootstrap_read_verified` / `k4s_bootstrap_load`)

The bootstrap uses the stdlib only (`hashlib os re stat sys types linecache`). It runs on Python 3.8+ and Linux. It
contains no `assert`, so it holds under `-O`, and no single-quote character. The steps run in this order:

1. **Pins.** The SHA-256 must be 64 lowercase hex digits. The size must be an `int` (not a `bool`) in 1..16 MiB.
2. **Path form, with no system call.** The path must be absolute and already normalized:
   - not starting with `//`;
   - no trailing `/`;
   - `os.path.normpath(p) == p`;
   - no empty, `.` or `..` component;
   - no control character and no backslash.

   Nothing is canonicalized: `realpath` is never called. The default path is
   `k4s_bootstrap_default_path(__file__, leaf)`. It joins the leaf onto `__file__`'s directory and prefixes `getcwd()`
   only when `__file__` is relative. It never normalizes or resolves, so an alias stays visible and the walk refuses it.
3. **Name gate, with no system call.** Every component, ancestors and leaf alike, is casefolded and must not
   `fullmatch` any of `K4S_BOOTSTRAP_OUTCOME_FAMILIES` (with `re.S`). These are the literal regexes of safe_input
   r3's `OUTCOME_FAMILIES`: games, hub-blocks, complete-json, interference-json, hub-ack-json and end-raw-json. The
   tuple is asserted equal to `si.OUTCOME_FAMILIES`. On a corpus of more than 40 000 generated names, the bootstrap
   agrees with `si.outcome_family` on every name. The corpus covers case variants, Unicode casefold cases (`ſ`, `ẞ`,
   `K`, `İ`), embedded newlines and NUL, every family, and more than 5 000 positives and more than 5 000 negatives.
4. **Walk.** The bootstrap opens `/` with `O_RDONLY|O_DIRECTORY|O_CLOEXEC`. It opens each ancestor with
   `O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC, dir_fd=<parent fd>`, and `fstat` must report a directory. A symlink, a
   non-directory or a missing ancestor refuses. Every descriptor is closed on every path, and a test checks that
   `/proc/self/fd` shows no leak.
5. **Leaf, before any read.**
   - `os.stat(leaf, dir_fd=parent, follow_symlinks=False)` must report a regular file with `st_nlink == 1` and
     `st_size ==` the pinned size. A FIFO, directory, symlink, hard link or wrong size refuses **unopened**.
   - Only then is the leaf opened with `O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_NOCTTY|O_CLOEXEC, dir_fd=parent`.
   - `fstat` must show the same dev/ino, a regular file, `st_nlink == 1` and the pinned size. A replacement, a late
     hard link or growth between the inspection and the open refuses before any read.
6. **Read, hash, execute.**
   - Exactly the pinned size is read from **that** descriptor; a short read means the file shrank.
   - A one-byte probe must return EOF, or the file grew.
   - The bytes must hash to the pin.
   - `k4s_bootstrap_exec` compiles **those bytes** under the filename `<k4s-bootstrap sha256=… PATH>`. It seeds
     `linecache` with the verified lines, so a traceback, `inspect` or `linecache` never re-opens the path.
   - The code runs in a fresh `types.ModuleType(module_name)`. The module is registered in `sys.modules` before exec,
     as import does, and the previous entry is restored if exec raises.
   - The module gets `__file__ = path` and `__k4s_bootstrap__ = ("k4s-bootstrap-r1", path, sha256, size)`.
7. **Refusal.** Every refusal is `raise refusal("k4s bootstrap refused: <reason>: '<path>'")`. `refusal` is the
   caller's convention: an exception class such as `RuntimeError` (S2/S4) or `SystemExit` (end_prep_common), or a
   callable that returns the exception, such as `lambda m: HostRefusal("bootstrap", m)`.

## Adopting it in Python (S2, S4, end_prep_common, …)

Paste `k4s_bootstrap_r1.py` verbatim, from its BEGIN line through its END line, above any use of the layer. Keep the
pins **outside** the region, so the region stays byte-identical. Add a test asserting that the region's SHA-256 is
`5611c604…`. Example (S2 r5):

```python
SAFE_INPUT_FILE = "safe_input.py"
SAFE_INPUT_SHA256 = "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00"
SAFE_INPUT_SIZE = 133606
SAFE_INPUT_FINGERPRINT = "33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592"
SAFE_INPUT_MODULE = "_k4s_s2_safe_input_r3"

# ==== BEGIN K4S CANONICAL BOOTSTRAP r1 (...)       <- k4s_bootstrap_r1.py, verbatim
...
# ==== END K4S CANONICAL BOOTSTRAP r1 ====

def load_safe_input(path=None):
    path = k4s_bootstrap_default_path(__file__, SAFE_INPUT_FILE) if path is None else path
    module = k4s_bootstrap_load(path, SAFE_INPUT_SHA256, SAFE_INPUT_SIZE, SAFE_INPUT_MODULE, RuntimeError)
    if module.constants_fingerprint() != SAFE_INPUT_FINGERPRINT:
        raise RuntimeError("S2: safe_input constants fingerprint differs from the pinned r3 value")
    return module

si = load_safe_input()
```

For `end_prep_common` (`C:40–70`), replace the body of `_load_safe_input`'s open/fstat/read/hash/exec block with
`k4s_bootstrap_load(SAFE_INPUT_PATH, SAFE_INPUT_SHA256, 133606, "safe_input", SystemExit)`. The constants are
**not** changed. Note two points:

- `HERE = os.path.dirname(os.path.abspath(__file__))` normalizes lexically, so a `.`/`..` form of `__file__` would be
  hidden from the walk. Use `k4s_bootstrap_default_path(__file__, "safe_input.py")` instead.
- Keep the existing "already loaded" check and the fingerprint, reader and receive pins after the load; the receive
  pin is `39a92e9d…`.

## Adopting it in the shell wrappers (`k4s_end_exit_push.sh`, `k4s_preflight_push.sh`)

1. Next to `host_tool_sha=…`, add `host_tool_size=<byte count of the pinned k4s_end_host_tool.py>`. The S6 r2 host
   tool is 17234 bytes for SHA `cf192690…`; use the values of the tool actually shipped.
2. Delete `test -f "$host_tool" && test ! -L "$host_tool" || exit 90` and the `printf … | sha256sum --check …` line
   (`EW:38–39`, `PW:36–37`). Paste `k4s_bootstrap_shell_r1.sh` verbatim in their place.
3. Delete the old `tool() { "$python" -I -S "$host_tool" "$@"; }` line. The fragment defines `tool()`.

The fragment does three things:

- It defines `k4s_loader='<loader program>'`.
- It defines `tool() { "$python" -I -S -c "$k4s_loader" "$host_tool" "$host_tool_sha" "$host_tool_size" -- "$@"; }`.
- It runs `k4s_verify_host_tool || exit 90`, which is the same call with `--verify-only`: it checks and executes
  nothing.

Each `tool …` call re-walks, re-gates and re-hashes the host tool, then executes exactly the verified bytes as
`__main__` with `sys.argv = [host_tool, ARGS…]`. The interpreter never opens the tool by path, and nothing is hashed
by `sha256sum`. The loader refuses unless it runs under `-I -S`, and `-I` keeps the working directory off `sys.path`
for `-c`. It is compatible with the fleet's Python 3.8.

**Interactions:**

- **Exclusive metadata creation is preserved.** The loader never reads stdin and creates no file. A pipe such as
  `printf … | tool si -- create-excl …` reaches the tool unchanged, and the tool's own `O_CREAT|O_EXCL|O_NOFOLLOW`
  creation and exit status are untouched. `test_exclusive_metadata_creation_is_preserved` checks the piped bytes, an
  existing name (status 3) and a planted symlink (status 3, target unchanged), and that the loader created nothing.
  `test_verify_only_executes_nothing_and_leaves_stdin_unread` checks that the stdin offset stays at 0.
- **Status 90 is the loader's refusal.** It is the same status the wrappers already use for a bootstrap refusal.
  Because every `tool` call re-verifies, a tool changed after the initial verify makes that call return 90, and the
  changed bytes never run (`test_a_mid_run_tool_change_refuses_with_status_90`). In `tool frozen-exec -- "$@";
  measurement_exit=$?`, such a refusal would be recorded as END exit code 90 with `command_exited: true`. The wrapper
  owner should decide whether to tell the two apart, for example with a fresh `k4s_verify_host_tool` immediately
  before `frozen-exec`, or by treating 90 there as a bootstrap refusal. This is a concurrent-replacement case, which
  is the accepted residual; a static alias is caught by the initial verify.
- The real S6 r2 host tool runs unchanged under the loader. It loads its sibling `safe_input.py` from the `__file__`
  the loader sets, parses its argv, and reaches its live `os.uname` host gate, which refuses on 05 with its own
  convention (exit 3). Its usage path exits 2. See `test_real_s6_r2_host_tool_runs_as_main_under_the_loader`.
  `os.uname` cannot be faked without root, so a full create-excl run of the real tool is not exercised offline; the
  synthetic exclusive-create tool covers those semantics.
- The host tool's own `read_pinned` loads `safe_input.py` after the bootstrap. It is owned by the S5/S6/S7 worker and
  is not changed here. It checks `realpath(path) == path` before opening, so it already refuses ancestor aliases
  without reading.

## The conformance kit (`tests/k4s_bootstrap_kit.py`)

Describe an entrypoint once, then run every scenario:

```python
sys.path.append("<end-prep>/bootstrap-r1/tests")
from k4s_bootstrap_kit import Entrypoint, check_scenario, run_scenario
EP = Entrypoint("s3", files={"s3_guard_job.py": src, "end_prep_common.py": common, "safe_input.py": layer},
                entry="s3_guard_job.py", layer="safe_input.py", sha256=PIN, size=133606, argv=["--help"],
                refusal_regex=r"k4s bootstrap refused")          # mode="import", module_name=... also supported
@pytest.mark.parametrize("scenario", EP.scenarios())
def test_f1(tmp_path, scenario):
    check_scenario(run_scenario(EP, scenario, str(tmp_path)))
```

For a shell loader, use `mode="loader", loader_file=<k4s_bootstrap_loader_r1.py>`, with the tool as both `entry` and
`layer`. The harness then runs under `-I -S`, as the wrappers do. For the bash wrappers themselves, follow
`tests/test_shell_loader.py`: real processes, the kernel atime held through an `O_PATH` descriptor, and execution
markers.

**Scenarios:** every alias is substituted before the entrypoint starts.

| Scenario | What it sets up | Expected |
|---|---|---|
| `control` | Honest package. | Success. The layer inode is opened once and read exactly SIZE bytes, those bytes hash to the pin, and the bootstrapped module records (path, pin, size). |
| `swap-ok` | After hashing (at the `<k4s-bootstrap` compile), a same-size decoy is renamed over the layer path. | Success; the decoy is never opened and never runs. |
| `ancestor-symlink` | `real/alias -> synth/games/pkg`. | refuse-unread |
| `ancestor-symlink-high` | `real/up -> synth/games`. | refuse-unread |
| `ancestor-symlink-plain-target` | `real/alias -> synth/plain/pkg`: no outcome name anywhere, so only the walk can refuse. This scenario catches a `realpath`-based loader. | refuse-unread |
| `leaf-symlink`, `leaf-symlink-pinned-bytes` | The leaf links to a canary, or to an outside copy of the exact pinned bytes. | refuse-unread |
| `hard-link`, `hard-link-pinned-bytes` | The leaf is a hard link (nlink 2) of a canary, or of the pinned bytes. | refuse-unread |
| `wrong-size-larger`, `wrong-size-smaller` | The leaf is a different size. | refuse-unread |
| `same-size-mismatch` | Mismatching bytes of the pinned size at the true path. | refuse-after-hash: read once, exactly SIZE bytes from one descriptor, never executed. |
| `fifo-leaf`, `dir-leaf` | The leaf is a FIFO or a directory. | Refused and never opened. |
| `non-normalized-dotdot-alias` | `real/hop/../pkg`, where `hop -> synth/games/sub`. Lexically this is `real/pkg`; the kernel resolves it to `synth/games/pkg`. | refuse-unread |
| `non-normalized-dot`, `non-normalized-double-slash` | Pinned bytes, but a non-normalized path form. | refuse-unread |
| `outcome-named-ancestor:<name>` | A real directory with an outcome name, for each of `games`, `GAMES`, `Games.d`, `hub-blocks`, `Hub_Block`, `old.hubblocks`, `x-complete.json.d`, `Interference.JSON.old`, `hub.ack.json`, `END-RAW.json.bak` and `gameſ`. It holds the pinned bytes. | refuse-unread |

"refuse-unread" means the canary inode is never opened, zero bytes are read, its atime is unchanged and no marker
appears. Consumption is judged by three independent instruments:

1. **The harness recorders**, installed before the entrypoint runs. They wrap `os.open`, `os.read`, `os.pread`,
   `os.readv`, `os.preadv`, `os.fdopen`, `builtins.open`, `io.open` and `io.open_code`, and identify every descriptor
   by (dev, ino) against inodes the kit identified before the run. An `io` open of a watched inode counts as
   consumption.
2. **Kernel atime.** Watched regular files get atime 0 before the run. relatime then updates atime on any read. The
   kit holds an `O_PATH` descriptor, so a renamed-away inode can still be checked. The control asserts that the
   instrument sees the honest read.
3. **Execution markers.** Canary and decoy bytes create a marker file if they ever run.

ptrace and strace are unavailable on the fleet; none of the instruments depend on them.

**Sensitivity is proven.** `test_kit_flags_the_legacy_loader` runs the pre-r5 loader, and
`test_kit_reproduces_end_full_f1_on_the_r4b_candidates` runs the immutable S2/S4 r4b files, read from
`../s1s2-r4b` and `../b3-r4b` and skipped if absent. The kit reports their canary consumption: for r4b, all 133606
canary bytes are read through an ancestor alias.

## Verification (127x05; numbers from the final bytes in `SHA256SUMS`)

Every run used `nice -n 19 taskset -c 0-7`, `PYTHONDONTWRITEBYTECODE=1`, `-B` and `-p no:cacheprovider`, with
`--basetemp` below `/dev/shm/k4s-bootstrap-r1-w/`. Python 3.8 used pytest 8.3.5 from a scratch copy of an existing
`/dev/shm` `--target` directory, so there was no network. Each interpreter runs its own entrypoint subprocesses, with
`-O` when pytest runs under `-O`.

| Suite | 3.12.12 normal | 3.12.12 `-O` | 3.8.10 normal | 3.8.10 `-O` |
|---|---:|---:|---:|---:|
| `bootstrap-r1/tests` | **375 passed** | **375 passed** | **279 passed** | **279 passed** |
| `s1s2-r5/tests` (270 + 61 new) | **331 passed** | **331 passed** | **331 passed** | **331 passed** |
| `b3-r5` (461 + 61 new; real-Q6 deselected) | **522 passed, 2 desel.** | **522 passed, 2 desel.** | **522 passed, 2 desel.** | **522 passed, 2 desel.** |

On 3.12 the suite has more tests than on 3.8. The shell-loader tests are parametrized over the distinct interpreters
`{sys.executable, /usr/bin/python3}`, so a 3.12 run exercises both interpreters' loader processes, while a 3.8 run
exercises only 3.8.

**Mutation** (`MUTATION-RESULTS-*.json`):

- `mutate_bootstrap.py` runs on 3.12 and 3.8, both under `-O`. **66 mutants on each interpreter: 60 killed, 6
  survived, 0 invalid.** The 6 survivors are the 4 declared equivalents and the 2 NULL controls. Snippet, loader and fragment mutants are applied to a
  scratch copy, the fragment is regenerated, and the whole suite runs with `-x`.
- Every guard has a killed mutant.
- Four single mutants are declared equivalent, each with a killed JOINT:
  - removing the leading-`//` check;
  - removing the trailing-`/` check;
  - removing `normpath` (each is masked by `normpath` or the explicit component check);
  - removing the length compare (masked by the exact-size read loop plus the SHA).
- The two NULL controls survive.
- `mutate_adopter.py` applies the same snippet mutants, plus adopter glue mutants, to S2's and S4's embedded copies.
  See `s1s2-r5` and `b3-r5`.

## Residuals and design points for the reviewer

- **What the gate covers.** It implements the OUTCOME families only, exactly as required, and not the END-claim, job,
  T1 or perception namespace rules. The bootstrapped path is a code location, such as a vendored layer or a host tool
  under `<END base>/tools`. Those rules are host- and role-dependent policy, which the layer applies afterwards. A
  stricter bootstrap gate could also refuse legitimate tool locations, for example any future `END-JOB` naming.
- **The entry script itself** is opened by the interpreter (`python3 S2.py`). That is outside any Python bootstrap.
  The shell form avoids it entirely, because `-c` means no script path is opened.
- **Invocation form.** Python 3.12 turns `python ./x.py` into `__file__ == "/cwd/./x.py"`, which the walk refuses.
  Invoke entrypoints with a normalized absolute path, as all tests and runbooks do.
- **Residual: concurrent replacement.** The walk is descriptor-relative, so swapping an ancestor that is already
  open has no effect. A replacement of the leaf between inspection and open is caught by dev/ino. The only remaining
  residual is the accepted one: concurrent replacement by another local actor. A same-inode rewrite after the
  inspection is caught by the SHA. A post-hash path change cannot matter, because exactly the hashed bytes run.
- **Residual: mounts.** Bind mounts are not detectable by pathname or nlink checks. They remain part of the trusted
  single-operator mount assumption, as in safe_input r3.
- **Kit change after the marker.** After `CANONICAL-READY`, the kit gained one scenario,
  `ancestor-symlink-plain-target`. The canonical snippet, loader and fragment did not change. The kit is not covered
  by the marker; adopters should take the final kit.
