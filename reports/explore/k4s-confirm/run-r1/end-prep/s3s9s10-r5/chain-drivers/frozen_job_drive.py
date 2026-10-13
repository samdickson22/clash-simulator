# AUDIT driver: the FROZEN end_evidence / end_job / producer_claim (runtime copy, read-only, unmodified) against the
# scratch clone at the synthetic END-JOB commit; the claim lands in the scratch clone's work tree only.
import sys, json, hashlib
RT = sys.argv[1]
sys.path[:0] = [RT + "/reports/explore/k4s-confirm/mac", RT + "/reports/explore/k4s-confirm",
                RT + "/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"]
import end_evidence as E, fleet_end
repo = sys.argv[2]
evp = sys.argv[3]
evsha = hashlib.sha256(open(evp, "rb").read()).hexdigest()
ev = E.end_evidence(evp, evsha, repo, fleet_end)
print("end_evidence OK", ev["counted_hosts"], ev["plan_sha256"][:12], ev["completion_sha256"][:12])
jobsha = hashlib.sha256(open(repo + "/reports/explore/k4s-confirm/end/END-JOB.json", "rb").read()).hexdigest()
job = E.end_job(repo, ev, jobsha, "74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357")
print("end_job OK commit", job["commit"], "sha", jobsha[:12])
d, names = E.producer_registry(repo, job, 0, "127x03")
print("producer_registry OK", d, names)
if "--claim" in sys.argv:
    claim, csha = E.producer_claim(repo, job, 0, "127x03", "/x/attempts/end-127x03-r00-l00/end-127x03-r00-l00")
    print("producer_claim OK", json.dumps(claim, sort_keys=True), csha[:12])
