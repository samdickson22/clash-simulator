import bootstrap
from fair_player import Resources
r=Resources()
for name in ('HogRider','GoblinBarrel','Skeletons','GoblinGang','Goblinstein','FirespiritHut'):
 print(name, repr(r.config['cards'].get(name))[:2000], flush=True)
print('bodies',repr(r.meta['bodies'])[:3000])
