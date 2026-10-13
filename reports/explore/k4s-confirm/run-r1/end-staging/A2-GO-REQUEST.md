# A2 GO REQUEST — K4S END staging on 127x03 then 127x04 (S10) — DRAFT, NOT READY

Drafted 2026-10-13T05:06:55Z on 127x05 by the s4s3 worker. Not committed. Every SHA below was computed by the command that wrote this file.

## Status: NOT READY — blockers (coordinator)
- **B1 (S4 refused; no bundles):** b3-r5 refuses every production assembly: `ASSEMBLY REFUSED: S1 runtime pin lacks a files list` (S4 needs a list; the pinned runtime-pin-r2 f81f3655 holds a dict; the frozen rule and S9 use the dict). See `/mpac/sdicks02/k4s-runner/run-r1/end-staging/S4-REFUSAL-b3r5-runtime-pin-files-shape.md` (fd47e7d91fa477c1cd4032a632b7c6a573616a45180a5a576def38b7256e2f05). Needs S4 fix + review + adoption, then the four bundles (requests already written; see PROGRESS-s4s3.md). Until then every `<TIERS_PINS_SHA256 …>`/`<ASSEMBLY_RECEIPT_SHA256 …>` below is a placeholder.
- **B2 (runtime path conflict):** S10 stages to `<base>/runtime/runtime-98566c032d0b`; S5 `layout()` (s5s6s7-r3/k4s_end_preflight.py:403-405) and S7's RC-6 check (k4s_end_launch_gate.py:319-320) require `<base>/runtime-98566c032d0b`. As drafted, A2 would put the runtime where A4 refuses it. One tool must change (ruling + review) BEFORE A2; never move it by hand on the host.
- **B3 (runtime lacks two S5 inputs):** S5 reads from the runtime root `reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json` (pin 3501e2acf444c2f23a5ed9f9471ebcabfc66216b412847c033759c3f4b2cde13) and closure member `reports/explore/k4s-confirm/SD1-MANIFEST.json` (pin b8ce7b4c088e275894b9654a85923aacf428656e71433f60ec32bed1ae63ef76, = git show P'). Both are tracked at P' with exactly those SHAs but are NOT S9 runtime members (S9 D1 rule: runtime-pin-r2 ∪ *.py ∪ six support members), so the staged runtime would fail S5 `pre_import_pins`. Needs an S9 membership change (re-review) or a ruling.
- **B4 (no reviewed tool):** host steps A2/A4 need that S10 does not do — see "Open items".

## Preconditions (each verified and recorded before the GO is used)
1. FSC STOP verified on 03 and 04, and ≥ 1 h elapsed since it (coordinator record cited in the GO ref).
2. No END window open (no END-JOB launch in progress / scheduled during staging); `--outside-end-window` carries the A2 GO ref.
3. B1–B3 resolved; bundles built by the fixed S4 and S10 `--dry-run` re-run on 05 with the real bundle SHAs (rc 0) and its output attached.
4. S10 itself, before writing anything on a host: P-check (base absent for Run A, or base + 4 subdirs present for Run B/C; Q4 parent canonical; every target and `.partial` absent) and P-facts (`hostname` == host, `df -P -B1 /mpac/sdicks02` ≥ bytes + 50 GiB, `who` recorded — S10 records but does not refuse on console users: the operator checks `who_lines` and keeps the run `nice`, per fleet rules).
5. Order: 03 Run A → 03 Run B → 04 Run A → 04 Run B. Stop at the first refusal (S10 writes `S10-REFUSAL-*.json` listing host paths needing authorized cleanup; nothing is ever deleted on a host by S10).

## Inputs (05, verified this session)
- Runtime: `/mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-98566c032d0b`, runtime-manifest.json 4dd88461caa82f09bb27bc6adad1756f62dbc8d21aa041441f8c106ef9b80e04 (S9 VERIFY OK inside every S10 dry-run).
- Guard jobs (S3 build + verify OK, commit P' 98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb): 03 pf00 ced24d01718b18941da39b6d2afc4dc230a744c45a07806581ebe0325af2045d, 03 rd00-a00 22b14d7ba344c71be2d5ea1d66c68e5ab4c60ab3585efb7a4ef6ae918212d25b, 03 rd00-a01 d39493f8a9cd76564e7768f61cef9fd1e33f0b4c94776847f93609adb1b2e03b, 04 pf00 b8a6cd28ab60b63f0781f48cdafd033eca5101227f6ae165bfddd098da29f7a5, 04 rd00-a00 da7fe5220a7d4b03ec00fcfca8c68bd63cd6b30d516b3cc53df8e6068031c3c8, 04 rd00-a01 2b7af425ee867355bca68189077b9256ff659fcd76dc666f11e11b837275b313.
- RC-6 candidate: `/mpac/sdicks02/k4s-runner/run-r1/end-staging/RC6-ROOTS-k4s-end-r1.json` (b3cdd3148b4c1fa7abe6058c9c8c531f87ff6d91802adf21b8e15704df713435).
- No-login S10 dry-runs (runtime + pf00 guard with --create-base; a00 guard alone), both hosts rc 0: `/mpac/sdicks02/k4s-runner/run-r1/end-staging/s10-dry-run/`.

## Commands (S10 = s3s9s10-r3/s10_stage_host.py af34f20c85c68571362bdc0ea7607ca20c20f762bfd200eddb120dc9f6f2f6e9)

### 127x03 (base `/mpac/sdicks02/jobs/clasher/k4s-end-r1`, Q4 guard parent `/mpac/sdicks02/jobs/clasher`)

**Run 127x03-A** (first staging: base + runtime + preflight bundle + its guard job; byte cross-check bundle↔guard job):
```bash
cd /tmp && umask 022 && env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 /mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -I -B \
  /mpac/sdicks02/k4s-runner/run-r1/end-prep/s3s9s10-r3/s10_stage_host.py --host 127x03 --create-base \
  --runtime /mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-98566c032d0b --runtime-manifest-sha256 4dd88461caa82f09bb27bc6adad1756f62dbc8d21aa041441f8c106ef9b80e04 \
  --bundle /mpac/sdicks02/k4s-runner/run-r1/end-staging/bundles/end-ref-127x03-pf00 <TIERS_PINS_SHA256 end-ref-127x03-pf00> <ASSEMBLY_RECEIPT_SHA256 end-ref-127x03-pf00> \
  --guard-job /mpac/sdicks02/k4s-runner/run-r1/end-staging/guard-jobs/guard-127x03-pf00 --guard-job-name k4s-end-guard-r1-pf00 --guard-manifest-sha256 ced24d01718b18941da39b6d2afc4dc230a744c45a07806581ebe0325af2045d \
  --record /mpac/sdicks02/k4s-runner/run-r1/end-staging/s10-127x03-r1 --outside-end-window "A2 GO <ref>, $(date -u +%FT%TZ)"
```
- Components: runtime (84635830 B), bundle end-ref-127x03-pf00 (~23373961902 B + small), guard job k4s-end-guard-r1-pf00 (63790441 B) → need ≥ bytes + 50 GiB free on /mpac (S10 P-facts refuses otherwise).
- **Logins: 8** = P-check, P-facts, base, R-runtime, R-bundle, R-guard, F, POST.
- Creates on 127x03 (each via `<final>.partial` then `mv -n -T`; runtime/bundles `chmod -R a-w`; guard dir writable):
  - `/mpac/sdicks02/jobs/clasher/k4s-end-r1/` with `attempts/`, `preflight/`, `runtime/`, `bundles/` (exclusive receive; base must be ABSENT before)
  - `/mpac/sdicks02/jobs/clasher/k4s-end-r1/runtime/runtime-98566c032d0b/` (S10 path — see BLOCKER B2)
  - `/mpac/sdicks02/jobs/clasher/k4s-end-r1/bundles/end-ref-127x03-pf00/`
  - `/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-pf00/`

**Run 127x03-B** (round-00 attempt-00 bundle + its guard job; bundles checked against the staged runtime manifest, runtime not re-shipped):
```bash
cd /tmp && umask 022 && env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 /mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -I -B \
  /mpac/sdicks02/k4s-runner/run-r1/end-prep/s3s9s10-r3/s10_stage_host.py --host 127x03 \
  --runtime-manifest-for-checks /mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-98566c032d0b --runtime-manifest-sha256 4dd88461caa82f09bb27bc6adad1756f62dbc8d21aa041441f8c106ef9b80e04 \
  --bundle /mpac/sdicks02/k4s-runner/run-r1/end-staging/bundles/end-ref-127x03-rd00-a00 <TIERS_PINS_SHA256 end-ref-127x03-rd00-a00> <ASSEMBLY_RECEIPT_SHA256 end-ref-127x03-rd00-a00> \
  --guard-job /mpac/sdicks02/k4s-runner/run-r1/end-staging/guard-jobs/guard-127x03-rd00-a00 --guard-job-name k4s-end-guard-r1-rd00-a00 --guard-manifest-sha256 22b14d7ba344c71be2d5ea1d66c68e5ab4c60ab3585efb7a4ef6ae918212d25b \
  --record /mpac/sdicks02/k4s-runner/run-r1/end-staging/s10-127x03-r2 --outside-end-window "A2 GO <ref>, $(date -u +%FT%TZ)"
```
- **Logins: 6** = P-check, P-facts, R-bundle, R-guard, F, POST.
- Creates: `/mpac/sdicks02/jobs/clasher/k4s-end-r1/bundles/end-ref-127x03-rd00-a00/`, `/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd00-a00/`.

**Run 127x03-C (optional, later; a01)**: same as Run B with `rd00-a01`, `--record /mpac/sdicks02/k4s-runner/run-r1/end-staging/s10-127x03-r3`; guard manifest d39493f8a9cd76564e7768f61cef9fd1e33f0b4c94776847f93609adb1b2e03b. Logins: 6. Only on a separate GO (fresh guard job per attempt, Q4/RC-3).

### 127x04 (base `/mpac/sdicks02/jobs-k4s/k4s-end-r1`, Q4 guard parent `/mpac/sdicks02/jobs-k4s`)

**Run 127x04-A** (first staging: base + runtime + preflight bundle + its guard job; byte cross-check bundle↔guard job):
```bash
cd /tmp && umask 022 && env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 /mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -I -B \
  /mpac/sdicks02/k4s-runner/run-r1/end-prep/s3s9s10-r3/s10_stage_host.py --host 127x04 --create-base \
  --runtime /mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-98566c032d0b --runtime-manifest-sha256 4dd88461caa82f09bb27bc6adad1756f62dbc8d21aa041441f8c106ef9b80e04 \
  --bundle /mpac/sdicks02/k4s-runner/run-r1/end-staging/bundles/end-ref-127x04-pf00 <TIERS_PINS_SHA256 end-ref-127x04-pf00> <ASSEMBLY_RECEIPT_SHA256 end-ref-127x04-pf00> \
  --guard-job /mpac/sdicks02/k4s-runner/run-r1/end-staging/guard-jobs/guard-127x04-pf00 --guard-job-name k4s-end-guard-r1-pf00 --guard-manifest-sha256 b8a6cd28ab60b63f0781f48cdafd033eca5101227f6ae165bfddd098da29f7a5 \
  --record /mpac/sdicks02/k4s-runner/run-r1/end-staging/s10-127x04-r1 --outside-end-window "A2 GO <ref>, $(date -u +%FT%TZ)"
```
- Components: runtime (84635830 B), bundle end-ref-127x04-pf00 (~23373961902 B + small), guard job k4s-end-guard-r1-pf00 (63786662 B) → need ≥ bytes + 50 GiB free on /mpac (S10 P-facts refuses otherwise).
- **Logins: 8** = P-check, P-facts, base, R-runtime, R-bundle, R-guard, F, POST.
- Creates on 127x04 (each via `<final>.partial` then `mv -n -T`; runtime/bundles `chmod -R a-w`; guard dir writable):
  - `/mpac/sdicks02/jobs-k4s/k4s-end-r1/` with `attempts/`, `preflight/`, `runtime/`, `bundles/` (exclusive receive; base must be ABSENT before)
  - `/mpac/sdicks02/jobs-k4s/k4s-end-r1/runtime/runtime-98566c032d0b/` (S10 path — see BLOCKER B2)
  - `/mpac/sdicks02/jobs-k4s/k4s-end-r1/bundles/end-ref-127x04-pf00/`
  - `/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-pf00/`

**Run 127x04-B** (round-00 attempt-00 bundle + its guard job; bundles checked against the staged runtime manifest, runtime not re-shipped):
```bash
cd /tmp && umask 022 && env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 /mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -I -B \
  /mpac/sdicks02/k4s-runner/run-r1/end-prep/s3s9s10-r3/s10_stage_host.py --host 127x04 \
  --runtime-manifest-for-checks /mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-98566c032d0b --runtime-manifest-sha256 4dd88461caa82f09bb27bc6adad1756f62dbc8d21aa041441f8c106ef9b80e04 \
  --bundle /mpac/sdicks02/k4s-runner/run-r1/end-staging/bundles/end-ref-127x04-rd00-a00 <TIERS_PINS_SHA256 end-ref-127x04-rd00-a00> <ASSEMBLY_RECEIPT_SHA256 end-ref-127x04-rd00-a00> \
  --guard-job /mpac/sdicks02/k4s-runner/run-r1/end-staging/guard-jobs/guard-127x04-rd00-a00 --guard-job-name k4s-end-guard-r1-rd00-a00 --guard-manifest-sha256 da7fe5220a7d4b03ec00fcfca8c68bd63cd6b30d516b3cc53df8e6068031c3c8 \
  --record /mpac/sdicks02/k4s-runner/run-r1/end-staging/s10-127x04-r2 --outside-end-window "A2 GO <ref>, $(date -u +%FT%TZ)"
```
- **Logins: 6** = P-check, P-facts, R-bundle, R-guard, F, POST.
- Creates: `/mpac/sdicks02/jobs-k4s/k4s-end-r1/bundles/end-ref-127x04-rd00-a00/`, `/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rd00-a00/`.

**Run 127x04-C (optional, later; a01)**: same as Run B with `rd00-a01`, `--record /mpac/sdicks02/k4s-runner/run-r1/end-staging/s10-127x04-r3`; guard manifest 2b7af425ee867355bca68189077b9256ff659fcd76dc666f11e11b837275b313. Logins: 6. Only on a separate GO (fresh guard job per attempt, Q4/RC-3).

**Login totals:** 14 per host for A+B (8 + 6), **28 for both hosts**; +6 per host for each later a01 run. Login count rule from s10_stage_host.py run(): P-check + P-facts + [base with --create-base] + one receive per component + F + POST.

## Open items (no reviewed host tool — coordinator must provide/rule; not invented here)
1. **`<base>/repository`** (S5/S7 `--repository`): a FULL clone (verify_clone role `repository`; shallow, alternates, grafts, replace refs, promisor, hooks, includes refused) of branch `k4s-end-r1`, later fast-forwarded to the END-JOB commit (plan A6). S10 RC-6 marks it "provisioned separately (S6/S7)"; S10 does not create it and no reviewed tool does.
2. **`<base>/tools/`** (S7 RC-6 key `tools`): `detach.sh`, both wrappers, `k4s_end_preflight.py`, `safe_input.py`, `k4s_end_host_tool.py` at their S7-pinned SHAs (s5s6s7-r3; host tool 22c441b1db0fb7e1cf31cd259a5e838f375a7a935b3c78f5f5f5891869508647). Not staged by S10.
3. **native + corpus under `<base>`** (S5 `layout()`: K4S-owned files under the base, not in attempts/preflight/repository/tools): native `clasher_core.abi3.so` (44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2) and K4 corpus (a97b1fbf6cbc33a7b65aa5fc91eb0acdd07c922aaf0737620a849163aaadbfe8); the END plan has the corpus at `$J/end-corpus/` in `k4s-confirm-r1`, outside the END base. Not staged by S10.
4. B2 / B3 above (tool changes), and B1 (S4 fix).
5. RC-6 commit: S7 needs `end-launch/ROOTS-DECLARATION.json` = the `s7_roots_declaration` object of the candidate, with real `commit` and bundle `tiers_pins_sha256`, committed before the END-JOB.

## What S5 preflight (A4) needs from A2 (per host H, base `<base>`)
- `--bundle <base>/bundles/end-ref-H-pf00` + `--bundle-pins-sha256` (its tiers-pins SHA) — guard job must be `<Q4>/k4s-end-guard-r1-pf00` (staged in Run A).
- `--compare-bundle <base>/bundles/end-ref-H-rd00-a00` + `--compare-bundle-pins-sha256` (parity except guard.job; guard `-rd00-a00` staged in Run B).
- `--runtime-root <base>/runtime-98566c032d0b` (B2) containing the 32-file closure incl. SD1 (B3).
- `--corpus-inventory <runtime>/reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json` + `--corpus-inventory-sha256` = the S5 constant (B3).
- `--native`, `--corpus` under `<base>` (open item 3).
- `--end-evidence <bundle>/k4s-end-evidence/end-evidence.json` + `--end-evidence-sha256` 2ab14a3e3f15d41ff80bef31a0a529eddc78a05e61f42bce1e4bfbc4de50a3fd (committed at P').
- `--k4s-manifest-sha256` = 74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357 (fixed), `--sd1-manifest-sha256` (SD1 pin above).
- `--repository <base>/repository` (open item 1), `--attempt-parent <base>/attempts` (empty; S10 creates it), `--out <base>/preflight/preflight-H-l00/preflight-H-l00` (S10 creates `preflight/`).
- `<base>/tools/` staged (open item 2); hold ≥ 120 s (03) / ≥ 900 s loaded, no login (04).
- The pf00/a00 guard jobs must still be fresh (unused) at preflight/launch; a00's guard is consumed by END attempt 00 only.
