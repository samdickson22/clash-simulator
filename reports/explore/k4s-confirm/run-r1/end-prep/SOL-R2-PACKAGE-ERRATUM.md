# Erratum and test-environment note for SOL-R2-PACKAGE-END-FULL.md

Written 2026-10-13T03:36:24Z by the K4S runner after Sol's r2 APPROVE (`reviews/SOL-REVIEW-END-FULL-r2.md` a770a69e; COORDINATOR 57598857). Documentation only; no code byte changes. The package index (e00debc9) stays as committed; this note supersedes the two statements below.

## 1. HOME exception wording (r2 non-blocking note)

The index says the sole HOME exception is `//home/sdicks02`. That is inaccurate. The delivered code (`s5s6s7-r3/k4s_end_host_tool.py`, HT:361) accepts **any** HOME that begins with exactly two slashes (not three), drops one leading slash, and then applies the normal gates to the result: normalized absolute path (`si.check_abs`), name/no-follow/single-link checks on every config file derived from it, include/driver refusals. The single-slash value is what is installed in the executed environment. The delivered test also accepts `//tmp/<clean-home>`. XDG_CONFIG_HOME keeps strict refusal: no double-slash normalization applies to it. The runner chose to correct the wording rather than narrow the code.

## 2. Test-run umasks (r2 non-blocking note)

The suites assume:
- process umask **0022** for every test run (`umask 022` before pytest). Under umask 0077, three S10 tests fail on directory modes (0700 guard dirs, 0500 staged read-only dirs instead of 0755/0555). Production behaviour is unchanged.
- when exporting the package from git, `git -c tar.umask=0022 archive …`. Git's default tar export gives the shims mode 0775, which fails the exact-0755 F6 assertions.
