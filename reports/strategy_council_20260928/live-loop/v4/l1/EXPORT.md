# T7 Mac export and runtime handoff

No Mac command was run. Fleet CUDA timing is not a Mac/ANE latency result.
`export_v4.py` exports two TorchScript modules on CPU and tests their reloaded
outputs against eager mode, including padding changes and 1.2s gaps.

- `frame.pt`: arena BGR float32 [1,3,832,448] and HUD atlas [1,3,64,448], scaled
  to [0,1]. Returns stride-16 features [1,64,52,28], body identity/side logits,
  normalized weak boxes, HP fraction and confidence, five card distributions,
  elixir digit/fraction, clock and phase. `FRAME_KEYS` fixes output order.
- `event.pt`: [1,16,64,52,28] cached features, [1,16] age in ms, bool valid mask,
  [1,2,64,36] pixel-derived birth counts. Returns card-side heatmaps, age, sigma
  and five cast-origin channels per side. `EVENT_KEYS` fixes output order.
- Coordinate grid is 36 columns by 64 rows, half tiles. Owner 0 is opponent,
  owner 1 is own, preserving native absolute orientation. No label file is an
  inference input. Raw head output is not a calibrated event probability.

Mac qualification, to run later in a separately authorized quiet-host window:

1. Transfer selected checkpoint, source, vocabulary, frozen calibration/threshold
   JSON and TorchScript modules, each checksum verified. Do not export shakedown
   weights as a qualified model. Create an isolated CoreML tools environment and
   record exact Torch/CoreML tools/macOS versions; do not change the fleet env.
2. Convert each traced module with CoreML `convert_to="mlprogram"`, fp16 compute,
   named static TensorType inputs. Convert masks explicitly to the supported
   bool/integer input representation and preserve masked-token invariance.
   Export `frame.mlpackage` and `event.mlpackage`; record conversion warnings.
   Attention is explicit matmul/softmax, not a fused SDPA operator; LayerNorm,
   GroupNorm, dilated convolution and interpolation still need conversion checks.
3. Compare float32 eager, TorchScript, fp16 CoreML CPU and CoreML ALL outputs on
   at least 100 validation windows. Test empty/partial histories, irregular gaps,
   all masked tokens, 32-frame wraparound, multiple events and own spell
   corroboration. Report per-output errors and event/board decision disagreements;
   conversions with nonfinite outputs or mask-dependent padding are rejected.
4. Keep the 32-frame feature cache and association/NMS/isotonic calibration on
   the host. The last 16 actual frames enter the head; never clear on a time gap.
   Cache is ~182KiB/frame fp16 (~5.7MiB/32 frames); full T16 input is ~2.84MiB.
   Avoid copying raw frame batches to the temporal model at runtime. If event
   attention falls back to GPU, benchmark hybrid CoreML-backbone/MPS-head too.
5. Benchmark with the pinned renderer emulator running: warm up 200 frames, then
   >=2,000 timestamped replay frames through decode, two packages and fusion.
   Record p50/p95/p99 per stage, processed FPS, queue age and end-to-end completion
   time. Required perception p95 <=40ms; total loop >=18 FPS and frame-to-tap
   p99 <=400ms remain T5/T9 integration measurements. Do not infer these from
   A6000 throughput or isolated model invocation.
6. Fallback: TorchScript/eager on MPS with exactly the same cache, masks and
   outputs. Re-run parity and the emulator-on latency gate. If neither passes,
   report BLOCKED and optimize using validation; do not change heldout gates.

`PixelPerception.step` is the pixel-only reference ABI for P1. It emits tracks,
raw own HUD and event candidates with top-three card mass, existence q, execution
time and sigma, and availability including measured FIFO completion by default.
A production driver should timestamp actual completion and hand candidates to
P2's additive contract adapter. It must not label raw HUD as tracked own state or
claim S3/T8 derived-state gates. The tracker is a basic high/low confidence
association baseline; S3's opponent-state repair is separate work.
