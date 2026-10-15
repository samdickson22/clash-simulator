import json,hashlib,os,sys
p=json.load(open("/mpac/sdicks02/repos/clasher-bot-runtime/r1/reports/explore/s1/receipts/runtime-pin.json"))
ns=p["native_source"]
for d in sys.argv[1:]:
    bad=[];
    for f,h in ns.items():
        q=os.path.join(d,f)
        if not os.path.exists(q): bad.append("MISSING:"+f); continue
        if hashlib.sha256(open(q,"rb").read()).hexdigest()!=h: bad.append("DIFF:"+f)
    extra=[]
    for r,ds,fs in os.walk(d):
        ds[:]=[x for x in ds if x not in ("target","__pycache__")]
        for x in fs:
            rel=os.path.relpath(os.path.join(r,x),d)
            if rel not in ns: extra.append(rel)
    print(d, "MATCH" if not bad else bad[:6], "extra:",extra[:8])
