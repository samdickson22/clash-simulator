#!/usr/bin/env bash
# Recipe only; needs a separately authorized Mac session and fresh directories.
set -euo pipefail
[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || { echo 'Darwin/arm64 only' >&2; exit 2; }
[[ ${SAM_AUTHORIZED_REPLAY:-} == yes ]] || { echo 'Separate Mac session authorization required' >&2; exit 2; }
runtime_root=${1:?fresh frozen runtime checkout}
bundle=${2:?reviewed tiers input bundle}
manifest_sha=${3:?independently approved tiers-pins.json SHA256}
build_output=${4:?fresh build directory outside the checkout}
python=${PYO3_PYTHON:?absolute native arm64 Python}
[[ ! -e "$build_output" ]] || { echo 'Fresh build output required' >&2; exit 2; }
export RUSTFLAGS='' CARGO_INCREMENTAL=0
"$python" -B - "$runtime_root" "$bundle" "$manifest_sha" <<'PY'
import hashlib, platform, sys
from pathlib import Path
root,bundle,expected = Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
assert platform.machine() == 'arm64' and sys.version_info >= (3,12)
assert hashlib.sha256((bundle/'tiers-pins.json').read_bytes()).hexdigest() == expected
sys.path.insert(0,str(root/'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3'))
from tier_backend import validate_bundle
validate_bundle(bundle,root,dry_run=False)
PY
mkdir -p "$build_output"
build_output=$(cd "$build_output" && pwd)
export CARGO_TARGET_DIR="$build_output/target"
rustc -vV > "$build_output/rustc.txt"
nice -n 10 cargo build --locked --manifest-path "$runtime_root/engine-rs/Cargo.toml" \
  --release --features extension-module,gil-release --target aarch64-apple-darwin -j 2 \
  > "$build_output/cargo.log" 2>&1
suffix=$("$python" -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')
cp "$build_output/target/aarch64-apple-darwin/release/libclasher_core.dylib" "$build_output/clasher_core$suffix"
file "$build_output/clasher_core$suffix" > "$build_output/file.txt"
otool -L "$build_output/clasher_core$suffix" > "$build_output/otool.txt"
"$python" -B - "$build_output" "$manifest_sha" "$suffix" <<'PY'
import hashlib,json,sys,time
from pathlib import Path
out=Path(sys.argv[1]); native=out/('clasher_core'+sys.argv[3])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result=dict(native_sha256=sha(native),source_manifest_sha256=sys.argv[2],
    target='aarch64-apple-darwin',rustflags='',locked=True,utc=time.time(),
    native_file=native.name,toolchain=(out/'rustc.txt').read_text(),
    file=(out/'file.txt').read_text(),otool=(out/'otool.txt').read_text(),
    final=False,files={p.name:sha(p) for p in out.iterdir() if p.is_file()})
with (out/'build-tiers.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
with (out/'build-tiers.sha256').open('x') as f:f.write(sha(out/'build-tiers.json')+'  build-tiers.json\n')
PY
