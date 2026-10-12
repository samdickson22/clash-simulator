# X4S-4 scripts, r2 for Sol re-review (exploration, NEVER ADOPTABLE)

The design is frozen at PLAN r3 87809ae0. The r1 script set was 13fb31d0, reviewed by Sol r1 (REQUEST_CHANGES, 18 findings). r2 fixes all 18 findings. Nothing has been run on any host. Everything below was done offline on 127x05, using synthetic fixtures under /dev/shm.

## Index

| File | Kind | SHA-256 |
|---|---|---|
| `run_collect.py` | new | `f945ac6c266267d52689df9cd0b3a658705740a513b86866e16d3786dc64780b` |
| `collect.py` | new | `3ed143df1ec7aaddf9b86ccdd30f27e0e88f5f83db576f715afa508974374658` |
| `label.py` | new | `a0703970802dc14f6bcd54884da9f9fc3a62401351d01d6e862b31796cd2856d` |
| `collect_w.py` | new | `62764d7baeac45f167aa32a290118e408270ed10fe7db8f19a612e62f2d69773` |
| `verify_onpolicy.py` | new | `5cdf8673c49abae28052df6398a816b151855faa1759a188658eb89a5be32f6a` |
| `diagnose.py` | new | `e0d3977cec756f501938d694ac623e9447d0ddfa05364006f40d5a49478c4759` |
| `contention.py` | new | `c7c90c18dd384227f47b2932569f109c3d01f2f22e6b513072b2e12489053780` |
| `qualify4.py` | new | `2798f6b8df8fe97280f1a67548054b2816ceb4543a91a622c415fe05aea40d0c` |
| `confine.py` | **new in r2** (F10) | `6a1316623b9826dff3242465e09dfcc77ad7de57b6c441cf679ab19af8089674` |
| `studytree.py` | **new in r2** (F9) | `76f7da1b6764d382edaa2146199f3cf65a698810ec969775a4c3425cfcb0d171` |
| `supervise.py` | modified (from x4s3) | `54626791f990c12e14e8c144387ac46352625a5c8a12a827246f8696e3b39be2` |
| `run_fit.sh` | modified (from x4s3) | `0dda76798d83b508274a42c771105a64842b7d7f2efd23091dd8e38cfeb35fa0` |
| `driver.py` | modified (from x4s3) | `8d6fe0c483df207ada3e168a429a06d6e18fd5555a1e599da4ce048e09feaf23` |
| `reduce.py` | modified (from x4s3) | `0e0e817b4d13136ece8ac1e97191746f2839fb76ae7509220cea98857a13d8ac` |
| `write_report.py` | modified (from x4s3) | `30a2e7dee5cc49195b04c0790193e935cc8164e29587252a2229a856122a66a3` |
| `audit_seeds.py` | modified (from x4s3) | `bda09cf62c48261f672ce6a9ebeecd53bdcdac38b2b8d8c1a2eb5629ced40b2a` |
| `plan.json` | config | `0d72c67a2f9b2d7f79cf1dfd453c70c90ce4564ac2d65f8ff2b6995befbf963c` |
| `plan-collect.json` | config | `57f6a1427a584a607fe1e8da79e14340736f90bbf909795a8f125ffd1b9fedea` |
| `plan-qual-capture.json` | config | `450522158dccbe73216c3cc2b86054cdde4fbe62f4d55dafd0e75c87470461d4` |
| `idx-qual.json` | config | `4587c7edd4a17da602e224777e96b98af33e570cea9fcbf3e5ed9543b82d606b` |
| `idx-smoke.json` | config | `4587c7edd4a17da602e224777e96b98af33e570cea9fcbf3e5ed9543b82d606b` |
| `test_x4s4_offline.py` | test | `0e48a0940d61420fdcd1d9a498bd51c79813fd5fcc0116340f90373d2f9f9193` |

Byte-identical reuse is unchanged from r1: `x4s3/run.py` (SHA e7f90d76…, asserted by the suite), `runtime.sh`, `detach.sh`, `calibrate.py`, the frozen R3 trainer, and `imitation/exit_r1/{rows,pack,emitter}.py`.

**Correction to r1 (F11).** r1 claimed that no `assert` remained outside `run_collect.py`. That was wrong: five inherited asserts remained in `audit_seeds.py` and `reduce.py`. In r2, an AST scan in the suite enforces **zero** `assert` statements in every X4S-4-owned script. `run_collect.py` keeps the asserts of the byte-copied `x4s3/run.py`.

## Findings → fixes → fixtures

Each Sol probe has a fixture named "F<n> probe" in `test_x4s4_offline.py`. Each negative is paired with a positive control.

| # | Fix | Fixture(s) |
|---|---|---|
| F1 | `run_game` is never replaced. `run_collect.py` adds two explicit hooks: `CAPTURE` (after `apply_lateness`) and `CAPTURE_END` (after the game JSON is durable, before the block proof). `install()` only sets the two hooks. | The exact `inference_check` AST from `run_collect.py`, with its asserts made explicit, passes after `collect.install()`; the r1 wrapper fails it. A diff test shows `run_collect.py` = `x4s3/run.py` + 9 hook lines, none removed. |
| F2 | Eligibility uses the decision's **input** transaction `p.core.pending`, which run.py sets before candidates, not the post-submit `ch.pending`. | A play whose own command sits in `ch.pending` is eligible, as is WAIT; a non-empty input transaction is rejected. The per-game capture file contains a hit play and a hit WAIT. |
| F3 | The fair check rebuilds the payload with `kw['b']` **replaced**; the battle is read only via `kw['b']`. Coverage counters cover perturbed decisions overall and early in the game (tick < 600). Qualification requires ≥ 1 perturbed decision per game and ≥ 50% perturbed early checks. | The **real** `collect.payload` (with stubbed engine resources) is byte-identical under the permutation, with cards actually moved. Negative controls that read the hidden hand, hidden cycle or future battle RNG through `kw['b']` are each detected. Qualification fails when a permutation moves no card. |
| F4 | `reduce.py verify_freeze()` runs before any game is opened. The receipt must be regular, single-link and non-writable. Its SHA must equal `--contention-sha`, and the same bytes must sit at `--freeze-commit` on origin/main. Schema must be `x4s4.contention.v2`. The phase set and per-phase inventory (census, launch, exit, SETTLED, block and game listings) must re-verify. | These are all refused with zero games read: Sol's writable minimal receipt, no receipt, wrong SHA, uncommitted bytes, a commit off origin/main, a writable receipt, a hard-linked receipt, a changed census and an extra phase. Real git fixtures are used. |
| F5 | Driver: an exit is retired or resumed only for a permitted guard reason or an owner ACK; anything else is an anomaly that stops dispatch. Exit codes are durable `child_exit` events. A fit is done only after a clean return **and** a known zero exit. `run_fit.sh` uses checked command substitution. `label.finish()` and `collect_w` exit 1 on failure. Labeling tolerates only the declared drops. | An rc-17, reason-less exit retires nothing and launches nothing (memory_guard and ACK controls). Fit states are tested for unknown, nonzero, zero (from events) and masked exits. A producer that prints a batch and then exits 17 aborts `run_fit.sh`. A memory_guard label result fails and exits 1. An undeclared scorer exception propagates. |
| F6 | The O_W gate requires selection == `range(n)`, per-game roots derived from the packed rows, a strict minimal prefix, seeds `C′+g`, a passing acceptance smoke and an exact last-game root count. On resume, `collect_w` re-verifies the seal and the realized identity. | Rejected: Sol's 45-of-60 case, a short prefix, sources `[0,1,2,4]`, a non-range selection, a wrong seed, a failed acceptance and a wrong last-game claim. Resume: a wrong seed, wrong opponent, broken seal or unsealed directory is refused. |
| F7 | Census = host busy ticks minus X4S-4 tree ticks, with own processes keyed by `(pid, starttime)`. The baseline is taken before the child starts, and a final row is written. None, gaps (15/30/15 s), an empty census and a missing exit or SETTLED all count as bad or refused. | Scripted `/proc`: a new foreign process with 1,000 ticks is counted. PSI, unreadable PSI, foreign load, unreadable foreign load, yield and a gap **each** flag exactly their own game. Capped, empty-census and tail-gap cases are covered, as is refusal of unsettled phases. |
| F8 | Reporting launches `reports/explore/x4s4/supervise.py`. `supervise.py`, `confine.py`, `x4s3/run.py` and `runtime.sh` in the runtime copy must match `RUNTIME-INVENTORY.json`. | The command names the X4S-4 supervisor; a tampered runtime file is refused with an anomaly. |
| F9 | Admission fails closed on unreadable PSI, memory, disk or GPU, PSI > 10, > 70 tree processes (`studytree.py`) and > 100 GB. Fit admission uses the same gate, and the fit PSS cap is 60 GiB. The labeler and O_W register their process groups and stop at the tree cap or hard stop. A diagnostic lock excludes fits and reporting. STOP uses lexists everywhere. Only a `wall_over_2x` fit auto-resumes, and only after the O_W gate. | Every admission probe is covered, plus the lock, a dangling STOP symlink, the resume rule (divergence never resumes), the studytree caps, the labeler's tree_cap and diagnose's refusal while a group is live. |
| F10 | `confine.writable()`/`mkdirs()` guard every writer: absolute canonical path, under the job root (or the report directory for RESULTS.md and seed-audit.json), allowed role, no symlink ancestor or target. Labeling `rmtree` touches only its own confined temp directory. | Confine negatives, plus outside-root refusals for capture, label plan, supervisor `--job`/`--phase`, reducer `--out`, `write_report --out` and qualification `--out`. |
| F11 | Explicit raises everywhere (`AuditError`, `SystemExit`). | Identical bank bases, an intersecting prior range and a policy-cache mismatch all fail **in each optimization mode**; the AST no-assert scan passes. |
| F12 | `qualify4 hashes` requires 16/16 cases with terminal SHA-matched proofs and the 1,000 s capture-all config. `roundtrip` checks **every** smoke capture across 0–7 × both arms. `parity` requires both arms; `--watch` writes PARITY-PAUSE and creates STOP. `label.py plan` requires a passing parity receipt or an explicit `PARITY-EXCEPTION` bound to its SHA. Collection configs are full staged runtime configs (student R3a, policy v1). | Failures on 15/16 cases, an unmoved permutation and a hash difference. 32/32 captures pass; a missing arm, digest error or bad C8 hash fails. One arm fails while both pass; the watcher pauses. A failed parity is refused, and the exception is accepted. |
| F13 | The plan authenticates block proofs (game SHA), binds the filename, summary and capture identity, and enforces the bank-C allocation (also at launch, in `collect.check_allocation`) and public/pending parity. A run requires the capture SHA to equal the plan entry. Resume checks the plan SHA, keep SHA, teacher and threads. Verify binds every packed source to its plan entry and receipt. | Refusals: stale block, seed mismatch, parity false, pending, out-of-allocation, launch allocation, stale capture, a resume with a different plan, a receipt/packed game-set mismatch, source identity drift and a stale plan. |
| F14 | Per-arm averaged primary; explicit no-estimate contention view; R5W prefix counts; composition, dedup and 600-tick tables; O_W single-candidate share; fixed control-data disclosures; decision-table row with its harmful/attribution follow-up. The report is confined. | A by-hand check of −37.5 / 0 / −18.75 pp; the per-arm mean equals the pooled value; render tests check every required section and the empty view. |
| F15 | `diagnose.CEAccumulator` keeps global numerators and denominators of the frozen objective and a per-root listwise CE. Each batch is cross-checked against the frozen `teacher_loss`. | Batch-size/order invariance over 1, 7, 64 and all; equality with the frozen formula; Sol's counterexample gives C (row-mean gives C/2). |
| F16 | A pre-read admissibility filter. Inside the sealed trees (T1, K4S-confirm, the Mac E4 session, the live loop, `*tiers*`), only seed declarations are opened; outcome-named files and symlinks are never opened. | Spy on `read_bytes`: sealed outcome files and a symlink alias are never opened. Controls: the same literal is found in an ordinary file and in a sealed PREREG declaration. |
| F17 | `plan.json` now describes r3: the ABBA order, no futility stop, host-wide contention, the new sub-labels and input pending. The driver docstring's inherited X4S-3 text is replaced. | A test checks plan.json against the driver constants and checks both collection configs. |
| F18 | The suite was rewritten as above: 76 cases. | The r2 suite run against the 13fb31d0 scripts fails 21 of the 31 cases that execute there, including the F1/F2/F3/F5/F11/F17 probes. ([receipts/r2-suite-vs-13fb31d0.json](receipts/r2-suite-vs-13fb31d0.json)) |

## Offline test results (127x05, /dev/shm, nice 19, cores 0–3, no host contact)

`test_x4s4_offline.py` passed **76/76 under -O0, -O and -OO** (exit 0 in each mode). Receipts:

| Mode | Receipt | SHA-256 |
|---|---|---|
| -O0 | [receipts/offline-tests-O0.jsonl](receipts/offline-tests-O0.jsonl) | `a7ba94a5425c99648e3fa94958a0c73fe0fb8be6989abba6ea7732890b2c10da` |
| -O | [receipts/offline-tests-O1.jsonl](receipts/offline-tests-O1.jsonl) | `ab9e6c51114920481630e0e172679d7746e9e5733005c6b8a7e0c158e52ccf81` |
| -OO | [receipts/offline-tests-O2.jsonl](receipts/offline-tests-O2.jsonl) | `1c22f827589e459680c60e7b5cac5efb15b9aac813bdecfc1d12e57417d6bcb6` |

**Environment.** Python 3.12.12 venv (`/dev/shm/x4s4-venv`), numpy 2.5.3, no torch. The real `BattleState`, `PlayerState`, `DiscreteTileActionSpace`, `seal`, `pack` and git are used; engine resources are stubbed for the real capture payload.

**Not covered offline** (qualification §6 on 01, after a GO): real W scoring and the 125 frozen references, real command-hash non-perturbation, real C8/root round trips, the emitter acceptance replay, RootTeacherStore compatibility, GPU diagnostic execution and the real repo-wide seed audit.
