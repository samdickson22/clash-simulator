Verdict: REJECT

| Round 1 finding | Status | Round 2 evidence |
|---|---|---|
| 1 MAJOR: return-ACK failure is permanent | RESOLVED | `mirror_k4s.py:161–169,188–195` separates hub ACK creation from source delivery, retries without a matching returned marker, and creates that marker only after push/pull-back byte comparison. The failed-push/healthy-next-pass and mismatched-marker tests pass. This resolves the original transport-retry defect; new finding 7 concerns validating the hub state being retried. |
| 2 MAJOR: registration race and successor revocation | RESOLVED | `mirror_k4s.py:74–80,115–119,206,223–228` acquires one exclusive nonblocking flock per job before registration, retains the descriptor through ordinary revocation, and checks complete receipt identity before revoking. Both concurrent-lock and successor-receipt tests pass. The stable lock file is not unlinked, and Python's descriptor defaults prevent ordinary subprocess inheritance. New finding 6 concerns transport descendants that outlive the root, rather than two simultaneous admitted roots. |
| 3 MAJOR: failed/interrupted revocation leaves a stale active receipt | PARTIAL | Ordinary revocation is checked, retried three times, and pulled back for byte comparison (`112–126`); failed cleanup returns 3 with a lifecycle error (`224–227`). Ordinary SIGTERM/SIGINT enter finally. These supplied tests pass. However, the signal test raises Stop from a mocked listing, not inside a real subprocess. Actual subprocess descendants are not drained before revocation/lock release; see finding 6. `--revoke` also branches before signal handling and the lifetime finally (`207–210`). |
| 4 MINOR: premature OA-1 approval wording | PARTIAL | `build_job_manifest.py:78` / `FROZEN-K4S.json:275` now explicitly says the binding is “not bound here”, but still asserts that the script SHA and binding verdict “are recorded” in an addendum “committed before any reporting game”. No binding addendum path/commit/hash was supplied or verified, and independent approval has not been obtained. Use explicitly pending/future wording until that evidence exists. |
| 5 MINOR: smoke freeze SHA versus K4S-SPEC §5 | PARTIAL | The author response accurately discloses the discrepancy and says coordinator disposition was requested. Frozen `run.py:297,307` and `K4S-SPEC.md:154` still differ as described in round 1. A committed addendum and coordinator disposition were not established by the supplied evidence. Preserve frozen bytes; complete the outcome-blind disclosure/disposition before launch. |

Independent review, round 2 of maximum 3, on 127x05. New-code locations below are relative to `/mpac/sdicks02/k4s-runner/run-r1/oa1/`; frozen references are relative to `/mpac/sdicks02/repos/clasher-k4s-run/reports/explore/k4s-confirm/`. OA-1 approval remains withheld because of findings 6 and 7. The original ACK delivery and concurrent-root defects have substantially improved; B2's inventory and runtime compatibility pass.

## New findings

6. **MAJOR — Interrupted or timed-out transport can outlive teardown and the job lock.** `mirror_k4s.py:92,95,147,149,173,197–198,220–228`.

   Scenario: SIGTERM/SIGINT raises `Stop` while a real rsync is running. Python's `subprocess.run` kills and waits for the direct subprocess on that exception; it does not terminate/reap the rsync → ssh descendant tree. The copier immediately proceeds to separate revocation transfers and then closes its flock descriptor. A surviving helper/remote receiver can still be doing the prior transfer while those actions occur. Timeouts also kill only the direct subprocess, so retrying a block can overlap its previous transport even without a second copier root.

   In particular, interruption of the active admission-receipt push can leave its source receiver poised to publish `active:true`. The cleanup's separate inactive push and pull-back can finish first, after which that older receiver can replace the source receipt with the active bytes. A pull-back verifies a snapshot, not the absence of an outstanding older writer. Block/ACK helpers can similarly remain in flight across root restart or phase hand-off. The frozen source classifier does not require the remote hub root to be live (`ssh_transport.py:39–44`), so successful cleanup alone is insufficient evidence that the prior admission cannot reappear.

   Independent local, read-only process-tree control used the actual `M._signal` and actual `subprocess.run`: a harmless Python child spawned a sleeping grandchild, then SIGTERM was delivered to the reviewing Python process. After `Stop('SIGTERM')` unwound the run, the grandchild was still alive and reparented to PID 1. It was explicitly terminated afterward. No SSH, rsync transfer, files, or outcomes were involved. This establishes the unhandled descendant lifetime; the late remote publication scenario follows from the uncoordinated transfer ordering, and was not exercised against a timing host.

   The flock works for ordinary competing roots on the same surviving lock inode. It is held throughout the three normal revocation attempts. It cannot exclude a descendant after the descriptor-owning root dies: descriptors are not passed to the subprocesses, and a new root can take the lock once the old root exits. `register()` / recovery `revoke()` check the recorded root's liveness, not lingering members of its transport tree. Thus SIGKILL/restart recovery also needs to account for these members. The `--revoke` branch currently lacks the new signal/finally handling altogether; interruption can leave recovery unconfirmed and releases the lock at process exit.

   Fix: supervise the entire transport lifetime. One straightforward catchable-signal approach is to record a stop request and let the current bounded transfer finish before starting revocation. For timeout/failure/recovery, explicitly account for and drain outstanding transport descendants; do not permit a successful hand-off or fresh registration while prior transfers can still publish. Apply the same lifecycle handling to `--revoke`. Add a real subprocess-tree regression and a controlled delayed-admission-publication regression, proving that no old active receipt can be published after confirmed revocation and no transport overlaps a successor. Keep the frozen guard unchanged.

7. **MAJOR — The restart/return path acknowledges an ACK file without checking that its block bytes still exist on the hub.** `mirror_k4s.py:163–169,188–194`.

   Scenario: a hub ACK survives while the block's `complete.json` or game files are missing, corrupt, or otherwise no longer the verified set, and the source return marker is absent. This can be an incomplete/restored hub tree or a partial cleanup. `one_pass()` sees only the ACK's existence and skips `copy_block()`. `return_ack()` sends that ACK and writes a matching marker without inspecting the complete proof or any game file. Health then reports the block durable and returned, with no error. An existing returned marker likewise authenticates only the ACK's SHA, not the current block bytes.

   Independent execution of the actual `one_pass()` / `return_ack()` / `push_verified()` in a wholly virtual filesystem supplied one syntactically plausible hub ACK and a source listing, with **no hub complete proof and zero hub game files**. The push and pull-back were intercepted in memory. The copier sent the source ACK and returned `durable_on_hub=1`, `ack_returned=1`, `pending_return=[]`, `error=null`, `block_errors={}`. `copy_block()` was never called. This proves a reachable ACK path that does not establish all game bytes on 05; it is not evidence that a scientific block has actually been lost.

   On a fresh ordinary copy, the canonical inventory, regular-file and game-hash checks at `128–158` correctly precede ACK creation. The defect is in trusting a surviving small ACK as the full block on later passes. This finding does not demand a new fsync/power-loss contract: it requires checking the state that the restart path is about to certify.

   Fix: before returning an existing ACK or counting a recovered block as durable, validate its host/job/phase/block binding, complete SHA, canonical descriptor inventory, and every regular non-symlink game file/hash on the hub. If the state is incomplete, reacquire/reverify the block or report an unresolved integrity error without returning an ACK. Add restart regressions for missing complete proof, missing game, changed game, and stale/broken ACK binding. Do not parse game outcomes.

## Command classification and confinement

The new pull-back commands fit the frozen command surface. A prefixed remote `rsync --server --sender ... . <job>/<phase>/<id>/hub-ack.json` satisfies `ssh_transport.copier_activity`: `--sender` is not forbidden, the full file path lies under the job, and PID/PGID plus the 05 LAN connection match the active receipt. It is also eligible for final source-proven LAN family budgeting. The ACK receiver remains valid under the same conditions; exact find listing remains covered by the supplied tests.

Registration and revocation, including admission-receipt pull-back, deliberately use plain rsync without the prefix. Independent memory-only calls to the actual frozen classifiers produced:

| Remote operation | Strict copier attribution | LAN family classification with authenticated parent/source evidence |
|---|---|---|
| Prefixed ACK pull-back, active receipt | True | `ssh_family_budget` |
| Plain registration receipt pull-back | False | `ssh_family_budget` |
| Plain revocation receipt pull-back, inactive receipt | False | `ssh_family_budget` |

The family controls supplied the required authenticated sshd parent generation and child source snapshots; they do not assert that every short-lived live command was sampled. OP-6 caps and interference accounting still apply. Registration must finish before the timing supervisor starts. The supplied oa1test3 evidence does not include a new guard census trace for the additional pull-back commands; their command-form compatibility was checked independently above. No new classification rejection was found.

`check_job()` now rejects the wrong host root, nested jobs, noncanonical job names, and locally symlinked top-level job paths (`69–72`); the supplied tests pass. Arm names are restricted to the ten canonical K4S names. New block pulls use `--no-links`, and game files and the immediate games directory are checked against symlinks before hashing. These are useful hardening changes.

Confinement remains a local top-level check, not an inspection of the remote path or every destination ancestor. Existing `hub-blocks`, phase, or block directory aliases are not individually rejected. Launch paths and their descendants must remain owned and canonical on both ends, as in the original producer model. More directly, the existing-ACK branch bypasses the new block validation entirely (finding 7). I did not find a canonical fresh-copy path that writes an ACK before its game hashes match on 05; I cannot make that statement for all restart paths in the reviewed implementation.

## B2 confirmation

The regenerated manifest's exact SHA is **`454b5f54b9047dc1c8f7cf51f9b8ea0a0585130aecc9141af29417c9d7372328`**. Its freeze commit is `391d2006acc5c70f42679d7f014b84bc9fe0c2f9`; its fill commit is `fab6e03ff33f33ee0956e2db02d25f2fe66014c5`.

I independently established:

- `files` is exactly the 175 frozen k4s-confirm tree entries plus prereg r3, with no missing/extra inventory entry. All 176 SHA values match both the freeze-commit blobs and detached-worktree bytes. The frozen harness and prereg have no tracked changes.
- Both freeze-record bindings match the fill-commit blobs. Both supplied local launch qualification receipts match their manifest SHA, intended host, and PASS verdict.
- In-memory execution of the actual builder, redirecting only its output and launch-receipt reads, reproduces the supplied manifest byte-for-byte. No manifest or alias was written.
- Actual frozen `barrier.reporting_release()` passes with the real manifest/worktree and a memory-only review authorization containing the required coordinator fields, this manifest SHA, and the freeze commit. This is interface compatibility, **not an actual reporting authorization**.
- Actual frozen `parent_source_seed.admit()` returns `[]` for this manifest without source-binding admission or writes. `qualified_hosts` and `reporting_hosts` remain `[127x03,127x04]`; `reporting_delta_review` remains core r6 APPROVE round 6; `parent_source_seeds` remains `[]`. Required roles, SD1 binding and c*=0.9 are retained.

B2 remains runtime-compatible with both frozen interfaces. The round 1 distinction still applies: the frozen inventory is mechanically generated; some author/review/coordinator attestations are assigned constants, and launch receipts are post-freeze evidence outside `files`. The operational-amendment wording is still subject to finding 4. Any correction that regenerates this manifest requires reporting authorization to bind the resulting final SHA.

The smoke metadata disclosure in the response is accurate. `run.py` computes the job-manifest SHA whenever the file exists, including smoke; the spec says null in smoke/qualification. No frozen runner/spec edit, manifest removal, or outcome-record rewriting is warranted. Complete the coordinator's documented disposition separately.

## Verification, identities and scope

- Requested pytest command, from oa1: **21 passed in 0.06s** (`-B`, `-p no:cacheprovider`, frozen harness selected by `K4S_FROZEN`).
- Read only `copier3-127x03.log`, `copier3-127x04.log`, the explicitly synthetic fixture generator, guard watcher code, and oa1test3 ACK/returned-marker/admission/health evidence. Both hosts show 10- and 8-game ACKs, two returned markers whose SHA matches the corresponding saved ACK, an isolated corrupt third block, and a saved inactive receipt. These healthy-path artifacts do not exercise the new failure scenarios or independently prove every source-side state after shutdown.
- Independent controls were local/read-only or wholly in memory: actual subprocess signal/descendant behavior; both frozen command classifiers; ACK-only restart; all inventory/binding SHA comparisons; builder reproduction; reporting barrier and empty source-seed admission.
- `mirror_k4s.py`: `4a5d9e9f5183fdd5edd1d442f8ebb07b397bbbbf134766750ca2645f3abcd7db`.
- `test_mirror_k4s.py`: `a50e379bd18e9942dc8fa058a953fa0de57a221ebfe2351731be69d1ba4447ed`.
- `build_job_manifest.py`: `ba4405425fa7de07d6f94042df760eef8e644358b04975ef4e1669dafc8816ce`.
- `FROZEN-K4S.json`: `454b5f54b9047dc1c8f7cf51f9b8ea0a0585130aecc9141af29417c9d7372328`.

No frozen inventory byte changed. No game outcome data was opened, no reducer or outcome-release path was executed, and no scientific game was run. The review used only the frozen harness/source/evidence inventory and explicitly synthetic or memory-only controls. No SSH or execution on 127x01/03/04/08, commit, or push occurred. The only authored persistent file is this review; the authorized pytest suite used its temporary fixtures. OA-1 is not approved for use pending fixes and round 3 review; this review grants no reporting or outcome access.
