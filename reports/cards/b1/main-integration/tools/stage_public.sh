#!/usr/bin/env bash
# PROPOSED host staging, independently review before execution. No engine/job
# execution here. Inputs are a reviewed committed-source archive and manifests.
set -euo pipefail
[[ $(hostname -s) == 127x04 ]] || exit 2
I=/mpac/sdicks02/jobs/clasher/cards/b1/review-r1-main-20261016-03-stage
A=/mpac/sdicks02/jobs/clasher/cards/b1/review-r1-main-20261016-03
OLD=/mpac/sdicks02/jobs/clasher/cards/b1/review-r1-main-20261016-02
BUILD=/mpac/sdicks02/jobs/clasher/cards/b1/review-r1-main-20261016-01
[[ -d "$I" && ! -L "$I" && ! -e "$A" && -f "$OLD/gate.done" && -f "$BUILD/build.done" ]]
if ps -p 1634216,1634860 -o pid=,args=; then exit 3; fi
(cd "$I" && sha256sum -c inputs.sha256)
[[ $(sha256sum "$OLD/tools.sha256" | cut -d' ' -f1) == 1d0cd6951ed85a0f852b022337bd672fb65d224351e8233c8d2de614a015a807 ]]
(cd "$OLD" && sha256sum -c --quiet source.sha256 && sha256sum -c --quiet tools.sha256)
sha256sum -c "$BUILD/native.sha256"
[[ $(sha256sum "$BUILD/out/clasher_core.abi3.so" | cut -d' ' -f1) == 6737c140a4ab2792df22e53190001c58208f4ea27b9fd4d0cb0862e0e2f8161d ]]
mkdir "$A" "$A/repo" "$A/out"
tar -xf "$I/source.tar" -C "$A/repo"
mv "$A/repo/engine-cards" "$A/tree"
cp "$I/source.sha256" "$A/source.sha256"
cp "$I/source-commit.txt" "$A/source-commit.txt"
cp "$I/native-build-inputs.sha256" "$A/native-build-inputs.sha256"
cp "$I/root-implementation-packet.json" "$I/root-source-review-r3.md" "$A/"
(cd "$A" && sha256sum -c --quiet source.sha256 && sha256sum -c --quiet native-build-inputs.sha256)
sed "s|  tree/|  $BUILD/tree/|" "$A/native-build-inputs.sha256" > "$A/native-build-origin-expected.sha256"
sha256sum -c --quiet "$A/native-build-origin-expected.sha256"
cp "$BUILD/out/clasher_core.abi3.so" "$A/out/clasher_core.abi3.so"
cp "$BUILD/build.done" "$A/build.done"
cp "$BUILD/native.sha256" "$A/native-origin.sha256"
sha256sum "$A/out/clasher_core.abi3.so" > "$A/native.sha256"
{
  printf 'Reused genuine01 native/build receipt; no fresh build execution. Rust/Cargo/build inputs verified identical.\n'
  cat "$BUILD/build.done" "$BUILD/native.sha256"
  sha256sum "$BUILD/source.sha256" "$A/native-build-inputs.sha256" "$A/native-build-origin-expected.sha256"
} > "$A/build-origin.txt"
cp -a "$OLD/tools" "$A/tools"
P=$A/repo/reports/cards/b1/main-integration/tools
cp "$P/combined_jobs.sh" "$A/tools/review_jobs.sh"
cp "$P/combined_reference_jobs.sh" "$A/tools/reference_jobs.sh"
cp "$P/public_emitted.py" "$P/gate_entry.py" "$A/tools/"
cp "$P/affected.py" "$P/first_update_paths.py" "$P/reference.py" "$A/tools/"
cp "$A/repo/reports/cards/b1/tools/review_regressions.py" "$A/repo/reports/cards/b1/tools/review_gate_assert.py" "$A/tools/"
cp "$A/repo/reports/cards/runtime/tools/probe_b1_public_root.py" "$A/tools/"
mkdir "$A/supplemental"
cp "$OLD/supplemental/supplemental.py" "$OLD/supplemental/supplemental_jobs.sh" "$A/supplemental/"
cp "$P/combined_supplemental_jobs.sh" "$A/supplemental/supplemental_jobs.sh"
(cd "$A/supplemental" && sha256sum supplemental.py supplemental_jobs.sh > tools.sha256)
cp "$OLD/stats-spec.json" "$A/stats-spec.json"
cp "$OLD/original-source.sha256" "$OLD/pinned-expected.sha256" "$OLD/original-compare.json" "$A/"
cp "$I/gate-inputs-expected.sha256" "$A/gate-inputs-expected.sha256"
sha256sum -c --quiet "$A/gate-inputs-expected.sha256"

# Mirror one level at a time. Every target is a NEW owned directory; never
# remove/write through a source symlink or change an immutable runtime input.
mirror() {
  local source=$1 target=$2 skip=$3 entry name
  mkdir "$target"
  for entry in "$source/"*; do
    name=${entry##*/}
    case " $skip " in *" $name "*) continue;; esac
    ln -s "$entry" "$target/$name"
  done
}
mirror "$OLD/root" "$A/root" 'engine-rs src gamedata.json reports'
ln -s ../tree "$A/root/engine-rs"
ln -s ../tree/py/src "$A/root/src"
ln -s ../tree/py/gamedata.json "$A/root/gamedata.json"
mirror "$OLD/root/reports" "$A/root/reports" 'strategy_council_20260928'
mirror "$OLD/root/reports/strategy_council_20260928" "$A/root/reports/strategy_council_20260928" 'engine-speed'
mirror "$OLD/root/reports/strategy_council_20260928/engine-speed" "$A/root/reports/strategy_council_20260928/engine-speed" 'stage5'
S=reports/strategy_council_20260928/engine-speed/stage5
mirror "$OLD/root/$S" "$A/root/$S" 'fair_player.py'
ln -s "$A/repo/$S/fair_player.py" "$A/root/$S/fair_player.py"
[[ $(readlink -f "$A/root/$S/fair_player.py") == "$A/repo/$S/fair_player.py" ]]
[[ $(readlink -f "$A/root/engine-rs") == "$A/tree" ]]
[[ $(readlink -f "$A/root/src") == "$A/tree/py/src" ]]
[[ $(readlink -f "$A/root/gamedata.json") == "$A/tree/py/gamedata.json" ]]
find "$A/root" -type l -printf '%p -> %l\n' | sort > "$A/mirror-links.txt"
(cd "$A" && find tools -type f -print0 | sort -z | xargs -0 sha256sum > tools.sha256)
{
  cd "$A"
  sha256sum source-commit.txt native-build-inputs.sha256 native-build-origin-expected.sha256 \
    build-origin.txt native-origin.sha256 stats-spec.json original-source.sha256 \
    pinned-expected.sha256 original-compare.json gate-inputs-expected.sha256 mirror-links.txt \
    root-implementation-packet.json root-source-review-r3.md
} > "$A/inputs.sha256"
(cd "$A" && sha256sum -c --quiet source.sha256 && sha256sum -c --quiet tools.sha256 && sha256sum -c --quiet inputs.sha256)
sha256sum -c --quiet "$A/native.sha256"
printf '%s stage only; new source/consumer/test receipts still required\n' "$(date -u +%FT%TZ)" > "$A/stage.done"
