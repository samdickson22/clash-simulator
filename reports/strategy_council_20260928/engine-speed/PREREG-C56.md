# Stage 5 C56 confirmation preregistration

Registered before any held-out evaluation game. This design fixes the estimand,
configuration, schedule construction and decision rules. Before launch, a sealed
manifest must pin the final validated code, binary, inputs and exact schedule.
Development/parity/template/timing probes are excluded from strength estimates.
No confirmation game has run at registration.

The player is srp-pub-mix-C56. Configuration: K=1; horizon160 ticks; interval10;
balanced C56 own continuation; equal balanced/pressure/defense opponent-model
mixture; script choice, no-op, script top4, every legal champion ability and16
sampled public-legal placements. There is no qualified C56 policy, so no policy
proposals. Candidate duplicates are removed in that order. Stable improvement
requires score > incumbent +1e-9. Leaf is defense-v2 +0.08 times elixir difference
/16, with terminal win +2, loss -2, draw0. Decisions occur every5 ticks starting at
90; search runs every second decision. C56 opponent scripts retain their existing
rule of never activating champion abilities.

The player receives only a v5 public packet, exact own HUD fields and timestamped
accepted public events. Enemy resource balance and resolved hand/cycle are
computed from public history. The deck prior is the frozen human C56 catalog,
reconstructed from train-role perspectives only. Hidden slot order is not claimed
known. Unobserved combat fields use deterministic model defaults; they are not
read from the real battle. Only unresolved opponent identities/order and an
independent rollout RNG are sampled. Exact simulator-state reconstruction is not
claimed by this public model.

Run256 games in128 paired matchups. Each pair swaps the planning seat while
preserving decks, initial deck orders and world RNG seed. Planning decks are
sampled by frequency from eval/eval_ood role perspectives. Common deck identities
may also occur in train; the holdout is the frozen human-data role. Opponent decks
are sampled by human train frequency, matching the declared prior. Select19
matchups each for Hog2.6 and Hog EQ/Firecracker/MM, and18 each for Royal
Hogs/Furnace, X-Bow, bait, Goblinstein and AQ. Family assignment is mutually
exclusive in the order Goblinstein, AQ, exact Hog2.6, Hog with EQ/Firecracker/MM,
X-Bow, RoyalHogs/Furnace, bait. Other decks are outside this stratified estimand.
Opponent styles rotate by pair index through balanced, pressure and defense,
giving86,86 and84 games. Schedule generation RNG3420700001. Game seed for pair i
is3420718301+1009*i. A seed audit of all reports, including ignored files and
binary game seed arrays, is required before launch. Any collision blocks launch;
replacement seeds require a dated amendment before evaluation.

Score wins as1, draws as0.5, losses as0. Primary pass requires pooled score >=0.55
and matchup-bootstrap95% CI lower bound >0.50. The defense-style cell must also
have score >=0.55 and CI lower bound >0.50. Bootstrap128 pair means with replacement
for the pooled interval and defense pair means for that cell,10,000 resamples,
NumPy RNG40404041. Use percentile2.5/97.5 endpoints. Report all seven family cells
and each opponent style, including counts, scores and intervals; family intervals
are descriptive. Report champion opportunities, attempts and accepted uses by
champion, rejected plays, and ability action choices.

There is no optional stopping, outcome exclusion, adaptive schedule, post-outcome
retuning or second confirmation attempt. Crashes retain artifacts and block a
final verdict until the same pinned run resumes or is declared invalid. A changed
algorithm requires an explicitly reported new study, never silent receipt reuse.
A failed statistical gate is a completed negative result, not permission to tune
on confirmation outcomes.

Timing includes public sensor conversion, history assimilation, candidate
construction, model-root construction and search. Use one execution thread,
nice10, with pregame resource initialization and warmup excluded. Report p99/max
for all decisions and searched decisions. Any wall decision >0.25s fails the
observed one-core budget. Record concurrent host load. A separate eight-game
native-core parity gate and >=200 exact root action/score/continuation comparisons
must pass before evaluation. Root/core timings alone do not establish the fair
player's budget. Strength and timing verdicts are separate.
