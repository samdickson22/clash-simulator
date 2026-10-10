# E4-v3 implementation draft

Implements the SHA-frozen r3 addendum (PREREG freeze `cc6410b2`), listed in
`spec-pins.json`. Independent implementation review is pending. No Mac work has
been performed. This package measures fixed public fixtures and admitted TRAIN
replay pixels; it has no client input, actuator, login, ladder or game launcher.
On Mac, any score mismatch outside the registered 1e-12 relative tolerance fails closed
for **all** tiers. Discrete native actions/candidates/root, belief ledger,
samples and RNG must match exactly. Near-exact arithmetic is disclosed. Linux
fleet references require EXACT with zero native or posterior discrepancy.

`measure_tiers.py` performs D0–D9, including full decisions under perception load,
conservative fleet-relative ratios and p10/p25/full state distribution, direct
200 ms cutoff/fallback/no-complete-play checks, CPU/MPS R3a agreement and cold/warm
forward timing, per-core P/E idle census, deadline-relative GC traces and eligible
freeze variants. CPU is the initial S speed/deadline baseline. If D6 admits MPS,
the complete loaded S speed/deadline corpus is measured again on that backend;
both baselines remain in raw receipts. Exit zero means measurement completed,
not that any tier qualifies. Every output directory is exclusive and SHA-sealed,
including failed runs. Formal E4/T9 and activation remain outside this package.

## Inputs and staging

Use a fresh frozen runtime containing the qualified S1/K2 sources and Rust/data
files, the frozen v1/R3a/calibration artifacts, the native golden125 states,
belief references, the 2,000-state student set, each tier's own 300-state corpus,
loaded three-repeat references from each reporting host and deadline references
at 200/160 ms. [FLEET-INPUT-SCHEMA.md](FLEET-INPUT-SCHEMA.md) gives the row contract
and fleet-reference CLI; [FLEET-END-CONTRACT.md](FLEET-END-CONTRACT.md) specifies
Amendment 1's committed evidence and ordered-attempt descriptor. Historical
fixtures serve native/belief golden checks; only Linux smoke may use them as timing corpora.
Mac rows require actual reserved packets, pre-poll D1/public history and belief
snapshots, captured RNGs, pending reservations and public opponent elixir. The
T1 ba3dc8b0 row allowlist is exact: 20 fields, `strata` has exactly three fields,
and `belief_resume` is rejected. Fleet mode derives every occupied reporting
slot from the pinned plan and uses no fleet perception worker. Mechanical
`--pool-fleet-references` pools raw host × repeat walls, applies the ±5% host rule,
and pools deadline counts. Amendment 1 binds END placement and conservative
committed-posterior replay. The END pool requires every counted reporting host
and fails on an outlier rather than dropping counted hosts. The same frozen T1
guard applies during references, including all eight final frozen dependencies,
OP-1/OP-2/OP-3/OP-4, immediate console stops and memory rules. Raw stopped END
phases retain valid counted blocks through the committed blind ledger and
counted inventory. Fixed 50-state work-block SSH budgets cannot be hidden in a
whole-run average; >0.5% flagged blocks fail reference qualification.
A6's real fleet-mode smoke is assigned to127x01 at T1 END (projected Oct11
02–06Z), awaiting T1's actual opening and reviewed300 bundle. The offline
stager and [A6-END-RUNBOOK.md](A6-END-RUNBOOK.md) are prepared. END references
remain unconfirmed until independent code/result review. Fleet mode never uses
the nice19 Linux dry-run load path.

`prepare_bundle.py` copies only explicit approved artifacts, verifies policy/source
pins, checks TRAIN membership before media access and generates `tiers-pins.json`
plus its SHA. Mac staging requires a reviewed `registration.json` packet containing
`sets`, pinned `corpus_receipt`, actual `packet_schedule` tick/timestamps/offsets/opportunity flags, and pooled
`fleet_reference` metadata with three repeats at nice10, physical core IDs,
`reporting_load_profile=true`, reporting `hosts` and per-host receipt comparisons
within 5% of the pooled reference and `pooling=raw-host-times-repeat-v1`. Input references are `golden.json`,
`belief-reference.json`, `student-reference.json`, `speed-reference.json`,
`deadline-reference.json`. The owner must seal all source reference receipts and
pooling evidence into the reviewed registration packet. No outcome data belongs
in that packet.
The registration and `tiers-summary.json` retain each host's signed
`reference_to_reporting_mean`, with `amendment_1=true` and no excluded hosts.

The JSON load configuration uses `kind=v3-body-hud-only`, `target_fps=20`,
`config={body:ABS_PATH,hud:ABS_PATH,geometry:ABS_PATH,device:mps}`, `split:ABS_PATH`
and `matches:[ABS_TRAIN_MATCH_DIR]`. V4 additionally needs its qualified checkpoint,
authenticated selection and owner launcher. V3 outputs all carry
`PROVISIONAL-LOAD`. Perception uses inherited body/HUD inference on real pixels;
Internet/client socket connections and automatic dependency downloads are blocked.

Topology JSON must partition all Mach CPU indices into `P` and `E` and contain
reviewed `mapping_evidence`; counts must match `hw.perflevel0/1.logicalcpu`.
Do not infer P/E index ordering from counts alone. Sam/coordinator supplies that
mapping, admitted TRAIN load and the session lock. Emulator evidence comes only
from `ps`; the runner never contacts an emulator.

Dependencies must be installed before the authorized session: native arm64 Python
3.12+, NumPy/Torch, inherited qualified perception dependencies (Ultralytics,
OpenCV, body checkpoint's dill, HUD and their dependencies) and the frozen student
source. Use the inherited approved lock/environment, record its package lock,
and keep BLAS/Torch/OpenCV at one thread. Linux smoke's isolated dependency lock is
included with its receipt; it does not establish Mac dependency qualification.

## Exact Mac session command

Run **only in a later separately authorized Mac session**, on the fresh approved
runtime. Set these absolute paths and the independently approved deterministic
bundle SHA before executing. `E4_STATES` and `E4_REFERENCE_PACKET` are the reviewed
production inputs, not the Linux smoke inputs. Output/build/bundle paths must not
already exist. `E4_LOCK` is the coordinator's existing session lease file.

```bash
export E4_RUNTIME=/absolute/fresh-frozen-runtime
export E4_BUNDLE=/absolute/new-tiers-bundle
export E4_REFERENCE_PACKET=/absolute/reviewed-pooled-reference-packet
export E4_STATES=/absolute/reviewed-public-states.pkl
export E4_R3A=/absolute/R3a.pt
export E4_CALIBRATION=/absolute/R3a-calibration.json
export E4_V1=/absolute/v1.pt
export E4_LOAD_CONFIG=/absolute/approved-train-mps-load.json
export E4_TOPOLOGY=/absolute/reviewed-mach-core-map.json
export E4_BUILD=/absolute/new-arm64-tier-build
export E4_OUTPUT=/absolute/new-tier-measurement
export E4_LOCK=/absolute/coordinator-session.lock
export E4_MANIFEST_SHA=INDEPENDENTLY_APPROVED_TIERS_PINS_SHA256
export PYO3_PYTHON=/absolute/native-arm64-python3.12
export SAM_AUTHORIZED_REPLAY=yes
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
nice -n 10 "$PYO3_PYTHON" -B - <<'PY'
import fcntl, os, pathlib, platform, subprocess, sys, sysconfig
assert platform.system() == 'Darwin' and platform.machine() == 'arm64'
assert os.environ['SAM_AUTHORIZED_REPLAY'] == 'yes'
e = os.environ
script = pathlib.Path(e['E4_RUNTIME']) / 'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3'
lock = open(e['E4_LOCK'], 'r+')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)  # held BEFORE staging
native = pathlib.Path(e['E4_BUILD']) / ('clasher_core' + sysconfig.get_config_var('EXT_SUFFIX'))
subprocess.run([sys.executable, '-B', str(script/'prepare_bundle.py'),
    '--runtime-root', e['E4_RUNTIME'], '--native', str(native),
    '--states', e['E4_STATES'], '--reference-packet', e['E4_REFERENCE_PACKET'],
    '--student', e['E4_R3A'], '--calibration', e['E4_CALIBRATION'], '--v1', e['E4_V1'],
    '--load-config', e['E4_LOAD_CONFIG'], '--topology', e['E4_TOPOLOGY'],
    '--output', e['E4_BUNDLE']], check=True)
subprocess.run(['bash', str(script/'build_tiers.sh'), e['E4_RUNTIME'],
    e['E4_BUNDLE'], e['E4_MANIFEST_SHA'], e['E4_BUILD']], check=True)
subprocess.run([sys.executable, '-B', str(script/'measure_tiers.py'),
    '--sam-authorized-replay', '--bundle', e['E4_BUNDLE'], '--runtime-root', e['E4_RUNTIME'],
    '--native', str(native), '--manifest-sha256', e['E4_MANIFEST_SHA'],
    '--coordinator-lock', e['E4_LOCK'], '--coordinator-lock-fd', str(lock.fileno()),
    '--output', e['E4_OUTPUT']], pass_fds=(lock.fileno(),), check=True)
PY
```

The inherited locked descriptor keeps the **same exclusive lock** held from staging
through build, five-minute averaged quiescence census, measurement and cleanup.
The existing B6 runner is a separate session/program; its authorization and gates
are inherited, and this command changes none of its scripts or production defaults.

## Linux smoke and tests

```
python3 -B -m unittest discover -s reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/tests -q
```

The receipt uses 127x05, nice19, **one physical search CPU, one replay CPU, one
background corpus CPU**. K2/K4 still execute their actual 2/4 native worker
threads, oversubscribed within the search CPU. The separately measured reference
uses that identical profile. This tests fleet-relative reduction; it does not
estimate qualified fleet throughput. No work remains on 127x03.

Prepare with `prepare_bundle.py --linux-dry-run` and the approved historical
`states-ready.pkl`, `symmetric-screen-samples.json`, pinned artifacts and a real
TRAIN CPU load. Then create a Linux `build-tiers.json` beside the copied qualified
native with `native_sha256` and `source_manifest_sha256` bound to that bundle.
Run at nice19 with one-thread BLAS settings:

```
nice -n 19 /absolute/isolated-python -B /absolute/e4v3/measure_tiers.py \
  --linux-dry-run --bundle /absolute/prepared-linux-bundle \
  --runtime-root /absolute/frozen-runtime --native /absolute/native/clasher_core.abi3.so \
  --search-cpus 50 --load-cpu 51 --background-cpus 52 \
  --manifest-sha256 PREPARED_BUNDLE_SHA256 --output /absolute/new-linux-receipt
```

Linux smoke executes all D steps with reduced counts: golden125 remains full;
agreement/forward/speed/packet cohorts are 32 unique states, unloaded is16,
thermal/capacity windows are2/3 seconds, minimum loaded duration is2 seconds.
Synthetic 2 Hz packet cadence is labelled and cannot satisfy the Mac corpus gate.
MPS is explicitly unavailable. Failures of CPU replay FPS or timing gates remain
visible; they are never replaced with simulated successes. D8 remains gated by
1–3 and5 as required by r3.

`classify_failure.py --receipts RUN --output NEW_CLASSIFICATION` verifies the sealed
raw receipt and classifies only preregistered technical failure candidates. It
never authorizes a repeat. Retain failed runs; use fresh directories for repeats.

Snapshot cloning/admission occurs before recorded packet entry; the current D1
advance, posterior update/sample and complete search remain inside the timer.
The committed-belief-copy capture contract records suspended-transaction flags
and Amendment 1 ratifies its conservative deadline replay. K0c top-8
exceptions use Linux log probabilities. A fallback sample discrepancy is
fail-closed unless the reference supplies an independently certified near-tie
`sample_margin`; the frozen text does not specify how to certify that margin, so
this remains an explicit review point.

## Draft Linux evidence

[Revised Linux05 handoff](receipts/linux05-20261010-r2/handoff.json) and its
[SHA inventory](receipts/linux05-20261010-r2/handoff-manifest.json) seal the full
measurement and separately measured loaded three-repeat calibration. The
pipeline source is `aefc607a`; subsequent fleet-only admission, GC/census and
pooling changes leave the timed `tier_backend.py` decision work unchanged;
summary metadata and fleet exactness admission have since changed. The receipt
retains precise source hashes. No fleet-reference host
or Mac was run by this worker; 03 remains vacated.

At nice19 on physical CPUs50/51/52, native golden125×four configurations and
belief/posterior/ledger/sample/RNG125×ON/OFF passed EXACT; R3a CPU agreement was
32/32. TRAIN perception measured 19.91–20.50 FPS across loaded tier windows.
All four tiers passed the **Linux smoke** deadline/GC gates at the conservative
0.8 cell. Median ratios were K0c0.9826/S0.9829/K2 0.9800/K4 0.9836;
conservative ratios were 0.9506/0.8577/0.9400/0.9272. Full distributions, p10/p25,
raw deadline/census/GC rows and retained default/frozen GC runs are archived.
MPS is unavailable on Linux; this is reduced-count historical-fixture smoke,
not reporting-corpus or Mac feasibility evidence. The earlier
[receipt](receipts/linux05-20261010-r1/handoff.json) identifies its older source.

`python3 -B -m unittest discover -s reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/tests -q`
passes 64 tests, including committed stopped-phase END evidence, full-occupancy clocks,
ordered technical attempts, END outlier refusal, sealed CLI pooling, strict row
admission and global native-score failure even with an allowed policy exception.
[Review response](REVIEW-RESPONSE.md) maps the T1 findings. Amendment 1 code and
A6 pending evidence are tracked in [REVIEW-A1-A6-RESPONSE.md](REVIEW-A1-A6-RESPONSE.md).
Independent review and separate Mac authorization remain outstanding.
