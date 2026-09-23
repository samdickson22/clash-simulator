# Clasher versus public Clash Royale bots and RL environments

Research snapshot: 2026-08-07  
Clasher revision: [`159f87d`](https://github.com/samdickson22/clash-simulator/commit/159f87d9c8edb6bec671026211e70e7874c986fe)  
Scope: 36 public GitHub repositories, inspected from source at pinned revisions

## Bottom line

Clasher is the strongest **RL gym and high-fidelity simulator** in this survey. No
other inspected project combines all of the following:

- 57 enabled or transitively reachable unit specifications rather than an
  eight-card teaching arena;
- mechanics derived from a pinned StatsRoyale data export plus decoded official
  client globals rather than a small table of hand-entered approximations;
- deterministic native-tick simulation, a separately checked fast path, and
  interaction-level parity tests;
- a public-information recurrent actor, separate privileged critic, masked
  card-conditioned spatial policy, and real multi-process PPO implementation;
- committed checkpoints and a documented curriculum spanning 5.59 million
  learner decisions;
- paired evaluation that replays the same matchup with the candidate on both
  seats, reports uncertainty and crown margin, and rejects regressions.

Clasher is **not** the strongest end-to-end bot for the commercial game. KataCR,
The Elixir Optimizers, ClashAI, and several smaller projects can observe a real
client from pixels and issue real inputs. KataCR has the best research artifact
package and real-game demonstration; The Elixir Optimizers has the best documented
perception-to-live-PPO experiment; ClashAI has the broadest active sim-to-real and
deck-strategy tooling. Clasher currently has no perception stack, screen-to-state
calibration, real-client controller, or live-game validation.

The biggest actionable finding is not a new neural architecture. It is to combine
Clasher's simulator and evaluation rigor with three ideas that other projects do
better: human demonstration warm starts, diverse strategic benchmark opponents,
and a reward signal that represents defensive danger and board value rather than
only eventual tower outcomes.

## How the comparison was made

Every repository was shallow-cloned and inspected at the revision listed in the
inventory. Claims are labeled by evidence strength:

- **demonstrated**: committed measurements, evaluation tables, videos, model
  artifacts, or detailed experiment logs exist;
- **implemented**: source code is present, but the inspected revision contains no
  result sufficient to show that it works well;
- **reported**: the author states a result, but the repository does not contain
  enough raw artifacts to independently reproduce it from the snapshot;
- **planned/prototype**: scaffolding, a notebook, or README design exists without
  a completed training result.

This distinction matters. Several repositories describe self-play, millions of
steps, or sophisticated models while committing neither checkpoints nor frozen
evaluation results. Those features are useful designs, not evidence of agent
strength.

This report compares engineering and research quality, not compliance with the
commercial game's terms. Live automation can violate Supercell's terms of service.

## Comparison at a glance

| Project | Real commercial game | Simulator | Learning system | Best evidence | What it does better than Clasher | What Clasher does better |
|---|---|---|---|---|---|---|
| **Clasher** | No | 57 enabled/reachable specs; native-tick, data-driven | Recurrent entity Transformer PPO with privileged critic | 5.59M decisions; 72-game paired gates; 1,011 tests collected | — | Fidelity, coverage, tests, throughput, paired evaluation, committed training lineage |
| [KataCR](https://github.com/wty-yy/KataCR/tree/36ceb9fcfbd117c2ce3d97eacee435c1898eb7b8) | Yes, phone screen and input | No | Offline StARformer and Decision Transformer | Models/datasets linked; reported 12 wins against 8,000-point built-in AI | Real-client operation, perception, expert replay data, publication-quality artifacts | Online experience scale, deterministic state, strategic self-play, evaluation controls |
| [The Elixir Optimizers](https://github.com/weihaog1/The-Elixir-Optimizers/tree/f941deb7c271cd8e2e1d9eaf5f6fcec7861d0251) | Yes, Google Play Games | No | Behavior cloning to MaskablePPO | 106 live episodes; final 3/10 versus humans; 0.804 detector mAP50 | Honest perception validation, BC warm start, live human result, reward iteration write-up | Millions of decisions, recurrent memory, controlled opponents, precise confidence evidence |
| [vegetableleaf/ClashAI](https://github.com/vegetableleaf/ClashAI/tree/5595ab08251d241dbe1fd34745281ee02b9856f0) | Implemented | Yes, large meta-deck pool claimed | BC, DDQN, PPO simulator path, PFSP league | Extensive active source and changelog; no committed checkpoint/evaluation artifact | Sim-to-real path, deck switching, strategic bots/PFSP, threat and defensive reward concepts | General mechanics, non-card-specific logic, tests, demonstrated training and promotion gates |
| [DeepRoyale ecosystem](https://github.com/DeepRoyale-APREF/MohaNetLight/tree/e1e80c5f574ec3e0722962cd3ee8a2e4ea3d6980) | No | Eight-card Arena 1 engine | MohaNetLight recurrent PPO plus baselines | Implemented; no checkpoint or training metrics committed | Clean package split, modular rewards, heuristic roster, baseline/ablation tools, reports | Card/mechanics breadth, fidelity evidence, test depth, actual trained champion |
| [Tanmay's Clash Royale Clone](https://github.com/tanmay4269/Clash-Royale-Clone/tree/63fa2258354b6acd242c0bf740f6057e1ab45366) | No | Eight Training Camp cards | PPO self-play with Elo checkpoint pool | Two reported 10M-step runs and browser demo; final shared frozen comparison is TODO | Browser-playable demo, Elo matchmaking design, long pedagogical experiment narrative | Fidelity, tests, fixed-opponent paired evidence, promotion discipline |
| [clash-royale-complete](https://github.com/lsteno/clash-royale-complete/tree/4329a33b2994716908724514093b5ab2d841eb4f) | Yes, ADB/emulator | No | DreamerV3 world model, semantic and pixel variants | Reported roughly 60% versus random; stronger training unstable | Model-based imagined rollouts, real-client bridge, pixel/semantic ablation | Throughput, action resolution, state reliability, reproducible artifacts and evaluation |
| [Jaso1024](https://github.com/Jaso1024/Real-Time-Strategy-RL-Clash-Royale/tree/aec65d72d53ecbdce6a3297c2ea3d295c4c74af9) | Yes, BlueStacks | No | Three factored PPO actor-critics over encoded pixels | Implemented; no modern result artifact | Early real-client factored-action design | Current mechanics, masks, recurrent state, tests, performance and results |
| Other live bots | Usually yes | No | Mostly DQN, PPO, Q-learning, or rules | Mostly prototypes | Hardware/client automation and perception experiments | Nearly every RL-gym, simulator, testing, and evaluation dimension |
| Other toy simulators | No | Small/simplified | PPO or basic Gym examples | Mostly demos | Simplicity and ease of understanding | Fidelity, breadth, architecture, validation and trained strength |

## What other projects do better than Clasher

### 1. They close the sim-to-real loop

KataCR is the clearest example. Its source includes dual YOLOv8 detection, card
and elixir classifiers, OCR, perception fusion, mobile video ingest, interaction,
offline replay construction, and live policy evaluation. It reports approximately
120 ms decision latency plus 240 ms feature fusion and links both datasets and
model weights. Its README reports twelve winning games against an 8,000-point
built-in opponent. Clasher cannot currently answer the most important external
validity question: does a strategy learned in its exact-state simulator survive
real rendering, observation noise, timing jitter, and input latency?

The Elixir Optimizers independently built a complete pixels-to-clicks pipeline:
dual YOLOv8m detection over 155 classes, structured state encoding, behavior
cloning from 40 human matches, MaskablePPO, and real human matchmaking. Its report
is unusually candid: the detector reached 0.804 mAP50 on 1,388 held-out real
images; live PPO trained for 106 episodes; the final checkpoint won 3 of 10 fresh
games; and the authors explicitly call the sample too small. That is weaker policy
evidence than Clasher's paired gates, but much stronger evidence of real-world
operability.

ClashAI, EzraGil08, AndreNijman, XSlayerDzX, 0xCyberstan, Dario-Soatto, and other
live projects also contain useful client anchoring, screen capture, object
tracking, hand recognition, OCR, action execution, and match-reset ideas. Most do
not demonstrate a strong trained policy, but their integration work addresses a
whole problem layer Clasher does not attempt.

**Verdict:** the public live bots are better robots; Clasher is a better gym.

### 2. They use human demonstrations and offline data

KataCR builds offline trajectories from expert battle videos and trains
StARformer/Decision Transformer policies. The Elixir Optimizers use behavior
cloning to initialize a live PPO policy. ClashAI records a user's screens and
mouse actions, labels placements, trains a cloned policy, and then fine-tunes it.
XSlayerDzX similarly describes a BC-LSTM-to-PPO path.

Clasher has an oracle planner and a DAgger smoke-tested pipeline, but the current
champion lineage was trained from self-play/random curricula rather than a proven
human or scripted-strategy prior. Demonstrations could teach timing, lane choice,
defensive placement, and elixir discipline before PPO has to discover them from a
sparse strategic signal.

**What to copy:** add an optional imitation phase using legal Clasher actions and
public observations. Human replay extraction can come later; first use competent
scripted/oracle demonstrations and measure whether the same frozen promotion gate
improves sample efficiency.

### 3. They expose more strategic opponent diversity

DeepRoyale's MohaNetLight includes parameterized Giant Push, Bridge Spam, Spell
Cycle, Defensive Counter, and Balanced bots, with ten roster variants. ClashAI's
simulator describes a large meta-deck pool and PFSP-style weighting toward hard
past opponents. Tanmay's simulator implements an Elo-rated checkpoint pool,
admission thresholds, and matchup sampling near an expected 50/50 score.

Clasher's curriculum is empirically better validated than any of those systems,
but its frozen opponents are all members of one policy lineage plus a uniform-legal
random agent. A model can improve its evaluation table while still learning a
narrow strategic dialect. The update-1500 and update-1440 passive regressions are
exactly the kind of failure a broader opponent suite can reveal sooner.

**What to copy:** build a frozen strategy benchmark with deterministic scripted
archetypes and later add PFSP over accepted policy snapshots. Keep Clasher's paired
seat-swapped evaluation; do not replace it with within-run Elo.

### 4. Their reward systems represent defense and board state more directly

Clasher's main potential is deliberately clean and zero-sum, but it only contains
crown difference, princess-tower damage, gated king pressure, a very small
tiebreak term, and an early-king-chip penalty. Defense receives credit only when it
eventually prevents tower damage. There is no explicit value for removing an
incoming push, preserving a counterpush, or responding near a threatened tower.

Other projects explore signals Clasher lacks:

- The Elixir Optimizers iterated through six live reward designs and explicitly
  rewarded defensive placement near enemy units. The report documents both the
  resulting behaviors and failure modes.
- ClashAI tracks enemy threat mass, changes in on-board unit value, defensive
  responses, elixir trades, and pending consequences. Its strongest concepts are
  potential-based threat and board deltas; its weakest are numerous Icebow- and
  card-specific bonuses.
- `cr-gym` makes reward terms composable components, which supports ablations and
  avoids hard-wiring one experiment into the environment.
- MohaNetLight includes reward diagnostics and sparse-versus-shaped baseline
  training commands.

**What to copy:** a general, zero-sum potential for HP- and elixir-weighted public
board value plus defensive danger to surviving towers. **What not to copy:**
card-name bonuses, fixed combo rewards, generic action bonuses, or survival rewards.
Those teach one deck script and are easy to exploit.

### 5. Some have better experimental breadth or presentation

MohaNetLight includes ConvLSTM and flat-MLP baselines under the same nominal PPO
pipeline, plus reward-ablation commands and model comparison scripts. Tanmay's
project has a long-form research narrative and browser-playable demo. DeepRoyale's
`cr-gym` has reusable tournament, tracker, CSV/JSON, and PDF-report abstractions.
KataCR publishes separate perception and replay datasets, model links, training
curves, and a paper-style system description. The Elixir Optimizers publish
perception metrics, latency, training progression, behavior analysis, known
limitations, and honest negative results in one polished report.

Clasher's internal training report is strong, and its viewer is good, but the
project would be easier to evaluate externally with a benchmark command that emits
a single machine-readable scorecard, a packaged web replay, baseline ablations,
and a public dataset/model card.

### 6. Several projects are more reusable legally

KataCR and a number of smaller bots include an MIT license. Clasher has no root
license file. DeepRoyale READMEs say MIT, but the inspected roots do not all contain
a license file, so their legal packaging is inconsistent too.

If Clasher is intended for public reuse, choosing and committing a license is a
straightforward improvement.

## What Clasher does better than every surveyed project

### 1. Simulator mechanics breadth and source authority

Clasher's enabled deck graph contains 52 direct specifications and five distinct
reachable child specifications: Barbarian, Delivery Recruit, Goblin, Golemite, and
LavaPups. The simulator therefore audits 57 runtime unit specifications. It also
implements the relevant spells, buildings, projectiles, status effects, death
payloads, formations, champion abilities, tower behavior, river routing, collision,
and action timing needed by those decks.

The nearest direct simulator competitors, DeepRoyale and Tanmay's clone, each
document eight cards. Other simulation projects are smaller or intentionally
text-based. Live vision systems may recognize far more card classes, but recognizing
a sprite is not equivalent to simulating every interaction of that card.

Clasher loads a pinned `gamedata-v5` snapshot with fingerprint
`ef863332281e7c47d628d23a80881ed300d47ede`, applies explicit balance corrections,
and encodes behavior through shared payload/global-driven mechanics. Tests rename
synthetic cards to verify that factories identify behavior from data shape rather
than card names. No other surveyed simulator presents comparable source authority
or generalization evidence.

This does **not** prove exact live-game parity. Current tests and invariant matrices
are strong internal evidence; a commercial-client differential oracle is still
missing.

### 2. Verification depth

The roadmap implementation tree collects 1,011 pytest cases across 38 test files. They include exact
fixed-point projectile flight, targeting and collision fast-path parity, death
spawns, simultaneous-hit ordering, spell timing, river movement, building
footprints, champion ability masking, deterministic rollouts, observation privacy,
Gymnasium contracts, recurrent PPO smoke tests, and optimizer-resume behavior.

For scale, the strongest documented external suites claim 153 tests for The Elixir
Optimizers, 69 for `cr-engine`, 64 for `cr-gym`, and 68 for MohaNetLight. KataCR has
no conventional test files in the inspected snapshot. ClashAI and Tanmay's clone
also contain no conventional Python test files. Test count alone is not quality,
but the interaction-specific content makes the gap meaningful.

### 3. Observation integrity and asymmetric actor-critic design

Clasher's actor sees public visible entities, its own hand/cycle, public arena
state, previous actions/rewards, and recurrent memory. Tests verify that changing
the hidden enemy hand does not change the actor observation. A separate critic sees
privileged full state only during training. Auxiliary heads ask public-state memory
to infer opponent hand membership and elixir.

Several competitors either use raw pixels, flat occupancy maps, or small structured
vectors. MohaNetLight is the closest architectural peer, with entity attention,
CNN arena features, LSTM memory, and a FiLM spatial decoder. Its inspected snapshot,
however, contains no committed trained checkpoint or evaluation result. Clasher's
architecture is both implemented and exercised by a documented multi-million-step
champion lineage.

### 4. Legal action semantics

Clasher masks card-slot/tile combinations from the actual simulator rules,
including elixir, hand refill, territory, water, building footprints, wide
formations, special anywhere placements, and champion abilities. The fast mask is
tested against the full engine and against both canonical sides. The hierarchical
joint distribution is tested to avoid biasing a card merely because it has more
legal tiles.

Most live bots mask only hand membership, cost, and a coarse placement grid. Toy
simulators implement simpler own-half masks. Clasher's mask is part of the game
model rather than a separate approximation.

### 5. Measured high-throughput recurrent training

The accepted update-1400 champion reached 5,591,040 learner decisions. Training
used persistent CPU simulator workers and CPU batch-one actor inference while MPS
processed recurrent PPO sequences. Measured throughput was usually about 250-365
learner decisions per second, with controlled batch-size experiments explaining why
larger MPS sequence batches were slower.

Real-game systems are constrained to roughly 1.5 FPS to one action every 2-3
seconds and cannot parallelize cheaply. DeepRoyale reports high simulated episode
throughput, but only for its much smaller eight-card engine and without a committed
trained-result lineage. Clasher has both performance measurements and useful policy
progress.

### 6. Promotion and rollback discipline

Clasher evaluates each sampled deck matchup twice, switching the candidate's seat.
It reports wins/losses, an approximate score interval, crown differential, seat
split, and no-op rate conditional on another legal play. Training statistics include
KL, explained variance, gradient norm, throughput, optimizer steps, and no-op
behavior.

This process promoted update 1400 after a 39-33 direct result over update 1300 and
strong fixed-anchor results. It then rejected update 1500 despite stable optimizer
statistics because every anchor regressed and passive waiting rose. It separately
rejected update 1440 when an apparent update-1420 gain failed to replicate.

No other surveyed project documents this combination of matched seeds, both seats,
uncertainty, fixed anchors, direct champion comparison, behavioral diagnostics, and
explicit rollback. Tanmay's write-up correctly says final frozen head-to-head
evaluation is required, but its own run-30/run-31 table still marks that comparison
TODO. The Elixir Optimizers explicitly acknowledge that 3/10 is uncertain. Most
other repos report training reward or a small win rate without seat control.

### 7. Reproducible artifacts

The local Clasher workspace retains 176 V2/legacy policy checkpoint files across
accepted and rejected branches. Four curated checkpoints are tracked in Git: the
update-140 viewer model and the update-800, update-1300, and accepted update-1400
curriculum anchors. The training report records hashes for key checkpoints. The
exact update-1400 model loads locally and contains about 1.28 million state-dict
parameters. Training and evaluation commands resolve explicit paths and fail loudly
when inputs are missing.

Many competitors link weights hosted elsewhere or commit none. DeepRoyale,
ClashAI, KataCR, and `clash-royale-complete` contain no policy checkpoint in the
inspected clone, although KataCR links downloadable external weights and Tanmay
serves external demo checkpoints. External hosting is reasonable for large models,
but it weakens revision-level reproducibility.

## Where Clasher is currently weaker as an RL gym

These are the material gaps, ordered by expected impact:

1. **The reward does not directly represent defense.** Board-value and threatened-
   tower potentials are the most justified next experiment. The existing tower-only
   objective can teach racing and delayed defense.
2. **Opponent diversity is too narrow.** Random plus the model's own history is not
   a strategy suite. Add fixed archetype bots and later PFSP.
3. **There is no demonstrated imitation warm start.** The oracle/DAgger code exists,
   but no accepted checkpoint demonstrates a sample-efficiency gain from it.
4. **No sim-to-real validation exists.** Exact parity remains unproven until selected
   scripted interactions or policies are compared with the real client.
5. **Evaluation measures relative strength, not human comprehensibility.** Add
   behavior metrics: defensive response latency, elixir-trade efficiency, tower
   threat conceded, counterpush preservation, lane-switching, and leak rate.
6. **There is no standard strategy benchmark or external baseline.** Every current
   learned opponent is related to the same architecture and data-generating process.
7. **Scientific packaging can improve.** Add a license, model card, machine-readable
   benchmark artifact, and one-command replay/web demo.

## Recommended roadmap

Implementation status (2026-08-07): all five roadmap foundations below are now
implemented in source. The `defense-v2` potential is opt-in and covered by exploit
tests; the public-information strategy roster emits paired benchmark JSON and PFSP
weights; the V2 oracle workflow produces a fixed corpus plus matched warm-start and
control checkpoints; normalized public-frame traces can be compared without live
automation; and the repository now includes a license, champion model card,
machine-readable evaluation, and canonical replay manifest. These implementations
enable the experiments below; they do not fabricate promotion evidence. No new
checkpoint should be promoted until its fixed paired gates actually pass.

The first controlled `defense-v2` pilot has now also completed. Update 1420 passed
all five matched 24-game safety rows, improved from 12-12 to 16-8 versus update
1300, went 15-9 directly against champion update 1400, and reduced mean incoming
tower danger by 36% in that direct matchup. The result was identical under both
evaluation reward profiles, ruling out recurrent reward-input drift. This warrants
expanded promotion evaluation but does not yet promote the 24-game challenger.

### P0: make defense measurable before training longer

Add two zero-sum potential terms derived only from public simulator state:

- HP- and elixir-weighted board value differential, using remaining unit health
  rather than raw unit counts;
- tower danger differential, based on enemy unit value, distance/time-to-contact,
  target eligibility, and surviving tower HP.

Keep the terminal result and tower objective dominant. Potential differences must
telescope across steps so the agent cannot farm repeated threat detections. Run
reward unit tests, exploit probes, then a 20-update update-1400 fork. Compare against
the exact existing paired anchor blocks and add defense metrics. Do not change the
opponent mixture in the same experiment.

### P1: add a strategy benchmark

Implement a small deterministic roster with shared, card-agnostic principles:

- bridge pressure;
- slow tank/support push;
- spell cycle/control;
- reactive defense/counterpush;
- split-lane pressure;
- elixir-conserving balanced play.

Each bot should use only legal public information and the same enabled decks. First
use them only for evaluation. Once stable, use them for a curriculum and PFSP-style
sampling. Preserve frozen paired evaluation; Elo should assist matchmaking, not
decide promotion.

### P1: prove an imitation baseline

Use the existing oracle/DAgger path to generate a fixed demonstration corpus. Train
the same architecture with and without the supervised warm start under equal
environment-decision budgets. Promote only if fixed paired opponents improve. This
tests the strongest transferable lesson from KataCR, Elixir Optimizers, and ClashAI
without waiting for a full visual replay parser.

### P2: create a thin real-client validation bridge

Do not begin with live RL. Build a read-only perception/replay validator:

1. ingest recorded real matches;
2. detect a deliberately small set of enabled-deck interactions;
3. reconstruct approximate public states;
4. compare timing, targeting, displacement, damage, and spawn ordering against
   Clasher scripts;
5. store mismatches as parity cases.

KataCR's public detection/replay datasets are the best starting artifact. This
would measure the sim-to-real gap without making slow real matches the training
environment.

### P2: improve research packaging

- Add a license.
- Export evaluation JSON alongside Markdown tables.
- Add a champion model card containing data version, deck scope, reward equation,
  architecture, training budget, known exploits, and exact launch commands.
- Publish a browser replay or a short canonical video suite against fixed opponents.
- Add baseline ablations only after defense/opponent changes are measurable.

## Ideas not worth importing

- **Card-name and combo rewards.** They can produce a convincing single-deck demo
  while preventing generalization and encouraging reward hacks.
- **Positive rewards for taking any action.** These cause spam and undermine elixir
  timing.
- **Per-step survival rewards.** They directly incentivize waiting and draws.
- **Raw enemy-disappearance rewards in vision.** Occlusion and detector misses look
  like kills.
- **A strategy action head with labels such as aggressive/defensive/farming unless
  it has independent semantics.** It can become a redundant latent variable rather
  than a useful action.
- **Replacing paired gates with Elo.** Elo inside a changing opponent pool is useful
  for sampling, not proof that one frozen checkpoint is stronger.
- **Training directly in the commercial game first.** It is too slow, noisy, and
  hard to control. Use real footage for validation and demonstrations; keep bulk RL
  in Clasher.
- **A larger model before better objectives.** Clasher's failures at updates 1500
  and 1440 were behavioral over-specialization under stable optimization, not an
  obvious capacity shortage.

## Detailed project findings

### KataCR

**Strongest contributions:** real mobile-device operation, mature perception stack,
generated detection dataset, replay dataset, downloadable models, offline sequence
policies, measured latency, and a strong real-game demonstration. It is also the
most visible project in the survey by GitHub adoption.

**Limitations relative to Clasher:** specialized card/elixir classifiers, Linux +
NVIDIA + particular aspect-ratio assumptions, approximately 20-round policy test
tables, no deterministic simulator, and no controlled self-play curriculum. The
inspected snapshot has no conventional tests or committed weights; weights are
external downloads.

**Best lesson:** expert replay data and a read-only real-game parity bridge.

### The Elixir Optimizers

**Strongest contributions:** unusually complete and honest final report, 155-class
dual detector, held-out real-image evaluation, BC-to-MaskablePPO transfer, action
masking, latency breakdown, six reward iterations, 153 reported tests, and a real
human evaluation.

**Limitations relative to Clasher:** only 106 real episodes, 10-game final sample,
single-frame BC and three-frame PPO stack rather than recurrent memory, real-time
single-environment throughput, unpredictable opponents, detector domain gap, and
coarse placement supervision. The overall training record is reported as 5 wins,
80 losses, 3 draws, and 18 interrupted/unknown games before the final evaluation.

**Best lesson:** perception metrics, explicit negative results, and behavior-cloning
warm start.

### vegetableleaf/ClashAI

**Strongest contributions:** end-to-end recording/labeling/live-control workflow,
active development, deck-switch documentation, simulator and live pipelines sharing
a policy, DDQN for scarce live data, PPO for parallel simulation, past-self league,
PFSP concepts, meta-deck opponents, threat tracking, and detailed reward-failure
analysis.

**Limitations relative to Clasher:** the inspected revision commits no trained
checkpoint, no frozen outcome table, and no conventional test suite. Many reward
and behavior paths are explicitly tuned to Icebow cards and combos. The simulator's
README claims broad features, but it lacks Clasher's authoritative data/parity
evidence.

**Best lesson:** PFSP and defensive-threat metrics. Copy the abstractions, not the
Icebow reward scripts.

### DeepRoyale: cr-engine, cr-gym, and MohaNetLight

**Strongest contributions:** the cleanest competitor packaging. The engine, Gym
wrapper, and model are separated; rewards are components; observations and actions
are typed dictionaries; tournament and report tooling are reusable; heuristic bots
cover several strategy archetypes; and MohaNetLight includes recurrent/entity/spatial
modeling plus ConvLSTM and flat-MLP baselines.

**Limitations relative to Clasher:** only eight Arena 1 cards, hand-entered level-1
stats, coarse 30 FPS continuous approximations, and no committed checkpoint or
result metrics. README examples showing 62% rolling win rate are example output, not
demonstrated training evidence. The three-repository installation is less convenient
than a single package, and license declarations are inconsistent with root files.

**Best lesson:** modular reward experiments, scripted strategy roster, and automatic
comparison reports.

### Tanmay's Clash Royale Clone

**Strongest contributions:** a playable browser demo, clear long-form documentation,
10-million-step reported Deep Sets and Transformer runs, checkpoint Elo, opponent
admission gates, worker-aware matchmaking, and good discussion of why self-play
training curves are not final evidence.

**Limitations relative to Clasher:** eight Training Camp cards, 4 FPS simplified
simulation, no conventional tests in the inspected revision, no committed policy
weights, and no shared frozen evaluation between the two flagship runs. The report
itself marks final head-to-head win rate and score as TODO.

**Best lesson:** public interactive replay and richer league sampling.

### clash-royale-complete

**Strongest contributions:** the only surveyed project centered on model-based RL.
It supplies DreamerV3 world-model training, imagined actor learning, semantic and
pixel observation variants, ADB/gRPC integration, action masking, and an explicit
negative comparison between noisy semantic extraction and expensive pixels.

**Limitations relative to Clasher:** approximately 1.5 FPS interaction, only 37
actions, real-client noise, unstable dense-reward training against stronger
opponents, one conventional test file, and no committed checkpoint/summary outputs
in the inspected snapshot. Roughly 60% versus random is author-reported rather than
recoverable from local artifacts.

**Best lesson:** world-model auxiliaries may eventually improve representation and
planning, but they are lower priority than reward/opponent fixes in Clasher.

### Jaso1024 and the older real-game agents

Jaso1024's three cooperating PPO agents, factored placement, pixel autoencoder, and
elixir/card features were forward-looking for 2022-2023. Chinedu-E explores VAE
latents plus structured card features. Tuuktuc86, Naman0r, EthanL5286, and others
document valuable emulator and computer-vision lessons. Their training/evaluation
evidence, action masks, reproducibility, and maintenance are substantially behind
Clasher and the newer live projects.

## Complete repository inventory

| Repository and inspected revision | Category | Evidence status | Material advantage over Clasher |
|---|---|---|---|
| [wty-yy/KataCR @ `36ceb9f`](https://github.com/wty-yy/KataCR/tree/36ceb9fcfbd117c2ce3d97eacee435c1898eb7b8) | Real-game research system | Demonstrated/reported | Best perception, data, models, publication, and live showcase |
| [weihaog1/The-Elixir-Optimizers @ `f941deb`](https://github.com/weihaog1/The-Elixir-Optimizers/tree/f941deb7c271cd8e2e1d9eaf5f6fcec7861d0251) | Real-game BC + PPO | Demonstrated | Best end-to-end experiment report and honest perception/live metrics |
| [vegetableleaf/ClashAI @ `5595ab0`](https://github.com/vegetableleaf/ClashAI/tree/5595ab08251d241dbe1fd34745281ee02b9856f0) | Hybrid simulator/live bot | Implemented | Broadest active sim-to-real, PFSP, deck tooling, defensive reward ideas |
| [lsteno/clash-royale-complete @ `4329a33`](https://github.com/lsteno/clash-royale-complete/tree/4329a33b2994716908724514093b5ab2d841eb4f) | Real-game DreamerV3 | Reported | Model-based imagined rollouts and pixel/semantic comparison |
| [DeepRoyale-APREF/cr-engine @ `be89925`](https://github.com/DeepRoyale-APREF/cr-engine/tree/be89925a22bf1efe25fb3acb9d4bef1ca08a9ed3) | Eight-card simulator | Implemented | Cleaner teaching package and IL symmetry extraction |
| [DeepRoyale-APREF/cr-gym @ `b06777c`](https://github.com/DeepRoyale-APREF/cr-gym/tree/b06777c2c287501a2f57de82a8a096ce171a0b66) | Gym/league layer | Implemented | Modular rewards, tracker, tournaments, reports |
| [DeepRoyale-APREF/MohaNetLight @ `e1e80c5`](https://github.com/DeepRoyale-APREF/MohaNetLight/tree/e1e80c5f574ec3e0722962cd3ee8a2e4ea3d6980) | PPO model package | Implemented | Heuristic strategy roster and baseline/ablation tooling |
| [tanmay4269/Clash-Royale-Clone @ `63fa225`](https://github.com/tanmay4269/Clash-Royale-Clone/tree/63fa2258354b6acd242c0bf740f6057e1ab45366) | Eight-card simulator/self-play | Reported | Browser demo, Elo pool, 10M-step narratives |
| [Jaso1024/Real-Time-Strategy-RL-Clash-Royale @ `aec65d7`](https://github.com/Jaso1024/Real-Time-Strategy-RL-Clash-Royale/tree/aec65d72d53ecbdce6a3297c2ea3d295c4c74af9) | Real-game PPO | Implemented | Factored multi-agent action architecture on live pixels |
| [EzraGil08/ClashGPT @ `fb41fbc`](https://github.com/EzraGil08/ClashGPT-Autonomous-Clash-Royale-Artificial-Intelligence/tree/fb41fbc74e95d2a1acdd3e8557d825b508d7a668) | Real-game MaskablePPO | Implemented | Dual YOLO + SORT pipeline and clear 49-action live environment |
| [XSlayerDzX/Reinforcement-Learning-AiAgent @ `a1a58ad`](https://github.com/XSlayerDzX/Reinforcement-Learning-AiAgent/tree/a1a58ad05951bbe47efe691c7c42e3f6fd387c5b) | Real-game BC-LSTM-PPO | Implemented | Human imitation and recurrent live-policy design |
| [0xCyberstan/Royale-RL @ `bdba976`](https://github.com/0xCyberstan/Royale-RL-A-Reinforcement-Learning-Agent/tree/bdba976fc329c41553ff81190e08dcf58428ad6e) | Real-game Decision Transformer | Implemented | YOLOv9/MobileNet/OCR integration and autonomous menu loop |
| [AndreNijman/CRBot @ `a01f654`](https://github.com/AndreNijman/CRBot/tree/a01f654b915db65015ab9000b324a22bb93a3b99) | Real-game DQN | Implemented | Live HUD, BlueStacks automation, Flask monitoring |
| [Dario-Soatto/clash-royale-bot @ `901545a`](https://github.com/Dario-Soatto/clash-royale-bot/tree/901545a606eb12fbd05086ff17ecbf54f23fa8d3) | Real-game DQN | Implemented | Modular YOLO/card/health/action pipeline |
| [Chinedu-E/ClashRoyale-AI @ `67830a6`](https://github.com/Chinedu-E/ClashRoyale-AI/tree/67830a6fbb7734e5d6df66d5c3061a2a45ddfe6a) | Real-game latent RL | Prototype | VAE latent observation experiment |
| [fabzio/deep-royale @ `eb67ac7`](https://github.com/fabzio/deep-royale/tree/eb67ac71c9171a445e9a57e38d955e8e31669e71) | Vision/state toolkit | Implemented | Community-supported real-game state generator |
| [sarinali/clashgent @ `e6e6fc1`](https://github.com/sarinali/clashgent/tree/e6e6fc1983adc37f9ee8daf5892fdbc0b4c7bed1) | Real-game PPO framework | Prototype | Plugin-style reward verifiers and emulator bridge |
| [aarohkandy/CRAIzy @ `2302498`](https://github.com/aarohkandy/CRAIzy/tree/2302498db606c13c8c1db421835efc5dde2112bd) | Distributed live bot | Prototype | Client/server split and off-device/Kaggle training concept |
| [naman0r/CS4100-CR-bot @ `afb2da2`](https://github.com/naman0r/CS4100-CR-bot/tree/afb2da27b57905344431be11f1a226042c040a21) | Real-game Q-learning | Prototype | Simple inspectable live automation coursework |
| [EthanL5286/ClashAI @ `17a8298`](https://github.com/EthanL5286/ClashAI/tree/17a829891745f804b1e97d9bd3d39bfc5769b9c3) | Vision bot | Prototype | Image-recognition experiment |
| [Deep-Jiwan/crbot @ `d14be01`](https://github.com/Deep-Jiwan/crbot/tree/d14be01d9ccaf3461f3f9f57e15d411c43f76fc9) | Real-game bot | Prototype | Emulator integration |
| [Desai0/CR_Neuro @ `982d558`](https://github.com/Desai0/CR_Neuro/tree/982d5585a248377779480eeb3585e49a2f4ae49e) | Real-game vision bot | Prototype | Threaded YOLO/OCR/automation architecture |
| [TheNewMan916/clash-royale-ai @ `f112ffc`](https://github.com/TheNewMan916/clash-royale-ai/tree/f112ffc809f422169c779f2cefae05b8e56b6b8c) | Real-game RL bot | Prototype | Live-client integration attempt |
| [Ch3mson/clash-royale-rl @ `bc3b3f9`](https://github.com/Ch3mson/clash-royale-rl/tree/bc3b3f96c941996b5cc66fe0c60fbc7a117e7592) | Real-game RL bot | Prototype | Small reward/environment experiment |
| [Authize/Clash-Royale-AI @ `4eb63ef`](https://github.com/Authize/Clash-Royale-AI/tree/4eb63ef13fbcaef907fbf80a7fe6fb15ab0bcde8) | Real-game bot | Prototype | MIT-licensed automation components |
| [tuuktuc86/Reinforcement_ClashRoyale @ `7625db0`](https://github.com/tuuktuc86/Reinforcement_ClashRoyale/tree/7625db03d34c8921016c74945dddd903839e42cf) | Real-game RL environment | Negative/prototype | Detailed write-up of emulator and reward difficulties |
| [MartinMondelli/Mini-Clash-Royale @ `73a91d1`](https://github.com/MartinMondelli/Mini-Clash-Royale-Multi-Agent-Reinforcement-Learning-using-PPO/tree/73a91d189b9bbce2ae8813c993749a890e17c6a1) | Mini multi-agent simulator | Notebook/demo | Compact simultaneous-action PPO teaching example |
| [b10902118/royale-simulator @ `d1ee334`](https://github.com/b10902118/royale-simulator/tree/d1ee334802198b304e2276c4f4297f0737966426) | Pygame simulator | Demo | Simple readable collision/targeting visualization |
| [Atrebg/clash_royale_RL @ `1a1449a`](https://github.com/Atrebg/clash_royale_RL/tree/1a1449ab127810117591e46b2d84fb659048800f) | Text Gym environment | Demo | Minimal standard-Gym teaching surface |
| [MeyerTalon/cr-rl-engine @ `44c738e`](https://github.com/MeyerTalon/cr-rl-engine/tree/44c738effa73f414f8ab29993c0ecc0fbc30c8f8) | Simplified simulator | Prototype | Small MIT-licensed engine scaffold |
| [MSU-AI/clash-royale-gym @ `1cd23be`](https://github.com/MSU-AI/clash-royale-gym/tree/1cd23be16e10b25c5a5a0889626a863092f32615) | Pixel Gym wrapper | Stub | Minimal familiar Gym interface |
| [amangupta20/Clash-Royale-Reinforcement-Learning-Agent @ `96c17ce`](https://github.com/amangupta20/Clash-Royale-Reinforcement-Learning-Agent/tree/96c17cece2678b8151ab433ce27fcfdb64767073) | Live Gym design | Prototype | Structured card-shared MLP and pure-Python ADB plan |
| [AWildridge/royale-bot @ `3b3a928`](https://github.com/AWildridge/royale-bot/tree/3b3a9281686a31d3e971a165011b59dc0b508421) | RL bot | Stub | No material demonstrated advantage |
| [HaydenDippL/CR.AI @ `1e5a6de`](https://github.com/HaydenDippL/CR.AI/tree/1e5a6de09ada09562219545bff2426adda7124dc) | RL bot | Stub/prototype | MIT-licensed project shell |
| [SuperSoccer18/ClashBot @ `6b8deba`](https://github.com/SuperSoccer18/ClashBot/tree/6b8deba1a461eb86d4301d96cb0b3cc9a38a661f) | Automation bot | Stub/prototype | No material demonstrated advantage |
| [sportygavin/ClashRoyaleBot @ `9cbb1f1`](https://github.com/sportygavin/ClashRoyaleBot/tree/9cbb1f130aa64dadec4881e0be2a4fe7c18757a3) | Automation bot | Stub/prototype | No material demonstrated advantage |

## Local Clasher evidence used

- [RL V2 training report](./rl_v2_training.md)
- [Primary project README](../README.md)
- [Policy architecture](../src/clasher/rl/model.py)
- [Structured observations](../src/clasher/rl/structured_obs.py)
- [Action space and masks](../src/clasher/rl/action_space.py)
- [Reward model](../src/clasher/rl/reward_model.py)
- [Paired evaluation](../src/clasher/rl/eval.py)
- [Enabled/reachable unit audit](../tests/test_enabled_reachable_children.py)
- [Enabled troop interactions](../tests/test_enabled_troop_interactions.py)
- [Enabled spell interactions](../tests/test_enabled_spell_interactions.py)
- [RL architecture and privacy tests](../tests/test_rl_structured_policy.py)

## Key external source map

The comparison above is based on source at the pinned revisions, especially:

- [KataCR English system description](https://github.com/wty-yy/KataCR/blob/36ceb9fcfbd117c2ce3d97eacee435c1898eb7b8/README_en.md)
- [The Elixir Optimizers final experiment report](https://github.com/weihaog1/The-Elixir-Optimizers/blob/f941deb7c271cd8e2e1d9eaf5f6fcec7861d0251/docs/final.md)
- [ClashAI overview](https://github.com/vegetableleaf/ClashAI/blob/5595ab08251d241dbe1fd34745281ee02b9856f0/README.md), [development log](https://github.com/vegetableleaf/ClashAI/blob/5595ab08251d241dbe1fd34745281ee02b9856f0/log.txt), and [PPO simulator trainer](https://github.com/vegetableleaf/ClashAI/blob/5595ab08251d241dbe1fd34745281ee02b9856f0/icebow/src/clashrl/train_sim_ppo.py)
- [DeepRoyale engine description](https://github.com/DeepRoyale-APREF/cr-engine/blob/be89925a22bf1efe25fb3acb9d4bef1ca08a9ed3/README.md), [Gym/league description](https://github.com/DeepRoyale-APREF/cr-gym/blob/b06777c2c287501a2f57de82a8a096ce171a0b66/README.md), and [MohaNetLight description](https://github.com/DeepRoyale-APREF/MohaNetLight/blob/e1e80c5f574ec3e0722962cd3ee8a2e4ea3d6980/README.md)
- [Tanmay simulator overview](https://github.com/tanmay4269/Clash-Royale-Clone/blob/63fa2258354b6acd242c0bf740f6057e1ab45366/README.md) and [full self-play report](https://github.com/tanmay4269/Clash-Royale-Clone/blob/63fa2258354b6acd242c0bf740f6057e1ab45366/docs/index.html)
- [`clash-royale-complete` DreamerV3 report](https://github.com/lsteno/clash-royale-complete/blob/4329a33b2994716908724514093b5ab2d841eb4f/README.md)
- [Jaso1024 factored PPO design](https://github.com/Jaso1024/Real-Time-Strategy-RL-Clash-Royale/blob/aec65d72d53ecbdce6a3297c2ea3d295c4c74af9/README.md)
- [EzraGil08 live MaskablePPO design and limitations](https://github.com/EzraGil08/ClashGPT-Autonomous-Clash-Royale-Artificial-Intelligence/blob/fb41fbc74e95d2a1acdd3e8557d825b508d7a668/README.md)

## Final assessment

If the goal is to train agents cheaply, repeatably, and with credible evidence of
relative improvement, Clasher is ahead of the surveyed field. If the goal is to put
a bot into the actual commercial client today, KataCR and the newer vision projects
are ahead because they solve perception and control.

The right next move is not to abandon the simulator for slow emulator training. It
is to preserve Clasher's unique strengths while importing the best ideas at its
weak boundary: defensive board-aware objectives, strategic opponent diversity,
imitation warm starts, and a thin real-game validation bridge. That combination
would turn the strongest surveyed gym into the strongest overall research platform.
