# K4S END — fix-check package r5 (diff-only) for Sol's integration r1 findings

Prepared 2026-10-13T12:26:29Z by the K4S runner. Offline only; no host step since A1/A1b. Candidates committed on main at f9458d7d76b34b5c86885b9ab5922322b1649c03. Review: `reviews/SOL-REVIEW-END-INTEGRATION-r1.md` (63fae416). Rulings: COORDINATOR 05c733d1 (B6 and D1 endorsed; U11/S8 deferred post-END, not closed).

## Diffs to review

| File | sha256 | What |
|---|---|---|
| `end-prep/FIXCHECK-r5/PRODUCTION-CODE-r5.diff` | 0dba0e3eff81cf75a2dc3d1919a60c1c371264dc579f9f3d8073b610244bbb3a | Production code only, r4 -> r5 (S9, S10, S11, S1b/S3 pin-chain lines, S7 gate, A6 builder) |
| `end-prep/s3s9s10-r5/DIFF-r5.patch` | a7de77ebe6f9cfbb552a5c6b8d08403b04579f794589be6e66241ba55f1bf89c | Full Part A diff incl. tests (the test vendor dir rename r4->r5 shows as delete+add) |
| `end-prep/s5s6s7-r5/DIFF-r5.patch` | cf5ad96fc569bff77632e25b3695c82b7a3b98934c2bd8e812572d7320c3a226 | Full Part B diff incl. tests |

Candidate dirs: `s3s9s10-r5/` SHA256SUMS 56506e878d4de3413ed9316f82adb920cbb92f95208dfd123f1794b864769468 (excludes its PROGRESS-r5.md); `s5s6s7-r5/` SHA256SUMS c4899e6a3c838679494f87733ac52c995d3c2c562aaccab80c19616d38bf1e4a. RESPONSE-r5.md in each maps finding -> fix file:line -> named tests.

## Finding 1 (U8 builder pins) — fixed in s5s6s7-r5

- **Deviation from the literal pins (disclosed):** finding 2's fix lives in S9 `refresh-clone`, so S9's bytes change and the adopted S9 is r5, not r4 80c15b5f. The runner rebuilt the production runtime at P' with S9 r5 (`end-staging/RUNTIME-r5-READY` 74b5682b71ff9339023b90ff61470f6b1deb5d2568888a8a27baa4bdcdccd79c): manifest d1767f78fdb3652d9f9fb27f63c51bf736828e38a243b4b97fa65f6429eddb02, which differs from r4's 1fa0ebf5 only in `started_utc`, `finished_utc` and `script_sha256`; runtime_files fc3dbeb4, measurement 42b8986d and inventory 74fc01a7 unchanged; verify --frozen OK. The r4-built runtime is kept at `end-staging/SUPERSEDED-r4-runtime-98566c032d0b`.
- Builder pins: S9 `s3s9s10-r5/s9_end_runtime.py` 4778f6f61cb5cb69a7cf476ce5ce00c53e3b3157ca052492a3bc3e3cb3745b60 and the manifest above, from the S9-FINAL / RUNTIME-r5-READY markers (`ADOPTED-S9-RUNTIME.json`). New check: the manifest must name that S9 as its builder, P' as its commit, repo-full as its repository and the frozen interpreter.
- Proof (`s5s6s7-r5/builder-proof/`, scratch copy of repo-full/.git only): END-JOB built from committed bytes at P', committed alone as scratch X; frozen end_evidence + end_job accept; **S9 r5 equivalence** on the production runtime passes (4283 members = manifest).
- Contract tests tie the builder constants to s3s9s10-r5's SHA256SUMS/S9-FINAL and to the production manifest/marker.

## Finding 2 (U1/U10 git metadata aliases) — fixed in s3s9s10-r5

- One guard source (`GIT_WRITE_GUARD` in S9, composed verbatim into the S11 host program) runs **before** every writing git command (S9 refresh fetch and checkout; S11 provision and advance fetch and checkout): the whole audited write set and every ancestor (real directories; existing leaves regular and single-link; lock siblings absent; everything under .git/objects regular single-link or real dir). Metadata only, no content reads. A post-check detects but is not relied on.
- Write reduction on every writing command: core.logAllRefUpdates=false, gc.auto=0, maintenance.auto=false, fetch.writeCommitGraph=false, no submodules/prune, hooks to /dev/null, `--no-auto-gc`. git 2.25 has no `--no-write-fetch-head`, so FETCH_HEAD is confined, not disabled; existing reflogs remain in the checked set because git still appends to them.
- Write set audited empirically (git 2.25.1, inotify + before/after snapshots of the exact six commands; a test requires every touched path to be in the plan); table in s3s9s10-r5 README §r5.1. S11 advance additionally refuses unless the checkout writes exactly END-JOB.json.
- Tests: Sol's 6 cases + 48 further alias cases end to end (S9 and fake-host S11): each refused before the fetch, foreign marker byte-identical, no success record; 3 checkout-time work-tree cases; all 186 write-set rows on both copies of the guard. Residual: a concurrent writer racing between check and git is not prevented (post-check detects).

## U4 (host interpreter) — both tools

`HOST_PYTHON` = `/mpac/sdicks02/repos/clasher/.venv/bin/python` with `-B` (what runtime.sh at P' execs; test-checked against its blob) in S10's probe and S7's gate/argv builder (same string, test-checked). The probe records path, realpath, sys.executable, prefix/base_prefix, site-packages realpaths and sys.path membership, pyvenv.cfg hash/keys, and numpy/torch/cv2/scipy origin+version; it refuses unless they match the pins and each module imports from the venv's own site-packages. Base-prefix/resolved-binary pins come from committed admission evidence; the authorized A2 probe confirms them on each host (refusal before staging otherwise).

## Verification (runner, pristine /dev/shm copies with sibling dirs; umask 022)

| Suite | 3.12 | 3.12 -O | 3.8 | 3.8 -O |
|---|---|---|---|---|
| s3s9s10-r5 | 1252 | 1252 | 1252 | 1252 |
| s5s6s7-r5 (s3s9s10-r5 beside it) | 744 | 689 + 55 verifier skips | 744 | 689 + 55 |

Worker mutation: s3s9s10-r5 56/56 new (py3.8; py3.12 after isolating tests); s5s6s7-r5 15/15 both interpreters.

## Production state after r5 (05 only)

- Runtime manifest d1767f78fdb3652d9f9fb27f63c51bf736828e38a243b4b97fa65f6429eddb02 (S9 r5).
- Six bundles (b3-r7) and six guard jobs (03 bus-only) unchanged from the integration package (S10 re-verifies them).
- RC-6 `--declare-roots` with r5: byte-identical to before, 872ced5028db256e3b587f7fd5f2a9a4f6a5247f0b1a0548adb3e7accb628a40 (to be placed on main at run-r1/end-launch/ after approval, per B6).
- S10 dry-runs 6/6 and S11 provision dry-runs 2/2 rc 0 with r5 code (`end-staging/r5-rebuild/dry/`).
