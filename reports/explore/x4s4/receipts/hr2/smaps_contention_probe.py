"""Offline (05): a process with a large file-backed mmap that page-faults from disk while another thread churns mmap/munmap
(mmap_lock writers). Prints its pid; runs for argv[2] seconds."""
import mmap, os, random, sys, threading, time
path, dur = sys.argv[1], float(sys.argv[2])
fd = os.open(path, os.O_RDONLY); size = os.fstat(fd).st_size
m = mmap.mmap(fd, size, prot=mmap.PROT_READ)
print(os.getpid(), flush=True); stop = time.monotonic()+dur
def faults():
    pg = mmap.PAGESIZE; n = size//pg
    while time.monotonic() < stop:
        i = random.randrange(n); _ = m[i*pg]
        if random.random() < 0.001: os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)   # force re-reads from disk
def churn():
    while time.monotonic() < stop:
        x = mmap.mmap(-1, 64 << 20); x[0:1] = b'x'; x.close()
ts = [threading.Thread(target=faults) for _ in range(6)] + [threading.Thread(target=churn) for _ in range(2)]
[t.start() for t in ts]; [t.join() for t in ts]
