# API Client

Shared JavaScript client for the US Stock Scorer API.

The backend remains the source of truth for scoring logic and response models. This package is the single frontend-facing place for API paths, request defaults, Bearer headers, transport adapters, and error mapping.

Current consumers:

- React/Vite web admin through `createFetchTransport(fetch)`

The client currently covers:

- Health and stock scoring.
- Admin login, session check and logout.
- Provider status, raw ticker data, score snapshots and ticker refresh.
- History sync runs and manual history sync.
- Backtest run listing and manual backtest runs.
- Strategy version listing, candidate generation, promotion and archival.

Example:

```js
const {
  createStockScorerClient,
  createFetchTransport
} = require("@stock-scorer/api-client");

const client = createStockScorerClient({
  baseUrl: "http://127.0.0.1:8000",
  transport: createFetchTransport(),
  headers: {
    Authorization: "Bearer local-read-token"
  }
});

const score = await client.getStockScore("MSFT");
```

Admin methods require an admin Bearer token. The web admin obtains that token through `loginAdmin(username, password)` and then creates a client with the returned token in the `Authorization` header.
