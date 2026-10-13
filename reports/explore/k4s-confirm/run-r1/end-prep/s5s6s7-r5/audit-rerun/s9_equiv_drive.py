# AUDIT driver: S9 (scratch copy, unmodified code) with its documented test hook: the REPO_FULL constant points at a
# scratch byte copy of repo-full carrying synthetic END-JOB commits (/dev/shm/s567r5/audit/eqclone). Nothing else patched.
import sys
sys.path.insert(0, "/dev/shm/s567r5/audit/code/s3s9s10-r5")
import s9_end_runtime as S9
S9.REPO_FULL = "/dev/shm/s567r5/audit/eqclone"
sys.exit(S9.main(sys.argv[1:]))
