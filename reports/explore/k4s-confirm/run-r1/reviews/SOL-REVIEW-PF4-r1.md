VERDICT: REQUEST_CHANGES

Reviewed offline on 127x05 against commit `3ce34dd86577a65bdf5a38a683355650c3e64b86`, before host use. No SSH or host contact and no repository edits. Tests and fault probes ran only in scratch. Paths below are relative to `/mpac/sdicks02/k4s-runner/run-r1/`, unless explicitly identified as frozen sources.

One blocking finding: C20 can turn missing post-warmup MHz evidence into a qualifying binding preflight. C15 and D4 are correct. The S10 pins and seven-bundle declaration are consistent. The swap protects the old/new identities and restores read-only directory permissions on the tested failure paths; its temp cleanup has a non-blocking reporting gap.

## F1 — P1, blocking: unavailable MHz evidence can qualify a binding run

**Locations:** `end-prep/s5s6s7-r7/k4s_end_preflight.py:950` (fallback), `:953` (gate disabled), `:956` (None accepted), `:1035` (binding calculation); `end-prep/s5s6s7-r7/CLASS-TABLE-PF4.md:97` (C20 incorrectly called SAME).

Excluding the warmup rows is appropriate. The unconditional fallback for fewer than two remaining rows is not safe for a binding run. It sets `passes=None`, leaves the check row passed, and permits exit 0. Neither `verdict()` nor the receive verification requires an available/passing MHz comparison. The latter exports `qualifying` without exporting MHz availability (`k4s_end_preflight.py:1199`). S7 consumes that qualification (`k4s_end_launch_gate.py:571`, `:574`, `:580`) and does not independently require MHz evidence.

**Concrete failure scenario:** on a 1200-second 04 hold with a 300-second warmup, the sampler emits at least 60 passing rows early in the hold, loses most subsequent sampling, and emits just one more hold row at +1000 seconds. The total count passes `guard_samples` (`:925-928`), and the first-to-last loaded bus span passes the 900-second binding minimum. The frozen census/admission/block validators do not demand post-warmup coverage or reject a sample gap (`fleet_validity.py:230-283`). C20 sees one compared row, skips `compare_mhz`, and the run can be `passed=true`, `mode=binding`, `qualifying=true`, with bus band `proceed` and no valid MHz comparison.

**Reproduced:** a scratch fault-injection monitor continued servicing guard checkpoints but stopped emitting periodic samples between an early cluster and one final sample. I used the actual pinned frozen `fleet_validity` validators, not the fixture's no-op census/admission validators. With a scaled 0.8-second hold / 0.4-second warmup and the real 60-sample floor, it produced 92 hold rows, one compared row, a 0.720-second measured span (scaled binding minimum 0.2), exit 0 and `qualifying=true`. A separate execution of the unchanged pure `verdict()` with production 04 durations (1200 requested, 1000 measured, 900 required) also returned binding/qualifying with `passes=None`. The supplied short-hold test's setup likewise qualifies with zero compared rows; its assertions never check `qualifying` (`tests/test_r7.py:173-180`).

The frozen END explicitly raises on fewer than two measured MHz rows (`fleet_profile.py:59-62`) and fails a negative comparison (`end_reference.py:400-403`). This fallback is therefore a LOOSER branch, not SAME. It does not change the frozen END's eventual gate, but it opens the RC-9 launch gate without the preflight evidence intended to protect the limited END attempts. A sampler problem can be discovered only after a claim.

**Required change:** retain the post-warmup window, but make insufficient evidence prevent binding qualification. Distinguish a deliberately short diagnostic from a hold expected to provide post-warmup rows: the former may record unavailable and remain non-qualifying; the latter should fail closed when fewer than two usable rows remain. Add a long-hold/starved-sampler regression with adequate total samples and loaded span, plus a short-hold test asserting non-qualification. Correct C20 and the class counts. Recompute the S5 hash/size and every dependent S7/S10/vendor/TOOLS-FINAL/swap NEW pin before host use.

## N1 — non-blocking robustness gap: temp removal failure is not reported

**Location:** `end-staging/a4/pf4-swap-preflight.sh:38`; missing coverage in `end-staging/a4/pf4-tests.sh:36-46`.

After the first cleanup `chmod a-w` succeeds, `WRITABLE` is zero. Cleanup then temporarily reopens tools for writing and calls `rm`, but ignores that command's status. If removal fails and the final `chmod a-w` succeeds, the handler reports only the original cause.

**Reproduced scenario:** send incorrect NEW bytes and inject `rm` failure in scratch. The old file remained intact at 0444, tools ended at 0555, but `.k4s_end_preflight.py.pf4-new` remained at 0444. Output was only `__RC=74`, with no cleanup-failure indication. A subsequent invocation refuses at the temp-absence guard (`:52`, code 96). The operation already fails closed, so this is not a route to a successful corrupt install and is not the reason for REQUEST_CHANGES.

Report unlink failure explicitly, preserve the original cause, and verify temp absence when cleanup claims to remove it. Keep directory a-w restoration independent of removal. Add removal/reopen failures to the fault tests.

## N2 — retained STRICTER check can reject a healthy host

**Locations:** `end-prep/s5s6s7-r7/k4s_end_preflight.py:689-694`, `:1024`, `:1029`; class-table D5 at `CLASS-TABLE-PF4.md:110`.

D5 infers a login from an increase in processes whose comm name is `sshd`. A pre-authentication TCP connection can create such a process without an authenticated login. An idle scanner connection spanning a census sample gives counts 1, 2, 1: the summary reports a login and the 04 verdict fails even when the frozen guard's SSH CPU budget, bus and console checks pass. The frozen counterpart uses those guard checks (`ssh_budget.py:111-117`; `fleet_validity.py:223`), not daemon count. The census records comm/CPU information rather than authentication state (`telemetry.py:131-159`).

This risk is accurately disclosed in the package and has a written RC-2/RC-7 measurement-integrity rationale: conservative rejection of possible SSH-related contamination before a claim. It remains a coordinator acceptance decision, not proof that a login occurred. I found no evidence to estimate its frequency offline. Of the retained STRICTER rows, this is the identified healthy-host false-positive risk; I found no second deterministic mismatch like C15. If retained, describe the result as sshd-count growth and explicitly accept that conservative proxy; otherwise use evidence that distinguishes authenticated sessions while retaining the frozen interference gates.

## Identity and package consistency

- The package index is exactly SHA-256 `e50dea5c639863765f66a65e36e6a976dc84d1a787be68fccb0b7156bc3cc83e`.
- The final comparison of all 245 reviewed r7/r9 package files, PF4 artifacts, swap/tests, and fresh pf01 request/bundle/guard manifests against their committed blobs using `git show` found every live copy byte-identical. Both package SHA256SUMS files also verified: 132 entries for r7 and 93 for r9.
- Old S5 is `c779345116c1bf6c0ab28af8751a36489642c5b9c870326f516361f54bf115f5`, 76,609 bytes. New S5 is `c40e663bde4976d96e4de86ba991e23e7289adb9c47b21676eda816fc96e42d3`, 78,954 bytes. These match the script guards and the actual predecessor/current committed files.
- All six S10 TOOL_PINS match r7 tools and the r9 test vendor bytes. S7's preflight pin matches; S11's S10 sibling pin matches r9 S10 (`91534e2d...`, 70,250 bytes). The five other staged tools are byte-identical to r6.
- The frozen source files used for the comparisons were read with `git show` from the review commit and verified against their closure or bundle runtime pins and the local runtime at P′. No evolving worktree source was substituted.

## S5 class audit

The table contains exactly 51 rows: SAME 18, STRICTER 15, S5-ONLY 18. Its claim of zero LOOSER rows needs the F1 correction. I checked all 15 rows listed as STRICTER, including the 14 retained rows, and additionally checked C13, C18-C23, D4 and the duration distinction. Frozen abbreviations here follow the table: ER/EB/KB/KL are under `runtime/reports/explore/k4s-confirm/`; FP/FV/TE/TB/FR are under `runtime/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/`. T1 modules are under `runtime/reports/explore/t1/`.

- **A2:** S5 `:387-388`, `:1048` against FP `:11-14`, ER `:301`. The extra counted-host restriction is the declared run scope, not an affinity-like mismatch.
- **A8:** S5 `:399-400`, `:540` against ER `:127`, KL `:131-157`. A fixed manifest anchor prevents caller-selected code identity; keep.
- **A10:** S5 `:510-522` against ER `:101-102`, EB `:76`. Production assembly/sidecar checks intentionally exclude synthetic bundles; keep.
- **B2:** S5 `:1088-1099` against ER `:301`, EB `:77-79`. Compare-bundle/evidence path identity is justified by RC-3 and input binding; keep.
- **B3:** S5 `:1100-1102` against ER `:103-104`. No-follow/single-link input checks are justified confinement, and the staged receiver produces regular single-link inputs; keep.
- **B4:** S5 `:1103-1106` / host tool `:489-535` against FV `:138-142`, `parent_source_seed.py:62-74`. The minimal shallow guard clone is a declared S3 product, not a guessed host repository; keep.
- **B5:** S5 `:1107-1108` against EB `:80`, ER `:305`. Full repository validation protects frozen Git reads from indirection; keep.
- **B7:** S5 `:537-561`, `:1117-1118` against KL `:131-157`, ER `:128`, `:327`. Closure verification before import and DELTA/inventory identity are justified; keep.
- **B8:** S5 `:707-718` against ER `:144-156`. Executing-file/closure identity before use protects imports; keep.
- **C2:** S5 `:769-778` against ER `:96-110`, `:292-294`. Added constant equalities agree with END's native/corpus requirements; keep.
- **C4:** S5 `:786-790` against FV `:112-114`, `:189`, and T1 side-file writes including `parent_source_seed.py:83`. Freshness is necessary for attribution. Reusing 04 pf00 should refuse; pf01 fixes that preparation issue.
- **C11:** S5 `:858-865` against ER `:363-365`, FR `:245-251`. The extra descriptor gate reads the freshly written admission file; keep.
- **C14:** S5 `:878-879` against ER `:371-374`, EB `:113`, FP `:13`. Every worker already verifies nice 10 before readiness; external renice changes the measured load. No frozen backend priority change analogous to its affinity narrowing was found; keep.
- **C15:** S5 `:883-887` against ER `:371-374`, EB `:115-118`, TB `:237-238`, KB `:99-100`, FP `:21`, TE `:77-88`. Correct: count equality avoids zip truncation; non-empty subsets allow every frozen tier width; disjoint pinned masks prevent cross-slot loading. Reference/census separation remains enforced by the earlier physical-CPU validation. Slot evidence is recorded before refusal and is AST-equal to ER's four-field expression.
- **D5:** S5 `:688-694`, `:1024-1029` against TE `:131-159`, FV `:223`, `ssh_budget.py:111-117`. See N2.
- **C18/C19:** S5 `:923-934` against TE `:185`, ER `:395-399`, FV `:230-283`. Sample-count and frozen validity checks remain intact, but cannot rescue missing post-warmup coverage (F1).
- **C20:** S5 `:941-956` against ER `:375-403`, FP `:59-62`. Window exclusion is appropriate; unavailable-to-qualification fallback is not equivalent (F1).
- **C21/C22:** S5 `:957-961`, `:583-594` against ER `:404-406`, TB `:450-469`. Post-run identities remain checked. The loaded-module check has a separate justified confinement role. I read the static runtime/name-gate evidence and late work-path imports; it is not an end-to-end host execution proof, but I found no concrete healthy-host refusal here.
- **C23/D4:** S5 `:966-974`, `:1028` against ER `:222-279` and `replay_load.py:249-256`. A background exit/cleanup exception must fail even when no check is open. D4 fixes that false success and weakens no integrity check.
- **A5/D6:** S5 `:393-394`, `:1035-1039` versus ER `:376`. The minimum preflight hold and END warmup are different quantities. The planned 600/1200-second holds leave ample rows on a healthy sampler; an exactly 900-second 04 request is not enough for a 900-second first-to-last sampled span.

## Swap and RC-6 assessment

The swap's old guards (`pf4-swap-preflight.sh:45-54`) check the correct host, real/canonical tools directory, regular non-symlink single-link old file, OLD SHA/size, absent temp and no tools write bits before enabling writes. The local source SHA/size check precedes the login (`:26`). The cleanup/signal traps precede writes (`:42-44`); the remote command clears BASH_ENV/SHELLOPTS and both body and EXIT handler disable errexit. Directory-restore failure is reported as 88 with its original cause.

Noclobber creates the temp exclusively on the ordinary guarded path (`:57`); its mode is set to 0444 (`:58`), and received stdin bytes are hashed and sized remotely **before** the move (`:59-60`). The temp and destination share a directory/filesystem, so `mv -T` replaces the file by atomic rename (`:61`). Tools a-w is restored before final SHA/size/type/nlink/mode/temp checks (`:62-70`). Success intentionally changes only the target file and transient tools permissions; the temp disappears. The 05 log is the sole additional intentional persistent write. Captured output, not a prior log, supplies the single exact decimal 0-255 token; ssh must exit 0 (`:78-85`). No successful corrupt-install path was found. N1 concerns failed cleanup only.

RC-6 SHA `6b6dbe1b5e23533f17f3054dc19828e865aa9a654114f8fee72ba2b07c0d9291` names seven bundles. Each declared bundle's tiers-pins SHA and guard path match its artifact. Relative to the six-bundle declaration, the only change is adding 04 pf01. Its request differs from pf00 only in `guard.job`; its bundle manifest also differs only in that field and matches the rd00-a00 comparison after removing the job field.

Pf01's manifest SHA is `9955d59e...`; receipt SHA `649dcea9...` binds that manifest, request `5244216f...`, host 04 and guard target `/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-pf01`. Runtime and measurement canonical hashes remain `fc3dbeb4...` / `42b8986d...`. I verified all 16 local guard-job inventory files (63,786,662 bytes) and absence of its side files/STOP markers. The S10 production dry-run independently passed, matched the recorded inventories and byte count 23,539,178,661, and verified bundle/guard byte equality. This verifies the prepared local artifacts; it does not claim they are already staged on 04. Replacing the committed/local end-launch declaration and rebuilding launch argv under the new roots remain the package's stated later steps.

## Local validation

- Swap suite: **33/33 PASS**, `FAILS=0`; no real ssh was executed.
- Full r7 S5/S6/S7 suite: **757 passed, 2 skipped**; the two skipped sibling-contract checks then **2 passed** after extracting their committed inputs into scratch. Focused S5 checks: **89 passed**. r7 tests under Python 3.8 `-O`: **15 passed**.
- Full r9 S3/S9/S10 suite under Python 3.12: **1318 passed**. The initial focused run had two mode assertions fail because the scratch login shell used umask 077 (directories ended at 0500); both passed with the documented umask 022. The full suite used 022 and passed. This was not a changed-pin failure.
- PF01-PF12 mutation rerun under Python 3.12 `-O`: **12/12 killed**, N12 survived. These tests catch the stated edits but do not cover F1's starvation/qualification case; PF10 actually preserves acceptance of unavailable data.
- Additional scratch probes established F1, the zero-row short-hold qualification, N1's leftover temp, and N2's process-count inference. No production file was changed by these probes.

Before host use, close F1 and refresh the dependent identities. N1 is a reported safe-failure cleanup limitation; N2 is the disclosed conservative operational decision for the coordinator.
