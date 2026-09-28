"""Verify concrete memory evidence before permitting the fixed scaling fits."""
import hashlib
import json
from pathlib import Path

MAX_RSS = 18*1024**3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_memory_reports(references, *, implementation, plan_sha256, runtime):
    if set(references) != {'neural','tree'}:
        raise ValueError('both neural and tree memory reports are required')
    audit = None
    for phase, reference in references.items():
        path = Path(reference['path'])
        if sha(path) != reference['sha256']:
            raise ValueError('memory report digest changed')
        report = json.loads(path.read_text())
        if (report.get('status') != 'passed' or report.get('phase') != phase
                or report.get('implementation') != implementation
                or report.get('collection_plan_sha256') != plan_sha256
                or report.get('runtime') != runtime
                or report.get('outcome_training') is not False):
            raise ValueError('memory report authority differs')
        peak, limit = report.get('peak_rss_bytes'), report.get('limit_bytes')
        if type(peak) is not int or type(limit) is not int or not 0 < peak <= limit <= MAX_RSS:
            raise ValueError('memory report exceeds limit or lacks measurement')
        current = report.get('data_audit',{})
        if (current.get('games') != 1536 or current.get('clusters') != 768
                or current.get('diagnostic_fitting_games') != 0
                or current.get('original',{}).get('games') != 384
                or current.get('extension',{}).get('games') != 1152):
            raise ValueError('memory report lacks exact combined-data audit')
        if audit is not None and current != audit:
            raise ValueError('memory reports audited different data')
        audit = current
        details = report.get('details',{})
        if details.get('outcome_model_saved') is not False:
            raise ValueError('probe must not save an outcome model')
        if phase == 'neural':
            if (details.get('batch') != [2,750,128]
                    or details.get('full_backpropagation') is not True
                    or details.get('finite_gradients') is not True
                    or details.get('optimizer_steps') != 1):
                raise ValueError('neural memory probe contract differs')
        elif (details.get('histogram_iterations') != 1 or details.get('sklearn') != '1.7.2'
                or details.get('largest_row_fold') not in range(4)
                or details.get('matrix_bytes',0) <= 0):
            raise ValueError('tree memory probe contract differs')
    return audit


def validate_readiness(readiness, *, implementation, plan_sha256, runtime):
    if (readiness.get('status') != 'passed' or readiness.get('implementation') != implementation
            or readiness.get('collection_plan_sha256') != plan_sha256
            or readiness.get('combined_games') != 1536
            or readiness.get('memory_verified') is not True):
        raise ValueError('scaling readiness does not match data, source and memory')
    audit = validate_memory_reports(readiness.get('memory_reports',{}),
        implementation=implementation,plan_sha256=plan_sha256,runtime=runtime)
    if readiness.get('data_audit') != audit:
        raise ValueError('readiness audit differs from memory evidence')
    return audit
