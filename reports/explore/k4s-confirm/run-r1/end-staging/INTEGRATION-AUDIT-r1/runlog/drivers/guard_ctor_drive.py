# AUDIT driver: FROZEN fleet_validity.ReportingGuard(bundle, manifest, owned) constructor + check_admissions on the
# fake host's staged bundle and staged S3 guard job (unmodified frozen code; no __call__, no process sampling).
import json, sys
RT = "/mpac/sdicks02/jobs/clasher/k4s-end-r1/runtime-98566c032d0b"
sys.path.insert(0, RT + "/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3")
import fleet_validity
bundle = "/mpac/sdicks02/jobs/clasher/k4s-end-r1/bundles/end-ref-127x03-pf00"
m = json.load(open(bundle + "/tiers-pins.json"))
g = fleet_validity.ReportingGuard(bundle, m, owned=None)
print("ReportingGuard constructed; job", g.job, "admissions", sorted(g.admissions), "seed deps", len(g.seed_dependencies))
