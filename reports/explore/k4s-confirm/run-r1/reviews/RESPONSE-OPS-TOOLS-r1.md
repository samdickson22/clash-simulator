# Author note on SOL-REVIEW-OPS-TOOLS-r1 (APPROVE_WITH_FIXES, 5 MINOR) — fixes applied 2026-10-11T20:32:18Z

1. checkpoint.py validates the phase against the allowlist and the tag against a safe pattern, and shell-quotes the job and phase in
   its remote command. launch_phase.sh validates the phase, job name and copier core.
2. checkpoint.py v2 does the following:
   - flags STOP files, missing or unparseable fields (per-host try → anomaly, never "healthy") and progress staleness;
   - classifies supervisor exit by its structured reason and the expected block total (1950 per host);
   - checks for a running, non-zombie supervisor.
3. checkpoint.py checks the copier through the current hub receipt identity (pid, pgid, start_ticks, cmdline sha, uid;
   not zombie or stopped), confirms the source receipt has the same pid and active=true, and flags copier health
   staler than 300 s. There are no hard-coded PIDs.
   OP-6 load (answer b): frequent checks no longer scan complete.json on the timing hosts. Flags are counted from
   the verified hub copies on 05, and the remote command only reads progress, the exits directory, stop files and
   the process table.
4. launch_phase.sh waits until the hub AND source receipts name the NEW detached copier PID for this job, phase and host,
   and fails if that copier exits first.
5. stage_reporting_ns.sh requires every runtime input and job file, refuses links that resolve into the source job,
   and on 03 runs the frozen idle_services pin with the identity check. The reporting launch already re-pinned 03
   separately at 20:07:46Z (PROGRESS).
The running reporting jobs are unaffected; these helpers are used for monitoring and future phases only.
