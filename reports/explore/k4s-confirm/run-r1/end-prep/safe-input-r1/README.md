# safe_input r1: the shared gate for PREREG-K4S END tooling (ruling P2-1)

**Status: CANDIDATE, not reviewed.** It needs a Sol review before any component adopts it. It is offline only and touches no host. Built on 127x05, 2026-10-12.

`safe_input.py` is the one layer that every local and remote read, write and subprocess in S1b, S2, S3, S4, S5, S6, S7, S9 and S10 should go through. It was built from the BLOCKING and HIGH findings of `SOL-REVIEW-END-PKG2-r1.md` and `SOL-REVIEW-END-PKG1-r2.md`, and from coordinator rulings E1–E4 (16:55Z, 17:12Z), R6/R7 (17:23Z) and P2-1 to P2-3 (17:30Z). [ADOPTION.md](ADOPTION.md) maps each component call to its replacement.

| File | Purpose |
|---|---|
| `safe_input.py` | The layer: stdlib only, Python 3.8+, Linux. A library, plus a small CLI for host shell wrappers. |
| `tests/conftest.py` | Loads the module under test (or a mutant). Provides a syscall recorder (`os.open`/`stat`/`lstat`/`read`/`listdir`/`readlink`, with the target inode resolved before each open attempt), an audit hook, and the canary helpers. |
| `tests/test_*.py` | 246 tests (`test_names_policy`, `test_reads`, `test_canaries_exemptions`, `test_writes`, `test_subprocess`, `test_git`, `test_remote`, `test_cli_publish_ps`). |
| `tests/mutate.py` | The mutation driver (not a pytest module). |
| `MUTATION-RESULTS-py38-O.json`, `MUTATION-RESULTS-py312-O.json` | Mutation results, per interpreter. |
| `ADOPTION.md` | Which call in each component is replaced by which `safe_input` call. |
| `SHA256SUMS` | SHA-256 of every file above. |

## Guarantees and their order

Every check is an explicit `raise Refusal(code, reason)`, never an `assert`, so all of them hold under `python -O`. `Refusal.code` is a stable class:

| Code | Meaning |
|---|---|
| `path` | Malformed path. |
| `name` | Forbidden name. |
| `allowlist` | The name is not declared by the role. |
| `policy` | Policy misuse or an unknown role. |
| `root` | The root is not canonical. |
| `symlink` / `not-dir` / `missing` / `not-regular` | What the walk found. |
| `nlink` | Hard-linked file. |
| `size` | Size cap or expected size. |
| `changed` | The object changed between check and open. |
| `growth` / `shrink` | The file changed size during the read. |
| `sha` | Expected SHA-256 mismatch. |
| `exemption` | E1/E4 violation. |
| `exists` | No-clobber refusal. |
| `subprocess` | Nonzero rc, timeout, bound exceeded or malformed output. |
| `remote`, `remote-refused`, `host`, `request`, `json`, `state` | Remote, request, JSON and object-state failures. |

1. **Policy and roles, with no defaults.** `Policy(host, [Role(...)], remote=False)`. Each `Role(name, root, access, max_size, exact=(), patterns=(), exemptions=(), grants=())` must declare:
   - an absolute normalized root;
   - access, either `read` or `write`;
   - a positive `max_size`;
   - at least one exact name or pattern.

   Patterns are matched component by component with `fnmatchcase`: `*` never crosses `/`, and `**` is a whole component meaning zero or more components. An unknown role, host, exemption or grant refuses. A local Policy refuses unless `os.uname().nodename` is `host`. Role roots are name-gated when the Policy is built. Roles are immutable.

2. **Names before any syscall** (`name_gate`). The full absolute path (root + relative path) is refused if any component, compared casefolded, is one of:
   - `games` or `hub-blocks`, or a `.x` / `.name` variant;
   - an outcome leaf name, in any component: `complete.json`, `local-complete.json`, `end-complete.json`, `interference.json`, `hub-ack.json`, `hub-ack.returned.json`, `end-raw.json`, plus the `name.*` and `.name*` temp variants such as `complete.json.tmp` and `.complete.json.swp`;
   - a K4S reporting job, `k4s-confirm-*`;
   - a live guard job, `k4s-end-guard-*`;
   - the strict END pair: consecutive components `k4s-confirm`/`end`, anywhere.

   It is also refused if it lies under:
   - one of the five FROZEN-T1 launch namespaces (copied from S4 r3b `T1_LAUNCH_NAMESPACES`);
   - `/mpac/sdicks02/repos/clasher-v4-cache`, on any host;
   - `/mpac/sdicks02/jobs`, on 127x04. This is the perception storage; it is the same prefix S1/S1b use, and stricter than `/mpac/sdicks02/jobs/clasher`.

   Only three grants exist, each lifting exactly one namespace rule:
   - `reporting-job-exact` lifts `k4s-confirm-*`, for exact names only;
   - `end-json-exact` lifts the END pair, for exact `.json` names strictly inside it; a role root can never be inside `end/`;
   - `guard-job` lifts `k4s-end-guard-*`.

   Outcome names, T1 namespaces and the perception and cache roots can never be granted. The role allowlist is checked after the names. Tests prove that no `open`, `stat`, `lstat` or `listdir` happens before a name, allowlist or path refusal.

3. **Walk** (`open_root`, `open_dirs`).
   - The root must satisfy `realpath(root) == root`, and every ancestor and the root itself are lstat'ed (no symlink, all directories).
   - The root is then opened component by component from `/` with `O_DIRECTORY|O_NOFOLLOW`.
   - Each relative component is `fstatat`'ed with no-follow (a symlink refuses as `symlink`, a non-directory as `not-dir`), then `openat`'ed with `O_DIRECTORY|O_NOFOLLOW`. Its fstat must be the same dev/ino, otherwise `changed`. On Linux, `O_DIRECTORY|O_NOFOLLOW` on a symlink gives ENOTDIR; it is re-classified as `symlink`.

4. **Descriptor gate** (`open_leaf`), before any byte is read.
   - `fstatat` without opening. A symlink, FIFO, socket, device or directory refuses (so devices and FIFOs are never opened), as does `st_nlink != 1` or size above the cap or the expected size.
   - Then `openat` with `O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_NOCTTY|O_CLOEXEC`.
   - Then `fstat` must show a regular file, the same dev/ino, `st_nlink == 1` and a size within the cap.

5. **Reads** (`Input`, `read_bytes`, `sha256_input`, `read_json`, `copy_input`).
   - Exactly `st_size` bytes are read from the gated fd. A short read refuses as `shrink`. One extra byte, or a different final `fstat` size, refuses as `growth`.
   - The optional `expected_sha256` is checked before any bytes are returned.
   - `read_json` takes a mandatory size cap (the smaller of the role cap and the argument) and decodes strict UTF-8. Duplicate keys and NaN/±Infinity refuse.
   - An `Input` is single-use.
   - `walk_tree` is a confined recursive inventory. Names are gated before each entry is lstat'ed or entered. A forbidden name, symlink, special file, hard link, oversize file or undeclared file refuses the whole walk; nothing is pruned. It reads no file contents.

6. **E1 and E4 are exact data, not patterns.**
   - **E1:** only the root-level `visualize_battle.py` symlink, with link text exactly `examples/visualize_battle.py`. `check_e1` validates it with `readlinkat`, without following, and gates the target as a normal input. The alias is never opened. `walk_tree` accepts E1 only at the root and only when its target is present.
   - **E4:** the four `complete.json` path and SHA pairs from the 17:12Z ruling, E2 first. `hash_e4`, `copy_e4` and `git_hash_e4` return `{path, sha256, size}` and never return bytes to the caller. Every other `complete.json`, and any E4 path through the ordinary read API, refuses.

7. **Writes** (`Writer`).
   - The root is opened canonically, and the parent of each target is walked component-wise from the held root fd.
   - Writes use `mkdirat`, or `O_CREAT|O_EXCL|O_NOFOLLOW` via dirfd. Nothing is ever truncated or replaced.
   - File and directory are fsynced, and the mode is set by `fchmod`.
   - `publish_excl(tmp, final)` replaces `tmp` + `mv`. It does `linkat`, which fails if `final` exists in any form, then unlinks `tmp`. `tmp` must be regular with `st_nlink == 1`.
   - `write_refusal_receipt` writes `<COMPONENT>-REFUSAL-<utc>-<pid>-<hex>.json` exclusively into a declared refusal role.
   - `create_e1_symlink` is the only symlink this layer creates.
   - Partial files on failure are kept, never unlinked.

8. **Subprocess** (`run_checked`).
   - The argv must be explicit, with an absolute normalized `argv[0]`; there is never a shell. The environment is exactly `env`, plus the `env_allow` names.
   - stdout and stderr are bounded; going over kills and refuses.
   - A watchdog kills the whole process group at the timeout. If a descendant still holds the pipes `LINGER_GRACE` (5 s) after the child exits, the call refuses.
   - The rc must be in `ok_rcs` (default 0) before the caller can see stdout. A failed stdin feed refuses.
   - `hostname_checked`, `ps_checked(fields=...)` and `git_checked` require rc 0, so valid-looking stdout with a nonzero rc refuses. `ps_checked` also requires every line to parse and the table to contain this process with its real parent.
   - `git_*` run `git --no-optional-locks -C <canonical repo>` with a fixed environment: no system or global config, literal pathspecs, no prompts.

9. **Git through the gate.**
   - `git_ls_tree` parses `ls-tree -r -l -z` strictly.
   - `gate_git_tree` is pure and runs before any blob is read. Each entry is name-gated and allowlisted. The tree is refused on any symlink other than the exact E1 entry, a non-blob, a mode other than 100644/100755, an oversize blob, a duplicate path, or an unlisted `complete.json`.
   - `git_blob` (planned entries only), `git_hash_e4` and `git_export(e1_mode='symlink'|'copy')` check each blob against its object id.
   - `git_show_file` replaces `git show C:path`. The role root must be the repository, and names and the allowlist are checked before git runs. The entry must be exactly one regular blob within the cap.

10. **Remote reader.**
    - `remote_program_source()` is `_CORE` (the same gate code this module runs locally) plus a small main.
    - It runs on the host as `nice -n 19 /usr/bin/python3 -I -S - <hex request>`, with the program on ssh stdin. The ssh argv carries only `[A-Za-z0-9/-]` words.
    - The request is canonical JSON: `file` (hash, optional content up to 8 MiB in total, E4 hash-only), `dir` and `absent` items.
    - The program validates the request strictly and name-gates every item first. Only then does it check `nodename == host`, open and gate every item, and read the bytes. If any item refuses, no byte of any item is read.
    - It replies with one JSON line: rc 0 = ok, rc 3 = refusal, rc 4 = error.
    - `parse_remote_response` validates strictly against the exact request: rc, one line, exact key sets, request SHA, host, item order, `nlink == 1`, regular mode, cap and expected size, E4 pins, and content base64, size and SHA. `build_remote_request` runs every name and allowlist gate locally first, so a forbidden path is never sent. `remote_check` does one login.

11. **Constants: a single source of truth.**
    - `APPROVED_K4S_MANIFEST_SHA256 = 74314eda…6357`.
    - `END_BASES`: 03 `/mpac/sdicks02/jobs/clasher/k4s-end-r1`, 04 `/mpac/sdicks02/jobs-k4s/k4s-end-r1`.
    - `Q4_GUARD_PARENTS`, `GUARD_JOB_NAME` (`-rdRR-aNN` and `-pfNN`), `STRICT_END_DIR`, `E3_ADMISSIONS_DIR`, E1, E2, `E4_COMPLETE_JSON`, `SSH_OPTIONS`.
    - `constants_fingerprint()` = **`1a3a8508967667a0cb6a49d1042891f728249c7972b2d28cf7a76255e1b4572d`**. Adopters should pin this value.
    - `remote_program_sha256()` = **`5b15dfe7b5f754c971a466ecf382465ec0a6fd03303e0ed74d79f5bc9da8bea1`** for this candidate.

**CLI for host shell wrappers** (exit 0 = ok, 3 = refused with `REFUSE <code>: …` on stderr, 2 = usage):

```
python3 -I -S safe_input.py create-excl  --host H --root R --rel REL --max-size N [--grant G]... [--mode 0444]  < bytes
python3 -I -S safe_input.py mkdir-excl   --host H --root R --rel REL [--grant G]...
python3 -I -S safe_input.py publish-excl --host H --root R --rel TMP --final REL [--grant G]...
python3 -I -S safe_input.py remote-program-sha256
```

## Minimal use

```python
import safe_input as si
P = si.Policy("127x05", [
    si.Role("s1b-manifest", "/mpac/sdicks02/k4s-runner/run-r1/end-prep/s1b-out", "read", 16 << 20,
            exact=("s1b-admissions-manifest.json",)),
    si.Role("out", "/mpac/sdicks02/k4s-runner/run-r1/end-prep/s3-out", "write", 64 << 20, patterns=("**",)),
    si.Role("refusals", "/mpac/sdicks02/k4s-runner/run-r1/end-prep/s3-refusals", "write", 1 << 20,
            patterns=("S3-REFUSAL-*.json",)),
])
doc = si.read_json(P, "s1b-manifest", "s1b-admissions-manifest.json", 16 << 20)
with si.Writer(P, "out") as w:
    w.mkdir_excl("job")
    w.write_json_once("job/manifest.json", {"ok": True})
```

## Verification (run on 127x05, 2026-10-12; every number below is from this session)

Each command was run with `nice -n 19`, `PYTHONDONTWRITEBYTECODE=1`, `-B` and `-p no:cacheprovider`, normally and with `-O`. `/usr/bin/python3` and the e4v3 venv have no pytest. A pytest was installed into `/dev/shm` only, with `uv pip install --target`, and supplied with `PYTHONPATH`: 8.3.5 for 3.8 (pytest 9 needs 3.9 or later), and 9.1.1 for the e4v3 venv. No venv was modified.

```
nice -n 19 <python> -B [-O] -m pytest -q -p no:cacheprovider tests
```

| Interpreter | Normal | `-O` |
|---|---|---|
| `/usr/bin/python3` 3.8.10 (PYTHONPATH=/dev/shm pytest 8.3.5) | 246 passed | 246 passed (1 warning) |
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 (pytest 9.1.1) | 246 passed | 246 passed (1 warning) |
| `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` 3.12.12 (PYTHONPATH=/dev/shm pytest 9.1.1) | 246 passed | 246 passed (1 warning) |

Under `-O` the only warning is pytest's standard assertion-rewrite notice. The tests do not depend on assertion rewriting: they use an explicit `ok()` helper and `refusal(code, ...)`, which checks the exact refusal code.

**Mutation check:** `python -B -O tests/mutate.py`. Each mutant runs the whole suite (`-x`) against a copy in a fresh `/dev/shm` temp dir, which is removed afterwards. Every edit target must occur exactly once. KILLED means pytest exited 1. **139/139 killed under `/usr/bin/python3` 3.8.10 `-O`, and 139/139 under k4s-freeze 3.12.12 `-O`.** 136 were killed in the full campaign. The remaining three (R07, E09, Q04) first came back `INVALID(edit)`: their edit targets had stopped being unique after later code changes. I made the edit strings unique in `mutate.py`, then re-ran those three with `--only` against the same module and tests; all three were killed under both interpreters. An earlier campaign had found real gaps (N09, E09, E10, T03, T04, S04, S11, Q13, Q16, M08). Each was fixed with a stronger test or code before this final run. The details, including `first_run` for the three re-runs, are in `MUTATION-RESULTS-py38-O.json` and `MUTATION-RESULTS-py312-O.json`.

**Equivalent mutants, excluded from the list and covered by joint mutants.** Some checks are deliberately layered, so removing one layer alone changes no observable behavior:
- the extra-byte growth probe is redundant with the final `fstat` size check: R03 mutates the `fstat` check alone, and R02 removes both;
- `O_NOFOLLOW` on exclusive create is redundant with `O_EXCL`, because POSIX `O_CREAT|O_EXCL` fails on any existing name, including a symlink: X01 removes `O_EXCL`;
- the `rel.startswith('/')` check is redundant with the empty-component check.

`O_NOCTTY` is not mutation-tested. No tty device can be opened in a test, and devices are refused before any open anyway.

**What the tests cover:**
- every refusal path, each asserting the exact refusal code;
- inode canaries under every role shape: exact, pattern, deep, E1, E4, END-granted, reporting-job-granted, guard-granted and multi-exemption. A synthetic outcome-named canary (`canary-src/games/g1/complete.json`, mode 000) is hard-linked under an allowed name. Every read API, plus `hash_e4`, `walk_tree` and `check_e1`, must refuse with `nlink`. The recorder proves the canary inode was never opened (even as an attempt) or read, the audit hook shows no open of the alias, and the canary bytes are unchanged;
- symlinks at the root, at a root ancestor, at the leaf, and at each of the four components;
- FIFO, socket, directory and device (`/dev/null`, `/dev/zero`) leaves, refused without being opened;
- races injected between the check and the open: leaf replaced, leaf hard-linked, leaf grown, directory replaced, directory swapped to a symlink, leaf swapped to a symlink, and leaf swapped to a FIFO (must not block);
- growth and shrink during the read, including growth after the probe;
- exclusive create against a pre-existing file, a symlink, a dangling symlink and a hard link, with inode content checked unchanged;
- `run_checked` with rc 37 and valid stdout, overflow, timeout, a lingering descendant, an unread stdin, relative argv and the env allowlist;
- the remote program run locally under `/usr/bin/python3` 3.8.10 through a fake ssh shim that enforces `ControlMaster=no`, `ControlPath=none` and `StrictHostKeyChecking=yes`. No real ssh was ever invoked.

**The reviewer's probes, reproduced generically:**
- the hard-linked `argv.nul` truncation attempt (`test_hard_linked_argv_nul_probe`, and the CLI variant);
- the base symlink to a foreign launch dir (`test_base_symlink_foreign_launch_dir_probe`, and the remote `dir`/`absent` variants);
- failed `ps` with a valid table (`test_ps_checked`);
- a git export containing `games/` and an unlisted `complete.json` (`test_reviewer_probe_games_and_unlisted_complete_json`). A logging git wrapper proves no `cat-file` ran before the refusal.

**Write confinement.** The tests write only under pytest's `tmp_path` (tempfile's temp dir, `/tmp/pytest-of-sdicks02/`), and the mutation runs only under `/dev/shm/safe-input-mut-*`. Remote-program tests run `/usr/bin/python3 -I -S -` locally against tmp trees. No real outcome, game, `complete.json`, reducer or verifier output was opened. The E4 path strings appear only as constants, and the tests create synthetic files at those relative paths inside tmp. To exercise the happy path, the E4 pins are patched with `monkeypatch.setitem` in the tests, because synthetic bytes cannot match the real pins; the real pins are asserted separately. Nothing was committed or pushed, and no SSH was used.

## Residuals and open points (disclosed, not hidden)

1. **Accepted TOCTOU residual** (coordinator scope ruling, 2026-10-12 16:00Z).
   - **Caught:** replacement of a directory or leaf between its `fstatat` and its `openat`. The dev/ino re-check refuses it with `changed`, `O_NOFOLLOW` gives `symlink`, and `O_NONBLOCK` gives `not-regular`. Once a fd is held, renaming paths cannot redirect the read.
   - **Remaining:** another local actor can rewrite a file's bytes in place, without changing its size, after the gate and during the read. Unless an expected SHA is supplied, this is undetected. Likewise, anything a concurrent actor does to a path after this layer has finished using it is out of scope.

   Static aliases, hard links and forbidden locations are not residuals: they refuse.
2. **The name list is exactly the specification.** Look-alikes such as `main01-complete.json`, `tiers-complete.json` and `fits_*_complete.json` are not in the ruled family. Metadata only (`git ls-tree --name-only origin/main`, no contents read) shows **30 such tracked files**, including `reports/explore/mac-e4-session/tiers-session-r1/sealed/tiers-complete.json`. S9 decides whether a whole-tree export may carry them; I did not decide it.
3. **A whole-tree git export of origin/main refuses under this name list.** Two tracked files are named exactly `hub-ack.returned.json`, both under `reports/explore/k4s-confirm/run-r1/candidates-evidence/oa1/integration/evidence-oa1test4-127x0{3,4}/`. These are OA1 integration smoke evidence; I saw the names only and did not open them. `hub-ack.returned.json` is on the required refusal list and E4 covers `complete.json` only, so S9 `gate_git_tree` over the full tree refuses. **This needs a coordinator ruling:** either an exact path+SHA exemption like E4, or an S9 export restricted to runtime members. The layer does not decide.
4. **E1 representation conflict.** S9 r1 `export_commit` dereferences tracked symlinks into regular copies (T1 A5 precedent), while S4 r3b expects the root-level symlink in the runtime tree. `git_export` therefore takes an explicit `e1_mode` (`symlink` or `copy`). The coordinator or S4/S9 must pick one, and both must agree.
5. **Remote coverage is reading only.** S10's host-side `tar -x` and S6's shell redirections are covered only when they are adopted through the CLI or a Writer-based receiver (see ADOPTION.md). Until then, `tar` follows a pre-existing symlinked parent.
6. **The remote program trusts the grants in its request.** The request is built locally from a Policy (`build_remote_request`), and the program still applies every non-grantable rule itself.
7. **Policy host check.** `Policy` trusts `os.uname().nodename`. `hostname_checked` is available for an rc-checked cross-check.
8. **E4 pins live in a mutable module dict** (the tests patch them). Production code must never write them; `constants_fingerprint()` exposes any edit.
9. **Conservative behavior.** Casefolded name matching may refuse a legitimate `Games` directory, and `walk_tree` refuses instead of pruning. Both are deliberate fail-closed choices.
10. **Memory.** `git_export` holds one blob at a time in memory, bounded by the role's `max_size`. `run_checked` buffers output up to its bounds.
11. **Live behavior is unverified.** Nothing ran against the real 03/04 hosts, a real ssh session, real repositories at production commits, or real outcome files.
