## Verification limits and supplemental prefix checks

The frozen receipts retain initial decks and seeds, actions, per-root candidate
counts and deadline completed/truncated flags. They do **not** retain original
full candidate-list hashes or an initial-state hash. Direct equality to those
unrecorded originals cannot be asserted. The coordinator explicitly accepted
this limitation and the checks below at actual ~01:18Z on 2026-10-09, with no
score adjustment, new gate games or change to the decision rule.

The fixed checks use the first primary world in both seats and the first
secondary world at B0/A0. Each stops before the first originally truncated root
(or at the terminal boundary when none was truncated). Two independent
replays passed, with exact original non-truncated actions and retained B
candidate counts. Each replay checked 1,434 decisions, 111 candidate lists and
six B candidate-count roots. Reconstructed full candidate-list hashes and
initial **public-state** hashes agree between the two replays. This establishes
replay consistency; it cannot establish equality to unlogged original hashes.
The complete gate-wide per-B-root count assertions are reported above.

| Fixed prefix | Stop (tick, seat) | Decisions per replay | Candidate lists per replay |
| --- | --- | --- | --- |
| pair-000-B-0.json | [120, 0] | 12 | 5 |
| pair-000-B-1.json | [120, 0] | 12 | 5 |
| pair-320-B-0.json | [100, 0] | 4 | 1 |
| pair-320-A-0.json | [3601, 0] | 1406 | 100 |

The initial helper attempt failed because native search rejects an infinite
deadline. Its source and failed wrapper receipt were preserved. The corrected
verification-only helper used a finite one-hour budget for roots that had
originally completed; frozen serving and analysis bytes were unchanged.

Receipts: `imitation/gates-bc/receipts/gate-b-completion-v1/spot-replay.json`,
`spot-summary.json`, `spot-helper-repair.json`. Future registrations should
record a full candidate-list hash per root and an initial-state hash per game.

Inference is conditional on the registered deck schedule (320 primary and
128 secondary eval-role worlds; zero eval_ood worlds; 42 distinct primary own
deck identities). No deck-population, eval_ood or mask-v2 generalization is
claimed. The primary design's approximate 80% MDE was +4.3 to +5.5 percentage
points under its stated decisive-fraction assumptions; a failed gate does not
exclude a smaller improvement. The secondary point bar is not a statistical
non-inferiority claim. No completed game, late decision or rejected command
was removed or adjusted.
