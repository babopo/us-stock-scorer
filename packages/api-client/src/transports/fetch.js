const { appendQuery } = require("../url");

function createFetchTransport(fetchImpl) {
  const requestFetch = fetchImpl || globalThis.fetch;

  if (typeof requestFetch !== "function") {
    throw new TypeError("createFetchTransport requires a fetch implementation");
  }

  return async function fetchTransport(request) {
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timeoutId =
      controller && request.timeoutMs
        ? setTimeout(() => {
            controller.abort();
          }, request.timeoutMs)
        : null;

    try {
      const response = await requestFetch(appendQuery(request.url, request.query), {
        method: request.method,
        headers: buildHeaders(request.headers, request.body),
        body: request.body === undefined ? undefined : JSON.stringify(request.body),
        signal: controller ? controller.signal : undefined
      });

      return {
        status: response.status,
        headers: headersToObject(response.headers),
        data: await parseResponseBody(response)
      };
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    }
  };
}

function buildHeaders(headers, body) {
  const nextHeaders = Object.assign({}, headers || {});
  const hasContentType = Object.keys(nextHeaders).some((key) => key.toLowerCase() === "content-type");

  if (body !== undefined && !hasContentType) {
    nextHeaders["content-type"] = "application/json";
  }

  return nextHeaders;
}

async function parseResponseBody(response) {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function headersToObject(headers) {
  const result = {};
  if (!headers || typeof headers.forEach !== "function") {
    return result;
  }

  headers.forEach((value, key) => {
    result[key] = value;
  });
  return result;
}

module.exports = {
  createFetchTransport
};
