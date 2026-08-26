# Real-game calibration gate for the simplified resident Gym

Date: 2026-08-26

## Decision

Use the real-match corpus to gate clock/phase transitions, typed play identity,
public-mask-v2 legality, orientation, and coarse deployment position. Do not
hold the production Gym to Python-only float/RNG/event details, but also do not
claim that the current videos validate combat trajectories, HP/damage,
projectile targeting, status duration, or match outcomes. Those channels remain
serialized-mechanics plus invariant driven until independent labels exist.

## Evidence inspected

- The persistent YouTube corpus has 29 matches, 76,148 neutral 10-Hz rows,
  65,285 clock-valid rows, 971,838 detections, 802,536 accepted typed
  identities, 471,866 accepted HP detections, and 699,631 resolved positions.
  Position confidence is a detector score, not calibrated geometric error.
- The replay-grouped 33-match audit contains 1,059 offline actions: 923 clocked,
  821 legal under label-independent public-mask v2, 711 legal and clocked, 220
  with complete actor HUD, and 24 fully verified replays.
- The older replay-disjoint spatial corpus contains 4,610 strict visual
  placement labels from 663 games. It is suitable for coarse placement
  distribution checks, not hitbox or trajectory claims.
- Five fixed persistent matches were sampled directly (12,362 rows). Every row
  interval was 100 ms. Of 10,735 accepted clock rows, adjacent accepted clock
  changes were 9,675 holds, 960 decrements of one second, and five +119-second
  regulation-to-overtime resets; there were no other adjacent changes. All 154
  accepted play timestamps lay on the 100-ms grid.
- In that sample, continuous deployment points were a median 0.286 tile and
  p95 0.477 tile from their encoded tile centers. This is only an encoding
  sanity check because the tile is derived from the same visual point, not an
  independent accuracy measurement.
- Accepted HP is not value-calibrated. Even the five-match sample had 5.18% of
  62,581 `hp_valid` values equal to zero, including implausible opening tower
  readings. Status and projectile-target supervision are both exactly zero.

## Production Gym tolerances

| Channel | Gate now |
| --- | --- |
| Internal time | Keep the serialized 50-ms phase order, but compare real evidence only after deterministic 100-ms resampling. Internal Python float residue is irrelevant. |
| Public clock | Same phase and at most 1 displayed second error. Adjacent 100-ms observations may hold or decrement by one; the only positive jump is the regulation-to-overtime reset to 2:00 (observed as +119 from 0:00 to 1:59 on the next sampled frame). Reject any other increase or illegal phase transition. |
| Play timing | Exact deterministic action application in the Gym. Against independently audited video onset, require p95 absolute alignment <=100 ms. The current 100-ms quantization alone does not prove that accuracy. |
| Card/action | Exact typed stable identity, actor, hand slot where visible, successful application, and public-mask-contract-v2 legality. Unknown Hero/Evolution art fails closed and is never root-collapsed. |
| Deployment | Exact actor/world orientation. For audited labels require >=95% within one 18x32 tile; report exact-tile accuracy separately. For manually labelled entity centers require median <=0.5 tile and p95 <=1.0 tile. Do not compare sprite boxes as hitboxes. |
| HUD/elixir | Preserve own four-card hand, Next, fractional elixir, and variant/readiness missingness. A future manual gate should require own-elixir MAE <=0.25; current values are not independently calibrated. |
| Determinism | Repeated seeded Gym runs must have identical projected actor/critic tensors, public-v2 masks, applied actions, rewards, done/winner, and recurrent state, with 100% native ticks and zero fallback. |

For every empirical accuracy gate, use whole replay-disjoint groups, at least 30
examples per represented class/channel, and a 95% lower confidence bound. A
small denominator is `insufficient_evidence`, not a pass.

## Not currently real-data-gatable

- sub-100-ms combat timing, attack windup, deploy delay, collision, pathing,
  hitboxes, knockback distance, and continuous unit trajectories;
- exact unit/tower HP, damage deltas, healing, shields, and building lifetime;
- projectile source/target, flight time, chains, pierce, splash contact, and
  reservation order;
- stun/slow/haste/stealth/readiness onset or duration and hidden RNG;
- exhaustive entity counts/recall, opponent hidden cycle/elixir, and action
  recall outside audited events;
- crowns, winner, terminal reason, tiebreak damage, and outcome distribution.

Until these channels receive independent labels, validate them with serialized
current-client mechanics, bounded invariants, deterministic seeded episodes,
and policy-visible consistency. Python differential behavior is diagnostic,
not the acceptance authority.

## Source artifacts

- `/Users/sam/Desktop/code/clasher/reports/persistent_batch_v1/local_closure_and_causal_gate_20260825.md`
- `/Users/sam/Desktop/code/clasher/reports/persistent_batch_v1/deck_closed_causal_corpus_audit_33games.json`
- `/Users/sam/Desktop/code/clasher/datasets/derived/tv_royale_youtube_persistent_batch_causal_clocked_20260825`
- `/Users/sam/Desktop/code/clasher/reports/tv_royale_data_quality_and_expansion_20260817.md`
- `/Users/sam/Desktop/code/clasher/reports/tv_royale_youtube_bulk_readiness_gate_20260817.md`
- `/Users/sam/Desktop/code/clasher/reports/tv_royale_portable_clock_precision_repair_20260817.md`
