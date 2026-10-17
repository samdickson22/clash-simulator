# LP1 preregistration — 2026-10-17

Status: registered before simulation; search implementation feasibility is a gate.
Source base: origin/main 11fca5cd4. Fresh BASE from os.urandom(6): **202492701121077**.
No existing results or game seeds informed this bank.

Audit bank: five controlled level-11 Python-engine scenarios, seeds BASE+0..4,
observed at ticks 5, 15, 30, 60 (20 states). Scenarios: Goblin Barrel pending cast;
Archers/Knight combat and shots; Tombstone/Hog Rider production and decay;
Musketeer/Knight under Freeze; Archer Queen/Electro Wizard and ability/status.
Each uses an eight-card distinct deck, physical own HUD and public contract-v5.
The diagnostic opponent state is held identical in truth and rebuild to isolate
reconstruction from belief error. Compare a lossless native snapshot exported
from the Python state with Resources.root and LevelRoot at level 11. Also
remove non-body rows to isolate the documented live perception carrier loss.
Report pending casts, body identity/HP, shots, clocks, production/decay, status,
native.evaluate and 160-tick three-style rollout scores for WAIT plus a fixed
public-legal small action set. This diagnostic is not a win-rate claim and
cannot measure evolved/hero fidelity if the simulator has no form support.
Raw receipts/snapshots stay outside git under bot-lp1 jobs storage.

Contingent game bank: BASE+10000+i, i=0..149, same seed/deck/seat per arm,
150 paired cases per opponent per level row (1200 games total). Opponents:
LIVE-K4CW-r16-fp (primary), R3a. Pool v3.2: logged King-9 rows excluding Goblin
Hut; alternate seats. Own deck: HogRider,Archers,Cannon,Skeletons,Fireball,Zap,
ElectroSpirit,Valkyrie. Rows: L16 primary; account HogRider=8,Archers=8,Cannon=9,
Skeletons=7,Fireball=7,Zap=9,ElectroSpirit=8,Valkyrie=7,King=7 versus logged levels.
Plain: LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-wint, deterministic
live-diag configuration. Treatment: same plus public root/decision projection
26 ticks. Physical command delay remains 27 for our player in both arms.
Prediction: projection minus plain win rate > 0 against K4CW-fp.
Primary analysis: paired win-rate difference with paired bootstrap 95% CI;
report draws, clean completion and all exclusions. Diagnostics: reaction,
idle-play share, elixir at enemy cross and decision CPU milliseconds. Fixed
budgets, no wall-clock cutoffs; all environment/compute rules remain binding.

Gates: no outcome games until projection semantics and immutable source/pool
pins are recorded in an amendment on main. An existing imitation forward_prior
is not sufficient: it changes only proposals. Any nontrivial bot/search or
engine change is referred to BOT LEAD/Opus; this worker does not implement it.
No bot/live or Mac changes are authorized. No pool or game data goes in git.
