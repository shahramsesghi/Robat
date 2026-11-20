# Security
- API key: entered hidden in the launcher, held only in the process environment, removed afterwards, never logged
  (redaction filter on all log output and reports). It is sent only in the `X-API-Key` header.
- The previous analyzer put the key in the URL and used the default `ZAR_CRON_SECRET_99`, which is also the cron secret
  hard-coded in run_scrapers.php. **Rotate it** and keep the new value outside the repository.
- SSRF: http/https only, ports 80/443, private/loopback/link-local rejected after DNS resolution, every redirect hop re-checked.
- Response size capped (2 MB), timeouts everywhere, TLS verification ON (`--insecure` is opt-in).
- Vendor JavaScript/PHP is never executed. The browser stage only loads pages and records JSON responses.
- Checkpoints are written atomically. Recipes are written to a separate folder; nothing is deployed or written to the DB.
