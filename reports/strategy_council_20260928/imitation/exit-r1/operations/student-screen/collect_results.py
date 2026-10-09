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
    prefit = read(job/'pre-fit-pin.json')
    fit = {}
    for arm in ARMS:
        root = job/'fits'/arm
        done = read(root/'complete.json')
        segment = read(root/'segment.json')
        segments=[read(p) for p in sorted((root/'segments').glob('*.json'))]+[segment]
        assert done['step'] == sum(s.get('effective_optimizer_steps',s['optimizer_steps']) for s in segments) == 4883 and not done['stopped']
        cursor=0
        for s in segments:
            assert s.get('cursor_start',0)==cursor
            cursor+=s.get('effective_optimizer_steps',s['optimizer_steps'])
        qualification=read(job/'loader-qualification'/arm/'PASS.json')
        assert qualification['passed']
        fit_wall=sum(s['wall_seconds'] for s in segments)
        fit_cpu=sum(s['cpu_seconds'] for s in segments)
        records = [json.loads(s) for s in (root/'train.jsonl').read_text().splitlines()]
        assert len(records) == 4883 and records[-1]['rows'] == 40001536
        assert [r['step'] for r in records] == list(range(1, 4884))
        timing = [json.loads(s) for s in (root/'timing.jsonl').read_text().splitlines()]
        assert len(timing) == 4883
        discarded_timing = [json.loads(s) for p in sorted((root/'archived-attempts').glob('*/timing.jsonl'))
                            for s in p.read_text().splitlines()]
        checkpoint = root/'step-00004883.pt'
        assert digest(checkpoint) == freeze['files'][str(checkpoint)]
        allocation_wall=(datetime.datetime.fromisoformat(segments[-1]['ended_at'])-
                         datetime.datetime.fromisoformat(segments[0]['started_at'])).total_seconds()
        fit[arm] = dict(segment=segment,segments=segments,qualification=qualification,
            checkpoint_sha256=digest(checkpoint),
            inputs=read(root/'inputs.json'), final=done,
            training_rows=40001536, rows_per_second=40001536/fit_wall,
            gpu_hours=fit_wall/3600,qualification_gpu_hours=qualification.get('wall_seconds',
                sum(s['segment']['wall_seconds'] for s in qualification['modes']))/3600,
            fitting_window_gpu_hours=allocation_wall/3600,
            optimizer_gpu_hours=sum(r['optimizer_seconds'] for r in timing+discarded_timing)/3600,
            discarded_updates=len(discarded_timing),
            cpu_hours=fit_cpu/3600,
            qualification_cpu_hours=sum(s['segment']['cpu_seconds'] for s in qualification['modes'])/3600,
            max_pss_bytes=max(max(r['pss_bytes'] for r in timing),
                              max(s.get('peak_loader_tree_pss_bytes',0) for s in segments)),
            min_mem_available_bytes=min(min(r['mem_available_bytes'] for r in timing),
                min(s.get('min_loader_mem_available_bytes') or 1<<62 for s in segments)),
            min_gpu_free_bytes=min(r['gpu_free_bytes'] for r in timing))
    exits = {h:read(job/f'host-exits/{h}.json') for h in ('03','04','01','08')}
    assert all(x['own_workers_vacated'] and ((x['complete'] and not x['failures']) or
        (h=='08' and (job/'reporting08-requeue.json').exists() and x['stop_requested'])) for h,x in exits.items())
    heldout = [read(g/'receipt.json') for g in sorted((job/'heldout').glob('game-*'))]
    assert len(heldout) == 64
    teacher = {a:read(job/f'supplement/{a}.json') for a in ARMS}
    performance=read(job/'loader-performance.json')
    allocator_qualification=read(job/'allocator-qualification/S-human/PASS.json')
    assert allocator_qualification['passed']
    micro_amendment=read(job/'student-micro3584-amendment.json')
    assert fit['S-human']['segment']['effective_human_microbatch']==3584
    receipt = dict(schema='clasher.exit-r1.student-screen-complete.v1',
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        lane='exploration; no multiplicity adjustment', corpus_manifest_sha256=digest(job/'corpus/manifest.json'),
        corpus_rows=corpus['rows'], corpus_root_decisions=6009681, source_games=49577,
        execution_freeze_sha256=aggregate['freeze_sha256'], aggregate_sha256=digest(job/'aggregate.json'),
        heldout_manifest_sha256=digest(job/'heldout-corpus/manifest.json'),
        pre_fit_pin_sha256=digest(job/'pre-fit-pin.json'), human_inputs=prefit['human_inputs'],
        runtime_source_files=prefit['source_files'], fits=fit, reporting_hosts=exits,
        reporting_cpu_hours=(sum(x['children_cpu_seconds']+x['manager_cpu_seconds'] for x in exits.values())+read(job/'reporting-failed-startup.json')['cpu_seconds'])/3600,
        failed_reporting_startup=read(job/'reporting-failed-startup.json'),
        reporting_native_amendment_sha256=digest(job/'student-reporting-native-amendment.json'),
        postprocessing_cpu_hours=controller['local_cpu_seconds']/3600,
        heldout_teacher_game_cpu_hours=sum(x['cpu_seconds'] for x in heldout)/3600,
        bootstrap=aggregate['bootstrap'],loader_performance=performance,
        loader_amendment_sha256=digest(job/'student-loader6-amendment.json'),
        owned_gpu_amendment_sha256=digest(job/'student-owned-gpu-amendment-v2.json'),
        owned_pss_scope_amendment_sha256=digest(job/'student-owned-gpu-amendment-v3.json'),
        parent_affinity_amendment_sha256=digest(job/'student-parent-affinity-amendment.json'),
        allocator_amendment_sha256=digest(job/'student-allocator-amendment.json'),
        allocator_qualification=allocator_qualification,
        human_micro_amendment=micro_amendment,
        human_micro_amendment_sha256=digest(job/'student-micro3584-amendment.json'),
        reporting08_amendment_sha256=digest(job/'student-reporting08-amendment.json'),
        reporting_rebalance_amendment_sha256=digest(job/'student-reporting-rebalance-amendment.json'),
        reporting_rebalance_transfer=read(job/'reporting-rebalance-transfer.json'),
        reporting_pre_mix_validation=read(job/'student-reporting-pre-mix-validation.json'),
        postprocessing_amendment_sha256=digest(job/'student-postprocessing-amendment.json'),
        mix_dispatch_amendment_sha256=digest(job/'student-mix-dispatch-amendment.json'),
        mix_pool_recovery=read(job/'student-mix-pool-recovery.json'),
        mix_pool_recovery_sha256=digest(job/'student-mix-pool-recovery.json'),
        reporting08_requeue=read(job/'reporting08-requeue.json') if (job/'reporting08-requeue.json').exists() else None,
        staged_reporting_amendment_sha256=digest(job/'student-staged-reporting-amendment.json'),
        staged_provenance=read(job/'staged-provenance.json'),
        allocator_qualification_gpu_hours=allocator_qualification['wall_seconds']/3600,
        allocator_qualification_cpu_hours=sum(x['segment']['cpu_seconds'] for x in allocator_qualification['modes'])/3600,
        owned_migration=read(job/'student-owned-migration.json'),results=aggregate['arms'],
        owned_micro_continuation=read(job/'student-micro3584-continuation.json'),
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
        'S-human uses the coordinator-authorized operational micro3584 amendment from '
        'checkpoint200. Effective batch8192, sampled rows/order and global loss denominators '
        'are unchanged. Gradient accumulation changes floating-point summation order; '
        'this continuation is not claimed bit-identical to micro7168. Its exact checkpoint '
        'recipe fingerprint remains7168; runtime/segment evidence records the actual3584.', '',
        'A coordinator-authorized staged reporting amendment began the common600 init-W '
        'reference cases and64 held-out teacher games on03 while fitting continued. '
        'S-human cases began on03;38 unclaimed fallback identities moved to04/08. '
        'S-teacher ran on04/08; S-mix was distributed across01/03/04/08 as its final EMA sealed. '
        'The frozen seed/deck/seat schedule and per-seed shared reference are unchanged. '
        'The03 manager paused new claims while its56 existing children completed untouched; '
        'phase costs include parent/reaped/unreaped child CPU with recorded tick precision. '
        'After the complete-case gate, independent arm diagnostics run in parallel on '
        'home03 cores58/59/60 at nice19/SCHED_IDLE, scientific Torchthreads1, '
        'with unchanged per-arm calculations and bootstrap settings. '
        'No agreement metrics, CIs or kill decisions were computed before all final fits '
        'and all3232 reporting tasks completed. Immutable raw stage receipts retain their '
        'original input-freeze SHA; the final reducer view validates each stage input and '
        'checkpoint as a matching subset of the common final freeze and changes only the '
        'provenance envelope, retaining original stage and raw-case SHAs.', '',
        'Reporting uses the qualified E1 native f387b2d2..., as required by the frozen plan. '
        'The first startup used the generation native and failed before creating any games; '
        'its 1289.014866 CPU-seconds are included in reporting costs. '
        'A later stale internal01 stop blocked the first mix pool; all interrupted '
        'phase costs and completed human receipts were retained, and the exact '
        'unfinished mix identities resumed in a new phase under the same freezes. '
        'Corpus and fit pins '
        'remain unchanged. The dated reporting native amendment preceded all affected outcomes.', '',
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
    table(lines,['Arm / host(s)','Rows/s, full fit wall','GPU-hours, full fit wall','Optimizer GPU-hours',
        'Fit CPU-hours','Peak PSS GiB','Minimum GPU free GiB','Minimum MemAvailable GiB'],
        [[f"{arm} / {' → '.join(dict.fromkeys(s['host'] for s in f['segments']))}",f"{f['rows_per_second']:.2f}",f"{f['gpu_hours']:.6f}",
          f"{f['optimizer_gpu_hours']:.6f}",f"{f['cpu_hours']:.6f}",f"{f['max_pss_bytes']/2**30:.3f}",
          f"{f['min_gpu_free_bytes']/2**30:.3f}",f"{f['min_mem_available_bytes']/2**30:.3f}"] for arm,f in fit.items()])
    lines += ['The coordinator-directed loader6 operational amendment preserved all scientific '
        'rows, mixing order, seeds, cursor, losses and optimizer state. All three arms '
        'passed serial/parallel two-step train-only GPU replay with the model, EMA, '
        'optimizer, scheduler and all RNG states bit for bit equal before resuming. '
        'Complete human and teacher index vectors are rechecked at every prefetched '
        'production step. Actual workers6, scientific loader1, prefetch4, no random '
        'mmap advice; leased aggregate PSS guard46GB and home MemAvailable floor24GiB. Parent '
        'cores118/119/126, loader cores120–125; Torch scientific threads1. '
        'Periodic checkpoints200–250 steps, with final-step EMA selection unchanged.', '']
    table(lines,['Arm','Before rows/s, >5min','Before s/step','After rows/s, >5min',
                 'After s/step','Remaining fit ETA hours at measurement'],
        [[a,f"{performance['arms'][a]['before']['rows_per_second']:.2f}",
          f"{performance['arms'][a]['before']['seconds_per_step']:.6f}",
          f"{performance['arms'][a]['after']['rows_per_second']:.2f}",
          f"{performance['arms'][a]['after']['seconds_per_step']:.6f}",
          f"{performance['arms'][a]['eta_seconds']/3600:.3f}"] for a in ARMS])
    lines += ['GPU-hours use elapsed wall time while each GPU was allocated, including '
        'store preparation and batch gathering across all exact-state fit segments. Optimizer time is synchronized step '
        'wall time and is shown separately. Initial fits ran simultaneously on01/04/09, '
              'nice10, one GPU per arm. 09 used the versioned capture-extension supervisor '
              'with a live Oct11 lease, four declared processes and46GB PSS cap. '
        'S-human continued on owned08 from checkpoint108 after an attempted-step239 '
        'CUDA OOM on09;130 completed unsaved updates were archived and replayed. '
        'Owned08 reproduced the same OOM; checkpoint200 preserved92 useful updates, '
        'and38 additional unsaved updates were archived and replayed. '
        'Expandable allocation was then enabled for S-human after a dated operational '
        'amendment and a bit-exact two-step default/expandable replay from200. '
        'It failed at the same dense step239 allocation with a CUDA driver invalid-argument '
        'error; another38 updates were archived and replayed. S-human then resumed200 '
        'with default allocation and the separately dated micro3584 runtime amendment. '
        'An inherited46GB aggregate PSS guard then clean-saved232 on owned08 while '
        'MemAvailable remained115.7GB. A dated amendment scoped that PSS cap to leased '
        'hosts and retained the24GiB home memory floor; exact232 resumed without lost updates. '
        'Their GPU/CPU cost is included in the segment totals. S-mix completed '
        'step239 but stopped because the wrapper incorrectly applied the leased8GiB '
        'reserve to owned01; it resumed exactly after that guard scope was corrected. '
        'Owned GPUs have no leased8GiB reserve floor. No CPU simulation ran on leased '
        'hosts.08 joined reporting at nice19/SCHED_IDLE with48 physical workers, '
        'cores0/1 reserved and the existing cache service untouched.08 had an owned stop file and '
        'a five-minute reclaim bound.', '']
    table(lines,['Arm','Loader qualification GPU-hours','Qualification CPU-hours',
                 'Whole fitting window GPU-hours (includes restart gaps)'],
        [[a,f"{fit[a]['qualification_gpu_hours']:.6f}",f"{fit[a]['qualification_cpu_hours']:.6f}",
          f"{fit[a]['fitting_window_gpu_hours']:.6f}"] for a in ARMS])
    lines += [f"Separate allocator qualification: {receipt['allocator_qualification_gpu_hours']:.6f} "
              f"GPU-hours and {receipt['allocator_qualification_cpu_hours']:.6f} CPU-hours.", '']
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
         ['Loader6 operational amendment',receipt['loader_amendment_sha256']],
         ['Parent affinity operational amendment',receipt['parent_affinity_amendment_sha256']],
         ['Owned GPU migration operational amendment',receipt['owned_gpu_amendment_sha256']],
         ['Owned PSS guard scope operational amendment',receipt['owned_pss_scope_amendment_sha256']],
         ['S-human allocator operational amendment',receipt['allocator_amendment_sha256']],
         ['S-human micro3584 operational amendment',receipt['human_micro_amendment_sha256']],
         ['Staged reporting operational amendment',receipt['staged_reporting_amendment_sha256']],
         ['Reporting rebalance amendment',receipt['reporting_rebalance_amendment_sha256']],
         ['Parallel postprocessing amendment',receipt['postprocessing_amendment_sha256']],
         ['S-mix per-mode dispatch amendment',receipt['mix_dispatch_amendment_sha256']],
         ['Immutable raw case SHA manifest',receipt['staged_provenance']['raw_case_sha_manifest_sha256']],
         *[[stage+' reporting stage freeze',sha] for stage,sha in receipt['staged_provenance']['stage_freeze_sha256'].items()],
         ['Owned migration receipt',digest(job/'student-owned-migration.json')],
         ['Final reporting execution freeze',receipt['execution_freeze_sha256']],
         ['Aggregate metrics',receipt['aggregate_sha256']],
         *[[arm+' final step4883 EMA checkpoint',f['checkpoint_sha256']] for arm,f in fit.items()],
         *[[Path(name).name,sha] for name,sha in receipt['inputs'].items()]])
    human=fit['S-mix']['inputs']['pins']
    table(lines,['Fit input','SHA256'],[['Human train manifest',human['human_manifest']],
          ['Human parent manifest',prefit['human_inputs']['01']['parent_manifest_sha256']],
          ['Human dev manifest',prefit['human_inputs']['01']['dev_manifest_sha256']],
          ['Public mask',prefit['human_inputs']['01']['mask_sha256']],
          ['Public assets',human['assets']],['Common init checkpoint',human['init_checkpoint']]])
    lines += ['The pre-fit receipt also pins the human parent/dev manifests, publicmask, '
        'all training columns, the immutable runtime source files and init step/width. '
        'Qualified fitting runtime: NumPy2.3.5, Torch2.7.1+cu118. Frozen scientific code '
        'commits:39b6adf6 andf98d8926. Execution receipt commits: b6b39380, f48d865d, '
        'ee6baaad, 666dd205, b839f178 and620c79a2 (later completion commits are in repository history). '
        'Eight frozen tests passed, including real pack '
        'identity/tamper rejection and ratio0 equality to qualified T11.', '',
        'Technical setup retries occurred before fitting: self-SSH replaced by local '
        'copy, B4 modules overlaid from the unchanged frozen source, task-local GPU '
        'site-packages exposed, destination verifier made Python3.8 compatible, and '
        'instrumentation moved after the fresh-output check. The old09 supervisor '
        'refused before admission; the coordinator directed use of the existing '
        'Oct11 capture-extension wrapper. No global wrapper was edited. No sampling, '
        'optimizer/schedule, reporting seed, scientific source code or kill rule changed. The disclosed '
        'micro3584 operational amendment changes floating-point accumulation order. '
        'V3 retains a historical base runtime hash; the micro amendment and continuation '
        'receipt pin the actual amended runtime adapter.', '',
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
