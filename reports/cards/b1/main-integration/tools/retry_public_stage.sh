#!/usr/bin/env bash
# Proposed reviewed retry: immutable04 production + genuine unaffected evidence.
# No engine startup. All writes target NEW05 only; review before execution.
set -euo pipefail
[[ $(hostname -s) == 127x04 ]]
I=/mpac/sdicks02/jobs/clasher/cards/b1/review-r1-main-20261016-05-stage
A=/mpac/sdicks02/jobs/clasher/cards/b1/review-r1-main-20261016-05
O=/mpac/sdicks02/jobs/clasher/cards/b1/review-r1-main-20261016-04
[[ -d "$I" && ! -L "$I" && ! -e "$A" && ! -e "$O/public.done" && ! -e "$O/gate" ]]
if ps -p 1634216,1634860,829556,974989,1140529,1141325,1709424,1709505,1777014,1777319,1870492,1870931 -o pid=,args=; then exit 3; fi
(cd "$I" && sha256sum -c inputs.sha256)
[[ $(sha256sum "$I/public_emitted.py" | cut -d' ' -f1) == 1dcd9d1908d399b1301f89ba4f09f6c078bc845a9ac6e0420d1d908beef790a6 ]]
[[ $(cat "$O/source-commit.txt") == 182039c8fbfce1103dd6430fa27e3c5f17b06c81 ]]
[[ $(sha256sum "$O/source.sha256" | cut -d' ' -f1) == 43299db661f38155682eb54086a7ac8b14650a3f9a69639849710bcba3d033a1 ]]
[[ $(sha256sum "$O/tools.sha256" | cut -d' ' -f1) == dd2e4c8472381618647cb4e733b3f450f064d0228ff42f0d68aab3c17f7d621d ]]
[[ $(sha256sum "$O/inputs.sha256" | cut -d' ' -f1) == e130c29e5e632ee147660a5cc6ccbebc8815e6208dd3cbdb6c8099f8856bf358 ]]
(cd "$O" && sha256sum -c --quiet source.sha256 && sha256sum -c --quiet tools.sha256 && sha256sum -c --quiet inputs.sha256 && sha256sum -c --quiet native-build-inputs.sha256)
(cd "$O/supplemental" && sha256sum -c --quiet tools.sha256)
sha256sum -c --quiet "$O/native-build-origin-expected.sha256"
sha256sum -c --quiet "$O/native.sha256"
[[ $(sha256sum "$O/out/clasher_core.abi3.so" | cut -d' ' -f1) == 6737c140a4ab2792df22e53190001c58208f4ea27b9fd4d0cb0862e0e2f8161d ]]
sha256sum -c --quiet "$O/gate-inputs-expected.sha256"
(cd "$O" && sha256sum -c --quiet - <<'ORIGIN_HASHES'
0d95e3049ff81009bc97e66128571bc9a623f6d9c42080e248c39620743ca846  affected.done
f2dfabd2bf3554f222bdadac3a353cfbe50449a5125624c41342549b13c7e3db  affected.json
efcf2cc3219199ec8beb4ded1cba13a7f6841775f83b630a060e1526f57e0b89  public-emitted.json
8d941d25fb6e5b68867fc23c35e7e3579d55676eccbd8b8c3cd64c4533b18c52  public-owner.json
bbdaf1a72bedeb2c89db61beabfd0da46ad297056ac3aea1d09f85e27caf9e0a  reference.done
b44b2aaa91c16347d72455fadd2b769922ebddd2b54d3b0c0679f5df06199877  reference/after.jsonl
6e6d51ce6ce4c91ae4fedab689abdf1281bc696314f2ad3e22669336f0667858  reference/before.jsonl
bcf18d6fff836f80b07dd7004fed69162d4e42a0f5497997e730b204d92298a9  reference/compare.json
95af5f1212884df3cef0a6bce0e0aa569e24972f19107feb2b84b5e29c0004ce  regressions.json
91e429627952de1659ee533ab21c0632139f1960e1354434c647fa343c11baba  supplemental.done
a5dc2edaced2894f07a3835c2fabd4262e3ff6dfb1e5b7e3e1b67f95d0fcf47d  supplemental/result.json
086184544ce710a18ce2579540f23d3060cb2cef7503da38091fffb3566136b3  test.done
ORIGIN_HASHES
)
mkdir "$A" "$A/reference" "$A/supplemental" "$A/admitted-inputs"
cp "$I/public_emitted.py" "$I/retry_public_stage.sh" "$I/harness-commit.txt" "$I/inputs.sha256" "$A/admitted-inputs/"
(cd "$A/admitted-inputs" && sha256sum -c inputs.sha256)
for name in tree repo root out; do ln -s "$O/$name" "$A/$name"; done
cp -a "$O/tools" "$A/tools"
cp "$I/public_emitted.py" "$A/tools/public_emitted.py"
cp "$I/retry_public_stage.sh" "$I/harness-commit.txt" "$A/"
for name in source.sha256 source-commit.txt native.sha256 native-build-inputs.sha256 native-build-origin-expected.sha256 original-source.sha256 pinned-expected.sha256 original-compare.json gate-inputs-expected.sha256 build.done build-origin.txt native-origin.sha256 stats-spec.json root-implementation-packet.json root-source-review.md; do
  cp "$O/$name" "$A/$name"
done
for phase in test affected supplemental reference; do cp "$O/$phase.done" "$A/$phase.done"; done
cp "$O/regressions.json" "$O/affected.json" "$A/"
cp "$O/supplemental/result.json" "$A/supplemental/result.json"
cp "$O/reference/compare.json" "$O/reference/before.jsonl" "$O/reference/after.jsonl" "$A/reference/"
cp "$O/public-emitted.json" "$A/origin-public-emitted-failed.json"
cp "$O/public-owner.json" "$A/origin-public-owner.json"
PYTHONDONTWRITEBYTECODE=1 python3 -B - "$A" "$O" <<'PY'
import hashlib,json,sys
from pathlib import Path
a,o=map(Path,sys.argv[1:])
proof={}
for phase,name,count in [('test','regressions.json',16),('affected','affected.json',94),('supplemental','supplemental/result.json',4)]:
    p=json.loads((a/name).read_text())
    if p['passed']!=count or p['total']!=count or not all(r['ok'] for r in p['tests']):raise SystemExit('invalid origin '+phase)
    proof[phase]={'executed_in':str(o),'receipt':(a/(phase+'.done')).read_text(),'result_sha256':hashlib.sha256((a/name).read_bytes()).hexdigest()}
p=json.loads((a/'reference/compare.json').read_text())
if p['total']!=39 or p['b1_regressions'] or not all(r['ours_unchanged'] and r['after']!='HARNESS-GAP' for r in p['results']):raise SystemExit('invalid reference origin')
for name in ('before.jsonl','after.jsonl'):
    if len((a/'reference'/name).read_text().splitlines())!=39:raise SystemExit('reference coverage')
proof['reference']={'executed_in':str(o),'receipt':(a/'reference.done').read_text(),'pairs':39,'actual_runs':78}
p=json.loads((a/'origin-public-emitted-failed.json').read_text())
if p['total']!=14 or p['passed']!=12 or any(r['name']!='rework-bodies-shots' or 'zero-speed ordinary control disappeared or moved' not in r['error'] for r in p['tests'] if not r['ok']):raise SystemExit('unexpected failed origin')
p=json.loads((a/'origin-public-owner.json').read_text())
if p['total']!=16 or p['passed']!=16:raise SystemExit('owner origin coverage')
record=dict(production_source_commit=(a/'source-commit.txt').read_text().strip(),harness_commit=(a/'harness-commit.txt').read_text().strip(),native='6737c140a4ab2792df22e53190001c58208f4ea27b9fd4d0cb0862e0e2f8161d',reused_actual_phases=proof,fresh_phases=['public','gate'],note='No non-public phase or build re-executed. Production source and their complete inputs remain immutable04; only the ordinary zero-speed harness grid oracle/comment changed. All public cases and the sole C56 gate must execute fresh05.')
with (a/'validation-origin.json').open('x') as f:json.dump(record,f,indent=2)
PY
find "$A" -maxdepth 1 -type l -printf '%p -> %l\n' | sort > "$A/reuse-links.txt"
(cd "$A" && find tools -type f -print0 | sort -z | xargs -0 sha256sum > tools.sha256)
{
  cd "$A"
  sha256sum admitted-inputs/public_emitted.py admitted-inputs/retry_public_stage.sh admitted-inputs/harness-commit.txt admitted-inputs/inputs.sha256 source-commit.txt harness-commit.txt retry_public_stage.sh validation-origin.json reuse-links.txt native-build-inputs.sha256 native-build-origin-expected.sha256 build-origin.txt native-origin.sha256 stats-spec.json original-source.sha256 pinned-expected.sha256 original-compare.json gate-inputs-expected.sha256 root-implementation-packet.json root-source-review.md test.done affected.done supplemental.done reference.done regressions.json affected.json supplemental/result.json reference/compare.json reference/before.jsonl reference/after.jsonl origin-public-emitted-failed.json origin-public-owner.json
} > "$A/inputs.sha256"
(cd "$A" && sha256sum -c --quiet source.sha256 && sha256sum -c --quiet tools.sha256 && sha256sum -c --quiet inputs.sha256 && sha256sum -c --quiet native-build-inputs.sha256)
sha256sum -c --quiet "$A/native.sha256"
printf '%s immutable04 production and genuine non-public evidence reused; fresh05 public+gate required\n' "$(date -u +%FT%TZ)" > "$A/stage.done"
