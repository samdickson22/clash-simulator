# Prospective operational clarification, 2026-10-08

The historical L2 gap distribution is computed by L2's unchanged analyze.py from
`native/pair-*/public-frames.jsonl.gz`, not the sparser decisions.jsonl. Use those
public frame timestamps for the exact empirical replay schedule (seed 6109).
Hash those inputs and the realized schedule before predictions. This corrects the
source path in the base registration; no gate or target distribution changes.

The v3 trainer has a 450MiB cache disk guard inherited from the constrained Mac.
For the full Phase A control, an explicit configurable cache budget may be raised
to 4096MiB on 127x01 without changing pixels, sampling, loss, architecture,
initialization or training duration. Default stays 450MiB. If fleet footprint
would exceed 40GB, stop rather than delete data or subsample the formal population.
