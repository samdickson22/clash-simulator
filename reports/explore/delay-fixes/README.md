# Delay fixes exploration

Completed: 12,500 terminal games, 1,250 paired seeds in each of ten arms; 24 current checks passed. [RESULTS.md](RESULTS.md) and [results.json](results.json) contain both legacy and matched-cadence contrasts. All own leased reservations/workers cleared at 03:06:50Z; home 08 sim/reduction work cleared at 03:19:49Z. The chronology below retains superseded controller/cap snapshots; [completion receipt](receipts/completion.json) and final manifests are authoritative.

Non-confirmatory simulation, no training or human eval/heldout inputs to the sims. The seed
namespace is `2**48 + 50000 + i`. No frozen registration, artifact, or gate seed
is edited. Existing S6 and gate-(b)/(c) proposer/driver files remain unchanged.

`src/clasher/analysis/loss_review/delay_fixes.py` supplies a flag-guarded planner
subclass and an exact simulation runtime queue. Flags default off:
`symmetric_opponent=False`, `max_outstanding=1`, `forward_prior=False`.
`opponent_delay=22` and `opponent_interval=10` parameterize the enabled opponent
model. A separate 4-command opponent capacity allows its ordinary cadence to
continue across its22-tick lead without imposing our legacy one-command lock.
The physical opponent script gets the same settings as the rollout opponent.
The live pixel-verification actuator is not replaced by this exploration runtime.

Pending opponent commands are invisible. Physical commands live in a driver-owned
queue outside the BattleState. Own physical HUD and public board change only at
execution, and the planner's enemy card-event stream receives only accepted
executions. The planner sees own reservations, never the true enemy pending
queue. Its native roots come from the established public reconstruction with a
train-deck posterior and independent simulation RNG. Rollout opponent commands
are freshly simulated hypothetical future decisions with a22-tick execution lag.
The opponent decision cadence is10 ticks, not extra hidden reaction truth.

The queue stores `(submitted,due,action,card,cost)` per accepted submission.
Availability masks subtract every reserved cost and remove each reserved slot;
reserved cycle entries remain explicit and are never prematurely refilled.
Physical roots retain the current unspent HUD state. Native continuation applies
all own known pending commands at their individual due ticks, debiting/cycling
once through the engine. Each rejection/completion releases only that command's
reservation, without a physical refund. Wrong-slot-card execution is forbidden.

Native `rollout_commands` is additive, explicitly called only by the enabled
variants. Legacy `rollout`, `search_candidates` and S6 default scoring are
untouched. Own continuation uses S6's cadence-before-execution tie rule, stable
score tie handling, the same160-tick horizon and16 sampled candidates plus script
proposals. Tests compare single-command native scores to original S6.

Forward imitation rolls a *fair hypothetical* root to `t+27`, with known own
pending commands and the rollout opponent's newly simulated future commands,
but no speculative new own candidate. Endpoint executions are included. Public
v5 projection copies only own HUD and visible public entity features. Future D1
uses simulated accepted public events, never sampled hidden hands or queues.
Proposals must also pass the current mask and use the same card in the same
slot, so forward elixir/refill cannot authorize a present double-spend.

Both imitation arms use the released main02 v1 EMA checkpoint read-only,
SHA256 `d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed`,
CPU fp32, in-memory T=1. The gate-(b) matched-count replacement pattern is
reused without calling its driver or touching its frozen artifacts/seeds.
Play-conditional top8 card/tile proposals replace random extras, retaining WAIT,
script proposals and each decision's exact baseline post-dedup candidate count.
This is a dev/exploration behavior comparison, not an imitation gate outcome.

Arms:
- U0/U27: own d0/d27; opponent immediate (legacy asymmetry).
- S0/S27: own d0/d27; opponent d22 with10-tick decisions.
- N2/N4: S27 plus own command capacity2/4.
- I0/IF: S27 plus current/forward-state released-v1 proposals.

All arms share seed, decks, opening shuffle, seat, style and helper RNG seeds.
There are five train-catalog deck archetypes and25 matchup cells; seats alternate
and opponent style changes each25 seeds.1000 seeds balance all25×3×2 strata
as closely as this sample allows. Abilities are disabled on both physical sides.

Behavior uses the loss-review `Game`/`extract` tool. Added pooled metrics:
- Submission silence: no next submission in `(submitted,submitted+27]`;
  only complete27-tick follow-up windows count.
- Execution silence: no next accepted execution in `(executed,executed+27]`,
  also with complete windows. This avoids conflating invisible commitment with
  server-visible execution.
- Post-execution submission silence: no new submission in the27 ticks after
  an accepted execution. This answers a different timing question.
- Pending blocked decisions: blocked10-tick decision polls / all decision polls.
- Interplay gap: mean seconds between successive accepted executions.
Under4 arrivals retain the ledger's lane-incursion-onset definition, not individual
bridge crossings. Outcomes use terminal win/loss/draw, with draws separately
recoverable; win is not inferred as1−loss.

Bootstrap resamples paired seeds, shared across arms, and recomputes pooled
numerator/denominator ratios. CIs are percentile95%, pointwise, exploratory and
uncorrected. The latency-asymmetry contrast is the paired loss difference-in-
differences `(U27−U0)−(S27−S0)`.

Compute: six allowed lease hosts attempted via wrapper v2 with22/26 workers,
whole-job declarations26/30. PSS/refusal receipts are preserved. One PSS refusal
on16 moved its unstarted seed block to authorized home08,26 workers. The supported
foreground wrapper is used because detached admission failed its supervision
key twice. No wrapper bypass or limit alteration. Each lease host has at most
one active task shard; all game/reduction paths there are lease-local. The initial GPU guard used utilization. Following the coordinator's00:46Z authorization, new shards use the shared throughput guard: only a fresh GPU-job interval throughput metric more than5% below its measured baseline can pause this driver's workers. Missing metrics and idle GPUs are exempt. Utilization is logged only. Workers use SCHED_IDLE and refresh affinity away from active GPU-job cores and SMT siblings. New shards stop04:15Z; workers stop04:29Z.
Full per-game reductions and source/runtime artifacts remain on08 and leases;
only compact receipts, summary JSON and the report are returned to05.

Provenance limitation: while locating the released checkpoint, the implementation
agent inadvertently opened the first 65 lines of the existing
`imitation/RESULTS-v1-offline.md` summary, which includes summarized gate-(a)
heldout outcomes. No raw heldout data were opened or loaded by the sims, and
those outcomes did not inform the arm definitions, checkpoint choice, or
comparisons. This exploration is not outcome-blinded.

Legacy decision wall latency includes GPU-guard pauses and is retained separately. New shards record active-wall latency with completed/live pauses removed, raw wall and process CPU latency;
CPU decision time is also retained. These sims do not qualify a live 200ms
end-to-end deadline.

Coordinator resource updates supersede the initial pool sizes: 13/15 fully
vacated at ~00:02Z, with no further launches until released; 09/14 now use
15-worker pools (19 whole-job processes declared); 11 and home08 use26.
The stalled initial guard required three high samples, which aliased against
periodic GPU readings. New shards resume after one high sample, and an idle
GPU with no compute process permits CPU work. During the 13/15 drain, verified
own workers were resumed only after the GPU compute process list was empty.
Monitor-reported pause counts during that brief drain can overstate actual
paused time. Resource restarts preserve every completed game; same-schedule
resume validates semantic options and checkpoint SHA even when migrating paths.
Technical-stop receipts retain CPU already consumed. 16's restart was refused
for an existing Clasher process below the nice minimum, and was not bypassed.
The replacement controller is `recover_launch.py`; accounting is
`launch-recovery.json`. The original primary controller was stopped before
any further launch, so its unstarted list is a stale snapshot; p0225 finished
and is explicitly collected. Target remains1250 paired seeds per arm.

The actual00:10Z coordinator update declared11 down and authorized lost-shard
reruns elsewhere. The adaptive controller reruns that block on13, adopts
running09/14/home08 shards, and uses caps13/15=10,09/14=15,16=26,08=12 after
the current26-worker home shard drains. New16 admission passed. Live caps are
in `resource-policy.json`; no new work targets11. `launch-adaptive.json` is
the current accounting; prior manifests remain as chronological evidence.

At00:24Z the wrapper's declared12GB PSS stop on16 was accepted (sampled
peak13.09GB). Its main had exited while supervised workers remained; only
verified descendants of that labelled supervisor were resumed/terminated.
103 completed games were preserved. The same25-seed shard resumed on16 with
16 workers, and future16 pools use16. Consumed child CPU and the wrapper stop
receipt are retained. Future shards were reduced to5 paired seeds to support
quicker drains under smaller pools; ongoing25-seed shards were adopted without
duplication. `fine_launch.py` / `launch-fine.json` are current. New labels include
the hostname to keep retry receipts distinct. `resource-policy.json` applies
before each new launch. The empty, stopped p1000 attempt was archived lease-local
before the same seed range could be assigned in5-seed shards.

Throughput guard API is shared with the A/B owner. Atomic pause-clock JSON contains `paused_total_seconds` and `paused_since_monotonic`; active clock subtracts both cumulative and ongoing pauses. Baselines must come from explicitly configured job logs, never GPU utilization or cumulative training rates. Home08 drains for the A/B owner’s30-minute coexistence measurement; its lane remains parked through that measurement. The A/B owner handles opt-in process-CPU decision deadlines in its own producer/consumer paths. This fixed-work delay experiment has no decision-budget deadline.

## Final reduction

Full game reductions are retained on 127x08. After all simulation shards drain,
run `final_reduce.py` there with `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`,
`OPENBLAS_NUM_THREADS=1`, `PYTHONPATH=src`, and the existing project Python.
It validates exactly 1,250 common terminal exploration seeds across all eight
arms before computing 5,000 paired bootstrap resamples and the compute audit.
The runner sets idle scheduling and periodically excludes observed GPU-job
cores and their SMT siblings. Plotting uses a separate task-local environment
if Matplotlib is unavailable in the existing environment.

`source-hashes.json` identifies the isolated leased binary and source snapshot;
`review-source-hashes.json` identifies the implementation, tests and reducers
in the shared checkout. These are distinct because other owners may change
shared engine files while this study continues to use its unchanged binary.

The final 16 lane accepted an aggregate-PSS refusal and retired. Its unstarted
shard was requeued on the remaining hosts; admission was not retried on 16.

## Approved matched-cadence controls

Before inspecting any study outcomes, a code audit found the retained legacy
S6 opponent rollout cadence is 3 ticks, whereas enabled symmetric rollouts use
10 ticks. The coordinator approved two additional controls, R0/R27: the existing
enabled S0/S27 native path with opponent lag 0 and cadence 10, same 1,250 seeds.
Physical opponent cadence is 10 in all arms. The controls use a separate
`lag-only/shards/` output tree. Their opponent capacity is 4, nonbinding at
zero lag. No original arm, implementation, checkpoint or candidate budget changes.

The addition was recorded using actual `date -u` at 2026-10-09T02:02:09Z.
Config SHA256: `9e0cf7befc10bd99f145148b2e72ff68997beed1c6de00ff21d67efc3fac44b6`.
See `lag-controls-config.json` and `receipts/lag-controls-addition.json`.
The report retains legacy-protocol comparisons and shows matched-cadence
lag-only contrasts side by side. If cutoffs prevent completion, each partial
control contrast pairs only the same completed seeds in its lagged arm; the
loss-cost difference-in-differences uses their common four-arm subset.
