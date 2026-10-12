# SOL review — K4S END tooling, full package, round 1

Independent review, 2026-10-12. **Overall: REQUEST_CHANGES.** The shared layer and most earlier repairs work, but the package still has bootstrap boundary defects, incompatible guard-repository assumptions, an unchecked global-config path, and incomplete launch prerequisites. Passing component suites do not establish that the assembled workflow can run safely.

## Scope, authority and immutable sources

I read the four prior SOL END reviews and COORDINATOR using `git show origin/main:reports/strategy_council_20260928/COORDINATOR.md`, including P2-1–P2-4, E1–E5, R6/R7, D1–D4, the full-clone rule and frozen-reader wrapper. The observed origin/main was `72426428cd48db0342b2cb6358211424ebc686d0`. I also read the committed receive-SHA erratum from origin/main; it is absent from the original daaf9d00 directory inventory.

Source citations below refer to these immutable candidates, relative to `reports/explore/k4s-confirm/run-r1/end-prep/`:

| Citation prefix | Candidate | Source file |
|---|---|---|
| SI | daaf9d00, safe-input-r3 | safe_input.py |
| S1 / S2 | 37349808, s1s2-r4b | s1_copy_end_sources.py / s2_end_evidence.py |
| S4 | 37349808, b3-r4b | assemble_fleet_reference.py |
| C / S1b / S3 / S9 / S10 | 4ada282b, s3s9s10-r2 | end_prep_common.py / s1b_copy_admissions.py / s3_guard_job.py / s9_end_runtime.py / s10_stage_host.py |
| HT / PF / EV / LG / LR | bedf553d, s5s6s7-r2 | k4s_end_host_tool.py / k4s_end_preflight.py / k4s_end_verify_push.py / k4s_end_launch_gate.py / k4s_end_launch_remote.py |
| EW / PW | bedf553d, s5s6s7-r2 | k4s_end_exit_push.sh / k4s_preflight_push.sh |

All five SHA256SUMS inventories verified: 26, 19, 17, 19 and 48 entries, respectively. All five vendored layers equal `806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00`. The E1 alias, four E4 OIDs and nine E5 OIDs independently match `git ls-tree 104fa857` in path, mode, type and OID; this check used metadata only. Verification-before-execution of layer bytes is present; finding 1 concerns the access preceding verification.

No repository edits, commits, pushes, real SSH, network clone, or real-host execution occurred. No real outcome or exempt opaque-file payload was opened. Tests used committed tooling exports in `/dev/shm`, synthetic repositories, canaries and fake hosts. S4's two real-Q6 tests were excluded before execution. Its frozen-consumer tests used a 43-path code/metadata export; every exported name passed the shared name gate first. S1/S2's existing tests read their declared committed health metadata and frozen closure, not outcome payloads. The requested report is the sole persistent reviewer output.

## Component verdicts

| Component | Verdict | Reason |
|---|---|---|
| safe_input r3 | APPROVE_WITH_CONDITIONS | Use its documented roles and opaque APIs; callers must enforce full-clone provenance, expected identities and the accepted mount/race assumptions. No new defect in the layer itself reproduced. |
| S1, unchanged | APPROVE | Existing approval retained; 34 S1 controls also passed in both modes. |
| S2 r4b | REQUEST_CHANGES | Earlier Git/profile/path findings repaired; sibling-layer bootstrap still follows ancestor aliases (1). |
| S4 r4b | REQUEST_CHANGES | Earlier Git/name/E4-ordering findings repaired; sibling-layer bootstrap still follows ancestor aliases (1). |
| S1b r2 | REQUEST_CHANGES | Remote admission defect repaired; shared Part A bootstrap remains unsafe (1). |
| S3 r2 | REQUEST_CHANGES | Earlier three findings repaired; shared bootstrap (1) and S3-to-host shallow-repository incompatibility (2). |
| S9 r2 | REQUEST_CHANGES | Export/location findings repaired; shared bootstrap (1) and full-clone check not enforced by build/verify/equivalence (4). |
| S10 r2 | REQUEST_CHANGES | Earlier four findings and D4 receive repaired; shared Part A bootstrap remains unsafe (1). |
| S5 r2 | REQUEST_CHANGES | Frozen-code anchor repaired; wrapper bootstrap (1), guard-repo incompatibility (2), and global config path (3). |
| S6 r2 | REQUEST_CHANGES | Redirection and C-d defects repaired; wrapper bootstrap (1) and frozen-exec global config path (3). |
| S7 r2 | REQUEST_CHANGES | Process-status and alias controls repaired; guard-repo incompatibility (2), global config path (3), and incomplete RC-9 binding (5). |

## Numbered findings

1. **END-FULL-F1 — BLOCKING: bootstrap reads precede ancestor/role confinement.** `S2:109–135`, `S4:86–108`, and `C:40–70` open the sibling `safe_input.py` using a full pathname and leaf-only O_NOFOLLOW. They check its descriptor's link count and its SHA, but do not reject a pre-existing symlink in the parent path before reading. Their production default uses `abspath(__file__)`, which retains ancestor aliases. These reads happen before the layer's own `open_root`/name gates can run.

   Independent probes gave each loader a synthetic ancestor alias into a `games/` tree. Wrapping `os.read` and identifying the canary inode showed the complete canary consumed before the SHA refusal, normally and under -O. This is a static alias, not the accepted concurrent-replacement residual. A late pin refusal does not undo the read.

   The wrappers have the same defect in stronger form: `EW:38–39` and `PW:36–37` use `test -f`, a leaf symlink test, then raw `sha256sum` on the host tool. There is no pre-hash nlink or ancestor gate. Both wrappers send a hard-linked synthetic canary, and a canary behind a symlinked tools directory, to the real `/usr/bin/sha256sum --check`, then exit 90 on its mismatch. A recording shim forwarded the unchanged checksum input to the real binary and recorded its rc 1; it did not provide a replacement hashing implementation. The four cases reproduce in both modes. An initial strace attempt was unavailable because ptrace is prohibited; this finding does not depend on that attempt.

   **Required:** make the stdlib bootstrap perform a complete normalized/name/ancestor walk and regular/single-link/size checks before content access, then execute the exact verified bytes. Apply this to the wrapper's host-tool bootstrap too, preserving exclusive metadata creation. Do not use a pathname re-open after hashing as the identity proof. Add entrypoint tests with alias substitutions before bootstrap, including mismatching bytes, asserting zero canary consumption.

2. **END-FULL-F2 — HIGH: S3's required shallow guard repo is rejected by S5/S7.** S3 builds it with `--depth=1` and an explicit shallow allowance (`S3:194–215`), and `prove_repo` requires it to be shallow (`S3:221`, `247–248`). HT constructs an ordinary `GitRepo` without that allowance in both `verify_clone` and `seed_commits` (`HT:242–250`, `266–270`). SI consequently refuses `.git/shallow` before git runs (`SI:1443–1445`). S5 invokes these helpers on the guard repo (`PF:909–912`); S7 does likewise (`LR:228–230`).

   **Probe:** build the candidate's synthetic S3 guard job, then feed its actual `job/repo` into the unchanged host checker. It refuses `indirection: .../.git has shallow (shallow not declared)`, normally and under -O. This prevents the legitimate staged workflow from reaching preflight/launch. Part B fixtures use full stand-in guard repositories and miss the incompatibility.

   **Required:** agree one guard-repository contract across S3/S5/S7. If the minimal Q3 shallow repo remains intended, permit it explicitly only for that proven guard role in both host helpers, retaining exact seed commits, bindings, config/ref checks and all other indirection refusals. Keep the evidence/END-JOB repository full. Alternatively change S3's construction and proof together. Test an S3-produced repo through S5 and S7, rather than constructing another repository shape.

3. **END-FULL-F3 — BLOCKING: relative XDG_CONFIG_HOME is checked at a different location from frozen git.** `HT:223–225` converts a relative value such as `xdg` to `/xdg/git/config`. It neither rejects it nor replaces it in the executed environment. `frozen_git_env` preserves the original value (`HT:199–204`). On the installed Git 2.25, frozen `git -C <repo>` reads `<repo>/xdg/git/config` instead. The static check therefore misses an include/driver config that the later reader honors.

   **Probe:** a synthetic full repo had `repo/xdg/git/config` containing an include of `repo/games/synthetic-config`, whose only payload was a reviewer-generated config canary. The host checker returned `checked=[]`; raw git under the candidate's `frozen_git_env`, with `-C repo`, returned that canary value. Both modes reproduced it. No real outcome or global user config was read. S5 uses the check and environment at `PF:915–920`; S6 frozen-exec uses them at `HT:333–339`; S7 checks at `LR:231` and relies on the same wrapper environment.

   **Required:** reject relative XDG_CONFIG_HOME, or establish an absolute canonical value and install that exact value in every executed frozen-reader environment. Apply the role/name gate to config paths, and preserve no-follow/nlink and include/driver refusals. Test `git -C` with a relative XDG path containing a forbidden include. Retaining HOME is acceptable only when all config locations actually consulted by the installed git are checked.

4. **END-FULL-F4 — HIGH: the full-clone verifier is an optional preparation check, not a build precondition.** `S9:239–252` correctly rejects promisor config/packs, hooks, shallow state and replacement refs, but its only production call is `prepare_clone` at `S9:266`. Build proceeds directly through `commit_pins`, locate and member planning (`S9:431–438`); `verify` and `equivalence` also do not call it (`S9:530`, `560`). The shared git helper deliberately does not detect promisor config.

   **Probe:** add `remote.origin.promisor=true` to the synthetic dedicated clone. `S9.verify_clone` refuses `indirection`; unchanged `S9.build` accepts the same repository and produces a successful runtime manifest. Both modes reproduce this. No missing objects or network access are needed: all synthetic objects are present.

   **Required:** require full-clone verification at the content-producing/authoritative entrypoints, or consume an enforced immutable preparation binding whose repository identity/config/pack facts are rechecked. A directory named `repo-full` is not proof that preparation occurred or that the clone still has that shape. Keep partial-clone detection at the dedicated-clone boundary if desired, but make that boundary mandatory.

5. **END-FULL-F5 — HIGH: RC-9 still accepts a preflight for different launch inputs and an ACK from another round.** `LG:397–409` binds runtime/repository/manifest, declared bundle entries, and evidence/SD1 pins, but does not compare the preflight's native/corpus identities with the launch argv, or require its compare bundle to be the actual attempt bundle. `LG:440–448` verifies 03's host/attempt/complete/C-d fields without binding the prior attempt's round to the 04 round being launched.

   **Independent local probes:** prerequisites accepted a changed native path; a changed corpus path; an attempt bundle `a01` although the preflight qualified compare bundle `a00`; and a 03 ACK naming round 01 for a round-00 04 launch. All passed argv structure checks and RC-9, normally and under -O; no SSH or foreground run was needed. A supplemental inconsistent receipt with numeric loaded bus 0.8% but `bus_band=bus_gate="proceed"` also passed (`LG:410–424`). The latter is a missing consistency check, not evidence that unmodified S5 emits an incorrect band.

   **Required:** bind the qualifying preflight to every relevant current launch input, including native/corpus and corpus inventory identity, and the actual attempt bundle or an explicitly verified equivalence that explains fresh guard-job differences. Require the prior 03 completion and admission to belong to the current round and established launch lineage. Validate the numeric loaded-bus evidence against the recorded band, rejecting missing/nonfinite/inconsistent values. Preserve the repaired schemas, SHA provenance, duration/load, C-d, bus decision and RC-7 checks.

6. **END-FULL-F6 — MEDIUM: committed Part B test shims are not executable.** Git records `tests/shims/{hostname,nice,rsync,taskset,timeout}` as mode 100644. `tests/helpers.py:141–145` puts this directory directly on PATH; no fixture sets execute bits. The documented matrix (`README.md:250–260`) is consequently unreproducible from the committed package.

   **Pristine committed-mode runs:** normal **243 passed / 33 failed**; -O **242 passed / 12 failed / 22 skipped**. Even `test_complete_pushes_everything_through_safe_input` fails immediately because its fake hostname cannot execute and the real local hostname is used. In temporary copies only, setting execute bits on those five shims restores the claimed suite behavior (see verification below); no source bytes were edited.

   **Required:** commit the intended modes or create executable copies in the fixture. Rerun the committed package, preserving the distinction between production optimization refusal and deliberately patched test helpers.

## Disposition of every earlier required finding

“Repaired” below means its specific reproduction/control now refuses correctly. It does not waive the new bootstrap or integration findings above. Named controls are in the corresponding candidate's delivered tests and were rerun in both modes where optimization is supported.

| Earlier finding | Disposition and immutable source evidence | Replayed controls |
|---|---|---|
| S2-R2-F1, filesystem/auxiliary roles | Repaired after bootstrap: all-path lexical pass and role construction at S2:436–472; SHA-bound reads at :492; exact artifact checks at :978–1015. | Outcome/END auxiliary paths, aliases, hard links, profiles and S1 receipt canaries. |
| S2-R2-F2, missing/empty profile | Repaired: exclusivity/field checks at S2:910–954; source used at :971. | Empty and null host profiles, absent/both sources, duplicate/nonfinite JSON. |
| S2-R3-F1, Git replacement/env | Repaired: Checkout.show uses SI git_show_file at S2:285–289; artifact prechecks :1007–1015; controlled frozen env :305–326 and :1017. | Replacement refs, GIT_DIR/object/config overrides, raw frozen-reader positive control, rc 37. |
| S4-R2-F1, hard links | Repaired for inputs: SI walk and descriptor gates at SI:321–352, :916–980; S4 RuntimeInventory and Sources use them (:302–337, :424–485). | Runtime/measurement/input hard links, descriptor-time substitutions, E1 target aliases. |
| S4-R2-F2, strict END | Repaired: S4:292–297 uses the shared name gate; runtime walk :426; committed input role :549–560. | Sealed receipt used as sets, END runtime subtree, auxiliary repository/output/job roots. |
| S4-R2-F3, synthetic pin reader | Repaired: S4:374–403 checks the pins through confined Sources before parsing, then fixes exemption identities. | Pins in games, ancestor aliases, hard links, widened exception set. |
| S4-R3-F1, Git indirection | Repaired: S4:554–560 uses SI git_run/git_plan; :567–583 reads/hashes planned objects only. | Replace refs, inherited Git overrides, rc 37, object-header/identity controls. |
| S4-R3-F2, outcome-name family | Repaired: common case-insensitive SI:179–248; source/runtime/repository gates use it. | END-FINAL, attempt, end-raw-copy, complete-v2 and case variants, with inode audit. |
| S4-R3-F3, E4 metadata ordering | Repaired: complete git_plan at S4:559 precedes check_e4 :578–583; SI:1594–1652 completes screening before any planned blob access. | Late unknown/wrong-mode E4 entry refuses before earlier E4 blobs are requested. |
| S1b-F1, remote hard-linked admission | Repaired: S1b:151–162 uses the pinned remote reader; SI:321–352 gates nlink before content. | Remote hard-link probe; exact three admission operands, stale E3 identities, second-host refusal. |
| S3-F1, admission override/aux input | Repaired: exact E3 role S3:126–131 and SHA-bound reads :172–187; override removed. | END-located admission/manifest, doctored S1b SHA/nlink, removed option. |
| S3-F2, verify aliases/derived paths | Repaired after bootstrap: S3:312–330 inventory; :401–425 caller-bound job name and pinned manifest/admission reads. | Ancestor/leaf aliases, hard links, games/complete/FIFO, tampered seed, extra member. |
| S3-F3, preflight guard job | Repaired: S3:70 and :83–96 support -pfNN; S10 consumes S3 target checks. | -pfNN build and staging, invalid/ambiguous job forms. |
| S9-F1, export all blobs/E exceptions | Repaired: S9:183–193 selects member metadata; :438–442 plans before export; SI enforces E1/E4/E5. | Nonmember canary OIDs never requested; family members, E1 text/mode, changed E4/E5 OIDs. |
| S9-F2, locate/verify roots | Repaired: fixed Q5 root/exact names S9:114, :283–303; pinned manifest/root and gated inventory :514–546. | Forbidden Q5 root, hard-linked external, missing bytes, auxiliary manifest aliases. |
| S10-F1, recursive/auxiliary reads | Repaired after bootstrap: S10:131–230 uses S9/S3 verification and gated bundle inventory; aux manifest route :393. | 19 bundle refusal cases, games/complete/hardlink/symlink, aux root/SHA aliases; zero fake logins. |
| S10-F2, base mismatch | Repaired: S10:66 uses SI.END_BASES; declared roots :90–113; creation :444–450. | Root declaration equality and full synthetic runtime/bundle/guard stage. |
| S10-F3, masked probe status | Repaired: S10:282–289 captures statuses; :318–345 checks them before stdout use. | Valid df/who/hostname output plus rc 37, wrong host, low space. |
| S10-F4, synthetic bundles | Repaired: S10:155–166 rejects stamps and binds receipt; PF:350–360 repeats rejection. | Synthetic field/name, nonproduction receipt, wrong status and host. |
| S5-F1, unanchored code import | Repaired: fixed 74314eda closure at PF:377–399 precedes frozen import :922–927. | Unanchored manifest and executable canary, modified closure/verifier, positive verified import. |
| S5-F2, input/output aliases | Repaired for runtime/bundle roles: PF:251–309 layout/Policy/Writer; :350–373 bundle/guard roles; :961–997 received verification. Wrapper bootstrap remains finding 1. | Aliased closure/bundle/native/guard source, existing output, test stamp and wrong job form. |
| S5-F3, background-only/04 bus | Substantially repaired: PF:829–853 exports qualifying load/duration; :478–482 bands; :1005–1016 exports verified summary; LG:387–424 enforces it. Finding 5 covers remaining launch binding/consistency. | Diagnostic mode, short loaded span, 04 0.1/0.5/0.8% bands, login and sample count. |
| S6-F1, claims/aux/sealed roles | Repaired: HT:139–190 and :276–300 gated registry; EV:173–196 SHA-bound claims; :277–291 separates D3 hashes from ordinary members. | Registry hard link, games member, wrong scope, extra claim/member, D3 SHA/alias refusal. |
| S6-F2, metadata truncation | Repaired for writes: EW:79, :97, :140, :150 use exclusive CLI; HT:332; corresponding PW writes use the same path. Bootstrap reads remain finding 1. | Seven pre-existing metadata aliases, aliases planted midrun, preflight argv hard link; canary bytes preserved. |
| S6-F3, early ACK | Repaired: EV:232–239 refuses before exit+1300; LG:446–448 repeats C-d requirement. | Boundary/early verification, claimed-without-receipt, complete/failed/unsealed outcomes. |
| S7-F1, local/host aliases | Repaired in the gate: LG:304–324 fixed/pinned roles; LR:277–285 descriptor/base checks and :320 exclusive creation. | Full fake-host base symlink, tool hard link, local receipt/argv/proof aliases. |
| S7-F2, failed ps/hostname | Repaired: LR:170 SI.ps_checked; :243 hostname_checked; :268 refusal handling. | Valid process table plus rc 37, valid hostname plus nonzero, malformed/missing-own-process table. |
| S7-F3, insufficient RC-9 | Partially repaired: LG:372–455 adds schemas, provenance, load/duration, bus decision, ACK/C-d/RC-7. Changed-input and other-round cases remain finding 5. | Earlier Boolean-only, diagnostic, short-duration, failed/early ACK and false RC-7 cases refuse; new binding cases still pass. |

Adoption preserves exact S1/phase bindings and finite-positive MHz refusal (`S2:646`, `900–908`, `996–1006`), fixed frozen closure verification, test-only stamps, independent copies and immutable clock-join refusal. Diagnosis remains report-only (`S2:1170–1231`); it does not repair, zip or re-time rows. The shared ordinary gates themselves reject static aliases before content, with both walk and descriptor nlink checks. The exceptions are the pre-layer bootstraps identified above.

## Opinions on the nine disclosures

1. **Six D1 support files: technically justified; accept subject to explicit coordinator ratification of the narrow D1 clarification.** The exact six are declared at S9:68–74. Selection is runtime pins plus Python names plus that support set (:183–188); runtime_files remains only pins plus Python names (:327–335). The pin list, binding and K4S manifest have fixed SHAs (:160–164); procedure/spec pins come from the anchored K4S closure and build_tiers.sh from the fixed measurement inventory (:338–353). The frozen runtime/measurement rules need them. They do not create an open-ended auxiliary export permission. The delivered member-set test and independent END-FINAL/Complete-v2/games nonmember probes confirm exclusion without blob access.

2. **S9 network clone outside git_run: acceptable narrow exception.** S9:260–265 uses the same scrubbed environment, no replacement objects, disabled hooks/fsmonitor, transport restriction, template suppression, no filter and fsck. It verifies before checkout (:266–271). Only file:// synthetic clones ran in this review. The flaw is failure to enforce that verified-clone boundary at later entrypoints (4), not using the network-capable clone exception itself.

3. **S3 removes its own FETCH_HEAD: acceptable.** S3:204 calls C:195–210 inside the fresh partial guard repo; the parent is descriptor-confined and the leaf must be regular and single-link. This is deletion of this invocation's own transport metadata, not cleanup of existing study/host data. I found no reason to require it to remain. The shallow repo it leaves has the separate compatibility defect (2).

4. **S10 receive receipt instead of disk rehash: acceptable within the stated nonconcurrent staging assumptions.** SI's receiver creates exclusively, hashes bytes being written, fsyncs, checks descriptor size/nlink/mode, and returns a manifest-bound per-file receipt (SI:2226–2343, :2414–2446). S10 validates it before F and checks moved-directory identity afterward (S10:452–474). This establishes what the receiver wrote, not immunity to later same-inode rewrites or disk corruption. Under the accepted residual, a second full disk read is not a mandatory repair. The fake-host transfer corruption/truncation, destination-alias, non-clobber and finalize controls pass.

5. **S6/S7 rename and names-only exceptions: accept; retained-HOME implementation needs repair.** TRANSFER-DONE avoids the never-grantable complete-json family while every consumer uses the new name. Registry listing (HT:139–190), S5's emptiness checks, and sealed-directory listing (EV:144–170) inspect names and types without parsing opaque results. D3 content reaches only the hash-only helper (EV:283–289). These limited listings are appropriate. Retaining HOME and checking configs statically can work on Git 2.25, but the current relative-XDG behavior is unsafe (3); this part is not approved as implemented.

6. **S2 diagnose-clock bound by full commit only: accept.** S2:1202–1209 selects exact health paths from pinned completion and a full commit. SI.git_show_file verifies the tree entry's type/size/OID and rehashes content to that OID before returning it (SI:1499–1520, :1555–1583). This is a cryptographic committed-object identity, not an unbound filesystem read. Diagnosis records the resulting SHAs (:1217–1218) and cannot produce an approval/repair receipt (:1228–1231). A separate predeclared SHA-256 is not needed for this report-only committed-byte route.

7. **S4 partials/freshness/HEAD E5: accept.** Failure retains the partial rather than destroying evidence (S4:947–983); publication still checks final absence (:986–998), with its documented accepted check/rename residual. Offline guard-job construction cannot prove host lifetime freshness; S7 checks side-file/STOP absence immediately before launch (LR:225–227), and S5 performs its host checks. E5 runtime OIDs are compared to the approved committed HEAD entries (S4:585–590, :709–710), which is stronger than matching a self-declared runtime list and compatible with the P-to-X END-JOB-only transition. Finding 2 currently prevents the intended host flow, so freshness checks alone do not establish package readiness.

8. **Misprinted receive SHA plus erratum: documentation-only, acceptable with the erratum shipped.** Independently computed from pinned r3 bytes: `39a92e9d55f9ffefba57bae453677bad7c834f7761283268b84e40bb2d1210b4`; reader SHA remains `2d2f212d73b49176c53b1a03a621b64fbc6a8d4c15bd18051ac31f91016a6152`. The origin/main erratum records exactly these. C:35–36 pins the correct values. Correct the README on the next revision and include the erratum in distributed documentation/checksum inventories; it is not a receiver-code defect.

9. **Residuals: narrowly acceptable, with enforced prerequisites.** Expected SHAs/object identities catch same-size byte changes after approved identity selection; they do not erase a prohibited pre-read alias access or prove source provenance. Bind mounts are not detected by canonical pathname/nlink checks and must remain part of the trusted single-operator mount assumption; no outcome-bearing bind mount is authorized. Partial-clone detection may live in repo-full verification rather than generic SI, but that verification must be an enforced precondition (4). None of these residuals excuses findings 1 or 3, both of which use static paths/configuration.

## Verification and limits

Every suite/probe interpreter used `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 with `nice -n 19`, `taskset -c 0-3`, `PYTHONDONTWRITEBYTECODE=1`, `-B`, and cacheprovider disabled. All source copies were in `/dev/shm`; fixture output used reviewer-owned `/tmp` bases where the components intentionally reject `/dev/shm` output roots. Children inherited priority/affinity. Frozen S3/S9 children intentionally stay unoptimized; S7's shipped host body uses the fleet Python. Production S5/S6/S7 optimization refusals remain tested; helper overrides are explicitly synthetic.

| Delivered suite | Normal | -O |
|---|---:|---:|
| safe_input r3 | 548 passed | 548 passed |
| S1/S2 r4b | 270 passed | 270 passed |
| S4 r4b, safe subset including frozen consumers | 461 passed, 2 deselected | 461 passed, 2 deselected |
| S1b/S3/S9/S10 r2 | 211 delivered tests passed | 211 delivered tests passed |
| S5/S6/S7 r2, committed shim modes | 243 passed, 33 failed | 242 passed, 12 failed, 22 skipped |
| S5/S6/S7 r2, only five scratch shim modes corrected | 276 passed | 254 passed, 22 skipped |

The Part A successful full run contained the 211 delivered tests plus two reviewer integration probes, hence pytest displayed 213 passed. The additional D1 controls were run separately. The corrected-mode delivered-suite totals are **1,766 normal passes** and **1,744 optimized passes**, with two deliberate real-Q6 exclusions per mode and 22 deliberate verifier optimization skips. These are distinct-suite counts, not inflated by repeated runs.

Independent added controls: **24 per mode** (six shared-layer D3/D4/opaque-reader cases, five Part A integration/member-set cases, thirteen Part B wrapper/bootstrap/config/RC-9 cases). Positive controls prove that extra nonmember outcome-named blobs are never requested, D3 forbidden ancestors refuse before seal access, E4/E5 ordinary JSON reads refuse unopened, and D4 forbidden destinations start no fake transport. Negative controls reproduce findings 1–5. A reproduction test passing means the described defective behavior was observed, not that the candidate is approved.

Reviewer harness corrections were separated from candidate defects: the first Part A combined run accidentally imported session fixtures twice, then was rerun successfully without those duplicate fixture exports; the first D1 added fixture descended from X and was correctly refused by R6, then used P and an advertised synthetic branch. The unavailable ptrace probe and these setup failures are not counted as candidate regressions. The committed Part B shim-mode failures are candidate packaging evidence, recorded before temporary mode repair.

No real preflight/load, model/native/pickle execution, real transport, actual staged disk verification, clock-skew qualification, admission freshness, or production equivalence run was attempted. Test success does not authorize a host step. Temporary source exports, logs, synthetic repositories, canaries and pytest bases were removed after verification.

Overall: REQUEST_CHANGES — six numbered findings require revised candidates.
safe_input: APPROVE_WITH_CONDITIONS; unchanged S1: APPROVE.
S2 and S4: REQUEST_CHANGES — repaired earlier findings, unsafe pre-layer bootstrap remains.
S1b, S3, S9 and S10: REQUEST_CHANGES — bootstrap plus clone/integration issues.
S5, S6 and S7: REQUEST_CHANGES — bootstrap/config/guard-repo/RC-9 issues.
Tests: 1,766 normal and 1,744 optimized delivered-suite passes after scratch shim-mode repair; 24 added controls per mode.
Boundary: offline synthetic execution only, no real outcomes/SSH/repository edits; temporary files removed.
