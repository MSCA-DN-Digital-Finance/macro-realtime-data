# Sources and terms of the public data files

Each file is `data/public/<dataset>.parquet` in long format `series, date, value` (+ `vintage` for real-time data);
`data/CATALOG.md` describes every dataset. Please cite the original provider when you use the data.

| Prefix | Provider | Terms |
|---|---|---|
| `fred_*` | Federal Reserve Bank of St. Louis, FRED (and the original source named on each series page) | Public domain or "citation required" per series. Series needing pre-approval are removed: SP500 (S&P Dow Jones Indices), DJIA (S&P Dow Jones Indices), NASDAQCOM (Nasdaq), BAMLC0A0CM (ICE Data Indices), BAMLH0A0HYM2 (ICE Data Indices) |
| `ecb_*` | European Central Bank, ECB Data Portal | Free reuse with the ECB named as source |
| `eurostat_*` | Eurostat | Free reuse with Eurostat named as source (CC BY 4.0) |
| `rtdsm`, `spf_us` | Federal Reserve Bank of Philadelphia (Real-Time Data Set for Macroeconomists; Survey of Professional Forecasters) | Free, cite the Philadelphia Fed |
| `gsw_curve` | Federal Reserve Board; Gürkaynak, Sack and Wright (2007) | Public, cite Gürkaynak, Sack and Wright (2007) |
| `french` | Kenneth R. French Data Library | Free, cite the Kenneth R. French Data Library |
