# Known Issues

## Data Collection Pipeline - NOT Production Ready

**Status:** Deferred to separate project
**Date Identified:** 2025-11-08
**Audit Report:** See agent audit output from 2025-11-08 session

### Critical Gaps

1. **Incomplete Field Capture from Form 4 XML**
   - Missing 11+ critical fields: footnotes, post-transaction ownership, indirect holdings, nature of ownership
   - Impact: Missing material context that affects signal quality
   - Example: 6.8% of transactions have NULL price (footnotes would explain why)

2. **SEC API 100-Filing Pagination Limit**
   - SEC caps at 100 filings per request
   - Current workaround (yearly chunking) incomplete for high-volume tickers
   - Impact: Systematic data loss for large companies (AAPL, MSFT, TSLA)
   - Evidence: Many tickers show exactly "100 filings found" (suspiciously round)

3. **No Data Validation at Database Insertion**
   - Zero validation before DB insert (ranges, consistency, duplicates)
   - Impact: Corrupt/invalid data can enter system silently
   - Missing: Field validation, consistency checks, duplicate detection

4. **Broken Amendment Handling**
   - Amendments insert as new filings instead of updating originals
   - Impact: Duplicate/conflicting transaction data (22 amendments in current DB)
   - Missing: Link to original filing, update/merge logic

5. **Silent Failure in Error Handling**
   - Multiple `except: pass` blocks with no logging
   - Impact: Parser failures masked, no visibility into data quality
   - Missing: Error metrics, alerting, failure tracking

### Data Quality Impact

**Current Database:**
- Only 246 purchases out of 16,790 transactions (1.5%) - suspiciously low
- 6.8% transactions missing price data (1,146 records)
- Date range: 2021-2025 (~4.5 years, not full 5)
- Missing tickers: AMD, META, NVDA

**Production Requirements Not Met:**
- No data lineage/audit trail
- No idempotency guarantees
- No monitoring/alerting
- No temporal coverage validation

### Recommendations from Audit

**P0 - Critical (Must Fix Before Production):**
1. Implement comprehensive field capture (all 20+ Form 4 fields)
2. Fix pagination / data completeness validation
3. Add data validation layer before DB insertion
4. Implement proper amendment handling

**Estimated Effort:** 2-3 weeks development + 1 week testing

### Decision

**Separate this into standalone data pipeline project** with:
- Production-grade SEC EDGAR collector
- Complete Form 4 field extraction
- Pagination handling
- Data validation and quality metrics
- Monitoring and alerting
- Clean API for downstream consumers

Current project will continue with existing data (sufficient for backtesting hypothesis).

### Impact on Current Project

**What We Can Do:**
- Backtest with 3,200+ purchase signals (2021-2025, 53 tickers)
- Validate strategy hypothesis
- Build dashboard and AI analysis
- Prove concept before investing in data infrastructure

**What We Cannot Do:**
- Guarantee data completeness
- Use for production trading decisions
- Commercialize without fixing pipeline
- Trust critical edge cases (footnoted transactions, amendments, etc.)

**Risk Acceptance:** Data quality issues acknowledged. Suitable for research/backtesting, not live trading.

---

## Other Known Issues

(None at this time)

---

**Last Updated:** 2025-11-08
