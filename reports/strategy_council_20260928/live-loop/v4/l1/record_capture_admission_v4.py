"""Authenticate non-clock files of full-epoch validation captures, without legacy schema substitution.

The caller recomputes portable fit admission first. Launch-plan and completion
hashes must come from the controller's actual completed job receipts. This module
never grants model selection or heldout access.
"""
from pathlib import Path
from portable_fit_admission_v4 import safe_file
from validation_admission_v4 import read,sha
from shared_epoch_inference_v4 import authorize


def authenticate_record_capture(folder,*,complete_sha,readiness,bundle,plan,plan_sha,
                         host,equality,equality_sha):
    code=Path(__file__).resolve().parent
    if readiness.get('validated') is not True or readiness.get('validation_matches')!=64:
        raise ValueError('Recomputed complete formal fit required')
    if sha(plan)!=plan_sha:raise ValueError('Externally pinned launch plan differs')
    launch=read(plan)
    if launch.get('schema')!='clasher.v4.epoch-fanout-plan.v2':raise ValueError('Unknown launch plan')
    authorize(equality,equality_sha)
    for name,digest in launch['source_files'].items():
        if sha(safe_file(code,name))!=digest:raise ValueError('Pinned capture/decoder source differs')
    if sha(folder/'complete.json')!=complete_sha:raise ValueError('Controller completion pin differs')
    complete=read(folder/'complete.json');manifest=read(folder/'manifest.json')
    epoch=manifest.get('epoch')
    if type(epoch) is not int or epoch not in range(1,25):raise ValueError('Registered epoch required')
    if epoch not in [r['epoch'] for r in launch['epoch_assignments'].get(host,[])]:
        raise ValueError('Epoch was not assigned to capture host')
    expected=dict(schema='clasher.v4.shared-epoch-capture.v1',epoch=epoch,
        checkpoint_sha256=readiness['checkpoint_sha256'][str(epoch)],
        bundle_sha256=readiness['bundle_sha256'],equality_sha256=equality_sha,
        spells=manifest.get('spells'),body_thresholds=[i/10 for i in range(1,10)],
        event_threshold=.5,storage='lossless JSON/gzip1 pre-NMS records',
        heldout_payloads_opened=False,selection_seal=False)
    if manifest!=expected:raise ValueError('Capture scientific configuration differs')
    # Spell routing is model/runtime metadata, never a truth-derived choice.
    from clasher.data import CardDataLoader
    cards=read(bundle/'fit/model/manifest.json')['cards'];loader=CardDataLoader()
    spells=[c for c in cards if str(loader.get_card(c).card_type).lower()=='spell']
    if manifest['spells']!=spells:raise ValueError('Capture spell routing differs')
    episodes={}
    for ep,digest in readiness['validation_receipt_sha256'].items():
        path=bundle/'matches'/ep/'receipt.json'
        if sha(path)!=digest:raise ValueError('Validation receipt changed')
        receipt=read(path)
        if receipt['episode']!=ep or receipt['split']!='validation':raise ValueError('Validation isolation failure')
        episodes[ep]=receipt['frames']
    names={'manifest.json'}|{f'body-{i}/{ep}-{suffix}' for i in range(1,10)
        for ep in episodes for suffix in ('decoder.jsonl.gz','completion.jsonl')}
    if (complete.get('schema')!='clasher.v4.shared-epoch-capture-complete.v1'
            or complete.get('episodes')!=episodes or complete.get('frames')!=sum(episodes.values())
            or set(complete.get('files_sha256',{}))!=names
            or complete.get('heldout_payloads_opened') is not False
            or complete.get('selection_seal') is not False):
        raise ValueError('Capture incomplete or outside full validation population')
    pins=complete['files_sha256']
    for name,digest in pins.items():
        if name.endswith('-completion.jsonl'):
            continue  # Preserve provenance digest; never open quarantined clocks.
        if sha(safe_file(folder,name))!=digest:raise ValueError('Capture file bytes changed')
    if sha(folder/'complete.json')!=complete_sha:raise ValueError('Capture mutated during admission')
    return dict(schema='clasher.v4.record-only-capture-admission.v1',epoch=epoch,host=host,
        capture_complete_sha256=complete_sha,capture_manifest_sha256=sha(folder/'manifest.json'),
        plan_sha256=plan_sha,equality_sha256=equality_sha,bundle_sha256=readiness['bundle_sha256'],
        checkpoint_sha256=expected['checkpoint_sha256'],readiness=readiness,
        episodes=episodes,files_sha256={n:d for n,d in pins.items() if not n.endswith('-completion.jsonl')},
        clocks_read=False,source_sha256=launch['source_files'],
        spells=spells,selection_seal=False,heldout_payloads_opened=False)
