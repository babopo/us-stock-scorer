from dataclasses import dataclass
from datetime import datetime, timezone
from time import time
from typing import Any

import httpx


class MarketDataError(Exception):
    """Base class for upstream market-data failures."""


class MarketDataConfigurationError(MarketDataError):
    pass


class MarketDataNotFound(MarketDataError):
    pass


class MarketDataRateLimited(MarketDataError):
    pass


class MarketDataUnavailable(MarketDataError):
    pass


@dataclass(frozen=True)
class DailyBar:
    date: str
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    volume: int


@dataclass(frozen=True)
class MarketSnapshot:
    ticker: str
    company_name: str
    last_price: float
    data_as_of: str
    daily_bars: list[DailyBar]
    overview: dict[str, Any]
    source: str


class AlphaVantageClient:
    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str, http_client: httpx.Client | None = None, timeout: float = 10.0):
        if not api_key:
            raise MarketDataConfigurationError(
                "ALPHA_VANTAGE_API_KEY is required when STOCK_SCORER_DATA_SOURCE=alpha_vantage"
            )
        self._api_key = api_key
        self._client = http_client or httpx.Client(timeout=timeout)
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "AlphaVantageClient":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def fetch_snapshot(self, ticker: str) -> MarketSnapshot:
        normalized = ticker.upper()
        daily_payload = self._get(
            function="TIME_SERIES_DAILY_ADJUSTED",
            symbol=normalized,
            outputsize="compact",
        )
        overview = self._get(function="OVERVIEW", symbol=normalized)
        bars = _parse_daily_bars(daily_payload, normalized)
        latest = bars[0]

        return MarketSnapshot(
            ticker=normalized,
            company_name=str(overview.get("Name") or normalized),
            last_price=latest.adjusted_close,
            data_as_of=latest.date,
            daily_bars=bars,
            overview=overview,
            source="alpha_vantage",
        )

    def _get(self, function: str, **params: str) -> dict[str, Any]:
        try:
            response = self._client.get(
                self.BASE_URL,
                params={"function": function, **params, "apikey": self._api_key},
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise MarketDataUnavailable(f"Alpha Vantage request failed: {exc}") from exc
        except ValueError as exc:
            raise MarketDataUnavailable("Alpha Vantage returned non-JSON data") from exc

        if not isinstance(payload, dict):
            raise MarketDataUnavailable("Alpha Vantage returned an unexpected payload")
        _raise_for_provider_error(payload)
        return payload


def _raise_for_provider_error(payload: dict[str, Any]) -> None:
    if "Note" in payload:
        raise MarketDataRateLimited(str(payload["Note"]))
    if "Information" in payload:
        raise MarketDataUnavailable(str(payload["Information"]))
    if "Error Message" in payload:
        raise MarketDataNotFound(str(payload["Error Message"]))


def _parse_daily_bars(payload: dict[str, Any], ticker: str) -> list[DailyBar]:
    series = payload.get("Time Series (Daily)")
    if not isinstance(series, dict) or not series:
        raise MarketDataNotFound(f"No daily adjusted price data found for {ticker}")

    bars = [_parse_daily_bar(day, values) for day, values in series.items()]
    return sorted(bars, key=lambda bar: bar.date, reverse=True)


def _parse_daily_bar(day: str, values: Any) -> DailyBar:
    if not isinstance(values, dict):
        raise MarketDataUnavailable(f"Malformed daily bar for {day}")
    close = _as_float(values, "4. close")
    return DailyBar(
        date=day,
        open=_as_float(values, "1. open"),
        high=_as_float(values, "2. high"),
        low=_as_float(values, "3. low"),
        close=close,
        adjusted_close=_as_float(values, "5. adjusted close", default=close),
        volume=int(_as_float(values, "6. volume")),
    )


def _as_float(values: dict[str, Any], key: str, default: float | None = None) -> float:
    raw = values.get(key)
    if raw in (None, "None", ""):
        if default is not None:
            return default
        raise MarketDataUnavailable(f"Missing Alpha Vantage field: {key}")
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise MarketDataUnavailable(f"Invalid Alpha Vantage field {key}: {raw}") from exc


class FmpClient:
    BASE_URL = "https://financialmodelingprep.com/stable"

    def __init__(self, api_key: str, http_client: httpx.Client | None = None, timeout: float = 10.0):
        if not api_key:
            raise MarketDataConfigurationError("FMP_API_KEY is required when STOCK_SCORER_DATA_SOURCE=fmp")
        self._api_key = api_key
        self._client = http_client or httpx.Client(timeout=timeout)
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "FmpClient":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def fetch_snapshot(self, ticker: str) -> MarketSnapshot:
        normalized = ticker.upper()
        quote = _first_row(self._get("quote", symbol=normalized))
        bars = _parse_fmp_daily_bars(
            self._get("historical-price-eod/full", symbol=normalized),
            normalized,
        )
        profile = _first_row(self._get("profile", symbol=normalized))
        income = _rows(self._get("income-statement", symbol=normalized, period="annual", limit="2"))
        latest = bars[0]
        company_name = str(profile.get("companyName") or quote.get("name") or normalized)

        return MarketSnapshot(
            ticker=normalized,
            company_name=company_name,
            last_price=_optional_float(quote.get("price")) or latest.adjusted_close,
            data_as_of=latest.date,
            daily_bars=bars,
            overview=_build_fmp_overview(company_name, profile, income),
            source="fmp",
        )

    def _get(self, endpoint: str, **params: str) -> Any:
        try:
            response = self._client.get(
                f"{self.BASE_URL}/{endpoint}",
                params={**params, "apikey": self._api_key},
            )
            _raise_for_fmp_http_status(response)
            payload = response.json()
        except httpx.HTTPError as exc:
            raise MarketDataUnavailable(f"FMP request failed: {exc}") from exc
        except ValueError as exc:
            raise MarketDataUnavailable("FMP returned non-JSON data") from exc

        _raise_for_fmp_payload_error(payload)
        return payload


def _raise_for_fmp_http_status(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise MarketDataConfigurationError("FMP rejected the API key")
    if response.status_code == 404:
        raise MarketDataNotFound("FMP endpoint or ticker was not found")
    if response.status_code == 429:
        raise MarketDataRateLimited("FMP rate limit exceeded")
    response.raise_for_status()


def _raise_for_fmp_payload_error(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    message = payload.get("Error Message") or payload.get("error") or payload.get("message")
    if not message:
        return
    text = str(message)
    if "limit" in text.lower() or "too many" in text.lower():
        raise MarketDataRateLimited(text)
    raise MarketDataUnavailable(text)


class FinnhubClient:
    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str, http_client: httpx.Client | None = None, timeout: float = 10.0):
        if not api_key:
            raise MarketDataConfigurationError("FINNHUB_API_KEY is required when STOCK_SCORER_DATA_SOURCE=finnhub")
        self._api_key = api_key
        self._client = http_client or httpx.Client(timeout=timeout)
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "FinnhubClient":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def fetch_snapshot(self, ticker: str) -> MarketSnapshot:
        normalized = ticker.upper()
        quote = self._get("quote", symbol=normalized)
        bars = _parse_finnhub_daily_bars(
            self._get(
                "stock/candle",
                symbol=normalized,
                resolution="D",
                **_finnhub_history_range(),
            ),
            normalized,
        )
        profile = self._get("stock/profile2", symbol=normalized)
        metrics = self._get("stock/metric", symbol=normalized, metric="all")
        if not isinstance(profile, dict):
            raise MarketDataUnavailable("Finnhub returned an unexpected profile payload")
        latest = bars[0]
        company_name = str(profile.get("name") or normalized)

        return MarketSnapshot(
            ticker=normalized,
            company_name=company_name,
            last_price=_optional_float(quote.get("c")) or latest.adjusted_close,
            data_as_of=latest.date,
            daily_bars=bars,
            overview=_build_finnhub_overview(company_name, profile, metrics),
            source="finnhub",
        )

    def _get(self, endpoint: str, **params: str) -> Any:
        try:
            response = self._client.get(
                f"{self.BASE_URL}/{endpoint}",
                params={**params, "token": self._api_key},
            )
            _raise_for_finnhub_http_status(response)
            payload = response.json()
        except httpx.HTTPError as exc:
            raise MarketDataUnavailable(f"Finnhub request failed: {exc}") from exc
        except ValueError as exc:
            raise MarketDataUnavailable("Finnhub returned non-JSON data") from exc

        _raise_for_finnhub_payload_error(payload)
        return payload


def _finnhub_history_range() -> dict[str, str]:
    to_timestamp = int(time())
    from_timestamp = to_timestamp - 120 * 24 * 60 * 60
    return {"from": str(from_timestamp), "to": str(to_timestamp)}


def _raise_for_finnhub_http_status(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise MarketDataConfigurationError("Finnhub rejected the API key")
    if response.status_code == 404:
        raise MarketDataNotFound("Finnhub endpoint or ticker was not found")
    if response.status_code == 429:
        raise MarketDataRateLimited("Finnhub rate limit exceeded")
    response.raise_for_status()


def _raise_for_finnhub_payload_error(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    message = payload.get("error") or payload.get("message")
    if not message:
        return
    text = str(message)
    if "limit" in text.lower() or "too many" in text.lower():
        raise MarketDataRateLimited(text)
    raise MarketDataUnavailable(text)


def _parse_finnhub_daily_bars(payload: Any, ticker: str) -> list[DailyBar]:
    if not isinstance(payload, dict):
        raise MarketDataUnavailable("Finnhub returned an unexpected candle payload")
    if payload.get("s") == "no_data":
        raise MarketDataNotFound(f"No Finnhub candle data found for {ticker}")
    if payload.get("s") not in (None, "ok"):
        raise MarketDataUnavailable(f"Finnhub candle request failed for {ticker}: {payload.get('s')}")

    timestamps = payload.get("t")
    opens = payload.get("o")
    highs = payload.get("h")
    lows = payload.get("l")
    closes = payload.get("c")
    volumes = payload.get("v")
    series = [timestamps, opens, highs, lows, closes, volumes]
    if not all(isinstance(values, list) for values in series):
        raise MarketDataNotFound(f"No Finnhub candle data found for {ticker}")
    if not timestamps:
        raise MarketDataNotFound(f"No Finnhub candle data found for {ticker}")
    if len({len(values) for values in series}) != 1:
        raise MarketDataUnavailable(f"Malformed Finnhub candle data found for {ticker}")

    bars = [
        DailyBar(
            date=_date_from_unix_timestamp(timestamps[index]),
            open=float(opens[index]),
            high=float(highs[index]),
            low=float(lows[index]),
            close=float(closes[index]),
            adjusted_close=float(closes[index]),
            volume=int(float(volumes[index])),
        )
        for index in range(len(timestamps))
    ]
    return sorted(bars, key=lambda bar: bar.date, reverse=True)


def _date_from_unix_timestamp(value: Any) -> str:
    try:
        timestamp = int(value)
    except (TypeError, ValueError) as exc:
        raise MarketDataUnavailable(f"Invalid Finnhub timestamp: {value}") from exc
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()


def _build_finnhub_overview(
    company_name: str,
    profile: dict[str, Any],
    metrics_payload: dict[str, Any],
) -> dict[str, Any]:
    metrics = metrics_payload.get("metric") if isinstance(metrics_payload, dict) else {}
    if not isinstance(metrics, dict):
        metrics = {}

    return {
        "Name": company_name,
        "MarketCapitalization": _finnhub_market_cap(profile.get("marketCapitalization")),
        "PERatio": _first_present(metrics, "peTTM", "peBasicExclExtraTTM", "peNormalizedAnnual"),
        "ForwardPE": _first_present(metrics, "forwardPE", "forwardPe"),
        "ProfitMargin": _percent_to_ratio(_first_present(metrics, "netProfitMarginTTM", "netProfitMarginAnnual")),
        "QuarterlyRevenueGrowthYOY": _percent_to_ratio(
            _first_present(metrics, "revenueGrowthTTMYoy", "revenueGrowthQuarterlyYoy")
        ),
        "QuarterlyEarningsGrowthYOY": _percent_to_ratio(
            _first_present(metrics, "epsGrowthTTMYoy", "epsGrowthQuarterlyYoy")
        ),
        "Beta": _first_present(metrics, "beta"),
    }


def _finnhub_market_cap(value: Any) -> float | None:
    market_cap = _optional_float(value)
    if market_cap is None:
        return None
    return market_cap * 1_000_000


def _percent_to_ratio(value: Any) -> float | None:
    numeric = _optional_float(value)
    if numeric is None:
        return None
    if abs(numeric) > 1:
        return numeric / 100
    return numeric


def _parse_fmp_daily_bars(payload: Any, ticker: str) -> list[DailyBar]:
    rows = _rows(payload)
    if not rows:
        raise MarketDataNotFound(f"No FMP historical price data found for {ticker}")
    bars = [_parse_fmp_daily_bar(row) for row in rows]
    return sorted(bars, key=lambda bar: bar.date, reverse=True)


def _parse_fmp_daily_bar(row: dict[str, Any]) -> DailyBar:
    close = _numeric_value(row, "close")
    return DailyBar(
        date=str(row["date"]),
        open=_numeric_value(row, "open"),
        high=_numeric_value(row, "high"),
        low=_numeric_value(row, "low"),
        close=close,
        adjusted_close=_numeric_value(row, "adjClose", "adj_close", default=close),
        volume=int(_numeric_value(row, "volume")),
    )


def _build_fmp_overview(
    company_name: str,
    profile: dict[str, Any],
    income_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    latest_income = income_rows[0] if income_rows else {}
    previous_income = income_rows[1] if len(income_rows) > 1 else {}
    latest_revenue = _optional_float(latest_income.get("revenue"))
    latest_net_income = _optional_float(latest_income.get("netIncome"))

    return {
        "Name": company_name,
        "MarketCapitalization": _first_present(profile, "mktCap", "marketCap"),
        "PERatio": _first_present(profile, "pe", "peRatio"),
        "ForwardPE": _first_present(profile, "forwardPE", "forwardPe"),
        "ProfitMargin": _ratio(latest_net_income, latest_revenue),
        "QuarterlyRevenueGrowthYOY": _growth(latest_income, previous_income, "revenue"),
        "QuarterlyEarningsGrowthYOY": _growth(latest_income, previous_income, "eps"),
        "Beta": _first_present(profile, "beta"),
    }


def _first_row(payload: Any) -> dict[str, Any]:
    rows = _rows(payload)
    return rows[0] if rows else {}


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        historical = payload.get("historical")
        if isinstance(historical, list):
            return [row for row in historical if isinstance(row, dict)]
    return []


def _numeric_value(values: dict[str, Any], *keys: str, default: float | None = None) -> float:
    for key in keys:
        raw = values.get(key)
        if raw not in (None, "None", ""):
            try:
                return float(raw)
            except (TypeError, ValueError) as exc:
                raise MarketDataUnavailable(f"Invalid FMP field {key}: {raw}") from exc
    if default is not None:
        return default
    raise MarketDataUnavailable(f"Missing FMP field: {'/'.join(keys)}")


def _first_present(values: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = values.get(key)
        if value not in (None, "None", ""):
            return value
    return None


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _growth(current: dict[str, Any], previous: dict[str, Any], key: str) -> float | None:
    current_value = _optional_float(current.get(key))
    previous_value = _optional_float(previous.get(key))
    if current_value is None or previous_value in (None, 0):
        return None
    return current_value / previous_value - 1


def _optional_float(value: Any) -> float | None:
    if value in (None, "", "None", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
