#!/usr/bin/env bash
set -euo pipefail
source /mpac/sdicks02/env.sh
cd /mpac/sdicks02/repos/clasher
uv sync --frozen --python 3.12.13
export PYO3_PYTHON="$PWD/.venv/bin/python"
bash engine-rs/build.sh
.venv/bin/python -c 'import site; from pathlib import Path; (Path(site.getsitepackages()[0])/"clasher_engine_core.pth").write_text(str(Path.cwd()/"engine-rs")+"\n")'
.venv/bin/python -c 'import sys; import clasher_core; print(sys.version); print(clasher_core.__file__)'
cargo test --manifest-path engine-rs/Cargo.toml -j 2
