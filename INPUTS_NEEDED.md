# Inputs still needed
1. ~~state.json.php~~ received. 403 diagnosed: see server_proposal/DIAGNOSIS_403.md.
2. `run_20261118_194511.log` - needed to confirm which failures were DNS (api.nobitex.ir, ecocoach.ir, emamigold.ir).
3. Schema-only export of `companies` / `prices` (db.php is NOT needed and must not be shared).
4. Per-source decision on fee models: several sources publish only a base price while production PHP adds a fee
   (e.g. +/-0.5%, +/-1%, +/-2%). The analyzer reports BASE_ONLY; whether the site should show a fee is a business choice.
