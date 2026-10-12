# K4S END S5 / S6 / S7 candidates (r1): preflight, exit-push + verifier deltas, launch gate

- **Status: CANDIDATES for Sol review. Nothing here has been run against any host.** No SSH was made, nothing was committed or pushed, and no existing file was edited.
- **Written:** 2026-10-12, about 15:30–16:10Z (`date -u` 16:02:11Z and 16:09:20Z), on 127x05.
- **Repository bytes:** read from origin/main `3845af98` via `git show`, into a scratch copy in `/tmp/s5s6s7-src/`.
  - I re-checked at `1aa63a16e`. None of the frozen inputs changed.
  - That commit added the coordinator's 15:41Z rulings Q2–Q6/Q9, END plan v2, the B3 assembler and design, and Sol's END-PKG1 r1 review. They are folded in as follows:
    - the host bases follow B3/Q4;
    - S5 runs the Q3 `git cat-file -e` check first;
    - S5 verifies pins with the stdlib *before* importing anything (Sol's S2 finding).
- **Read boundary:** I never opened a game file, a `games/` directory, `complete.json`, reducer or verifier output, or an outcome field. The only "result" data the tests read are synthetic.

## Files (full SHA-256 in `SHA256SUMS`)

| File | Role | SHA-256 (prefix) |
|---|---|---|
| `k4s_end_preflight.py` | **S5**, on-host preflight (`run`), plus the 05-side `verify-received` | 65d37c75 |
| `k4s_preflight_push.sh` | **S5**, foreground runner and post-exit push for the preflight (derived from the S6 wrapper) | e3f1da6f |
| `k4s_end_exit_push.sh` | **S6**, K4S delta of T1 `end_exit_push.sh` 0a87166f | 62cdda77 |
| `k4s_end_verify_push.py` | **S6**, K4S delta of T1 `end_verify_push.py` 753722c9 | d7f2fec4 |
| `k4s_end_launch_gate.py` | **S7**, 05 side: validation, the one SSH session, the receipt, `admission` | 89953655 |
| `k4s_end_launch_remote.py` | **S7**, host side: sent over stdin to `/usr/bin/python3 -I -B -` | cde4644a |
| `quiet-read-v3.cmd` | Approved quiet read, a byte copy of `run-r1/rounds/r4/quiet-read-v3.cmd` | a293207e |
| `t1-originals/{end_exit_push.sh,end_verify_push.py,detach.sh}` | T1 bytes the diffs are taken against; `detach.sh` is used unchanged | 0a87166f / 753722c9 / 1648dfdc |
| `diffs/*.diff` | S6 unified diffs against T1, plus the preflight wrapper against the S6 wrapper | — |
| `tests/` | Offline pytest suite, with PATH shims in `tests/shims/` | — |
| `TEST-RUN.txt` | Output of the last test run | — |

**Pins between files:**
- The gate pins the SHAs of the S6 wrapper, the preflight wrapper, `k4s_end_preflight.py`, the host program, frozen `detach.sh` 1648dfdc and quiet-read v3.
- The verifier pins the S6 wrapper SHA.
- `tests/test_pins.py` fails if any of these drifts.
- **Any edit to one of these files means re-pinning, which changes the gate's SHA.**

## 0. Proposed host layout (it MUST equal the RC-6 roots declaration)

These are hard-coded constants, identical in the two wrappers and the gate; `test_pins` enforces that.

| | 127x03 | 127x04 |
|---|---|---|
| base | `/mpac/sdicks02/jobs/clasher/k4s-end-r1` | `/mpac/sdicks02/jobs-k4s/k4s-end-r1` |
| END attempt parent | `<base>/attempts` | same |
| preflight parent | `<base>/preflight` | same |
| `--repository` clone | `<base>/repository` | same |
| runtime | `<base>/runtime` (= B3 DESIGN `runtime_root`) | same |
| guard jobs | B3: `/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rdRR-aNN` | `/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rdRR-aNN` |
| 05 receive | `/mpac/sdicks02/k4s-runner/run-r1/end-received/<host>/<attempt>` and `…/preflight-received/<host>/<attempt>` | same |

**Why these choices:**
- The plan draft's base name `k4s-confirm-end-r1` was dropped because it matches B3's forbidden `k4s-confirm-*` pattern.
- 04 never uses `/mpac/sdicks02/jobs/clasher/`, which is 04's perception root according to B3.

**Attempt names.** These are the launch index (`lNN`), not the claim index, because a pre-claim refusal makes no claim:
- END: `end-<host>-r<RR>-l<NN>`
- preflight: `preflight-<host>-l<NN>`

**`--out` is `<job>/<attempt>`.** The claim records only `basename(--out)` (`end_evidence.py:504`). If T1's fixed name `measurement` were reused, every attempt would get the same `receipt_directory`, and two attempts would collide under `end/receipts/round-RR/<host>/<dir>/` (END-RUNBOOK operator step 4).

---

## S5: on-host END preflight (`k4s_end_preflight.py run`)

### What it runs, in order

Every step is a recorded check with UTC start and finish times, a source citation, and pass or error.

**Before any runtime module is imported (stdlib only):**

| # | Check | What it does |
|---|---|---|
| 0 | `guard_repo_commits` | Reads `guard.job` from the bundle's `tiers-pins.json` as JSON. Runs `git -C <guard job>/repo cat-file -e <commit>^{commit}` for b2f9e25e… and ce042b97… (ruling Q3; `t1/parent_source_seed.py:62-69` runs `git show` there only after the claim) |
| 1 | `pre_import_pins` | Checks the K4S manifest bytes against `--k4s-manifest-sha256`, then each of the six END sources (`k4s_logic.END_MEASUREMENT_FILES`) against the manifest's `end_files`/`k4s_files` pin. Each must be a regular, non-symlinked file inside the runtime |
| 2 | `frozen_import` | Imports `end_reference` and then `end_background` from the runtime (`end_reference.py:56-61, 285-288`). Requires that every loaded module file is one of the verified paths |

**Then, in `end_reference.reference()` order:**

| # | Check | Source | What it does |
|---|---|---|---|
| 3 | `frozen_helpers` | `:289-291` | `evidence_spec`, `frozen_helpers` (K4S manifest and e4v3 helper pins, verified before import) |
| 4 | `frozen_identity` | `:96-110, :292-294` | The frozen `tier_backend.validate_bundle` (fleet-reference profile); native, corpus, kernel, scorer, SD1 and END-source pins; executing sources |
| 5 | `bundle_parity` | RC-3 | Only with `--compare-bundle <attempt bundle>`. The two manifests must be identical except `reference_load_profile.guard.job`, and the guard jobs must differ |
| 6 | `guard_job_fresh` | | None of the four guard side-files and no `STOP`/`STOP-<host>` in the preflight's own guard job |
| 7 | `reporting_profile` | `:297-301` | `FrozenHooks.host()`, then `k4s_reporting_profile`: committed evidence, plan, `slot_layout` with the **live nice, which must be 10**, and `host_reporting` |
| 8 | `physical_cpus` | `:302-304` | `validate_physical_cpus` and the reference-slot affinity |
| 9 | `end_job_read_only` | `:305` | **Skipped by default**, because RC-2 runs before the END-JOB exists. With `--end-job-sha256` it calls the frozen `end_job`, which only reads git |
| — | **never** | `:307-311` | `pool_context`, `producer_claim`, `K4SStore(REFERENCE_SCOPE)` |
| 10 | `backend_and_corpus` | `:159-165, :326-328` | `backend(a)` (native, models, pickles) and `check_corpus` |
| 11 | `topology` | `:333` | `validate_topology(manifest["topology"], cpu_counters(), darwin=False)` |
| 12 | `guard_admission` | `:334-365` | Spawns the frozen `fleet_reference.reference_monitor`. That builds the T1 `ReportingGuard` and runs `checkpoint("admit")`, including `parent_source_seed.admit` |
| 13 | `background_ready` | `:366-374` | `K4SFleetBackground` spawns every background slot and waits for readiness. Each slot's affinity and nice are read back; nice must be 10 and the masks must be the pinned ones |
| 14 | `loaded_hold` | `:375-387` | **Default:** the END warm-up loop verbatim (`k4s_work` in the reference slot with results discarded; 50-state guarded `warm-…` blocks) for `--hold-seconds`. **With `--no-reference-work`:** background load only, in guarded `--block-seconds` idle blocks. Requires at least `--min-samples` (≥ 60) 1 Hz guard rows after admission |
| 15 | `monitor_stop` | `:392-394` | |
| 16 | `frozen_guard_validators` | `:395-399` | `validate_census`, `validate_admission`, and `validate_blocks(require_measurement=False)` |
| 17 | `mhz_comparison` | `:400-403` | The frozen `compare_mhz` on the hold rows, relabelled `reference-speed`. **A gate only when reference work ran**; otherwise it is informational |
| 18 | `post_pins` | `:404-406` | `validate_bundle`, the native SHA and executing sources again |
| 19 | `cleanup` | `:252-279` | The frozen `cleanup_steps`. A cleanup failure is recorded but never replaces a primary failure |

**Pieces it cannot reach without the claim, and what it does instead:**
- The `checkpoint`/`guarded`/`check_monitor`/`set_phase` closures (`end_reference.py:338-362`) exist only inside `reference()` after `producer_claim`. They are **copied line for line** into S5. This is the minimal reviewed alternative; each copy cites its source line.
- Everything else is a module-level function and is called directly.
- **Not exercised at all:**
  - `measure()`, meaning deadline mode, the 1/c sleep charge and the K4S==K4 exactness check;
  - `run_attempt`, `end-raw` and the REFERENCE_SCOPE seal;
  - `producer_claim` and `pool_context`. Their failures happen *at* the claim and are pre-claim refusals, not strikes; `pool_context` applies only to round > 0.

### Output and pass rule

**Output:**
- One fresh directory (`--out`, which must not exist), sealed with scope **`K4S-END-PREFLIGHT`**. It uses the same seal format as `K4SStore`, but is written by a stdlib store, so refusals before the import are sealed too. The pool's `SealedReceipt` requires `K4S-END-REFERENCE`, so it can never accept this directory.
- Contents: `capacity.jsonl`, `guard-admission.json`, `guard-blocks.jsonl`, `guard-sources/` (the preflight guard job's side-files), and `preflight-result.json`.
- `preflight-result.json` (`clasher.k4s.end-preflight.v1`) holds:
  - every check;
  - the slot read-back;
  - names-only listings of the registry and attempt parent, taken before and after;
  - **health-only summaries**:
    - bus: cumulative over the whole run and over the hold, with windows of 1/10/30/60/300 s scored by the frozen integer rule `ticks*100 > hz*dt`, and the RC-2 band (≤ 0.3% proceed, ≥ 0.7% coordinator re-rules, otherwise between);
    - per-block guard results;
    - per-core and occupied-mean MHz;
    - sshd process counts per 1 Hz row;
    - guard reasons.

**Pass** requires all of the following:
- every check passed (or was skipped by design);
- the registry root and attempt-parent listings are unchanged;
- **on 04**, no sshd-process increase during the hold (no login).

The RC-2 bus band is **reported, not gated**. The coordinator decides.

**Exit codes:**

| Code | Meaning |
|---|---|
| 0 | passed; sealed `passed` |
| 1 | failed; sealed `failed` |
| traceback, nothing written | refused before the store: wrong host, nice ≠ 10, not SCHED_OTHER, `-O`, hold < 60 s (03) or < 900 s (04), `--min-samples` < 60, block seconds outside [1, 300], `--out` exists or overlaps the attempt parent, repository, runtime, bundle or compare-bundle |

### Exact on-host usage (after Sol review and coordinator authorization A4)

**1. Staging** (other reviewed steps; S3/S4):
- the runtime;
- a **preflight bundle**, built by the B3 assembler from the same request as the attempt bundle except `guard.job`;
- a fresh **preflight guard job** whose `repo/` is a git clone holding b2f9e25e and ce042b97 (Q3). **Open:** B3's `JOB_NAME` has no preflight form; see Q3 under "Open decisions" below;
- `<base>/preflight/` and `<base>/attempts/` exist;
- staged under `<base>`: frozen `detach.sh` (1648dfdc), `k4s_preflight_push.sh` (e3f1da6f…) and `k4s_end_preflight.py` (65d37c75…), for example in `<base>/tools/`.

**2. 05:** prepare an **empty** `/mpac/sdicks02/k4s-runner/run-r1/preflight-received/<host>/preflight-<host>-l00/`.

**3. Pinned argv** (JSON list; its sha256 is that of the NUL-joined argv):

```
nice -n 10 taskset -c 61 bash <base>/<detach.sh> <job>/detach.log <job>/detach.json \
  bash <base>/tools/k4s_preflight_push.sh <job> \
  env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 [PYTHONPATH=…] <venv python> -B \
  <base>/tools/k4s_end_preflight.py run --bundle <preflight bundle> --runtime-root <base>/runtime \
  --native <native> --corpus <K4 states.pkl> --corpus-inventory <corpora.json> \
  --k4s-manifest-sha256 74314eda… --sd1-manifest-sha256 <SD1> --end-evidence <bundle>/k4s-end-evidence/end-evidence.json \
  --end-evidence-sha256 <S> --repository <base>/repository --attempt-parent <base>/attempts \
  --compare-bundle <attempt bundle> --hold-seconds 120 (03) | 960 (04) \
  --out <job>/preflight-<host>-l00
```

Here `<job>` = `<base>/preflight/preflight-<host>-l00`.

**4. Launch** with S7: `k4s_end_launch_gate.py launch --kind preflight …` (see S7). That is one SSH session, and it ends a few seconds after the detach.

**5. No SSH to the host** until the push arrives:
- 03: hold + model load, about 5–10 min;
- 04: at least 15 min hold + load, and **no login at all**.

The preflight wrapper pushes `exit.json`, `detach.*`, `argv.nul`, `preflight/` and `TRANSFER-COMPLETE.json` to 05. Its `exit.json` also records the registry-root and attempt-parent listing hashes from before and after.

**6. 05:** `nice -n 19 taskset -c 63 python3 -I k4s_end_preflight.py verify-received --receive <dir>`. It checks:
- the seal, every file SHA, and that there are no extra files or symlinks;
- no `PUSH-FAILED`;
- that the transfer marker matches `exit.json`;
- that the registry and attempt-parent listings are unchanged;
- exit code ⇔ seal status ⇔ `passed`.

It writes `PREFLIGHT-VERIFIED.json` (exclusive) and exits 0 on pass and 2 on a sealed fail. That file plus its SHA is the `--preflight-verified` input to every END launch (RC-9).

**Logins per host for the preflight:** exactly **1** (the S7 session). The post-exit push is outbound, from the host to 05.

---

## S6: exit-push wrapper and verifier deltas

### `k4s_end_exit_push.sh` (diff: `diffs/k4s_end_exit_push.sh.diff`, +48/−15)

**Changes from T1:**
- host tuple 03/04, each with its own base;
- the attempt parent must be exactly `<base>/attempts` (RC-6);
- `--out` instead of `--output`, and it must equal `<job>/<attempt>`;
- `--repository` must be exactly once and equal `<base>/repository`;
- `--round` must be exactly once and match `0|[1-9][0-9]?`;
- the `--o*`, `--rep*` and `--ro*` forms (argparse abbreviations and `=` forms) are refused;
- the receive base is the 05 runner `end-received`;
- `exit.json` gains `registry_exists`;
- after exit, `<repository>/reports/explore/k4s-confirm/end/registry/round-RR/<host>/` is pushed to `<receive>/registry/` **whenever it exists, with or without a measurement directory** (RC-5).

Everything else is T1's bytes: no trap, polling or network call during the run; bounded transport only after exit; `PUSH-FAILED`.

**Exit codes:** 90 means refused (nothing run, nothing pushed). 91 means `argv.nul`/`exit.json` could not be written. 92 means the push failed (`PUSH-FAILED.json`). Otherwise it returns END's own exit code.

**Refusals (all tested):**
- wrong host;
- a job with a trailing `/`, `..` or whitespace;
- a parent that is not `<base>/attempts`, including 04 using 03's base;
- a symlinked job;
- an existing `<job>/<attempt>` or `exit.json`;
- a missing `detach.log` or an empty `detach.json`;
- an empty command;
- `--out` missing, repeated, wrong, in `=` form or abbreviated;
- the same for `--repository` and `--round`;
- `--round` values `07`, `100` or `-1`.

### `k4s_end_verify_push.py` (diff: `diffs/k4s_end_verify_push.py.diff`, +31/−5)

**Changes from T1:**
- `BASE` = `/mpac/sdicks02/k4s-runner/run-r1`;
- hosts 03/04;
- the wrapper SHA literal is the S6 wrapper;
- the seal `scope` must be `K4S-END-REFERENCE`;
- `exit.json` `registry_exists` must be a Boolean and agree with `<receive>/registry/`;
- the pushed registry must be exactly `attempt-00…NN.json`, regular files, with each claim's `host` and `attempt` index matching;
- at most one claim may name this attempt's `receipt_directory`.

**What it records:**
- `registry_claims` (name, SHA, attempt, round, `receipt_directory`, `launched_utc`);
- **`claim_without_receipt`**: true when this attempt has a claim but no sealed receipt.

**SEALED (ACK) additionally requires** that the receipt's sealed `attempt-claim.json` has `claim_sha256` equal to the pushed claim file's SHA and the same claim.

**Kept from T1:** `--prepare`, the C-a pinned proofs, `-O` refused at import, 05/nice 19/CPU 63, and the exit codes (0 ACK, 2 UNSEALED, nonzero or traceback means REFUSE).

**Usage** is T1's C-a…C-d procedure, unchanged:
1. Before launch: `--prepare` the receive directory and commit the proof.
2. Verify no earlier than `exit_utc + 1300 s`, with `nice -n 19 taskset -c 63 python3 -I k4s_end_verify_push.py --receive … --launch-receipt <S7 receipt> --launch-receipt-sha256 … --prepare-proof <committed copy> --prepare-proof-sha256 …`.

---

## S7: launch and prelaunch gate (`k4s_end_launch_gate.py`)

### `launch` (on 05)

Run it as `nice -n 19 python3 -I k4s_end_launch_gate.py launch --host H --kind end|preflight --argv-json A --argv-sha256 S --quiet-cmd quiet-read-v3.cmd --receipt-out R [options]`.

**Options:**
- `--prepare-proof P --prepare-proof-sha256 S` (END);
- `--preflight-verified PATH:SHA` ×2 (END; both hosts);
- `--prior-03-ack PATH:SHA` (END on 04);
- `--second-attempt-ruling REF`;
- `--allow-timer UNIT.timer=justification` (repeatable);
- `--clearance-seconds` (default and minimum 7200);
- `--window-seconds` (default 7200, minimum 3600);
- `--dry-run`, which prints the composed host program and opens no session.

**Local checks on 05, before any session.** Each is a `GateRefusal` traceback with no receipt and no SSH:
- the gate runs on 127x05, not under `-O`;
- the receipt does not exist yet;
- argv bytes equal the pin;
- **argv structure:**
  - it starts with the frozen inner `nice -n 10 taskset -c 61` (no outer prefix);
  - it continues `bash <detach> <job>/detach.log <job>/detach.json bash <wrapper> <job>`, with detach and wrapper under the base;
  - `<job>` = `<declared parent>/<attempt name for this host>`;
  - then `env` with exactly OMP/OPENBLAS/MKL=1, plus an optional PYTHONPATH;
  - no `nice`, `taskset`, `chrt`, `ionice`, `setsid`, `sudo`, `renice`, `-O`, `-OO` or `-I` token after it;
  - an absolute python with exactly `-B`;
  - END: the runtime's `end_reference.py` with **exactly** the 13 required options (no `--kernel`/`--scorer`/manifest overrides), each once, with no abbreviation or `=` form, `--out` = `<job>/<attempt>`, `--repository` = `<base>/repository`, and `--round` matching the name;
  - preflight: the staged `k4s_end_preflight.py run`, `--attempt-parent` = `<base>/attempts`, and the RC-2 minimum hold;
- the quiet-read file SHA is a293207e;
- clearance and window minimums are met; `--allow-timer` entries are well formed;
- **receive directory:**
  - END: it holds only `PREPARED.json`, equal to the pinned proof; the proof names it and predates now;
  - preflight: it is empty;
- **RC-9 (END):** both hosts' `PREFLIGHT-VERIFIED` show passed with the registry unchanged; on 04, 03's `DURABLE-ACK` shows SEALED + `complete` + `ack_allowed`;
- **no ControlMaster to the host on 05:** `ssh -O check H` must fail. It only talks to a local control socket;
- the host program's SHA equals its pin.

**The one session:** `ssh -o ControlMaster=no -o ControlPath=none -o BatchMode=yes H /usr/bin/python3 -I -B -`, with the host program on stdin. In order, it runs:

| # | Step | Rule |
|---|---|---|
| 1 | `hostname` | must equal H |
| 2 | quiet-read v3 **#1**, verbatim (`bash -c <file bytes>`) | — |
| 3 | sleep 30 s | — |
| 4 | quiet-read v3 **#2**, verbatim | Each read needs rc 0; both apt units `inactive` or `failed` (`active`, `activating`, `deactivating` and `reloading` refuse); `maint=0`; `who=0`. The helper should be exactly the pinned PID (03 2368, 04 2296); **a change is recorded as `helper_changed`, not refused** |
| 5 | `TZ=UTC LC_ALL=C systemctl list-timers --all --no-pager`, **unfiltered**, raw output kept | Every `.timer` line's NEXT must be ≥ clearance away, unless the unit is allowlisted. `n/a` is fine. An unparseable line, zero timers or rc ≠ 0 refuses (RC-8) |
| 6 | Stamps | `release-upgrade-available` age ≤ 24 h − window; `updates-available` mtime > `/var/lib/apt/lists` mtime; a missing file refuses (C2 extension) |
| 7 | `who` | zero lines |
| 8 | `ps -eo pid=,ppid=,ni=,cls=,args=` | **Any `sshd: …` session process outside this session's own ancestry refuses.** That covers an open ControlMaster or a login from anywhere, any user. The listener is excluded |
| 9 | Staged-file SHAs | detach, wrapper and (preflight) script |
| 10 | Job | the parent exists and the job does not |
| 11 | END registry, names only | refuse any non-`attempt-NN.json` name; refuse at ≥ 2 claims; refuse at 1 claim unless `--second-attempt-ruling` (04 `op1_interference` ⇒ STOP; this applies to both hosts) |
| 12 | **C5 pre-exec gate** | This process and its parent have `ni` 0 and `cls` TS (SCHED_OTHER); argv sha256 equals the pin; argv starts with `nice -n 10 taskset -c 61` (no outer prefix) |
| 13 | Launch | `mkdir <job>`, then run the pinned argv once with stdin `/dev/null`. Frozen `detach.sh` returns after its PID receipt |
| 14 | Post-exec read-back | At most 10 s: the wrapper (detach PID) and its END/preflight python must have `ni` 10 and TS. This is recorded only. **No signal is ever sent** (C6). The `slot_layout` nice check inside END is the binding one |

The program prints one `__K4S_GATE_RESULT__ {json}` line and exits, which closes the session. An unexpected exception still prints the result, with `launched` and `job_created_utc` as they stood.

**The receipt** (`clasher.k4s.end-launch-receipt.v1`, exclusive) contains:
- everything above, including the raw quiet and timer outputs;
- `session_open_utc` and `session_close_utc` (05 clock);
- `utc` = detach `launched_at_utc` (host clock);
- `measurement_argv`, `launch_command` and `wrapper_sha256`, the keys the S6 verifier reads;
- `C5_preexec_gate` and `postexec`;
- `C5_no_further_SSH: true`. This is an attestation that this tool makes no further SSH call. It is **not** proof about other threads; that is the coordinator's C5 broadcast.

**Exit codes:**

| Code | Meaning |
|---|---|
| 0 | launched |
| 3 | refused on the host; nothing created |
| 4 | job created but the launch command failed |
| 5 | no host result: unknown host state. **STOP; do not relaunch** |
| 6 | launched, but SSH returned non-zero |

### `admission` (on 05, after the verifier ran at C-d)

`k4s_end_launch_gate.py admission --launch-receipt R --launch-receipt-sha256 S --out F`:
- reads only the sealed `guard-admission.json` `utc`, after checking its SHA against the seal manifest;
- records `seconds_close_to_admission` and `closed_before_admission` (RC-7);
- exits 0 if the session closed before admission and 2 otherwise;
- carries the caveat that the 05 and host clocks are not skew-corrected.

### Quiet read #1

It runs **inside** the same session, 30 s before #2. That avoids an extra login just before admission, which matters on 04. A separate earlier read is still possible with the approved command (`ssh -o ControlMaster=no -o ControlPath=none H "$(cat quiet-read-v3.cmd)"`), but the gate does not need it and it adds a login.

### Logins per host

- **Preflight:** 1.
- **Each END attempt:** 1.
- **Collection and verification:** 0, because the pushes are outbound.
- **Not counted here:** staging, the optional separate quiet read, and stale-stamp pre-trigger logins (A5).
- **The launch login itself runs `pam_motd`.** That is why the stamps must already be fresh. The gate's stamp check is a backstop: if a stale stamp has already spawned `check-new-release`, quiet-read #1/#2 see it as maintenance and refuse.

---

## Tests (offline)

`cd s5s6s7-r1 && nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python [-O] -m pytest -q -p no:cacheprovider tests/`

**Result (TEST-RUN.txt):**
- **normal: 155 passed;**
- **`-O`: 145 passed and 11 skipped.** The skipped tests are the verifier's, which refuses `-O` at import (T1 R3-1); under `-O` only that refusal is tested.
- The gate's `-O` refusal is tested by a real `python -O` subprocess. Under `-O` its logic tests patch that check out.

| File | Coverage |
|---|---|
| `test_s6_wrapper.py` (39) | A copy of each wrapper in which **only** the two base lines and the receive line are changed to tmp paths (asserted: exactly 3 changed lines). Shims for `hostname`, `rsync`, `timeout`, `nice` and `taskset`, with a fake producer using the frozen claim and seal formats. Covers every refusal path, plus complete, failed, pre-claim refusal, claim-only (registry pushed with no measurement), push failure (92), round-01 registry, the 04 base, and preflight-wrapper refusals and registry-change exposure |
| `test_s6_verifier.py` (13) | Real wrapper output fed to the verifier: SEALED complete or failed with the claim bound; UNSEALED with `claim_without_receipt` true or false; earlier claims listed; refusals for wrapper SHA, argv, proof, timing, claim tampering, a non-contiguous or duplicate claim, a missing pushed registry, extra files, scope, PUSH-FAILED, namespace and a missing `registry_exists` |
| `test_s5_preflight.py` (39) | Pure checks (refusals, isolation, parity, fresh guard job, window and integer bus rule, bus, sshd and MHz summaries, AST check that nothing claim- or measure-related is referenced), the pre-import pin and seed-commit checks (real `git` in tmp), and orchestration with **fake frozen modules**. The guard monitor is a **real spawned process** speaking the real checkpoint protocol. Covered: happy path and its check order; END-JOB and parity; idle hold; admission, block and background failures; slot nice read-back; MHz gate; registry write; 04 login; cleanup failure, and that it never masks the primary; `verify-received` and its refusals |
| `test_s7_gate.py` (61) | 05-side argv structure (27 refusal cases), receive, RC-9, host parsers (r4 quiet sample, timers, stamps, sshd ancestry), and **end-to-end launches** through a fake `ssh` that runs the host program under **/usr/bin/python3 3.8** with fake `ps`/`systemctl`/`who`/`hostname`/`nice`/`taskset`, the **real frozen detach.sh**, and a stub wrapper and script. Covered: happy END and preflight launches, 16 host refusals, allowlisted timer, helper change, existing job, registry limits, local ControlMaster, local refusals, the `admission` record, the host-program exception path and the `-O` refusal |
| `test_pins.py` (3) | T1 originals 0a87166f/753722c9/1648dfdc, quiet a293207e, every cross-file pin, and path agreement across the files |

---

## What remains unverifiable offline

1. **Every frozen module on a real host.** The S5 orchestration ran only against fakes. Not exercised for real:
   - `validate_bundle` with the real bundle;
   - the K4S manifest and pins;
   - `k4s_reporting_profile` with the real committed evidence;
   - torch/native/pickle loading;
   - `K4SFleetBackground` spawn and readiness;
   - T1 `ReportingGuard` construction and admission (`/proc` census, console users, `parent_source_seed.admit`'s `git show`);
   - `compare_mhz` on real rows.

   Real bus, MHz and sshd numbers exist only once it runs on the host. Whether the interpreter, venv and torch exist on 03/04 is unknown (plan §8.5).
2. **Whether the frozen import chain in the preflight's spawned monitor child hits the guard's import-collision check** (`fleet_validity.py:73`). The preflight's `__main__` imports only the stdlib, so it brings fewer modules into the child than END does. That is inferred from the code, not observed.
3. **Real SSH and OpenSSH 8.2 behaviour.** Unverified:
   - `ssh -O check` with the real `~/.ssh/config`;
   - that the session's process chain is `sshd: user [priv]` → `sshd: user@notty` → python (the ancestry and "other sessions" logic assumes these titles; another layout fails closed only if it adds unknown `sshd:` processes);
   - `pam_motd` effects.
4. **systemd 245's real `list-timers` format under `TZ=UTC`.** The parser was tested on synthetic lines modelled on the r4 evidence. A mismatch fails closed as "unparseable".
5. **Real rsync-over-ssh semantics,** including creation of `registry/` and `preflight/` on 05. These were shimmed with `cp`. T1 used the same pattern for `durable-measurement/`.
6. **Real priorities.** `nice` and `taskset` were shimmed, and `ni`/`cls` values faked by the `ps` shim. The C5 gate and read-back logic are tested; the kernel's values are not.
7. **That the session really closes before guard admission.** END's own startup (pins, evidence git reads, model load) must take longer than the ≤ 10 s read-back. This is recorded after the fact by `admission`, not enforced.
8. **Clock skew** between 05 and the host, for `admission` and the verifier's ordering checks. This is inherited from T1.

## Open decisions for Sol and the coordinator

1. **Paths and names (§0).** They must equal the RC-6 roots declaration. Changing them means editing the constants in both wrappers and the gate, then re-pinning.
2. **Launch-index attempt names** and **`--out = <job>/<attempt>`** (needed for unique receipt directories).
3. **Preflight guard-job name.** B3 `JOB_NAME` (`k4s-end-guard-r<N>[-rdRR-aNN]`) has no preflight form. Options: use an unsuffixed `k4s-end-guard-r<N>` for the preflight, or extend the assembler.
4. **Preflight hold default.** Reference-slot warm-up work is ON: it uses the END warm-up loop verbatim with results discarded, gives a full 11-slot load, and makes the MHz comparison a gate. `--no-reference-work` gives background-only load with the MHz comparison informational. Suggested hold: 03 ≥ 120 s; 04 ≥ 960 s (≥ 15 min plus margin).
5. **Second attempt on either host needs `--second-attempt-ruling`.** This is stricter than the runbook's mechanical 03 repeat. It implements "04 `op1_interference` ⇒ STOP" without reading `failure.json` on the launch path.
6. **Any other `sshd:` session on the host refuses the launch,** including other users'. That is conservative and may cost a window.
7. **Quiet "not active"** is interpreted as `inactive`/`failed` only. A helper PID change is recorded and not fatal, as the brief specifies.
8. **The host program uses `/usr/bin/python3`** (Ubuntu 20.04: 3.8). It does not use the END venv.
