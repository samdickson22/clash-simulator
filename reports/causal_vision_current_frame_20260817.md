# Current-frame causal vision contract — 2026-08-17

## Scope

This pass separates current camera evidence from match state that must live
inside the exported model. It uses local bounded replay samples only. No model
training, sustained detector run, simulator benchmark, or GPU workload ran.

Production inference may receive the current public frame and detector/OCR
confidence. It may not receive simulator card-play history, a Python-maintained
cycle/elixir accumulator, externally carried HP, predicted occluded positions,
or externally deduplicated play events. Those temporal operations belong in the
model recurrent state.

## Implemented

- `CurrentFramePublicSignals` validates one strict runtime payload. It rejects
  nonzero opponent history/seen-card arrays and externally tracked motion.
- `VisibleBattleClock` retains one visible OCR reading and confidence. The pure
  parser accepts regulation and `OT`/`Overtime` timer strings and fails closed
  on malformed times. An actual image-to-text clock detector is still missing.
- `CurrentFrameDeploymentCue` clusters current in-arena deployment-marker boxes
  for either player. It exposes centre, detector confidence, support, and visual
  extent. Detector boxes and extents are explicitly not collision hitboxes.
- `CurrentFrameCardPlayCue` conservatively associates one marker with one unique
  co-located visual card identity. Ambiguous identities emit nothing. A marker
  that persists across frames emits repeated current evidence; only model-owned
  state may deduplicate it.
- `CurrentFrameCombatCue` defines the current-frame attack/status evidence
  contract without inventing remaining timers. The actual attack/status
  classifiers are not implemented yet.
- UI hand and elixir template match scores now survive as confidence rather
  than being silently promoted to exact confidence one.
- The local player's visible fifth slot is now correctly treated as the public
  Next card. The real-play validator previously rejected it as hidden.
- A current-frame Next-icon baseline retains both absolute match score and
  runner-up margin and fails closed on ambiguity. On the visually inspected
  validation frame 625 it correctly returned `royal_hogs`, but with deliberately
  low confidence `0.1977` (`0.2391` best score, `0.1564` runner-up). This is a
  baseline, not a production-quality detector.
- `infer_offline_next_card_labels` uses the card that refills a just-played hand
  slot to label the earlier visible Next icon. This consumes a future frame and
  is explicitly training/audit-only; it never mutates runtime frame state.
- `TVRoyalePlacementConverter.public_observation` can now accept a directly
  observed `raw_next_card`; older corpora remain missing rather than fabricated.

## Visual audit

Combined current-frame HUD and deployment-grid audit:

`/Users/sam/.codex/visualizations/2026/08/05/019fd3ea-23fc-7453-b38e-4399dafde4c4/vision-audit/current_frame_and_spatial_contract.jpg`

The left image marks the visible local timer, hand, Next icon, and elixir. The
top opponent HUD exists because the source is a spectator replay and is marked
for exclusion from live actor input. The right image shows an already recovered
Bowler deployment: rectangles are detector sprite bounds; the cross is the
deployment-marker centre; neither is a gameplay hitbox.

Source files visually inspected:

- `/Users/sam/.codex/visualizations/2026/08/05/019fd3ea-23fc-7453-b38e-4399dafde4c4/vision-audit/raw_frame_00625.png`
- `/Users/sam/.codex/visualizations/2026/08/05/019fd3ea-23fc-7453-b38e-4399dafde4c4/vision-audit/next_crop_00625.png`
- `/Users/sam/Desktop/code/clasher/datasets/derived/tv_royale_raw_cascade_1000_v1/games/arena_23/b4b4602c-ab60-4d90-844d-c9012a0ba760/audit/001_frame_00625.jpg`

## Critical gaps found outside the narrow implementation

1. `load_public_observation_sidecar` can retain the base corpus's exact
   simulator `action_masks` when a sidecar omits masks. Inspected published
   schema-v2 sidecars omit them.
2. The same loader does not overlay or clear opponent history/seen-card arrays,
   so simulator `BattleState.public_card_play_history` can survive a public
   sidecar overlay.
3. Both sidecar builders set the demonstrated expert action legal in the actor
   input mask. That label-conditioned mask must become separate loss-only
   metadata.
4. `causal-vision-v1` carries tracks, HP, hand, and towers outside the model.
   It remains useful as an offline teacher but does not meet the deployed model
   packaging contract. Production should use current-frame extraction.
5. The replay's timer globals are currently calculated from source frame index,
   not read from the visible timer. Trimming/re-timing a replay can therefore
   shift the supposed game state.
6. Static card stats and public action-mask logic still perform runtime card
   data lookups. Under the self-contained-model rule, those values must be
   encoded in model parameters/buffers or learned card embeddings.

## Remaining vision work

- Train/calibrate image-to-text public game-clock recognition and test that
  identical rendered clocks at different source indices produce identical
  readings.
- Replace the low-confidence Next template baseline with a calibrated small
  classifier using the offline refill labels; retain current-frame-only input.
- Create a manually labelled held-out opponent-play set covering both sides,
  varied arenas, spells, swarm/spawn cards, and repeated cards. Measure event
  precision/recall, duplicate rate, timestamp error, and missed-spend rate.
- Add current-frame attack-animation and visible status classifiers. Their
  outputs should be presence/onset cues; remaining durations belong inside the
  model.
- Version a strict public schema that requires sensor origin, current-frame vs
  offline-teacher mode, detector/template hashes, public-only masks, and exact
  array presence.

## Validation

- Ruff: clean on all touched source/tests.
- Mypy: clean on the four touched RL modules.
- Focused tests: `49 passed in 0.90s`.
- Wider public/causal/next-card selection: `43 passed, 90 deselected in 2.28s`.
