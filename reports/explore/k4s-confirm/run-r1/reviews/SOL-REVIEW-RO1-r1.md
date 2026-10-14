VERDICT: REQUEST_CHANGES

Reviewed on 127x05, offline, against commit `03d904d9a19f25fa553f867cf60addc867d8b210`, using `git show <commit>:<path>`. Paths below are relative to `reports/explore/k4s-confirm/run-r1/`; their live counterparts are under `/mpac/sdicks02/k4s-runner/run-r1/`. No repository edits, SSH executions, network requests, or host contacts. Local reproductions used disposable scratch directories.

Both items need changes before approval: the one-off script has three robustness defects; r8's production directory logic is sound, but its unchanged synthetic fixture now prevents existing runtime-staging integration checks from running.

1. **P1 — A failure after enabling parent writes can leave the runtime writable.** `end-staging/a4/ro1-results.sh:25`, `:26`, `:27`, `:28`.

   Starting with parent mode 0555, line 25 changes it to 0755. If the subsequent `chmod a-w results` fails, line 27 immediately emits `__RC=97` and exits without reaching the parent restoration. Local fault injection reproduced exactly that: token 97, parent 0755, newly created results still writable. A failing parent chmod likewise exits at 98 with no further restoration attempt. The mkdir-failure branch also ignores the cleanup chmod's status; forcing both failures returned 96 with parent 0755. There is no cleanup trap: delivering TERM immediately after parent chmod left the parent 0755 and emitted no token.

   Restore the parent immediately after mkdir, before any further child processing, and install checked cleanup for failures and catchable termination signals before enabling writes. Do not report a handled failure while silently leaving restoration incomplete. The ordinary mkdir-failure path does restore the parent when its cleanup chmod succeeds, but this does not cover the other paths.

2. **P1 — A previous log token can turn a current SSH failure into success.** `end-staging/a4/ro1-results.sh:36`, `:37`.

   Output is appended with `tee -a`, but the exit parser searches the entire historical log. Concrete reproduction using a local replacement for the SSH call: the first invocation logged `__RC=0`; the next emitted only a connection error and `__SSH_RC=255`. The second invocation exited **0**, selecting the earlier token. With a fresh log, the same failure correctly exited 255. This also affects interruption before a current token and logging failures that leave an older token as the last readable one.

   Parse only the current invocation's captured output; require a complete, anchored token with a valid value, and fail closed when it is absent or malformed. Keep the append-only log as evidence, not as the authoritative status source. Current remote refusals do propagate correctly when their token is appended: a current `__RC=97` with simulated SSH status 0 produced local exit 97.

3. **P2 — Permission and emptiness probes treat command failure as a successful empty result.** `end-staging/a4/ro1-results.sh:23`, `:29`, `:30`.

   Each `[ -z "$(...)" ]` checks stdout but discards the probe's exit status. If `find` fails without stdout, for example on a transient filesystem error, a writable parent can pass guard 94. Fault injection against a 0755 parent reproduced creation and final `__RC=0`; the required writable-parent refusal was bypassed. Similarly, a failed `ls -A` is interpreted as an empty results directory. With an unexpected hidden entry and an injected ls failure, the body still emitted `__RC=0`.

   Capture and check each command's status before interpreting its output, including both find checks and the emptiness check. Failed evidence collection must refuse; an error message on stderr does not make the current conditional fail closed.

4. **P2 — r8 breaks existing runtime-staging tests through a parentless synthetic fixture.** `end-prep/s3s9s10-r8/s10_stage_host.py:398`, `:412`; fixture: `end-prep/s3s9s10-r8/tests/fixture_guard_job.py:198`.

   The unchanged `world_files()` fixture contains no file beneath `reports/strategy_council_20260928/engine-speed`, so its S9 inventory has no such parent directory. The new unconditional parent requirement therefore rejects the runtime used by existing integration tests. I built and verified the actual synthetic S9 runtime (34 files, 26 directories): r7's runtime_component accepted it; r8 refused with the RO-1 parentless message. Executing the existing test body `tests/test_r4_s10.py:123` (`test_runtime_staged_at_base_runtime_p12_and_accepted_by_s5_layout`) reproduced that refusal before any login; its refusal receipt recorded an empty login list. `tests/test_flow.py:58` uses the same affected runtime fixture.

   Add a suitable synthetic engine-speed source file to the fixture so its inventory contains the required parent, retain the parentless refusal, and rerun the existing staging checks. The new helper tests alone do not cover this integration regression.

Verified properties and evidence:

- All **119 tracked files** in the reviewed A4 and r8 directories match their live copies byte-for-byte; none are missing. The live script mode is **0555**. All **92** r8 SHA256SUMS entries match pinned source bytes.
- Script SHA256: `73eeb3edc647c76a463133e7c7159f9fe558dc5aa3eb80e7fb952253bed22dd9`.
- Diff SHA256: `7161d83bf016c49e0e22cb8f18abec824f56ad44008ed9f0fec559bb75e2a9d0`.
- Host bases are correct: 03 `/mpac/sdicks02/jobs/clasher/k4s-end-r1`; 04 `/mpac/sdicks02/jobs-k4s/k4s-end-r1`. The target is directly beneath each base's `runtime-98566c032d0b`, with the requested council/engine-speed/results suffix.
- With functioning probes and stable paths, local tests rejected a wrong host (90), a symlinked parent (91), symlinked ancestor components (92), existing results files/directories/dangling symlinks (93), and owner/group/other write bits on the parent (94).
- Host input is restricted to the two literal case arms before command construction. Paths are fixed, and quoted arguments plus Bash `%q` preserve the remote body. Full command-construction tests through a local Bash replacement succeeded for both hosts; injection-like host arguments exited 2 before reaching it. Remote-login-shell compatibility remains an offline assumption: `%q` uses Bash shell syntax here.
- One SSH invocation is present, with `BatchMode=yes`, `ControlMaster=no`, `ControlPath=none`, and `StrictHostKeyChecking=yes`, plus the specified no-TTY/forwarding controls and nice 19. None was executed. The successful remote body creates only results and changes the two directory modes; it does not write runtime files or the runtime manifest. Its separate log is on 05.
- The pinned r7-to-r8 production diff exactly matches s10-r8.diff: the new helper/constant and directory argument in S10, and the S11 pin update. No prior tests or other production source files changed or disappeared. S11 correctly pins S10 SHA256 `9c634a8955a46741fa921e4ad9f813dd0038f6784945f5db0a7a514502376868`, size **70224**.
- On the existing local production manifest, directory planning changes **416 to 417** directories, adding exactly results. Component construction and receive-request validation preserve all **4316** file records, sizes, SHA256s, and modes; the helper does not mutate the manifest. Production-component construction used an isolated S9 return stub, not a claimed full production S9 verification. Existing S9 verification calls and other checks remain in place.
- All three new test functions passed when executed directly under Python 3.8, normally and with `-O`. No pytest installation was available, so this is not a full pytest-suite pass. `bash -n` passed. The exact receiver ran locally with a small pinned es_common.py payload; after a-w, results was empty and 0555, the import succeeded, and the file set/bytes stayed unchanged. Removing results reproduced the import-time PermissionError.
