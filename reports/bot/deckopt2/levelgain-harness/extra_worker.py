"""Queue-only extension; frozen game/player construction is unchanged."""
import sam_worker as base
from sam_common import ROOT
_original_remote=base.remote
def remote(argv):
 return _original_remote([ROOT/'extra_queue.py' if str(v)==str(ROOT/'sam_queue.py') else v for v in argv])
base.remote=remote
if __name__=='__main__':base.main()
