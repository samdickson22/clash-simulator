set -e
cd /mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-98566c032d0b/runtime && find . -type f -print0 | sort -z | xargs -0 -P8 -n50 sha256sum | sort -k2 > /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/logs/sha-runtime-src.txt
cd /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/base/runtime-98566c032d0b && find . -type f -print0 | sort -z | xargs -0 -P8 -n50 sha256sum | sort -k2 > /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/logs/sha-runtime-copy.txt
cd /mpac/sdicks02/k4s-runner/run-r1/end-staging/bundles/end-ref-127x03-pf00 && find . -type f -print0 | sort -z | xargs -0 -P4 -n1 sha256sum | sort -k2 > /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/logs/sha-bundle-src.txt
cd /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/base/bundles/end-ref-127x03-pf00 && find . -type f -print0 | sort -z | xargs -0 -P4 -n1 sha256sum | sort -k2 > /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/logs/sha-bundle-copy.txt
sha256sum /mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/native/clasher_core.abi3.so /mpac/sdicks02/jobs/clasher/t1-20261010-r1/corpus-publication-staging-r1/K4-states.pkl > /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/logs/sha-inputs-src.txt
sha256sum /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/base/end-inputs-r1/clasher_core.abi3.so /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/base/end-inputs-r1/K4-states.pkl > /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/logs/sha-inputs-copy.txt
diff /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/logs/sha-runtime-src.txt /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/logs/sha-runtime-copy.txt && echo RUNTIME_MATCH
diff /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/logs/sha-bundle-src.txt /mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1/logs/sha-bundle-copy.txt && echo BUNDLE_MATCH
echo DONE
