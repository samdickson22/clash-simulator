# S2: channel decomposition and ELT diagnosis

Protocol written before any S2 game, including development pilots. Confirmation is forbidden until this document and all executable inputs are frozen in evaluation-manifest.json and preflight passes. No S2 outcomes will be inspected before all 3,584 identity-valid terminal receipts, all successful partition receipts and both successful supervisor receipts exist.

## Population, runtime and seeds

14 cells share 128 paired worlds, both seats (256 games per cell). C56 scripts cycle balanced/pressure/defense. Families: Hog 2.6 (20 pairs), Hog EQ/Firecracker/MM, Royal Hogs/Furnace, X-Bow, bait, Goblinstein, AQ (18 each). As S1, planning decks come from eval/eval_ood roles restricted to train-supported decks, weighted by role frequencies; opponent decks and the prior are train-only. Deck order is shuffled by the fixed schedule RNG. Seats swap decks exactly as S1. No head-to-head cells.

S1 r2 runtime copied byte-for-byte from manifest 3ad63c0a7ad1634bac32bf5b031a7a312013497d8863aeaa3b0e2b0e077e5677. Native SHA256 13e908c5cb235a3d81cd585b12caf6c2e5fa624888ed3a3cc0ede14933a5f309. No engine/gamedata edits. Python advances games; Rust scores fair reconstructed roots. This is not new native parity or live-client certification.

Confirmation world seeds: 9712000001+1009*i; sensor seeds: 9812000001+1009*i, i=0..127. Planner seed world+100000+seat; sampling seed planner+1; legacy posterior seed planner+2. Channel streams are SeedSequence([sensor+seat,channel_index]) for board/HP/HUD/events; latency sensor+500+seat; taps sensor+700+seat. Seeds are shared across cells within each matchup. Schedule RNG 9711100001; bootstrap RNG 9711100003. Development worlds 9710800001+1009*i and sensors 9810800001+1009*i, i=0,1,2, with the same offsets, are disjoint from confirmation. Pilot uses development pair 0. Seed audit covers available historical report text, seed fields, retained receipt seeds, and NPZ metadata, including all S1; missing historical archives are explicitly listed. Any collision blocks launch.

## Player and cells

All cells use B's single-root srp-pub-mix search controller, same public candidate generator, horizon 160, interval 10, and fixed 63 candidate-style rollouts (up to 21 candidates, all three styles). No event-triggered search or E-arm own-command tracker is introduced. Controller polls every two ticks from tick 90 and searches every ten ticks; one outstanding command. No host wall-clock deadline changes actions.

| Cell | Definition |
| --- | --- |
| Full | S1 B-N97: legacy 1,024-particle posterior; N97 events; predecessor board/HP/HUD corruption; target image latency; zero injected tap failures |
| R-derived | Full with exact public-event-derived opponent elixir/hand/cycle, as A. Board and packet histories remain noisy. Unrevealed hand/cycle remain uncertain; no hidden identities are supplied. |
| R-board | Full with exact visible entity set, positions and identities; HP remains noisy |
| R-hp | Full with exact HP of visible real entities; phantoms retain source HP because a phantom has no truth HP; board corruption unchanged |
| R-own | Full with exact own hand/next/elixir at image capture; target image age unchanged |
| R-events | Full with perfect event identities and exact execution timestamps, through unchanged ELT with q=1 |
| R-latency | Full with image age zero; event-channel delivery delays remain part of event noise, as S1 |
| R-taps | Full with zero injected tap failures: an intentional duplicate because Full already has probability zero |
| A+derived | Clean A board/HP/HUD/latency, but ELT fed N97 events; noisy public event-history features also follow that channel |
| A+board | Clean A plus Full board corruption |
| A+hp | Clean A plus Full HP corruption |
| A+own | Clean A plus Full own HUD corruption |
| A+latency | Clean A plus target image age |
| A | S1 clean A exact public derivation and clean inputs |

The brief explicitly names ELT in R-events and A+derived although S1 B uses OpponentPosterior. This protocol follows those literal cell definitions, keeping B's controller fixed. R-events therefore changes both event fidelity and tracker relative to Full; its measured gain is not an isolated event-channel causal effect. A+derived prices ELT plus its N97 event adapter, not the legacy posterior alone. These limitations must appear with the results, and no additional cells are silently added. No changes to elt.py are permitted.

Noisy ELT uses S1's singleton identity candidates, validation-calibrated per-card existence probabilities with the N97 odds shift, and arrival-minus-two-ticks monotonic execution estimates with sigma zero. Perfect-event ELT bypasses that timing approximation and uses true public timestamps and q=1. Non-card public resource events retain S1's treatment. Target image age is four ticks with probability .98 and eight otherwise. No identity-confusion sensitivity is added to the predecessor board model. Ordinary illegal or unaffordable action rejections remain, even with tap failures off. HP and HUD repairs remove measurement noise at capture, not the separate image latency. Channel RNG seeds, not individual event realizations after divergent actions, are paired.

## Preflight and sealing

Unit tests cover noise switches, unchanged ELT, scoring-only trace independence, complete schedule coverage and bootstrap sign/cluster behavior. On three fixed development seeds, terminal action SHA256 and action count must match: all channels repaired versus frozen S1 A; none repaired versus frozen S1 B-N97. Tests inspect action equivalence and technical completion only, never winner/score. R-taps must share Full configuration. A timing pilot runs all 14 cells on development pair 0, with outcomes suppressed. Raw pilot outcomes are not saved. No recalibration or budget change.

Runtime/source hashes are checked before preflight and again before seal; tested code is included in the final manifest. The seal is produced after timing-only preflight, as in S1; all confirmation begins after the seal. The frozen execution map has 152 partitions, 76 assigned to 04 and 76 to 08, index modulo 152. Concurrency may be reduced without changing partitions. Nice 10, one native/BLAS thread. Total of our worker processes per host ≤80, or ≤16 if who reports a console user; launcher reserves headroom and rechecks before each wave. 01 runs light orchestration/collection only. 05 runs no simulator work. No 02/07/09–18 use. No commits.

## Technical recovery (S1 rule)

fleet/fleet_run.sh owns each detached node supervisor with lock, log, PID and exit receipt. Each worker has its own lock/log/PID/atomic exit receipt. Valid terminal receipts match the full manifest, job identity, seeds, variant and seat, are immutable, and are skipped on resume. Incomplete games restart on identical inputs; logs/current files are retained. Wrong identity or hashes are a hard failure and never overwritten. After a nonzero process exit, preserve its receipt and use a new attempt label for the same partition. No rerun is triggered by a loss, slow game, rejection count or surprising diagnostic.

No code or engine changes after freezing. A correctness bug requires stopping confirmation, retaining evidence, and a separately documented new preregistration and fresh seeds. No interim outcomes or strength aggregates. Monitor only identities, counts, terminal flags, elapsed/CPU times, errors and hashes. If a host disappears, stop collection without a retry loop, write resume state and report; do not assume its processes are dead, migrate or restart them. Never delete fleet data or signal unverified PIDs. No tailscale/crontab changes.

## Complete-only analysis

Win=1, draw=.5, loss=0. Average both seats within each matchup. For scores and all paired contrasts, 10,000 percentile paired-matchup bootstrap resamples of the 128 matchup means, retaining paired arms and both seats, numpy default_rng(9711100003). Report every cell's score and 95% CI. Rank repair effects (Repair−Full) descending by point estimate and add costs (A−Add) descending; report Add−A as well.

Materiality: a channel is material if its repair gain's 95% lower bound is strictly >0 OR its add effect (Add−A)'s 95% upper bound is strictly <0. The latter is equivalently A−Add lower bound >0. This resolves the brief's opposite signs without changing its intended directional rule. No multiplicity adjustment, selection or follow-up retuning. Channels without an add cell use repair only. Label R-events' confound and R-taps' degeneracy.

Interaction check: sum the seven repair gains and compare to A−Full; report both and their difference, with paired-bootstrap intervals formed by summing at matchup level. This is a descriptive nonadditivity check; the tracker substitution in R-events also limits interpretation. Family and Hog 2.6 score/contrast summaries are descriptive, using the same cluster method within family. ELT/derived diagnostics by cell use S1's decision sampling (tick modulo 20 equals 10): elixir MAE, 90% interval coverage/width, hand concentration fraction and accuracy when concentrated. Report actual event rates, rejected commands, taps, timing, and per-host CPU.

ELT diagnosis: save a scoring-only distribution snapshot at every decision in A+derived and R-events, plus event corruption type, true execution tick and delivered tick. No truth enters the belief, action RNG or candidate generation. Analyze 90% elixir coverage, fully known hand concentration, and maximum-hypothesis mass≥.9 separately. Missing-event onset is its true tick; confused/spurious onset is delivered tick. Report whether each metric was already bad before the first corrupt event, first bad sample after it, later recovery, and terminal unrecovered episode. Associate terminal loss with the most recent preceding error type; report counts and representative job/event/tick evidence. Permanent means unrecovered through the last observed decision, right-censored; association is not proof of individual-event causation. Report no-error games and finite-prior ambiguity separately. Explain implementation mechanisms from unchanged ELT, diagnose only.

Outputs: RESULTS.md, result.json, ELT-DIAGNOSIS.md, manifest and receipt aggregate hashes, game CPU-hours, worker total CPU-hours including initialization, preflight CPU separately, and elapsed time. Raw receipts/traces and binaries stay on fleet; only S2-owned code, docs, small audits/receipts and results mirror to 05. PROGRESS.md and RESUME.md remain current.
