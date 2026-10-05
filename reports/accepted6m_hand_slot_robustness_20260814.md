# Accepted-6M hand-slot robustness closure (2026-08-14)

## Decision

Reject both the post-hoc slot-invariance retrofit lineage and the current-corpus
fresh hard-invariant lineage. Keep the equivariant architecture and exact audit
machinery as diagnostic infrastructure, but do not spend more offline epochs or
augmentation sweeps on these formulations: the fresh conditional-slot-only
model achieved exact symmetry and the strongest chronology fit yet scored
0--72 in complete games. None of the checkpoints in this report is promoted
over the accepted parent. The next bounded causal test is on-policy
mechanics-query PFSP from the behavior-preserving accepted parent, with timing
and placement frozen and the final public human partitions held out for
no-regression evidence.

## Accepted parent and causal defect

The accepted parent is
`checkpoints/mechanics_slot_probe/accepted6m_zero_seed1056701/zero_adapter.pt`
(SHA-256
`cf783bdef5c3ce0b529606839b3887a3e3457045394642ad72466cc3087cc305`).
It has 6,194,196 parameters and scored 51--21 with +78 crowns on the matched
72-game random/strategy/Hog screen. Its workload records were random 10--2,
balanced 6--6, reactive-defense 5--7, bridge-pressure 5--1, slow-push 6--0,
spell-control 5--1, split-lane 4--2, and Hog 10--2.

That outcome concealed a large physical-slot dependency. In the real Hog
games, legal-affordable Hog conversion was 0/23 in slot 0, 18/20 in slot 1,
4/4 in slot 2, and 32/32 in slot 3. An all-24-permutation counterfactual audit
preserved card plus tile on only 51.07% of decisions. Hog selection changed
from 34.60% when moved to destination slot 0 to 75.32%, 86.92%, and 84.18% in
slots 1, 2, and 3. The evidence is bound in
`reports/accepted6m_zero_mechanics_rl_initializer_seed1056701/hand_slot_robustness_hog12.json`.

## Structural intervention

The actor can now represent current-hand slots as an unordered set and score
each card with a shared semantic/mechanics query. The next-card token remains
distinct. Tests prove that permuting the four current-hand cards exactly
permutes card probabilities and card-conditioned placement logits while
preserving aggregate play probability. Legacy checkpoint behavior remains the
default when the feature flags are disabled.

The all-24-permutation distillation target contains 53,384 recurrent states,
35,893 informative states, and SHA-256
`9afd46edc5953b9250e5c3f8fc32b9cdba7e444fc8a265bd4370a283915db019`.
The accepted teacher's original card choice agrees with its symmetrized target
on only 59.30% of states (KL 2.39213; target entropy 0.83807). This independently
confirms that physical slot identity is deeply entangled with the teacher's
card policy.

Hard-label mechanics-only and semantic-plus-mechanics training did not pass
gameplay. The best permutation-distilled checkpoint selected by held-out top-1
agreement is
`checkpoints/equivariant_slot_choice/accepted6m_distilled_top1_seed1056804/distilled_epoch5.pt`
(SHA-256
`67898aed13aacba67a1c207ed5a29bedea966ba386cd3031bdd9bff3d3827be4`).
It reached 75.69% held-out top-1 agreement and exact 100% card-and-tile
permutation preservation. Hog selection was 82.43% in every destination slot,
with equal mean conditional probability.

## Gameplay rejection

Exact symmetry did not preserve skill. The top-1 student scored 41--31 with
only +9 crowns on the same broad 72-game screen, versus 51--21 and +78 for the
parent. Workloads were random 7--5, balanced 6--6, reactive-defense 4--8,
bridge-pressure 3--3, slow-push 3--3, spell-control 4--2, split-lane 4--2, and
Hog 10--2. Its playable-state no-op rate fell toward immediate play (0.18% on
the random workload versus 70.24% for the parent), exposing a timing/card-mass
coupling rather than a safe card-choice-only substitution.

Two timing repairs were tested and rejected:

- an invariant max-pool timing rule retained exact symmetry but produced only
  8.33% Hog selection in every destination and scored 4--7--1 on the Hog gate;
- a learned 1,155-parameter invariant timing query distilled from all 24
  permutations retained exact symmetry, but scored 1--11 on the Hog gate. Its
  source timing targets covered 53,384 states; the teacher agreed with the
  symmetrized timing decision on 92.73% (KL 0.23497), while the student reached
  84.96% held-out top-1 agreement and KL 0.17749.

The relevant checkpoint SHA-256 values are
`6ff43161be0d80cd6d1a5b76a4a51380fe8f039b814bd9fc603fc997fccad837`
for the max-pool arm and
`314eef4a75281ae8f546750adbe240360eb76e6c6b6647d3d0873d7f5ace7a3a`
for the learned-timing arm.

## Interpretation and next experiment

The structural scorer is behaving as designed; the failure is distributional.
Once its first altered action changes the recurrent trajectory, later states
are off-policy relative to the fixed teacher/corpus targets. The accepted
policy also encoded useful behavior through the same slot-biased representation
being removed, so post-hoc symmetrization cannot preserve that behavior by
snapshot agreement alone.

The next causal experiment is therefore a matched clean pretraining run in
which slot-invariant card choice exists from initialization. The first bounded
A/B uses `datasets/human_safety_balanced_v1.npz` (420,672 frames, SHA-256
`d26c657343002ed74c084a4cdf69d97c87d358bd15069b94aad7f1f8be72a660`):
210,672 frames from 190 validated human replays plus 210,000 exact safety
decisions. The live 1,000-game public corpus remains an untouched broader
human-data/no-regression source until its integrity, post-260 split, and visual
audit are complete. A fresh structural policy must pass exact slot symmetry,
Hog/card-utilization, broad strategy, defense, passivity, chronology, and
whole-archetype held-out gates before diversified PFSP RL.

## Fresh structural A/B result

The matched one-epoch fresh experiment used seed and split seed `1011001`, a
192-wide attention encoder/decoder, five actor and three critic layers, a
384-unit LSTM, 32-step recurrent chunks, spatial-v1 supervision, and identical
optimization settings for the structural and legacy arms. The structural
checkpoint is
`checkpoints/human_safety_structural_fresh_seed1011001/epoch1.pt` (SHA-256
`7b4816f442cd47eb94c0e353f3fbcfcba205cb37c976d14efed2c1b2c3636462`);
the matched legacy checkpoint is
`checkpoints/human_safety_legacy_fresh_seed1011001/epoch1.pt` (SHA-256
`304308de1e0b221193ae148102f7c54aa093adb2992fa0864b9a35c64411fd74`).

The legacy arm fit the episode-random validation split better: 74.36% exact
action and 88.11% action-type accuracy, versus 71.94% and 81.81% for the
structural arm. On the independent later-arena chronology, however, the
ranking reversed. Structural exact-action accuracy was 14.05% versus 0.10%
for legacy, action-type accuracy was 29.77% versus 18.55%, and joint NLL was
7.148 versus 10.424. This is strong evidence that the invariant structure
removes an episode-split shortcut.

The structural checkpoint also passed the exact all-24 hand permutation audit:
card identity and card-plus-tile preservation were both 100% over 59,280
permutations, with maximum slot-logit equivariance error `7.16e-6`. It failed
behaviorally. The matched 72-game screen scored **1--71 with -181 crowns**:
random 1--11 and every strategy/Hog workload 0 wins. Weighted playable no-op
was 99.47%; Hog was played only three times in 2,714 legal-affordable decisions.
The complete artifacts are under
`reports/human_safety_structural_fresh_seed1011001/`.

Therefore epoch 1 is rejected. This does not yet reject training the structural
architecture from initialization: only one optimization epoch was run, and its
independent chronology transfer was materially better. One bounded lower-rate
continuation epoch is allowed, with immediate random/balanced/Hog activity gates.
If passivity persists, further offline epochs are stopped and the experiment
moves to on-policy distribution correction rather than treating validation
accuracy as evidence of playing skill.

A separate fallback is now implemented but not yet trained: recurrent hand-slot
permutation augmentation. It retains the proven legacy policy architecture and
randomly relabels all four current-hand slots once per sequence, remapping the
hand, confidence, legal-action mask, previous actions, expert targets, and
privileged own-hand cards exactly. This tests whether statistical symmetry can
remove the shortcut without the hard structural timing failure. Exact inverse
tests, the real fitter integration smoke, Ruff, mypy, and the 22-test focused
imitation/slot suite pass. It remains an experiment, not an accepted fix.

The matched fresh legacy checkpoint confirms that augmentation targets a real
defect rather than an aesthetic preference. It scored 10--2 in the Hog audit,
but preserved card plus tile on only 28.46% of all hand permutations. Hog
selection varied from 8.55% in destination slot 0 to 63.19% in slot 1, 39.57%
in slot 2, and 60.87% in slot 3. The maximum slot-logit equivariance error was
28.63. These results bind the unaugmented baseline at
`reports/human_safety_legacy_fresh_seed1011001/hand_slot_robustness_hog12.json`.

Its matched broad gameplay baseline is stronger than the accepted parent:
**55--17 with +84 crowns** and 71.76% playable no-op, versus 51--21/+78 for
the parent on the same 72 records. This makes it the capability target for the
augmentation arm, but not an unconditional promotion: its 28.46% permutation
preservation is a severe held-out deck/cycle generalization liability.

The allowed structural continuation did not recover. One additional epoch at
LR `1e-4` improved validation loss from 1.753 to 1.685 and slot accuracy from
47.58% to 52.13%, but validation exact accuracy fell to 69.48%. Independent
chronology exact accuracy fell from 14.05% to 9.12% and joint NLL worsened from
7.148 to 8.609. Gameplay remained **1--71**, with 99.39% weighted playable
no-op. The hard-invariant fresh formulation is therefore rejected, and no more
offline epochs are authorized for it. The statistical permutation-augmentation
arm has started automatically from a fresh legacy initialization.

## Full-dose statistical augmentation result

The one-epoch full-dose checkpoint is
`checkpoints/human_safety_handperm_fresh_seed1011001/epoch1.pt` (SHA-256
`f69f2ac4796b05271c8a6a0f6e3dc819283ba657e35e3564f4ad3bb30b311448`).
It used the matched legacy corpus, seed, split, architecture, optimizer, and
training duration; every recurrent sequence received one consistent random
four-slot relabeling.

The intervention substantially weakened the shortcut. Card-plus-tile
preservation rose from 28.46% to 63.15%, maximum slot-logit error fell from
28.63 to 8.80, and Hog destination-slot selection became 82.59%, 62.69%,
88.56%, and 82.59%. Hog gameplay itself was 11--1 in the independent audit.
The result is not promotion-safe: the broad screen regressed from 55--17/+84
to 42--30/+34, playable no-op rose from 71.76% to 90.52%, and balanced strategy
fell from 10--2 to 0--12. Chronology action-type accuracy was only 15.83%.

Full-dose augmentation is therefore rejected as an initializer, but its
large measured invariance gain makes augmentation strength a justified causal
axis rather than another architecture guess. The next arm applies the exact
same relabeling to 25% of recurrent sequences. It must preserve the accepted
51--21 gameplay floor while improving the unaugmented 28.46% permutation score;
otherwise statistical augmentation is stopped rather than patched indefinitely.

## Twenty-five-percent mixture result

The weaker mixture checkpoint is
`checkpoints/human_safety_handperm25_fresh_seed1011001/epoch1.pt` (SHA-256
`6e4c26dd08537b8cbdef5a41c29cefaf7fc7138a49bc8858aafaf7700eb33d49`).
It recovered gameplay to 53--19/+66 crowns with 68.67% playable no-op, clearing
the accepted model's 51-win floor but trailing the matched unaugmented sibling's
55--17/+84. Aggregate card-plus-tile preservation improved from 28.46% to
40.58% and maximum slot-logit error fell from 28.63 to 20.27.

That aggregate improvement is not sufficient. Hog selection remained 9.81%
when mapped to slot 0 and 66.20--73.05% in the other slots, so the designated
card's physical-slot spread worsened. A matched four-game-per-card extension
covering Giant, Balloon, Goblin Barrel, Miner, X-Bow, and Royal Hogs improved
card-plus-tile preservation on five of six and max slot-logit error on all six,
but card-specific selection spreads improved inconsistently and gameplay fell
from 20--4 to 17--7. Artifacts are under
`reports/human_safety_handperm25_fresh_seed1011001/multicard_slot_audit/`.

Simple augmentation-dose fitting is stopped. The next fresh ablation separates
the two things the failed hard-invariant architecture changed: conditional card
choice becomes exactly equivariant, while play/wait timing retains the
permutation-invariant aggregate of the learned base timing logits instead of
using the failed replacement timing query.

## Equivariant conditional-slot-only result

The final factorization ablation is also rejected. The checkpoint is
`checkpoints/human_safety_equivariant_slotonly_fresh_seed1011001/epoch1.pt`
(SHA-256
`196887397ffa0d349b5685b9206667a6c8091bf491b5392d239f017d3b7c90f3`).
It made conditional card choice exactly permutation equivariant while retaining
the permutation-invariant aggregate of the learned base timing logits; the
failed learned replacement timing query was disabled.

The representation behaved exactly as intended. The Hog audit preserved card
identity and card plus tile on 100% of 50,520 counterfactual permutations.
Maximum slot-logit error was `3.82e-6`, maximum location error was `2.29e-5`,
and the four destination-slot Hog probabilities and selections were equal.
On the independent later-arena chronology, exact action accuracy rose to
41.19%, action-type accuracy to 48.43%, and joint NLL fell to 5.983. This is the
strongest chronology fit in the matched ablation family.

The live policy was unusable. It lost all 72 broad-screen games with -184
crowns: 0--12 against random, balanced, and reactive-defense; 0--6 against
bridge-pressure, slow-push, spell-control, and split-lane; and 0--12 on the Hog
pool. Per-workload playable-state no-op ranged from 98.48% to 100%. In the
separate 12-game Hog permutation audit it again went 0--12 and selected Hog on
only 0.252% of legal destination trials, identically in every slot.

This closes the current-corpus hard-invariance architecture family. Exact
symmetry and better offline chronology likelihood do not establish a usable
initializer when the first policy action moves the recurrent rollout outside
the supervised state distribution. No additional epoch, augmentation dose, or
timing-head patch is authorized. The retained 6.19M human+safety policy remains
the bounded PFSP parent. Simulator-native teacher trajectories provide
recurrent rehearsal; the final 1,000-game public human partitions remain
untouched disjoint no-regression evidence. Complete-game outcomes provide the
on-policy correction.
