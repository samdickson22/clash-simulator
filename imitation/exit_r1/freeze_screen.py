"""Bind the coordinator-approved plan/audit and final model/runtime inputs."""
import argparse
from .screen import ARMS,freeze_inputs


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--plan-sha256',required=True)
    p.add_argument('--seed-audit',required=True);p.add_argument('--native',required=True)
    p.add_argument('--init',required=True);p.add_argument('--S-mix',dest='mix',required=True)
    p.add_argument('--S-teacher',dest='teacher',required=True);p.add_argument('--S-human',dest='human',required=True)
    p.add_argument('--output',required=True);a=p.parse_args()
    checkpoints=dict(zip(('init',*ARMS),(a.init,a.mix,a.teacher,a.human)))
    print(freeze_inputs(a.plan,a.plan_sha256,a.seed_audit,checkpoints,a.native,a.output))


if __name__=='__main__':main()
