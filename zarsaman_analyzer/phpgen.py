"""Proposed PHP recipes. Written to a separate folder; never deployed automatically."""
from __future__ import annotations
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

from .config import Config
from .models import CompanyResult, Mode, Status
from .recipes import RECIPES
from .security import redact

LIB = r'''<?php
// GENERATED helper (proposal only). TLS verification is ON. No spreads are ever synthesised.
declare(strict_types=1);

function zarsaman_http_get(string $url, array $headers = [], int $timeout = 12): array {
    $ch = curl_init($url);
    $h = ['Accept: application/json, */*;q=0.8'];
    foreach ($headers as $k => $v) { $h[] = $k . ': ' . $v; }
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true, CURLOPT_FOLLOWLOCATION => true, CURLOPT_MAXREDIRS => 4,
        CURLOPT_TIMEOUT => $timeout, CURLOPT_CONNECTTIMEOUT => min(6, $timeout),
        CURLOPT_SSL_VERIFYPEER => true, CURLOPT_SSL_VERIFYHOST => 2,
        CURLOPT_PROTOCOLS => CURLPROTO_HTTP | CURLPROTO_HTTPS, CURLOPT_REDIR_PROTOCOLS => CURLPROTO_HTTP | CURLPROTO_HTTPS,
        CURLOPT_ENCODING => '', CURLOPT_HTTPHEADER => $h,
        CURLOPT_USERAGENT => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36',
    ]);
    $body = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err = (string)curl_error($ch);
    curl_close($ch);
    return ['ok' => is_string($body) && $body !== '' && $code >= 200 && $code < 300, 'body' => is_string($body) ? $body : '', 'code' => $code, 'error' => $err];
}

/** Path syntax: a.b.0.c  or  list[key=value,key2=value2].field */
function zarsaman_pick($node, string $path) {
    foreach (explode('.', $path) as $tok) {
        if (!preg_match('/^([^\[\]]*)(?:\[(.+)\])?$/', $tok, $m)) { return null; }
        $name = $m[1]; $sel = $m[2] ?? '';
        if ($name !== '') {
            if (!is_array($node) || !array_key_exists($name, $node)) { return null; }
            $node = $node[$name];
        }
        if ($sel !== '') {
            if (!is_array($node)) { return null; }
            $conds = [];
            foreach (explode(',', $sel) as $pair) { [$k, $v] = array_pad(explode('=', $pair, 2), 2, ''); $conds[$k] = $v; }
            $found = null;
            foreach ($node as $item) {
                if (!is_array($item)) { continue; }
                $ok = true;
                foreach ($conds as $k => $v) { if ((string)($item[$k] ?? '') !== $v) { $ok = false; break; } }
                if ($ok) { $found = $item; break; }
            }
            if ($found === null) { return null; }
            $node = $found;
        }
    }
    return $node;
}

function zarsaman_num($v): ?float {
    if (is_int($v) || is_float($v)) { return (float)$v; }
    if (!is_string($v)) { return null; }
    $v = strtr($v, ['۰'=>'0','۱'=>'1','۲'=>'2','۳'=>'3','۴'=>'4','۵'=>'5','۶'=>'6','۷'=>'7','۸'=>'8','۹'=>'9','٬'=>'',','=>'',' '=>'']);
    return preg_match('/^-?\d+(\.\d+)?$/', $v) ? (float)$v : null;
}
'''


def _q(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _paths_for(r: CompanyResult) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    recipe = RECIPES.get(r.company_id) if r.recipe_id else None
    for ev in r.evidence:
        role = ev["role"]
        out[role] = {"paths": [ev["locator"]], "factor": ev["factor"]}
    if recipe:
        for role, paths in (("buy", recipe.buy), ("sell", recipe.sell), ("base", recipe.base)):
            if paths and role in out:
                out[role]["paths"] = list(paths)
    return out


def generate(results: List[CompanyResult], cfg: Config, out_dir: Path) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "fixtures").mkdir(exist_ok=True)
    files: List[Path] = []
    lib = out_dir / "_zarsaman_recipe_lib.php"
    lib.write_text(LIB, encoding="utf-8")
    files.append(lib)
    lo, hi = int(cfg.toman_range[0]), int(cfg.toman_range[1])
    for r in results:
        if r.status not in (Status.READY_FOR_PHP, Status.BASE_ONLY_READY) or not r.source_url:
            continue
        recipe = RECIPES.get(r.company_id)
        headers = recipe.headers if recipe else {}
        if recipe and recipe.method != "GET":
            continue
        spec = _paths_for(r)
        lines = [
            "<?php",
            f"// GENERATED PROPOSAL - company {r.company_id} ({r.name.replace(chr(10), ' ')}) - status {r.status.value}",
            "// NOT deployed. Review against run_scrapers.php before use. Evidence: " + redact("; ".join(r.reasons))[:200],
            "declare(strict_types=1);",
            "require_once __DIR__ . '/_zarsaman_recipe_lib.php';",
            "",
            f"function zarsaman_recipe_{r.company_id}(): array {{",
            f"    $url = {_q(redact(r.source_url))};",
            "    $headers = [" + ", ".join(f"{_q(k)} => {_q(v)}" for k, v in headers.items()) + "];",
            "    $r = zarsaman_http_get($url, $headers, 12);",
            "    if (!$r['ok']) { return ['success' => false, 'error' => 'fetch_failed http=' . $r['code'] . ' ' . $r['error']]; }",
            "    $json = json_decode($r['body'], true);",
            "    if (!is_array($json)) { return ['success' => false, 'error' => 'response_not_json']; }",
            "    $get = function (array $paths, float $factor) use ($json): ?float {",
            "        foreach ($paths as $p) { $n = zarsaman_num(zarsaman_pick($json, $p)); if ($n !== null && $n > 0) { return $n * $factor; } }",
            "        return null;",
            "    };",
        ]
        for role, s in spec.items():
            arr = "[" + ", ".join(_q(p) for p in s["paths"]) + "]"
            lines.append(f"    ${role} = $get({arr}, {float(s['factor'])!r});")
        lines.append(f"    $min = {lo}.0; $max = {hi}.0;")
        if r.mode == Mode.PAIR:
            lines += [
                "    if ($buy === null || $sell === null || $buy < $min || $buy > $max || $sell < $min || $sell > $max) { return ['success' => false, 'error' => 'pair_missing_or_out_of_range']; }",
                "    if ($buy > $sell) { return ['success' => false, 'error' => 'buy_gt_sell_needs_review']; }   // never swapped",
                "    return ['success' => true, 'mode' => 'PAIR', 'finalBuy' => (int)round($buy), 'finalSell' => (int)round($sell)];",
            ]
        else:
            lines += [
                "    if ($base === null || $base < $min || $base > $max) { return ['success' => false, 'error' => 'base_missing_or_out_of_range']; }",
                "    return ['success' => true, 'mode' => 'BASE_ONLY', 'finalBuy' => (int)round($base), 'finalSell' => (int)round($base)];   // single quote, no fabricated spread",
            ]
        lines.append("}")
        p = out_dir / f"company_{r.company_id}.php"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        files.append(p)
        if r.fixture:
            (out_dir / "fixtures" / f"company_{r.company_id}.json").write_text(redact(r.fixture), encoding="utf-8")
    return files


def lint(files: List[Path]) -> Dict[str, str]:
    php = shutil.which("php")
    if not php:
        return {"_": "php binary not found - syntax check skipped"}
    out = {}
    for f in files:
        p = subprocess.run([php, "-l", str(f)], capture_output=True, text=True)
        out[f.name] = (p.stdout + p.stderr).strip().splitlines()[0] if (p.stdout or p.stderr) else "?"
    return out
