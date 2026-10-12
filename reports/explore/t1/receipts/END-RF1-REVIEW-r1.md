# END RF1 independent review r1

- Reviewer: Opus (independent, read-only), on 127x05. Started at 2026-10-12T02:54:56Z (taken from `date -u`).
- Scope:
  - RF1 (536bf5bd), plus the erratum c42b32fe;
  - the rules it amends: L1 9f919cb3, R-ord b21b5a20, `reference-attempt-roots-0108.json`, `release_reference.attempt_roots`/`pool_inputs`, PC1, the R2 C2/PC1 residuals, E4 review F3, and `fleet_pool`.
- Read from: origin/main ab3d1b3e/c42b32fe, plus the received r1 files on 05.
- No SSH, edits, backends, outcomes or heldout data.

## Verdict: **APPROVE_WITH_CONDITIONS**

The exemption is sound, and the r1 evidence clearly falls inside it. Counting r1 isn't a viable alternative. The priority fix needs tightening: it should gate before exec, and it must never kill the run. See C1–C8.

## Evidence checked

**r1's sealed data:**
- `receipt-manifest.json` (d1fba388…) is `{"files":{"failure.json":"8aa5acbf…"},"status":"failed"}`.
- Both SHAs recompute.
- `durable-measurement` holds only `failure.json` plus the seal pair.

**Why that file set is exhaustive:**
- `ReceiptStore.seal` lists **every** file under the output (`receipts.py:69`, `rglob`).
- `end_verify_push.verify` (753722c9, `:107-109`) independently requires the actual set to equal the manifest set plus the seal pair.

**Where E4 stopped.** The traceback in both `failure.json` and `detach.log` is: `measure_tiers.py:688` → `fleet_reference.py:34` (`pinned_profile`) → `fleet_profile.py:41` → `:14 slot_layout` → ValueError on priority.
- That is before `evidence`/`host_reporting` (`fleet_profile.py:43-44`).
- It is before the row checks, the capture receipt (`:95-96`) and `fleet-identity.json` (`:97`).
- It is long before the monitor start, census, exactness, warmup or timing (`:120-126`).
- `fleet_technical_cause` = null.
- `detach.log` contains only the traceback.

**Launch and exit:**
- Launch was at 02:48:04Z with wrapper nice 19, recorded in the launch receipt. Exit was at 02:48:18Z with code 1.
- TRANSFER-COMPLETE is present, and there is no PUSH-FAILED.

**The erratum is correct.**
- `verify` requires `(code==0) == (status=='complete')` (`:96`). It returns `ack_allowed=True, classification=SEALED, status=failed` for sealed failed data.
- `main` then writes `DURABLE-ACK.json` and exits 0 (`:138-142`).
- So a non-zero exit is **not** the expected result for r1.

## Findings

### F1. Purpose preserved: APPROVE

The all-attempts rule exists so that reference *timing* can't be selectively omitted.
- An E4 invocation that refuses before `fleet-identity.json` has produced no timing, census, MHz, exactness or admission data.
- So omitting it from the pool can't select on any measured quantity.
- At the point of refusal the operator knows nothing about the attempt's eventual timing. Refusing pre-identity is therefore informationally equivalent to never having launched.
- The only lever left is *when* to launch, which is a matter of ex-ante conditions. That lever already exists, and C1/C2/c6387611 already constrain it.

**Hidden content in a priority refusal: none of consequence.**
- The data consists of a deterministic traceback and a UTC stamp.
- The ~14 s launch-to-exit wall time reflects imports and bundle hashing, not reference work, and the disclosure exposes it anyway.
- `pinned_profile` raised before `fleet_end.evidence`/`host_reporting`, so not even reporting-side data was read.

### F2. Class definition: sound, but word it mechanically (C1)

**What already makes the class tight.** "Manifest status failed and file set exactly {`failure.json`}" is **mechanically sufficient**, for two reasons:
- The seal is exhaustive.
- The first store write after line 34 is `corpus-capture.json` at `:96`.

So no attempt that reached line 96 can qualify, and therefore nothing with timing content can either.

**Two wording problems:**
- **(a) "file set" is ambiguous.** The directory actually holds three files (failure plus the seal pair). Say "manifest `files` keys == {`failure.json`}, as verified by a 753722c9 SEALED ACK".
- **(b) "traceback ends before `fleet_reference.py:97`" is literally false for r1.** The traceback *ends* in `fleet_profile.py:14`. Define it instead as one of:
  - the innermost `fleet_reference.py` frame is `in run` at a line ≤ 96;
  - there is no `fleet_reference.py` frame at all, meaning a refusal in `measure_tiers.main:667-685`, which is equally pre-identity.

**Abuse resistance.** The data-side predicate can't be gamed to drop an attempt with timing content. The residual risk is *repeated* engineered refusals used to re-roll launch timing. That risk is small, but it should be bounded (C2).

### F3. Interaction with the amended rules is consistent, given C3/C4

**Release side.**
- With r1 absent from the release-side root, `attempt_roots` (`children == requested`, reads `fleet-identity.json` at `:135`) and `fleet_pool` (`:96`, `:104`, chronology from `identity.utc`) both pass on `{r2[,r3]}`.
- `pool_inputs` never sees r1.

**Host side and PC1.**
- The host root on 08 will list {r1, r2, …}, so PC1's literal "host listing == descriptor" no longer holds.
- RF1 replaces it with "descriptor ∪ disclosure". That is acceptable only if the disclosure is committed before r2 launches, so it can't be retrofitted (C3).

**Effect on the R2 residual.**
- RF1 deliberately creates R2 residual (i): a failed attempt not copied release-side.
- PC1's independent evidence (launch receipts, host listings, the committed disclosure) is what covers that residual.
- A release-side byte copy *outside* the registered root costs nothing and restores the spirit of "preserve full roots at release-side paths" (C4).

**Preservation text.** The preservation text in `reference-attempt-roots-0108.json` ("every passing or failed END reference attempt") is now interpreted as "every E4 invocation that sealed `fleet-identity.json`".
- This matches the checker's own operational definition of an attempt, which can't exist without identity.
- It is a declared interpretation, flagged to PC1, and not silent.

### F4. Counting r1 is not viable, and RF1 is already the no-code alternative

**What counting r1 would do:**
- It would put r1 in the descriptor and in the release-side root.
- `fleet_pool.py:104` and `release_reference.py:135` would then raise FileNotFoundError on `fleet-identity.json`. The chronology check (`:110`) would too.
- `classify_attempt` is never reached, so r1 can never become a technical-repeat candidate. 08 would be blocked permanently, which is exactly F3.
- Even with a code change, it would burn 08's only technical repeat on a launcher error that carries zero information.

**What "no code change" really means here.** The only no-code options are:
- (i) RF1;
- (ii) the definitional reading in F3, which has the identical effect.

RF1 is the clean choice.

**A rejected variant:** placing r1 under the registered release-side root with a stub `fleet-identity.json`. That would be fabrication. Do not do it.

### F5. The priority fix is necessary but mis-ordered, and its "owned STOP" is hazardous (C5, C6)

**(a) A record isn't a gate.** r1's launch receipt *already* recorded wrapper nice 19 at 02:48:04Z, and launch still proceeded.
- The preventive check is the **parent** nice (= 0), plus SCHED_OTHER, in the exact remote context that will exec the frozen launch command. That check must abort *before* exec.
- The wrapper-PID nice (= 10) after launch is confirmation only.

**(b) "Must not be wrapped in nice or taskset" needs clarifying.** The frozen launch command *itself* begins with `nice -n 10 taskset -c 61 bash END-frozen-detach…` (launch receipt).
- The rule must say: no nice, taskset, ionice or chrt **around or before** the frozen launch command, whether locally, in the SSH remote command or in a helper.
- The frozen `nice -n 10 taskset -c 61` prefix stays byte-identical.
- Otherwise a "fix" that strips the inner nice yields nice 0, which E4 also refuses.

**(c) Owned STOP is moot, and killing is risky.**
- E4 runs `slot_layout(…, os.getpriority(...))` at `fleet_profile.py:41`. With a wrong nice, E4 deterministically self-refuses within seconds, pre-identity, and seals `failure.json`. It can never reach admission (`fleet_reference.py:126`).
- A SIGTERM/SIGKILL, by contrast, bypasses the `except`/`finally` in `measure_tiers.main`. That leaves an **UNSEALED** directory, which is outside the RF1 class.
  - Under F3 it can be neither pooled nor omitted.
  - 753722c9 writes `UNSEALED.json` with no ACK.
- So with a wrong nice: **do not signal**. Let E4 seal its refusal, then STOP and escalate.

**(d) Root cause in the preflight.** The E4 review's C3 preflight called `slot_layout(profile, plan, host, 10)` with a literal 10. It never tested the inherited priority, which is why this escaped. C5 closes that gap.

### F6. r2 as 08's first counted attempt: APPROVE

**It is consistent with the rules:**
- `fleet_pool` limits a host to 1–2 attempts, and a pass on index 0 forbids index 1 (`:96`, `:116-118`).
- `release_reference` limits a host to 1–2 attempts (`:197`).
- r2 becomes `attempts[0]`, and any technical repeat (r3) becomes `attempts[1]`.

**Basenames.** The non-contiguous basenames (r2, r3) don't matter to either checker. The disclosure explains the gap.

**r2's conditions in RF1 item 4 are adequate,** with C5–C7 added.

### F7. Erratum c42b32fe: APPROVE

- The ACK correctly proves r1's durable binding: launch receipt, prepare nonce, argv, transfer after exit, exact file set and hashes.
- The ACK does **not** check priority, because `measurement_argv` excludes the nice/taskset prefix. The launch receipt's `wrapper_identity.nice=19` and the STOP receipt carry the cause, so the disclosure must bind both.
- Note that the verifier adds `DURABLE-ACK.json` to `end-received/…/r1/`. That is the approved addition and the only permitted change, so "preserved unchanged" means "unchanged except for the approved ACK".
- Hazard: an exit 0 with `status=failed` must never be routed as a passing reference (C8).

## Conditions

**C1. Mechanical class predicate.** All of the following must hold, and each must be recorded in the disclosure:
- (i) a 753722c9 `DURABLE-ACK.json` with `classification=SEALED`, `status=failed`, `files=1` and `exit_code≠0`;
- (ii) manifest `files` keys exactly equal {`failure.json`};
- (iii) `failure.json` has `fleet_technical_cause` null;
- (iv) the innermost `fleet_reference.py` frame is `in run` at a line ≤ 96, or there is no `fleet_reference.py` frame (a refusal in `measure_tiers.main`);
- (v) `detach.log` contains no output other than the traceback.

If any of these fails, the attempt follows L1 (assembled and counted), or STOP if nothing arrived.

**C2. Bounded use.**
- Allow at most **one** exempt refusal per host per END campaign.
- Each one needs a cause recorded before verification in a launch-time receipt. For r1 that is the wrapper nice 19 in the launch and STOP receipts.
- A second exempt-class refusal on the same host means STOP and a fresh coordinator ruling before any further launch on that host.

**C3. Commit timing.** Commit the refusal-disclosure receipt **before r2 launches**. It must contain:
- the launch receipt SHA;
- `argv.nul` SHA;
- `exit.json`;
- `failure.json` 8aa5acbf…;
- manifest d1fba388…;
- the DURABLE-ACK (exact verifier argv, stdout, stderr and exit 0);
- the STOP receipt;
- the cause;
- the predicate results from C1.

The PC1 rule then becomes: original host-root listing == descriptor attempts ∪ committed exempt disclosures, disjoint. The PC1 reviewer re-evaluates C1 independently from the bound bytes.

**C4. Release-side copy outside the root.**
- On 05, place a byte-identical plain copy of r1's `durable-measurement` at a dedicated prefix **outside** the registered root, e.g. `BASE/fleet-end-refusals-0108/127x08/end-reference-127x08-0a87166f-r1/`.
- Use full hashes and bind them in the disclosure.
- The registered release-side root must never contain r1.

**C5. Pre-exec gate.** In the exact remote shell that will exec the frozen launch command, abort before exec unless:
- `ps -o ni= -p $$` == 0;
- the scheduler is SCHED_OTHER;
- the command to exec is byte-identical to the pinned argv, with no prefix of its own.

Record all three. After exec and before the launch SSH closes, record the wrapper-PID nice, which must be 10. If it is visible, also record the E4 python PID nice, which must also be 10. Apply this to 01 and to 08 r2 alike, and add it to the prelaunch receipt template.

**C6. No signal on a wrong nice.**
- If the wrapper nice ≠ 10, send no signal. Let E4 self-refuse and seal, then STOP and escalate.
- Kill a run only if `fleet-identity.json` exists with a wrong observed nice, which is impossible under the current code. If it ever happens, that attempt is an L1 failed attempt.
- Replace RF1's "owned STOP before admission" with this.

**C7. Host listing proof.** As part of r2's C1 proof, record a read-only listing of 08's `<root>/end-reference-127x08-0a87166f-r1/measurement` from the host.
- 08 is untimed at that point, so C5 isn't violated.
- The listing must show only `failure.json` plus the seal pair, with matching SHAs. This proves the transfer captured everything on the host.

**C8. Status branch on the ACK.** Every post-ACK step (assembly, poolable gate, descriptor build) must branch on DURABLE-ACK `status`, not on the verifier's exit code. `status=failed` routes to either the C1 predicate (exempt) or L1 failed-attempt assembly, never to the passing path.

**Unchanged:** R-ord independence, 01 GO under its cutoff with C5/C6, the r2 prerequisites in RF1 item 4, and L1 for every non-exempt failure.
