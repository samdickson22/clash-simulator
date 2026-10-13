# AUDIT driver: S10 (scratch copy, unmodified) with its documented test hook S10.SSH_BINARY -> namespaced fake ssh.
import sys
sys.path.insert(0, "/dev/shm/ia-r1/code/s3s9s10-r3")
import s10_stage_host as S10
S10.SSH_BINARY = "/dev/shm/ia-r1/drivers/fake-ssh"
sys.exit(S10.main(sys.argv[1:]))
