# C1 final-tools r3 implementation response

Original assignment and F1–F7 response remain in FINAL-TOOLS-r2-response.md; original rejection is CARD LEAD
`reports/cards/reviews/C1-final-tools-r1.md`. Fresh r2 independently **REJECTED c45854febf93352284dd9f76b02651d989d906a7**
for two additional startup defects, verifying the original six repair classes apart from these findings.
Full verdict,12+7 groups and exact hash/command receipts are preserved in FINAL-TOOLS-r2.md/r2-independent/.
Do not rerun old r2 defect-expecting checks against revised source and present that as an r2 receipt.

- R2-1 P1 CPU accounting: sanitized invocation now explicitly supplies USER derived by `/usr/bin/id -un`
  before the unchanged CPU wrapper. It retains env-i/bash-p; no arbitrary caller USER/environment restoration.
  Static regression checks require identity-derived USER in the documented invocation. Wrapper source was
  read, never executed; future actual admission remains gated.
- R2-2 P2 full archive: archive_files omits `-- <prefix>` for a full tree and retains it/stripping for nonempty
  engine/tools prefixes. Mock checks assert exact argv for both forms, then check corrupt commit/blob negative
  controls. Real local read-only `git --no-replace-objects ls-tree -r -z HEAD` exit0, count/hash/commit in r3 receipt;
  old empty-argument command's128 diagnostic is preserved with r2 evidence.
- Parent's additional reproducibility finding: -I implies-E, silently ignoring PYTHONHASHSEED=0 for workers.
  Local Python flag-only checks showed hash_randomization1 under-I versus0 under-P -s -S -B. Workers now use
  those latter flags under the explicit minimal environment and enforce seed0, safe_path/no_site/no_user_site
  plus standalone frozen base_prefix/version in bootstrap. Effective worker flags/seed are recorded. Control
  interpreter stays-I: it does no engine work. New local13th group probes actual stdlib interpreter flags
  only, never worker/engine/native/host main; positive result `0 True 1 1`. No gate launched.

Updated full suite:13 local groups PASS; AST all7 Python tools and bash syntax pass. No engine/native,
approved comparator or followup code change. r3 code/commands/logs in repair-local-receipt-r3.json and
repair-local-tests-r3.log. All prior failed artifacts/verdicts remain; no runtime/active-pin mutation.

Fresh independent scope is the COMPLETE six-finding repair plus all r2 objections/responses and the hash-seed
fix, bound to the revised commit (not a follow-up verdict on stale c45854f). No unresolved code objection
is deliberately deferred. External readiness prerequisites remain B2 acceptance/integration, exact-source
build/affected checks, owner-authenticated complete dependency/input inventory, duplicate-job audit and fresh
C56. Human approval authenticity remains owner authority; no byte-equivalence/engine acceptance claim.
Only local serial pure/source/mock/flag tests are permitted for this review: no launcher/host script main,
engine/native import, simulation/build/remote/emulator/deploy/pin execution. Preserve strict silence and
one automatic whole-review completion. Roll back scoped repair commits without running rejected old tools.
