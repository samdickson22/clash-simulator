# Cross-review questions

Read the other model's complete Round1 proposal. Identify substantive disagreements and source findings that change your recommendation. Do not agree merely because consensus was requested. Where evidence cannot decide, agree on a bounded comparison and its decision rule.

Please converge on these decisions:

1. Which architecture and initialization should produce the first useful learned actor? What, if anything, should be reused from historical checkpoints? Separate reusable software from validated model behavior.
2. What is the credible demonstration source now? Distinguish a temporary scripted warm start from human strategic supervision, and make any human-data audit timebox explicit.
3. What must be fixed in the actual collection/training/inference path? Include visible entity levels, own undeployed card levels, recurrent state, previous rewards, causal observations, masks, and sampling/update likelihoods. Distinguish day-one requirements from later improvements.
4. How do we satisfy practical public-state and action-ranking readiness without restarting an endless exact-replay campaign? Preserve v7's failed attempt and all exposure records. Explain the evidence and scope needed before a first bounded learning run, and which criteria require new frozen data. State the limitations of any proposed numerical thresholds.
5. How will the policy learn and demonstrate adaptation to levels and modest dynamics differences? Avoid equating exact native trajectory matching with transfer or scripted-opponent wins with human competence.
6. What concrete first implementation milestone can the coordinator execute immediately after consensus? Give an ordered file/interface scope, meaningful tests, bounded resource use, and a clear completion condition. It should progress the learning pipeline rather than merely add planning documents.
7. What are the first learning/evaluation experiment, fixed opponents/splits, continue/pivot rules, and compute/storage limits? Hardware facts are in `local-environment.json`. No paid allocation exists.

Output a revised common-strategy proposal, list any remaining disagreements, and state what exact plan you would approve. A later round will ask both models to explicitly approve the same versioned plan.
