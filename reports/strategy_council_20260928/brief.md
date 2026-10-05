# Clasher architecture and training council

## Latest user clarification, after Round1

Sam has a compute grant for this project. Reasonable compute is available; the Mac mini's disk space and single chip are not strategy restrictions. His instruction is to let Astra and Fable come up with the strategy, without coordinator micromanagement of budgets. This supersedes the local-only compute assumptions below and in the independent Round1 proposals. The coordinator has relayed the clarification and each model's complete proposal to the other for Round2.

Sam also clarified that Max is intentional: prioritize deep consideration of alternatives, assumptions, and tradeoffs over latency or token cost. Keep both models at Max. Concise cross-review requests are intended to avoid repeating settled material, not to limit reasoning depth or hurry agreement.

Sam requested two new persistent T3 threads, Astra and Fable at Max reasoning, to brainstorm model architectures and training strategies. The coordinator must relay each round to the other model until both explicitly agree on a concrete strategy, then implement it. Agreement must be substantive; identify genuine disagreements and resolve empirical uncertainty with bounded experiments rather than pretending certainty.

## User objective and latest direction

Build a strong human-level Clash Royale bot. First demonstrate useful adaptive playing competence. Players tolerate balance changes and mixed card levels; exact interaction breakpoints and identical replay trajectories must not indefinitely delay a first useful model. A different tower outcome under fixed replay commands does not itself establish harmful learned strategy. Prioritize systematic decision errors and repeatable simulation-only exploits under reacting play. Train/evaluate across varied decks and card interactions, including professional-style and procedural decks, even if initial deployment specializes to Hog2.6.

The requested discussion should seriously compare architectures and training strategies, not merely endorse the existing design. Consider representation, recurrent memory/belief, action timing/placement, supervision, RL/opponents, adaptation across levels/dynamics, transfer, evaluation, and practical throughput. No current evidence proves human-level playing strength.

## Current evidence and constraints

- Work only in `/Users/sam/Desktop/code/clasher`, consolidated main at base `95feeb0e525ee1665360df6e28116b01c3436ecf`. The coordinator's uncommitted repairs and docs must be preserved. Former worktree paths are compatibility symlinks, not separate checkouts.
- Start by reading `AGENTS.md`, `AGENTS.local.md` if present, `docs/history/HANDOFF_NEW_THREAD_20260928.md`, `docs/design/PIPELINE_DESIGN.md`, and `reports/v7_recovery_20260928/README.md`. Relevant source, data audits and logs are available locally. Source is the authority for capabilities; old reports may overstate what is currently wired.
- Simulator reference is pinned Null's15.535.86, not established official-client equivalence. V7's original frozen attempt failed after12 complete configurations and a scalar failure on13;115 never started. Its criteria, ledger exposures and failure must remain intact.
- The shared boundary bug is now repaired: movement used a spawn inset, altering troop pressure and an extra Giant hit. Scalar and tensor movement bounds now reflect native movement; spawn margins remain. Also repaired consolidation ledger path checks and two stale tensor mass calls.
- 1,644 broad simulator/public-contract tests passed. 91 focused tensor/spawn/impulse tests passed,15 skipped. New regressions fail under source-only counterfactual restoration. Tensor evidence covers CPU movement phases, not full resident-engine/CUDA parity.
- All13 opened v7 captures now complete64 scalar reacting branches with no bad decision families or clear regressions under the original criteria. This is opened development evidence, not fresh acceptance or demonstrated policy strength.
- Existing recurrent/structured models, inference and PPO/replay/training code are substantial but need selective inspection. Do not assume historical checkpoints, teacher pipelines, public contracts or accelerated runtimes are suitable without checking their interfaces.
- Expert-data warning in `docs/design/PIPELINE_DESIGN.md`: the audited first5,000 IL_Replay matches have almost no entirely base-card sides, no match with two base-only Level11 sides, unknown active forms on placements, and unattributed ability events. Do not silently relabel modern forms as base-card ground truth. Investigate what supervision can safely be salvaged or acquired and what fallback is practical.
- Public-state calibration and counterfactual-ranking gates precede policy training/search in the existing project instructions. Explain how to establish a practical, prospective readiness gate consistent with Sam's latest tolerance for small dynamics differences. Do not retroactively turn opened v7 into acceptance or quietly waive recorded gates.
- No paid cloud compute has been allocated. Local Mac mini audits and bounded experiments are available; measure hardware/throughput before proposing budgets. Disk was approximately11GiB free at the last check; recheck before meaningful output. Reference emulator and old training scheduler are off. No automatic restart or bulk collection during this discussion.

## Round1 deliverable

Independently inspect enough relevant source and data to propose an executable strategy. Compare at least three materially different architecture/training combinations. Choose a recommendation and explain why it is the most useful next empirical step rather than simply the theoretically strongest system. Clearly distinguish verified facts, hypotheses and open decisions.

Specify actor information boundary, representation/memory, actions and timing, level/dynamics handling, data and initialization, opponent curriculum, learning algorithm, evaluation and stage gates, first bounded local milestone, decision criteria for continuing or pivoting, and subsequent compute requirements. Name exact reusable modules and missing interfaces. Avoid a sprawling option list or a plan whose first result requires a large infrastructure rewrite. Human-level play remains the goal, not a claim.

Write your full proposal to your assigned `round1.md` file, preferably no more than2,500 words. Final chat response should briefly summarize the recommendation, principal uncertainty and exact output path. The coordinator will relay the other model's full file in round2. Do not claim consensus in round1.

During council rounds, read source freely and write only your assigned council files. Do not edit production/tests, launch training/native collection, modify frozen evidence/registries, commit/push, or create more threads. Ask the coordinator through your response if a genuinely required input is missing; proceed with independent useful analysis meanwhile.
