# PREREG-K4S run r1: manual P2 replacement-cycle checklist (Proposal M)

Authority: coordinator Option A (COORDINATOR.md afe83faa), standing policy P2 (adc12f36), Proposal M (2c847954).
Every cycle is run **by hand**; no new code is executed (round.py/round.sh are shelved). Frozen tools only:
`replace.py`, `schedule.canonical`, `launch.sh`, `run_qualification.sh`, `stage_k4s.py`, `export_staging_extras.sh`,
`idle_services.py`, `barrier.reporting_release`. Reviewed helpers: OA-1 `mirror_k4s.py`, `tools/launch_phase.sh`.
Outcomes stay SEALED: commands read only launch/exit/admission/ACK/descriptor/ledger metadata. Game files are only
hashed (frozen replace.py). Any failed check = STOP the procedure, keep evidence, escalate to the coordinator.

Cuts (P2): about 08:40Z, 11:10Z and 13:20Z, before the apt-daily / apt-daily-upgrade timers on 127x03/127x04. Each
cut ends phase `replacement-r{N-1}` and starts `replacement-rN` in namespace `k4s-confirm-replacement-rN`. Jobs:
03 `/mpac/sdicks02/jobs/clasher/<ns>`, 04 `/mpac/sdicks02/jobs-k4s/<ns>`. Every remote command block runs under
`bash -euo pipefail`. Every time is copied from `date -u`.

## 1. Stop (both hosts)
- Read `<ns>/<phase>/launch.json` on each host and check host, dispatch_sha256 (= history) and supervisor_pid.
- Touch the owned STOP target `<job>.STOP` on both hosts and record the UTC.
- Read the FINAL `owned-supervisor-admission.json` after the supervisor exits. Prove, with `ps -eo pgid,pid,stat`
  (command success checked, zombies ignored), that the supervisor PGID and EVERY recorded worker-group PGID have no
  live members.
- Read `supervisor-exit.json`: host, reason (`owned_STOP` expected), completed / failed / unstarted lists.
- Any other stop cause (not owned_STOP, apt, or motd foreign_compute) = escalate.

## 2. Drain (both hosts)
- The completed-ID set (`find <phase>/*/complete.json`, checked exit) must equal the supervisor-exit completed list.
- For every completed block, the hub copy on 05 must have:
  - `hub-ack.json` bound to hub 127x05, source host, job, phase, block, and `complete_sha256 == sha(complete.json)`;
  - `hub-ack.returned.json` bound to the ACK sha.
- Write `STOP-COPY`. The copier PID from the hub admission must exit.
- Final copy health must show `revoked=true`, with no lifecycle or fatal error.
- The hub AND source admissions must be `active=false` with the same identity as the copier that exited. Only then
  remove `STOP-COPY`.

## 3. Inventory (05)
- Copy phase metadata only: launch, supervisor-exit, stop-reason, pids/, descriptors/, exits/.
- Build the hub view from this run's history phases only (`rounds/history.json`). For each block, require:
  - an ACK binding;
  - a descriptor equal to its dispatch row on the same host;
  - `canonical()`;
  - no duplicate id.
- Copy `ledger/blind-ledger.json` to a WORKING ledger. Run frozen `replace.py` once:
  - source phases = the two stopped phases;
  - dispatches = all history dispatches;
  - hosts = 03 and 04.
- Validate before publishing:
  - all rows canonical;
  - new ledger events == the failed blocks of the stopped phases;
  - every new replacement is in the dispatch;
  - exact 3000/900 logical coverage, each logical block exactly once.
- Gates: cumulative lost ≥150 primary or ≥45 guard, or ledger max `replacement_k` ≥8 primary or ≥6 guard = escalate (no
  launch). k is the frozen 0-based index (count = k + 1). Since the r2 audit (F5), the stricter count reading of Option A's
  "within 2 of the k limit 11/9" applies (count 9/7 = index 8/6); see `rounds/r2/RECEIPT-ERRATUM.md`.
- Publish: save `blind-ledger-before-rN.json`, promote the working ledger, and write `dispatch/replacement-rN.json`.

## 4. Stage (both hosts, fresh namespace)
- `export_staging_extras.sh <job> extras.tar` on the 05 freeze worktree. Copy it to the host and check its sha.
- Run `stage_k4s.py --job <job> --overlay .` from the extracted 391d2006 overlay (04: `--base` and `--inherited-pin`
  from `jobs-k4s/k4s-prep-20261011/base-s1`).
- Extract the extras into `<job>/repo` and link `STOP -> <job>.STOP`.
- Overlay 175/175 equal to `frozen-overlay.sha256`.
- PREREG r3 copy with sha 9650972d….
- Launch `run_qualification.sh` detached (NICE=10).

## 5. Finalize (both hosts)
- Qualification:
  - `QUALIFICATION-FINISHED`, TESTS-PASS, QUALIFIED and BELIEF-QUALIFIED present;
  - the receipt is PASS with all checks true, the host and job match, and runtime_pin_sha256 == sha(runtime-pin.json).
- Runtime-pin maps (files, native_source, inputs, inherited pin, plan) equal the smoke job's.
- Every pinned file, native-source file and input re-hashed equal.
- Carry-over copied from the smoke job and full-hash checked:
  - FROZEN-K4S 416f6e51…;
  - SMOKE-PASS (03 d3ed1c61…, 04 5c4b7606…);
  - smoke-admission (03 e338db63…, 04 9c4d636f…).
- Dispatch copied and its sha checked. No `owned-supervisor-admission.json` present.
- 03: frozen `idle_services.py` pin = PID 2180947, start_ticks 139691386, cmdline 16152ceb….
- Authorization = the 20:04:59Z bindings, with `reporting_jobs`, phase, dispatch path/sha and policy citations
  updated. `reporting_jobs_note.ruling` cites: windowed-rounds ruling COORDINATOR 76887b33 at 22:10:17Z (windowed
  dispatch superseded), Option A afe83faa at 22:11 UTC (commit 22:11:53Z), P2 adc12f36 and Proposal M 2c847954
  (see `receipts/AUTHORIZATION-CITATION-ERRATUM-20261012.md`). Frozen barrier PASS (176 files) on both hosts.

## 6. Prelaunch (both hosts)
- The cut's timer has fired (`systemctl list-timers` LAST time after the cut).
- Quiet read v2 (coordinator ruling after the 09:08Z test; supersedes the first inline command, which counted the idle
  boot-time `unattended-upgrade-shutdown --wait-for-signal` helper). Run exactly `rounds/r3/quiet-read-v2.cmd`
  (sha256 08aabe92…), one ssh per host, and record the full stdout and the exit code of EVERY read:
  `bash -c 'set -euo pipefail; for u in apt-daily.service apt-daily-upgrade.service; do printf "%s=%s\n" "$u" "$(systemctl is-active "$u" || true)"; done; P=$(ps -eo pid=,lstart=,comm=,args=); test -n "$P"; M=$(printf "%s\n" "$P" | grep -E "[0-9]{4} +(apt|apt-get|apt-check|dpkg|unattended-upgr|update-notifier|check-new-rele) " | grep -vF "/usr/share/unattended-upgrades/unattended-upgrade-shutdown --wait-for-signal" || true); H=$(printf "%s\n" "$P" | grep -F "/usr/share/unattended-upgrades/unattended-upgrade-shutdown --wait-for-signal" | grep -v grep || true); printf "helper=%s\n" "$H"; printf "maint_lines=<<%s>>\n" "$M"; printf "maint=%s\n" "$(printf "%s" "$M" | grep -c . || true)"; printf "who=%s\n" "$(who | wc -l)"'`
  Quiet = rc 0, both units not `active`, `maint=0`, `who=0`, and `helper` shows at most that exact helper. Record its
  PID and lstart; a change from the pinned baseline (03 PID 2368, 04 PID 2296) is noted but is not a FAIL by itself.
  Two consecutive quiet reads 30 s apart are required. A non-quiet read is retried up to 3 more times at 30 s intervals;
  without two consecutive quiet reads it is a FAIL: STOP and escalate.
- Stamps: `release-upgrade-available` younger than 24 h minus the round window; `updates-available` newer than
  `/var/lib/apt/lists`. If either is stale: one ordinary login, wait for the checks to exit, re-read.
- Record the next timers.
- 03 read window (COORDINATOR 89b28b6d, sequencing in P2 adc12f36), only if the coordinator has DECLARED it: confirm
  that the 03 phase has exited (supervisor-exit, no owned groups) and that `apt-daily.service` / `apt-daily-upgrade.service`
  are inactive. Then post "03 quiet" and hold the 03 launch until the builder posts "released". P2 timeout: 30 minutes after the coordinator's GO
  to the builder. On timeout, proceed with rN and tell the coordinator. The window is DECLARED for the ~08:40Z cut (P2).
  The "quiet" post states whether any K4S qualification or other owned process is running (audit F5 disclosure).
- Cut 2 (~11:10Z) read window for the perception owner on BOTH 03 and 04 (coordinator, same handshake): after the joint
  STOP and 04's apt-daily, quiet-read v2 on each host; when both have two consecutive quiet reads, post "03/04 quiet"
  (with the qualification/owned-process statement). Hold the r3 launch on EACH host until the coordinator forwards that
  host's "released"; per-host 30-min timeout from the coordinator's GO, after which that host proceeds.
  Only then do the motd/timer reads above. If no window is declared, there is no hold.
- Escalation gates clear.

## 7. Launch (per host)
- Copier first (`launch_phase.sh`: registration bound to the NEW copier PID, job, phase and host), then the frozen
  `launch.sh`.
- Confirm on each host:
  - `replacement-rN/launch.json` host and dispatch sha;
  - `host-admission-replacement.json` admitted with 0 foreign, 0 active, no console;
  - the supervisor alive.
- On any failure: owned STOP on every launched host, prove shutdown, keep evidence, escalate.
- Append the phase to `rounds/history.json`.
- Commit `rounds/rN/RECEIPT.json` with every hash, then post "round rN receipt committed <sha>" to the coordinator.
  From r3 on (audit F3/F4), persist under `rounds/rN/evidence/` and hash in the receipt:
  - step 1: the final `owned-supervisor-admission.json`, `stop-reason.json`, `supervisor-exit.json`, and the `ps -eo
    pgid,pid,stat` census output with its exit code;
  - step 2: the completed-ID set, the ACK/returned binding listing, the final `copy-health-*.json`, the hub and source
    `owned-copier-admission.json` records, and the hub-view listing;
  - step 4: extras-tar sha, overlay check output (175/175), PREREG copy sha, stage output;
  - step 5: qualification receipts, the `pin.verify` output, the idle-pin read, the authorization, the barrier output;
  - step 6: the quiet-read stdout and exit code, the stamp and timer reads;
  - step 7: the `launch_phase.sh` output, the copier pid files and both copier registrations, `launch.json`, the host admission.
  Every time is an exact `date -u` value (no `~`, no rounding).
