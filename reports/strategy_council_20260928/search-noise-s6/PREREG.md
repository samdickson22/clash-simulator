# S6: command delay and delay-aware fair search

Frozen before any S6 game, including development games. Implements the October 7
actuation-timing amendment items 4–5. Nominal hook delay is 22 ticks; measured
submission-to-first-native-observation latency is not an exact execution tick.

## Protocol

Player B, S2–S5 family: single public root, horizon 160 ticks, search every 10
ticks, poll every two ticks starting at tick 90, 63 candidate/style rollouts,
at most 21 unchanged public candidates, balanced/pressure/defense C56 mixture.
No action-dependent wall-clock deadline. The S1 pinned runtime and native binary
remain byte-identical. Delay implementation is search-side Python orchestration
of existing native primitives; no engine or gamedata semantic changes.

128 worlds × two seats per cell. Planning decks: eval/eval_ood, train-supported,
role-frequency weighted. Opponent decks and inference prior: train only. Families:
20 Hog 2.6, 18 each Hog EQ/Firecracker/MM, Royal Hogs/Furnace, X-Bow, bait,
Goblinstein, AQ. Shuffle deck order; swap decks across seats; cycle script style
balanced/pressure/defense by pair index. Five cells, in this order:

1. clean-d0: exact public deduction, no sensor noise/latency, d=0, unaware (S).
2. clean-d22-unaware: identical clean inputs, command delay 22.
3. clean-d22-aware: identical channel, delay-aware rollouts (S-d).
4. T3-N97-d22-unaware: S5 T3-N97 sensor and frozen S4 tracker v3, delay 22.
5. T3-N97-d22-aware: identical noisy channel, delay-aware rollouts.

Noisy cells retain frozen board/HP/own-HUD/event noise, image age four ticks with
probability .98, otherwise eight; event recall/precision .97/.97; no injected tap
failures. Frozen S4 tracker and dependencies, including N97 radius .0682, are
copied unchanged. No tracker tuning. Clean deduction uses public events only.

## Command and planning contract

Only the evaluated player's commands are delayed; scripts keep their established
cadence. One outstanding command. At submission the own belief reserves cost and
cycles the submitted slot (empty until refill), with command identity and due tick
visible. Actual engine state changes only on execution at submission tick + d.
Reservation and engine spend are separate representations; applying the reserved
command must not debit a second time or cycle twice. Ordinary engine rejection
remains; rejected commands release reservation. No retries. Pending blocks new
decisions, and the blocked poll count is recorded. Delay is configurable in the
channel; study values are fixed by cells.

Aware search creates a pending candidate in the root before rollout. It advances
the public model to the due tick, simulating the opponent meanwhile, then applies
the candidate once. Subsequent own script commands use the same single-outstanding
delay channel at the original 10-tick rollout decision grid. Opponent rollout
actions retain their original immediate cadence. Horizon stays rooted at t+160,
not 160 ticks after arrival. Unaware search uses the original immediate rollouts.
At d=0 both planner modes dispatch to the unchanged native scorer exactly.
The ledger is player state, not an engine change; native physical state retains
unspent resources until execution, while its accompanying belief reserves them.

## Seeds, freeze and preflight

World seeds 9782000001+1009*i and sensor seeds 9882000001+1009*i, i=0..127.
Schedule RNG 9781100001; bootstrap RNG 9781100003. Development worlds
9780800001+1009*i, sensors 9880800001+1009*i, i=0,1,2. Planner world+100000+seat,
sampling +1, legacy +2; audit through +4. Sensor channel SeedSequence indices
board/HP/HUD/events 0..3, latency sensor+500+seat, taps sensor+700+seat.
Audit retained report text/receipts/NPZ metadata on 01 and 04 against all historical
studies, explicitly including S1–S5. Any detected collision or scan error blocks
games. Report missing archives as limitations, never claim unobserved disjointness.

Before confirmation: inherited tracker tests; channel/rollout unit tests for exact
due time, reservation, duplicate submission rejection, single spend/cycle, failed
execution, wait, horizon and seat handling; three full development games comparing
d=0 aware vs unaware action hashes/counts/ticks and the original Player B; five
terminal timing pilots, one per cell, with outcomes suppressed. No outcome-based
implementation changes. Correctness fixes during preflight are logged; a bug after
confirmation freeze stops the study and is reported. Final manifest freezes all
execution/analysis sources, runtime, schedule, execution map, tests and preflight
receipts. Read-only S1–S5 audits plus S4 tracker hashes before and after games.

## Inference

Exactly 1,280 identity-valid immutable terminal receipts, 128 partition successes
and two supervisor successes required before outcomes are inspected. Win=1,
draw=.5, loss=0. Average both seats per world. NumPy default_rng(9781100003),
10,000 shared paired-world bootstrap resamples of 128 worlds, percentile 95% CIs.
Report all cell scores/CIs. Primary: clean-d22-aware minus clean-d22-unaware;
PASS iff lower bound strictly >0. Secondary: T3-N97-d22-aware minus
T3-N97-d22-unaware, same rule. Descriptive latency cost: clean-d0 minus
clean-d22-aware, with CI. No multiplicity adjustment, optional stopping, tuning,
outcome exclusions or outcome-dependent reruns. Independently recompute raw
receipt identities, counts, scores, aggregate hash and every bootstrap interval.
Report rejection, pending/blocked counts, tracker diagnostics and game CPU hours;
meter operations/preflight separately without double-counting child CPU.

## Operations and technical reruns

Games/tests on 04/08 only, nice >=10 and one native/BLAS thread. 128 fixed
partitions: even on 04, odd on 08; at most 64 active game workers per host,
further reduced for other jobs and supervision. Leave at least 16 threads for
T5/loaders; total project processes <=96, <=16 with fleet-console-users >0.
Recheck capacity; pause verified own worker PIDs if a console arrival reduces
capacity. 01 is light collector; 05 code/docs/small results only. No borrowed
hosts planned. Copy only S6-owned files with rsync -c; keep bulk runtime/receipts
fleet-side and mirror small artifacts to 05. No commits, data deletion, broad
process killing, tailscale/crontab changes or forbidden hosts.

S1–S5 technical-rerun rule: skip immutable valid terminal receipts on resume;
restart identical incomplete inputs only after verified technical failure with
fresh attempt labels, preserving logs and current-state receipts. Wrong identity
or changed frozen hash is a hard failure. On disappearance stop collection and
report; never assume workers died or duplicate active work. Keep PROGRESS.md and
RESUME.md current.
