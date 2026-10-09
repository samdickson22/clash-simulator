#!/usr/bin/env bash
# Explicit 03-only build, fresh paths, same quickwins feature/target policy.
set -euo pipefail
[[ $(hostname -s) == 127x03 && $(uname -m) == x86_64 ]]
source_dir=${1:?engine-rs source directory}
output=${2:?fresh output directory}
[[ ! -e "$output" ]]
mkdir -p "$output"
export CARGO_HOME=/mpac/sdicks02/tools/cargo RUSTUP_HOME=/mpac/sdicks02/tools/rustup
export PATH="$CARGO_HOME/bin:$PATH" CARGO_TARGET_DIR="$output/target" CARGO_INCREMENTAL=0
export PYO3_PYTHON=/mpac/sdicks02/repos/clasher/.venv/bin/python
export RUSTFLAGS='-C target-cpu=x86-64-v3'
cargo build --locked --manifest-path "$source_dir/Cargo.toml" --release --features extension-module,gil-release -j 1
cp "$output/target/release/libclasher_core.so" "$output/clasher_core.abi3.so"
sha256sum "$source_dir/Cargo.toml" "$source_dir/Cargo.lock" "$source_dir"/src/*.rs "$output/clasher_core.abi3.so" > "$output/build-manifest.txt"
