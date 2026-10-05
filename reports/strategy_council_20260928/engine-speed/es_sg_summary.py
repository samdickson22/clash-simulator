import json, glob, os
from es_common import RESULTS
for p in sorted(glob.glob(str(RESULTS / "simplegym_*.json"))):
    d = json.load(open(p))
    t = d.get("trials", [])
    if d.get("skipped"): print(os.path.basename(p), "SKIPPED"); continue
    print(os.path.basename(p), "median row-ticks/s %.1f" % d["median"]["row_ticks_per_second"],
          "digests_equal", len({x.get("digest") for x in t}) == 1,
          "peak_dev_mem", max((x.get("peak_device_memory_bytes") or 0) for x in t) / 2**30 if t else None)
