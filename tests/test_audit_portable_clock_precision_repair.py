from __future__ import annotations

from scripts.audit_portable_clock_precision_repair import _distribution


def test_distribution_uses_conservative_observed_quantiles() -> None:
    result = _distribution([0.1, 0.2, 0.3, 0.4, 0.5])
    assert result["count"] == 5
    assert result["minimum"] == 0.1
    assert result["median"] == 0.3
    assert result["maximum"] == 0.5


def test_empty_distribution_fails_closed_without_invented_statistics() -> None:
    assert _distribution([]) == {"count": 0}
