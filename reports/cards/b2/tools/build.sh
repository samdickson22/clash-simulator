#!/bin/bash
# usage: build.sh SRC_DIR OUT_DIR   (Batch B2 copy of native-total-tools/build.sh; -j 8 per CARD LEAD compute rule)
set -euo pipefail
src=$1; out=$2
export CARGO_HOME=/mpac/sdicks02/tools/cargo RUSTUP_HOME=/mpac/sdicks02/tools/rustup
export PATH=/mpac/sdicks02/tools/cargo/bin:$PATH
export CARGO_TARGET_DIR=$out/target CARGO_INCREMENTAL=0
export PYO3_PYTHON=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
mkdir -p $out
date -u +%FT%TZ > $out/build-start.txt
nice -n 15 cargo +1.97.1 build --offline --manifest-path $src/Cargo.toml --release --features extension-module,gil-release -j 8
cp $CARGO_TARGET_DIR/release/libclasher_core.so $out/clasher_core.abi3.so.tmp
mv $out/clasher_core.abi3.so.tmp $out/clasher_core.abi3.so
sha256sum $out/clasher_core.abi3.so | tee $out/sha256.txt
date -u +%FT%TZ > $out/build-end.txt
