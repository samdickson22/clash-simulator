#!/usr/bin/env bash
# Standalone training env. Never runs uv sync or touches the engine .venv/uv.lock.
set -euo pipefail
case $(hostname -s) in
  127x09|127x11|127x13|127x14|127x15|127x16|127x18) ;;
  *) echo 'Only granted Clasher lease hosts may build this GPU environment' >&2; exit 2 ;;
esac
if [[ -n $(who) ]]; then
  echo 'Host occupied; postpone environment setup until who is empty' >&2
  exit 75
fi
base=/mpac/sdicks02/repos/clasher-lease
env_path=$base/envs/clasher-gpu
source "$base/env.sh"
export TMPDIR=$base/tmp PYTHONDONTWRITEBYTECODE=1
export CUDA_CACHE_PATH=$base/cache/cuda TRITON_CACHE_DIR=$base/cache/triton
export TORCHINDUCTOR_CACHE_DIR=$base/cache/torchinductor MPLCONFIGDIR=$base/cache/matplotlib
export YOLO_CONFIG_DIR=$base/tmp/clasher-gpu-yolo-config
mkdir -p "$TMPDIR" "$base/envs" "$base/jobs/clasher"
exec 9>"$base/jobs/clasher/gpu-env.lock"
flock -n 9 || { echo 'GPU environment setup is already running' >&2; exit 75; }
uv_bin=$base/tools/uv/uv
[[ -n $uv_bin ]] || { echo 'uv unavailable' >&2; exit 2; }
if [[ ! -x $env_path/bin/python ]]; then
  nice -n 10 "$uv_bin" venv --python 3.12.13 "$env_path"
fi
actual_python=$("$env_path/bin/python" -c 'import platform; print(platform.python_version())')
[[ $actual_python == 3.12.13 ]] || { echo "Existing env has Python $actual_python; expected 3.12.13" >&2; exit 2; }
requirements=$(mktemp "$TMPDIR/clasher-gpu-pins.XXXXXX")
trap 'rm -f "$requirements"' EXIT
cat > "$requirements" <<'PINS'
certifi==2026.7.22
charset-normalizer==3.5.2
contourpy==1.3.3
cycler==0.12.1
filelock==3.32.3
fonttools==4.66.1
fsspec==2026.7.0
idna==3.20
jinja2==3.1.6
kiwisolver==1.5.1
markupsafe==3.0.3
matplotlib==3.11.2
mpmath==1.3.0
networkx==3.6.1
numpy==1.26.4
nvidia-cublas-cu11==11.11.3.6
nvidia-cuda-cupti-cu11==11.8.87
nvidia-cuda-nvrtc-cu11==11.8.89
nvidia-cuda-runtime-cu11==11.8.89
nvidia-cudnn-cu11==9.1.0.70
nvidia-cufft-cu11==10.9.0.58
nvidia-curand-cu11==10.3.0.86
nvidia-cusolver-cu11==11.4.1.48
nvidia-cusparse-cu11==11.7.5.86
nvidia-nccl-cu11==2.21.5
nvidia-nvtx-cu11==11.8.86
opencv-python==4.10.0.84
packaging==26.3
pandas==3.0.6
pillow==12.3.0
psutil==7.2.2
py-cpuinfo==9.0.0
pyparsing==3.3.3
python-dateutil==2.9.0.post0
pyyaml==6.0.3
requests==2.34.2
scipy==1.17.1
seaborn==0.13.2
setuptools==78.1.0
six==1.17.0
sympy==1.14.0
thop==0.1.1.post2209072238
torch==2.7.1+cu118
torchvision==0.22.1+cu118
tqdm==4.70.1
triton==3.3.1
typing-extensions==4.16.0
ultralytics==8.1.24
urllib3==2.8.0
PINS
# Explicit +cu118 versions prevent selecting a CUDA 12 wheel from PyPI.
# All 49 packages, including NVIDIA runtime libraries, are version pinned above.
# Search both trusted indexes: the Torch mirror also carries stale PyPI packages.
nice -n 10 "$uv_bin" pip sync --python "$env_path/bin/python" \
  --default-index https://pypi.org/simple \
  --index https://download.pytorch.org/whl/cu118 \
  --index-strategy unsafe-best-match "$requirements"
nice -n 10 "$uv_bin" pip check --python "$env_path/bin/python"
"$env_path/bin/python" -c 'import sys, importlib.metadata as m; print(sys.version); print({p:m.version(p) for p in ("torch","torchvision","ultralytics","numpy")})'
printf 'Activate: source %s/env.sh; source %s/bin/activate\n' "$base" "$env_path"
printf 'Trusted local Ultralytics checkpoints: export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1\n'
