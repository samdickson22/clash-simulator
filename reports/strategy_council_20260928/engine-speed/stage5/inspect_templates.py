from c56_controller import resources,CARDS
from differential import config
b,m,s,bots=resources();c=config(CARDS)
print(b.token_names[:40])
for name in ('Goblinstein','ArcherQueen','MightyMiner','Log','Fireball'):
 d=c['cards'][name];print(name,list(d));print([(e['class'],e['stats']['name'],e.get('champion'),e.get('spell_name')) for group in d['units'] for e in group][:4])
print('config',list(c))
