# ExIt round-1 student screen — draft for coordinator freeze

Exploration lane; no multiplicity adjustment. The coordinator reviews and freezes
this file by SHA before any reporting game. Any later recipe, case, seed or metric
change requires a dated amendment before observing affected reporting outcomes.
Smoke/tuning outcomes never choose checkpoints or parameters on reporting seeds.

## Arms and immutable inputs

S-mix (teacher fraction0.5), S-teacher (1.0), S-human control (0.0) each fine-tune
from one common pinned init: selected v2, or explicitly released v1 if v2 has not
been selected. The init checkpoint SHA, human train/dev store/asset SHA, completed
teacher corpus manifest SHA, native binary SHA and source hashes are recorded
before fitting. Round1 teacher data stops at6M roots combined (~39M poll rows).
Only terminal SHA-sealed training games enter the teacher corpus. Held-out teacher
diagnostic games have separate fresh seeds and cannot enter any training store.

Each arm runs4883 optimizer steps ×8192 rows =40,001,536 rows, one GPU, same batch,
steps and schedule. These are T11 defaults: AdamW, lr3e-4, weight decay0.05,
2000-step linear warmup followed by qualified cosine schedule, gradient clip1.0,
EMA0.999; microbatch7168 for human forcing. Teacher all-four-slot soft CE is
accumulated in microbatches≤128 with denominators from the full effective batch.
No early checkpoint selection: use final-step EMA. Training seed2026100901 is
common across arms; model width192. Temperature0.1, rare-play weight4, value loss0
are fixed. Human wait thinning/IPW matches T11. Teacher pending-command waits are
unsupervised; expanded timed waits remain supervised. Human-only ratio0 dispatches
to the unchanged qualified T11 loss/optimizer. No training on evaluation roles.
Wall-time (~1 GPU-hour) is an estimate; report actual rows/s and GPU-hours.

## Cases and metrics

(a) Each student plays256 head-to-head terminal S6 games against the init policy,
using the gate(c) stochastic T=1 action adapter every5ticks, symmetric d27,
capacity1 and abilities disabled. Alternate seats by pair index. Report student
loss, win, draw and play/WAIT rates, with bootstrap intervals by game seed.

(b) Main metric: each student supplies both fallback and top8 legal play proposals
inside E1 deadline-enforced W-screen8 search, versus W with the init
fallback/proposer. Run600 fresh paired seeds per arm. Also run the common init-W
versus init-W reference on the same600 seeds. Loss change is student loss minus
reference loss for each seed; negative favors the student. The S-human control
uses the same reference and seed/deck/seat schedule. Both search players have
200ms end-to-end wall deadlines (including public observation, fallback sample,
top8 proposal, belief update, candidate generation, fair reconstructed root,
completed-root scoring and submission), horizon160, 10tick search cadence,
5tick fallback cadence, symmetric d27 and capacity1. Reserve8ms for return, as
in E1. Late/partial roots never count; use the same-packet fallback if no root
finishes. Fair information is own HUD plus public events; reconstructed roots
use independent belief/RNG. Record deadline hits, fallback use, completed roots,
overruns, proposer latency and command hashes. W-screen8 remains ON; no reserve
floor intervention. Leased hosts do no simulation work.

The five highest-frequency train archetype decks are fixed by the B2 frozen
catalog (bridge_wincon, siege, beatdown, bait, chip). Own deck=i mod5, opponent
deck=floor(i/5) mod5; both decks shuffled from the shared seed; seat=i mod2.
This matches the E1 25-matchup screen. Identical cases are used by every arm and
the reference. Each seed is one bootstrap unit; never treat poll rows as games.

(c) Teacher agreement: generate a held-out teacher slice of64 full terminal games
with B2's eight-deck teacher/opponent schedule on separate fresh seeds. Report
diagnostics at scored teacher-root rows with valid supervised labels and at all
eligible poll rows separately. At teacher roots, teacher play prevalence is
fraction chosen action<2304; student expected play prevalence is its stochastic
T=1 gate-play probability averaged over those states. Play recall is the mean student gate-play probability on teacher-chosen
plays (teacher self-recall=1.0). Also report the ratio of student expected play
prevalence to teacher play prevalence, top8 action agreement, and hard
chosen-action agreement.
Teacher WAIT rate is chosen WAIT prevalence; student WAIT rate is its expected
T=1 gate-WAIT probability. These probability-based rates avoid diagnostic RNG
noise and make an all-WAIT student fail. Report the corresponding free-running
rates from (a)/(b), including pending/timed waits as separate counters.

## Frozen kill rules and reporting

Kill an arm if play recall<0.50 of the teacher, OR student WAIT rate>
1.5× teacher WAIT rate on the held-out teacher-root slice, OR the upper bound
of the paired95% CI for metric(b) student-minus-init loss change is≥0.
A zero-play teacher slice, missing case, nonterminal game, SHA mismatch or
invalid observation makes the screen incomplete; it cannot pass an arm.
These rules explicitly guard the August Hog all-WAIT collapse. No NLL-only
adoption. A surviving exploration arm still needs registered confirmatory
gates and the L2 amendment before any live replacement or DAgger round2.

Use5000 paired bootstrap resamples, fixed bootstrap seed80991010, percentile
95% CI, resampling complete game seeds jointly for each student and reference.
For diagnostics, resample held-out whole games. No multiplicity adjustment;
every table says exploration lane and shows all arms, including killed arms.
Publish all256/600 case counts, terminal counts, init/student checkpoint SHAs,
training rows, corpus/input/runtime/plan SHA and deadline diagnostics.

## Fresh seed reservation and audit prerequisite

Proposed fresh reporting ranges (not admitted until audits pass):
- head-to-head4503601007370496+[0,256);
- paired fallback/proposer4503601107370496+[0,600);
- held-out teacher4503601207370496+[0,64).

Smoke/tuning uses4503601307370496+[0,32), separate from reporting and generation.
All arms deliberately share seeds within a metric; the three metrics are
disjoint. Existing references: `imitation/evaluation/seed_audit.py` (literal
inventory plus formula-range review), `reports/explore/e1/config.json` (E1
reporting/smoke ranges), B2 `PLAN.md` and source launch manifests (generation,
acceptance and stop-drill ranges), and `imitation/gates-bc/receipts/` seed
inventory/merge receipts. Existing audits do not admit these new integers.
Before freeze, coordinator obtains a new exact inventory and formula-range
review covering all prior provenance roots/hosts, with hashes and no overlap;
record the resulting audit SHA in the execution freeze. Exclude only this new
proposal and its generated inventories, never historical game provenance.
The runner refuses reporting execution without a passed seed audit containing
the entire reporting range and a matching coordinator-frozen plan SHA.

## Execution

GPU destinations:01 only after T11 release;09/13/14/15 only under their live GPU
leases and current resource caps. CPU games run on authorized home cores after
capacity release; nice≥10/SCHED_IDLE/setsid/taskset,08nice19 and owned stop file.
Protect MemAvailable≥24GiB and08cache services;08must vacate≤5minutes.
No heavy work on05. Stage and pack data under /mpac/sdicks02, never HOME; the
packed corpus preserves source-game seal hashes and is copied with SHA checks.
Keep runtime snapshots immutable. This worker supplies the runner and tests;
the coordinator owns B4 freeze and allocation of reporting games.
