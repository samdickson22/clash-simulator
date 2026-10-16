# B2 semantic snapshot contract decision

2026-10-16. CARD LEAD authorizes a separate, versioned semantic comparison proposal and its independent review. This does not accept the engine or change the verdict of the existing strict run.

Evidence: `clasher-cards-b2/reports/cards/b2/evidence/snapshot-cache-diagnostic-20261016.md`, the preserved raw run `3422841`, and native `leaf.rs`'s explicit Troop-only cached-base-speed read. The bounded Astra diagnostic establishes that current Python state does not reconstruct all native historical cache values. Digest equality alone supplies no equivalence proof.

## Required contract

- Keep the original strict comparator, failed raw snapshots, exact source/native identities and failure receipts. Label the new contract separately; never retroactively rewrite strict FAIL as PASS or call selected semantic equality complete serialized equality.
- Define a field/class applicability matrix and record every inapplicable field's path, raw values and source-grounded reason. Do not silently drop values from the evidence. An exemption is limited to the proved classes/read paths.
- For Troops, compare meaningful unslowed/base speed independently from Python against the actual non-null native cache. Use the exact native fallback only when the native cache is absent. Do not recompute or replace a non-null historical value from current charge state, copy native actual values into expected, or blanket-ignore the field on Troops. Preserve source-phase/history distinctions; an unexplained mismatch remains a failure.
- For Tower/projectile cache applicability, inspect propagation as well as direct reads. A cache copied into a subsequently materialized Troop can become meaningful to danger ETA; prove reinitialization/non-reachability or exercise descendant continuation and compare its actual base speed. Do not declare all projectile histories globally inert merely because flight ignores the cache.
- Project actual Python `Projectile.target_position` as the last committed endpoint consistently at initial native construction and comparison. Keep aim, target IDs, homing, launch delay, hit history, buffs and damage strict. Record the existing shared-exporter gap separately: a probe-only correction does not prove that the production snapshot exporter itself was repaired.
- Preserve every existing meaningful snapshot field and target-selector/mutation assertion. Existing explicit baseline exclusions retain their documented scope; no opportunistic additions on a failing case.

## Validation and admission

The existing owner implements the complete proposal, collector/report/validator changes and regression controls end-to-end. Required independent review must cover the exact contract, applicability proofs, expected-state independence, counts and affected host scripts before altered execution.

Negative controls must detect incorrect troop base speed, original-speed/slow recovery, charge threshold/reset history, committed aim, target IDs, hit contents/multiplicity and buffs. Include a source/child propagation witness if its cache can reach a Troop. Keep meaningful native/Python continuation and both-seat source/offset/path overlap/mutation requirements. New raw failures remain failures under the applicable contract; constructor normalization must never step the expected native state.

Use one fresh identified affected validation after the existing run terminates; preserve its useful first-update/Clone/scenario evidence independently. No competing full sweep, obsolete gate, source/native substitution or shared engine/export edit is authorized by this comparison decision. Review future changes normally if actual engine defects are demonstrated. C56 parity and final engine review still precede acceptance, with B2→C1 integration order unchanged.

Rollback: retain the original comparator and immutable failed run; revert the reporting/probe-only contract commit if invalidated. No runtime or active pin has changed.

Communication: strict silence; files hold detailed work. Only blocking parent action, urgent live failure, explicit request or essential direct-owner handoff may be messaged, at most two sentences plus one path. Automatic final delivery once the whole assignment is done; no routine result/acknowledgment DMs or tiny per-step delegates.
