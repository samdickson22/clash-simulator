# K4S run r1: completion-v2 is the record of truth (RC-1 disclosure)

- **Recorded:** 2026-10-12T15:23:40Z (`date -u`). Coordinator ruling after 4af19c23 adopts the END plan review r1 (`audits/K4S-END-PLAN-REVIEW-r1.md`, sha256 `b69f015d…`, retained verbatim), RC-1.
- **The record:** `completion-v2/REPORTING-COMPLETION.json` (`3794d953…`), with counted inventory `completion-v2/counted-inventory.json` (`22c41cb7…`), commit 23604d1c, is **the completion of record** for every downstream binding:
  - the END evidence `completion` and `counted_inventory`;
  - END-JOB `completion_sha256`;
  - the PC4 sidecar;
  - the verifier receipt;
  - release item 1.
- **v1:** `completion/` (`ed7d11b7…` / `f10ab943…`) stays committed, unedited and **superseded**.
- **Release check:** `barrier.outcome_release` does not cross-check release item 1 against the END-JOB completion, so that check is to be made at release.

The reviewer's three disclosure notes:

1. **How v2 was produced.** v2 was produced by **re-serialising v1's rows under the frozen envelope** (`json.dumps({schema, outcomes_sealed, blocks}, indent=1) + "\n"`). The reviewer reproduced `22c41cb7` exactly.
   - v2's `script_sha256` (`94f3e405…`) names the producer of the rows, which is v1's `final_pass.py`. It does not name the producer of the envelope.
   - The edited `final_pass.py` (`47f93505…`, 23604d1c) was **not** re-run.
2. **Ledger path.** `completion-v2/VALIDATION.txt` names `ledger/blind-ledger.json`, the runner's local name. The committed file is `reports/explore/k4s-confirm/run-r1/ledger/blind-ledger-final.json`, with the same sha256 `649272bd…`.
3. **DBus disclosure.** The canonical rows SHA `2e18ce34e955ad19608d6a704408d8d9b60019bb5486e9fbcce2f6efb55d3a29` is equal in v1 and v2. So the R2 DBus disclosure (`completion/DBUS-FLAG-DISCLOSURE.md`, `128d66a0…`) and `dbus-recount.json`, which cite the v1 inventory `f10ab943`, stand unchanged.

No amendment is needed: no arm, cell, seed, N, hypothesis, gate or analysis changes.
