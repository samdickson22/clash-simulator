# pooled paired delta over seed pairs: per case mean over pairs of (a_i - b_i), bootstrap over cases
import sys, random
sys.path.insert(0, '/mpac/sdicks02/repos/clasher-bot')
from bot.exit.report import rows, opp, boot, fmt
pairs = [p.split(',') for p in sys.argv[2:]]   # each "A_SPEC,B_SPEC"
for o in sys.argv[1].split(','):
    per = {}
    for a, b in pairs:
        ta, tb = opp(rows(a), o), opp(rows(b), o)
        for i in set(ta) & set(tb):
            per.setdefault(i, []).append(ta[i] - tb[i])
    xs = [sum(v) / len(v) for v in per.values() if len(v) == len(pairs)]
    print(o, fmt(boot(xs)), 'n_cases', len(xs))
