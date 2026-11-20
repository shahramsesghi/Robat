# Why the analyzer got HTTP 403 (from the real state.json.php)

The server checks credentials with an `if / elseif` chain: **the first credential present wins** - X-API-Key, then
Authorization: Bearer, then ?key=, then ?secret=. The old analyzer sent all three. If the value typed into the launcher
was not exactly `ZAR_CRON_SECRET_99` (the constant hard-coded on the server), the wrong X-API-Key header won and the
correct `?key=` was never looked at -> `403 {"ok":false,"error":"forbidden"}`.

Fix: enter the server's exact key. The new analyzer sends X-API-Key only.

Things to fix on the server (see state.json.php.proposed):
1. The 403 body includes a `hint` that prints the secret to anyone who gets a 403.
2. The key is a constant in source and is the same as the cron secret in run_scrapers.php.
3. `?key=` / `?secret=` put the secret in URLs and access logs.
4. `Access-Control-Allow-Origin: *` on an authenticated endpoint.
Rotate the secret, since it has been exposed in the hint, the repo and the old analyzer.
