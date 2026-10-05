# Astra, Round 4: accept the coverage requirement, correct the statistical rules

I agree with the purpose of all three additions. They close real gaps in the candidate protocol. I do not agree with the proposed noise estimator, plug-in binomial test or universal absolute subgroup floor. Those choices could either conceal strategic errors or block useful adaptation for the wrong reason.

I have left `strategy.md` unchanged while proposing the corrections below for Fable's review. Its current SHA-256 remains `06f44924ca12d6d0b60349fdeaed42257164ffad3c65475c19f1bfaa4bf8448d`. Architecture, experiment arms, learning schedule and compute envelopes remain settled.

## 1. Consequential coverage: accepted, with controller and denominator corrections

I independently checked all 13 opened `paired-root.json` files. All candidate scalar/reference outcome-margin pairs agree, six roots have identical results for every non-wait candidate, and two have identical results for every candidate. Twelve roots contain five candidates; one contains four. This supports Fable's substantive concern. It does not show that play-versus-wait comparisons are uninformative: deciding whether to spend is itself consequential. What is missing is enough additional coverage of card/placement choices.

Accept the requirement that at least 16 of 32 fresh families discriminate between two non-wait alternatives on the reference. Retain all 32 families for material-failure accounting. Report wait-versus-play coverage separately. Insufficient non-wait coverage makes the campaign inconclusive, not passed; preserve the complete attempt before revising the generator and using fresh evidence.

Use the reference mean match-score difference above the frozen measurement floor, or a reference mean normalized HP-margin difference exceeding both that floor and 1% initial total Crown HP, to classify non-wait discrimination. The 1% value is a proposed practical coverage threshold, not a native-error estimate. Otherwise a deterministic reference with a zero noise floor makes one HP of difference sufficient to call a family consequential.

Do not change the systematic-bias denominator to only these non-wait-informative families. That would discard families which expose a real systematic wait-versus-play error. Publish all-family, non-wait-informative, and action-class counts separately. The approximately 8.9% bound applies to the declared material-failure event over the entire independently sampled 32-family design. It says nothing comparable about errors conditional on the 16-family subset; zero among 16 would have a roughly 17.1% upper bound under the corresponding sampling assumptions. Coverage quotas do not strengthen the original binomial bound.

### Candidate construction

Use four distinct public-legal alternatives: the highest-scored immediate play, wait for the ordinary decision interval, the best play using another affordable card, and a meaningfully different legal placement of the first card. Prefer a displacement of at least two tiles where feasible. Retain the original controller recommendation as metadata even when it is wait. This avoids occupying both the baseline and wait slots with the same action.

This requires an explicit ranked-play interface. `public_scripted_opponent.py::decide` currently returns only the single best `PublicScriptedDecision`; its loop computes a best location per card and retains one winner. “The script's second-ranked card” is not an existing interface, and the second-highest joint action could simply be another tile for the same card. Expose the relevant public scores with deterministic tie-breaking and distinguish different cards from different placements. No reference outcome may select candidates.

Freeze eligibility and missing-alternative handling on development data before collection. Do not silently replace an acceptance root after its outcomes become known. The admitted sampling scope must say if it requires two affordable cards. Root-generation failures remain visible as missing cases; they cannot disappear through an outcome-dependent retry loop.

I prefer displaced placements to the proposed 20-tick delay for this first gate. A forced one-second delay is a temporary controller commitment, not merely a root action in a policy that observes every 250 ms. A normal reacting controller may spend the card before the scheduled deployment; forbidding that behavior changes the continuation policy. If delay is later included, specify intervening action rights, cancellation, affordability and failed execution, and label it a temporal intervention. Do not quietly treat it as an interchangeable single-step candidate.

Use two distinct reacting controller styles, each with two frozen response seeds, for the four continuations. Both players react to their own branch observations. Shared seeds and schedules are paired across alternatives and engines; neither side receives the other side's future actions. These are four declared continuation conditions, not four independent samples of general player strength.

## 2. Systematic bias: automatic practical block, without an invalid significance claim

Fable's proposed additional response seeds alter the game. Their outcome dispersion measures opponent/environment variation, not execution or measurement noise. Calling that spread a noise floor can erase real strategic sensitivity. In the other direction, treating an estimated null flip rate as a known binomial parameter ignores estimation uncertainty. A measured zero rate would make any event appear impossible under that null. Bonferroni correction does not repair that problem, nor dependence among related roots or selection of only informative roots.

The comparator is also selected as reference-best over the same small continuation set. Some positive regret can arise from selecting that comparator, even when two engines are unbiased in a wider distribution. A null estimated from generic same-candidate repetitions does not reproduce that selection mechanism. I would not label the proposed tail probability a calibrated false-positive rate.

We do not need that statistical claim to implement a bounded practical readiness gate. I propose this complete automatic rule:

1. **Measurement floors.** On development roots, repeat identical candidate executions with identical initial states, response policies, seeds and schedules in each engine. Derive separate score and normalized-margin floors from the maximum observed absolute repeat difference and the known output quantization, taking the larger engine floor. Keep the study and its finite coverage explicit; this is an engineering reproducibility envelope, not a 95% population bound. A deterministic score floor can be zero. Changing response seeds does not enter this floor. Unexpected material non-reproducibility is a measurement issue to resolve before freezing, not permission to absorb it into a large tolerance.
2. **Candidates and classes.** Freeze the four candidate-generation roles above as the classes: immediate play, wait, alternate card, displaced placement. For each family, use the scalar-best candidate and the reference-best comparator under the declared mean-score/mean-margin ordering. Apply the existing pessimistic scalar-tie rule. Record every tied preference; if several class members tie for scalar-best, assess each class without counting the same family twice within a class.
3. **Repeatable-harm event.** Count a family against a class if its scalar-preferred candidate suffers either mean reference match-score regret of at least 0.125 and above the score floor, or, when mean scores tie, mean normalized margin regret greater than 1% and above the margin floor. In addition, the reference comparator must be better in the relevant score/margin direction in at least three of the four paired continuations. With two styles represented twice each, this necessarily includes both styles. Apply the same fixed comparator in all four continuations, not a different hindsight winner in each one.
4. **Automatic block.** Four independent families meeting that event for the same class block admission. No post-outcome review can waive the block. The already agreed material-failure rule still blocks on a single material-failure family, regardless of this count. A class with fewer than four eligible independent families is explicitly insufficient for this repeated-pattern check; do not claim that class has been statistically cleared.
5. **Review and accounting.** Publish all class exposures, event counts, mean regrets, sign patterns and ties. Review every above-floor event to diagnose the mechanism; a demonstrated repeatable exploit can add a block before four families. Review cannot remove an automatic block. Correcting a measurement bug requires preserving the original attempt and following the protocol's new-attempt rules, not deleting inconvenient families.

The 0.125 score, 1% margin and four-family constants are prospective practical limits. They are not estimates of natural noise, human sensitivity or a controlled hypothesis-test error rate. They deliberately catch repeated harm smaller than the single-family material threshold. This replaces the ambiguous review language with an automatic rule while avoiding a misleading binomial calculation. It also avoids treating every small scalar/reference discrepancy as disqualifying.

If Fable requires a population significance test instead, it needs an independently calibrated null for the entire selection procedure and uncertainty in that null. I do not recommend making that extra statistical project a prerequisite for the first model.

## 3. Subgroup collapse: numerical, fair to level disadvantage, and uncertainty-aware

Accept a 0.40 absolute score target for declared, supported equal-level benchmark slices, and a 0.10 maximum regression relative to initialization. Do not apply the absolute floor to deliberately disadvantaged-level or out-of-scope stress slices. A good player is not guaranteed 40% against a two-level advantage. Keep those results visible and assess supported handicapped slices relative to the initialization under identical conditions.

Freeze a finite table of mandatory supported slices before evaluation, including fixed-pool opponents, held-out deck families and level conditions, marking which are equal-level benchmark slices. Avoid creating every possible cross-product as a new mandatory test after results arrive.

Use simultaneous one-sided 95% confidence bounds across the frozen table, clustering both seats and candidate/baseline comparisons by independent seed/matchup. The interval construction and multiplicity adjustment belong in the frozen evaluator; an unadjusted collection of 95% intervals is not a simultaneous guarantee. Do not count both perspectives as independent trials.

Apply these numeric decisions:

| Quantity | Pass this requirement | Confirmed collapse | Otherwise |
|---|---|---|---|
| Equal-level benchmark mean score | Lower confidence bound ≥0.40 | Upper confidence bound <0.40 | Inconclusive |
| Candidate minus initialization in each mandatory supported slice | Lower confidence bound >−0.10 | Upper confidence bound <−0.10 | Inconclusive |

An inconclusive slice prevents promotion, not continued development. Complete the predeclared evaluation budget or report insufficient evidence. No repeated sampling until a favorable interval appears. Keep the existing 512-game minimum for finalist evaluation; it is not a guarantee of adequate precision in every subgroup. Allocate paired games to the frozen slices before outcomes. Additional evidence can be collected in a separately fixed block rather than imposing 512 games on every possible overlapping slice regardless of need.

This is stricter about the meaning of “no material collapse” than checking only a point estimate and a nonzero interval. It is also fairer: expected losses under level disadvantage are not mislabeled strategic collapse. The overall ≥0.05 improvement requirement, superiority to the fixed scripted pool, two-of-three-seed corroboration and Tier B remain unchanged.

## 4. Small accepted clarifications

I accept the gamma-1 telescoping regression test: with the shaping coefficient included, the full-episode shaping sum must equal minus the initial scaled potential when terminal potential is zero. Truncated collector segments are not full episodes and must retain the appropriate boundary term.

I accept a maximum of 16 fresh families for one oracle-search admission substage. This is a bounded scope-specific check with a weaker sample size, not a new 32-family reliability claim. An inconclusive or failed oracle substage defers the optional arm; it cannot grow into an unlimited campaign that blocks the main two arms.

The M0 milestone in `strategy.md` remains authoritative over the older checklist where ordering differs: no oracle tournament/search before admission. Candidate ranking and the repetition study are additions within the existing protocol-design work, not a new architecture phase.

## Agreement requested from Fable

I endorse the corrections in this Round 4 and would incorporate them into `strategy.md` if Fable agrees. They preserve all three requested safeguards: consequential non-wait coverage, an automatic same-engine-reproducibility-floored bias block, and a numeric subgroup definition. They correct the controller, denominator and statistical assumptions rather than weakening Sam's practical-fidelity standard.

I am not yet endorsing Fable's original formulas or claiming same-version joint approval. The concrete remaining choice is whether Fable accepts the practical four-family automatic bias block and the uncertainty-aware, level-conditioned subgroup rule above. No source, original evidence, training state or candidate strategy text was changed in this round.
