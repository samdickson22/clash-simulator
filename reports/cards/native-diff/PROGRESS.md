# Native mixed-deck differential progress

2026-10-16 00:28 UTC: runner and deterministic 600-game plan prepared in the CARD
LEAD worktree `/mpac/sdicks02/repos/clasher-cards`. Measurement only; no engine edits.
Native on 127x08 verified SHA-256
`681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b`.

Plan: 122 ladder cards, 600 games of two eight-card decks, 3,600 ticks or game over.
Each card appears in 77–80 games; all 7,381 unordered card pairs co-occur in at
least one game. This is deck coverage, not proof that every mechanic pair fires.
Deployments and actual first-divergence evidence are counted separately.
Seed 6812026. Both seats start at 10 elixir and thereafter regenerate naturally.
Only public deploy/apply APIs are used during games. First mismatch is retained;
games continue to 3,600 ticks or Python game over, then replay the equal prefix
for phase-boundary diagnostics. Native panics are caught as BaseException.

Host job directory: `/mpac/sdicks02/jobs/clasher/cards/native-diff/` on 127x08.
All batch launches use setsid, nice 15 and BOT LEAD `cpu_job.sh`, N <= 16.
`run_batch.sh` records exact worker PIDs and waits on those PIDs. No process searches
or broad kills. Atomic `game-NNNN.json` files make worker restarts skip finished games.

2026-10-16 00:26 UTC: smoke launcher PID **1852172**, worker PIDs **1852249,
1852250**, both waited successfully (exit 0). Two games × 3,600 ticks matched.
Smoke is excluded from the final denominator because it exposed expensive-card
starvation in the action-selection policy. Corrected by reserving elixir for the
next least-played card instead of selecting only currently affordable cards.

Full 600-game batch launched on 127x08 with launcher PID **1886743**.
Worker PIDs in `batch/pids.tsv`; exit records in `batch/exits.tsv`.
The host-only config cache `config-681b5f2c.json` accelerates restarts.

2026-10-16 00:35:04 UTC: full batch completed, all **600** atomic game files;
**496 match / 104 mismatch (17.33%)**, **1,842,169 ticks**, **0 native panics**,
**0 Python exceptions**, **0 triage replay errors**. All 16 workers waited and
exited 0; PID and exit records copied to `job-records/`. All 104 first differences
have phase-boundary replays. 75 involve the known missing IceGolemite freeze
payload; 29 require deeper attribution.

Supplemental controls/deep triage launched on 127x08, launcher PID **1973576**,
same nice 15 / 16-CPU lease. `run_followups.sh` requires `batch/finished.utc`, then
runs 12 control workers and 4 replay workers, records and waits on every PID.
24 C56-only controls are separate from the 600-game primary denominator.
Full raw diagnostic/config tables stay on the host. Worktree `games/` files are
sanitized copies with source data tables/prototypes omitted.

2026-10-16 00:37:32 UTC: controls/deep triage complete. All 16 workers exited 0.
24 C56 controls: 12 with IceGolemite mismatch, 12 without match. All 29 other
primary mismatches have deeper histories and phase evidence in `triage/`.

2026-10-16 00:38:23 UTC: 12 focused mechanic-pair games complete, all match,
41,078 ticks. Launcher **2003561**, workers **2003705–2003716**, all waited and
exited 0. Combined with primary games they close all 12 sampled proximity gaps:
465/465 distinct pairs among 31 observed mechanic classes have encounter
opportunities. This does not prove every effect pair fired; abilities are not used.

Additional valid all-C56 scripted clock controls: seven games, all match.
Launcher **2047519**, worker **2056107**, explicitly waited, exit 0. Earlier
setup assertions on occupied tower tiles were corrected before these controls;
they were harness assertions, not engine exceptions. The earlier two successful
prototype controls and these seven controls are outside the primary denominator.

An optional 64-game C56 extension was prepared (`baseline-plan.json`) but **never
ran**: the 8-CPU request (launcher **2075965**, room waiter **2075969**) remained
queued and was cancelled by exact PID, then the 2-CPU request (launcher
**2116836**, room waiter **2116841**) also remained queued and was cancelled.
No baseline worker PIDs or result files were created. Pending claim cleanup is
checked by exact owned claim path; no process-name searches or broad kills.

2026-10-16 00:51 UTC: complete. `RESULTS.md`, `causes.json`, `game-causes.json`,
`coverage.json`, `metrics.json`, `provenance.json`, 600 primary `games/*.json`,
24 controls, 12 focused games and 29 compact deep replays are saved. All 104
primary mismatches are assigned exactly once: 75 known C56 IceGolemite, 15
new-card interactions, 14 C56-card timing failures in mixed contexts. C56-only
status for those 14 is explicitly unproven, not inferred from the failing card's
scope. No jobs remain intentionally active. No engine changes, commits or pushes.

Verification: runner matches the measured host SHA-256; Python and shell syntax;
600 complete unique primary results; exact cause-count accounting; all completed
worker exits 0; all first-tick phase replays succeeded; recursive evidence scan
finds no imported configs or embedded official source tables. Full raw evidence
and config remain on 127x08; repo evidence is sanitized.

Restart: copy this directory's `mixed_games.py`, `run_batch.sh`, and `plan.json`
to the job directory. Launch `run_batch.sh JOBDIR JOBDIR/plan.json 16 batch`
through the lease wrapper as above, recording the launcher PID. Do not start a
second batch while recorded workers remain active. Completed command/PIDs and
outcomes are recorded above; the optional baseline batch was cancelled before launch.

Launch command, from the host job directory:

```sh
setsid nice -n 15 /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 16 \
  bash ./run_batch.sh "$PWD" "$PWD/plan.json" 16 batch \
  > batch-launch.log 2>&1 < /dev/null &
echo "$!" > batch-launch.pid
```

Assumptions: level 11 defaults, no champion ability activation, no private mechanic
injection, action coordinates derived from Python then passed identically to both
engines. `Heal` is targeted according to its runtime resolved kind (current ladder
data uses Heal Spirit); Mirror waits for valid prior-card history.
