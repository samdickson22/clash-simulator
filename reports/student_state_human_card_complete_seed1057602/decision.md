# Human card-complete supervision decision

## Data split

The accepted diagnostic split is
`datasets/derived/tv_royale_public_v2_card_complete_split_seed1057602`.
Replay IDs and complete deck signatures are disjoint across train, validation,
and chronology. Training contains all 66 enabled cards in 13,950 samples from
561 replays. Validation contains 65/66 cards; Dark Prince cannot appear in both
signature-disjoint partitions because the source corpus contains it in only one
replay/deck signature. Public-state sidecars are row-aligned and include
value-plus-confidence HP estimates; confident visible-HP coverage is about 56%.

## Direct human correction

The accepted parent (`student_state_symmetry_dagger_seed1056901/iteration2.pt`)
scored 37.3089% conditional card-slot accuracy on validation. A one-epoch,
placement-only, query-only correction (learning rate 1e-5, anchor KL 20) fell to
36.9419%, with 11 corrected and 17 regressed action types. Conservative blends
did not rescue it: alpha 0.125 improved one validation sample with no regression,
then regressed two chronology samples and fixed none. All direct human
card-choice corrections are rejected before gameplay.

This does not mean HP cannot be extracted. It means that direct behavioral
cloning from reconstructed public video state remains mismatched with the exact
simulator state used by the policy, and the mismatch is large enough that more
epochs are unsafe.

## Decision

Keep the human corpus for representation, belief/value auxiliary targets, and
held-out diagnostics. Do not use it as an unrestricted direct policy target.
Outcome-grounded simulator RL remains responsible for play timing and final
card choice.

