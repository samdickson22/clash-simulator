REJECT

Reviewed UTC: 2026-10-18T02:40:41Z (from date -u)
Reviewer: gpt-6.1-sol, high correctness review. Review only; no source edits, commits, deployment, remote commands, runtime imports, heavy jobs, delegation, or coordinator messages. This report is the only file written.

Blocking findings

1. [P2] The common default preempts existing per-job defaults.
   Files: main/bot/fullpool/run/env.sh:4 (existing assignment at :20) and main/bot/exit/filler.sh:16 (existing assignment at :19), under /tmp/clasher-cards4-publish-5d98zvo_.
   With NUMBA_CACHE_DIR unset, the original code selects /mpac/sdicks02/jobs/clasher/bot-fullpool/numba-cache. The insertion sets it first to /mpac/sdicks02/cache/numba, so the unchanged := assignment no longer selects the established job cache. This also changes which cache is created/used by future fullpool/filler launches and can discard reuse of their existing compiled cache. I reproduced both before/after values by evaluating only the cache assignment statements, without running either launcher or mkdir. This conflicts with the stated preservation of existing per-job cache behavior. Unconditional assignments such as deckopt3/run.sh:22 and livediag/run_l16_cadence.sh:16 do still win; conditional assignments do not. Preserve the existing conditional cache selection when arranging these insertions, and account for inherited defaults from upstream wrappers as well. If replacing these established defaults is intentional, that behavioral change needs to be reconciled with the stated scope before approval.

2. [P2] The fleet audit can silently omit standard launchers that the tracked patch explicitly covers.
   File: /tmp/clasher-numba-fleet-audit.py:25-27; compare /tmp/clasher-numba-default-patch.py:18.
   The fleet selector accepts runtime/cache/cpu_job.sh text or a narrow filename prefix. Evaluating that selector against the pre-patch tracked standard files excludes bot/detach.sh, bot/exit/cal_eval.sh, bot/exit/cpu_feeder.sh, bot/exit/fit_eval.sh, and bot/exit/gpu_queue.sh. None appears in any of the three fleet plans. For example, gpu_queue.sh executes arbitrary queued commands directly with bash -c (main/bot/exit/gpu_queue.sh:19), and cpu_feeder.sh launches through detach.sh (:54), so these paths need not pass through patched cpu_job.sh or bot/env.sh. Thus the plans do not establish complete standard-launcher coverage. This is a demonstrated audit-selector gap, not a claim that every omitted file exists on each remote host. Use the explicit standard-launcher list in the fleet audit and record presence/absence, exclusion, or coverage for each allowed host before claiming coverage; include existing writable instances that require the default.

Verified scope and shell behavior

- Independently verified all 42 manifest entries against their scratch checkout HEAD: matching before/after SHA256 values and exactly one insertion of the requested comment/export, with no other shell-byte changes. All 42 passed bash -n again.
- Independently verified all 219 prospective plan rows (127x01: 26; 127x04: 104; 127x08: 89): exactly the same two added lines, no removed lines, and matching host identity. Listed paths are within the standard bot checkout or bot-* job paths; none names a source/repo/code snapshot, archive, runtime root, or Mac wrapper. No 03 or 09-18 plan is present. The plan diffs do not change runtime roots, pins, commands, or priorities.
- Placement is before the first executable statement in the 42 full tracked files, preserving shebangs and initial comments. The export works under bash -eu for unset/empty values and preserves a nonempty caller value, including spaces and glob characters. Empty values deliberately take the default because the specified expansion uses :-.
- The tracked patch helper writes only the two scratch checkouts. The fleet audit is read-only. Its owner-write-bit filter is not independent proof of effective remote writability or symlink-free ancestors. Full deployed file contents and filesystem metadata were not supplied in these JSON plans; I did not remotely re-audit them.

Running-job and deployment limits

Existing Python processes keep their current environment; this export does not repair them retroactively. The plans contain no application/writer implementation, so safe replacement of scripts currently being read by Bash is not established by the diffs. Apply any approved deployment using same-directory atomic file replacement with mode preservation and a before-hash check, rather than truncating/re-writing an active script inode. The local patch helper's write_text is appropriate only for its scratch checkouts. No running jobs should be restarted or signaled by this environment-only rollout. Cache-directory creation and effective writability on 01/04/08 remain deployment prerequisites; these plans themselves do not create or verify the directory.

Separate release-documentation discrepancy (pre-existing; not an environment-patch finding)

The requested phrase "live16402d symlink" disagrees with the supplied implementation. release/reports/cards/release/live16402d/tools/release.py:80-86 publishes a staged directory using renameat2 with flag 1 (RENAME_NOREPLACE), called at :160 after freezing/inventory checks. Its :66-68 and :134 reject symlinks at the target and its ancestors. It does not implement publishing live16402d as a symlink; do not substitute a symlink operation for this documented directory publisher.

Also, release_host.sh:26-28 rejects either existing destination before doing work. Given the already-created r1-cards4 directories, simply rerunning that wrapper after the cache fix will stop. Resumption must use the existing release.py verify/create operations with the established pins/receipts while preserving r1-cards4; this review does not authorize overwriting/removing it or changing release.py.
