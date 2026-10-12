# K4S END, blocker B3: the END guard job and the fleet-reference bundle (CANDIDATE b3-r1)

- **Status:** CANDIDATE for an independent Sol review. Nothing here has been run against a host, staged on a host, or adopted.
- **Written:** 2026-10-12, starting about 15:26Z (`date -u` gave 2026-10-12T15:26:01Z partway through). Offline implementer on 127x05.
- **Sources:** origin/main `754c43cd` (fetched at the start), read through a temporary detached worktree that has since been removed. Every `path:line` below refers to that commit.
- **Read boundary:**
  - Never opened: any `games/` directory, `complete.json`, reducer or verifier output, or any outcome field.
  - No SSH. No commits. Writes only to this directory. The only scratch work was in `/tmp`.
  - Committed health receipts were read: the r4 host admissions, the T1 END receipts and FROZEN-T1.
- **Conventions:** **Inference** marks anything not read directly in code or bytes. "Verified" means checked in this session by a command or a test whose result is recorded here.

Deliverables in this directory:

| File | Role |
|---|---|
| `assemble_fleet_reference.py` | the assembler (§C) |
| `test_assemble_fleet_reference.py` | offline tests (§D) |
| `DESIGN.md` | this file |
| `OPEN-QUESTIONS.md` | items that need a coordinator ruling |

---

## 0. Summary

1. **Reuse T1's freeze verbatim. A K4S-specific freeze is neither possible nor needed.**
   - The frozen guard hard-codes the T1 freeze shape (`fleet_validity.py:57-70, :88`).
   - T1's `parent_source_seed.admit` reads exactly `job/FROZEN-T1.json` (`t1/parent_source_seed.py:63`).
   - Bytes: `reports/explore/t1/FROZEN-T1.json` sha256 `24817e16c3da7b5c9b6e48c56e69144e84678b7d143a146fe2884f446d07d7e4`, last changed in aeeb3003. Identical on origin/main (verified).
2. **Guard modules:** the nine T1 files under `reports/explore/t1/`. All nine equal their freeze pins on origin/main (verified, §A.2).
   - K4S's own copies differ for five of them, so END runs **T1's** guard semantics, not K4S's reporting semantics (§A.2).
3. **Guard job: a fresh, K4S-owned directory per host**, ideally one per attempt:
   - 03: `/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1[-rdRR-aNN]`
   - 04: `/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1[-rdRR-aNN]`
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
6. **Assembler and tests.**
   - Tests: **92 passed normally and 92 passed under `python -O`**, with `K4S_FROZEN_ROOT` set to the origin/main worktree. Without it: 82 passed and 10 skipped.
   - Under `-O`, three hand-made mutants of the assembler were each killed (§D).
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
| `system-bus-admission.json` | **always** (required, `:110-111`; "no refresh") | A **byte copy of an existing K4S job's admission on the same host**. FLEET-END-CONTRACT l.93-96: "existing approved job admissions … No admission identity is silently refreshed". T1 did the same: bundle `guard-admissions/system-bus-admission.json` `b994527d` = committed `t1/receipts/system-bus-admission-127x01.json`. | Format `{utc, host, identity:{pid, start_ticks, exe, cmdline_sha256, uid}, …}` (`t1/system_bus.py:21-27`; K4S uses the same module bytes). `system_bus.begin` asserts that the pinned identity is live at every block (`:31-34`). |
| `idle-services.json` | **03 only** (plan `idle_service_exception.hosts = [127x03, 127x08]`) | Byte copy of the 03 K4S job's idle admission (perception v4 cache service PID 2180947) | If it exists in the job it must be pinned (`fleet_validity.py:112-114`). `idle_services.update` raises if the identity changes, and a vanished service sets `retired`, which fails blocks (`:243-244`). |
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
- **Name (enforced):** `k4s-end-guard-r<N>[-rd<RR>-a<NN>]`.
  - **Recommendation:** use the per-attempt form, e.g. `k4s-end-guard-r1-rd00-a00`.
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
| runtime tree at a commit ≥ 133f3ae4, plus 33 external runtime-pin files | `runtime_files_sha256` = canonical SHA computed by the assembler (it reports the computed value on mismatch) | **Missing** as a complete tree (§E, Q5) |
| e4v3 measurement set | `measurement_files_sha256` = `42b8986d7e7748dd826ddad021ced3573d3ca5bbc21333120f1bf212beef8c25` (origin/main; equal to the reviewed T1 A5 18-file inventory; verified) | available in any runtime at ≥ 8799a0d6 / origin/main |
| `v1.pt`, `R3a.pt`, `R3a-calibration.json` | frozen `d77005d5…`, `37509a43…`, `e3003533…` (hard-pinned) | location on 03/04 not verified (Q6) |
| `states.pkl`, `states-rows.json`, `states-rows.bin`, `sets` | T1's `0addf7c0…`, `bcd30777…`, `8cc2f611…` and T1's own-tier `sets` (golden 125; speed 4×300) from `END-A3-manifest-*-f6cebbaa.json` | **on T1 storage (01/08) only**; needs an authorized read-only copy (Q6) |
| topology | `{P: 0..127, E: [], label: "Linux logical IDs; physical masks pinned by reporting plan"}` (T1 value) | constant; checked on the host by the preflight |
| END evidence + artifacts | `clasher.k4s.end-evidence.v1`, committed | **not built**; depends on B1 (Q1) and B2 (Q7) |
| FROZEN-T1, 9 modules, 4 seeds | §A.2 and §A.4 | committed on origin/main (verified) |
| admissions | §A.3 | **on hosts only**; listing and copy needed (Q2) |

---

## C. The assembler (`assemble_fleet_reference.py`)

**CLI:**

```
assemble_fleet_reference.py --request R.json --request-sha256 S --out NEW_DIR [--dry-run]
```

- Exit 0 on success. Exit 2 with `ASSEMBLY REFUSED: <reason>` on any check failure.
- Python errors that slip past the explicit checks, e.g. a malformed S1 runtime-pin JSON, raise with exit 1. That is still fail-closed.
- `--dry-run` runs every check (all hashing included) and the `--out` checks, then prints the exact planned `tiers-pins.json` bytes to stdout. It writes nothing. Tests confirm the bytes equal a later real run.

**Request** (`clasher.k4s.end-fleet-reference-request.v1`; the exact key set is enforced; every source path is absolute):

```json
{
  "schema": "clasher.k4s.end-fleet-reference-request.v1",
  "host": "127x03",
  "runtime_root": "/mpac/sdicks02/jobs/clasher/k4s-end-r1/runtime",
  "runtime_files_sha256": "<canonical sha of runtime_files>",
  "measurement_files_sha256": "42b8986d7e7748dd826ddad021ced3573d3ca5bbc21333120f1bf212beef8c25",
  "topology": {"P": [0, 1, "…", 127], "E": [], "label": "Linux logical IDs; physical masks pinned by reporting plan"},
  "sets": {"source": "/abs/sets.json", "sha256": "…"},
  "models": {"v1.pt": {"source": "…", "sha256": "d77005d5…"}, "R3a.pt": {}, "R3a-calibration.json": {},
             "states.pkl": {}, "states-rows.json": {}, "states-rows.bin": {}},
  "end_evidence": {"source": "/abs/<repo>/reports/explore/k4s-confirm/<evidence>.json", "sha256": "…",
                   "artifacts_root": "/abs/<repo>/reports/explore/k4s-confirm"},
  "guard": {"job": "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd00-a00",
            "freeze": {"source": "/abs/<repo>/reports/explore/t1/FROZEN-T1.json", "sha256": "24817e16…"},
            "modules": {"common.py": {"source": "/abs/<repo>/reports/explore/t1/common.py", "sha256": "36e5eec3…"}, "…": {}},
            "admissions": {"system-bus-admission.json": {"source": "…", "sha256": "…"}, "idle-services.json": {}},
            "seed_inputs": {"reports/explore/t1/receipts/op5-parent-source-127x03.json": {"source": "…", "sha256": "167cbe71…"}, "…": {}}}
}
```

**Check order.** Every check runs before anything is written:
1. Request: its SHA, schema and exact keys. Host ∈ {127x03, 127x04}.
2. Runtime: `measurement_files` (rule `prepare_bundle.py:117`) must equal the request's canonical SHA. Then `runtime_files` (rule `:36-52`, including the qualified-S1 check) must equal the request's canonical SHA.
3. Models: the exact six names. v1/R3a/calibration must equal the frozen SHAs.
4. State index: schema; `source = states.pkl` pin with `verified: true`; `container = states-rows.bin` pin and byte size; unique IDs; no pickle is executed.
5. Sets: shape. The speed, agreement and packets IDs must be in the state index; golden is only shape-checked, since `tier_backend` only subtracts it.
6. Topology: Linux shape.
7. Evidence:
   - its SHA, schema and kind;
   - every item has `{path, sha256, commit (40-hex), repository_path}`, with safe relative paths and no conflicting duplicate pins;
   - every artifact resolves inside `artifacts_root` (no symlink escape) and matches its SHA;
   - the plan item has SHA `38064dcd…` (hard-pinned) and `study == PREREG-K4S`;
   - the host is in the plan and not forbidden;
   - `compute.slots` is an int ≥ 2;
   - the evidence has a phase on this host.
8. Guard:
   - the job namespace (§A.5);
   - the freeze SHA is `24817e16…` (hard-pinned), and the three deltas are CONFIRM;
   - exactly the nine modules, each equal to its `freeze.files` pin;
   - admissions: `system-bus-admission.json` is required and only it and `idle-services.json` are allowed; idle only on plan idle-exception hosts; the admission `host` must equal the bundle host; the bus identity has exactly `BUS_KEYS` and uid 103;
   - seeds = exactly the freeze bindings plus the 08 join; each equal to `freeze.files` and the binding SHA.
9. Defensive: no source may sit under a `games/` directory or be named `complete.json`, whether as named or as resolved.
10. `--out`: new, absolute, parent exists, no leftover `.partial`, not inside the runtime or evidence trees.

**Determinism.**
- The manifest is canonical JSON of the inputs only: no time, no host probe.
- Copies are byte copies.
- `assembly-receipt.json` holds the request, manifest and assembler SHAs only.
- Tested: identical inputs give a byte-identical bundle tree.

**Read-only on its inputs:** tested by SHA and mtime snapshots before and after a run. **Never reads outcomes:** it parses only the evidence document, the plan, the freeze, the admissions, the seed receipts, the sets and the state index. It hashes and copies the other evidence artifacts without parsing them. Those artifacts are the health-only documents the frozen END reader itself consumes.

---

## D. Tests and results

**Command:** `nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B [-O] -m pytest -q -p no:cacheprovider test_assemble_fleet_reference.py`, with `K4S_FROZEN_ROOT=<read-only origin/main 754c43cd worktree>`.

| Run | Result |
|---|---|
| normal, frozen root set | **92 passed** in 2.58 s |
| `python -O`, frozen root set | **92 passed**, 1 warning in 2.53 s. The warning is pytest's missing-assertion warning under `-O`. The suite uses an explicit `ok()` raise, never a bare `assert`, so the checks stay active. |
| normal, frozen root **unset** | **82 passed, 10 skipped**. Skip reason: `K4S_FROZEN_ROOT (read-only origin/main checkout) not set`. |
| mutation check under `-O` (scratch copies, deleted afterwards) | Removing the host check: 4 failed. Skipping the post-copy re-hash: 1 failed. Skipping the exact seed-map check: 1 failed. **All three mutants were killed.** |

**Coverage:**
- **Happy path:** bundle content, pins, mode 0444, profile and guard config. The 04 variant has no idle admission.
- **Dry run:** byte-identical to the later real manifest, and writes nothing.
- **Determinism**, and inputs unchanged.
- **Every fail-closed branch:**
  - request SHA, schema and keys; host;
  - runtime: path, e4v3 present, measurement, runtime, incomplete, unqualified S1;
  - models: set, frozen SHA, bytes;
  - state index: six variants; sets: six variants; topology: five variants;
  - evidence: SHA, schema, eleven item variants, and a symlink escape;
  - plan: forbidden host, study, three malformed variants; outcome paths, direct and via symlink;
  - guard job: eleven bad namespaces, including T1, K4S reporting, perception, `..` and a trailing slash; the per-attempt name is accepted; 04's perception root is refused;
  - freeze: SHA and each of the three deltas; modules: missing, extra, and K4S-variant bytes;
  - admissions: missing bus, supervisor admission, wrong host, bad uid, malformed idle, idle on 04;
  - seeds: missing join, extra, wrong bytes, 08 without `source_join`, binding absent from `freeze.files`;
  - entry shape; `--out` (exists, partial, inside runtime, inside evidence); copy corruption, after which the partial directory is removed; CLI exit code 2.
- **Frozen consumers** (real frozen bytes from origin/main; fresh `python -I -B` subprocesses; synthetic models, states and admissions):
  - `prepare_bundle.runtime_pins` parity, success and failure;
  - the measurement rule equals the reviewed A5 18-file inventory;
  - `tier_backend.validate_bundle` accepts the bundle and rejects a tampered seed copy. Only its three model-SHA constants are patched to the synthetic models;
  - `state_rows.StateRows` and `telemetry.validate_topology` (128 IDs);
  - `fleet_profile.slot_layout` with the **real K4S plan** on 127x03 and 127x04, giving 5 reference CPUs, 10 background masks and census CPU 63;
  - `fleet_validity.ReportingGuard.__init__` with the real FROZEN-T1, the real nine modules and the real four seeds:
    - it accepts a job staged per §A.5;
    - it rejects a job missing the pinned idle admission, and a job with an unpinned supervisor admission;
    - it detects a changed `repo/` seed.

**Not covered offline, and why:**
- `end_background.k4s_reporting_profile` and `end_evidence.end_evidence` on an assembled bundle. They need a committed K4S END evidence in a git repository with the full counted inventory: 3,000/900 logical blocks with exact raw-exit membership (`end_evidence.py:81-159`). No such evidence exists yet (B1/B2). Building a fake one is a separate B4 builder task.
- `ReportingGuard.__call__` / `parent_source_seed.admit`. They read `/proc`, call `who` and `fleet-console-users`, and run `git show`, all host state. They belong in the on-host preflight (§A.6) and in an offline dry-run of the whole producer (plan draft §8 item 10).
- `TierBackend` construction. It needs torch, the real models and the real states.

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

1. The location and bytes of each host's K4S `system-bus-admission.json` and `idle-services.json` (§A.3).
2. Whether `/mpac/sdicks02/repos/clasher` on 03/04 contains `b2f9e25e` and `ce042b97` (§A.4).
3. That T1's seed `admit` accepts nothing on 03/04 (§A.4).
4. That the guard occurrence files are sealed into the K4S receipt (§A.5).
5. That the 33 external runtime files are available byte-identically, as in T1's runtime lineage (§E).
6. That T1's states, rows and sets are the intended K4S background corpus. The plan draft §8 Q6 says "inference: yes".
