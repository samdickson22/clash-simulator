#!/usr/bin/env bash
# CPU-only, opt-in Linux builds. Never invokes the in-place build.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
variant=${1:?usage: build_quickwins.sh baseline|gil|v3|gil-v3 NEW_OUTPUT_DIR}
output=${2:?supply a new output directory}
case "$variant" in baseline|gil|v3|gil-v3) ;; *) exit 2 ;; esac
case "$(hostname -s)" in 127x04|127x08) ;; *) echo 'Build only on approved CPU hosts 127x04/08' >&2; exit 2 ;; esac
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || exit 2
mkdir -p "$output"
output=$(cd "$output" && pwd)
[[ ! -e "$output/clasher_core.abi3.so" && ! -e "$output/target" ]] || {
    echo 'Output must be a fresh binary/build path' >&2; exit 2;
}
features=extension-module
[[ $variant != *gil* ]] || features+=,gil-release
export RUSTFLAGS=''
if [[ $variant == *v3* ]]; then
    for flag in avx avx2 bmi1 bmi2 f16c fma movbe xsave sse4_1 sse4_2 ssse3 popcnt cx16 lahf_lm; do
        grep -qw "$flag" /proc/cpuinfo || { echo "CPU lacks $flag" >&2; exit 2; }
    done
    # Linux reports AMD's LZCNT capability as abm on some kernels.
    grep -Eqw 'lzcnt|abm' /proc/cpuinfo || { echo 'CPU lacks LZCNT' >&2; exit 2; }
    export RUSTFLAGS='-C target-cpu=x86-64-v3'
fi
export CARGO_TARGET_DIR="$output/target" CARGO_INCREMENTAL=0
export PYO3_PYTHON=${PYO3_PYTHON:?set PYO3_PYTHON to Python 3.12+}
nice -n 19 cargo build --locked --manifest-path engine-rs/Cargo.toml \
    --release --features "$features" -j 1
cp "$CARGO_TARGET_DIR/release/libclasher_core.so" "$output/clasher_core.abi3.so"
{
    echo "variant=$variant"
    echo "features=$features"
    echo "RUSTFLAGS=$RUSTFLAGS"
    echo 'platform=Linux x86_64 fleet only; never copy v3 variants to Mac'
    rustc --version
    sha256sum engine-rs/Cargo.toml engine-rs/Cargo.lock engine-rs/src/*.rs
    sha256sum "$output/clasher_core.abi3.so"
} > "$output/build-manifest.txt"
nice -n 19 env PYTHONPATH="$output" "$PYO3_PYTHON" -B -c \
    'import clasher_core; print("New-path native import:", clasher_core.__file__)'
