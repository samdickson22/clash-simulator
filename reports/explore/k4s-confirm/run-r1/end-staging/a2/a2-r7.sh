#!/bin/bash
# K4S END A2 (staging) for ONE host: S10 run A (base, runtime, tools, end-inputs, pf00 bundle + guard job),
# run B (rd00-a00), run C (rd00-a01), then S11 provision (repository at P' on k4s-end-r1). Stops at the first nonzero rc.
# Usage: a2.sh HOST GO_REF     (HOST = 127x03 | 127x04; run 03 to completion before 04)
set -u; H=$1; GO=$2
E=/mpac/sdicks02/k4s-runner/run-r1/end-prep; S=/mpac/sdicks02/k4s-runner/run-r1/end-staging; PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python; P=98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb; RM=9d6ab1f7386894727035c14a95c518b54e9472c9cb90eb6d023c589fe2269b43
case $H in 127x03|127x04) ;; *) echo bad host; exit 2;; esac
for d in s3s9s10-r7 s5s6s7-r6; do (cd $E/$d && sha256sum -c --quiet SHA256SUMS) || { echo "SHA256SUMS $d FAILED"; exit 2; }; done
[ "$(sha256sum $S/runtime-98566c032d0b/runtime-manifest.json | cut -c1-64)" = "$RM" ] || { echo runtime manifest differs; exit 2; }
TP_03_pf00=5082e8b21f687c7e92af9e93ed5c1b0c21e9af858ad3ab90955ed49e07fd1b03; RC_03_pf00=c0874a6f6a33dc17a166e2fde415b3a22947f849f00868ac582f82a73700535a; GM_03_pf00=a068acdd508b5da79fa5b786784c98215ff5bae7e2bb0b283c0fc7ec18c2ff50
TP_03_rd00_a00=39e3f2566a2dd528053101f982934898f24821ba58db6d960a92e4a0ca428070; RC_03_rd00_a00=49b96b98bc65a9f27adfa65c46b51620f27189fa1ac74c5432a4fba30f5ab857; GM_03_rd00_a00=86e396c05912ea7ba737c01a798dd0fef369469c7d289044dcea3c87519743a9
TP_03_rd00_a01=03b8f52e08447141cb436fcd683867376ca482bf7689eb1550d7d0380f825fc5; RC_03_rd00_a01=7e0814a7afb54e264135052aed3c6f3d277aab74cdc70cfed13004b954b1c173; GM_03_rd00_a01=ec474156bab1564d315d8c61aba84f75ee0dbe3e072d415181383acde9bfab6e
TP_04_pf00=fd8c9ee5e8fc262f49f17961b62668b2daa156e1c49bfbc26be93754e00faa0f; RC_04_pf00=9fc01c8053e958e637a34de44fed1123ae53b88aaec6aa5c4ea66fd7a3883729; GM_04_pf00=8eb50146d98b726d6be75839d5e9dd394cbde7cef254da9f8d9e52aa2c7bacde
TP_04_rd00_a00=2fb48c3e71ca4dbc6be3300cf557eba94d0f6eab36d994385ef1ac7d92f2fb6e; RC_04_rd00_a00=ce9d6c2a8ce75132bb1ef4cd0c536731cb1e3bec71d73ce7acda3473806a63d5; GM_04_rd00_a00=065e1a10fdd15f9a34e05c35449d007aa996d12ebafc7e2f6376bca29dfeb3d9
TP_04_rd00_a01=d1292b2eff22e2449237187d6bc8d8dc45e623d43f164bd639a920a549d2a458; RC_04_rd00_a01=f563d2c05e69e066f2c5d64e0ad451d1abe5b3619f55d5df024a7f133c9502ad; GM_04_rd00_a01=5c391e34b602a20bc7c8ef7a2bc4abd6041d56f06cef1ebbbe4dd3a0a0e663ac
X=${H#127x}; cd /tmp; umask 022
run(){ echo "__START $1 $(date -u +%FT%TZ)"; env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 "${@:2}"; rc=$?; echo "__RC $1 $rc $(date -u +%FT%TZ)"; [ $rc -eq 0 ] || exit $rc; }
for t in pf00 rd00-a00 rd00-a01; do v=${t//-/_}; tp=TP_${X}_$v; rc=RC_${X}_$v; gm=GM_${X}_$v
  if [ $t = pf00 ]; then first=(--create-base --runtime $S/runtime-98566c032d0b --runtime-manifest-sha256 $RM --tools-source $E/s5s6s7-r6 --end-inputs); else first=(--runtime-manifest-for-checks $S/runtime-98566c032d0b --runtime-manifest-sha256 $RM); fi
  run s10-$t $PY -I -B $E/s3s9s10-r7/s10_stage_host.py --host $H "${first[@]}" --bundle $S/bundles/end-ref-$H-$t ${!tp} ${!rc} --guard-job $S/guard-jobs/guard-$H-$t --guard-job-name k4s-end-guard-r1-$t --guard-manifest-sha256 ${!gm} --record $S/a2/s10-$H-$t-r2 --outside-end-window "A2 GO $GO, $(date -u +%FT%TZ)"
done
run s11-provision $PY -I -B $E/s3s9s10-r7/s11_host_repository.py provision --host $H --commit $P --record $S/a2/s11-$H-provision-r2 --outside-end-window "A2 GO $GO, $(date -u +%FT%TZ)"
echo "__A2_DONE $H $(date -u +%FT%TZ)"
