#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/w-screen8-20261009-r1
repo=$job/repo
py=/mpac/sdicks02/repos/clasher/.venv/bin/python
export CUDA_VISIBLE_DEVICES='' PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1
export XDG_CACHE_HOME=$job/cache PYTHONPYCACHEPREFIX=$job/cache/pycache
export CARGO_HOME=/mpac/sdicks02/tools/cargo RUSTUP_HOME=/mpac/sdicks02/tools/rustup PATH=/mpac/sdicks02/tools/cargo/bin:$PATH
export PYO3_PYTHON=$py CARGO_TARGET_DIR=$job/native-baseline-v1/target RUSTFLAGS='-C target-cpu=x86-64-v3'
cd "$repo"
base_paths=$repo/src:$job/baseline-source/engine-rs:$repo/reports/strategy_council_20260928/engine-speed/stage5:$repo/reports/strategy_council_20260928/engine-speed:$repo/reports/strategy_council_20260928/search-noise-s6:$repo/reports/strategy_council_20260928/search-noise-s4
export PYTHONPATH=$job/native-baseline-v1:$base_paths
cargo test --locked --manifest-path "$job/baseline-source/engine-rs/Cargo.toml" --lib -j 1
"$py" -B -c 'import clasher_core,pytest,sys,types,pathlib; b=types.ModuleType("bootstrap"); b.HERE=pathlib.Path("reports/strategy_council_20260928/search-noise-s6").resolve(); sys.modules["bootstrap"]=b; raise SystemExit(pytest.main(["tests/analysis/test_delay_fixes.py","reports/perf-audit/quickwins/test_resources.py","reports/strategy_council_20260928/search-noise-s6/test_delay.py","tests/test_native_elixir.py","tests/test_native_terminal_commands.py","tests/test_native_command_checks.py","-k","not frozen_tracker"]))'
qual=$repo/reports/perf-audit/quickwins/qualify.py
"$py" -B "$qual" prepare "$job/baseline-qualification" --games 1000
"$py" -B "$qual" verify "$job/baseline-qualification" --label candidate
"$py" -B "$qual" delayed-corpus "$job/baseline-qualification" --label candidate
reference=/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/reference
export PYTHONPATH=$reference:$base_paths
if cmp -s "$job/native-baseline-v1/clasher_core.abi3.so" "$reference/clasher_core.abi3.so"; then
    # The binary bytes are identical: reuse the already-executed deterministic
    # qualification, recording that this is reuse rather than a second run.
    cp "$job/baseline-qualification/candidate-verify.json" "$job/baseline-qualification/reference-verify.json"
    cp "$job/baseline-qualification/candidate-d27-corpus.json" "$job/baseline-qualification/reference-d27-corpus.json"
    printf '{"reference_reuses_candidate":true,"reason":"byte-identical binaries verified with cmp"}\n' > "$job/baseline-qualification/reference-reuse.json"
else
    "$py" -B "$qual" verify "$job/baseline-qualification" --label reference
    "$py" -B "$qual" delayed-corpus "$job/baseline-qualification" --label reference
fi
"$py" -B "$qual" compare "$job/baseline-qualification" --reference reference --variants candidate
"$py" -B "$qual" resources "$job/baseline-qualification"
printf 'PASS\n' > "$job/baseline-qualification/PASS"
