import bootstrap
from bootstrap import HERE
import cProfile,pstats
code=(HERE/'dev_replay.py').read_text().replace("for row in data['rows']:","for row in data['rows'][:600]:")
namespace={'__name__':'profile_dev_replay'};exec(compile(code,'profile_dev_replay','exec'),namespace)
p=cProfile.Profile();p.enable();namespace['run'](0,'profile');p.disable();pstats.Stats(p).sort_stats('tottime').print_stats(18)
