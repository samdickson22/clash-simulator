# RESPONSE to SOL-REVIEW-END-PKG1-r1: S1/S2 round-2 candidates

**Scope.** This response covers S1 and S2 only; S4 is a separate package. Every finding below maps to its change. S1 references are to `s1_copy_end_sources.py` (= `S1`), S2 references to `s2_end_evidence.py` (= `S2`), and tests to `tests/test_s1.py` (= `T1`) and `tests/test_s2.py` (= `T2`). Line numbers are those of the r2 bytes listed in the final SHA list.

**Coordinator ruling.** Replacement between a check and the following open (TOCTOU) is an accepted residual on these single-operator hosts, as in X4S-3; it is stated in README "Residuals". Everything else in the review is addressed.

**Verification.**
- **Tests:** 86/86 normally and 86/86 under `-O`, with `/mpac/sdicks02/venvs/k4s-freeze/bin/python`.
- **Mutation check:** 23/23 targeted mutants killed under `-O` (scratch `/tmp/s1s2r2-mut/`). This includes the review's 3 survivors.

## S1

### S1-F1 (blocking): remote rejection came after forbidden reads; directory aliases were accepted

**Change.** The remote `stat`/`sha256sum`/`cat` are replaced by one read-only program, `REMOTE_PROGRAM` (S1:132-206), run as `/usr/bin/python3 -I -S` under `nice -n 19`. Its arguments are the literal paths only (S1:430-450).

- `opened()` (S1:142-161) opens from `/`, one component at a time:
  - each directory with `O_DIRECTORY|O_NOFOLLOW`;
  - the leaf with `O_NOFOLLOW|O_NONBLOCK`.

  A symlinked leaf **or ancestor** therefore fails (ELOOP/ENOTDIR) and is never resolved.
- On the descriptor, still before any read, it requires `S_ISREG` and `st_nlink == 1` (no hard-link alias).
- Pass 1 (S1:175-193) opens and gates **all** files, type and size included, before pass 2 (S1:194-205) reads any byte. Pass 2 reads the gated descriptor itself.

**Tests.**
- leaf symlink into `games/`: ELOOP; the target is mode 000, so following it would have given EACCES (T1:208);
- **phase-directory alias into 04's `/mpac/sdicks02/jobs/clasher/` tree:** refused at that component; no C login (T1:220);
- namespace ancestor symlink (T1:235);
- hard link (T1:245);
- FIFO, which does not block (T1:253);
- missing file (T1:202).

**Mutation check.** Removing no-follow, nlink or `S_ISREG` each gets killed.

### S1-F2 (blocking): local ancestor aliases were accepted; receipts were opened with `open(..., "w")`

**Change.** `Destination` (S1:330-366):
- `--dest` must be:
  - normalised and absolute;
  - canonical: `realpath == path` (S1:249);
  - **strictly below** the fixed `DEST_ROOT` (S1:72);
  - non-existent.
- Every component is opened `O_NOFOLLOW` from `/` (`open_dir`, S1:257). This is validated before any login, and the parent descriptor is retained.
- dest is created with `mkdirat` (S1:342). Every subdirectory, copy, manifest and refusal file is then created **relative to the retained descriptors** with `O_CREAT|O_EXCL|O_NOFOLLOW` (S1:125, 290-311). Nothing is ever opened with `"w"`.
- The final listing goes through the descriptor (`fwalk`, no follow) and refuses symlinks, special files or nlink ≠ 1 (S1:355-366).

**Tests.**
- a dest below a symlinked ancestor is refused, and the alias target is untouched (T1:344);
- a dest outside the root (T1:354);
- an existing dest (T1:336);
- output substitution: `write_exclusive` refuses a planted symlink and an existing file, both left intact (T1:386).

**Mutation check.** Removing no-follow + canonical, or `O_EXCL`, gets killed.

### S1-F3 (blocking): the cap came after hashing; streaming was unbounded; launch/exit were exempt

**Size gate before any hash or read**, enforced remotely in pass 1:
- **launch.json / supervisor-exit.json:** the size must equal the **committed phase-meta size** exactly (S1:182). The committed sizes are taken from `git show` and checked to be 1..95 MiB (S1:402-406).
- **mhz.jsonl / census.jsonl:** 1..95 MiB (S1:184; the stream mode cap is at S1:188).

**Finding: the 95 MiB cap now applies to all four files.** The committed phase-meta sizes on origin/main are:
- launch.json: 346–350 B;
- supervisor-exit.json: 36,487 – 1,045,522 B (largest: `127x04-reporting`).

No launch or exit file is legitimately larger than 95 MiB, so none needs an exemption. In fact the rule for these two is stricter than the cap: equal to the committed size.

**Bounded stream.**
- C re-opens and re-gates all 10 files, requiring size, `st_dev` and `st_ino` == P, and refuses **before writing one byte** if any changed (S1:186-193).
- Each file is streamed for exactly its size from the gated descriptor, then EOF is required (S1:162-173).
- 05 reads **exactly the sum of the P sizes** straight into exclusive per-file outputs, then reads one more byte: any excess byte kills the login and refuses (`Session.stream`, S1:503-546; excess check at S1:535).
- P/V output is capped at 64 KiB (S1:122, 492). stderr keeps only a 4 KiB tail. The timeouts are hard kills (S1:489, 507).

**Preserved from r1.** Per-piece SHA and re-read (S1:543-546), the remote-rc refusal, and V's comparison, which now includes device/inode (S1:627-631).

**Tests.**
- oversize on 03 and on 04 (T1:154, 163);
- a **64 GiB sparse census is never hashed**: refused in seconds (T1:171);
- empty source (T1:196);
- launch size mismatch refused remotely (T1:129);
- same-size launch/exit SHA mismatch (T1:136, 145);
- **growth** between P and C, and **same-bytes replacement** (new inode), both refused before streaming, with no partial files (T1:270, 278);
- excess bytes (T1:286);
- **256 MiB flood**: local files equal the inspected sizes, and the writer was stopped rather than drained (T1:292);
- **same-length corruption** (T1:311);
- **valid stream with rc 37** (T1:317);
- unit test: the remote cap literal == `MAX_BYTES` (T1:184).

**Mutation check.** Removing the max gate, the exact gate, the stream identity check, the excess check, both piece comparisons (r1 survivor) or the rc check each gets killed.

### S1-F4 (required): early refusals had no receipt

**Change.** There is a fixed, documented `REFUSAL_DIR = /mpac/sdicks02/k4s-runner/run-r1/end-prep/s1-refusals` (S1:73). `write_refusal` (S1:660-690) writes `S1-REFUSAL-<utc>-<pid>-<random>.json` there for **every** refusal or failure, exclusive and no-follow. The directory must be canonical and is created if missing.

- If this run created dest, a copy also goes to `<dest>/S1-REFUSAL.json`.
- `main` wraps argument parsing: `Parser.error` raises a refusal (S1:693-696). The repository, commit, window, dest, ssh and P-stage checks all sit inside the same handler (S1:698-721).
- If `REFUSAL_DIR` is aliased, nothing is written anywhere. The script prints `RECEIPT NOT WRITTEN` and still exits 2.
- No success manifest is ever written on failure. Partial copies are kept and listed in `partial_files`.

**Tests** (the receipt is asserted on every refusal test):
- missing window (T1:330);
- existing dest (T1:336);
- argument error (T1:361);
- invalid commit (T1:368);
- P failure (T1:324);
- symlinked refusal dir is never written (T1:376);
- partial copy kept (T1:261).

**Mutation check.** Removing the receipt write gets killed.

### Other S1 points in the review

- **Surviving mutant: per-piece/local-rehash comparisons.** Now killed by T1:311.
- **Valid output with remote rc 37.** Covered (T1:317).
- **Command-level exactness** is kept: fixed hosts, `shlex.quote`, the path alphabet, the 04 `/mpac/sdicks02/jobs/` exclusion (S1:418-428). T1:67 now parses every remote command and checks:
  - the fixed prefix;
  - that the program is exactly `REMOTE_PROGRAM`;
  - that every operand is an allowed name in that host's phase directory.

  The manifest records `remote_program_sha256`.
- **Production ssh.** Production requires `ssh` to resolve to `/usr/bin/ssh` (S1:613; T1:413). That way the PATH shim used by the tests cannot be the production transport.
- **Test mode is separable.** It requires `K4S_S1_TEST_MODE=SYNTHETIC-NOT-FOR-PRODUCTION`; any other value is refused (S1:234-246). It adds the TEST-ONLY schemas to the manifest and receipts, and S2 refuses those schemas in production.

## S2

### S2-F1 (critical/blocking): unverified code ran and performed its own verification

**Change.** The stdlib-only `bootstrap` (S2:513-551) runs before any frozen import:

1. It reads the raw `mac/K4S-MAC-MANIFEST.json` from the code root no-follow (`read_confined`, S2:219-263) and requires the **fixed** `APPROVED_K4S_MANIFEST_SHA256 = 74314eda…` (S2:84). There is no CLI override.
2. It verifies every pin set the frozen `load_k4s_manifest(..., require_frozen=True)` verifies: `k4s_files`, `end_files`, `reused_readonly` and the kernel files. It also checks the measure_tiers statement, the native provenance (S2:85), `frozen`, and that the SD1 and kernel pins are filled. That is 32 files.
3. It keeps the **verified bytes** of the five modules S2 executes (`SERVED`, S2:88-93).

Then:
- `ClosureFinder` / `VerifiedLoader` (S2:461-502) execute those modules **from exactly the hashed bytes**, with no re-open and no `.pyc`.
- Any other import that does not resolve to the interpreter's stdlib is refused with `ImportError`. That covers site-packages, and any repository or code-root file even after frozen `end_evidence` puts its directories on `sys.path`.
- The import-origin checks are retained (S2:559-562).
- The **verified** frozen `load_k4s_manifest` runs afterwards as a second opinion (S2:563-565).
- A closure audit at the end requires every module loaded after the bootstrap to be stdlib or served (S2:569-581).

**Test-only facilities.** `--no-manifest-check` and every record or expectation override can be used only with **both** `--test-mode` and `K4S_S2_TEST_MODE=SYNTHETIC-NOT-FOR-PRODUCTION`. Either one alone is refused, and so is a wrong marker (`Mode`, S2:298-318). A test-mode run can only write `…TEST-ONLY` schemas with `test_mode: true` (S2:706, 945-948). A production `ok:true` therefore needs the bootstrap.

**Tests.**
- **pre-import canary:** a top-level write appended to `end_evidence.py` never executes (T2:294);
- **modified verifier:** the review's reproduction, `verify_pinned = lambda …: None` plus a changed `fleet_end.py`, is refused at the K4S pin check; there is no `ok` and no `frozen_manifest_verified` (T2:305);
- modified helper (T2:317);
- modified manifest (T2:324);
- **symlinked frozen module** with identical bytes is refused with ELOOP (T2:331);
- `ClosureFinder` unit test: refuses a planted module and site-packages, allows the stdlib (T2:351);
- the mode separation (T2:227, 245, 259, 269);
- happy path: the served SHAs == the manifest pins (T2:87).

**Mutation check.** Skipping the bootstrap, or a permissive finder, gets killed.

### S2-F2 (blocking): validator paths were not the declared health-only paths

**Change.** Before any artifact read, validate (S2:618-705):

1. reads the evidence no-follow at its fixed path and checks its SHA (S2:636-637);
2. requires the completion item to be the completion of record. It reads the **pinned** completion via `git show` and checks its SHA (S2:640-644, 353-357);
3. derives the exact role paths from the completion's `counted_host_phases` (S2:331-351). Each host and phase name must be a registered name; production requires exactly the 10 pairs;
4. runs `structure()` (S2:584-605). Every item must be **exactly its role's `repository_path`**, with `path` == that path relative to the evidence and commit X. The phase order must equal the completion's. `repo_relative()` (S2:178-186) rejects absolute paths, `..`, `.`, `games`, `complete.json`, `hub-blocks` and `end/`;
5. checks the record pins. In production, launch/exit == `EXPECTED_META` (S2:657-659) and the **S1 receipt** binds all 40 items (S2:660-662, 359-397);
6. confines the work tree for every artifact (S2:663-665): a canonical repository root, every component `O_NOFOLLOW`, regular file, `st_nlink == 1`, non-empty. All of this happens before the frozen `end_evidence` reader opens anything.

`build` uses the same `role_paths` and pins (S2:399-453). The frozen committed-byte and ancestry checks remain as extra checks.

**Zero-forbidden-read controls**, using an audit hook (`tests/audit_run.py` records every `open`, `subprocess.Popen` and `listdir`/`scandir`):
- **allowlist on the happy path** (T2:115): every absolute open is stdlib, a code-root file, an exact role path, the evidence, the result or the S1 receipt; every `git show` names a role path; zero events touch `games`, `complete.json` or `hub-blocks`;
- **the review's games/ reproduction** is refused before any read (T2:373);
- items pointing into `end/registry/…`, at `…/complete.json`, at another phase's file or through `..` are refused before any read, including when validation would fail later (T2:390-407);
- a **work-tree leaf symlink into `games/`** is refused with ELOOP; the target is mode 000, and the frozen reader never opens the leaf (T2:410);
- an **ancestor symlink** is refused, and nothing below it is opened (T2:428);
- evidence symlink (T2:443);
- result symlink (T2:453);
- build output symlink (T2:190).

**Mutation check.** Removing the exact role check, or the work-tree confinement, gets killed.

### S2-F3 (required tests): MHz and launch/exit-mismatch controls

The MHz path keeps the frozen `host_reporting` join and the per-core finite-positive check (`mhz_preconditions`, S2:608-615).

**MHz tests:**
- **NaN, +inf, 0 and −1 MHz** in a full-occupancy row (T2:545-548);
- missing occupied core (T2:551);
- NaN in a non-full-occupancy row is not selected, consistent with frozen `compare_mhz` (T2:556);
- full-occupancy selection counts with mixed `inflight` (T2:565);
- insufficient full-occupancy (T2:574);
- census row with no MHz row, the kill between writes (T2:581);
- interior gap (T2:593);
- duplicate census utc (T2:599);
- MHz with no census row, and a slots mismatch (T2:606).

**Launch/exit mismatch with correct telemetry:**
- in validate, for both `launch.json` and `supervisor-exit.json` (T2:513);
- in build (T2:215);
- mhz/census mismatch in validate (T2:526). Validate now cross-checks launch/exit against the S1 receipt as well (S2:383-397, 660-662).

**Mutation check.** All three review survivors are killed: S1 piece comparisons, S2 finite-positive MHz, S2 S1 meta cross-check.

### "Production validation should use the verified S1 receipt and the final S4 profiles"

- In production, `--s1-manifest` + `--s1-manifest-sha256` are required for `build` and `validate`. The receipt must have the production schema, `status: copied`, an exact 20+20 row set, and verified rows (S2:359-381).
- Production validate requires either `--profile-json` + `--profile-json-sha256` (S4) or an explicit `--declared-default-profile`. The result records `profile_source` (S2:624-626, 666-672).
- README tells the operator to re-validate with the S4 profiles before the END-JOB.

## Census/MHz misalignment (review section, plus the coordinator's diagnostics request)

The frozen join is unchanged and its refusal is kept.

- **New `diagnose-clock` subcommand** (S2:722-876). It reads **only** `end-sources/<host>/<phase>/{census,mhz}.jsonl`, either via `git show X:` (plus the pinned completion for the phase list), or from an S1 destination tree read no-follow and checked against the S1 manifest's SHAs. It keeps only the health fields (utc/host/inflight; utc/slots/core count and finiteness).
- Per host/phase, it reports:
  - the counts;
  - unparseable lines;
  - duplicate and wrong-host census rows;
  - duplicate MHz utc values;
  - **MHz without census** (utc, line);
  - **census without MHz** (utc, line, position first/interior/last, and the neighbouring joined utc);
  - slot mismatches;
  - joined and full-occupancy rows;
  - non-finite full-occupancy MHz;
  - the **first frozen `host_reporting` rule that would refuse** (rule order of `fleet_end.py:204-221`).
- It never repairs, filters, re-times or zips rows (`repair: "none…"`). Exit 0 = clean, 3 = diagnosed mismatch.
- `validate` attaches the same `clock_diagnosis` for the failing host when frozen `host_reporting` refuses, and the frozen error message stands (S2:690-697).

**Tests:** T2:574-616 (via validate); T2:618 (repository mode, audited to the completion plus the 6 source paths, with no census counters output); T2:637 (clean S1-dest mode, and a copy that differs from its manifest).

**README note 5 is corrected** per the review: `supervise.py:109-117` uses one `progress['utc']` for both rows. Only an abrupt termination or I/O error between the two appends leaves an unmatched census row; SIGTERM/SIGINT only set `interrupted`. I re-read those lines on origin/main to confirm.

## Not addressed here (out of scope for S1/S2)

- S4-F1..F3 and the S4 `frozen_python()` `-O` note belong to the separate S4 package.
- Live `ReportingGuard`, seed lookups and model/native loading remain S3/S5 responsibilities, as the review states.
