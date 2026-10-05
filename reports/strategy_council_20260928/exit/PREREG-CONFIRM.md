# Confirmatory proposal-network evaluation

Frozen before the first confirmation game. The creation time and SHA256 are recorded
in confirm/manifest.json. This protocol supersedes the old acceptance gate only for
this new experiment. Original iteration-1 outcomes and artifacts remain unchanged.

## Players and primary test

Compare srp-pub-pol with exit/it1/student.pt against srp-pub-pol with
pilot/v7r4h-launch/runs/s2902/seed-2902/scripted/policy_decisions_001000000.pt.
Only the proposal checkpoint changes. Retain K=1, top eight legal policy proposals,
script candidates and no-op, search every second five-tick decision, native
160-tick continuations with interval 10, public-v4 observations and masks, exact
derived public state, zero public recurrent reward, canonical P16 level 11,
6001-tick horizon, and existing terminal/HP tiebreak rules. Neither planner reads
true hidden opponent state. Both H2H planners get the same declared mixture of
training, development and Hog26 priors, as in exit/evaluate.py.

Primary sample is 256 games, 128 matchups, two controller seats per matchup.
Matchup p uses seed 610000003 + 1009*p, p=0..127. Student seat is g modulo 2,
p=floor(g/2). Matchups with p modulo 3 = 0 use Hog26 for BOTH world seats,
43 matchups / 86 games. The other 85 matchups use development.json for world
seat 0 and training.json for world seat 1, sampled through the srp-public helper.
Keep both ordered world decks fixed while swapping controllers, so each proposer
plays each deck once. This implements the requested one-third Hog26 mixture,
rounded by the every-third rule. Checked-in srp-public itself has no Hog26 H2H
mixture and compares search to a raw policy; this adaptation uses its asymmetric
deck pools and exit's paired search-versus-search controller swap.

Score win=1, draw=0.5, loss=0. Matchup-cluster percentile bootstrap resamples
complete two-seat matchup averages, 10,000 replicates, NumPy RNG 770061,
2.5th/97.5th percentiles, reusing exit/analyze.py summary. Primary PASS requires
student score >=0.55 AND 95% interval lower bound >0.50. Report pooled and deck
subgroups. No tuning, outcome-based early stop, extra games, or exclusions.

## Required secondary comparison

For EACH proposer, run identical fresh 128 holdout games against public scripts:
balanced 44, pressure 42, defense 42. Candidate development decks and opponent
training decks use the original asymmetric script protocol, with candidate seat
g modulo 2 and ordered candidate/opponent decks swapped together across seats.
Cell seeds are 611000003, 612000003, 613000003 respectively; actual matchup seed
is cell seed + floor(g/2)*1009. Report each style and the pooled comparison.

Compute drop = initial score rate minus student score rate, pairing identical
style, matchup seed, seat and ordered decks. Bootstrap the complete two-seat
differences, 10,000 replicates, RNG 770061. Required secondary PASS is observed
drop <=0.05 AND the upper endpoint of the paired 95% drop interval <0.10.
Both conditions are gates; report the drop and interval explicitly.

Hog26 secondary: EACH proposer plays 64 games, balanced 22, pressure 22, defense
20, cell seeds 615000003, 616000003, 617000003. Candidate Hog26, opponent training
pools, otherwise identical pairing. Report scores and paired drop CI without an
additional gate. Total confirmation games: 640. Overall PASS requires primary
and required holdout secondary PASS. Policy-alone outcomes are descriptive only:
iteration 1 initial 83/192 vs student 64/192, Hog26 32/96 vs 18/96. Do not rerun or
use policy-alone performance as a gate.

## Conditional iterations 2 and 3

Start only after overall confirmation PASS. Reuse collect.py and fit.py unchanged,
starting iteration 2 from it1/student.pt, iteration 3 from accepted it2/student.pt.
Each iteration collects 150 games, 50 Hog26, using the current proposer in the
acting search player. Use the exact iteration-1 target/loss recipe in DESIGN.md
and config.toml: train-only entropy-1 temperature, normalized max-minus-mean
weights, full-prefix recurrence, candidate soft CE plus 1.0 full-legal student
KL to frozen previous policy, AdamW LR 5e-6, one epoch, four 64-step chunks per
batch, gradient cap 0.5, 20% held-out complete pairs. Existing collection seed
formula is 880043 + iteration*100000000 + matchup*1009. Same split/fit seeds.
No hyperparameter adjustment. One final checkpoint per iteration.

For iteration i=2,3, H2H base is 600000003+i*10000000. Run 128 games, 64
matchups, every-third Hog26 and otherwise the same fixed development/training
world-deck pair. Compare new search player against previous accepted iteration's
search player. Accept if score >=0.50 AND paired-bootstrap lower bound >0.45,
AND holdout-script drop <=0.05. Script sample is 64 per proposer, balanced 22,
pressure 22, defense 20, seed bases H2H base + 1000000, +2000000, +3000000.
Report paired drop CI, but no CI gate is added to these iteration acceptances.
Stop on first rejection and keep the last accepted proposer. Evaluate against
the previous accepted proposer, never against the original initial by accident.

## Integrity, resources and reporting

confirm/seed-audit.json checks all JSON/JSONL report seed fields, including
archived games, against all planned confirmation, conditional collection and
conditional evaluation matchup seeds. Any overlap blocks launch. Original source
pins must still verify; confirm/manifest.json additionally binds this protocol,
new code, audit, and both proposer hashes before any new game. Record their hashes
with every game. Check source pins and the exit/ <2 GiB guard before each game.

Use at most three task-owned heavy workers, single-thread inference, nice 10,
with driver launched via pilot/detach.sh. Foreign c56/extraction/watchdog and
other jobs are untouched. Reuse only complete games whose spec, manifest and
checkpoint hashes match. Resume missing games with unchanged specs. Exceptions
or source drift block completion; retain all failures. Incomplete samples cannot
PASS. Count engine-rejected plays without excluding their games, consistent with
the documented iteration-1 simultaneous placement conflict. Retain timing maxima.
No engine, original helper, other experiment, or frozen runtime edits. Update
PROGRESS.md after every stage. Write CONFIRM.md and machine-readable results after
all confirmation games; add iteration results only if conditional work is allowed.
