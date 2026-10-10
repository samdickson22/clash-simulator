"""Admit corrected reporting only after four terminal, matched smoke cases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import socket
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', required=True)
    parser.add_argument('--reporting-job', required=True)
    args = parser.parse_args()
    assert socket.gethostname().split('.')[0] in ('127x01', '127x03')
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10 and os.sched_getscheduler(0) == os.SCHED_IDLE
    job, reporting = Path(args.job), Path(args.reporting_job)
    plan = read(job/'stage3-wrapper-qualification-plan-v2.json')
    harness = read(job/'stage3-harness.json')
    assert harness['kind'] == 'K1-vs-v1'
    assert sha(job/'stage3-harness.json') == sha(reporting/'stage3-harness.json') == plan['harness_receipt_sha256']
    assert sha(reporting/'ops/k_stage3_v2.py') == harness['adapter_sha256'] == plan['adapter_sha256']
    assert sha(reporting/'ops/game_worker_v2.py') == harness['reporting_worker_sha256']
    assert sha(reporting/'ops/game_pool_v2.py') == harness['reporting_pool_sha256']
    assert sha(reporting/'ops/reduce_stage3_v2.py') == harness['reducer_sha256']
    results, keys, meters = {}, {}, []
    for arm in ('init', 'smoke-student'):
        results[arm], keys[arm] = [], []
        for index in (2, 3):
            receipt = job/f'qualification-{arm}-{index}.json'
            result = read(receipt)
            case = job/'stage3/cases'/f'fallback-{arm}-{index:04d}.json'
            record = read(case)
            meter_path = job/f'qualification-meter-{arm}-{index}.json'
            meter = read(meter_path)
            assert meter['status'] == 'passed'
            assert result['passed'] and result['terminal'] and record['terminal']
            assert result['case_sha256'] == sha(case)
            assert result['adapter_sha256'] == record['adapter_sha256'] == plan['adapter_sha256']
            assert record['harness_sha256'] == plan['harness_receipt_sha256']
            assert record['seed'] == result['seed'] == 4503601527370496+index
            assert record['index'] == index and record['seat'] == index % 2 and record['arm'] == arm
            assert record['opponent'] == 'v1-policy' and record['own_fallback'] == 'released v1'
            checks = result['checks']
            assert checks['fallback_calls'] > 0 and checks['min_inference_offset_seconds'] >= 0
            assert (checks['proposal_calls'] == 0) if arm == 'init' else (checks['proposal_calls'] > 0)
            raw = job/'stage3/k-raw'/arm/'games'/f'sim-{index:04d}-d27-{arm}.json'
            assert sha(raw) == record['raw_game_sha256']
            keys[arm].append((record['seed'], record['seat'], record['own_deck'], record['opponent_deck']))
            results[arm].append(dict(receipt=str(receipt), receipt_sha256=sha(receipt), checks=checks))
            meters.append(dict(path=str(meter_path), sha256=sha(meter_path), **meter))
    assert keys['init'] == keys['smoke-student'], 'Smoke seed/deck/seat pairing differs'
    usage = resource.getrusage(resource.RUSAGE_SELF)
    summary = dict(passed=True, utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),
        adapter_sha256=plan['adapter_sha256'], harness_sha256=plan['harness_receipt_sha256'],
        qualifier_sha256=plan['qualifier_sha256'], seal_source_sha256=sha(__file__),
        contrast='student-hooked K1 versus v1 minus empty-hook K1 versus v1',
        opponent='v1-policy', own_fallback='released v1', search_players_per_game=1,
        search_threads=1, coarse_horizon=160, inference_after_wall0=True,
        scoring_cutoff_seconds=.192, paired_seeds=[x[0] for x in keys['init']],
        complete_terminal_games=4, exact_seed_deck_seat_pairs=2, results=results,
        smoke_meters=meters, smoke_cpu_hours=sum(x['cpu_seconds'] for x in meters)/3600,
        seal_cpu_seconds=usage.ru_utime+usage.ru_stime,
        reporting_games_consumed=0, interpretation='Mechanics qualification with v1 student stand-in; no arm survival decision.')
    (reporting/'stage3-wrapper-qualification-v2.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
