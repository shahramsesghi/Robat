<?php
// GENERATED PROPOSAL - company 43 (تاپ‌گلد) - status BASE_ONLY_READY
// NOT deployed. Review against run_scrapers.php before use. Evidence: recipe_base
declare(strict_types=1);
require_once __DIR__ . '/_zarsaman_recipe_lib.php';

function zarsaman_recipe_43(): array {
    $url = 'https://topgoldonline.com/wp-admin/admin-ajax.php?action=gpc_get_live_price';
    $headers = ['Referer' => 'https://topgoldonline.com/', 'X-Requested-With' => 'XMLHttpRequest'];
    $r = zarsaman_http_get($url, $headers, 12);
    if (!$r['ok']) { return ['success' => false, 'error' => 'fetch_failed http=' . $r['code'] . ' ' . $r['error']]; }
    $json = json_decode($r['body'], true);
    if (!is_array($json)) { return ['success' => false, 'error' => 'response_not_json']; }
    $get = function (array $paths, float $factor) use ($json): ?float {
        foreach ($paths as $p) { $n = zarsaman_num(zarsaman_pick($json, $p)); if ($n !== null && $n > 0) { return $n * $factor; } }
        return null;
    };
    $base = $get(['data.price', 'price'], 1.0);
    $min = 15000000.0; $max = 35000000.0;
    if ($base === null || $base < $min || $base > $max) { return ['success' => false, 'error' => 'base_missing_or_out_of_range']; }
    return ['success' => true, 'mode' => 'BASE_ONLY', 'finalBuy' => (int)round($base), 'finalSell' => (int)round($base)];   // single quote, no fabricated spread
}
