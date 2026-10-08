#!/usr/bin/env bash
# Run on the measurement host, never on the shared command center.
# No cargo dependencies; default rustc IEEE arithmetic, no fast-math/FMA flags.
set -euo pipefail
cd "$(dirname "$0")/../../../.."
case $(uname -s) in
  Darwin) library=src/clasher/live/_lattice.dylib ;;
  Linux) library=src/clasher/live/_lattice.so ;;
  *) echo 'Unsupported lattice build host' >&2; exit 2 ;;
esac
rustc --version
nice -n 10 rustc --crate-type cdylib --edition=2021 -C opt-level=3 \
  src/clasher/live/lattice.rs -o "$library"
