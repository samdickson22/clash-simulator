"""E4 spawn children born between the ownership and census snapshots stay E4's;
identity-changed processes neither stay owned nor vouch for new descendants."""
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
        return dict(dict(self.own,pid=pid,ppid=100,start_ticks=pid-80,cmd=SPAWN,cmdline_sha256="a"*64),**fields)

    def pre(self,pid=101):
        """A child still showing its parent's argv (fork/vfork pre-exec)."""
        return self.worker(pid,cmd=self.own["cmd"],cmdline_sha256=self.own["cmdline_sha256"])

    def foreign_exec(self,row,**fields):
        return dict(dict(row,cmd="python3 foreign.py",cmdline_sha256="f"*64,exe="/opt/foreign/python3"),**fields)

    def shell(self,row):
        return dict(row,cmd="/bin/sh -c python3 foreign_child.py",cmdline_sha256="d"*64,exe="/bin/sh")

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

    def pids(self,rows):
        return sorted(r["pid"] for r in rows)

    # Positive: the diagnosed race (08 r2/r3), children and grandchildren.
    def test_spawn_children_seen_only_by_census_are_owned(self):
        early=[self.bus,self.own,self.worker(101)]
        late=early+[self.worker(102),self.worker(103)]
        reason,g=self.call(early,late)
        self.assertIsNone(reason,g["foreign_compute"]);self.assertEqual(g["foreign_compute"],[])
        self.assertEqual(self.owned(g),{100,101,102,103})
        reason,g=self.call(late,late)
        self.assertIsNone(reason);self.assertEqual(self.owned(g),{100,101,102,103})

    def test_late_grandchild_listed_before_its_parent_is_owned(self):
        grandchild=self.worker(103,ppid=102)
        reason,g=self.call([self.bus,self.own],[self.bus,grandchild,self.worker(102),self.own])
        self.assertIsNone(reason,g["foreign_compute"]);self.assertEqual(self.owned(g),{100,102,103})

    # Negatives: foreign processes and PID reuse.
    def test_real_foreign_python_is_still_flagged(self):
        foreign=dict(self.own,pid=300,ppid=1,pgid=300,start_ticks=300,cmd="python3 foreign.py",cmdline_sha256="f"*64)
        base=[self.bus,self.own,self.worker(101)]
        for first in (base,base+[foreign]):
            with self.subTest(in_first=len(first)>3):
                reason,g=self.call(first,base+[foreign,self.worker(102)])
                self.assertEqual(reason,"foreign_compute");self.assertEqual(self.pids(g["foreign_compute"]),[300])
                self.assertNotIn(300,self.owned(g))
        # A foreign python with the E4 cmdline, outside the E4 tree, is not owned.
        clone=dict(self.own,pid=301,ppid=1,start_ticks=301)
        reason,g=self.call(base,base+[clone])
        self.assertEqual(reason,"foreign_compute");self.assertEqual(self.pids(g["foreign_compute"]),[301])

    def test_reused_pid_with_new_start_ticks_is_not_owned(self):
        rows=[self.bus,self.own,self.worker(101)]
        self.assertIsNone(self.call(rows,rows)[0])
        for ppid in (1,100):
            with self.subTest(ppid=ppid):
                reused=self.foreign_exec(self.worker(101),ppid=ppid,start_ticks=999,exe="/usr/bin/python3")
                reason,g=self.call(rows,[self.bus,self.own,reused])
                self.assertEqual(reason,"foreign_compute")
                self.assertEqual([(r["pid"],r["start_ticks"]) for r in g["foreign_compute"]],[(101,999)])
                self.assertFalse(self.guard.audit.own_process(self.job,reused))

    # Negatives (Sol r1 F1/F2): a pinned six-KEY identity is never replaced.
    def test_arbitrary_exec(self):
        child=self.pre()
        reason,g=self.call([self.bus,self.own,child],[self.bus,self.own,self.foreign_exec(child)])
        self.assertEqual(reason,"foreign_compute");self.assertEqual(self.pids(g["foreign_compute"]),[101])
        self.assertEqual(self.guard.known_identity[101][4:],(self.own["cmdline_sha256"],"/usr/bin/python3"))

    def test_arbitrary_exec_active(self):
        child=self.pre();base=[self.bus,self.own,child]
        self.assertIsNone(self.call(base,base)[0])
        reason,g=self.call(base,[self.bus,self.own,self.foreign_exec(child,cpu_ticks=20)])
        self.assertEqual(reason,"foreign_compute")
        self.assertEqual(self.pids(g["foreign_compute"]),[101]);self.assertEqual(self.pids(g["foreign_active"]),[101])

    def test_repeated_exec(self):
        child=self.pre();first=dict(child,exe="/opt/foreign/one");second=dict(child,exe="/opt/foreign/two")
        for a,b in ((child,first),(first,second),(second,second)):
            reason,g=self.call([self.bus,self.own,a],[self.bus,self.own,b])
            self.assertEqual(reason,"foreign_compute");self.assertEqual(self.pids(g["foreign_compute"]),[101])
            # The ownership map reflects the ownership snapshot (as on 94d0e7f2).
            self.assertEqual(101 in self.owned(g),a is child)
        self.assertEqual(self.guard.known_identity[101][5],"/usr/bin/python3")

    def test_late_rearm(self):
        init=dict(self.own,pid=1,ppid=0,pgid=1,uid=0,start_ticks=1,cmd="/sbin/init",cmdline_sha256="c"*64,exe="/sbin/init")
        child=self.worker(101,ppid=102,start_ticks=23,cmd="/sbin/init",cmdline_sha256="c"*64)
        initial=[init,self.bus,self.own,self.worker(102),child]
        self.assertIsNone(self.call(initial,initial)[0])
        orphan=[init,self.bus,self.own,dict(child,ppid=1)]
        reason,g=self.call(orphan,orphan);self.assertIsNone(reason);self.assertIn(101,self.owned(g))
        late=[init,self.bus,self.own,self.foreign_exec(child,ppid=1)]
        reason,g=self.call(late,late)
        self.assertEqual(reason,"foreign_compute");self.assertNotIn(101,self.owned(g))
        self.assertEqual(self.guard.known_identity[101][4],"c"*64)

    # Negatives (Sol r1 F3): an identity-rejected ancestor vouches for no one,
    # whether the new descendant is first seen by the census or by both snapshots.
    def test_denied_parent_new_child(self):
        for both in (False,True):
            with self.subTest(child_in_ownership_snapshot=both):
                self.tearDown();self.setUp()
                base=[self.bus,self.own,self.worker(101)]
                self.assertIsNone(self.call(base,base)[0])
                child=self.worker(102,ppid=101,cmd="python3 foreign_child.py",cmdline_sha256="b"*64)
                denied=[self.bus,self.own,self.shell(self.worker(101)),child]
                reason,g=self.call(denied if both else base,denied)
                self.assertEqual(reason,"foreign_compute");self.assertEqual(self.pids(g["foreign_compute"]),[102])
                self.assertNotIn(102,self.owned(g));self.assertNotIn(102,self.guard.known_identity)

    def test_rejected_intermediate_late_grandchild(self):
        base=[self.bus,self.own,self.worker(101)]
        self.assertIsNone(self.call(base,base)[0])
        child=self.worker(102,ppid=101);grandchild=self.worker(103,ppid=102)
        reason,g=self.call(base,[self.bus,self.own,grandchild,self.shell(self.worker(101)),child])
        self.assertEqual(reason,"foreign_compute");self.assertEqual(self.pids(g["foreign_compute"]),[102,103])
        self.assertTrue({102,103}.isdisjoint(self.owned(g)));self.assertTrue({102,103}.isdisjoint(self.guard.known_identity))


if __name__=="__main__":unittest.main()
