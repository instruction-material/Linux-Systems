# Concurrent Publishers and Kernel File Locks

This optional extension follows readiness, rollback and manifest inspection.
Those are single-publisher operations. This investigation asks what happens
when two independent processes both claim the same deployment generation,
and how a real nonblocking exclusive file lock coordinates them.

## Equipment, identity and the named repair

Use an ordinary Linux account with Bash, Python 3.8+, fcntl and /proc available.
Nginx is unnecessary for this file-coordination exercise. Keep task.sh,
lock_observer.py and publisher.py together in the extracted role. Edit/save/
export in the site IDE, then execute in that external Linux terminal.

The observer creates one private case under an explicit empty owned nonsymlink
parent. current.json begins with generation 0 and release initial. Each actual
publisher opens the same activation.lock inode, attempts its policy, records
its real PID/UID and observed generation, then waits at its own file barrier.
Publishing atomically replaces current.json with observedGeneration+1 and
the actor name. Atomic replacement alone does not coordinate two decisions
made from the same old generation.

The starter acquire_lock function returns True without requesting a lock.
Repair that function to call fcntl.flock on the open descriptor with LOCK_EX
and LOCK_NB. Return False when the kernel reports contention, preserving other
errors. Keep the descriptor open throughout the publication; closing it
releases the lock in this worker, which has no duplicated descriptor. File
locks are advisory: every cooperating publisher must
follow the same protocol. The existence of activation.lock is not ownership.

## Predict contention and observe the lost generation

From the extracted role folder:

~~~bash
lab_root=$(mktemp -d)
bash task.sh "$lab_root" > publishers.json 2> publishers.err
publisher_status=$?
printf 'status=%s\n' "$publisher_status"
cat publishers.err
cat publishers.json
~~~

The first alpha process reaches its readiness barrier. An independent parent
descriptor then makes an actual exclusive nonblocking flock attempt. After
repair that probe is blocked; in the starter it succeeds, showing that no
kernel lock is held despite the first publisher's claim.

While alpha is held, beta tries to publish. The reference returns status 75
for that contention and changes no state. Status 75 is the worker's chosen
exit convention; the kernel supplies a lock error, not that exit status. In the starter both processes
capture generation 0. The observer lets alpha publish generation 1, then beta
also publishes generation 1, replacing alpha's result without advancing the
generation for the second committed publication. Retain each PID, decision
and actual state snapshot rather than inferring coordination from the final
file alone.

After alpha exits, a fresh retry publisher acquires the lock and publishes
generation 2. A separate held publisher is interrupted with SIGINT, exits 130,
closes its descriptor and leaves generation 2 unchanged. A recovery publisher
then advances to generation 3. A final independent lock probe succeeds after
all actors exit. The inode stays the same throughout the case; no actor
unlinks/replaces the lock file while another descriptor can still refer to it.

Observation status 0 requires real exclusion, a rejected competing publisher,
recovery to generation 3 and released resources. The untouched starter exits 1
after recording its overlapping claims. These statuses do not complete the
independent locking-notes.md record. Run --reverse with the empty parent to
exchange the initial alpha/beta names; exclusivity and generation rules stay
the same.

## Interruption, rejection, recovery and undo

Use `--hold-seconds 8` to pause after the first publisher and the independent
probe. ready.json records its actual PID and lock inode. Inspect only that
owned actor with ps. Ctrl-C interrupts the observer; it stops/reaps its owned
publisher processes and emits status 130 with partial observations. Rerun
normally for recovery. Missing/nonempty/symlink parents and invalid hold values
are rejected; existing sentinels are preserved.

The report retains worker argv/PID/timing/status/output, lock device/inode,
independent probe results and errno, state generations, interruption and
cleanup. Check workerPidsGone, ownedCaseRemoved and workspaceEmpty, then remove
only the empty parent. Keep source files and outside inputs unchanged.
Complete all five notes tasks, explaining why an advisory lock is a protocol
for cooperating processes and why a final generation alone cannot prove
that every earlier publication was coordinated.

Primary reference: [Linux flock semantics and descriptor lifetime](https://man7.org/linux/man-pages/man2/flock.2.html).
