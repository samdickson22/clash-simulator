# R8 slot-permission source checks

The planner now restricts each current physical card slot using explicit, fresh screen-derived permission while retaining the original native action mask as a model feature. The unchanged final tap guard still enforces every submitted play. Historical R5 3/22, R6 15/42 and s40 4/28 refusal gates remain failed.

Run with Python >=3.10 and numpy from a checkout containing this exact source:

```sh
python -B reports/live/loop/r8-checks/tests/run_all.py --output /tmp/unique-r8-check
```

The `candidate` symlink refers to this checkout's production sources. The tests and baseline/field fixtures are the exact independently reviewed portable suite; source pins in MANIFEST.json verify the checked files before and after execution. Baselines are immutable legacy/negative controls, not runtime selections. Fixture JSON contains only screen-derived game data. Tests use actual source AST with explicit fake model/native/I/O leaves: 196 backend/main integration checks, producer cases, and 63 freshness controls. They do not establish actual neural ranking, native execution, performance, strength or live acceptance.

The canonical port preserves main's level/full-pool root hooks and content-keyed worker config transport. REVIEW.txt records fresh independent GO and prior F1/F2 producer fixes. Fourteen production paths change; handread is an unchanged closure pin. ROLLBACK.json is SOURCE rollback only. Actual-host fifteen-file package and fourteen-original rollback remain separately pinned; canonical lopp_fast/players differ from host candidates. Do not install this source checkout as that host profile.

Publication grants no host installation, driver restart, hold clearance, model/runtime/pin change or play. NO DRIVER, validation PAUSE and LL_HANDSYNC=0 on any separately authorized fallback remain; restored r4 must never enable HANDSYNC. New host installer review/dry run, coordinated actual-base guards/paired rollback and separate live authority remain required.
