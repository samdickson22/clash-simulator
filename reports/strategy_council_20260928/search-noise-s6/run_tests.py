import bootstrap
import unittest
names=['test_tracker_v2','test_tracker_v3','test_v3_mass','test_recovery','test_delay']
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
raise SystemExit(0 if result.wasSuccessful() else 1)
