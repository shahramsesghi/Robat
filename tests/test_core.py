import json, tempfile, unittest, os
from pathlib import Path

from zarsaman_analyzer.analyzer import analyze_company, stable
from zarsaman_analyzer.checkpoint import Checkpoint
from zarsaman_analyzer.config import Config
from zarsaman_analyzer.http import FetchResult, classify_error
from zarsaman_analyzer.inventory import Company, SourceUrl, load_inventory
from zarsaman_analyzer.models import Candidate, CompanyResult, Mode, StateMode, Status
from zarsaman_analyzer.phpgen import generate, lint
from zarsaman_analyzer.recipes import RECIPES, pick
from zarsaman_analyzer.roles import classify_key, resolve, walk_json
from zarsaman_analyzer.security import check_url, redact
from zarsaman_analyzer.state import StateClient, diagnose
from zarsaman_analyzer.units import UnknownUnit, normalize, parse_number
from .helpers import FakeFetcher, ok

NOSLEEP = lambda s: None


def cfg_tmp():
    c = Config()
    c.workspace = Path(tempfile.mkdtemp())
    c.ensure_dirs()
    return c


def co(cid, name, urls, **kw):
    return Company(cid, name, [SourceUrl(u, k, a) for u, k, a in urls], **kw)


class TestUnits(unittest.TestCase):
    def test_rial_to_toman(self):
        self.assertEqual(normalize(263170000, "rial"), 26317000.0)

    def test_toman_passthrough(self):
        self.assertEqual(normalize(24500000, "toman"), 24500000.0)

    def test_unknown_unit_rejected(self):
        with self.assertRaises(UnknownUnit):
            normalize(1, "mesghal")

    def test_no_magnitude_conversion(self):
        # 26270 looks like soot but generic discovery must not convert it
        c = Config()
        cands = walk_json({"buyPrice": 26270, "sellPrice": 26100}, "u", c)
        self.assertEqual(cands, [])      # out of toman range, not auto-multiplied

    def test_parse_number_persian(self):
        self.assertEqual(parse_number("۲۴٬۵۰۰٬۰۰۰"), 24500000.0)
        self.assertIsNone(parse_number("abc"))


class TestRoles(unittest.TestCase):
    cfg = Config()

    def test_key_classification(self):
        self.assertEqual(classify_key("buyPrice"), "buy")
        self.assertEqual(classify_key("todaySellPrice"), "sell")
        self.assertEqual(classify_key("platform_buy"), "buy")
        self.assertIsNone(classify_key("buy_change_percent"))
        self.assertIsNone(classify_key("max_24h_price"))

    def test_pair_preserved_without_spread(self):
        r = resolve(walk_json({"data": {"buy_price_toman": 24400000, "sell_price_toman": 24600000}}, "u", self.cfg))
        self.assertEqual((r.mode, r.buy, r.sell), (Mode.PAIR, 24400000.0, 24600000.0))

    def test_buy_gt_sell_never_swapped(self):
        r = resolve(walk_json({"buy_toman": 24900000, "sell_toman": 24400000}, "u", self.cfg))
        self.assertEqual((r.buy, r.sell), (24900000.0, 24400000.0))
        self.assertIn("buy_gt_sell", r.flags)

    def test_base_only(self):
        r = resolve(walk_json({"price_toman": 24500000}, "u", self.cfg))
        self.assertEqual(r.mode, Mode.BASE_ONLY)
        self.assertEqual(r.buy, r.sell)

    def test_duplicate_collapse(self):
        c = [Candidate("u", "a.price", 1, "base", "toman", 1, 24500000.0), Candidate("u", "a.price", 1, "base", "toman", 1, 24500000.0),
             Candidate("u", "b.rate", 1, "base", "toman", 1, 24500000.0)]
        self.assertEqual(resolve(c).mode, Mode.BASE_ONLY)

    def test_ambiguous_rejected(self):
        r = resolve(walk_json({"a": {"price_toman": 24500000}, "b": {"price_toman": 25100000}}, "u", self.cfg))
        self.assertEqual(r.mode, Mode.NONE)
        self.assertIn("ambiguous", r.reason)

    def test_unspecified_unit_flagged(self):
        r = resolve(walk_json({"buy": 24400000, "sell": 24600000}, "u", self.cfg))
        self.assertIn("unit_unverified", r.flags)
        self.assertIn("product_unverified", r.flags)


class TestRecipePath(unittest.TestCase):
    def test_selector(self):
        d = {"result": [{"symbol": "X", "side": "buy", "price": "1"}, {"symbol": "GLD", "side": "sell", "price": "2"}]}
        self.assertEqual(pick(d, "result[symbol=GLD,side=sell].price"), "2")
        self.assertIsNone(pick(d, "result[symbol=NOPE].price"))


class TestAnalyze(unittest.TestCase):
    def test_recipe_pair_ready(self):
        cfg = cfg_tmp()
        rec = RECIPES[131]
        body = {"todaySellPrice": 24800000, "todayBuyPrice": 24850000}
        f = FakeFetcher({rec.url: [body, {"todaySellPrice": 24801000, "todayBuyPrice": 24850500}]})
        r = analyze_company(co(131, "زرین", [(rec.url, "api", False)]), cfg, f, sleep=NOSLEEP)
        self.assertEqual(r.status, Status.READY_FOR_PHP)
        self.assertEqual((r.final_buy, r.final_sell), (24800000.0, 24850000.0))   # no spread invented
        self.assertTrue(r.stable)

    def test_recipe_rial_unit(self):
        cfg = cfg_tmp()
        rec = RECIPES[130]
        f = FakeFetcher({rec.url: {"price": 263170000}})
        r = analyze_company(co(130, "esf", [(rec.url, "api", False)]), cfg, f, sleep=NOSLEEP)
        self.assertEqual(r.status, Status.BASE_ONLY_READY)
        self.assertEqual(r.final_buy, 26317000.0)

    def test_recipe_soot_declared(self):
        cfg = cfg_tmp()
        rec = RECIPES[26]
        f = FakeFetcher({rec.url: {"price": "24492"}})
        r = analyze_company(co(26, "talasea", [(rec.url, "api", False)]), cfg, f, sleep=NOSLEEP)
        self.assertEqual(r.final_buy, 24492000.0)
        self.assertEqual(r.status, Status.BASE_ONLY_READY)

    def test_recipe_buy_gt_sell_needs_review(self):
        cfg = cfg_tmp()
        rec = RECIPES[131]
        f = FakeFetcher({rec.url: {"todaySellPrice": 24900000, "todayBuyPrice": 24400000}})
        r = analyze_company(co(131, "x", [(rec.url, "api", False)]), cfg, f, sleep=NOSLEEP)
        self.assertEqual(r.status, Status.NEEDS_REVIEW)
        self.assertEqual((r.final_buy, r.final_sell), (24900000.0, 24400000.0))

    def test_repeat_instability(self):
        cfg = cfg_tmp()
        rec = RECIPES[133]
        f = FakeFetcher({rec.url: [{"price": "24000000"}, {"price": "25000000"}]})
        r = analyze_company(co(133, "zhik", [(rec.url, "api", False)]), cfg, f, sleep=NOSLEEP)
        self.assertEqual(r.status, Status.NEEDS_REVIEW)
        self.assertFalse(r.stable)

    def test_second_visit_failure(self):
        cfg = cfg_tmp()
        rec = RECIPES[133]
        f = FakeFetcher({rec.url: [{"price": "24000000"}, FetchResult(url="", error="HTTP 500", status=500)]})
        r = analyze_company(co(133, "zhik", [(rec.url, "api", False)]), cfg, f, sleep=NOSLEEP)
        self.assertEqual(r.status, Status.NEEDS_REVIEW)

    def test_dns_failure_classified(self):
        cfg = cfg_tmp()
        r = analyze_company(co(9999, "x", [("https://nonexistent.example/api", "api", False)]), cfg, FakeFetcher({}), sleep=NOSLEEP)
        self.assertEqual(r.status, Status.FAIL)
        self.assertEqual(r.failure_class, "dns")
        self.assertEqual(classify_error("getaddrinfo failed"), "dns")

    def test_generic_never_ready_without_evidence(self):
        cfg = cfg_tmp()
        u = "https://site.example/api"
        f = FakeFetcher({u: {"buy": 24400000, "sell": 24600000}})
        r = analyze_company(co(500, "g", [(u, "api", False)]), cfg, f, sleep=NOSLEEP)
        self.assertEqual(r.status, Status.NEEDS_REVIEW)

    def test_generic_explicit_evidence_ready(self):
        cfg = cfg_tmp()
        u = "https://site.example/api"
        body = {"gold18k_buy_toman": 24400000, "gold18k_sell_toman": 24600000}
        r = analyze_company(co(500, "g", [(u, "api", False)]), cfg, FakeFetcher({u: body}), sleep=NOSLEEP)
        self.assertEqual(r.status, Status.READY_FOR_PHP)

    def test_aggregator_not_primary(self):
        cfg = cfg_tmp()
        r = analyze_company(co(501, "a", [("https://backend.goldinex.org/price/website/comparison", "api", True)]), cfg, FakeFetcher({}), sleep=NOSLEEP)
        self.assertEqual(r.status, Status.SKIPPED)

    def test_silver_and_ticker_excluded(self):
        cfg = cfg_tmp()
        for cid, name in ((1018, "اینوی نقره"), (73, "گرم طلا ۱۸ عیار"), (90, "دلار")):
            from zarsaman_analyzer.inventory import exclusion_reason
            c = co(cid, name, [], exclude_reason=exclusion_reason(cid, name))
            self.assertEqual(analyze_company(c, cfg, FakeFetcher({}), sleep=NOSLEEP).status, Status.SKIPPED)

    def test_company_error_isolated(self):
        class Boom:
            def fetch(self, *a, **k): raise RuntimeError("boom")
        r = analyze_company(co(133, "z", [("https://x.example", "api", False)]), cfg_tmp(), Boom(), sleep=NOSLEEP)
        self.assertEqual(r.status, Status.FAIL)

    def test_live_state_disagreement(self):
        from zarsaman_analyzer.state import StateSnapshot
        from datetime import datetime
        cfg = cfg_tmp()
        rec = RECIPES[133]
        snap = StateSnapshot(mode=StateMode.LIVE_STATE, records={133: {"last_buy": 20000000, "last_sell": 20000000,
                             "last_updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}})
        r = analyze_company(co(133, "z", [(rec.url, "api", False)]), cfg, FakeFetcher({rec.url: {"price": "24500000"}}), snap, NOSLEEP)
        self.assertEqual(r.status, Status.NEEDS_REVIEW)

    def test_local_cache_not_used_as_reference(self):
        from zarsaman_analyzer.state import StateSnapshot
        cfg = cfg_tmp()
        rec = RECIPES[133]
        snap = StateSnapshot(mode=StateMode.LOCAL_CACHE, records={133: {"last_buy": 1, "last_sell": 1, "last_updated_at": "2026-01-01 00:00:00"}})
        r = analyze_company(co(133, "z", [(rec.url, "api", False)]), cfg, FakeFetcher({rec.url: {"price": "24500000"}}), snap, NOSLEEP)
        self.assertEqual(r.status, Status.BASE_ONLY_READY)
        self.assertFalse(r.reference["used"])


class TestRealRunFixes(unittest.TestCase):
    def test_rejected_out_of_range_is_reported(self):
        cfg = cfg_tmp(); u = "https://s.example/api"
        r = analyze_company(co(600, "x", [(u, "api", False)]), cfg, FakeFetcher({u: {"buy": 245000000, "sell": 246000000}}), sleep=NOSLEEP)
        self.assertIn("rejected_out_of_range", "; ".join(r.reasons))
        self.assertIsNone(r.final_buy)          # never auto-converted

    def test_recipe_missing_path_reported(self):
        cfg = cfg_tmp(); rec = RECIPES[109]
        r = analyze_company(co(109, "abshode", [(rec.url, "api", False)]), cfg, FakeFetcher({rec.url: {"other": 1}}), sleep=NOSLEEP)
        self.assertEqual(r.status, Status.FAIL)
        self.assertTrue(any("path_not_found" in w for w in r.warnings))
        self.assertTrue(any(w.startswith("body_excerpt") for w in r.warnings))

    def test_human_override_swaps_explicitly(self):
        cfg = cfg_tmp(); rec = RECIPES[131]
        f = FakeFetcher({rec.url: {"todaySellPrice": 24900000, "todayBuyPrice": 24400000}})
        c = co(131, "x", [(rec.url, "api", False)])
        r0 = analyze_company(c, cfg, f, sleep=NOSLEEP)
        self.assertEqual(r0.status, Status.NEEDS_REVIEW)
        r1 = analyze_company(c, cfg, f, sleep=NOSLEEP, overrides={131: {"labels_inverted": True}})
        self.assertEqual((r1.final_buy, r1.final_sell), (24400000.0, 24900000.0))
        self.assertEqual(r1.status, Status.READY_FOR_PHP)
        self.assertIn("human_override:labels_inverted", r1.warnings)

    def test_override_ignored_without_flag(self):
        cfg = cfg_tmp(); rec = RECIPES[131]
        f = FakeFetcher({rec.url: {"todaySellPrice": 24900000, "todayBuyPrice": 24400000}})
        r = analyze_company(co(131, "x", [(rec.url, "api", False)]), cfg, f, sleep=NOSLEEP, overrides={131: {"labels_inverted": False}})
        self.assertEqual(r.status, Status.NEEDS_REVIEW)


class TestState(unittest.TestCase):
    def test_header_only_and_live(self):
        cfg = cfg_tmp(); cfg.state_key = "SECRETKEY123"
        f = FakeFetcher({cfg.state_endpoint: {"ok": True, "companies": [{"id": 5, "last_buy": 1, "last_sell": 2, "last_updated_at": "2026-11-18 10:00:00"}]}})
        s = StateClient(cfg, f).fetch()
        self.assertEqual(s.mode, StateMode.LIVE_STATE)
        url, hdr = f.calls[0]
        self.assertNotIn("SECRETKEY123", url)
        self.assertEqual(hdr["X-API-Key"], "SECRETKEY123")

    def test_real_server_shape(self):
        cfg = cfg_tmp(); cfg.state_key = "k"
        body = {"ok": True, "generated_at": "2026-11-20 10:00:00", "warnings": [], "prices": [],
                "companies": [{"id": 8, "name": "وال گلد", "last_buy": 24308000.0, "last_sell": 24308000.0,
                               "last_updated_at": "2026-11-20 09:59:00", "consecutive_failures": 0, "is_active": 1}]}
        s = StateClient(cfg, FakeFetcher({cfg.state_endpoint: body})).fetch()
        self.assertEqual(s.mode, StateMode.LIVE_STATE)
        self.assertEqual(s.records[8]["last_buy"], 24308000.0)

    def test_403_falls_back_to_cache_not_live(self):
        cfg = cfg_tmp()
        (cfg.state_dir / "price_state.json").write_text(json.dumps({"1": {"name": "a", "last_buy": 1, "last_sell": 1, "last_success_at": "2026-11-10 10:00:00"}}))
        f = FakeFetcher({cfg.state_endpoint: FetchResult(url="", status=403, text='{"ok":false,"error":"forbidden"}', error="HTTP 403")})
        s = StateClient(cfg, f).fetch()
        self.assertEqual(s.mode, StateMode.LOCAL_CACHE)
        self.assertIn("NOT live", s.detail)
        self.assertIn("REJECTED", s.detail)

    def test_401_html_and_no_reference(self):
        cfg = cfg_tmp()
        f = FakeFetcher({cfg.state_endpoint: FetchResult(url="", status=401, text="<html>", error="HTTP 401")})
        s = StateClient(cfg, f).fetch()
        self.assertEqual(s.mode, StateMode.NO_REFERENCE)
        self.assertIn("web-server", diagnose(401, "<html>", True))

    def test_http200_ok_false_not_live(self):
        cfg = cfg_tmp()
        f = FakeFetcher({cfg.state_endpoint: {"ok": False}})
        self.assertNotEqual(StateClient(cfg, f).fetch().mode, StateMode.LIVE_STATE)


class TestSecurity(unittest.TestCase):
    def test_redaction(self):
        t = redact("https://x/api?AccessKey=abcd1234&a=1 Authorization: Bearer tok.en-1 key SECRETVAL", ["SECRETVAL"])
        self.assertNotIn("abcd1234", t); self.assertNotIn("tok.en-1", t); self.assertNotIn("SECRETVAL", t)

    def test_ssrf(self):
        for u in ("http://127.0.0.1/", "http://10.0.0.5/x", "http://[::1]/", "ftp://a.example/", "http://localhost/", "https://a.example:8443/"):
            self.assertFalse(check_url(u, resolve=False)[0], u)
        self.assertTrue(check_url("https://8.8.8.8/", resolve=False)[0])


class TestInventoryAndCheckpoint(unittest.TestCase):
    def test_inventory(self):
        d = Path(tempfile.mkdtemp()) / "s.csv"
        d.write_text("id,company_id,company_name,api_url,website_url,is_active\n"
                     "1,5,Talaino,https://a.example/api,https://a.example,1\n"
                     "2,5,Talaino,https://backend.goldinex.org/price/website/comparison,NULL,1\n"
                     "3,1018,اینوی نقره,https://s.example,,1\n"
                     "4,77,Ticker,https://t.example,,1\n"
                     "5,6,Off,https://o.example,,0\n"
                     "6,7,Cap,https://www.google.com/recaptcha/api.js,,1\n", encoding="utf-8")
        comps = {c.company_id: c for c in load_inventory(d)}
        self.assertNotIn(6, comps)
        self.assertTrue(any(u.aggregator for u in comps[5].urls))
        self.assertTrue(comps[1018].exclude_reason and comps[77].exclude_reason)
        self.assertEqual(comps[7].urls, [])     # CAPTCHA script dropped

    def test_checkpoint_resume(self):
        d = Path(tempfile.mkdtemp())
        cp = Checkpoint(d, "r1")
        cp.record(CompanyResult(5, "a", status=Status.READY_FOR_PHP, mode=Mode.PAIR, final_buy=1.0, final_sell=2.0))
        cp2 = Checkpoint.resume_latest(d)
        self.assertEqual(cp2.results[5].status, Status.READY_FOR_PHP)
        self.assertFalse(list(d.glob("*.tmp")))


class TestPhp(unittest.TestCase):
    def test_generation(self):
        cfg = cfg_tmp()
        rec = RECIPES[131]
        r = analyze_company(co(131, "زرین", [(rec.url, "api", False)]), cfg,
                            FakeFetcher({rec.url: {"todaySellPrice": 24800000, "todayBuyPrice": 24850000}}), sleep=NOSLEEP)
        out = Path(tempfile.mkdtemp())
        files = generate([r], cfg, out)
        src = (out / "company_131.php").read_text(encoding="utf-8")
        self.assertIn("buy_gt_sell_needs_review", src)
        self.assertNotIn("0.99", src); self.assertNotIn("1.01", src)
        self.assertTrue((out / "fixtures" / "company_131.json").exists())
        res = lint(files)
        for k, v in res.items():
            if k != "_":
                self.assertIn("No syntax errors", v, f"{k}: {v}")


if __name__ == "__main__":
    unittest.main()
