# PC4 reviewer check r2: OP-7 sensitivity sidecar from the landed bytes (1cb46a13)

**Verdict: PASS**

- **Reviewer:** Claude Opus 5.5 (1M context), the independent PC4 reviewer (also ran r1). I am not the T1 worker, the coordinator or the lineage investigator.
- **Hosts:** reviewed on 127x05; executed read-only on hub 127x01 (`ssh -o ControlMaster=no -o BatchMode=yes 127x01`). No other host was used.
- **Authority:** COORDINATOR 9897216c R1 item 4 and 3c29de85 ("second PC4 run from the landed bytes ... add `-B`"); `END-PC4-LINEAGE-INVESTIGATION-r1.md` §5.4.
- **Written:** 2026-10-12T08:45:16Z.
- **Scope:** health-only. I opened no `games/` files and no outcome fields. On 01 I wrote only the scratch directory `/mpac/sdicks02/tmp/pc4b-20261012T084334Z`, which is now removed. Nothing under `/mpac/sdicks02/jobs/clasher/` on 01 was written (a `find -newer` check after the run found nothing), and the paused mirror (516161) was not touched.

## Result

The CLI run from the landed bytes gives a sidecar that **equals the first-run sidecar ea3d44d3 and the committed 48730da5 in every field except the top-level `utc`**. The match is also byte-for-byte: with `utc` masked, all three files hash to `33a272e0a40142fddea050961ed1e7a347a5c1a4d46d5a22e9f75e4969dea018`.

**All 28 checks in `pc4_reviewer_check.py` (5c4cdada, unchanged from r1) pass.** The complete-proof digest is ef621e51 and the set digest is d0f01069, both the same as r1. The flags are SSH 477, apt 0, both 0 and either 477, with 0 SSH stops and 0 apt stops.

## Source and module SHAs

- **Commit:** 1cb46a138788a4dde81bc74f7313f07804e15bfc. It is an ancestor of origin/main.
- **Archive:** `git archive 1cb46a13 reports/explore/t1`, made on 05, sha256 `f796174364647f1e998d0104d82894f800847e2da8ad7b2bc8813f5eed029db3`, 512 files. I extracted it into scratch on 01 and compared a full sha256 listing of the extracted tree with the local archive: they were identical.
- **Module check:** a probe imported `ssh_sensitivity` and `apt_budget` (the CLI imports `apt_budget` lazily) without running the CLI. It confirmed the local modules below. `host_audit` was not loaded.

| module | landed SHA | expected | 488f6c8d | status |
|---|---|---|---|---|
| ssh_sensitivity | bb124cc4 | bb124cc4 | bb124cc4 | ok |
| apt_budget | c1578535 | c1578535 | c1578535 | ok |
| cpu_accounting | 5ecae99d | 5ecae99d | 5ecae99d | ok |
| common | 36e5eec3 | main | 36e5eec3 | same as 488f6c8d |
| idle_services | 911c18ae | main | 911c18ae | same as 488f6c8d |
| ssh_transport | 16a211a5 | main | 16a211a5 | same as 488f6c8d |
| ssh_budget | **0c2759f5** | main | **0ef24fac** | **differs** (expected; R1 leaves ssh_budget unchanged) |

**ssh_budget difference** (0c2759f5 on main vs 0ef24fac pinned in 488f6c8d, which r1 used):
- Main's OP-6 version does not import `cpu_accounting`.
- `sample`/`begin`/`update` use `increment()`/`partition_ticks()` instead of `Accounting`.
- `finish()` doesn't emit `cpu_accounting_rule`.

None of these are on the PC4 path:
- `ssh_sensitivity` uses only `lan_connection`, and `apt_budget` uses only `generation` and `total_ticks`. All three functions, plus `UID`, `LAN` and `AVERAGE_STOP_MIN_SECONDS`, are byte-identical in both versions.
- `cpu_accounting` is still loaded, through `ssh_sensitivity` and `apt_budget` directly.

**Effect on output: none.** The sidecar is unchanged apart from `utc`.

## Run (once, on 127x01)

- **cwd:** `/mpac/sdicks02/tmp/pc4b-20261012T084334Z/reports/explore/t1`
- **argv:** `nice -n 19 taskset -c 62 /mpac/sdicks02/tools/uv-python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12 -E -s -B ssh_sensitivity.py --root /mpac/sdicks02/jobs/clasher/t1-20261010-r1/replacement-frozen-op7-0108-r3/hub-blocks --ledger /mpac/sdicks02/tmp/pc4b-20261012T084334Z/blind-ledger.json --out /mpac/sdicks02/tmp/pc4b-20261012T084334Z/ssh-sensitivity-pc4-landed.json`
- **Ledger:** `blind-ledger.json` is 866e6f7f, copied from `1cb46a13:reports/explore/t1/receipts/blind-ledger-final-op7-r3.json`.
- **`sys.executable`:** `/mpac/sdicks02/tools/uv-python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12` (binary sha256 021044895e95…, same as r1).
- **Version:** `3.12.13 (main, Aug  7 2026, 02:25:39) [Clang 22.1.3 ]`
- **Flags:** `ignore_environment=1`, `no_user_site=1`, `dont_write_bytecode=1`. No `__pycache__` was written; this closes r1's procedure note 2.
- **Timing:** started and ended at 2026-10-12T08:43:58Z.
- **Exit code:** 0.
- **stdout:** `SSH sensitivity health ledger written; outcomes SEALED`
- **stderr:** empty (0 bytes).
- **Writes:** no file under the interpreter tree or under `/mpac/sdicks02/jobs/clasher` on 01 is newer than the run start.
- **Cleanup:** I copied the outputs to 05 and re-verified their SHAs, then removed the scratch at 2026-10-12T08:44:23Z. No `pc4*` scratch is left in `/mpac/sdicks02/tmp` on 01.

## Checker inputs (05)

- **Checker:** `PC4/pc4_reviewer_check.py` 5c4cdada, run with `python3 -I`.
- **Inputs:** taken from 1cb46a13 `receipts/`:
  - sidecar 48730da5;
  - inventory 50f24dd6;
  - END 6f6f0007;
  - completion 9e788d20;
  - ledger 866e6f7f;
  - bindings 08cad0ff, the same as r1.

  `FROZEN-T1.json` 488f6c8d came from ef4c073a.
- **Fixed input name:** the script reads `from01/ssh-sensitivity-pc4.json`. That file is a byte copy of the landed output (16e1b34f).
- **Reviewer inputs:** the archive, copy-back and run metadata are kept at `/mpac/sdicks02/tmp/pc4b-review-20261012T084326Z`, outside every job root.

## Files in `PC4/` (r2)

- `ssh-sensitivity-pc4-landed.json`: `16e1b34f7e376e42f3a18a7d9bb8b2ac09613d9f3555bfd2f97f8c7cad388f2e` (utc 2026-10-12T08:43:58Z)
- `PC4-REVIEWER-CHECK-RECEIPT-r2-landed.json`: `98e980ff8f214bd4c01f0087f8e59c32a7344cd72c33d7e754b31e9ea1f025ff`
- The r1 files are unchanged (11bbfc9a, 48fe1011, 5c4cdada, ea3d44d3). Their copies in 1cb46a13 `receipts/PC4/` are byte-identical.

## Findings

1. **PASS.** The §5.4 second run from the landing commit's bytes reproduces the sidecar exactly, apart from `utc`.
2. **ssh_budget 0c2759f5 vs 0ef24fac:** this is a real byte difference in an imported module. It has no effect on the output, for the reasons above.
3. **Still outstanding (outside this check):** reducer aebb2017's emitted ledger must equal this sidecar except `utc` (R1 item 2, R6/R7).
