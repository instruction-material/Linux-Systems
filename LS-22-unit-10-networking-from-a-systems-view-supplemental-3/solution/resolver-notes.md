# Controlled DNS Diagnosis and Explicit Address Bypass

Retain predictions and cite your own saved observations. Running the equipment
does not complete this record. Use the shared README for the full sequence.

## 1. Predictions for the three DNS answers

Retain predictions before running: ready produces .1 and HTTP success; wrong produces .2 and a failed selected-address connection; missing produces NXDOMAIN with no selected-address HTTP request.

## 2. Independent ready-answer and socket comparison

Cite ready.json and an independent dig of the exact owned UDP address/port. Compare DNS answer .1, DNS PID, HTTP PID and HTTP 200. Do not confuse the DNS process/port with the web process/port.

## 3. Wrong answer versus explicit HTTP bypass

wrong-answer.json can have DNS NOERROR and a .2 answer while HTTP following that answer is refused. Its explicit .1 bypass still returns 200 from the unchanged app. A syntactically successful DNS response is not necessarily the desired address.

## 4. NXDOMAIN versus tool exit and unattempted request

nxdomain.json has a valid negative DNS response; dig can exit 0. The selected request is null because there is no A address. The separately named bypass tests HTTP without claiming ordinary DNS succeeded.

## 5. Restored fixture, limits and cleanup

Restart only the fixture in ready mode, record its actual new DNS port, and prove .1 plus selected-address HTTP 200. Stop both processes and compare exact UDP/TCP ss filters. Curl --resolve overrides one request's address; it does not repair global NSS/DNS configuration.
