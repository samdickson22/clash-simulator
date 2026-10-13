# K4S END A1 (and A1b): exact commands and preconditions — GO request

Prepared 2026-10-13T03:38:35Z by the K4S runner on 127x05. Nothing here has touched 03/04. Tooling frozen at Sol full r2 APPROVE (a770a69e; COORDINATOR 57598857).

## What A1 does

- **A1 = S1 (B2 copy)**: from 05, read-only, exact paths only: for each of the 10 counted (host, phase) dirs, `launch.json` + `supervisor-exit.json` (inspected and hashed against committed phase-meta, never copied) and `mhz.jsonl` + `census.jsonl` (copied). 3 logins per host, 6 total (P03, P04, C03, V03, C04, V04), each `ControlMaster=no ControlPath=none BatchMode=yes StrictHostKeyChecking=yes`; remote program under `nice -n 19 /usr/bin/python3 -I -S`. On 04 only `/mpac/sdicks02/jobs-k4s/k4s-confirm-*` is named (never `/mpac/sdicks02/jobs/`). No game file, `games/`, `hub-blocks/` or complete/interference/outcome file is named.
- **A1b = S1b (E3 admissions)**, requested in the same GO window: one login per host (2 total) with the pinned reader program (2d2f212d…); reads exactly 03 `k4s-confirm-replacement-r4/{system-bus-admission.json,idle-services.json}` and 04 `k4s-confirm-replacement-r4/system-bus-admission.json`, plus an absence probe of `k4s-confirm-replacement-r5` on each root. Expected identities: 03 bus PID 2049/start 1273, 04 bus PID 2005/start 1032, 03 idle PID 2180947/start 139691386.

Total host contact: 8 short SSH logins, all read-only, sequential, from 05; no host file is created or modified.

## Code and inputs (verified on 05 at 2026-10-13T03:38:35Z)

| Item | Value |
|---|---|
| S1 | `end-prep/s1s2-r5/s1_copy_end_sources.py` sha256 `b987ab9756dd05439f79bd924a0ce31df3c31b24b125a25d8d9cbba31d0fdc65` (= approved b987ab97, unchanged since r2) |
| S1b | `end-prep/s3s9s10-r3/s1b_copy_admissions.py` sha256 `7515d5fe60f2883a84bb8f1cf23bc5596d3c6108cb82f635baf2aa4f104ac3f3` (s3s9s10-r3 SHA256SUMS e50fb462…, verified) |
| Repository | `end-prep/repo-full` (dedicated no-filter clone); live full-clone check passed in S9 locate at 03:37Z (`a1-prep/s9-locate-r1/s9-locate.json`, 33/33 Q5 runtime files found on 05) |
| Commit | `72426428cd48db0342b2cb6358211424ebc686d0` (holds phase-meta, rounds/history.json, completion-v2) |
| Python | `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12, `-I -B`, env scrubbed (`env -i`) |
| Dry runs | `a1-prep/s1-dry-run-r2.txt` sha256 `2bae86155891d8bf898836802ec90963cded12e29f752159a2ac82de1be8c072` (6 planned logins, expected SHAs/sizes); `a1-prep/s1b-dry-run.txt` sha256 `0e7bb6410a64dde2469c7f77c27cf2c1b5b551f61d644a1486f3c70fecf009e4` (2 logins). Both rc 0, no ssh, nothing written. |
| Destinations | S1 `end-prep/b2-copy-r1/end-sources` (parent created, empty; dest absent). S1b `end-prep/admissions-copy-r1` (absent) |
| 05 disk | /mpac 1.5 T free (worst case 10 × 95 MiB) |
| known_hosts | 127x03 and 127x04 present on 05 |

## Preconditions (all must hold at GO)

1. FSC STOP on 03 and 04 verified by the coordinator (STOP_AT 07:30Z, COORDINATOR 5f1a28be), and ≥ 1 h elapsed since verification.
2. No END timing window and no S5 preflight open on either host (none exists yet).
3. No other thread's SSH copier or measurement on 03/04 during A1/A1b; no perception read window in progress on 03/04 (A1 reads only K4S trees).
4. The runner rechecks immediately before running: SHA256SUMS of s1s2-r5 and s3s9s10-r3; S1/S1b sha256 as above; dest absent; `date -u` for the receipt.

## Exact commands (run on 127x05 by the runner, sequentially; GO_REF = the coordinator GO commit/heading)

```
E=/mpac/sdicks02/k4s-runner/run-r1/end-prep
PY=/mpac/sdicks02/venvs/k4s-freeze/bin/python
C=72426428cd48db0342b2cb6358211424ebc686d0
cd /tmp && umask 022
# A1 (S1): 6 logins
env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 $PY -I -B $E/s1s2-r5/s1_copy_end_sources.py \
    --repository $E/repo-full --commit $C --dest $E/b2-copy-r1/end-sources \
    --outside-end-window "A1 GO $GO_REF, $(date -u +%FT%TZ)"
# A1b (S1b): 2 logins; only if A1 exited 0
env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 $PY -I -B $E/s3s9s10-r3/s1b_copy_admissions.py \
    --repository $E/repo-full --commit $C --dest $E/admissions-copy-r1 \
    --outside-end-window "A1b GO $GO_REF, $(date -u +%FT%TZ)"
```

Both are short one-shot foreground processes (no STOP file; to abort, the runner kills the exact PID). Any refusal stops the sequence and writes a receipt (S1: `end-prep/s1-refusals/`; S1b: `admissions-copy-r1/S1B-REFUSAL-*.json`); no retry without a new GO.

## After (05 only, no host contact)

1. Re-hash every copied file against `s1-copy-manifest.json` / `s1b-admissions-manifest.json`; record the manifest SHAs.
2. Commit, by explicit path via temp index with `clasher-secret-scan` (`/mpac/sdicks02/k4s-runner/commit_paths_end.sh`, which admits only `reports/explore/k4s-confirm/end-sources/127x0[34]/*/*.jsonl`, `end-sources/s1-copy-manifest.json`, `end-guard-admissions/127x0[34]-*.json`, `end-guard-admissions/s1b-admissions-manifest.json` and run-r1 paths): end-sources commit **X**, then the E3 admissions commit. Any file > 95 MiB was already refused by S1.
3. Report to the coordinator: logins used (expect 6 + 2), manifest SHAs, commit SHAs.
4. Then 05-only: S2 build/validate evidence at P; S9 prepare-clone at P (the current `repo-full` is moved aside to `repo-full-pre-P` first, since prepare-clone requires absence); S9 build; S4 bundles; S3 guard jobs; RC-6 declaration. The next host step (A2 staging) gets its own GO request.

## Disclosure

The first S1 dry run at 03:36:47Z was piped through `head`, and the closed pipe made S1 write a refusal receipt (`end-prep/s1-refusals/S1-REFUSAL-20261013T033647Z-3173965-dfa733a2.json`, BrokenPipeError, no ssh, dest not created). It is kept as written. Later dry runs wrote to files.
