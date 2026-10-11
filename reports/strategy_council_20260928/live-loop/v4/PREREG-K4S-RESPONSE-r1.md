# PREREG-K4S: response to REVIEW-r1

- **Author:** design worker (Opus, 127x05), 2026-10-11T09:11Z.
- **Review:** `PREREG-K4S-REVIEW-r1.md`, an independent Claude Opus 5.5 reviewer at high effort. Verdict
  **REVISE**: 5 MAJOR, 8 MINOR, 1 NIT. The reviewer judged the games and statistics sound and the decision layer
  defective.
- **Revision:** `PREREG-K4S-DRAFT-r2.md`.
- **Disposition:** all 14 findings are **accepted**. None changes the games, arms, seeds, n, margins or α. The
  reviewer asked that the next round be a conformance check only.

| # | Severity | Disposition | Where in r2 |
|---|---|---|---|
| F1 | MAJOR | **Accepted.** Deployment is now keyed on the **TIERS selection** (not available / K4 / K2 or S / F0), not on c_M. The false premise ("TIERS has nothing feasible below 0.8×") is removed from §0 and the H2 rationale; r2 says that only **K4** is TIERS-infeasible below 0.8×. When TIERS selects S or K2, TIERS stands by default. The alternative (level-A K4S replaces S/K2) is the new **Q12**. | §0, §1.2 table, §1.5 table, Q10, Q12 |
| F2 | MAJOR | **Accepted, using the reviewer's recommendation.** With TIERS = K4 at 0.8–0.9×, K4S replaces K4 only if c_e = 0.8 is admitted at A or B, or c_e = 0.9 is admitted at A *and* the 0.9 gate-check veto passes. The +5 pp allowance vs K4@0.9 is disclosed through the veto definition. §1.5 and Q6/Q10 now state the same rule. | §1.5, Q6, Q10 |
| F3 | MAJOR | **Accepted.** Cell 1.0 is now **TIERS's K4 cell**: c_M = 1.0 iff TIERS finds K4 Mac-feasible at 1.0 under its own r_5, p10 ≥ 0.70 and gates 2–6. The SD1-specific gates (r_inf, poll p99, K4S deadline equivalence, generalised p10) apply only for c ≤ 0.9. The p10 rule is now described as a deliberate generalisation (c − 0.10), which matches TIERS at 0.8. | §1.4 |
| F4a | MAJOR | **Accepted.** The switch is defined by c_e alone (S ON iff c_e ≤ c\*). The r-based "equivalently" sentence is deleted. | §1.3 |
| F4b | MAJOR | **Accepted** (the reviewer's first option). If phase E shows S significantly hurts at 0.9×, then c\* = 0.8: H4 (A(0.9)) is dropped, the K4/K4S@0.9 arms become descriptive, and a 0.9× Mac follows TIERS (plain K4). No vacuous trailing H3′ remains. The threshold is now expressed as a cell c\* (default 0.9), not as r\*. | §1.3, §1.5, Q2 |
| F4c | MAJOR | **Accepted.** r2 states the rule text is final. At r2's writing (09:07Z), phase E had not been reduced: the X4S-2 PROGRESS on origin/main ends at phase B. The coordinator's c\* record must cite phase E's reduction UTC. Any later change to the rule voids it, and c\* then defaults to 0.9. | §1.3 |
| F5 | MAJOR | **Accepted.** New release condition 6: TIERS `tiers-summary.json` committed, or the TIERS outcome barrier released (including via its 14-day escape). A K4S Mac session run after K4S release needs an independent review of its mechanical session classification first, mirroring TIERS §6.6(b). Decoupling from the K4S Mac summary itself is kept, as the reviewer judged valid. | §4.5, §1.4, Q3 |
| F6a | MINOR | **Accepted.** The 0.9 gate check (K4S@0.9 − K4@0.9 ≤ +5) is now a **deployment veto** on c_e = 0.9. It is outside the α chain and never stops the sequence. | §1.2, §1.5 |
| F6b | MINOR | **Accepted, with the default changed.** B(0.6) moves to **H3**, before the A-levels. Under the F2 rule, B(0.8) already licenses replacing K4 on 0.8–0.9× Macs, so A(0.9) and A(0.8) carry less decision value than the 0.6× rescue. The trade-off table is in **Q13** so the coordinator can revert. New order: B(0.8), B(0.7), B(0.6), A(0.9), A(0.8), A(0.7), A(0.6). | §1.2, §3.5, Q13 |
| F6c | MINOR | **Accepted.** The nesting claim is restricted to c ≤ 0.8. B(0.9) is undefined. | §1.2 |
| F7 | MINOR | **Accepted.** r2 states that the confirmatory K4S equals X4S-2's charged (K4Sh) configuration. The pessimistic column is identified as the only direct charged estimate at 0.8 (+3.2). The shrinkage behind the central values is justified: the charge cost is ≈0 at 140/120, and the +3.5 at 160 is non-monotone. §0 now says A(0.8) is about a coin flip at the direct estimate. Sequential products count the shared SUP(0.8) event once, and Q13 notes that r1's 0.33 double-counted it. | §0, §3.5, Q13 |
| F8 | MINOR | **Accepted.** r_inf is now defined on the **same `poll_seconds` span** that the charge scales. Its fleet reference is new END item (c). The coverage derivation uses the exact emulated bound 200 − 8/c (≤ 192, conservative). Under-penalised overrun lateness (by the factor c) is disclosed. Gate 3 is restated on the poll span. | §1.4, §2.4, §4.5 |
| F9 | MINOR | **Accepted.** An undefined c_e (no usable cell ≤ c_M) leaves the TIERS outcome in place. The monotonicity convention is labelled untested, and the X4S non-monotone point estimates are cited. New §5.3 item 9 checks L(K4S@0.9) − L(K4S@0.8) and L(K4S@1.0) − L(K4S@0.9). | §1.5, §5.3 |
| F10 | MINOR | **Accepted.** A TIERS-style, role-scoped supersession sentence is added, to be issued by coordinator `0523ae6f` at the freeze. It is disclosed as outcome-informed (X4S/X4S-2). The recipe now includes the existing R2 gate/card/tile loss terms with conditional full-8,192 denominators, and the threshold's midpoint and smaller-on-tie rule. | §2.1 |
| F11a | MINOR | **Accepted.** Replacement blocks inherit the lost block's arm set. | §3.1, §3.4 |
| F11b | MINOR | **Accepted.** Primary and guard blocks are interleaved **10:3**, with the T1 B2 host balancer. | §3.1 |
| F11c | MINOR | **Accepted.** Rotation is ρ = ⌊i/50⌋ mod 8 for primary and ⌊i/18⌋ mod 8 for guard. Each cell sees all eight rotations, and rotation is no longer tied to seat. | §3.1 |
| F12 | MINOR | **Accepted.** If the END pool still fails after its repeat, it is re-run until it conforms, or the coordinator declares the K4S Mac ratio unavailable. In that case the tier is Mac-infeasible and outcomes remain releasable for the fleet claims (TIERS A1.1 wording). | §4.5 |
| F13a | MINOR | **Accepted.** New qualification step: K4@1.0 must match T1 K4@200 on command hashes and injected-clock decisions, comparing the delta runtime with the frozen T1 runtime `ef4c073a` on the qualification seeds. | §4.1 |
| F13b | MINOR | **Accepted.** `guard-decks.json` is pinned by its full sha256 `6d51628bb1262f53258e88ef6247cfb41f2762f9f13323387fcd36ad126c48ef` (verified locally and on origin/main). | §3.3, §4.1 |
| F14 | NIT | **Accepted, all five items.** (1) One baseline is used: the rescue cost is −9.7 pp at 0.8× and −25.2 pp at 0.7× (K4S − K4). (2) r1's §5.3 item 5 moves into §2.4's disclosed limits. (3) Per-decision SD1 P(play) and the coarse_order hash are added. (4) The use of K4's corpus rather than K4S's is disclosed in §1.4. (5) The n = 2,400, Δ = +5 power cell now reads .025. | §1.3, §2.4, §3.6, §1.4, §3.5 |

## Items not changed (and why)

- **Games, arms, n, margins, α and the seed bank are unchanged.** The reviewer found them sound and reproduced the
  σ, power, seed-window and compute arithmetic.
- **K4's own v1 poll is still charged.** The reviewer agreed this models one Mac consistently.
- **Phase E is still used only through the single prespecified c\* rule.**

## Request

A conformance check of r2 against F1–F14, run by a reviewer who did not author r2, then the coordinator's Q1–Q13
decisions and the c\* record. Nothing is frozen by this worker.
