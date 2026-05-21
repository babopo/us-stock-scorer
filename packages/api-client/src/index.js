const { createStockScorerClient, normalizeTicker } = require("./client");
const { ApiError, getErrorCode, isApiError } = require("./errors");
const { createFetchTransport } = require("./transports/fetch");
const { createWxTransport } = require("./transports/wx");

module.exports = {
  ApiError,
  createFetchTransport,
  createStockScorerClient,
  createWxTransport,
  getErrorCode,
  isApiError,
  normalizeTicker
};
