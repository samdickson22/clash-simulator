# S40 shared-bot contract coordination — 2026-10-16 12:33 UTC

Decision: no conflicting interface edit in this BOT lead's owned work. Accept the existing isolated helper's
frozen API as the coordination direction, subject to the loop owner's integration tests and fresh independent
review. This is not integration, release, host-byte or live-play approval. Loop owner steers its existing helper;
no new workers, shared source edits or competing implementation from this thread.

Owner requirements: `/mpac/sdicks02/scratch/live-loop/diagnostics/s40-r7/REQUIREMENTS.md`.
Frozen helper API: `/mpac/sdicks02/scratch/bot-slot-permission-s40-r1/API.md`.

## Accepted API and model boundary

- Immutable versioned `SlotPermission(allowed4bool, capture_id, poll_tick, reasons4str)`; strict schema as in API.md.
  Append metadata to `ConfidenceAwareActorObservation` and `PublicActionMaskInput` without changing existing
  model arrays, feature dimensions, identities, confidence, logits/probabilities or public state.
- Independent packet capture identity, backend-bound `PublicView.tick`, session-pinned required capability.
  Only explicit legacy mode permits absent/None data. Required mode cannot downgrade after metadata loss.
  A present sidecar is validated even in legacy mode; required missing/malformed/stale/mismatched/exceptional
  metadata yields WAIT-only with a visible reason, not an unobserved fallback to the old contract.
- **Two masks are mandatory.** The owner/helper's actual e4v3 audit establishes that build_row encodes native
  action-mask availability into numeric model features. Keep original native legality `action_mask` unchanged
  through every model_packet/build_row/inference path; derive a separate `eligibility_mask` for choice only.
  Replacing PublicActionMaskBuilder.build's model-facing result with the restricted mask would violate the
  required feature/logit parity. Carry sidecar metadata through the input type; separate the mask outputs.
- Eligibility is native legality AND current four-slot permission, never OR. Only the four playable slot blocks
  are constrained; the extra visible next-card identity/confidence stays untouched. WAIT stays legal; required
  failures disallow ability as specified. Use actual contract constants/mapping, not a newly inferred tile map.

## Integration checks that matter

1. **Capture/poll binding:** validate against the independent current packet capture and backend poll tick,
   not an expected value copied back from the sidecar itself. Session identity/current-frame freshness remain
   enforced by the loop's existing producer/guard rules. A reserved packet copy retains the same capture binding;
   no fresh authority can be synthesized from a synthetic catch-up poll. Do not invent new clock/delay bounds.
2. **Native legality versus selection:** CachedPolicy/StandalonePlayer/R3a inference receives the original mask;
   top-1/top-k/sampling/proposer candidate selection uses current eligibility without modifying recorded logits,
   confidence, probabilities or gate scores. Apply eligibility before ranking/top-k selection, so a denied best
   card cannot erase another legal slot merely by truncating the old candidate list first.
3. **Cache scope:** cached logits/features may remain model-scoped, but cached legal proposals/defaults must be
   re-filtered or keyed by permission capture/poll identity. Existing generic bot/players/variants.py caches by
   D1 and native action_mask; those keys alone do not distinguish changed permission with identical features.
   Check the actual e4v3 implementations and do not copy current main wholesale into its lineage.
4. **Every actual-action route:** fast play, default poller, coarse/proposal generation, student-last/refinement,
   search scoring result, deadline/native/error/exception/default fallbacks and reused frozen actions obey the
   same current eligibility. A cached fallback cannot retain an action denied by the current sidecar.
5. **Model/state preservation and cadence:** both pollers/public events still advance at five-tick cadence even
   with all slots denied. Preserve authoritative/reserved own state, reservation ledger, roots, card IDs and
   confidence arrays. Do not implement an early return that skips D1/event updates, zero IDs, or global can_act
   denial for one bad slot. Packet reconstruction/transport/clone paths must carry metadata; missing required
   fields remain visibly fail-closed rather than silently reverting to legacy.
6. **Real command versus simulated future:** permissions constrain the current externally issued action. Do not
   reinterpret current UI slot permissions as immutable legality for future hypothetical rollout hands, whose
   cards/cycle change. Native timeout/fallback outputs for the actual command are covered; simulated future card
   physics and root/config/state are preserved.
7. **Final guard remains independent:** do not hide a deliberately noncompliant player's denied proposal by
   changing final guard accounting or intercepting the guard's original refusal path. Preserve original proposed
   and chosen/final actions with reasons; the historical FAILED4/28 stays failed. Replay original prefixes only
   until the first intervention; a changed action requires a new real input/rollout trajectory afterward.

## Ownership and acceptance

Loop owner owns producer, original four-prefix controls, integration package, final guard, fresh review, release
gates and concrete paired rollback. Existing bounded backend helper owns isolated actual e4v3 prototype only.
No conflicting edits by this thread to public observation/mask interfaces or bot consumers were found; this
coordination does not claim every other checkout is free of work. Existing experimental level root hooks and
runtime pins must not be overwritten by a wholesale source copy or broad shared merge.

Acceptance still requires explicit legacy parity (including absent/None), required-mode loss/staleness/schema/
exceptions, both model-mask/feature/logit bit parity and changed-choice eligibility, all alternate routes/cache
reuse, all-denied cadence, partial availability, deliberately noncompliant guard counters and r5/r6 transaction
controls. Record actual module/source/runtime paths and hashes of deployed e4v3 consumers; a test importing a
different main/frozen runtime is not evidence. Fresh review/scans and rollback precede any host bytes or release.

No source implementation, test execution, model/runtime/pin change, compute job or live action by this thread.
