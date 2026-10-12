# K4S END, blocker B3: the END guard job and the fleet-reference bundle (CANDIDATE b3-r3)

- **Status:** CANDIDATE r3 for an independent Sol review. Nothing here has been run against a host, staged on a host, or adopted.
  - r3 answers SOL-REVIEW-END-PKG1-r2 (S4: REQUEST_CHANGES; e347219d), maps each finding to a change in `RESPONSE-r2.md`, and implements the coordinator's E1–E3 exemption rulings (COORDINATOR `2026-10-12 16:55Z`, commit ab1715910).
  - r2 answered SOL-REVIEW-END-PKG1-r1 (`RESPONSE-r1.md`, kept).
- **Written:** all on 2026-10-12, by an offline implementer on 127x05.
  - r1 from about 15:26Z;
  - r2 stamped `2026-10-12T16:21:15Z`;
  - r3 stamped `2026-10-12T17:17:40Z` (`date -u`).
- **Sources (r3):** r3 read origin/main `fa32ab3f`, which contains ab1715910 (verified ancestor), through a temporary detached worktree in `/tmp`, removed afterwards.
  - Between 1aa63a16 and fa32ab3f, no file changed under the e4v3 directory, `reports/explore/k4s-confirm/*.py` (outside `run-r1/`), `plan.json`, FROZEN-T1, the T1 modules, the S1 receipts or the two `visualize_battle.py` entries. I verified this with `git diff --name-only`; the only changes under those pathspecs are under `run-r1/`.
  - `path:line` citations to frozen code are therefore unchanged.
- **Sources (r2):** r2 read origin/main `1aa63a16` (fetched at the start of r2; it carries the 15:41Z rulings `fa89baa9` and the 16:00Z scope ruling) through a temporary detached worktree in `/tmp`, removed afterwards. `path:line` citations to frozen code are unchanged from r1 (754c43cd); between 754c43cd and 1aa63a16 there is no change to the e4v3 directory, `reports/explore/k4s-confirm/*.py` and `plan.json`, the T1 modules and FROZEN-T1, or the two S1 receipts (verified with `git diff --stat`: the only differences under those pathspecs are new files under `run-r1/`); the test suite's `FROZEN_PINS` check passes at 1aa63a16.
- **Read boundary:**
  - Never opened: any `games/` directory, `complete.json`, reducer or verifier output, or any outcome field. The runtime-pin member `imitation/model/receipts/throughput-0935/complete.json` was **not** opened; its SHA is taken from T1's committed A3 manifests.
  - No SSH. No commits.
  - r3 writes only to this directory (`b3-r3/`, a copy of `b3-r2/`) and to `/tmp` scratch, which is removed.
  - r2 wrote only to `b3-r2/`.
  - r3's only new access to T1-owned files on 05 is `stat -c %h` (link counts) of the three Q6 files: all three are 1. The two Q6 tests still read the 353 KB index.
  - Read-only on 05, T1-owned: the three Q6 files in `t1-20261010-r1/end-a5-pool-context-20261012-r1/bundle/` were hashed (sha256sum); the 353 KB `states-rows.json` is read by one test; the `sets`/`files` fields of six T1 `tiers-pins.json` manifests on 05 were parsed (paths listed in `README.md`). `find` over the T1 tree pruned `games` and `complete.json`.
  - Committed health receipts were read: r4 host admissions (process rows), T1 idle-service admission 03, the T1 END A3/A5 receipts, FROZEN-T1.
- **Conventions:** **Inference** marks anything not read directly in code or bytes. "Verified" means checked in this session by a command or a test whose result is recorded here.

Deliverables in this directory:

| File | Role |
|---|---|
| `assemble_fleet_reference.py` | the assembler (§C) |
| `test_assemble_fleet_reference.py` | offline tests (§D) |
| `DESIGN.md` | this file |
| `mutation_check_r3.py` | r3 mutation check of every new gate (scratch copies, `-O`) |
| `OPEN-QUESTIONS.md` | items that need a coordinator ruling (ruled items marked; r3: R1–R3 ruled by E1–E3, new R6/R7) |
| `README.md` | r3 operator notes: production vs test-only mode, refusals, production consequences, accepted TOCTOU residual |
| `RESPONSE-r2.md` | r3 response to SOL-REVIEW-END-PKG1-r2, finding -> change |
| `RESPONSE-r1.md` | r2 response to SOL-REVIEW-END-PKG1-r1 (unchanged) |

---

## 0. Summary

1. **Reuse T1's freeze verbatim. A K4S-specific freeze is neither possible nor needed.**
   - The frozen guard hard-codes the T1 freeze shape (`fleet_validity.py:57-70, :88`).
   - T1's `parent_source_seed.admit` reads exactly `job/FROZEN-T1.json` (`t1/parent_source_seed.py:63`).
   - Bytes: `reports/explore/t1/FROZEN-T1.json` sha256 `24817e16c3da7b5c9b6e48c56e69144e84678b7d143a146fe2884f446d07d7e4`, last changed in aeeb3003. Identical on origin/main (verified).
2. **Guard modules:** the nine T1 files under `reports/explore/t1/`. All nine equal their freeze pins on origin/main (verified, §A.2).
   - K4S's own copies differ for five of them, so END runs **T1's** guard semantics, not K4S's reporting semantics (§A.2).
3. **Guard job: a fresh, K4S-owned directory per host**, ideally one per attempt:
   - 03: `/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rdRR-aNN` (attempt) or `…-pfNN` (preflight)
   - 04: `/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rdRR-aNN` or `…-pfNN`
   - r2: the suffix is mandatory and the job must not exist at assembly time (ruling Q4: one fresh guard job per attempt; plan v2 S5: the preflight has its own).
   - Contents:
     - `FROZEN-T1.json`;
     - the host's `system-bus-admission.json`;
     - on 03 only, `idle-services.json`;
     - `repo/<4 OP-5 seed receipts>`.
   - **Not included:** an owned-supervisor admission or an owned-copier admission.
   - The assembler enforces this namespace (§A.5).
4. **New finding (blocking risk; preflight it).** With T1's freeze, `parent_source_seed.admit` runs `git show` for commits `b2f9e25e…` and `ce042b97…` on **both** hosts at the admission checkpoint.
   - This happens **after** the END claim, so a failure there burns an attempt.
   - K4S reporting never exercised this path, because FROZEN-K4S has `parent_source_seeds = []`.
   - The commit repository is `job/repo` if `job/repo/.git` exists. Otherwise it is `/mpac/sdicks02/repos/clasher` on the host (`t1/parent_source_seed.py:65`). See §A.4 and OPEN-QUESTIONS Q3.
5. **Bundle.** It follows the T1 `END-A3-manifest-*-f6cebbaa` layout:
   - K4S evidence and its artifacts under `k4s-end-evidence/`;
   - the guard under `t1-guard/`, `t1-freeze.json`, `guard-admissions/` and `seed-inputs/`;
   - the models and state rows at the root.
   - The field-by-field mapping is in §B.
6. **Assembler and tests (r3).**
   - **Test results:** with `K4S_FROZEN_ROOT` = an origin/main fa32ab3f worktree, **252 passed normally and 252 passed under `python -O`**; frozen-consumer subprocesses inherit `-O`. Without it: 227 passed, 25 skipped.
   - **Mutation check:** under `-O`, `mutation_check_r3.py` killed **27 of 27** mutants of the r3 gates (§D). r2's 33 mutants were all killed in r2 and are not re-run here.
   - **r3 adds:**
     - the `st_nlink == 1` gate in the walk and at the descriptor, for every input class (§C.2);
     - one `location_free()` gate on complete absolute paths, including the strict END namespace, for every input and every auxiliary location (§C.2);
     - confined synthetic pins (§C.3);
     - the E1–E3 exemptions exactly as ruled (§C.2, §C.3).
   - **r2 added:**
     - confinement of every inventory name/entry before hashing;
     - production pins with a test-only SYNTHETIC switch;
     - the frozen `StateRows` checks, mirrored on the index;
     - committed-admission binding.
   - Frozen consumers exercised offline on assembled synthetic bundles: `tier_backend.validate_bundle`, `fleet_validity.ReportingGuard.__init__`, `state_rows.StateRows`, `fleet_profile.slot_layout` (03 and 04), `telemetry.validate_topology`, and `prepare_bundle.runtime_pins` (parity check).
7. **Runtime tree gap (new; see Q5).** A plain git export of origin/main **cannot** be the END runtime.
   - The frozen `runtime_pins` rule fails with "Incomplete frozen runtime": 33 files named by `reports/explore/s1/receipts/runtime-pin-r2.json` are not in git (verified; list in §E).
   - T1's END runtimes held 3,785 files, so they included these external dependencies. The K4S END runtime must too.

---

## A. The END guard job and the T1-shaped freeze

### A.1 Why T1's freeze is reused verbatim

The guard is fixed by frozen code that END cannot change. `end_reference.py:334-336` starts `fleet_reference.reference_monitor`, which constructs `fleet_validity.ReportingGuard(bundle, manifest, owned)` (`fleet_reference.py:235-239`). The requirements below come from `fleet_validity.py` (A5 `0775b704`) and the T1 guard modules:

| Requirement | Code |
|---|---|
| `profile.guard.freeze` is a bundle file pinned in `files` | `fleet_validity.py:58-60` |
| `operational_delta_op5`, `_op5_08`, `_op6` each have verdict `CONFIRM` | `:61-63` |
| each of the 9 guard modules at `<bundle>/<guard.root>/<m>.py` equals `freeze.files["reports/explore/t1/<m>.py"]`, both in the manifest and on disk | `:64-70` |
| the live job copy is named exactly `FROZEN-T1.json` | `:88`, checked at `:127-130` |
| the freeze's `parent_source_seeds`, plus the 08 `source_join` server and client, are pinned as `seed_inputs` | `:92-108` |
| `admit()` reads `job/FROZEN-T1.json` and git-verifies each binding under the prefix `reports/explore/t1/receipts/` | `t1/parent_source_seed.py:43-51, :62-68` |

`FROZEN-K4S.json` `416f6e51` has none of the three deltas, has empty seeds, and keys its files under `reports/explore/k4s-confirm/`. A "K4S freeze" that passed these checks would need fabricated T1 CONFIRM verdicts.

**Decision:** use the T1 freeze bytes `24817e16…` unchanged, both as the bundle file `t1-freeze.json` and as the live `job/FROZEN-T1.json`. The assembler hard-pins this SHA (`FROZEN_T1_SHA256`).

The guard consults only the freeze's `files`, the three deltas and `parent_source_seeds` (verified by grep over the nine modules and `fleet_validity.py`). Its other content (T1 hosts 01/08, T1 reporting namespaces) is not read.

### A.2 Guard module bytes (`<bundle>/t1-guard/`)

All nine equal `FROZEN-T1.files` and the origin/main bytes (verified):

| Module | T1 sha256 (= freeze) | Same in K4S copy (`k4s-confirm/`)? |
|---|---|---|
| `common.py` | `36e5eec3bf3cd4e285bc4d2c10631038cbe8cad54d2c25a2245336c251ee20c0` | no: `K4S_JOB` default |
| `host_audit.py` | `5717d01cc2a83adc19a4cf2846f9a95952f2ca73810b879807c5941cdddc0dd7` | no: K4S adds the apt_budget classification |
| `idle_services.py` | `911c18aee5af1d61cf66b7e5187af4cb6b3fb58d3143152a3ab385b4a76816b2` | yes |
| `system_bus.py` | `785eb2c5fbf6bc35c7d4c5c614b97bf5796b4f516aa0aeeacecbd386b9a04e11` | yes |
| `ssh_transport.py` | `16a211a5fe68b35248d40c303bdd0dfa1e4e900542478edd7e9c51ea5994925f` | yes |
| `perception_confirmation.py` | `6e2fb8d31f48b47cc76bc8fea98bd191fb7e7c51af4bada01dfbf37fc3365680` | yes |
| `owned_supervisor.py` | `fcd7aac922281e33ae315fcd91dd2ffd0cea7ca8bdf1d93716a09cd77e782249` | no: supervise path |
| `ssh_budget.py` | `0c2759f5f09728770bf339441151eb55a1f3cd17d5f04b46109f4e68f2cedd1d` | no: K4S `cpu_accounting` |
| `parent_source_seed.py` | `3cf10b3b679408b8f31cff575d11af57d40b7652a046f6bfcaced28f7bc6de1e` | no: reads `FROZEN-K4S.json` |

**Disclosure (from code; its effect on a live run is an inference).** During END, the guard is T1's, not K4S's reporting guard:
- **No apt-helper classification.** K4S `host_audit` refuses `apt_command` rows as forbidden; T1's doesn't. A Python `check-new-release` process is still `foreign_compute` under T1's rule (`t1/host_audit.py:91-92`).
- **SSH-family CPU uses T1's older `increment` accounting**, not K4S's `cpu_accounting.Accounting`.
- `ReportingGuard` replaces `host_audit.own_process` with its own PID/start-tick tree (`fleet_validity.py:117-118`). The supervise-path predicate in `owned_supervisor` is therefore unused for E4 ownership, and only an *existing* supervisor admission would matter. Under this design there is none.

### A.3 Admissions in the guard job

| Job file | Include? | Source bytes | Checks |
|---|---|---|---|
| `FROZEN-T1.json` | **always** | T1 freeze `24817e16` | `fleet_validity.py:88, :129` |
| `system-bus-admission.json` | **always** (required, `:110-111`; "no refresh") | r2 / ruling Q2: the host's latest K4S admission, **committed outcome-blind** at exactly `reports/explore/k4s-confirm/end-guard-admissions/<host>-system-bus-admission.json` (r3, E3) and bound by `--committed-admission`; the assembler requires the request source to be that committed file at HEAD of `--repository`, and the identity to equal the pinned r4 identity (03 PID 2049 / 1273; 04 PID 2005 / 1032; `/usr/bin/dbus-daemon`, cmdline `f481db68…`, uid 103). Originally: a **byte copy of an existing K4S job's admission on the same host**. FLEET-END-CONTRACT l.93-96: "existing approved job admissions … No admission identity is silently refreshed". T1 did the same: bundle `guard-admissions/system-bus-admission.json` `b994527d` = committed `t1/receipts/system-bus-admission-127x01.json`. | Format `{utc, host, identity:{pid, start_ticks, exe, cmdline_sha256, uid}, …}` (`t1/system_bus.py:21-27`; K4S uses the same module bytes). `system_bus.begin` asserts that the pinned identity is live at every block (`:31-34`). |
| `idle-services.json` | **03: required; 04: refused** (plan `idle_service_exception.hosts = [127x03, 127x08]`; r2 production pins) | Committed byte copy of the 03 K4S job's idle admission, at exactly `reports/explore/k4s-confirm/end-guard-admissions/127x03-idle-services.json` (r3, E3); exactly one service whose `service` identity equals the pinned PID 2180947 / ppid 2180946 / pgid 2180934 / start_ticks 139691386 / cmdline `16152ceb…` / uid 3822945 (= `t1/receipts/idle-services-admission-127x03.json` and the r4 03 process row) | If it exists in the job it must be pinned (`fleet_validity.py:112-114`). `idle_services.update` raises if the identity changes, and a vanished service sets `retired`, which fails blocks (`:243-244`). |
| `owned-supervisor-admission.json`, `owned-copier-admission.json` | **never** | n/a | END has no supervisor and no copier. T1 A5 removed the copier admission (`END-A5-reference-approved-argv-08-r1.json` `binding_changes`). An unpinned copy in the job is refused (`:112-114`); this was tested against the frozen code. |

Live identities in the committed r4 host admissions (14:04Z, `rounds/r4/evidence/step7/127x0{3,4}-host-admission.json`; verified by reading the process rows):

| Host | System dbus (uid 103) | Idle service |
|---|---|---|
| 03 | PID 2049, start_ticks 1273, cmdline `f481db68…` | PID 2180947, start_ticks 139691386, ppid 2180946, pgid 2180934 |
| 04 | PID 2005, start_ticks 1032, cmdline `f481db68…` | none |

**Inference:** a `system-bus-admission.json` with these identities exists in each K4S phase job directory. Its bytes and exact path are not committed and must be listed on-host (Q2). The assembler refuses an admission whose `host` field differs from the bundle host, and refuses a malformed bus identity (uid must be 103).

### A.4 OP-5 seed inputs (`seed_inputs` + `job/repo/…`)

Derived from the freeze (`parent_source_seeds`) and the 08 receipt's `source_join`. This exactly matches T1's END bundle `seed_inputs` (verified against `END-A3-manifest-01-f6cebbaa.json`).

| Repository path | sha256 | Commit used by `admit()` `git show` | Needed on 03/04 by `admit()`? |
|---|---|---|---|
| `reports/explore/t1/receipts/op5-parent-source-127x03.json` | `167cbe71eeabcd455ab0763dfd5d6061bab4d132a8783622e020d78abbd18838` | `b2f9e25e1002d43cc910a4bb476716cc4cd32623` | **yes, both hosts** (`committed_binding` runs before the host test, `:68-69`) |
| `reports/explore/t1/receipts/op5-parent-source-127x08.json` | `7081bb443e7b4776679f3c25daa521216f8d3946accb55b3441fac964b1a7c27` | `ce042b9775f80cb495c327b14a4712730ae95c85` | **yes, both hosts** |
| `reports/explore/t1/receipts/op5-parent-generation-127x08.json` (08 join server) | `f47a87ab42d6d14e9301c94198629595d277790ada358bc3c62fb88a8abe420f` | `0e137378…` | no; only on 127x08 (`:71-74`) |
| `reports/strategy_council_20260928/live-loop/v4/l1/receipts/a21-a2-preparation-20261010-r1/08-transport-identity-20261010T172047Z.json` (08 join client) | `10735e94cd3888eeafa8e8fb97eab87bddc2ec27c5a5ae3ba5b1f94c50950961` | `274aed9a…` | no; only on 127x08 |

- **All four** must be pinned in the bundle and present byte-identically at `job/repo/<path>`. `ReportingGuard` re-checks them on every guard call (`fleet_validity.py:105-106, :131-133`).
- **`admit()` side effects on 03/04 (from code):**
  - It loads the 03 binding (git show), then skips it on 04.
  - On 03 it compares the T1 receipt's 2026-10-10 sshd parent identity with the live process rows. **Inference:** no row matches, so nothing is accepted.
  - The 08 binding is git-shown on both hosts, then skipped.
  - It writes `job/parent-source-seed-admission.json` with `accepted=[]` (inference).
  - Any `git` failure raises inside the monitor at the admission checkpoint. That happens **after** `producer_claim` (`end_reference.py:309, :365`), so it is a counted attempt.
- **Where `git show` runs (`t1/parent_source_seed.py:65`):** `commit_repo = job/repo` if `job/repo/.git` exists, otherwise the host's `/mpac/sdicks02/repos/clasher`.
  - **Option A (recommended):** `job/repo` is a K4S-owned git clone that contains both commits, with the four paths checked out at their frozen bytes.
    - Example: `git clone --no-checkout --no-hardlinks <K4S-owned local clone> job/repo`, then `git -C job/repo checkout <END runtime commit> -- <the 4 paths>`. All four are unchanged on origin/main (verified).
    - This removes any dependence on a shared checkout. It costs about 0.5 GB per job (`.git` on 05 is 486 MB).
  - **Option B (T1 precedent; T1/K4S `stage.py` copy `repo/` without `.git`):** a plain `job/repo` tree, relying on the host checkout `/mpac/sdicks02/repos/clasher` containing `b2f9e25e` and `ce042b97`.
    - That checkout is not verified on 03/04. On 04 it exists, because K4S r4 ran `/mpac/sdicks02/repos/clasher/.venv/bin/python`, but its commits are unknown.
  - Either way, the preflight (§A.6) must run the frozen `committed_binding` read-only for both bindings on each host.

### A.5 Namespace, lifetime and contents (per host)

- **Parent (enforced by the assembler, `JOB_PARENTS`):**
  - 03: `/mpac/sdicks02/jobs/clasher`
  - 04: `/mpac/sdicks02/jobs-k4s`
  - **Never** under T1's `t1-20261010-r1`, a K4S reporting job (`k4s-confirm-*`), `repos/clasher-v4-cache`, or 04's `/mpac/sdicks02/jobs/clasher/` perception root.
- **Name (enforced, r2):** `k4s-end-guard-r<N>-rd<RR>-a<NN>` (attempt) or `k4s-end-guard-r<N>-pf<NN>` (preflight); the bare `k4s-end-guard-r<N>` form is refused, and the job path must not exist when the bundle is assembled (so the job is created fresh from the bundle copies).
  - Reason: the guard appends to `allowlist-occurrences.jsonl`, `ssh-family-occurrences.jsonl` and `op2-confirmations.jsonl` and rewrites `parent-source-seed-admission.json` in the job. T1 made a "fresh guard job (byte-identical freeze, bus and seed inputs; no copier admission …)" before every launch (`END-exit-push-REVIEW-r2.md:114`).
  - Because `guard.job` is inside the manifest, each attempt gets its own bundle. That is also the T1 precedent: only `guard.job` changed between per-attempt bundles. `host_pins.bundle_manifest_sha256` is per host and never compared across hosts (`end_pool.py:93-95, :324-326`).
- **Staging:** create the job fresh, before the END-JOB claim and outside the attempt roots. Copy the files from the **bundle copies**, so the SHAs are identical by construction. Make them `chmod 444`. The directory itself stays writable, because the guard writes into it.
- **Files at launch:**

  ```
  <job>/FROZEN-T1.json                     24817e16…
  <job>/system-bus-admission.json          = bundle guard-admissions/system-bus-admission.json
  <job>/idle-services.json                 (03 only) = bundle guard-admissions/idle-services.json
  <job>/repo/<4 seed paths>                = bundle seed-inputs/<path>   (+ repo/.git under Option A)
  ```

  Nothing else may be present: no `STOP`, no `STOP-<host>` (`fleet_validity.py:189`), and no supervisor or copier admissions.
- **Written by the guard during the run:**
  - `parent-source-seed-admission.json`
  - `allowlist-occurrences.jsonl`
  - `ssh-family-occurrences.jsonl`
  - `op2-confirmations.jsonl`
  - FLEET-END-CONTRACT l.150 says these are copied to `guard-sources/` of the receipt. **Inference:** not verified in the K4S END code path.

### A.6 What fails before the claim and what fails after (why a host preflight is needed)

`end_reference.reference()`:

| Pre-claim: a precondition refusal, not an attempt (END-RUNBOOK l.103-104) | Post-claim: a **counted attempt** if it fails |
|---|---|
| `frozen_helpers` and K4S manifest pins (`:291`) | backend construction: `TierBackend`, `StateRows`, `sets.golden` (`:326`; `tier_backend.py:130, :147`) |
| `validate_bundle` (`:294`, `tier_backend.py:450-469`) | corpus inventory check (`:327-328`) |
| K4S pins, executing sources, shared pins (`:96-141`) | `validate_topology` (`:333`) |
| `k4s_reporting_profile`: evidence with git checks, plan, `slot_layout`, `host_reporting` (`:298-299`) | `ReportingGuard.__init__` (freeze, modules, admissions, seeds, job bytes) and the admission call: seed `admit` with **git show**, `/proc` census (`:334-365`) |
| profile host = node, physical CPUs, END-JOB (`:301-305`) | background workers using `sets.speed` (`:366-370`); end-of-run validators (`:395-404`) |

**Recommended on-host preflight.** Read-only, pre-claim, outside the attempt roots, under `nice`, in a fresh interpreter. It needs its own Sol review before it runs on a host (memory rule).
1. `tier_backend.validate_bundle(bundle, runtime, dry_run=True, require_references=False)`.
2. `fleet_validity.ReportingGuard(bundle, manifest, [])`, construction only. Its `__init__` reads files only; the tests exercise exactly this offline.
3. `telemetry.validate_topology(manifest["topology"], cpu_counters(), darwin=False)`.
4. `state_rows.StateRows(bundle, manifest["files"]).close()`.
5. For both freeze seed bindings: the frozen `parent_source_seed.committed_binding(repo, commit_repo, freeze, binding, "reports/explore/t1/receipts/")`.
6. `fleet_profile.slot_layout(...)` with the host's real nice value.

---

## B. Fleet-reference bundle: layout, manifest, and who reads what

### B.1 Directory layout (written by `assemble_fleet_reference.py`)

```
<bundle>/
  tiers-pins.json                 manifest (canonical JSON + "\n"; receipts.canonical)
  tiers-pins.sha256               "<sha>  tiers-pins.json\n"           (unpinned, as in prepare_bundle.py:222-223)
  assembly-receipt.json           request/manifest/assembler SHAs        (unpinned, CANDIDATE)
  v1.pt  R3a.pt  R3a-calibration.json  states.pkl  states-rows.json  states-rows.bin
  k4s-end-evidence/end-evidence.json                       committed K4S END evidence (= --end-evidence-sha256)
  k4s-end-evidence/<item.path>  (×4 top-level + 4 per counted host/phase)  plan, completion, ledger, inventory, launch, supervisor-exit, mhz, census
  t1-freeze.json                                            FROZEN-T1 24817e16
  t1-guard/<9 modules>.py
  guard-admissions/system-bus-admission.json [idle-services.json on 03]
  seed-inputs/<4 repository paths>
```

Every bundle copy has mode `0444` and is re-hashed after copying. The bundle is assembled in `<out>.partial` and renamed into place only after every step succeeds. A failure removes the partial directory.

### B.2 Manifest fields, and every consumer that reads them

| Field | Value written | Read by (path:line at 754c43cd) |
|---|---|---|
| `schema` | `clasher.e4v3.inputs.v1` | `tier_backend.py:453` |
| `final` | `false` | Not read by K4S END. Kept for T1/prepare_bundle parity. |
| `profile` | `fleet-reference` | `end_reference.py:102`; `end_background.py:76`; `tier_backend.py:140, :189, :251` (anything other than `linux-dry-run` is production) |
| `threshold` | `0.5005528330802917` | `tier_backend.py:462` |
| `specification` | the e4v3 `spec-pins.json` content from the runtime | `tier_backend.py:455` (must equal the imported e4v3 `spec-pins.json`) |
| `files` | every bundle copy → sha256 | `tier_backend.py:456` (all verified); `end_reference.py:108, :115` (model pins); `:137-138` (R3a pins for SD1); `end_background.py:74-83`; `fleet_validity.py:59, :69, :87-88, :99`; `state_rows.py:29-42` |
| `runtime_files` | frozen `runtime_pins` rule over `--runtime-root` (`prepare_bundle.py:36-52`) | `tier_backend.py:457`; `end_reference.py:117` (canonical SHA, a shared pin across hosts); `:135` (`runtime_files["reports/explore/s1/anchor.py"]` = scorer normal form) |
| `measurement_files` | frozen rule over `<runtime>/…/e4v3` (`prepare_bundle.py:117`) | `tier_backend.py:458` (against the **imported** e4v3 directory); `end_reference.py:118` (shared pin) |
| `topology` | `{P: [all logical CPU IDs], E: [], label}` from the request | `end_reference.py:333` → `telemetry.validate_topology` (post-claim) |
| `sets` | `{golden, speed:{K0c,S,K2,K4}[, agreement, packets]}` from the request | `tier_backend.py:147-152` (post-claim); `end_background.py:96-101` (`corpus_loop`) |
| `reference_load_profile.host` | the request host | `end_reference.py:109, :301`; `fleet_profile.py:13`; `fleet_end.py:190` |
| `.reference_slot` | `0` | `fleet_profile.py:24-26`; `fleet_end.py:193-194` |
| `.slot_count` | `plan.compute.slots`, which is 11, because `console_rule` is false | `fleet_profile.py:17-18`; `fleet_end.py:202-203` (must equal every counted `launch.slots`); `end_reference.py:400` |
| `.console_rule` | `false` (an explicit Boolean) | `fleet_profile.py:15-17` |
| `.warmup_seconds` | `300` | `fleet_profile.py:27`; `end_reference.py:376` |
| `.perception` | `"none"` | `fleet_profile.py:27` |
| `.plan` | `k4s-end-evidence/<evidence plan path>` (the same file the evidence pins) | `end_background.py:75, :82` (= evidence `plan_sha256` = the file); `fleet_validity.py:82-85` (the guard modules' `plan()`) |
| `.end_evidence` | `k4s-end-evidence/end-evidence.json` | `end_background.py:75-79` (pin = `--end-evidence-sha256` = the file) |
| `.guard.root` | `t1-guard` | `fleet_validity.py:64-71` |
| `.guard.job` | the per-host job (§A.5) | `fleet_validity.py:86, :113, :129, :132, :189`; T1 modules through `j` |
| `.guard.freeze` | `t1-freeze.json` | `fleet_validity.py:58-63, :88` |
| `.guard.admissions` | `{system-bus-admission.json: guard-admissions/…[, idle-services.json: …]}` | `fleet_validity.py:87, :110-114, :128-130` |
| `.guard.seed_inputs` | `{<4 repository paths>: seed-inputs/<path>}` | `fleet_validity.py:92-108, :131-133` |

**Not written** (T1 had these; no K4S END consumer reads them, verified by grep over `k4s-confirm/*.py`, `mac/*.py` and the imported e4v3 modules):
- `corpus_receipt` / `corpora.json`, `deadline_replay_semantics`, `golden.json`, `belief-reference.json`: read only by `fleet_reference.run` (`:30-32, :98-105`), which K4S does not call.
- `reference_load_profile.amendment`: read only by the TIERS `fleet_end.evidence` (`:138`), which K4S replaces with `end_evidence.end_evidence`.

### B.3 Where the END evidence goes

- `end_evidence.end_evidence(path, …)` resolves every artifact relative to **the `--end-evidence` file's parent** (`end_evidence.py:183-184` → `fleet_end.artifact(path.parent, …)`, `fleet_end.py:20-34`). That reader is given `spec["end_evidence"]` (the CLI path), not the bundle copy (`end_background.py:80`).
- The assembler copies the evidence to `k4s-end-evidence/end-evidence.json`, and each artifact to `k4s-end-evidence/<item.path>`, after checking each against `item.sha256`.
- **Recommendation:** run with `--end-evidence <bundle>/k4s-end-evidence/end-evidence.json`. The reader then resolves artifacts inside the immutable bundle and git-checks them against `--repository` (`fleet_end.py:29-33`; the commits must be ancestors of HEAD).
- Pointing `--end-evidence` at the repository's committed file also works. Either way, `profile.end_evidence` (the bundle copy) must have the same SHA.
- **Constraint from the reader:** the evidence's artifact paths cannot contain `..` (`fleet_end.py:13-17`). The committed evidence must therefore sit at or above every artifact. With `plan.json` at `reports/explore/k4s-confirm/plan.json`, that means `reports/explore/k4s-confirm/<name>.json` or higher, and not under `…/end/` (END-RUNBOOK l.83-89). This is a constraint on the B4 evidence builder.

### B.4 What must be byte-equal on 03 and 04

`end_reference.shared_bundle_pins` (`:113-119`) puts these into the common pins, and the pool requires them equal across hosts (END-RUNBOOK l.32-34):
- the canonical SHA of `runtime_files`;
- the canonical SHA of `measurement_files`;
- the `files` pins of `v1.pt`, `R3a.pt`, `R3a-calibration.json` and `states.pkl`.

So build both hosts' bundles from **one** runtime tree, byte-identical on both hosts, and the same model and state files. Per host, these may differ: `reference_load_profile.host`, `guard.job`, the admission copies, and therefore `bundle_manifest_sha256`. The two requests should differ only in `host`, `guard.job`, `guard.admissions` and the source paths.

### B.5 Bundle inputs: what exists and what is missing

| Input | Expected | Status |
|---|---|---|
| runtime tree at a commit ≥ 133f3ae4, plus 33 external runtime-pin files | `runtime_files_sha256` = canonical SHA computed by the assembler (it reports the computed value on mismatch) | **Missing** as a complete tree. Ruled (Q5, fa89baa9): built at the END-JOB commit; the 33 from SHA-matched bytes already on 05 only. Must keep the tracked symlink `visualize_battle.py` → `examples/visualize_battle.py` (E1, §C.2). r3: it must not contain `reports/explore/k4s-confirm/end/`, and every file must be single-link (OPEN-QUESTIONS R6/R7) |
| e4v3 measurement set | `measurement_files_sha256` = `42b8986d7e7748dd826ddad021ced3573d3ca5bbc21333120f1bf212beef8c25` (origin/main; equal to the reviewed T1 A5 18-file inventory; verified) | available in any runtime at ≥ 8799a0d6 / origin/main |
| `v1.pt`, `R3a.pt`, `R3a-calibration.json` | frozen `d77005d5…`, `37509a43…`, `e3003533…` (hard-pinned) | location on 03/04 not verified (Q6) |
| `states.pkl`, `states-rows.json`, `states-rows.bin`, `sets` | **production pins (r2):** `0addf7c0176c358e…`, `bcd307770b70394878f7…`, `8cc2f611e867dc38…` (full values in the code) and T1's own-tier `sets` (golden 125; speed 4×300), canonical `d84b07f6de0ac1cf…` | Ruled (Q6, fa89baa9): T1's byte-exact copies **on 05** (verified r2: sha256 of `end-a5-pool-context-20261012-r1/bundle/{states.pkl, states-rows.json, states-rows.bin}` equal the pins; the 11 other A3/A5 copies on 05 listed in `locate/q6-states-locate-05.txt` were not re-hashed). The sets value is identical in END-A3-manifest-01/08-f6cebbaa and in the A5 manifests on 05 (`README.md`) |
| topology | `{P: 0..127, E: [], label: "Linux logical IDs; physical masks pinned by reporting plan"}` (T1 value) | **production pin (r2)**; S4 cannot observe the target host, so the binding check is the S5 preflight's live `validate_topology` (mandatory, pre-claim) |
| END evidence + artifacts | `clasher.k4s.end-evidence.v1`, committed | **not built**; depends on B1 (Q1) and B2 (Q7) |
| FROZEN-T1, 9 modules, 4 seeds | §A.2 and §A.4 | committed on origin/main (verified) |
| admissions | §A.3 | Ruled (Q2): fetched by the reviewed exact-path reader and committed outcome-blind before the END-JOB; **not committed yet**, so the assembler requires `--committed-admission NAME PATH SHA` and refuses without it |

---

## C. The assembler (`assemble_fleet_reference.py`, r3)

### C.1 CLI and request

```
assemble_fleet_reference.py --request R.json --request-sha256 S --repository REPO \
    --committed-admission system-bus-admission.json <repo path> <sha256> \
    [--committed-admission idle-services.json <repo path> <sha256>]   # required on 127x03, refused on 127x04
    --out NEW_DIR [--dry-run]
```

- Exit 0 on success; exit 2 with `ASSEMBLY REFUSED: <reason>` on any check failure. Python errors that slip past the explicit checks raise with exit 1 (still fail-closed: nothing is published before the final rename).
- `--dry-run` runs every check (all hashing included) and the `--out` checks, then prints the exact planned `tiers-pins.json` bytes to stdout. It writes nothing.
- `--repository` is the K4S checkout that holds the committed END evidence and the committed Q2 admission copies. Only two git commands run in it, with no work-tree enumeration:
  - `git cat-file blob HEAD:<fixed path>`, for the evidence and the E3 admission paths;
  - r3 (E1): `git ls-tree -z HEAD -- visualize_battle.py`, then `git cat-file blob <that blob>`.
- Request schema `clasher.k4s.end-fleet-reference-request.v2` (exact keys as r1). r2 constraints: `end_evidence.source` must be `REPO/reports/explore/k4s-confirm/end-evidence.json` and `artifacts_root` `REPO/reports/explore/k4s-confirm`; every `guard.admissions` source must be `REPO/<the --committed-admission path>`. r3 (E3): that path must be exactly `reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>`.

### C.2 Read confinement (r2 S4-F1; r3 S4-R2-F1/F2/F3; E1/E2)

Every path is validated before any of its bytes are read (hash, parse or copy). The same helpers apply to **every input class**:
- the request and the synthetic pins;
- the runtime members and their S1 metadata;
- the measurement entries;
- the Q6 models and state rows, and the sets;
- the END evidence and its artifacts;
- the guard freeze, modules, admissions and seeds;
- the assembler's own file, whose hash goes in the receipt.

They also apply to **every auxiliary location**: `--repository`, `--out`, the guard-job parent, the committed-admission paths, the evidence item paths, the `git cat-file` paths and the seed paths.

1. **Names.** Inventory names must be normalized relative POSIX paths: not absolute; no `''`, `.`, `..`, backslash or NUL. These are the S1 runtime-pin entries, discovered runtime `.py` entries, measurement entries, evidence item paths, seed paths and committed admission paths. Request sources must be absolute and `normpath`-normal.
2. **Locations, by name only, on the complete absolute path (r3 `location_free()`).** `walk()` calls it before its first `lstat`, so no input can bypass it. It refuses:
   - a `games` or `hub-blocks` component;
   - a `complete.json`, `local-complete.json`, `end-complete.json`, `interference.json`, `hub-ack.json` or `end-raw.json` leaf;
   - a `k4s-confirm-*` component (K4S reporting jobs) or `k4s-end-guard-*` component (live guard jobs);
   - one of FROZEN-T1's five launch namespaces;
   - **(r3) the strict END namespace:** a `k4s-confirm` component immediately followed by `end`. This is END-RUNBOOK `END_DIR = reports/explore/k4s-confirm/end/`, wherever it is rooted: the repository, a runtime export or any copy.

   Other notes:
   - In the runtime tree, directories named `games`/`hub-blocks`/job names, and (r3) the END namespace directory, are refused and never listed or descended.
   - `reports/explore/k4s-confirm/end-guard-admissions/` (E3) is not the END namespace (tested).
   - No tracked path at origin/main fa32ab3f has a `games`, `hub-blocks`, `k4s-confirm-*`, `k4s-end-guard-*` or `k4s-confirm/end` component. This was verified with `git ls-files`.
3. **No aliases.** Each component is `lstat`-walked from its declared root (request sources from `/`); a symlink anywhere refuses.
   - **E1** is the only exception: `visualize_battle.py` → `examples/visualize_battle.py`.
     - (r3) `--repository` HEAD must carry it as a mode-120000 entry whose blob is exactly that text (`committed_alias()`).
     - The runtime must have it as the same root-level link, with the exact link text.
     - The link itself is never opened. The walk restarts at the target, which passes every gate (names, no symlink, `st_nlink == 1`) and is opened by its own path.
   - Python 3.12 `rglob('*.py')` (the frozen rule) matches file symlinks and does not descend symlinked directories (verified in r2). The assembler discovers the same names with `os.scandir`, without following links.
4. **Single link (r3, S4-R2-F1).** A regular-file leaf must have `st_nlink == 1`, checked in the walk before the file is opened.
   - A hard link to anything, including an outcome file, is refused with the input's own label.
   - There is no hard-link exception: the E1 target and the E2 file must also be single-link.
5. **Descriptor gate.**
   - Files are opened with `O_NOFOLLOW|O_NONBLOCK|O_NOCTTY`.
   - Before any read, `fstat` of the descriptor must show a regular file with the walked `(st_dev, st_ino)` and (r3) `st_nlink == 1`.
   - Copies are made from that descriptor while hashing, into `O_CREAT|O_EXCL|O_NOFOLLOW` targets, then re-hashed. The copy pass re-opens through the same gate.
   - All runtime and measurement entries are walked before any of them is hashed.
6. **E2 (only outcome-named exemption).** `imitation/model/receipts/throughput-0935/complete.json` is exempt only at that runtime path.
   - The exemption is a constant, and `check_exemptions()` refuses any pins file that widens or moves it.
   - Its SHA must be `d1492d0f…` in production.
   - It is hashed once, as a frozen runtime member, and never parsed (tested).
   - Every other `complete.json`-family leaf is refused.
7. **Accepted residual (coordinator scope ruling, 16:00Z):** replacement of an *ancestor directory* between the walk and the open (TOCTOU) on these single-operator hosts. Pre-existing symlinks, hard links and forbidden locations are refused statically and are not part of the residual.

### C.3 Production pins and the test-only switch (S4-F2)

- `PRODUCTION_PINS` (code constants; sources in the code comment and `README.md`): six model SHAs (three frozen + Q6), the T1 own-tier `sets` canonical SHA, the measurement inventory SHA `42b8986d…`, FROZEN-T1, the K4S plan, the 128-CPU topology, the per-host admission sets and identities, the runtime alias and the outcome-name exception.
- **Default = production.** Without `K4S_S4_SYNTHETIC_PINS`, every pin is enforced; the request cannot substitute other models, state bytes, sets, topology, measurement inventory or admissions.
- **Admissions (E3):** 03 must have exactly `system-bus-admission.json` + `idle-services.json`; 04 exactly `system-bus-admission.json`.
  - For each, `--committed-admission NAME PATH SHA` is mandatory.
  - PATH must be exactly `reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>` and must pass `location_free()`.
  - The HEAD blob SHA, the SHA argument, the request SHA and the work-tree file SHA must all be equal.
  - The content's `host` must be the bundle host.
  - The identity must equal the r4 pin. A stale identity (after a reboot, bus replacement or cache-service restart) is refused, with a message naming the coordinator re-pin ruling that is then required.
- **Test-only mode:** `K4S_S4_SYNTHETIC_PINS=<abs pins.json>`, read (r3, S4-R2-F3) through `absolute()` + `read_confined()`, i.e. the same name, lstat, hard-link and descriptor gates. It cannot change the E1/E2 paths (`check_exemptions()`). Its content must have `"marker": "SYNTHETIC"`, the pins schema and every pin key. It additionally requires an `--out` whose name contains `SYNTHETIC`, adds `"k4s_s4_synthetic": "SYNTHETIC-TEST-ONLY"` to the manifest and writes the receipt with `production_pins: false`, `status: SYNTHETIC-TEST-ONLY`. A production consumer (S3/S5/runbook) must refuse a manifest carrying `k4s_s4_synthetic` or a receipt with `production_pins` false (the frozen consumers ignore unknown manifest keys, so this is a procedural check; noted in `README.md`).
- Guard job: mandatory `-rdRR-aNN` / `-pfNN` suffix; the job path must not exist. (r3) Its parent (`JOB_PARENTS[host]`) passes `location_free()`.

### C.4 State index (S4-F3)

`check_state_index` mirrors `state_rows.StateRows.__init__` (`state_rows.py:34-61`) without unpickling: schema; `pickle_protocol == 5` (int); source `states.pkl` pin and `verified: true`; container `states-rows.bin` pin; row count = `source.rows`; rows contiguous from 0 with positive lengths; final length = `container.bytes`; unique IDs; container file size = index length. Stricter than frozen: integer types, string IDs, 64-hex row SHAs. **And** the index bytes are pinned (`bcd30777…`). Tests run the frozen `StateRows` on every index mutant (same verdict) and on the real Q6 index (accepted; sparse stand-in container of the pinned size).

### C.5 Check order

0. (r3) Assembler file and `--request` confined, then read. 1. Request SHA, schema, keys, host (synthetic pins, if set, confined then read). 2. `--repository` confined; `--committed-admission` set, exact E3 paths and HEAD blob SHAs; E1 committed mode-120000 entry. 3. Runtime: e4v3 confined; measurement inventory (confined entries) = pin = request; spec-pins; runtime inventory (confined, §C.2) = request. 4. Models = pins; state index (§C.4). 5. Sets = pin, then shape and ⊆ index. 6. Topology shape and pin. 7. Evidence: location in `--repository`, SHA, committed at HEAD, schema/kind; each item: safe name, `repository_path` = `reports/explore/k4s-confirm/<path>`, `location_free()` (so not `end/`), one commit for all, confined walk, SHA; plan pin, study, slots, host. 8. Guard: job namespace + freshness; freeze pin and deltas; nine modules = freeze pins; admissions (§C.3); seeds = freeze bindings + 08 join. 9. `--out`: normalized absolute, (r3) `location_free()`, parent lstat-confined, new, no partial, outside runtime/evidence/repository; `*SYNTHETIC*` in test mode. 10. Copy pass: every source re-opened through the descriptor gate.

**Determinism.** Unchanged from r1: canonical manifest of the inputs only; byte copies; tested byte-identical bundles.

**Read-only on its inputs** (tested by SHA + mtime snapshots). **Never reads outcomes:** it never parses the E2 receipt; it parses only the evidence document, the plan, the freeze, the admissions, the seed receipts, the sets, the state index and the S1 pin JSONs; every other artifact is hashed and copied without parsing, after its name passed §C.2.

---

## D. Tests and results (r3)

**Command:** `nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B [-O] -m pytest -q -p no:cacheprovider test_assemble_fleet_reference.py`, with `K4S_FROZEN_ROOT=<read-only detached worktree of origin/main fa32ab3f>`.

| Run | Result |
|---|---|
| normal, frozen root set | **252 passed** |
| `python -O`, frozen root set | **252 passed**, plus 1 warning: pytest's missing-assertion warning. The suite uses `ok()`, never a bare `assert`. Frozen-consumer subprocesses inherit `-O`. |
| normal, frozen root **unset** | **227 passed, 25 skipped** (reason: `K4S_FROZEN_ROOT … not set`) |
| `mutation_check_r3.py` under `-O` (scratch copies in a fresh temp dir, deleted) | **27 of 27 killed.** The baseline (unmutated copy) passes 252 first. Each mutant names its killing tests; see the table in `RESPONSE-r2.md`. |
| r2's 33 mutants | All killed in r2 (`RESPONSE-r1.md`). Not re-run in r3. |

**New coverage in r3.** Every r3 control asserts the specific refusal message. Where bytes could be at stake, an in-process audit hook (`sys.addaudithook`) records the inode of every file opened, under any name. The test then asserts that the canary inode was never opened. Canaries are also mode 000.
- **S4-R2-F1, hard links:**
  - an outcome canary (`games/<class>/complete.json`, mode 000) is hard-linked into each of 22 input classes:
    - runtime pin member, discovered `.py`, E1 target, E2 file;
    - S1 runtime-pin and qualified JSONs;
    - a measurement `.py` and `spec-pins.json`;
    - `states.pkl`, `states-rows.json`, `states-rows.bin`, `v1.pt`;
    - sets;
    - END evidence, an evidence artifact, telemetry;
    - the guard freeze and a guard module;
    - the bus and idle admissions;
    - a seed;
    - the synthetic pins.
  - Each class runs twice: with the original bytes (every SHA and composite pin consistent, so only the gate can refuse) and with canary bytes (stale SHAs).
  - Also: the `--request` file; the E1 target through the alias walk; the assembler file itself (subprocess).
  - The descriptor gate is tested end to end, with a link created after the walk (`os.fdopen` is never reached for that inode), as a unit, and at copy time (a link made after planning).
- **S4-R2-F2, END namespace and auxiliary locations:**
  - the reviewer's sealed `end/receipts/…/reference-warmup.json` used as `sets`;
  - `end/attempt-00.json`, `end/registry/…/attempt-00.json`, `end/END-JOB.json` and `copy/k4s-confirm/end/pools/…` used as a request source;
  - an END runtime member, and an END directory in the runtime tree (never passed to `os.scandir`);
  - `runtime_root` in the END namespace;
  - `--repository` under the END namespace, `games/` or a job tree, refused by name before `lstat`;
  - `--out` under the END namespace, `games/`, a guard-job tree, `end-raw.json`, or a T1 launch namespace, with nothing written;
  - a guard-job parent in a `games`, T1 or END location;
  - a `git cat-file` path in the END namespace;
  - a frozen seed path in the END namespace;
  - committed-admission paths: the END namespace, `games/`, and any path that is not the exact E3 path;
  - `end-guard-admissions/` is accepted as distinct from `end/`;
  - unsafe absolute paths are refused by `location_free()`.
- **S4-R2-F3, synthetic pins:**
  - through a symlinked parent;
  - under `games/` or the END namespace, or named `complete.json`;
  - hard-linked;
  - relative or non-normalized.
  - The canary inode is never opened.
- **E1:** the committed entry is required (a regular file with the same text, a different link text, and no entry are each refused); the link is never opened (audit); the target passes the hard-link gate through the alias walk; test mode cannot widen the alias map.
- **E2:** opened exactly once (audit: one open of its inode) and never passed to `parse_json`; refused at any other path (`throughput-0936/complete.json`); test mode cannot add or move exceptions; the production constants equal the ruled path and SHA.
- **E3:** the exact path is required; a stale bus `start_ticks` is refused with the re-pin message.

**Coverage added in r2 (kept):**
- **S4-F1 (each asserts refusal with the specific message, the canary is mode 000, and the canary path never reached `open_confined`):** absolute runtime-pin entry; `../` entry; runtime `.py` symlink into a `games/` canary; measurement `.py` symlink outside the tree; runtime-pin entry through a symlinked directory; `games/` and `complete.json` inventory names; a `games/` directory in the runtime tree (never descended); symlinked S1 runtime-pin JSON; request source with a symlinked ancestor; request sources in `k4s-confirm-*`, `k4s-end-guard-*`, a T1 launch namespace, `games/`, `hub-blocks/`, `interference.json`, `end-raw.json`; evidence artifact symlink, `games/` item, `end/` item; leaf replaced or swapped for a symlink after the walk; `--out` through a symlinked parent (nothing written there); the pinned alias (wrong link text, regular file, absolute link) and the outcome-name exception (wrong SHA).
- **S4-F2:** production pins equal the verified constants; production is the default and refuses the synthetic inputs; each model/index/bin pin, the sets pin, measurement/freeze/plan pins, topology pin; 03 without idle (request and `--committed-admission`); 04 with idle; missing/duplicate/unknown/misplaced `--committed-admission`; work-tree vs HEAD vs argument SHA; admission not the committed copy; bus/idle identity, uid, host, service-count checks; synthetic mode requires the marker, every key, and a `*SYNTHETIC*` `--out`, and stamps manifest + receipt; guard job suffix and freshness; evidence must be committed at HEAD at its fixed location; one evidence commit.
- **S4-F3:** 13 index mutants (protocol 999 and `True`, schema, source/container pins, unverified, row count, offset 77, gap, zero length, final length, duplicate, missing container) each refused by the assembler **and** by the frozen `StateRows` (13 parity tests); container size mismatch.
- **Production bytes on 05 (read-only):** the real Q6 index equals its pin and passes the mirror; the frozen `StateRows` accepts it (sparse stand-in container; no pickle loaded); T1's committed own-tier sets (A3 01 and 08) equal the sets pin, have 125 / 4×300 IDs, and every speed ID is in the real index.
- Kept from r1 (adapted): happy path (now with the alias, a hidden `.py`, the outcome-name exception), 04 variant, dry run, determinism, immutability, every r1 fail-closed branch, the frozen consumers (`runtime_pins` parity incl. alias and exception, `validate_bundle`, `StateRows`, `validate_topology`, `slot_layout` 03/04, `ReportingGuard.__init__` accept/reject).

**Not covered offline, and why** (unchanged from r1, plus): no production-mode end-to-end run is possible yet (runtime tree, END evidence and committed admissions do not exist); production mode is exercised for its refusals and each pin is exercised by moving one synthetic pin to its production value. `end_background.k4s_reporting_profile`/`end_evidence.end_evidence` on an assembled bundle, `ReportingGuard.__call__`/`admit`, `TierBackend` construction and live topology remain S2/S3/S5 responsibilities. The test guard `repo/` is a file tree, not the Q3 git clone (S3).

---

## E. Reference values computed in this session (origin/main 754c43cd)

- **`measurement_files`:** 18 entries, canonical SHA `42b8986d7e7748dd826ddad021ced3573d3ca5bbc21333120f1bf212beef8c25`. Equal to `END-A5-runtime-manifest-inventory-diff.json` `full_18_inventory`, which includes `fleet_validity` `0775b704`.
- **Frozen `runtime_pins` on a plain git export of 754c43cd fails** with "Incomplete frozen runtime". 33 names from `runtime-pin-r2.json` are not in git:
  - `imitation/__init__.py`, `imitation/evaluation/{legacy_audit,seed_compat}.py`, `imitation/evaluation/runtime_dependencies/{derived_d1,own_cycle,sidecar_observer}.py`;
  - `reports/strategy_council_20260928/{c56/engine/root-v3/human_deck_catalog.json, m0/data/roles_v2/training.json, search-noise-s6/runtime/support/{human_deck_catalog,selection}.json}`;
  - `src/clasher/analysis/loss_review/{delay_fixes,delay_runtime,delay_simulate,scheduling,search_ab,tempo,throughput_guard}.py`;
  - `student-source/exit_r3/{__init__,network,rows,student,teacher_batch,test_r3,test_round2,train}.py`;
  - `tests/analysis/{test_delay_fixes,test_delay_fixes_summary,test_search_ab,test_search_ab_guard,test_tempo,test_tempo_launch,test_throughput_guard}.py`, `tests/test_l1_v4.py`.
  - The 11 qualified S1 files all match. The export has 3,835 tracked `.py` files; with the 33 added, the union would be 4,119 names (inference: T1's f6cebbaa runtime had 3,785).
- **Scorer normal form** of `k4s-confirm/anchor_x.py` = `75a1b7d7…` = sha of `reports/explore/s1/anchor.py`. The `end_reference.py:135` check will pass for any runtime with that file.
- **Plan** `38064dcd…`: `study = PREREG-K4S`; hosts 01/03/04/08 with 55 physical CPUs and census CPU 63; slots 11; slot_width 5; smt false; nice 10; forbidden 02/05/06/07; idle exception 03/08; perception exception host 03.

## F. Inferences (not verified)

1. The location and bytes of each host's K4S `system-bus-admission.json` and `idle-services.json` (§A.3). r2: the expected identities are pinned from committed r4 evidence; whether the committed Q2 copies will carry them is unverified until they exist.
2. Whether `/mpac/sdicks02/repos/clasher` on 03/04 contains `b2f9e25e` and `ce042b97` (§A.4).
3. That T1's seed `admit` accepts nothing on 03/04 (§A.4).
4. That the guard occurrence files are sealed into the K4S receipt (§A.5).
5. That the 33 external runtime files are available byte-identically, as in T1's runtime lineage (§E).
6. ~~That T1's states, rows and sets are the intended K4S background corpus.~~ Ruled (Q6, fa89baa9; plan v2 S4): yes; pinned in r2.
7. (r2) That the production runtime has no symlink other than `visualize_battle.py` and no `games`/`hub-blocks`/job-named directory. Verified by name: no tracked path at origin/main 1aa63a16 has such a component, its only tracked symlink is `visualize_battle.py`, and every name in `runtime-pin-r2.json` (1,557) and in T1's A3 `runtime_files` (3,785) passes the r2 name rules. Whether the assembled runtime tree on disk has extra symlinks is checked by the assembler itself.
8. (r3) That the production inputs are single-link files, and that the runtime given to S4 can exclude `reports/explore/k4s-confirm/end/` without changing frozen membership.
   - Verified: the three Q6 copies on 05 have `st_nlink == 1` (`stat -c %h`).
   - Verified by name, with the r3 rules: every name in `runtime-pin-r2.json` (1,557) and in each A3 manifest's `runtime_files` (3,785) passes `location_free()`, and none is in the END namespace. Of origin/main's 11,619 tracked paths, the only ones refused are four outcome-named leaves: E2, plus three `complete.json` receipts under `live-loop/v4`, which are not runtime members.
   - Unverified until the runtime tree, evidence and admissions exist: their link counts, and the absence of `.py` under the END namespace on the hosts. See OPEN-QUESTIONS R6/R7.
