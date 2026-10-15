# Logical Paths, Physical Targets and Parent Traversal

This optional transfer follows the directory-purpose and static-site project.
A path used by a service or shell can include a symbolic link. Its visible name,
resolved target and parent traversal are separate observations. The project
reports those paths; it does not serve files, install a release, change
permissions or prove that a service is configured correctly. Complete
`path-notes.md` with predictions and actual results. The same pauses support
independent study and a paced walkthrough.

## Concepts and equipment

Use an ordinary account in an owned Linux lab with Bash. The site IDE edits,
saves and exports the source; execute these commands in the external Linux
terminal after extraction. The supplied program is read-only. The following
commands create a disposable directory/link example under one private parent.
They do not change `/srv`, `/etc`, `/var`, `/usr` or system configuration.

A symbolic link stores another path. A relative link target is interpreted
from the link's containing directory. Bash's logical directory mode retains
the traversed link spelling in PWD, while physical mode resolves the actual
directory. In logical mode `..` removes the last logical path component; in
physical mode it moves to the resolved directory's parent. These can differ.
Neither visible directory spelling nor an `ls` listing alone proves the target
that another program will open.

## Create a real link and predict the four paths

From the extracted role folder, retain the printed parent path in this shell:

~~~bash
lab_root=$(mktemp -d)
printf 'lab_root=%s\n' "$lab_root"
mkdir -p "$lab_root/physical/site"
printf '<h1>Owned example</h1>\n' > "$lab_root/physical/site/index.html"
ln -s physical/site "$lab_root/served"
readlink -- "$lab_root/served"
~~~

Predict these four values: logical directory, resolved physical directory,
logical parent and physical parent. For this arrangement the logical path ends
in `/served`, the physical path ends in `/physical/site`, the logical parent is
the private parent, and the physical parent ends in `/physical`. The absolute
prefix comes from this run; it is not supplied as an observation.

~~~bash
bash task.sh "$lab_root/served" > linked.paths 2> linked.err
trace_status=$?
printf 'status=%s\n' "$trace_status"
cat linked.err
while IFS= read -r -d '' field && IFS= read -r -d '' value; do
    printf '%s=%q\n' "$field" "$value"
done < linked.paths
~~~

The output is four field/value pairs, each separated by NUL. NUL cannot occur
inside a Unix path, while spaces and newlines can. The display loop quotes each
value for inspection without splitting it. Keep the binary record alongside
its decoded display. Do not use command substitution to store a NUL stream.

Independently compare Bash's own directory observations in a child shell:

~~~bash
(
    cd -L -- "$lab_root/served"
    pwd -L
    pwd -P
    (cd -L -- .. && pwd -L)
    (cd -P -- .. && pwd -P)
)
~~~

The four printed lines correspond to the four recorded fields for this
ordinary path arrangement. The binary program output also preserves paths
containing newlines, which plain line output cannot label unambiguously.

The starter deliberately computes the field named physical_parent using
logical traversal at its single TODO. Repair that flag so the field describes
the physical parent. Keep the other three observations, argument boundary and
binary stream unchanged. Compare the reference after recording a working
attempt. Status 0 means all four observations completed; it does not mean the
starter's named decision is repaired or the worksheet is complete. Status 2
means invalid input or an unsupported environment, and a failed directory
change can return 1. Discard a partial record as a complete result.

## Compare direct access and another logical spelling

~~~bash
bash task.sh "$lab_root/physical/site" > direct.paths 2> direct.err
ln -s physical/site "$lab_root/another view"
bash task.sh "$lab_root/another view" > alternate.paths 2> alternate.err
~~~

The two link spellings have different logical paths and the same physical
path. Direct access has the same logical and physical directory. Record each
run's status and decode its record independently. Verify the document remains
unchanged. A `cd` inside the program runs in a child shell and does not change
the caller's working directory.

For a changed case, create a failed target and then correct that exact link:

~~~bash
ln -s missing-target "$lab_root/broken"
bash task.sh "$lab_root/broken" > broken.paths 2> broken.err
broken_status=$?
printf 'broken=%s\n' "$broken_status"
rm -- "$lab_root/broken"
ln -s physical/site "$lab_root/broken"
bash task.sh "$lab_root/broken" > corrected.paths 2> corrected.err
corrected_status=$?
printf 'corrected=%s\n' "$corrected_status"
external_root=$(mktemp -d)
printf 'external_root=%s\n' "$external_root"
mkdir -- "$external_root/target"
ln -s "$external_root/target" "$lab_root/outside view"
bash task.sh "$lab_root/outside view" > outside.paths 2> outside.err
~~~

Record how a name inside the first tree resolves outside that tree. The
program reports the selected readable path and does not enforce containment.
This is a path-observation exercise, not a deployment or access-control check.
No arbitrary production path is needed for the experiment.

## Retain evidence and clean up

Complete the five notes tasks with the predicted and actual paths, the TODO
repair, direct/alternate comparisons, failed target and corrected target.
Verify the source bytes, current identity and caller directory remain as
recorded. Remove the exact disposable directories after reviewing their
printed values; keep the saved workspace and result records separately.

~~~bash
printf 'Review before removal: %q\n' "$lab_root" "$external_root"
rm -r -- "$lab_root" "$external_root"
~~~

Primary references: [Bash cd modes](https://www.gnu.org/software/bash/manual/html_node/Bourne-Shell-Builtins.html)
and [GNU symbolic links](https://www.gnu.org/s/coreutils/manual/html_node/ln-invocation.html).
