"""OP-2: source-bound reader snapshots, with a <=2 s fork/exec confirmation.

No grace applies to an unproven source. Retain every observed child identity:
an exited unresolved child still denies its parent, even if later scans omit it.
"""
import json,time
from pathlib import Path
from common import plan,utc
from ssh_transport import authenticated

UID=3822945
SOURCE='129.65.221.14'
LIMIT=2.0

def identity(r):
    return tuple(r[k] for k in ('pid','start_ticks','uid','cmdline_sha256'))

def child_identity(r):
    return tuple(r[k] for k in ('pid','start_ticks','uid'))

def connection_ok(value):
    parts=(value or '').split()
    return len(parts)==4 and parts[0]==SOURCE and parts[3]=='22'

def descendants(parent,rows):
    found=[];pending=[parent['pid']];seen=set(pending)
    while pending:
        pid=pending.pop()
        for r in rows:
            if r['ppid']==pid and r['pid'] not in seen:
                found.append(r);seen.add(r['pid']);pending.append(r['pid'])
    return found

def transient(r,parent):
    # Only a fork before exec: empty argv or the inherited authenticated title.
    return r['uid']==UID and r['cmd'] in ('',parent['cmd'])

class Confirmation:
    def __init__(self,clock=time.monotonic,sleep=time.sleep):
        self.clock=clock;self.sleep=sleep;self.parents={}

    def apply(self,rows,j,collect,reader,block_ids=()):
        if plan()['compute']['perception_io_exception']['host']!='127x03':
            raise AssertionError('OP-2 host changed')
        import socket
        if socket.gethostname()!='127x03':return
        live_keys={identity(r) for r in rows if authenticated(r) and r['uid']==UID}
        self.parents={k:v for k,v in self.parents.items() if k[0]==str(j) and k[1] in live_keys}
        for parent in rows:
            if not authenticated(parent) or parent['uid']!=UID:continue
            original=descendants(parent,rows)
            if not original:continue
            key=(str(j),identity(parent));proof=self.parents.get(key)
            parent_conn=parent.get('ssh_connection_snapshot')
            if proof is None and parent_conn and connection_ok(parent_conn):
                proof=dict(parent_identity=list(identity(parent)),connection=parent_conn,
                           source_child_identity=None,evidence='parent snapshot')
            # Learn only from a reader recognized by the unchanged command/path rule.
            for child in original:
                conn=child.get('ssh_connection_snapshot')
                if (proof is None and connection_ok(conn) and reader(child,rows,source=conn)
                        and child['perception_io_allowlist']['ssh_ancestor_pid']==parent['pid']):
                    proof=dict(parent_identity=list(identity(parent)),connection=conn,
                               source_child_identity=list(identity(child)),evidence='child snapshot')
            if proof is None:continue # ordinary OP-1 denies; absolutely no wait
            self.parents[key]=proof
            started=self.clock();observed={};resolved={};latest=rows
            reason=None;deadline=started+LIMIT
            while True:
                current_parent=next((r for r in latest if r['pid']==parent['pid']),None)
                if current_parent is None or identity(current_parent)!=identity(parent):
                    reason='authenticated parent identity changed';break
                pc=current_parent.get('ssh_connection_snapshot')
                if pc and (not connection_ok(pc) or pc.split()!=proof['connection'].split()):reason='wrong parent source';break
                current=descendants(current_parent,latest)
                for child in current:
                    child_key=child_identity(child)
                    observed.setdefault(child_key,dict(child))
                    conn=child.get('ssh_connection_snapshot')
                    if child['uid']!=UID or (conn and (not connection_ok(conn) or conn.split()!=proof['connection'].split())):
                        reason='wrong child UID/source';break
                    if reader(child,latest,source=conn or proof['connection']):
                        resolved[child_key]=dict(child)
                    elif child_key in resolved:
                        # A reader executing a different command is never hidden by history.
                        reason='resolved child changed command';break
                    elif not transient(child,current_parent):
                        # Existing shell transport remains under the OP-1 subtree check.
                        children=[c for c in current if c['ppid']==child['pid']]
                        if not children or not child['cmd'] or Path(child['cmd'].split()[0]).name not in ('sh','bash'):
                            reason='non-reader child';break
                        resolved[child_key]=dict(child,op2_wrapper=True)
                if reason:break
                pending=set(observed)-set(resolved)
                if not pending:break
                now=self.clock()
                deadline=min(deadline,*(observed[k].get('snapshot_monotonic',started)+LIMIT for k in pending))
                if now>=deadline:reason='confirmation limit';break
                present={child_identity(c) for c in current}
                if not pending<=present:reason='exited unresolved child';break
                self.sleep(min(.02,deadline-now))
                latest=collect()
                if self.clock()>deadline:reason='confirmation limit';break
            receipt=dict(utc=utc(),block_ids=list(block_ids),parent_identity=list(identity(parent)),
                         source=proof,elapsed_seconds=self.clock()-started,limit_seconds=LIMIT,
                         accepted=reason is None,reason=reason,
                         observed=[dict(identity=list(k),ppid=v['ppid'],cmd=v['cmd'],
                                        cmdline_sha256=v['cmdline_sha256'],
                                        ssh_connection_snapshot=v.get('ssh_connection_snapshot')) for k,v in observed.items()],
                         resolved=[dict(identity=list(k),ppid=v['ppid'],cmd=v['cmd'],
                                        cmdline_sha256=v['cmdline_sha256'],
                                        reader_command=v.get('perception_io_allowlist',{}).get('command')) for k,v in resolved.items()])
            parent['op2_confirmation']=receipt
            if reason:
                parent['op2_denied']=reason;parent.pop('allowlist_kind',None)
            else:
                # The original snapshot is evidence even when that child has exited.
                for child in original:
                    final=resolved.get(child_identity(child))
                    if final and not final.get('op2_wrapper'):
                        child['allowlist_kind']='perception_reader'
                        child['op2_confirmation']=receipt
                # Include newly observed children so OP-1 examines their complete tree too.
                known={child_identity(r) for r in rows}
                for child_key,child in observed.items():
                    if child_key not in known:
                        row=dict(resolved[child_key]);row['op2_confirmation']=receipt
                        if not row.get('op2_wrapper'):row['allowlist_kind']='perception_reader'
                        rows.append(row);known.add(child_key)
            j.mkdir(parents=True,exist_ok=True)
            with (j/'op2-confirmations.jsonl').open('a') as f:
                f.write(json.dumps(receipt)+'\n')

CONFIRMATION=Confirmation()
