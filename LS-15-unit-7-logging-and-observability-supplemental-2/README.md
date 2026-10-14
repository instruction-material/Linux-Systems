# Log Investigation Transfer Practice

This optional project transfers the core investigation habit to structured
application records. It is distinct from the user-service journal project:
request identity, completion event and numeric HTTP status answer whether one
request failed and whether a later completed retry recovered. An application
message is not a service-manager exit result, and a recorded 200 does not prove
the current service is available.

## Supplied source and learner task

`sample.log` contains redacted JSON-per-line events for case-7 plus an unrelated
request. `task.sh` supplies input validation, explicit timezone handling,
chronological ordering and reporting. Complete `is_server_failure`: a server
failure is a completed response whose numeric status is from 500 through 599.
Starting a request is not a response, 400 is a client response rather than a
server failure, and a message containing ERROR is not itself a classification.
The embedded Python receives a dictionary named row. Square-bracket access
reads an already validated field. Check the completion event before reading
status: start records have no response status. Python and short-circuits, so
its right-hand condition is evaluated only when its left-hand condition holds.
The reference completes the same named function; `application-notes.md` records
causal reasoning and limitations. No network request is performed by this pack.

## Predict, run and explain

From the selected role directory:

~~~sh
bash task.sh sample.log case-7
~~~

The untouched starter exits 78 with its named task. After completion, case-7
has four events, responses 503 then 200, exactly one server failure and a later
recorded recovery. Recovery is measured after the latest server failure; a
newer 503 reopens the case until a later completed 200. The other request's 500 is excluded. A 200 before a later
503 does not recover that later failure. A request start without a completion leaves
lastStatus null and cannot establish success. UTC offsets are compared as
instants, not as strings; each timestamp needs a timezone. Missing input,
invalid JSON, a string or boolean status, or an invalid timestamp fails with
status 2 rather than being silently converted to a zero count.

Copy the supplied records to a temporary file before changed-case work. Test a
400 response, a 599 response, a different request, shuffled input order, an
incomplete retry and timestamps expressed with equivalent UTC offsets. Record
predictions before running each changed case. Keep a malformed-input failure
separate from a valid empty request selection.

## Review and boundaries

Use the notebook to state the symptom, chosen request, ordered response
statuses, first failure, later completion, excluded noise, remaining unknowns
and one changed-case result. The source and command sequence support both
independent reading and a paced walkthrough. Compare the reference after
an attempted draft; preserve every earlier saved attempt. Only supplied
or explicitly redacted records are needed, and no production log collection
or private data upload is part of this project. The site IDE supports source
editing, save/reopen and exact ZIP export; execute this Bash/Python tool in the
Linux terminal. No pip dependency is required.
