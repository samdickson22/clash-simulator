# Public SRP preregistration

Original protocol frozen 2026-10-04T08:08:35.990451+00:00, before any evaluation game.

Existing Git HEAD: 95feeb0e525ee1665360df6e28116b01c3436ecf. No commit was made because the task explicitly forbids
Git commits. HEAD does not identify the uncommitted implementation. Exact runnable
code and config identity is the SHA256 content manifest in manifest.json, including
all workspace Python engine/actor dependencies, native Rust source/extension,
canonical gamedata, deck files and checkpoint. Config SHA256: 3248617040f21bd9d47038cf2daa66a2891b038c17937d790fb08b841b2e61a6.
Planner SHA256: a55a16f6c50d94afa0084c38a6a073fce0a2de2f6b46fa54881f7f11232d2864. Analysis SHA256: b7a6fc266712d91b3927f1d2237934073f52cc9a39b6b3fde8bc170de2e6fd29.

Players are srp-pub and srp-pub-pol, K=4 each, native 160-tick horizon, 10-tick
continuations, balanced own script, balanced StrategyBot opponent model, defense-v2
leaf plus unit elixir weight, planning every second five-tick decision. Candidates
are script choice, no-op, script top four and 16 random legal placements; policy
variant substitutes eight top-probability legal policy actions. Same candidates
are scored in every sampled root. Full public masks only; no true-state legal mask
is queried by the planner. Policy is v7r4h s2902 1M, CPU, recurrent state updated
every decision with executed own actions and zero public reward. No fitting.

For EACH player, primary holdout games are balanced 0..85 seed 70000019,
pressure 0..85 seed 71000022, defense 0..83 seed 72000025, totaling 256.
Candidate decks are development.json; opponent decks training.json, roles_v2.
Game g has candidate seat g modulo 2 and matchup seed base+floor(g/2)*1009.
Both seats share ordered decks sampled by the original OQ/eval helper. Canonical
level 11 P16, public-v4, five-tick decisions, max_ticks 6001, original terminal
and HP tiebreak rules. Public scripts use the same checkpoint builder/projection.

Score is win 1, draw 0.5, loss 0. Matchup-cluster percentile bootstrap retains both
seats, 10,000 resamples, RNG 20261001, exact copied oq_report.boot implementation.
PASS requires pooled score >=0.55 with 95% lower bound >0.50 AND defense score
>=0.55 with lower bound >0.50. Otherwise FAIL. The two player verdicts are separate;
no multiplicity-adjusted superiority claim. No outcome-based tuning or exclusions.

Secondary, for EACH player: Hog 2.6, 64 games, balanced 0..21 seed 73000028,
pressure 0..21 seed 74000031, defense 0..19 seed 75000034. Same opponent role and
statistics. Paired score difference versus recorded privileged srp_xm_c256 on
identical role/style/base seed/game; include only complete common seat pairs and
report actual N. Head-to-head versus the stochastic s2902 1M policy: 128 games,
seed 76000037, games 0..127, holdout candidate/training policy decks, paired seats;
Torch seed matchup_seed+271828. Report score and matchup-bootstrap CI, no pass bar.
Total planned 896 games. Checkpoint opponent sees its normal public actor inputs;
critic outputs do not choose actions. Candidate policy uses zero critic arrays.

Cost selection used partial, non-evaluation script trajectories with seeds
991001..991004, never these evaluation seeds. K=4 chosen for headroom: measured
max whole-decision wall 0.1360/0.0970 s. K=8 was near/over the budget across repeats.
Runtime logs include CPU and wall totals, maxima, over-250ms counts, search calls,
placements and rejected actions. Single-thread inference and at most three nice-10
workers. These measurements test throughput and tails, not an OS scheduling guarantee.

No early stop based on results. Interrupted work resumes missing games with the
same specs. If a required external stop prevents completion, analyze only the
largest common even game prefix across each role's cells and label INCOMPLETE,
never PASS. Unexpected exceptions are retained and block completion until resolved;
any code amendment must be timestamped with affected games identified. Worker
receipts bind manifest hash. Report all planned cells, failed actions and budget
overruns. Copies of original OQ setup/statistics live here; original files remain
read-only. Public board reconstruction limitations are in DESIGN.md.

## Amendment 1: deterministic reconstruction fixes

2026-10-04T08:15:53.951122+00:00 before any revised-run game.
The original 14 completed games and source/manifest/protocol are preserved under
invalidated-v1. All three original workers failed on the public token
FreezeIceGolemite/AreaEffect. The revised constructor maps that alias to the
canonical Ice Golem death-field template. Review also found full shields on
visibly damaged bodies; these now receive zero shield. Both changes implement
public identity/consistency rules. All 896 games restart; none of the early
outcomes enter revised analysis. Their existence means this is an amended
preregistration, not a claim of wholly unseen seeds. K, candidates, priors,
continuations, seeds, counts, and statistics are unchanged. No strength tuning.

Fresh validation: 1,600 synthetic public roots across all 16 cards and 22 observed
identity/kind pairs; 16 policy top-eight parity cases against production inference;
6,002 resource/cycle timeline ticks including both phase changes; eight paired
hidden mutations and eight denied-read cases. All pass. Updated whole-call K=4
CPU means 0.09643 / 0.07057 s, wall maxima 0.13638 / 0.09791 s. The content manifest
now binds the revised code and this amendment.

## Amendment 2: coordinator's derived-public-state rule

2026-10-04T08:43:49.930181+00:00 before any revision-3 evaluation game.
The coordinator required exact use of calculable opponent state. All workers were
stopped between games, leaving 232 complete revision-2 games. Those games, source,
manifest and preregistration are preserved under superseded-v2, with cell counts
in results/superseded-v2-counts.json. None enter the restarted primary analysis.

The dedicated derived_public_state.py module uses exact public elixir tracking and
all surviving hand/cycle possibilities. Known quantities are fixed, never newly
sampled. Once the hand multiset and queue agree across all possibilities, use the
resolved state directly. A private UI slot permutation is distinguished from
available hand membership; a consistent representative handles still-unknown UI
slots. Otherwise sample remaining hidden identities/orders conditional on all
public plays and refill timing. Fresh engine RNG is always independent of truth.
P16 has no Collector or other resource-generating card; there are zero estimate
fallbacks. No hidden true resources are read by the module or planner.

Tests now mutate unrevealed deck identities and engine RNG only, with denied-read
guards for all private player fields. Full-game replay audit: 24 complete recorded
games, 115,223 ticks, 23,058 decision observations; exact terminal and tower-HP
reproduction. Elixir error rate 0/23,058, maximum error 0. Hand membership determined
18,516/23,058 = 80.3018%, zero errors; queue/next card determined 21,913/23,058 =
95.0343%, zero errors. Every determined slot/queue position also matches truth.
Six unit tests cover exact resources, early derivation, all-eight cycle order,
conditional unknown identities/positions, and inconsistent-history rejection.
Fresh privacy checks, 1,600 public-root template checks, 16 policy top-eight parity
cases, and 6,002 synthetic timeline ticks pass.

The full restarted evaluation will also report hand/queue certainty fractions
across every decision. Primary/hog/head-to-head seeds, counts, pass bars, checkpoint,
K=4 and candidate budgets remain unchanged. Fresh benchmark CPU means K=1/4/8:
srp-pub 0.03618/0.09622/0.17568 s; srp-pub-pol 0.03211/0.07033/0.12025 s.
K=4 wall maxima 0.14671/0.10307 s; K=8 random-candidate max 0.25431 s.
This is the coordinator-directed amended preregistration, not a claim that no
previous versions ran these seeds. Restart every one of the 896 planned games.

## Amendment 3: policy startup warmup

2026-10-04T08:49:02.318275+00:00 before any revision-4 evaluation game.
The first revised worker decisions exposed PyTorch's one-time lazy validation
imports: one cold call reached 0.26365 core-s / 0.32196 wall-s. Stopped all workers
between games and preserved all 18 revision-3 receipts and source under
cold-start-v3. No tracking mismatch or rejected action occurred.

Resources now runs one synthetic public policy call during initialization and
discards that recurrent state. Real games still initialize recurrence afresh and
reset their specified Torch seed. This changes startup timing only. On the first
100 decisions of the recorded policy-assisted balanced game, every action was
identical, first decision 0.07878 s and maximum 0.08376 s. Resource setup including
warmup cost 0.9463 wall-s, separate from model checkpoint loading and game decisions.

All 896 games restart again; prior receipts are excluded. Strategy, derived-state
rules, K=4, all seeds and statistical bars are unchanged. Privacy checks still pass.
Warm benchmark CPU K=1/4/8: srp-pub 0.03641/0.09732/0.17739;
srp-pub-pol 0.03271/0.07206/0.12218 s. K=4 wall maxima 0.14242/0.10752 s.
Report startup separately and retain every runtime decision over 250 ms.
