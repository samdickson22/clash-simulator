## 2026-10-12 11:49Z: TIERS Mac-session output layout and release-driver r3 scope (rulings)

**R-M1: fixed output directory.** `D = reports/explore/mac-e4-session/tiers-session-r1`. The frozen procedure left this undefined; the coordinator now assigns it, which settles `TIERS_RECEIPT_REL`.

**Public commit (exact paths):**
- `D/sealed/{tiers-summary.json, tiers-complete.json, receipt-manifest.json, receipt-manifest.sha256, tiers-identity.json, build-tiers.json, pre-session-census.json, runtime-versions.json, exactness-tiers.json, belief-exactness.json, student-agreement.json}`.
- `D/a3p-poll-check.json`, `D/stage-nocopy-session-verify.json`, `D/preconditions.json`, `D/session-receipt.json`.
- Only on failure: `D/sealed/failure.json`, `D/sealed/cleanup-failure.json` and `D/classification/*`.
- `release.mac_summary_path` points to `D/sealed/tiers-summary.json`.
- None of these files contain game outcomes.

**R-M2: the full sealed inventory stays private.** It includes `capacity.jsonl` and the other large row files.
- It is committed as a **local, never-pushed** commit at `D/sealed/` in the Mac's `$S/k4s-commit-repo`.
- A verified `git bundle` is copied to 05 at `/mpac/sdicks02/jobs/clasher/mac-e4-private/`.
- A public `D/private-commit-binding.json` records the commit SHA, tree SHA, every path with its SHA and size, and the bundle SHA. This mirrors 2969615c.

**R-M3: close the A3-P gap.** Frozen `reduce.select()` reads only `tiers-summary` feasibility; it does not read the adopted A3-P lateness gate. Release driver r3 must also do the following:
- Read `D/a3p-poll-check.json`, binding it by commit and SHA, and verify that its `receipt_manifest_sha256` equals the sealed seal.
- **Fail closed before any game read** if any tier has `frozen_feasible=true` and `feasible_after_a3p=false`. That case goes back to the coordinator, who rules on it with a reviewed A3-P-adjusted selection or a reducer amendment.
- If A3-P passes wherever the frozen summary says feasible, the release proceeds unchanged.

The driver r3 allowlist is exactly the public paths in R-M1, plus `D/private-commit-binding.json`.

**Mac staging is done:** tiers-pins 273ef196, `validate_bundle` PASS, fixture clones 0444, 22.4 GB free. Chrome and Claude were quit gracefully. ChatGPT was left running because it hosts Codex agents.
