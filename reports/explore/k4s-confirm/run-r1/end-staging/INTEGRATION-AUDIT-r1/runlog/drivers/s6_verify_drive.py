# AUDIT driver: S6 verifier verify() (scratch copy, unmodified) called the way its tests call it, on the fake 05, with
# a launch-receipt dict shaped like S7's (launched=True for this audit: the real gate refused only on environment
# artifacts) and `now` = exit + 1300 s + 1 (documented test hook; C-d).
import importlib.util, json, sys, datetime
spec = importlib.util.spec_from_file_location("k4s_end_verify_push", "/dev/shm/ia-r1/code/s5s6s7-r3/k4s_end_verify_push.py")
V = importlib.util.module_from_spec(spec); sys.modules["k4s_end_verify_push"] = V; spec.loader.exec_module(V)
root, argv_json, detach_json, exit_json = sys.argv[1:5]
argv = json.load(open(argv_json)); det = json.load(open(detach_json)); ex = json.load(open(exit_json))
launch = dict(schema="clasher.k4s.end-launch-receipt.v2", kind="end", host="127x03", job=argv[12],
              attempt=argv[12].rsplit("/", 1)[1], launched=True, utc=det["launched_at_utc"],
              wrapper_sha256=V.WRAPPER_SHA256, measurement_argv=argv[13:], _sha256="0" * 64)
si = V.load_si()
prepared = json.load(open(root + "/PREPARED.json"))
now = V.utc_epoch(ex["utc"]) + V.C_D_SECONDS + 1
print(json.dumps(V.verify(si, root, launch, prepared, now), sort_keys=True))
