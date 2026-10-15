# Listener Failure versus an HTTP Error

Retain predictions and cite your own saved observations. Running the equipment
does not complete this record. Use the shared README for the full sequence.

## 1. Predictions for bind, URL and application cases

Preserve initial predictions: the .1/.2 mismatch should fail before HTTP, /missing should return 404 from a live server, and unavailable /health should return 503 from a live server.

## 2. Wrong bind and changed client target

Use wrong-bind.json to cite the socket's .2 bind and the .1 client destination at the same numeric port. changed-target.json should reach that same serving PID at .2. This changed request has not moved the listening configuration.

## 3. Healthy versus missing path

With a .1 ready server, compare /health 200 with /missing 404/curl 22. Both bodies identify the same process. A missing path is evidence at the application protocol layer, not of an absent listener.

## 4. Listening but unavailable application

unavailable.json should retain an ss listener/PID and return 503/curl 22 with its unavailable body. The fixture sets this condition deliberately. A real incident needs application/dependency/log evidence before assigning a deeper cause.

## 5. Corrected request and socket cleanup

recovered.json should show the ready server's actual new PID/port and a successful /health. Independently compare ss and curl, then stop only that foreground process and confirm its socket is absent. Keep all earlier records.
