# L1 v3 real-stream experiment

Certify the unchanged renderer's continuous 1x capture before collecting training
samples. Log monotonic request brackets and returned native ticks, screenshot
production timestamps and host arrivals. Fit offset and drift with held-out timing
anchors. Independently compare visible clock transitions and known deployments.
Keep interval uncertainty; an affine fit alone cannot certify compositor ticks.
If timing cannot be certified, record the measured blocker and do not label a
large dataset as certified.

Use at least 3,000 accepted deployments over P16 and renderer-supported C56 cards,
both seats, varied seeds, decks, placement and phases, with explicit negative
windows. Split seeds and deck multisets before collection. Use sanitized 540x1140
JPEG or H.264 continuous frames near 10 FPS. Native observations and commands live
in evaluation-only metadata and never enter inference. Hold out complete matches.
Freeze model and threshold choices on validation before the final stream score.

Fuse persistent body-track births, grouped multi-unit cards, known spawner and
death-spawn exclusions, temporal spell visuals and own HUD transitions. Derive
opponent elixir and hand/cycle using only public events and visible time. Retain
miss and false-positive hypotheses and expose a sampleable distribution. Evaluate
elixir mean MAE, interval coverage and width, and hand accuracy with concentration
coverage. No calibration claim from a wide interval alone.

Acceptance requires correct-card causal events within 500 ms with recall and
precision >=90%, placement within one tile across all truth >=90%, elixir MAE
<=0.75 with calibrated uncertainty, and >=90% hand accuracy when concentrated.
Unmeasured gates fail admission. L2 remains blocked unless all required gates pass.

One owned emulator initially, at most two overall. Verify IPv4 and IPv6 game UID
egress rejection before app use. Keep new data <=2 GiB and live-loop <=5.5 GiB,
with host disk reserve. No protected paths, probe/APK or engine edits, no foreign
process signals, no Git mutations. Detached jobs use the supplied detach.sh.

## Pre-fit amendments

The installed probe does not support the newer rich-telemetry cursor command.
The collector instead admits an ordinary observation only when started and
completed step counters agree before and after the read and native identity is
unchanged. This proves observation consistency, not compositor timing.

Protocol 2 records command schedules immediately and retains 700 ms of final
video. Primary validation and heldout scoring require protocol 2. Protocol 1
training excludes its last second; its validation/heldout data stay diagnostic.
This eligibility change preceded model fitting and heldout prediction inspection.
The additional collection plan stops at a completed episode once 3,000 accepted
deployments and every frozen validation/heldout match are complete.

The temporal model adds arena-wide context for distant projectile/target cues.
Spell ownership combines visual identity with a 150 ms causal own-HUD buffer.
Clock-to-placement offsets use training frames only. Validation selects a global
threshold and per-card thresholds where at least five true validation plays
exist. Heldout predictions never change weights, thresholds or these rules.

A nominal 90% elixir interval is checked against an 85-95% coverage band, with
its width reported. Validation's residual distribution calibrates the predictive
elixir marginal and its sampler while preserving rank dependence with hand
hypotheses. Hand accuracy requires nonempty concentration coverage. Native truth
is read only after predictions freeze, at one-second query times. Scoring uses
only predictions completed by each query time and includes measured inference
latency in the event deadline. These choices are fixed in config.toml before fit.

A late-stream reader starts with a generic unknown deck/hand and bounded elixir
prior at the first visible clock; it does not simulate invented plays through
unobserved warmup time. The red clock background identifies overtime. White
foreground segmentation avoids mistaking that background for clock digits.

State-filter event reliability is fitted on opponent events only, using a
separate two-second identity match window. Correct late evidence still informs
state even when it fails the unchanged 500 ms event gate. Matching stays
one-to-one, so duplicate predictions do not become additional accepted spend.
The primary event recall/precision/placement gates always retain 500 ms.

Availability includes FIFO backlog: each output becomes available at the later
of its frame arrival and the previous output completion, plus measured processing
time. A detector slower than the recorded stream cannot get an optimistic
500 ms score by resetting its processing clock for each frame. This is an
offline scheduling estimate; concurrent capture, perception and search still
require a separate closed-loop measurement.
