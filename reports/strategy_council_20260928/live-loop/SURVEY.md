# Live-client loop: survey and plan (coordinator, 2026-10-04)

Sources: three read-only survey agents (state acquisition; actions and orchestration; policy/decks/engine scope).
Their file-level citations are summarised here; the coordinator wrote this synthesis.

## What exists today

- **No live loop.** Nothing in the repo taps, swipes or reads the screen of the official Supercell client. No match
  has been played against any human or the official server (HANDOFF.md:183,407,704,1292).
- **Screen-only vision (human-visible pixels), offline on recorded spectator video only:**
  - KataCR YOLOv8 detector pair (43.7M params each, 155 labels, April 2024): ~10-11 FPS on the M4 Pro; no held-out
    mAP; stale for the current client (84 of 315 arena classes map exactly; 88 have no class).
  - HUD template extractor (own hand, next card, elixir, play events): 62/62 events on one held-out replay; next-card
    confidence weak. HUD card identity (MobileNetV3 prototypes): 27/27 events on one holdout.
  - Clock OCR: 87/88 on accepted frames but only 88/108 accepted (fails its 99% gate). HP-bar reader: fast, covers
    56-66% of bodies, no labelled error. Visual-state classifier: rejected (mean F1 0.119).
  - `perspective_sanitizer.py` crops spectator footage to a player's view.
- **Strict public input contract:** `live_inference_contract.PublicVisionFrame` + `structured_live_adapter.py`
  (rejects any privileged key; gates: clock MAE <=1 s, placement within 1 tile >=90%, HP MAE <=0.10, status F1
  >=90%). Only ever fed simulator projections (100 traces bit-exact); "not operational" (match lifecycle missing,
  mask stays wait-only). Policy inference 1.4-2.0 ms CPU.
- **Native reference = instrumented private-server client, offline:** Null's Royale 15.535.13 APK (content
  15.535.86), repackaged with an injected probe (`libcrprobe.so`, ~46 inline hooks in libg.so), re-signed, run on
  rooted API-35 emulators with the app's network blocked. Driven over a TCP command channel (configure, step,
  replay-schedule-card, observe, observe-rich, snapshot, render on/off). It reads internal state (both hands,
  elixir, cycle, targets, timers) for simulator validation only; `audit_native_public_boundary.py` strips private
  fields before any actor tensor. It can render matches on screen; a touch hook maps pixels to tiles for a
  1080x1920 layout (the AVD is 1080x2280; not validated).
- **Decks:** P16 runs Hog 2.6 and 39 pilot role decks; C56 adds the common human families (Hog/EQ/Firecracker/MM,
  Royal Hogs/Furnace/Hut, X-Bow, Goblin Barrel bait, Goblinstein, Log Bait Rocket, AQ Royal Hogs). Rust C56 port:
  B1-B4 + repaired cards passed, champions in progress. No evolutions, level-11 nominal, Princess towers only.

## Terms of service and legal status (flag for the owner)

- Automating the official client (taps, screen reading to act) violates Supercell's Terms of Service, whatever the
  opponent; ladder botting additionally harms other players. The project's standing rule forbids live-ladder botting
  and live-client memory readers (owner-mode memory; external_review clashai.md:313,374).
- The native validation reference itself is an unauthorised private-server client, repackaged and re-signed with
  injected code. It is used offline with networking blocked, but running a modified copy of Supercell's client is
  itself a ToS/IP risk. This predates the current work; the coordinator did not create it and has not removed it.
  Owner decision: keep it as an offline validation instrument (current state), or retire it and validate only
  against recorded official-client footage.

## Plan (screen-only, fair information)

The player is srp-pub-mix (search-tuning/RESULTS.md): it needs per-decision public state (units with identity,
owner, position, HP; towers; own hand/elixir/next; opponent revealed plays with times) and emits (slot, tile).
Opponent elixir and hand/cycle are derived exactly from public plays (srp-public/derived_public_state.py).

- **L1 — perception from pixels, offline.** Train a current-client detector and HUD readers on frames rendered by
  the offline native renderer with exact ground truth from `observe` (positions, identities, HP, hand, elixir,
  clock). This yields unlimited labelled frames without touching official servers. Acceptance: the
  `live_inference_contract` gates on held-out rendered matches (and a spot check on recorded official footage),
  >=10 FPS on the M4 Pro.
- **L2 — closed loop on the offline renderer.** srp-pub-mix plays from pixels only (screencap/screenrecord stream ->
  perception -> PublicVisionFrame -> derived state -> search -> tap via adb input on the rendered screen) against
  the scripted opponent. Acceptance: match lifecycle detection, decision latency p99 <= 400 ms end to end, and
  win rate within a pre-registered margin of the same matchups played in the simulator (perception-error cost).
- **L3 — official client.** Training Camp against the built-in AI and private friendly battles with consenting
  people, never ladder. This is outward-facing, account-risking and against the ToS even without harm to others:
  it requires the owner's explicit go-ahead. Everything up to L2 stays offline.

First milestone: the rendered-frame dataset generator and the detector/HUD evaluation harness (L1).
