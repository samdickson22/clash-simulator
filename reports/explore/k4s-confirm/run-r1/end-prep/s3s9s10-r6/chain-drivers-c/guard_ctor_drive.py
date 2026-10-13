# r4 CHAIN-c (IR-03; from the audit's guard_ctor_drive.py): the FROZEN fleet_validity.ReportingGuard constructor +
# check_admissions (unmodified frozen code from the staged runtime copy; no __call__, no sampling) on the fake 03.
# argv: RUNTIME BUNDLE CASE [JOB]; CASE ir03 = the bundle's guard admissions minus idle-services.json (the b3-r7 shape,
# SIMULATED in-memory: the files map is unchanged); orig = the b3-r6 manifest as built (03 idle pinned).
import copy, json, sys
RT, bundle, case = sys.argv[1:4]
sys.path.insert(0, RT + "/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3")
import fleet_validity
m = json.load(open(bundle + "/tiers-pins.json"))
if case != "orig":
    m = copy.deepcopy(m)
    m["reference_load_profile"]["guard"]["admissions"].pop("idle-services.json", None)
if len(sys.argv) > 4:
    m["reference_load_profile"]["guard"]["job"] = sys.argv[4]
try:
    g = fleet_validity.ReportingGuard(bundle, m, owned=None)
    print("GUARD_OK job", g.job, "admissions", sorted(g.admissions), "seed deps", len(g.seed_dependencies))
except Exception as e:
    print("GUARD_REFUSED", type(e).__name__, str(e)[:300]); sys.exit(3)
