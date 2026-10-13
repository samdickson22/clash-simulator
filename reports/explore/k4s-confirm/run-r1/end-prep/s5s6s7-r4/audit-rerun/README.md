# INTEGRATION-AUDIT-r1 drivers re-run against s5s6s7-r4 outputs (offline, 127x05, scratch only)

- `frozen_job_drive.py`, `s9_equiv_drive.py`: the audit's drivers (`INTEGRATION-AUDIT-r1/runlog/drivers/`) with ONLY
  their scratch paths substituted (see `diff` in PROGRESS-r4.md); everything else byte-identical.
- Inputs: `../builder-proof/END-JOB.json` (k4s_a6_builder.py build) committed ALONE on P' 98566c03 in a scratch
  copy of `repo-full/.git` (`/dev/shm/s567r4/audit/eqclone`; commit in `X`); the evidence and its 44 artifacts
  materialized from their committed blobs; S9 from a scratch `cp -a` of `s3s9s10-r3` (its SHA256SUMS verified);
  the S9 runtime `end-staging/runtime-98566c032d0b` read only; interpreter `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python`
  (as in the audit), `env -i`, empty HOME, nice 19, CPUs 16-23.
- Results: `frozen_job_drive.out` (frozen end_evidence OK, end_job OK at X, producer_registry OK, producer_claim OK
  into the SCRATCH work tree only), `s9_equiv_drive.out` (S9 equivalence rc 0: diff = exactly END-JOB.json,
  4280 git members, runtime/measurement files identical).
- Not re-run: the S4/S5/S7/S10 fake-host drivers (their fake host trees and the IA-P1 bundle were removed by the audit,
  and no production bundle exists yet, B1). The S7 gate is exercised end to end over a fake ssh by
  `tests/test_r4.py` (build-argv -> launch, composed host program).
- Scratch `/dev/shm/s567r4/audit` removed afterwards.
