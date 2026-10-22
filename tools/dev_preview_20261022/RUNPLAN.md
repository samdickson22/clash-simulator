This package prepares one finite full-DEV diagnostic on idle 127x14. It is pending a fresh parent Sol high code and operational review. Preparation is not admission, host clearance, or permission to transport. No command below has been executed against a remote host.

The input is the frozen 119970-source-match, 119475-usable-match, 23498034-row snapshot. All 2332353 rows with split == 1 enter both metric passes and the scalar calibration fit. The unchanged Store loads arrays containing all splits; the DevOnly adapter refuses every non-DEV request before labels reach either metric function. There is no FINAL metric pass. The helper imports the exact reviewed featurizer, model, and train_bc from source 40ea0b503d94daba5486cb151f759b233664ba43, including the R7 dataset fix. It calls train_bc.evaluate, fit_gate_bias, then evaluate again. It never calls select_bc.main or admission. Calibration changes only the temporary in-memory gate intercept. Parameters have requires_grad=False; there is no optimizer, weight export, or calibration artifact.

The only result is unselected-dev-preview.json in a new private output directory. Raw and DEV-fitted diagnostic NLL, existing card/tile/value accuracy, gate ECE/Brier, value Brier, and Hog subgroup metrics retain their existing names and definitions. ECE exists only for all, so no Hog ECE or new joint accuracy is invented. Null subgroup values retain the reviewed code's meaning. No candidate is ranked, admitted, selected, promoted, or used for early stopping. No selection.json, anchor.pt, best file, or checkpoint is written.

Scope and authority

- Existing BC jobs on 01/02/08/13/15 remain untouched. Seed 2026102008 on 14 is failed, excluded, and must not restart. Its reported failure was the old wrapper's one-second sample_resources communicate TimeoutExpired after step 6500. This is not evidence proving OOM, NaN, or a data fault, and the failure has no eligible completion.
- This is a separate read-only DEV diagnostic under Sam's standing compute-max direction and the explicit candidate to evaluate BC checkpoints as they land. It consumes no replacement-seed experiment budget. It cannot alter schedules, seeds, quality gates, final selection, or the live M947 handoff.
- Final full-DEV selection across all three primaries follows the existing procedure only after they complete. The concrete inventory contains only finalized ep01 from primary seed 2026102002 on 01 and 2026102003 on 02. No best.pt or running writer path is eligible. Fresh parent checks at 23:34 show both primaries in epoch 2. Parent collection completed at 23:35:43Z. Do not collect duplicates. The helper accepts ep00 only if separately inventoried and reviewed; this plan schedules ep01 only.
- 16/17 remain HOLD. No 09/12 usage. R53 qualification/S soak and persistent-sampler work belong to other owners. No watcher, lease, sampler, main branch, or current job edits are part of this package.

Required evidence before execution

1. Parent fresh Sol high review of this exact commit and these commands, followed by parent operational review. No review was spawned by this implementation sub-agent.
2. Review inventory.frozen.json, already bound to the parent ep01 collection receipt. Confirm the two raw SHA/size pins and record its raw inventory SHA for --inventory-sha256. Copy it byte-for-byte to metadata/inventory.r1.json. inventory.template.json remains a refusal fixture with unset checkpoint pins; it is not the launch inventory. The helper allows one to four explicitly pinned ep00/ep01 candidates with matching external collection evidence; this concrete plan includes exactly the two ep01 files. No discovery/glob, later epoch, retry or duplicate collection is authorized.
3. Recheck the unchanged READY environment and store on 14 against the supplied maps. Runtime checks all 73 original source files, 6241 store files, 20303 environment files, full feature hash, manifest hash, checkpoint cfg and FP32 state, strict weight keys/shapes, n_params=8756421, seed/epoch, and completed epoch DEV metadata. Maps are themselves pinned in the helper. Environment must be Python 3.12 at the READY path with PYTHONHOME, Torch 2.7.1+cu118 and NumPy 2.3.5.
4. Establish fresh operational evidence that failed 14 has drained and remains excluded; verify all-clasher ownership accounting and available capacity. Old diagnostics and launch-handoff.json are historical evidence only. Verify live R37 watcher PID 1490887, boot/start identity from R5, source hash cf162c7a8d1beddd46bfed5b226ebe91ec4138af451f33a30ac950195bb61872, no pending stop/HALT/release, and its continuous owned-tree coverage. Never restart or edit it here.
5. Reopen /mpac/sdicks02/fleet-leases/127x14.json by pathname and validate the arbitrary-writer lease with the unchanged R37 reader. Deadline is 2026-10-25T07:53:00Z or any earlier active bound. Reclaim/refused must exit the entire owned tree within 30 minutes. No lock/inode assumption, lease rewrite, resume, or automatic retry is allowed. Default TERM termination is sufficient for this read-only job. Partial outputs are discarded from scientific use.

Resource plan

Use the unchanged R37 admit command, which rechecks the active lease and host before spawning, and the unchanged reviewed run_guarded.sh. Do not use supplemental_job.py or the old one-second BC sampler wrapper. No new controller or watcher is added, so no new wrapper stop/cleanup implementation needs qualification. R37 tracks the shell, timeout, Python, and all descendants and enforces all-clasher processes <=32, PSS <=32 GiB, CPUs 0..31, nice >=10, load <=90, MemAvailable >28 GiB, and physical GPU free >=8 GiB. The reviewed host guard adds a 29 GiB threshold at 20-second intervals; train_bc host_resource_check also runs during Store loading and each batch. R37 checks fractional load; run_guarded's integer load check alone is insufficient.

Reserve 8 processes, 30.5 GiB PSS and nominal 39 GiB GPU, leaving capacity for R37 and host accounting. Reserve admission requires MemAvailable - 30.5 >28 GiB and measured GPU free -39 >=8 GiB. Refuse if another clasher allocation makes any sum exceed its cap. Do not shrink the reservation to force admission. OMP/MKL/OpenBLAS/NumExpr threads=3, Torch intra-op=3 and inter-op=1; no DataLoader or batch-prefetch pool is created. Both evaluation and calibration use batch 512, below the reviewed defaults of 1024/2048. Historical full M DEV/calibration GPU peak was 32.0996 GiB. Preserve the R5 allocator fraction 37.5/47.98828125. At physical total about 47.5 GiB this allows about 37.15 GiB allocator plus 1.5 GiB context, leaving over 8 GiB. Physical headroom remains a measured R37 gate, not a prediction from the nominal allocator. An allocator refusal/OOM stops this diagnostic and creates no valid preview; it cannot trigger a retry or training change.

The outer timeout is six hours for the entire inventory, then TERM with a 60-second KILL bound. R37's earlier stop_by and reclaim bounds always take precedence. No success report is published until all included candidates finish. Each input checkpoint is opened read-only and checked for raw SHA/size, strict CPU load, and post-evaluation identity/hash consistency. A result from a terminated or failed process is not usable even if a report file was partly created.

Exact CPU verification, already run locally

```bash
CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 \
  /mpac/sdicks02/repos/clasher-pv1-rl-env271-20261022/bin/python -B \
  -m unittest discover -s tools/dev_preview_20261022 -v
```

These tests use tiny synthetic rows and CPU tensors. They check the real unchanged measurement functions, DEV-only requests, full-count refusal, malformed/incomplete/non-FP32 weights, feature/config/raw-hash mismatch, nonfinite data, file mutation, symlinks, changed source bytes, extra files, output exclusivity/privacy and no promotion output. They do not establish CUDA feasibility, current clearance, real checkpoint finalization, or elapsed time.

Proposed preparation after review, not executed

On 05, create a fresh package directory under /mpac/sdicks02/jobs/clasher/dev-preview-20261022. The implementation commit and metadata maps must arrive there through parent-approved transport. Preserve original source, READY env and dataset; no in-place patches. The helper deliberately refuses the adapter-patched R5 source tree. Stage only the original 73-file source archive in inputs/source-40ea. The source archive is 1177600 bytes with SHA dd3c26ff79de1f9acd39b8f27919451ac250e4ef04be82244303680331a55e8d. Source/store/env map SHA pins are in inventory.template.json; copies in the preparation metadata preserve their original bytes.

The parent has collected both ep01 files on 05. Do not reconnect to 01/02 or collect duplicates. Receipt /mpac/sdicks02/jobs/clasher/interim-dev-preview-inputs-20261022/ep01-parent-collection/receipt.json has raw SHA edbada61e1fb3b7c52193b965637c1d6c6b0436f214ae837863bf5c023eee175 and pins source/snapshot, source before/after SHA/size/inode/mtime, and local hashes. Both files are 35061136 bytes. Seed 2002 SHA is 984ec9b3ab9a7c36253ace0c990e71b0908e0473ad28c7941a7a3cb97beb261e; seed 2003 SHA is e83d92f378cebfb8adb4fbebf61bfdbb504e5b302fa6e6745c191f2917b71825. Their exact origins and fresh 14 destinations are in inventory.frozen.json. Runtime verifies a byte-identical receipt copy at metadata/parent-collection-receipt.json and checks the candidate mappings.

After parent fresh Sol high and operational review, the following exact two-file operation is proposed on 05. Parent must approve 05/14 CPU/transport accounting first. It reads the existing parent-collected files, never reconnects to 01/02, and creates each 14 leaf exclusively. Failed copies remain and refuse reuse. The bounded loop visits the two distinct candidates once; it has no retries. Capture stdout and command exit status in a new transport receipt.

```bash
python3 -B - <<'PY'
import hashlib, json, pathlib, shlex, subprocess
receipt=pathlib.Path('/mpac/sdicks02/jobs/clasher/interim-dev-preview-inputs-20261022/ep01-parent-collection/receipt.json')
assert hashlib.sha256(receipt.read_bytes()).hexdigest()=='edbada61e1fb3b7c52193b965637c1d6c6b0436f214ae837863bf5c023eee175'
for c in json.loads(receipt.read_text())['rows']:
    p=pathlib.Path(c['local_path']); raw=c['local_sha256']; size=35061136
    assert c['before']==c['after'] and c['before']['sha256']==raw and c['before']['size']==size
    def probe():
        st=p.stat(); h=hashlib.sha256(p.read_bytes()).hexdigest()
        assert st.st_size==size and h==raw
        return [st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,h]
    before=probe(); print(json.dumps(dict(phase='05-before',path=str(p),stat_sha=before)),flush=True)
    remote=pathlib.PurePosixPath('/mpac/sdicks02/jobs/clasher/dev-preview-20261022/inputs')/c['host']/('M-s%d'%c['seed'])/raw/'ep01.pt'
    subprocess.run(['ssh','127x14','umask 077; mkdir -p -- '+shlex.quote(str(remote.parent.parent))+' && mkdir -- '+shlex.quote(str(remote.parent))],check=True,timeout=30)
    subprocess.run(['scp',str(p),'127x14:'+shlex.quote(str(remote)+'.partial')],check=True,timeout=600)
    check='sha256sum -- '+shlex.quote(str(remote)+'.partial')+' && stat -c %s -- '+shlex.quote(str(remote)+'.partial')
    result=subprocess.check_output(['ssh','127x14',check],timeout=120).decode().splitlines()
    assert result[0].split()[0]==raw and int(result[1])==size and probe()==before
    print(json.dumps(dict(phase='14-verified',seed=c['seed'],probe=result,local_after=probe())),flush=True)
    # Publish exclusively; remove only the successful transfer partial, keeping failed copies.
    subprocess.run(['ssh','127x14','ln -- '+shlex.quote(str(remote)+'.partial')+' '+shlex.quote(str(remote))+' && rm -- '+shlex.quote(str(remote)+'.partial')],check=True,timeout=30)
PY
```

The existing 05 files and parent receipt remain untouched. Copy inventory.frozen.json byte-for-byte to metadata/inventory.r1.json, with its independently recorded raw SHA passed below. A failed check stops the work without recopying a primary file. A partial on 14 is retained and cannot be admitted; no retry is authorized.

On 14 after parent-approved staging, with package at $DEV/code and immutable map copies in $DEV/metadata, prepare original source from the pinned archive, not from the adapter tree. The parent must transport source-40ea0b503.tar into $DEV/inputs exclusively. This command is proposed only. Parent must include setup and transport in the 14 all-clasher accounting and run source extraction under an existing R37 CPU admission. It extracts only the pinned regular members, using exclusive creates; it does not overwrite anything.

```bash
DEV=/mpac/sdicks02/jobs/clasher/dev-preview-20261022
export DEV
python3 -B - <<'PY'
import hashlib, json, os, pathlib, tarfile
root=pathlib.Path(os.environ['DEV']); archive=root/'inputs/source-40ea0b503.tar'
assert archive.stat().st_size==1177600
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='dd3c26ff79de1f9acd39b8f27919451ac250e4ef04be82244303680331a55e8d'
mp=root/'metadata/source-map.json'
assert hashlib.sha256(mp.read_bytes()).hexdigest()=='dd1f0b08b67f655ba1ab94340f7db5b5efc0e91bfe55f856e4a7b0d28dd4c89a'
mapping=json.loads(mp.read_text()); dest=root/'inputs/source-40ea'; dest.mkdir(mode=0o700)
with tarfile.open(archive) as t:
    for name,pin in mapping.items():
        rel=pathlib.PurePosixPath(name); assert not rel.is_absolute() and '..' not in rel.parts
        m=t.getmember(name); assert m.isfile()
        b=t.extractfile(m).read(); assert len(b)==pin['bytes'] and hashlib.sha256(b).hexdigest()==pin['sha256']
        p=dest/name; p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f: f.write(b)
        p.chmod(0o400)
PY
```

Exact proposed 14 GPU admission command, never executed by this implementation

Frozen inventory raw SHA is 3dcf13b61a57ed301f1e7d2f9a825b299a5731eb60f42466fbd652d4438d916e. Use the exact fresh output basename below for the one reviewed finite evaluation. DEV_INVENTORY_SHA256 must be the independently recorded raw inventory SHA, not computed from an unreviewed template. Verify the implementation commit/package hash independently as well. Creating code/metadata/inputs/outputs directories and transferring files is parent work after review; the helper itself only creates the last output directory exclusively.

```bash
set -euo pipefail
DEV=/mpac/sdicks02/jobs/clasher/dev-preview-20261022
READY=/mpac/sdicks02/repos/clasher-bc-supplemental-40ea-20261022
SUP=/mpac/sdicks02/repos/clasher-pv1-lease-1316-995579193e/lease_supervisor.py
: "${DEV_INVENTORY_SHA256:?external inventory SHA required}"
export PYTHONHOME="$READY/env/python"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 GPU=0
export OMP_NUM_THREADS=3 MKL_NUM_THREADS=3 OPENBLAS_NUM_THREADS=3 NUMEXPR_NUM_THREADS=3
export NUMPY_MADVISE_HUGEPAGE=0 PV1_HOST_MIN_AVAILABLE_GIB=29 PV1_HOST_MAX_LOAD=90
unset PYTHONPATH
printf '%s  %s\n' cf162c7a8d1beddd46bfed5b226ebe91ec4138af451f33a30ac950195bb61872 "$SUP" | sha256sum --check --strict -
printf '%s  %s\n' 8a42d07709d690a00fd96c73b8eca05363f7210e7752e5beb8b728eed88cd499 "$DEV/inputs/source-40ea/bot/pretrain_v1/run_guarded.sh" | sha256sum --check --strict -
# Preexisting outputs root must be private; the output leaf must not exist.
test -d "$DEV/outputs"
test ! -e "$DEV/outputs/primary-ep01-r1"
test ! -e "$DEV/guard-r1.log"
test ! -e "$DEV/guard-r1.log.guard"
"$READY/env/python/bin/python3.12" -B "$SUP" admit \
  --name dev-preview-primary-ep01-r1 --workers 8 --pss-gb 30.5 --gpu-gb 39 \
  --grace 60 --cwd "$DEV" -- \
  /usr/bin/taskset -c 0-31 /bin/bash "$DEV/inputs/source-40ea/bot/pretrain_v1/run_guarded.sh" \
  "$DEV/guard-r1.log" -- \
  /usr/bin/timeout --signal=TERM --kill-after=60s 6h \
  "$READY/env/python/bin/python3.12" -B "$DEV/code/preview.py" \
  --inventory "$DEV/metadata/inventory.r1.json" --inventory-sha256 "$DEV_INVENTORY_SHA256" \
  --source-map "$DEV/metadata/source-map.json" --store-map "$DEV/metadata/store-map.json" \
  --env-map "$DEV/metadata/env-map.json" --out "$DEV/outputs/primary-ep01-r1"
```

R37 covers the guard, timeout and evaluator as one owned tree. The command verifies run_guarded's original SHA before invoking the shell; the helper verifies every original source file again. R37 grace 60 gives an earlier bound than 30 minutes, with no checkpoint-save obligation. Since R37 admission returns after spawn, a zero admit exit is not an evaluation success. Parent completion evidence must include the wrapper exit status, no timeout/reclaim/resource breach, all candidate hashes unchanged, exact DEV count and inventory SHA, complete=true with selected=false, finite metrics, and verified full tree drain. Do not restart R37, release the host lease, or change another job to obtain this evidence. Do not watch/poll or launch from this implementation stage.

Remaining pins and limits

The two ep01 pins are frozen in inventory.frozen.json from the parent receipt. The implementation package hash and current operational admission evidence still require parent review. CUDA memory/time behavior is supported only by the prior measurement and conservative batch bounds, not a new GPU test. Parent review and admission remain required. This implementation provides no GO decision.
