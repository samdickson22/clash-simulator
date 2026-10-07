# T2 actuation results

Verdict: blocked on the pinned renderer's verification latency.

447 retained factorial trials; 12/16 cells present. Full matrix complete: False.

| Method | Trials | First acceptance | Two-tap p95 | Pixel detections <=600 ms |
|---|---:|---:|---:|---:|
| grpc | 320 | 320/320 (100.0%) | 26.91 ms | 0/320 |
| adb-spawn | 127 | 127/127 (100.0%) | 59.79 ms | 0/127 |

grpc: 316/320 detections within 600 ms of the probe's first observed acceptance; pixel-minus-native observation p95 39.92 ms. The probe poll is an observation-time upper bound, not an exact touch execution timestamp.

adb-spawn: 126/127 detections within 600 ms of the probe's first observed acceptance; pixel-minus-native observation p95 36.51 ms. The probe poll is an observation-time upper bound, not an exact touch execution timestamp.

The candidate transport is persistent emulator gRPC touch injection, with four RPCs per card-plus-tile action and no per-tap subprocess. The matrix compares 0 and 20 ms inter-tap delays, 3 and 24 native ticks since the previous own deployment, and 0.1 and 1.0 actual elixir margins. Actual margins are measured and checked within 0.06 elixir. The adb baseline starts one host process for each tap. The pinned hook uses the L2 1080x1920 tap map even though screenshots are 1080x2280.

No transport is qualified for v4 production. Native acceptance arrives roughly 1.1 seconds after submission. The attested hook formats a touch command at current tick + 2 and adds the 20-tick live-command age. Faster tap delivery does not remove that delay. The 600 ms verifier and 800 ms reservation timeout cannot be admitted against this backend. The coordinator must decide whether to approve a new attested touch shim or amend the renderer-only timing contract. This worker changed neither the APK nor the pinned hook.

`actuator.py` implements fresh-HUD slot remapping, one outstanding command, optimistic spend/slot reservation, dual HUD verification, at most one retry after 150 ms, rollback and a one-second card hold. Its unit tests cover stale frames, remapping, false confirmations, retry limits and holds. It must remain unintegrated until the timing mismatch is resolved.

Stale re-tap and specificity experiment not yet complete.

## Provenance and limitations

Renderer: host GPU, two cores, 3 GiB, read-only AVD emulator-5584; adb 5042, gRPC 8558, probe 26794. Attestation SHA256 `864227bf7208aa9c06cd976db3fa0734a32277b0552f92e496ad283a917b4a93`. IPv4 and IPv6 app-UID egress rejection was verified. Other projects and Stage 6 jobs remained running.

Raw trials are in `actuation/trials.jsonl`; setup schedule receipts and actual elixir margins are retained in each row. Development attempts with an intro overlay and unmanipulated margins remain in separate `development-*-trials.jsonl` files and do not enter the matrix. Later trials reuse a live match during setup and reset at tick 1600 or terminal. Setup uses 4x stepping, measured taps and verification use 1x. Pixel HUD uses the retained v1 reader; v3 weights are not required.
