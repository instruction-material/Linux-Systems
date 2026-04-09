# Apache vs Nginx

- Apache expresses host routing with `<VirtualHost>` blocks; Nginx uses `server` blocks.
- Both point at a document root and both require a syntax check before reload.
- Nginx commonly fronts upstream apps with `proxy_pass`; Apache often uses modules
  such as `proxy` and `proxy_http` for similar behavior.
