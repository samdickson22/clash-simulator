# K4S END tooling: integration audit r1 (offline, 127x05)

- **What this is:** a one-pass, offline producer→consumer audit of the approved END tooling (safe-input-r3, bootstrap-r1, s1s2-r6, b3-r5, s3s9s10-r3, s5s6s7-r3) against the frozen END code and the real artifacts, plus a fake-host dry run of the whole chain. No production code was changed. Every approved directory passed `sha256sum -c SHA256SUMS` before use.
- **Hard limits kept:**
  - No ssh, scp, rsync or network to any host. The fake hosts are user+mount+UTS namespaces built with the components' own test hooks.
  - Everything ran under `nice -n 19 taskset -c 0-15`.
  - No backend, torch, native or pickle load happened. Every chain stops at `frozen_identity` or earlier.
  - No game, `complete.json`, end-raw or end-complete, reducer or verifier output was opened.
  - Only `INTEGRATION-AUDIT-r1/` was written outside scratch.
- **Audit-only deviations (marked everywhere):**
  - **IA-P1.** A two-line patch to a *scratch copy* of S4 that accepts the dict form of `files` (`runlog/simulated/AUDIT-PATCH-IA-P1.diff`). It was used only to get past B1.
  - **SIMULATED-\*.json.** Stand-ins for the untooled host steps (tools, repository, native/corpus stubs, a00 bundle metadata) and for the proposed B2/B3/B5 fixes, applied on the fake host only.
  - **Synthetic data.** PREFLIGHT-VERIFIED, PREPARED and LAUNCH dicts for the S7/S6 consumers, shaped like the real S5/S7 outputs, plus synthetic END-JOB commits on a scratch byte copy of `repo-full`.
- **Resume log:** `PROGRESS.md`. **Run log:** `runlog/` (drivers, logs, records, fake-host outputs, simulated inputs; `runlog/SHA256SUMS`).

## 1. Headline

The chain **S4 → S10 → (simulated provisioning) → S5 → S5 push wrapper → verify-received → S7 gate (preflight and END) → S6 END wrapper → S6 verifier**, and **S9 equivalence + the frozen END-JOB/claim path**, all run end to end on fake hosts with real inputs. They stop only at the limits listed in §1a. With every listed fix simulated, the frozen `frozen_identity` passes on the staged tree, and nothing else in the chain refuses.

**§1a — where the dry run stops, and why:**
- the stub native file (the deliberate stop before any backend load);
- environment checks that cannot pass inside a namespace on 05: the systemd bus, 05's motd stamps, 05's sshd sessions, and nice 19 vs C5.

**Blocking for production:**
- 6 MISMATCH rows: B1, B2, B3, B5, B6, B7;
- 11 UNTOOLED host or 05 steps: B4 split into U1–U4, plus U5–U11. U12 (two coordinator ruling files) is optional.

## 2. Interface table

Verdicts: **MATCH** = proven by a real or fake-host run (or a static read, which says so); **MISMATCH**; **UNTOOLED** = no reviewed producer; **UNVERIFIABLE-OFFLINE**; **LOW** = a non-blocking gap.

| id | producer → consumer | expectation, producer side (file:line) | expectation, consumer side (file:line) | verdict | evidence | minimal fix (component) |
|---|---|---|---|---|---|---|
| **B1** | S1/S9 runtime-pin-r2 (pinned f81f3655) → S4 `RuntimeInventory.members` | `files` is a dict name→sha, 1557 entries; S9 reads it as a dict (`s9_end_runtime.py:355-356`); frozen `prepare_bundle.py:42` uses `set(...["files"])` (dict keys) | requires a list (`assemble_fleet_reference.py:606-608`) | **MISMATCH** (known) | Real S4 dry run refuses: `S4-REFUSAL-b3r5-runtime-pin-files-shape.md`. With IA-P1 (accept dict keys) all 6 requests pass the dry run (`runlog/logs/s4-dry-*.err`), and the real 03-pf00 assembly writes manifest `ca4ce6ef…` (= its dry run). Frozen `validate_bundle` then accepts that bundle against the S9 runtime (`runlog/logs/frozen-identity.log`) | **S4 r6:** accept the dict form (names = keys) with the same name gates. Add a test with the real pinned shape (the suite's fixture writes a list, `test_assemble_fleet_reference.py:144`). Requests stay valid if `runtime_root` is unchanged |
| **B2** | S10 → S5 / S7 (RC-6) | runtime at `<base>/runtime/runtime-<P12>/` (`s10_stage_host.py:246 BASE_SUBDIRS`, `:272 roots() runtime=<base>/runtime`, `:315-316`) | `--runtime-root` must be `<base>/runtime-<P12>` (`k4s_end_preflight.py:403-405`; `k4s_end_launch_gate.py:319-320`). The END argv script path = `<declared runtime>/reports/explore/k4s-confirm/end_reference.py` (`k4s_end_launch_gate.py:394-397`) | **MISMATCH** (known) | Fake S10 Run A put the runtime at `<base>/runtime/runtime-98566c032d0b` (a-w). S5 v1 refused at `pre_import_pins`: "root …/runtime-98566c032d0b: No such file". After the simulated move (which needed `chmod u+w`, because a-w dirs cannot be renamed across parents) S5 got past it (`runlog/fake-host-outputs/s5-preflight-127x03-l00/l02-result.json`) | **S10 r4:** stage to `<base>/runtime-<P12>`. Make the runtime component's parent `<base>`, drop `runtime` from `BASE_SUBDIRS` and `roots()`, and update the P/F/POST items and `--print-roots`. Change S10, not S5/S7: their pins chain into the gate SHA |
| **B3** | S9 runtime membership → S5 `pre_import_pins`, S5/S7 `--corpus-inventory`, frozen END | members = runtime-pin ∪ `*.py` ∪ six `SUPPORT_MEMBERS` (`s9_end_runtime.py:253-254`). SD1-MANIFEST.json (b8ce7b4c) and t1 corpora.json (3501e2ac) are not members | S5 closure includes SD1 (`k4s_end_preflight.py:96`, read at `:525-547` in role `runtime` `:438`). Corpus inventory = `<runtime>/reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json` (`:78`, `:417-418`; S7 `:89`, `:432-433`). The **frozen END** also needs SD1 in the runtime: S7's END argv has exactly 13 options, with no `--sd1-manifest` (`k4s_end_launch_gate.py:70-72`), so the frozen default `HERE/SD1-MANIFEST.json` applies (`end_reference.py:426`) | **MISMATCH** (known; affects END as well as S5) | S5 v2 (after the B2 simulation): `pre_import_pins FAIL … missing: runtime:reports/explore/k4s-confirm/SD1-MANIFEST.json` | **S9 r4:** add `reports/explore/k4s-confirm/SD1-MANIFEST.json`, `reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json` (and B5's file) to `SUPPORT_MEMBERS` with SHA pins, and hash them in the stdlib closure check. This is membership-neutral for `runtime_files`/`measurement_files` (proved: frozen `validate_bundle` passes on the overlay), so existing bundle pins and requests stay valid |
| **B5** (new) | S9 runtime → frozen `end_reference.k4s_pins` (END and S5 `frozen_identity`) | DELTA-MANIFEST.json (P' blob, sha256 34eca2b7…) is not exported | `json.loads((HERE / "DELTA-MANIFEST.json").read_text())`, `end_reference.py:128`, runs inside `frozen_identity`, i.e. before any claim. It is not in S5's `FROZEN_CLOSURE`, so S5's pre-import pins cannot catch it | **MISMATCH** | Frozen driver (`runlog/logs/frozen-identity.log`): on the S9 runtime, `FileNotFoundError …/DELTA-MANIFEST.json` after `validate_bundle` had passed. On the overlay with DELTA + SD1 + corpora, **`frozen_identity OK`**, which proves these 3 files are the complete set for frozen identity. Fake-host S5 v3 with the same three files: every S5 check passes up to `frozen_identity`, which stops only on the stub native | **S9 r4** (same change as B3). Optional S5 hardening: L6 |
| **B6** (new) | Plan v2 §2 (RC-6 "committed and pushed before the END-JOB"; A4 "commit an outcome-blind disclosure") → S9 `equivalence` (P2-2) | commit placement is not specified | `diff-tree P X` must be exactly `end/END-JOB.json` (`s9_end_runtime.py:805-808`); R6: END dir at X holds only END-JOB (`:809-811`) | **MISMATCH** (rule vs tool) | Scratch clone: X_ok = P'+END-JOB passes (`runlog/logs/s9-equiv-927f53c9….out`). X_rc6 = P'+RC-6 file+END-JOB → `S9 REFUSED: … got ['…/END-JOB.json', '…/run-r1/end-launch/ROOTS-DECLARATION.json']` | **Ruling, no code:** RC-6 declarations, preflight disclosures and any other commit before X go to **main** (or a side branch), never to `k4s-end-r1`. `k4s-end-r1` gets exactly X = P'+END-JOB. (Alternative: an S9 allowlist; not recommended) |
| **B7** (new) | S10 `--print-roots` (RC-6 draft) → S7 `validate_roots` (ROOTS-DECLARATION.json) | schema `clasher.k4s.end-rc6-roots.DRAFT.v1`: `runtime` is a parent dir, `guard_job_parent`, no `tools`, no per-bundle tiers SHA, no `commit` (`s10_stage_host.py:242,277-285`) | schema `clasher.k4s.end-roots-declaration.v1`, exact keys `{base,runtime,bundles,repository,attempts,preflight,tools,guard_parent}`; `runtime` = `<base>/runtime-<P12>`; `bundles{name:{path,tiers_pins_sha256,guard_job}}`; 40-hex `commit` (`k4s_end_launch_gate.py:305-331`) | **MISMATCH** (+ no reviewed producer) | The runner hand-built the S7 form with an unreviewed scratch builder (`requests/make_rc6.py.txt`). That form passes S7 `validate_roots` in the fake gate (`runlog/simulated/ROOTS-DECLARATION.synthetic.json`) | **S10 r4 (or an S7 subcommand):** emit exactly the S7 schema from `--commit` + bundle tiers SHAs (+ guard jobs) and self-check it with S7's `validate_roots` rules |
| **U1** (B4) | (none) → `<base>/repository` (S5 `repository_clone`, S7 frozen-reader, S6 `frozen-exec`, frozen END/S5 git reads) | — | Full non-shallow clone, `verify_clone` role `repository` (`k4s_end_host_tool.py:489-541`: no replace refs, hooks only `*.sample`, no promisor, static si preflight). **HEAD on `k4s-end-r1`**: at P' (or any descendant of 022ec7bf) for preflights, because frozen `fleet_end.artifact` needs `merge-base --is-ancestor 022ec7bf HEAD` (`fleet_end.py:30-33`); at X for END, because frozen `end_job` reads the END-JOB from HEAD and requires it added in exactly one commit (`end_evidence.py:356-366,415-432`). **Writable work tree:** `producer_claim` mkdirs `end/registry/round-RR/<host>/` in it (`end_evidence.py:499`). A clone of `main` fails all of these | **UNTOOLED** | A simulated byte copy of repo-full at P' passes S5 `repository_clone` + `frozen-exec`. After a simulated fetch and checkout of X_ok, it passes S7 frozen-reader + `registry_listing`, and the frozen `end_job`/`producer_claim` work at X_ok (`runlog/drivers/frozen_job_drive.py`) | New **S11 host-repository tool**, spec in §4 |
| **U2** (B4) | (none) → `<base>/tools/` | — | Exactly `detach.sh` 1648dfdc, `k4s_end_exit_push.sh` 65625fc0, `k4s_preflight_push.sh` c9779cfb, `k4s_end_preflight.py` 62532c18, `safe_input.py` 806e5ebb, `k4s_end_host_tool.py` 22c441b1. Single-link regular files, read through the descriptor gate (S7 `file_pins` `k4s_end_launch_gate.py:405,428-436`; wrappers' bootstrap) | **UNTOOLED** | Simulated copy: every S7 `file_pins` = True in both fake gates. The wrapper bootstrap verified the host tool | Add a `tools` component to **S10 r4** (§4) |
| **U3** (B4) | (none) → native `.so` + K4 corpus under `<base>` | — | Files under `<base>`, not in attempts/preflight/repository/tools (`k4s_end_preflight.py:419-422`; `k4s_end_launch_gate.py:436-440`); frozen identities 44874fd6 / a97b1fbf (`end_reference.py:103-104`) | **UNTOOLED** | Stubs pass S5 `input_locations` (open only). Frozen `frozen_identity` refuses the stub ("Unqualified native"): the intended audit stop | Add an `end-inputs` component to **S10 r4** (§4) |
| **U4** (A3) | (none) → interpreter on 03/04 | — | Absolute `python*` with exactly `-B` in the argv (`k4s_end_launch_gate.py:388-391`), able to run the frozen backend (torch, native). The host tool and S7 host program use `/usr/bin/python3` 3.8 (tested) | **UNTOOLED / UNVERIFIABLE-OFFLINE** | The audit bound 05's `e4v3-venv` at `/mpac/sdicks02/jobs/clasher/e4v3-venv` inside the fake 03 (SIMULATED). The host path and torch presence are unknown | A3 check-only probe (read-only, reviewed) + coordinator ruling on the path (§4) |
| **U5** | (none) → S7 `end-launch/<host>/<attempt>/launch-argv.json` | — | Exact argv shape (`k4s_end_launch_gate.py:362-445`), pinned by `--argv-sha256` (`:752-754`) | **UNTOOLED** | Built by hand in the audit (`runlog/simulated/launch-argv.*.json`); both passed `validate_argv` | **S7 r4** `build-argv` subcommand (§4) |
| **U6** | (none) → empty `preflight-received/<host>/<attempt>/` on 05 | — | Must exist and be empty before a preflight launch (`k4s_end_launch_gate.py:475-477`). END receive dirs are made by verifier `--prepare`; nothing makes the preflight ones | **UNTOOLED** | Created by hand in the fake 05 | **S7 r4** `prepare-preflight-receive` (or S5 `prepare`) |
| **U7** | verifier `--prepare` → S7 / verifier read of `end-launch/<host>/<attempt>/PREPARE-PROOF.json` | `--prepare` writes only `<receive>/PREPARED.json` (`k4s_end_verify_push.py:245-268`) | S7 `check_receive` (`k4s_end_launch_gate.py:481-485`) and the verifier (`:467-471`) need a byte-equal pinned copy at `end-launch/…/PREPARE-PROOF.json` ("committed copy") | **UNTOOLED** (small) | Synthesized in the audit; S7 accepted it | **S6 verifier r4:** have `--prepare` also write the PREPARE-PROOF copy exclusively and print its SHA |
| **U8** | (none) → `reports/explore/k4s-confirm/end/END-JOB.json` (commit X) | — | Exact `JOB_FIELDS` bound to the evidence (`end_evidence.py:306-307,415-432`) | **UNTOOLED** | Synthetic END-JOB built from the committed evidence: frozen `end_job` and `producer_registry`/`producer_claim` OK at X_ok; S9 equivalence OK | New small **END-JOB builder** (§4) |
| **U9** | (none) → RC-6 declaration | — | see B7 | **UNTOOLED** | see B7 | see B7 |
| **U10** (B8) | (none) → X present in REPO_FULL for S9 `equivalence` | `prepare-clone` only creates REPO_FULL; `si.git_run` blocks network | `is_commit(g, x)` (`s9_end_runtime.py:803`) on REPO_FULL | **UNTOOLED** | Only possible on a scratch copy via the REPO_FULL test hook | **S9 r4** `refresh-clone --commit X` (§4) |
| **U11** | END claims and sealed receipts → registry commit, `end/receipts/round-RR/<host>/<dir>/`, END-FINAL, `end_pool pool`/`recheck` | S6 pushes claims and receipts to `end-received/` | Frozen: claims committed under REGISTRY_ROOT, receipt copies under RECEIPTS_ROOT, END-FINAL exact fields (`end_evidence.py:570-606`). The pool defaults `--repository` to the runtime ROOT (`end_pool.py:640`), so it must be given the clone explicitly | **UNTOOLED** (S8 is "later" in plan v2) | none | **S8** (after END); spec in §4 |
| U12 | (coordinator) → `BUS-DECISION-<pf>.json`, `REPEAT-RULING.json` | — | Pinned schemas (`k4s_end_launch_gate.py:563-573,764-770`) | **UNTOOLED** (rulings; optional) | not exercised | A template in the runbook is enough |
| M1 | S1 → S2 → evidence commit P' | A1/A1b/S2 commits on `k4s-end-r1` (022ec7bf, 7fc4aff6, 98566c03) | frozen `end_evidence` (artifacts relative to the evidence file, committed at 022ec7bf, ancestor of HEAD) | **MATCH** | Frozen `end_evidence` on the bundle's evidence copy with the scratch clone: OK, counted_hosts [127x03, 127x04] | — |
| M2 | S2 evidence → S4 bundle `k4s-end-evidence/` → frozen END / S5 / S7 | S4 copies evidence + 42 artifacts at evidence-relative paths | S5 `--end-evidence` inside bundle (`k4s_end_preflight.py:423`); S7 (`k4s_end_launch_gate.py:434-435`); frozen `k4s_reporting_profile` pin equality (`end_background.py:77-79`) | **MATCH** | Frozen `end_evidence` passes on `<bundle>/k4s-end-evidence/end-evidence.json` | — |
| M3 | S1b admissions → S3 guard job → S10 → S5/S7 → frozen ReportingGuard | S3 job: FROZEN-T1, admissions, shallow `repo/` with the four seeds | S10 guard-byte equality; S5 `guard_repo`; S7 frozen-reader; `fleet_validity.py:63-130` (`job/<name>`, `job/repo/<seed path>`) | **MATCH** | S10 Run A/B OK (`runlog/s10-records/`). S5 `guard_repo` PASS. S7 `guard_repo` + seed commits OK. **Frozen `ReportingGuard(...)` constructed and passed `check_admissions` on the staged fake host** (`runlog/drivers/guard_ctor_drive.py`) | — |
| M4 | S4 bundle → S10 bundle checks → frozen `validate_bundle` | receipt production v2, PRODUCTION_PINS, runtime/measurement canonical SHAs | `s10_stage_host.py:347-394`; `tier_backend.py:450-469` | **MATCH** | Real 03-pf00 bundle (23.3 GB) staged by S10 to the fake 03 in about 2 min 20 s; frozen `validate_bundle` OK | — |
| M5 | S4 pf00 / a00 / a01 → S5 `bundle_parity`, S7 `bundle_binding` (RC-9 lineage) | per host, the manifests differ only in `guard.job` | `k4s_end_preflight.py:944-954`; `k4s_end_launch_gate.py:598-616`; host recompute `k4s_end_launch_remote.py` frozen_reader | **MATCH** | Guard-free digest equal across pf00/a00/a01: 03 `8e06dc40…`, 04 `9adb181f…`. Fake S5 exported equal digests; the END gate recorded binding `exact` (a00) | — |
| M6 | S9 runtime → S10 (S9.verify) → host tree | S9 manifest 4dd88461 | S10 `runtime_component` | **MATCH** (apart from B2/B3/B5) | S9 VERIFY OK inside S10 | — |
| M7 | S9 `equivalence` ← END-JOB commit X | P'+END-JOB only | `s9_end_runtime.py:797-827` | **MATCH** | X_ok rc 0: 4280 git members identical | — |
| M8 | S5 → `k4s_preflight_push.sh` → push → S5 `verify-received` → `PREFLIGHT-VERIFIED.json` | sealed `preflight/` + metadata pushed to `preflight-received/<h>/<a>/` | `k4s_end_preflight.py:1118-1177` | **MATCH** | Fake 03 under `detach.sh`: `frozen-exec` re-verified the clone + env, S5 ran, push → fake 05 `verify-received` wrote v3 PREFLIGHT-VERIFIED (`runlog/logs/s5-verify-l05.out`; status failed only because of the stub native) | — |
| M9 | PREFLIGHT-VERIFIED (S5 shape) → S7 RC-9 (`preflight_ok`, `launch_identity`, `bus_evidence`, `bundle_binding`) | v3 keys from `verify_received` | `k4s_end_launch_gate.py:518-645` | **MATCH** | Synthetic passing receipts shaped from the real one: the END gate (03, round 00) passed every 05-side check (`runlog/fake-host-outputs/s7-LAUNCH-RECEIPT-end-127x03-r00-l00.json`) | — |
| M10 | S7 gate → host program → staged tree (tools, base/job, bundle, guard job, repository, git env, registry) | as provisioned | `k4s_end_launch_remote.py` steps 7–10 | **MATCH** (with U1–U3 simulated) | Both fake gates (preflight l04, END r00-l00): no failure outside the environment artifacts listed in §1a | — |
| M11 | frozen END claim → S6 `registry-snapshot` → push → S6 verifier | claim at `<repo>/reports/explore/k4s-confirm/end/registry/round-00/127x03/attempt-00.json` (`end_evidence.py:464-510`) | `k4s_end_host_tool.py:557-590`; `k4s_end_verify_push.py:345-440` | **MATCH** | Fake 03 END wrapper: the snapshot captured the frozen-made claim; verifier `verify()` → `UNSEALED`, `claim_without_receipt: true`, C-d satisfied (`runlog/logs/s6-verify.out`) | — |
| M12 | S7 `WRAPPER_SHA256`, verifier `WRAPPER_SHA256` ↔ wrapper bytes | r3 wrapper sha256 65625fc0… | `k4s_end_launch_gate.py:41`; `k4s_end_verify_push.py:35,385` | **MATCH** (the comment "r2" is stale; cosmetic) | `sha256sum` | — |
| M13 | branch assumption | all END data on `k4s-end-r1` | no production tool hard-codes `main` (grep of all tools; S9 `prepare-clone` checks out P detached) | **MATCH** | grep | U1 spec pins the branch |
| M14 | wrappers' post-exit push 03/04 → 05; S7/S10 → 03/04 | NFS-shared `~/.ssh/config` `Host 127x??` (fleet key, no ControlMaster); `known_hosts` has 127x03/04/05 | `StrictHostKeyChecking=yes` (si) / accept-new (rsync) | **MATCH (static)** / live UNVERIFIABLE | `ssh-keygen -F` found each host once | — |
| V1 | frozen backend, background slots, live guard admission (03 idle-service PID 2180947, 04 bus PID), MHz/bus numbers | — | — | **UNVERIFIABLE-OFFLINE** | forbidden here | S5 preflight on the hosts |
| V2 | S7 timers / stamps / quiet-read on systemd 245 | — | `k4s_end_launch_remote.py` parse_* | **UNVERIFIABLE-OFFLINE** | namespace: "Failed to connect to bus" | first real S7 session (fails closed) |
| V3 | real transport (S10 receive over Tailscale/LAN, host→05 rsync), free space ≥ bytes + 50 GiB | — | — | **UNVERIFIABLE-OFFLINE** | fake host: 23.3 GB in about 2.3 min locally | — |
| V4 | RC-7 admission and C-d clocks (05 vs host) | — | `k4s_end_launch_gate.py:838-873` | **UNVERIFIABLE-OFFLINE** (accepted residual) | — | — |
| V5 | verifier `main()` / `--prepare` | — | requires CPU {63} at nice 19 (`k4s_end_verify_push.py:459`) | **UNVERIFIABLE-OFFLINE** (audit CPU rule 0-15); `verify()` was exercised directly | — | — |
| L1 | S7 host program → runtime dir / END-JOB at HEAD | — | S7 never checks that `<declared runtime>` exists, or that `--repository` HEAD holds an END-JOB whose SHA = `--end-job-sha256` | **LOW** | The frozen END fails on these before `producer_claim` (no strike) but burns a launch window | S7 r4: `check_dir(runtime)` + `git cat-file` of HEAD:END-JOB sha |
| L2 | RC-6 lineage | 04's END requires 03's launch under the same `roots_sha256` (`k4s_end_launch_gate.py:696-697`) | all of round 00's bundles, a01 included, must be declared before 03's first launch | **LOW** (rule) | candidate includes a01 | keep |
| L3 | preflight re-run | the pfNN guard job is consumed (side files) | a re-run needs pf01 bundle + guard + RC-6 re-declare | **LOW** (rule) | — | runbook |
| L4 | S4 receipt `assembler_sha256` | recorded (`aabfcb3c…` for the audit-patched copy) | S10/S5 never check which S4 built a bundle | **LOW** | the IA-P1 bundle passed S10 | S10 r4: pin the adopted S4 SHA |
| L6 | S5 `FROZEN_CLOSURE` | omits DELTA-MANIFEST | B5 is caught only inside frozen code (still before claim) | **LOW** | — | optional: S5 pre-import pin of DELTA (changes the gate pin chain) |

**Counts by verdict, over the 37 rows above:**

| Verdict | Count | Rows |
|---|---:|---|
| MISMATCH | 6 | B1, B2, B3, B5, B6, B7 |
| UNTOOLED | 12 | U1–U12; U4 also UNVERIFIABLE; U12 optional |
| MATCH | 14 | M1–M14; M6 is "MATCH apart from B2/B3/B5", M14 static only |
| UNVERIFIABLE-OFFLINE | 5 | V1–V5 |
| LOW | 5 | L1–L4, L6 |

## 3. Attempt rules vs tools

| Rule (plan v2 §3) | Tool behaviour | Verdict |
|---|---|---|
| One launch SSH, closed before admission (RC-7) | S7 runs one `si.SSH_OPTIONS` session; the host program exits ≤ 10 s after launch. `admission` records close < admission − 1 s, and the 04 END requires 03's record | MATCH. Not enforced for 03's own attempt (recorded only; accepted) |
| C5: no SSH to the timed host | S6/S5 wrappers push outbound only after exit; S7 refuses other sshd sessions on the host and a local ControlMaster (`ssh -O check` rc 255 only) | MATCH. S10 staging, U1 clone and the X fast-forward must finish before the window (rule) |
| Quiet-read v3, the second read inside S7's session | Both reads, 30 s apart, inside the one session (stricter than the plan) | MATCH |
| Timers: unfiltered, ≥ 2 h or allowlisted | `systemctl list-timers --all`, TZ=UTC; parse failure = refusal | MATCH (V2 for the real format) |
| Stamps | release-upgrade age ≤ 24 h − window; updates-available newer than apt lists | MATCH |
| C-d (03 seal verified ≥ exit + 1300 s before 04) | verifier `c_d_satisfied`; S7 04 END checks the ACK epochs + lineage | MATCH |
| RC-9 lineage pf00 / a00 / a01 and guard jobs | `-pfNN` / `-rdRR-aNN` checks, the guard-free digest (exact or guard-job-equivalent), the 03 receipt/ACK/admission chain | MATCH (M5) |
| Frozen END: `--repository` HEAD has the END-JOB, claims, evidence on `k4s-end-r1` | frozen `end_job` / `producer_claim` / `fleet_end.artifact` all use HEAD; S9 equivalence forbids extra commits P..X | needs U1 and the B6 ruling; nothing assumes `main` |

## 4. Host and 05 steps that need a NEW reviewed tool (minimal specs)

1. **S11 host repository (U1).**
   - Per host, create `<base>/repository` exclusively. Two ways:
     - from a `git bundle` of `k4s-end-r1` made on 05 from REPO_FULL and shipped by an S10 receive;
     - or by an https clone from GitHub with `--no-checkout --template=`, no filter, P2-4 env, hooks absent.
   - Then `checkout --detach <commit>`.
   - Verify with `k4s_end_host_tool.verify_clone(role="repository")` and `rev-parse HEAD == <commit>`. Record a receipt.
   - Mode `ff --to X`: fetch the second bundle (or https), require P ancestor of X, check out X detached, verify again, and require `git show HEAD:…/END-JOB.json` SHA = the pinned END-JOB SHA.
   - Never `main`. Keep the work tree writable (frozen claims).
   - Logins: one per mode. Run outside any END window.
2. **S10 r4 components (U2, U3, B2, B7).**
   - `tools`: the 6 files above at the S7 pins → `<base>/tools/`, a-w, single-link.
   - `end-inputs`: native `clasher_core.abi3.so` 44874fd6 and K4 corpus a97b1fbf from a named 05 source with SHA → `<base>/inputs/end-inputs-r1/`.
   - The runtime goes at `<base>/runtime-<P12>` (B2).
   - `--print-roots` emits the exact S7 `clasher.k4s.end-roots-declaration.v1` given `--commit` and the bundle tiers SHAs (B7).
3. **S9 r4 (B3, B5, U10).**
   - `SUPPORT_MEMBERS` += SD1-MANIFEST.json (b8ce7b4c), DELTA-MANIFEST.json (34eca2b7) and t1 corpora.json (3501e2ac).
   - The closure check pins them.
   - New `refresh-clone --commit X`: https fetch of `k4s-end-r1` into REPO_FULL with prepare-clone's hygiene, `verify_clone`, X a descendant of P.
   - Then rebuild the runtime (new manifest SHA; `runtime_files_sha256` and measurement are unchanged, so bundle pins are unaffected).
4. **S4 r6 (B1).** Accept the dict `files` (keys) and add a real-shape test. Re-assemble the 6 requests (regenerate them only if the S9 output path changes).
5. **S7 r4 small additions (U5, U6, L1).**
   - `build-argv --kind --host --attempt …` from RC-6 + constants: writes `launch-argv.json` exclusively and prints the sha.
   - `prepare-preflight-receive`.
   - Optional L1 host checks.
6. **S6 verifier r4 (U7).** `--prepare` also writes `end-launch/<h>/<a>/PREPARE-PROOF.json` (byte-equal, exclusive).
7. **END-JOB builder (U8).**
   - Fields from the committed evidence: evidence sha, completion, plan, counted_hosts; k4s manifest 74314eda; declared_utc/by.
   - Commit it alone on `k4s-end-r1`.
   - Self-check on a scratch clone: frozen `end_job` + S9 `equivalence` (exactly what `runlog/drivers/frozen_job_drive.py` + `s9_equiv_drive.py` do).
8. **A3 probe (U4).** A read-only, one-login check of the declared interpreter path, its version and the torch/native import capability (without loading models). Coordinator ruling on the path.
9. **S8 (U11, after END).**
   - Collect claims from `end-received` (hash-bound to the listing).
   - Commit them under REGISTRY_ROOT on `k4s-end-r1`.
   - Copy sealed receipts hash-only into RECEIPTS_ROOT.
   - Build END-FINAL.
   - Run `end_pool pool`/`recheck` with an explicit `--repository` and one pinned interpreter (PC3).

## 5. Recommended fix packaging (order)

1. **Rulings now (no code):**
   - B6: RC-6, disclosures and anything else before X go to `main`, never `k4s-end-r1`.
   - A3: the interpreter path.
2. **Part A package `s3s9s10-r4`:** S9 (B3, B5, U10) + S10 (B2, B7, U2, U3) + S11 (U1) as a new sibling in the same pin chain. This is one Sol review because all three share `end_prep_common` and the pin chain.
3. **`b3-r6` (B1).** Independent and two lines; review it in parallel with step 2.
4. **Part B `s5s6s7-r4`:** S7 `build-argv` + `prepare-preflight-receive` (U5, U6), verifier `--prepare` PREPARE-PROOF (U7), optional L1/L6. This touches the gate pin chain only. No change to the S5/S7 layout is needed if S10 adopts B2.
5. **END-JOB builder (U8),** then the A3 probe (U4), then S8 (U11), which is needed only after the END runs.
6. **After 2–4:**
   - rebuild the S9 runtime;
   - S4 ×6;
   - S10 `--dry-run` ×2 hosts;
   - re-run this fake-host chain (drivers in `runlog/drivers/`) before asking for the A2 GO.

## 6. Scratch and cleanup

- Scratch locations: `/dev/shm/ia-r1/`, `/tmp/ia-r1-bundles-*` (the 23 GB IA-P1 bundle), `/tmp/ia-r1-hosts-*` (fake 03/05 roots) and `/tmp/ia-r1-rec-*` (S10 records, copied to `runlog/s10-records/`). All of them are removed at the end (PROGRESS records it).
- Fake-host namespaces never changed anything outside these directories. No host was contacted.
