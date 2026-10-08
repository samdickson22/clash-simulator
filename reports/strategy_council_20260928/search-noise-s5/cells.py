"""S5 frozen Full channels, B controller, and S4 tracker v3."""
def cell(tracker, recall=.97):
    return dict(arm='B',tracker=tracker,noise=['board','hp','hud','events','latency'],
        recall=recall,precision=recall,latency='target',failure=0.,identity=0.)
CELLS={'T3-N97':cell('t3'),'ELT-N97':cell('elt'),'Full-N97':cell('legacy'),
       'R-derived':cell('exact'),'T3-N90':cell('t3',.90),'Full-N90':cell('legacy',.90)}
H2H=()
