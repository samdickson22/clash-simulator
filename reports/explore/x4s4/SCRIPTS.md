# X4S-4 scripts, r3 for Sol re-review (exploration, NEVER ADOPTABLE)

The design is frozen at PLAN r3 87809ae0. The history of the script set:

| Round | Script set | Sol verdict |
|---|---|---|
| r1 | 13fb31d0 | REQUEST_CHANGES, 18 findings |
| r2 | f15691b5 | REQUEST_CHANGES (a556419e): F1, F2, F3, F8, F11 fixed; R2-F1–R2-F10 open |
| r3 | this commit | — |

r3 fixes R2-F1 to R2-F10. Nothing has been run on any host. Everything below was done offline on 127x05, using synthetic fixtures and disposable git repositories under /dev/shm.

## Index

| File | Kind | SHA-256 |
|---|---|---|
| `x4s4io.py` | **new in r3**: the one I/O, subprocess and signal gate | `5b5080324db052584f54303f8267cd440905727deeec9f5647eb7dc0683419f6` |
| `studytree.py` | r3: shared live guards | `94ad2e752ccfc49d2e364f89959b10944613dbfea8e1545f62a709d9c5bc930f` |
| `run_collect.py` | unchanged since r2 | `f945ac6c266267d52689df9cd0b3a658705740a513b86866e16d3786dc64780b` |
| `collect.py` | new | `ce29b1311cc0489a32f09885fd8f44c5df40ed9d9d7292597b4567c9fa006494` |
| `label.py` | new | `d5782818e42d013f1a45b6af2917827a9afe851f367c47ab4b60328fe2dc1532` |
| `collect_w.py` | new | `a0c9d322996b2396bcbb9e600970d91f5ff08ab31c9a27d4c8567a5ef958bc03` |
| `verify_onpolicy.py` | new | `767259e6f54b10b99ff7517a0a8c339b0593bfefab47bb987f7421d2c63acc1f` |
| `diagnose.py` | new | `3a4e6c1c7b12d8c0987a01747c3075622b3df063188b82f815aef6921e066dbc` |
| `contention.py` | new | `0139abc5590fdb1bd5698bde97b9d63362ebc929c2eb85b14f27cb5d0ae53be3` |
| `qualify4.py` | new | `8dcd13056b2d18bfd02434e4090cc02ba069b465673cb0c7abee7b7b8b34af08` |
| `supervise.py` | modified (from x4s3) | `b333b12f1f41d471bbcb3a06d7f96b7e1f7672e6e79e5e1e64e28d4d3fc9e987` |
| `run_fit.sh` | unchanged since r2 | `0dda76798d83b508274a42c771105a64842b7d7f2efd23091dd8e38cfeb35fa0` |
| `driver.py` | modified (from x4s3) | `fe70dbb71487b7be6e5789defe51bd5104e072306469d18375f670a3bba445ff` |
| `reduce.py` | modified (from x4s3) | `8757c77fc9ae8bb260397eb716956a3e79c33db61013f91d836791a3c8a74911` |
| `write_report.py` | modified (from x4s3) | `db3df449df258cbf339af9acda86324490097869be50aa6caac26a079617bc7b` |
| `audit_seeds.py` | modified (from x4s3) | `36b4d037386514b1bc840e8e20690af9cadf1902d6b9f165462b4c802facd022` |
| `seed-sources.json` | **new in r3**: the reviewed seed-source inventory | `b221a75e27f97f9aa2ef6602e3142c1c4ec013fe9ae7545253c50c3213fb90d1` |
| `plan.json` | config | `13840cc60834dd6c46ff1aa9bc4b75ca752a6df9bc9e95939bab544b2d04c4e1` |
| `plan-collect.json` | config, unchanged | `57f6a1427a584a607fe1e8da79e14340736f90bbf909795a8f125ffd1b9fedea` |
| `plan-qual-capture.json` | config, unchanged | `450522158dccbe73216c3cc2b86054cdde4fbe62f4d55dafd0e75c87470461d4` |
| `idx-qual.json`, `idx-smoke.json` | config | `4587c7edd4a17da602e224777e96b98af33e570cea9fcbf3e5ed9543b82d606b` |
| `test_x4s4_offline.py` | test | `9b838960afb50ab49111aeb996ff1dbacbbe575f1a33461d380194864593c97d` |

`confine.py` is removed; `x4s4io.py` replaces it. Byte-identical reuse is unchanged: `x4s3/run.py` (e7f90d76…), `runtime.sh`, `detach.sh`, `calibrate.py`, the frozen trainer, and `imitation/exit_r1/{rows,pack,emitter}.py`. Every owned file compiles under both `/usr/bin/python3` 3.8.10 (the fleet's system python, which runs the driver) and 3.12.

**Staging consequence.** The runtime inventory checked before every reporting launch now lists:
- `x4s4/supervise.py`, `x4s4io.py`, `studytree.py`, `qualify4.py`;
- `x4s3/run.py`, `runtime.sh`;
- `fit/run_fit.sh`, checked before every fit;
- `inputs/assets.npz`, checked by the diagnostic.

## Shared I/O layer (the coordinator's advice)

`x4s4io.py` vendors the tested primitives of the K4S shared layer safe_input r1 (blob c7e3fce7…, commit 4c9439de):
- the component-wise `O_DIRECTORY|O_NOFOLLOW` walk with a dev/ino re-check;
- the descriptor gate (regular, `st_nlink == 1`, cap, same inode after open);
- exact-size reads;
- strict JSON (no duplicate keys, no NaN or Infinity);
- exclusive creation;
- `run_checked` (absolute argv, exact environment, bounded output, group watchdog, rc checked before stdout is used).

It does not vendor the K4S name policy, which forbids a `games` path component and so cannot serve X4S-4. X4S-4 declares its own roots instead: job roles plus three exact report-root names.

It adds:
- atomic replacement over single-link files only;
- `O_APPEND|O_NOFOLLOW` appends;
- fd-based removal that never follows a link;
- fresh-tree copy (links copied as links);
- `(pgid, leader starttime)` process ownership with PID-only signalling;
- complete sealed-directory re-verification;
- a self-verifying git object walker: `--no-replace-objects`, `GIT_NO_REPLACE_OBJECTS`, a null graft file, no hooks, a scrubbed environment, and every commit, tree and blob hashed against its id.

An AST test checks that no owned script reads, writes, renames, removes, spawns or group-signals outside it. Only `/proc` pseudo-files are read directly.

## Sol r2 findings → fixes → fixtures

Each Sol r2 probe has a named fixture (`R2-F<n> probe`). Write-safety negatives assert that the outside sentinel is unchanged.

| # | Fix | Fixtures |
|---|---|---|
| R2-F1 | Every writer goes through x4s4io before its first mutation: the driver (events, state, logs, receipts, checkpoint copies, runtime overlay and its `plan.json`, calibration output, fit and cache directories), collection, labeling, O_W, supervisor, qualification, reducer, report, contention, diagnostic and audit. The collection entry validates `--out` before the inherited runner runs. | Sol's three probes, all rejected with the sentinel unchanged: the hard-linked `receipt.json.tmp` with `label.write_json`, a symlinked `driver/events.jsonl`, and a collection entry pointed outside (directory not created). Also replace/create/append through hard links and symlinks, read gates (symlink, hard link, ancestor, FIFO not opened), fd removal and the overlay copy. |
| R2-F2 | A reporting attempt settles only if the reaped child status (a durable `child_exit` event carrying the launch's `launch_id`) agrees with the supervisor receipt. Otherwise, including after a restart with unknown status, it needs an ACK bound to that exact attempt (`launch_id`, pid, starttime, receipt SHA, disposition, owner). The ACK is consumed and its anomaly archived, and the evidence is kept in `SETTLED.json`. Fits use the same mechanism. | Sol's probe (child 17 with a clean receipt) gives an anomaly, no SETTLED and no dispatch. An unknown status gives an anomaly; a wrong-attempt ACK gives a stale-ACK anomaly; the exact ACK settles and is consumed. Guard-stop and clean controls pass. Fit states: unknown, another launch's event, ACK-resolved once, known nonzero. |
| R2-F3 | Running fits are stopped when memory is below 24 GiB or unreadable, the GPU is unreadable or over 40 GB, or PSS exceeds **50 GiB (the frozen rule, restored)** or is unreadable. Fit admission requires the GPU to be readable with ≤ 8 GiB already used. Admission reserves the new workers (fit 10, phase 53, label/O_W workers+1). Label, O_W, acceptance and diagnostic run `studytree.monitor` live: STOP, hard stop, memory, PSI, own PSS, tree size and disk. On a breach the parent stops its own verified worker PIDs, so in-flight O_W work has a real hard-stop path, and a game finishing after the deadline is not counted. The supervisor applies the tree and disk caps itself. The diagnostic takes its lock inside the driver's exclusive `DISPATCH.lock` flock. All signals are PID-only on verified `(pgid, starttime)` members; the one exception is `run_checked`'s kill of the short helper session it created itself. | Sol's probes all stop: MemAvailable 0, GPU unreadable, 50,000 MiB admission. Also PSS over 50 GiB or unreadable, the reservation over 70, the diagnostic lock, the O_W game straddling the deadline, and the studytree monitor cases (dangling STOP, unreadable deadline). |
| R2-F4 | Contention schema v3 freezes every counted game's SHA, size and exact `st_mtime_ns`, the census/launch/exit/SETTLED SHAs and the `retired.json` SHA. The reducer re-derives all of it. Committed bytes come from the verified commit → tree → blob walk, and ancestry from the replace-free graph. The wording now says "before any outcome field is used". | Sol's mtime probe is refused, and the rebuild would change the exclusion from [0,1] to []. Sol's git-replace probe is refused even though plain git returns the substituted bytes. Also retired, census and phase-set changes, wrong SHA, uncommitted bytes, a commit off main, and writable or hard-linked receipts. |
| R2-F5 | Every packed source is re-verified completely (exact inventory and every file re-hashed). Packed bytes must equal the source arrays under pack.py's exact transforms. O sources must match plan, teacher and threads. O_W sources must match the selection identity rows. The acceptance smoke is exactly 2 games on the **qualification bank** (excluded from C′), with seals, replay identity and producer SHAs verified. | Sol's teacher-edit probe and Sol's Boolean-only acceptance receipt are both rejected. Also forged packed bytes (with the batch's own seal forged to match), a one-game or C′ acceptance, and a selection without identity rows. |
| R2-F6 | The seed audit reads only hash-verified git blobs of a pinned commit, selected from tree metadata by a reviewed rule. Outcome tokens anywhere in the path exclude a file, as does any content alias of an excluded file. Sealed trees contribute only listed declarations. `seed-sources.json` pins the commit (7f82af0d), the rule and the derived-list SHA: 7,711 sources and 35 sealed declarations, each listed by path and blob id. Omissions are counted per reason (`sealed` 2,681, `outcome_path` 812, `alias_of_excluded` 55, …). | Sol's hard-link alias and `t1/outcomes/plan.json` probes: never read (blob-request spy). A list differing from the reviewed one is refused. Literal-scan and range controls. |
| R2-F7 | Census values must be finite and admissible (PSI in [0,100], foreign CPU in [0,1024], reduced-concurrency flag exactly false) and in chronological order. Non-JSON rows, including NaN or Infinity, are bad. Readers return None for non-finite values. | Sol's all-NaN phase and Infinity, negative, overflowing, chronology and non-boolean flag cases are each bad in an uncapped phase. |
| R2-F8 | Games are projected (outcome fields dropped) to require a terminal flag, seed, arm, budget and student checkpoint. Smoke games are proof-authenticated. Parity receipts carry the exact game inventory and a `final` flag, and label admission re-derives the inventory. The C7b watch runs inside the collection supervisor. A collection runner without a live supervisor refuses to start, and exits 70 with a receipt if the supervisor dies. A failed parity needs an exception bound to a coordinator commit on origin/main whose COORDINATOR.md names the receipt SHA. | Sol's 16 non-terminal games fail. Sol's stale-parity probe (games added after the receipt) is refused. Also a non-final receipt, a forged smoke game, the watch pause and watch failure, monitor death, and a bare exception string refused while a commit-bound one is accepted. |
| R2-F9 | Gates carry the plan, receipt, selection, acceptance, O-gate and source SHAs. The report reads fixed job inputs and refuses unchained ones. The diagnostic takes inputs only from the verified holdout gate and the five staged students, records the holdout gate SHA, and reports a missing diagnostic explicitly as unavailable. | Rejected: an O_W gate not built on this O gate, a stale label plan, a diagnostic not run on the verified holdout. Also tested: the unavailable rendering, the diagnostic input refusals, and an out-of-root output. |
| R2-F10 | `plan.json` `ordering.interrupted` now states the fixed-N / largest-prefix / R5W-separation rule; the supervisor docstring says T+24 h. | Static checks. The suite asserts "not writable", never an exact mode, and runs under umask 022 and 077. |

**Owner decisions after Sol's opinion.**
1. The exception must now be bound to a coordinator commit on origin/main whose COORDINATOR.md names the receipt SHA; a bare ruling string is refused, per Sol's condition.
2. ACKs are attempt-bound and consumed (adopted).
3. The 15/30/15 tolerances are kept, now only after the validity and chronology checks.
4. Coverage is unchanged.
5. Replaced by the inventory-based audit (R2-F6).

The rest is a mapping and adds no new judgement.

## Offline test results (127x05, /dev/shm, nice 19, cores 0–3, no host contact)

`test_x4s4_offline.py` passes **81/81 under -O0, -O and -OO with umask 077**, and also under umask 022. Receipts (umask 077 runs):

| Mode | Receipt | SHA-256 |
|---|---|---|
| -O0 | [receipts/offline-tests-O0.jsonl](receipts/offline-tests-O0.jsonl) | `0e4b8110b2139d04a01633f730f01eb3e464c4c88913f990e17f54e384aa7af6` |
| -O | [receipts/offline-tests-O1.jsonl](receipts/offline-tests-O1.jsonl) | `c80c6b493ef6ce75065f9d309949423abcd554c7389f88b06677e7a793687222` |
| -OO | [receipts/offline-tests-O2.jsonl](receipts/offline-tests-O2.jsonl) | `6f5e1dd432b50f943168d7a0c21bf5b9adff9c26318f7d0f1bceb4ed54dc4811` |

The r3 suite was also run against the r2 scripts of f15691b5, with r3's `x4s4io.py` added so imports resolve. It recorded 30 cases, of which 14 failed ([receipts/r3-suite-vs-f15691b5.json](receipts/r3-suite-vs-f15691b5.json)). 11 of those are test-group exceptions on r2 interfaces, so this is weak evidence. The discriminating evidence is the named per-probe fixtures above.

**Not covered offline** (qualification §6 on 01, after a GO):
- real W scoring and the 125 native references;
- real command hashes and C8/root round trips;
- the emitter acceptance replay;
- RootTeacherStore compatibility;
- the GPU diagnostic;
- the real seed audit run against `seed-sources.json`.
