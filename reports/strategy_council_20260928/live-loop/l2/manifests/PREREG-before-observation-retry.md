# L2 preregistration

This protocol precedes every evaluation match. Setup, tap calibration, player smoke tests and terminal-screen probes use separate seeds and are excluded. The frozen schedule contains 48 seed-matched pairs, 16 each for Hog 2.6, X-Bow cycle and Royal Hogs spawners. Balanced, pressure and defense C56 scripts each appear in 16 native matches. Seat 1 is always the pixel player because L1 reads the bottom HUD. Hog uses the P16 mixture player; the other families use the C56 deadline search. No champions or abilities are selected.

## Inputs and controllers

The actor accepts sanitized 1080x2280 emulator screenshot streams downsampled by the existing L1 sanitizer to 540x1140, capture timestamps, public card metadata and an independent planning seed. L1 v3 weights, HUD templates, validation thresholds, event reliabilities and residual distribution are frozen. Probe state never enters the actor. The opponent and evaluator may read the probe. Original PublicVisionFrame values and confidence are retained in compressed logs.

Both existing public script controllers reject every uncertain input. L2 therefore explicitly constructs a separate conditional point model for script scoring; confidence-one fields on that model mean exact conditional values, not certain perception. Missing body HP uses its last measured value or a full-health prior. King HP is always unmeasured by L1. Detected entities are retained at their predicted positions and identities. Own unseen queue cards are sampled from public card metadata, constrained by previously seen own cards and visible next. Opponent uncertainty uses the v3 joint posterior, 1024 particles, validation missed-play rate and residual correction. These are declared L2 adaptations, not previously certified behavior. No engine or probe guard is edited. The baseline consumes clean simulator public state and exact public-event derivations. Thus the comparison measures the whole adapted pixel loop, not event recall alone.

Search has a 200 ms cooperative deadline. C56 keeps its existing two-worker cutoff. P16 checks the deadline between native rollouts and discards partially scored candidates. Native player and opponent decisions are targeted every 500 ms of wall time at 1x renderer speed. Simulator decisions target every 10 ticks. The opponent's native command uses an eight-tick lead to avoid the observed scheduling race. Timing/engine differences remain explicit confounders; this is not a causal estimate of perception alone.

## Action and lifecycle

The player uses adb input taps through the existing native touch hook. The hook retains its 1080x1920 input coordinate system on the 1080x2280 display. Calibrated visible-coordinate taps failed; hook-coordinate taps deployed the selected Log and changed hand/elixir. No probe player-action injection is planned. The opponent submits only its chosen action via replay-schedule-card.

Matches configure their registered native seed/decks, warm up without actions to tick 220 so the intro clears, then run continuously at 1x. Pixel lifecycle identifies running clock/HUD and ending by at least 700 ms of absent clock and absent own elixir bar. This is provisional and must be checked against evaluator-only terminal receipts. Pixel result reading is not certified; the native terminal winner is the outcome label for offline evaluation. Failure to read the result from pixels counts against L3 readiness. Full native terminal receipts are mandatory for match inclusion.

The paired simulator uses the same seed, deck multisets and the native opening hand/queue order copied by the evaluator, with the same no-action opening. This setup information never reaches the pixel actor. Clean simulator and native are distinct engines and RNG implementations. Completed native and simulator outcomes stay paired; no outcomes are dropped for poor play, rejects, timeouts or detector failures. Infrastructure interruptions retain their partial logs and stop the run for repair; any replacement protocol must be dated before new games.

## Outcomes and gates

Primary: native pixel win proportion minus clean simulator win proportion across the 48 pairs, with a two-sided 95% percentile bootstrap CI using 10,000 resamples within each family, RNG 1967100103. Each native/simulator seed pair is resampled together. Draws count as zero wins; report wins/draws/losses and score with half credit for draws separately. Family/style splits are descriptive. The preregistered noninferiority margin is 10 percentage points; require the paired CI lower bound >= -0.10, all 48 complete pairs, and no actor truth leakage.

Timing: production timestamp to completed action submission, plus receive-to-submission separately, p50/p95/p99/max. Report both all decisions and non-wait deployments. These timestamps measure screenshot production, not certified compositor-to-native-tick timing. Search, tap time, stream gaps, actions per game minute and per wall minute are separate. Search deadline violations and end-to-end p99 >400 ms fail readiness.

Action rejection: evaluator-only hand-slot disappearance/change and elixir-spend evidence in the first stable post-submission observation, compared with the last stable pre-submission observation. Unresolved or overlapping windows remain unknown rather than accepted. Report submitted, confirmed, rejected and unknown counts. A wrong perceived card versus the actual slot is a distinct perception failure even if adb successfully deployed that slot.

Failure analysis compares frozen predictions and choices with evaluation-only truth after the run. Report own-hand/elixir mistakes, missed opponent deployments, missing/misidentified bodies/HP, command rejection and lifecycle errors. Individual examples are associations, not counterfactual causal proof. No model fitting, threshold tuning or deck/style changes after evaluation begins.

L3 readiness requires full paired completion, the noninferiority and timing gates, successful pixel lifecycle/result reading, and a reliable uncertainty interface. L1's previously failed timing certification and perception gates remain unresolved and cannot be overturned by this experiment alone.

## Resources and preservation

One owned offline read-only emulator, networking blocked for the game UID, no official client. At most three owned heavy processes: emulator, native capture/perception/search worker, and one simulator worker. All long workers launch via pilot/detach.sh. Persistent L2 files stop growing at 900 MiB, below the 1 GiB cap. No engine, gamedata, engine-rs, pilot or c56 edits; no Git mutations or foreign-process signals. PROGRESS.md and per-match receipts support resumption.

Pre-evaluation clarification: the provisional pixel result reader uses visible surviving King/Princess counts and explicitly returns unknown for equal counts. Its output is computed before reading the terminal label, logged separately, and scored for correctness/abstention. It is not certified for tiebreaks. No result label is used for actor decisions.

## Transport replacement registration, before run 2

Run 1 stopped during its second native game when the adb executable aborted with SIGABRT after repeated active-gRPC fork warnings. One native terminal and two simulator terminals, the partial native second game, all logs and the original registration/source files are retained under interrupted-r1. Their win/loss outcomes were not inspected for selection or tuning. None enters run 2's primary estimate.

Only the action subprocess launch changes: close_fds=False with an absolute adb executable selects CPython's macOS posix_spawn path and avoids forking active gRPC/MPS threads. This follows the existing L1 stream collector's documented fork precaution. Player, perception, uncertainty assumptions, decks/style allocation, budget, analysis and gates remain unchanged. Run 2 uses 48 fresh seeds starting at 1967150031 with stride 1009, disjoint from run 1. Its seed audit and replacement manifest precede every new game. Only the owned waiting simulator worker was stopped; the original emulator remains owned, paused and offline.

## Read-only forward recovery amendment, before resumed pair 5

The second run completed five native and six simulator games before the host adb forward disappeared during native pair 5. The emulator and app remained alive, and restoring the same owned mapping immediately restored the probe. No win/loss outcomes were inspected. Completed receipts remain primary evidence; recovery-forward retains the incomplete native trajectory. Pair 5 is replayed from its registered seed, with its opening hand/queue checked against the preserved setup before reusing its clean simulator receipt. No completed outcome is replaced.

Read-only probe requests now have at most three reconnect attempts. The driver may restore only the exact owned serial/port mapping, uses --no-rebind if it is absent, and refuses any conflicting owner. A mutation is retried only on connection refusal before delivery; a lost mutation response is never blindly repeated. Player/perception code, priors, deadlines, seeds, decks/styles, outcome definitions and gates are unchanged. The original and amended manifests remain under manifests/, and each game names its actual source manifest. This is an infrastructure repair, not a strength-selected rerun.

## Startup lifecycle correction, before the next pair-5 attempt

The first reconnect replay passed exact opening equality, then stopped at native tick 235 after three frames of a delayed intro banner. It made zero player decisions and produced no result receipt. recovery-startup preserves that startup-only attempt. The end-cue rule now requires that a running match has previously been detected from pixels. This implements the declared start-then-end lifecycle and prevents an unstarted intro from being called terminal. All completed games, controller/perception settings and registered worlds remain unchanged; only the incomplete seed is retried. Its opening equality check remains mandatory. The source version is retained in manifests/r2-startup.json.
