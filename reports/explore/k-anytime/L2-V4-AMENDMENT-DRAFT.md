# L2-v4 anytime search amendment draft

Updated 2026-10-10T01:33:49Z.

Exploration follow-up only. This document is a technical draft, not a PREREG, formal amendment, selection seal or authorization to run live. The existing L2-v4 protocol and production configuration remain untouched.

The completed K study advances **K4 and K4h** under the frozen rule that the upper paired 95% CI on loss change versus K0 must be ≤ −10 pp. Both achieve −27.17 pp; upper bounds are −22.50 and −22.83 pp. K4's CI excludes zero, so the declared kill rule does not trigger. K1 fails and provides no basis to remove the four-thread dependency. See [RESULTS.md](RESULTS.md) and the [Mac E4 v2 note](MAC-E4-V2.md).

Proposed search behavior for a later reviewed amendment:

- WAIT/WAIT10 deduplicated complete scoring, then complete timed waits, then every eligible play's balanced coarse scan, then complete top-8 refinement.
- Generic GIL release with four total scorer workers and private roots. Preserve live K=4 belief sampling; use one global four-worker pool, with candidate admission requiring all registered root/style contributions.
- Common full-decision deadline 200 ms and return reserve 8 ms, starting before observation/packet construction. Reject partial or late scores; select the best complete score by the frozen reduction and epsilon tie order.
- K4: coarse and complete scoring at horizon 160. K4h: horizon 80 coarse ranking, then all three styles recomputed at 160 for retained plays. Register the selected arm and any matrix comparison before confirmatory games; retain K4h's changed candidate-ranking semantics explicitly.
- Preserve symmetric d=27/capacity-one as the exploration reference. Live delay calibration remains the existing separate T9/E4 procedure, with an explicitly reviewed configuration; the simulation delay is not a Mac calibration.
- Declare fallback behavior and adapter provenance explicitly. K used the sealed v1 policy T=1 only when no complete score existed; fallback was 0.75%/0.72% for K4/K4h. The live runtime's WAIT fallback has not been changed by this draft.
- No student proposals, reserve floor, candidate restrictions, wait-prior changes, combat transition or v3 optimization are included in the K comparator.

Before activation: obtain the authorized Mac session, separately build/pin/qualify the Mac GIL binary, pass complete four-root exactness and injected-clock tests, pass loaded E4 timing/integration and command-acceptance gates, and obtain the independently reviewed confirmatory registration and formal L2-v4 amendment. Specify independent fresh seeds and keep heldout evaluation behind its existing authorization. K touched no heldout data and conducted no Mac/live work.
