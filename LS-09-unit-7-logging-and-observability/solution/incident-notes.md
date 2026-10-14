# Incident evidence

Record the symptom, unit, boot, bounded time window, first relevant application error, rejected hypotheses, correction, retest and cleanup.

The redacted fixture names `config_missing` at 200 microseconds. A later, different invocation emits `ready` at 400 microseconds. The other boot, other unit and pre-window record do not belong to this case. The INFO message containing ERROR does not have error priority. These are fixture conclusions; live status and journal evidence must be collected separately.

Manager entries also belong to the case when USER_UNIT names the target, even if _SYSTEMD_USER_UNIT identifies init.scope. Keep these state explanations alongside the application diagnostic.
