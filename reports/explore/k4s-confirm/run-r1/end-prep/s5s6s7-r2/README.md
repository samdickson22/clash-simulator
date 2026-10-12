# K4S END S5 / S6 / S7 candidates r2: preflight, exit-push + verifier, launch gate on safe_input

- **Status: CANDIDATES for Sol review (package 2 r2 / r4 adoption). Nothing here has been run against any host.**
  No SSH was made, nothing was committed or pushed, and no existing directory was edited: this directory is a new
  copy of `s5s6s7-r1/` (`cp -a`), changed in place.
- **Written:** 2026-10-12, about 21:30–22:45Z, on 127x05.
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
- **Finding → change map:** [RESPONSE-r1.md](RESPONSE-r1.md). Resume log: `../r4-s5s6s7-PROGRESS.md`.

## safe_input pin

**Final pin: safe_input r3** — `safe_input.py` SHA-256 **`806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00`**,
`constants_fingerprint()` **`33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592`**, byte-identical to
`end-prep/safe-input-r3/safe_input.py`. Development and the first mutation campaign used r2 (`f9ca4926…`, fingerprint
`6661ca0b…`); at the end `safe-input-r3/PROGRESS-r3.md` said DONE and `sha256sum -c SHA256SUMS` in `safe-input-r3/`
verified every file (all OK; every file listed except SHA256SUMS itself), so the pin was switched to r3 and every test
and both mutation campaigns were re-run on the r3-pinned package (results below are r3). r3 changes nothing S5/S6/S7
call (E5 only; API additions are optional parameters).

Every component loads the vendored `safe_input.py` from its own directory through a stdlib bootstrap (canonical path,
`O_NOFOLLOW`, regular, `st_nlink == 1`, exact size, SHA-256 equal to the pin) and then requires
`si.constants_fingerprint()` to equal the pin, before any other read. The S7 host program receives the same bytes
inside its stdin program and checks the SHA-256 on the host before `exec`. No component carries its own name list,
gate, git wrapper or bounded-subprocess helper any more.

## Files (full SHA-256 in `SHA256SUMS`)

| File | Role |
|---|---|
| `safe_input.py` | The shared layer, byte-identical vendored copy (see pin above) |
| `k4s_end_host_tool.py` | **New.** Host-side helpers on safe_input: names-only END registry listing, the RC-5 registry snapshot, frozen-reader clone checks and git environment, the pinned bootstrap loader, and the CLI the wrappers use (`si -- create-excl/publish-excl`, `registry-snapshot`, `frozen-exec`) |
| `k4s_end_preflight.py` | **S5** on-host preflight (`run`) and the 05 `verify-received` |
| `k4s_preflight_push.sh` | **S5** foreground runner + post-exit push for the preflight |
| `k4s_end_exit_push.sh` | **S6** K4S delta of T1 `end_exit_push.sh` 0a87166f |
| `k4s_end_verify_push.py` | **S6** K4S delta of T1 `end_verify_push.py` 753722c9 |
| `k4s_end_launch_gate.py` | **S7** 05 side: RC-6, argv, RC-9, the one SSH session, the receipt, `admission` |
| `k4s_end_launch_remote.py` | **S7** host program body (shipped with safe_input + host tool) |
| `quiet-read-v3.cmd` | Approved quiet read, byte copy of `rounds/r4/quiet-read-v3.cmd` (a293207e) |
| `t1-originals/` | T1 bytes the S6 diffs are taken against; `detach.sh` 1648dfdc is used unchanged |
| `diffs/` | S6 vs T1, preflight wrapper vs S6 wrapper, and every file vs `s5s6s7-r1` (`r1-to-r2/`) |
| `tests/` | Offline suites, generated host shims, `repin.py` (pin chain), `mutate.py` (mutation driver) |
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
| 4 | `guard_repo` | frozen-reader ruling: the guard job's `repo/` passes `verify_clone` (si static git preflight, no `refs/replace/`, hooks only `*.sample`), then Q3 `git cat-file -e` of b2f9e25e and ce042b97 through `si.git_run` |
| 5 | `repository_clone` | the `--repository` clone passes `verify_clone` |
| 6 | `frozen_git_env` | the global git config files pass safe_input's config gate; inherited `GIT_*` removed; the P2-4 git keys + `GIT_CONFIG_PARAMETERS` set for everything frozen code spawns |
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
(`clasher.k4s.end-preflight.v2`) exports:

- `mode`: **binding** only if reference-slot work ran (> 0 states), every background slot became ready
  (= slot_count − 1) and the measured loaded guard span ≥ 60 s (03) / **900 s (04)**; otherwise **diagnostic**
  (`--no-reference-work` is always diagnostic). `qualifying` = passed and binding.
- `load` (slot_count, background slots expected/ready, reference work, states worked) and `duration` (requested,
  measured, required).
- `bus_band` of the loaded cumulative bus %: `proceed` (≤ 0.3), `coordinator-decision` (between), `stop` (≥ 0.7),
  `unavailable`; `bus_gate` = the band on 04 (`not-gated-on-127x03` on 03).
- `passed` requires every check, an empty and unchanged attempt parent, an unchanged registry, guard sources copied
  through the descriptor gate, and on 04 no sshd increase during the hold.

### 05: `verify-received`

`python3 -I k4s_end_preflight.py verify-received --receive <RUNNER>/preflight-received/<host>/preflight-<host>-lNN`
(05, not -O): everything through safe_input — PUSH-FAILED absent, metadata files through the descriptor gate, exit ⇔
transfer marker (`TRANSFER-DONE.json`), seal SHA, scope, a `walk_tree` whose role allows exactly the sealed names
(an extra, aliased, symlinked or outcome-named file refuses), every file SHA. Writes `PREFLIGHT-VERIFIED.json`
(`clasher.k4s.end-preflight-verified.v2`, exclusive) with mode, qualifying, load, duration, bus band/gate, inputs,
`receipt_manifest_sha256`, `preflight_result_sha256`. That document is S7's RC-9 input.

---

## S6: exit-push wrapper and verifier deltas

### `k4s_end_exit_push.sh` (diff vs T1: `diffs/k4s_end_exit_push.sh.diff`)

- **No shell redirection writes any file** (test `test_wrapper_sources_have_no_writing_redirection`). `argv.nul`,
  `exit.json` (via `.tmp` + `publish-excl`), `TRANSFER-DONE.json` and `PUSH-FAILED.json` are created by
  `python3 -I -S <tools>/k4s_end_host_tool.py si -- create-excl|publish-excl` (O_EXCL, no-follow, canonical
  symlink-free job root; an existing or hard-linked name refuses; nothing is truncated or replaced; `set -o pipefail`,
  every status checked). The host tool's SHA is checked (`sha256sum --check`) before first use; it loads safe_input
  through the pinned bootstrap.
- Pre-checks: attempt name `end-<host>-rRR-lNN` matching `--round`; parent exactly `<base>/attempts`; every metadata
  name absent (no file, no dangling link); `detach.log`/`detach.json` regular, not links.
- The END command runs through `frozen-exec`: the `--repository` clone is verified (frozen-reader ruling) and the
  command is `exec`ed with inherited `GIT_*` removed and the P2-4 git environment set. The argv recorded in
  `argv.nul` is exactly `"$@"`.
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
with schema v2, scope, host/attempt/receive, provenance (re-hash of the sealed `receipt-manifest.json` and
`preflight-result.json`), passed/no failed check/registry and attempt parent unchanged and empty, **mode binding +
qualifying**, the full reference load and the measured duration, 04 no login, input binding to RC-6 (runtime,
repository, manifest, bundles, guard job, layer SHA) and, for the launching host, to this argv's evidence and SD1
SHAs. **04 bus:** `proceed` passes; `coordinator-decision` needs a pinned `BUS-DECISION-<preflight>.json`
(`decision: proceed`, coordinator ref, bound to that preflight's seal); `stop`/`unavailable` refuse ("STOP before any
claim"), for a launch on either host. **04 END:** 03's `DURABLE-ACK.json` (schema v2, SEALED, complete,
`c_d_satisfied`, `verified_epoch ≥ exit_epoch + 1300`, seal re-hash) and 03's RC-7 `ADMISSION.json`
(`closed_before_admission: true`).

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
| 11 | frozen-reader | bundle `tiers-pins.json` with its declared SHA → guard job = the declared one, fresh; `--repository` and guard `repo/` pass `verify_clone`; Q3 commits; global git config |
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

Final matrix on 127x05 (`TEST-RUN.txt`), every run `nice -n 19`, `-B`, `PYTHONDONTWRITEBYTECODE=1`,
`-p no:cacheprovider`; pytest 8.3.5 for 3.8 installed only into `/dev/shm/s567r2-pytest38` (no venv modified):

| Interpreter | normal | `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **276 passed** | **254 passed, 22 skipped** |
| `/usr/bin/python3` 3.8.10 (host python) | **276 passed** | **254 passed, 22 skipped** |

The 22 `-O` skips are the verifier's tests (it refuses `-O` at import, T1 R3-1; the refusal itself is tested). The
only `-O` warning is pytest's `PytestConfigWarning` about asserts; the suites use explicit `ok()`/`raises()` checks,
never `assert` (r1's suites used `assert`, so r1's `-O` runs proved less than they appeared to). Per file:
host tool 26, S5 64, S6 wrapper 50, S6 verifier 23, S7 109, pins 4. The S7 host program always runs under
`/usr/bin/python3` 3.8 (the hosts' python).

| File | Coverage |
|---|---|
| `test_host_tool.py` | registry listing (absent/present, unexpected names refused before stat, hard-linked claim, symlinked `end/`), snapshot (exclusive copies, canary untouched), `verify_clone` (replace refs, alternates, grafts, filter, hooksPath, non-sample hook), Q3 commits, frozen env (scrub, and a raw-git positive control: replace refs and repo hooksPath are neutralised), global config gate, pinned loader (symlink, hard link, SHA), CLI create-excl (**hard-linked argv.nul canary never truncated**, symlinked job root, wrong node, tampered layer) |
| `test_s5_preflight.py` | refusals; **production anchor and closure equal the manifest of record** (pinned git read); layout; **S5-F1 probes** (unanchored manifest, tampered closure file, ancestor symlink, hard link: canary end_reference never executes; positive control shows it would); S4 stamps; bundle hard link; native symlink; existing output; frozen-reader (replace ref, missing seed commit, alternates, env before import); binding happy path (order, mode, load, duration, seal); diagnostic; **04 bus bands proceed/decision/stop**; short hold = diagnostic; 04 login; sealed failures; cleanup never masks; registry write; non-empty attempt parent; guard not fresh; hard-linked guard side file; loaded-module closure; AST no-claim; verify-received happy/exclusive and 9 refusals |
| `test_s6_wrapper.py` | 17 refusal cases; attempt-name form; **Sol S6-F2 probe for 7 metadata names**; aliases planted during the run; symlinked job and tampered tool; complete (push set, 0444 single-link files, frozen env seen by the command); failed/preclaim/claim-only; round 1 on 04; push failure; **hard-linked registry claim never pushed**; replace ref stops the command; preflight wrapper refusals, run, hard-linked argv.nul; no redirection in either wrapper |
| `test_s6_verifier.py` | -O import refusal; SEALED via `main` (ACK fields, exclusive); **C-d**; failed/preclaim/claim-only; **Sol S6-F1 registry hard-link alias**; **games/ member**; 14 refusals (extra file, D3 hard link and SHA, member SHA and symlink, seal, wrapper, argv, PUSH-FAILED, listing SHA, extra/undeclared registry name, proof, scope); prepare exclusive + aliased base |
| `test_s7_gate.py` | end-to-end END and preflight launches; non-empty preflight receive dir; **Sol S7-F1 base-symlink probe**; **S7-F2 failed ps with a valid table (rc 37)**; failed hostname with valid stdout; 23 host refusals (quiet, timers, stamps, who, sshd, C5 own/parent nice, tool pin and hard link, guard not fresh, grafts, filter, seed commit); allowlisted timer; helper change; existing job; registry limits with the pinned ruling; host registry hard link; local ControlMaster; **RC-9: 14 receipt validations incl. schema-less Boolean doc, diagnostic, 0.8 %/stop, unavailable, missing decision**; bus decision; evidence binding; **04 needs 03 complete + C-d + RC-7** (7 cases); 04 happy; local refusals; tampered quiet/host program; RC-6 (9 cases); END argv (29) and preflight argv; diagnostic launch; parsers; admission |
| `test_pins.py` | `repin.py --check`; vendored layer byte-identical + fingerprint; T1 originals, quiet, detach; shared constants |

Test-only routes (explicit, never reachable from a CLI): synthetic `K4S_MANIFEST_SHA256`/`FROZEN_CLOSURE`/
`SEED_COMMITS`/minimum holds in `s5_fixture.py`; `si.END_BASES`/`Q4_GUARD_PARENTS`/`D3_RECEIVE_BASE` and the 05 bases
pointed at tmp; `os.uname` for the fake host (the generated `fakepy.py`/`fake_remote.py` interpreters do only that);
`G.optimized` in the S7 site (the real `-O` refusal has its own test). Passing under `-O` with these overrides is not
evidence that production S5/S7 allow `-O`: both refuse it.

### Mutation

`tests/mutate.py` (74 mutants over every adoption point and new gate + 6 NULL controls): each mutant is applied
to a fresh copy in `/dev/shm/s567r2-mut-*` (each edit target must occur exactly once, `--check-edits`), the copy is
**re-pinned** so that the SHA bootstraps load it, and the named test files run with `-O -B -x`; `test_pins.py` is
never included, so no mutant is killed by a pin alone. Kills were checked to be test failures (FAILED lines), not
import or syntax errors. The 8 verifier mutants (V01–V08) and the NULL control that includes the verifier run without
`-O`, because the verifier refuses `-O` at import by design.

| Campaign (r3 pin, package SHAs recorded in the JSON) | Killed | NULL survived |
|---|---|---|
| 3.12.12 -O (`MUTATION-RESULTS-py312-O.json`) | **72/74** | 6/6 |
| 3.8.10 -O (`MUTATION-RESULTS-py38-O.json`) | **72/74** | 6/6 |

Not killed, documented as equivalent (`EQUIVALENT` in `mutate.py`): **P14** (`reference_slot_work` and
`mode_requested` derive from the same `--no-reference-work` argument) and **P22** (verify-received's set equality is
implied by the exact-names walk plus the per-file hashing). **Disclosed history:** the first campaign (r2 pin)
killed 61/74; the 11 non-equivalent survivors were real test gaps (anchor vs closure, closure table, receipt
production/status, bundle SHA, runtime name, pf/rd forms, sample minimum, sealed-member bytes, frozen manifest binding,
non-empty preflight receive dir, own-process nice). Tests were added for each, the 13 were re-run (11 killed, P14/P22
survived), then the pin was switched to r3 and both final campaigns above were run.

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
6. The frozen env does not change `HOME`: git 2.25 ignores `GIT_CONFIG_GLOBAL`, so `~/.gitconfig` and the XDG git
   config are statically checked with safe_input's config gate (sections/keys only, values not interpreted) and the
   code-running keys are overridden by `GIT_CONFIG_PARAMETERS`. A promisor (partial-clone) setting on a host clone is
   not refused (lazy fetch is disabled: `GIT_NO_LAZY_FETCH=1`, `protocol.allow=never`).
7. Accepted TOCTOU residual (16:00Z / 18:19Z): a same-size in-place rewrite between a check and a later open by
   another local actor. Reads of files this run itself produced (frozen monitor outputs, the received seal before
   it is verified, `assembly-receipt.json`) have no prior SHA; they are bound afterwards (seal, verified manifest SHA).
   Wrapper: between the `sha256sum` check of the host tool and the interpreter opening it.

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
