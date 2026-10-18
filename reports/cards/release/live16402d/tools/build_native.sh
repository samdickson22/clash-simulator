#!/usr/bin/env bash
# Build the native core from an exported engine tree into a FRESH JOB/native-<sha8>/ (never over a loaded .so).
#   cpu_job.sh 8 bash build_native.sh SRC JOB        (SRC = build_runtime --export-only tree; 127x04/127x08 only)
# Same pinned toolchain/features as jobs/clasher/cards/build.sh, but cargo -j8 and nice 15.
set -euo pipefail
SRC=${1:?export tree} J=${2:?job}
case $(hostname -s) in 127x04|127x08) ;; *) echo "wrong host" >&2; exit 2;; esac
export CARGO_HOME=/mpac/sdicks02/tools/cargo RUSTUP_HOME=/mpac/sdicks02/tools/rustup
export PATH=/mpac/sdicks02/tools/cargo/bin:$PATH CARGO_INCREMENTAL=0
export PYO3_PYTHON=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
B=$J/native-build
[[ ! -e $B ]]
mkdir -p "$B"
export CARGO_TARGET_DIR=$B/target
date -u +%FT%TZ > "$B/build-start.txt"
nice -n 15 cargo +1.97.1 build --offline --manifest-path "$SRC/engine-cards/Cargo.toml" --release \
  --features extension-module,gil-release -j 8
so=$CARGO_TARGET_DIR/release/libclasher_core.so
h=$(sha256sum "$so" | cut -c1-64)
out=$J/native-${h:0:8}
[[ ! -e $out ]]
mkdir "$out"
cp "$so" "$out/clasher_core.abi3.so"
chmod a-w "$out/clasher_core.abi3.so"
echo "$h  $out/clasher_core.abi3.so" | tee "$out/sha256.txt"
date -u +%FT%TZ > "$B/build-end.txt"
