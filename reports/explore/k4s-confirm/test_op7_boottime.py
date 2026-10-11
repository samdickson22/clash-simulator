"""Host-independent run of T1's test_op7::test_fresh_reaps_cannot_renew_stale_orphan_debt (T1 bytes unchanged).

The T1 fixture hard-codes process start_ticks=145613425 (about 16.85 days at HZ 100), while the meter classifies
processes against the live CLOCK_BOOTTIME. The original therefore passes only on hosts up longer than about
16.85 days (127x03 at 17.5 d passes; 127x04 at 12.7 d fails with 15100 != 7700). This runs the identical T1 test
function with CLOCK_BOOTTIME pinned to 2,000,000 s (about 23 days). qualify.sh deselects the two
host-dependent originals and runs this instead (disclosed deviation; guard code unchanged).
"""
import time
import pytest
import test_op7 as T


@pytest.mark.parametrize('module,budget_key', [(T.A, 'apt_budget'), (T.B, 'ssh_budget')])
def test_fresh_reaps_cannot_renew_stale_orphan_debt_pinned_boottime(module, budget_key, monkeypatch):
    real = time.clock_gettime
    monkeypatch.setattr(time, 'clock_gettime', lambda c: 2_000_000.0 if c == time.CLOCK_BOOTTIME else real(c))
    T.test_fresh_reaps_cannot_renew_stale_orphan_debt(module, budget_key)
