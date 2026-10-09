"""Pure registered ranking for recomputed shared-capture scores, never file authority.

Keep capture provenance distinct from historical replay schemas. File drivers
must recompute these inputs, not deserialize and trust claimed metrics.
"""
from fractions import Fraction
from body_scoring_v4 import POLICY
from body_selection_v4 import checked_counts,COUNT_KEYS
from selection_matrix_v4 import counts
from selection_guard_v4 import _sha
from scoring_v4 import select_threshold,select_epoch

GRID=[i/10 for i in range(1,10)]


def check_ready(ready):
    if (ready.get('validated') is not True or ready.get('steps')!=9600 or ready.get('epochs')!=24
            or ready.get('validation_matches')!=64 or len(ready.get('validation_receipt_sha256',{}))!=64
            or any(ready.get(k) is not False for k in ('selection_seal','heldout_opening_authorized','heldout_payloads_opened'))):
        raise ValueError('Full formal fit and validation population required')
    for key in ('fit_manifest_sha256','completion_sha256','admission_sha256','bundle_sha256'):
        if not _sha(ready.get(key)):raise ValueError('Formal provenance missing')
    ck=ready.get('checkpoint_sha256',{})
    if set(ck)!={str(i) for i in range(1,25)} or not all(_sha(d) for d in ck.values()):
        raise ValueError('Complete checkpoint provenance required')
    if not all(_sha(d) for d in ready['validation_receipt_sha256'].values()):raise ValueError('Receipt pins required')


def check_capture(admitted,ready,epoch):
    if (admitted.get('schema')!='clasher.v4.record-only-capture-admission.v1' or admitted.get('readiness')!=ready
            or admitted.get('clocks_read') is not False or admitted.get('epoch')!=epoch or admitted.get('checkpoint_sha256')!=ready['checkpoint_sha256'][str(epoch)]
            or admitted.get('bundle_sha256')!=ready['bundle_sha256']
            or set(admitted.get('episodes',{}))!=set(ready['validation_receipt_sha256'])
            or admitted.get('selection_seal') is not False or admitted.get('heldout_payloads_opened') is not False):
        raise ValueError('Capture identity differs')
    for key in ('capture_complete_sha256','capture_manifest_sha256','plan_sha256','equality_sha256'):
        if not _sha(admitted.get(key)):raise ValueError('Capture evidence pin missing')


def rank_body_cells(cells):
    cells=list(cells)
    if len(cells)!=9:raise ValueError('Nine complete body cells required')
    first=cells[0];ready=first['readiness'];check_ready(ready);epoch=first['epoch']
    if type(epoch) is not int or epoch not in range(1,25):raise ValueError('Registered epoch required')
    admitted=first['capture_admission'];check_capture(admitted,ready,epoch)
    grid={};population=None
    for row in cells:
        t=row['body_threshold']
        if type(t) not in (int,float) or t not in GRID or t in grid:raise ValueError('Complete distinct body grid required')
        if (row.get('schema')!='clasher.v4.clock-free-body-score.v1' or row.get('epoch')!=epoch
                or row.get('event_thresholds')!={'default':.5} or row.get('policy')!=POLICY
                or any(row.get(k)!=first.get(k) for k in ('readiness','capture_admission','sources','truth_payloads'))
                or any(row.get(k) is not False for k in ('selection_seal','heldout_opening_authorized','heldout_payloads_opened'))):
            raise ValueError('Body grid configuration or provenance differs')
        if set(row['per_match'])!=set(ready['validation_receipt_sha256']):raise ValueError('Full match counts required')
        per={ep:checked_counts(v) for ep,v in row['per_match'].items()};micro=checked_counts(row['micro'])
        if micro!={k:sum(v[k] for v in per.values()) for k in COUNT_KEYS}:raise ValueError('Body micro counts differ')
        truth={ep:tuple(v[k] for k in ('truth','eligible_frames','unscorable_frames')) for ep,v in per.items()}
        if population is not None and population!=truth:raise ValueError('Body truth coverage changed')
        population=truth
        if not micro['truth']:raise ValueError('No eligible positive body truth')
        grid[t]=row
    def rank(row):
        c=row['micro'];return Fraction(2*c['matched'],c['truth']+c['predictions']),Fraction(c['matched'],c['predictions']) if c['predictions'] else Fraction(0),row['body_threshold']
    chosen=max(grid.values(),key=rank)
    return dict(schema='clasher.v4.clock-free-body-ranking.v1',epoch=epoch,readiness=ready,
        capture_admission=admitted,body_threshold=chosen['body_threshold'],micro=chosen['micro'],
        event_thresholds={'default':.5},rule='body micro F1, then precision, then higher threshold',
        selection_seal=False,heldout_opening_authorized=False,heldout_payloads_opened=False)

