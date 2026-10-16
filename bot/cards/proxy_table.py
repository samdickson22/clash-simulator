"""Live board proxies for the 66 ladder cards outside the supported C56.

Combat role and observed body count take priority over printed elixir. Each
observed body is replaced individually; proxy_card is an engine identity, NOT
an instruction to deploy that card's default number of bodies or charge its
cost. TRUE card identity/cost feed the revealed set, cycle, and elixir ledger.

Costs audited against both RoyaleSim cards-160402017*.json snapshots (16.402).
Mirror cost=None: charge the opponent's last TRUE played-card cost + 1, using
play history (battle.py _resolve_card_play). With missing history keep the cost
unknown; never charge 1 or Zap's price. Clone/Mirror bodies are dynamic copies
of observed targets, not a static body family or a source-card revelation.
MergeMaiden cost=None: select forms by observed flight; ground=3, mounted=6.
Its top-level ground body is only a compatibility default; do not infer cost
from that default. Heal is a troop despite the legacy exported spell type.

bodies counts INITIAL combat bodies per deployment (summonNumber + second
character count), not lifetime spawns, passengers, bottles, or delayed spell
spawns. 3M's missing export list is supplied by the live three-member overlay.
Spells may have body_map entries for eventual spawns, even with bodies=0.
Evolutions/hero variants are outside this base-card table.

Kind/flight are hard constraints for placed bodies. Stationary effect objects,
incubation objects, and delivery carriers map to None, with explicit reasons
in UNPLACED_BODIES. They are not fabricated troops. Persistent buildings map
to C56 buildings, including emerged GoblinDrill and BrokenCannon. Attached
passengers are omitted until detached; their carrier already has one body.
Excluded champions/unsafe stateful proxies are listed below with reasons.

SHARED_BODY lists visual sprite families, not internal-object equality or
combat proxies. A shared sprite alone MUST NOT reveal its source card.
CLASS_ONLY estimates are nominal compatibility data, NEVER an elixir charge;
class-only entities NEVER enter the revealed eight-card set.

The module has no runtime dependency on gamedata or the upstream checkout;
tests independently walk both metadata graphs and engine corrections.
"""

C56 = frozenset((
    'AngryBarbarians', 'Archer', 'ArcherQueen', 'Arrows', 'BabyDragon', 'Balloon',
    'BarbLog', 'Bats', 'Berserker', 'BlowdartGoblin', 'BombTower', 'Cannon',
    'DarkPrince', 'Earthquake', 'ElectroSpirit', 'FireSpirits', 'Fireball', 'Firecracker',
    'FirespiritHut', 'Ghost', 'Giant', 'GoblinBarrel', 'GoblinGang', 'GoblinHut',
    'Goblins', 'Goblinstein', 'Golem', 'HogRider', 'IceGolemite', 'IceSpirits',
    'InfernoTower', 'Knight', 'Lightning', 'Log', 'MightyMiner', 'Miner',
    'MiniPekka', 'MinionHorde', 'Minions', 'Musketeer', 'Poison', 'Prince',
    'Princess', 'Rascals', 'Rocket', 'RoyalDelivery', 'RoyalHogs', 'SkeletonArmy',
    'Skeletons', 'Tesla', 'Tornado', 'Valkyrie', 'Wallbreakers', 'Wizard',
    'Xbow', 'Zap',
))

BODIES_47 = frozenset((
    'AngryBarbarian', 'Archer', 'ArcherQueen', 'BabyDragon', 'Balloon', 'Barbarian',
    'Bat', 'Berserker', 'BlowdartGoblin', 'BombTower', 'Cannon', 'DarkPrince',
    'DeliveryRecruit', 'ElectroSpirit', 'FireSpirits', 'Firecracker', 'Furnace_rework', 'Ghost',
    'Giant', 'Goblin', 'GoblinHut_Rework', 'Goblin_Stab', 'Golem', 'HogRider',
    'IceGolemite', 'IceSpirits', 'InfernoTower', 'Knight', 'MightyMiner', 'Miner',
    'MiniPekka', 'Minion', 'Musketeer', 'Prince', 'Princess', 'RascalBoy',
    'RascalGirl', 'RoyalHog', 'Skeleton', 'SpearGoblin', 'Tesla', 'Valkyrie',
    'Wallbreaker', 'Wizard', 'Xbow', 'goblinstein', 'goblinstein_doctor',
))

COST_DISAGREEMENTS = {'DarkMagic': (3, 5)}  # gamedata, live 16.402

UNPLACED_BODIES = {
    'GiantSkeletonBomb': 'stationary delayed bomb: effect only, no combat troop',
    'SkeletonContainerNew': 'stationary skeleton payload carrier: omit container, map Skeleton descendants',
    'GoblinDrillDig': 'underground delivery carrier: omit until GoblinDrill building emerges',
    'RageBottle': 'stationary spell carrier: effect only',
    'RageBarbarianBottle': 'stationary rage carrier: effect only',
    'PhoenixEgg': 'stationary ground incubation object (NO_MOVE_ALLOW_ATTRACT): omit until rebirth',
    'SpearGoblinGiant': 'attached airborne passenger: omit until detached SpearGoblin is observed',
}

UNSAFE_PROXY_BODIES = {
    'Miner': 'tunnel/deploy-anywhere state (cards/miner.py)',
    'IceGolemite': 'death slow/freeze (cards/ice_golem.py)',
    'Golem': 'splits into unsupported Golemites (cards/golem.py)',
    'Ghost': 'invisibility state (cards/royal_ghost.py)',
    'DarkPrince': 'shield and charge (cards/dark_prince.py / formations)',
    'Prince': 'charge state (formations / mechanic_detector)',
}

CHAMPION_PROXIES = frozenset(('ArcherQueen', 'Goblinstein', 'goblinstein', 'goblinstein_doctor', 'MightyMiner'))

AIR_BODY_NAMES = frozenset((
    'BabyDragon', 'Balloon', 'Bat', 'Bats', 'DartBarrell', 'ElectroDragon',
    'FlyingMachine', 'InfernoDragon', 'LavaHound', 'LavaPup', 'LavaPups',
    'MegaMinion', 'MergeMaiden_Mounted', 'Minion', 'MinionHorde', 'Minions',
    'Phoenix', 'PhoenixNoRespawn', 'SkeletonBalloon', 'SkeletonDragon',
    'SkeletonDragons', 'SpearGoblinGiant',
))

NAMED = {
    'Assassin': dict(
        cost=3.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Knight', proxy_body='Knight',
        body_map={'Assassin': 'Knight'},
        why='melee single, cost 3 (no Miner: tunnel state)',
    ),
    'AxeMan': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Wizard', proxy_body='Wizard',
        body_map={'AxeMan': 'Wizard'},
        why='ranged splash, cost 5 (never a champion proxy)',
    ),
    'BarbarianHut': dict(
        cost=6.0, cls='building', kind='building', air=False, bodies=1,
        proxy_card='GoblinHut', proxy_body='GoblinHut_Rework',
        body_map={'Barbarian': 'Barbarian', 'BarbarianHut': 'GoblinHut_Rework'},
        why='spawner building with Barbarian descendants',
    ),
    'Barbarians': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=5,
        proxy_card='Knight', proxy_body='Barbarian',
        body_map={'Barbarian': 'Barbarian'},
        why='five ground melee bodies, each Barbarian; preserve count over proxy card deployment',
    ),
    'BattleHealer': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Valkyrie', proxy_body='Valkyrie',
        body_map={'BattleHealer': 'Valkyrie'},
        why='durable ground melee support; healing is not approximated by a ranged attacker',
    ),
    'BattleRam': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='HogRider', proxy_body='HogRider',
        body_map={'Barbarian': 'Barbarian', 'BattleRam': 'HogRider'},
        why='building-targeting ram, cost 4; death spawns Barbarian',
    ),
    'Bomber': dict(
        cost=2.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Firecracker', proxy_body='Firecracker',
        body_map={'Bomber': 'Firecracker'},
        why='ground ranged splash; Firecracker retains role while true Bomber costs 2',
    ),
    'BossBandit': dict(
        cost=6.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Knight', proxy_body='Knight',
        body_map={'BossBandit': 'Knight'},
        why='ground melee tank; champion dash and ability omitted',
    ),
    'Bowler': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Wizard', proxy_body='Wizard',
        body_map={'Bowler': 'Wizard'},
        why='ground ranged splash, cost 5',
    ),
    'Clone': dict(
        cost=3.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Tornado', proxy_body='',
        body_map={},
        body_rule='copy_observed_body',
        why='copy observed target bodies dynamically; charge true Clone cost once, never once per clone',
    ),
    'DarkMagic': dict(
        cost=5.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Arrows', proxy_body='',
        body_map={},
        why='live Void costs 5; area damage proxy, printed cost does not choose the board role',
    ),
    'DarkWitch': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Knight', proxy_body='Knight',
        body_map={'Bat': 'Bat', 'DarkWitch': 'Knight'},
        why='ground melee support plus Bat spawns; no invented ranged splash',
    ),
    'DartBarrell': dict(
        cost=4.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='BabyDragon', proxy_body='BabyDragon',
        body_map={'DartBarrell': 'BabyDragon'},
        why='air ranged single, cost 4',
    ),
    'ElectroDragon': dict(
        cost=5.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='BabyDragon', proxy_body='BabyDragon',
        body_map={'ElectroDragon': 'BabyDragon'},
        why='flying ranged splash support; chain stun omitted',
    ),
    'ElectroGiant': dict(
        cost=7.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Giant', proxy_body='Giant',
        body_map={'ElectroGiant': 'Giant'},
        why='building-targeting tank; reflection and Golem splitting omitted',
    ),
    'ElectroWizard': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Wizard', proxy_body='Wizard',
        body_map={'ElectroWizard': 'Wizard'},
        why='ground ranged support; deployment and attack stun omitted',
    ),
    'EliteArcher': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Musketeer', proxy_body='Musketeer',
        body_map={'EliteArcher': 'Musketeer'},
        why='ranged single, cost 4',
    ),
    'Elixir Collector': dict(
        cost=6.0, cls='building', kind='building', air=False, bodies=1,
        proxy_card='Cannon', proxy_body='Cannon',
        body_map={'ElixirCollector': 'Cannon'},
        why='stationary building body; production omitted',
    ),
    'ElixirGolem': dict(
        cost=3.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Giant', proxy_body='Giant',
        body_map={'ElixirGolem1': 'Giant', 'ElixirGolem2': 'HogRider', 'ElixirGolem4': 'RoyalHog'},
        why='building-targeting stages: Giant, HogRider, RoyalHog; no death freeze',
    ),
    'Fisherman': dict(
        cost=3.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Knight', proxy_body='Knight',
        body_map={'Fisherman': 'Knight'},
        why='ground melee single target; hook omitted',
    ),
    'Freeze': dict(
        cost=4.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Zap', proxy_body='',
        body_map={},
        why='control stun area; control-first over cost',
    ),
    'GiantBuffer': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Giant', proxy_body='Giant',
        body_map={'GiantBuffer': 'Giant'},
        why='building-targeting tank; enchantment omitted',
    ),
    'GiantSkeleton': dict(
        cost=6.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Valkyrie', proxy_body='Valkyrie',
        body_map={'GiantSkeleton': 'Valkyrie', 'GiantSkeletonBomb': None},
        why='ground melee tank; bomb is explicitly unplaced',
    ),
    'GoblinCage': dict(
        cost=4.0, cls='building', kind='building', air=False, bodies=1,
        proxy_card='Cannon', proxy_body='Cannon',
        body_map={'GoblinBrawler': 'Knight', 'GoblinCage': 'Cannon'},
        why='defensive building, cost 3; Brawler as Knight (melee single)',
    ),
    'GoblinCurse': dict(
        cost=2.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Log', proxy_body='',
        body_map={'Goblin': 'Goblin_Stab', 'GoblinCurseGoblin': 'Goblin_Stab'},
        why='damage area, cost 2',
    ),
    'GoblinDemolisher': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Firecracker', proxy_body='Firecracker',
        body_map={'GoblinDemolisher': 'Firecracker', 'GoblinDemolisher_kamikaze_form': 'Wallbreaker'},
        why='ranged splash, then Wallbreaker for building-targeting kamikaze form',
    ),
    'GoblinDrill': dict(
        cost=4.0, cls='building', kind='building', air=False, bodies=1,
        proxy_card='GoblinHut', proxy_body='GoblinHut_Rework',
        body_map={'Goblin': 'Goblin_Stab', 'GoblinDrill': 'GoblinHut_Rework', 'GoblinDrillDig': None},
        why='spawner building, cost 4',
    ),
    'GoblinGiant': dict(
        cost=6.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Giant', proxy_body='Giant',
        body_map={'GoblinGiant': 'Giant', 'SpearGoblin': 'SpearGoblin', 'SpearGoblinGiant': None},
        why='building-targeting ground tank; Giant body preserves target preference',
    ),
    'GoblinMachine': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Valkyrie', proxy_body='Valkyrie',
        body_map={'GoblinMachine': 'Valkyrie'},
        why='ground melee tank; rocket omitted',
    ),
    'GoldenKnight': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Knight', proxy_body='Knight',
        body_map={'GoldenKnight': 'Knight'},
        why='ground melee single target; champion dash omitted',
    ),
    'Graveyard': dict(
        cost=5.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Poison', proxy_body='',
        body_map={'Graveyard_rework_Skeleton': 'Skeleton', 'Skeleton': 'Skeleton'},
        why='damage over time area, cost 4 nearest C56 damage spell',
    ),
    'Heal': dict(
        cost=1.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='ElectroSpirit', proxy_body='ElectroSpirit',
        body_map={'HealSpirit': 'ElectroSpirit'},
        why='one ground kamikaze spirit; heal omitted, spirit combat role retained',
    ),
    'Hunter': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Musketeer', proxy_body='Musketeer',
        body_map={'Hunter': 'Musketeer'},
        why='ranged single, cost 4',
    ),
    'IceWizard': dict(
        cost=3.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Wizard', proxy_body='Wizard',
        body_map={'IceWizard': 'Wizard'},
        why='ground ranged splash; slow omitted',
    ),
    'InfernoDragon': dict(
        cost=4.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='BabyDragon', proxy_body='BabyDragon',
        body_map={'InfernoDragon': 'BabyDragon'},
        why='air ranged, cost 4',
    ),
    'LavaHound': dict(
        cost=7.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='Balloon', proxy_body='Balloon',
        body_map={'LavaHound': 'Balloon', 'LavaPups': 'Minion'},
        why='air building-targeting tank, cost 7 (nearest air Balloon)',
    ),
    'LittlePrince': dict(
        cost=3.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Musketeer', proxy_body='Musketeer',
        body_map={'ChampionGuard': 'Valkyrie', 'LittlePrince': 'Musketeer'},
        why='ranged attacker plus Valkyrie approximation of ChampionGuard',
    ),
    'MegaKnight': dict(
        cost=7.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Valkyrie', proxy_body='Valkyrie',
        body_map={'MegaKnight': 'Valkyrie'},
        why='ground melee splash tank; jump omitted',
    ),
    'MegaMinion': dict(
        cost=3.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='Minions', proxy_body='Minion',
        body_map={'MegaMinion': 'Minion'},
        why='air melee single, cost 3',
    ),
    'MergeMaiden': dict(
        cost=None, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Musketeer', proxy_body='Musketeer',
        body_map={'MergeMaiden_Mounted': 'BabyDragon', 'MergeMaiden_Normal': 'Musketeer'},
        cost_rule='observed_form',
        forms={
            'MergeMaiden_Normal': dict(
                cost=3.0, cls='troop', air=False, bodies=1,
                proxy_card='Musketeer', proxy_body='Musketeer',
                body_map={'MergeMaiden_Normal': 'Musketeer'},
            ),
            'MergeMaiden_Mounted': dict(
                cost=6.0, cls='troop', air=True, bodies=1,
                proxy_card='BabyDragon', proxy_body='BabyDragon',
                body_map={'MergeMaiden_Mounted': 'BabyDragon'},
            ),
        },
        why='observed ground/flying ranged form selects Musketeer/BabyDragon and true cost 3/6',
    ),
    'MiniSparkys': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=3,
        proxy_card='Musketeer', proxy_body='Musketeer',
        body_map={'MiniZapMachine': 'Musketeer'},
        why='ranged, cost 4',
    ),
    'Mirror': dict(
        cost=None, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Zap', proxy_body='',
        body_map={},
        cost_rule='last_played+1', body_rule='copy_observed_body',
        why=('copy last played card; charge its TRUE prior play cost + 1, never the proxy cost; '
             'unresolved history stays unknown'),
    ),
    'Monk': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Knight', proxy_body='Knight',
        body_map={'Monk': 'Knight'},
        why='durable ground melee; reflection omitted',
    ),
    'Mortar': dict(
        cost=4.0, cls='building', kind='building', air=False, bodies=1,
        proxy_card='Xbow', proxy_body='Xbow',
        body_map={'Mortar': 'Xbow'},
        why='stationary long-range siege building; projectile splash omitted',
    ),
    'MovingCannon': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Musketeer', proxy_body='Musketeer',
        body_map={'BrokenCannon': 'Cannon', 'MovingCannon': 'Musketeer'},
        why='ranged ground attacker, then Cannon building after shield loss',
    ),
    'Pekka': dict(
        cost=7.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='MiniPekka', proxy_body='MiniPekka',
        body_map={'Pekka': 'MiniPekka'},
        why='heavy melee single target',
    ),
    'Phoenix': dict(
        cost=4.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='Minions', proxy_body='Minion',
        body_map={'Phoenix': 'Minion', 'PhoenixEgg': None, 'PhoenixNoRespawn': 'Minion'},
        why='flying melee single body; stationary egg unplaced; reborn form remains flying',
    ),
    'Rage': dict(
        cost=2.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Zap', proxy_body='',
        body_map={'RageBottle': None},
        why='non-damage area buff, cost 2',
    ),
    'RageBarbarian': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Berserker', proxy_body='Berserker',
        body_map={'RageBarbarian': 'Berserker', 'RageBarbarianBottle': None},
        why='fast ground melee; rage bottle explicitly unplaced',
    ),
    'RamRider': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='HogRider', proxy_body='HogRider',
        body_map={'Ram': 'HogRider', 'RamRider': 'Musketeer'},
        why='building-targeter (never a champion proxy)',
    ),
    'Ronin': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Knight', proxy_body='Knight',
        body_map={'Ronin': 'Knight'},
        why='ground melee single target; champion ability omitted',
    ),
    'RoyalGiant': dict(
        cost=6.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Giant', proxy_body='Giant',
        body_map={'RoyalGiant': 'Giant'},
        why='building-targeting ground tank; Giant body preserves target preference',
    ),
    'RoyalRecruits': dict(
        cost=7.0, cls='troop', kind='troop', air=False, bodies=6,
        proxy_card='Knight', proxy_body='DeliveryRecruit',
        body_map={'Recruit': 'DeliveryRecruit'},
        why='six shielded ground melee bodies; same recruit sprite family',
    ),
    'SkeletonBalloon': dict(
        cost=3.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='Balloon', proxy_body='Balloon',
        body_map={'Skeleton': 'Skeleton', 'SkeletonBalloon': 'Balloon', 'SkeletonContainerNew': None},
        why='flying building-targeting carrier; stationary container unplaced, seven Skeleton descendants',
    ),
    'SkeletonDragons': dict(
        cost=4.0, cls='troop', kind='troop', air=True, bodies=2,
        proxy_card='BabyDragon', proxy_body='BabyDragon',
        body_map={'SkeletonDragon': 'BabyDragon'},
        why='air ranged swarm, cost 4',
    ),
    'SkeletonKing': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Valkyrie', proxy_body='Valkyrie',
        body_map={'Skeleton': 'Skeleton', 'SkeletonKing': 'Valkyrie', 'SkeletonKingSkeleton': 'Skeleton'},
        why='ground melee splash plus Skeleton ability spawns; no champion state',
    ),
    'SkeletonWarriors': dict(
        cost=3.0, cls='troop', kind='troop', air=False, bodies=3,
        proxy_card='SkeletonArmy', proxy_body='Skeleton',
        body_map={'SkeletonWarrior': 'Skeleton'},
        why='melee swarm, cost 3',
    ),
    'Snowball': dict(
        cost=2.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Zap', proxy_body='',
        body_map={},
        why='instant area damage and brief control; knockback omitted',
    ),
    'SpearGoblins': dict(
        cost=2.0, cls='troop', kind='troop', air=False, bodies=3,
        proxy_card='Goblins', proxy_body='SpearGoblin',
        body_map={'SpearGoblin': 'SpearGoblin'},
        why='ranged swarm, cost 2',
    ),
    'SuspiciousBush': dict(
        cost=2.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Wallbreakers', proxy_body='Wallbreaker',
        body_map={'BushGoblin': 'Goblin_Stab', 'SuspiciousBush': 'Wallbreaker'},
        why='building-targeting melee, cost 2',
    ),
    'ThreeMusketeers': dict(
        cost=9.0, cls='troop', kind='troop', air=False, bodies=3,
        proxy_card='Musketeer', proxy_body='Musketeer',
        body_map={'ThreeMusketeer_Rework_Character_1': 'Musketeer',
                    'ThreeMusketeer_Rework_Character_2': 'Musketeer',
                    'ThreeMusketeer_Rework_Character_3': 'Musketeer'},
        why='three ranged ground bodies, including live rework members; preserve count over cost',
    ),
    'Tombstone': dict(
        cost=3.0, cls='building', kind='building', air=False, bodies=1,
        proxy_card='GoblinHut', proxy_body='GoblinHut_Rework',
        body_map={'Skeleton': 'Skeleton', 'Tombstone': 'GoblinHut_Rework'},
        why='spawner building with Skeleton descendants; preserve role over cost',
    ),
    'Vines': dict(
        cost=3.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Tornado', proxy_body='',
        body_map={},
        why='control, cost 3; effect assumed from name',
    ),
    'Witch': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Wizard', proxy_body='Wizard',
        body_map={'Skeleton': 'Skeleton', 'Witch': 'Wizard'},
        why='splash caster, cost 5',
    ),
    'WitchMother': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Musketeer', proxy_body='Musketeer',
        body_map={'VoodooHog': 'RoyalHog', 'WitchMother': 'Musketeer'},
        why='ranged single, cost 4',
    ),
    'ZapMachine': dict(
        cost=6.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Wizard', proxy_body='Wizard',
        body_map={'ZapMachine': 'Wizard'},
        why='ranged splash ground (never a champion proxy)',
    ),
}

CLASS_ONLY = {
    'troop': dict(proxy_body='Knight', cost=4.0, reveals_card=False, charge_elixir=False),
    'building': dict(proxy_body='BombTower', cost=4.0, reveals_card=False, charge_elixir=False),
    'air': dict(proxy_body='BabyDragon', cost=4.0, reveals_card=False, charge_elixir=False),
}

SHARED_BODY_REVEALS_CARD = False

# Curated sprite equivalences include SkeletonKing/Graveyard skeleton rows,
# Recruit/DeliveryRecruit, Goblin/Goblin_Stab/curse Goblins, and all 3M members.
# Bomber also appears as the visible rider of BombTower.
SHARED_BODY = {
    'Assassin': [],
    'AxeMan': [],
    'BarbarianHut': ['BarbLog'],
    'Barbarians': ['BarbLog'],
    'BattleHealer': [],
    'BattleRam': ['BarbLog'],
    'Bomber': ['BombTower'],
    'BossBandit': [],
    'Bowler': [],
    'Clone': [],
    'DarkMagic': [],
    'DarkWitch': ['Bats'],
    'DartBarrell': [],
    'ElectroDragon': [],
    'ElectroGiant': [],
    'ElectroWizard': [],
    'EliteArcher': [],
    'Elixir Collector': [],
    'ElixirGolem': [],
    'Fisherman': [],
    'Freeze': [],
    'GiantBuffer': [],
    'GiantSkeleton': [],
    'GoblinCage': [],
    'GoblinCurse': ['GoblinBarrel', 'GoblinGang', 'Goblins'],
    'GoblinDemolisher': [],
    'GoblinDrill': ['GoblinBarrel', 'GoblinGang', 'Goblins'],
    'GoblinGiant': ['GoblinGang', 'GoblinHut'],
    'GoblinMachine': [],
    'GoldenKnight': [],
    'Graveyard': ['SkeletonArmy', 'Skeletons'],
    'Heal': [],
    'Hunter': [],
    'IceWizard': [],
    'InfernoDragon': [],
    'LavaHound': [],
    'LittlePrince': [],
    'MegaKnight': [],
    'MegaMinion': [],
    'MergeMaiden': [],
    'MiniSparkys': [],
    'Mirror': [],
    'Monk': [],
    'Mortar': [],
    'MovingCannon': [],
    'Pekka': [],
    'Phoenix': [],
    'Rage': [],
    'RageBarbarian': [],
    'RamRider': [],
    'Ronin': [],
    'RoyalGiant': [],
    'RoyalRecruits': ['RoyalDelivery'],
    'SkeletonBalloon': ['SkeletonArmy', 'Skeletons'],
    'SkeletonDragons': [],
    'SkeletonKing': ['SkeletonArmy', 'Skeletons'],
    'SkeletonWarriors': [],
    'Snowball': [],
    'SpearGoblins': ['GoblinGang', 'GoblinHut'],
    'SuspiciousBush': [],
    'ThreeMusketeers': ['Musketeer'],
    'Tombstone': ['SkeletonArmy', 'Skeletons'],
    'Vines': [],
    'Witch': ['SkeletonArmy', 'Skeletons'],
    'WitchMother': [],
    'ZapMachine': [],
}

# Body aliases preserve body identity; card aliases resolve deployment names.
# In particular Skeleton (body) and Skeletons (card) never share an alias map.
BODY_ALIASES = {
    'FlyingMachine': 'DartBarrell', 'LavaPup': 'LavaPups',
    'RoyalRecruit': 'Recruit', 'FireSpirit': 'FireSpirits',
    'IceSpirit': 'IceSpirits', 'GoblinDemolisherKamikaze': 'GoblinDemolisher_kamikaze_form',
}
CARD_ALIASES = {
    'Archers': 'Archer', 'IceGolem': 'IceGolemite', 'IceSpirit': 'IceSpirits',
    'Bandit': 'Assassin', 'Executioner': 'AxeMan', 'Night Witch': 'DarkWitch',
    'Flying Machine': 'DartBarrell', 'Magic Archer': 'EliteArcher',
    'ElixirCollector': 'Elixir Collector', 'Heal Spirit': 'Heal',
    'Spirit Empress': 'MergeMaiden', 'Void': 'DarkMagic', 'Zappies': 'MiniSparkys',
    'Cannon Cart': 'MovingCannon', 'Lumberjack': 'RageBarbarian',
    'Skeleton Barrel': 'SkeletonBalloon', 'Guards': 'SkeletonWarriors',
    'Giant Snowball': 'Snowball', 'Mother Witch': 'WitchMother', 'Sparky': 'ZapMachine',
    'Barbarian Barrel': 'BarbLog', 'Elite Barbarians': 'AngryBarbarians',
    'Royal Ghost': 'Ghost', 'Dart Goblin': 'BlowdartGoblin', 'Furnace': 'FirespiritHut',
    'The Log': 'Log',
}


def _norm(name):
    return ''.join(ch for ch in name.casefold() if ch.isalnum())


_BODY_INDEX = {}
for _card, _entry in NAMED.items():
    for _true, _proxy in _entry['body_map'].items():
        _key = _norm(_true)
        if _key in _BODY_INDEX and _BODY_INDEX[_key] != _proxy:
            raise ValueError(f'body {_true} maps to two proxies: {_card}')
        _BODY_INDEX[_key] = _proxy

_BLOCKED = {_norm(n) for n in CHAMPION_PROXIES | UNSAFE_PROXY_BODIES.keys()}
for _body in BODIES_47:
    _BODY_INDEX.setdefault(_norm(_body), None if _norm(_body) in _BLOCKED else _body)
for _alias, _body in BODY_ALIASES.items():
    _BODY_INDEX[_norm(_alias)] = _BODY_INDEX[_norm(_body)]

_CARD_INDEX = {_norm(n): n for n in NAMED | dict.fromkeys(C56)}
_CARD_INDEX.update({_norm(a): n for a, n in CARD_ALIASES.items()})

# Only unambiguous C56 deployments need a main-body lookup here. Mixed C56
# deployments have no unique main body: callers should provide observed bodies.
_C56_CARD_BODIES = {
    'Archer': 'Archer', 'AngryBarbarians': 'AngryBarbarian', 'Bats': 'Bat',
    'Goblins': 'Goblin_Stab', 'Minions': 'Minion', 'MinionHorde': 'Minion',
    'RoyalHogs': 'RoyalHog', 'Skeletons': 'Skeleton', 'SkeletonArmy': 'Skeleton',
    'Wallbreakers': 'Wallbreaker', 'FirespiritHut': 'Furnace_rework',
    'GoblinHut': 'GoblinHut_Rework',
}


def proxy_body(name: str, *, kind=None, air=None):
    """Resolve a body/card case-insensitively, keeping aliases in separate maps.

    Unknown names return None unless kind explicitly requests a class proxy.
    Known unplaced/unsafe bodies always return None, even with a class hint.
    For Spirit Empress supply observed air=True/False, or its exact form name.
    Copied Clone/Mirror bodies must be passed by observed body name.
    """
    key = _norm(name)
    if key in _BODY_INDEX:
        return _BODY_INDEX[key]
    card = _CARD_INDEX.get(key)
    if card in NAMED:
        entry = NAMED[card]
        if 'forms' in entry:
            if air is None:
                return None
            return next(f['proxy_body'] for f in entry['forms'].values() if f['air'] == air)
        return entry['proxy_body'] or None
    if card is not None:
        body = _C56_CARD_BODIES.get(card)
        return _BODY_INDEX.get(_norm(body)) if body else None
    if kind == 'building':
        return CLASS_ONLY['building']['proxy_body']
    if kind == 'troop':
        return CLASS_ONLY['air' if air else 'troop']['proxy_body']
    return None
