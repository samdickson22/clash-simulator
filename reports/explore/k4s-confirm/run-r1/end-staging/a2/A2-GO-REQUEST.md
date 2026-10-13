# K4S END A2 (staging on 03 then 04) — GO request

Prepared 2026-10-13T13:58:45Z by the K4S runner on 127x05. No host contact since A1/A1b (04:49Z). Code: s3s9s10-r6 (SHA256SUMS d6c4815b7a9b91bfaadd6312a0f2d7c585e0dbdca8a1e550e507a1a26bf87124) and s5s6s7-r6 (2b4b6f215514103e97542012d4f314438d7969cd1da33503ffd22f20cade2cb6), coordinator diff-check pending; b3-r7 bundles.

## What A2 does, per host (03 to completion first, then 04)

Script `end-staging/a2/a2.sh` (sha256 49c22eec9918699f47e5e873fbcc5c19894c3af25bf91eb101d64bca3d24e603, mode 0555; `a2.sh HOST GO_REF`). It first re-verifies both code dirs' SHA256SUMS and the runtime manifest SHA, then runs, stopping at the first nonzero rc:

| Step | Tool | Creates on the host (base 03 `/mpac/sdicks02/jobs/clasher/k4s-end-r1`, 04 `/mpac/sdicks02/jobs-k4s/k4s-end-r1`) | Logins | Bytes |
|---|---|---|---|---|
| s10-pf00 (run A) | S10 `--create-base` + runtime + `--tools-source s5s6s7-r6` + `--end-inputs` + bundle/guard pf00 | `<base>` with attempts/, preflight/, bundles/; `runtime-98566c032d0b/`; `tools/` (6 pinned files); `end-inputs-r1/` (native 44874fd6…, K4-states.pkl a97b1fbf…); `bundles/end-ref-<host>-pf00/`; guard job `<Q4 parent>/k4s-end-guard-r1-pf00` | 10 | ~26.5 GB |
| s10-rd00-a00 (run B) | S10 bundle/guard rd00-a00 | `bundles/end-ref-<host>-rd00-a00/`; `<Q4 parent>/k4s-end-guard-r1-rd00-a00` | 6 | ~23.5 GB |
| s10-rd00-a01 (run C) | S10 bundle/guard rd00-a01 (second attempt's inputs, staged now to avoid another A2) | `bundles/end-ref-<host>-rd00-a01/`; `<Q4 parent>/k4s-end-guard-r1-rd00-a01` | 6 | ~23.5 GB |
| s11-provision | S11 | `<base>/repository`: full clone, branch k4s-end-r1 at P' 98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb, writable work tree, plus `<base>/repository-transfer-98566c032d0b` | 1 | ~0.14 GB |

Per host: 23 logins, ~74 GB, all ssh from 05 with ControlMaster=no/ControlPath=none/BatchMode/StrictHostKeyChecking=yes; remote commands at nice 19. Everything written is a-w after publication; nothing outside `<base>` and the two Q4 guard parents (`/mpac/sdicks02/jobs/clasher` on 03, `/mpac/sdicks02/jobs-k4s` on 04, names `k4s-end-guard-r1-*` only). On 04 nothing under `/mpac/sdicks02/jobs/` is named.

S10's P-facts login also runs the read-only **interpreter probe** of `/mpac/sdicks02/repos/clasher/.venv/bin/python -B` (U4 ruling): path/realpath, prefix/base_prefix, site-packages, numpy/torch/cv2/scipy import from the venv (no model load). A mismatch refuses before anything is staged on that host; that is a STOP for coordinator review, not a retry.

## Inputs (verified on 05)

- Runtime `end-staging/runtime-98566c032d0b`, manifest 9d6ab1f7386894727035c14a95c518b54e9472c9cb90eb6d023c589fe2269b43 (S9 r6; verify --frozen OK).
- Bundles (b3-r7 S4 2b8f5fb3…) and guard jobs (s3s9s10-r4 S3; 03 bus-only per IR-03): SHAs inside a2.sh; RC-6 declaration 872ced5028db256e3b587f7fd5f2a9a4f6a5247f0b1a0548adb3e7accb628a40 lists the same six bundles.
- Dry runs with exactly this code: S10 6/6 and S11 2/2 rc 0 (`end-staging/r6-rebuild/dry/`).

## Preconditions

1. Coordinator GO for A2, at or after 14:30Z, after confirming the FSC STOP on 03/04 and the >= 1 h gap.
2. Coordinator diff-check of r6 (s3s9s10-r6, s5s6s7-r6) accepted.
3. RC-6 declaration committed to **main** at `reports/explore/k4s-confirm/run-r1/end-launch/ROOTS-DECLARATION.json` (872ced5028db256e3b587f7fd5f2a9a4f6a5247f0b1a0548adb3e7accb628a40) before A2 (B6); `k4s-end-r1` stays at P'.
4. No END window, preflight or other K4S/T1 copier on 03/04; no perception read window; 03: nothing restarted since IR-03.
5. Runner rechecks immediately before each host: SHA256SUMS, runtime manifest, record dirs absent, `date -u`.

## After A2 (05 only)

Commit the S10/S11 records (staging manifests, probe facts) to main; report per host: logins used, staged SHAs, probe result. The next host step (A4 preflights 03 then 04 via S7/S5) gets its own GO request.
