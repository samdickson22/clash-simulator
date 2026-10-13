import json,sys
r=json.load(open(sys.argv[1]))
print({k:r.get(k) for k in ("passed","mode","qualifying","failed_checks")})
for c in r["checks"]: print(" ", c.get("name"), "PASS" if c.get("passed") else ("SKIP" if c.get("skipped") else "FAIL"), (c.get("error") or c.get("reason") or "")[:400].replace("\n"," | "))
