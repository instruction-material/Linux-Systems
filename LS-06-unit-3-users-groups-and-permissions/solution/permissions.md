# Permission evidence record

Predict the effect of file read permission and ancestor directory traversal separately. Record the active UID, supplementary groups, original modes, observed read result, exact correction and final modes. Explain why a file chmod cannot repair this ancestor failure. Complete the supplied identity matrix in the guide.

Reference: private starts at 0600 and index.html at 0640. Owner read on the file is insufficient because private lacks owner execute. Adding only u+x produces 0700 while the file remains 0640. The marker and identity checks constrain operations to an owned lab. These physical observations concern the active account; the separate service-identity matrix is a supplied reasoning case.
