# K4S END prep: S1 (B2 exact-path copier) and S2 (END evidence builder + offline validator) — CANDIDATES r1

Status: **candidates for Sol review.** Nothing here has been run against a host. No commit, no push, no ssh was made
while writing them. Authored on 127x05 against origin/main `df03cbba` (fetched 2026-10-12, ~15:30Z), following
`run-r1/audits/K4S-END-PLAN-REVIEW-r1.md` §2, §4a S1/S2, RC-1, RC-4 and the notes, and
`run-r1/end-plan/K4S-END-PLAN-DRAFT-research.md` §1.4.

| File | Role |
|---|---|
| `s1_copy_end_sources.py` | S1: run from 05, reads 03/04 read-only over ssh (stdlib only) |
| `s2_end_evidence.py` | S2: `build` / `validate`, 05 only, no ssh (stdlib + the frozen code) |
| `tests/conftest.py`, `tests/test_s1.py`, `tests/test_s2.py` | offline pytest (fake ssh shim; synthetic git repo) |

## S1 — B2 exact-path copier

**What it reads.** There are 10 fixed phase directories (the namespace comes from the committed `run-r1/rounds/history.json`, which is cross-checked against a constant table):

- 127x03: `/mpac/sdicks02/jobs/clasher/k4s-confirm-<reporting-r1|replacement-rN>/<reporting|replacement-rN>/`
- 127x04: `/mpac/sdicks02/jobs-k4s/k4s-confirm-<…>/<…>/`. S1 never names anything under `/mpac/sdicks02/jobs/` on 04 (`FORBIDDEN_PREFIXES`; that's the perception storage).

Inside each directory S1 names exactly 4 full literal paths: `launch.json`, `supervisor-exit.json`, `mhz.jsonl` and `census.jsonl`. It uses no glob, no listing and no recursion, and opens no other name. It never touches `games/`, `complete.json` or block logs. The only remote programs are `stat`, `sha256sum` and `cat`, each with explicit file operands and run under `nice -n 19`.

**Expected values come from committed bytes.** S1 runs `git show <commit>:…` on the local checkout, with no fetch and no work-tree reads. It checks that:
- the phase-meta `launch.json` / `supervisor-exit.json` SHA-256 equals the constant `EXPECTED` table, which equals the 20 SHAs in the plan draft §1.4;
- each exit SHA equals completion-v2 `supervisor_exits[host/phase].sha256`;
- completion-v2 is `3794d953…` and its `counted_host_phases` are exactly the 10 pairs.

**Order and logins: 6 ssh logins in total, 3 per host.**

| # | Login | Remote command | Local checks (in this order) |
|---|---|---|---|
| 1 | P 127x03 | `LC_ALL=C stat -c '%F\|%s\|%n'` + `sha256sum` of the 20 paths on that host | per phase: launch/exit SHA == committed (else **REFUSE**); every file is a `regular file` (symlinks refused); mhz/census `0 < size ≤ 95 MiB` (99,614,720 B; else **REFUSE and stop**) |
| 2 | P 127x04 | same | same. **No copy starts unless P passed on both hosts** |
| 3 | C 127x03 | `cat -- <10 exact mhz/census paths>` → one local temp stream | stream length == sum of the P sizes; split by the P sizes; each piece's SHA == its P SHA; written with `open(...,'xb')` |
| 4 | V 127x03 | same as P | every size and SHA unchanged since P (else **REFUSE**: "changed during the copy"); mhz/census on-host SHA == local SHA |
| 5–6 | C, V 127x04 | as above | as above |

**ssh options on every login:** `-T`, `BatchMode=yes`, `ControlMaster=no`, `ControlPath=none`, `StrictHostKeyChecking=yes`, `ConnectTimeout=20`, `ServerAliveInterval=15`, `ServerAliveCountMax=4`, `ClearAllForwardings=yes` and `RequestTTY=no`. stdin is `/dev/null`. Timeouts are 900 s for P/V and 3600 s for C.

**Output.**
- `<dest>/<host>/<phase>/{mhz.jsonl,census.jsonl}`, 20 files. `<dest>` must not already exist.
- `<dest>/s1-copy-manifest.json` (schema `clasher.k4s.end-sources-copy.v1`). Per file it records:
  - the remote path and size;
  - the on-host SHA before and after the copy;
  - the local path, size and SHA.

  Per meta file it records the on-host SHA, the committed SHA and the committed path. It also records the six logins with their argv and UTC times, the script SHA, the commit, and the `--outside-end-window` text.
- The destination must hold exactly those 20 files, or S1 refuses.

**S1 refuses, with exit 2 and no manifest, when:**
- a launch or exit SHA differs from the committed one;
- a file is missing (non-zero `stat` exit);
- a path is a symlink or not a regular file;
- an mhz/census file is over 95 MiB, or empty;
- the stream length is wrong;
- a piece's SHA differs;
- an on-host file changed between P and V;
- any ssh fails or times out;
- `--dest` already exists;
- `--outside-end-window` is missing on a live run;
- the commit is not a full 40-hex commit;
- history or completion differs from the tables.

Once `<dest>` exists, a refusal writes `<dest>/S1-REFUSAL.json`, and partial copies may remain. **Do not commit a refused tree.** Delete it and re-plan. Unexpected exceptions exit 1.

**Timing.** S1 must never run inside any END timing window on any host, meaning from the first quiet read of an END launch to that attempt's exit plus C-d, and never during a preflight (RC-2) measurement either. S1 cannot detect a window itself. The live run therefore requires `--outside-end-window "<coordinator GO reference + UTC>"`, which is recorded in the manifest. Run it after the coordinator's A1 GO, before any END staging that starts quiet reads.

### Real run (after Sol review and the A1 GO; from 127x05)

```bash
cd /mpac/sdicks02/k4s-runner/run-r1/end-prep/s1s2-r1
git -C /mpac/sdicks02/repos/clasher fetch -q origin
C=$(git -C /mpac/sdicks02/repos/clasher rev-parse origin/main)
PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python        # 3.12.12, stdlib only needed
# 1. dry run: prints the six planned ssh argv and the 20 expected SHAs; no ssh, no writes
nice -n 19 $PY -I s1_copy_end_sources.py --repository /mpac/sdicks02/repos/clasher --commit $C --dry-run
# 2. live copy (exactly 6 logins)
nice -n 19 $PY -I s1_copy_end_sources.py --repository /mpac/sdicks02/repos/clasher --commit $C \
    --dest /mpac/sdicks02/k4s-runner/run-r1/end-prep/b2-copy-r1/end-sources \
    --outside-end-window "A1 GO <ref>, $(date -u +%FT%TZ)"
```

Then, which is a coordinator step and not part of S1:
1. Copy the `end-sources/` tree byte-for-byte to `reports/explore/k4s-confirm/end-sources/`. Include `s1-copy-manifest.json` if wanted; S2 does not require it in the repository.
2. Re-check the SHAs against the manifest.
3. Run `clasher-secret-scan` on the staged diff.
4. Commit via a temp index on origin/main and push. Call this commit **X**.

If any file is over 95 MiB, S1 refuses: escalate, and do not use LFS (`fleet_end.artifact` needs real blobs).

Prerequisites on 05: `ssh 127x03` and `ssh 127x04` must resolve via the LAN fleet key, and 05's `known_hosts` must already hold both host keys. `StrictHostKeyChecking=yes` refuses otherwise; do not relax it.

## S2 — END evidence builder + offline validator (05 only)

**`build`** writes `clasher.k4s.end-evidence.v1`, kind `counted-reporting`, with exactly the keys `schema, kind, plan, completion, blind_ledger, counted_inventory, phases`.
- Each phase entry has `host, phase, launch, supervisor_exit, mhz, census`. Every artifact item is exactly `{path, sha256, commit, repository_path}`:
  - `commit` is the single `--commit` X;
  - `repository_path` is the repo path;
  - `path` is that path relative to the evidence directory.
- The default evidence location is `reports/explore/k4s-confirm/end-evidence.json`, so paths are relative to `reports/explore/k4s-confirm/`. Examples: `plan.json`, `run-r1/completion-v2/REPORTING-COMPLETION.json`, `run-r1/phase-meta/127x03-reporting/launch.json`, `end-sources/127x03/reporting/mhz.jsonl`.
- Bytes come only from `git show X:<path>`.

**Pinned defaults** (the records):

| Input | Path | SHA |
|---|---|---|
| plan | `plan.json` | `38064dcd…` |
| completion | completion-v2 | `3794d953…` (RC-1: the completion of record) |
| counted inventory | | `22c41cb7…` |
| blind ledger | `blind-ledger-final.json` | `649272bd…` |

Counted hosts must be `127x03`, `127x04`. Phases follow the completion's `counted_host_phases`. Each supervisor-exit SHA must be bound by the completion's `supervisor_exits`, and the completion must bind the inventory and the ledger.

With `--s1-manifest`, S2 also checks:
- each mhz/census local SHA == on-host SHA == committed SHA, and the size matches;
- each launch/exit on-host SHA == committed SHA, and the path matches.

**Build refuses:**
- an evidence path inside `reports/explore/k4s-confirm/end/` (the strict namespace);
- an evidence name like `END-JOB*`, `END-FINAL*` or `attempt-*`;
- a path outside the study directory;
- any pin mismatch;
- an uncommitted artifact;
- an unbound exit;
- an empty artifact;
- a mismatch with the S1 manifest;
- an existing output file.

**`validate`** (fail closed; writes one JSON result and exits 0 only if `ok`):
1. Check that `--commit` is an ancestor of HEAD, that the evidence SHA equals `--evidence-sha256`, and that the structure is the exact layout above. Every item must carry commit X, and `path` must equal `repository_path` taken relative to the evidence.
2. Import the **frozen** code from `--code-root`, which defaults to the checkout. Verify it with `k4s_logic.load_k4s_manifest(K4S-MAC-MANIFEST.json, 74314eda…, require_frozen=True)` and `end_pool.frozen_helpers`, which checks the e4v3 pins. S2 refuses if any frozen module was imported from elsewhere. `--no-manifest-check` exists for tests only, and the result records it.
3. Run the frozen `end_evidence.end_evidence(evidence, sha, repository, fleet_end)`. This covers byte equality with the committed blob, ancestry, launch/exit identity and `counting()`.
4. Check the record bindings: completion, plan, inventory and ledger SHAs; counted hosts; and membership `blocks == 3900`, `losses == 99`.
5. Per counted host, run the frozen `fleet_profile.slot_layout(profile, plan, host, plan.compute.nice)` and `fleet_end.host_reporting(evidence, profile, plan)`. That covers the exact utc join, at least 2 full-occupancy rows and `slots == 11`. Also apply the reporting-side preconditions of `compare_mhz`: every occupied physical core is present, with finite MHz above zero.
6. Optionally, cross-check against the S1 manifest.

The result records:
- the frozen module SHAs and the interpreter;
- `optimize`;
- per host: the reference CPUs, the background slot count, `census_cpu`, the full-occupancy row counts per phase, and the census row counts.

**Offline limits (stated, not hidden).**
- `slot_layout` is given the counted host and the plan's `nice` (10). Its live hostname and priority gate is therefore **not** exercised here; on the host it runs before the claim.
- The profile defaults to the S4 declaration from review §4a: slot 0, 11 slots, `console_rule:false`, `warmup_seconds` 300, perception `none`. Once the S4 bundles exist, re-run with `--profile-json '{host: reference_load_profile}'`.
- Nothing past `slot_layout` (backend, guard, topology, MHz gate under load) can run on 05. That is RC-2's job.

### Real run (after X is pushed)

```bash
PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python          # PC3 interpreter (3.12.12)
S2=/mpac/sdicks02/k4s-runner/run-r1/end-prep/s1s2-r1/s2_end_evidence.py
M=/mpac/sdicks02/k4s-runner/run-r1/end-prep/b2-copy-r1/end-sources/s1-copy-manifest.json
git -C /mpac/sdicks02/repos/clasher fetch -q origin
X=<full SHA of the end-sources commit>
git -C /mpac/sdicks02/repos/clasher worktree add --detach /tmp/k4s-s2-build $X
nice -n 19 $PY -I $S2 build --repository /tmp/k4s-s2-build --commit $X \
    --out /tmp/k4s-s2-build/reports/explore/k4s-confirm/end-evidence.json --s1-manifest $M
sha256sum /tmp/k4s-s2-build/reports/explore/k4s-confirm/end-evidence.json
# coordinator: commit end-evidence.json alone (commit Y, child of X; temp index; secret scan; push)
git -C /mpac/sdicks02/repos/clasher worktree add --detach /tmp/k4s-s2-check <Y>
nice -n 19 $PY -I $S2 validate --repository /tmp/k4s-s2-check --commit $X \
    --evidence-sha256 <sha of end-evidence.json> --s1-manifest $M \
    --result /mpac/sdicks02/k4s-runner/run-r1/end-prep/b2-copy-r1/s2-validation.json
git -C /mpac/sdicks02/repos/clasher worktree remove /tmp/k4s-s2-build
git -C /mpac/sdicks02/repos/clasher worktree remove /tmp/k4s-s2-check
```

The evidence has to be committed in a later commit Y than X. It names X in every item, and a file cannot name its own commit. The END-JOB, which binds `end_evidence_sha256`, comes after Y.

## Tests (offline; what was verified)

```bash
cd /mpac/sdicks02/k4s-runner/run-r1/end-prep/s1s2-r1
nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -m pytest -q -p no:cacheprovider tests
nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -O -m pytest -q -p no:cacheprovider tests
```

Both runs passed: **34 passed** normally and **34 passed** under `-O`. The scripts run as subprocesses with `-I`, plus `-O` when pytest runs under `-O`, and the happy-path test asserts that the subprocess's `sys.flags.optimize` matched.

The tests need the real clasher checkout at origin/main (`CLASHER_REPO` overrides the location):
- the S1 fake hosts serve the **real committed** phase-meta bytes, so the real constant table is what gets tested;
- the S2 code root is the K4S manifest's closure exported from origin/main, so the frozen manifest check runs on real frozen code.

**S1 tests.** A fake `ssh` on `PATH` serves a temp tree as each host's `/`. It refuses a login that lacks `BatchMode`/`ControlMaster=no`/`ControlPath=none` and logs every argv. The tests cover:
- the happy path: 6 logins in the order P03, P04, C03, V03, C04, V04;
- every option present and `nice -n 19` in every command;
- every absolute path in every command is one of the 4 allowed names in that host's own phase directories, with no glob, find, ls, tar, rsync, scp or `-r`;
- no `/mpac/sdicks02/jobs/` path in any 04 command;
- the destination holds exactly 20 files plus the manifest, and each file's bytes match the original;
- decoys (`games/`, `complete.json`, `mhz.jsonl.old`, block logs, a perception look-alike on 04) are never named;
- dry run: no ssh, no writes;
- launch mismatch on 04: refused after the two P logins, no destination;
- exit mismatch on 03;
- oversize (sparse 95 MiB + 1) on 03, and on 04 (after both P logins, before any copy);
- a size-boundary unit test: exactly 95 MiB is accepted, +1 and 0 are refused;
- a missing file;
- a symlink;
- a file mutated during the copy (V refuses and `S1-REFUSAL.json` is written);
- extra stream bytes;
- an ssh failure (rc 255);
- a missing window acknowledgement, with no login made;
- an existing destination, with no login made;
- the forbidden-prefix and `..` guard.

**S2 tests.** These run on a synthetic committed repository: 3000/900 counted blocks, 1 loss with a replacement, 3 host/phases, and mhz/census rows. They cover:
- build plus validate on the happy path, with the frozen manifest verified, membership 3900/1, and full-occupancy rows 8 and 4;
- build refusals: evidence under `end/`; an authority-like name; the real-run pins against synthetic data; uncommitted sources; an unbound exit; overwrite; the S1 manifest cross-check, both pass and fail;
- validate refusals: evidence SHA mismatch; a work-tree artifact that differs from its commit (frozen `pin mismatch`); commit not an ancestor (orphan HEAD); a broken mhz/census join; no full-occupancy rows; an extra top-level key; a wrong membership expectation; a tampered frozen `fleet_end.py` (manifest `Pin mismatch`); a code root without frozen code; result overwrite;
- `--no-manifest-check` is recorded as `frozen_manifest_verified:false`.

**Also verified.**
- `s2 validate` runs on the e4v3 interpreter (`/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` 3.12.12, the one T1 used for pool and recheck). On the synthetic fixture the result was `ok`, with the manifest verified.
- `s2 build` on the **real** origin/main inputs got past the plan, completion-v2, inventory, ledger and first-phase launch/exit pin and binding checks. It then refused at the first uncommitted source (`end-sources/127x03/reporting/mhz.jsonl`), which is expected before B2.
- `s1 --dry-run` on the real repository resolved every table entry against the committed bytes.

**Not verified.** No live S1 run was made. S2 has not run on real mhz/census data, because none is committed yet.

## Notes for Sol review

1. **S1 is exact-path at the command level, not by syscall tracing.** The remote side runs only `stat`, `sha256sum` and `cat`, with literal file operands; none of them recurse or expand. The fake shim tests check the command strings and the argv. The shim does not trace remote `open()` calls.
2. **One `cat` per host for 10 files.** This keeps logins at 6. A wrong split cannot go unnoticed: the total length plus each piece's SHA against login P, and then login V, would catch it. The alternative, one `cat` per file, would take 24 logins.
3. **The size cap applies to mhz/census only.** Launch and exit files are SHA-pinned to committed blobs, so they are not size-capped. Empty mhz/census files are also refused, as an addition: they could never satisfy `host_reporting`.
4. **Health-only content.** The copied census rows are `supervise.py` `progress` dicts: utc, host, phase, local completed/failed block counters, queued, inflight, console, memory and the stop reason. The mhz rows are utc, slots and per-CPU MHz. Neither has a game result field. The remote `sha256sum` reads only the 4 named files.
5. **A real-data risk the validator will catch, but cannot fix.** `supervise.py` appends the `census.jsonl` row before it reads `/proc/cpuinfo` and appends the `mhz.jsonl` row. A supervisor killed between those two writes would leave one census row without its MHz row. The frozen `host_reporting` then refuses ("Reporting MHz/census inventories differ"). The raw files cannot be edited, so that case would need a coordinator ruling. The utc stamps are at 1-second resolution (`date -u +%FT%TZ`), and each loop takes longer than 1 s, so duplicate stamps are unlikely but not impossible.
6. **`slot_layout` offline** gets the host and `nice` from the plan; see Offline limits. Re-validate with `--profile-json` after S4.
7. **S2's extra checks are stricter than the frozen reader.** They require exact key sets, a single commit X, `path` equal to `repository_path` relative to the evidence, the completion binding exits, ledger and inventory, and the record SHAs. The frozen reader is still the authority, and it runs unchanged.
8. **Scratch.** The tests write only under pytest `tmp_path` (`/tmp/pytest-of-sdicks02/`, rotated by pytest). The two manual smoke checks used `/tmp/s2-e4v3-smoke` and `/tmp/s2-real-check`; both were removed.
