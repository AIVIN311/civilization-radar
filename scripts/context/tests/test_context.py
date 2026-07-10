import csv, json, math, sys, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).resolve(); sys.path.insert(0,str(HERE.parents[1]))
from common import iso_date, parse_number, spearman
from build_radar_features import build
from analyze_tw_overlay import align_event, market_features
from validate_context import duplicate_check

class ContextTests(unittest.TestCase):
    def test_twse_parsing(self):
        self.assertEqual(iso_date("115/07/09"),"2026-07-09"); self.assertEqual(parse_number("1,234"),1234); self.assertIsNone(parse_number("--"))
    def test_duplicate_classes(self):
        rows=[{"d":"x","v":"1"},{"d":"x","v":"1"},{"d":"x","v":"2"}]
        self.assertEqual(duplicate_check(rows,["d"],["v"]),(1,1))
    def test_features_hhi(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); snap=root/"s.jsonl"; mapping=root/"m.json"; out=root/"o.csv"
            snap.write_text('\n'.join(json.dumps(x) for x in [{"date":"2026-01-02","domain":"a","dns_total":75,"cf_served":50,"origin_served":25},{"date":"2026-01-02","domain":"b","dns_total":25,"cf_served":0,"origin_served":25}]),encoding="utf-8")
            mapping.write_text('{"default":"other","a":"one","b":"two"}',encoding="utf-8"); build(snap,mapping,out,"2026-01-01","2026-01-31")
            with out.open(encoding="utf-8",newline="") as handle: row=next(csv.DictReader(handle))
            self.assertAlmostEqual(float(row["hhi"]),.625); self.assertAlmostEqual(float(row["cache_share"]),.5)
    def test_market_math(self):
        rows=[]
        for i,c in enumerate([100,110,121]): rows.append({"date":f"2026-01-0{i+1}","symbol":"TAIEX","close":str(c)})
        f=market_features(rows); self.assertAlmostEqual(f[("2026-01-02","TAIEX")]["log_return_1d"],math.log(1.1))
        self.assertEqual(spearman([1,2,3],[3,2,1]),-1)
    def test_event_alignment(self):
        dates=["2026-03-19","2026-03-20","2026-03-23"]
        self.assertEqual(align_event({"datetime_local":"2026-03-19T13:31:00+08:00"},dates),"2026-03-20")
        self.assertEqual(align_event({"datetime_local":"2026-03-21"},dates),"2026-03-23")

if __name__=="__main__": unittest.main()
