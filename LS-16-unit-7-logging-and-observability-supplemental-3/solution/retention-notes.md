# Retention evidence

Record the owned path, policy, actual logrotate version, state file, preview, three rotations, compressed archive contents, active-file mode, unchanged external sentinel and cleanup.

With rotate 2, three forced nonempty rotations retain the second and third batches as app.log.2.gz and app.log.1.gz. The first batch expires. A new empty app.log has mode 0600. An empty run does not shift archives. These conclusions require actual logrotate execution.
