# PHP review prompt

Review the proposed recipes in `recipes/20261120_164319/` against production `run_scrapers.php`.
Rules: preserve explicit buy/sell; never invent a spread; single quote = BASE_ONLY; do not swap buy/sell by sorting.
Do not deploy; do not touch the live DB.

## Verified candidates

- 5 طلاینو [BASE_ONLY_READY] https://talaino.com/gold/gold/gold-read.php? buy=23,485,000 sell=23,485,000
- 8 وال گلد [BASE_ONLY_READY] https://api.wallgold.ir/api/v1/prices buy=23,593,000 sell=23,593,000
- 11 گلدنیا [BASE_ONLY_READY] https://api.goldnia.com/api/v1/app/rates buy=23,561,000 sell=23,561,000
- 13 داریک [READY_FOR_PHP] https://apisc.daric.gold/loan/api/v1/User/Collateral/GetGoldlPrice buy=23,515,607 sell=23,627,464
- 23 عیاره [BASE_ONLY_READY] https://ayyareh.com/general/getGoldPrice.php buy=23,558,000 sell=23,558,000
- 26 طلاسی [BASE_ONLY_READY] https://api.talasea.ir/api/market/getGoldPrice buy=23,688,000 sell=23,688,000
- 31 زرلاین [BASE_ONLY_READY] https://api.zarline.app/core/v1/markets/N2K1LGxd8B/price buy=23,688,000 sell=23,688,000
- 36 گلدیس [BASE_ONLY_READY] https://goldis.ir/backend/api/v1/pricing/spot?metal=gold buy=23,522,550 sell=23,522,550
- 38 بابیسط [READY_FOR_PHP] https://birjandigold.ir/get_price.php buy=23,483,813 sell=23,629,208
- 43 تاپ‌گلد [BASE_ONLY_READY] https://topgoldonline.com/wp-admin/admin-ajax.php?action=gpc_get_live_price buy=23,627,000 sell=23,627,000
- 66 مهربان گلد [READY_FOR_PHP] https://mehrban.gold/api/config/goldprice?isSite=true buy=23,513,000 sell=23,655,000
- 70 طلاوان [BASE_ONLY_READY] https://goldcore.talaavan.com/v1/price buy=23,561,000 sell=23,561,000
- 83 طلالند [BASE_ONLY_READY] https://apigw.tala.land/market/GetLastPrice?code=G1 buy=23,609,000 sell=23,609,000
- 102 آساکوین [READY_FOR_PHP] https://api.asacoine.com/api/v1/market/metals/price/GOLD-TMN buy=23,448,460 sell=23,731,540
- 115 گنجه گلد [READY_FOR_PHP] https://ganjegold.ir/api/v1/prices buy=23,461,800 sell=23,604,000
- 117 مهرسان گلد [BASE_ONLY_READY] https://api.mehrsun.gold/mehr/Mft23031 buy=23,561,000 sell=23,561,000
- 123 گلدینکس [BASE_ONLY_READY] https://backend.goldinex.org/price buy=23,569,000 sell=23,569,000
- 130 اصف گلد [BASE_ONLY_READY] https://esf.gold/api/prices/prices buy=23,591,000 sell=23,591,000
- 131 زرین گلد [READY_FOR_PHP] https://api.zaringld.ir/api/admin/price buy=23,511,430 sell=23,550,674
- 133 طلای ژیک [BASE_ONLY_READY] https://api.zhikgold.ir/api/v1/market-price buy=23,561,000 sell=23,561,000

## Open items (human decision)

- 1 زرمینکس: https://api.zarminex.ir/function_url/: no_candidates | rejected_out_of_range: buy@buy=238183995; sell@sell=231074025; buy@base_buy=238183995; sell@base_sell=231074025 (unit unknown - verify on the sit
- 2 گلدیکا: https://api.goldika.ir/api/public/price: no_candidates | rejected_out_of_range: buy@data.price.buy=239463882; sell@data.price.sell=233784896; buy@data.discounted_price.buy=239463882; sell@data.discoun
- 3 طلایی شو: https://midas.talaeshow.com/api/v1/gold/live-price?commodity_id=3: no_candidates
- 4 تکنوگلد: https://technogold.gold: no_candidates
- 6 طلاین: https://taline.ir/: no_candidates
- 10 همراه گلد: https://hamrahgold.com/price-board: no_candidates
- 12 بازر: https://api.baazar.ir/landing/v1/price/: no_candidates | rejected_out_of_range: sell@data.sellPrice=235193913; buy@data.buyPrice=237502422 (unit unknown - verify on the site, then declare it in a reci
- 15 اینوی: https://invi.ir/gold-price: no_candidates
- 16 ملی‌گلد: https://melligold.com/: no_candidates
- 17 میلی گلد: https://milli.gold/api/v1/public/milli-price/external: no_candidates
- 18 طلانو: https://service.talano.ir/api/v1/market/price/?market_id=b0808638-7909-4468-83e9-ecac3d22499a: no_candidates | rejected_out_of_range: buy@buyPrice=23531; sell@sellPrice=23296 (unit unknown - verify on
- 19 دیجی‌کالا طلا: https://api.digikala.com/wealth/v1/prices/: no_candidates | rejected_out_of_range: base@gold18.price=237750; base@silver999.price=4024 (unit unknown - verify on the site, then declare it in a recipe)
- 20 زرگری: https://zaargari.com/: no_candidates
- 21 زرپی ۲۴: https://zarpay24.com/trade-gold: ambiguous_candidates=3 distinct_base=0
- 22 زریال‌گلد: https://www.tala.ir/banner/?ids=,&is-mobile=0&android=0&ios=0&h=1080&w=1920: no_candidates
- 24 توکنیکو: https://tokeniko.com/api/prices-with-change: no_candidates | rejected_out_of_range: sell@products.0.sellPrice=322522432; buy@products.0.buyPrice=320909820; sell@products.1.sellPrice=3783977; buy@produ
- 25 بازار طلا: explicit_labelled_pair; unresolved:buy_gt_sell,unit_unverified,product_unverified; buy_gt_sell; unit_unverified; product_unverified
- 27 نوبیتکس: https://nobitex.ir: no_candidates
- 28 آیگلدن: https://api.tgju.org/v1/widget/tmp?keys=137121,137122: no_candidates
- 30 ایران تی تی: https://irantt.com/: ambiguous_candidates=5 distinct_base=0
- 32 زرنیو: explicit_labelled_pair; unresolved:buy_gt_sell,unit_unverified,product_unverified; buy_gt_sell; unit_unverified; product_unverified
- 33 سکه پناه: https://www.panahcoin.com/rates/: no_candidates
- 34 اچ‌زد طلا: https://goldcore.talaavan.com/v1/price: no_candidates | rejected_out_of_range: base@data.rate=235610000 (unit unknown - verify on the site, then declare it in a recipe)
- 37 طلانار: https://talanar.ir/api/products-budget.php: no_candidates
- 39 اسنپ سرمایه: single_unique_base; unresolved:unit_unverified,product_unverified; unit_unverified; product_unverified
- 40 گرمی‌نو: explicit_labelled_pair; unresolved:buy_gt_sell,unit_unverified,product_unverified; buy_gt_sell; unit_unverified; product_unverified
- 41 اکوکوچ: https://ecocoach.net/_trading/prices/: ambiguous_candidates=2 distinct_base=2
- 42 مظنه‌اپ: https://mazaneapp.ir/: no_candidates
- 44 حامدگلد: https://hamedgold.ir: no_candidates
- 45 توچال‌گلد: https://tochal.gold/geram18/: no_candidates
- 46 مجیدگلد: https://api.majidgold.ir/api/initial-data: ambiguous_candidates=4 distinct_base=3
- 47 بانک طلا: https://mbank.gold/: no_candidates
- 49 امامی‌گلد: https://api.emamigold.com/api/price: no_candidates | rejected_out_of_range: buy@buyPrice=23607; sell@sellPrice=23294 (unit unknown - verify on the site, then declare it in a recipe)
- 54 جواهری حقانی: https://haghanigold.com/wp-admin/admin-ajax.php?action=dm_bank_calc_rates&asset=gold: ambiguous_candidates=4 distinct_base=0
- 56 طلاپ: explicit_labelled_pair; unresolved:buy_gt_sell,unit_unverified,product_unverified; buy_gt_sell; unit_unverified; product_unverified
- 57 گرمی: explicit_labelled_pair; unresolved:buy_gt_sell,unit_unverified,product_unverified; buy_gt_sell; unit_unverified; product_unverified
- 58 سکه نیک: https://nikcoin.me/: no_candidates
- 61 تبدیل: single_unique_base; unresolved:unit_unverified,product_unverified; unit_unverified; product_unverified
- 62 ازکی سرمایه: single_unique_base; unresolved:unit_unverified,product_unverified; unit_unverified; product_unverified
- 63 اکو گلد: explicit_labelled_pair; unresolved:buy_gt_sell,unit_unverified,product_unverified; buy_gt_sell; unit_unverified; product_unverified
- 67 مطلا: https://motalla.ir/board: no_candidates
- 81 دایا: https://www.goldendaya.ir/: no_candidates
- 86 سامانه معاملات TGJU: https://call5.tgju.org/ajax.json: no_candidates | rejected_out_of_range: base@tolerance_low.0.php:first-price=2923.1; base@tolerance_low.1.php:first-price=530.94; base@tolerance_low.2.php:first-price=
- 104 کیف طلا: https://kifetala.com: no_candidates
- 105 باطلام: https://batalam.com/: ambiguous_candidates=4 distinct_base=0
- 106 سه سکه: https://seseke.ir/: no_candidates
- 108 زرپین: single_unique_base; unresolved:unit_unverified,product_unverified; unit_unverified; product_unverified
- 111 قلک زرگرباشی: https://ghzar.com/: no_candidates
- 112 سلام گلد: buy_equals_sell_treated_as_base; unresolved:product_unverified; product_unverified
- 113 طلاکنش: https://api.farakonsh.ir/api/servant/Coin/GetByCode?orderType=40824&AccessKey=***REDACTED***&amount=1&moduleType=30021&Code=T18: no_candidates
- 114 طلانکس: explicit_labelled_pair; unresolved:buy_gt_sell,product_unverified; buy_gt_sell; product_unverified
- 118 ای شمش: https://eshemsh.ir/wp-admin/admin-ajax.php?action=get_gold_price: no_candidates | rejected_out_of_range: base@price=237056392.26187727 (unit unknown - verify on the site, then declare it in a recipe)
- 120 هجرت: https://hjrt.ir/: no_candidates
- 122 زیوتو: https://backend.sawiss.com/api/price-board: no_candidates | rejected_out_of_range: sell@data.products.0.sellPrice=243109867; buy@data.products.0.buyPrice=234876609.92; sell@data.products.1.sellPrice=3
- 124 آیساگلد: explicit_labelled_pair; unresolved:buy_gt_sell,unit_unverified,product_unverified; buy_gt_sell; unit_unverified; product_unverified
- 125 رضوانی: https://rezvanigold.ir/: no_candidates
- 126 گالری طلاکوب کاشان: https://info.talakoob.org/: no_candidates
- 127 طلای فتحی: https://fathigold.com/wp-admin/admin-ajax.php?action=fetch_marquee_prices: no_candidates
- 128 طلاوین: https://talawin.ir/: ambiguous_candidates=3 distinct_base=0
- 132 بله: single_unique_base; unresolved:unit_unverified,product_unverified; unit_unverified; product_unverified
- 134 زرین‌پیک: https://zarin-peyk.ir/api/v1/prices/Gold/history?: no_candidates
- 135 تیسا: explicit_labelled_pair; unresolved:unit_unverified,product_unverified; unit_unverified; product_unverified
- 136 مظفر: https://mozafar.gold/api/prices/latest: one_sided_quote_only
- 137 طلافروش: https://api.talaforosh.net/api/v1/products: no_candidates
- 138 طلای فرجی: https://farajigold.com/market/gold: no_candidates
- 140 گلدستن: https://goldstn.ir/: no_candidates
- 141 مهرکوثر: https://www.mehrekosar.ir/: no_candidates
- 142 ریماس گالری: explicit_labelled_pair; unresolved:unit_unverified,product_unverified; unit_unverified; product_unverified