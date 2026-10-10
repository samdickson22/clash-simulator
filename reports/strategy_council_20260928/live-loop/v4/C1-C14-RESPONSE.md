# C1–C14 response: PREREG search tiers r2

PREREG revision author (Opus), 2026-10-10, for coordinator `0523ae6f`. This maps each condition in
`REVIEW-PREREG-SEARCH-TIERS-20261010.md` to the edited text. It is an input to the required pre-freeze conformance
check. Nothing is committed or launched.

**Files (line numbers refer to these files as written):**
- **P** = `live-loop/v4/PREREG-SEARCH-TIERS-r2-DRAFT.md`
- **A** = `live-loop/v4/mac-e4-package/E4-V3-ADDENDUM-r2-DRAFT.md`
- **M** = `DECISION-MAC-TIERS-20261010-r2.md`

The r1 drafts are unchanged. Where r2 goes beyond the condition's wording, the row says so under **Note**.

| C | Requirement | Where applied |
|---|---|---|
| **C1** | R3a under its own name; supersede NEVER-ADOPTABLE for these bytes only, outcome-informed; S1/r1(b) planning only | P 87–95: the review's paragraph, verbatim. "S1-student" removed everywhere. §9 D1: P 459–460. |
| | Reason 2 marked post-hoc | P 105 |
| | Disclosures: chain, R3b–R3e, r1 S-teacher, only student measured, heldout64 calibration, fallback not equalised, training overlap (8 decks incl. L2; v1 in mix) | P 119–135 (§2.2); also P 482–483 (§10) |
| | Verifier author ≠ reducer author; conformance reviewer not in S1/R3 | P 137–141 (§2.3); P 294–295; P 6–7 |
| | Memo "One caveat" | M 26–31 |
| **C2** | Delete "which the student never trained on" | Deleted; P 113–114 now says the own decks **are** in R3a's training corpus |
| | Guard: L2 own decks vs the 3 most frequent C56-catalogue decks not among the 8 R1 decks, all cards supported by native/v1/R3a; hashed selection script before freeze; alternating seats; 600 seeds; 3 × 3 × 2; card-support qualification, no unknown-card fallback | P 148–160. Catalogue path `c56/engine/root-v3/human_deck_catalog.json` (the one `exit_r1/emitter.py` reads). |
| | G1 (upper 95% < 0 vs K0c) and G2 (cheaper vs costlier admissible ≤ +10 pp, upper 95%) | P 49–50 (table); P 368 (G1 in A); P 374–377 (G2 in the rule); power P 274–276 |
| | Descriptive L2-own vs L2-opponent cells | P 161–162, P 59–60. **Note:** made concrete as 72 descriptive seeds (range at P 175), never in a gate. |
| | §2.1 point 3, §0 | P 113–114; P 17–18 |
| **C3** | Rule item 3, verbatim (cheapest T with NI against **every** costlier U ∈ A at 97.5%; else most cores) | P 371–373 (G2 added at P 374–376) |
| | "Monotone" claim replaced | P 388–390 (verbatim replacement plus examples). "monotone" no longer appears. |
| | Full float precision, no rounding | P 291–292; A 106 |
| | NI at 97.5% in §5 | P 283–284; rationale P 57–58; P 51 |
| **C4** | Work unit = the complete decision (belief prep, candidates, root, scoring, reduction, forward/proposals); exactness covers final action and scores | P 304–312; A 81–83 |
| | r_T = min(median ratio, Σ/Σ, p90/p90); p10 ≥ 0.70 | P 327–335; P 342; A 109–111 |
| | Gate 6: fleet deadline-mode reference at 200/160 ms (C5 hosts/load, 3 repeats); Mac 200 ms corpus run (D5b); ≤ fleet + 2 pp; else move down one cell; below 0.8 infeasible | P 320–323 (fleet reference); P 353–356 (gate); P 361–363 (cell step-down); A 94 (D5b); A 112–114 |
| | Corpus states from each tier's own excluded games | P 301–303 (each tier plays the corpus range itself; outcomes never read) |
| | **Note** | r_1 is split into r_S and r_K0c (P 333–334). S's cell uses r_S; the control cell uses r_K0c, so a slow student cannot drop the control into the collapsed 0.8 cell and make V1 easier. |
| **C5** | Reference under the reporting load profile (all other slots run the corpus loop) | P 313–315 |
| | Every reporting host; ±5% exclusion; pooled per-state median | P 313, P 317–319 |
| | `/proc/cpuinfo` MHz during reference and reporting | P 316 |
| **C6** | Belief/RNG exactness: 125 histories, posterior, weights, cumulative order, ledger, samples, RNG, deadline ON/OFF | P 411–413; A 89 (D1b) |
| | D1 bracket replaced: single-thread mismatch ⇒ **all** tiers; 2/4-worker only ⇒ K2/K4 | A 88 (verbatim); P 415–417. Belief mismatch ⇒ all tiers (A 89, P 415). |
| | ARM64-NEAR-EXACT (125/125 actions and candidates, scores ≤ 1e-12 relative) | P 418–420; A 100–103. **Note:** extended to belief floats only when every discrete output matches exactly. |
| | D2: top-8 swap allowed iff fleet logits differ by ≤ 1e-4; gate rule kept | A 90; P 423–424 |
| **C7** | B.1 "§D5" → "§D7" | A 52 |
| | B.2 pinned psutil, or `host_processor_info` via ctypes | A 56–57 |
| | D5 per-state median over repeats; rotated 50-state tier blocks | A 93; A 108; P 329, P 430–431 |
| | "Opportunity" from packet timestamps at live cadence; delayed = >25 ms; gate 4 = ≤1% and no pause adding a charged tick (>50 ms) | P 344–350; A 115–118 |
| | D8 for every tier passing gates 1–3 and 5; `gc.freeze()` once after warm-up, default thresholds | A 97; A 119–120; P 344–345; P 439–440 |
| | Emulator state from the process table only | A 66–68 |
| | Exclusive Mac: coordinator lock + 5-min census, no foreign process > 0.2 core | A 34–40 |
| | §F classification mechanical, by frozen script from receipts | A 156–158; P 385–387 |
| **C8** | PROVISIONAL (emulator-off) text, verbatim; formal E4 amended first | P 379–382 (§6.5 item 5); P 22–23 (§0); P 490–492 (§10); P 511–513 (§11); A 172–175 (G); M 65–67 |
| **C9** | Drift suspension with defined exit, verbatim | P 446–449; M 93–94 |
| **C10** | (a) `measure_tiers.py` and the reducer frozen before any reporting game | P 395–396; A 53–55; P 503–504 |
| | (b) Outcome barrier closed until `tiers-summary.json` is committed; 14-day escape; independent check of later repeats | P 397–400; P 507–510; A 16–17, A 156–158; M 43–44, M 85–86 |
| | (c) Replacement bank, same matchup/seat, blind to outcomes; guard analogue | P 168, P 170 (ranges); P 220–223 (index 2400 + 50·k + c; 600 + 18·k + (i mod 18)) |
| | (d) >10% replaced ⇒ stop and amend before opening outcomes | P 224–225; P 453 |
| | (e) Off-host copy at least every 30 min | P 210–212 |
| | **Note** | Added: stop if a cell's bank row is exhausted (P 225), and a lost-host rule (continue on the remaining hosts; stop if fewer than two remain; P 226–228). |
| **C11** | Code deltas listed; qualification batteries re-run; identical pins per host | P 189–206 (8 deltas, diff review, S1 + K2 + K-v2 batteries on every host, per-host pin receipts) |
| | Hosts from {01, 03, 04, 08} | P 182–185; P 37; M 42 |
| | Pause hub mirror and cross-host pollers via stop files | P 218–219 |
| | `fleet-console-users`; 8 slots if positive at launch | P 183–185 |
| | Stop a host when a console user exceeds one core for > 60 s; in-flight blocks to the bank | P 216–217 |
| **C12** | v1 is the training opponent; the ranking against humans is untested | P 480–481; M 89–90 |
| | In-distribution asymmetry favours S | P 482–483; P 131–135; M 31–32 |
| | F0's Mac feasibility unmeasured | P 484–485; P 370; M 63–64 |
| | One-root L2-v4 amendment first; wait if L2-v4 has started with K = 4 | P 486–487; P 464–465; A 179 |
| | Uncharged GC pauses between decisions | P 488–489 |
| **C13** | Cost ≈ 1,500 reserved core-h (≈ 400–450 used), ≈ 7 h on four hosts, ≈ 15 h on 100 cores | P 35–38; M 74–76 |
| | S1 power "0.67 at its own α (0.48 at the Bonferroni α)" | P 267–268 |
| | §6.1 "smoke-range" → "corpus-range" | P 301–302 |
| | Memo: "within the 5-point margin in one exploratory study"; CI rule wording; cost; provisional | M 21–22; M 58–60; M 74–76; M 65–67 |
| **C14** | The 0.8-cell case: K4@160 likely beats S@160 by > 5 pp, so K4 is selected | P 29–31; M 61–64 |

## The two power statements

1. **S1's own power** (C13): P 267–268 now reads "about 0.67 power at its own α (0.48 at this study's Bonferroni
   α)". Recomputed: σ = 0.61 at n = 600 gives 0.673 at one-sided 0.025.
2. **False NI of K2 against K4:** P 269–271. Because NI moved to 97.5% (C3), the figure is restated at the new level:
   about 6×10⁻⁸ at the planning σ = 0.56 (3×10⁻⁹ at σ = 0.48). It also records that r1's "<10⁻⁷" held at 95% only for
   σ = 0.48 (1.6×10⁻⁸; 2.6×10⁻⁷ at 0.56), which matches the reviewer.

Also updated because of C3: the NI power table at 97.5% (P 259–264). At n = 2,400 it gives 0.98 at a true 0 and 0.90
at +1, matching the reviewer's 0.983 and 0.896.

## Recommendations C15–C18

- **C15 (Mac before outcomes):** adopted as a preference (P 401–402, P 508; M 99). C10(b) already enforces the
  ordering.
- **C16 (1,200-seed guard):** not adopted. It would add about 600 blocks (about 300 core-h). G2 stays at +10 pp, as
  C2 specifies (P 55–56).
- **C17 (logging):** adopted (P 84–85; harness delta 7 at P 200).
- **C18 (factorial ablation):** left as a separate exploration item (P 117–118).
