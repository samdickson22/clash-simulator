# Conformance check: PREREG search tiers r2 (90c443aa) against C1–C14

Reviewer: Opus (the round-1 independent reviewer; no part in K/K-v2/K2/S1/R3/X), 2026-10-10, for coordinator
`0523ae6f`. Scope: `live-loop/v4/PREREG-SEARCH-TIERS-r2-DRAFT.md` (**P**), `mac-e4-package/E4-V3-ADDENDUM-r2-DRAFT.md`
(**A**), `DECISION-MAC-TIERS-20261010-r2.md` (**M**), `live-loop/v4/C1-C14-RESPONSE.md` (**R**), checked against
`REVIEW-PREREG-SEARCH-TIERS-20261010.md`. I only read files and ran read-only arithmetic. To check the guard rule I
copied the C56 deck catalogue from 127x01 to `/tmp/sdicks02/review-cat/`. Nothing was committed or launched. Paths
are relative to `reports/`.

## Verdict: **CONFORMS_WITH_EDITS**

All of C1–C14 are applied, and nearly all of them verbatim. C15 and C17 are adopted, and C16 and C18 are handled
correctly. R's line references are accurate to within two lines. The corrected NI and false-NI figures and both power
tables reproduce exactly.

Eight edits (E1–E8) are needed before the freeze. All are exact and local, and none needs another full review: the
coordinator can check the diff against this list.
- **E1 is substantive.** As written, the guard rule would select a one-card variant of a training deck. C2 was my
  wording, so the error is mine.
- **E2–E4** close gaps that the r2 additions exposed or left open.
- **E5–E8** are corrections, one of them to my own C13 power wording.

### Summary (under 150 words)

- C1–C14 conform. Line references are verified (six are off by 1–2 lines, which is cosmetic).
- **E1 (guard decks):** "not among the eight R1 decks" means exact-set exclusion, which would pick Royal Hogs with
  BarbLog, a 7/8 match to the L2 own deck. A card-overlap rule is needed, and the catalogue must be SHA-pinned
  because it is not git-tracked.
- **E2 (arm64 near-exact):** this is not a loophole in substance, but it lacks an explicit tolerance and a rule that
  zero weights stay zero.
- **E3:** s_1 is undefined if K0c has no Mac cell, a case the r_S/r_K0c split makes reachable.
- **E4:** Torch tiers can't meet "exact final action" on the corpus.
- **E5–E8:** the interleave ratio should be 4:1, not 5:1; guard replacements must keep their cell; the S1 power
  pair mixes σ; and there are three wording fixes.
- C16 and C18 are handled correctly, and the four added notes are sound.

---

## 1. Condition-by-condition (C1–C14)

| C | Applied? | Evidence (verified) | Notes |
|---|---|---|---|
| C1 | **Yes, verbatim** | P 89–95 matches the review's paragraph word for word. Also: post-hoc label P 105; disclosures P 121–135; verifier ≠ reducer P 139–140; reviewer independence P 141, P 6–7; §9 D1 P 459–460; memo M 26–31. "S1-student" appears nowhere (grep). | The "additive pointer in `exit-r3/`" has no run-order step (E8c). The disclosure's "8 own decks" is really 6 distinct decks (E8b). |
| C2 | **Yes, but the deck rule is defective** | "Never trained on" is deleted, and P 113–114 states the overlap. Guard spec P 148–160; G1/G2 P 49–50, P 368, P 374–376; power P 274–276 (all reproduce: G1 1.00/0.88/0.49, G2 0.99/0.86/0.59). Descriptive cells P 161–162. | **E1:** the C2 selection rule as written admits near-copies of training decks. |
| C3 | **Yes, verbatim** | Rule P 371–373; "monotone" replaced P 388–390 (gone from all files); full precision P 291–292, A 108 (R cites A 106); NI 97.5% P 51, P 283–284; rationale P 57–58. | — |
| C4 | **Yes** | Work unit P 304–312, A 81–83; r_T = min of 3 P 330–331, A 110–111; p10 ≥ 0.70 P 342; gate 6 P 320–323, P 353–356, P 361–363, A 94, A 112–114; own-tier corpora P 301–303. | The review's C4 said "own excluded smoke games" and its C13 said "corpus-range"; r2 reconciles the two correctly with a dedicated corpus range on which each tier plays its own games. **E4:** corpus exactness for the Torch tiers. |
| C5 | **Yes** | P 313–319: load profile, every host, ±5%, pooled per-state median, 1 Hz MHz. | — |
| C6 | **Yes, plus one extension** | Belief/RNG P 411–413, A 89; D1 bracket verbatim A 88, P 415–416; near-exact for scores verbatim P 417–418, A 100–101; D2 swap rule A 90, P 423–424. | Belief-float extension: §2.3 and **E2**. |
| C7 | **Yes** | B.1 → §D7 A 52; psutil A 56–57; D5 aggregation A 93, A 109; opportunity and gate 4 P 346–351, A 115–118; D8 A 97; `gc.freeze()` A 119–120; `ps` only A 66–68; lock + census A 34–40; mechanical §F A 156–158, P 385–387. | The census uses "averaged over the 5 min", which is a reasonable reading of C7. |
| C8 | **Yes, verbatim** | P 379–382, A 172–175; also P 22–23, P 490–492, P 512–513, M 65–67. | — |
| C9 | **Yes, verbatim** | P 446–449; memo M 93–94. | — |
| C10 | **Yes** | (a) P 395–396, A 53–55, P 503–504. (b) verbatim P 397–399. (c) ranges P 170, P 172 (R cites 168/170); formula P 220–221. (d) P 224–225. (e) P 210–212. | **E6:** the guard replacement index does not map to its cell under i mod 18. |
| C11 | **Yes** | 8 deltas, diff review, batteries on every host, pins P 189–206; hosts P 182–185; stop files P 218–219; console rules P 183–185, P 216–217. | E8a: the 30-minute copy versus the paused hub mirror. |
| C12 | **Yes** | P 480–489; also P 131–135, P 370, P 464–465; M 30–32, M 63–64, M 90–92; A 179. | — |
| C13 | **Yes as worded, but my wording was wrong** | Cost P 35–38, M 74–76 (my recomputation: 7.0 h on 44 slots, 9.2–9.5 h on 33, 15.3 h on 20 slots; 1,525 → ≈1,560 with the 72 descriptive blocks). Power P 267–268; corpus-range P 301–302; memo M 21–22, M 58–60. | **E7:** the "0.67 / 0.48" pair mixes σ = 0.61 and σ = 0.63. |
| C14 | **Yes** | P 29–31; M 61–64. | — |

**R's line references** were all checked. Six are off by 1–2 lines:
- A 106 → A 108;
- P 168/170 → P 170/172;
- P 418–420 → P 417–419;
- M 31–32 → M 30–31;
- P 401–402 → P 400–401;
- P 117–118 → P 116–117.

All are cosmetic, and R is not a frozen artefact.

## 2. The four added notes

### 2.1 Separate r_S and r_K0c (P 333–334): sound, with one gap that it exposes

Splitting is strictly safer than one shared r_1. A slow student can no longer push the control into the collapsed
0.8 cell, where V1 becomes trivial. If S is slower than K0c, S plays at 160 ms against K0c at 200 ms, which is
harder for S.

**The gap.** §6.4 defines s_1 as "the cell of K0c", but gives K0c no cell if r_K0c < 0.80, its p10 < 0.70, or it
fails gate 6 at 160 ms. Under the old shared r_1, S died in the same event, though s_1 was still undefined for K2
and K4. With the split, S can now be feasible while the control has no cell, which leaves V1 and G1 undefined for
every tier. → **E3.**

### 2.2 The 72 descriptive L2-vs-L2 seeds: sound

- They are used in no gate.
- The range is listed for the seed audit (P 175), and they are played last.
- Cost: 72 blocks of 366 s on 44 slots is about 10 min of wall time, as stated.

Two small gaps:
- **Replacement and caps.** The text doesn't say that their lost blocks aren't replaced and don't count toward the
  §3.2 caps. → E8d.
- **Overlap with the primary population.** Two of the primary population's five "archetype" decks are the
  L2 Hog 2.6 and X-Bow decks (see E8b), so 4 of the 18 descriptive cells duplicate primary cells. That is harmless,
  but it should be disclosed.

### 2.3 arm64 "near-exact" rule extended to belief floats: not a loophole, but underspecified

**Why it is not a loophole:**
- The search consumes the belief only through its discrete outputs: the sampled root, the cumulative order, the
  ledger and the RNG state. The rule requires all of those to match exactly on 125 × 2 histories.
- The floats (posterior, weights) can change a sample only when a uniform draw lands within a few ulp of a
  cumulative boundary, which has probability about 1e-15 per draw.
- §6.1 separately requires end-to-end action and score equality on the 1,200 corpus decisions, which already
  include belief preparation.
- The review's own C6 rationale was that macOS libm differs from glibc in the last ulp. The posterior uses
  exp/log, which is exactly where that shows up. So strict float equality would kill every tier for a reason that
  doesn't change any decision. The extension carries out C6's intent rather than weakening it.

**What it lacks:**
- **(i) No numeric tolerance.** "The same applies" leaves it open whether 1e-12 relative applies to the belief
  floats.
- **(ii) No metric is defined.** Relative error is undefined at 0, and nothing stops a weight that is 0 on Linux
  from being a denormal on the Mac. Support (which hypotheses have nonzero weight) is really a discrete output and
  must be exact.
- **(iii) No growth check.** The posterior is updated sequentially, so drift could grow with history length.

→ **E2.** With E2, the rule is narrower than the score rule the review itself pre-registered.

### 2.4 Extra stop rules (bank row exhausted; fewer than two hosts): sound, with one wording conflict

- **Bank-row arithmetic is correct.**
  - Primary: 2400 + 50·8 + 49 = 2849 < 2880, so k ≤ 8 is safe for every cell. k = 9 exists only for c < 30, so
    "k > 8" stops conservatively.
  - Guard: 600 + 18·5 + 17 = 707 < 720, so "k > 5" is correct.
- **The two-host floor** adds a stop. It does not remove one.
- **The conflict.** "or a host fails §6.1's ±5% reference rule, stop and amend" (P 227) contradicts §6.1 (P 317–318),
  where a host failing ±5% is *excluded before the freeze*, not a stop. The reference is never re-measured during
  reporting, so the clause can only fire pre-freeze. → E8e.

## 3. C16 not adopted; C18 deferred

- **C16: acceptable.** It was a recommendation. G2 stays at +10 pp exactly as C2 specified. The cost figure
  (≈ 600 blocks ≈ 305 reserved core-h) is correct.
- **What +10 pp at n = 600 means.** The guard reliably blocks only large cheaper-tier degradations. A cheaper tier
  that is truly +7 pp worse on held-out decks still passes G2 with probability 0.26 (0.59 at +5, 0.025 at +10).
  Add that one sentence to §10 (E8f) so a selection is not later read as "transfer-verified to 5 pp".
- **C18: correctly handled** (P 116–117). It is a separate exploration item, as recommended. Calling it
  "deferred" is accurate.
- **C15:** C10(b) already enforces the ordering; preferring "before step 6 ends" is fine.
- **C17:** adopted (P 84–85, delta 7).

## 4. The corrected power statements

| Statement | r2 | Recomputed | Status |
|---|---|---|---|
| False NI of K2 vs K4 at 97.5%, true +8.5, σ 0.56 | ≈ 6×10⁻⁸ | Φ(−5.303) = 5.7×10⁻⁸ | ✓ |
| Same, σ 0.48 | ≈ 3×10⁻⁹ | Φ(−5.813) = 3.1×10⁻⁹ | ✓ |
| r1 figure at 95% | 1.6×10⁻⁸ / 2.6×10⁻⁷ | 1.6×10⁻⁸ / 2.6×10⁻⁷ | ✓ |
| NI table, 97.5% (n = 1,800 and 2,400) | .99/.94/.79/.51/.23; 1.00/.98/.90/.65/.31 | identical | ✓ |
| V1 table (n = 600–3,000) | as P 254–257 | identical | ✓ |
| **S1's own power** | "0.67 at its own α (0.48 at the Bonferroni α)" | σ 0.61: **0.673 / 0.506**; σ 0.63: 0.645 / 0.476 | **✗: the pair mixes σ (my C13 error)** → E7 |

## 5. Required edits before the freeze (exact wording)

**E1: guard decks must actually be held out (P 151–154; M 40).**

The catalogue (SHA-256 `80de4afb5b63c7dbdcb0ab285a715f9a93f4d6eeacffdfbe9f8c300ea7fecd8a`, 2,925 decks) is present
on 127x01 but not git-tracked. Running `emitter.decks()` against it and excluding exact matches gives the top
three, before the card-support filter:

| Freq | Deck | Max cards shared with an R1 deck |
|---:|---|---:|
| 6,319 | Royal Hogs with **BarbLog** | **7/8** (the L2 Royal Hogs own deck, Log → BarbLog) |
| 4,650 | Hog EQ / Firecracker / Mighty Miner | 4/8 |
| 3,490 | the same deck with BarbLog | 3/8, but **7/8 with the previous guard deck** |

Exact-set exclusion therefore puts a near-mirror of a training deck into the guard, plus two near-identical
opponent decks. Replace "that are not among the eight R1 training decks" with:

> "that share **at most 4 of 8 cards** with every R1 training deck (`exit_r1/emitter.py` `decks()`), and at most 4
> of 8 cards with each previously selected guard deck."

Add to the TIERS-manifest sentence:

> "The catalogue is pinned by SHA-256 (`80de4afb…`) in the TIERS manifest."

Under this rule, with no deck lost to the card-support filter, the selection would be Hog EQ, Goblinstein Royal
Hogs and ArcherQueen Royal Delivery. All three are `bridge_wincon`; that is acceptable and disclosed. In M 40,
"three common human decks the student never trained against" is then accurate.

**E2: near-exact belief floats (P 418–419; A 101–103).** Replace "The same applies to belief floats (posterior,
weights) when every discrete output (cumulative order, ledger, samples, RNG state) matches exactly." with:

> "The same applies to belief floats (posterior, weights) iff every discrete output (support, i.e. which hypotheses
> have nonzero weight; cumulative order; ledger; samples; RNG state) matches exactly, and every nonzero float
> satisfies |mac − linux| ≤ 1e-12 · max(|mac|, |linux|). The maximum relative difference is reported per history,
> against history length."

**E3: control cell when K0c has no Mac cell (P 363–364).** Append:

> "K0c's cell uses gates 1–3 and 6 only. If K0c has no cell (r_K0c < 0.80, p10 < 0.70, or gate 6 fails at 160 ms),
> s_1 = 1.0: V1 and G1 are then tested against the full-speed control, which is conservative (a fortiori), and this
> is disclosed."

**E4: corpus exactness for the Torch tiers (P 310–311; A 83).** After "…against the Linux receipts", add:

> "For S and K0c, a corpus state whose Mac forward output (gate decision or top-8 list for S; top-8 list or T=1
> fallback sample for K0c) differs from Linux within §7.3's tolerances is still timed but exempt from action
> equality. Such states are counted per tier. If they exceed 0.5% of a tier's corpus, that tier fails gate 3. Any
> other corpus action mismatch, or a score mismatch beyond ARM64-NEAR-EXACT, fails gate 3 for that tier (for all
> tiers if it is in the single-thread scorer)."

Why this is needed: Torch on arm64 (CPU or MPS) is not bit-identical to the fleet, and D2 itself allows 0.5%
disagreement. As written, the corpus check either fails S and K0c for a reason that doesn't matter or is silently
waived. The v1 forward used by K0c also has no cross-platform check anywhere.

**E5: interleave ratio (P 186–187).** "interleaving the primary and guard queues 5:1 (the population ratio)" →
"**4:1** (2,400 : 600, the population ratio)".

**E6: guard replacement cell (P 221).** Since 600 mod 18 = 6, the index 600 + 18·k + c does **not** fall in cell c
under "i mod 18". Append:

> "A replacement seed is played in, and bootstrap-stratified by, the lost block's cell c, never by its own index
> mod 18 (this matters for the guard, where 600 mod 18 = 6)."

**E7: S1 power (P 267–268).** Replace with:

> "S1's own n = 600 (σ = 0.61) had about 0.67 power at its own α (about 0.51 at this study's Bonferroni α) at its
> point estimate."

This corrects my own C13 wording.

**E8: wording.**
- (a) **P 210:** after "at least every 30 minutes", add "by a copy job pinned to a non-slot core at nice 19; the
  general hub mirror stays paused (§3.2)".
- (b) **P 131–132:** "8 own decks (the five archetype decks **and** the three L2 decks…)" → "eight deck slots, six
  distinct decks: the archetype picks for `bridge_wincon` and `siege` are the L2 Hog 2.6 and X-Bow decks, so the
  primary population's own and opponent decks include two L2 decks".
- (c) **§11 step 4:** add "the additive pointer in `exit-r3/` (C1)".
- (d) **P 162:** add "Lost descriptive blocks are not replaced and do not count toward §3.2 caps; their outcomes are
  sealed with the rest."
- (e) **P 227:** delete "or a host fails §6.1's ±5% reference rule"; a failing host is excluded before the freeze
  (§6.1).
- (f) **§10, new bullet:** "G2 (+10 pp, n = 600) passes a cheaper tier that is truly +5 / +7 / +10 pp worse on
  held-out decks with probability 0.59 / 0.26 / 0.025; transfer is verified only to that resolution."
- (g) **P 155:** "Styles off" → "No L2 opponent-script style (the opponent is the v1 policy); the arms' three
  rollout styles are unchanged."

Once E1–E8 are in, r2 conforms and is ready to freeze. The coordinator can check the diff against this list; no
further independent round is required.
