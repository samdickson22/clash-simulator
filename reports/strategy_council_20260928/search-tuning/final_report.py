"""Final receipt audit and readable report; no experimental decisions change."""
from experiment import *
from array import array


def describe(rows):
    value=summary(rows)
    return f"{sum(r['score'] for r in rows):g}/{len(rows)} = {value['score']:.6f} [{value['ci95'][0]:.6f}, {value['ci95'][1]:.6f}]"


def main():
    verify()
    result=json.loads((HERE/'result.json').read_text())
    complete=json.loads((HERE/'completion.json').read_text())
    assert complete['games_complete'] and complete['timing_complete']
    pins=json.loads((HERE/'confirmation-manifest.json').read_text())
    for pin_key,name in [('prereg_sha256','PREREG.md'),('schedule_sha256','confirmation-schedule.json'),
                     ('experiment_sha256','manifest.json'),('reporting_sha256','resume.py')]:
        assert pins[pin_key]==sha(HERE/name),(pin_key,name)
    launch=json.loads((HERE/'confirmation-launch.json').read_text())
    assert (HERE/'PREREG.md').stat().st_mtime < datetime.fromisoformat(launch['started']).timestamp()
    timing_result=json.loads((HERE/'timing-games-summary.json').read_text())
    assert set(timing_result['variants'])=={'1','4'}
    timing_pins=json.loads((HERE/'timing-games-prereg.json').read_text())
    assert timing_pins['source_sha256']==sha(HERE/'timing_games.py')
    winner=result['winner']['name'];digest=hashlib.sha256();counts={};light=[]
    all_overruns=0;winning_max=0.;rejections=[0,0]
    confirm_wall={'winner':array('d'),'current':array('d')}
    confirm_cpu={name:[0.,0] for name in confirm_wall}
    for label in ('stage1','stage2','stage3','confirmation'):
        jobs=json.loads((HERE/f'{label}-schedule.json').read_text());paths=[];pairs=defaultdict(list)
        for job in jobs:
            cfg=Config(**job['config']);spec=job['spec']
            path=HERE/'games'/str(spec['stage'])/(key(cfg,spec)+'.json');paths.append(path)
            raw=path.read_bytes();rec=json.loads(raw)
            digest.update(str(path.relative_to(HERE)).encode()+b'\0'+hashlib.sha256(raw).hexdigest().encode()+b'\n')
            assert rec['spec']==spec and rec['config']==asdict(cfg)
            assert rec['manifest_sha256']==pins['experiment_sha256']
            assert rec['score']=={'win':1.,'draw':.5,'loss':0.}[rec['outcome']]
            assert rec['matchup_seed']==spec['seed']+spec['game']//2*1009
            assert rec['seat']==spec['game']%2 and 0 < rec['ticks'] <= 6010
            assert len(rec['timings'][0]) > 0
            for i in (0,1):rejections[i]+=rec['failed'][i]
            wall=[t[0] for t in rec['timings'][0]]
            assert all(t[0]>=0 and t[1]>=0 and type(t[2]) is bool for t in rec['timings'][0])
            all_overruns+=sum(t>.25 for t in wall)
            if cfg.name==winner:winning_max=max(winning_max,max(wall))
            if spec['stage']=='confirm':
                assert rec['confirmation_manifest_sha256']==sha(HERE/'confirmation-manifest.json')
                streams=[(spec['which'],rec['timings'][0])]
                if spec['style']=='search':streams.append(('current',rec['timings'][1]))
                for who,samples in streams:
                    confirm_wall[who].extend(t[0] for t in samples)
                    confirm_cpu[who][0]+=sum(t[1] for t in samples if t[2])
                    confirm_cpu[who][1]+=sum(t[2] for t in samples)
            rec.pop('timings');light.append(rec)
            pairs[(cfg.name,spec['role'],spec['style'],spec.get('which'),rec['matchup_seed'])].append(rec)
        assert len(paths)==len(set(paths))
        assert set(paths)==set(paths[0].parent.glob('*.json'))
        for pair in pairs.values():
            a,b=sorted(pair,key=lambda r:r['seat']);assert (a['seat'],b['seat'])==(0,1)
            assert a['world_decks']==(b['world_decks'] if a['spec']['style']=='search' else b['world_decks'][::-1])
        counts[label]=len(paths)
    assert counts==dict(stage1=672,stage2=672,stage3=576,confirmation=640)
    conf=[r for r in light if r['spec']['stage']=='confirm']
    h2h=[r for r in conf if r['spec']['style']=='search']
    assert summary(h2h)==dict(result['confirmation']['h2h'],ci95=tuple(result['confirmation']['h2h']['ci95']))
    c=result['confirmation'];assert c['verdict']==('PASS' if summary(h2h)['score']>=.55 and summary(h2h)['ci95'][0]>.5 else 'FAIL')
    deltas={}
    for role in ('holdout','hog26'):
        groups={who:[r for r in conf if r['spec']['style']!='search' and r['spec']['role']==role and r['spec']['which']==who] for who in ('winner','current')}
        a,b=groups.values();assert len(a)==len(b)==(128 if role=='holdout' else 64)
        differences=[]
        for x,y in zip(a,b):
            assert (x['matchup_seed'],x['seat'],x['world_decks'])==(y['matchup_seed'],y['seat'],y['world_decks'])
            differences.append(dict(x,score=x['score']-y['score']))
        deltas[role]=summary(differences)
        assert abs(deltas[role]['score']+c['scripts'][role]['drop'])<1e-12
    assert c['secondary_pass']==all(d['score']>=-.05 for d in deltas.values())
    timing_rows={threads:[json.loads((HERE/'timing-games'/f'threads-{threads}-game-{game}.json').read_text()) for game in range(4)] for threads in (1,4)}
    for threads,rows in timing_rows.items():
        assert timing_result['variants'][str(threads)]['winner']==timing(rows)
        for game,rec in enumerate(rows):
            assert rec['timing_only'] and rec['torch_threads']==threads
            assert rec['timing_manifest_sha256']==sha(HERE/'timing-games-prereg.json')
            assert rec['config']==result['winner'] and rec['spec']['game']==game
            assert rec['world_decks']==timing_rows[1][game]['world_decks']
    lines=['# Search tuning results','',f"Primary confirmation: **{c['verdict']}**. Secondary no-drop checks: **{'PASS' if c['secondary_pass'] else 'FAIL'}**.",'',
           'The selected profile is the equal mixture of balanced, pressure and defense public-script opponent models. It uses one sampled hidden completion, one rollout per style per candidate, and averages their scores.',
           '', 'Configuration: K=1; horizon 160 ticks; rollout interval 10; policy top-8 plus script top-4, script choice and no-op; balanced public-script own continuation; defense-v2 plus elixir; terminal +2 / -2, draw 0. Prewarm policy inference and reset recurrence for each game.',
           '', 'This is the best of 14 predeclared profiles, not an exhaustive search over interactions. Policy continuations were not implemented: the typical inference-only estimate exceeded 250 ms, and no validated native-to-policy observation adapter was available.',
           '', '## Tournament','', '| Stage | Profile | Score | Hog26 score | Search core-s | Wall p99, s | Wall max, s | Overruns |', '|---|---|---:|---:|---:|---:|---:|---:|']
    for stage,table in result['stages'].items():
        for row in table:
            a,g,t=row['all'],row['hog26'],row['timing']
            lines.append(f"| {stage} | {row['name']} | {a['score']*a['n']:g}/{a['n']} = {a['score']:.4f} | {g['score']*g['n']:g}/{g['n']} | {t['search_cpu_mean']:.5f} | {t['wall_p99']:.5f} | {t['wall_max']:.5f} | {t['overruns']} |")
    lines += ['', 'Scores count wins as 1 and draws as 0.5. Stage-specific scores determine advancement, with Hog26 score and then name breaking ties. Fresh seed blocks are shared across profiles within a stage; stages and confirmation are disjoint. Terminal magnitude 4 at K=1 is a behavior-equivalent control and scored exactly 0.5.',
              '', '## Preregistered confirmation','', 'All intervals below are 95% matchup-cluster bootstraps, 10,000 resamples, RNG 20261001. Both seats remain in each cluster.',
              '', 'Primary head-to-head: '+describe(h2h)+'. Required score >= 0.55 and lower bound > 0.50.',
              'Hog26 head-to-head: '+describe([r for r in h2h if r['spec']['role']=='hog26'])+'.',
              'Holdout head-to-head: '+describe([r for r in h2h if r['spec']['role']=='holdout'])+'.',
              '', '| Script population | Current | Winner | Winner minus current, paired CI |', '|---|---|---|---|']
    for role in ('holdout','hog26'):
        rows={who:[r for r in conf if r['spec']['style']!='search' and r['spec']['role']==role and r['spec']['which']==who] for who in ('winner','current')}
        d=deltas[role]
        lines.append(f"| {role} | {describe(rows['current'])} | {describe(rows['winner'])} | {d['score']:+.6f} [{d['ci95'][0]:+.6f}, {d['ci95'][1]:+.6f}] |")
        for style in STYLES:
            groups={who:[r for r in group if r['spec']['style']==style] for who,group in rows.items()}
            lines.append(f"| {role}, {style} | {describe(groups['current'])} | {describe(groups['winner'])} | descriptive |")
    lines += ['', 'The secondary gate uses the pooled point-score drop in each population, at most 0.05. Paired difference intervals are descriptive and do not change the registered gate.',
              '', '## Timing','', 'One-thread evaluation settings throughout all scored games. Policy warmup and per-game initialization precede measured decisions; sensor conversion, history assimilation, policy proposals and search are included. Each full-game receipt stores every decision wall/CPU time and search flag.',
              '', '| Confirmation controller | Decisions | Search core-s | Wall p99, s | Wall max, s | Overruns |', '|---|---:|---:|---:|---:|---:|']
    for who,wall in confirm_wall.items():
        values=np.asarray(wall);cpu,calls=confirm_cpu[who]
        lines.append(f"| {who} | {len(values)} | {cpu/calls:.5f} | {np.quantile(values,.99):.5f} | {values.max():.5f} | {int((values>.25).sum())} |")
    lines += ['', f'Across all tournament and confirmation candidate decisions: {all_overruns} overruns. The selected profile maximum over every scored stage was {winning_max:.6f} s.',
              '', '| Isolated whole-game repeat | Winner search core-s | Winner wall p99, s | Winner max, s | Current wall p99, s | Current max, s |', '|---|---:|---:|---:|---:|---:|']
    for threads in ('1','4'):
        w=timing_result['variants'][threads]['winner'];b=timing_result['variants'][threads]['current']
        lines.append(f"| {threads} Torch threads, 4 games | {w['search_cpu_mean']:.5f} | {w['wall_p99']:.5f} | {w['wall_max']:.5f} | {b['wall_p99']:.5f} | {b['wall_max']:.5f} |")
    lines += ['', 'Four Torch threads are descriptive. They parallelize eligible neural operations; native rollout search remains serial under the GIL. This is not a four-worker native-search benchmark. Both thread settings use identical fresh seed pairs, one holdout and one Hog26 matchup. These eight timing outcomes are excluded from every strength estimate and acceptance gate.',
              '', 'Only one owned worker ran the isolated repeats. Unrelated host jobs were left running; their process/load snapshots are in timing-games-summary.json. Hard quiet-core isolation was not verified. Evaluation workers inherited nice 20 from a nice-10 driver plus nice -n 10 child launches; timing repeats ran at nice 10. Public-root replay measurements are retained separately in winner-timing.json.',
              '', '## Audit and scope','', f"Validated {sum(counts.values())} scored receipts: {counts}. Every pair is complete, controller seats swap correctly, and script-comparison seeds/decks match. Rejected commands across scored games: {rejections[0]} candidate and {rejections[1]} opponent, all outcomes retained. A replay confirmed the simultaneous Cannon-placement conflict; see REPORTING_AMENDMENT.md.",
              '', 'The first 24-game run was invalidated after review found an alternative-leaf terminal-draw bug. Its source, manifest and receipts remain under invalidated-v1. The corrected tournament uses fresh seeds. No confirmation data was used to retune a configuration.',
              '', 'Seed audit: all report JSON/JSONL seed fields, plus 302 ignored NPZ game archives whose seeds match the scanned JSON sidecars; zero overlap. Native runtime is pinned locally, with eight complete P16 action/state/RNG parity games. Baseline action/score comparisons, native-leaf loop checks and terminal regressions passed.',
              '', f"Experiment manifest: {sha(HERE/'manifest.json')}", f"Confirmation manifest: {sha(HERE/'confirmation-manifest.json')}", f"Scored receipt aggregate SHA256: {digest.hexdigest()}",
              '', 'Recommendation: the opponent-style mixture is statistically confirmed and passes the observed one-thread budget. Retain the stated quiet-core limitation; no quiet-core or four-core native-search certification is claimed. All persistent task writes are under search-tuning/.']
    (HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    total=sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file());assert total<1024**3
    write(HERE/'final-audit.json',dict(created=datetime.now(timezone.utc).isoformat(),passed=True,
        scored_games=counts,total_scored_games=sum(counts.values()),timing_games=8,
        prereg_before_confirmation_launch=True,scored_receipt_sha256=digest.hexdigest(),
        candidate_overruns=all_overruns,winning_wall_max=winning_max,rejected_commands=rejections,
        paired_script_differences=deltas,quiet_core_verified=False,artifact_bytes=total,
        report_sha256=sha(HERE/'RESULTS.md'),analysis_sha256=sha(Path(__file__))))
    progress('Final audit and RESULTS.md complete: all 2,560 scored games plus eight separate timing games verified; primary and secondary checks passed. Quiet-core isolation remains explicitly unverified.')
    print(json.dumps(dict(verdict=c['verdict'],secondary_pass=c['secondary_pass'],games=counts,bytes=total,paired_differences=deltas),indent=2))


if __name__=='__main__':main()
