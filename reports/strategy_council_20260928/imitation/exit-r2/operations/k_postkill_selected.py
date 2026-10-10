"""Same qualified search adapter; add selection-amendment provenance to outputs."""
import k_postkill_sdefault as original
from postkill_selected import labelled

def run_case(job, *args, **kwargs):
    previous = original.labelled
    original.labelled = lambda value: labelled(value, job)
    try:
        return original.run_case(job, *args, **kwargs)
    finally:
        original.labelled = previous
