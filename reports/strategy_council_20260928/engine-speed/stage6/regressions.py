"""Load the private extension before unittest discovery changes sys.path."""
import hashlib
from pathlib import Path
import unittest

import clasher_core

native = Path(clasher_core.__file__).resolve()
assert native.parent == Path(__file__).resolve().parent / 'native', native
print('private_native', native, hashlib.sha256(native.read_bytes()).hexdigest(), flush=True)
suite = unittest.defaultTestLoader.discover('engine-rs', pattern='test_stage4*.py')
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
