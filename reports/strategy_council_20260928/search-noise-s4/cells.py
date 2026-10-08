"""S4 independent derived-state switches on the frozen Full-N97 channels."""
def configuration(repair_elixir=False,repair_hand=False,tracker=None):
    return dict(arm='B',tracker=tracker or ('exact' if repair_elixir and repair_hand else 'legacy'),
                noise=['board','events','hp','hud','latency'],recall=.97,precision=.97,
                latency='target',failure=0.,identity=0.,repair_elixir=repair_elixir,repair_hand=repair_hand)
CELLS={'Full':configuration(),'R-elixir':configuration(True,False),'R-hand':configuration(False,True),
       'R-derived':configuration(True,True),'ELT':configuration(tracker='elt')}
H2H=()
