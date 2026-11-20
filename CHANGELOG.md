# Changelog
## 1.0.0
- Rewrite as a modular package. Recipe verification first, strict generic discovery second.
- No synthetic spreads, no sorting to decide buy/sell, no magnitude-based unit guessing.
- State modes LIVE_STATE / LOCAL_CACHE / NO_REFERENCE; key sent only in X-API-Key.
- Repeat-visit validation, atomic checkpoints, resume, proposed PHP recipes (never deployed).

## 1.0.1
- Cookie-keeping redirects (fixes loops on Talaino/Melligold/Kifetala).
- Out-of-range labelled numbers are reported, never converted. New `probe` command.
- Recipe failures show missing paths and a body excerpt. Human `role_overrides.json`.
- Report lists identical quotes across companies.
