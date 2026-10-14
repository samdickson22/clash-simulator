set -e
date -u +"start %FT%TZ"
cp -a /mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-98566c032d0b/runtime /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/base/runtime-98566c032d0b
mkdir /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/base/runtime-98566c032d0b/reports/strategy_council_20260928/engine-speed/results
date -u +"runtime %FT%TZ"
cp -a /mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/native/clasher_core.abi3.so /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/base/end-inputs-r1/
cp -a /mpac/sdicks02/jobs/clasher/t1-20261010-r1/corpus-publication-staging-r1/K4-states.pkl /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/base/end-inputs-r1/
date -u +"inputs %FT%TZ"
cp -a /mpac/sdicks02/k4s-runner/run-r1/end-staging/bundles/end-ref-127x03-pf00 /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/base/bundles/end-ref-127x03-pf00
date -u +"bundle %FT%TZ"
