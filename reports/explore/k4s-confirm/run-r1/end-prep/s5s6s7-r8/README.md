# K4S END S5 / S6 / S7 candidates r7: preflight, exit-push + verifier, launch gate on safe_input, END-JOB builder

- **r7 (2026-10-14 UTC, 127x05, offline): ruling PF-4 (COORDINATOR c14b40e8; 04 l00 preflight failed at
  `background_ready`). The S5 affinity readback check is now the ruled subset form, and every S5 check is classed against
  the frozen END in [CLASS-TABLE-PF4.md](CLASS-TABLE-PF4.md). The class audit fixed two more: the MHz window, and an
  error outside any check that still sealed `passed`.** The runner copied `s5s6s7-r6` and made the affinity edit; the
  worker continued. r6 is unchanged. [RESPONSE-r7.md](RESPONSE-r7.md), [DIFF-r7.patch](DIFF-r7.patch),
  [PROGRESS-r7.md](PROGRESS-r7.md); section **r7** at the end. Only `k4s_end_preflight.py` changes among the six
  TOOLS-FINAL files; S7's `PREFLIGHT_SHA256` follows it. No SSH, commit or push.

- **r6 (2026-10-13 UTC, 127x05, offline): SOL-FIXCHECK-END-INTEGRATION-r5. The builder is re-pinned to S9 r6
  (`s3s9s10-r6`, the U10 fix) and to the production runtime the runner rebuilt with it (RUNTIME-r6-READY), and the
  proof is regenerated. Nothing else changed.** New copy of `s5s6s7-r5/` (`cp -a`, r5 SHA256SUMS verified; r5
  immutable). [DIFF-r6.patch](DIFF-r6.patch), [RESPONSE-r6.md](RESPONSE-r6.md), [PROGRESS-r6.md](PROGRESS-r6.md);
  section **r6** at the end. No SSH, commit or push.

- **r5 (2026-10-13 UTC, 127x05, offline): SOL-REVIEW-END-INTEGRATION-r1 finding 1 (U8 builder pins) and the U4
  interpreter ruling (COORDINATOR 10:33Z).** New copy of `s5s6s7-r4/` (`cp -a`, r4 SHA256SUMS verified in the copy; r4
  immutable). Diff-only: [DIFF-r5.patch](DIFF-r5.patch); item → fix → tests: [RESPONSE-r5.md](RESPONSE-r5.md); resume
  log: [PROGRESS-r5.md](PROGRESS-r5.md); section **r5** at the end. No SSH, commit or push. The text below r5 is the
  r4/r3 record (its counts are theirs).

- **r4 (2026-10-13 UTC, 127x05, offline): INTEGRATION-AUDIT-r1 Part B rows U5, U6, U7, U8, L1, L6, U12.** New copy of
  `s5s6s7-r3/` (`cp -a`, r3 SHA256SUMS verified in the copy; r3 immutable). Row → fix file:line → named tests:
  [RESPONSE-r4.md](RESPONSE-r4.md). Resume log: [PROGRESS-r4.md](PROGRESS-r4.md). Section **r4** below. Nothing was
  run against a host; no SSH, commit or push. The r3 text below is kept as the r3 record (its counts are r3's).

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
| `k4s_a6_builder.py` | **r4 (U8)** END-JOB builder, 05 only: `build` (exact frozen fields from committed bytes at P') and `self-check` (scratch `.git` copy: END-JOB alone on P', frozen `end_job`, S9 `equivalence`) |
| `templates/` | **r4 (U12)** `BUS-DECISION.template.json`, `REPEAT-RULING.template.json` (the schemas `launch` checks) |
| `builder-proof/` | **r4** recorded U8 proof: `END-JOB.json` (declared_by marks it NOT the A6 declaration), `BUILD.json`, `SELF-CHECK.json` |
| `audit-rerun/` | **r4** the audit's `frozen_job_drive.py` / `s9_equiv_drive.py` re-run against the builder output (`rerun.sh` regenerates `builder-proof/` and these outputs) |
| `t1-originals/` | T1 bytes the S6 diffs are taken against; `detach.sh` 1648dfdc is used unchanged |
| `diffs/` | S6 vs T1, preflight wrapper vs S6 wrapper (regenerated for r3), every file vs `s5s6s7-r1` (`r1-to-r2/`) and every changed file vs `s5s6s7-r2` (`r2-to-r3/`) |
| `tests/` | Offline suites, generated host shims, `repin.py` (pin chain incl. r3 size pins), `mutate.py` (mutation driver); r3: `test_f1_bootstrap.py`, `test_f2_s3_guard_integration.py` + `s3_guard_builder.py`, `bootstrap_kit/` (byte copies of bootstrap-r1's kit, harness, loader and canonical files) |
| `PROGRESS-r3.md` | r3 resumable log |
| `MUTATION-RESULTS-py38-O.json`, `MUTATION-RESULTS-py312-O.json` | Mutation campaign results |
| `TEST-RUN.txt` | Output summary of the final test matrix |

**Pin chain** (`tests/repin.py` rewrites it in dependency order; `tests/test_pins.py` fails on any stale pin):
safe_input → host tool → preflight + both wrappers → verifier (END wrapper) → gate (host tool, wrappers, preflight,
host program, detach, quiet read); r4: safe_input → `k4s_a6_builder.py`. Editing any of these files means re-pinning,
which changes the gate's SHA.

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

---

## r4 (INTEGRATION-AUDIT-r1 Part B)

**Inputs read:** `end-staging/INTEGRATION-AUDIT-r1/REPORT.md` (rows U5–U8, U12, L1, L6, §4 items 5–7) and its
`runlog/drivers/` + `runlog/simulated/` (how the audit hand-built these artifacts); `s5s6s7-r3/{README,RESPONSE-r3}.md`;
`end-plan/K4S-END-PLAN-v2.md` (A3, A6, RC-6); the frozen `end_evidence.py` / `end_reference.py` / `fleet_end.py` in the
S9 runtime `end-staging/runtime-98566c032d0b` (read only); `s3s9s10-r3/s9_end_runtime.py` (equivalence, REPO_FULL);
S4 `b3-r5/assemble_fleet_reference.py` (bundle evidence name, receipt fields); `end-staging/{A2-GO-REQUEST.md,
RC6-ROOTS-k4s-end-r1.json}` (05 bundle staging path). Repository data: only named health-only blobs at P' 98566c03 of
`repo-full` (end-evidence.json, DELTA-MANIFEST.json, SD1-MANIFEST.json, K4S manifest, corpora.json, the evidence's plan
/ completion / ledger / inventory / phase artifacts), via `git cat-file`/`git show` or safe_input's gated reader; every
SHA in the code came from a command. No game, `games/` directory, outcome complete.json, end-raw/end-complete, reducer
or verifier output was opened.

**Disclosure (PROGRESS-r4.md, 05:4xZ):** to read those five blobs I first made a full `cp -a` of `repo-full` (work
tree included) under `/dev/shm`. That byte-copied the work tree's tracked files, among them 4 `complete.json` files
(names counted with `find`; 0 `games/` directories); nothing was parsed or displayed, and the copy was deleted at once.
From then on every scratch clone copies `repo-full/.git` ONLY and materializes just the evidence and its artifacts.

### What is new

| Command | Where | Does |
|---|---|---|
| `k4s_end_launch_gate.py build-argv --kind end --host H --attempt end-H-rRR-lNN --roots-sha256 S --bundle NAME --end-job-commit X --preflight-verified H=preflight-H-lNN:SHA` | 05 | Writes `end-launch/H/<attempt>/launch-argv.json` (O_EXCL, no-follow, 0444) from the pinned RC-6 declaration (bundle path, tiers-pins SHA, guard job), the S4 receipts in `end-staging/bundles/NAME/` (sidecar, production CANDIDATE receipt for this host / manifest / guard job, evidence of record inside the bundle), the END-JOB blob at X in `repo-full` (its SHA = `--end-job-sha256`), the launching host's pinned PREFLIGHT-VERIFIED identity (native / corpus) and the gate constants. The composed argv must pass `validate_argv` first. Prints `argv_sha256` (for `launch --argv-sha256`) |
| `… build-argv --kind preflight --host H --attempt preflight-H-lNN --roots-sha256 S --bundle PF_NAME --compare-bundle RD_NAME --native P --corpus P --hold-seconds N [--end-job-commit X] [--diagnostic-preflight]` | 05 | The same for the preflight argv S5 runs (`--hold-seconds` ≥ the host minimum) |
| `k4s_end_launch_gate.py prepare-preflight-receive --host H --attempt preflight-H-lNN` | 05 | Creates the EMPTY `preflight-received/H/<attempt>/` (0700, exclusive) the preflight push wrapper rsyncs into and `launch` requires |
| `k4s_end_verify_push.py --receive …/end-received/H/<attempt> --prepare` | 05 (nice 19, CPU 63) | As r3, plus the byte-equal `end-launch/H/<attempt>/PREPARE-PROOF.json` (exclusive); prints `prepare_proof_sha256` for `launch --prepare-proof-sha256` and the verifier |
| `k4s_a6_builder.py build --declared-by TEXT --out NEW_DIR` | 05 | `NEW_DIR/END-JOB.json` with exactly the frozen fields from committed bytes at P' + `BUILD.json`; prints the SHA |
| `k4s_a6_builder.py self-check --out DIR --job-sha256 S` | 05 | Scratch-only proof: frozen `end_evidence`+`end_job` accept the END-JOB at X = P' + END-JOB alone, and S9 r3 `equivalence` passes; `DIR/SELF-CHECK.json` |

`validate_argv` now also pins the host python (`HOST_PYTHON`, A3 **pending ruling**), the evidence path inside the
bundle (`k4s-end-evidence/end-evidence.json`), the END evidence SHA of record, the SD1 SHA, the preflight
corpus-inventory SHA and the `--end-job-sha256` format; the host program (L1) checks the staged runtime directory and
`end_reference.py` pin, the presence of the native/corpus files, and the END-JOB at HEAD of `--repository`. S5 (L6)
pins `DELTA-MANIFEST.json` before any import.

**05 order for one END attempt (A6 onwards):** `k4s_a6_builder.py build` → coordinator commits `END-JOB.json` alone on
`k4s-end-r1` (B6), pushes, fast-forwards the host clones (S11) and the 05 full clone (S9 r4 `refresh-clone`) →
`self-check` on that END-JOB → `k4s_end_verify_push.py --prepare` → `build-argv --kind end` → `launch` with the printed
SHAs. For a preflight: `prepare-preflight-receive` → `build-argv --kind preflight` → `launch --kind preflight`.

### U8 proof (recorded)

`builder-proof/` (builder `k4s_a6_builder.py` SHA recorded in `BUILD.json` and `SELF-CHECK.json`): built from P';
fields `completion_sha256` = the completion of record, `counted_hosts` [127x03, 127x04], `k4s_manifest_sha256` 74314eda,
`end_evidence_sha256` = end-evidence.json at P'. The self-check committed it alone on a scratch copy of P' (`diff-tree`
= exactly the END-JOB path), the FROZEN `end_evidence` + `end_job` accepted it at that commit, and S9 r3
`equivalence` passed (4280 git members; runtime_files / measurement_files identical). `audit-rerun/` repeats this
with the audit's own drivers (`frozen_job_drive.py --claim`, `s9_equiv_drive.py`; only their scratch paths
substituted): both rc 0.

### Tests (r4)

Final matrix on 127x05 from a pristine `cp -a` copy (`/dev/shm/s567r4/pristine/s5s6s7-r4`; 0 `__pycache__`/`.pyc`
before and after); `umask 022`, `PYTHONDONTWRITEBYTECODE=1`, `-B`, `-p no:cacheprovider`, `nice -n 19 taskset -c 16-23`;
3.8 with `PYTHONPATH=/dev/shm/s3s9s10r2-pytest38`. Output summary: `TEST-RUN.txt`.

| Interpreter | normal | `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **726 passed** | **671 passed, 55 skipped** |
| `/usr/bin/python3` 3.8.10 | **726 passed** | **671 passed, 55 skipped** |

r3 was 611 / 561 + 50. The 55 `-O` skips: the 50 r3 verifier skips plus the 5 r4 verifier tests in `test_r4.py` (the
verifier refuses `-O` at import). Tests per file: `test_host_tool.py` 79, `test_s5_preflight.py` 70, `test_s6_wrapper.py`
50, `test_s6_verifier.py` 23, `test_s7_gate.py` 154, `test_pins.py` 4, `test_f1_bootstrap.py` 243 (r3 214 + the 28
kit scenarios of `k4s_a6_builder.py` + its region test), `test_f2_s3_guard_integration.py` 17, **`test_r4.py` 56**,
**`test_a6_builder.py` 30**. Existing fixtures changed only to the new contracts (diffs in `diffs/r3-to-r4/`): the S7
`Site` uses the gate's pinned python / SD1 / evidence SHAs, the bundle evidence path, an END-JOB committed at HEAD of
the host `--repository`, and stage-able bundle manifests; the S5 fixture adds a DELTA-MANIFEST; the verifier Setup
provides `end-launch/`. The integration tests `test_a6_builder.py::test_real_a6_builder_proof_frozen_and_s9` and
`test_r4.py::test_production_pins_equal_the_committed_blobs_at_p_prime` read `repo-full` (read only) and the S9 runtime.

### Mutation (r4)

`tests/mutate.py` now has 178 mutants (127 from r3 + **51 new**: R01–R19 gate / build-argv / U12, L01–L08 host L1
and S5 L6, U01–U04 verifier U7, J01–J20 the A6 builder) and 10 NULL controls (N09 `test_r4.py`, N10
`test_a6_builder.py` added). Same method as r3: fresh `/dev/shm/s567r4-mut-*` copy, re-pinned, named tests with
`-O -B -x` (verifier mutants without `-O`), `test_pins.py` never included; run under `nice -n 19 taskset -c 24-31`,
8 jobs.

| Campaign (package SHAs in the JSON; builder a76da2b6…, gate e346a71f…) | Killed | NULL survived |
|---|---|---|
| 3.12.12 -O (`MUTATION-RESULTS-py312-O.json`) | **176/178** | 10/10 |
| 3.8.10 -O (`MUTATION-RESULTS-py38-O.json`) | **176/178** | 10/10 |

All 51 new mutants were killed in both campaigns, each by a pytest FAILED line. The two survivors are r3's documented
equivalents P14 and P22. J17 ("scratch directory kept") leaves its scratch directory by construction; the two it left
(one per campaign) were removed afterwards. Guards with no mutant because they are unreachable defence in depth:
`ensure_dir`'s `check_dir` of an existing level (a symlinked level is refused again by the canonical root open of the
next level), the second absence check / emptiness proof in `prepare-preflight-receive` (the directory was just made
with `mkdir_excl`), the builder's `JOB_FIELDS` equality after constructing exactly those keys (J12 mutates the constant
instead), and the host program's `check_dir(runtime)` (the pinned read of `end_reference.py` opens the same root
canonically).

### r4 open items

See RESPONSE-r4.md "Rulings / open items": A3 host python ruling; S10 r4 must stage the r4 `k4s_end_preflight.py`
(its SHA changed with L6); native/corpus location (S10 r4 end-inputs); B6 ruling; S9 r4 (B3/B5, U10) before the
runtime and X exist on 05.

## r5 (SOL-REVIEW-END-INTEGRATION-r1: finding 1, U4)

**Inputs read:** `reviews/SOL-REVIEW-END-INTEGRATION-r1.md` (63fae416; finding 1 and the U4 ruling paragraph); the
COORDINATOR at origin/main (10:33Z rulings B6, D1, U4, U11; 05c733d1); `s5s6s7-r4/{README,RESPONSE-r4}.md`;
`reports/explore/k4s-confirm/runtime.sh` at P' 98566c03 (`git show` from `repo-full`, read only);
`s3s9s10-r4/s10_stage_host.py` TOOL_PINS; the markers `s3s9s10-r5/S9-FINAL` and `end-staging/RUNTIME-r5-READY`;
the production `runtime-manifest.json` (metadata). No game, `games/`, outcome complete.json, end-raw/end-complete,
reducer or verifier output was opened; every scratch clone copied `repo-full/.git` only.

### What changed (diff: `DIFF-r5.patch`)

| File | Change |
|---|---|
| `k4s_end_launch_gate.py` | **U4:** `HOST_PYTHON = /mpac/sdicks02/repos/clasher/.venv/bin/python` (the interpreter P' `runtime.sh` execs with `-B`), `RUNTIME_SH_REL`; message "(U4)". `validate_argv` / `compose_argv` / build-argv use the one constant with `-B`. Repinned: only this file's SHA moved |
| `k4s_a6_builder.py` | **Finding 1:** S9 = adopted `s3s9s10-r5/s9_end_runtime.py`, runtime = production `runtime-98566c032d0b` with the RUNTIME-r5-READY manifest SHA (written by `tests/adopt_pins.py`, record `ADOPTED-S9-RUNTIME.json`); `frozen_inputs` now requires the manifest's `script_sha256` = the S9 pin, `commit` = P', `repository` = REPO_FULL, `python` = FROZEN_PYTHON; SELF-CHECK records the manifest's builder and member-set SHA |
| `TOOLS-FINAL` | The six S10 TOOL_PINS files (name, sha256, size, source): byte-identical to r4, written first; never changed |
| `ADOPTED-S9-RUNTIME.json` | Adoption record (S9 path/SHA/size, S9-FINAL marker SHA, runtime path, manifest SHA + its script/commit/python/member SHAs, RUNTIME-r5-READY marker SHA) |
| `builder-proof/` | Regenerated: `BUILD.json`, `END-JOB.json`, `SELF-CHECK.json`, `RERUN-1-build-selfcheck.log`, `RERUN-2-audit-only.log` |
| `audit-rerun/` | `rerun.sh` reads pins from the record (re-hashed), `--audit-only`, S9-FINAL chain only, trap cleanup; regenerated outputs |
| `tests/test_r5.py` (new, 10) | U4 constant / compose / validate / runtime.sh-at-P' / S10-agreement; U8 contract tests (record, sibling package, production manifest, recorded proof) |
| `tests/adopt_pins.py` (new) | Marker → builder constants + record; `--check` |
| `tests/test_a6_builder.py` | +8 `test_r5_frozen_inputs_bind_runtime_to_adopted_s9` cases; `frozen_inputs` returns the manifest; real-proof test uses a private scratch parent and checks the adopted pins |
| `tests/test_s7_gate.py` | Stand-in interpreter path in the venv layout |
| `tests/mutate.py` | +9 mutants (I01–I03, J21–J26), J18 retargeted, N11 NULL, copies named `s567r5-mut-*` |

### U8 proof (recorded, `builder-proof/`)

Built from P' (END-JOB SHA in `BUILD.json`), committed ALONE on a scratch copy of `repo-full/.git` (scratch X in
`SELF-CHECK.json`, `diff-tree` = exactly END-JOB.json), FROZEN `end_evidence` + `end_job` accepted it at X (45
evidence files materialized from committed blobs), and the ADOPTED S9 (`s9_sha256` in SELF-CHECK = S9-FINAL)
`equivalence` passed against the PRODUCTION runtime manifest (`runtime_manifest_sha256` = RUNTIME-r5-READY): 4283 git
members whose SHA equals the manifest's `git_members_sha256`, runtime_files / measurement_files identical (canonical
SHAs fc3dbeb4 / 42b8986d unchanged). `audit-rerun/` repeats it with the audit's drivers: both rc 0.

### Tests (r5)

Final matrix from a pristine `cp -a` copy (`/dev/shm/s567r5/pristine/s5s6s7-r5`; 0 `__pycache__`/`.pyc` before and
after); `umask 022`, `PYTHONDONTWRITEBYTECODE=1`, `-B`, `-p no:cacheprovider`, `nice -n 19 taskset -c 16-23`; 3.8 with
`PYTHONPATH=/dev/shm/s3s9s10r2-pytest38`. Then `tests/test_r5.py` in place (where the sibling `s3s9s10-r5` is beside
it). Output summary: `TEST-RUN.txt`.

| Interpreter | normal (pristine) | `-O` (pristine) |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **742 passed, 2 skipped** | **687 passed, 57 skipped** |
| `/usr/bin/python3` 3.8.10 | **742 passed, 2 skipped** | **687 passed, 57 skipped** |

744 tests (r4 726 + `test_r5.py` 10 + 8 new `test_a6_builder.py` cases). Skips: the 2 sibling-package contract
tests (`test_u4_s10_probe_interpreter_is_the_same_string`, `test_u8_adopted_record_matches_the_sibling_s9_package`)
skip in a relocated copy by design and run in place; `-O` adds r4's 55 verifier skips. In-place `test_r5.py` results
are in `TEST-RUN.txt`: first 9 passed + 1 failed in each mode (the sibling-SHA256SUMS test, while `s3s9s10-r5` still
listed its r4 S9), then, after that package's SHA256SUMS became final (`sha256sum -c` OK), **10 passed** in all four
modes.

### Mutation (r5)

`tests/mutate.py` has 187 mutants (178 r4 + 9 new: I01–I03 U4, J21–J26 builder binding / pin drift; J24/J25 drift a
SHA constant by one hex digit computed from the file, no SHA typed) and 11 NULL controls (N11 `test_r5.py`). Run on the
new and changed guards only (`--only I01 I02 I03 J17 J18 J19 J20 J21 J22 J23 J24 J25 J26 R01 N09 N10 N11`), same
method as r4 (fresh `/dev/shm/s567r5-mut-*` copy, re-pinned, named tests with `-O -B -x`), `nice -n 19 taskset -c 24-31`,
8 jobs:

| Campaign | Killed | NULL survived |
|---|---|---|
| 3.12.12 -O (`MUTATION-RESULTS-r5-py312-O.json`) | **15/15** | 3/3 |
| 3.8.10 -O (`MUTATION-RESULTS-r5-py38-O.json`) | **15/15** | 3/3 |

Each kill is a pytest FAILED line of the intended test (I01 constant test, I02 compose test, I03 validate test,
J21/J22/J20 the portable binding cases, J23–J26 the record contract test, J17 the real proof's private-scratch check,
J18/J19 the production pin cases, R01 the build-argv single-field test). `R01` appears twice because r1 and r4 both used
the id (pre-existing duplicates R01–R06; `--only` selects both; both killed). Two discarded attempts are logged in
PROGRESS-r5.md: new ids G01–G03 collided with r1 ids (renamed I01–I03), the N11 NULL was killed by a ROOT-relative
marker path in the record test (fixed), and the N10 NULL was killed by a `/dev/shm` scratch-name race between concurrent
mutants in the real-proof test (the test now uses a private scratch parent).

### r5 open items

1. U4 qualification of the venv on 03/04 (resolved site-packages, imports) is the S10 probe's authorized host step.
2. `RUNTIME-r5-READY` is 0644; its SHA is in the record and the contract test fails on any change.
3. The adopted pins deviate from Sol's literal r4 values (80c15b5f / 1fa0ebf5) because finding 2 changed S9; disclosed
   by the coordinator.
4. U11 (S8) deferred (coordinator); B6 / D1 endorsed and unaffected here.

## r6 (SOL-FIXCHECK-END-INTEGRATION-r5: re-pin to S9 r6)

**Inputs read:** `reviews/SOL-FIXCHECK-END-INTEGRATION-r5.md` (U8 FIXED; the U10 fix is Part A); the markers
`s3s9s10-r6/S9-FINAL` and `end-staging/RUNTIME-r6-READY` (written by the runner after rebuilding the production runtime
with S9 r6); the production `runtime-manifest.json` (metadata). No game, `games/`, outcome complete.json,
end-raw/end-complete, reducer or verifier output was opened; the proof's scratch clone copied `repo-full/.git` only.

**Nothing but the pins changed.** New copy of `s5s6s7-r5/` (`cp -a`, r5 SHA256SUMS verified in the copy; r5
immutable). Diff: [DIFF-r6.patch](DIFF-r6.patch); response: [RESPONSE-r6.md](RESPONSE-r6.md); resume log:
[PROGRESS-r6.md](PROGRESS-r6.md).

| File | Change |
|---|---|
| `k4s_a6_builder.py` | `S9_PATH` = `s3s9s10-r6/s9_end_runtime.py`, `S9_SHA256` = S9 r6, `FROZEN_RUNTIME_MANIFEST_SHA256` = the RUNTIME-r6-READY manifest (all four written by `tests/adopt_pins.py`, computed from the markers; `FROZEN_RUNTIME` path unchanged); three comment words r5 → r6. No logic change |
| `ADOPTED-S9-RUNTIME.json` | Re-adopted (r5 copy removed first; `adopt_pins.py` refuses an existing record) |
| `tests/adopt_pins.py` | Marker / package names r5 → r6 only (`s3s9s10-r6`, `RUNTIME-r6-READY`) |
| `tests/test_r5.py` | Contract expectations r5 → r6 only (sibling package, adopted S9 path, marker paths) |
| `tests/test_a6_builder.py` | One skip-reason string r5 → r6 |
| `tests/mutate.py` | J23's edit target follows the pin (r6 path → the predecessor r5 path) |
| `audit-rerun/rerun.sh` | Comment, `--declared-by` label and scratch path `s567r5` → `s567r6`; outputs regenerated |
| `builder-proof/` | Regenerated by `rerun.sh` (r5 copy removed first; the script requires it absent). r5's `RERUN-2-audit-only.log` is gone: the first r6 run passed, so no audit-only rerun was needed |
| `TOOLS-FINAL` | **Unchanged** (copied; the six files are byte-identical to r5, re-checked by command) |

**Pins (computed by `adopt_pins.py`, record `ADOPTED-S9-RUNTIME.json`):** S9 `s3s9s10-r6/s9_end_runtime.py`
sha256 `bdc2deeb96bf60a16b8877ffa2038760673d60bb63edcde8d947195fdfdcf3a7` (84364 bytes; = S9-FINAL); production runtime
`end-staging/runtime-98566c032d0b`, manifest sha256 `9d6ab1f7386894727035c14a95c518b54e9472c9cb90eb6d023c589fe2269b43`
(= RUNTIME-r6-READY; its `script_sha256` = S9 r6, commit P' 98566c03, python e4v3-venv; `git_members_sha256`
89cff336…, runtime / measurement files fc3dbeb4… / 42b8986d…, the same as r5). `adopt_pins.py --check`: current.

### U8 proof (recorded, `builder-proof/`, regenerated by `audit-rerun/rerun.sh`, first run OK)

Build from P' (END-JOB sha256 `1197e0b1…`, `BUILD.json`). The END-JOB was committed ALONE on a scratch copy of
`repo-full/.git` ONLY (`/dev/shm/s567r6`, removed); `diff-tree` = exactly END-JOB.json. FROZEN `end_evidence` +
`end_job` accepted it at X. The ADOPTED S9 r6 `equivalence` then passed against the production manifest: 4283 git members
(SHA = the manifest's), runtime / measurement files identical. `SELF-CHECK.json` ok = true, s9_sha256 = S9 r6,
runtime_manifest_sha256 = 9d6ab1f7…. The audit's two drivers (`audit-rerun/*.out`) also pass: frozen end_evidence /
end_job / producer_registry / producer_claim (scratch work tree only) and S9 r6 equivalence rc 0. Log:
`builder-proof/RERUN-1-build-selfcheck.log`.

### Tests (r6, `TEST-RUN-r6.txt`)

In place, with `s3s9s10-r6` beside it (so the sibling contract tests run). The package tree was byte-for-byte unchanged
before and after, with 0 `.pyc`.

| Interpreter | normal | `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **744 passed** | **689 passed, 55 skipped** |
| `/usr/bin/python3` 3.8.10 | **744 passed** | **689 passed, 55 skipped** |

744 = r5's 744 (no test added). The `-O` skips are r4's 55 verifier skips (the verifier refuses `-O`). The two
sibling-package tests that r5 skipped in its pristine copy run here and pass.

### Mutation (r6)

Only the pins changed, so only the U8 binding / pin-drift subset was rerun: `--only J17–J26 N09 N10 N11`, with J23's
target following the pin (S9 path r6 → the predecessor r5). The method is r5's: a `/dev/shm` copy, re-pinned, named
tests with `-O -B -x`, 6 jobs. py3.12 `-O`: **10/10 killed, 3/3 NULLs survived**
(`MUTATION-RESULTS-r6-py312-O.json`). py3.8 `-O`: **10/10 killed, 3/3 NULLs survived**
(`MUTATION-RESULTS-r6-py38-O.json`). J23–J26 were killed by
`test_r5.py::test_u8_builder_constants_equal_the_adopted_record`, as in r5.

### r6 open items

1. The r5 disclosures stand (U4 qualification is the S10 probe's host step; U11 deferred).
2. `RUNTIME-r6-READY` is mode 0444; the record stores its SHA.

---

## r7 (ruling PF-4: S5 vs frozen END class audit)

**Inputs read.**
- The COORDINATOR PF-4 entry (c14b40e8) and RO-1.
- `audits/K4S-END-PLAN-REVIEW-r1.md` RC-2..RC-9.
- The frozen runtime `end-staging/runtime-98566c032d0b/runtime`, read only: `end_reference.py`, `end_background.py`, `mac/k4s_backend.py`, `mac/k4s_logic.py`, the e4v3 `fleet_validity`, `fleet_reference`, `fleet_profile`, `telemetry`, `tier_backend`, `replay_load`, `receipts`, and the T1 guard `host_audit`, `ssh_budget`, `system_bus`.
- Preflight metadata only: `preflight-received/127x04/preflight-127x04-l00` and `127x03/preflight-127x03-l01` (`preflight-result.json`, `argv.nul`, file sizes).
- The production bundle `end-staging/bundles/end-ref-127x04-pf00/tiers-pins.json` (`runtime_files`, profile).
- No outcome file was opened.

### What changed (`DIFF-r7.patch`, production files only; tests in `DIFF-r7-tests.patch`)

| File | Change |
|---|---|
| `k4s_end_preflight.py` | **background_ready** (runner's edit, kept): one readback per pinned mask, each a non-empty subset of it, masks pairwise disjoint (frozen `tier_backend.py:238` / `k4s_backend.py:100` narrow workers per tier). The slot evidence is recorded first, with exactly END's four fields (AST-equal to `end_reference.py:371-374`). **mhz_comparison:** only hold rows from the first hold row + the frozen `warmup_seconds` on are compared (END compares only post-warm-up `measure()` rows); fewer than 2 such rows are recorded `unavailable`, never gated. **verdict:** an error with no check row open fails the run (r6 sealed it `passed`). Docstring r7 note |
| `k4s_end_launch_gate.py` | `PREFLIGHT_SHA256` re-pinned (`tests/repin.py`); nothing else |
| `TOOLS-FINAL` | rewritten from computed hashes; only the `k4s_end_preflight.py` row differs from r6 |
| `tests/test_r7.py` (new, 15) | observed 04 readbacks pass; full-mask readbacks pass; 5 refusals (next-slot CPU, reference CPU, empty, overlapping masks, count); nice readback kept (2); AST parity with the frozen slot evidence; evidence literal == 04 l00 record; MHz window (3); error outside a check |
| `tests/fake_frozen.py` | `fake["layout"]`, `fake["warmup_seconds"]` (default 0.2 s for the sub-second hold), `fake["exit_fails"]`; the fake `compare_mhz` refuses < 2 rows like the frozen one |
| `tests/mutate.py` | PF01–PF12 and NULL N12 (`test_r7.py`) |

The canonical bootstrap region is byte-identical to r6 (region SHA compared by command). `safe_input.py`,
`k4s_end_host_tool.py`, both wrappers, the verifier, the host program and the builder are byte-identical to r6.

### Class table (`CLASS-TABLE-PF4.md`)

| Verdict | Rows |
|---|---|
| SAME | 18 |
| STRICTER | 15 |
| LOOSER | 0 |
| S5-ONLY | 18 |
| **Total** | **51** |

- Every STRICTER row is kept with a ruling (S5-F1/F2, P2-1, P2-4, RC-2/3/6/7/9, frozen-reader, `fleet_profile.py:13`), except C15, which is fixed.
- The dynamic-state assumptions (OS readbacks, file existence and permissions, process tables, clocks, environment, loaded modules) have their own section.
- `pf4-evidence/loaded-modules-scan.txt` is the offline proof that `loaded_modules_check` (never run on a host) cannot refuse the production run:
  - all 4052 runtime `.py`/`.so` files are pinned;
  - safe_input refuses only 8 `*_games.py`, and none of them is importable from the END chain.

### Operational flags

1. The 04 `-pf00` guard job now holds 04 l00's side files. A 04 l01 on that bundle refuses at `guard_job_fresh` (RC-3), so 04 l01 needs a fresh `-pf01` guard job and bundle.
2. The 04 sshd-count login check can be tripped by a pre-auth sshd fork. It is kept under RC-2/RC-7; recorded for the coordinator.
3. A 04 hold of exactly 900 s is never binding; 1200 s is in use.

### Tests (r7, `TEST-RUN-r7.txt`)

In a scratch copy with `s3s9s10-r6` (the sibling the contract tests name) and `s3s9s10-r8` beside it. The scratch tree
was byte-for-byte unchanged before and after, with 0 `.pyc`.

| Interpreter | normal | `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **759 passed** | **704 passed, 55 skipped** |
| `/usr/bin/python3` 3.8.10 | **759 passed** | **704 passed, 55 skipped** |

759 = r6's 744 + 15 (`test_r7.py`). The `-O` skips are the verifier's 55 (it refuses `-O`).

### Mutation (r7)

`tests/mutate.py --only PF01 … PF12 N12`, the r5 method: a `/dev/shm` copy, re-pinned, named tests with `-O -B -x`.
- py3.12 `-O`: **12/12 killed, N12 survived** (`MUTATION-RESULTS-r7-py312-O.json`).
- py3.8 `-O`: **12/12 killed, N12 survived** (`MUTATION-RESULTS-r7-py38-O.json`).
- Each mutant was killed by its intended test (the tails are in the JSON).

### r7 open items

1. The host step is a one-file replace of `<base>/tools/k4s_end_preflight.py` (PF-4 item 3), and the S10 `TOOL_PINS` re-pin. Both belong to the runner, from `TOOLS-FINAL`.
2. Sol reviews the r7 diff, the class table and the host script as one package (PF-4 item 4).

## r8 (2026-10-14T02:14:50Z, runner; Sol PF4-r1 F1 + PF-4 ruling N2)

- F1: `mhz_comparison` fails closed on a binding hold with fewer than 2 post-warm-up rows (frozen fleet_profile.py:59-62 refuses); only a diagnostic hold records `unavailable`; `verdict()` requires a passing MHz comparison for binding/qualifying. Tests in tests/test_r7.py (`test_pf4r8_*`); mutants F1-01..03 killed (MUTATION-RESULTS-r8-F1.json).
- N2: the 04 check is `sshd_count_growth_during_hold` (S5 summary, verify-received, S7 gate message), described as sshd-count growth, not login.
- Pins: preflight 09d747ac (79878 B), S7 PREFLIGHT_SHA256 re-pinned (tests/repin.py), TOOLS-FINAL preflight row. CLASS-TABLE-PF4.md C20/D5 rows and counts corrected.
