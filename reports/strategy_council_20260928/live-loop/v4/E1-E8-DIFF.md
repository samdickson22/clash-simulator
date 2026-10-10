# E1–E8 diff: PREREG search tiers r2 → r3

PREREG r3 editor (Opus), 2026-10-10, for coordinator `0523ae6f`. This applies edits E1–E8 of
`REVIEW-PREREG-SEARCH-TIERS-r2-CONFORMANCE-20261010.md` §5, and nothing else. Nothing was committed or launched.
The only remote action was a read-only `ssh 127x01` to hash the catalogue. Paths are relative to `reports/`.

## Files

| r2 | r3 | Hunks |
|---|---|---:|
| `live-loop/v4/PREREG-SEARCH-TIERS-r2-DRAFT.md` | `live-loop/v4/PREREG-SEARCH-TIERS-r3-DRAFT.md` | 13 |
| `live-loop/v4/mac-e4-package/E4-V3-ADDENDUM-r2-DRAFT.md` | `live-loop/v4/mac-e4-package/E4-V3-ADDENDUM-r3-DRAFT.md` | 2 |
| `DECISION-MAC-TIERS-20261010-r2.md` | **Not produced; no edit affects it.** E1 cites M 40, but the review says that, with E1 in place, "three common human decks the student never trained against" is accurate. No other edit touches M. | 0 |

**Coverage.** Each edit maps to these hunks:
- E1: P2.
- E2: P11, A2.
- E3: P10.
- E4: P9, A1.
- E5: P4.
- E6: P6.
- E7: P8.
- E8: (a) P5, (b) P1, (c) P13, (d) P3, (e) P7, (f) P12, (g) P2, in its last two `+` lines.

Every hunk carries exactly one E-label. The exception is P2, where E1 and E8(g) are adjacent lines, so diff merges them
into one hunk. A few unchanged neighbouring words were rewrapped onto new lines to keep the ~118-column wrap.

## E1 evidence (catalogue pin and selection re-run)

- **Pinned copy (127x01, read-only `sha256sum`):**
  `/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json`.
  - SHA-256 `80de4afb5b63c7dbdcb0ab285a715f9a93f4d6eeacffdfbe9f8c300ea7fecd8a`, 655,636 bytes, 2,925 decks.
  - Schema `c56-human-deck-catalog-v1`, `source_role` train.
  - `git ls-files` confirms that the file is untracked.
  - Every other copy found on 127x01 (job snapshots, `search-noise*/runtime/support/`) has the same SHA, as does the
    reviewer's copy at `127x05:/tmp/sdicks02/review-cat/`.
- **Re-run.**
  - Script: `/tmp/sdicks02/r3-editor/select_guard.py` on 127x05 (scratch; not a frozen artefact).
  - The script uses `exit_r1/emitter.py` `decks()` logic verbatim, with `archetype()` copied verbatim from
    `src/clasher/analysis/loss_review/metrics.py`, because that module imports numpy, which is absent here.
  - It walks the catalogue in descending frequency and keeps a deck iff it shares ≤ 4/8 cards with each R1 deck and
    ≤ 4/8 with each guard deck already kept.
  - The R1 list has 8 slots and 6 distinct decks (this supports E8(b)).

  | # | Freq | Deck | Max with R1 | Max with earlier guard |
  |---:|---:|---|---:|---:|
  | 1 | 4,650 | Hog EQ: HogRider, Earthquake, Firecracker, MightyMiner, Cannon, ElectroSpirit, Log, Skeletons | 4 | – |
  | 2 | 2,398 | Goblinstein Royal Hogs: RoyalHogs, Goblinstein, BombTower, Lightning, BarbLog, Archers, ElectroSpirit, Skeletons | 3 | 2 |
  | 3 | 1,848 | AQ Royal Delivery: RoyalHogs, ArcherQueen, RoyalDelivery, Earthquake, Cannon, IceSpirit, Log, Skeletons | 4 | 4 |

  - This matches the review's predicted selection, and no picked frequency is tied.
  - Rejected above #1: frequency 11,614 (8/8, L2 Hog), 6,319 (7/8, BarbLog Royal Hogs).
  - Rejected between picks: 3,490 (R1 3/8, but 7/8 with #1), 3,145 (8/8), 2,490 (8/8).
  - If the card-support filter drops a deck, the next survivors in order are 1,357 (Log bait), 453, 341 and 315; the
    later picks would then need re-checking against the guard-overlap rule.
- **Card support (indicative only, not the binding filter).**
  - All 17 distinct cards in the three decks appear in `src/clasher/rl/contract_v5_tokens.json`.
  - Native 44874fd6 and the R3a vocabulary were not checked. That remains `select_guard_decks.py`'s job at the freeze.

## Interpretive choices (flag for the coordinator)

1. **E1.**
   - The bold now closes after "…every R1 training deck", so the review's inner bold is not nested.
   - The catalogue pin uses the full SHA, not `80de4afb…`.
   - Per the task brief, the 127x01 path and the re-run selection list were added.
2. **E4 in A.** "§7.3's tolerances" became "PREREG §7.3's tolerances", because the addendum has no §7.3.
3. **E7.** I replaced the whole sentence with the review's text, which drops ", and passed by 1.17 pp". That fact
   remains in P §2.1 item 1 ("S1 passed, by 1.17 pp"). The old bold was dropped, following the review's unbolded
   quote.
4. **E8(b).** The citations (`exit-r1/PLAN.md` l.12–14, `decks()`) were kept, in parentheses after "six distinct
   decks".
5. **E8(g).** The review's text replaces the whole r2 sentence "Styles off, since the opponent is the v1 policy.",
   since keeping "since…" would duplicate the new parenthetical.
6. **E8(a).** The new text is appended without a comma. The "(§3.2)" self-reference is verbatim.

## Deliberately not changed ("no other changes")

These are left for the coordinator at freeze:
- The r3 files still carry r2 self-labels and cross-references:
  - the P title and header ("PREREG r2", "Draft r2");
  - P §6.2, which points to `E4-V3-ADDENDUM-r2-DRAFT.md`;
  - the A header, which links `PREREG-SEARCH-TIERS-r2-DRAFT.md`;
  - P §11 steps 1 and 7, which say "r2" and "addendum r2".
- P §10 "R3a trained on all eight R1 decks including the L2 decks" is not wrong, but it is now phrased differently
  from E8(b).
- The review's §2.2 note that 4 of the 18 descriptive cells duplicate primary cells is not an E-edit, so it was not
  added.

---

## `live-loop/v4/PREREG-SEARCH-TIERS-r3-DRAFT.md` (13 hunks)

### PREREG-SEARCH-TIERS hunk 1: **E8(b)**

```diff
--- a/live-loop/v4/PREREG-SEARCH-TIERS-r2-DRAFT.md
+++ b/live-loop/v4/PREREG-SEARCH-TIERS-r3-DRAFT.md
@@ -130,7 +130,8 @@
   claim, but the effect cannot be attributed to proposal quality.
-- **Training-distribution overlap.** R3a trained on the R1 corpus: 8 own decks (the five archetype decks **and** the
-  three L2 decks; `exit-r1/PLAN.md` l.12–14, `exit_r1/emitter.py` `decks()`), all 64 matchups, against an opponent
-  mix that **includes the released v1 stochastic policy**, which is this study's opponent. The primary population is
-  in distribution for S and not for K2/K4, which have no training. That asymmetry favours S in every primary
-  contrast. The guard population removes the opponent-deck overlap but not the own-deck or opponent-policy overlap.
+- **Training-distribution overlap.** R3a trained on the R1 corpus: eight deck slots, six distinct decks
+  (`exit-r1/PLAN.md` l.12–14, `exit_r1/emitter.py` `decks()`): the archetype picks for `bridge_wincon` and `siege`
+  are the L2 Hog 2.6 and X-Bow decks, so the primary population's own and opponent decks include two L2 decks; all
+  64 matchups, against an opponent mix that **includes the released v1 stochastic policy**, which is this study's
+  opponent. The primary population is in distribution for S and not for K2/K4, which have no training. That
+  asymmetry favours S in every primary contrast. The guard population removes the opponent-deck overlap but not the own-deck or opponent-policy overlap.
```

### PREREG-SEARCH-TIERS hunk 2: **E1 (deck rule, catalogue pin, path, re-run selection) + E8(g) (last two + lines: styles)**

```diff
@@ -151,6 +152,21 @@
   - Opponent deck: the **three most frequent decks in the frozen C56 human deck catalogue
-    (`c56/engine/root-v3/human_deck_catalog.json`) that are not among the eight R1 training decks** and whose cards
-    are all supported by native 44874fd6 and by the v1/R3a vocabularies. They are selected by a hashed script,
-    `select_guard_decks.py`, committed with its output in the TIERS manifest before the freeze.
-  - Styles off, since the opponent is the v1 policy. Alternating seats.
+    (`c56/engine/root-v3/human_deck_catalog.json`) that share at most 4 of 8 cards with every R1 training deck**
+    (`exit_r1/emitter.py` `decks()`), and at most 4 of 8 cards with each previously selected guard deck, and whose
+    cards are all supported by native 44874fd6 and by the v1/R3a vocabularies. They are selected by a hashed script,
+    `select_guard_decks.py`, committed with its output in the TIERS manifest before the freeze. The catalogue is
+    pinned by SHA-256 (`80de4afb5b63c7dbdcb0ab285a715f9a93f4d6eeacffdfbe9f8c300ea7fecd8a`, 2,925 decks) in the
+    TIERS manifest. It is not git-tracked; the pinned copy is
+    `127x01:/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json`.
+  - **Selection under this rule** (re-run 2026-10-10 against the pinned catalogue, before the card-support filter;
+    no frequency ties; "R1 / guard" is the most cards shared with any R1 training deck / any earlier guard deck):
+    1. Hog EQ (frequency 4,650; R1 4/8, guard –): HogRider, Earthquake, Firecracker, MightyMiner, Cannon,
+       ElectroSpirit, Log, Skeletons;
+    2. Goblinstein Royal Hogs (2,398; R1 3/8, guard 2/8): RoyalHogs, Goblinstein, BombTower, Lightning, BarbLog,
+       Archers, ElectroSpirit, Skeletons;
+    3. ArcherQueen Royal Delivery (1,848; R1 4/8, guard 4/8): RoyalHogs, ArcherQueen, RoyalDelivery, Earthquake,
+       Cannon, IceSpirit, Log, Skeletons.
+
+    All three are `bridge_wincon`; that is acceptable and disclosed.
+  - No L2 opponent-script style (the opponent is the v1 policy); the arms' three rollout styles are unchanged.
+    Alternating seats.
   - **600 paired seeds**, stratified 3 own × 3 opponent × 2 seats = 18 cells; seed index i goes to cell i mod 18
```

### PREREG-SEARCH-TIERS hunk 3: **E8(d)**

```diff
@@ -161,3 +177,4 @@
 - **Descriptive in-distribution cells (not selection evidence):** L2-own vs L2-opponent decks (3 × 3 × 2 = 18
-  cells × 4 seeds = **72 seeds**), in distribution for S. Played last; they never enter any gate.
+  cells × 4 seeds = **72 seeds**), in distribution for S. Played last; they never enter any gate. Lost descriptive
+  blocks are not replaced and do not count toward §3.2 caps; their outcomes are sealed with the rest.
 - **Seeds (fresh; the seed audit must prove them disjoint from every frozen K/K-v2/K2/S1 (R1/R2 and the abandoned
```

### PREREG-SEARCH-TIERS hunk 4: **E5**

```diff
@@ -186,3 +203,3 @@
   - Blocks are dispatched in seed-index order within each population, interleaving the primary and guard queues
-    5:1 (the population ratio), so that host loss and drift spread over both.
+    **4:1** (2,400 : 600, the population ratio), so that host loss and drift spread over both.
```

### PREREG-SEARCH-TIERS hunk 5: **E8(a)**

```diff
@@ -209,5 +226,6 @@
 
-- **Off-host copy.** Completed blocks are copied to the hub (127x01; mirror 127x04) at least every 30 minutes. A
-  block counts only when all 8 arm-cells are complete **and** it is on the hub. A block completed on a host that is
-  lost before the copy is a lost block.
+- **Off-host copy.** Completed blocks are copied to the hub (127x01; mirror 127x04) at least every 30 minutes by a
+  copy job pinned to a non-slot core at nice 19; the general hub mirror stays paused (§3.2). A block counts only when
+  all 8 arm-cells are complete **and** it is on the hub. A block completed on a host that is lost before the copy is
+  a lost block.
 - **What is lost.** A block is lost if its host is powered off or unreachable, if foreign compute hits its slot, or
```

### PREREG-SEARCH-TIERS hunk 6: **E6**

```diff
@@ -221,4 +239,5 @@
   **2400 + 50·k + c**, which keeps its matchup and seat. The guard is analogous: **600 + 18·k + (i mod 18)**.
-  Assignment is in loss order and blind to outcomes (no outcome is opened before §11 step 8). Replacements are
-  dispatched to the remaining hosts.
+  A replacement seed is played in, and bootstrap-stratified by, the lost block's cell c, never by its own index
+  mod 18 (this matters for the guard, where 600 mod 18 = 6). Assignment is in loss order and blind to outcomes (no
+  outcome is opened before §11 step 8). Replacements are dispatched to the remaining hosts.
 - **Caps.** If more than **10%** of blocks in either population need replacement (240 primary or 60 guard), or any
```

### PREREG-SEARCH-TIERS hunk 7: **E8(e)**

```diff
@@ -226,3 +245,3 @@
 - **Lost host.** The study continues on the remaining named hosts (about 9.5 h wall on three). If fewer than two
-  named hosts remain, or a host fails §6.1's ±5% reference rule, stop and amend; no host is added after the freeze
+  named hosts remain, stop and amend; no host is added after the freeze
   without an amendment and its own qualification and reference.
```

### PREREG-SEARCH-TIERS hunk 8: **E7**

```diff
@@ -266,4 +285,4 @@
 - **Choice: n = 2,400.** It gives ≥0.93 power for K2/S V1 at the planning effects, and still 0.76 if the true
-  effect has regressed 2 pp toward the margin. **S1's own n = 600 had about 0.67 power at its own α (0.48 at this
-  study's Bonferroni α)** at its point estimate, and passed by 1.17 pp.
+  effect has regressed 2 pp toward the margin. S1's own n = 600 (σ = 0.61) had about 0.67 power at its own α (about
+  0.51 at this study's Bonferroni α) at its point estimate.
 - **K4 in the 1.0 cell.** V1 power is essentially 1. **A false NI of K2 against K4, with true +8.5 pp, has
```

### PREREG-SEARCH-TIERS hunk 9: **E4**

```diff
@@ -310,3 +329,7 @@
 - **Exactness.** Identical work is enforced by exact equality of the final action and the scores against the Linux
-  receipts (with the ARM64-NEAR-EXACT rule of §7.2).
+  receipts (with the ARM64-NEAR-EXACT rule of §7.2). For S and K0c, a corpus state whose Mac forward output (gate
+  decision or top-8 list for S; top-8 list or T=1 fallback sample for K0c) differs from Linux within §7.3's
+  tolerances is still timed but exempt from action equality. Such states are counted per tier. If they exceed 0.5%
+  of a tier's corpus, that tier fails gate 3. Any other corpus action mismatch, or a score mismatch beyond
+  ARM64-NEAR-EXACT, fails gate 3 for that tier (for all tiers if it is in the single-thread scorer).
 - **Fleet reference (no-deadline), under the reporting load profile.**
```

### PREREG-SEARCH-TIERS hunk 10: **E3**

```diff
@@ -363,3 +386,5 @@
 - The control cell is s_1 = the cell of K0c (r_K0c and K0c's gate 6). K0c need not be Mac-feasible on gates 4–5;
-  it is only the control.
+  it is only the control. K0c's cell uses gates 1–3 and 6 only. If K0c has no cell (r_K0c < 0.80, p10 < 0.70, or
+  gate 6 fails at 160 ms), s_1 = 1.0: V1 and G1 are then tested against the full-speed control, which is
+  conservative (a fortiori), and this is disclosed.
```

### PREREG-SEARCH-TIERS hunk 11: **E2**

```diff
@@ -417,4 +442,6 @@
    - If actions and candidates match 125/125 and every score differs by ≤ 1e-12 relative, the result is
-     **ARM64-NEAR-EXACT**: it passes, with disclosure. The same applies to belief floats (posterior, weights) when
-     every discrete output (cumulative order, ledger, samples, RNG state) matches exactly. Anything else fails.
+     **ARM64-NEAR-EXACT**: it passes, with disclosure. The same applies to belief floats (posterior, weights) iff
+     every discrete output (support, i.e. which hypotheses have nonzero weight; cumulative order; ledger; samples;
+     RNG state) matches exactly, and every nonzero float satisfies |mac − linux| ≤ 1e-12 · max(|mac|, |linux|).
+     The maximum relative difference is reported per history, against history length. Anything else fails.
 3. **Student cross-platform agreement** on 2,000 frozen states:
```

### PREREG-SEARCH-TIERS hunk 12: **E8(f)**

```diff
@@ -483,2 +510,4 @@
   a mix that includes v1. The guard removes only the opponent-deck overlap.
+- G2 (+10 pp, n = 600) passes a cheaper tier that is truly +5 / +7 / +10 pp worse on held-out decks with
+  probability 0.59 / 0.26 / 0.025; transfer is verified only to that resolution.
 - **F0's own Mac feasibility is unmeasured.** If A = ∅, the L2-v4 four-root configuration stays, and it is likely
```

### PREREG-SEARCH-TIERS hunk 13: **E8(c)**

```diff
@@ -502,4 +531,4 @@
    deadline mode) under load, the ±5% host rule, and the seed audit.
-4. **Freeze:** source, plan, seed audit, guard decks, speed corpora, fleet references, `measure_tiers.py` and the
-   tiers reducer. Secret-scan, commit, push.
+4. **Freeze:** source, plan, seed audit, guard decks, speed corpora, fleet references, `measure_tiers.py`, the
+   tiers reducer and the additive pointer in `exit-r3/` (C1). Secret-scan, commit, push.
 5. Smoke on the fleet (excluded range).
```

## `live-loop/v4/mac-e4-package/E4-V3-ADDENDUM-r3-DRAFT.md` (2 hunks)

### E4-V3-ADDENDUM hunk 1: **E4**

```diff
--- a/live-loop/v4/mac-e4-package/E4-V3-ADDENDUM-r2-DRAFT.md
+++ b/live-loop/v4/mac-e4-package/E4-V3-ADDENDUM-r3-DRAFT.md
@@ -82,3 +82,7 @@
 generation, root, scoring with the tier's workers, Python reduction and action selection, and for S/K0c the cached
-forward and top-8 proposals. Exactness covers the final action and scores.
+forward and top-8 proposals. Exactness covers the final action and scores. For S and K0c, a corpus state whose Mac
+forward output (gate decision or top-8 list for S; top-8 list or T=1 fallback sample for K0c) differs from Linux
+within PREREG §7.3's tolerances is still timed but exempt from action equality. Such states are counted per tier. If
+they exceed 0.5% of a tier's corpus, that tier fails gate 3. Any other corpus action mismatch, or a score mismatch
+beyond ARM64-NEAR-EXACT, fails gate 3 for that tier (for all tiers if it is in the single-thread scorer).
```

### E4-V3-ADDENDUM hunk 2: **E2**

```diff
@@ -101,4 +105,5 @@
 the result is **ARM64-NEAR-EXACT**: it passes, with disclosure. For D1b the same applies to belief floats (posterior,
-weights) when every discrete output (cumulative order, ledger, samples, RNG state) matches exactly. Anything else
-fails.
+weights) iff every discrete output (support, i.e. which hypotheses have nonzero weight; cumulative order; ledger;
+samples; RNG state) matches exactly, and every nonzero float satisfies |mac − linux| ≤ 1e-12 · max(|mac|, |linux|).
+The maximum relative difference is reported per history, against history length. Anything else fails.
```
