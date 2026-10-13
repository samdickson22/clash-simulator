# INTEGRATION-AUDIT-r1 drivers re-run against s5s6s7-r5 outputs (offline, 127x05, scratch only)

- r5: every pin comes from `../ADOPTED-S9-RUNTIME.json` (adopted S9 = `s3s9s10-r5/s9_end_runtime.py` from S9-FINAL;
  production runtime `end-staging/runtime-98566c032d0b`, manifest from RUNTIME-r5-READY), re-hashed by `rerun.sh`
  before use, plus `tests/adopt_pins.py --check`.
- `frozen_job_drive.py`, `s9_equiv_drive.py`: the audit's drivers (`INTEGRATION-AUDIT-r1/runlog/drivers/`) with their
  scratch paths substituted; r5 also replaces `import s10_stage_host as S10` / `S9 = S10.S9` with
  `import s9_end_runtime as S9`, because only the S9-FINAL chain (s9_end_runtime.py, end_prep_common.py,
  safe_input.py, each checked against its S9-FINAL row) is copied to scratch. Everything else byte-identical.
- Inputs: `../builder-proof/END-JOB.json` (k4s_a6_builder.py build) committed ALONE on P' 98566c03 in a scratch
  copy of `repo-full/.git` ONLY (`/dev/shm/s567r5/audit/eqclone`; commit in `X`); the evidence and its 44 artifacts
  materialized from their committed blobs; the production runtime read only; interpreter
  `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` (as in the audit), `env -i`, empty HOME, nice 19, CPUs 16-23.
- Results: `frozen_job_drive.out` (frozen end_evidence OK, end_job OK at X, producer_registry OK, producer_claim OK
  into the SCRATCH work tree only), `s9_equiv_drive.out` (S9 r5 equivalence rc 0: diff = exactly END-JOB.json,
  4283 git members = the production manifest's set, runtime/measurement files identical).
- Run record: `../builder-proof/RERUN-1-build-selfcheck.log` (build + self-check OK; its audit part refused because
  the r4 rerun verified the sibling package's SHA256SUMS, which `s3s9s10-r5` had not regenerated yet) and
  `../builder-proof/RERUN-2-audit-only.log` (`rerun.sh --audit-only` with the S9-FINAL chain: OK).
- Scratch `/dev/shm/s567r5/audit` removed on every exit (trap).
