"""Run prior R33/R34 cases and R35 validation without changing reviewer artifacts.

All writes and harmless child fixtures stay in this checkout. R35's failure probes
are retained with fixed expectations in test_lease_supervisor_r35.
"""
import json
from pathlib import Path
import runpy
import sys


def main():
    tests = Path(__file__).resolve().parent
    prior = runpy.run_path(str(tests/'r34_fix_probe.py'), run_name='r34_fix_import')
    if prior['main'](): return 1
    validation = runpy.run_path('/mpac/sdicks02/scratch/pretrain-v1-dev/review/SOL-R35-validation.py',
                                run_name='r35_validation_import')
    # The prior runner already executes the ten R34 positive groups.
    validation['parser_cases']()
    validation['before_spawn_gate']()
    for point in ('during', 'after'):
        for fail_save in (False, True): validation['real_admission_race'](point, fail_save)
    print(json.dumps(dict(runtime=sys.version, r35_validation=validation['RESULT']['cases']), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
