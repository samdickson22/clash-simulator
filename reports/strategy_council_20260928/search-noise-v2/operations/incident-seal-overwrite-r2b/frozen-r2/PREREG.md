# S1: event-likelihood tracking and multiple-root search

Final protocol. It becomes frozen at sealed_unix in evaluation-manifest.json. No confirmation games may start until that manifest exists and all required preflight receipts pass. The manifest hashes this document, schedule, analysis, player, noise model, runtime and native extension. All arms share that frozen runtime throughout confirmation.

## Question and gates

Primary: E4 minus B at N64 against C56 scripts. Success requires the lower endpoint of the paired-matchup 95% bootstrap interval to exceed zero.

Event gate: choose the lowest level in {90/90,97/97} with E4 minus clean A point estimate at least -0.05 and lower 95% endpoint strictly above -0.10. Never select below 90/90. If neither passes, retain the provisional 95/95 gate and require further decision-side work before L2-v4. These are the two ordered design endpoints, not a search over new thresholds. Family results, especially Hog 2.6, are descriptive.

## Engine scope

The Linux extension has known rare native parity defects. In the Stage 5 planner gate, Electro Spirit chain targeting excludes spawn-staggered targets and diverges from Python at one of 200 recorded roots. A Fisherman seat-1 defect exists in the broader Stage 6 scope. The same Electro Spirit failure reproduces on frozen Mac build 42. The coordinator explicitly authorized S1 to proceed on this build because all arms share it. This overrides DESIGN's original requirement to wait for the native parity repair. It does not establish native/Python parity.

Linux extension SHA256: 830fcc54cee623da0e9db021d943a7043474f08faa8e677e21d360c266b962fd. source-copies.json records exact Python/runtime hashes and Rust source pins. No engine source is edited. The complete private runtime is sealed; later coordinator engine fixes cannot change an active study. Python advances the actual match, as in search-noise; the pinned native extension scores model rollouts in every arm.

## Schedule and populations

The primary matrix has B, E1, E4 and E4R at N64=180/280 recall and 180/270 precision, N90=.90/.90, and N97=.97/.97, with other channels at frozen predecessor noise and target latency. Clean A is a separate script cell. Each cell has 128 paired matchups, two seats each, 256 games.

Secondary E4/N90 cells use old latency, empirical L2 latency, first-attempt tap failure .10 and .60, and 10% body identity confusion within type. Target latency reuses the primary E4/N90 cell rather than launching an identical duplicate. Three head-to-head cells, B/E4/E4R at N64 versus clean A, each use 64 fresh paired matchups and two seats. Total: 18 script cells times 256 plus 3 head-to-head cells times 128 = 4,992 games. The design's approximate 5,100 count included a repeated target-latency cell; this protocol avoids counting that cell twice.

Script matchups balance seven predecessor families, with counts 20/18/18/18/18/18/18. Head-to-head counts are 10/9/9/9/9/9/9. Deck roles, train-only opponent prior and heldout support filtering follow search-noise/register.py. Script styles cycle balanced/pressure/defense. Seats swap decks for script comparisons. All arm comparisons share worlds, deck orders and channel seeds within matchup; scripts and head-to-head use separate worlds.

Confirmation world seeds are 7612000001+1009*i and sensor seeds 8612000001+1009*i for i=0..191. Planner and posterior offsets match the predecessor. Additional latency/failure streams use noise seed +500/+501 and +700/+701. Seed audit scans previous report seed fields, text and NPZ metadata. Pilot seeds are in the separate 76107/76108/76109/76110 development blocks and never enter confirmation. Schedule/bootstrap RNGs are 7611100001/7611100003.

## Arms and computation

B uses the frozen 1,024-particle v3 posterior and one draw. E1 uses ELT and one root. E4 uses four stratified ELT roots. In every ELT arm, if one hypothesis has at least .9 mass, all roots use it while independently completing unresolved identities and RNG. Otherwise roots use stratified posterior draws, with one stratum for E1. E4R adds a fifth root from the weighted q90 opponent-elixir hypothesis. A uses exact public derivation and clean inputs. All use the C56 balanced/pressure/defense mixture, horizon 160 ticks and interval 10, with identical public candidate generation.

budget.json records one Mac pilot calibration: the median number of candidate-style rollouts completed in 200 ms, using one native thread. The resulting total per-decision budget is 63. Every retained action receives all three styles at every root; retain the first floor(63/(3*K)) candidates, with K=5 for E4R. Thus the cap permits 21,21,5,4 candidates for B/E1/E4/E4R, subject to available candidates. Candidate order is the existing script choice, no-op, script top-four, optional ability, then random proposals. Unused indivisible budget is not reassigned. This compares complete multi-root action estimates under a common total budget; it also changes action coverage, which is an interpretation limit. No Linux wall-clock deadline changes action selection.

Public packets arrive every two ticks. Nominal searches occur every ten ticks. E arms additionally search on a newly delivered event, with a four-tick minimum between event-triggered searches. All arms allow one outstanding command. This is the S1 controller cadence, not a literal replay of the predecessor's 200-ms search cadence.

## ELT implementation

Each hypothesis retains the C56 exact public ledger and finite deck/order support. This is the Stage 5 extension of srp-public; it quotients the unobservable initial hand-slot permutations, preserving the public hand multiset and ordered cycle exactly. The beam retains 128 hypotheses. Candidates branch into accepting the top identity, accepting a second identity with probability at least .15, and rejecting a false positive. Equivalent support/ledger states merge by summed probability. Impossible branches are removed. One legal latent missed play in the preceding gap can repair a cycle contradiction, with the frozen validation-selected missed-play rate. A missed spend cannot repair insufficient elixir.

The existing synthetic event channel emits point card identities. Its player adapter therefore supplies a singleton card distribution; the top-two API is unit-tested but is not exercised by this noise model. Existence calibration uses the frozen validation-only per-card probabilities. N90/N97 apply an explicitly assumed prevalence odds shift relative to 2:1 correct/false odds; no confirmation observation fits it. Miss rate uses the same validation selection. No heldout strength result tunes ELT.

Noisy execution time is arrival minus two ticks, clipped to a monotonic estimate, with sigma zero in the legacy event adapter. This is a fixed age-estimation assumption, not a trained v4 age head or true execution timestamp. The ELT API also supports timing quadrature for nonzero sigma. At q=1 with exact timestamps, the replay preflight must match all 24 original srp-public full games, preserving their original terminal equality assertions.

Own pending commands optimistically spend and cycle a copy of public own state. A public own-HUD cue after execution reconciles it, including rollback on a rejected command. Recent verified own state supplies the model between stale images. The simulator's one-tick verification cue is an explicit idealization; it is not the v4 pixel verifier. It never exposes opponent state.

## Noise, latency and taps

Body, HP, HUD and event corruption reuse the predecessor model. Event quality scales recall, precision and proxy confusion rates. Missing HP remains the predecessor's 50% point estimate. The identity cell changes 10% of detected non-tower troop/building tokens to another supported token of the same type; other features stay fixed.

Target sampled observation age is four ticks on 98% of polls and eight ticks on 2%, giving 200-ms median and 400-ms p99 before polling quantization. Old latency uses the predecessor's 150-ms image lag plus a fixed 100-ms command delay; timing is independent of host load. L2 delay resamples the completed study's production_to_action_ms field, quantized up to engine ticks. latency.json records the full empirical sample and source hashes. At each poll the sensor selects the newest captured packet no newer than the sampled age. This avoids artificial FIFO blocking under variable delay. Own state and board can be stale; the elapsed clock and arrived event stream remain current. This allocation of total latency to image age is a modelling choice, not an identified decomposition.

Failure cells reject the first command attempt with the declared independent probability, then retry the same action once after 150 ms. Ordinary illegal/unaffordable rejections also remain in the data. No unlimited retries or outcome-dependent exclusions occur.

## Fair information and preflight

The player accepts detached public packets, own HUD and publicly visible events only. Exact opponent elixir and any revealed hand/cycle consequences are permissible derivations. Non-privilege tests vary only unresolved opponent identities/order and simulator RNG; they do not demand invariance to changes in publicly derivable elixir. Scoring-only truth diagnostics must not alter beliefs, actions or RNG. Unit tests cover exact ledgers, contradictory candidates, second identities, parent isolation, deterministic sampling, pending command reconciliation and noise rates.

Pilot runs use separate seeds and emit timing/resource diagnostics only. No aggregate pilot strength is inspected. Preconfirmation implementation corrections and technical failures remain logged. The final test receipts, pilot timing, seed audit and fixed schedule must exist before freezing.

## Execution and technical recovery

Only 127x02, 127x07 and 127x08 run games, under nice 10 with one-thread BLAS/native search. Hub cap is 48 workers, peer cap 100, with lower caps allowed for measured memory or console use. Each peer must have smoke-p16-linux-20261007.exit equal to zero. Check who before launch. No work runs on 127x05 or extraction/roader hosts.

fleet_run.sh owns each detached node supervisor, with its lock, log and exit receipt. The supervisor forks workers after loading immutable resources and the exact initial prior once. Each child retains its own worker lock, log, PID and atomic exit receipt. The supervisor records a nonzero child exit if a killed child cannot write its own receipt. A regression test compares shared and uncached prior actions. A fixed global job index modulo the frozen worker count assigns every game exactly once. Worker index to host is frozen in execution.json. A valid terminal receipt must match the complete manifest hash, job identity, seeds, arm and seat. Such receipts are immutable and skipped on resume. Incomplete games restart on identical inputs; their logs/current files are retained. A receipt with wrong identity or hashes is a hard failure, not a reason to overwrite it. After a nonzero process exit, preserve its receipt and use a new attempt label for the same partition. No rerun is triggered by a loss, slow game, rejection count or surprising diagnostic.

No code or engine changes are allowed after freezing. A correctness bug requires stopping confirmation, retaining evidence, and a separately documented new preregistration and fresh seeds. No interim outcomes or strength aggregates are inspected. Monitoring uses process identity, counts, terminal flags, elapsed/CPU time, errors and source hashes only.

## Analysis

Analyze only after all 4,992 valid terminal receipts and every partition's successful exit/done receipts exist. Use 10,000 percentile bootstrap resamples of paired matchup means, preserving both seats and paired arms. RNG seed 7611100003. Report score with win=1/draw=.5/loss=0, paired differences, 95% intervals, primary verdict, event gate, all per-cell results and descriptive family/Hog 2.6 results.

Sum recorded per-game process CPU seconds for compute, separately report initialization/test/pilot overhead from detached logs, and give elapsed wall time and per-host counts. Report actual injected event rates, elixir MAE/coverage/width, tap rejections/failures, search latency and source/receipt aggregate hashes. Preserve raw receipts on the hub; mirror code, manifest, progress, RESULTS.md and result.json to the Mac. No commit and no live-client work.

Seed-audit coverage note: six historical report NPZ symlinks point at removed worktree artifacts. They are listed under unavailable_archives and cannot be inspected again. All available text/seed metadata and all available NPZ archives are audited; the predecessor audit had inspected those historical archives before removal. No positive collision was found. Disjointness claims apply to retained auditable evidence, with this explicit historical coverage limitation.

Timing-calibration scope: budget.json pins the Mac extension used for the one-time pilot, copied from the predecessor runtime. The Linux experiment extension is separately pinned above. Quiet-core isolation on the Mac was not established. The calibration measures an allocation for this study; it does not certify v4 real-time latency.

## 2026-10-08 r2 deviation — lost runtime and replacement fleet

The coordinator authorized this deviation before any confirmation outcome was
inspected. The r1 Linux runtime was lost with 127x02 after its outage around
2026-10-07 23:25 UTC. The recovered copy could not reproduce r1: 8 of 465
manifest-listed files were missing and 32 differed. The r1 manifest remains
253aba47a826e6dbb2d951114d0f7596b0d45bd3eee294d65e6c032c0513c849.
Surviving r1 documents, manifests, runtime fragments and receipts are retained
under r1-archive/. No r1 confirmation receipt is admitted to r2. If 127x02
returns, its r1 receipts must be archived unread and never merged.

Protocol r2 snapshots the current qualified 127x01 source tree into a fresh
isolated runtime. The Linux native extension is
13e908c5cb235a3d81cd585b12caf6c2e5fa624888ed3a3cc0ede14933a5f309,
qualified by the hub's full Linux parity gate at 2026-10-08 00:32:53 UTC.
This build includes the Electro Spirit chain fix and the drafted Inferno
Dragon dash-channel fix. The build change applies equally to every arm.
This paragraph supersedes r1's engine-build and known-defect statements;
the hub gate is not a claim of full Stage 6 admission.

The question, arms, noise/latency models, allocation budget, all 192 paired
worlds, 4,992 games, original seeds, cell allocation, job-index modulo 248
partition, analysis, bootstrap seed and pass rules are unchanged.
execution.json moves only worker indices 0–47 from 127x02 to 127x04.
Indices 48–147 remain on 127x07 and 148–247 remain on 127x08. Maximum
concurrency is 48/100/100 respectively, reduced to four when a console user
is present. 127x01 runs the light collector; 127x05 runs no study compute.
127x04's separate C56 extraction allocation remains capped at 32.

All preflight gates are rerun on this isolated runtime before the single r2
seal: the 24 original full-game replays with ELT exact at every observation
and the original terminal assertions, the 14-test Linux study suite, the
four-child fork pilot, the 18 terminal timing-only cell pilots, and full-game
optimized-versus-slow-reference action-digest equality. The slow reference
performs the documented clone/advance/check path and tries latent repairs
without the optimized rejection short-circuits; it changes no confirmation
code and uses the original pilot inputs. Outcomes are suppressed.
Fresh r2 receipts and source hashes are required; r1 receipts earn no r2
preflight credit.

Operational scripts use the recovered peers' recovery-smoke-127xNN-20261008
receipts and -r2 job labels. Distribution continues to copy manifest-listed
files and verify every peer hash. No confirmation outcome or interim strength
aggregate is inspected before all 4,992 valid terminal receipts and all 248
successful partition exit/done receipts exist. The original technical-rerun
and post-seal correctness-bug rules remain in force. Small audit artifacts,
documents and final results are mirrored to the 127x05 checkout; runtime
binaries and raw confirmation receipts remain on the fleet.
