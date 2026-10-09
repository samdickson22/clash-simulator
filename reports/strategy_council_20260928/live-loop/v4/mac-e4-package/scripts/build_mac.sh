#!/usr/bin/env bash
# Prepared recipe only. Native arm64 build; never use Linux quickwins on a Mac.
set -euo pipefail
[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || { echo 'Requires native macOS/arm64 (no Rosetta)' >&2; exit 2; }
root=${1:?isolated runtime checkout}
output=${2:?fresh versioned build directory outside engine-rs}
python=${PYO3_PYTHON:?absolute native arm64 Python 3.12+ path}
cd "$root"
package=reports/strategy_council_20260928/live-loop/v4/mac-e4-package
"$python" -B "$package/scripts/measure_mac.py" verify-sources
[[ ! -e "$output" ]] || { echo 'Fresh build output required' >&2; exit 2; }
mkdir -p "$output"
output=$(cd "$output" && pwd)
"$python" -c 'import platform,sys; assert platform.machine()=="arm64" and sys.version_info >= (3,12)'
rustc -vV > "$output/rustc.txt"
rustup target add aarch64-apple-darwin
export CARGO_TARGET_DIR="$output/target" CARGO_INCREMENTAL=0
export PYO3_PYTHON="$python" RUSTFLAGS=''
nice -n 10 cargo build --locked --manifest-path engine-rs/Cargo.toml \
  --release --features extension-module,gil-release --target aarch64-apple-darwin -j 2 \
  > "$output/cargo.log" 2>&1
suffix=$("$python" -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')
cp "$output/target/aarch64-apple-darwin/release/libclasher_core.dylib" "$output/clasher_core$suffix"
file "$output/clasher_core$suffix" > "$output/file.txt"
otool -L "$output/clasher_core$suffix" > "$output/otool.txt"
PYTHONPATH="$output:$PWD/src" "$python" -B "$package/scripts/measure_mac.py" \
  build-receipt --native-dir "$output" --output "$output/build.json"
