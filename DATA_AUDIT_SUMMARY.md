# Database Audit Summary - Open InsiderTrader

**Audit Date:** 2025-11-07
**Database:** data/insider_trades.db
**Auditor:** Sub-agent comprehensive analysis

---

## Executive Summary

**Status:** ⚠️ **READY FOR BACKTEST WITH LIMITATIONS**

The database contains **13,053 transactions** with **3,596 purchase signals** across **53/56 companies** spanning **4.5 years (2021-2025)**. Strong coverage in recent years (2023-2025) but significant gaps in early period (2020-2022). Suitable for initial strategy validation but missing 3 major tech tickers and pre-2021 data.

---

## Key Statistics

| Metric | Value | Status |
|--------|-------|--------|
| Total Transactions | 13,053 | ✅ |
| Purchase Transactions (P+M) | 3,596 | ✅ |
| Date Range | 2021-02-24 to 2025-11-06 | ⚠️ (not full 5yr) |
| Companies | 53/56 (94.6%) | ⚠️ |
| Unique Insiders | 1,221 | ✅ |
| Transactions with Prices | 92.2% | ⚠️ (7.8% missing) |
| Market Cap Coverage | 21.4% | ⚠️ |

---

## Temporal Coverage

### By Year
- **2021:** 4 transactions (0.03%) ❌ Severe gap
- **2022:** 11 transactions (0.08%) ❌ Severe gap
- **2023:** 448 transactions (3.4%) ⚠️ Low
- **2024:** 3,603 transactions (27.6%) ✅ Good
- **2025:** 8,956 transactions (68.6%) ✅ Good

### Purchase Signals by Year
- **2021:** 2 purchases (P=2, M=0)
- **2022:** 9 purchases (P=9, M=0)
- **2023:** 157 purchases (P=16, M=141)
- **2024:** 1,071 purchases (P=22, M=1,049)
- **2025:** 2,344 purchases (P=172, M=2,172)

**Analysis:** 99% of purchase signals are from 2023-2025. Limited historical depth.

---

## Missing Data

### Missing Companies (3/56)
- **AMD** - 0 transactions (collection failed)
- **META** - 0 transactions (collection failed)
- **NVDA** - 0 transactions (collection failed)

All three are major tech companies that should have significant insider activity.

### Data Quality Issues
- **7.8%** transactions missing `price_per_share` (1,021/13,053)
  - Affects 371 purchase signals (19.5% of purchases)
- **50.6%** insiders missing `officer_title` (647/1,279)
- **21.4%** transactions have matching market cap data
- **1 date error** fixed: "0025-07-25" → "2025-07-25"

---

## Top Active Companies

| Rank | Ticker | Transactions | Company |
|------|--------|--------------|---------|
| 1 | CRM | 646 | Salesforce |
| 2 | BAC | 620 | Bank of America |
| 3 | TSLA | 560 | Tesla |
| 4 | ADBE | 535 | Adobe |
| 5 | LIN | 532 | Linde |
| 6 | TMUS | 531 | T-Mobile |
| 7 | AMZN | 398 | Amazon |
| 8 | GOOGL | 372 | Google |
| 9 | LLY | 367 | Eli Lilly |
| 10 | TMO | 357 | Thermo Fisher |

---

## Backtest Recommendations

### Clean Dataset Parameters
```python
# Recommended filters for backtest
date_range = "2023-01-01 to 2025-11-06"  # Strong coverage period
exclude_tickers = ["AMD", "META", "NVDA"]  # No data
require_price = True  # Exclude 371 signals without prices
require_market_cap = False  # Only 21% coverage

# Expected clean signals: ~3,200 purchases
```

### Risk Factors
1. **Limited Historical Depth:** Only 2.9 years of strong data
2. **Missing Major Tech:** AMD, META, NVDA have significant market cap
3. **Early Period Gaps:** Cannot validate 2020-2022 bear market performance
4. **Price Data:** 19.5% of purchase signals lack pricing

### Confidence Level
- **High Confidence:** 2024-2025 results (2,344 signals, 99% coverage)
- **Medium Confidence:** 2023 results (157 signals, good coverage)
- **Low Confidence:** 2021-2022 results (11 signals, severe gaps)

---

## Collection Issues Identified

### SEC API Limitations
- **100 filing limit** per request
- Date range parameters not working as expected
- No filings returned for dates before 2021

### Parser Issues
- Method name mismatch: `parse_form4` vs `parse`
- Prevented AMD, META, NVDA data storage
- All filings fetched but none parsed successfully

### Next Steps to Fix
1. Debug SEC API date filtering
2. Fix parser method names in collection scripts
3. Implement proper pagination beyond 100 filings
4. Re-run collection for 2020-2022 period
5. Target AMD, META, NVDA with corrected parser

**Estimated Time:** 2-4 hours for complete fix

---

## Recommendation

**Proceed with backtest using 2023-2025 data (3,200+ clean signals).**

If backtest shows promising alpha:
- Invest time in fixing collection for full 5-year dataset
- Add AMD, META, NVDA
- Validate across complete market cycle

If backtest shows weak/no alpha:
- No need to invest in data collection improvements
- Strategy validation complete with available data

---

**Full audit report available from sub-agent analysis (2025-11-07 session)**
