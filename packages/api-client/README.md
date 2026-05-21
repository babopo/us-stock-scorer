# API Client

Shared JavaScript client for the US Stock Scorer API.

The backend remains the source of truth for scoring logic and response models. This package is the single frontend-facing place for API paths, request defaults, transport adapters, and error mapping.

Current consumers:

- WeChat Mini Program through `createWxTransport(wx)`
- Future web admin through `createFetchTransport(fetch)`

Example:

```js
const {
  createStockScorerClient,
  createFetchTransport
} = require("@stock-scorer/api-client");

const client = createStockScorerClient({
  baseUrl: "http://127.0.0.1:8000",
  transport: createFetchTransport()
});

const score = await client.getStockScore("MSFT");
```
