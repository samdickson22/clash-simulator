from collections import defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path.cwd()
V4 = ROOT/'reports/strategy_council_20260928/live-loop/v4'
OUT = V4/'mac-native-build48'
ES = ROOT/'reports/strategy_council_20260928/engine-speed'
sys.path[:0] = [str(ROOT/'engine-rs'), str(ROOT/'src')]
from clasher.live.runtime import quantiles

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2)+'\n')

def final_json(log):
    rows=[]
    for line in Path(log).read_text().splitlines():
        try: rows.append(json.loads(line))
        except (json.JSONDecodeError, ValueError): pass
    return rows[-1]

def tests(name, count):
    log=OUT/f'{name}.log'
    text=log.read_text()
    match=re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK\s*$',text)
    assert match and int(match[1])==count, (name, text[-1000:])
    return dict(total=count,passed=count,errors=0,failures=0,elapsed_seconds=float(match[2]),log=str(log.relative_to(ROOT)),log_sha256=sha(log))

def main():
    build=read(OUT/'build-identity.json')
    assert all(sha(ROOT/p)==v for p,v in build['source_pins'].items())
    assert sha(build['native_path'])==build['native_sha256']
    assert read(OUT/'verification-complete.json')['passed']
    runtime=tests('runtime-retry',36)
    stage6=tests('stage6',69)
    p16=final_json(OUT/'p16.log'); c56=final_json(OUT/'c56.log')
    assert p16['checked_episodes']==12 and not p16['mismatches']
    assert c56['episodes']==7 and not c56['mismatches']
    identity={}
    for name,row,total,baseline in [
        ('p16',p16,12,ES.parent/'c56/engine/p16_identity_baseline_admitted.json'),
        ('c56',c56,7,ES/'c56_identity_baseline_canonical.json'),
        ('random',read(OUT/'random.json'),24,ES/'random_identity_baseline_admitted.json'),
        ('recorded',read(OUT/'recorded.json'),8,ES/'recorded_identity_baseline_admitted.json')]:
        assert not row['mismatches']
        if name in ('random','recorded'): assert len(row['results'])==total
        identity[name]=dict(passed=total,total=total,mismatches=[],baseline=str(baseline.relative_to(ROOT)),baseline_sha256=sha(baseline))
    s5=read(OUT/'stage5-200.json')
    assert s5['complete'] and len(s5['results'])==200
    stage5=dict(passed=200,total=200,candidates=sum(r['candidates'] for r in s5['results']),wall_seconds=read(OUT/'stage5.exit.json')['wall_seconds'],reference_sha256=sha(ES/'stage5/parity-r3.json'),receipt=str((OUT/'stage5-200.json').relative_to(ROOT)),receipt_sha256=sha(OUT/'stage5-200.json'),adapter=read(OUT/'stage5-adapter.json'))
    assert stage5['wall_seconds']<1800
    smoke=read(OUT/'latency-smoke.json')
    assert smoke['timing_ms']['frame_to_tap']['count']>=50 and not smoke['audit_errors']
    old=read(V4/'runtime-mac-latency.json')
    before=OUT/'runtime-mac-latency.before-build48.json'
    assert not before.exists()
    before.write_bytes((V4/'runtime-mac-latency.json').read_bytes())
    original_native=set(); old_samples=defaultdict(list); smoke_delays=set(); smoke_native=set()
    for match in smoke['matches']:
        seed=match['seed']
        historical=ROOT/'mac-latency-r2'/seed
        prov=read(historical/'provenance.json')
        original_native.update(v for k,v in prov['hashes'].items() if 'clasher_core.abi3.so' in k)
        with gzip.open(historical/'latency.jsonl.gz','rt') as f:
            for line in f:
                r=json.loads(line)
                if r['metric']=='frame_to_tap':old_samples['frame_to_tap'].append(r['ms'])
                if r['metric']=='search' and r.get('diagnostic',{}).get('candidates',0)>=2:old_samples['search_active'].append(r['ms'])
        fresh=OUT/'latency-smoke'/seed
        freshprov=read(fresh/'provenance.json')
        smoke_native.update(v for k,v in freshprov['hashes'].items() if 'clasher_core.abi3.so' in k)
        with gzip.open(fresh/'latency.jsonl.gz','rt') as f:
            for line in f:
                r=json.loads(line)
                if r['metric']=='search':
                    diagnostic=r.get('diagnostic',{})
                    for key in ('delay_ticks','total_delay_ticks','planner_total_delay_ticks','command_delay_ticks'):
                        if key in diagnostic:smoke_delays.add(diagnostic[key])
    assert smoke_native=={build['native_sha256']},smoke_native
    assert smoke_delays=={27},smoke_delays
    assert len(original_native)==1,original_native
    old_same={k:quantiles(v) for k,v in old_samples.items()}
    comparison=dict(new=smoke['timing_ms']['frame_to_tap'],historical_all_matches=old['latency']['timing_ms']['frame_to_tap'],historical_same_matches=old_same['frame_to_tap'],
        delta_vs_historical_all_ms={q:smoke['timing_ms']['frame_to_tap'][q]-old['latency']['timing_ms']['frame_to_tap'][q] for q in ['p50','p95','p99']},
        delta_vs_historical_same_matches_ms={q:smoke['timing_ms']['frame_to_tap'][q]-old_same['frame_to_tap'][q] for q in ['p50','p95','p99']},
        new_active_search=smoke['timing_ms']['search_active'],historical_same_matches_active_search=old_same['search_active'],
        original_native_sha256=next(iter(original_native)),smoke_native_sha256=build['native_sha256'],
        timing_note='Smoke uses the configured 27-tick total delay; original 228-submission calibration used provisional 28 ticks. Short smoke with a different sample count and scheduling; not a controlled binary-only speedup or full latency requalification.',
        configured_delay_ticks=27,observed_diagnostic_delays=sorted(smoke_delays))
    write(OUT/'latency-comparison.json',comparison)
    live=ROOT.parent/'clasher'
    initial=read(OUT/'live-checkout-before.json'); tracked_changes=[]; protected_changes=[]
    for name,h in initial['tracked_sha256'].items():
        p=live/name
        if not p.is_file() or sha(p)!=h:tracked_changes.append(name)
    nowstat={}
    for sub in ['engine-rs','.venv']:
        for p in (live/sub).rglob('*'):
            s=p.lstat();nowstat[str(p.relative_to(live))]=[s.st_ino,s.st_size,s.st_mtime_ns,p.is_symlink()]
    for name in initial['protected_stat'].keys()|nowstat.keys():
        if initial['protected_stat'].get(name)!=nowstat.get(name):protected_changes.append(name)
    audit=dict(tracked_files_checked=len(initial['tracked_sha256']),tracked_content_changes=tracked_changes,protected_metadata_entries_checked=len(initial['protected_stat']),protected_metadata_changes=protected_changes,
        live_native_sha256=sha(live/'engine-rs/clasher_core.abi3.so'),runtime_engine_is_symlink=(ROOT/'engine-rs').is_symlink(),runtime_engine_resolved=str((ROOT/'engine-rs').resolve()),
        python_environment=str((ROOT/'.venv').resolve()),python_environment_used_read_only=True,python_engine_or_gamedata_edits=False,emulator_renderer_actions=False,apk_actions=False,data_deleted=False,git_commits=False)
    write(OUT/'isolation-audit.json',audit)
    assert not tracked_changes and not protected_changes,audit
    assert audit['live_native_sha256']==next(iter(original_native))
    timestamp=datetime.now(timezone.utc).isoformat()
    evidence={str(p.relative_to(ROOT)):sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.suffix in ['.json','.log','.py','.txt']}
    receipt=dict(schema='clasher.live-v4.mac-native-build48.v1',status='passed',updated_utc=timestamp,mac_root=str(ROOT),build=build,identity=identity,stage5=stage5,stage6=stage6,runtime_tests=runtime,
        latency_smoke=smoke,latency_comparison=comparison,isolation=audit,evidence_sha256=evidence,
        qualification_scope='Mac build48 source parity and requested runtime checks. Fleet build48 qualifies the private native core; full Stage 6/S122 admission retains its existing ThreeMusketeers Python-controller blocker.',
        recorded_checkpoint=read(OUT/'recorded-checkpoint.json'),
        excluded_attempts=[dict(log=str((OUT/'runtime.log').relative_to(ROOT)),reason='Initial verification wrapper omitted __main__ guard for macOS spawn; wrapper corrected, product sources unchanged, full 36-test suite rerun.'),dict(log_pattern=str((OUT/'recorded-[0-7].log').relative_to(ROOT)),reason='All initial recorded attempts stopped during Context setup before any game because the frozen pilot checkpoint was absent. Exact qualified checkpoint subsequently copied and hashed; all eight games replayed fresh.')],
        execution=dict(nice=10,max_verification_lanes=2,build_jobs=1,blas_threads=1,verification_script=str((OUT/'verify_all.py').relative_to(ROOT)),post_script=str((OUT/'post_checks_retry.py').relative_to(ROOT)),recorded_balancer=str((OUT/'balance_recorded.py').relative_to(ROOT)),recorded_balancer_note='After game 7 frees its compute lane, game 3 runs there. Per-game exclusive lock prevents duplicate concurrent evaluation; original lane subsequently validates that fresh saved row through the unmodified identity authority.'))
    write(V4/'MAC-NATIVE-BUILD48.json',receipt)
    current=dict(old)
    current['updated_utc']=timestamp
    current['native_at_original_measurement']=dict(sha256=next(iter(original_native)),path=str(ROOT/'engine-rs/clasher_core.abi3.so'),provenance='mac-latency-r2/*/provenance.json; original historical measurement retained')
    current['native']=dict(build='build48',path=build['native_path'],sha256=build['native_sha256'],source_git_commit=build['source_git_commit'],source_pins_matched=66,rustc=build['rustc'].splitlines()[0],receipt='MAC-NATIVE-BUILD48.json',receipt_sha256=sha(V4/'MAC-NATIVE-BUILD48.json'))
    current['tests_before_native_upgrade']=old['tests']
    current['tests']=dict(runtime,zero_delay_s6_comparisons_passed=2,native_sha256=build['native_sha256'])
    current['native_upgrade_latency_smoke']=dict(metrics=smoke,comparison=comparison,receipt='MAC-NATIVE-BUILD48.json')
    current['limitations_before_native_upgrade']=old['limitations']
    current['limitations']=[x for x in old['limitations'] if not x.startswith('Two zero-delay native ABI')]
    current['limitations'].append(comparison['timing_note'])
    write(V4/'runtime-mac-latency.json',current)
    new=comparison['new'];same=comparison['historical_same_matches'];active=comparison['new_active_search'];prioractive=comparison['historical_same_matches_active_search']
    md=f'''# Mac native build48 verification

Completed {timestamp}. **PASS**: build48 native installed only under `{ROOT}`; runtime tests **36/36**, including both formerly failing zero-delay S6 comparisons.

- Mac native SHA256: `{build['native_sha256']}`.
- Toolchain: `{build['rustc'].splitlines()[0]}`, aarch64-apple-darwin. Existing toolchain; no installation or sudo. Build followed `engine-rs/build.sh`, release/extension-module, one Cargo job, nice 10; {build['build_seconds']:.2f} seconds.
- Source: git `main` at `{build['source_git_commit']}` from 127x05. **66/66 build48 source hashes matched** before and after verification. Complete hashes are in `MAC-NATIVE-BUILD48.json` and `mac-native-build48/build-identity.json`. Build48 pins SHA256: `{build['build48_pins_sha256']}`. The fleet Linux native SHA is platform-specific and is not the Mac binary pin.
- `NativeScripts.rollout` now exposes `full_rng=False`.

## Verification

| Check | Result |
|---|---|
| P16 admitted identity | **12/12**, zero mismatches |
| C56 canonical identity | **7/7**, zero mismatches |
| Random admitted identity | **24/24**, zero mismatches |
| Recorded admitted identity | **8/8**, zero mismatches; all fresh replays, merged through original checker |
| Stage 5 replay | **200/200 roots**, {stage5['candidates']:,} candidates, exact admitted action/trace hashes; {stage5['wall_seconds']:.2f} seconds |
| Stage 6 regressions | **69/69** methods, including build48 holdout reductions; {stage6['elapsed_seconds']:.3f} seconds |
| Full isolated runtime suite | **36/36**; {runtime['elapsed_seconds']:.3f} seconds |

Verification used at most two nice-10 lanes, with BLAS threads limited to one. Every gate process checked the loaded native path and SHA. The four historical identity drivers retain their existing Python/admitted-baseline semantics; Stage 5 and Stage 6 explicitly compare native behavior. Qualified gate drivers/fixtures came from the sealed build48 Linux isolated tree; the input ledger is `mac-native-build48/qualified-gate-source-pins.json`. Stage 5's adapter only relocates its native-path assertion from `stage6/native` to this runtime's `engine-rs`; its algorithm and baseline were unchanged.

## Latency smoke

The new binary completed **{new['count']} first-attempt mock submissions** across {len(smoke['matches'])} frozen-train replay match(es), on MPS with configured total delay **27 ticks**, without emulator/renderer actions. The run loaded the new native SHA in every provenance record. No audit errors; {smoke['counts']['search_overruns']} search deadline overruns. Processed {100*smoke['processed_fraction']:.3f}% at {smoke['processed_fps']:.3f} FPS.

| Frame to first-attempt submission completion, ms | Samples | p50 | p95 | p99 |
|---|---:|---:|---:|---:|
| New build48 smoke | {new['count']} | {new['p50']:.2f} | {new['p95']:.2f} | {new['p99']:.2f} |
| Historical same replay match(es) | {same['count']} | {same['p50']:.2f} | {same['p95']:.2f} | {same['p99']:.2f} |
| Historical full Mac calibration | 228 | {comparison['historical_all_matches']['p50']:.2f} | {comparison['historical_all_matches']['p95']:.2f} | {comparison['historical_all_matches']['p99']:.2f} |

Against the same historical match(es), smoke p50 changed {comparison['delta_vs_historical_same_matches_ms']['p50']:+.2f} ms and p99 {comparison['delta_vs_historical_same_matches_ms']['p99']:+.2f} ms. Active search p50/p99: {active['p50']:.2f}/{active['p99']:.2f} ms now versus {prioractive['p50']:.2f}/{prioractive['p99']:.2f} ms historically. {comparison['timing_note']} Original calibration and 27-tick timing profile were retained. The smoke is below the full-suite sample requirement; no full latency or production qualification is claimed.

## Isolation and receipts

The original runtime `engine-rs` symlink was preserved as `engine-rs.pre-build48-link` and replaced by a real directory. Symlinked verification-report trees were similarly preserved and copied into the isolated root. Prior differing gate files were retained under `mac-native-build48/prior-gates`. The shared `.venv` was used read-only; no packages were installed.

Postflight checked **{audit['tracked_files_checked']:,} live-checkout tracked file hashes** and **{audit['protected_metadata_entries_checked']:,} engine-rs/.venv metadata entries**: zero changes. Live native remains `{audit['live_native_sha256']}`. No Python engine/gamedata edits, emulator/renderer/APK actions, data deletion, or git commits.

An initial test-wrapper attempt lacked the macOS multiprocessing `__main__` guard and was excluded. Its verified process tree was terminated, the wrapper fixed, and all 36 tests rerun successfully. Initial recorded attempts stopped before game execution because the frozen pilot checkpoint was absent. The pilot tree was isolated, the exact checkpoint copied from the qualified fleet tree (SHA256 `c7aae667e45073bfab442b9d36a4b2c45bca7321df442d8ebfac419e191dc522`), and all eight recorded games replayed fresh. Failed-attempt evidence is retained.

Primary receipt: `MAC-NATIVE-BUILD48.json`. Build, source/input hashes, test/identity logs, isolation audit, original latency receipt, smoke raw logs/provenance, and comparison: `mac-native-build48/`. `runtime-mac-latency.json` now records both the historical measurement's original native pin and the installed build48 pin, the passing tests, and the separate smoke. This report, JSON receipt, updated latency receipt, and compact evidence are mirrored to 127x05.

Fleet build48 qualified the private native core. This update does not change the existing full Stage 6/S122 admission blocker for the ThreeMusketeers Python controller, or the separate formal-v4/emulator-on prerequisites.
'''
    (V4/'MAC-NATIVE-BUILD48.md').write_text(md)
    print(json.dumps(dict(native=build['native_sha256'],identity=identity,stage5=stage5['passed'],stage6=stage6['passed'],runtime=runtime['passed'],latency=new,isolation=audit),indent=2))

if __name__=='__main__':main()
