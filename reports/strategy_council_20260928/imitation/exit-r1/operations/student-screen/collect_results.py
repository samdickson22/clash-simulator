"""Render complete frozen-screen summaries; never inspect or select partial fits."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

ARMS = ('S-mix', 'S-teacher', 'S-human')
def digest(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()
def read(p):
    return json.loads(Path(p).read_text())
def interval(m, scale=1):
    value = m['value'] * scale
    lo, hi = [x * scale for x in m['ci95']]
    return f'{value:.6f} [{lo:.6f}, {hi:.6f}]'
def table(lines, headers, rows):
    lines += ['| ' + ' | '.join(headers) + ' |',
              '| ' + ' | '.join(['---'] * len(headers)) + ' |']
    lines += ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows]
    lines.append('')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--job', required=True)
    a = p.parse_args()
    job = Path(a.job)
    controller = read(job/'controller.json')
    assert controller['stage'] == 'complete', controller
    aggregate = read(job/'aggregate.json')
    assert digest(job/'aggregate.json') == controller['aggregate_sha256']
    freeze = read(job/'execution-freeze.json')
    assert digest(job/'execution-freeze.json') == aggregate['freeze_sha256']
    corpus = read(job/'corpus/manifest.json')
    fit = {}
    for arm in ARMS:
        root = job/'fits'/arm
        done = read(root/'complete.json')
        segment = read(root/'segment.json')
        assert done['step'] == segment['optimizer_steps'] == 4883 and not done['stopped']
        records = [json.loads(s) for s in (root/'train.jsonl').read_text().splitlines()]
        assert len(records) == 4883 and records[-1]['rows'] == 40001536
        assert [r['step'] for r in records] == list(range(1, 4884))
        timing = [json.loads(s) for s in (root/'timing.jsonl').read_text().splitlines()]
        assert len(timing) == 4883
        checkpoint = root/'step-00004883.pt'
        assert digest(checkpoint) == freeze['files'][str(checkpoint)]
        fit[arm] = dict(segment=segment, checkpoint_sha256=digest(checkpoint),
            inputs=read(root/'inputs.json'), final=done,
            training_rows=40001536, rows_per_second=40001536/segment['wall_seconds'],
            gpu_hours=segment['wall_seconds']/3600,
            optimizer_gpu_hours=sum(r['optimizer_seconds'] for r in timing)/3600,
            cpu_hours=segment['cpu_seconds']/3600,
            max_pss_bytes=max(r['pss_bytes'] for r in timing),
            min_mem_available_bytes=min(r['mem_available_bytes'] for r in timing),
            min_gpu_free_bytes=min(r['gpu_free_bytes'] for r in timing))
    exits = {h:read(job/f'host-exits/{h}.json') for h in ('03','04','01')}
    assert all(x['complete'] and x['own_workers_vacated'] and not x['failures'] for x in exits.values())
    heldout = [read(g/'receipt.json') for g in sorted((job/'heldout').glob('game-*'))]
    assert len(heldout) == 64
    teacher = {a:read(job/f'supplement/{a}.json') for a in ARMS}
    receipt = dict(schema='clasher.exit-r1.student-screen-complete.v1',
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        lane='exploration; no multiplicity adjustment', corpus_manifest_sha256=digest(job/'corpus/manifest.json'),
        corpus_rows=corpus['rows'], source_games=49577,
        execution_freeze_sha256=aggregate['freeze_sha256'], aggregate_sha256=digest(job/'aggregate.json'),
        heldout_manifest_sha256=digest(job/'heldout-corpus/manifest.json'),
        pre_fit_pin_sha256=digest(job/'pre-fit-pin.json'), fits=fit, reporting_hosts=exits,
        reporting_cpu_hours=sum(x['children_cpu_seconds']+x['manager_cpu_seconds'] for x in exits.values())/3600,
        postprocessing_cpu_hours=controller['local_cpu_seconds']/3600,
        heldout_teacher_game_cpu_hours=sum(x['cpu_seconds'] for x in heldout)/3600,
        bootstrap=aggregate['bootstrap'], results=aggregate['arms'],
        game_diagnostics=aggregate['game_diagnostics'], teacher_diagnostics=teacher,
        inputs={name:sha for name,sha in freeze['files'].items()
                if name.endswith(('STUDENT-SCREEN-PLAN.md','student-seed-audit.json',
                                  'STUDENT-SCREEN-FREEZE-20261009.json','main02.pt','assets.npz','clasher_core.abi3.so'))})
    out = job/'result-artifacts'
    out.mkdir(exist_ok=True)
    (out/'student-screen-complete.json').write_text(json.dumps(receipt,indent=2)+'\n')
    lines = ['# Frozen ExIt round-1 student screen results', '',
        'Exploration lane; no multiplicity adjustment. All intervals are percentile 95% '
        'bootstrap intervals from 5,000 resamples with seed 80991010. Complete game seeds '
        'are the resampling unit; metric(b) resamples student/reference pairs jointly.', '',
        'Each arm used the released v1 main-2026100802 step22552 EMA, width192, '
        '4,883 steps ×8,192 =40,001,536 rows, fixed T11 optimizer/schedule, final EMA only. '
        'Teacher fractions were 0.5/1.0/0.0, temperature0.1, rare-play weight4 and value loss0. '
        'No reporting seed was used for tuning or checkpoint selection.', '',
        '## Arm decisions and metrics(a)/(b)', '']
    rows=[]
    for arm in ARMS:
        r=aggregate['arms'][arm]
        h=aggregate['game_diagnostics']['h2h'][arm]['student']['metrics']
        b=r['fallback']
        rows.append([arm,interval(h['loss'],100),interval(h['win'],100),interval(h['draw'],100),
            f"{100*b['loss_change']:.6f} [{100*b['ci95'][0]:.6f}, {100*b['ci95'][1]:.6f}]",
            'SURVIVES' if r['survives'] else 'KILLED', '; '.join(r['kill_reasons']) or 'None'])
    table(lines,['Arm','(a) loss %, 95% CI','(a) win %, 95% CI','(a) draw %, 95% CI',
        '(b) loss change pp, paired 95% CI','Decision','Kill rules fired'],rows)
    lines += ['All three arms completed 256/256 terminal head-to-head games and 600/600 '
              'terminal fallback/proposer games. The common init-W reference completed 600/600. '
              'Each arm has the same 64 terminal held-out teacher games. No arm was omitted '
              'because a kill rule fired.', '', '## Fit throughput and resources', '']
    table(lines,['Arm / host','Rows/s, full fit wall','GPU-hours, full fit wall','Optimizer GPU-hours',
        'Fit CPU-hours','Peak PSS GiB','Minimum GPU free GiB','Minimum MemAvailable GiB'],
        [[f"{arm} / {f['segment']['host']}",f"{f['rows_per_second']:.2f}",f"{f['gpu_hours']:.6f}",
          f"{f['optimizer_gpu_hours']:.6f}",f"{f['cpu_hours']:.6f}",f"{f['max_pss_bytes']/2**30:.3f}",
          f"{f['min_gpu_free_bytes']/2**30:.3f}",f"{f['min_mem_available_bytes']/2**30:.3f}"] for arm,f in fit.items()])
    lines += ['GPU-hours use elapsed wall time while each GPU was allocated, including '
              'store preparation and batch gathering. Optimizer time is synchronized step '
              'wall time and is shown separately. Fits ran simultaneously on01/04/09, '
              'nice10, one GPU per arm. 09 used the versioned capture-extension supervisor '
              'with a live Oct11 lease, four declared processes and46GB PSS cap. '
              'No CPU simulation ran on leased hosts; 08 remained unused.', '']
    table(lines,['Home host','Physical worker cores','Peak owned processes','Pool wall-hours',
        'Worker CPU-hours','Manager CPU-hours','Minimum MemAvailable GiB'],
        [[h,len(e['cores']),e['peak_owned_processes'],f"{e['elapsed_seconds']/3600:.6f}",
          f"{e['children_cpu_seconds']/3600:.6f}",f"{e['manager_cpu_seconds']/3600:.6f}",
          f"{e['minimum_mem_available_bytes']/2**30:.3f}"] for h,e in exits.items()])
    lines += [f"Total home reporting pool CPU-hours: {receipt['reporting_cpu_hours']:.6f}, "
              f"including held-out teacher generation ({receipt['heldout_teacher_game_cpu_hours']:.6f} "
              'game CPU-hours). These process-accounting totals include interpreter startup '
              'and SHA checks; game-only times below exclude startup. '
              f"Separate freeze/held-out packing/agreement/reduction CPU-hours: {receipt['postprocessing_cpu_hours']:.6f}. "
              'Data staging and training-corpus preparation are outside these screen compute totals.', '',
              '## Metric(c): teacher agreement', '',
              'Rates below are probability-based at T=1. Top8 agreement is recall among '
              'teacher-chosen plays. Teacher self-recall is1.0. Pending-command WAIT rows '
              'are unsupervised; expanded timed WAITs remain supervised.', '']
    for scope in ('teacher','all_poll_rows'):
        lines += [f"### {'Scored teacher roots' if scope=='teacher' else 'All eligible poll rows'}", '']
        table(lines,['Metric (95% CI)',*ARMS],
            [[metric,*[interval(teacher[arm][scope]['metrics'][metric]) for arm in ARMS]]
             for metric in teacher['S-mix'][scope]['metrics']])
        lines += [f"64 whole teacher games; {teacher['S-mix'][scope]['rows']:,} eligible rows.", '']
    lines += ['## Free-running and deadline diagnostics', '',
              'Play/WAIT rates use sampled actions per poll; pending and timed WAITs are '
              'shown separately. Deadline counters use search decisions as denominator. '
              'Completed roots exclude late/partial roots. Latency quantiles are descriptive '
              'decision quantiles; mean latency CIs resample whole games.', '']
    for mode in ('h2h','fallback'):
        for arm,sides in aggregate['game_diagnostics'][mode].items():
            lines += [f'### {mode} / {arm}', '']
            table(lines,['Metric (95% CI)','Student / reference seat','Opponent seat'],
                [[metric,interval(sides['student']['metrics'][metric]),
                  interval(sides['opponent']['metrics'][metric])]
                 for metric in sides['student']['metrics']])
            s=sides['student']
            lines += [f"Terminal {s['terminal_games']}/{s['games']}; game CPU-hours "
                      f"{s['cpu_seconds']/3600:.6f}; summed game wall-hours {s['wall_seconds']/3600:.6f}; "
                      f"ordered command hashes SHA256 `{s['command_hashes_sha256']}`.", '']
            if mode=='fallback':
                table(lines,['Latency seconds, p50 / p95 / p99','Student / reference seat','Opponent seat'],
                    [[key,*[' / '.join(f'{v:.6f}' for v in sides[side][key])
                             for side in ('student','opponent')]]
                     for key in ('proposer_seconds_p50_p95_p99','decision_wall_seconds_p50_p95_p99')])
    lines += ['## Immutable provenance and execution notes', '',
        'The frozen 14:38:39Z completed-game prefixes contain49,577 terminal SHA-sealed '
        'games, 6,009,681 roots and38,738,534 rows. Forty games finished during stop '
        'drainage and were excluded to preserve the exact coordinator cutoff. All '
        'generators exited0 and vacated before packing. All71 packed files were '
        'checksum-verified on every fitting host before any optimizer step.', '']
    table(lines,['Artifact','SHA256'],
        [['Packed training corpus manifest',receipt['corpus_manifest_sha256']],
         ['Held-out teacher manifest',receipt['heldout_manifest_sha256']],
         ['Pre-fit pin receipt',receipt['pre_fit_pin_sha256']],
         ['Final reporting execution freeze',receipt['execution_freeze_sha256']],
         ['Aggregate metrics',receipt['aggregate_sha256']],
         *[[arm+' final step4883 EMA checkpoint',f['checkpoint_sha256']] for arm,f in fit.items()],
         *[[Path(name).name,sha] for name,sha in receipt['inputs'].items()]])
    human=fit['S-mix']['inputs']['pins']
    table(lines,['Fit input','SHA256'],[['Human train manifest',human['human_manifest']],
          ['Public assets',human['assets']],['Common init checkpoint',human['init_checkpoint']]])
    lines += ['The pre-fit receipt also pins the human parent/dev manifests, publicmask, '
        'all training columns, the immutable runtime source files and init step/width. '
        'Qualified fitting runtime: NumPy2.3.5, Torch2.7.1+cu118. Frozen scientific code '
        'commits:39b6adf6 andf98d8926. Eight frozen tests passed, including real pack '
        'identity/tamper rejection and ratio0 equality to qualified T11.', '',
        'Technical setup retries occurred before fitting: self-SSH replaced by local '
        'copy, B4 modules overlaid from the unchanged frozen source, task-local GPU '
        'site-packages exposed, destination verifier made Python3.8 compatible, and '
        'instrumentation moved after the fresh-output check. The old09 supervisor '
        'refused before admission; the coordinator directed use of the existing '
        'Oct11 capture-extension wrapper. No global wrapper was edited. No recipe, '
        'reporting seed, scientific code or kill rule changed.', '',
        'Seed audit limitation from the coordinator freeze:02/07/18 were not directly '
        'inventoried; committed formula ranges and archive/mirror supplements cover '
        'them as disclosed in the seed-audit receipt. A surviving exploration arm '
        'would still require registered confirmatory gates and the L2 amendment '
        'before live replacement or DAgger round2.', '',
        'Complete machine-readable evidence: `receipts/student-screen-complete.json`; '
        'pre-fit and launch evidence: `receipts/student-screen-pre-fit.json` and '
        '`receipts/student-fit-launch.json`. Raw corpora, checkpoints and games remain '
        'under the host-local task directory and are not committed.', '']
    (out/'STUDENT-SCREEN-RESULTS.md').write_text('\n'.join(lines))
    print(json.dumps(dict(output=str(out),receipt_sha256=digest(out/'student-screen-complete.json'))))

if __name__ == '__main__':
    main()
