import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "first_module",
    ("clasher.spells", "clasher.dynamic_spells"),
)
def test_spell_modules_load_in_either_import_order(first_module):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                f"import {first_module}; "
                "from clasher.dynamic_spells import load_dynamic_spells; "
                "from clasher.spells import SPELL_REGISTRY; "
                "assert SPELL_REGISTRY['Fireball'].name == 'Fireball'; "
                "assert load_dynamic_spells()['Fireball'].name == 'Fireball'"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
