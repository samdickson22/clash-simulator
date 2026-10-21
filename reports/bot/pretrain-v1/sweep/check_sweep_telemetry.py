"""Focused fail-closed checks of sweep_08's telemetry parsers (Sol R12). python3 check_sweep_telemetry.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sweep_08 as S

def bad(fn, text):
    try:
        fn(text)
    except S.Telemetry:
        return True
    return False

assert S.parse_apps('123, 10240\n456, 512\n') == {123: 10.0, 456: 0.5}
assert S.parse_apps('') == {}
for t in ('123, -10240', '123, nan', '123, inf', '123, [N/A]', 'abc, 10', '0, 10', '123, 1\n123, 2', '123'):
    assert bad(S.parse_apps, t), t
assert S.parse_total('49140\n') == 49140.0
for t in ('nan', '', '[N/A]', '1000', '999999'):
    assert bad(S.parse_total, t), t
assert S.parse_ps('  1     0 init\n 42 1 python3 x\n')[42] == (1, 'python3 x')
for t in ('', 'oops', '12 abc python', '12'):
    assert bad(S.parse_ps, t), t
print('telemetry parser checks: ok')
