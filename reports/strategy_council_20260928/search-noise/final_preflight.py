import bootstrap
from bootstrap import HERE
import hashlib,json
from evaluate import Resources,game,write
from noise import Sensor
from fair_player import observe
r=Resources();prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text())
ep=dict(pair=-1,seed=3926710201,noise_seed=3926710301,planning_deck=['HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log'],opponent_deck=['Log','Fireball','Cannon','Skeletons','IceSpirit','IceGolem','Musketeer','HogRider'],mode='scripts',family='Hog 2.6',style='balanced')
row=game(r,prior,ep,0,'B');assert row['terminal'];c=row['perception'];assert abs(c['hp_observed']/c['hp_trials']-.6606)<.02
row['sources']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'noise.py',HERE/'player.py',HERE/'evaluate.py']};write(HERE/'final-preflight.json',row)
print('Final input model terminal smoke passed; HP coverage',c['hp_observed']/c['hp_trials'],'HP MAE',c['hp_abs_error']/c['hp_observed'],flush=True)
