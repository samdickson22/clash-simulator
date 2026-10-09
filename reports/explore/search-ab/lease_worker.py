"""Lease-local CPU shard; only the absolute lease deadline counts paused time."""
from worker_runtime import main
if __name__=='__main__':main(leased=True)
