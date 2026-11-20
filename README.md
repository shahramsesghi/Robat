# Zarsaman Analyzer 1.0

Verifies and discovers live 18-karat gold prices (Toman/gram) for the sellers on zarsaman.ir.
Principle: **an honest NEEDS_REVIEW beats a wrong price.**

## Quick start (Windows)
1. Unzip, put your sources export at `zarsaman_workspace\input\sources.csv` (a sample is included).
2. Double-click `START_ANALYZER.bat`, type the state API key (hidden) or press Enter for offline mode.
3. Open `zarsaman_workspace\output\source_analysis\REPORT_<run>.md`.

## Commands
    python -m zarsaman_analyzer doctor
    python -m zarsaman_analyzer status
    python -m zarsaman_analyzer run --stage both
    python -m zarsaman_analyzer run --stage http --only-failed --company-id 131 --limit 10 --workers 4 --resume --offline --no-browser
Flags: `--only-failed --only-stale --skip-fresh-minutes N --stage2-all --company-id --limit --workers --resume --offline --no-browser --insecure`.

## Diagnosing a failing source
    python -m zarsaman_analyzer probe --company-id 109
Prints HTTP status, body excerpt, every candidate and every number rejected as out-of-range for that company.

## Human role overrides
If a source labels buy/sell from the customer's side (`buy > sell`), the run writes `role_overrides_TEMPLATE_<run>.json`.
After VERIFYING on the site, copy it to `zarsaman_workspace\input\role_overrides.json` and set `"labels_inverted": true`.
The swap is then applied explicitly and recorded as `human_override`. It is never inferred automatically.

## How it decides
- **Recipes** (`recipes.py`, ~27 sources): field mappings copied from production `run_scrapers.php`, units *declared* per recipe.
  They are re-verified live: fetched twice, range-checked, stability within 0.5%.
- **Generic discovery** for the rest: only labelled JSON keys; unit only from explicit words (toman/rial); a result is READY only
  if the key also names the product (18k/750). Otherwise NEEDS_REVIEW. HTML text is always NEEDS_REVIEW.
- Statuses: `READY_FOR_PHP` (explicit buy/sell, stable), `BASE_ONLY_READY` (one quote), `NEEDS_REVIEW`, `FAIL`, `SKIPPED`.
- `buy > sell` from a source is **never swapped**; it becomes NEEDS_REVIEW.
- Aggregator URLs (goldinex, zarscan, zarscope, talabaz) are never primary evidence. CAPTCHA/analytics URLs are dropped.
- Silver (1018, 1038 or name contains نقره) and tickers (71-79, 90-101) are SKIPPED.

## State modes
LIVE_STATE (HTTP 200, valid JSON, ok=true) | LOCAL_CACHE (file; never called live) | NO_REFERENCE. Shown in every report.

## Tests
    python -m unittest discover -s tests -t .

## Limits
The browser stage (Playwright) and live HTTP were not run in the build environment (no network). PHP `php -l` was not run (no PHP there).
