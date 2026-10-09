#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1
host=$(hostname -s)
mkdir -p "$job/inputs" "$job/cache" "$job/tmp"
export XDG_CACHE_HOME=$job/cache PIP_CACHE_DIR=$job/cache/pip TMPDIR=$job/tmp
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
case $host in
  127x01) gpu=/mpac/sdicks02/envs/clasher-gpu/bin/python
    [[ -L "$job/human" ]] || ln -s /mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/imitation/data/v2-store-v1 "$job/human" ;;
  127x04) gpu=/mpac/sdicks02/envs/clasher-gpu/bin/python
    [[ -L "$job/human" ]] || ln -s /mpac/sdicks02/repos/clasher-t11-home-v1/data/v2-store-v1 "$job/human" ;;
  127x09) gpu=/mpac/sdicks02/repos/clasher-lease/envs/clasher-gpu/bin/python
    mkdir -p "$job/human/train"
    rsync -a --quiet 127x01:/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/imitation/data/v2-store-v1/train/ "$job/human/train/"
    scp -q 127x01:/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/imitation/data/v2-store-v1/manifest.json 127x01:/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/imitation/data/v2-store-v1/mask_table.npy "$job/human/" ;;
  *) exit 2 ;;
esac
if [[ $host == 127x01 ]]; then
  cp /mpac/sdicks02/repos/clasher-eval-snapshots/inputs-bc-v1/main02.pt "$job/inputs/"
  cp /mpac/sdicks02/jobs/clasher/t11-20261008-v1/inputs/assets.npz /mpac/sdicks02/jobs/clasher/t11-20261008-v1/inputs/assets.npz.json "$job/inputs/"
else
  scp -q 127x01:/mpac/sdicks02/repos/clasher-eval-snapshots/inputs-bc-v1/main02.pt "$job/inputs/"
  scp -q 127x01:/mpac/sdicks02/jobs/clasher/t11-20261008-v1/inputs/assets.npz 127x01:/mpac/sdicks02/jobs/clasher/t11-20261008-v1/inputs/assets.npz.json "$job/inputs/"
fi
"$gpu" -m venv --system-site-packages "$job/venv"
gpu_packages=$("$gpu" -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
task_packages=$("$job/venv/bin/python" -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
printf '%s\n' "$gpu_packages" > "$task_packages/qualified-gpu.pth"
"$job/venv/bin/python" -m pip install --quiet numpy==2.3.5
"$job/venv/bin/python" -B "$job/ops/verify_human.py" "$job/human" "$job/inputs"
export PYTHONPATH=$job/source:$job/source/src
"$job/venv/bin/python" -B -c 'from imitation.exit_r1.student import initialize; from imitation.model.store import PackedStore; import os,torch; p=os.environ["PYTHONPATH"].split(":")[0].rsplit("/",1)[0]; model,c=initialize(p+"/inputs/main02.pt"); s=PackedStore(p+"/human/train","train",p+"/inputs/assets.npz"); assert c.width==192; assert all(torch.equal(getattr(model,b).cpu(),torch.from_numpy(s.assets[k])) for k,b in (("costs","costs"),("descriptors","descriptors"),("tiles","tile_features"))); print("v1 width192 static asset equality PASS")'
date -u +%FT%TZ > "$job/fit-ready.txt"
