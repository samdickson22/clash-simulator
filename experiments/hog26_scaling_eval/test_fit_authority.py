import pytest
from fit_authority import pin_fits


def test_incomplete_scaled_fits_refused_before_any_diagnostic_data(tmp_path):
    with pytest.raises(ValueError,match='all scaled fits must complete'):
        pin_fits(tmp_path)
