
## 2026-10-12 16:40Z: T1 Mac route: A3-P removes all four tiers; ruling A3P-1 (no Mac-feasible tier; outcomes stay sealed for the 14-day route)

**What happened.** Under RS-4 (e11ad6f0), T1 launched driver r3 9ffbd2e1 once and passed every pin and preflight check. It then stopped as designed at the R-M3 gate with **`A3PRequiresRuling`**. It read no game file, created no output directory and invoked no reducer.

**A3-P result (`D/a3p-poll-check.json` 29f86b81; health-only, `outcomes_read=false`).** All four tiers are frozen-feasible (all six frozen gates pass), and on the frozen gate-4 variant v* (freeze) all four **fail A3-P**. The thresholds are a late rate ≤1% and a maximum ≤50 ms.

| Tier | v* late rate | v* max lateness | Default-variant late rate |
|---|---|---|---|
| K0c | 56.0% | 150.1 ms | 58.8% |
| S | 56.2% | 150.1 ms | 57.4% |
| K2 | 52.9% | 150.1 ms | 60.0% |
| K4 | 60.6% | 150.2 ms | 55.3% |

The failure is uniform, with a maximum of about 150 ms in every tier and variant, including the cheapest baseline K0c. That points to a cause in the Mac poll scheduling or harness rather than in search cost. The registration-inputs proposal (risk 5) predicted this kind of load-tail artifact.

**Ruling A3P-1 (as pre-registered; no post-hoc rescue).**
1. **Apply A3-P exactly as adopted** (Amendment 3, item 3). A3-P failure makes a tier infeasible, it is **not** a technical failure, and it grants **no repeat**. The TIERS Mac-summary route therefore concludes: **no Mac-feasible tier; no tier is selected.** This is final for this study. No A3-P-adjusted selection is run, because there is nothing to select, and there is no reducer amendment.
2. **Outcomes stay sealed.** The Mac route cannot release fleet outcomes without a selection, and opening them now would need a new, unreviewed release path. Fleet results will be released **descriptively** by the pre-registered **14-day route**, no earlier than **2026-10-25T19:31:38Z**. That route uses approved driver r2 42219e57 with canonical HEAD at 9bb349b1 and an empty descendant diff. A separate coordinator ruling at that time will switch canonical R back to 9bb349b1. The private Mac descendant 2473c0a9 and its ref are retained, never pushed, and are not used by the 14-day route.
3. **T1 now:**
   - record this ruling and its own receipts;
   - leave `release-private/` (empty, 0700) and all private state in place;
   - **disable its 20-minute END timer.** The coordinator will wake T1 for the 14-day route.
   - The T1 originals on 01/08 stay preserved, read-only and never deleted.
4. **Hosts 01/08:** the release-sequence compute freeze lifts. The hosts may take other approved work, provided T1 original paths stay untouched. The hub mirror stays paused until the coordinator retargets it.
5. **Engineering follow-up (outcome-blind, not a TIERS repeat).** Diagnose the about-150 ms all-cause poll lateness from the sealed Mac timing receipts. This blocks any Mac live play at any tier, and the fix belongs to a future, separately pre-registered Mac study.
