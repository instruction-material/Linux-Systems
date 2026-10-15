# Interface, Route, Listener and Application Evidence

Retain predictions and cite your own saved observations. Running the equipment
does not complete this record. Use the shared README for the full sequence.

## 1. Prediction and layer map

Predict before looking: interface/address, route selection, TCP listener/PID, ICMP and HTTP are separate observations. Retain a mistaken initial prediction and explain the correction.

## 2. Actual interface, route, listener and application evidence

Cite first.json fields, including lo flags/address entries, selectedRoute, the exact ss local address/port and serving PID, and http status/body. UNKNOWN operstate alone is not proof of failure. Record the actual values rather than copying a PID from this guide.

## 3. Independent command comparison

Run the documented ip, ss and curl commands independently while the server is alive. Compare their live output to the saved record. A route lookup is not a packet-delivery test; ICMP success is not an HTTP-service test.

## 4. Stopped service changed case

missing.json can have HTTP 404/curl 22 with the original socket still present. After Ctrl-C, stopped.json should instead show no owned listener and a refused connection with HTTP status 0. If the ephemeral port was reused, record that evidence and repeat with a fresh owned server.

## 5. Restoration, narrow conclusions and cleanup

Restore a new ready server and cite restored.json's actual new port/PID, HTTP 200 and body. Stop it and show that its exact listener disappears. A collector exit of 0 means saved observations, not completed learner work or universal network health.
