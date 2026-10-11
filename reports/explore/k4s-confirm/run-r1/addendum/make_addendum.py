"""Build the K4S launch freeze addendum (md + json) from on-disk bytes. Outcome-blind; reads no game file."""
import hashlib,json,subprocess,sys
from pathlib import Path
L=Path('/mpac/sdicks02/k4s-runner/run-r1');R='reports/explore/k4s-confirm/run-r1'
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
verdict=sys.argv[1];final_review=sys.argv[2];minor_fix=sys.argv[3] if len(sys.argv)>3 else None   # e.g. APPROVE reviews/SOL-REVIEW-OA1-B2-r5.md
utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
files={f'{R}/oa1/mirror_k4s.py':L/'oa1/mirror_k4s.py',f'{R}/oa1/test_mirror_k4s.py':L/'oa1/test_mirror_k4s.py',
       f'{R}/oa1/build_job_manifest.py':L/'oa1/build_job_manifest.py',f'{R}/oa1/FROZEN-K4S.json':L/'oa1/FROZEN-K4S.json',
       f'{R}/tools/k4s_health.py':L/'tools/k4s_health.py'}
reviews={f'{R}/reviews/{p.name}':p for p in sorted((L/'reviews').glob('*.md'))}
rec=dict(schema='clasher.k4s.launch-addendum.v1',study='PREREG-K4S',composed_utc=utc,freeze_commit='391d2006acc5c70f42679d7f014b84bc9fe0c2f9',fill_commit='fab6e03ff33f33ee0956e2db02d25f2fe66014c5',
 coordinator_thread='0523ae6f-baa3-4d4e-b233-b392671670db',outcomes_sealed=True,frozen_bytes_changed=False,
 oa1=dict(ruling='2026-10-11T18:00Z (COORDINATOR.md 3badf70d): hub 127x05 owned copier supersedes r3 4.4 hub-01 wording for K4S',
   r4_r5_rulings=['2026-10-11T19:07Z r4 authorized','2026-10-11T19:19Z r5 no-signal design authorized; 10-min lock timeout = stop for manual handling'],
   script_sha256=h(L/'oa1/mirror_k4s.py'),tests_sha256=h(L/'oa1/test_mirror_k4s.py'),binding_review=dict(path=f'{R}/{final_review}',sha256=h(L/final_review),verdict=verdict,minor_fix_note=dict(path=f'{R}/{minor_fix}',sha256=h(L/minor_fix)) if minor_fix else None),review_rounds='r1-r6 REJECT (all findings resolved), r7 APPROVE_WITH_FIXES (MINOR 13 fixed as prescribed)',commit='6ac7b64166a8506ac535cd21e1b061a239b08d99'),
 b2=dict(ruling='2026-10-11T18:00Z (3badf70d)',commit='6ac7b64166a8506ac535cd21e1b061a239b08d99',sol='compatible with frozen barrier.reporting_release and parent_source_seed.admit in r1-r7 (byte-for-byte reproduction)',manifest_path=f'{R}/oa1/FROZEN-K4S.json',manifest_sha256=h(L/'oa1/FROZEN-K4S.json'),builder_sha256=h(L/'oa1/build_job_manifest.py'),mac_manifest_pinned='d89cab16 (391d2006 bytes; fleet runtime)'),
 b4='03/04: 391d2006 objects fetched by SHA into /mpac/sdicks02/repos/clasher (FETCH_HEAD only); PREREG r3 bytes 9650972d copied into each staged repo (frozen barrier prerequisites)',
 amendment_1=dict(commit='45f32c0f',amended_mac_manifest='8bb20a753bdb8f5f606ea2288336b1350f96a5199d158b2b8750317c26493009',binding='fleet reporting keeps d89cab16 (391d2006 bytes); END and Mac sessions only from a separate amended tree naming 8bb20a75; no END declaration may name d89cab16'),
 idle_service_03=dict(ruling='2026-10-11T18:22Z (d999d016)',pid=2180947,start_ticks=139691386,cmdline_sha256='16152ceb7942621141a2d8d91189affdeacde28ad1a9059ffbadde5e9bde799a',note='frozen idle_services.py pin; equals T1 committed pin; >1% core or new child flags blocks, never stops'),
 smoke_freeze_sha_disclosure=dict(ruling='2026-10-11T18:48Z (f442b968)',text='frozen run.py stamps freeze_manifest_sha256 = sha256(FROZEN-K4S.json) whenever the job manifest exists, so excluded smoke games carry the manifest SHA; K4S-SPEC 5 says null in qualification and smoke; accepted, no frozen byte changed'),
 stop_drill=dict(ruling='2026-10-11T18:48Z (f442b968)',receipt=f'{R}/receipts/stop-drill.json',sha256=h(L/'receipts/stop-drill.json')),
 launch_qualification={x:dict(path=f'{R}/receipts/launch-qualification-{x}.json',sha256=h(L/f'receipts/launch-qualification-{x}.json')) for x in ('127x03','127x04')},
 dispatch=dict(smoke=dict(path=f'{R}/dispatch/smoke-dispatch.json',sha256=h(L/'dispatch/smoke-dispatch.json')),reporting=dict(path=f'{R}/dispatch/reporting-dispatch.json',sha256=h(L/'dispatch/reporting-dispatch.json'),blocks=3900,games=33000)),
 end_prep='K4-states.pkl a97b1fbf + corpora.json 3501e2ac (= git 81f2483e) copied read-only (0444, SHA-verified) from the 05 bundle into <job>/end-corpus on 03/04; END only in the coordinator-declared window from a separate amended tree',
 files={k:h(v) for k,v in files.items()},reviews={k:h(v) for k,v in reviews.items()})
(L/'addendum/K4S-LAUNCH-ADDENDUM.json').write_text(json.dumps(rec,indent=1)+'\n')
md=f"""# PREREG-K4S launch freeze addendum (run r1)

- Composed {utc} (`date -u`) by the K4S runner r1 (Claude Opus 5.5, 127x05) for coordinator 0523ae6f. Machine-readable twin: `K4S-LAUNCH-ADDENDUM.json`.
- **No frozen byte changed** (freeze 391d2006, fill fab6e03f). Outcomes SEALED; nothing here reads a game outcome.

| Item | Binding |
|---|---|
| OA-1 hub copier (coordinator 18:00Z, 3badf70d; r4 19:07Z, r5 19:19Z) | `oa1/mirror_k4s.py` `{rec['oa1']['script_sha256']}`; tests `{rec['oa1']['tests_sha256']}`; binding GPT-6.1-Sol review `{final_review}` **{verdict}** (`{rec['oa1']['binding_review']['sha256']}`). Supersedes the r3 §4.4 "hub 01" wording for K4S. |
| B2 job manifest (3badf70d) | `oa1/FROZEN-K4S.json` **`{rec['b2']['manifest_sha256']}`** (176 files = frozen k4s-confirm tree + PREREG r3 at 391d2006; Mac manifest pinned d89cab16); builder `{rec['b2']['builder_sha256']}` |
| B4 barrier prerequisites | {rec['b4']} |
| K4S Amendment 1 (45f32c0f) | amended Mac manifest 8bb20a75…; fleet reporting keeps d89cab16; END/Mac only from a separate amended tree naming 8bb20a75 |
| 03 idle service (18:22Z, d999d016) | PID 2180947, start_ticks 139691386, cmdline 16152ceb… (= T1's committed pin); flags only |
| Smoke freeze-SHA disclosure (18:48Z, f442b968) | {rec['smoke_freeze_sha_disclosure']['text']} |
| STOP drill (f442b968) | `receipts/stop-drill.json` `{rec['stop_drill']['sha256']}`: owned STOP drained in ≈1.7 s / 2.7 s, 0 owned groups |
| Launch qualification | 03 `{rec['launch_qualification']['127x03']['sha256']}`, 04 `{rec['launch_qualification']['127x04']['sha256']}` (28/28 each) |
| Dispatch | smoke `{rec['dispatch']['smoke']['sha256']}`; reporting `{rec['dispatch']['reporting']['sha256']}` (3900 blocks, 33000 games) |
| END prep | {rec['end_prep']} |
| Health tool | `tools/k4s_health.py` `{rec['files'][R+'/tools/k4s_health.py']}` (Sol-reviewed with OA-1) |
"""
(L/'addendum/K4S-LAUNCH-ADDENDUM.md').write_text(md)
print(h(L/'addendum/K4S-LAUNCH-ADDENDUM.json'),h(L/'addendum/K4S-LAUNCH-ADDENDUM.md'))
