"""An absent or fitting-authorized evaluation pin must fail before data access."""

import pytest
from diagnostic_data import load_diagnostic


def test_missing_authority_refuses_before_loader_import():
    for pin in ({}, {'schema': 'clasher.hog26.expanded-value-diagnostic.v1', 'fitting': True, 'all_fits_reviewed': True},
                {'schema': 'clasher.hog26.expanded-value-diagnostic.v1', 'fitting': False, 'all_fits_reviewed': False},
                {'schema': 'clasher.hog26.expanded-value-diagnostic.v1', 'fitting': False, 'all_fits_reviewed': True, 'fits': 16, 'acceptance': False}):
        with pytest.raises(ValueError, match='authority'):
            load_diagnostic(verified_pin=pin)
