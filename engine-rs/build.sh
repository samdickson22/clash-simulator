#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$PWD/engine-rs/target}"
export CARGO_INCREMENTAL=0
export PYO3_PYTHON="${PYO3_PYTHON:-$PWD/.venv/bin/python}"
nice -n 10 cargo build --manifest-path engine-rs/Cargo.toml --release --features extension-module -j 1
case "$(uname -s)" in
  Darwin) native_library="$CARGO_TARGET_DIR/release/libclasher_core.dylib" ;;
  Linux) native_library="$CARGO_TARGET_DIR/release/libclasher_core.so" ;;
  *) echo 'Unsupported build host' >&2; exit 1 ;;
esac
# A new inode avoids stale executable mappings/code-signature cache entries.
native_stage=$(mktemp engine-rs/clasher_core.XXXXXX)
trap 'rm -f "$native_stage"' EXIT
cp "$native_library" "$native_stage"
mv "$native_stage" engine-rs/clasher_core.abi3.so
PYTHONPATH="$PWD/engine-rs:$PWD/src" "$PYO3_PYTHON" -B -c 'import clasher_core; print("Native extension import passed")'
