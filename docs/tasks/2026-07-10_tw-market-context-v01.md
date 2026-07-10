# 台股市場情境層 v0.1

## Goal

建立與 canonical pipeline 隔離的台股情境疊圖，分析 Radar 與 TAIEX／2330 的 overlap、association、regime 與 event window。

## Allowed changes

- `scripts/context/**`
- `input/context/macro_events.csv`
- 本工作紀錄
- 執行期非 canonical artifacts：`output/context/**`

## Do-not-touch list

- scoring、gate、kernel、persistence
- DB schema、主 pipeline 與排程
- `series_registry` 與 baseline mapping 路徑
- canonical `output/latest`

## Verification steps

1. 標準庫單元測試涵蓋民國日期、千分位、缺值、重複、HHI、return、Spearman 與事件交易日對齊。
2. 從保存的 TWSE raw JSON 離線重建，並比較數值 artifacts fingerprints。
3. 單月 TWSE live smoke，確認 timeout、重試、節流與 raw receipt。
4. 完整窗口執行；驗證通過後才原子替換 `output/context/latest`。
5. 執行 `python scripts/run_acceptance_v07.py`。
6. 比較執行前後 `output/latest` 的遞迴 SHA-256 manifest。

## Results / notes

- `output/context/**` 明確為 non-canonical，不參與 baseline promotion。
- matplotlib 缺失只產生 WARN；數值與 Markdown 輸出仍須完成。
- 單元測試：5/5 PASS。
- TWSE live smoke：PASS；Python 3.13 對 TWSE 憑證鏈的 strict X.509 相容性問題，以保留 CA／hostname 驗證、僅移除 `VERIFY_X509_STRICT` 解決。
- 完整窗口：market 246 rows、Radar 150 days、有效 overlap 96 trading days；validation PASS，沒有 unknown domain、衝突重複、無效 OHLC 或月份缺口。
- 連續兩次 `--offline` 重建的 `market_daily.csv`、`radar_daily_features.csv`、`validation.json`、`aligned_daily.csv`、`analysis.json`、`report.md` SHA-256 全數一致。
- 分析判讀：11 個 `relationship_candidate`、99 個 `descriptive_only`；仍僅為 association，不宣稱因果或預測。
- `output/latest` 執行前後遞迴 SHA-256 manifest 完全一致。
- v0.7 acceptance：schema、determinism、provider swap、non-fatal render、none profile、isolation、behavioral 與 v0.5 regression 通過；最後既有 v0.4 summary hash check 失敗，expected `73040be047b87d6638347a2dca4f9ba4a39490fd8c615d679695752b635dd235`，got `e911ad326025cc25758a0756f5d71fde08dffff68c79467d578c1ef058559f16`。未修改 hash contract。

## Follow-ups

- 第二階段才評估 SP500、NASDAQCOM、NASDAQSOX、VIXCLS、DGS10、美元指數、台幣匯率與 `FRED_API_KEY`。
- v0.1 不新增 Windows 排程。
