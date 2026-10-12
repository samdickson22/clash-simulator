# RESPONSE to SOL-REVIEW-END-PKG1-r2: S2 round-3 candidate

**Scope.** This answers the S2 section of `run-r1/reviews/SOL-REVIEW-END-PKG1-r2.md` (e347219d) under coordinator ruling ab171591 ("2026-10-12 16:55Z"). S4 is a separate package.

**S1 is APPROVED and unchanged.** `s1_copy_end_sources.py` is byte-identical to the reviewed r2 bytes, `b987ab9756dd05439f79bd924a0ce31df3c31b24b125a25d8d9cbba31d0fdc65` (verified with sha256sum after the copy and again at the end). `tests/test_s1.py` is unchanged too, and S1's 34 tests pass on the r3 `conftest.py`.

**References.**
- `S2:` = `s2_end_evidence.py` (r3);
- `G:` = `tests/test_s2_gate_profile.py` (new);
- `T2:` = `tests/test_s2.py`;
- `C:` = `tests/conftest.py`;
- `A:` = `tests/audit_run.py`.

Line numbers are those of the r3 bytes listed at the end.

**Verification (all offline, on 127x05, `nice -n 19`):**
- **Tests:** **221/221** normally and **221/221** under `-O`: 34 S1 + 53 `test_s2.py` + 134 `test_s2_gate_profile.py`. Interpreter: `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12.
- **Mutation check:** **53/53** targeted mutants of the r3 S2 bytes killed under `-O`; none survived and none was INVALID. The driver is `tests/mutate_s2.py` and the results are in `MUTATION-RESULTS-r3.json`.
- **Smoke:** on the END interpreter `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` (3.12.12), plus a production-mode run on real origin/main `d482ab3d`. See README, "Also verified this round".

## S2-R2-F1 (BLOCKING): auxiliary input reads permitted sealed END outcome paths

**Change: one shared outcome/strict-END location gate for every explicit input, before any content access.**

- **The gate.** `gate_paths` (S2:285-294) is used by **all three entrypoints** for **every** path on the command line:
  - `build` (S2:570-576): `--repository`, `--s1-manifest`, `--out`;
  - `validate` (S2:839-843): `--repository`, `--code-root`, `--s1-manifest`, `--profile-json`;
  - `diagnose-clock` (S2:1036-1041, 1056): `--s1-dest`, `--s1-manifest`, `--repository`;
  - `--result` is gated **first** in `main` (S2:1147), before `validate`/`diagnose` run. Nothing is written to an ungated result.

  It runs in two passes.
  1. **Pure, with no system call, over all paths first** (S2:287-292). `lexical` (S2:225-232) requires an absolute, normalised, safe-character path that `forbidden_reason` (S2:210-222) does not refuse. `forbidden_reason` refuses:
     - a `games`, `hub-blocks` or `end` component;
     - the outcome/END-receipt name family: `*complete*.json*`, `*interference*.json*`, `*end-raw*.json*`, `END-JOB*`, `END-FINAL*`, `attempt-*.json`;
     - `k4s-confirm-*` and `t1-*` job trees;
     - `/mpac/sdicks02/jobs` and `/mpac/sdicks02/jobs-k4s`.

     Then comes **confinement to the allowed root**, through `Roots` (S2:235-254):
     - checkouts: exactly `/mpac/sdicks02/repos/clasher`, or `/tmp/k4s-s2-<name>`;
     - S1 receipt/dest, profile and result: strictly below `/mpac/sdicks02/k4s-runner/run-r1/end-prep/`;
     - production `build --out`: exactly `<repository>/reports/explore/k4s-confirm/end-evidence.json` (S2:570).

     Then the **name rules**: the receipt must be `s1-copy-manifest.json` (S2:456-457); in s1-dest mode it must be `<dest>/s1-copy-manifest.json` (S2:1036); the profile must be `.json` (S2:460-461); outputs must not be authority-like (S2:464-466).
  2. **lstat walk** (S2:257-282). Every component from `/` is `lstat`-ed; nothing is resolved, and any symlink component is refused. Each ancestor must be a directory. The leaf must be a directory, a **regular non-empty file with `st_nlink == 1`**, or, for outputs, absent. The r2 `canonical_abs()`/`os.path.realpath` is gone: realpath would itself resolve aliases and stat their targets.
- **Content access** happens only through `read_gated` (S2:387-391) → `read_confined` → `open_confined` (S2:328-360):
  - each directory is opened `O_NOFOLLOW`;
  - the leaf is **lstat-ed through its parent descriptor before it is opened** (S2:340-344). A symlink, a non-regular file or nlink ≠ 1 is refused **unopened**. This also covers derived paths: work-tree artifacts, S1-dest copies, the evidence and the frozen closure;
  - the opened `(st_dev, st_ino)` must equal the pre-open lstat and the gated identity (S2:354-356).

  `open_dir` (S2:310-325) and `write_new` (S2:394-412) run `lexical` before their first descriptor. `repo_relative` (S2:299-307) applies the same `forbidden_reason` to every repo-relative role, closure and evidence path.
- **The r2 reproductions.**
  - **(1)** A valid profile at `reports/explore/k4s-confirm/end/end-raw.json` with the right SHA is now refused with "forbidden location" before any stat or open. git and the bootstrap never run (G:161, the first case; production form G:519).
  - **(2)** `load_s1(testing=False)` called **directly** on a production-schema receipt at that path is refused before any system call (G:680). Its new signature takes only a gated `(path, lstat)` (S2:512). Even when called directly with an ungated tuple, `open_dir`'s lexical gate refuses it first.
- **"Even when a later schema or SHA check would refuse."** The location refusal precedes every content check. G:692 uses canaries with a wrong SHA or invalid content: the error is the location refusal, never "SHA mismatch"/"schema", and the canary is never touched.
- **`load_s1` reading before the schema check.** Content must be read to see the schema. The location is now gated before that read. The receipt is then parsed strictly (`strict_json`, S2:415-427: no duplicate keys, no NaN/Infinity), and its rows are typed and host/phase-checked (S2:524-531) before use.

**Audited full-entrypoint controls (all under `-O` too).**

`tests/audit_run.py` now records:
- the audit-hook events (open, subprocess, listdir/scandir);
- **wrapped `os.stat`/`os.lstat`**, which have no audit event (A:43-49);
- **the `(dev, ino)` of every successful `os.open`/`io.open`** (A:52-66).

So a hard-link alias is caught by inode, whatever its name. `violations()` (G:98-120) fails on any event naming a canary location or any `forbidden_reason` location, any open of a canary inode, or any stat of a canary inode other than the lstat of the operator-named alias. That lstat is how the alias is detected; see README Residual 3.

| Control | Entrypoints | Tests |
|---|---|---|
| Profile canaries, 12 locations including the reproduction; mode 000 | validate | G:161 |
| S1-receipt canaries, 6 locations | validate | G:175 |
| S1-receipt canaries, 3 locations, plus `--out` in a forbidden directory | build | G:183 |
| Forbidden `--repository`, `--code-root`, `--result` | validate, diagnose-clock (repository) | G:199 |
| Forbidden `--s1-dest` trees | diagnose-clock (s1-dest) | G:235 |
| Receipt must be the dest's own | diagnose-clock (s1-dest) | G:245 |
| Outside the allowed root, never stat-ed | validate | G:252 |
| Relative / `..` / `//` / unsafe characters | validate | G:262 |
| Name rules | validate | G:271 |
| **Hard-linked** profile | validate | G:282 |
| **Hard-linked** S1 receipt | **build, validate, diagnose-clock** | G:293 |
| **Hard-linked** S1-dest copy, refused unopened | diagnose-clock | G:315 |
| **Hard-linked** work-tree artifact, refused unopened | validate | G:328 |
| **Symlinked** profile, leaf and ancestor | validate | G:342 |
| **Symlinked** S1 receipt | **build, validate, diagnose-clock** | G:359 |
| Symlinked checkout, code-root ancestor, s1-dest, result parent | validate, diagnose-clock | G:381 |
| Gate → open identity (replaced inode) | unit | G:406 |
| Lexical gate is pure, inside a syscall trap (G:425-457): 20 production-root cases, all-lexical-before-any-lstat, production `--out` rule, production validate | unit, production roots | G:482, 493, 514, 519 |
| Descriptor helpers lexical-first | unit | G:651 |
| Test root confined below `/tmp/` | unit | G:526 |
| Production refuses `K4S_S2_TEST_ROOT` and writes nothing outside its roots | validate | T2:266 |
| Positive controls: the same bytes pass at an allowed location; the happy path names no forbidden location | validate | G:129, 142 |

The existing exact artifact roles and no-follow checks are **kept**. The r2 controls (games/ item, wrong roles, leaf/ancestor work-tree symlinks, evidence and result symlinks) still pass (T2), and the regression mutants confirm them (below).

**Test mode cannot widen the boundary.** `K4S_S2_TEST_ROOT` (required in test mode, strictly below `/tmp/`, itself gated; S2:235-248) only replaces the allowed roots. `forbidden_reason`, the lstat walk, nlink and the name rules are identical in both modes. A production run with `K4S_S2_TEST_ROOT` set is refused (S2:240-241; T2:266). The test fixture sets it to pytest's base temp (C:29-34); production-mode tests drop it (C:37-39).

## S2-R2-F2 (REQUIRED, MEDIUM): malformed supplied profiles silently fell back to defaults

**Change.**

- **Exactly one profile source in every mode** (`load_profiles`, S2:811-831): `--profile-json` + `--profile-json-sha256`, or `--declared-default-profile`. Both, neither, or a SHA without the file are refused. In r2, test mode could omit both and default silently.
- **Strict parsing.** The S4 file is read through the gate and parsed by `strict_json`: duplicate keys and NaN/Infinity are refused. It must be an object holding **exactly** the counted hosts.
- **Field-by-field validation** of each host's value (`check_profile`, S2:787-808), against the frozen code:
  - a **non-empty object**, so `{}`, `null`, a list, a string, a number or a boolean is refused;
  - `host` equal to its key;
  - `reference_slot` the int `0`, as `fleet_end.py:193` (Amendment 1) and `fleet_profile.py:24-26` require;
  - `slot_count` the int `11`, as `fleet_profile.py:17-19` requires (console_rule false → compute.slots = 11);
  - `console_rule` the bool `false`, per `fleet_profile.py:15`;
  - `warmup_seconds` a finite int/float `>= 300`, per `fleet_profile.py:27`;
  - `perception` `"none"`, per `fleet_profile.py:27`;
  - no unknown fields. The only extras allowed are those S4 r2 writes into `reference_load_profile`: `plan`, `end_evidence`, `amendment` (non-empty strings; `amendment` is read by `fleet_end.py:138`) and `guard` (a non-empty object).

  Bool/float look-alikes (`False`, `0.0`, `11.0`, `"0"`, `"300"`) are refused by exact type.
- **No fallback.** The host loop uses `profiles[host]` (S2:899), and that value has already been validated. The declared default is built only on the explicit `--declared-default-profile` branch, and it goes through the same `check_profile` (S2:817-821).
- **`profile_source` is recorded correctly** (S2:821, 830-831, 925):
  - `s4-bundles` with `profile_json_path` (the gated path) and `profile_json_sha256`;
  - or `declared-default` with both `null`.

  The validated profile per host remains in `hosts[*].profile`. Profiles are validated right after the location gate, before git and the bootstrap (S2:844).

**Tests.**
- **The r2 reproductions**, `{}` per host and `null` per host, are refused through the full validate entrypoint. The result has no `profile_source` and no `hosts` (G:547, 584).
- 34 further malformed variants: wrong value types, a missing or extra host key, a top-level list, a host mismatch, an unknown field, each field's wrong value or type, wrongly typed extras, and each required field missing (G:547-591).
- Duplicate key, NaN, Infinity and invalid JSON (G:598).
- Both / neither / SHA-only / wrong SHA (G:604).
- Accepted `300.0` and `600`, with and without the S4 extras (G:619).
- Recorded sources (G:129, 142).
- Unit: `check_profile` never completes from defaults (G:632).

## Other S2 notes in the r2 review

- **R1 S2-F1, "the verified frozen verifier's subsequent rereads retain the disclosed check/open residual."** Unchanged and stated (README Residual 1).
- **R1 S2-F2, "fixed for the evidence artifact list; incomplete for the entire input boundary."** Completed by S2-R2-F1 above. Artifact leaves are now lstat-ed before they are opened (S2:340-344), so a hard-linked or symlinked work-tree artifact is refused unopened (G:328; T2 symlink tests).
- **R1 S2-F3.** Unchanged; it stays killed by the regression mutant (R2-finite-positive-mhz-off).
- **"Keep existing exact artifact roles and no-follow checks."** Kept. The regression mutants R2-exact-role-off and R2-worktree-confinement-off are killed.
- **"I did not rerun the runner's 23/23 or 33/33 mutation campaigns."** The r3 campaign is reproducible from the package:
  - `tests/mutate_s2.py` holds the exact snippet edits; each must occur once;
  - per-mutant scratch copies and `--basetemp`, under `-O`;
  - "killed" only on a pytest test failure (exit 1). Any other exit is reported as INVALID.

  It covers 28 F1 gates, 19 F2 rules (including **the r2 behaviour restored**, `profiles.get(host) or default` without the check) and 6 r2 regressions. **53/53 killed.**

  An earlier run reported 5 INVALID, which were **not** counted as kills. A syscall trap in the pure-lexical tests stayed active during pytest's failure reporting; it now restores before reporting (G:425-450), and all 53 are killed.
- **Exceptions E1/E2 (coordinator rulings).** S2 needs neither:
  - it reads no symlink (E1 concerns S4's `visualize_battle.py`);
  - it never reads the training receipt (E2). Every `*complete*.json*` name stays refused by S2's predicate.
- **"S3/S5 must explicitly reject that stamp."** The S2 analogue: a test-mode S2 run can only write the `…TEST-ONLY…` schemas with `test_mode: true`. Consumers of an S2 result must require the production schema. This is unchanged from r2 and stated in the README.

## Behaviour changes the operator must know (README updated)

1. **Production locations.**
   - `--repository`/`--code-root`: exactly the main checkout or `/tmp/k4s-s2-<name>`.
   - `--s1-manifest`, `--s1-dest`, `--profile-json`, `--result`: strictly below `run-r1/end-prep/`.
   - `build --out`: exactly the evidence path inside `--repository`.

   The README run block already uses these forms; the r3 production smoke on `d482ab3d` exercised them.
2. **Naming.** The S1 receipt must be named `s1-copy-manifest.json`, which is what S1 writes. In `diagnose-clock --s1-dest`, it must be the dest's own receipt.
3. **Profile choice.** Exactly one profile source, also in test mode.
4. **Refusals without a result file.** A refusal that occurs before a result location is gated (a mode/flag error, or an unsafe `--result`) is reported on stderr with exit 2, and **no result file is written anywhere**. In r2, it was written to the ungated path.
5. **Symlink messages.** A leaf symlink is now refused by the pre-open lstat ("symlink (alias), refused unopened"), not by ELOOP.

## Not done / not verified

- There was no live run, no host access and no ssh. S2 has not run on real mhz/census, because none is committed.
- No real S4 bundle profile has been fed to S2, because S4 r3 does not exist yet. The extras list follows S4 r2. Any new S4 profile field is refused, fail-closed, until it is added and reviewed.
- The location predicate is name-based plus root confinement (README Residual 4). Mount aliases are still not detectable (Residual 2).

## Files (r3 bytes)

| File | SHA-256 | vs r2 |
|---|---|---|
| `s1_copy_end_sources.py` | `b987ab9756dd05439f79bd924a0ce31df3c31b24b125a25d8d9cbba31d0fdc65` | unchanged |
| `s2_end_evidence.py` | `973a5ace14fd78afd39f162320a7633e8cd18206be53102679778db12dcdc19f` | changed |
| `README.md` | `95ee842825abecbf23d9af42b833ca0c154bb0c4bd240cb5c168f7a6abecbf84` | changed |
| `RESPONSE-r1.md` | `a90f3c2deee8ac420c112311e4a5ab2a5fac7fe98a25437d153b785feb2a7a8d` | unchanged |
| `MUTATION-RESULTS-r3.json` | `b24e10466cc0942a4aeccb503593249b8577dcbf965927003128b51da9fe25a0` | new |
| `tests/audit_run.py` | `1df571d5e986b11c445a80a51cd7fd06bc5d0ab4f3fd6bf45bd40d42cf13e977` | changed |
| `tests/conftest.py` | `3ce31ab08b2da5754361f23f688840df9fe37ef48ce1029bfd79776d124a98ce` | changed |
| `tests/test_s1.py` | `ab538d966c530f83529551c4be738c1ab697d1232d0f7b4a2614691413f65adf` | unchanged |
| `tests/test_s2.py` | `b7d57ca3ca6110c0e8ae74a091beb03f8d7dfbcc611d4204fdfc348eab272d25` | changed |
| `tests/test_s2_gate_profile.py` | `4367e713d9878ef3b0d730bdb7f5b292828a9b39b8fdc504e074baf7965b02cd` | new |
| `tests/mutate_s2.py` | `8d6bace3de417d189e0f4fea6d7cb344af640e33bb5842f11c2256db6366c729` | new |

`RESPONSE-r2.md` (this file) is new; its SHA-256 is reported alongside the package, as a file cannot contain its own hash.
