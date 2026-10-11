# PREREG-K4S-CONFORMANCE-r2

- **Reviewer:** independent conformance reviewer, Claude Opus 5.5 (1M context), run on 127x05. I did not write r1, r2
  or the response. Read-only: the only file written is this one. No compute beyond `sha256sum`/`grep`, no ssh, and
  no heldout data, sealed T1 output, reporting game result or X4S-2 phase E/F output was opened. **I am blind to
  phase E**, which matters for N1 below.
- **Time:** 2026-10-11, after origin/main `1ecd18c5`.
- **Documents:**
  - `PREREG-K4S-DRAFT-r2.md`, commit `a44bd628`. sha256 `b159d116e702c0327c303f3843a3b8e4b5bc3e9b4f9d27272e28f999fa988598`
    **verified**, on disk and in `git show a44bd628:` (byte-identical). a44bd628 is on origin/main.
  - `PREREG-K4S-DRAFT-r1.md`: byte-identical to `68a15c6a`.
  - `PREREG-K4S-REVIEW-r1.md` (F1–F14) and `PREREG-K4S-RESPONSE-r1.md`.
  - Checked against: TIERS r3 (`PREREG-SEARCH-TIERS-r3-DRAFT.md` §1, §6.2–6.6, §7, §8, §9), the TIERS freeze record,
    Amendment 1, T1 `PLAN.md`/`AMENDMENT1-RELEASE-BARRIER.md` (only where they mention `measure_tiers.py`),
    `explore/x4s/RESULTS.md` (contrast table), the x4s2 file list and git log (no phase E/F content), and
    `imitation/exit-r3/RESULTS.md` l.85/97/125.

## Verdict: **CONFORMS_WITH_FIXES**

- All 14 round-1 findings are addressed. 13 are **RESOLVED**; F4b is **PARTIAL**: the c\* = 0.8 branch as written
  still gives S-ON K4S to a 0.9× Mac.
- The r1 → r2 diff changes no game, arm, cell, n, seed, margin, α, bootstrap or compute figure. The only changes to
  the hypothesis structure are the three the response declares (F4b, F6a, F6b).
- **Three new required fixes**, all in the deployment and Mac layer:
  - **N1:** the c\* = 0.8 branch contradicts itself (this is the F4b residue).
  - **N2:** the Mac addendum would modify TIERS's frozen `measure_tiers.py`.
  - **N3:** the F0 fill-in ignores *why* TIERS chose F0, and the K4S cell map omits TIERS's 4-worker exactness gate.

  Each is a text-only fix and none touches the games. There are also six minor or nit corrections (M1–M6) that should
  be made but do not block the freeze.
- Statistics, power and the order change were re-derived and hold, apart from the stale comparison numbers in M1–M2.

## 1. Round-1 findings: conformance

| # | Status | r2 text that resolves it (quoted or located) | Note |
|---|---|---|---|
| **F1** | **RESOLVED** | §1.5 table keyed on "TIERS selection": not yet available / **K4** / **K2 or S** → "**TIERS stands** (Q12)" / **F0**. §0 l.22–23: "At 0.6–0.7×, K4 itself is TIERS-infeasible … Whether S or K2 remain feasible depends on their own 1-core and 3-core ratios." H2 rationale l.106: "below K4's TIERS feasibility floor". Q10 and Q12 added. | The false premise is gone everywhere (grep: no "nothing feasible"). The new F0 row has its own gap, which is **N3** and was not part of F1. |
| **F2** | **RESOLVED** | §1.5 "Usable evidence cells": "c = 0.8 and it is admitted at A or B; or c = 0.9, admitted at A, **and** the §1.2 gate-check veto passes". K4 row: "c_e ∈ {0.9, 0.8} with c_e ≤ c\*: **K4S**". Q6: "when c_e ∈ {0.9 (A with veto passing), 0.8 (A or B)}". Q10: "to replace TIERS K4 at c_e = 0.8, or where TIERS selects F0". | §1.5, Q6 and Q10 now agree. The "+5 pp allowance vs K4@0.9" is only implicit in the veto definition: see **M4**. |
| **F3** | **RESOLVED** | §1.4 l.155–156: "**Cell 1.0 is TIERS's K4 cell.** c_M = 1.0 iff TIERS finds K4 Mac-feasible in its 1.0 cell, by TIERS's own r_5, p10 ≥ 0.70 and gates 2–6 … No SD1-specific gate applies at 1.0". l.180: "This deliberately generalises TIERS's p10 ≥ 0.70 at 0.8 to every cell." | Matches TIERS §6.3 gate 1 and §6.4 (s = 1.0 iff r_T ≥ 1.0, gate 6 at 200 ms). The K4 row then gives "If c_M = 1.0: plain K4". |
| **F4a** | **RESOLVED** | §1.3 l.130–131: "S-default is ON iff the evidence cell c_e (§1.5) is ≤ the threshold cell c\*. It is defined by c_e alone." | No r-based "equivalently" remains. grep finds no `r*` or r-threshold in r2. |
| **F4b** | **PARTIAL** | §1.3 l.141–144: under c\* = 0.8, "H4 is dropped … K4@0.9 and K4S@0.9 become descriptive; a 0.9× Mac follows TIERS (plain K4)." No trailing H3′ remains. | **The mechanics contradict the stated outcome.** Under c\* = 0.8 a Mac with c_M = 0.9 has c_e = max{usable ≤ 0.9} = 0.8, because 0.9 is no longer admitted. Then c_e = 0.8 ≤ c\*, so the §1.5 K4 row deploys **K4S with S ON**, and so does the F0 row. That is the exact failure F4b described ("a 0.9 Mac falls to c_e = 0.8 with S ON"). See **N1**. |
| **F4c** | **RESOLVED** | §1.3 l.138–139: "applies it once, before the freeze, and records it in the freeze record with phase E's reduction UTC". l.147–149: "**Locking.** This rule text is final as of r2 … Any later change … would void the rule; c\* would then default to 0.9." | Verified: the latest x4s2 commit on origin/main is `00328d1b` (08:23Z, "Phase B reduced"). There is no phase E/F receipt on origin/main, then or now. Timestamp nit: **M3**. |
| **F5** | **RESOLVED** | §4.5 item 6: "**TIERS `tiers-summary.json`, or a released TIERS outcome barrier** (including via its 14-day escape)". §1.4 l.197–198: post-release K4S Mac session needs "an independent reviewer [to confirm] the mechanical session-validity classification before it runs (TIERS §6.6(b))". Q3 updated. | Matches TIERS §6.6(b) and D6. A separate TIERS-interference issue exists in the Mac addendum: **N2**. |
| **F6a** | **RESOLVED** | §1.2 l.117–118: "**The 0.9 gate check is not in the chain.** … a **deployment veto** on using c_e = 0.9 … It never stops the sequence. A veto can only remove admissions, so FWER is unaffected." A(0.9) row now has no gate-check part. | |
| **F6b** | **RESOLVED** | Q13 with trade-off table. The order is changed to B(0.8), B(0.7), **B(0.6)**, A(0.9), A(0.8), A(0.7), A(0.6), with the rationale in §1.2 l.113–114. | The reviewer asked only for a Q. The author also changed the default. That is disclosed ("Accepted, with the default changed"), and the coordinator accepts Q13 as written. Numbers re-derived (§3 below); one stale value: **M1**. |
| **F6c** | **RESOLVED** | §1.2 l.97–98: "For c ≤ 0.8, A(c)'s parts imply B(c)'s … B(0.9) is not defined." | |
| **F7** | **RESOLVED** | §3.5 l.453: "The confirmatory K4S arms equal X4S-2's charged configuration (K4Sh)". l.462–467: pessimistic column = the direct +3.2, with the shrinkage justified. §0 l.58: "level A at 0.8 is about a coin flip". l.484: "The shared SUP(0.8) event is counted once." | The marginal at +3.2 is ≈0.52, so "coin flip" is right for the marginal. The cumulative value is .27. |
| **F8** | **RESOLVED** | §1.4 l.172–175: r_inf on "`poll_seconds`, from the call to the policy poll until its return … The fleet value comes from END item (c)". §2.4 l.337–340: "W_search/c + poll/c² ≤ 200 − 8/c … a further 8/c − 8 ms of slack". l.343–344: overrun under-penalisation disclosed. Gate 3: "Poll-span p99 ≤ 20 ms". §4.5 (c) added. | Derivation re-checked: dividing the fleet constraint W + poll/c ≤ 200c − 8 by c gives the stated bound, and 200 − 8/c < 192 for c < 1. |
| **F9** | **RESOLVED** | §1.5 l.207: "If there is none, c_e is *undefined*", and every table row falls back to the TIERS outcome. l.208–210 disclose the non-monotonicity (18.2% < 20.7%). §5.3 item 9 added. | X4S `K4S-160 minus K4S-200` = −2.50 [−6.00, 1.00] (RESULTS l.28). Consistent. |
| **F10** | **RESOLVED** (issued at the freeze) | §2.1 l.270–279: a role-scoped supersession "for these exact bytes in the K4S cutoff-default role only", issued by `0523ae6f`, disclosed as "**outcome-informed**". Recipe l.257: "existing R2 gate/card/tile loss terms, with conditional full-8,192 denominators". l.265–267: "midpoint … on exact distance ties, take the smaller threshold". | Quote verified at `imitation/exit-r3/RESULTS.md` l.85 ("ALWAYS NEVER-ADOPTABLE") and l.97 ("regardless of its paired benefit"). Wording nits: **M5**. |
| **F11a** | **RESOLVED** | §3.1 l.371 and §3.4 l.436: "Replacement blocks inherit the lost block's arm set". | |
| **F11b** | **RESOLVED** | §3.1 l.374: "interleaving primary and guard **10:3** (3,000 : 900)", plus the T1 B2 balancer. | |
| **F11c** | **RESOLVED** | §3.1 l.367: "**ρ = ⌊i/50⌋ mod 8** (primary) or **⌊i/18⌋ mod 8** (guard)". | Checked: cell c holds i = c + 50k, so ρ = k mod 8 runs over all eight values (60 seeds per cell: 8/8/8/8/7/7/7/7). Guard is the same with 50 seeds per cell. Seat is part of the cell, so rotation is independent of seat. |
| **F12** | **RESOLVED** | §4.5 l.628–630: "re-run until it conforms, or the coordinator declares the K4S Mac speed ratio unavailable … outcomes may still be released for the fleet claims". Release item 2 accepts the declaration. | |
| **F13a** | **RESOLVED** | §4.1 l.539–540: "**K4@1.0 ≡ T1 K4@200:** command hashes and injected-clock decisions … under the delta runtime and under the frozen T1 runtime `ef4c073a`, must match." | |
| **F13b** | **RESOLVED** | §3.3 l.397–398 pins `6d51628bb1262f53258e88ef6247cfb41f2762f9f13323387fcd36ad126c48ef`. §4.1 l.549 makes it a qualification pin. | `sha256sum reports/explore/t1/guard-decks.json` matches. |
| **F14** | **RESOLVED** | (1) §1.3 l.135: "−9.7 pp at 0.8× and −25.2 pp at 0.7× (X4S, K4S − K4, same budget)". These match X4S −9.67 / −25.17. (2) r1's §5.3 item 5 has been removed, and the conservative-charge disclosure is in §2.4. (3) §3.6 adds "**SD1 P(play)**, **coarse_order hash**". (4) §1.4 l.164–166 discloses the corpus. (5) §3.5 table now reads .025. | |

## 2. Diff r1 → r2: did anything change beyond the response's claims?

I diffed the two drafts section by section.

**Unchanged, verified:**
- the arm-cell table: 8 core arm-cells plus 2 subsample arm-cells, the same budgets and the same subsample rule (i < 600 / i < 300);
- the populations and decks, n = 3,000 / 900, all seed ranges, the bank, the audit list and the caps;
- the opponent;
- the margins: A +5 / SUP < 0 / guard +10, and B +10 / < 0 / +15;
- α = 0.025 one-sided, from the 95% interval;
- bootstrap: 10,000 resamples, `default_rng(2026101170)`, stratified;
- the validity band [10%, 30%];
- the game count of 33,000, with the same compute and wall figures;
- the host candidates and the OP lessons.

**Changed, and each change is declared:**

| Change | Declared under |
|---|---|
| A(0.9) loses its gate-check part; it becomes a veto outside the chain. | F6a |
| Order: B(0.6) moves from H5 to H3, and A(0.9)/A(0.8) shift to H4/H5. | F6b / Q13 |
| Δ_ref is redefined from L(D(c)@c) to L(K4S@c). This matters only in r1's r\* = 0.9 branch, now deleted. Under the default it is identical. | F4b |
| r\* = 0.9 branch (H3′ moved to after H7) replaced by c\* = 0.8 (H4 dropped). | F4b |
| The Mac cell mapping splits into the TIERS 1.0 cell and the K4S cells ≤ 0.9; r_inf is redefined; gate 3 now applies to the poll span. | F3, F8 |
| The deployment table is re-keyed. | F1, F2, F9 |
| Release item 6 is added; the END failure path is added. | F5, F12 |
| The SD1 supersession and recipe items are added. | F10 |
| Rotation formula, replacement arm set and 10:3 dispatch. | F11 |
| A K4@1.0 ≡ T1 qualification and the guard SHA pin are added. | F13 |
| §5.3: item 5 removed, item 9 added; mechanism gains SD1 P(play); §3.6 fields added. | F9, F14 |
| §4.2 conflict snapshot updated (09:04Z; T1 at "1,799/3,072 durable"). | — |

On the last row: the snapshot contains operational counts only, with no outcome information, so it is not a leak.

**Undeclared changes: none of substance.** The response's sentence "None changes the games, arms, seeds, n, margins
or α" is true. The order change is outside that list and is declared separately under F6b.

## 3. Internal consistency

### 3.1 Hypothesis order and α

- The fixed sequence over H1–H7 (or H1–H3, H5–H7 when c\* = 0.8) is FWER ≤ 0.025 under any order prespecified
  before outcomes. Dropping H4 is a deterministic function of pre-freeze exploration data, so it stays valid.
- The veto only removes admissions. Intersection–union within each hypothesis needs no adjustment. The §1.2, §3.5,
  §5.2 and Q13 statements agree.
- **Sequential power re-derived** with σ = 0.47/0.51/0.50/0.56, SE 0.86/0.93/0.91/1.87, and SUP(0.8) counted once:

  | Step | Central | Pessimistic |
  |---|---|---|
  | H1 B(0.8) | 1.00 | .908 (SUP −3.0) |
  | H2 B(0.7) | 1.00 | .91 |
  | H3 B(0.6) | .964 (NI10 at +6.5; guard ≈1) | .67 (.766 × .963) |
  | H4 A(0.9) | .94 | .52 |
  | H5 A(0.8) | .86 | .27 (NI5 at +3.2 ≈ .556 × guard ≈ .93) |

  These match the §3.5 table and §0. Stale comparison values are listed in M1–M2.

### 3.2 Gate rule and its use of X4S-2 phase E

- c\* has two values, and the only input is phase E's d180 lower bound. The no-phase-E default is 0.9, and the
  locking clause is present.
- §6 allows phase E only through the c\* rule.
- **Inconsistent under c\* = 0.8 (N1).** With the default c\* = 0.9 the rule is consistent: every usable cell is
  ≤ 0.9, so S is always ON when K4S is deployed. That matches §0 ("S is ON in every K4S evidence cell").

### 3.3 Deployment vs PREREG-SEARCH-TIERS

**No override of 1-core or 2-worker picks.** The K2/S row reads "TIERS stands". K4S replaces only a TIERS **K4**
pick, and only at c_M ≤ 0.9 with c_e ∈ {0.9, 0.8}. At c_M = 1.0, plain K4 stays. This holds.

**No pre-emption.** The "not yet available" row holds K4S. Release item 6 keeps K4S's K4@200/160 estimates sealed
until TIERS's Mac summary exists or TIERS has released.

**No leakage of sealed T1 outcomes.** r2 cites only T1 operational counts and frozen identifiers:
- T1's K4 corpus inventory `81f2483e`;
- the runtime `ef4c073a`;
- the guard-deck SHA.

§5.3 item 7 ("after T1 opens") is descriptive and post-release. I found no T1 outcome input to any K4S rule.

There is one residual risk. The K4S freeze could happen *after* T1/TIERS outcomes open: TIERS may release before
K4S freezes. The freeze-time choices left are mechanical (hosts, hashes, audit, c\* from phase E only), so the risk
is small. The freeze record should still attest to it (checklist item F-10).

**Gaps found:**
- **N2:** the Mac addendum modifies a TIERS-frozen script.
- **N3:** the F0 fill-in and the missing 4-worker exactness gate.

### 3.4 Release barrier

All six items are well formed:
- item 2 has the "ratio unavailable" alternative;
- item 6 matches TIERS §6.6(b) and D6.

The decision not to gate release on the K4S Mac summary is still valid. Every cell is inside the FWER family, the
mapping is mechanical and takes the minimum across sessions, and a post-release Mac session needs an independent
classification review.

### 3.5 SD1 definition and the role-scoped supersession

- The bytes, manifest and recipe match round 1's verified facts: checkpoint `37509a43…`, calibration `e3003533…`,
  threshold 0.5005528330802917.
- The supersession is correctly scoped. It is an additive pointer, R3's files are not edited, it is outcome-informed
  and disclosed, and TIERS §2.1's separate tier-S supersession is untouched.
- The sentence still has to be **issued** at the freeze. Wording: M5.

## 4. New findings

**N1. REQUIRED. §1.3 vs §1.5: under c\* = 0.8, a 0.9× Mac still gets S-ON K4S. This is the residue of F4b.**
- **What happens.**
  - §1.3 says that under c\* = 0.8, "a 0.9× Mac follows TIERS (plain K4)".
  - But H4 is dropped, so 0.9 is never usable, and c_e for c_M = 0.9 is 0.8.
  - Then c_e = 0.8 ≤ c\* = 0.8, which satisfies both the §1.3 switch and the §1.5 K4 row ("c_e ∈ {0.9, 0.8} with
    c_e ≤ c\*").
  - The Mac therefore deploys K4S with S ON, on the exact speed band where phase E would have shown that S hurts.
  - The F0 row has the same problem.
- **Fix (additive, in §1.5).** "**Eligibility:** K4S is deployed (any row) only if c_M ≤ c\*. Under c\* = 0.8, a Mac
  with c_M = 0.9 receives the TIERS selection, F0 included." With the default c\* = 0.9 this is a no-op, because
  every K4S cell is ≤ 0.9. §1.3's switch text is unchanged.
- **Timing.**
  - Make this edit before anyone who edits the text has seen phase E's d180. Phase E is still unreduced on
    origin/main, and this reviewer is blind to it.
  - It implements r2's own stated consequence; it does not create a new rule.
  - Record the edit and its UTC in the c\* record.
  - If the edit is made after phase E has been reduced, the §1.3 locking clause applies and c\* = 0.9. Under
    c\* = 0.9, N1 is moot, so either path is safe. The coordinator only needs to record which one was taken.

**N2. REQUIRED. §1.4 "Implementation" and Q5: the K4S Mac addendum would edit a TIERS-frozen artifact.**
- **What happens.**
  - r2 says "a reviewed addendum adds a K4S configuration to E4's `measure_tiers.py`", with the TIERS session as the
    default.
  - TIERS §6.6(a) freezes `measure_tiers.py` in the TIERS manifest before any fleet reporting game.
  - T1 runs it "unmodified" (T1 `PLAN.md` l.15; `AMENDMENT1-RELEASE-BARRIER.md` l.50).
  - Editing it contradicts r2's own statement that it "edits no TIERS or T1 file". Running K4S work inside the TIERS
    session can also perturb TIERS inputs: thermal state, rotation timing, and a session repeat triggered by a K4S
    failure, which would put a second session into TIERS's minimum-across-sessions.
- **Fix.** The K4S measurement is a **separate, reviewed script and manifest**, for example `measure_k4s.py`, that
  does not modify TIERS's frozen bytes or manifest hash. If it runs in the TIERS session:
  - it runs **after** TIERS's complete §7 list;
  - a K4S-only technical failure never triggers, invalidates or reclassifies a TIERS session;
  - the TIERS inputs it reuses (K4 feasibility for c_M = 1.0 and the §7.2 exactness verdict) are read from TIERS's
    committed receipts, never re-measured.

**N3. REQUIRED. §1.5 F0 row and §1.4 cell map: the F0 fill ignores why TIERS chose F0, and the K4S map omits TIERS
gate 3.**
- **(a) Why TIERS chose F0.**
  - TIERS selects F0 when A = ∅ (§6.5). That can mean every tier was Mac-infeasible, which is K4S's intended use. It
    can also mean K4 *was* Mac-feasible but failed V1, V2 or G1, which is a strength failure. TIERS §8's "program
    kill" treats the latter as "the failure is strength, not speed".
  - In the strength case, K4S is only shown within 10 pp of K4@1.0, so it has no claim against TIERS's verdict.
  - With c_M = 1.0, the F0 row would also deploy S-ON K4S on a full-speed Mac, contradicting §0 ("At full speed the
    tier is plain K4").
  - **Fix:** the F0 row applies only if TIERS found **K4 Mac-infeasible** (TIERS §6.3–6.4). If K4 was Mac-feasible
    and TIERS still selected F0, F0 stands. This also excludes c_M = 1.0.
- **(b) The missing exactness gate.**
  - The K4S cell gates for c ≤ 0.9 (1–6) do not include TIERS gate 3: arm64 exactness, including **1/2/4-worker
    equality** and belief/RNG exactness.
  - §5.4 kills K4S only on a *single-thread* failure. Under TIERS §7.2, a 2/4-worker-only mismatch makes K2/K4
    infeasible. That is exactly the case where TIERS falls to F0 and K4S, a 4-worker search, would then be deployed.
  - **Fix:** add, as K4S gate 0 for every c ≤ 0.9, "TIERS §6.3 gate 3 / §7.2 passes, including 4-worker equality
    (taken from TIERS's committed receipt), and SD1 agreement ≥ 99.5% (§7.3)". Extend the §5.4 Mac-side kill to "a
    4-worker equality failure kills K4S".
- **(c) Optional, for disclosure.** In the F0 case K4S has no absolute bound like TIERS V2 (< 40%). A level-B K4S
  with L(K4@1.0) near the top of the validity band (30%) could approach 40%. Add a descriptive report of
  L(K4S@c_e) with its CI next to the F0 deployment. This is not required.

## 5. Minor and nit corrections (not freeze-blocking)

- **M1.** In Q13's "r1 order" column, B(0.6) pessimistic is printed **.24**. That is r1's value with SUP(0.8)
  double-counted, while the same table corrects A(0.8) for the double count. Counted once, it is ≈ .69 × .52 × .74
  ≈ **.26–.27**. The default does not change.
- **M2.** §3.5 l.498 and Q9 ("A(0.8) … 0.71 at 2,400/600"; "3,600 adds ≈ 0.04") are **r1-order** numbers. Under r2's
  order, B(0.6) precedes A(0.8):
  - at 2,400/600, A(0.8) is ≈ .92 × .89 × .78 ≈ **0.64** central;
  - 3,600 adds ≈ 0.06–0.08.

  The conclusion (3,000/900) is unchanged and slightly strengthened. Re-state the numbers.
- **M3.** §1.3 l.147 says "At r2's writing (09:07Z)". The header (after a44bd628's correction) says 09:11Z, and
  `806f92ab` is committed 09:11:59Z. Cite the commit time: "as of `806f92ab` (09:11:59Z), the last x4s2 commit on
  origin/main is `00328d1b` (Phase B, 08:23Z)". This is verified.
- **M4. F2's disclosure.** Add an explicit sentence to §1.5: "Deployment at c_e = 0.9 permits K4S up to +5 pp (upper
  95% bound) worse than plain K4@0.9 on the Mac's own cell; this is disclosed."
- **M5. SD1 role scope.**
  - The supersession says "K4S cutoff-default role", but SD1 does three things in §2.3: the seat poll, coarse-order
    scheduling and the cutoff default. Write "the K4S S-default role defined by §2.3 (all three uses)".
  - In a sentence that will be issued formally, use full repo paths:
    `reports/strategy_council_20260928/imitation/exit-r3/RESULTS.md` (l.85, 97, 125) and `…/exit-r3/PLAN.md`.
    "Paths are relative to `reports/`" does not resolve `exit-r3/`.
- **M6.** §0 l.25–26 ("ON only when … below the full-speed cell 1.0") should say "≤ c\*" so that it also covers the
  c\* = 0.8 branch.

## 6. Freeze checklist

**Blockers to fix in the text before the freeze**
- [ ] **N1**: add the c_M ≤ c\* eligibility clause to §1.5. Record its UTC relative to phase E's reduction.
- [ ] **N2**: make the K4S Mac script and manifest separate from TIERS's frozen `measure_tiers.py`, and state the
  in-session ordering and failure-isolation rules.
- [ ] **N3**: restrict the F0 fill to "TIERS K4 Mac-infeasible", add gate 0 (TIERS gate 3 / §7.2 with 4-worker
  equality, plus §7.3 SD1 agreement), and extend §5.4.
- [ ] M1–M6, recommended in the same edit.
- [ ] A short **conformance re-check** of just these edits by someone other than the author. A diff-only check is
  enough.

**Things to fill or commit at the freeze** (r2 §7 steps 3–6)
- [ ] **F-1. The c\* record.** Apply §1.3 to the committed phase E receipt:
  - record the receipt SHA, phase E's reduction UTC, d180 with its 95% CI, and the resulting c\* plus H-sequence;
  - or record "phase E not complete → c\* = 0.9";
  - also record whether any rule text changed after the reduction; if it did, c\* = 0.9.
- [ ] **F-2. SD1.** Commit `SD1-MANIFEST.json`, binding the checkpoint `37509a43…`, calibration `e3003533…`,
  threshold, inference-source SHAs, Torch version and mode. Its sha256 is **the SD1 hash**.
- [ ] **F-3. The SD1 supersession** (§2.1, with the M5 wording), issued by `0523ae6f`, plus the additive pointer in
  `exit-r3/`.
- [ ] **F-4. The seed audit** (T1 `audit_seeds.py`, extended):
  - all seven ranges are disjoint at offsets {0, 13, 100000–100003, 271828–271829} from every listed prior bank,
    including X4S-2 E/F and all T1 banks;
  - no repo seed literal falls in 2^52 + [5.87e9, 7.37e9) on the freeze commit, not only at `bc2e4e5b`.
- [ ] **F-5. Runtime pins.** The T1 runtime `ef4c073a` bytes, native `44874fd6…`, opponent SHA, the reviewed delta
  manifest (eight deltas, each with a non-author review) and the reducer/verifier with different authors.
- [ ] **F-6. Qualification receipts on every named host.** T1 batteries; K4@1.0 ≡ T1 K4@200; K4 ≡ K4S with no
  deadline; the S-default injected-clock cases; charge share; SD1 manifest; guard-deck SHA `6d51628b…`; card
  support.
- [ ] **F-7. Host set.** At least 2 of {01, 03, 04, 08}, with per-host transport-retirement declarations, clear of
  T1 reporting and T1 END. 04 is not usable before 2026-10-12T12Z.
- [ ] **F-8. The K4S Mac procedure** (release item 5, frozen before release): the N2 script, load-selection rule and
  failure classifier.
- [ ] **F-9. The Q1–Q13 decision record.** All defaults are accepted as written; restate Q13's order and Q12's
  "TIERS stands".
- [ ] **F-10. Freeze-record attestation.** State whether T1/TIERS outcomes were open at freeze time, and that no
  PREREG-K4S text changed after this conformance round except N1–N3, M1–M6 and the F-1…F-9 fills.
- [ ] Run `clasher-secret-scan` on the staged diff, then commit and push. The coordinator commits; this reviewer
  does not.
