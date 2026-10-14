VERDICT: REQUEST_CHANGES

Diff-only round 2 fix-check on 127x05, offline, against commit `3e09133d23528041703845b7fb11715960ba5ca4`. Read the round 1 review first and retrieved the candidate sources/diffs with `git show <commit>:<path>`. Paths below are relative to `reports/explore/k4s-confirm/run-r1/`; live counterparts are under `/mpac/sdicks02/k4s-runner/run-r1/`. No real SSH invocation, network request, or host contact occurred. All executions used local scratch directories; the Python staging suite and integration checks additionally ran in an isolated network namespace. No repository edits. The only retained new artifact is this review.

The fixture regression is closed. The script closes the original stale-log and failed-probe defects and restores the parent on ordinary failures and signals, but cleanup still depends on Bash starting without errexit, and two local parser paths can report false success.

1. **P1 — Inherited errexit can abort cleanup before restoring the parent.** `end-staging/a4/ro1-results-r2.sh:22`, `:27`, `:29`, `:30`.

   `set -u` does not clear an existing `-e`. A fresh `/bin/bash -c` can enable errexit through an exported `SHELLOPTS` or its `BASH_ENV`; the launch does not explicitly disable it. The EXIT handler removes all traps, then executes the results chmod as an unguarded simple command before attempting the parent chmod. If that child chmod fails with errexit enabled, Bash exits from the handler and never restores the parent.

   Concrete local reproduction using the extracted body and the production invocation form `/bin/bash -c`: begin with parent 0555; supply `SHELLOPTS=braceexpand:errexit:hashall:interactive-comments`; let mkdir create results and deliver TERM to its parent shell; fail only `chmod a-w -- "$P/results"`. The shell exits 1, emits no `__RC`, and leaves the parent **0755**. The operation trace contains the enabling parent chmod and failed child cleanup chmod, but no restoring parent chmod. With the same injected failures and no inherited errexit, the parent becomes 0555 and the token is 87. Adding `set +e` only at entry to the scratch EXIT handler also restores the parent and preserves token 87.

   Make cleanup independent of inherited errexit, and ensure failure of a child cleanup command cannot skip the checked parent restoration. Add the combined signal/child-cleanup-failure test with inherited errexit. This is a conditional environment robustness defect, not a claim that either remote host currently exports these options. Round 1 finding #1 is therefore only partially closed.

2. **P2 — Out-of-range tokens can wrap to exit status zero.** `end-staging/a4/ro1-results-r2.sh:57`, `:60`.

   The regular expression accepts every integer spelling of one to three digits, including values outside the process exit-status range. Passing that string directly to Bash `exit` reduces it modulo 256. In an otherwise unchanged scratch copy, with only the hardcoded transport and LOG redirected locally, a fake transport emitting exactly `__RC=256\n` and returning 0 makes the script exit **0**. The same happens for 512 and 768; 999 becomes 231. These are malformed protocol outputs, not values the current remote body intentionally emits.

   Validate the numeric range before exiting (at least 0–255, with deliberate decimal handling), and reject an out-of-range token with 255. Add boundary cases 255/256 and the zero-wrapping values. Anchoring and limiting digit count alone do not establish a valid exit status.

3. **P2 — Failure of the token-count command falls through to success.** `end-staging/a4/ro1-results-r2.sh:58`, `:59`, `:60`.

   `|| true` suppresses a `grep -c` error. If that command exits 2 without stdout, `n` becomes empty. `[ "$n" -ne 1 ]` then emits an integer-expression error and returns 2; inside the OR condition this is false, so with SSH status 0 the refusal branch is skipped. The final exit still uses the captured success token.

   Concrete local reproduction: the scratch transport emits `__RC=0` and returns 0; a PATH shim delegates all grep calls to the real binary except `grep -c`, which reports a simulated read error and exits 2 without output. The script emits `[: : integer expression expected` and exits **0**, despite failing to establish token cardinality. A nonnumeric count also reproduces the false success.

   Check parser-command failures and require a successfully established count of exactly one. An absent or malformed count must enter the failure branch, rather than relying on a numeric comparison that itself can fail. Add the failing-count regression; consider counting the validated lines in Bash to avoid this extra probe.

Round 1 closure and test evidence:

- **#1, parent restoration: partially closed**, as described above. With ordinary shell options, mkdir failures, partial enabling-chmod failures, result chmod failures, TERM/INT/HUP during the writable window, and unexpected ERR/EXIT all restored the parent when restoration was available. A transient initial parent-restore failure retried successfully and retained 98. Persistent restoration failure produced exactly one token 88 and the original cause (98, or 96 for a mkdir failure); it did not silently report the original failure alone.
- **#2, stale log token: closed.** Parsing uses only the current `out`, and nonzero SSH status overrides a current token. Historical success followed by a current transport failure returns 255. Missing, duplicate, unanchored, negative, trailing-junk, CRLF, and four-digit tokens were rejected. The separate parser defects above remain.
- **#3, failed probes: closed.** Each hostname, realpath, pre/post find, pre/post stat, and ls assignment checks its status before using stdout. Local injection with empty and misleading nonempty output returned the appropriate refusal codes 90, 92, 84, 82, 81, and 83. Writable and nonempty results were separately refused with 99 and 89.
- **#4, parentless r8 fixture: closed.** `end-prep/s3s9s10-r8/tests/fixture_guard_job.py:213` adds the synthetic engine-speed source file. Its S9 runtime now has 35 files and 27 directories, including the required parent. Existing runtime staging/S5 consumer and runtime/bundle/guard integration bodies pass; the staged results directory is empty and 0555. Reverting only the fixture change in a scratch candidate returns the inventory to 34 files/26 directories and reproduces the RO-1 parentless refusal in `tests/test_r4_s10.py:126`. The helper's parentless refusal test remains unchanged and passes.
- The supplied shell suite reran successfully: **25/25, FAILS=0**. Scratch mutations removing cleanup, discarding each find/ls failure, restoring historical-log parsing, ignoring SSH status, or ignoring token multiplicity all made the relevant tests fail. These tests discriminate the original fixes, but lack the three new failure cases above.
- The complete candidate suite independently passed **1318 tests in 186.07 seconds** under Python 3.12.12. The three r8 helper bodies and the two affected integration bodies also passed under Python 3.8.10 normally and with `-O`, and Python 3.12.12 with `-O`. Python 3.8 runs invoked those bodies directly with minimal fixture/exception-context support because pytest is not installed in that interpreter; they are not claimed as full pytest runs. The committed suite receipt separately reports 1318 passes in each of four modes.

Trap ordering and write scope:

- Traps are installed before guards and before `WRITABLE=1`; signals during guards performed no chmod or mkdir. The flag is set before enabling writes, including protection against a chmod that changes the mode and then fails.
- The main path restores the parent immediately after mkdir. A single TERM between successful restoration and flag clearing caused a harmless second parent restoration, preserved 87, and left both directories 0555. Normal completion performed no extra EXIT cleanup. With ordinary options, the EXIT handler preserved intended refusal tokens and used 86 only for an otherwise unclassified exit.
- The remote body contains no file-writing redirection, copy, removal, or manifest update. Its successful mutation trace is exactly `chmod u+w parent`, one nonrecursive `mkdir results`, `chmod a-w parent`, and `chmod a-w results`. Failure cleanup touches only those same directory modes, potentially repeating chmod. It creates no runtime file or second directory; local logging remains on 05. A refused execution can retain the newly created results directory, including a writable child if its chmod fails; successful completion checks that both directories lack write bits and results is empty.

Artifact integrity:

- All **127 tracked files** in the reviewed A4 and r8 trees matched their live copies byte-for-byte, both initially and at the final check. The live r2 script mode is **0555**. All **92 SHA256SUMS entries** match committed bytes.
- Script SHA256: `1f8d9b44644362cfe26f38ae37267c19125292cd6d15c2a52f2dafa418d10f63`.
- r2 script diff SHA256: `ca83911b71380b80a3f751657c722686a6a9f1a6517f2c43c8caff97b96503b8`.
- Fixture diff SHA256: `828403ba391b2e2630adc750332edb29318811efa4c78f5d92b29ff630c08200`.
- r8 SHA256SUMS SHA256: `9cd0374c51e49445f06a96df6e975a2242f95b80635a76177072f3975e6e0b16`.
- S10 remains byte-identical to round 1, SHA256 `9c634a8955a46741fa921e4ad9f813dd0038f6784945f5db0a7a514502376868`. No r8 file was added or removed; the only changed Python source is the two-line fixture addition. Other changes are README/response/progress notes and checksums. Both supplied diff hunks exactly match the corresponding committed source differences. `bash -n` passed.
