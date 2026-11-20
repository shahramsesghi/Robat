"""Known extraction recipes.

Field mappings are taken from the production run_scrapers.php contract and are re-verified live by
the analyzer (fetch twice + range + stability). Units are DECLARED per recipe, never guessed.
A path may contain list selectors:  result[symbol=GLD_18C_750TMN,side=buy].price
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .units import parse_number

_TOKEN = re.compile(r"^([^\[\]]*)(?:\[(.+)\])?$")


def pick(node: Any, path: str) -> Any:
    cur = node
    for tok in path.split("."):
        m = _TOKEN.match(tok)
        if not m:
            return None
        name, sel = m.group(1), m.group(2)
        if name:
            if isinstance(cur, dict):
                if name not in cur:
                    return None
                cur = cur[name]
            elif isinstance(cur, list) and name.isdigit() and int(name) < len(cur):
                cur = cur[int(name)]
            else:
                return None
        if sel:
            if not isinstance(cur, list):
                return None
            conds = dict(p.split("=", 1) for p in sel.split(","))
            found = None
            for it in cur:
                if isinstance(it, dict) and all(str(it.get(k)) == v for k, v in conds.items()):
                    found = it
                    break
            if found is None:
                return None
            cur = found
    return cur


@dataclass
class Recipe:
    company_id: int
    name: str
    url: str
    unit: str                                  # declared: toman | rial | soot_toman
    buy: Tuple[str, ...] = ()                  # alternative paths, first hit wins
    sell: Tuple[str, ...] = ()
    base: Tuple[str, ...] = ()
    headers: Dict[str, str] = field(default_factory=dict)
    method: str = "GET"
    body: Optional[str] = None
    role_note: str = ""

    def extract(self, data: Any) -> Dict[str, Optional[float]]:
        def first(paths: Tuple[str, ...]) -> Tuple[Optional[float], str]:
            for p in paths:
                v = parse_number(pick(data, p))
                if v is not None and v > 0:
                    return v, p
            return None, ""
        out: Dict[str, Any] = {}
        for role, paths in (("buy", self.buy), ("sell", self.sell), ("base", self.base)):
            if paths:
                out[role] = first(paths)
        return out


def _r(cid, name, url, unit, **kw) -> Recipe:
    return Recipe(cid, name, url, unit, **kw)


_REF = lambda site: {"Referer": site, "Accept": "application/json"}

RECIPES: Dict[int, Recipe] = {r.company_id: r for r in [
    _r(5, "طلاینو", "https://talaino.com/gold/gold/gold-read.php?", "toman",
       base=("current", "daily.stats.current"), headers=_REF("https://talaino.com/")),
    _r(8, "وال گلد", "https://api.wallgold.ir/api/v1/prices", "toman",
       buy=("result[symbol=GLD_18C_750TMN,side=buy].price", "data[symbol=GLD_18C_750TMN,side=buy].price"),
       sell=("result[symbol=GLD_18C_750TMN,side=sell].price", "data[symbol=GLD_18C_750TMN,side=sell].price"),
       headers=_REF("https://wallgold.ir/"),
       role_note="both sides are usually identical; equal values collapse to BASE_ONLY"),
    _r(9, "زرافزا", "https://api.zarafza.com/v2/prices", "toman",
       buy=("data.G18.buy.price", "G18.buy.price"), sell=("data.G18.sell.price", "G18.sell.price"),
       headers=_REF("https://zarafza.com/"),
       role_note="production maps G18.buy.price->customer-sell-side per PHP; verify on site"),
    _r(11, "گلدنیا", "https://api.goldnia.com/api/v1/app/rates", "toman",
       base=("YekGram18", "data.YekGram18"), headers=_REF("https://goldnia.com/")),
    _r(13, "داریک", "https://apisc.daric.gold/loan/api/v1/User/Collateral/GetGoldlPrice", "toman",
       buy=("Data.BestBuyPrice", "data.bestBuyPrice"), sell=("Data.BestSellPrice", "data.bestSellPrice"),
       headers=_REF("https://daric.gold/")),
    _r(23, "عیاره", "https://ayyareh.com/general/getGoldPrice.php", "toman", base=("goldPrice",)),
    _r(26, "طلاسی", "https://api.talasea.ir/api/market/getGoldPrice", "soot_toman",
       base=("price", "data.price"), headers=_REF("https://talasea.ir/"),
       role_note="price is per soot; x1000 declared by production PHP"),
    _r(31, "زرلاین", "https://api.zarline.app/core/v1/markets/N2K1LGxd8B/price", "toman",
       base=("data.price", "price")),
    _r(36, "گلدیس", "https://goldis.ir/backend/api/v1/pricing/spot?metal=gold", "rial",
       base=("price_per_gram_rial",), headers=_REF("https://goldis.ir/")),
    _r(38, "بابیسط", "https://birjandigold.ir/get_price.php", "toman",
       buy=("site_sell_garam",), sell=("site_buy_garam",), headers=_REF("https://birjandigold.ir/"),
       role_note="site_sell_garam = customer sells to site (production mapping)"),
    _r(43, "تاپ‌گلد", "https://topgoldonline.com/wp-admin/admin-ajax.php?action=gpc_get_live_price", "toman",
       base=("data.price", "price"), headers={"Referer": "https://topgoldonline.com/", "X-Requested-With": "XMLHttpRequest"}),
    _r(66, "مهربان گلد", "https://mehrban.gold/api/config/goldprice?isSite=true", "toman",
       buy=("data.sell",), sell=("data.buy",), headers=_REF("https://mehrban.gold/"),
       role_note="data.buy = customer buys from site (production mapping)"),
    _r(70, "طلاوان", "https://goldcore.talaavan.com/v1/price", "rial",
       base=("rate", "data.rate"), headers=_REF("https://talaavan.com/"),
       role_note="same upstream feeds hztala(34) and kifetala(104)"),
    _r(80, "زیپا", "https://api.zipaapp.com/api/V1/gold/price", "soot_toman",
       base=("irg18k_price", "data.irg18k_price")),
    _r(83, "طلالند", "https://apigw.tala.land/market/GetLastPrice?code=G1", "soot_toman",
       base=("price", "data.price"), headers=_REF("https://www.tala.land/")),
    _r(84, "طلای ایران", "https://irjco.ir/api/gold/price/current", "toman",
       buy=("sellPrice",), sell=("buyPrice",), headers=_REF("https://irjco.ir/"),
       role_note="site buyPrice = customer buys (production mapping)"),
    _r(102, "آساکوین", "https://api.asacoine.com/api/v1/market/metals/price/GOLD-TMN", "toman",
       buy=("sellPrice", "data.sellPrice"), sell=("buyPrice", "data.buyPrice"), headers=_REF("https://asacoine.com/")),
    _r(109, "آبشده", "https://abshode.ir/wp-content/uploads/abshode-live/prices.json", "toman",
       buy=("buy",), sell=("sell",), headers=_REF("https://abshode.ir/")),
    _r(115, "گنجه گلد", "https://ganjegold.ir/api/v1/prices", "toman",
       buy=("data[asset_code=GOLD18].sell_price_toman",), sell=("data[asset_code=GOLD18].buy_price_toman",),
       role_note="API buy_price = customer buys (production mapping)"),
    _r(117, "مهرسان گلد", "https://api.mehrsun.gold/mehr/Mft23031", "toman",
       base=("YekGram18", "data.YekGram18"), headers=_REF("https://mehrsun.gold/")),
    _r(119, "میداس گلد", "https://midasgold.shop/api/gold/current-price", "toman",
       base=("gold_18k.value", "data.gold_18k.value"), headers=_REF("https://midasgold.shop/")),
    _r(123, "گلدینکس", "https://backend.goldinex.org/price", "toman",
       base=("gold_price", "data.gold_price"), headers=_REF("https://goldinex.org/")),
    _r(130, "اصف گلد", "https://esf.gold/api/prices/prices", "rial",
       base=("price", "data.price"), headers=_REF("https://esf.gold/")),
    _r(131, "زرین گلد", "https://api.zaringld.ir/api/admin/price", "toman",
       buy=("todaySellPrice", "data.todaySellPrice"), sell=("todayBuyPrice", "data.todayBuyPrice"),
       headers=_REF("https://zaringld.ir/")),
    _r(133, "طلای ژیک", "https://api.zhikgold.ir/api/v1/market-price", "toman",
       base=("price",), headers=_REF("https://zhikgold.ir/")),
]}
