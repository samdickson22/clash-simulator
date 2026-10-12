# K4S run r1: authorization citation erratum (timestamps only)

- **Recorded:** 2026-10-12T04:59:33Z (`date -u`), at the coordinator's request. Only timestamps change; no ruling content changes.
- **Windowed-rounds ruling:** COORDINATOR.md **76887b33**, recorded at **2026-10-11T22:10:17Z**. It was earlier labelled ~22:13Z. Its windowed-dispatch part was superseded by Option A, but its item 5 still applies: authorization uses the same bindings as 20:04:59Z, plus `reporting_jobs` and a citation of this ruling.
- **Option A:** COORDINATOR.md **afe83faa**. The entry heading is 22:11 UTC and the commit time is 2026-10-11T22:11:53Z. `REPORTING-AUTHORIZATION-v3-replacement-r1.json` and `replacement-r1-launch-receipt.json` label it "~22:12Z".
- **The committed replacement-r1 authorization is NOT edited.** It was staged on both hosts and passed the frozen barrier, so its bytes are evidence. It cites only Option A (labelled "~22:12Z") and does not cite 76887b33. This erratum supersedes those labels for the record.
- **From replacement-r2 onward,** `reporting_jobs_note.ruling` cites:
  - the windowed-rounds ruling 76887b33 at 22:10:17Z (its windowed-dispatch part superseded);
  - Option A afe83faa at 22:11 UTC (commit 22:11:53Z);
  - P2 adc12f36;
  - Proposal M 2c847954.
