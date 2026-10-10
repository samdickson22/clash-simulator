# PREREG-SEARCH-TIERS Amendment 1 (operational): signed by coordinator 0523ae6f, 2026-10-10T14:46:46Z

Binds frozen PREREG ([freeze record](PREREG-SEARCH-TIERS-FREEZE-20261010.json), SHA 47aba25e…) and E4-v3 fleet review r2 (`mac-e4-package/e4v3/REVIEW-E4V3-FLEET-R2-20261010T1444Z.md`, commit efa54f44). No hypothesis, arm, seed, contrast, alpha or selection-rule change.

**A1.1 END placement of the fleet reference.** The loaded fleet-reference measurement runs after T1 reporting completes.
- **END marker:** T1's committed completion receipt.
- **Pooled-reference exclusions:** if the ±5% pooling would exclude a host whose games are counted, the pool **fails closed**. The reference must then be re-run until it conforms, or the Mac speed ratio is declared unavailable under the PREREG's fallback.
- **No outcome release**, including the 14-day escape, before the pooled reference is committed.

**A1.2 MHz gate.** Compare only full-occupancy reporting rows against the reference. Disclose the signed ratio. One repeat is allowed on failure.

**A1.3 Committed-posterior deadline replay** (already disclosed). Rows carry the committed posterior copy, with `_pending=None` and a suspended-transaction flag. Fleet and Mac both replay the full public-history update with no suspended-progress credit.

**Preconditions before any reference run:**
- the pool's host list equals the reporting host set, with a fixed reference slot per host;
- the reference stops on foreign compute and on console users, with the same guard as reporting, including OP-1;
- fleet exactness is bit-exact (the Mac near-exact E2 allowance does not apply on the fleet);
- one real end-to-end fleet-mode smoke run passes;
- failures are classified by a mechanical rule committed beforehand.
