# SOL review — K4S END package 2, round 1

Reviewer: independent Sol code reviewer. Written 2026-10-12, approximately 17:23 UTC. **Overall: REQUEST_CHANGES.** None of the seven components is ready for production use in its reviewed form.

## Authority and review boundary

Authoritative candidates, exported selectively through git into a temporary directory:

- Part A: **28ab0bdd54d5b2ebf1d39424b5b798cdc0f750e4**, `reports/explore/k4s-confirm/run-r1/end-prep/s3s9s10-r1/`.
- Part B: **fcb74fd2b65484cc8658e6ef3735318515643c9a**, `reports/explore/k4s-confirm/run-r1/end-prep/s5s6s7-r1/`.
- Both committed SHA256SUMS inventories verified completely. The E3 patch is already applied in the Part A committed S3 source; I reviewed that source and the patch.

I read COORDINATOR through `git show origin/main:reports/strategy_council_20260928/COORDINATOR.md`, including the adopted END plan, Q2–Q6/Q9, the 1aa63a16 scope ruling, and ab171591 E1–E3. **During review, origin/main also supplied the 17:12Z E4 ruling on the four tracked complete.json files.** Its final observed commit was **3466cefe5ad3be0c48213f5649e476cd9bfe31a6**. E4 is incorporated below; the earlier blanket prohibition is no longer the right basis for refusing those four exact files. The adopted `K4S-END-PLAN-v2.md` and its independent plan review were read through git too.

I used the package-1 r2 review for defect classes, and reviewed the Part B diffs against the supplied approved T1 originals (wrapper 0a87166f, verifier 753722c9, detach 1648dfdc). An inherited behavior is labelled as such rather than represented as a new delta.

No SSH to any host, no real host execution, no S9 locate/build against real T1 runtime directories, and no opening of any of the four real complete.json files. No candidate or shared-checkout edit, commit, or push. Tests used temporary repositories and synthetic commits as their fixtures require. Forbidden-name canaries in the probes contained only reviewer-created synthetic bytes. Git tree/log metadata supplied the real complete.json paths and provenance; their payloads were not inspected. The report is the only persistent reviewer output.

**Scope interpretation:** the accepted check/open replacement residual does not excuse static ancestor symlinks, hard links, incorrect input locations, or writes through pre-existing aliases. Hashing, copying, and git blob export all consume bytes; refusing a SHA or schema after such access does not satisfy refusal-before-read. Intentional health roles such as the pushed END claim registry and reference seal are permitted only in their declared workflows; they are not a general grant to use sealed END locations as auxiliary inputs.

Line citations below use the immutable committed source in the package indicated by the component. `common` means Part A `end_prep_common.py`; `preflight`, `gate`, `remote`, `wrapper`, and `verifier` mean the corresponding Part B files. Severity BLOCKING denotes a sealed-read/alias boundary failure or execution before anchored verification; HIGH denotes a required operational gate/integration failure; MEDIUM denotes other required fail-closed handling.

## Independent verification

All suite/probe interpreters used `/mpac/sdicks02/venvs/k4s-freeze/bin/python` **3.12.12**, `nice -n 19`, `taskset -c 0-3`, `PYTHONDONTWRITEBYTECODE=1`, and `-B`, normally and with `-O`. The source copies were in `/dev/shm`; pytest output fixtures were in one temporary `/tmp` directory because Part A deliberately permits output under `/tmp` and refuses `/dev/shm`. Cacheprovider was disabled. Child processes inherited nice/affinity; fake-host priority/affinity values were shimmed as documented by the suites. Frozen S3 subprocesses deliberately run without -O, as the candidate specifies.

| Suite | Normal | Optimized |
|---|---:|---:|
| Part A, permitted subset | 91 passed, 28 deselected; 23.39 s | 91 passed, 28 deselected; 23.59 s |
| Part B, complete delivered suite | 155 passed; 54.16 s | 145 passed, 11 skipped; 52.32 s |
| Total delivered tests executed | **246 passed, 28 deselected** | **236 passed, 11 skipped, 28 deselected** |

The 28 Part A exclusions were selected before execution using pytest's fixture closure: every test depending on `runtime_build`, the direct real-source locate test, and the four locate-variation tests whose fixture copies real T1 runtime files. `runtime_build` explicitly performs a real S9 build using default T1 sources (`tests/conftest.py:115–122`); `fake_sources` also reads the real candidate runtime (`tests/test_s9.py:23–38`). Excluding these was required by the user's hard boundary. Collection did existence checks for the real source directories, without reading their contents. I therefore **do not independently confirm 119/119** or a complete production runtime/staging run.

The Part B optimization count is correct: its verifier refuses -O at import, and the skipped tests are its normal verification tests. The S5/S7 orchestration tests use explicit fixture overrides for their production optimization/host/minimum-duration checks; passing them under -O is not evidence that production S5/S7 allow optimized execution.

Independent probes: **22 checks normally**, and **19 checks plus 3 verifier probes skipped under -O**. They cover remote hard links; shared hard-link/ancestor/location reads; S3 committed and auxiliary END paths; S9 generic forbidden blob export and a hard-linked END locate source; S10 recursive reads and auxiliary ancestor aliases; masked P-command statuses; S5 self-declared bootstrap execution and alias acceptance; high-bus verdict/RC-9 acceptance; 04 no-reference-work argv; full fake-host S7 launches with failed ps and an aliased base; S7 auxiliary reads; S6 registry hard links, arbitrary games inventory, early ACK, and metadata overwrite; and the immutable pool scope refusal.

All reported acceptance/failure paths reproduced in both modes where the helper is callable. The three S6 verifier probes ran normally only, because the immutable verifier correctly refuses -O. An initial ps probe added a shell parent and consequently tripped C5; the corrected probe preserves the existing shim's process ancestry and changes only its table-mode exit to 37. That final probe launches successfully and establishes the status defect. No production preflight, model/native/pickle load, live guard, live timing window, or real transfer was attempted.

## S1b — REQUEST_CHANGES

1. **S1b-F1 — BLOCKING: the remote reader accepts hard-linked admissions and reads them.** The component-wise remote directory walk and leaf O_NOFOLLOW are good (`s1b_copy_admissions.py:83–93, 108–116`). However, the descriptor checks at **:118–122** require regular type and bounded size only; there is no `st_nlink == 1` before the reads at **:123–130**.

   **Probe:** the unchanged remote READER, run locally on a synthetic admission leaf hard-linked to a separate canary, exits **0** and emits the canary's complete bytes; nlink is 2. Normal and -O agree. Subsequent identity/SHA checks cannot undo a prohibited alias read.

   **Required:** reject multiply-linked regular leaves on the inspected descriptor before any read/hash, and add a fake-host hard-link control that proves zero content reads. Preserve the exact three source paths and two-login sequence. This is the same mandatory alias class as package-1 r2, not a race residual.

Positive findings: exactly three admission paths; no listing/glob of reporting data; ancestor and leaf symlinks/specials refused remotely; bounded streams; remote status checked before parsing (`:267–270`); pinned stale identities refused. The local default E3 layout in S3 does not repair this remote defect. Live interpreter availability and the separately authorized read window remain unverified.

## S3 — REQUEST_CHANGES

1. **S3-F1 — BLOCKING: auxiliary inputs and the admission override bypass their location gates.** `--admissions-dir` is unrestricted (**s3_guard_job.py:373**); **:159–161** constructs and git-opens the requested path before any E3 or outcome-location check. The optional S1b manifest is read at **:155–157** using the generic shared reader, without a forbidden-location or role gate.

   **Probes:** production `committed_inputs()` accepts committed synthetic admissions under `reports/explore/k4s-confirm/end/receipts/reviewer/<host>-<name>`. It also reads and accepts a structurally valid synthetic S1b manifest placed at `end/end-raw.json`. Normal and -O agree; neither reproduction uses a concurrent replacement.

   **Required:** production admissions must come from the exact E3 directory and host/name layout before `git show`; reject other admission roots, traversal, games, and strict END auxiliary locations before accessing bytes. Gate the S1b manifest's role/location too. A test override must retain the no-outcome boundary and a test-only mark.

2. **S3-F2 — BLOCKING: verification inputs accept static aliases and derived paths are not confined.** The shared reader opens the full pathname with leaf-only O_NOFOLLOW and has no nlink check (**common:27–37**). S3's `load()` reads an unchecked root (**s3_guard_job.py:338–342**); `verify()` derives its job from unchecked `manifest['job_name']` (**:347–352**). Inventory hashes regular files without nlink checks (**:256–271**). `prove_repo()` and admission validation also use direct reads (**:205–207, :356–359**).

   **Probe:** the unchanged shared reader accepts an input hard-linked to a synthetic games canary, an input through a pre-existing ancestor symlink, and a directly named games input. Each returns the canary bytes. These helpers are used by S3 verification/auxiliary reads. S3's initial build creates fresh outputs, but that does not protect the separately callable verify path or its input roots.

   **Required:** canonical, role-confined roots and relative manifest-derived members; component-wise no-follow opens; regular/nlink descriptor checks before content access for manifests, inventory, admissions, config and seed work-tree files. Preserve the four fixed committed seed/join roles and status checks.

3. **S3-F3 — HIGH: the required preflight guard-job form is unsupported.** `JOB_NAME` and target generation permit only `k4s-end-guard-r1-rdRR-aNN` (**:73, :98–112**). There is no -pfNN form or preflight build argument. S10 consumes this same regex.

   **Required before the RC-2 preflight:** implement a distinct fresh -pfNN name, with explicit production target validation, and update dependent S10/S4 tests/pins. An unsuffixed or attempt-named job is not an adequate substitute for the agreed preflight/attempt separation. This is a needed integration change, not an allegation that the existing build reused a job.

Positive findings: freeze and nine modules are checked from committed bytes before frozen imports; four seed/join bindings are explicit; Q3 commits are proved; S3 builds its git repository locally in a new output; no host writes occur in S3 itself. The E3 patch is correct for the default directory. Git subprocesses used for authoritative content/proofs check nonzero status.

## S9 — REQUEST_CHANGES

1. **S9-F1 — BLOCKING: git export lacks the exact E1/E4 and outcome allow/deny gates.** `ls_tree()` checks syntactic relative names only (**s9_end_runtime.py:143–147, :180–190**). `export_commit()` requests and reads **every blob** at **:358–364**, then exports it. No pre-read check excludes games/strict END outcome members or refuses unlisted complete.json. The symlink branch accepts any in-tree tracked symlink, rather than only the exact E1 entry and link text (**:365–367, :379–387**).

   **Probe:** unchanged export of a tiny synthetic git tree reads and exports `games/reviewer.json` and `reports/other/complete.json`, normally and under -O. This remains a defect after E4: E4 explicitly requires refusal of any complete.json outside its exact four-path/SHA list. I did not export/read the four real receipt blobs.

   **Required:** inspect all tree metadata first and gate names/modes before any corresponding blob read. Enforce E1's exact path, mode and link text; enforce E2/E4's exact four paths and SHAs for opaque hash/export only, never JSON parsing; reject unlisted complete.json and outcome paths. Refuse an unsupported tree rather than quietly exporting it. Git commit immutability does not substitute for a content-role gate.

2. **S9-F2 — BLOCKING: locate and verification accept forbidden source locations and hard links.** `--source` accepts any canonical directory (**:570, :576**); `locate()` checks canonical roots and prunes games while descending, but does not reject an already-forbidden root or a strict END subtree (**:219–240**). It hashes candidates before pin equality. Shared reads omit nlink. Runtime/measurement inventories and manifest reads have no complete role gate (**:267–288, :407–422, :510–528**); verify derives its root from unchecked `runtime_dir` (**:521**).

   **Probes:** a canonical synthetic root at `reports/explore/k4s-confirm/end/receipts`, holding a hard-linked file with an allowed external suffix, is hashed and chosen by production `locate()`. `load_manifest()` accepts a static ancestor symlink. The shared hard-link/direct-games controls also pass.

   **Required:** gate the full source root and every candidate before hashing; production Q5 source provenance must be explicit. Check ancestors/nlink and manifest-derived root/member confinement throughout locate, add_externals, inventories and verify. Pruning a child called games does not protect a source root already inside games or END receipts.

Positive findings: Q5 base ancestry and fixed f81f3655/56b67dd4/74314eda identities are enforced; the 33 external names are exact; import closure verification precedes the frozen cross-check; all 31 distinct K4S pins and the 42b8986d measurement inventory are covered. Blob identity and git status are checked, and the tree must equal git plus externals. Those strengths do not fix the pre-read location/alias gaps. See the equivalence opinion below.

## S10 — REQUEST_CHANGES

1. **S10-F1 — BLOCKING: recursive staging inputs can read outcomes and static hard-link aliases; auxiliary manifests bypass root checks.** `local_root()` rejects ancestor symlinks but admits any canonical location (**s10_stage_host.py:115–120**). `walk_entries()` descends all directories and hashes every regular leaf without an outcome-name or nlink gate (**:139–155**). Q6 input overrides are likewise hashed before provenance/role rejection (**:173–180**). The `--runtime-manifest-for-checks` branch invokes the unchecked S9 loader directly (**:460–461**). HashingReader inherits the shared leaf-only descriptor gate (**:410–413**).

   **Probes:** production `walk_entries()` accepts and hashes both a multiply-linked `allowed.py` and `games/game.json`. The auxiliary S9 manifest loader accepts an ancestor alias. Pin/list comparisons occur after these reads.

   **Required:** location/role checks and no-follow/nlink gates on every local input before read/hash/stream, including auxiliary manifests. Reject forbidden recursive members before entering them. Permit only the explicitly ruled opaque complete.json inventory roles, not arbitrary receipt files.

2. **S10-F2 — HIGH: Part A stages into a different base from Part B's enforced launch bases.** Part A has **`k4s-confirm-end-r1`** (**:55–56**); Part B wrappers and gate have **`k4s-end-r1`** (`k4s_end_exit_push.sh:9–10`, `k4s_preflight_push.sh:11–12`, `k4s_end_launch_gate.py:29–30`). The Part A docstring incorrectly calls these the S5/S6/S7 bases (**:12–13**).

   **Effect:** an otherwise valid S10 staging run produces runtime/bundle targets outside the base S7 accepts. Do not stage under one spelling and launch under the other. Adopt the declared k4s-end-r1 roots consistently, update examples/tests, and re-pin affected files before production. Guard jobs are a separately declared Q4 namespace; do not silently relocate them.

3. **S10-F3 — MEDIUM: P masks nonzero probe statuses behind valid stdout.** P starts with `set -eu`, without pipefail, and uses `df | tail | awk`, `echo "GIT|$(git --version)"`, and an echoed who pipeline (**:259, :267–269**).

   **Probe:** synthetic df and git commands print valid-looking output then exit **37**; the unchanged generated P script returns **0** and emits the expected DF/GIT rows, normally and under -O. The outer SSH status check cannot recover these discarded statuses.

   **Required:** status-preserving captures and pipefail; check each probe's status before consuming its output. Keep the existing TV/F pipefail and SSH-status checks.

4. **S10-F4 — HIGH: no explicit refusal of S4 test-only bundles.** `bundle_component()` checks six production file pins, profile, inventory and optional runtime/guard consistency (**:186–227**) but never rejects `k4s_s4_synthetic` or the assembly receipt's `production_pins:false`. The assembler deliberately stamps test mode; frozen consumers ignore extra fields. This is static evidence, not a claim that a complete real production bundle was forged offline.

   **Required:** reject explicit synthetic/test-only markers before staging, independently of whether some production file pins match. Carry this rejection into S5 as well. A pin subset is not a replacement for checking the producer's test stamp.

Positive findings: P/TV/F use three sessions with ControlMaster=no/ControlPath=none; remote targets/ancestors are checked before extraction; tar uses keep-old-files and writes .partial; TV rehashes/list-checks; F preserves partials on error. I found no explicit remote rm/rmdir/unlink in S10. F's mv is preceded by target nonexistence checks; its concurrent replacement gap is within the accepted residual. These conclusions do not waive F1/F2 or prove real-host transfer behavior.

## S5 — REQUEST_CHANGES

1. **S5-F1 — BLOCKING: bootstrap trusts the caller's manifest SHA rather than anchoring 74314eda before import.** `bootstrap()` compares manifest bytes only with the supplied argument and hashes the six END source files using pins from that same document (**k4s_end_preflight.py:189–206**). There is no fixed 74314eda check there. `Frozen()` executes imports at **:392–395**, before the later frozen-helper/full-manifest check in **:439–442**.

   **Probe:** a synthetic runtime with an arbitrary same-schema manifest and its supplied SHA passes unchanged bootstrap. A canary end_reference module writes an EXECUTED marker when unchanged `Frozen()` imports it; the later missing ER.ROOT check refuses only after execution. This is not marked test-only. The helper behavior reproduces under -O; production `run` itself correctly refuses -O before this point.

   **Required:** anchor the fixed manifest of record, then verify the complete pre-import closure with stdlib before executing any runtime module. Test alternate pins only through a explicitly marked nonproduction route. Reuse the stronger S9/S2 bootstrap principle; a later frozen refusal cannot protect already-executed code.

2. **S5-F2 — BLOCKING: input reads and output roots permit static aliases and forbidden locations.** Bundle metadata is directly parsed before location gating (**:176–177**). Bootstrap resolves the runtime root and uses direct reads/hashes (**:192–204**); it permits in-root ancestor links and hard links. Further direct reads include compare-bundle metadata and corpus inventory (**:450, :481**). Guard paths are resolved rather than checked against declared roots (**:455–457**); copying and sealing also follow regular-file aliases (**:162–164, :636–645**). `isolated()` checks overlap only and resolves away aliases; it does not require the declared host preflight base (**:229–237, :666–668**).

   **Probe:** unchanged bootstrap accepts a source hard-linked to an external canary and a pre-existing ancestor symlink pointing to a relocated directory inside the runtime. Both are hashed. The verifier's sealed-member loop similarly checks only leaf symlinks before hash (**:737–743**).

   **Required:** explicit role/location roots for all inputs and host outputs; reject static aliases before resolve/open, require regular/nlink descriptors, and gate manifest-derived guard jobs. Reject S4's synthetic stamp before guard/runtime work. Keep native/corpus/venv provisioning out of this package's authorization, but their explicit paths must still pass read-location gates.

3. **S5-F3 — HIGH: 04 can be marked passed without satisfying the adopted full-load/bus decision gate.** `--no-reference-work` disables reference-slot work, leaving only background workers (**:556–575, :776**). The MHz check then becomes informational (**:602–605**). Loaded bus bands are descriptive (**:314–334**); `verdict()` checks check-status, listings, and a login-count change, but no bus threshold (**:649–655**). Verify-received publishes the band with `passed` (**:751–758**). S7 permits the no-reference-work flag and trusts the Boolean without the bus decision.

   **Probes:** production verdict returns **passed:true** for otherwise passing 04 evidence with loaded bus **0.8%**, despite the recorded “coordinator re-rules” band. S7 prerequisites accept that evidence without a ruling. A full-shaped 04 preflight argv with `--no-reference-work` is accepted by S7.

   **Required:** the binding 04 preflight must establish the agreed load and duration; a background-only diagnostic needs an explicit different nonqualifying result or a coordinator amendment. At the END launch gate, require loaded cumulative bus at the adopted proceed threshold (about 0.3%), or an explicit reviewed coordinator decision for the intermediate/high bands, and reject unavailable evidence. At ≥0.7%, stop before any claim until a new ruling. Export duration, load identity, reference-work mode and relevant pins into the verified preflight so S7 can enforce the decision.

Positive findings: no producer_claim/measure call on the preflight path; fresh exclusive result directory; explicit no-claim/no-timing result fields; real checkpoint protocol exercised with a fake frozen monitor; cleanup does not replace a primary exception; failed checks normally seal failed. Frozen validators, background readiness and post-pins are invoked in the intended sequence.

**Pool exclusion is sound for unmodified S5 output.** Store writes scope **K4S-END-PREFLIGHT**, sealing status passed/failed (`:149–167, :705–706`). The immutable pool calls `end_evidence.SealedReceipt(... scope=K4S-END-REFERENCE)` (`end_pool.py:279–280`); the immutable receipt reader checks scope before reading inventory members (`end_evidence.py:251`). A direct probe with actual S5 Store output and the immutable reader refuses “unexpected scope”, normally and under -O. An unmodified S5 result cannot become a counted reference by ordinary routing through the pool. This correct exclusion does not make its operational preflight pass trustworthy until F1–F3 are fixed.

## S6 — REQUEST_CHANGES

1. **S6-F1 — BLOCKING: the newly added registry reader permits hard-linked claim aliases; auxiliary/verifier inventories also lack outcome-role gates.** The new claim check requires a file and rejects leaf symlinks, but has no nlink check before `read_text()` (**k4s_end_verify_push.py:60–65**). Auxiliary launch/proof paths are hashed before any role/location check (**:163–165**). The inherited seal loop permits arbitrary normalized relative names, including games, then hashes them (**:123–134**).

   **Probes, normal mode:** replace a pushed claim with an identical hard-linked canary; unchanged verification reads it and returns **ack_allowed:true**. Add `games/reviewer.json` containing synthetic bytes to an otherwise valid synthetic sealed inventory and update that synthetic seal; it is hashed and ACKed. The latter inventory behavior and unrestricted auxiliary readers are inherited from T1, but fail the explicit K4S no-games/no-outcome boundary requested here. No real END receipt was read in these probes.

   **Required:** enforce registry regular/nlink checks before parsing and fixed claim roles/schema/round bindings. Apply safe role-bound reads to launch/proofs and sealed members; allow the registered reference-health outputs deliberately, and reject games, complete.json outside explicit exemptions, and outcome-role substitutions before hashing. Preserve scope and sealed claim equality checks.

2. **S6-F2 — BLOCKING: host metadata redirections can overwrite an existing file or foreign hard-linked inode.** The wrapper verifies only the job leaf and absence of measurement/exit, then redirects into `argv.nul` (**k4s_end_exit_push.sh:24–26, :65**). It does not reject a pre-existing argv.nul or check its link count; temporary exit/transfer and PUSH-FAILED redirections have analogous nonexclusive semantics (**:75–77, :111–118**). The preflight wrapper uses the same pattern (**k4s_preflight_push.sh:27–29, :73, :83–86, :115–122**). The ancestor/base alias issue is shared with S7. These redirection semantics are inherited, not a new T1-diff invention.

   **Probe:** in a temporary fake-host job, hard-link a separate “keep me” canary as argv.nul. Run the three-line-base-substituted wrapper with a preclaim-refusing synthetic command. The command exits 1, but **before it runs**, argv redirection truncates the foreign inode and replaces its contents with the command's NUL argv. This reproduces normally and under -O.

   **Required:** check full host base ancestry and required detach artifacts; create every new metadata/temp file exclusively/no-follow after type/link checks, reject pre-existing metadata instead of overwriting it, and use no-clobber publication. Keep originals and partials on failure. Fresh creation by a repaired S7 reduces exposure but does not make the separately callable wrapper safe.

3. **S6-F3 — HIGH, inherited operational gap: the verifier does not enforce C-d's exit+1300 s minimum, while S7 trusts its ACK.** It checks marker mtime and timestamp ordering (**verifier:93–95**), but never compares current time with exit_epoch+1300. Neither main (**:147–170**) nor S7 prerequisites imposes that lower bound.

   **Probe:** immediately after the synthetic wrapper exits, unchanged `verify()` returns an ACK, with actual elapsed time well below 1300 s. This is not an optimization bypass; the verifier refuses -O correctly.

   **Required integration:** enforce C-d before ACK generation, or require a separately pinned C-d verification-time proof and validate it before S7 accepts 03's ACK for 04. The README's manual wait is a valid operational instruction, but the claimed mechanical RC-9 gate does not establish that it happened. Do not treat an early ACK as satisfying RC-9.

Positive findings: RC-6's exact textual attempt parent/out is enforced; repository/round option counts and abbreviations are checked; the registry is pushed when it exists even if no measurement exists; foreground status is preserved; transport is post-exit and bounded; PUSH-FAILED prevents ACK; claim_without_receipt is recorded; new scope and sealed-claim binding checks are correct. S6's optimization refusal remains appropriate. No explicit host deletion command was found; F2 concerns overwrites and writes through aliases.

## S7 — REQUEST_CHANGES

1. **S7-F1 — BLOCKING: unsafe local reads and static host ancestor aliases defeat location/write confinement.** Local argv, quiet, proof, prerequisite and admission files are read through unrestricted Path.read_bytes/read_text (**k4s_end_launch_gate.py:85–86, :189–200, :243–248, :309–321**). Host pin checks and job-parent checks reject leaf links only (**k4s_end_launch_remote.py:206–214**). Host mkdir/launch follows ancestors (**:240–242**).

   **Probes:** unchanged `pinned_json()` reads and accepts a valid pinned synthetic document at `end/end-raw.json` and via a hard-link alias. In a full fake-host launch, replace the declared base with a static symlink to a separate foreign directory. The gate returns **0**, reports launched, and creates the job/wrapper marker under the foreign directory. Normal and -O helper/test runs agree; production gate's -O refusal is separately retained.

   **Required:** location/role checks on every local read; descriptor type/nlink gates; canonical declared receive/output roots and manifest-derived members; host component-wise checks for the complete base, parents and pinned script paths before reading or creating anything. Do not accept a resolved-away pre-existing alias as a declared namespace.

2. **S7-F2 — HIGH: failed ps with valid stdout is treated as a successful SSH-session/C5 census.** `ps_table()` discards the returned rc and stderr (**remote:141–149**), and main relies on that table for other-session refusal and the pre-exec gate (**:199–204, :226–237**). Hostname status is also discarded (**:183–186**).

   **Probe:** the existing fake ps prints its valid process table, with original process ancestry preserved, then exits **37**. The full unchanged fake-host launch returns **0** and runs the wrapper. This is exactly the valid-stdout/nonzero defect class. Empty stdout may incidentally fail C5; that does not handle partial/valid stdout plus failure.

   **Required:** refuse any nonzero hostname/ps status before using stdout; retain status/stderr in the receipt and validate table completeness needed for session ancestry. Preserve the working who/timers/quiet/launch status checks. Add the valid-table/rc-37 regression control.

3. **S7-F3 — HIGH: RC-9 accepts insufficient preflight/ACK proofs.** `prerequisites()` reads arbitrary pinned JSON and checks only two preflight Booleans plus host membership (**gate:203–215**), and four ACK fields (**:216–221**). It does not validate receipt schema/declared provenance, load/duration and current input binding, loaded-bus decision, or C-d elapsed time. The permissive 04 no-reference-work argv is **:165–172**. Scope/health correctness in the actual S5 verifier is useful but is not established by reading any document with those Boolean keys.

   **Probes:** a synthetic pair of documents with passed/unchanged true, 04 bus 0.8% and no re-ruling passes prerequisites. No full-load or duration evidence is required. S6's early ACK probe supplies the timing counterexample.

   **Required:** consume the specific verified receipts under declared role paths, validate their schemas and relevant runtime/bundle/evidence/guard/input identities, require qualifying 04 load/duration and bus clearance/ruling, and validate C-d before accepting 03's complete ACK. Do not let a stale/different preflight or a schema-less Boolean document satisfy the claimed launch gate.

Positive findings: exactly one launch SSH with ControlMaster=no/ControlPath=none; the local `ssh -O check` is a local control-socket probe rather than an additional login. Quiet v3 is SHA-pinned and run twice in the same session 30 s apart; timers are unfiltered and fail on nonzero/unparseable output; who failure refuses; other sshd sessions outside own ancestry are refused when the census succeeds. The outer SSH nonzero is not masked as ordinary success (launched+nonzero returns 6); unknown result returns 5 and must STOP. No explicit host deletion occurs.

**RC-7 operational limit:** session close is recorded, but closing before admission is not guaranteed by the postexec loop, which can keep the launch session open up to ten seconds (`remote:255–268`). The separate `admission` command checks it afterwards; S7 launch/RC-9 does not require that result. I did not establish an actual real-host close/admission ordering violation offline. Require the recorded close/admission check before accepting the attempt and progressing to 04; missing or false ordering must not be treated as satisfying the adopted rule. The README appropriately discloses clock skew and the lack of live evidence. Preserve informational priority read-back without sending a signal or retrying a possibly started attempt.

## Runner decisions and runtime metadata

These opinions do not authorize any host action.

1. **Evidence-commit build/stage, then equivalence after the END-JOB-only commit: support with explicit coordinator conditions.** The symbolic check at **S9:540–561** checks ancestry and both fixed commit pin sets, compares mode/blob identities for the union of all Python names, runtime-pin names, K4S pins/manifest, and the entire e4v3 tree. For the existing E1 symlink and an actual descendant whose sole added path is `reports/explore/k4s-confirm/end/END-JOB.json`, this is strong enough to show unchanged runtime_files and measurement_files **provided the same verified external bytes and staged tree are used**. END-JOB is read from the separately updated --repository clone, not needed as a runtime_files member.

   It is not, by itself, a hash verification of the already-staged hosts or an equality check of external filesystem bytes. It accepts other nonrelevant changes, and it does not prove the END-JOB exists/is the only change. Require exact P/X commits and diff membership of that one END-JOB path; committed evidence/admissions/roots already in P; fixed external and staged inventories; S9 verify/S10 receipts and bundle consistency; no intervening runtime/bundle changes; and fast-forwarded repository clones containing X. Obtain an explicit Q5 ruling allowing this deviation from “build at the END-JOB commit”. Once the S9 boundary findings are fixed, this avoids unnecessary restaging without weakening the relevant-byte proof. Do not generalize it to arbitrary symlink trees: equivalence does not follow arbitrary dereferenced symlink targets, another reason to enforce E1 exactly.

2. **-pfNN names: support and require implementation.** S4 r2's acceptance does not make S3/S10's present regex support the name. Fix S3-F3 and propagate it through the target checks and frozen bundle/job provenance. One distinct fresh job per preflight and attempt; no lifetime reuse. Host freshness remains a live gate, not something 05 can infer from a local path.

3. **Bases k4s-end-r1 on 03/04: support.** They are K4S-owned and consistent with Part B. Resolve S10-F2 first. The committed RC-6 declaration must enumerate runtime, bundles, separate Q4 guard-job parent, repository, attempts and preflight roots. Guard jobs are currently siblings under Q4, not children of the END base; that must be explicit, not an undeclared outside-base write. No permission is implied to touch T1/perception roots.

4. **Ship S4 bundles only, not separate raw background inputs: support conditionally.** The bundles already contain the byte-exact Q6 state/index/bin payloads consumed by END; duplicating them in a raw-input tree adds no measurement benefit. Use S10's bundle-only route after fixing its boundaries and test stamp rejection, verify every included Q6/model byte at both ends, and retain runtime/measurement/guard consistency. Runtime, fresh guard jobs and separately provisioned dependencies still have to be staged as declared. The approximately 23 GB/host size is the runner's estimate, not independently measured here. This packaging choice does not relax Q6 source provenance or the T1-owner confirmation.

5. **Native binary, 04 K4 corpus, --repository clone, venv: agree they are outside this candidate review's provisioning scope.** No approval of their installation, contents, availability or real compatibility is inferred. They remain mandatory preflight dependencies and separately authorized host steps. In particular, S3's small guard repo/ is different from the mutable --repository clone that carries END-JOB/claims.

6. **The four tracked complete.json paths: metadata supports narrow E2/E4 treatment, not a general complete.json permission.** I obtained the following paths/blob identities through tree/log metadata only. The SHA256 values below come from the coordinator's explicit E2/E4 metadata ruling, not from my opening or hashing these files.

   - `imitation/model/receipts/throughput-0935/complete.json`: model-throughput provenance, last adding/changing commit a2d50054 (2026-10-08); SHA256 **d1492d0f49d4f9c7836ca0c1fc48240e8749545e2855c6fa61c70e2b192eb5fc**. E2 already exempts this exact training receipt. That is one of the four, not a fifth file.
   - `reports/strategy_council_20260928/live-loop/v4/emulator-host/complete.json`: blob **a2f94dd0ce1ab1f4b233d63201a454318dc0ecff**, last changed **1a40041a**, dated 2026-10-07; SHA256 **0a4906396b270206e900b62ca9dbc0f44e2de6aefb512c7990824a4b2fed836f**. Its unchanged provenance predates T1/K4S confirmatory games; metadata establishes it cannot carry either study's later outcomes. Metadata alone does not certify absence of every possible other-project outcome field. E4 supplies the narrow carrying/hash exemption.
   - `reports/strategy_council_20260928/live-loop/v4/l1/receipts/b08-gap-export-20261012-r1/complete.json`: blob **9e15e1f73e4f3dd05fa635da0f621851a52c873a**, commit **10a928e539b50e89c9c542b47a076123ff0b80b9**, whose message identifies five small verified cut-2 transfer receipts; SHA256 **9c84b7a8b8c821921dd9cd0ddf1e814a24dc99c56d82829ff5894add34040c81**. Path, commit message and coordinator GO/completion provenance establish the transfer-completion role rather than a K4S/T1 game-result role.
   - `reports/strategy_council_20260928/live-loop/v4/l1/receipts/b08-supplemental-proof-export-20261012-r1/complete.json`: blob **1a73d2e1c54ab69fac9433047a8c957c3693d055**, commit **cb9a246932eda078c08516654224f075d1e8b43c**, whose message identifies once-per-host cut-3 exports/releases and five small receipts; SHA256 **724ee1d7032442e192994236a28abf0cd61951ffc096f412b50c359737049d2d**. Same transfer-role conclusion.

   “Hashes them and never opens them” is technically inaccurate: a hash/export consumes bytes, although it need not parse or interpret them. E4 now explicitly permits these exact files to be carried/hashed, never parsed. **S9 must implement the exact allowlist and refuse any unlisted complete.json before blob access.** No real receipt payload was opened by this reviewer. Absence of a games component is not, alone, proof that arbitrary JSON is outcome-free.

   **17 tracked runtime-pin-r2 differences independently confirmed at 28ab0bdd**, using committed code bytes, skipping the real training complete.json entirely. They are:

   ```text
   engine-rs/src/scripts.rs
   imitation/evaluation/p16_adapter.py
   imitation/evaluation/paths.py
   imitation/evaluation/register.py
   imitation/evaluation/run_gate.py
   imitation/evaluation/run_p16.py
   imitation/evaluation/seed_audit.py
   imitation/evaluation/smoke.py
   reports/explore/e1/reduce.py
   reports/explore/e1/write_report.py
   reports/explore/w-confirm/write_report.py
   reports/explore/w-screen8/parity.py
   reports/explore/w-screen8/run.py
   reports/strategy_council_20260928/search-noise-s6/delay.py
   src/clasher/analysis/loss_review/simulate.py
   src/clasher/live/decision.py
   src/clasher/vision/l1_v4.py
   ```

   Using git bytes for tracked files follows the approved T1 inventory rule: runtime-pin-r2 supplies membership, while qualified-source and fixed K4S/e4v3 pins remain binding. S9 records the tracked differences (`:482–493`). Support this disclosed behavior; do not describe the entire tracked tree as byte-equal to runtime-pin-r2. The existing explicit K4S/qualified/measurement verification must still pass. This review did not run a complete real runtime build to establish that final production result.

## Disposition

Fix the numbered findings in new immutable candidates, preserve the accepted check/open race residual as a disclosure, and obtain another offline review before any host GO. The passing delivered tests do not cover the reproduced read/write boundaries or mechanical launch prerequisites. The E4 exemptions, packaging support and equivalence opinion do not authorize staging or launch.

All temporary source copies, logs, pytest fixture trees, synthetic git repositories, canaries and reviewer drivers were removed after verification; this report is the sole persistent output.

S1b: REQUEST_CHANGES — remote hard-link admission reads.
S3: REQUEST_CHANGES — admission/auxiliary location and alias gaps; missing -pfNN form.
S9: REQUEST_CHANGES — missing exact E1/E4 export gates and source confinement.
S10: REQUEST_CHANGES — unsafe reads, base mismatch, masked P status and test stamps.
S5: REQUEST_CHANGES — unanchored bootstrap, aliases and nonqualifying 04 pass.
S6: REQUEST_CHANGES — registry aliases, host overwrites and C-d integration gap.
S7: REQUEST_CHANGES — escaped host writes, masked ps status and incomplete RC-9.
