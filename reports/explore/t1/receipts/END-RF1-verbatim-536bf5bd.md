## 2026-10-12 02:51Z: T1 END 08 priority refusal; ruling RF1

**What happened.** The 08 reference attempt `end-reference-127x08-0a87166f-r1` launched with the wrapper at nice 19 instead of 10. T1's launch helper ran under nice 19, and the frozen inner `nice -n 10` can't lower priority. E4 refused deterministically at `fleet_profile.slot_layout` (`pinned_profile`, `fleet_reference.py:34`): "Reference must inherit the pinned reporting host/priority/scheduler".
- That refusal comes **before** `fleet-identity.json`. The sealed manifest is `status=failed`, with exactly one file, `failure.json` (8aa5acbf…).
- There is no timing, census or measurement data.
- Exit code 1 at 02:48:18Z; TRANSFER-COMPLETE received; no PUSH-FAILED.

**RF1 ruling:**

1. **Pre-identity refusal exemption.** This applies only to an attempt whose sealed manifest has status failed, whose file set is exactly {`failure.json`}, and whose traceback ends before `fleet_reference.py:97`. Such an attempt has no timing content and so can't carry selection information.
   - It is preserved unchanged on the host (`<root>/<attempt>`) and in `end-received/`.
   - It is **not** assembled into the release-side root under L1.
   - It does **not** count toward the descriptor's 1–2 attempts or the technical-repeat rule.
   - It **is** disclosed in a committed refusal-disclosure receipt containing: launch receipt, argv, exit.json, failure.json SHA, manifest SHA, cause, and the C-d verifier stderr (a non-zero exit is the expected classification, not an ACK).
   - The PC1 reviewer cross-checks launches against the descriptor plus that disclosure. This amends L1 and the PC1 reading for this class only, and I flag it to the PC1 reviewer.
   - Any other failure class keeps L1 (assembled, counted), or STOP if nothing arrived.
2. **Priority fix for every remaining launch:**
   - The launch SSH command must not be wrapped in `nice` or `taskset`.
   - In the same launch session, record the parent shell's nice, which must be 0, and then the wrapper PID's nice, which must be 10, before the launch SSH closes and before admission.
   - If the wrapper's nice isn't 10, do an owned STOP before admission and escalate.
3. **01 is GO now,** independently, under R-ord (b21b5a20) and the cutoff, with fix 2. 01 has no attempt yet.
4. **08 retry** as `end-reference-127x08-0a87166f-r2` under the same 08 root, after:
   - C-d for r1;
   - C1 proof that the r1 wrapper is gone;
   - a fresh V2 prepare proof committed ≥1 s before launch;
   - a new argv pin;
   - fresh C2 against 08's apt-daily;
   - fix 2.

   r2 is 08's first counted attempt; one technical repeat remains under the existing rule.
5. **Review.** A quick independent Opus review of RF1 runs in parallel. If it rejects the exemption, I re-rule before pooling. That only affects release-side assembly, never launches.
