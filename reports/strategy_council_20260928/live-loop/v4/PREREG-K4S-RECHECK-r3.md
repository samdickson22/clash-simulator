# PREREG-K4S-RECHECK-r3: diff-only conformance re-check of r3 against CONFORMANCE-r2

- **Blinding statement.** **I have not seen X4S-2 phase E.** I opened no file under `reports/explore/x4s2/receipts/`,
  and neither `explore/x4s2/RESULTS.md` nor `explore/x4s2/PROGRESS.md`. I read no x4s2 commit subject or message. The
  only x4s2 history I read was hash and commit time, for commits reachable from `806f92ab`.
- **Reviewer:** Claude Opus 5.5 (1M context), run as a review sub-agent at high effort on 127x05. I am independent of
  the r3 editor: I did not write r1, r2, r3 or either response. I ran only `sha256sum`, `grep`, `diff`, `git log`
  (hash and time only) and a small Python power calculation. I used no ssh, made no commits and wrote only this file.
- **Time:** 2026-10-11T09:28:50Z (`date -u`). origin/main at that time was `2041174e`.
- **Documents** (all in `reports/strategy_council_20260928/live-loop/v4/`):

  | File | sha256 | Status |
  |---|---|---|
  | `PREREG-K4S-DRAFT-r2.md` (base) | `b159d116e702c0327c303f3843a3b8e4b5bc3e9b4f9d27272e28f999fa988598` | **Verified.** The file on disk is byte-identical to `git show a44bd628:` of the same path, and a44bd628 is on origin/main. |
  | `PREREG-K4S-DRAFT-r3.md` (under check) | `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a` | Uncommitted. File mtime 09:24:40Z. Its header says it was written at 09:24:22Z. |
  | `PREREG-K4S-DIFF-r2-r3.diff` | `0ee3925399141662ba79d322bdd9bc920dc3a4817d43b5bf1e458990a362ce10` | **Verified.** Apart from its two header timestamp lines, it is byte-identical to a fresh `diff -u r2 r3` (16 hunks). |
  | `PREREG-K4S-RESPONSE-r2.md` | `a9b8f828f297393a110f944293d7dbcfe52a195f8d7bf190bfe4182ab7f0bf82` | Read. |
  | `PREREG-K4S-CONFORMANCE-r2.md` (the spec) | `ad681329c3c072e68e5486fff47db9812a1f35fd375eddb1ec0c815a1fd092b4` | Read in full. |
  | `PREREG-SEARCH-TIERS-r3-DRAFT.md` (frozen) | `ef0db97ad509753ccf63c7376f800d6db7f0b82ee07f102476eafb939e2a4c77` | **Verified.** Read §6.3–§6.6, §7 and §8 for reference only. |

## Verdict: **CONFORMS**

- All required fixes (N1, N2, N3(a), N3(b)), all minor fixes (M1–M6) and the header conform to CONFORMANCE-r2 and to
  the frozen TIERS text.
- Every one of the 16 diff hunks maps to an assigned item. **No change is unattributed.**
- No game, arm, cell, n, seed, margin, α, bootstrap or compute figure changed.
- r3 introduces **no blocking internal inconsistency**. §4 lists five optional recommendations (R1–R5). The
  coordinator may apply them at the freeze or skip them; none is required.

## 1. Per-item conformance

| Item | Verdict | r3 text (quoted) | Check against the spec and TIERS |
|---|---|---|---|
| **N1** (eligibility) | **CONFORMS** | §1.5: "**Eligibility.** K4S is deployed (in any row below) only if c_M ≤ c\*. Under c\* = 0.8, a Mac with c_M = 0.9 receives the TIERS selection, F0 included. Under the default c\* = 0.9 this clause is a no-op, because every K4S cell is ≤ 0.9." §1.3, c\* = 0.8 bullet: "a 0.9× Mac (c_M = 0.9 > c\*) receives the TIERS selection, F0 included; K4S is not eligible (§1.5 eligibility)." §0 Tier: "ON only when … c_e … is ≤ the threshold cell c\* (§1.3; default 0.9), and K4S is deployed only if the Mac's cell c_M ≤ c\*." §0 Decision: "…on a 0.8–0.9× Mac with c_M ≤ c\*". Q6: "and c_M ≤ c\* (§1.5 eligibility)". | This is the review's fix text verbatim, plus the matching §1.3 sentence. I traced the review's failure case with the r3 rules: under c\* = 0.8 with c_M = 0.9, eligibility fails, so the K4 row gives plain K4 and the F0 row gives F0. Under c\* = 0.8 with c_M = 0.8, eligibility holds and the K4 row deploys K4S with c_e = 0.8 ≤ c\*, as intended. The "no-op" claim holds. c_M = 1.0 also fails eligibility, but there the K4 row already gives plain K4, and the F0 fill excludes c_M = 1.0 (c_M = 1.0 implies K4 is TIERS-feasible). §1.3, §1.5 and §0 now agree. |
| **N1** timing note | **CONFORMS** | §1.3: "**r3's N1 edit** … implements r2's stated c\* = 0.8 consequence above; it is not a new rule. It was made at 2026-10-11T09:24:22Z by an editor who had not seen any X4S-2 phase E output. The coordinator's c\* record states whether it precedes phase E's reduction. If it does not, the locking clause applies and c\* = 0.9, under which the clause is a no-op." | Matches the review's N1 "Timing" guidance: record the UTC, and if the edit came after the reduction, c\* = 0.9. Both paths are safe. See R1 and R2 for evidencing the time and for the locking-clause wording. |
| **M6** | **CONFORMS** | §0 Tier, as quoted above: "≤ the threshold cell c\* (§1.3; default 0.9)". | "Below the full-speed cell 1.0" has been replaced. |
| **N2** (separate script) | **CONFORMS** | §1.4: "the K4S measurement uses its **own** reviewed script and manifest (for example `measure_k4s.py`). It never edits TIERS's frozen `measure_tiers.py`, the TIERS manifest or its hash (TIERS §6.6(a))." Sub-bullets: "runs only **after TIERS's complete §7 list**"; "A K4S-only failure never triggers, invalidates or reclassifies a TIERS session, and never adds a session to TIERS's minimum across sessions"; reused TIERS inputs "are read from TIERS's committed receipts, never re-measured." Also Q5, §4.5 item 5 ("separate from `measure_tiers.py`"), §4.6 ("after TIERS's §7 list") and §7 step 4 ("`measure_tiers.py` is not edited"). | All three parts of the review's fix are present: separate bytes and manifest, running after §7, and failure isolation. The "minimum across sessions" clause goes further than the review asked, in the same direction as its intent. TIERS §6.6(a) freezes `measure_tiers.py` in the TIERS manifest, and r3 now leaves it untouched. The header line "It edits no TIERS or T1 file" is now true. |
| **N3(a)** (F0 fill) | **CONFORMS** | §1.5 F0 row: "Only if TIERS found **K4 Mac-infeasible** (TIERS §6.3–6.4): if c_e is defined and ≤ c\*, K4S at c_e … otherwise F0. If K4 was Mac-feasible and TIERS still selected F0 (a strength failure, TIERS §8), **F0 stands**." Also §0 Decision ("because it found K4 Mac-infeasible") and Q10. | The two cases cover every F0 outcome. Under TIERS §6.5.1, K4 ∉ A means K4 was either infeasible or failed V1, V2 or G1. TIERS §8 "Tier kills" covers the second case. c_M = 1.0 is excluded, because §1.4 defines c_M = 1.0 as "TIERS finds K4 Mac-feasible in its 1.0 cell". The optional N3(c) disclosure was not adopted, which is acceptable because the review marked it "not required". |
| **N3(b)** (gate 0, kill rule) | **CONFORMS** | §1.4 cell mapping: "0. **Exactness (TIERS gate 3).** TIERS §6.3 gate 3 / §7.2 passes on this Mac, including belief/RNG exactness and **1/2/4-worker equality** (taken from TIERS's committed receipt), and SD1 cross-platform agreement is **≥ 99.5%** (TIERS §7.3 procedure and tolerances)." §5.4: "A 2/4-worker-only equality failure (TIERS §7.2), or any other §1.4 gate 0 failure, kills K4S on that Mac: K4S is a 4-worker search." | Matches TIERS §6.3 gate 3 (which incorporates §7.2) and the §7.2 outcomes ("A mismatch only in 2/4-worker equality ⇒ K2/K4 infeasible"). The §7.3 threshold and tolerances (≥99.5%; 1e-4 / logit tie) are imported by reference. Gate 0 does not depend on the cell, so failing it means "nothing passes" and the tier is Mac-infeasible, which agrees with the §5.4 kill. It also agrees with the existing §5.4 bullets on SD1 agreement below 99.5% and on single-thread exactness. |
| **M1** | **CONFORMS** | Q13: "\| B(0.6) \| .96 (.67) \| .86 (≈.27) \|" | I re-derived **.270** (§3). |
| **M2** | **CONFORMS** | §3.5: "At 2,400 / 600, A(0.8) falls to ≈ 0.65 central under this order (cumulative .91 × .90 × .80, because B(0.6) now precedes it)." and "3,600 / 1,080 adds ≈ 0.08 for about 20% more cost (≈ 0.06 if the guard stays at 900)." Q9: "0.86 vs ≈ 0.65 at 2,400 / 600 with B(0.6) at H3; 3,600 / 1,080 adds ≈ 0.08". | I re-derived **.650**, +.077 and +.058 (§3). The review's ≈0.64 came from coarser rounding of the factors (.92 × .89 × .78). The editor's 0.65 is the more exact value. |
| **M3** | **CONFORMS** | §1.3: "As of `806f92ab` (09:11:59Z), the last x4s2 commit on origin/main was `00328d1b` (Phase B, 08:23Z), so phase E had not been reduced." | Verified hash and time only. `806f92ab` committed 2026-10-11T09:11:59+00:00 and is on origin/main. The last commit touching `reports/explore/x4s2` that is reachable from it is `00328d1b`, at 01:23:04−07:00 = 08:23:04Z. For the label "Phase B" I relied on CONFORMANCE-r2; I did not read the subject. |
| **M4** | **CONFORMS** | §1.5: "**Allowance at 0.9 (disclosed).** Deployment at c_e = 0.9 permits K4S to be up to +5 pp (upper 95% bound) worse than plain K4@0.9 on the Mac's own cell; this is disclosed." | This is the review's sentence verbatim. It matches the §1.2 veto definition (upper bound ≤ +5 pp). |
| **M5** | **CONFORMS** | §2.1 supersession: "(`reports/strategy_council_20260928/imitation/exit-r3/RESULTS.md` l.85, 97, 125) **for these exact bytes in the K4S S-default role defined by §2.3 only (all three uses: the seat poll, the coarse ordering and the cutoff default)**." Recipe source and pointer location also use full paths. | All three §2.3 uses are named, matching §2.3 items 1–3. Both paths exist. RESULTS.md l.85, l.97 and l.125 carry the NEVER-ADOPTABLE text. On a path-convention nit, see R4. |
| **Header** | **CONFORMS** | "Draft r3, 2026-10-11T09:24:22Z … r3 changelog (text only; no game, arm, cell, n, seed, margin, α, bootstrap or compute figure changes)" with N1–N3 and M1–M6 and their section references. | Every section reference in the changelog matches a diff hunk (§2). The header time is consistent with the file mtime (09:24:40Z). The relabelling to "What changed in r2" and the new "History" bullet are header bookkeeping only. |

## 2. Hunk-by-hunk attribution (fresh `diff -u r2 r3`, 16 hunks)

| # | r2 → r3 lines | Content | Item |
|---|---|---|---|
| 1 | 1,9 → 1,22 | Title r3, "What this is", changelog, History, relabelled "What changed in r2" | Header |
| 2 | 23,7 → 36,8 | §0 Tier: "≤ the threshold cell c\*" and "deployed only if c_M ≤ c\*" | M6, N1 |
| 3 | 41,8 → 55,8 | §0 Decision: "with c_M ≤ c\*"; "because it found K4 Mac-infeasible" | N1, N3(a) |
| 4 | 141,12 → 155,17 | §1.3 c\* = 0.8 consequence; Locking cites `806f92ab`; r3 N1 timing note | N1, M3 |
| 5 | 177,6 → 196,9 | §1.4 gate 0 | N3(b) |
| 6 | 192,8 → 214,14 | §1.4 Implementation (separate script, after §7, isolation, receipts) | N2 |
| 7 | 204,17 → 232,22 | §1.5 Allowance at 0.9; Eligibility; F0 row | M4, N1, N3(a) |
| 8 | 243,7 → 276,8 | §2.1 recipe source full path | M5 |
| 9 | 270,13 → 304,15 | §2.1 supersession role and full paths; pointer path | M5 |
| 10 | 495,8 → 531,9 | §3.5 Choice numbers | M2 |
| 11 | 636,7 → 673,8 | §4.5 release item 5 | N2 |
| 12 | 663,7 → 701,7 | §4.6 Mac line | N2 |
| 13 | 716,6 → 754,8 | §5.4 4-worker / gate-0 kill | N3(b) |
| 14 | 743,7 → 783,7 | §7 step 4 | N2 |
| 15 | 763,12 → 803,12 | Q5, Q6, Q9, Q10 | N2, N1, M2, N3(a) |
| 16 | 777,6 → 817,6 | Q13 r1-order B(0.6) | M1 |

**Unattributed changes: none.** Every consistency edit outside the core sections (§0 Decision, Q6, Q10, §4.5 item 5,
§4.6, §7 step 4) directly implements N1, N2 or N3, as the assignment allows.

**Figure check.** I tokenised the numbers in the removed and added diff lines. The only numerals that were removed
outright are:
- `09:11` (r2 header time);
- `09:07` (old Locking time, replaced under M3);
- `0.71` ×2 (§3.5 and Q9, replaced under M2);
- `0.04` (§3.5, replaced under M2).

Every added numeral is one of:
- a SHA fragment, a date or time, or a section reference;
- 99.5 (gate 0, from TIERS §7.3, already in §5.4);
- the M1/M2 values (.27, 0.65, .91/.90/.80, 0.08, 0.06, 3,600 / 1,080 / 900);
- the M4 values "+5 pp" and "95%".

**No game, arm, cell, n, seed, margin, α, bootstrap or compute figure changed.** The design table, the arm-cell
table, the seed bank, the §3.5 planning values and sequential-power table, §4.6 games and wall time, and §5.1 are
all outside every hunk.

## 3. Independent re-derivation of M1 and M2

**Model.**
- One-sided α = 0.025 (z = 1.95996), with SE = 100σ/√n pp.
- Non-inferiority power: NI = Φ((M − Δ)/SE − z). Superiority power: SUP = Φ(−d/SE − z).
- σ values: 0.47 (NI), 0.51 (NI at 0.6), 0.50 (SUP), 0.56 (guard).
- Planning values from r2/r3 §3.5. Central: Δ_ref +1.5 / +2.0 / +4.2 / +6.5; guard +2.0 / +2.5 / +3.5 / +5.
  Pessimistic: Δ_ref +2.5 / +3.2 / +4.7 / +7.5; guard +3.5 / +3.5 / +3.5 / +8.
- SUP(0.8) is −6.2 central and −3.0 pessimistic, counted once. SUP at 0.7 and 0.6 is −24 / −60 on the subsample.

**Model check.** At 3,000 / 900 in the r2/r3 order, this model reproduces the §3.5 table:
- central: .964 / .938 / .862;
- pessimistic: .908 / .669 / .520 / .270.

**M1** (r1 order B(0.8), B(0.7), A(0.9), A(0.8), B(0.6), pessimistic):

| Step | Marginal | Cumulative |
|---|---:|---:|
| B(0.8) | .908 | .908 |
| B(0.7) | 1.000 | .908 |
| A(0.9) | .777 | .705 |
| A(0.8) | .519 | .366 |
| B(0.6) | .738 | **.270** |

r3's "≈.27" is correct.

**M2** (r2/r3 order, central, n = 2,400 / 600):

| Step | Marginal | Cumulative |
|---|---:|---:|
| B(0.6) | .912 | .911 |
| A(0.9) | .895 | .816 |
| A(0.8) | .796 | **.650** |

Central A(0.8) cumulative power at other sizes, against .862 at 3,000 / 900:

| Size | A(0.8) | Gain |
|---|---:|---:|
| 3,600 / 1,080 | .939 | **+.077** |
| 3,600 / 900 | .920 | **+.058** |

r3's "≈ 0.65", "≈ 0.08" and "≈ 0.06 if the guard stays at 900" are correct. The editor's response arithmetic
matches mine to three decimals.

## 4. Internal consistency introduced by r3

- **Eligibility clause vs the K4 row.**
  - The two are consistent. Under c\* = 0.9, the K4 row's own condition "c_M ≤ 0.9" equals eligibility.
  - Under c\* = 0.8, eligibility narrows the K4 row to c_M = 0.8, and therefore c_e = 0.8, which is the intended
    outcome.
- **Gate 0 vs §5.4.** Consistent (see N3(b) above). The 2-worker-only case also kills K4S, which matches TIERS §7.2
  (it makes K2/K4 infeasible).
- **N2 vs the §1.4 integrity bullets.**
  - The two are consistent. "One valid session … minimum r … across valid sessions" governs K4S's own sessions.
  - The new clause stops K4S sessions from entering TIERS's minimum. See R3 for a non-blocking ambiguity.
- **N1 timing note vs the locking clause.** These are consistent when read together: the note gives the condition
  under which the locking clause does or does not void the rule. See R1 and R2.
- **Nothing new contradicts §0's expected-outcome table, the §1.2 sequence, §5.2 or §6.**

## Recommendations (optional; none is required for the freeze)

- **R1. Evidencing the N1 edit time.**
  - "Made at 2026-10-11T09:24:22Z" is the editor's attestation. r3 is not yet committed.
  - The c\* record (CONFORMANCE-r2 F-1) should compare phase E's reduction UTC with a verifiable time for r3. That
    means the commit time of the first commit containing these bytes (sha256 `9650972d…`), alongside this re-check's
    observation of the same sha256 at 09:28:50Z.
  - If only the commit time is admissible and it falls after the reduction, the §1.3 clause sends c\* to 0.9, which
    is safe.
  - Committing r3 promptly keeps the c\* = 0.8 branch available.
- **R2. Locking wording (nit).**
  - §1.3 still reads "This rule text is final as of r2", while r3 edits the c\* = 0.8 consequence bullet.
  - The adjacent N1 note resolves this. Optionally, append "(the r3 N1 edit below excepted, under the condition
    stated there)" so that no reader takes the r3 edit itself as a void-triggering change.
- **R3. Session validity across the two scripts.**
  - Not specified: whether a TIERS-invalid session also invalidates the K4S measurements taken in that session.
  - Not specified: which TIERS receipt, after TIERS's own minimum-across-sessions, supplies the gate 0 and
    c_M = 1.0 inputs.
  - Suggested rule for the frozen K4S Mac procedure (CONFORMANCE-r2 F-8):
    - K4S uses TIERS's final committed verdicts;
    - a K4S block inside a session that TIERS classifies as technically invalid is itself invalid.
  - The PREREG text does not need to change.
- **R4. Path convention (nit).** The header says "Paths are relative to `reports/`", but §2.1 now uses repo-root paths
  that begin with `reports/`. This is harmless, because the review asked for full repo paths in the sentence to be
  issued. Optionally mark them "(repo-root path)".
- **R5. Pre-existing items, out of r3's scope.** These were not changed, which was correct under the assignment. They
  are listed for the coordinator only.
  - §1.2 H4 row: "a 0.9× Mac otherwise uses 0.8 evidence" describes only the default c\* = 0.9.
  - §7 step 1 still names the r2 conformance check.
  - Q13 r1-order pessimistic A(0.9) .69 and A(0.8) ≈.35: under the model above these are .705 and .366, and the
    editor's own response shows the same values.
  - Gate 0 reuses TIERS's §7.2 receipt. That reuse is valid only if K4S's 4-worker scorer and native bytes
    (`44874fd6…`) are the ones TIERS qualified on the same Mac. F-8 should bind this.
