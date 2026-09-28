# Prospective calibration and ranking protocol

Status: development protocol, no learning/search acceptance yet. This protocol
implements the active goal's entry gates; it does not authorize a policy run.
The pinned offline native runtime is a reference for its declared ruleset,
not proof of official-game equivalence. Official observations and human playing
strength remain separate requirements in PIPELINE_DESIGN.md.

The existing native traces, all fixed placement families and friendly-building
controls are opened development evidence. They remain permanently in that role.
No model, final test, or independent acceptance claim may use them as an unseen
holdout. Keep raw captures content-addressed; record code and ruleset digests,
config, realized cards/levels/forms, seed, both seats, command submission and
execution ticks, and complete error accounting.

## Historical development collection: timed defensive responses

These controls have been collected and opened for simulator repair. The timing
instructions in this section describe that collection; new runs should use the
verified scheduling path in the startup correction below.

Use the verified play command path. Each command requires visible body creation
and elixir change, not just an accepted queue status. Account for its22-tick
submission-to-first-body delay. Do not use replay-schedule-card until execution
has been demonstrated. Define candidate execution ticks first, and submit early
enough to realize those ticks. Record the native state at the actual decision
boundary; do not attribute transport latency to simulator movement.

Collect HogRider, Giant and Prince pushes against Cannon and Tesla with two
predeclared defensive positions, (5.5,18.5) and (7.5,19.5), and execution offsets
30,50,70 ticks after native tick221, the last tick before the initial attacker
appears at222. Thus defense bodies first appear at251,271,291. Rotate both seats. Every
root's candidate alternatives must share the initial state, seed, ruleset and
first attack. Include a no-defense baseline per attacker and seat. End at a
fixed sufficiently long tick and verify the attacker's removal; extend every
candidate of a family if any branch remains alive. A surviving attacker is an
incomplete outcome, not a zero-error success. These cases are development, not
a reacting-policy match benchmark.

Compare per-branch total and per-tower damage, surviving bodies, elixir spent,
first target/acquisition and first damage event. Record ties and strict ordering
reversals separately for each attacker/building/seat/timing family. A change in
terminal damage by one ordinary attacker hit or any strict reversal is a repair
candidate. Coordinate drift alone is not a failure of strategic fidelity; it
requires timing/contact or outcome evidence. Exact replayed values remain
available for diagnosis instead of being hidden by this prioritization rule.

## Public-state gate

Before fitting any policy, freeze the supported card/form/ruleset scope and the
public observation/action contract. Current private component inspection is only
for simulator diagnosis. It must never enter actor examples or branch inputs.
Validate both-seat coordinate and command round trips, own hand/cycle/elixir,
publicly observed entities and tower health, last own play for Mirror, and the
history-derived opponent belief. Masking and feature serialization must use the
same public contract. Unknown forms, missing entities, uncertain ticks and
truncation must produce explicit failures or uncertainty, never guessed truth.

Create an independent physical-match split before public-state acceptance
collection. Keep both perspectives and all related clips/reconstructions in the
same split. Freeze tolerances from annotation uncertainty and intended decision
cadence before inspecting acceptance outcomes. Require no hidden-state leakage,
no silent truncation, no unsupported-card substitution and no known unresolved
state/action mismatch that changes a decision in the accepted scope. Publish
coverage and failures by card family, deck, seat, time and entity density; pooled
agreement cannot hide a failing family. Hold acceptance data out of training and
repair selection. An opened acceptance failure becomes development evidence and
requires a fresh independent acceptance collection after repair.

## Counterfactual-ranking gate

Before learning/search, compare candidate rankings on independently collected
roots excluded from fitting, repair selection and tolerance setting. Freeze the
candidate generator, public histories, opponent response model, seeds, horizon,
terminal utility and compute. Include wait, timing changes and nearby legal
placements. Evaluate paired alternatives to completed outcomes under reacting
opponents, and retain the full matchup table, ties, failures and uncertainty.

Predeclare the sample-size and acceptance thresholds after the development
variance estimate, before acceptance collection. Require useful action ranking
relative to the frozen baseline, no consequential subgroup regression, and
improvement that survives completed reacting-opponent games. Fixed no-more-play
branches cannot satisfy this gate by themselves. Missing thresholds, uncollected
independent roots or an unvalidated opponent response model mean the gate is
not passed. No retrospective threshold changes or pooled-only promotion.

Expert reconstruction audits and public feature implementation may proceed
read-only while these gates are developed. Policy updates, PPO, self-play
training, search and teacher distillation remain blocked on the applicable
entry evidence. After entry, each stage retains its additional checks in the
pipeline design. Human-level play still requires a frozen candidate and the
predeclared independent human evaluation.

## Startup and scheduling correction from paired-game collection

Later controls established a startup boundary: native card plays execute from
interval90 onward, first visible at91. The prior scheduled-card failures at
interval70 occurred before that boundary. After startup, replay-schedule-card
executes at its requested next-frame boundary with visible bodies and elixir
spend. Future paired collection can use this verified path with a declared
one-tick observation-to-execution boundary and an explicit startup wait. The
older22-tick play controls remain valid at their recorded timings; do not rewrite
them or silently shift prior immediate-action scalar datasets.

## Entry status after the Log repair

The `log-push-full` development replay matches all197 sampled native tower-health
checkpoints in one scripted game. It is still opened development evidence. Its
body audit retains health, position and count discrepancies, including an Archer
pending-damage retargeting difference. It cannot establish either entry gate.

Before independent acceptance collection begins:

1. Finish and declare the supported ruleset and forms. Current paired replays
   still use an explicit partial IceSpirit HP profile; the default raw ruleset
   and the tensor implementation are not certified by these scalar results.
2. Resolve known decision-changing state/action discrepancies in that scope,
   and audit public representations of transient objects. Private component
   inspection may diagnose errors but must not become actor input.
3. Freeze public-state tolerances, sampling cadence, failure accounting and
   physical-match grouping. Every opened replay window and related control must
   remain in development; replaying it with new code does not create a holdout.
4. Complete development variance estimates for the reacting-opponent ranking
   evaluation. Then freeze numerical thresholds, sample sizes, candidate actions,
   response model, horizons, utility and seeds before collecting acceptance roots.
5. Collect independent acceptance data and evaluate the full declared coverage,
   retaining subgroup failures. Any opened acceptance failure returns to
   development and requires fresh independent evidence after repair.

Those declarations, independent roots and acceptance results remain incomplete.
No policy fitting, self-play training, search or promotion is authorized by the
197-checkpoint result. The remaining pipeline and human-evaluation requirements
continue to apply after these entry gates pass.

## Playable deadline and result presentation

Native last-command controls establish one final legal interval: submissions at
3600/6000 execute at3601/6001. Later submissions cannot spend elixir or apply a
spell. Scalar deadline decisions therefore occur after that interval, using
integer milliseconds. Native tiebreaker presentation may continue after policy
actions close. Record the playable endpoint and the finalized native result
separately, and verify the actual winner. Comparing post-animation tower health
to the scalar playable endpoint is not a valid state-fidelity test.

The current opened replay matches198 sampled tower frames through6001 and its
winner matches native finalized6146. This remains one development game. Small
position-sensitive life/impact shifts are recorded in the residual audit; their
acceptability requires prospective tactical-sensitivity tests and independent
coverage. Neither pooled checkpoint agreement nor a matching winner passes the
public-state or reacting-opponent ranking gate. Ruleset support, native public
projection, terminal masks, nuisance ranges and acceptance thresholds remain
explicit entry work.

## Native public-level reference source

The level-aware public contract distinguishes a unit's visible level from its
normalized HP. Reviewed rendered Knight 11/Mirror 12 and Musketeer 12/Mirror 13
controls bind native character offset0x120 plus one to the displayed labels in
this exact build. The bounded reader checks attestation, object identity, the HP
component owner backlink, and unchanged paused state. It supplies reference level
labels; it is not a pixel OCR system or a general build-independent memory layout.
Raw memory, addresses, targets and timers remain diagnostic and never enter actor
arrays. Each projected level reading is bound to its frame/epoch and source digest.

Automated native labels do not pass the public-state gate by themselves. Pixel
label timing is also unresolved at object birth: the rendered Log control showed
an engine object at201 before its sprite appeared at202. Stable paused state is
not sufficient proof of pixel/state alignment. Acceptance collection must declare
how it handles birth/death visibility uncertainty, spectator HUD masking, and the
camera-to-arena coordinate transform. Keep all these opened controls in development.

## Reacting continuation development pilot

The first finite reacting comparison uses opened development game1293401 at
pre-action tick4020. `reacting-log-pilot-protocol.json` freezes four owner1 choices:
wait, the recorded Log placement, a one-tile neighboring placement, and a one-tick
delay. The simultaneous owner0 Tesla action stays fixed at the root. Later both
seats use the fixed public geometry controller at a30-tick cadence, independently
on each engine's own public observations. Random draws are keyed by response
seed, absolute tick and owner, so skipping a choice cannot shift later draws.
No branch utility chooses an action during collection. This is a finite diagnostic
experiment, not a deployed planner, teacher or learning run.

Native roots must reproduce the original archived public snapshot exactly.
Scalar roots replay the same accepted command history and preserve any measured
state drift. Consequently this pilot measures the combined effect of accumulated
replay error and subsequent reacting control; it does not isolate a perfectly
reconstructed common latent state. Native private attack clocks and targets are
not supplied to either controller. Both engines validate each chosen public mask
and native commands require elixir-spend evidence. Unsupported observations or
incomplete outcomes fail the collection rather than receive a zero utility.

Compare completed owner1 outcomes first, then remaining own-minus-enemy tower
HP as a declared tie-break. Retain strict reversals, lost distinctions and ties
separately. Report later command divergence alongside outcome divergence. One
opened root and one weak controller seed cannot estimate population variance or
pass either entry gate. These results can direct repairs and improve measurement;
fresh independent roots and a validated opponent model remain required.

## Native root identity and expanded deck development

New native collections bind the canonical native configuration, including seed,
decks, levels and match settings, to a persistent data role before any observation
is collected. Output paths, producer code and scalar ruleset revisions do not
change that root's identity. Accepted command semantics identify a physical
continuation within the root. Both seat archives receive the same physical and
duplicate-group IDs. The local SQLite registry refuses conflicting role bindings.
Legacy opened games have external root bindings; their original archives remain
unchanged for reproduction.

This is exact-configuration grouping. Seat swaps, transformed scenarios and
other known relatives still require an explicit family assignment before
acceptance. The registry does not certify independence, validate an opponent,
implement acceptance-to-development retirement, or pass an entry gate.

The Goblins/Knight development game adds a fresh configuration and seed. Its
prospective root rule selects the first accepted owner1 Cannon/Goblins command
at or after1800. Waiting and legal one-tile horizontal neighbors form the finite
candidate set; illegal neighbors remain reported exclusions. Two response seeds
are frozen before branch collection. The first batch was stopped when a pinned
Goblin damage mismatch was verified. Its completed wait pair and partial next
branch remain unscored evidence. Do not silently resume or score that incomplete
batch, or treat its originally matching full-game winner as acceptance.

## Fresh model card metadata

The fresh learning configuration must explicitly select the audited card
metadata version. `card_semantics_version=4` retains the v3 layout but decodes
compact `target_type` flags and derives missing character mass through the
verified runtime rule. Legacy versions1–3 retain their prior values for old
checkpoint reproduction. The default is unchanged; do not silently migrate an
existing checkpoint or mistake that default for the new learning configuration.

This metadata version is distinct from public policy input contract3 and public
sequence archive4, which govern visible levels and serialized observations.
Version4 metadata fixes known flags/mass defects; it does not certify every
card descriptor, ruleset field, perception input or training gate. No fit is
authorized by metadata or inference-only unit tests.

## Decision-focused development audit and family ledger (September 16)

`src/clasher/rl/calibration_decisions.py` scores the worst native result among
all simulator-best tied actions. A selected win/draw/loss misprediction is a
failure even when every alternative has the same native outcome. It reports
regret separately from prediction error and groups related roots and response
realizations by physical family. Development reports always deny acceptance
and training authorization; they do not infer confidence from repaired cases.

The production public-controller rechecks contain five decision roots in four
declared families. The verified report is
`reports/calibration_development_20260915/public-opponent-development/resident-fallback-production-rechecks/registered-family-decision-audit.json`.
All four families have zero selected-action regret; two have a clear improvement
over the recorded-action baseline. The separate raw audits retain inferior-action
HP prediction errors and ending-time differences. These opened data do not prove
independent accuracy, official-client equivalence, or human strength.

`decision-criteria-draft-v1.json` in the same development report base proposes
64 fresh families, zero bad families, a 95% one-sided planning bound below 5%,
and an 81 HP regret budget among equal-outcome actions. That budget is one
level-11 Skeleton hit in the pinned profile (32 base damage, 256% multiplier),
not a threshold chosen to accommodate the observed 631 HP prediction error.
It also proposes at least five clearly improved families and no clear regression
against the declared baseline. These are draft decisions, not collection
approval. Scope, independent sampling, subgroup coverage, public-state numeric
tolerances and the response-model declaration must still be frozen. The bound
requires independent draws from the declared distribution; it does not establish
per-card accuracy or certify unobserved decks.

`src/clasher/rl/calibration_families.py` freezes explicit family membership and
roles atomically in the existing root registry. Known members cannot acquire a
new family or role, and exposure cannot be reset by registering the family again.
Opening an evaluation consumes freshness too; a frozen evaluation result can
still be assessed, but its cases cannot be described as new unopened evidence.
Acceptance families stay excluded from training even after failure.

Five existing development families (nine exact native configurations) are now
registered, including both seats of the public-controller study and the paired
deck studies. Their manifest and registration receipt are
`opened-family-manifest-v1.json` and `opened-family-registration-v1.json` in the
development report base. This is explicitly retrospective development grouping.
Other legacy studies remain ungrouped. The ledger cannot infer undeclared
relationships and is not yet a complete acceptance collector/evaluator; the
prospective sampler must declare all related configurations before collection.

## Numeric reference-state checks (draft, September 16)

`public-reference-criteria-draft-v1.json` in the calibration development report
base declares the current 16-card, level-11, base-form reference-label scope.
It is an initial engineering scope, not the final game roster or human benchmark.
`src/clasher/rl/public_reference_checks.py` compares serialized observations
with native reference labels. Body position and own elixir must round-trip to
the exact source integers; body and Crown health must equal their float32
reference fractions. Own hand/next-card tokens and canonical Crown columns must
match. Missing/duplicate bodies fail a multiset comparison. Unobserved private
channels must retain zero values and confidence. There is no allowed gameplay
error hidden in these numeric serialization checks.

These conditions do not set camera noise tolerances. Reference confidence1
means a supplied exact label, not a measured detector confidence. Nor do they
require independently simulated matches to retain identical trajectories.
Simulator decision sufficiency remains subject to the separate ranking criteria.
Independent transient-effect identity/level correspondence, command timing,
family sampling and the prospective evaluator are still unfinished. The draft
therefore grants neither acceptance nor training permission.

September 17 public-vocabulary correction: token IDs previously depended on the
union of the two match decks. Replacing an unrevealed opponent card changed own
hand and entity IDs despite an otherwise identical public state. No policy was
trained on these captures. New collection and branch evaluation use the fixed
16-card `PUBLIC_REFERENCE_CARDS` roster through `public_reference_builder`.
Historical display aliases are normalized by native card identity before replay.
New captures bind `public_card_roster` and `token_vocabulary_sha256` in their plans.
Legacy captures remain auditable for diagnostics but cannot clear public-input
acceptance. Prospective preparation requires the full frozen roster, and the
acceptance evaluator rejects a vocabulary that is not independent of hidden decks.

Both-seat hidden-deck invariance tests pass for actor arrays, card metadata and
legal-action masks. A complete development collection passed236 public frame and
HUD sensitivity checks; ten branch controls retained1142 controller decisions and
all terminal outcomes after the encoding change. These are development checks,
not independent acceptance or camera calibration. The source-bound86-root rerun
must finish before freezing the next independent cohort.
