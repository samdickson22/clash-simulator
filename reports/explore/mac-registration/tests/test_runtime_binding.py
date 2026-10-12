"""A4 erratum E3: END-A5 pins = committed END-A3 manifest with only fleet_validity.py replaced per T1's diff."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import macreg_io as io

NEW = "0775b704905324d70f9a43bc580bcbba1548cb2d2a4835c84ff61a0d8b64ae0f"


def fixture():
    runtime = {"a/%04d.py" % i: "%064x" % i for i in range(3784)}
    runtime[io.FLEET_VALIDITY_REL] = "9" * 64
    measurement = {"fleet_validity.py": "9" * 64, "tier_backend.py": "1" * 64}
    diff = dict(status="ADOPTED", A5_adopted=True, adopted_commit="8799a0d6", A3_runtime_3785_diff_entries=[io.FLEET_VALIDITY_REL],
                measurement_files18_diff_entries=["fleet_validity.py"], native_unchanged=io.NATIVE_SHA256[:8],
                fleet_validity_sha256=NEW, full_18_inventory=dict(measurement, **{"fleet_validity.py": NEW}))
    return dict(runtime_files=runtime, measurement_files=measurement), diff


class A5Binding(unittest.TestCase):
    def test_single_entry_replaced(self):
        manifest, diff = fixture()
        runtime, measurement = io.a5_expected(manifest, diff)
        self.assertEqual(runtime[io.FLEET_VALIDITY_REL], NEW)
        self.assertEqual(measurement["fleet_validity.py"], NEW)
        changed = [k for k in runtime if runtime[k] != manifest["runtime_files"][k]]
        self.assertEqual(changed, [io.FLEET_VALIDITY_REL])
        self.assertEqual(manifest["runtime_files"][io.FLEET_VALIDITY_REL], "9" * 64)  # input not mutated

    def test_fails_closed(self):
        for mutate in (lambda m, d: d.update(status="DRAFT"),
                       lambda m, d: d.update(A3_runtime_3785_diff_entries=[io.FLEET_VALIDITY_REL, "x.py"]),
                       lambda m, d: d.update(measurement_files18_diff_entries=["fleet_validity.py", "tier_backend.py"]),
                       lambda m, d: d.update(native_unchanged="00000000"),
                       lambda m, d: d["full_18_inventory"].update(**{"tier_backend.py": "2" * 64}),
                       lambda m, d: m["runtime_files"].pop(io.FLEET_VALIDITY_REL)):
            manifest, diff = fixture()
            mutate(manifest, diff)
            with self.assertRaises(ValueError):
                io.a5_expected(manifest, diff)


if __name__ == "__main__":
    unittest.main()
