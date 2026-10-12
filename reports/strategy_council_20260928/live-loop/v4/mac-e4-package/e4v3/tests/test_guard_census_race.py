"""E4 spawn children born between the ownership and census snapshots stay E4's."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fleet_validity import ReportingGuard
from test_guard_seeds import stage_guard,fresh_modules

SPAWN="python3 -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=5, pipe_handle=7) --multiprocessing-fork"


class GuardCensusRaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.modules=fresh_modules();self.modules.__enter__()
        base=Path(self.tmp.name);manifest,self.bus,self.job,_=stage_guard(base)
        self.guard=ReportingGuard(base,manifest,[100])
        self.guard.audit.console=lambda:dict(positive=False);self.guard.audit.memory=lambda:30*2**30
        self.own=dict(self.bus,pid=100,ppid=1,pgid=90,start_ticks=10,uid=1000,exe="/usr/bin/python3",
                      cmd="python3 fleet_reference.py",cmdline_sha256="e"*64)

    def tearDown(self):
        self.modules.__exit__(None,None,None);self.tmp.cleanup()

    def worker(self,pid,**fields):
        return dict(self.own,pid=pid,ppid=100,start_ticks=pid-80,cmd=SPAWN,cmdline_sha256="a"*64,**fields)

    def call(self,first,census):
        """First processes() is the ownership snapshot; every later one (census
        and its identity re-scans) is the later census snapshot."""
        calls=[]
        def processes():
            calls.append(1);return copy.deepcopy(first if len(calls)==1 else census)
        self.guard.audit.processes=processes
        row={};reason=self.guard(row)
        self.assertGreater(len(calls),1)
        return reason,row["reporting_guard"]

    def owned(self,guard_row):
        return set(map(int,guard_row["owned_pid_start_ticks"]))

    def test_spawn_children_seen_only_by_census_are_owned(self):
        early=[self.bus,self.own,self.worker(101)]
        late=early+[self.worker(102),self.worker(103)]
        reason,g=self.call(early,late)
        self.assertIsNone(reason,g["foreign_compute"]);self.assertEqual(g["foreign_compute"],[])
        self.assertEqual(self.owned(g),{100,101,102,103})
        reason,g=self.call(late,late)
        self.assertIsNone(reason);self.assertEqual(self.owned(g),{100,101,102,103})

    def test_real_foreign_python_is_still_flagged(self):
        foreign=dict(self.own,pid=300,ppid=1,pgid=300,start_ticks=300,cmd="python3 foreign.py",cmdline_sha256="f"*64)
        base=[self.bus,self.own,self.worker(101)]
        for first in (base,base+[foreign]):
            with self.subTest(in_first=len(first)>3):
                reason,g=self.call(first,base+[foreign,self.worker(102)])
                self.assertEqual(reason,"foreign_compute")
                self.assertEqual([r["pid"] for r in g["foreign_compute"]],[300])
                self.assertNotIn(300,self.owned(g))
        # A foreign python with the E4 cmdline, outside the E4 tree, is not owned.
        clone=dict(self.own,pid=301,ppid=1,start_ticks=301)
        reason,g=self.call(base,base+[clone])
        self.assertEqual(reason,"foreign_compute");self.assertEqual([r["pid"] for r in g["foreign_compute"]],[301])

    def test_reused_pid_with_new_start_ticks_is_not_owned(self):
        rows=[self.bus,self.own,self.worker(101)]
        self.assertIsNone(self.call(rows,rows)[0])
        for ppid in (1,100):
            with self.subTest(ppid=ppid):
                reused=dict(self.worker(101),ppid=ppid,start_ticks=999,cmd="python3 foreign.py",cmdline_sha256="f"*64)
                reason,g=self.call(rows,[self.bus,self.own,reused])
                self.assertEqual(reason,"foreign_compute")
                self.assertEqual([(r["pid"],r["start_ticks"]) for r in g["foreign_compute"]],[(101,999)])
                self.assertEqual(g["owned_pid_start_ticks"]["101"],21)
                self.assertFalse(self.guard.audit.own_process(self.job,reused))

    def test_pre_exec_vfork_child_is_not_permanently_de_owned(self):
        pre=dict(self.worker(101),cmd=self.own["cmd"],cmdline_sha256=self.own["cmdline_sha256"])
        post=self.worker(101)
        for snapshots in (((pre,post),(post,post)),((pre,pre),(post,post)),((pre,pre),(pre,post),(post,post))):
            with self.subTest(snapshots=len(snapshots)):
                self.tearDown();self.setUp()
                for first,census in snapshots:
                    reason,g=self.call([self.bus,self.own,first],[self.bus,self.own,census])
                    self.assertIsNone(reason,g["foreign_compute"]);self.assertIn(101,self.owned(g))

    def test_exec_transition_is_once_and_keeps_pid_pgid_start_uid(self):
        pre=dict(self.worker(101),cmd=self.own["cmd"],cmdline_sha256=self.own["cmdline_sha256"])
        post=self.worker(101)
        rows=lambda child:[self.bus,self.own,child]
        self.assertIsNone(self.call(rows(pre),rows(post))[0])
        # A second identity change after exec is still refused (frozen OP-3),
        # in the census at once and in both snapshots thereafter.
        other=dict(post,cmdline_sha256="b"*64,cmd="python3 other.py")
        for first in (post,other):
            reason,g=self.call(rows(first),rows(other))
            self.assertEqual(reason,"foreign_compute");self.assertEqual([r["pid"] for r in g["foreign_compute"]],[101])
        self.assertNotIn(101,self.owned(g))
        # The one exec transition may not move pgid (or start_ticks/uid).
        self.tearDown();self.setUp()
        moved=dict(post,pgid=555)
        self.assertIsNone(self.call(rows(pre),rows(pre))[0])
        for first in (pre,moved):
            reason,g=self.call(rows(first),rows(moved))
            self.assertEqual(reason,"foreign_compute")
        self.assertNotIn(101,self.owned(g))

if __name__=="__main__":unittest.main()
