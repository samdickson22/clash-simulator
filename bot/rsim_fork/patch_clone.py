"""Apply the Clasher in-memory clone patch to a RoyaleSim checkout (MIT; upstream RoyaleGym/RoyaleSim @ ffe0d27, 0.1.34).

    python patch_clone.py /path/to/RoyaleSim
"""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / "crates/royalesim/src/py.rs"
s = p.read_text()
head = '#[pyclass(module = "royalesim")]\npub struct Battle {'
assert s.count(head) == 1, "pyclass anchor"
s = s.replace(head, '// Clasher fork (2026-10-14): Clone added for an in-memory branch primitive; see clone()/restore_from().\n'
              '#[pyclass(module = "royalesim")]\n#[derive(Clone)]\npub struct Battle {')
anchor = "#[pymethods]\nimpl Battle {\n"
assert s.count(anchor) == 1, "pymethods anchor"
s = s.replace(anchor, anchor + '''    /// Clasher fork: an exact in-memory copy of this battle (BattleState is plain owned data; the card
    /// table is shared through its Arc). The copy steps identically to the original.
    #[pyo3(name = "clone")]
    fn py_clone(&self) -> Battle {
        Clone::clone(self)
    }

    /// Clasher fork: overwrite this battle's state with a copy of `other`'s. Both must have been built with the
    /// same card names and overrides (only the catalogue is checked).
    fn restore_from(&mut self, other: PyRef<'_, Battle>) -> PyResult<()> {
        if other.catalogue != self.catalogue {
            return Err(PyValueError::new_err("restore_from: catalogues differ"));
        }
        self.state = other.state.clone();
        self.step_commands.clear();
        Ok(())
    }

''')
p.write_text(s)
print("patched", p)
