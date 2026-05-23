# Market Data Fallback Design

Date: 2026-05-23

## Goal

When FMP cannot score a ticker because it is missing, rate limited, or temporarily unavailable, the API should automatically try another configured provider before returning an error.

## Scope

- Add Finnhub as a real market-data provider.
- Add `STOCK_SCORER_DATA_SOURCES` as an ordered fallback chain.
- Keep `STOCK_SCORER_DATA_SOURCE` working for existing single-provider setups.
- Show Finnhub configuration and active-chain status in the admin provider status endpoint.

## Provider Order

If `STOCK_SCORER_DATA_SOURCES` is present, it controls provider order:

```env
STOCK_SCORER_DATA_SOURCES=fmp,finnhub,alpha_vantage
```

If it is absent, the app uses the existing `STOCK_SCORER_DATA_SOURCE` value, defaulting to `fixture`.

## Finnhub Snapshot Mapping

`FinnhubClient` builds the existing `MarketSnapshot` shape from:

- `/quote` for current price.
- `/stock/candle` for daily OHLCV history.
- `/stock/profile2` for company name and market capitalization.
- `/stock/metric` for PE, beta, profit margin, and growth proxies.

Missing optional fundamentals should degrade to neutral scoring through the existing scoring behavior, while missing candle data should fail the provider and allow fallback.

## Error Handling

Provider failures in the fallback chain are treated as recoverable when they are configuration errors, not found, rate limited, or unavailable. The API tries the next configured provider. If every provider fails, it returns a market-data error that includes the attempted providers and their error messages.

## Tests

- Finnhub payload parsing produces a valid `MarketSnapshot`.
- Finnhub rate-limit payload raises `MarketDataRateLimited`.
- FMP failure falls back to Finnhub.
- Provider status reports Finnhub key and active-chain membership.
