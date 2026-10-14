# Users, groups and permissions: diagnose ancestor traversal

This Linux project creates one bounded directory tree under an empty directory
owned by an unprivileged account. It changes no system accounts, supplementary
groups or unrelated paths. Running as root is rejected because root can bypass
the access failure this lesson observes.

## Permission model

Each mode has owner, group and other classes. Read on a regular file permits
reading its bytes; write permits modifying bytes. Directory read permits
listing names, execute permits traversal and access to named children, and
write plus execute permits creating or removing directory entries. Deleting a
file is principally a permission on its containing directory, not its file
write bit. Effective group membership includes supplementary groups.

The supplied file is 0640 and belongs to the active account. Its private parent
is 0600: the same owner has read and write on the directory, but no traversal.
The file remains unreadable through that path. Adding owner execute to that
parent repairs access without broadening group or other permissions.

## Create, inspect and correct the owned lab

Extract one role and the guide. In an unprivileged Linux shell:

~~~sh
lab_root=$(mktemp -d)
bash task.sh setup "$lab_root"
bash task.sh inspect "$lab_root"
bash task.sh fix "$lab_root"
bash task.sh verify "$lab_root"
~~~

Setup prints can_read=no. Before the correction, verify returns status 1.
The reference fix prints can_read=yes; final verify confirms parent mode 0700
and unchanged file mode 0640. The starter fix is deliberately unfinished at
the named TODO. Replace it with one targeted command. Record the predicted and
observed results in permissions.md before comparing the reference.

To undo the correction inside this lab, set only the private parent back to
0600 and repeat inspect. To remove the disposable tree, first restore owner
traversal with the completed fix, verify the recorded lab_root value, then
remove exactly that directory. Setup refuses nonempty directories and later
operations require the owned marker and nonsymlink directory layout.

## Supplied service-identity case

The following case is fictional; the program's physical observations do not
prove access for other accounts. Predict it from identities and complete paths:

~~~text
0750 root:signal-web /srv/signal-garden
2750 deploy:signal-web /srv/signal-garden/releases
0640 deploy:signal-web /srv/signal-garden/releases/index.html
deploy and www-data belong to signal-web; observer does not.
~~~

deploy can traverse, read and write the file, and create or remove entries in
releases. www-data can traverse and read, but cannot write the file or change
directory entries. observer cannot traverse the first directory. A shared
group does not automatically grant write permission; the mode bits govern it.
The setgid bit on releases makes newly created entries inherit its group,
subject to the actual creation mode and umask.

## Walkthrough and completion evidence

Explain the owner/group/other selection before each observation. Locate the
first failed ancestor instead of recursively changing permissions. Completion
requires the TODO repair, the independent record, the supplied identity matrix
and an observed undo. A successful reference program does not complete the
worksheet or establish access for the fictional service accounts.
