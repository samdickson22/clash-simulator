# S6 capacity interruptions

The 04 supervisor recorded 126 capacity pauses; 08 recorded none at the 07:46 UTC inspection. Each code-75 interruption preserves valid terminal receipts and restarts identical incomplete inputs with a fresh capacity label, as specified before confirmation. These are technical capacity interruptions, not outcome-dependent reruns. Final counts are in launch-<host>-r1.json.

The capacity receipt field `python_processes` sums workload NLWP (threads), despite its inherited name. Peak sampled total was 215 on 04 and 67 on 08. The 215 figure is not a process count. S6 had at most 64 single-thread game workers per host. When the host-wide workload rose, the supervisor signalled only unreaped direct S6 children and reduced its workload; other jobs were untouched. Detection is on the five-second monitoring grid.

A retained 04 process snapshot shows concurrent imitation shakedown/training and separate live-runtime replay workers. It cannot attribute the historical peak to a particular process. The supervisor counts those workloads conservatively; an unattended workload cap of 80 reserves 16 below the hard process cap. Console-user counts stayed zero in these receipts.

All interrupted CPU is included in the supervising GNU time record. Completed-game CPU alone understates the operational cost. No outcome was inspected during these interruptions.
