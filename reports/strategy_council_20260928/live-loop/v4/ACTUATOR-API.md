# T2 actuator interface

The pinned renderer has not passed the full 600/800 ms lifecycle gate. Read T2-RESULTS.md and actuation/candidate-config.json before integrating this into T5. The pure state machine is implemented; its short verification and reservation deadlines remain the approved design values.

`actuator.Actuator` accepts only pixel-derived `Hud` values, chosen card/cost/tile and host monotonic time. `submit()` returns `tap` or `blocked`. It remaps the chosen card to the latest slot and reserves the cost immediately. `effective()` exposes the spend and optimistic slot change to the belief process. `observe()` returns `pending`, `accepted`, a single retry `tap`, or `failed`. A retry uses the same reservation. Failed commands hold their card for one second.

P4 must call `observe()` for each new HUD frame, execute each returned `tap` once, and return terminal results to P2/P3. Do not use a probe to verify an action. Transport timeout is ambiguous and must enter verification rather than an immediate resend. The caller serializes state-machine calls; one command may be pending.

`input_channel.GrpcInput(port, proto_dir, discovery)` opens one authenticated emulator gRPC channel. `play(slot, x, y, delay)` sends the card and tile taps and returns command-submission duration in milliseconds. Its coordinates match the pinned L2 touch hook. `close()` closes that channel. The module has no probe or evaluator imports. `common.GrpcInput` is an evaluator-only ownership adapter and must not enter the pixel player.

`Hud.produced_at` is host monotonic time. Capture production epoch timestamps must be converted using a contemporaneous wall/monotonic anchor before constructing it. A HUD older than 60 ms cannot submit a new action. Current hand, next card and own elixir are the only state exposed to the actuator.
