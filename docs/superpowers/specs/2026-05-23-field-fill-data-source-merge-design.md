# Field-Fill Data Source Merge Design

Date: 2026-05-23

## Goal

Upgrade the live scoring data-source behavior from first-success fallback to field-fill aggregation. When multiple providers are configured, the service should request every configured source that can be used, merge the successful real-provider snapshots by configured priority, and score from the merged result.

## Current Behavior

`STOCK_SCORER_DATA_SOURCES=fmp,finnhub,alpha_vantage` currently means ordered fallback. The score service returns the first successful provider result. If FMP succeeds, Finnhub and Alpha Vantage are not requested, so missing FMP fields such as PE proxies remain missing even when later providers could supply them.

## Target Behavior

The configured source order remains the priority order. For example:

```env
STOCK_SCORER_DATA_SOURCES=fmp,finnhub,alpha_vantage
```

The API should:

1. Request each configured provider in order.
2. Keep every successful `MarketSnapshot`.
3. Continue past provider failures while collecting the failure details.
4. Build one merged snapshot from successful snapshots.
5. Score the merged snapshot with the existing scoring pipeline.

Single-source setups continue to behave like today.

## Merge Rules

The first successful snapshot is the primary snapshot. It owns:

- `ticker`
- `company_name`
- `last_price`
- `data_as_of`
- `daily_bars`

The merged `overview` is filled by provider priority. For each overview field, use the first successful provider that returns a non-empty value. Empty values are `None`, empty string, `"None"`, and `"-"`.

The merged `source` should list the providers that actually contributed successful snapshots, joined with `+`, such as `fmp+finnhub`.

## Failure Rules

Provider errors remain recoverable while at least one provider succeeds. This includes configuration errors, not-found responses, rate limits, and temporary upstream failures.

If every provider fails, keep the existing aggregate error behavior:

- All configuration failures become `MarketDataConfigurationError`.
- All not-found failures become `MarketDataNotFound`.
- Mixed or unavailable failures become `MarketDataUnavailable`.

## Fixture Behavior

Fixture remains useful for local development and tests. If `fixture` is the only configured source, return fixture scoring exactly as today.

If `fixture` is mixed with real providers, it should only be used when no real provider succeeds. This keeps fixture from masking live data while preserving a development fallback.

## Admin Status

`/v1/admin/providers/status` can keep showing the configured chain in `active_source`. No response-model change is required for this feature.

## Testing

Add service-level tests that prove:

1. The service requests later providers even when the first provider succeeds.
2. Missing primary overview fields are filled from later successful providers.
3. Primary price and daily bars still come from the first successful provider.
4. A failed later provider does not break scoring if an earlier provider succeeded.
5. All providers failing preserves the existing aggregate error behavior.

## Out Of Scope

- Averaging scores across providers.
- Conflict detection when two providers disagree.
- New provider APIs for balance sheets, cash flows, or richer ratios.
- Frontend API contract changes.
