# Separate qualification staging and launch package

This is an implementation for parent review. It grants no staging, admission or launch authority. No remote command has been run. R40 retains exclusive access to 127x09 and 127x12 until its explicit release for each host. The six running BC jobs stay untouched.

The source is `fe6d64214200679372f337bb37b33606f5c9997d`. Its canonical pretrain Python aggregate is `ff71c87aa81d069f2574dcb30aff0df988a56a7a20d7b925a96f1441c669dd0e`. `inventory.json` freezes all 96 source files, including all 83 Python files, tests, catalog and `bot/__init__.py`. It also freezes the exact 402 relocated input destinations and both unchanged prepared configs. Source is copied as a complete directory payload. There is no tar extraction, link materialization, download or implicit import fallback.

R48 and R49 permit qualification code/config eligibility only. R49's evaluator finding remains outside `soak`. This package neither changes that source nor substitutes the later evaluator fix. Production R47/R50 reporting is separate.

The parent owns the final configs, physical evidence, release, independent review and launch authority. The package never manufactures those files. The new precision receipt at `/mpac/sdicks02/jobs/clasher/rl-qualification-receipts-20261022/fe6d64214/precision-GO.json`, SHA256 `0d85120715f2df663f3e38eb41be25d7d3626c9843d367ca41348f3bd448d67a`, and queue composition, SHA256 `c46dfc02ebd422dc9f4d2c57c21f2ac39ebdf8316a73e45b37c15d62d6fd3d8a`, are component evidence only. Include the consumed parity/review/evidence copies explicitly in the extra-file list. Redundant copy files are unnecessary.

## Files and local verification

`operate.py` admits exactly one named phase through the pinned R37 CLI, or runs as that admitted root. `prepare_payload.py` makes a fresh local directory payload from the pinned checkout and exact inputs. It does not transport or install anything. `cpu_probe.py` imports Torch/NumPy and the staged driver with CUDA hidden, checks origins and the source aggregate, and optionally runs the real complete `D.audit(..., qualification=True)`. It never constructs a Runtime or invokes an engine. `test_operate.py` uses disposable CPU fixtures only.

Run tests from this directory. They retain each fresh fixture directory under the jobs package, use no current-job scans, and signal only their own explicitly captured disposable CPU children. Do not delete prior attempts.

```sh
env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  nice -n 10 python3 -B -m unittest -v test_operate
```

`freeze.json` lists SHA256 and byte count for each of the six reviewed package files. The package pin is the SHA256 of `freeze.json` itself. Every remote entry rechecks every listed file. Any edit requires a new freeze and a fresh independent operational review. The parent must independently verify the package pin when copying these files to the exact jobs package path.

## Parent-supplied contract

The contract is a JSON file at a new allowed jobs path, with its raw SHA256 supplied on every command. It has these required fields. A reference always has exactly `path` and `sha256`, with a nonzero lowercase SHA256 and a canonical absolute path under `/mpac/sdicks02/jobs/clasher`.

- `schema`: `qualification-operation-v1`.
- `host`: `127x09` for M or `127x12` for S100.
- `source_commit`, `source_sha256`: the exact source identities above.
- `package_sha256`: the externally verified SHA256 of this package's `freeze.json`.
- `final_config`, `release`, `operational_review`, `r49`: explicit references. The R49 bytes must have SHA256 `9c3fd940f160ad9938dd480fb6891a092f32b4434c438ea7929aef5eaa235470`.
- `supervisor`: path `/mpac/sdicks02/repos/clasher-pv1-lease-20261022/bot/pretrain_v1/lease_supervisor.py` and SHA256 `0613d6db62371eb197bb5d41cbf342b57f1998ddeb91e04c7c5ab2be36ac0ffc`. The parent must confirm this installed location from readiness before approving the contract. There is no override to an unreviewed supervisor.
- `out`: exactly `/mpac/sdicks02/jobs/clasher/rl-qualification-launch-20261022/hosts/HOST/soak`.
- `job_names`: distinct explicit names for `source`, `inputs`, `soak`, each matching `qual-fe6-[A-Za-z0-9_-]{1,48}`. Names and host outputs belong to one attempt. A failed phase is retained and cannot be retried by this package.
- `extra_files`: an ordered list of records with exactly `path`, `sha256`, `bytes`. Each is a separately supplied immutable file of at most 16 MiB. Include the final config, all four authority refs, physical/max-shape evidence, the operational review report, qualification gate evidence and precision parity results. Paths cannot overlap the package, driver, existing prepared-input tree, R37 state or R40 working tree. Supply parent-pinned copies of physical receipts at new receipt paths. All consumed evidence must resolve either to this explicit list or one of the frozen 402 inputs. Raw provenance references inside unconsumed historical evidence are not rewritten.

The final config must equal its frozen R49 prepared config except for the four evidence registration/launch references and `gpu_admission`. The latter still has to pass the exact driver's physical/max-shape admission checks. Both final config and physical evidence are externally pinned. Runtime and actor locations stay exactly `/mpac/sdicks02/repos/clasher-pv1-ready-20261022/{runtime,actor_source}`, with joint manifest SHA256 `60b94e875dfe856e8bd712ee6947c7f3998ecccc50a2972d20fa4f35e1f2eaee`. No scientific field, source, live environment or relocated input can change during final binding.

The package verifies required qualification and precision receipts through the unchanged driver audit. It does not infer qualification launch authority from a component receipt. There is no switch that skips these checks.

## Release and review authority

The parent supplies an R40 release JSON with `schema=qualification-r40-release-v1`, `status=released`, `host`, exact `source_commit` and `source_sha256`, and `final_config` equal to the contract reference. It must record a UTC `utc`, with `explicit_per_host_release`, `actual_measurement`, `exact_owned_tree_reaped`, and `full_gpu_free` all true. `physical_measurement` must equal the final config's `gpu_admission.process_measurement` reference. The corresponding measurement must report a passing full CUDA process peak for the same size, precision and anchor, matching the config's physical peak and covering its reserved peak. A physical two-Adam-step measurement is an admission input, not six-hour memory proof.

The independent reviewer then supplies an operational review JSON with `schema=qualification-operational-review-v1`, `status=GO`, `scope=separate-six-hour-qualification`, `model=gpt-6.1-sol`, `effort=high`, `independent=true`, `host`, the exact source identities, `final_config`, `package_sha256`, `release`, `r49`, and an explicit `report` reference. `phases` must be exactly `["source","inputs","soak"]`. `inventory_sha256` is the canonical digest of the complete inventory object. `extra_files_sha256` is the canonical digest of the ordered extra-file list with only this operational-review JSON's own record removed. Its report remains included. This avoids self-reference. Canonical digests use `operate.digest`, sorted JSON keys, compact separators and finite numbers.

These schemas are the package's external interface for parent-issued authority. A fresh independent review must approve the code and this concrete authority contract before any remote use. This implementation is not that review and issues no GO. The package checks pinned assertions; the parent and reviewer must establish their truth from actual release and measurement evidence.

## Later parent procedure

Do not run these steps during implementation. After R40's per-host physical release, parent receipt/config binding and the independent operational review, the parent can build each host's payload locally. Set `CONTRACT`, `CONTRACT_SHA256`, and `PAYLOAD` to actual reviewed values, not placeholders. The payload destination must be fresh and below the jobs package.

```sh
env PYTHONDONTWRITEBYTECODE=1 nice -n 10 python3 -B prepare_payload.py \
  --contract "$CONTRACT" --contract-sha256 "$CONTRACT_SHA256" --out "$PAYLOAD"
```

The payload contains `source/` with the complete reviewed subtree, `inputs/0` through `inputs/401` in sorted destination order, `extras/SHA256` for each explicit extra file, and a local payload inventory. Parent-owned transport must preserve this directory payload and the six frozen package files plus `freeze.json` at exact allowed paths on the released host. This package includes no SSH or transfer command. Transport itself remains subject to parent authorization and review. Existing different bytes cause refusal; nothing is overwritten or extracted.

On each host, the parent invokes the already installed ready Python explicitly. Preserve its GPU mask and CPU affinity. `PYTHONHOME` is required because the moved executable alone does not relocate its base prefix. Each command below exits after R37 returns an admission record. The admitted job persists independently under the existing watcher. It does not depend on a shell, SSH session or local parent process staying alive.

```sh
export PYTHONHOME=/mpac/sdicks02/repos/clasher-pv1-ready-20261022/python
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
READY_PYTHON=/mpac/sdicks02/repos/clasher-pv1-ready-20261022/python/bin/python3.12
PACKAGE=/mpac/sdicks02/jobs/clasher/rl-qualification-launch-20261022
nice -n 10 "$READY_PYTHON" -B "$PACKAGE/operate.py" admit source \
  --contract "$CONTRACT" --contract-sha256 "$CONTRACT_SHA256" --incoming "$PAYLOAD"
```

Wait for the source phase's successful receipt and R37's exact gone/reaped evidence before issuing the next command. Then admit `inputs` with the same arguments. Wait for its receipt and exact gone/reaped evidence before admitting `soak` with the same arguments. These are two sequential CPU staging jobs, followed by one separate persistent soak per host. Parent owns waiting and verifying those receipts. There is no automatic cross-host launch, retry, resume, replacement or top-up.

Source staging has a 300-second wall bound. Input staging has an 1800-second wall bound. Each reserves at most three processes and 4 GiB PSS with zero GPU reservation. Each normally uses one wrapper and one CPU import/audit child. Both enforce their own process/PSS budget as well as the host totals. The source receipt records all 96 source hashes and the expected input inventory digest, with zero verified input files. The input receipt records all 402 input hashes, all 9409 runtime and 17010 actor files, exact tree membership and a successful complete CPU audit. No CUDA context is initialized by either stage.

Soak reserves 40 processes and 48 GiB PSS. GPU reservation is the final config's physical process peak, never allocator-only memory. This reservation includes the wrapper, learner, 32 persistent actors, monitors, timeout work and query descendants; all actual token-bearing descendants are charged and checked. There is no separate timeout process. Each command uses nice at least 10 and sets all math thread environments to one. Child environments preserve all three R37 lease-generation variables and the inherited GPU mask. Python caches, NumPy/Numba/Torch caches and temporary files stay in the jobs package. No cache or system path outside allowed roots is touched.

The soak wrapper has a 25200-second total wall bound, including full rehashing, a CPU audit, startup and bounded shutdown. Its driver child has a 22770-second deadline, allowing 900 seconds for pre-readiness preparation, the driver's 120-second all-worker readiness bound, 21600 seconds of exposure, and 150 seconds of driver shutdown. The six-hour clock and 128-update ceiling come from the pinned driver. Ceiling exhaustion before exposure completes fails. The wrapper never uses raw queue promotion or registered steps. A successful driver result remains `completed-exposure-pending-review`, test-only, with no registered prefix, promotion or qualified engine resume.

## Enforcement and remaining gates

The exact R37 watcher PIDs/start times are checked from readiness and against the current boot. They are never restarted. A fresh active owner lease is read by path before every admission and repeatedly during each job. Watcher status and its valid lease observation must both be at most 60 seconds old and match the newly opened lease bytes and identity. Independent writers need no inode agreement or cooperative lock. Reclaim, refused, lease replacement, unreadability or stale observation prevents package admission. While running, this wrapper stops conservatively on unreadability; R37 retains its separately persisted 300-second unreadable window and all reclaim/expiry enforcement. Owner leases remain read-only.

R37 alone admits and enforces its full durable resource accounting. The package additionally requires all-clasher process totals at most 96 on 09 and 64 on 12, aggregate PSS at most 64 GiB, every clasher process nice at least 10, MemAvailable at least 32 GiB and load at most 90. Do not substitute R37's lower 28 GiB admission floor for this package's 32 GiB guard. Expiry can never pass `2026-10-25T07:53:00Z`. Admission requires enough lease horizon for the entire phase plus its reclaim grace, R37's 600-second exit margin and 180 seconds of cleanup margin. Lease 13-16 is not used.

The original driver's exact PID/start/session worker accounting, blocked-ack handling and independent physical GPU-free monitor remain active. Physical GPU free must remain at least 8 GiB. R37's independent ownership/resource/reclaim guard remains active around the complete tree, including any stuck GPU work. The wrapper uses the same reviewed R37 token/descendant discovery and pidfd signals to clean only its owned children. It adopts orphaned descendants, reaps them, and refuses success if cleanup is incomplete. Failure permits the soak driver's existing cooperative shutdown for up to 160 seconds, followed by exact TERM and KILL phases of five seconds each. An outer 180-second cleanup deadline bounds failure handling. R37 retains responsibility for any incomplete tree, within its unchanged maximum 30-minute reclaim contract. No global signal or foreign-process control exists here.

Before soak, every source/input byte and extra-file pin is rechecked, both ready trees are checked for full membership and hashes, and the real CPU qualification audit must pass. Driver admission then independently checks actual physical GPU fit. A release assertion cannot replace that check or the running physical-free monitor.

Still required from the parent: actual R40 release/evidence for both hosts, final source/config-bound qualification launch gates and configs, fresh independent Sol high operational review, exact-path remote transport and both CPU staging receipts, fresh R37 admission, actual six-hour runs, exact final reaping, and post-exposure review. None is discharged by these local tests or this package's existence.
