# ADOPTION r2: replacing each component's reads, writes, subprocesses and git calls with safe_input (P2-1, P2-4, D1–D4)

**Status: CANDIDATE, not reviewed.** This document says what each component must change. No component was edited, nothing was committed, and nothing ran on a host.

Line numbers refer to the local copies under `/mpac/sdicks02/k4s-runner/run-r1/end-prep/` (the same files r1 mapped):

| Component | File (directory) |
|---|---|
| S1b | `s3s9s10-r1/s1b_copy_admissions.py` |
| S2 | `s1s2-r3/s2_end_evidence.py` |
| S3 | `s3s9s10-r1/s3_guard_job.py` and `s3s9s10-r1/end_prep_common.py` ("common") |
| S4 | `b3-r3b/assemble_fleet_reference.py` |
| S5 | `s5s6s7-r1/k4s_end_preflight.py` |
| S6 | `s5s6s7-r1/k4s_end_verify_push.py`, `k4s_end_exit_push.sh`, `k4s_preflight_push.sh` |
| S7 | `s5s6s7-r1/k4s_end_launch_gate.py`, `k4s_end_launch_remote.py` |
| S9 | `s3s9s10-r1/s9_end_runtime.py` |
| S10 | `s3s9s10-r1/s10_stage_host.py` |

`si` means `safe_input`. "Role X" means a `si.Role` that the component declares explicitly in its own `Policy`.

## 0. Rules for every component

1. **Import a pinned copy.** Load `safe_input.py` from a fixed path and require its SHA-256 from `SHA256SUMS` before use. Then require `si.constants_fingerprint()` to equal the value in README.md. The r2 fingerprint also covers the family denylist, the E4 blob OIDs, the E1 link OID, the D3 constants, the git policy (environment, global flags, subcommands, indirection files, refused config), and the receive bootstrap.
   - **Host-run code** (S5, the S6 wrappers' CLI calls, the S7 remote program, and the S10 receiver) gets the same bytes, either committed into the runtime at evidence commit P or shipped verbatim. The receiver is shipped by `si.remote_receive`, which sends `si.receive_program_source()` and has the host bootstrap check its SHA-256 before running it.
   - Delete each component's own name lists, gate helpers and git wrappers, so that only one copy exists:
     - S2: `forbidden_reason`/`lexical`/`lstat_walk`/`open_dir`/`open_confined`/`read_confined`/`write_new`/`strict_json` (`:210–425`) and `git` (`:195–206`);
     - S4: `outcome_free`/`no_t1_launch_namespace`/`end_namespace_free`/`location_free`/`walk`/`absolute`/`open_confined`/`sha_confined`/`read_confined`/`write_new`/`copy_verified` (`:225–349, :867–882`), `git_run`/`git_blob`/`committed_alias`/`committed_receipts` (`:546–593`), and the constants `OUTCOME_DIRS`/`OUTCOME_LEAVES`/`JOB_COMPONENT`/`T1_LAUNCH_NAMESPACES`/`E4_COMPLETE_JSON`/`E1_*` (`:83–99, :169–184`);
     - common: `open_regular`/`read_bounded`/`sha_file`/`confined_new`/`write_new`/`run_bounded` (`:27–163`).
2. **One Policy per process**, declared at the top of the component, with an exact host. Each role has an exact root, access, cap and names. Never use `patterns=("**",)` on a root that can hold sealed data.
3. **Every refusal leaves a receipt** through `si.write_refusal_receipt(writer, "<S#>", error, context)` into a declared refusal role. Exit statuses stay as they are.
4. **Every subprocess goes through `si.run_checked`**, with an absolute `argv[0]`, an explicit timeout and output bounds, and explicit `ok_rcs` whenever a nonzero rc is meaningful. Remove every unbounded `subprocess.run(..., capture_output=True)`.
5. **Every git invocation goes through `si.git_run`** (P2-4), directly or through `si.git_ls_tree`, `si.git_show_file`, `si.git_plan`, or `si.git_checked` (r1 name; rc 0 required). Declare the repository as `si.GitRepo(work_tree=…)`. A linked worktree must declare `git_dir=` and `common_dir=`. Never pass `-C`, `--git-dir`, `-c` or a git environment yourself; `git_run` refuses them. The only subcommands allowed are `si.GIT_SUBCOMMANDS`.
   - `git show C:path` becomes `si.git_show_file(P, "<repo role>", repo, C, rel, max_size, expected_sha256)`.
   - Any read of more than one tracked file becomes the two-phase API: `plan = si.git_plan(P, "<repo role>", repo, C, members=…)` (phase 1: metadata only), then `plan.read(path, expected_sha256)`, `plan.hash_e4(entry)`, `plan.e1_check()`, `plan.e1_verify_shipped(P, role)` or `plan.export(writer)` (phase 2).
   - `merge-base --is-ancestor`, where rc 1 is meaningful, becomes `si.git_run(repo, ["merge-base", "--is-ancestor", a, b], ok_rcs=(0, 1)).rc`.
   - P2-2's END-JOB-only diff becomes `si.git_run(repo, ["diff-tree", "-r", "-z", "--name-only", "--no-renames", P, X])`. The names must be exactly `reports/explore/k4s-confirm/end/END-JOB.json`; compare names only, never read the blob.
6. **Production reads pass expected SHAs** (the accepted residual condition at 18:19Z). Use `expected_sha256=` on `read_bytes`, `read_json`, `copy_input`, `git_show_file` and `GitPlan.read`. D3 and `remote_receive` require it.
7. **Names.** The family denylist (README §2) applies in every call. END-JOB, END-FINAL and `attempt-*.json` are END-claim names: a role that must read them declares exact names and `grants=("end-claim-exact",)`. Inside `k4s-confirm/end` it also needs `"end-json-exact"`. Outcome families can never be granted.

## Open points the layer does not decide

- **D5 (needs a ruling before S9/S4 can export at the current origin/main).** Nine non-E-listed tracked files are inside the D1 member set and match a family. `si.git_plan(..., members=<frozen rule>)` refuses them by name before any blob is read. The full list is in `D5-TRACKED-FAMILY-MATCHES.txt`:
  - eight `*games*.py` scripts, for example `reports/explore/k4s-confirm/check_games.py` and `scripts/compare_native_public_games.py`;
  - `tests/fixtures/native_friendly_completed_15_535_86.json`.

  The options are exact-path E-list entries, a narrower family, or a membership change. Only the coordinator can choose.
- **E4 blob OIDs.** `si.E4_GIT_BLOB_OIDS` comes from tree metadata only. Three of the four values match Sol's PKG2 review; E2's value (`7c950203…`) has no independent source. Binding the OIDs is what lets phase 1 refuse a changed E4 blob before reading it (S4-R3-F3). The coordinator should ratify the four values.
- **Partial clone.** `/mpac/sdicks02/repos/clasher` is a promisor (partial) clone. The git helper disables every transport, so a blob that is missing locally refuses instead of being fetched lazily. S9 and S4 must run against a repository that holds every member blob, for example after one explicit, separately authorized fetch.

## S1b: copy admissions (Sol PKG2 S1b-F1)

| Lines | Current | Replace with |
|---|---|---|
| `:80–131` `READER` (no `st_nlink`, `:118–122`), `:206–210` `command`, `:212–214` `ssh_argv`, `:217–240` `parse`, `:267–270` `run_bounded` | Hand-rolled remote reader and header parser. | `si.remote_check(Pr, items, max_content=3<<20)`, which is unchanged from r1. Pr is `si.Policy(host, [Role("job", JOB_ROOTS[host], "read", 1<<20, exact=("k4s-confirm-replacement-r4/system-bus-admission.json", "k4s-confirm-replacement-r4/idle-services.json" [03 only], "k4s-confirm-replacement-r5"), grants=("reporting-job-exact",))], remote=True)`. The items are `{"kind":"file","content":True}` for each admission, plus `{"kind":"absent","rel":"k4s-confirm-replacement-r5"}`. This closes **S1b-F1**: the remote enforces `st_nlink == 1` before any read, and if any item fails, every item refuses. |
| `:195–197` `committed_latest` (`subprocess.run git show`) | Git with an inherited environment. | `si.git_show_file(P, "repo", si.GitRepo(work_tree=repo), commit, HISTORY, 16<<20, expected_sha256=…)`. |
| `:254–255`, `:276–290` `confined_new` / `write_new` / `sha_file` | Common helpers. | `w = si.Writer(P, "s1b-out")`, then `w.mkdir_excl(...)` and `w.create_excl(...)`. Write the manifest with `w.write_json_once`. |
| `:292–293` `S1B-REFUSAL.json` | Common `write_new`. | `si.write_refusal_receipt(w, "S1B", error, {"logins": logins})`. |
| `:260` `shutil.which(a.ssh)` | PATH lookup. | Fixed `/usr/bin/ssh` (`si.SSH_BINARY`). |

## S2: END evidence (S2-R2-F1/F2, **S2-R3-F1**)

| Lines | Current | Replace with |
|---|---|---|
| `:195–206` `git` (inherited environment, replace objects honoured: **S2-R3-F1**) and its callers `:502`, `:583`, `:846`, `:919`, `:1063` | `subprocess.run(["git", "-C", repo, …])`. | `repo = si.GitRepo(work_tree=MAIN_CHECKOUT)`. A detached checkout (`TMP_CHECKOUT`) that is a linked worktree uses `si.GitRepo(work_tree=TMP, git_dir=MAIN/.git/worktrees/<name>, common_dir=MAIN/.git)`; undeclared, it refuses. `rev-parse` and `merge-base` go through `si.git_run(repo, […])`. Every `show C:path` (`pinned_completion` `:501–504`, `:583`, `:1063`) becomes `si.git_show_file(P, "checkout", repo, C, rel, cap, expected_sha256=pin)`. A replace ref, `GIT_DIR`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_INDEX_FILE` or `GIT_CONFIG_*` can no longer substitute bytes: `tests/test_git_r2.py` shows the true bytes are returned while raw git returns the canary. |
| `k4s_logic.git_bytes()` (frozen, `mac/k4s_logic.py:510–514`) | Inherited environment in the frozen reader. | It cannot be edited because it is frozen. Before calling into frozen code, S2 must run every git read the frozen code would make itself, through `si.git_show_file`, and pass the frozen reader only bytes or paths whose SHA it has already checked. If the frozen reader still has to spawn git, S2 runs it in a child whose environment is exactly `si.GIT_FIXED_ENV` plus an empty `HOME`, after `si._git_preflight(repo)` has passed. This still leaves the repo's replace refs in force for that call: **flag for review.** Removing that residual needs a non-frozen path. |
| `:210–233` `forbidden_reason` / `lexical` | Local name list. | Removed; `si.name_gate` (the family denylist) runs inside every `si` call. |
| `:236–296` `Roots` / `gate_paths` / `lstat_walk` | Role roots and lstat walk. | Roles `checkout`, `s1-dest`, `profile` and `out`, as in r1. **S1 manifest and profile roles must not be rooted in or above `k4s-confirm/end`.** |
| `:310–392` descriptor gate | — | `si.open_input` / `si.read_bytes` / `si.read_json(..., expected_sha256=…)`. |
| `:394–425` `write_new` / `strict_json` | — | `si.Writer(P, "out").create_excl`; `si.loads_strict`. |

## S3: guard-job builder (Sol PKG2 S3-F1, F2)

| Lines | Current | Replace with |
|---|---|---|
| `:373` `--admissions-dir`, `:159–161` `show(...)` | Path built from an unchecked argument. | Remove the option. Use `si.git_show_file(P, "repo-e3", repo, commit, f"{si.E3_ADMISSIONS_DIR}/{host}-{name}", 1<<20, expected_sha256=…)`. |
| `:156` `C.read_bounded(s1b_manifest)` | Generic reader. | `si.read_json(P, "s1b-manifest", "s1b-admissions-manifest.json", 16<<20, expected_sha256=…)`. |
| `:129–151` `show` (freeze, receipt, modules) | `subprocess.run git show`. | `si.git_show_file(P, "repo-pins", repo, commit, rel, cap, expected_sha256=pin)`. |
| `:122–126` `git`, `:178`, `:185`, `:198–200` (init/fetch/checkout of the guard repo) | Unbounded git with an inherited environment. | `g = si.GitRepo(work_tree=<out>/<job>/repo, protocols=("file",))`, then `si.git_run(g, ["init", "-q"])` (refuses if the git dir exists), `si.git_run(g, ["fetch", "-q", <source repo path>, <commit>])` (only `file` is enabled) and `si.git_run(g, ["checkout", "-q", "--detach", <commit>])`. Hooks, fsmonitor, filters and includes never run: `core.hooksPath=/dev/null`, and the repo-config gate refuses filter, diff and merge drivers and includes. `cat-file -e` becomes `si.git_run(g, ["cat-file", "-e", c + "^{commit}"])`. |
| `:205–208` seed / `.git/config` / `FETCH_HEAD` | Direct reads. | `si.read_bytes(P, "guard-repo", b["path"], expected_sha256=b["sha256"])`; `si.check_absent(P, "guard-repo", ".git/FETCH_HEAD")`. The role has `grants=("guard-job",)`. |
| `:256–273` `inventory` | `os.walk` without `st_nlink`. | `si.walk_tree(P, "guard-job")` + `si.sha256_input`. |
| `:338–358` `load` / derived job / admissions | Unchecked derived root. | `si.read_json(P, "s3-out", "guard-job-manifest.json", 64<<20)`; `si.GUARD_JOB_NAME.fullmatch(...)`; then a `guard-job` role. |
| `:285–335` publish / remove | Common helpers. | `si.Writer(P, "s3-out")`, as in r1. No `rmtree` outside the run's own partial directory. |
| `:240–246` temp writes / copytree / subprocess | — | A Writer rooted at the temp dir; `si.walk_tree` + `si.copy_input`; `si.run_checked`. |
| `:311` `git --version` | Status discarded. | `si.git_run(repo, ["--version"])`. |

## S4: fleet-reference assembler (**S4-R3-F1, F2, F3**)

| Lines | Current | Replace with |
|---|---|---|
| `:173–184` `OUTCOME_LEAVES` (six exact, case-sensitive names), `:234–270` `outcome_free` / `end_namespace_free` / `location_free` (**S4-R3-F2**) | A second, narrower name gate. | Removed. Every input is a `si` role read, so `END-FINAL.json`, `attempt-00.json`, `end-raw-copy.json`, `complete-v2.json` and their case and prefix/suffix variants refuse by family before any syscall (`tests/test_families.py`). Declared health filenames stay readable when listed exactly; END claims need `grants=("end-claim-exact",)`. |
| `:546–555` `git_run` (inherited environment: **S4-R3-F1**), `:557–561` `git_blob` | Unbounded subprocess; replace objects honoured. | `repo = si.GitRepo(work_tree=<repository>)`; `git_blob(HEAD:<rel>)` becomes `si.git_show_file(P, "repo", repo, head, rel, cap, expected_sha256=…)`. |
| `:564–571` `committed_alias` (E1), `:574–593` `committed_receipts` (E4, interleaved with blob reads: **S4-R3-F3**) | Per-entry check then read. | `plan = si.git_plan(P, "repo-tree", repo, head, members=<the paths S4 needs>)`. Phase 1 screens ALL tree metadata first: every tracked `complete.json` must be one of the four exact E4 paths, mode 100644, with the pinned blob OID, member or not. A late unlisted, wrong-mode or changed-identity E4 entry therefore refuses with **zero** object reads (`test_refusal_anywhere_aborts_before_first_object_read`, `test_e4_identity_refused_in_phase_one`). Then call `plan.hash_e4(e)` for each `plan.e4` entry (hash only) and `plan.e1_check()` for E1 (exact mode-120000 link with OID `si.E1_LINK_OID`; link blob read with cat-file, never followed; target screened). |
| `:439–511` `runtime_python` / `runtime_files` (runtime walk with E1 as a symlink) | Own walk. | **D2:** the runtime ships `visualize_battle.py` as a regular file. Use `si.walk_tree(P, "runtime")`, which needs no E1 exemption because the file is regular, and `si.sha256_input`. Bind the shipped file to the committed target with `plan.e1_verify_shipped(P, "runtime")`, which refuses a symlink, a hard link or different bytes. E4 entries go through `si.hash_e4`. |
| `:389–411` `pinned_json` / `active_pins` | — | `si.read_json(P, role, rel, cap, expected_sha256=…)`; synthetic pins only under the test marker. |
| `:867–939` writes / `copy_verified` / `remove_stage` | — | `si.Writer` + `si.copy_input(..., expected_sha256=…)`; bytewise copies with `st_nlink == 1` (R7). |

## S5: on-host preflight (Sol PKG2 S5-F1, F2)

| Lines | Current | Replace with |
|---|---|---|
| `:189–206` `bootstrap` | Trusts the caller's SHA. | `si.read_bytes(P, "runtime", MANIFEST_REL, expected_sha256=si.APPROVED_K4S_MANIFEST_SHA256)`, then `si.read_bytes(..., expected_sha256=pin)` for every pre-import closure file. |
| `:93–97`, `:176–177`, `:450`, `:481` direct reads | — | `si.sha256_input` / `si.read_json(..., expected_sha256=…)`; reject `k4s_s4_synthetic` / `production_pins:false`. |
| `:178–185` `git cat-file -e` | `subprocess.run`. | `si.git_run(si.GitRepo(work_tree=Q4_GUARD_PARENTS[host] + "/" + job + "/repo"), ["cat-file", "-e", c + "^{commit}"])`. The job name is checked with `si.GUARD_JOB_NAME`. |
| `:151–167`, `:229–237`, `:263–267`, `:455–457`, `:636–645` writes / roots / guard checks | Resolve, plus writes that follow aliases. | `si.Writer(P, "preflight-parent")`, `si.check_dir`, `si.check_absent`, `si.copy_input`, as in r1. |
| `:715–757` `verify_received` (05) | — | Role `receive`; `si.read_json`; `si.walk_tree` + `si.sha256_input`. A preflight seal never contains END outcome names; if one appears, it refuses by family. |

## S6: exit-push wrappers and verifier (Sol PKG2 S6-F1, F2; **D3**)

| Lines | Current | Replace with |
|---|---|---|
| `k4s_end_exit_push.sh:65`, `k4s_preflight_push.sh:73` `> argv.nul` | Truncates through aliases. | `… \| /usr/bin/python3 -I -S "$SAFE" create-excl --host "$host" --root "$job" --rel argv.nul --max-size 65536 \|\| exit 91` (r1 CLI, unchanged). |
| `exit_push.sh:76–77, :112–118`, `preflight_push.sh:85–86, :116–122` | `> tmp; mv`. | `create-excl` + `publish-excl`, with `set -o pipefail` and every status checked. |
| `k4s_end_verify_push.py:24–39` | Resolve / `mkdir` / `open("x")`. | Role `receive-parent` (write) = `si.D3_RECEIVE_BASE + "/" + host`, then `w.mkdir_excl(attempt)` and `w.write_json_once(...)`. |
| `:50–65` `registry_claims` (`registry/attempt-NN.json`), `:135–137` `attempt-claim.json` | No `st_nlink` check (**S6-F1**); these names are now END-claim family names. | Role `s6-registry` (read): root `<receive>/<host>/<attempt>`, `exact=("registry/attempt-00.json", …, "durable-measurement/attempt-claim.json")`, `grants=("end-claim-exact",)`. Read each with `si.read_json(..., expected_sha256=…)`. The names are exact because the grant is exact-only. |
| `:110–134` sealed-member loop (`is_file` / `resolve` / `sha` / `rglob`) | Hashes any name, including `games/`. | **D3.** For `end-raw.json` and `end-complete.json` only, use role `s6-sealed-end` = `si.Role("s6-sealed-end", si.D3_RECEIVE_BASE + "/" + host, "read", cap, exact=(f"{attempt}/durable-measurement/end-raw.json", f"{attempt}/durable-measurement/end-complete.json"), exemptions=("D3",))` and `si.hash_sealed_end_member(P, "s6-sealed-end", rel, manifest["files"][name])`, which returns SHA and size only, never bytes. It refuses unless both seal files exist and are regular single-link files, and unless the SHA equals the seal manifest's. Every other sealed member goes through an ordinary role (`exact=` the manifest's names) + `si.sha256_input(..., )`, compared to the manifest SHA. Enumerate with `si.walk_tree` on a role that excludes the two D3 names: the walk refuses outcome families by name, so a `games/` member refuses the whole seal. |
| `:163–168` proofs / ACK write | Two opens; parent follows aliases. | `si.read_json(P, "proofs", name, cap, expected_sha256=…)`; `si.Writer(P, "receive").create_excl(...)`. |

## S7: launch gate and host program (Sol PKG2 S7-F1, F2)

| Lines | Current | Replace with |
|---|---|---|
| `gate.py:85–86, :189–200, :243–248, :309–321` | Unrestricted reads. | `si.read_json(P, role, rel, cap, expected_sha256=…)`. A role that reads END-JOB.json declares it exactly with `grants=("end-json-exact", "end-claim-exact")`. |
| `:227–231` `ssh -O check` | `subprocess.run`. | `si.run_checked(["/usr/bin/ssh", "-O", "check", host], 30, 4096, ok_rcs=(255, 1))`. |
| `:233–236`, `:281` compose and ssh | Unbounded. | `si.run_checked([ssh, *si.SSH_OPTIONS, …], …, ok_rcs=(0, 3, 4, 5, 6))`. |
| `remote.py:37–48, :141–149, :205–216, :240` | rc discarded; aliases followed. | `si.ps_checked`, `si.hostname_checked`, `si.sha256_input`, `si.check_dir`, `si.check_absent`, `si.Writer(Ph, "attempts").mkdir_excl(job)`, as in r1. The registry listing becomes `si.walk_tree(Ph, "registry")` on a role with `exact=` claim names and `grants=("end-claim-exact",)`. |

## S9: runtime export (Sol PKG2 S9-F1, F2; **D1, D2**)

| Lines | Current | Replace with |
|---|---|---|
| `:152–178` `git` / `resolve_commit` / `is_ancestor` / `show` | `subprocess.run`. | `si.git_run` for rev-parse and `merge-base --is-ancestor` (`ok_rcs=(0, 1)`). `si.git_show_file(..., expected_sha256=…)` for RUNTIME_PIN (`f81f3655…`), QUALIFIED (`56b67dd4…`) and the K4S manifest (`si.APPROVED_K4S_MANIFEST_SHA256`). |
| `:180–190` `ls_tree`, `:348–389` `export_commit` (reads every blob) | **S9-F1.** | **D1:** `pins = set(si.loads_strict(si.git_show_file(P, "repo", repo, P_commit, RUNTIME_PIN_REL, 64<<20, expected_sha256=RUNTIME_PIN_SHA))["files"])`, then `plan = si.git_plan(P, "repo-tree", repo, P_commit, members=lambda e: e["path"] in pins or e["path"].endswith(".py"))`. This is the frozen `runtime_pins` rule (`prepare_bundle.py:36–52`: pin list ∪ every `*.py`) evaluated on tree metadata only. The role is `repo-tree`: root = repository, `patterns=("**",)`, `exemptions=("E1", "E4")`. Non-members (the two `hub-ack.returned.json`, `tiers-complete.json` and the rest of `D5-TRACKED-FAMILY-MATCHES.txt`) are never read. Members with a family name refuse unless E-listed; **at origin/main nine do (D5).** R6: assert `reports/explore/k4s-confirm/end/` has no member (the strict END rule refuses it anyway). Then call `plan.export(si.Writer(P, "runtime-out"))`. **D2:** this writes E1 as a regular copy of the verified target blob, and `e1_mode` can only be `'copy'`. |
| `:215–250` `locate` | **S9-F2.** | One role per Q5 source root, then `si.walk_tree` + `si.sha256_input`, as in r1. |
| `:267–303`, `:407–433` inventories / verify | Direct reads. | `si.walk_tree` + `si.sha256_input` / `si.read_bytes(..., expected_sha256=pin)`. The runtime's `visualize_battle.py` is an ordinary regular member; bind it with `plan.e1_verify_shipped(P, "runtime")`. |
| `:391–404` `add_externals` | — | `si.copy_input(..., expected_sha256=expected)` (R7). |
| `:510–528` `load_manifest` / derived root | — | `si.read_json` + `^runtime-[0-9a-f]{12}$` + a `runtime` role. |
| P2-2 equivalence | — | `si.git_run(repo, ["diff-tree", "-r", "-z", "--name-only", "--no-renames", P, X])`; the names must be exactly the one END-JOB path. Then two `si.git_plan` runs (at P and at X, same `members`) must give identical `(path, mode, oid)` for every member. |

## S10: host staging (Sol PKG2 S10-F1, F3, F4; **D4**)

| Lines | Current | Replace with |
|---|---|---|
| `:55–56` `END_BASES` | Wrong base (S10-F2). | `si.END_BASES`. |
| `:115–228`, `:410–426` local walks / reads | **S10-F1.** | `si.walk_tree` + `si.sha256_input` / `si.read_json`; reject the S4 test stamp (S10-F4). |
| `:256–271` `p_script` | Masked statuses (**S10-F3**). | Existence and ancestor probes become `si.remote_check(Ph, [{"kind":"absent",…},{"kind":"dir",…}])`. df, git and who use `set -o pipefail` with separate status checks. |
| `:273–293` `tv_script` (`mkdir`, `tar -x --keep-old-files`) | Follows pre-existing symlinked parents. | **D4:** `si.remote_receive(Ph, "dest", P_local, files, dirs, ssh_binary=si.SSH_BINARY)`. `Ph = si.Policy(host, [si.Role("dest", si.END_BASES[host] + "/runtime-<commit12>.partial", "write", cap, patterns=("**",), exemptions=("E4",))], remote=True)`. The receiver creates that root exclusively under its canonical parent; it never overwrites, deletes or follows a link. `files` lists `{src_role, src_rel, dst, size, sha256, mode (0o444/0o555), e4}` from the S9 inventory (every SHA required); `dirs` lists every directory, parents first. Before ssh starts, every local source passes the descriptor gate (no read). The receiver re-checks every name, the host, sizes, SHAs and the E4 pins, refuses `..`, absolute paths, duplicates, symlinks and extra bytes, fsyncs, and returns a receipt with per-file `sha256/size/nlink` that `si.parse_receive_receipt` validates strictly. Guard jobs use a second Policy rooted under `si.Q4_GUARD_PARENTS[host]` with `grants=("guard-job",)`. |
| `:305–323` `f_script` (`chmod` / `mv -T`) | Rename. | Keep `mv -T` of the `.partial` root after `si.remote_check` absent(final) + dir(partial), in the same session. The window between them is the accepted residual. |
| `:488–527` records / refusals | — | `si.Writer` + `si.write_refusal_receipt`. |

## Findings closed by adoption (once implemented and re-reviewed)

| Finding | How |
|---|---|
| S1b-F1 | Remote `st_nlink` through `si.remote_check`. |
| S2-R2-F1, S3-F1/F2, S5-F2, S7-F1/F2, S9-F2, S10-F1/F3/F4 | Roles, the descriptor gate, `walk_tree` and rc-checked helpers, as in r1. |
| **S2-R3-F1, S4-R3-F1** | `si.git_run`: scrubbed environment, fresh HOME, `--no-replace-objects` + `GIT_NO_REPLACE_OBJECTS=1`, hooks off, transports off, explicit `--git-dir`, static refusal of alternates, grafts, shallow, gitfile, undeclared commondir, and config drivers and includes. Type, size and OID are verified on every object read. The frozen `k4s_logic.git_bytes()` path stays open (see S2). |
| **S4-R3-F2** | The shared case-insensitive family denylist. |
| **S4-R3-F3** | `si.git_plan`: full metadata screening, including pinned E4 blob OIDs, before the first object read. |
| S6-F1 | Registry and claims through exact `end-claim-exact` roles; sealed END members through **D3**. |
| S6-F2 | CLI `create-excl` / `publish-excl` (r1). |
| S9-F1 | **D1** member plan + **D2** export, blocked at origin/main by **D5** until a ruling. |
| S10 TV | **D4** `remote_receive`. |

Logic findings that this layer does not change: S3-F3, S5-F3, S6-F3 and S7-F3.
