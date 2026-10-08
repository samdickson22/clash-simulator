"""S3: B controller and S2 channel protocol throughout."""
def cell(tracker, recall=.97, precision=None):
    return dict(arm='B',tracker=tracker,noise=['board','hp','hud','events','latency'],
        recall=recall,precision=recall if precision is None else precision,
        latency='target',failure=0.,identity=0.)
CELLS={'T2-N97':cell('t2'),'T2-N90':cell('t2',.90),
       'Full-N97':cell('legacy'),'Full-N90':cell('legacy',.90),
       'ELT-N97':cell('elt'),'R-derived':cell('exact'),
       'T2-N64':cell('t2',.6428571428571429,.6666666666666666)}
H2H=()
