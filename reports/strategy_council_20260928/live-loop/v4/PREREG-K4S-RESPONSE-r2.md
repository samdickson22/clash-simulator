# PREREG-K4S: response to CONFORMANCE-r2

- **Author:** design worker (Opus, 127x05), round-3 editor for coordinator `0523ae6f`; written 2026-10-11T09:25Z.
- **Review:** `PREREG-K4S-CONFORMANCE-r2.md`, verdict **CONFORMS_WITH_FIXES** (N1–N3 required, M1–M6 minor).
- **Base:** `PREREG-K4S-DRAFT-r2.md`, commit `a44bd628`, sha256 `b159d116e702c0327c303f3843a3b8e4b5bc3e9b4f9d27272e28f999fa988598`
  (verified on disk before editing).
- **Revision:** `PREREG-K4S-DRAFT-r3.md`; full change in `PREREG-K4S-DIFF-r2-r3.diff`. Nothing else was changed.
- **Phase E blinding.** The editor did not open any X4S-2 phase E/threshold receipt, `explore/x4s2/RESULTS.md` or
  `explore/x4s2/PROGRESS.md`. The only x4s2 history read was hash and commit time (no subjects), at or before
  `806f92ab`, for M3.

| # | Disposition | Where in r3 |
|---|---|---|
| N1 | **Applied.** New §1.5 **Eligibility** clause: "K4S is deployed (in any row below) only if c_M ≤ c\*. Under c\* = 0.8, a Mac with c_M = 0.9 receives the TIERS selection, F0 included"; a no-op under the default c\* = 0.9. §1.3's c\* = 0.8 bullet now says the same ("receives the TIERS selection, F0 included; K4S is not eligible"), replacing "plain K4". A §1.3 timing note records that the edit implements r2's stated consequence, was made at 2026-10-11T09:24:22Z by a phase-E-blind editor, and that the c\* record must state whether it precedes phase E's reduction (else c\* = 0.9 and the clause is moot). §0 Tier/Decision and Q6 add "c_M ≤ c\*". | §1.5, §1.3, §0, Q6 |
| N2 | **Applied.** §1.4 Implementation: K4S uses its **own** reviewed script and manifest (e.g. `measure_k4s.py`) and never edits `measure_tiers.py`, the TIERS manifest or its hash (TIERS §6.6(a)). Inside a TIERS session it runs only after TIERS's complete §7 list; a K4S-only failure never triggers, invalidates or reclassifies a TIERS session, nor adds one to TIERS's minimum across sessions; the reused TIERS inputs (K4 1.0-cell feasibility, §7.2 verdict) are read from TIERS's committed receipts. Q5, §4.5 item 5, §4.6 Mac line and §7 step 4 updated to match. | §1.4, Q5, §4.5, §4.6, §7 |
| N3 | **Applied, both parts.** (a) §1.5 F0 row: K4S fills F0 only if TIERS found **K4 Mac-infeasible** (§6.3–6.4); if K4 was Mac-feasible and TIERS still chose F0, **F0 stands** (this also excludes c_M = 1.0). §0 Decision and Q10 say the same. (b) New §1.4 **gate 0** for every c ≤ 0.9: TIERS §6.3 gate 3 / §7.2 incl. belief/RNG exactness and **1/2/4-worker equality** (from TIERS's committed receipt), plus SD1 agreement **≥ 99.5%** (§7.3). §5.4 Mac side: "A 2/4-worker-only equality failure (TIERS §7.2), or any other §1.4 gate 0 failure, kills K4S on that Mac". N3(c) (optional descriptive V2-style report) was not adopted, to keep the change set to the assigned items. | §1.5, §1.4, §5.4, §0, Q10 |
| M1 | **Applied.** Q13 r1-order B(0.6) pessimistic .24 → **≈.27** (arithmetic below). | Q13 |
| M2 | **Applied.** §3.5 Choice: A(0.8) at 2,400/600 is **≈ 0.65** central under the r2/r3 order (.91 × .90 × .80); 3,600/1,080 adds **≈ 0.08** (≈ 0.06 with guard kept at 900). Q9 updated. The review's ≈0.64 agrees within the guard planning range (0.62–0.67, below). | §3.5, Q9 |
| M3 | **Applied.** §1.3 Locking now reads "As of `806f92ab` (09:11:59Z), the last x4s2 commit on origin/main was `00328d1b` (Phase B, 08:23Z)". Verified: `806f92ab` committer time 2026-10-11 09:11:59 +0000; last commit touching `reports/explore/x4s2` reachable from it is `00328d1b` at 08:23:04 +0000. | §1.3 |
| M4 | **Applied.** §1.5 sentence: "Deployment at c_e = 0.9 permits K4S to be up to +5 pp (upper 95% bound) worse than plain K4@0.9 on the Mac's own cell; this is disclosed." | §1.5 |
| M5 | **Applied.** Supersession now covers "the K4S S-default role defined by §2.3 only (all three uses: the seat poll, the coarse ordering and the cutoff default)", citing `reports/strategy_council_20260928/imitation/exit-r3/RESULTS.md` l.85, 97, 125. The pointer location and the recipe's `PLAN.md` source use the same full path (both files verified to exist there). | §2.1 |
| M6 | **Applied** (with N1). §0 Tier: ON only when c_e "≤ the threshold cell c\* (§1.3; default 0.9)". | §0 |
| Header | Marked **r3** with write time 2026-10-11T09:24:22Z, changelog N1–N3/M1–M6 with section references; the r2 "What changed" bullet is relabelled "What changed in r2" and r1 lineage moved to a History bullet. | header |

## Arithmetic for M1 and M2

Model (r2 §3.5 planning values): one-sided α = 0.025, z = 1.95996. NI power = Φ((M − Δ)/SE − z); SUP power =
Φ(−d/SE − z); SE = 100·σ/√n pp. σ = 0.47 (NI), 0.51 (NI at 0.6), 0.50 (SUP), 0.56 (guard). Δ_ref central / pessimistic:
0.9 +1.5/+2.5, 0.8 +2.0/+3.2, 0.7 +4.2/+4.7, 0.6 +6.5/+7.5. Guard Δ_ref^G: central 0.9 +2.0, 0.8 +2.5, 0.7 +3.5,
0.6 +5; pessimistic +3.5 at 0.9–0.7, +8 at 0.6. SUP(0.8) −6.2 / −3.0, counted once; SUP(0.7/0.6) −24/−60 on n = 600.
Script: `/tmp/sdicks02/k4s-r3/power.py` (scratch, not committed).

**Check against r2's table (n = 3,000/900):** central cumulative B(0.6) .964, A(0.9) .938, A(0.8) .862; pessimistic
.669 / .520 / .270. These reproduce r2's .96/.94/.86 and .67/.52/.27, so the model matches.

**M1 (r1 order: B(0.8), B(0.7), A(0.9), A(0.8), B(0.6); pessimistic):**
- SUP(0.8): SE 0.913, Φ(3.0/0.913 − 1.96) = Φ(1.326) = .908; B(0.8)/B(0.7) NI parts ≈ 1 → .908.
- A(0.9): NI5 at +2.5, SE .858: Φ(0.954) = .830; guard NI10 at +3.5, SE 1.867: Φ(1.522) = .936 → .777; cum .705.
- A(0.8): NI5 at +3.2: Φ(0.138) = .555; guard NI10 at +3.5: .936 → .519; cum .366.
- B(0.6): NI10 at +7.5, SE .931: Φ(0.725) = .766; guard NI15 at +8: Φ(1.789) = .963 → .738; cum **.270 ≈ .27**.
- (Central r1-order check: .973 / .894 / .862, matching Q13's .97 / .89 / .86.)

**M2 (r2/r3 order, central, n = 2,400 / 600):** SE primary .959 (σ .47), 1.041 (σ .51); guard 2.286.
- B(0.6): NI10 at +6.5: Φ(3.5/1.041 − 1.96) = Φ(1.402) = .920; guard NI15 at +5: Φ(2.414) = .992 → .912; cum .911.
- A(0.9): NI5 at +1.5: Φ(1.690) = .954; guard NI10 at +2: Φ(1.540) = .938 → .895; cum .816.
- A(0.8): NI5 at +2.0: Φ(1.168) = .879; guard NI10 at +2.5: Φ(1.321) = .907 → .797; cum **.650**.
- Sensitivity to the central guard value at 0.8 (+2.0 / +2.5 / +3.0): .672 / .650 / .619.

**3,600 vs 3,000 (central A(0.8) cumulative):**

| Guard Δ^G(0.8) | 3,000/900 | 3,600/1,080 | gain | 3,600/900 | gain |
|---|---:|---:|---:|---:|---:|
| +2.0 | .871 | .942 | +.071 | .929 | +.058 |
| +2.5 | .862 | .939 | +.077 | .920 | +.058 |
| +3.0 | .847 | .930 | +.083 | .904 | +.057 |

Hence "≈ 0.08 (≈ 0.06 if the guard stays at 900)", consistent with the review's 0.06–0.08.

## Request

A diff-only conformance re-check of N1–N3 and M1–M6 by a reviewer independent of this editor
(`PREREG-K4S-RECHECK-r3.md`). Nothing is frozen by this worker.
