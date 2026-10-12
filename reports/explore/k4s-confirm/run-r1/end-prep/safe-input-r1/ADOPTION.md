# ADOPTION: replacing each component's reads, writes and subprocesses with safe_input (P2-1)

**Status: CANDIDATE.** This document describes what each component must change. No component was edited.

Line numbers refer to the local copies under `/mpac/sdicks02/k4s-runner/run-r1/end-prep/`:

| Component | File (directory) |
|---|---|
| S1b | `s3s9s10-r1/s1b_copy_admissions.py` |
| S2 | `s1s2-r3/s2_end_evidence.py` (the local r3 working copy, not the r2 that Sol reviewed) |
| S3 | `s3s9s10-r1/s3_guard_job.py` and the shared `s3s9s10-r1/end_prep_common.py` ("common") |
| S4 | `b3-r3b/assemble_fleet_reference.py` |
| S5 | `s5s6s7-r1/k4s_end_preflight.py` |
| S6 | `s5s6s7-r1/k4s_end_verify_push.py`, `k4s_end_exit_push.sh`, `k4s_preflight_push.sh` |
| S7 | `s5s6s7-r1/k4s_end_launch_gate.py`, `k4s_end_launch_remote.py` |
| S9 | `s3s9s10-r1/s9_end_runtime.py` |
| S10 | `s3s9s10-r1/s10_stage_host.py` |

`si` means `safe_input`. "Role X" means a `si.Role` that the component must declare explicitly in its own `Policy`.

## 0. Rules that apply to every component

1. **Import a pinned copy.** Load `safe_input.py` from a fixed path and require its SHA-256 (`SHA256SUMS`) before using it. Then require `si.constants_fingerprint() == 1a3a8508967667a0cb6a49d1042891f728249c7972b2d28cf7a76255e1b4572d`.
   - **Host-run code** (the S5 preflight, the S6 wrappers, the S7 remote program, and the S10 receiver if adopted) must receive the same bytes: either committed into the runtime at evidence commit P, or concatenated verbatim into the shipped program. The host-side check is the same SHA.
   - Delete the component's own name lists and gate helpers, so that only one list exists. The components affected are:
     - S2 `forbidden_reason`/`lexical`/`lstat_walk`/`open_dir`/`open_confined`/`read_confined`/`write_new`/`strict_json` (`:210–425`);
     - S4 `outcome_free`/`no_t1_launch_namespace`/`end_namespace_free`/`location_free`/`walk`/`absolute`/`open_confined`/`sha_confined`/`read_confined`/`write_new`/`copy_verified` (`:225–349, :867–882`) and `OUTCOME_DIRS`/`OUTCOME_LEAVES`/`JOB_COMPONENT`/`T1_LAUNCH_NAMESPACES`/`E4_COMPLETE_JSON`/`E1_*` (`:83–99, :169–184`);
     - common `open_regular`/`read_bounded`/`sha_file`/`confined_new`/`write_new`/`run_bounded` (`:27–163`).
2. **One Policy per process, declared at the top of the component.** The Policy has an exact host, and each role has an exact root, access, cap and names. Never use `patterns=("**",)` on a root that can hold sealed data. Use exact names or narrow patterns.
3. **Every refusal must leave a receipt** through `si.write_refusal_receipt(writer, "<S#>", error, context)` into a declared refusal role. The component keeps its existing exit-status semantics.
4. **Every subprocess goes through `si.run_checked`** (or the `git_*`, `ps_checked` and `hostname_checked` helpers), with an absolute `argv[0]`:
   - `/usr/bin/git`, `/usr/bin/ssh`, `/usr/bin/ps`, `/usr/bin/hostname`;
   - an explicit timeout and output bounds;
   - `ok_rcs` stated explicitly whenever a nonzero rc is meaningful (for example `ssh -O check`, which must be nonzero).

   Remove every `subprocess.run(... capture_output=True)` that has no bounds.
5. **Every `git show C:path`** becomes `si.git_show_file(P, "<repo role>", repo, C, rel, max_size, expected_sha256)`. The role root must be the repository, and the role must list the exact paths. **Every whole-tree read** becomes `si.git_ls_tree` → `si.gate_git_tree` → `si.git_blob` / `si.git_hash_e4` / `si.git_export`.
6. **Coordinator decisions that block full adoption** (the layer does not take them):
   - **D1.** Two tracked files named `hub-ack.returned.json` are under `reports/explore/k4s-confirm/run-r1/candidates-evidence/oa1/integration/evidence-oa1test4-127x0{3,4}/`. They make `gate_git_tree` refuse the whole tree at origin/main. This needs either an exact path+SHA exemption or an S9 export limited to runtime members.
   - **D2.** The E1 representation in the runtime tree: S9 r1 dereferences it to a regular copy (`:378–388`), while S4 r3b requires a root-level symlink (`:228–234`, `walk(alias=...)`). `si.git_export` needs `e1_mode='copy'` or `'symlink'`; pick one for both components.
   - **D3.** S6 verifies the seal of the END measurement directory. That directory contains `end-raw.json` and `end-complete.json` (`end_reference.py:243,407`; `end_pool.py:70`; names only, not opened), so verification hashes them. The layer refuses those names under every role. S6 sealed-member hashing therefore needs an explicit hash-only ruling, analogous to E4 but bound to the seal's own per-file SHA, before S6 can adopt it.
   - **D4.** S10's host-side `tar -x` is not a safe_input write. The required replacement (a shipped stdlib receiver using `si.Writer`) is described under S10.

## S1b: copy admissions (Sol PKG2 S1b-F1)

| Lines | Current | Replace with |
|---|---|---|
| `:80–131` `READER` (no `st_nlink` check, `:118–122`) and `:206–210` `command`, `:212–214` `ssh_argv`, `:217–240` `parse`, `:267–270` `run_bounded` | Hand-rolled remote reader and header parser. | `si.remote_check(Pr, items, max_content=3<<20)`. `Pr = si.Policy(host, [Role("job", JOB_ROOTS[host], "read", 1<<20, exact=("k4s-confirm-replacement-r4/system-bus-admission.json", "k4s-confirm-replacement-r4/idle-services.json" [03 only], "k4s-confirm-replacement-r5"), grants=("reporting-job-exact",))], remote=True)`. The items are `{"kind":"file","content":True}` for each admission, plus `{"kind":"absent","rel":"k4s-confirm-replacement-r5"}` (the next-job probe, replacing `lexists`, `:94–106`). The remote program enforces regular file, `st_nlink == 1` and size before any read, and refuses every item if any one fails. This closes **S1b-F1**. On 04 the role root `/mpac/sdicks02/jobs-k4s` is outside the 04 perception prefix; the old `FORBIDDEN_PREFIXES` check (`:72`) is subsumed by `PERCEPTION_PREFIXES`. |
| `:195–197` `committed_latest` (`subprocess.run git show`) | Unbounded git with a status check. | `si.git_show_file(P, "repo", repo, commit, HISTORY, 16<<20)`. |
| `:254–255` `confined_new` + `mkdir`, `:276–290` `write_new` / `sha_file` | Common helpers. | `w = si.Writer(P, "s1b-out")` (root = `DEST_ROOT`), then `w.mkdir_excl(dest_name)`, `w.mkdir_excl(f"{dest}/{host}")`, `w.create_excl(f"{dest}/{host}/{name}", data)`. The returned SHA replaces the re-read at `:280,283`, or re-read with `si.sha256_input(P, "s1b-dest-read", ...)` if an independent re-read is wanted. Write the manifest with `w.write_json_once`. |
| `:292–293` `S1B-REFUSAL.json` | Common `write_new`. | `si.write_refusal_receipt(w, "S1B", error, {"logins": logins})` with `patterns=("S1B-REFUSAL-*.json",)`, plus a copy in dest through `w.create_excl`. |
| `:260` `shutil.which(a.ssh)` | PATH lookup. | A fixed `/usr/bin/ssh`, through `si.remote_check(..., ssh_binary=...)`. Test mode may pass a shim path, which the test-mode marker must gate. |

## S2: END evidence (Sol PKG1-r2 S2-R2-F1, F2)

r3 already contains much of this logic. Adoption deletes the duplicate and closes the gap that remains for the auxiliary inputs.

| Lines | Current | Replace with |
|---|---|---|
| `:210–222` `forbidden_reason`, `:225–233` `lexical` | A local name list. | `si.name_gate` runs inside every `si` call. Remove the list. |
| `:236–254` `Roots`, `:285–296` `gate_paths`, `:257–282` `lstat_walk` | Role roots and lstat walk. | A Policy with these roles: `checkout` (repository: MAIN_CHECKOUT, or the TMP_CHECKOUT regex expanded to one exact root per run); `s1-dest` (PREP_ROOT/<dest>, exact `"<host>/<phase>/{mhz,census}.jsonl"` and `s1-copy-manifest.json`); `profile` (exact profile JSON name); `out` (write, exact result name). **The S1 manifest and profile roles must not be rooted in or above `k4s-confirm/end`** (closes S2-R2-F1). Names are refused before any open. |
| `:310–360` `open_dir`/`open_confined`, `:363–392` `confined_size`/`read_confined`/`read_gated` | Descriptor gate. | `si.open_input(P, role, rel, expected_size)` / `si.read_bytes(...)`. The gated `(dev, ino)` identity is checked inside `si.open_leaf`. |
| `:516–518` `load_s1`, `:823–825` `load_profiles`, `:854–856` evidence | `read_gated` + `strict_json`. | `si.read_json(P, "s1-dest" \| "profile" \| "checkout", rel, cap, expected_sha256=<the supplied SHA>)`. For **S2-R2-F2**, after `read_json` validate each host's profile object directly (a nonempty dict); never use `or dict(...)` (`:688–689`). |
| `:692` `read_confined(root, rel, "frozen code")` | Bootstrap reads. | `si.read_bytes(P, "code-root", rel, expected_sha256=pin)`, with role `code-root` = the runtime root and exact = the 31 pinned paths plus the manifest. Keep the S2 bootstrap order: manifest `74314eda` (`si.APPROVED_K4S_MANIFEST_SHA256`) before any import. |
| `:195–206` `git`, `:502`, `:583`, `:846`, `:919`, `:1063` | `subprocess.run git` with an rc check. | `si.git_checked(repo, args)` for rev-parse and merge-base; `si.git_show_file(P, "checkout", repo, commit, rel, cap)` for every `show C:path` (`:502`, `:583`, `:1063`). |
| `:394–412` `write_new`, `:615`, `:1166` | Exclusive write. | `si.Writer(P, "out").create_excl(result_name, data)`. |
| `:415–425` `strict_json` | Strict JSON. | `si.loads_strict`. |

## S3: guard-job builder (Sol PKG2 S3-F1, F2; F3 is a logic change outside this layer)

| Lines | Current | Replace with |
|---|---|---|
| `:373` `--admissions-dir` (unrestricted), `:159–161` `show(repository, commit, f"{admissions_dir}/{host}-{name}")` | Path built from an unchecked argument. | Remove the option. Use `si.git_show_file(P, "repo-e3", repo, commit, f"{si.E3_ADMISSIONS_DIR}/{host}-{name}", 1<<20)` with role `repo-e3` (root = repository, exact = the three E3 paths). A test override may only substitute the role root, under a test marker. Closes **S3-F1 (admissions)**. |
| `:156` `C.read_bounded(s1b_manifest, 16<<20)` | Generic reader with no role. | `si.read_json(P, "s1b-manifest", "s1b-admissions-manifest.json", 16<<20)`. Role root = the exact S1b dest directory, outside `end/`. Closes **S3-F1 (S1b manifest)**. |
| `:129–131` `show`, `:136–151` freeze/receipt/modules | `subprocess.run git show`. | `si.git_show_file(P, "repo-pins", repo, commit, rel, cap, expected_sha256=pin)`. Role exact = FREEZE_REL, the 9 `reports/explore/t1/<m>.py`, and SEEDS[1].path. |
| `:122–126` `git`, `:178`, `:185`, `:198–200` | Unbounded git. | `si.run_checked(["/usr/bin/git", ...], timeout, bound, env=...)` (the clone/init in a fresh temp HOME; init, fetch and checkout write only into the new job/repo). `cat-file -e` uses `si.git_checked`. |
| `:205–206` seed `path.read_bytes()`, `:207–208` `.git/config` `read_text`, `FETCH_HEAD` `exists` | Direct reads. | `si.read_bytes(P, "guard-repo", b["path"], expected_sha256=b["sha256"])` and `si.read_bytes(P, "guard-repo", ".git/config", max_size=1<<16)`; `si.check_absent(P, "guard-repo", ".git/FETCH_HEAD")`. Role `guard-repo` = `<out>/<job>/repo` with `grants=("guard-job",)` (the job name is `k4s-end-guard-*`) and exact names. Closes **S3-F2 (prove_repo)**. |
| `:256–273` `inventory` (`os.walk` + `sha_file`) | Recursive walk without an nlink check. | `si.walk_tree(P, "guard-job")` (role `guard-job` = `<out>/<job>`, `grants=("guard-job",)`, exact = the top level plus `repo/**` patterns). Then hash each file with `si.sha256_input`. The walk refuses hard links and specials, refuses names before entering, and refuses undeclared files. |
| `:338–342` `load`, `:347` `job = Path(out) / manifest["job_name"]`, `:355–358` admissions read | Unchecked manifest-derived root. | `si.read_json(P, "s3-out", "guard-job-manifest.json", 64<<20)`. Then require `si.GUARD_JOB_NAME.fullmatch(manifest["job_name"])` and build the `guard-job` role from it. Admission bytes come from `si.read_bytes(P, "guard-job", name, expected_sha256=entry["sha256"])`. Closes **S3-F2 (verify)**. |
| `:285–295`, `:314` `confined_new`/`write_new`, `:289–292` `mkdir` | Common helpers. | `si.Writer(P, "s3-out")` with `mkdir_excl(partial)`, `mkdir_excl(partial/job)` and `create_excl`. Publish with an atomic `os.rename` of the partial directory into a nonexistent name, after `si.check_absent(P, "s3-out", out_name)`. The check is required because rename(2) silently replaces an existing empty directory; the remaining window is the accepted TOCTOU residual. **No `rmtree` of anything not created by this run.** Keep `remove()` (`:328–335`) only for the run's own partial directory, verified first by dev/ino against the `mkdir_excl` result. |
| `:240` `(mods/name).write_bytes`, `:242` `shutil.copytree`, `:246` `subprocess.run` (FROZEN snippet) | Temp-dir writes and an unbounded subprocess. | Writes inside a `tempfile` dir through a Writer role rooted at it. Replace the copytree with `si.walk_tree` + `si.copy_input`. Run the snippet with `si.run_checked([python, "-I", "-B", "-c", ...], 600, 1<<20, cwd=tmp)`. |
| `:311` `git --version` | Discards the status. | `si.git_checked(...)`, or `si.run_checked(["/usr/bin/git", "--version"], 10, 4096)` (rc must be 0). |

## S4: fleet-reference assembler (Sol PKG1-r2; r3b already gates most reads)

| Lines | Current | Replace with |
|---|---|---|
| `:225–343` `relative`/`outcome_free`/`no_t1_launch_namespace`/`end_namespace_free`/`location_free`/`walk`/`absolute`/`open_confined`/`sha_confined`/`read_confined` | A second copy of the gate. | `si` roles. Every request source is an absolute path; split it into a declared role root and an exact rel. The roles are: `q6` (the T1 pool-context bundle dir on 05, exact = the 3 Q6 names); `models`; `sets`; `evidence` (outside `end/`); `guard-freeze`; `guard-admissions` (E3 dir, exact names); `seeds`; `runtime` (`patterns` = S1 list + `**/*.py`; `exemptions=("E1","E4")`); `measurement` (exact 18 names). Then call `si.open_input`/`si.sha256_input`/`si.read_json`. |
| `:389–398` `pinned_json` | Hash and parse. | `si.read_json(P, role, rel, cap, expected_sha256=entry["sha256"])`. |
| `:401–411` `active_pins` (synthetic pins) | Reads through its own gate (r3 S4-R2-F3). | `si.read_json(P, "synthetic-pins", name, 1<<20)` under the test marker only. |
| `:439–511` `runtime_python`/`runtime_files` (rglob + walk + E4 check `:443–452`) | Its own walk. | `si.walk_tree(P, "runtime")`. It returns `files`, the `e1` record and the `e4` list. Hash members with `si.sha256_input`, and the E4 entries with `si.hash_e4` (never in `files`). E1: `si.check_e1(P, "runtime")`, then hash the target as an ordinary member (D2 decides symlink or copy). |
| `:546–555` `git_run`, `:557–561` `git_blob`, `:564–571` `committed_alias`, `:574–593` `committed_receipts` | Unbounded subprocess; E1/E4 checked from git. | `si.git_ls_tree(repo, head_commit)` → `si.gate_git_tree(P, "repo-tree", entries)`. The plan refuses an unlisted `complete.json` and any symlink other than E1; then `si.git_blob(repo, plan, plan["e1"])` (link text) and `si.git_hash_e4` for each E4 entry. `git_blob(HEAD:<rel>)` becomes `si.git_show_file`. **Note D1:** a whole-tree gate at origin/main refuses until the `hub-ack.returned.json` decision is made. S4 may instead restrict `repo-tree` to the paths it needs. |
| `:867–871` `write_new`, `:873–882` `copy_verified`, `:884–920` `write_bundle` (`os.mkdir`, lexists) | Exclusive writes. | `w = si.Writer(P, "bundle-parent")`, then `w.mkdir_excl(stage)`, `w.mkdir_excl(stage/dir)` and `si.copy_input(P, role, rel, w, f"{stage}/{name}", expected_sha256=digest)`. For tiers-pins and the receipt, use `w.create_excl`. Q6/model copies are bytewise into new files (`st_nlink == 1`), per R7. |
| `:922–939` `remove_stage` | Removes the staged tree. | Keep it only for the run's own stage directory, verified by the dev/ino of its `mkdir_excl`. |

## S5: on-host preflight (Sol PKG2 S5-F1, F2; F3 is a logic change)

S5 runs **on 03/04** and needs `si` on the host (rule 0.1). Its local Policy is `si.Policy(host, roles)`; the nodename is checked.

| Lines | Current | Replace with |
|---|---|---|
| `:189–206` `bootstrap(runtime_root, k4s_manifest_sha256)` | Trusts the caller's SHA; `resolve()` plus direct reads. | `raw = si.read_bytes(P, "runtime", MANIFEST_REL, expected_sha256=si.APPROVED_K4S_MANIFEST_SHA256)` (the fixed anchor; closes **S5-F1**). Then `si.read_bytes(P, "runtime", rel, expected_sha256=pin)` for every pre-import closure file. Role `runtime` = `END_BASES[host]/runtime-<commit12>`, exact = the closure names. |
| `:93–97` `sha_file` (plain `open`) | Direct read. | `si.sha256_input` with an explicit role. |
| `:176–177` `guard_repo_commits` (`json.loads((bundle/"tiers-pins.json").read_text())`), `:450` compare-bundle, `:481` corpus inventory | Direct reads. | `si.read_json(P, "bundle" \| "compare-bundle" \| "corpus", rel, cap)`. Roles are rooted at `END_BASES[host]/bundles/<name>` and the declared corpus dir. Reject `k4s_s4_synthetic` / `production_pins:false` right after this read (S10-F4/S5). |
| `:178–185` `git cat-file -e` | `subprocess.run`. | `si.git_checked(repo, ["cat-file", "-e", c + "^{commit}"])` with `repo = Q4_GUARD_PARENTS[host]/<guard job>/repo`. The guard job name is from the bundle, checked with `si.GUARD_JOB_NAME`, and its role has `grants=("guard-job",)`. |
| `:229–237` `isolated` (`resolve()`), `:151–167` `Store` (`mkdir`, `open("x")`, `rglob`) | Resolve and an alias-following write. | `w = si.Writer(P, "preflight-parent")` with root = `END_BASES[host]/preflight`, then `w.mkdir_excl(<pfNN>)` and `w.write_json_once(...)`. The seal walk becomes `si.walk_tree(P, "preflight-out")` + `si.sha256_input`. The role roots are declared, so overlap checks become role declarations (closes **S5-F2**, output side). |
| `:263–267` `fresh_guard_job` (`exists`), `:455–457` guard path `resolve()` | Exists checks through aliases. | `si.check_dir(P, "guard-job")` + `si.check_absent(P, "guard-job", n)` for each side file. |
| `:636–645` `copy_guard_sources` (`read_bytes` / `write_bytes`) | Follows aliases. | `si.copy_input(P, "guard-job", name, w, f"{pf}/guard-sources/{name}")` (the role lists the GUARD_SIDE_FILES exactly). |
| `:715–757` `verify_received` (05) | `is_file`/`read_text`/`rglob`/`sha_file`. | Role `receive` = `/mpac/sdicks02/k4s-runner/run-r1/end-received/<host>/<attempt>`, exact metadata names. Use `si.read_json`; walk the preflight seal with `si.walk_tree(P, "receive-preflight")`; check each member with `si.sha256_input`. The preflight directory never contains END outcome names; if one appears, it refuses by name. Write `PREFLIGHT-VERIFIED.json` (`:787`) with `si.Writer.create_excl`. |

## S6: exit-push wrappers and verifier (Sol PKG2 S6-F1, F2; F3 is a logic change)

| Lines | Current | Replace with |
|---|---|---|
| `k4s_end_exit_push.sh:65`, `k4s_preflight_push.sh:73` `printf '%s\0' "$@" > "$job/argv.nul"` | Truncates through aliases (**S6-F2**). | `printf '%s\0' "$@" \| /usr/bin/python3 -I -S "$SAFE" create-excl --host "$host" --root "$job" --rel argv.nul --max-size 65536 >/dev/null \|\| exit 91`. A pre-existing name, symlink or hard link refuses with rc 3 and nothing is written. `$SAFE` is the pinned `safe_input.py` path in the staged runtime. |
| `exit_push.sh:76–77`, `preflight_push.sh:85–86` `> exit.json.tmp; mv` | Not no-clobber. | `printf … \| python3 -I -S "$SAFE" create-excl --rel exit.json.tmp …` then `python3 -I -S "$SAFE" publish-excl --root "$job" --rel exit.json.tmp --final exit.json`. `linkat` refuses an existing final. |
| `exit_push.sh:112–113`, `preflight_push.sh:116–117` (TRANSFER-COMPLETE), `:118` / `:122` (PUSH-FAILED) | Same. | The same create-excl / publish-excl pattern. Add `set -o pipefail` around each pipe and check every status. |
| `exit_push.sh:24–26`, `preflight_push.sh:27–29` `test -d "$job" && test ! -L "$job"` | Leaf-only alias check. | `python3 -I -S "$SAFE" mkdir-excl` was used by S7 to create the job (see S7). Here, check the full ancestry once with a read-only `si.check_dir`. Either add a `check-dir` CLI subcommand (not in r1), or rely on the `create-excl` walk: it opens every component from the declared root with `O_NOFOLLOW` and so refuses a symlinked base or job. |
| `k4s_end_verify_push.py:24–28` `namespace` (`resolve()`), `:31–39` `prepare` (`mkdir` / `open("x")`) | Resolve. | Role `receive-parent` = `/mpac/sdicks02/k4s-runner/run-r1/end-received/<host>`, write: `w.mkdir_excl(attempt)` + `w.write_json_once(f"{attempt}/PREPARED.json", proof)`. |
| `:42–47` `sha`, `:60–65` `registry_claims` (`is_file` + `read_text`), `:73–98` metadata `read_text` / `read_bytes` | No nlink check (**S6-F1**). | Role `receive` (exact: `PREPARED.json`, `exit.json`, `TRANSFER-COMPLETE.json`, `PUSH-FAILED.json`, `argv.nul`, `detach.json`, `detach.log`, `registry/attempt-NN.json` for the NN in range). Use `si.read_json(P, "receive", name, cap)` and `si.read_bytes(P, "receive", "argv.nul", max_size=1<<16)`. The registry listing becomes `si.walk_tree(P, "receive", "registry")`. |
| `:110–137` sealed-member loop (`is_file` / `resolve` / `sha` / `rglob`) | Hashes any name, including `games/`. | `si.walk_tree(P, "receive-measurement")` + `si.sha256_input`. **Blocked by D3:** the sealed END directory legitimately holds `end-raw.json` and `end-complete.json`, which this layer refuses under every role. A coordinator hash-only ruling must come first. Until then S6 cannot adopt this loop without refusing every complete seal. |
| `:163–165` launch / prepare proofs | `sha(path)` then `read_text` (two opens). | `si.read_json(P, "proofs", name, cap, expected_sha256=…)` (one gated open). |
| `:166–168` ACK write (`open("x")`) | Exclusive but alias-following parent. | `si.Writer(P, "receive").create_excl("DURABLE-ACK.json" \| "UNSEALED.json", …)`. |

## S7: launch gate and host program (Sol PKG2 S7-F1, F2; F3 is a logic change)

| Lines | Current | Replace with |
|---|---|---|
| `k4s_end_launch_gate.py:85–86` `sha_file` (`read_bytes`), `:189–200` `pinned_json` / receive checks, `:243–248` argv / quiet reads, `:309–321` `admission` reads | Unrestricted reads (**S7-F1**). | Roles: `launch-inputs` (exact: argv JSON, `quiet-read-v3.cmd`, the remote program); `receive` (as in S6); `preflight-verified` (exact verified-receipt names); `acks`. Use `si.read_json(P, role, rel, cap, expected_sha256=digest)`; replace the `spec.rpartition(':')` path with role + rel. |
| `:227–231` `ssh -O check` | `subprocess.run`. | `si.run_checked(["/usr/bin/ssh", "-O", "check", host], 30, 4096, ok_rcs=(255, 1))`. It must be nonzero; a 0 means a ControlMaster is open, so refuse. |
| `:233–236` `compose`, `:281` `subprocess.run(ssh, input=program)` | Unbounded; the remote has no `si`. | Program = `safe_input.py` bytes (pinned) + `CONFIG` + remote body. Run it with `si.run_checked([ssh, *si.SSH_OPTIONS, "--", host, "nice", ...], 600, bound, stdin_bytes=program, ok_rcs=(0, 3, 4, 5, 6))`, then parse strictly. |
| `k4s_end_launch_remote.py:37–40` `run`, `:141–149` `ps_table` (rc discarded) | **S7-F2.** | `si.ps_checked("/usr/bin/ps", fields=("pid", "ppid", "ni", "cls"))` (rc 0, every line parses, own row present). `res["host"] = si.hostname_checked("/usr/bin/hostname", expected=cfg["host"])`. `who`, timers and quiet go through `si.run_checked` with their meaningful `ok_rcs`. |
| `:43–48` `sha_file`, `:205–210` file pins (`isfile` / `islink`) | Leaf-only. | `si.sha256_input(Ph, "pins", rel)` with role `pins` = the pinned script directory under `END_BASES[host]`, exact names. |
| `:211–214` job parent check, `:216` registry `listdir`, `:240` `os.mkdir(job)` | Ancestor aliases followed (**S7-F1, probe**). | `Ph = si.Policy(host, [Role("attempts", END_BASES[host] + "/attempts", "write", …, exact=(job_name,)), Role("registry", …, "read", …)])`. Then `si.check_dir(Ph, "attempts")`, `si.check_absent(Ph, "attempts", job_name)`, `si.walk_tree(Ph, "registry")` (claims, names only) and `si.Writer(Ph, "attempts").mkdir_excl(job_name)`. A symlinked base refuses as `root`; the reproduced foreign-directory launch cannot happen. |

## S9: runtime export (Sol PKG2 S9-F1, F2)

| Lines | Current | Replace with |
|---|---|---|
| `:152–178` `git` / `resolve_commit` / `is_ancestor` / `show` | `subprocess.run`. | `si.git_checked` for rev-parse and merge-base (merge-base `--is-ancestor` has the meaningful rcs 0 and 1: use `si.run_checked(..., ok_rcs=(0, 1))` and read `rc`). `si.git_show_file` for the RUNTIME_PIN, QUALIFIED and K4S manifest (expected SHAs `f81f3655…`, `56b67dd4…`, `si.APPROVED_K4S_MANIFEST_SHA256`). |
| `:180–190` `ls_tree`, `:348–389` `export_commit` | Reads every blob before any gate (**S9-F1**). | `entries = si.git_ls_tree(repo, P_commit)`; `plan = si.gate_git_tree(P, "repo-tree", entries)` (role `repo-tree`: root = repository, `patterns=("**",)`, `exemptions=("E1", "E4")`). It refuses `games/`, an unlisted `complete.json`, END paths (R6: `end/` must be absent at P), any non-E1 symlink and gitlinks, before any blob. Then `si.git_export(repo, plan, si.Writer(P, "runtime-out"), e1_mode=<D2>)`. **D1** must be decided first. |
| `:215–250` `locate` (`os.walk`, prunes games only below the root) | Root and END subtree not gated (**S9-F2**). | One role per Q5 source root: the exact T1 A5 runtime trees on 05 and the K4S overlay. Roots in `end/`, `games` or a T1 launch namespace refuse at Policy construction. `si.walk_tree(P, src_role)` refuses forbidden names before entering and refuses hard links. Hash only candidates whose rel matches an EXTERNAL name, with `si.sha256_input`. Drop the `--source` free-form option or require it to equal a declared root. |
| `:267–270` `measurement_files`, `:273–289` `runtime_files` (`rglob`), `:291–303` `verify_closure` | Direct reads. | `si.walk_tree(P, "runtime")` + `si.sha256_input` / `si.read_json` / `si.read_bytes(…, expected_sha256=pin)`. |
| `:391–404` `add_externals` (`read_bounded` / `write_new`) | No nlink check on the source. | `si.copy_input(P, src_role, rel, w, name, expected_sha256=expected)`. The copy is bytewise into a new `st_nlink == 1` file (R7). |
| `:407–422` `inventory`, `:425–433` `verify_tree` (`read_bytes`) | `os.walk`. | `si.walk_tree(P, "runtime")`, then `si.read_bytes` / `si.sha256_input`. |
| `:510–516` `load_manifest`, `:521` `root = out / manifest["runtime_dir"]` | Unchecked derived root. | `si.read_json(P, "s9-out", "runtime-manifest.json", 256<<20)`; validate `runtime_dir` against `^runtime-[0-9a-f]{12}$`; then build the `runtime` role from it. |
| `:445–468` `confined_new`, `mkdir`, `remove_tree` | Common helpers. | `si.Writer` `mkdir_excl` / `create_excl`; remove only the run's own partial (dev/ino-checked). |

## S10: host staging (Sol PKG2 S10-F1, F3, F4; F2 = bases)

| Lines | Current | Replace with |
|---|---|---|
| `:55–56` `END_BASES = …/k4s-confirm-end-r1` | **S10-F2.** | `si.END_BASES` (k4s-end-r1). Update the examples and tests. |
| `:115–120` `local_root`, `:139–156` `walk_entries`, `:173–183` `inputs_component`, `:186–228` `bundle_component` (`read_bounded`), `:410–426` `HashingReader` (`open_regular`) | Hashes any leaf (**S10-F1**). | Roles: `runtime` (from the S9 manifest), `q6-inputs` (exact 3 names), `bundle-<name>` (exact: the manifest `files` + `tiers-pins.*`), `guard-job` (`grants=("guard-job",)`). Use `si.walk_tree` + `si.sha256_input`; `si.read_json(P, "bundle-…", "tiers-pins.json", 64<<20)`. Reject the S4 test stamp right there (**S10-F4**). For streaming, the tar member reader becomes `si.open_input(P, role, rel, expected_size=f["size"])` + `Input.copy_to`-style chunk reads (exact size, growth refuses). |
| `:460–461` `S9.load_manifest(a.runtime_manifest_for_checks)` | Unchecked. | `si.read_json(P, "s9-out-checks", "runtime-manifest.json", 256<<20)`. |
| `:256–271` `p_script` (P login: `test -e` / `stat` / `df \| tail \| awk` / `echo "GIT\|$(git --version)"` / `who \| wc`) | Masked statuses (**S10-F3**). | The existence and ancestor probes become `si.remote_check(Ph, [{"kind": "absent", …}, {"kind": "dir", …}])`, which checks every component no-follow on the host in one login. The df, git and who probes must use `set -o pipefail` and separate captures with explicit status checks. They are not file reads, so `si.remote_check` does not replace them. |
| `:273–293` `tv_script` (`mkdir`, `tar -x --keep-old-files`) | Host-side writes follow pre-existing symlinked parents. | **D4.** Replace `tar -x` with a shipped receiver: `safe_input.py` bytes + about 40 lines that parse the tar stream (`tarfile` `r\|`, members restricted to DIRTYPE/REGTYPE with normalized names) and create each member through `si.Writer(Ph, "<component>.partial")` (`mkdir_excl` / `open_excl`, exact size, fsync). The partial root is created by `mkdir_excl` under `END_BASES[host]` or under a Q4 guard parent. Until then, the `test ! -L` ancestor checks at `:282–284` are the only defense, which is the residual class Sol flagged. |
| `:305–323` `f_script` (`chmod` / `mv -T`) | Rename; the accepted residual for concurrent replacement. | Keep `mv -T` after `si.remote_check` `absent`(final) + `dir`(partial) in the same pass as F. A single-session check-and-rename is what the TOCTOU ruling accepts. |
| `:488–527` record / refusal (`confined_new` / `write_new`) | Common helpers. | `si.Writer(P, "s10-records")` with `mkdir_excl` / `create_excl`, and `si.write_refusal_receipt`. |
| `:496`, `:504` `shutil.which(a.ssh)`, `run_bounded` | PATH lookup. | `/usr/bin/ssh` via `si.run_checked(..., stdin_bytes=…)`. Keep the three-login structure. |

## Findings closed by adoption (once each mapping above is implemented and re-reviewed)

| Finding | How it closes |
|---|---|
| S1b-F1 | Remote `st_nlink`, through `si.remote_check`. |
| S2-R2-F1 | Auxiliary inputs go through roles, so END names are refused before any open. S2-R2-F2 is a logic change. |
| S3-F1 and S3-F2 | Roles, `git_show_file` and `walk_tree`. |
| S4-R2-F1 to F3 | r3/r3b reports fixes for these (pending Sol r3; not verified here). Adoption makes the gate single-source. |
| S5-F2 | Covered. **S5-F1** needs the bootstrap to use the `APPROVED_K4S_MANIFEST_SHA256` anchor, as mapped above. |
| S6-F1 | Metadata and registry reads are covered. The sealed members are **blocked by D3**. |
| S6-F2 | The CLI `create-excl` / `publish-excl`. |
| S7-F1 and S7-F2 | Covered. |
| S9-F1 | Covered **after D1/D2**. |
| S9-F2 | Covered. |
| S10-F1, S10-F3 (P probes) and S10-F4 | Covered. S10-F2 is the constant. The TV extraction needs **D4**. |

HIGH findings that are logic, not I/O, are unchanged by this layer: S3-F3 (`-pfNN`), S5-F3 (04 load/bus), S6-F3 (C-d 1300 s) and S7-F3 (RC-9 schemas).
