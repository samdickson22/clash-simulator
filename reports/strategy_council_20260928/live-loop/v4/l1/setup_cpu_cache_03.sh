#!/usr/bin/env bash
# Dedicated CPU environment; never alter the shared project environment.
set -euo pipefail
[[ $(hostname -s) == 127x03 ]] || exit 2
root=/mpac/sdicks02/repos/clasher-v4-cpu
mkdir -p "$root"
export UV_CACHE_DIR="$root/uv-cache" UV_CONCURRENT_DOWNLOADS=4 UV_CONCURRENT_INSTALLS=4
uv=/mpac/sdicks02/tools/uv/uv
[[ -e "$root/.venv/bin/python" ]] || "$uv" venv --python /mpac/sdicks02/repos/clasher/.venv/bin/python "$root/.venv"
"$uv" pip install --python "$root/.venv/bin/python" 'numpy==1.26.4' 'opencv-python==4.10.0.84'
"$uv" pip install --python "$root/.venv/bin/python" --index-url https://download.pytorch.org/whl/cpu 'torch==2.7.1+cpu'
"$root/.venv/bin/python" -B - <<'PY'
import ctypes.util,json,cv2,numpy,torch
from clasher.vision.l1_v4 import prepare_pixels
assert cv2.__version__=='4.10.0' and numpy.__version__=='1.26.4'
assert torch.__version__=='2.7.1+cpu' and ctypes.util.find_library('zstd')
a,h=prepare_pixels(numpy.zeros((1140,540,3),numpy.uint8))
assert a.shape==(832,448,3) and h.shape==(64,448,3)
print(json.dumps(dict(opencv=cv2.__version__,numpy=numpy.__version__,torch=torch.__version__,cpu_only=True,synthetic_only=True)))
PY
