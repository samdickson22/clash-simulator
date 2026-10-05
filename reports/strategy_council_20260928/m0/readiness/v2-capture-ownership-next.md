# Next bounded v2 capture ownership adapter

The current runner executes opened development captures and refuses fresh acceptance. The next adapter should connect the existing 32-episode root-bank declarations and the native-config converter to capture claims and outcome claims. This is a concrete proposed implementation boundary; none of these claims have been created yet.

## Inputs and identity

Consume the root-bank manifest, one converter manifest per episode, pinned native config files, source/config hashes, ruleset/projectile catalog identities, and the required native attestation. Each episode manifest must bind `family_id`, `source_episode_id`, the complete RootRequest hash, root-bank hash, native config hash, both ordered decks, root owner, seed, base level-11 forms and prefix styles. An emitted native config is not a capture receipt.

Do not reuse the historical calibration ledger as a writable v2 ledger. Read its root/config identities to reject fresh reuse; preserve its exposure records. Use a dedicated `readiness-v2.sqlite` for new prospective claims. Canonical config SHA and source episode identity must both be unique for fresh roles, so mirrors, seat changes or alternate root ticks from one captured episode cannot masquerade as independent families.

## Minimal implementation

Add one `readiness_capture_ownership.py` module and a root-prefix collector using the existing native transport/projection helpers. Keep the schema narrow:

1. **Attempt declaration:** attempt ID, immutable root-bank/generator/source/config/criteria hashes, expected 32 family/episode IDs, scope and evidence role. Declare this before native prefix execution.
2. **Episode claim:** attempt/family/source-episode IDs, config SHA, converter manifest SHA, native attestation, claim nonce, and canonical output directory. Insert atomically before `configure`. Existing fresh claims cannot be retried or redirected. A failed claim remains in the attempt.
3. **Root capture receipt:** claim identity, config and initial-frame hashes, accepted prefix commands and command receipts, complete five-tick public-frame sequence, root-selection report, selected tick/frame/public-packet/candidate hashes when selected, and explicit `prefix_complete`/`game_complete` flags. Stop after the first eligible causal root. No synthetic terminal result or full-game completion claim belongs in this receipt.
4. **Branch claims:** `(attempt, family, condition, candidate_role, engine)` as the unique key, bound to the selected root and final branch protocol. Claim before execution. The four ordered continuation conditions must be represented explicitly; v7's `(root, candidate, engine)` key is insufficient. Repetition indices belong only to a separately declared development study.
5. **Exposure event:** append-only family/attempt purpose plus evidence hash, recorded before outcomes are inspected. Failed or partial attempts remain opened. Evaluation cannot delete missing cases or change roles, and training can never consume acceptance families.

Use SQLite `BEGIN IMMEDIATE` for claims and exclusive output creation. Require the same canonical directory when validating a claim, and verify input/artifact hashes before branch execution and evaluation. A process failure should yield a retained incomplete claim, not an automatic retry. Concurrent runners must use both the native process lock and the ledger uniqueness checks.

## Freeze order

Freeze the generator, root eligibility/missingness rules, controller settings and source/config bytes before capturing the declared prefixes. Derive root/candidate bindings only from those causal public prefixes, then seal the complete branch protocol before opening branch outcomes. A missing or ineligible declared episode remains missing in that attempt; do not draw replacements after inspecting it. If all 32 roots cannot be bound under the declared design, report the attempt as inconclusive and preserve it before defining another prospective attempt.

The existing `Protocol` record currently stores fully bound families. The adapter therefore needs two explicit receipts: the pre-capture design declaration and the post-prefix root-binding seal. Both hashes must appear in branch claims. Treating a post-capture protocol hash as if it were the pre-capture declaration would lose provenance.

## Remaining requirements

The new root-bank selector requires every five-tick packet in its scan window. Existing archived 30-tick captures are useful development data but cannot prove that an earlier eligible root was not skipped. Fresh prefixes must supply that cadence.

Structural public-v4 validity and channel calibration remain separate. Unknown level 0/confidence 0 is valid missingness; it does not establish that native own-hand/next-card levels were measured. The runner can report such coverage honestly while calibration and acceptance remain unestablished. Complete same-execution repetition and consequential-coverage evidence, justified rounding allowances and coordinator review still precede a final readiness freeze. Native transport itself has not been launched by this adapter-design subtask.
