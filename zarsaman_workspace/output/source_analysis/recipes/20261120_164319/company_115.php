<?php
// GENERATED PROPOSAL - company 115 (گنجه گلد) - status READY_FOR_PHP
// NOT deployed. Review against run_scrapers.php before use. Evidence: recipe_pair
declare(strict_types=1);
require_once __DIR__ . '/_zarsaman_recipe_lib.php';

function zarsaman_recipe_115(): array {
    $url = 'https://ganjegold.ir/api/v1/prices';
    $headers = [];
    $r = zarsaman_http_get($url, $headers, 12);
    if (!$r['ok']) { return ['success' => false, 'error' => 'fetch_failed http=' . $r['code'] . ' ' . $r['error']]; }
    $json = json_decode($r['body'], true);
    if (!is_array($json)) { return ['success' => false, 'error' => 'response_not_json']; }
    $get = function (array $paths, float $factor) use ($json): ?float {
        foreach ($paths as $p) { $n = zarsaman_num(zarsaman_pick($json, $p)); if ($n !== null && $n > 0) { return $n * $factor; } }
        return null;
    };
    $buy = $get(['data[asset_code=GOLD18].sell_price_toman'], 1.0);
    $sell = $get(['data[asset_code=GOLD18].buy_price_toman'], 1.0);
    $min = 15000000.0; $max = 35000000.0;
    if ($buy === null || $sell === null || $buy < $min || $buy > $max || $sell < $min || $sell > $max) { return ['success' => false, 'error' => 'pair_missing_or_out_of_range']; }
    if ($buy > $sell) { return ['success' => false, 'error' => 'buy_gt_sell_needs_review']; }   // never swapped
    return ['success' => true, 'mode' => 'PAIR', 'finalBuy' => (int)round($buy), 'finalSell' => (int)round($sell)];
}
