Verdict: REJECT

Independent review, round 1 of maximum 3. Reviewer: GPT-6.1-Sol, high effort. OA-1 is not approved for launch until findings 1–3 are fixed and re-reviewed. B2's supplied frozen inventory and runtime compatibility pass; findings 4–5 concern provenance wording and a pre-existing specification discrepancy.

Locations for new code are relative to `/mpac/sdicks02/k4s-runner/run-r1/oa1/`. Frozen references are relative to `/mpac/sdicks02/repos/clasher-k4s-run/`. Review performed locally on 127x05. No SSH, remote execution, commit/push, outcome release, reducer execution, or game outcome data access. Only this review was authored; the explicitly requested pytest command ran its supplied temporary fixtures. Additional controls used virtual paths and bytes in memory.

Numbered findings

1. **MAJOR — Return-ACK failure is permanent despite subsequent healthy passes.** `mirror_k4s.py:95–96,123,126–127`.

   Scenario: all game files hash-match on 05, `complete.json` is committed, and the local `hub-ack.json` is written. The source-bound ACK rsync then exits nonzero or times out. The exception is recorded for that pass, but the local ACK remains. Every later pass, including a restarted copier, skips the block at line 123 solely because that local ACK exists. Its source block never receives an ACK. The next health receipt nevertheless reports it as acknowledged and clears the prior block error. The frozen supervisor then stops reporting/replacement at `supervise.py:70–71` after 30 minutes; source-side health/smoke admission also cannot count it.

   Independent memory-only control injected rsync return code 23 on the ACK push: 8 verified game files and the local ACK remained. A separate actual-main control with that existing ACK made zero `copy_block` calls and emitted `acked=1,error=null,block_errors={}`. The successful supplied integration does not exercise this failure.

   Fix: make return-ACK delivery an idempotent operation that runs even when the hub block is already committed. Track successful source delivery separately from hub durability, and retry after transport failure or a crash between the two steps. An existing hub ACK must not suppress this recovery. Health must distinguish durable-on-hub from ACK-returned-to-source. Add a regression for failed ACK push followed by a healthy pass and by process restart, without reusing any scientific game execution.

2. **MAJOR — Registration is a check-then-write race; teardown can revoke another copier.** `mirror_k4s.py:58–66,130–132`.

   Scenario: two launches for the same job/source/phase both observe no prior admission receipt (or both validate the same dead prior identity) before either publishes its own. Both pass the check and can return successfully. There is no exclusive lock held for their lifetimes. The later writer replaces the first copier's identity while it may already have an rsync in flight. Both can touch the same pending proof, ACK and health paths. Furthermore, teardown reads the current receipt and sets it inactive without checking that it still belongs to the terminating process: the first copier can revoke the second copier's receipt.

   Independent two-thread control synchronized the two actual `register()` calls at their initial `exists()` check, with all writes/transfers intercepted in memory. Both returned successfully and published distinct active identities for one job/source/phase. The sequential prior-live check alone does not implement the promised single-copier invariant.

   Fix: acquire a nonblocking exclusive local lock before inspecting/publishing admission and retain it through copy work and completed revocation. Because this implementation shares one admission filename across phases, lock at least per resolved job, rather than allowing different phases to overlap. Validate the current receipt against this process's complete generation identity before teardown; never deactivate a successor. Add concurrent-registration and successor-receipt teardown controls. Existing separate 03/04 job paths can have independent locks.

3. **MAJOR — Failed or interrupted revocation leaves a remotely active stale receipt, sometimes with a successful exit.** `mirror_k4s.py:114–132`; frozen `ssh_transport.py:15–16,39–45`.

   Scenario: normal STOP-COPY/--once completion writes `active=False` locally, but the final source rsync exits nonzero. It lacks `check=True`, so `main()` returns normally while the source receipt remains `active=True`. A timeout raises instead, but there is no guaranteed recovery. SIGTERM or an unhandled exception after registration bypasses the cleanup entirely. On 03/04, the frozen strict copier classifier checks active/job, matching PID/PGID environment and source IP, but deliberately does not establish that the hub process is still alive; its live-root check only applies on the receipt's own host. Thus an old active receipt can continue admitting matching commands from an authenticated process on 05 after the real copier exits.

   Independent actual-main control made the final rsync return code 23: main returned successfully with an inactive local receipt. A separate strict-classifier control, using an old active receipt and no live hub root in the supplied rows, accepted the exact find command with matching PID/PGID and 05 source IP on 03. This is a command-constrained replay weakness of the inherited protocol, not evidence that arbitrary Python is accepted by `copier_activity`.

   Fix: guarantee ownership-checked cleanup for ordinary exits and catchable termination, check revocation transfer success, and expose failure as an unresolved lifecycle error rather than successful completion. Retry/confirm source revocation while retaining the single-copier lock, or require an explicit outcome-blind recovery before phase hand-off. Document fail-stop recovery for SIGKILL/power loss, where finally handlers cannot run. Do not claim remote revocation merely from the local active flag. Add final-transfer-failure and termination tests. The frozen guard need not be edited.

4. **MINOR — The manifest prematurely states that OA-1's verdict and SHA have already been recorded.** `build_job_manifest.py:78`; `FROZEN-K4S.json:271`.

   The current string says “Sol verdict and sha recorded in the K4S freeze addendum” before this review has approved OA-1. No verdict/hash/addendum binding is present in that string, and the reviewed OA-1 bytes receive REJECT here. This sentence is neither a projection of the original freeze record nor demonstrated completed evidence.

   Fix: describe OA-1 as coordinator-authorized but pending independent approval until approval is obtained. Then record the actual script hash, binding review verdict/path/hash and addendum evidence separately, without changing a frozen byte. Regenerating the job manifest changes its SHA, so any reporting authorization must bind the final manifest bytes. Do not manufacture an approval or rewrite the old freeze record.

5. **MINOR — Installing the required job manifest makes smoke freeze metadata differ from the frozen implementation contract.** Frozen `reports/explore/k4s-confirm/run.py:297,307`; `reports/explore/k4s-confirm/K4S-SPEC.md:154`.

   The spec says `freeze_manifest_sha256` is null in qualification and smoke, but run.py stamps it whenever the job manifest exists, regardless of those modes. B2 is required before host admission, so smoke gets a non-null SHA. This is a literal contract discrepancy. It is pre-existing in the frozen runner and does not alter reporting execution or estimands: smoke/qualification are excluded, r3 does not prescribe this null convention, and frozen health does not reject this metadata value.

   Fix: acknowledge the frozen runner's actual behavior in the outcome-blind launch/addendum documentation and obtain the coordinator's disposition of that implementation-contract wording. Preserve frozen runner/spec bytes. Do not remove the admission-required manifest or post-process game records to force a null. This is not a reason to modify the study's statistical rules.

Answers to Q1–Q5

Q1. Remote command surface and guard classification

For steady-state listing, block pulls, proof pulls and ACK pushes, the generated surface is accepted by the frozen protocol for the supplied ordinary job paths:

- Listing executes `env T1_COPIER_PID=<root pid> T1_COPIER_PGID=<root pgid> find <job>/<phase> -mindepth 2 -maxdepth 2 -name complete.json -print`. The strict classifier consumes the env prefix, optionally unwraps an exact shell `-c`, then requires those find arguments.
- Rsync uses `--rsync-path` with the same env prefix. Its remote sender/receiver are `rsync --server ... . <path under job>`, satisfying the strict classifier's server/path checks. The actual integration observed `rsync --server --sender -logDtpre.iLsfxC . <job>/smoke/<id>/`; both longer option strings in the supplied tests also pass.
- The receipt explicitly binds source IP `129.65.221.15`, avoiding 05's loopback hostname resolution. Connection source IP and port 22, PID and PGID must match for strict attribution.

The supplied eight unit tests passed. Integration watch2 on both source hosts observed all captured rsync senders as `ssh_family_budget`, with no copier command in foreign/active sets. The frozen census applies `FAMILIES` after strict attribution and overwrites the allowlist kind, so these logs establish final budgeted classification, not independently retained evidence of the earlier `owned_copier_child` classification. Short-lived find/ACK-receiver commands were not captured in those watch2 summaries; their strict acceptance is covered by unit tests. 04's `None` observation is for an sshd parent, with no corresponding foreign/active copier entry; it is not evidence of a classified foreign copier. The reported DBus and 03 idle Python foreign entries are unrelated unpinned services in the synthetic test job. Their real-job pins were not independently inspected remotely.

Registration and final receipt transfer are plain rsync, without the env prefix. They do not meet strict copier attribution. Bootstrap must finish before a timing supervisor starts, as the protocol requires. Final transfer can still be admitted through LAN-source `FAMILIES`, with its CPU budget and interference accounting. Neither path gets exemption from OP-6 limits.

No normal well-attributed steady-state copier command is shown to stop a host as foreign compute. Failed source attribution, changed receipt identity, or concurrent registration can break strict attribution; source-proven LAN family attribution may still apply. OP-6 sample/average caps can legitimately stop a host even for a correctly attributed copier. Finding 1 separately causes an offhost-copy stop without any foreign-compute misclassification.

Q2. Proof, inventory, ACK durability, paths and supervisor race

For canonical frozen-supervisor output and one copier, `copy_block` first copies raw files while excluding source complete/ACK, then pulls complete into `complete.pending.json`, checks host and block identity, requires 8 or 10 unique descriptor arms and exactly their `{id}-d27-{arm}.json` inventory, and hashes every listed game before replacing hub complete and writing an ACK. It does not parse game contents. A missing or mismatched game cannot reach the ACK write. Both 8- and 10-game blocks are represented in supplied tests and synthetic integration. Both source-host evidence sets contain ACKs for blocks 0001/0002 and health reports a hash error for 0003 while acknowledging the others. The prior corrupt-block-stalls-entire-pass defect is fixed by the per-block exception boundary.

The source supervisor publishes complete via tmp+replace only after game completion (`supervise.py:89`, `common.py:9–11`). Listing therefore sees an absent or complete proof, not partial JSON. Games precede publication and interrupted directories cannot be reused. With that immutable-source lifecycle, pulling raw files before pulling the proof introduces no unsafe publication race. Missing files still fail the hub hash check. The concurrent-copier case is not safe under the current implementation; finding 2 must close it.

On the normal path, an ACK cannot precede all listed game bytes hash-matching on 05. Return delivery is nevertheless unreliable under finding 1. “Committed/durable” here has the same successful-copy/atomic-replace semantics as the frozen copier; no fsync-based power-loss guarantee has been added.

The supplied source paths are distinct K4S jobs, including the separate `/mpac/sdicks02/jobs-k4s/` root on 04. Writes consist of hub-local block/admission/health files and source-local admission/ACK files. There is no hard-coded T1 destination, 01/08 execution, frozen repository write or 04 perception-storage write in that intended configuration. This is not a general confinement guarantee for hostile input: `--job` validates absolute/name only, not resolved approved roots; rsync `-a` preserves symlinks and SHA follows them; arm strings are not independently restricted to canonical names. A deliberately aliased job or symlinked fixture could hash outside the hub or direct writes elsewhere. The frozen runner creates ordinary regular game files and canonical descriptors, so that is outside the normal producer model reviewed here. Keep launch paths owned, canonical and outside protected storage; do not treat the copier/guard as a hostile-input sandbox.

Q3. Registration, STOP-COPY, hand-off and stale admission

Sequential registration refuses a still-live prior hub generation using PID plus PGID/start ticks/cmdline SHA/UID; a recycled PID with a different generation can be replaced. Self-PGID leadership is checked. Because one receipt belongs to the entire job, this is more restrictive than one copier per tuple: different phases cannot run concurrently in one job. Separate 03/04 job paths avoid collision between source hosts. There is no atomic lifetime exclusion, however: finding 2 demonstrates simultaneous successful registration.

STOP-COPY is tested at the top of each pass; an existing file prevents listing/copying after registration and proceeds to cleanup. It is not a prompt in-flight cancellation: the current entire listed-block pass can continue before the next check, including transfer timeouts. Operators should allow for this delay when changing phases. Cleanup normally sends `active=False`, but the failed-transfer/signal cases in finding 3 prevent a reliable hand-off, and cleanup is not identity-checked against a successor.

Yes, a remotely stale active receipt can let a matching authenticated process on 05 replay approved find/rsync commands. The strict source-host guard does not check remote root liveness, start ticks or cmdline SHA; those are checked at registration on 05, not on 03/04. Wrong source IP or wrong PID/PGID fails strict attribution. This does not grant an arbitrary non-LAN process ownership, and arbitrary compute is not one of the strict command forms. LAN family metering remains a separate, broader inherited admission rule. Reliable receipt revocation and serialized hand-off are required; cryptographic remote process authentication is not provided by this frozen protocol.

Q4. Manifest compatibility, provenance and smoke metadata

The supplied SHA is `cecb2f593b002465cf7dc66c2f744cce10cffab325445a597ed6c596b9083700`. Its inventory is exactly all 175 frozen k4s-confirm files plus prereg r3: 176 entries, no omitted or extra inventory entry. I independently checked every SHA against both `git show 391d2006acc5c70f42679d7f014b84bc9fe0c2f9:<path>` and the corresponding detached-worktree file. Freeze-record pins at the fill commit and both transport receipt hashes at the freeze commit also agree. In-memory execution of the actual builder reproduced the supplied manifest byte-for-byte, including launch-receipt path strings and SHAs.

Actual frozen `barrier.reporting_release` passed using the real manifest/worktree and an intercepted, memory-only review authorization supplying its required fields and the reviewed SHA/commit. This establishes compatibility, not an actual coordinator authorization or validation of remote staging. Actual `parent_source_seed.admit` returned `[]` for this manifest without attempting a source binding. Its unconditional manifest read is satisfied. B4's remote object fetches/prereg staging were not independently re-run or inspected; this review's no-SSH boundary is preserved.

The checked values are correct: qualified/reporting hosts exactly `[127x03,127x04]`; core binding review APPROVE round 6; the companion approval records exist and agree; prep qualifications are PASS with guard support; seed audit is PASS with no violations; c*=0.9 agrees with plan and committed decision; SD1 hash `b8ce7b4c088e275894b9654a85923aacf428656e71433f60ec32bed1ae63ef76` equals the frozen manifest's actual hash. The reducer's Opus prep-worker attribution is corroborated by frozen spec/progress/skeleton, and the verifier's Haiku 5.5 independence is explicitly attested in frozen VERIFIER-NOTES.md. The transport-retirement/allocation-release evidence supports no parent-source seed bindings. No author, review-round, host, c* or SD1 misstatement was found.

It is not literally true that every field is mechanically derived from committed evidence. Authors, independent-review booleans, reviewer/companion verdicts and coordinator identity are assigned constants, although corroborated for these supplied bytes; the builder does not parse/check all those attestations. The two optional launch receipts are hashed from local files, not pinned to a commit or parsed for PASS/host/study by the builder. Their supplied local copies do hash-match and report PASS for the intended hosts, but their paths do not exist at the fill commit; they are explicitly post-freeze launch evidence outside `files`, and the frozen barrier does not validate that extension. The OA-1 completion sentence is presently premature under finding 4. Those distinctions should remain explicit when describing B2 as a mechanical projection.

The smoke SHA issue is a real literal K4S-SPEC discrepancy, not evidence that smoke entered reporting or that results changed. r3 governs over the implementation spec and does not mandate null in smoke; health does not validate this field. Retain the required manifest and record the discrepancy outcome-blind as finding 5 describes.

Q5. Frozen bytes, outcomes and scope

No frozen inventory byte differed from commit 391d2006 in the reviewed detached worktree. The new copier and manifest builder do not intentionally edit frozen code, inspect an outcome field or reduce outcomes. The builder reads committed code/documents/audit/qualification evidence and local launch receipts; the copier copies opaque bytes, hashes them and parses only complete/admission metadata. The approved 05 hub rebinding and 8/10-game support leave 03/04 as the reporting hosts; 05 performs command/transport work, not study game execution. Phase-specific hub storage requires downstream callers to pass the intended phase tree, which the frozen health/reducer interfaces already support.

Beyond the approved operational hub supersession, the material issues are implementation failures to satisfy ACK/lifecycle promises, premature new-manifest evidence wording, and the already-frozen smoke-metadata spec discrepancy. I found no change to seeds, arm orders, c*, SD1, replacement banks, statistical rules or outcome-release requirements. Approval of OA-1 remains withheld pending a new review of fixes 1–3; no actual reporting or outcome access is authorized by this review.

Verification and reviewed identities

- Supplied command: `K4S_FROZEN=/mpac/sdicks02/repos/clasher-k4s-run/reports/explore/k4s-confirm /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -m pytest -q -p no:cacheprovider test_mirror_k4s.py`, from oa1: **8 passed in 0.60s**.
- Read-only synthetic integration evidence: both watch2 summaries, copier2 logs, ACK/admission/health copies, fixture generator and guard watcher. No fixture generation or remote census was run by this reviewer.
- Independent memory-only controls: failed return ACK; subsequent existing-ACK skip/false healthy count; final revocation failure with successful return; concurrent actual registration; stale strict receipt replay; actual frozen reporting barrier and empty parent-seed admission; byte-for-byte builder regeneration.
- Exact committed/worktree manifest inventory and 176 SHA comparisons passed; fill-record, transport, c* and SD1 bindings passed. Launch receipt local SHA comparisons passed.
- `mirror_k4s.py`: `e56874dcd16c6376a45ada5306496ce8dd12960e531f304d374a04082628dd1b`.
- `test_mirror_k4s.py`: `318edcf35d761a6cfb24e58282cce2b10ee243609237b84697f6eff2ae4a7a70`.
- `build_job_manifest.py`: `19f643e8387e182f52a2c91f33e602c23a22792abf7a0680aa15ad82c00af240`.
- `FROZEN-K4S.json`: `cecb2f593b002465cf7dc66c2f744cce10cffab325445a597ed6c596b9083700`.
