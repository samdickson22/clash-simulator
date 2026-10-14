# PF-4 package (COORDINATOR c14b40e8) — one package for Sol, then GO

Prepared 2026-10-14T01:39:31Z by the K4S runner on 127x05. Offline only; no host action since the 04 l00 preflight (00:57Z).

## 1. s5s6s7-r7 — S5 fix and class audit
- Production diff vs r6: `end-prep/s5s6s7-r7/DIFF-r7.patch` 2a98e2f55ff447fca198ce647be4e996d501253d3b961403f37d08b1e7197abc; tests diff `DIFF-r7-tests.patch` 1b6b4c6f725212cfbb626029987a18b2ea3a8bba20e590219fe15e16ffc283d3.
- Class table: `end-prep/s5s6s7-r7/CLASS-TABLE-PF4.md` 20801ea3eb210180983d38dbca81b7871cde1a63a5ff643e1376b0cca57df496 — 51 rows with file:line both sides: SAME 18, STRICTER 15 (C15 affinity FIXED; 14 kept, each with its ruling), LOOSER 0 (D4 fixed), S5-ONLY 18 (each citing its ruling); plus a dynamic-state section.
- Fixes: C15 affinity readback = non-empty subset of its pinned mask, masks pairwise disjoint; slot evidence recorded before any check with exactly the frozen END fields (end_reference.py:371-374); C20 MHz comparison only over rows after warmup_seconds as END does (fewer than 2 rows: recorded unavailable, not a gate); D4 an exception outside an open check now fails the run (was sealed passed).
- New S5 `k4s_end_preflight.py` c40e663bde4976d96e4de86ba991e23e7289adb9c47b21676eda816fc96e42d3, 78954 bytes; S7 PREFLIGHT_SHA256 re-pinned (gate 92e60241961daadf56ca1e90d8e3dd53c807b1e624e43caf64a929cec4a68c96); TOOLS-FINAL d45a10a0afeeb1e03cf536a8953175d24a599faa2ff382f74fb406b72e9f44db (only the preflight row changed). SHA256SUMS 2796b6301cf30738c0678f02e764949a70d02dcaee4bd9d370490731a8d1649a.
- Tests (worker; runner rerun pending/attached): 759 normal, 704 + 55 verifier skips -O, py3.12 and py3.8; 15 new in tests/test_r7.py incl. the observed 04 readbacks. Mutation PF01-PF12 12/12 both interpreters.
- Open for your decision (row D5): 04 "no login during the hold" counts sshd processes, so a pre-auth sshd fork (scanner, other user) fails the 04 preflight; kept under RC-2/RC-7.
- Offline proof: loaded_modules_check cannot refuse the production run (`pf4-evidence/loaded-modules-scan.txt`).

## 2. s3s9s10-r9 — S10 TOOL_PINS
- `end-staging/pf4/s10-r9.diff` b24b5b349a87203b5ecc34ff16ef4829ea711869449441bc39f9366e7c15d043: TOOL_PINS k4s_end_preflight.py -> the r7 bytes; S11's S10 pin; test vendor gate+preflight -> r7 and VENDOR_SHA256. SHA256SUMS e38a9f5b85ce9de0b16341f8659032aae521357c5c22f25421565b33527899a8. Suite 1318 x4 (`end-staging/a4/s3s9s10-r9-suite.out`).

## 3. Host step: one-file replace of <base>/tools/k4s_end_preflight.py
- Script `end-staging/a4/pf4-swap-preflight.sh` a200084183e4a52e69252408999730bda17ea97124fc3464f5cac9198e34f5fc: RO-1 r3 discipline (env -u BASH_ENV -u SHELLOPTS; set +e body and EXIT handler; trap before writes; restore-failed 88; Bash-only token parse, 0-255, one __RC line, ssh rc 0, else 255). Guards: hostname, real tools dir + realpath, old file regular single-link with OLD sha c779345116c1bf6c0ab28af8751a36489642c5b9c870326f516361f54bf115f5 / 76609 bytes, temp absent, tools without write bits. New bytes on the one login's stdin into an exclusive temp, 0444, NEW sha/size checked, mv -T over the old file, tools a-w, then final sha/size/mode/nlink verified; BEFORE/AFTER stat+sha printed; nothing else written. Local: the 05 source must equal NEW sha/size before any login.
- Tests `end-staging/a4/pf4-tests.sh` 0fc243bfff731b814e3cdbf853a7b67d79b456d767abb64804c24073b3f12d34, output ace984d119d5dff1e77cf6e2a2e4cfb549932e2d3a113464f7a359c5ead4b2aa: 33/33 PASS (all guards; chmod/cat/sha/mv failures; TERM/HUP during write, INT after mv; restore failure -> 88 cause 77; SHELLOPTS errexit; local token, stdin==new bytes, env-cleared argv, source mismatch refuses before login).

## 4. 04 needs a fresh preflight guard job (RC-3)
04 l00's guard wrote side files into `/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-pf00`, so 04 l01 needs `-pf01`. Prepared on 05:
- guard job `end-staging/guard-jobs/guard-127x04-pf01` (manifest 6b34255d03ca37a7e2024e4c1d922370d06e6d03f31becb1b907875adc691eee, build+verify rc 0);
- request `end-staging/requests/request-127x04-pf01.json` 5244216f9311311bda01b20d549d711994725ebcdd303664abedb04dc4aa6747 (pf00 request with only guard.job changed);
- bundle `end-staging/bundles/end-ref-127x04-pf01` (b3-r7; tiers-pins 9955d59ec9f0e90242b7a00f2009528fe7fc80e18ad56c97ea0efad34239fdea, receipt 649dcea9827a453a4b467ec8d730a614085125069021583fd36e01c8ad4b4237);
- RC-6 declaration with 7 bundles `end-staging/pf4/ROOTS-DECLARATION.json` 6b6dbe1b5e23533f17f3054dc19828e865aa9a654114f8fee72ba2b07c0d9291 (replaces 872ced50 at run-r1/end-launch/ on main per B6);
- S10 dry run for 04 (bundle + guard job pf01): rc 0, 6 logins, ~23.5 GB (`end-staging/pf4/dry/`).
03's pf00 guard job is still fresh (03 l01 failed before its guard started).

## Proposed host sequence after Sol + GO
1. pf4-swap-preflight.sh 127x03, then 127x04 (1 login each).
2. Place RC-6 6b6dbe1b on main + local end-launch; S10 stage pf01 bundle + guard job on 04 (6 logins).
3. 04 l01: prepare receive, build-argv (bundle pf01, compare rd00-a00, hold 1200) with the new roots, S7 with PF-2 flags, verify-received, report.
4. 03 per PF-3: A5 at/after 02:53Z (one plain login + quiet reads, max 3 logins), then l03 rebuilt under the new roots (05), S7 with PF-2 flags, verify-received, report.
