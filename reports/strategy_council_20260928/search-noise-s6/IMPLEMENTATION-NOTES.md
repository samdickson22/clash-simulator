# S6 implementation

All modifications live in search-noise-s6. The S1 manifest runtime and native
binary are copied with verified hashes, never rebuilt or modified. Tracker v3
and its S4 dependencies are copied verbatim; frozen-s4-inputs.json excludes only
the S4 evaluation harness, which S6 necessarily replaces.

delay.py provides a configurable CommandChannel (default 22 ticks), a
PendingCommand and a DelayedRoot. The root holds the unchanged physical public
engine model plus a reserved own belief and pending identity/due tick. Reserved
cost/slot changes are never applied to the physical engine; apply_discrete at
execution is the one and only engine spend/cycle. This preserves resource-cap
and engine rejection semantics. The belief reservation projects own regeneration
and refill while outstanding, and never expires at the predecessor's 16 ticks.
Receipt counters enforce submitted = executed + outstanding; no retry exists.

DelayAwarePlanner subclasses the existing C56 planner. Awareness is an explicit
flag; disabled or d=0 delegates directly to the old scorer, without extra RNG
draws. For positive delay, candidates remain unchanged. Each candidate gets a
pending root and three native rollouts. Python orchestrates native clone, step,
select_action, apply_discrete and evaluate; there is no engine implementation
change. The own candidate executes at t+d; subsequent own rollout script plays
also use one outstanding delayed command. Opponent scripts retain the original
instant action and 10-tick rollout grid. The leaf stays at t+160; commands due at
or after that boundary do not affect the leaf. Native stepping is a no-op after
terminal, and native evaluation supplies the existing terminal/leaf value.

The simulator harness reserves at submission and blocks further decisions until
execution/rejection. Its actual command channel applies in the same seat order
as before, after both controllers choose. Pending info is visible as the player's
pending_info public own packet and channel.pending. The inherited noisy sensor
streams and image-age behavior remain unchanged. The shadow ledger does not add
new own-HUD observations or change the S5 noise model after acknowledgment.

Games are partitioned into 128 fixed indices on 04/08, at most 64 concurrent each.
The supervisor counts host-wide workload threads, reserves four process slots
for launch/monitor activity, and uses cap 80 unattended (16 below the hard 96)
or 16 with fleet-console-users >0. A capacity reduction signals only verified,
unreaped direct children with SIGUSR1; they preserve terminal receipts and exit
with technical code 75. Such partitions resume identical incomplete inputs with
a fresh capacity attempt label. All prior logs/current-state remain. A 5-second
poll bounds detection; the next Python boundary handles the signal. No stopped
processes are hidden from the count. Other failures stop further launches.

Independent recomputation reads raw receipts only after the complete barrier.
compute_audit.py reads each host's own top-level GNU time logs; supervisor time
already contains reaped child CPU, which is never added a second time. Small
transfers and final report rendering are unmetered and disclosed.
