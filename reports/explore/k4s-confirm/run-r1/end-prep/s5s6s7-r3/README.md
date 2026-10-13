# K4S END S5 / S6 / S7 candidates r3: preflight, exit-push + verifier, launch gate on safe_input

- **Status: CANDIDATES for Sol review (SOL-REVIEW-END-FULL-r1 response, Part B). Nothing here has been run against
  any host.** No SSH was made, nothing was committed or pushed, and no existing directory was edited: this directory
  is a new copy of `s5s6s7-r2/` (`cp -a`, r2 immutable), changed in place. Worked on 127x05 (offline only).
- **r3 (2026-10-13 UTC):** END-FULL-F2 (host side), F3, F5, F6 and the wrapper half of F1 (plus every other Part B
  pre-confinement read of safe_input / the host tool). Finding → exact fix → named tests: [RESPONSE-r3.md](RESPONSE-r3.md).
  Resume log: [PROGRESS-r3.md](PROGRESS-r3.md). r2's response stays as `RESPONSE-r1.md`.
- **r2 written:** 2026-10-12, about 21:30–22:45Z, on 127x05.
- **Inputs read (binding):** `reviews/SOL-REVIEW-END-PKG2-r1.md` (all S5/S6/S7 findings and probes);
  `SOL-REVIEW-END-S2S4-r3.md` "What r4 safe_input adoption must preserve"; `safe-input-r2/{README,ADOPTION}.md`;
  COORDINATOR at origin/main `bb1d4472` (15:16Z = 4af19c23 attempt rules, 15:23Z plan, 15:41Z Q2–Q6, 16:55Z E1–E3,
  17:12Z E4, 17:23Z R6/R7, 17:30Z P2-1..P2-3, 18:03Z P2-4, 18:19Z D1–D4, 21:28Z E5 / full clone / frozen-reader);
  `end-plan/K4S-END-PLAN-v2.md`; `audits/K4S-END-PLAN-REVIEW-r1.md` RC-2, RC-5..RC-9.
- **Read boundary:** no game file, `games/` directory, outcome `complete.json`, reducer or verifier output was opened.
  The only real repository data read: one pinned `git_show_file` of `K4S-MAC-MANIFEST.json` (74314eda) at origin/main
  (test `test_production_anchor_and_closure_equal_the_manifest_of_record`), `ls-tree` metadata, and the static
  `_git_preflight` of the shared checkout's `.git/config` names. Every other byte is synthetic, under pytest's
  `tmp_path` or `/dev/shm`.
- **r3 inputs read:** `reviews/SOL-REVIEW-END-FULL-r1.md` (in full); `end-plan/K4S-END-PLAN-v2.md`;
  `s3s9s10-r2/RC6-ROOTS-DRAFT.json` and `s3s9s10-r2/s3_guard_job.py` (the S3 guard-repo contract; not modified);
  `bootstrap-r1/` (CANONICAL-READY, its three canonical files and the conformance kit, adopted byte for byte); the
  frozen identities `k4s_logic.py:29/53` and `corpora.json` at 81f2483e (one `git show | sha256sum`, metadata/code only).
- **Finding → change map (r2):** [RESPONSE-r1.md](RESPONSE-r1.md). Resume log (r2): `../r4-s5s6s7-PROGRESS.md`.

## safe_input pin

**Final pin: safe_input r3** — `safe_input.py` SHA-256 **`806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00`**,
`constants_fingerprint()` **`33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592`**, byte-identical to
`end-prep/safe-input-r3/safe_input.py`. Development and the first mutation campaign used r2 (`f9ca4926…`, fingerprint
`6661ca0b…`); at the end `safe-input-r3/PROGRESS-r3.md` said DONE and `sha256sum -c SHA256SUMS` in `safe-input-r3/`
verified every file (all OK; every file listed except SHA256SUMS itself), so the pin was switched to r3 and every test
and both mutation campaigns were re-run on the r3-pinned package (results below are r3). r3 changes nothing S5/S6/S7
call (E5 only; API additions are optional parameters).

**r3 (END-FULL-F1): canonical bootstrap r1.** Every Python component (host tool, preflight, gate, verifier) embeds
`bootstrap-r1/k4s_bootstrap_r1.py` byte for byte (SHA-256 `5611c604…`, between its BEGIN/END lines; the pins
`SAFE_INPUT_SHA256`/`SAFE_INPUT_SIZE` = 133606 and `HOST_TOOL_SHA256`/`HOST_TOOL_SIZE` stay outside the region) and
reads safe_input and the host tool ONLY through `k4s_bootstrap_load`: the default path is `__file__`'s sibling taken
as given (never resolved or normalized), it must be absolute and normalized, every component must pass the safe_input
outcome-name families, every ancestor is opened `O_DIRECTORY|O_NOFOLLOW` from `/`, the leaf must be a regular
single-link file of exactly the pinned size BEFORE any byte is read, and exactly those bytes are hashed and executed
(no re-open, no import path, no .pyc). Then `si.constants_fingerprint()` must equal the pin. The r2 loaders
(`read_pinned`, `module_from_bytes`, `load_module`, the verifier's `load_si`) are gone. Both wrappers embed
`bootstrap-r1/k4s_bootstrap_shell_r1.sh` byte for byte (SHA-256 `1ed816fa…`) in place of `test -f` +
`sha256sum --check`: `tool()` runs `/usr/bin/python3 -I -S -c "$k4s_loader" PATH SHA SIZE -- ...`, which walks, gates,
hashes and executes the verified host-tool bytes as `__main__` on every call (the interpreter opens no script by path;
loader refusal = exit 90, the wrappers' bootstrap refusal code). The S7 host program still receives safe_input and the
host tool inside its stdin program (base64, SHA-256 checked on the host before `exec`): no path read there. No
component carries its own name list, gate, git wrapper or bounded-subprocess helper.

**safe_input r3 receive program:** `si.receive_program_source()` SHA-256 is
**`39a92e9d55f9ffefba57bae453677bad7c834f7761283268b84e40bb2d1210b4`** (computed from the vendored bytes under both
/usr/bin/python3 3.8.10 and k4s-freeze 3.12.12; the `979b37a1…` printed in the safe-input-r3 README is a misprint,
corrected by the committed erratum). S5/S6/S7 do not call the receiver; the value is cited for the package record.

## Files (full SHA-256 in `SHA256SUMS`)

| File | Role |
|---|---|
| `safe_input.py` | The shared layer, byte-identical vendored copy (see pin above) |
| `k4s_end_host_tool.py` | Host-side helpers on safe_input: names-only END registry listing, the RC-5 registry snapshot, frozen-reader clone checks in an explicit role (r3), the ONE frozen-reader environment and its config-file check (r3), the guard-job-free bundle digest (r3), the canonical bootstrap, and the CLI the wrappers use (`si -- create-excl/publish-excl`, `registry-snapshot`, `frozen-exec`) |
| `k4s_end_preflight.py` | **S5** on-host preflight (`run`) and the 05 `verify-received` |
| `k4s_preflight_push.sh` | **S5** foreground runner + post-exit push for the preflight |
| `k4s_end_exit_push.sh` | **S6** K4S delta of T1 `end_exit_push.sh` 0a87166f |
| `k4s_end_verify_push.py` | **S6** K4S delta of T1 `end_verify_push.py` 753722c9 |
| `k4s_end_launch_gate.py` | **S7** 05 side: RC-6, argv, RC-9, the one SSH session, the receipt, `admission` |
| `k4s_end_launch_remote.py` | **S7** host program body (shipped with safe_input + host tool) |
| `quiet-read-v3.cmd` | Approved quiet read, byte copy of `rounds/r4/quiet-read-v3.cmd` (a293207e) |
| `t1-originals/` | T1 bytes the S6 diffs are taken against; `detach.sh` 1648dfdc is used unchanged |
| `diffs/` | S6 vs T1, preflight wrapper vs S6 wrapper (regenerated for r3), every file vs `s5s6s7-r1` (`r1-to-r2/`) and every changed file vs `s5s6s7-r2` (`r2-to-r3/`) |
| `tests/` | Offline suites, generated host shims, `repin.py` (pin chain incl. r3 size pins), `mutate.py` (mutation driver); r3: `test_f1_bootstrap.py`, `test_f2_s3_guard_integration.py` + `s3_guard_builder.py`, `bootstrap_kit/` (byte copies of bootstrap-r1's kit, harness, loader and canonical files) |
| `PROGRESS-r3.md` | r3 resumable log |
| `MUTATION-RESULTS-py38-O.json`, `MUTATION-RESULTS-py312-O.json` | Mutation campaign results |
| `TEST-RUN.txt` | Output summary of the final test matrix |

**Pin chain** (`tests/repin.py` rewrites it in dependency order; `tests/test_pins.py` fails on any stale pin):
safe_input → host tool → preflight + both wrappers → verifier (END wrapper) → gate (host tool, wrappers, preflight,
host program, detach, quiet read). Editing any of these files means re-pinning, which changes the gate's SHA.

## 0. Layout (from `si.END_BASES` / `si.Q4_GUARD_PARENTS`; must equal the RC-6 declaration)

| | 127x03 | 127x04 |
|---|---|---|
| base | `/mpac/sdicks02/jobs/clasher/k4s-end-r1` | `/mpac/sdicks02/jobs-k4s/k4s-end-r1` |
| runtime | `<base>/runtime-<commit12>` (S9/S10 name) | same |
| bundles | `<base>/bundles/<name>/` (`tiers-pins.json`, `.sha256`, `assembly-receipt.json`) | same |
| `--repository` clone | `<base>/repository` | same |
| END attempt parent / preflight parent | `<base>/attempts` / `<base>/preflight` | same |
| staged tools | `<base>/tools/` (`detach.sh`, both wrappers, `k4s_end_preflight.py`, `safe_input.py`, `k4s_end_host_tool.py`) | same |
| guard jobs (separate Q4 parent) | `/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-{pfNN,rdRR-aNN}` | `/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-{pfNN,rdRR-aNN}` |
| 05 receive | `/mpac/sdicks02/k4s-runner/run-r1/{end-received,preflight-received}/<host>/<attempt>` | same |
| 05 launch inputs/receipts | `/mpac/sdicks02/k4s-runner/run-r1/end-launch/<host>/<attempt>/` | same |

Attempt names: END `end-<host>-r<RR>-l<NN>` (launch index), preflight `preflight-<host>-l<NN>`; `--out` is
`<job>/<attempt>`. The preflight bundle's guard job must be a `-pfNN` job and its compare (attempt) bundle a
`-rdRR-aNN` job; an END bundle's guard job must be `-rd<this round>-aNN` (S3-F3 / runner decision 2).

### RC-6 roots declaration (consumed by S7)

`end-launch/ROOTS-DECLARATION.json`, pinned by `launch --roots-sha256`, schema `clasher.k4s.end-roots-declaration.v1`:

```json
{"schema": "clasher.k4s.end-roots-declaration.v1", "commit": "<40-hex commit that declared it>",
 "hosts": {"127x03": {"base": "...", "runtime": "<base>/runtime-<commit12>", "repository": "<base>/repository",
                      "attempts": "<base>/attempts", "preflight": "<base>/preflight", "tools": "<base>/tools",
                      "guard_parent": "<Q4 parent>",
                      "bundles": {"<name>": {"path": "<base>/bundles/<name>", "tiers_pins_sha256": "<64 hex>",
                                             "guard_job": "<Q4 parent>/k4s-end-guard-r1-<pfNN|rdRR-aNN>"}}},
           "127x04": {"...": "..."}}}
```

Exact keys, both hosts, every root equal to `si.END_BASES`/`si.Q4_GUARD_PARENTS`, no guard job shared by two
bundles. Every launch argv path (runtime, bundle, repository, attempt parent, tools, job) must be a declared root.

---

## S5: on-host preflight (`k4s_end_preflight.py run`)

### Order

Before any runtime module is imported (stdlib + safe_input only):

| # | Check | What it does |
|---|---|---|
| — | refusals (no write) | host 03/04 (rc-checked `hostname`), nice 10 / SCHED_OTHER, not `-O`, hold ≥ 120 s (03) / 900 s (04), ≥ 60 samples, block seconds, **`--k4s-manifest-sha256` must equal the code constant 74314eda** |
| — | layout (pure) | every path argument equals the declared layout (runtime-<commit12>, bundles/<name>, repository, attempts, `--out = <base>/preflight/<job>/<job>`, corpus inventory = the runtime's manifest path, native/corpus K4S-owned under the base, evidence inside the bundle) |
| — | bundle manifest | `tiers-pins.json` read with `--bundle-pins-sha256` (descriptor gate), guard job must be `<Q4>/k4s-end-guard-r1-pfNN` |
| 1 | `listings_before` | attempt parent names-only (must be empty) + END registry names-only (`k4s_end_host_tool.registry_listing`) |
| 2 | `bundle_stamp` | compare bundle the same way (`-rdRR-aNN`); sidecar SHA; **S4 `k4s_s4_synthetic` stamp or a non-production `assembly-receipt.json` refuses** |
| 3 | `input_locations` | native and corpus pass the descriptor gate (opened, never read) |
| 4 | `guard_repo` | frozen-reader ruling, **role `guard-repo`** (r3, F2): the guard job's `repo/` is the S3 Q3 repository, a depth-1 SHALLOW clone (S3 `build_repo`/`prove_repo`); `verify_clone` declares shallow for this role only and requires it (`rev-parse --is-shallow-repository` true; `.git/shallow` regular, single-link, only 40-hex commits present in the repo); every other refusal is kept (si static preflight: real `.git`/`objects`, no commondir, alternates, grafts, driver/include config or code-running core keys; no `refs/replace/`; hooks only `*.sample`; r3: no promisor/partial-clone config or `*.promisor` pack); then Q3 `git cat-file -e` of b2f9e25e and ce042b97 through `si.git_run` (same role) |
| 5 | `repository_clone` | the `--repository` (evidence / END-JOB) clone passes `verify_clone` in **role `repository`: full**, shallow refused |
| 6 | `frozen_git_env` | r3 (F3): `k4s_end_host_tool.frozen_env_checked` builds THE frozen-reader environment (inherited `GIT_*` removed, P2-4 git keys + `GIT_CONFIG_PARAMETERS`; HOME and XDG_CONFIG_HOME absolute, normalized, canonical or refused, see below) and checks exactly the config files that environment makes git 2.25 read; the process environment is replaced by that very object (checked equal) |
| 7 | `pre_import_pins` | **S5-F1:** the manifest read with the FIXED 74314eda (never caller-supplied); the closure it pins (k4s_files, end_files, reused_readonly, k4s_kernel.files, SD1 manifest: 32 files) must equal the code constant `FROZEN_CLOSURE`; every file read through safe_input with its pin; corpus inventory read with `--corpus-inventory-sha256` |
| 8 | `frozen_import` | `end_reference`, `end_background`; every runtime module loaded is a verified closure file (`closure_only`) |

Then `end_reference.reference()` order except the claim and the measurement (unchanged from r1, plus):
`frozen_identity` must return exactly the pinned bundle manifest; `guard_job_fresh` checks the side files and STOP
names through `si.check_absent`; `guard_samples` reads `capacity.jsonl` only after the monitor stopped (a growing
file refuses in safe_input, so r1's live top-up loop was removed); `post_pins` adds `loaded_modules_check` (every
runtime module outside the closure must be a bundle `runtime_files` member whose bytes, read through safe_input, equal
the pin). NEVER `pool_context`, `producer_claim`, `K4SStore(REFERENCE_SCOPE)`, `measure()` (AST-checked).

### Output, mode, bus band (P2-3)

One fresh directory created with `si.Writer.mkdir_excl`, every file written `O_CREAT|O_EXCL|O_NOFOLLOW` (0444),
sealed with scope **K4S-END-PREFLIGHT** (`walk_tree` + `sha256_input`). `preflight-result.json`
(r3: `clasher.k4s.end-preflight.v3`) exports:

- `mode`: **binding** only if reference-slot work ran (> 0 states), every background slot became ready
  (= slot_count − 1) and the measured loaded guard span ≥ 60 s (03) / **900 s (04)**; otherwise **diagnostic**
  (`--no-reference-work` is always diagnostic). `qualifying` = passed and binding.
- `load` (slot_count, background slots expected/ready, reference work, states worked) and `duration` (requested,
  measured, required).
- `bus_band` of the loaded cumulative bus %: `proceed` (≤ 0.3), `coordinator-decision` (between), `stop` (≥ 0.7),
  `unavailable`; `bus_gate` = the band on 04 (`not-gated-on-127x03` on 03).
- `passed` requires every check, an empty and unchanged attempt parent, an unchanged registry, guard sources copied
  through the descriptor gate, and on 04 no sshd increase during the hold.
- r3 (F5): `identity` — the native/corpus paths it used and the identities `end_reference.frozen_identity` verified
  (native `44874fd6…` = `k4s_logic.NATIVE_PROVENANCE_SHA`, corpus `a97b1fbf…` = `T1_K4_CORPUS_SHA`; the run fails if
  the frozen identity is anything else) plus the corpus inventory path and SHA (`--corpus-inventory-sha256` must be
  `3501e2ac…`, corpora.json at 81f2483e); `bundle_identity` — the guard-job-free digest
  (`k4s_end_host_tool.bundle_sans_guard_sha256`: canonical `tiers-pins.json` without `reference_load_profile.guard.job`)
  of its own and of its compare bundle, from the pinned manifest bytes (equal: bundle parity).

### 05: `verify-received`

`python3 -I k4s_end_preflight.py verify-received --receive <RUNNER>/preflight-received/<host>/preflight-<host>-lNN`
(05, not -O): everything through safe_input — PUSH-FAILED absent, metadata files through the descriptor gate, exit ⇔
transfer marker (`TRANSFER-DONE.json`), seal SHA, scope, a `walk_tree` whose role allows exactly the sealed names
(an extra, aliased, symlinked or outcome-named file refuses), every file SHA. Writes `PREFLIGHT-VERIFIED.json`
(r3: `clasher.k4s.end-preflight-verified.v3`, exclusive) with mode, qualifying, load, duration, bus band/gate,
the loaded-bus numbers (`percent`, `seconds`, `cpu_ticks`, `hz`), inputs, `identity`, `bundle_identity`,
`receipt_manifest_sha256`, `preflight_result_sha256`. That document is S7's RC-9 input.

---

## S6: exit-push wrapper and verifier deltas

### `k4s_end_exit_push.sh` (diff vs T1: `diffs/k4s_end_exit_push.sh.diff`)

- **No shell redirection writes any file** (test `test_wrapper_sources_have_no_writing_redirection`). `argv.nul`,
  `exit.json` (via `.tmp` + `publish-excl`), `TRANSFER-DONE.json` and `PUSH-FAILED.json` are created by
  `python3 -I -S <tools>/k4s_end_host_tool.py si -- create-excl|publish-excl` (O_EXCL, no-follow, canonical
  symlink-free job root; an existing or hard-linked name refuses; nothing is truncated or replaced; `set -o pipefail`,
  every status checked). r3 (F1): the host tool is never opened by path: the canonical shell bootstrap r1 (pasted
  verbatim after `host_tool`, `host_tool_sha`, `host_tool_size`) verifies it once up front (`--verify-only`, exit 90 on
  refusal: alias, hard link, symlink, wrong size, wrong bytes, outcome-named ancestor) and every `tool` call
  re-walks, re-gates, re-hashes and executes the verified bytes; `sha256sum` is no longer used. The host tool loads
  safe_input through the canonical Python bootstrap.
- Pre-checks: attempt name `end-<host>-rRR-lNN` matching `--round`; parent exactly `<base>/attempts`; every metadata
  name absent (no file, no dangling link); `detach.log`/`detach.json` regular, not links.
- The END command runs through `frozen-exec`: the `--repository` clone is verified (frozen-reader ruling, role
  `repository`: full) and the command is `exec`ed with the very environment object whose config files were checked
  (r3, F3: `frozen_env_checked`; `os.execvpe(..., env)`). The argv recorded in `argv.nul` is exactly `"$@"`.
- RC-5: after exit, `registry-snapshot` lists `registry/round-RR/<host>/` names-only (strict names, regular, nlink 1)
  and copies each claim through safe_input into `<job>/registry/` + `registry-listing.json`; both are pushed
  whenever END exited, with or without a measurement. A refused snapshot makes the run PUSH-FAILED (exit 92).
- The transfer marker is renamed `TRANSFER-DONE.json`: `TRANSFER-COMPLETE.json` matches safe_input's never-grantable
  `complete-json` outcome family, so no tool could read or write it.

Exit codes unchanged: 90 refused (nothing run or pushed), 91 metadata could not be created, 92 push/snapshot
failure (`PUSH-FAILED.json`), else END's own code (3 if frozen-exec refused before END ran).

### `k4s_end_verify_push.py` (diff vs T1: `diffs/k4s_end_verify_push.py.diff`)

Inputs at fixed paths only (`--receive`, plus `--launch-receipt-sha256`/`--prepare-proof-sha256` for
`end-launch/<host>/<attempt>/{LAUNCH-RECEIPT,PREPARE-PROOF}.json`). Every read/hash/stat/write through safe_input.

- **C-d:** no ACK and no UNSEALED record before `exit_utc + 1300 s`; the ACK records `exit_epoch`, `verified_epoch`,
  `c_d_earliest_utc`, `c_d_satisfied`.
- **Registry (S6-F1):** `registry-listing.json` binds names + SHAs; the received `registry/` is walked with an exact
  `end-claim-exact` role (a hard-linked, symlinked or undeclared file refuses) and must equal the listing; each claim
  is read with its listed SHA and must name this host, its index and the attempt's round. `claim_without_receipt`
  is recorded.
- **Sealed members:** `end-raw.json` / `end-complete.json` are D3 hash-only (`si.hash_sealed_end_member` against the
  seal manifest, never parsed); every other member is hashed through an exact role (outcome-family names such as
  `games/reviewer.json` refuse by name before any syscall); a names-only listing proves there is no extra member.
- Kept: `--prepare` (now exclusive through safe_input, mode 0700), `-O` refused at import, 05 / nice 19 / CPU 63,
  scope `K4S-END-REFERENCE`, sealed claim binding, exit codes 0 ACK / 2 UNSEALED / nonzero-traceback REFUSE.

---

## S7: launch and prelaunch gate

`nice -n 19 python3 -I k4s_end_launch_gate.py launch --host H --kind end|preflight --attempt A --argv-sha256 S
--roots-sha256 S [--prepare-proof-sha256 S] [--preflight-verified 127x03=preflight-127x03-lNN:S
--preflight-verified 127x04=preflight-127x04-lNN:S] [--prior-03 A03:ACK_SHA:ADMISSION_SHA] [--bus-decision-sha256 S]
[--second-attempt-ruling-sha256 S] [--allow-timer UNIT.timer=why]... [--clearance-seconds N] [--window-seconds N]
[--diagnostic-preflight] [--dry-run]`

**On 05, before any session** (each a refusal with no receipt and no SSH): 05 and not -O (rc-checked hostname);
receipt absent; RC-6 declaration validated; argv equal to its pin and structurally exact against the declaration
(see `validate_argv`: inner `nice -n 10 taskset -c 61`, `<tools>/detach.sh`, `<tools>/<wrapper>`, job = parent/attempt,
env pins, `-B`, END: exactly the 13 options with declared runtime/bundle/repository and a `-rd<round>-aNN` guard job;
preflight: declared bundles with their pinned SHAs, `-pfNN`/`-rdRR-aNN`, hold minimum, `--no-reference-work` only with
`--diagnostic-preflight`); quiet-read v3 bytes by SHA; receive dir (preflight empty; END only `PREPARED.json` = the
committed proof); **RC-9** (below); no local ControlMaster (`ssh -O check` rc-checked: only 255 proceeds).

**RC-9 / P2-3 / C-d (END launches):** both hosts' `PREFLIGHT-VERIFIED.json` at their declared receive paths, pinned,
with schema v3, scope, host/attempt/receive, provenance (re-hash of the sealed `receipt-manifest.json` and
`preflight-result.json`), passed/no failed check/registry and attempt parent unchanged and empty, **mode binding +
qualifying**, the full reference load and the measured duration, 04 no login, input binding to RC-6 (runtime,
repository, manifest, bundles, guard job, layer SHA) and, for the launching host, to this argv's evidence and SD1
SHAs. **r3 (F5):** (a) each preflight's `identity` must be the K4S END native/corpus/corpus-inventory identities
under that host's declared roots, and for the launching host its native, corpus and corpus-inventory paths must equal
this END argv's `--native`, `--corpus`, `--corpus-inventory`; (b) its own and compare bundles must carry one
guard-job-free digest, and the END bundle is either EXACTLY the preflight's compare bundle (path + RC-6 tiers-pins
SHA; binding `exact`) or, for a later attempt/round whose preflight can no longer run, a different declared bundle
whose equivalence the host program VERIFIES from its pinned `tiers-pins.json` bytes (binding `guard-job-equivalent`:
recomputed digest must equal the preflight's; the END bundle can never be the preflight's own bundle or guard job);
(d) the loaded-bus numbers must be present, finite, non-negative and consistent (`percent = 100·ticks/hz/seconds`,
`seconds` = the measured loaded duration), the recorded band must be the P2-3 band of that percent (≤ 0.3 proceed,
≥ 0.7 stop, between coordinator-decision: the same constants as S5) and the gate must be the band on 04 /
`not-gated-on-127x03` on 03. **04 bus:** `proceed` passes; `coordinator-decision` needs a pinned `BUS-DECISION-<preflight>.json`
(`decision: proceed`, coordinator ref, bound to that preflight's seal); `stop`/`unavailable` refuse ("STOP before any
claim"), for a launch on either host. **04 END:** 03's `DURABLE-ACK.json` (schema v2, SEALED, complete,
`c_d_satisfied`, `verified_epoch ≥ exit_epoch + 1300`, seal re-hash) and 03's RC-7 `ADMISSION.json`
(`closed_before_admission: true`). r3 (F5c): 03's attempt must be of the round being launched; the admission record
must have been made from this ACK and 03's launch receipt (`verified_sha256`, `launch_receipt_sha256`, kind end); 03's
`LAUNCH-RECEIPT.json`, read with the SHA the ACK binds, must be a launched 03 END attempt with `--round` = this round,
under the same RC-6 declaration (`roots_sha256`) and on the same two qualifying preflight receipts as this launch.

**The one session** (`si.SSH_OPTIONS`: `-T`, BatchMode, ControlMaster=no, ControlPath=none, StrictHostKeyChecking;
`/usr/bin/python3 -I -B -`), every host subprocess through `si.run_checked`, every host file through safe_input:

| # | Step | Rule |
|---|---|---|
| 1 | `si.hostname_checked(expected=H)` | rc 0 + one valid line; valid stdout with nonzero rc refuses |
| 2–4 | quiet-read v3 #1, 30 s, #2 (verbatim) | rc 0; apt units inactive/failed; maint 0; who 0; helper change noted |
| 5 | `systemctl list-timers --all` unfiltered, TZ=UTC | every timer ≥ clearance (≥ 2 h) unless allowlisted; rc, parse, zero-timers refuse |
| 6 | stamps | gated no-follow fstatat (no read); release-upgrade age ≤ 24 h − window; updates-available newer than apt lists |
| 7 | `who` | rc 0 and zero lines |
| 8 | `si.ps_checked` | rc 0, every line parsed, own process with its real parent; then other sshd sessions refuse |
| 9 | staged tool SHAs | descriptor gate (symlink/hard link refuse) and pin equality |
| 10 | base / parent / job | `si.check_dir` on the base (canonical: **a symlinked base or ancestor refuses**), parent, job absent |
| 11 | frozen-reader | bundle `tiers-pins.json` with its declared SHA → guard job = the declared one; END: its guard-job-free digest = the qualifying preflight's (r3 F5b); guard job fresh; `--repository` (role `repository`, full) and guard `repo/` (role `guard-repo`, the S3 shallow Q3 repo) pass `verify_clone`; Q3 commits; `frozen_env_checked` on the environment the launched wrapper inherits (r3 F3) |
| 12 | END registry | names-only listing; ≥ 2 claims refuse; 1 claim needs the pinned second-attempt ruling |
| 13 | C5 pre-exec gate | from the rc-checked table: this process and parent ni 0 / TS; argv byte-equal; no outer prefix |
| 14 | launch | `si.Writer.mkdir_excl(job)`; pinned argv run once via `/usr/bin/env --` (exact argv, no shell) |
| 15 | postexec | ≤ 10 s priority read-back, rc-checked ps, no signal (C6) |

The receipt (`clasher.k4s.end-launch-receipt.v2`, exclusive) records the session open/close UTC and epoch (05 clock),
the RC-6 commit, gate/remote/layer/tool SHAs, the prerequisites, and the host result. Exit codes as r1 (0 launched,
3 refused on host, 4 job created but launch failed, 5 unknown host state: STOP, 6 launched but ssh nonzero).

`admission --host H --kind K --attempt A --launch-receipt-sha256 S --verified-sha256 S` (after the verifier at C-d):
the sealed `guard-admission.json` read with its seal-manifest SHA; writes `ADMISSION.json` (exclusive);
`closed_before_admission` needs close + 1 s < admission (05 vs host clock, not skew-corrected). The 04 END launch
requires 03's record to be true (RC-7).

---

## Tests (offline)

Final matrix on 127x05, run **from a pristine `cp -a` copy of this directory** (`/dev/shm/s567r3-pristine/s5s6s7-r3`,
as delivered: shims 0755, no `__pycache__` before or after). Every run used `nice -n 19 taskset -c 8-15`, `-B`,
`PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`. pytest 8.3.5 for 3.8 comes from `/dev/shm/s567r3-pytest38`
(no venv modified). Output summary: `TEST-RUN.txt`.

| Interpreter | normal | `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **611 passed** | **561 passed, 50 skipped** |
| `/usr/bin/python3` 3.8.10 (host python) | **611 passed** | **561 passed, 50 skipped** |

The r2 baseline was 276 normal and 254 + 22 skipped under `-O`. The 50 `-O` skips are all verifier tests: 22 of the 23
in `test_s6_verifier.py` (the verifier refuses `-O` at import, T1 R3-1; the 23rd test checks that refusal) and the
28 kit scenarios of the verifier's loader in `test_f1_bootstrap.py`.

Tests per file:

| File | Tests |
|---|---|
| `test_host_tool.py` | 79 |
| `test_s5_preflight.py` | 70 |
| `test_s6_wrapper.py` | 50 |
| `test_s6_verifier.py` | 23 |
| `test_s7_gate.py` | 154 |
| `test_pins.py` | 4 |
| `test_f1_bootstrap.py` | 214 |
| `test_f2_s3_guard_integration.py` | 17 |

The only `-O` warning is pytest's `PytestConfigWarning` about asserts. The suites never use `assert`; they use
explicit `ok()`/`raises()` checks.

F6 check: in a second pristine copy with the five shims set to 0644, pytest stops at session start with an
INTERNALERROR naming every non-executable shim.

**F2 integration against the revised Part A.** `K4S_PARTA_DIR=<end-prep>/s3s9s10-r3` (DONE; 30 SHA256SUMS entries
verified; `s3_guard_job.py` `bf99e74b…`) gives **17 passed** in all four modes. The default is the immutable
`s3s9s10-r2`.

r3 additions:

| File | Coverage |
|---|---|
| `test_host_tool.py` | **F2** roles: explicit and required; shallow refused for `repository` and allowed and required for `guard-repo`; 12 indirections × 2 roles, including promisor config, promisor pack, commondir, include and replace; `.git/shallow` gates. **F3**: 14 relative/empty/non-normalized values; symlinked HOME/XDG; HOME `//` canonicalization installed; NOSYSTEM required; name gate on config paths; installed-git `--show-origin` enumeration (XDG set and unset); Sol relative-XDG `git -C` probe (control, then refusal); frozen-exec execs the identical checked env object; frozen-exec CLI refusal. **F6** shim checks. **F1** canonical loader refusals |
| `test_s5_preflight.py` | **F3**: the env the frozen code runs with is the checked object; relative or empty XDG fails the run before any frozen import. **F5**: identities and bundle identity exported; frozen identity must be the K4S END one; inventory pin. The real S5 verified summary is accepted by S7's `launch_identity` and `bus_evidence` |
| `test_s7_gate.py` | **F3**: the host program refuses relative, empty or odd XDG and a global-config include, and checks HOME=`//x` canonically. **F5**: Sol probes (changed native and corpus path; a01 vs a00, admitted only as host-verified guard-job equivalence and refused on the host when a01 differs beyond guard.job; 10 round/lineage breaks including the other-round ACK; 12 inconsistent-bus cases including 0.8 % recorded as proceed); identity binding (7 cases, both hosts); exact binding recorded; bundle identity required; constants equal to S5's |
| `test_f2_s3_guard_integration.py` | REAL S3 guard jobs (unmodified Part A builder) through `verify_clone`, the full S5 `run` (03 and 04) and the S7 host program (END and preflight launches). Negatives: shallow `--repository` (S5 and S7); graft, alternates, replace, promisor, hook and include in the real repo; the real repo checked in the `repository` role |
| `test_f1_bootstrap.py` | Byte equality of the six embedded regions and of the vendored kit with bootstrap-r1. The kit is run against 6 Python loaders × every scenario (zero canary opens and bytes, atime unchanged, nothing executed; control and swap execute exactly the hashed bytes). Both wrappers run as real bash × 19 alias scenarios (exit 90 before any tool call, nothing created, command never started). A host tool swapped after verification is never executed |

### Mutation

`tests/mutate.py` covers 127 mutants: the 74 from r2, 6 of them retargeted to the r3 text, plus 53 new ones, one or
more for every new guard (F2a–l, F3a–i, F5a–u, F6a, F1a–j). There are also 8 NULL controls.

Each mutant is applied to a fresh copy in `/dev/shm/s567r3-mut-*`; every edit target must occur exactly once
(`--check-edits`). The copy is re-pinned, including the r3 size pins, and the named tests run with `-O -B -x`.
`test_pins.py` is never included. Canonical-region mutants (H08, H09, F1e, F1f, F1j) and wrapper mutants (W05,
F1g–i) are judged only by the BEHAVIOURAL kit and wrapper tests, given as pytest node ids. The byte-equality region
tests would otherwise kill them trivially.

Every kill was checked to be a pytest FAILED line, not an import, collection or syntax error. The verifier mutants
(V01–V08, F1d) and the NULL controls that include the verifier run without `-O`, because the verifier refuses `-O`
at import.

| Campaign (package SHAs recorded in the JSON) | Killed | NULL survived |
|---|---|---|
| 3.12.12 -O (`MUTATION-RESULTS-py312-O.json`) | **125/127** | 8/8 |
| 3.8.10 -O (`MUTATION-RESULTS-py38-O.json`) | **125/127** | 8/8 |

All 53 new mutants were killed in both campaigns. Two r2 mutants survive, documented as equivalent (`EQUIVALENT` in
`mutate.py`):
- **P14**: `reference_slot_work` and `mode_requested` derive from the same argument;
- **P22**: verify-received's set equality is implied by the exact-names walk plus per-file hashing.

Two guards have no mutant, because they are unreachable defence in depth:
- in S5, `require(dict(os.environ) == env)` after `clear()` + `update(env)`;
- in S7, "the END bundle is not the preflight's own bundle or guard job". `validate_argv` already refuses an END
  bundle whose guard job is not `-rd<round>-aNN`, and a preflight bundle always has a `-pfNN` guard job.

**Disclosure:** the 3.12 campaign ran before one test-only change. The F2 integration test's Part A source changed
from auto-selected to deterministic `s3s9s10-r2`; at that time the auto-selection also resolved to r2, so the
behaviour was identical. The 3.8 campaign ran on the final bytes. Both JSONs record the same package SHAs.

## What remains unverifiable offline

1. Every frozen module on a real host (unchanged from r1): `validate_bundle`, the real manifest/closure bytes in the
   runtime, torch/native/pickle loading, `K4SFleetBackground`, the T1 `ReportingGuard` and admission, `compare_mhz`;
   real bus/MHz/sshd numbers.
2. Real OpenSSH 8.2 / sshd process titles, `ssh -O check` with the real config, `pam_motd`; systemd 245's
   `list-timers` format under `TZ=UTC` (parser tested on synthetic lines; a mismatch fails closed).
3. Real rsync transfer into the 05 receive dirs (shimmed with `cp`); real priorities (`nice`/`taskset`/`ni`/`cls`
   shimmed).
4. That the launch session closes before guard admission: recorded after the fact by `admission` and now REQUIRED
   for the 04 launch (RC-7), but not enforced for 03's own attempt beyond being recorded.
5. Clock skew between 05 and the host (admission, verifier ordering): inherited from T1; C-d is evaluated on the 05
   clock against the host-clock `exit_utc`.
6. **Frozen-reader git configuration (r3, END-FULL-F3).** git 2.25.1 ignores `GIT_CONFIG_GLOBAL`, so the user
   config cannot be disabled; instead the files the installed git reads are enumerated from the EXECUTED environment
   (`git_config_files`, config.c `do_git_config_sequence`): system `/etc/gitconfig` — never read, `GIT_CONFIG_NOSYSTEM=1`
   is required; XDG — `$XDG_CONFIG_HOME/git/config` if set, else `$HOME/.config/git/config`; global — `$HOME/.gitconfig`;
   plus the repository's `.git/config`/`config.worktree` (si's preflight) and `GIT_CONFIG_PARAMETERS` (set). Each file
   path passes `si.name_gate`, a no-follow walk from `/`, and the descriptor gate (regular, single link) before
   `si._check_git_config` (no filter/diff/merge/include/includeIf section, no code-running core key); includes are
   refused, so no further file is reachable. A test runs the installed git (`config --list --show-origin`) under the
   executed env and checks that every file origin is a checked file or the repository config. **Choice: refusal.** A
   relative, empty-but-set or non-normalized XDG_CONFIG_HOME or HOME is refused (not rewritten), with ONE exception
   for a strong reason: the fleet passwd home is `//home/sdicks02` (`getent passwd` on 127x05), so sshd sets
   `HOME=//home/sdicks02`; refusing it would refuse every real run. A leading `//` (exactly two slashes) is therefore
   canonicalized to `/` and that canonical value is INSTALLED in the executed environment (same directory on Linux);
   the checked paths derive from the executed environment object, which frozen-exec passes to `execvpe` itself
   (identity tested). r3 also refuses promisor/partial-clone host clones (config and `*.promisor` packs).
7. Accepted TOCTOU residual (16:00Z / 18:19Z): a same-size in-place rewrite between a check and a later open by
   another local actor. Reads of files this run itself produced (frozen monitor outputs, the received seal before
   it is verified, `assembly-receipt.json`) have no prior SHA; they are bound afterwards (seal, verified manifest SHA).
   Wrapper (r3): the host tool is no longer re-opened by the interpreter after a separate check; every `tool` call
   hashes and executes the same bytes. Bind mounts stay within the trusted single-operator mount assumption.
8. **The guard-job-equivalent bundle binding** (F5b) relies on the host program's recomputation at launch; S7 on 05
   cannot read the attempt bundle. The preflight itself only compares its own and compare bundles.

## Open decisions for Sol and the coordinator

1. **RC-6 declaration schema** (above) is defined here; it must be committed and pushed before the END-JOB.
2. **`TRANSFER-COMPLETE.json` → `TRANSFER-DONE.json`** (forced by the shared denylist).
3. **Names-only listings composed from safe_input primitives** inside the strict END namespace (registry) and the D3
   sealed directory, because the layer cannot root or walk there (README of safe_input §2). Each name is regex- or
   `name_gate`-checked before it is stat'ed. A layer API for this would remove the composition.
4. **`frozen-exec`** puts the P2-4 git environment around the frozen END/preflight command (frozen-reader ruling); the
   END process environment therefore differs from T1's in `GIT_*` keys only.
5. **Second attempt** needs `--second-attempt-ruling-sha256` (`REPEAT-RULING.json`, schema
   `clasher.k4s.end-second-attempt-ruling.v1`); `SECOND-ATTEMPT-…` would hit the END-claim name family.
6. 03 minimum preflight hold raised to 120 s (samples are counted after the monitor stops; ≥ 60 loaded seconds
   required for a binding 03 run).
7. **r3, F5(b) choice: exact binding where possible, host-verified guard-job equivalence otherwise.** A preflight
   requires an EMPTY attempt parent (RC-2/RC-9: preflights precede every claim), so no preflight can run after a
   host's first claim; per-attempt bundles get fresh guard jobs (RC-3), and a host may have a second attempt / later
   rounds. Exact-only binding would make every attempt after the first unlaunchable. So: the END bundle equal to the
   preflight's compare bundle is `exact`; any other declared `-rdRR-aNN` bundle is admitted only as
   `guard-job-equivalent`, verified on the host from the attempt bundle's pinned bytes against the digest the
   preflight computed from its own pinned bundles. Recorded in the launch receipt (`bundle_binding`).
8. **r3, F2 contract: keep the minimal Q3 shallow guard repo** (runner decision). Only the `guard-repo` role
   declares shallow; the `repository` role (evidence/END-JOB clone) stays full. There is no default role.
9. **r3, F2 integration source:** `tests/test_f2_s3_guard_integration.py` builds real guard jobs with the UNMODIFIED
   Part A `s3_guard_job.build` (from `s3s9s10-r3` once its PROGRESS says DONE, else `s3s9s10-r2`; `$K4S_PARTA_DIR`
   overrides; its SHA256SUMS is verified first) in Part A's own synthetic world, then places that job byte/mode-copied
   at the Q4 path for the S5 preflight run and the S7 host program.
